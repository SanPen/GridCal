# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import numpy as np
import pandas as pd
import timeit
from dataclasses import dataclass
from typing import Tuple, Union
from scipy import sparse as sp
from scipy.sparse import csc_matrix as csc
from scipy.sparse import lil_matrix

from GridCalEngine.Utils.Sparse.csc import diags
from GridCalEngine.Compilers.circuit_to_data import NumericalCircuit
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.common_functions import (compute_power, polar_to_rect)
from GridCalEngine.Simulations.OPF.opf_options import OptimalPowerFlowOptions
from GridCalEngine.enumerations import AcOpfMode
from GridCalEngine.basic_structures import Vec, CxVec, IntVec, Logger, csr_matrix, csc_matrix
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.common_functions import get_Sf, get_St
from GridCalEngine.Simulations.OPF.NumericalMethods.newton_raphson_ips_fx import IpsSolution


@dataclass
class NonlinearOPFResults:
    """
    Numerical non linear OPF results
    """
    Va: Vec = None
    Vm: Vec = None
    S: CxVec = None
    Sf: CxVec = None
    St: CxVec = None
    loading: Vec = None
    Pg: Vec = None
    Qg: Vec = None
    Qsh: Vec = None
    Pcost: Vec = None
    tap_module: Vec = None
    tap_phase: Vec = None
    hvdc_Pf: Vec = None
    hvdc_loading: Vec = None
    lam_p: Vec = None
    lam_q: Vec = None
    sl_sf: Vec = None
    sl_st: Vec = None
    sl_vmax: Vec = None
    sl_vmin: Vec = None
    nodal_capacity: Vec = None
    error: float = None
    converged: bool = None
    iterations: int = None

    def initialize(self, nbus: int, nbr: int, nsh: int, ng: int, nhvdc: int, ncap: int):
        """
        Initialize the arrays
        :param nbus: number of buses
        :param nbr: number of branches
        :param nsh: number of controllable shunt elements
        :param ng: number of generators
        :param nhvdc: number of HVDC
        :param ncap: Number of nodal capacity nodes
        """
        self.Va: Vec = np.zeros(nbus)
        self.Vm: Vec = np.zeros(nbus)
        self.S: CxVec = np.zeros(nbus, dtype=complex)
        self.Sf: CxVec = np.zeros(nbr, dtype=complex)
        self.St: CxVec = np.zeros(nbr, dtype=complex)
        self.loading: Vec = np.zeros(nbr)
        self.Pg: Vec = np.zeros(ng)
        self.Qg: Vec = np.zeros(ng)
        self.Qsh: Vec = np.zeros(nsh)
        self.Pcost: Vec = np.zeros(ng)
        self.tap_module: Vec = np.zeros(nbr)
        self.tap_phase: Vec = np.zeros(nbr)
        self.hvdc_Pf: Vec = np.zeros(nhvdc)
        self.hvdc_loading: Vec = np.zeros(nhvdc)
        self.lam_p: Vec = np.zeros(nbus)
        self.lam_q: Vec = np.zeros(nbus)
        self.sl_sf: Vec = np.zeros(nbr)
        self.sl_st: Vec = np.zeros(nbr)
        self.sl_vmax: Vec = np.zeros(nbus)
        self.sl_vmin: Vec = np.zeros(nbus)
        self.nodal_capacity: Vec = np.zeros(ncap)
        self.error: float = 0.0
        self.converged: bool = False
        self.iterations: int = 0

    def merge(self,
              other: "NonlinearOPFResults",
              bus_idx: IntVec,
              br_idx: IntVec,
              il_idx: IntVec,
              gen_idx: IntVec,
              hvdc_idx: IntVec,
              ncap_idx: IntVec,
              contshunt_idx: IntVec,
              acopf_mode):
        """

        :param other:
        :param bus_idx:
        :param br_idx:
        :param il_idx:
        :param gen_idx:
        :param hvdc_idx:
        :param ncap_idx:
        :param contshunt_idx:
        :param acopf_mode:
        :return:
        """
        self.Va[bus_idx] = other.Va
        self.Vm[bus_idx] = other.Vm
        self.S[bus_idx] = other.S
        self.Sf[br_idx] = other.Sf
        self.St[br_idx] = other.St
        self.loading[br_idx] = other.loading
        self.Pg[gen_idx] = other.Pg
        self.Qg[gen_idx] = other.Qg
        self.Qsh[contshunt_idx] = other.Qsh
        self.Pcost[gen_idx] = other.Pcost
        self.tap_module[br_idx] = other.tap_module
        self.tap_phase[br_idx] = other.tap_phase
        self.hvdc_Pf[hvdc_idx] = other.hvdc_Pf
        self.hvdc_loading[hvdc_idx] = other.hvdc_loading
        self.lam_p[bus_idx] = other.lam_p
        self.lam_q[bus_idx] = other.lam_q

        if ncap_idx is not None:
            self.nodal_capacity[ncap_idx] = other.nodal_capacity

        if acopf_mode == AcOpfMode.ACOPFslacks:
            self.sl_sf[il_idx] = other.sl_sf
            self.sl_st[il_idx] = other.sl_st
            self.sl_vmax[bus_idx] = other.sl_vmax
            self.sl_vmin[bus_idx] = other.sl_vmin
        self.error: float = 0.0
        self.converged: bool = False
        self.iterations: int = 0

    @property
    def V(self) -> CxVec:
        """
        Complex voltage
        :return: CxVec
        """
        return self.Vm * np.exp(1j * self.Va)


class NonLinearOptimalPfProblem:

    def __init__(self,
                 nc: NumericalCircuit,
                 options: OptimalPowerFlowOptions,
                 logger: Logger,
                 pf_init: bool = True,
                 Sbus_pf: Union[CxVec, None] = None,
                 voltage_pf: Union[CxVec, None] = None,
                 optimize_nodal_capacity: bool = False,
                 nodal_capacity_sign: float = 1.0,
                 capacity_nodes_idx: Union[IntVec, None] = None,
                 ):

        self.options = options
        self.nc = nc
        self.logger = logger
        self.optimize_nodal_capacity = optimize_nodal_capacity
        self.capacity_nodes_idx = capacity_nodes_idx
        self.nodal_capacity_sign = nodal_capacity_sign
        self.results = NonlinearOPFResults()

        # Parameters

        self.Sbase = nc.Sbase
        self.from_idx = nc.passive_branch_data.F
        self.to_idx = nc.passive_branch_data.T
        self.indices = nc.get_simulation_indices(Sbus=Sbus_pf)
        self.slack = self.indices.vd
        self.slackgens = np.where(self.nc.generator_data.get_bus_indices() == self.slack)[0]

        self.Sd = - nc.load_data.get_injections_per_bus() / self.Sbase

        if optimize_nodal_capacity:
            self.Pg_max = nc.generator_data.p / self.Sbase
            self.Pg_min = nc.generator_data.p / self.Sbase
        else:
            self.Pg_max = nc.generator_data.pmax / self.Sbase
            self.Pg_min = nc.generator_data.pmin / self.Sbase

        self.Pg_max[self.slackgens] = nc.generator_data.pmax[self.slackgens] / self.Sbase
        self.Pg_min[self.slackgens] = nc.generator_data.pmin[self.slackgens] / self.Sbase
        self.Qg_max = nc.generator_data.qmax / self.Sbase
        self.Qg_min = nc.generator_data.qmin / self.Sbase

        self.ngen = len(self.Pg_max)

        # Shunt elements are treated as generators with fixed P.
        # As such, their limits are added in the generator limits array.

        self.id_sh = np.where(nc.shunt_data.controllable == True)[0]
        self.sh_bus_idx = nc.shunt_data.get_bus_indices()[self.id_sh]
        self.nsh = len(self.id_sh)

        # Since controllable shunts will be treated as generators, we deactivate them to avoid its computation in the
        # Admittance matrix. Then, the admittance elements are stored.

        nc.shunt_data.Y[
            self.id_sh] = 0 + 0j  # TODO: this modifies the original data, better to make a copy of Y for shunts
        self.admittances = nc.get_admittance_matrices()

        self.Qsh_max = nc.shunt_data.qmax[self.id_sh] / self.Sbase
        self.Qsh_min = nc.shunt_data.qmin[self.id_sh] / self.Sbase

        self.Pg_max = np.r_[self.Pg_max, np.zeros(self.nsh)]
        self.Pg_min = np.r_[self.Pg_min, np.zeros(self.nsh)]

        self.Qg_max = np.r_[self.Qg_max, self.Qsh_max]
        self.Qg_min = np.r_[self.Qg_min, self.Qsh_min]

        self.Vm_max = nc.bus_data.Vmax
        self.Vm_min = nc.bus_data.Vmin

        self.id_Vm_min0 = np.where(self.Vm_min == 0)[0]

        if len(self.id_Vm_min0) != 0:
            for i in self.id_Vm_min0:
                self.logger.add_warning('Lower voltage limits are set to 0. Correcting to 0.9 p.u.',
                                        device="Bus " + str(i))
                self.Vm_min[self.id_Vm_min0] = 0.9

        self.id_Vm_max0 = np.where(self.Vm_max < self.Vm_min)[0]

        if len(self.id_Vm_max0) != 0:
            for i in self.id_Vm_max0:
                self.logger.add_warning('Upper voltage limits are set lower to the lower limit. Correcting to 1.1 p.u.',
                                        device="Bus " + str(i))
                self.Vm_max[self.id_Vm_max0] = 1.1

        self.pf = nc.generator_data.pf
        self.tanmax = ((1 - self.pf ** 2) ** (1 / 2)) / (self.pf + 1e-15)

        self.pv = np.flatnonzero(self.Vm_max == self.Vm_min)
        self.pq = np.flatnonzero(self.Vm_max != self.Vm_min)

        # Check the active elements and their operational limits.
        self.nbr = nc.passive_branch_data.nelm
        self.br_idx = np.arange(self.nbr)
        self.br_mon_idx = nc.passive_branch_data.get_monitor_enabled_indices()
        self.gen_disp_idx = np.r_[
            nc.generator_data.get_dispatchable_active_indices(),
            np.arange(self.ngen, self.ngen + self.nsh)
        ]
        self.Cfmon = nc.passive_branch_data.monitored_Cf(self.br_mon_idx)
        self.Cfmon_t = self.Cfmon.T
        self.Ctmon = nc.passive_branch_data.monitored_Ct(self.br_mon_idx)
        self.Ctmon_t = self.Ctmon.T

        self.k_m = self.indices.k_m
        self.k_tau = self.indices.k_tau
        self.k_mtau = self.indices.k_mtau
        self.R = nc.passive_branch_data.R
        self.X = nc.passive_branch_data.X

        # Sizing of the problem
        self.nbus = nc.bus_data.nbus
        self.n_slack = len(self.slack)
        self.ntapm = len(self.k_m)
        self.ntapt = len(self.k_tau)
        self.npv = len(self.pv)
        self.npq = len(self.pq)
        self.n_br_mon = len(self.br_mon_idx)
        self.n_gen_disp_sh = len(self.gen_disp_idx)
        self.n_gen_disp = self.n_gen_disp_sh - self.nsh
        gen_disp_idx_2 = self.gen_disp_idx[:self.n_gen_disp]

        self.ind_gens = np.arange(len(self.Pg_max))
        self.gen_nondisp_idx = nc.generator_data.get_non_dispatchable_indices()
        self.gen_bus_idx = np.r_[self.nc.generator_data.get_bus_indices(), self.sh_bus_idx]
        self.Sg_undis = (nc.generator_data.get_injections() / self.Sbase)[self.gen_nondisp_idx]
        self.rates = nc.passive_branch_data.rates / self.Sbase  # Line loading limits. If the grid is not well conditioned, add constant value (i.e. +100)
        self.rates2 = np.power(self.rates[self.br_mon_idx], 2.0)
        self.Va_max = nc.bus_data.angle_max  # This limits are not really used as of right now.
        self.Va_min = nc.bus_data.angle_min

        # Relevant ids
        self.Ybus_indptr = self.admittances.Ybus.indptr
        self.Ybus_cols, self.Ybus_indices = self.admittances.Ybus.nonzero()

        # positions of the diagonal in the CSC scheme
        self.Ybus_diag_pos = np.where(self.Ybus_indices == self.Ybus_cols)[0]

        # TODO: Maybe an opportunity to use some sort of function so this is clearer?
        self.Cdispgen = csc_matrix((np.ones(self.n_gen_disp_sh),
                                    (self.gen_bus_idx[self.gen_disp_idx],
                                     np.arange(self.n_gen_disp_sh))),
                                   shape=(self.nbus, self.n_gen_disp_sh))
        self.Cdispgen_t = self.Cdispgen.T

        self.Inom = nc.generator_data.snom[self.gen_disp_idx] / self.Sbase

        self.c0 = np.r_[nc.generator_data.cost_0[gen_disp_idx_2], np.zeros(self.nsh)]
        self.c1 = np.r_[nc.generator_data.cost_1[gen_disp_idx_2], np.zeros(self.nsh)]
        self.c2 = np.r_[nc.generator_data.cost_2[gen_disp_idx_2], np.zeros(self.nsh)]

        self.c0n = nc.generator_data.cost_0[self.gen_nondisp_idx]
        self.c1n = nc.generator_data.cost_1[self.gen_nondisp_idx]
        self.c2n = nc.generator_data.cost_2[self.gen_nondisp_idx]

        # Transformer operational limits
        self.tapm_max = nc.active_branch_data.tap_module_max[self.k_m]
        self.tapm_min = nc.active_branch_data.tap_module_min[self.k_m]
        self.tapt_max = nc.active_branch_data.tap_angle_max[self.k_tau]
        self.tapt_min = nc.active_branch_data.tap_angle_min[self.k_tau]

        # We grab all tapm even when uncontrolled since the indexing is needed
        self.all_tap_m = nc.active_branch_data.tap_module
        # if the tapt of the same trafo is variable.
        # We grab all tapt even when uncontrolled since the indexing is needed if
        self.all_tap_tau = nc.active_branch_data.tap_angle
        # the tapm of the same trafo is variable.

        # TODO: Simplify this using a method in the hvdc_data class
        self.hvdc_nondisp_idx = np.where(nc.hvdc_data.dispatchable == 0)[0]
        self.hvdc_disp_idx = np.where(nc.hvdc_data.dispatchable == 1)[0]

        self.f_nd_hvdc = nc.hvdc_data.F[self.hvdc_nondisp_idx]
        self.t_nd_hvdc = nc.hvdc_data.T[self.hvdc_nondisp_idx]
        self.Pf_nondisp = nc.hvdc_data.Pset[self.hvdc_nondisp_idx]

        self.n_disp_hvdc = len(self.hvdc_disp_idx)
        self.f_disp_hvdc = nc.hvdc_data.F[self.hvdc_disp_idx]
        self.t_disp_hvdc = nc.hvdc_data.T[self.hvdc_disp_idx]
        self.P_hvdc_max = nc.hvdc_data.rates[self.hvdc_disp_idx]

        if options.acopf_mode == AcOpfMode.ACOPFslacks:
            self.nsl = 2 * self.npq + 2 * self.n_br_mon
            # Slack relaxations for constraints

            # Cost squared since the slack is also squared
            self.c_s = np.power(nc.passive_branch_data.overload_cost[self.br_mon_idx] + 0.1, 1.0)  # TODO power of 1???
            self.c_v = nc.bus_data.cost_v[self.pq] + 0.1

        else:
            self.nsl = 0
            self.c_s = np.zeros(0)
            self.c_v = np.zeros(0)

        if optimize_nodal_capacity:
            self.nslcap = len(capacity_nodes_idx)
            self.slcap0 = np.zeros(self.nslcap)

        else:
            self.nslcap = 0
            self.slcap0 = np.zeros(0)

        self.neq = 2 * self.nbus + self.n_slack + self.npv

        if options.ips_control_q_limits:
            self.nineq = (2 * self.n_br_mon + 2 * self.npq + self.n_gen_disp + 4 * self.n_gen_disp_sh + 2 * self.ntapm
                          + 2 * self.ntapt + 2 * self.n_disp_hvdc + self.nsl)
        else:
            # No Reactive constraint (power curve)
            self.nineq = (2 * self.n_br_mon + 2 * self.npq + 4 * self.n_gen_disp_sh + 2 * self.ntapm + 2 * self.ntapt
                          + 2 * self.n_disp_hvdc + self.nsl)

        # Variables

        if pf_init:

            # TODO: try to substitute by using nc.generator_data.get_injections_per_bus()
            #  @Carlos: get_injections does not account for the powerflow results

            # This array has the number of total generators connected to the same bus of each generator, counting itself
            ngenforgen = np.bincount(self.gen_bus_idx[:self.ngen])[self.gen_bus_idx[:self.ngen]]

            # If there are multiple generators connected to the same bus, they share in equal parts the injection.
            allPgen = (Sbus_pf.real / self.Sbase + self.Sd.real)[self.gen_bus_idx[:self.ngen]] / ngenforgen

            # Same for Q
            allQgen = (Sbus_pf.imag / self.Sbase + self.Sd.imag)[self.gen_bus_idx[:self.ngen]] / ngenforgen

            self.Sg_undis = allPgen[self.gen_nondisp_idx] + 1j * allQgen[self.gen_nondisp_idx]
            self.Pg = np.r_[allPgen[gen_disp_idx_2], np.zeros(self.nsh)]
            self.Qg = np.r_[allQgen[gen_disp_idx_2], np.zeros(self.nsh)]
            self.Vm = np.abs(voltage_pf)
            self.Va = np.angle(voltage_pf)
            self.tap_m = nc.active_branch_data.tap_module[self.k_m]
            self.tap_tau = nc.active_branch_data.tap_angle[self.k_tau]
            self.Pfdc = nc.hvdc_data.Pset[self.hvdc_disp_idx]

        else:

            # TODO: Unresolved Pmax, ie Pmax and Pmin must be in __init__
            self.Pg = np.r_[
                (self.Pmax[gen_disp_idx_2] + self.Pmin[gen_disp_idx_2]) / (2 * self.Sbase),
                np.zeros(self.nsh)
            ]
            self.Qg = np.r_[
                (self.Qg_max[gen_disp_idx_2] +  self.Qg_min[gen_disp_idx_2]) / (2 * self.Sbase),
                np.zeros(self.nsh)
            ]
            self.Va = np.angle(nc.bus_data.Vbus)
            self.Vm = (self.Vm_max + self.Vm_min) / 2
            self.tap_m = nc.active_branch_data.tap_module[self.k_m]
            self.tap_tau = nc.active_branch_data.tap_angle[self.k_tau]
            self.Pfdc = np.zeros(self.n_disp_hvdc)

        if options.acopf_mode == AcOpfMode.ACOPFslacks:
            self.sl_sf = np.ones(self.n_br_mon)
            self.sl_st = np.ones(self.n_br_mon)
            self.sl_vmax = np.ones(self.npq)
            self.sl_vmin = np.ones(self.npq)
        else:
            self.sl_sf = np.zeros(0)
            self.sl_st = np.zeros(0)
            self.sl_vmax = np.zeros(0)
            self.sl_vmin = np.zeros(0)

        if optimize_nodal_capacity:
            self.slcap = np.zeros(self.nslcap)
        else:
            self.slcap = np.zeros(0)

        self.x0 = self.var2x()
        self.NV = len(self.x0)

        # Predefine some global electrical variable
        self.V = polar_to_rect(self.Vm, self.Va)
        self.Scalc = compute_power(self.admittances.Ybus, self.V)

        self.allSf = get_Sf(k=self.br_idx, Vm=self.Vm, V=self.V,
                            yff=self.admittances.yff, yft=self.admittances.yft,
                            F=self.from_idx, T=self.to_idx)

        self.allSt = get_St(k=self.br_idx, Vm=self.Vm, V=self.V,
                            ytf=self.admittances.ytf, ytt=self.admittances.ytt,
                            F=self.from_idx, T=self.to_idx)

        self.Sf = self.allSf[self.br_mon_idx]
        self.St = self.allSt[self.br_mon_idx]

        self.Sf2 = np.conj(self.Sf) * self.Sf
        self.St2 = np.conj(self.St) * self.St

        # Predefine the objective function

    def var2x(self) -> Vec:
        return np.r_[
            self.Va,
            self.Vm,
            self.Pg,
            self.Qg,
            self.sl_sf,
            self.sl_st,
            self.sl_vmax,
            self.sl_vmin,
            self.slcap,
            self.tap_m,
            self.tap_tau,
            self.Pfdc,
        ]

    def x2var(self, x: Vec):
        a = 0
        b = self.nbus

        self.Va = x[a: b]
        a = b
        b += self.nbus

        self.Vm = x[a: b]
        a = b
        b += self.n_gen_disp

        self.Pg = x[a: b]
        a = b
        b += self.n_gen_disp

        self.Qg = x[a: b]
        a = b

        if self.options.acopf_mode == AcOpfMode.ACOPFslacks:
            b += self.n_br_mon

            self.sl_sf = x[a: b]
            a = b
            b += self.n_br_mon

            self.sl_st = x[a: b]
            a = b
            b += self.npq

            self.sl_vmax = x[a: b]
            a = b
            b += self.npq

            self.sl_vmin = x[a: b]
            a = b
            b += self.nslcap

        else:
            b += self.nslcap
            # Create empty arrays for not used variables
            self.sl_sf = np.zeros(0)
            self.sl_st = np.zeros(0)
            self.sl_vmax = np.zeros(0)
            self.sl_vmin = np.zeros(0)

        self.slcap = x[a:b]
        a = b
        b += self.ntapm

        self.tap_m = x[a: b]
        a = b
        b += self.ntapt

        self.tap_tau = x[a: b]
        a = b
        b += self.n_disp_hvdc

        self.Pfdc = x[a: b]

    def update(self, x: Vec) -> Tuple[Vec, Vec, Vec]:

        # Set the new values for the variables.
        self.x2var(x)

        # Update the admittances matrices in case there are changes to the taps
        if self.ntapm + self.ntapt != 0:

            prev_all_tap_m = self.all_tap_m.copy()
            prev_all_tap_tau = self.all_tap_tau.copy()
            self.all_tap_m[self.k_m] = self.tap_m
            self.all_tap_tau[self.k_tau] = self.tap_tau

            self.admittances.modify_taps(m=prev_all_tap_m,
                                         m2=self.all_tap_m,
                                         tau=prev_all_tap_tau,
                                         tau2=self.all_tap_tau)

        else:
            pass

        # Compute the electrical balance
        self.V = polar_to_rect(self.Vm, self.Va)
        self.Scalc = compute_power(self.admittances.Ybus, self.V)

        Pgen = np.zeros(self.nbus)
        Qgen = np.zeros(self.nbus)
        np.add.at(Pgen, self.gen_bus_idx[self.gen_disp_idx], self.Pg)  # Variable generation
        np.add.at(Pgen, self.gen_bus_idx[self.gen_nondisp_idx], self.Sg_undis.real)  # Variable generation
        np.add.at(Qgen, self.gen_bus_idx[self.gen_disp_idx], self.Qg)  # Fixed generation
        np.add.at(Qgen, self.gen_bus_idx[self.gen_nondisp_idx], self.Sg_undis.imag)  # Fixed generation

        dS = self.Scalc + self.Sd - Pgen - 1j * Qgen  # Nodal power balance

        if self.nslcap != 0:
            dS[self.capacity_nodes_idx] -= self.slcap  # Nodal capacity slack generator addition

        for link in range(self.n_disp_hvdc):
            dS[self.f_disp_hvdc[link]] += self.Pfdc[link]  # Variable DC links. Lossless model (Pdc_From = Pdc_To)
            dS[self.t_disp_hvdc[link]] -= self.Pfdc[link]

        for nd_link in range(len(self.hvdc_nondisp_idx)):
            dS[self.f_nd_hvdc[nd_link]] += self.Pf_nondisp[nd_link]  # Fixed DC links
            dS[self.t_nd_hvdc[nd_link]] -= self.Pf_nondisp[nd_link]

        self.allSf = get_Sf(k=self.br_idx, Vm=self.Vm, V=self.V,
                            yff=self.admittances.yff, yft=self.admittances.yft,
                            F=self.from_idx, T=self.to_idx, )
        self.allSt = get_St(k=self.br_idx, Vm=self.Vm, V=self.V,
                            ytf=self.admittances.ytf, ytt=self.admittances.ytt,
                            F=self.from_idx, T=self.to_idx, )

        self.Sf = self.allSf[self.br_mon_idx]
        self.St = self.allSt[self.br_mon_idx]

        self.Sf2 = np.conj(self.Sf) * self.Sf
        self.St2 = np.conj(self.St) * self.St

        fval = 1e-4 * (
                np.sum((self.c0 + self.c1 * self.Pg * self.Sbase + self.c2 * np.power(self.Pg * self.Sbase, 2)))
                + np.sum(self.c_s * (self.sl_sf + self.sl_st)) + np.sum(self.c_v * (self.sl_vmax + self.sl_vmin))
                + np.sum(self.nodal_capacity_sign * self.slcap))

        gval = np.r_[dS.real, dS.imag, self.Va[self.slack], self.Vm[self.pv] - self.Vm_max[self.pv]]

        if self.options.acopf_mode == AcOpfMode.ACOPFslacks:

            sl_sf = self.sl_sf
            sl_st = self.sl_st
            sl_vmax = self.sl_vmax
            sl_vmin = self.sl_vmin
        else:
            sl_sf = np.zeros(self.n_br_mon)
            sl_st = np.zeros(self.n_br_mon)
            sl_vmax = np.zeros(self.nbus)
            sl_vmin = np.zeros(self.nbus)

        if self.options.ips_control_q_limits:  # if reactive power control...
            v_g = self.Vm[self.gen_bus_idx[self.gen_disp_idx]]
            ctrlq_ineq = (np.power(self.Qg[:self.ngen], 2.0)
                          + np.power(self.Pg[:self.ngen], 2.0)
                          - np.power(v_g * self.Inom, 2.0))
        else:
            ctrlq_ineq = np.zeros(0)

        if self.n_disp_hvdc != 0:
            hvdc_ineq1 = self.Pfdc - self.P_hvdc_max
            hvdc_ineq2 = - self.P_hvdc_max - self.Pfdc
        else:
            hvdc_ineq1 = np.zeros(0)
            hvdc_ineq2 = np.zeros(0)

        hval = np.r_[
            self.Sf2.real - self.rates2 - sl_sf,  # rates "lower limit"
            self.St2.real - self.rates2 - sl_st,  # rates "upper limit"
            self.Vm[self.pq] - self.Vm_max[self.pq] - sl_vmax,  # voltage module upper limit
            self.Pg - self.Pg_max[self.gen_disp_idx],  # generator P upper limits
            self.Qg - self.Qg_max[self.gen_disp_idx],  # generator Q upper limits
            self.Vm_min[self.pq] - self.Vm[self.pq] - sl_vmin,  # voltage module lower limit
            self.Pg_min[self.gen_disp_idx] - self.Pg,  # generator P lower limits
            self.Qg_min[self.gen_disp_idx] - self.Qg,  # generation Q lower limits
            - self.sl_sf,  # Slack variable for Sf >0
            - self.sl_st,  # Slack variable for St >0
            - self.sl_vmax,  # Slack variable for Vmax >0
            - self.sl_vmin,  # Slack variable for Vmin >0
            self.tap_m - self.tapm_max,  # Tap module upper bound
            self.tapm_min - self.tap_m,  # Tap module lower bound
            self.tap_tau - self.tapt_max,  # Tap module lower bound
            self.tapt_min - self.tap_tau,  # Tap phase lower bound
            ctrlq_ineq,
            hvdc_ineq1,
            hvdc_ineq2
        ]

        return fval, gval, hval

    def get_jacobians_and_hessians(self, mu: Vec, lam: Vec, compute_hessians: bool) -> Tuple[
        Vec, csc_matrix, csc_matrix,
        csc_matrix, csc_matrix, csc_matrix]:
        """

        TODO: we should split this function into functions outside the class, that should make it more manageable
              one for each of these: fx, Gx, Hx, fxx, Gxx, Hxx, and leave this function just to call them

        :param mu:
        :param lam:
        :param compute_hessians:
        :return:
        """

        # Number of variables of the typical power flow (V, th, P, Q). Used to ease readability
        npfvar = 2 * self.nbus + 2 * self.n_gen_disp_sh

        if self.options.ips_control_q_limits:  # if reactive power control...
            nqct = self.n_gen_disp
        else:
            nqct = 0

        Vmat = diags(self.V)
        vm_inv = diags(1 / self.Vm)
        E = Vmat @ vm_inv
        Ibus = self.admittances.Ybus @ self.V

        # Useful pre-constructed matrices:
        diags_gensh_disp_ones = diags(np.ones(self.n_gen_disp_sh))
        diags_bus_ones = diags(np.ones(self.nbus))
        diags_pq_ones = diags(np.ones(self.npq))
        diags_disp_hvdc_ones = diags(np.ones(self.n_disp_hvdc))
        diags_br_mon_ones = diags(np.ones(self.n_br_mon))

        # OBJECTIVE FUNCTION GRAD --------------------------------------------------------------------------------------
        ts_fx = timeit.default_timer()
        fx = np.zeros(self.NV)

        if self.nslcap == 0:
            fx[2 * self.nbus: 2 * self.nbus + self.n_gen_disp_sh] = (2 * self.c2 * self.Pg * (self.Sbase * self.Sbase)
                                                                     + self.c1 * self.Sbase) * 1e-4

            if self.options.acopf_mode == AcOpfMode.ACOPFslacks:
                fx[npfvar: npfvar + self.n_br_mon] = self.c_s
                fx[npfvar + self.n_br_mon: npfvar + 2 * self.n_br_mon] = self.c_s
                fx[npfvar + 2 * self.n_br_mon: npfvar + 2 * self.n_br_mon + self.npq] = self.c_v
                fx[npfvar + 2 * self.n_br_mon + self.npq: npfvar + 2 * self.n_br_mon + 2 * self.npq] = self.c_v
        else:
            fx[npfvar + self.nsl: npfvar + self.nsl + self.nslcap] = self.nodal_capacity_sign

        te_fx = timeit.default_timer()
        # EQUALITY CONSTRAINTS GRAD ------------------------------------------------------------------------------------
        """
        The following comments illustrate the shapes of the equality constraints gradients:
        Gx = 
            NV
        +---------+
        | GS.real | N 
        +---------+
        | GS.imag | N 
        +---------+
        | GTH     | nslack
        +---------+
        | Gvm     | npv
        +---------+

        where Gx has shape (N + N + nslack + npv, N + N + Ng + Ng + nsl + ntapm + ntapt + ndc), where nslack is
        the number of slack buses, and nsl the number of slack variables.
        Each submatrix is composed as:

        GS = 
            N     N      Ng     Ng      nsl     ntapm    ntapt    ndc
        +------+------+------+------+---------+--------+--------+------+
        | GSva | GSvm | GSpg | GSqg | GSslack | GStapm | GStapt | GSdc | N
        +------+------+------+------+---------+--------+--------+------+

        GTH = 
           N      N    Ng    Ng    nsl  ntapm ntapt  ndc
        +------+-----+-----+-----+-----+-----+-----+-----+
        | GTHx |  0  |  0  |  0  |  0  |  0  |  0  |  0  |
        +------+-----+-----+-----+-----+-----+-----+-----+

        Gvm = 

           N     N     Ng    Ng    nsl  ntapm ntapt  ndc
        +-----+------+-----+-----+-----+-----+-----+-----+
        |  0  | Gvmx |  0  |  0  |  0  |  0  |  0  |  0  |
        +-----+------+-----+-----+-----+-----+-----+-----+

        """

        ts_gx = timeit.default_timer()

        dataYbus_Vmat = self.admittances.Ybus.data * self.V[self.Ybus_cols]

        # GSvm = Vmat @ (np.conj(diags(Ibus)) + np.conj(self.admittances.Ybus @ Vmat)) @ vm_inv  # N x N matrix
        data = dataYbus_Vmat.copy()
        np.add.at(data, self.Ybus_diag_pos, Ibus)
        GSvm = csc_matrix((np.conj(data) * (1 / self.Vm)[self.Ybus_cols]
                           * self.V[self.Ybus_indices], self.Ybus_indices, self.Ybus_indptr),
                          shape=(self.nbus, self.nbus))

        # GSva = 1j * Vmat @ (np.conj(diags(Ibus)) - np.conj(self.admittances.Ybus @ Vmat))
        data = - dataYbus_Vmat.copy()
        np.add.at(data, self.Ybus_diag_pos, Ibus)
        GSva = csc_matrix((np.conj(data) * 1j * self.V[self.Ybus_indices], self.Ybus_indices, self.Ybus_indptr),
                          shape=(self.nbus, self.nbus))

        GSpg = - self.Cdispgen
        GSqg = -1j * self.Cdispgen

        # TODO: This is subject to a CSC function
        GTH = lil_matrix((len(self.slack), self.NV))
        for i, ss in enumerate(self.slack):
            GTH[i, ss] = 1.

        # TODO: This is subject to a CSC function
        Gvm = lil_matrix((len(self.pv), self.NV))
        for i, ss in enumerate(self.pv):
            Gvm[i, self.nbus + ss] = 1.

        dSbusdm, dSfdm, dStdm, dSbusdt, dSfdt, dStdt = self.compute_branch_power_derivatives()

        if self.ntapm > 0:
            # TODO: Do we really need a copy? I think a reference is enough here
            Gtapm = dSbusdm.copy()
        else:
            # TODO: Why not a csc directly?
            Gtapm = lil_matrix((self.nbus, self.ntapm), dtype=complex)

        if self.ntapt > 0:
            # TODO: Do we really need a copy? I think a reference is enough here
            Gtapt = dSbusdt.copy()
        else:
            Gtapt = lil_matrix((self.nbus, self.ntapt), dtype=complex)

        # TODO: There is a chance for a CSC function here
        GSpfdc = lil_matrix((self.nbus, self.n_disp_hvdc), dtype=complex)
        for k_link in range(self.n_disp_hvdc):
            GSpfdc[self.f_disp_hvdc[k_link], k_link] = 1.0  # TODO: check that this is correct
            GSpfdc[self.t_disp_hvdc[k_link], k_link] = -1.0  # TODO: check that this is correct

        # TODO: Why not a csc directly?
        Gslack = lil_matrix((self.nbus, self.nsl), dtype=complex)

        # TODO: There is a chance for a CSC function here
        Gslcap = lil_matrix((self.nbus, self.nslcap), dtype=complex)
        if self.nslcap != 0:
            for idslcap, capbus in enumerate(self.capacity_nodes_idx):
                Gslcap[capbus, idslcap] = -1

        GS = sp.hstack([GSva, GSvm, GSpg, GSqg, Gslack, Gslcap, Gtapm, Gtapt, GSpfdc])

        Gx = sp.vstack([GS.real, GS.imag, GTH, Gvm]).tocsc()

        te_gx = timeit.default_timer()

        # INEQUALITY CONSTRAINTS GRAD ----------------------------------------------------------------------------------

        """
        The following comments illustrate the shapes of the equality constraints gradients:

        Hx =
            NV
        +---------+
        | HSf     | M
        +---------+
        | HSt     | M
        +---------+
        | Hvu     | N
        +---------+
        | Hpu     | Ng
        +---------+
        | Hqu     | Ng
        +---------+
        | Hvl     | N
        +---------+
        | Hpl     | Ng
        +---------+
        | Hql     | Ng
        +---------+
        | Hslsf   | M
        +---------+
        | Hslst   | M
        +---------+
        | Hslvmax | npq
        +---------+
        | Hslvmin | npq
        +---------+
        | Htapmu  | ntapm
        +---------+
        | Htapml  | ntapm
        +---------+
        | Htaptu  | ntapt
        +---------+
        | Htaptl  | ntapt
        +---------+
        | Hqmax   | Ng (if ctQ==True), 0 else
        +---------+
        | Hdcu    | ndc
        +---------+
        | Hdcl    | ndc
        +---------+
        """
        ts_hx = timeit.default_timer()

        Yf_mon = self.admittances.Yf[self.br_mon_idx, :]
        Yt_mon = self.admittances.Yt[self.br_mon_idx, :]

        Vfmat = diags(self.V[self.nc.passive_branch_data.F[self.br_mon_idx]])
        Vtmat = diags(self.V[self.nc.passive_branch_data.T[self.br_mon_idx]])

        IfCJmat = np.conj(diags(Yf_mon @ self.V))
        ItCJmat = np.conj(diags(Yt_mon @ self.V))

        Sfmat = diags(self.Sf)
        Stmat = diags(self.St)

        # thisfitswell_Cf@E = csc(((self.V / self.Vm)[self.from_idx[self.br_mon_idx]], (self.br_idx[self.br_mon_idx],self.from_idx[self.br_mon_idx])), shape = (self.n_br_mon, self.nbus))

        Sfvm = IfCJmat @ self.Cfmon @ E + Vfmat @ np.conj(Yf_mon @ E)
        Stvm = ItCJmat @ self.Ctmon @ E + Vtmat @ np.conj(Yt_mon @ E)

        Sfva = 1j * (IfCJmat @ self.Cfmon @ Vmat - Vfmat @ np.conj(Yf_mon @ Vmat))
        Stva = 1j * (ItCJmat @ self.Ctmon @ Vmat - Vtmat @ np.conj(Yt_mon @ Vmat))

        Hpu = sp.hstack([lil_matrix((self.n_gen_disp_sh, 2 * self.nbus)), diags_gensh_disp_ones,
                         lil_matrix((self.n_gen_disp_sh, self.NV - 2 * self.nbus - self.n_gen_disp_sh))])
        Hpl = sp.hstack([lil_matrix((self.n_gen_disp_sh, 2 * self.nbus)), - diags_gensh_disp_ones,
                         lil_matrix((self.n_gen_disp_sh, self.NV - 2 * self.nbus - self.n_gen_disp_sh))])
        Hqu = sp.hstack(
            [lil_matrix((self.n_gen_disp_sh, 2 * self.nbus + self.n_gen_disp_sh)), diags_gensh_disp_ones,
             lil_matrix((self.n_gen_disp_sh, self.NV - 2 * self.nbus - 2 * self.n_gen_disp_sh))])
        Hql = sp.hstack(
            [lil_matrix((self.n_gen_disp_sh, 2 * self.nbus + self.n_gen_disp_sh)), - diags_gensh_disp_ones,
             lil_matrix((self.n_gen_disp_sh, self.NV - 2 * self.nbus - 2 * self.n_gen_disp_sh))])

        if self.options.acopf_mode == AcOpfMode.ACOPFslacks:

            Hvu = sp.hstack([lil_matrix((self.npq, self.nbus)), diags_bus_ones[self.pq, :],
                             lil_matrix((self.npq, 2 * self.n_gen_disp_sh + 2 * self.n_br_mon)),
                             - diags_pq_ones, lil_matrix(
                    (self.npq, self.npq + self.nslcap + self.ntapm + self.ntapt + self.n_disp_hvdc))])

            Hvl = sp.hstack(
                [lil_matrix((self.npq, self.nbus)), -diags_bus_ones[self.pq, :],
                 lil_matrix((self.npq, 2 * self.n_gen_disp_sh + 2 * self.n_br_mon + self.npq)),
                 - diags_pq_ones,
                 lil_matrix((self.npq, self.nslcap + self.ntapm + self.ntapt + self.n_disp_hvdc))])

            Hslsf = sp.hstack([lil_matrix((self.n_br_mon, npfvar)), - diags_br_mon_ones,
                               lil_matrix((self.n_br_mon,
                                           self.n_br_mon + 2 * self.npq + self.nslcap + self.ntapm + self.ntapt + self.n_disp_hvdc))])

            Hslst = sp.hstack([lil_matrix((self.n_br_mon, npfvar + self.n_br_mon)), - diags_br_mon_ones,
                               lil_matrix((self.n_br_mon,
                                           2 * self.npq + self.nslcap + self.ntapm + self.ntapt + self.n_disp_hvdc))])

            Hslvmax = sp.hstack([lil_matrix((self.npq, npfvar + 2 * self.n_br_mon)), - diags_pq_ones,
                                 lil_matrix(
                                     (self.npq,
                                      self.npq + self.nslcap + self.ntapm + self.ntapt + self.n_disp_hvdc))])

            Hslvmin = sp.hstack(
                [lil_matrix((self.npq, npfvar + 2 * self.n_br_mon + self.npq)), - diags_pq_ones,
                 lil_matrix((self.npq, self.nslcap + self.ntapm + self.ntapt + self.n_disp_hvdc))])

        else:
            Hvu = sp.hstack([lil_matrix((self.npq, self.nbus)), diags_pq_ones,
                             lil_matrix((self.npq, self.NV - self.nbus - self.npq))])
            Hvl = sp.hstack([lil_matrix((self.npq, self.nbus)), - diags_pq_ones,
                             lil_matrix((self.npq, self.NV - self.nbus - self.npq))])
            Hslsf = lil_matrix((0, self.NV))
            Hslst = lil_matrix((0, self.NV))
            Hslvmax = lil_matrix((0, self.NV))
            Hslvmin = lil_matrix((0, self.NV))

        if (self.ntapm + self.ntapt) != 0:

            Sftapm = dSfdm[self.br_mon_idx, :].copy()
            Sftapt = dSfdt[self.br_mon_idx, :].copy()
            Sttapm = dStdm[self.br_mon_idx, :].copy()
            Sttapt = dStdt[self.br_mon_idx, :].copy()

            SfX = sp.hstack(
                [Sfva, Sfvm, lil_matrix((self.n_br_mon, 2 * self.n_gen_disp_sh + self.nsl + self.nslcap)), Sftapm,
                 Sftapt,
                 lil_matrix((self.n_br_mon, self.n_disp_hvdc))])
            StX = sp.hstack(
                [Stva, Stvm, lil_matrix((self.n_br_mon, 2 * self.n_gen_disp_sh + self.nsl + self.nslcap)), Sttapm,
                 Sttapt,
                 lil_matrix((self.n_br_mon, self.n_disp_hvdc))])

            if self.options.acopf_mode == AcOpfMode.ACOPFslacks:

                # Equivalent to HSf = 2 * (Sfmat.real @ SfX.real + Sfmat.imag @ SfX.imag) + Hslsf

                HSfdata = self.Sf.real[SfX.row] * SfX.data.real + self.Sf.imag[SfX.row] * SfX.data.imag
                HSf = 2 * csc((HSfdata, (SfX.row, SfX.col)), shape=(self.n_br_mon, self.NV)) + Hslsf

                HStdata = self.St.real[SfX.row] * StX.data.real + self.St.imag[StX.row] * StX.data.imag
                HSt = 2 * csc((HStdata, (StX.row, StX.col)), shape=(self.n_br_mon, self.NV)) + Hslst

            else:

                # Equivalent to HSf = 2 * (Sfmat.real @ SfX.real + Sfmat.imag @ SfX.imag)

                HSfdata = self.Sf.real[SfX.row] * SfX.data.real + self.Sf.imag[SfX.row] * SfX.data.imag
                HSf = 2 * csc((HSfdata, (SfX.row, SfX.col)), shape=(self.n_br_mon, self.NV))

                HStdata = self.St.real[SfX.row] * StX.data.real + self.St.imag[StX.row] * StX.data.imag
                HSt = 2 * csc((HStdata, (StX.row, StX.col)), shape=(self.n_br_mon, self.NV))

            if self.ntapm != 0:
                Htapmu = sp.hstack(
                    [lil_matrix((self.ntapm, npfvar + self.nsl + self.nslcap)), diags(np.ones(self.ntapm)),
                     lil_matrix((self.ntapm, self.ntapt + self.n_disp_hvdc))])

                Htapml = sp.hstack(
                    [lil_matrix((self.ntapm, npfvar + self.nsl + self.nslcap)), diags(- np.ones(self.ntapm)),
                     lil_matrix((self.ntapm, self.ntapt + self.n_disp_hvdc))])

            else:
                Htapmu = lil_matrix((0, self.NV))
                Htapml = lil_matrix((0, self.NV))

            if self.ntapt != 0:
                Htaptu = sp.hstack(
                    [lil_matrix((self.ntapt, npfvar + self.nsl + self.nslcap + self.ntapm)),
                     diags(np.ones(self.ntapt)),
                     lil_matrix((self.ntapt, self.n_disp_hvdc))])
                Htaptl = sp.hstack([lil_matrix((self.ntapt, npfvar + self.nsl + self.nslcap + self.ntapm)),
                                    diags(- np.ones(self.ntapt)),
                                    lil_matrix((self.ntapt, self.n_disp_hvdc))])

            else:
                Htaptu = lil_matrix((0, self.NV))
                Htaptl = lil_matrix((0, self.NV))

        else:
            Sftapm = lil_matrix((self.n_br_mon, self.ntapm))
            Sttapm = lil_matrix((self.n_br_mon, self.ntapm))
            Sftapt = lil_matrix((self.n_br_mon, self.ntapt))
            Sttapt = lil_matrix((self.n_br_mon, self.ntapt))
            Htapmu = lil_matrix((self.ntapm, self.NV))
            Htapml = lil_matrix((self.ntapm, self.NV))
            Htaptu = lil_matrix((self.ntapt, self.NV))
            Htaptl = lil_matrix((self.ntapt, self.NV))

            SfX = sp.hstack(
                [Sfva, Sfvm,
                 lil_matrix((self.n_br_mon, 2 * self.n_gen_disp_sh + self.nsl + self.nslcap + self.n_disp_hvdc))])
            StX = sp.hstack(
                [Stva, Stvm,
                 lil_matrix((self.n_br_mon, 2 * self.n_gen_disp_sh + self.nsl + self.nslcap + self.n_disp_hvdc))])

            if self.options.acopf_mode == AcOpfMode.ACOPFslacks:

                # HSf = 2 * (Sfmat.real @ SfX.real + Sfmat.imag @ SfX.imag) + Hslsf
                # HSt = 2 * (Stmat.real @ StX.real + Stmat.imag @ StX.imag)

                HSfdata = self.Sf.real[SfX.row] * SfX.data.real + self.Sf.imag[SfX.row] * SfX.data.imag
                HSf = 2 * csc((HSfdata, (SfX.row, SfX.col)), shape=(self.n_br_mon, self.NV)) + Hslsf

                HStdata = self.St.real[SfX.row] * StX.data.real + self.St.imag[StX.row] * StX.data.imag
                HSt = 2 * csc((HStdata, (StX.row, StX.col)), shape=(self.n_br_mon, self.NV)) + Hslst

            else:

                # HSf = 2 * (Sfmat.real @ SfX.real + Sfmat.imag @ SfX.imag)
                # HSt = 2 * (Stmat.real @ StX.real + Stmat.imag @ StX.imag)

                HSfdata = self.Sf.real[SfX.row] * SfX.data.real + self.Sf.imag[SfX.row] * SfX.data.imag
                HSf = 2 * csc((HSfdata, (SfX.row, SfX.col)), shape=(self.n_br_mon, self.NV))

                HStdata = self.St.real[SfX.row] * StX.data.real + self.St.imag[StX.row] * StX.data.imag
                HSt = 2 * csc((HStdata, (StX.row, StX.col)), shape=(self.n_br_mon, self.NV))

        if self.options.ips_control_q_limits:  # if reactive power control...
            # tanmax curves (simplified capability curves of generators)
            Hqmaxp = 2 * self.Pg[:self.n_gen_disp_sh]
            Hqmaxq = 2 * self.Qg[:self.n_gen_disp_sh]
            # Hqmaxv = - 2 * diags(np.power(self.Inom, 2.0)) * self.Cdispgen_t @ diags(
            #     self.Vm)
            Hqmaxv_data = np.power(self.Inom, 2) * self.Vm[self.gen_bus_idx[self.gen_disp_idx]]
            Hqmaxv = csc((- 2 * Hqmaxv_data, (np.arange(self.n_gen_disp), self.gen_bus_idx[self.gen_disp_idx])),
                               shape=(self.n_gen_disp, self.nbus))

            Hqmax = sp.hstack(
                [lil_matrix((nqct, self.nbus)), Hqmaxv, diags(Hqmaxp), lil_matrix((nqct, self.nsh)), diags(Hqmaxq),
                 lil_matrix((nqct, self.nsh)),
                 lil_matrix((nqct, self.nsl + self.nslcap + self.ntapm + self.ntapt + self.n_disp_hvdc))])
        else:
            Hqmax = lil_matrix((nqct, self.NV))
            Hqmaxv = lil_matrix((nqct, self.nbus))

        Hdcu = sp.hstack(
            [lil_matrix((self.n_disp_hvdc, self.NV - self.n_disp_hvdc)), diags_disp_hvdc_ones])
        Hdcl = sp.hstack(
            [lil_matrix((self.n_disp_hvdc, self.NV - self.n_disp_hvdc)), - diags_disp_hvdc_ones])

        Hx = sp.vstack([HSf, HSt, Hvu, Hpu, Hqu, Hvl, Hpl, Hql, Hslsf, Hslst, Hslvmax,
                        Hslvmin, Htapmu, Htapml, Htaptu, Htaptl, Hqmax, Hdcu, Hdcl])

        Hx = Hx.tocsc()
        te_hx = timeit.default_timer()

        # HESSIANS ---------------------------------------------------------------------------------------------------------

        if compute_hessians:

            # OBJECTIVE FUNCTION HESS --------------------------------------------------------------------------------------
            ts_fxx = timeit.default_timer()
            if self.nslcap == 0:
                fxx = diags((np.r_[
                    np.zeros(2 * self.nbus),
                    2 * self.c2 * (self.Sbase * self.Sbase),
                    np.zeros(self.n_gen_disp_sh + self.nsl + self.nslcap + self.ntapm + self.ntapt + self.n_disp_hvdc)
                ]) * 1e-4).tocsc()
            else:
                fxx = csc((self.NV, self.NV))

            te_fxx = timeit.default_timer()
            # EQUALITY CONSTRAINTS HESS ------------------------------------------------------------------------------------
            '''
            The following matrix represents the structure of the hessian matrix for the equality constraints

                         N         N         Ng        Ng       nsl       ntapm       ntapt       ndc
                    +---------+---------+---------+---------+---------+-----------+-----------+----------+
               N    |  Gvava  |  Gvavm  |  Gvapg  |  Gvaqg  |  Gvasl  |  Gvatapm  |  Gvatapt  |  Gvapdc  |
                    +---------+---------+---------+---------+---------+-----------+-----------+----------+
               N    |  Gvmva  |  Gvmvm  |  Gvmpg  |  Gvmqg  |  Gvmsl  |  Gvmtapm  |  Gvmtapt  |  Gvmpdc  |
                    +---------+---------+---------+---------+---------+-----------+-----------+----------+
               Ng   |  Gpgva  |  Gpgvm  |  Gpgpg  |  Gpgqg  |  Gpgsl  |  Gpgtapm  |  Gpgtapt  |  Gpgpdc  |
                    +---------+---------+---------+---------+---------+-----------+-----------+----------+
               Ng   |  Gqgva  |  Gqgvm  |  Gqgpg  |  Gqgqg  |  Gqgsl  |  Gqgtapm  |  Gqgtapt  |  Gqgpdc  |
                    +---------+---------+---------+---------+---------+-----------+-----------+----------+
               nsl  |  Gslva  |  Gslvm  |  Gslpg  |  Gslqg  |  Gslsl  |  Gsltapm  |  Gsltapt  |  Gslpdc  |
                    +---------+---------+---------+---------+---------+-----------+-----------+----------+
              ntapm | Gtapmva | Gtapmvm | Gtapmpg | Gtapmqg | Gtapmsl | Gtapmtapm | Gtapmtapt | Gtapmpdc |
                    +---------+---------+---------+---------+---------+-----------+-----------+----------+
              ntapt | Gtaptva | Gtaptvm | Gtaptpg | Gtaptqg | Gtaptsl | Gtapttapm | Gtapttapt | Gtaptpdc |
                    +---------+---------+---------+---------+---------+-----------+-----------+----------+
               ndc  | Gpdcva  | Gpdcvm  | Gpdcpg  | Gpdcqg  | Gpdcsl  | Gpdctapm  | Gpdctapt  | Gpdcpdc  |
                    +---------+---------+---------+---------+---------+-----------+-----------+----------+

            
            '''
            ts_gxx = timeit.default_timer()
            # P
            lam_p = lam[0: self.nbus]
            lam_diag_p = diags(lam_p)

            # B_p = np.conj(self.admittances.Ybus @ Vmat)
            data = self.admittances.Ybus.data * self.V[self.Ybus_indices]
            B_p = csc_matrix((np.conj(data), self.Ybus_indices, self.Ybus_indptr),
                             shape=(self.nbus, self.nbus)).transpose()

            # D_p = np.conj(self.admittances.Ybus).T @ Vmat
            data = np.conj(self.admittances.Ybus.data) * self.V[self.Ybus_cols]
            D_p = csc_matrix((data, (self.Ybus_cols, self.Ybus_indices)),
                             shape=(self.nbus, self.nbus)).transpose()

            I_p = np.conj(Vmat) @ (D_p @ lam_diag_p - diags(D_p @ lam_p))
            F_p = lam_diag_p @ Vmat @ (B_p - diags(np.conj(Ibus)))
            C_p = lam_diag_p @ Vmat @ B_p

            Gaa_p = I_p + F_p
            Gva_p = 1j * vm_inv @ (I_p - F_p)
            Gvv_p = vm_inv @ (C_p + C_p.T) @ vm_inv

            # Q
            lam_q = lam[self.nbus: 2 * self.nbus]
            lam_diag_q = diags(lam_q)

            B_q = np.conj(self.admittances.Ybus @ Vmat)
            D_q = np.conj(self.admittances.Ybus).T @ Vmat
            I_q = np.conj(Vmat) @ (D_q @ lam_diag_q - diags(D_q @ lam_q))
            F_q = lam_diag_q @ Vmat @ (B_q - diags(np.conj(Ibus)))
            C_q = lam_diag_q @ Vmat @ B_q

            Gaa_q = I_q + F_q
            Gva_q = 1j * vm_inv @ (I_q - F_q)
            Gvv_q = vm_inv @ (C_q + C_q.T) @ vm_inv

            Gaa = Gaa_p.real + Gaa_q.imag
            Gva = Gva_p.real + Gva_q.imag
            Gav = Gva.T
            Gvv = Gvv_p.real + Gvv_q.imag

            (GSdmdm, dSfdmdm, dStdmdm,
             GSdmdvm, dSfdmdvm, dStdmdvm,
             GSdmdva, dSfdmdva, dStdmdva,
             GSdmdt, dSfdmdt, dStdmdt,
             GSdtdt, dSfdtdt, dStdtdt,
             GSdtdvm, dSfdtdvm, dStdtdvm,
             GSdtdva, dSfdtdva, dStdtdva) = self.compute_branch_power_second_derivatives(lam[0: 2 * self.nbus],
                                                                                         mu[0: 2 * self.n_br_mon])

            if self.ntapm + self.ntapt != 0:
                G1 = sp.hstack(
                    [Gaa, Gav, lil_matrix((self.nbus, 2 * self.n_gen_disp_sh + self.nsl + self.nslcap)), GSdmdva,
                     GSdtdva,
                     lil_matrix((self.nbus, self.n_disp_hvdc))])
                G2 = sp.hstack(
                    [Gva, Gvv, lil_matrix((self.nbus, 2 * self.n_gen_disp_sh + self.nsl + self.nslcap)), GSdmdvm,
                     GSdtdvm,
                     lil_matrix((self.nbus, self.n_disp_hvdc))])
                G3 = sp.hstack(
                    [GSdmdva.T, GSdmdvm.T, lil_matrix((self.ntapm, 2 * self.n_gen_disp_sh + self.nsl + self.nslcap)),
                     GSdmdm, GSdmdt.T, lil_matrix((self.ntapm, self.n_disp_hvdc))])
                G4 = sp.hstack(
                    [GSdtdva.T, GSdtdvm.T, lil_matrix((self.ntapt, 2 * self.n_gen_disp_sh + self.nsl + self.nslcap)),
                     GSdmdt, GSdtdt, lil_matrix((self.ntapt, self.n_disp_hvdc))])

                Gxx = sp.vstack(
                    [G1, G2, lil_matrix((2 * self.n_gen_disp_sh + self.nsl + self.nslcap, self.NV)), G3, G4,
                     lil_matrix((self.n_disp_hvdc, self.NV))]).tocsc()

            else:
                G1 = sp.hstack(
                    [Gaa, Gav,
                     lil_matrix((self.nbus, 2 * self.n_gen_disp_sh + self.nsl + self.nslcap + self.n_disp_hvdc))])
                G2 = sp.hstack(
                    [Gva, Gvv,
                     lil_matrix((self.nbus, 2 * self.n_gen_disp_sh + self.nsl + self.nslcap + self.n_disp_hvdc))])
                Gxx = sp.vstack(
                    [G1, G2, lil_matrix((2 * self.n_gen_disp_sh + self.nsl + self.nslcap + self.n_disp_hvdc,
                                         npfvar + self.nsl + self.nslcap + self.n_disp_hvdc))]).tocsc()

            te_gxx = timeit.default_timer()
            # INEQUALITY CONSTRAINTS HESS ----------------------------------------------------------------------------------
            '''
            The following matrix represents the structure of the hessian matrix for the inequality constraints

                        N         N         Ng        Ng       nsl       ntapm       ntapt       ndc
                   +---------+---------+---------+---------+---------+-----------+-----------+----------+
              N    |  Hvava  |  Hvavm  |  Hvapg  |  Hvaqg  |  Hvasl  |  Hvatapm  |  Hvatapt  |  Hvapdc  |
                   +---------+---------+---------+---------+---------+-----------+-----------+----------+
              N    |  Hvmva  |  Hvmvm  |  Hvmpg  |  Hvmqg  |  Hvmsl  |  Hvmtapm  |  Hvmtapt  |  Hvmpdc  |
                   +---------+---------+---------+---------+---------+-----------+-----------+----------+
              Ng   |  Hpgva  |  Hpgvm  |  Hpgpg  |  Hpgqg  |  Hpgsl  |  Hpgtapm  |  Hpgtapt  |  Hpgpdc  |
                   +---------+---------+---------+---------+---------+-----------+-----------+----------+
              Ng   |  Hqgva  |  Hqgvm  |  Hqgpg  |  Hqgqg  |  Hqgsl  |  Hqgtapm  |  Hqgtapt  |  Hqgpdc  |
                   +---------+---------+---------+---------+---------+-----------+-----------+----------+
              nsl  |  Hslva  |  Hslvm  |  Hslpg  |  Hslqg  |  Hslsl  |  Hsltapm  |  Hsltapt  |  Hslpdc  |
                   +---------+---------+---------+---------+---------+-----------+-----------+----------+
             ntapm | Htapmva | Htapmvm | Htapmpg | Htapmqg | Htapmsl | Htapmtapm | Htapmtapt | Htapmpdc |
                   +---------+---------+---------+---------+---------+-----------+-----------+----------+
             ntapt | Htaptva | Htaptvm | Htaptpg | Htaptqg | Htaptsl | Htapttapm | Htapttapt | Htaptpdc |
                   +---------+---------+---------+---------+---------+-----------+-----------+----------+
              ndc  | Hpdcva  | Hpdcvm  | Hpdcpg  | Hpdcqg  | Hpdcsl  | Hpdctapm  | Hpdctapt  | Hpdcpdc  |
                   +---------+---------+---------+---------+---------+-----------+-----------+----------+

               '''

            ts_hxx = timeit.default_timer()

            muf = mu[0: self.n_br_mon]
            mut = mu[self.n_br_mon: 2 * self.n_br_mon]
            muf_mat = diags(muf)
            mut_mat = diags(mut)
            Smuf_mat = diags(Sfmat.conj() @ muf)
            Smut_mat = diags(Stmat.conj() @ mut)

            Af = np.conj(Yf_mon).T @ Smuf_mat @ self.Cfmon
            Bf = np.conj(Vmat) @ Af @ Vmat
            Df = diags(Af @ self.V) @ np.conj(Vmat)
            Ef = diags(Af.T @ np.conj(self.V)) @ Vmat
            Ff = Bf + Bf.T
            Sfvava = Ff - Df - Ef
            Sfvmva = 1j * vm_inv @ (Bf - Bf.T - Df + Ef)
            Sfvavm = Sfvmva.T
            Sfvmvm = vm_inv @ Ff @ vm_inv

            if self.options.ips_control_q_limits:  # using reactive power control

                # TODO: Avoid negative slicing

                b = None  # This allows proper slicing of the mu vector when n_disp_hvdc is 0.
                if self.n_disp_hvdc != 0:
                    b = - 2 * self.n_disp_hvdc

                Hqpgpg = diags(np.r_[np.array([2] * self.n_gen_disp) * mu[
                                                                       - self.n_gen_disp - 2 * self.n_disp_hvdc:b], np.zeros(
                    self.nsh)])
                Hqqgqg = diags(np.r_[np.array([2] * self.n_gen_disp) * mu[
                                                                       - self.n_gen_disp - 2 * self.n_disp_hvdc:b], np.zeros(
                    self.nsh)])
                Hqvmvm = (self.Cdispgen @ diags(mu[- self.n_gen_disp - 2 * self.n_disp_hvdc: b])
                          @ (- 2 * diags(np.power(self.Inom, 2.0)) * self.Cdispgen_t))
            else:
                Hqpgpg = lil_matrix((self.n_gen_disp, self.n_gen_disp))
                Hqqgqg = lil_matrix((self.n_gen_disp, self.n_gen_disp))
                Hqvmvm = lil_matrix((self.nbus, self.nbus))

            Hfvava = 2 * (Sfvava + Sfva.T @ muf_mat @ np.conj(Sfva)).real
            Hfvmva = 2 * (Sfvmva + Sfvm.T @ muf_mat @ np.conj(Sfva)).real
            Hfvavm = 2 * (Sfvavm + Sfva.T @ muf_mat @ np.conj(Sfvm)).real
            Hfvmvm = 2 * (Sfvmvm + Sfvm.T @ muf_mat @ np.conj(Sfvm)).real

            At = np.conj(Yt_mon).T @ Smut_mat @ self.Ctmon
            Bt = np.conj(Vmat) @ At @ Vmat
            Dt = diags(At @ self.V) @ np.conj(Vmat)
            Et = diags(At.T @ np.conj(self.V)) @ Vmat
            Ft = Bt + Bt.T
            Stvava = Ft - Dt - Et
            Stvmva = 1j * vm_inv @ (Bt - Bt.T - Dt + Et)
            Stvavm = Stvmva.T
            Stvmvm = vm_inv @ Ft @ vm_inv

            Htvava = 2 * (Stvava + Stva.T @ mut_mat @ np.conj(Stva)).real
            Htvmva = 2 * (Stvmva + Stvm.T @ mut_mat @ np.conj(Stva)).real
            Htvavm = 2 * (Stvavm + Stva.T @ mut_mat @ np.conj(Stvm)).real
            Htvmvm = 2 * (Stvmvm + Stvm.T @ mut_mat @ np.conj(Stvm)).real

            if self.ntapm + self.ntapt != 0:

                Hftapmva = 2 * (dSfdmdva.T + Sftapm.T @ muf_mat @ np.conj(Sfva)).real
                Hftapmvm = 2 * (dSfdmdvm.T + Sftapm.T @ muf_mat @ np.conj(Sfvm)).real
                Hftaptva = 2 * (dSfdtdva.T + Sftapt.T @ muf_mat @ np.conj(Sfva)).real
                Hftaptvm = 2 * (dSfdtdvm.T + Sftapt.T @ muf_mat @ np.conj(Sfvm)).real
                Hftapmtapm = 2 * (dSfdmdm.T + Sftapm.T @ muf_mat @ np.conj(Sftapm)).real
                Hftapttapt = 2 * (dSfdtdt.T + Sftapt.T @ muf_mat @ np.conj(Sftapt)).real
                Hftapmtapt = 2 * (dSfdmdt.T + Sftapm.T @ muf_mat @ np.conj(Sftapt)).real

                Httapmva = 2 * (dStdmdva.T + Sttapm.T @ mut_mat @ np.conj(Stva)).real
                Httapmvm = 2 * (dStdmdvm.T + Sttapm.T @ mut_mat @ np.conj(Stvm)).real
                Httaptva = 2 * (dStdtdva.T + Sttapt.T @ mut_mat @ np.conj(Stva)).real
                Httaptvm = 2 * (dStdtdvm.T + Sttapt.T @ mut_mat @ np.conj(Stvm)).real
                Httapmtapm = 2 * (dStdmdm.T + Sttapm.T @ mut_mat @ np.conj(Sttapm)).real
                Httapttapt = 2 * (dStdtdt.T + Sttapt.T @ mut_mat @ np.conj(Sttapt)).real
                Httapmtapt = 2 * (dStdmdt.T + Sttapm.T @ mut_mat @ np.conj(Sttapt)).real

                H1 = sp.hstack([Hfvava + Htvava,
                                Hfvavm + Htvavm,
                                lil_matrix((self.nbus, 2 * self.n_gen_disp_sh + self.nsl + self.nslcap)),
                                Hftapmva.T + Httapmva.T,
                                Hftaptva.T + Httaptva.T,
                                lil_matrix((self.nbus, self.n_disp_hvdc))])

                H2 = sp.hstack([Hfvmva + Htvmva,
                                Hfvmvm + Htvmvm + Hqvmvm,
                                lil_matrix((self.nbus, 2 * self.n_gen_disp_sh + self.nsl + self.nslcap)),
                                Hftapmvm.T + Httapmvm.T,
                                Hftaptvm.T + Httaptvm.T,
                                lil_matrix((self.nbus, self.n_disp_hvdc))])

                H3 = sp.hstack(
                    [lil_matrix((self.n_gen_disp_sh, 2 * self.nbus)), Hqpgpg, lil_matrix(
                        (self.n_gen_disp_sh,
                         self.n_gen_disp_sh + self.nsl + self.nslcap + self.ntapm + self.ntapt + self.n_disp_hvdc))])

                H4 = sp.hstack(
                    [lil_matrix((self.n_gen_disp_sh, 2 * self.nbus + self.n_gen_disp_sh)), Hqqgqg,
                     lil_matrix(
                         (self.n_gen_disp_sh, self.nsl + self.nslcap + self.ntapm + self.ntapt + self.n_disp_hvdc))])

                H5 = sp.hstack([Hftapmva + Httapmva, Hftapmvm + Httapmvm,
                                lil_matrix((self.ntapm, 2 * self.n_gen_disp_sh + self.nsl + self.nslcap)),
                                Hftapmtapm + Httapmtapm, Hftapmtapt + Httapmtapt,
                                lil_matrix((self.ntapm, self.n_disp_hvdc))])

                H6 = sp.hstack([Hftaptva + Httaptva,
                                Hftaptvm + Httaptvm,
                                lil_matrix((self.ntapt, 2 * self.n_gen_disp_sh + self.nsl + self.nslcap)),
                                Hftapmtapt.T + Httapmtapt.T,
                                Hftapttapt + Httapttapt,
                                lil_matrix((self.ntapt, self.n_disp_hvdc))])

                Hxx = sp.vstack([H1, H2, H3, H4, lil_matrix((self.nsl + self.nslcap, self.NV)), H5, H6,
                                 lil_matrix((self.n_disp_hvdc, self.NV))]).tocsc()

            else:
                H1 = sp.hstack([Hfvava + Htvava, Hfvavm + Htvavm,
                                lil_matrix(
                                    (self.nbus, 2 * self.n_gen_disp_sh + self.nsl + self.nslcap + self.n_disp_hvdc))])
                H2 = sp.hstack(
                    [Hfvmva + Htvmva, Hfvmvm + Htvmvm + Hqvmvm,
                     lil_matrix((self.nbus, 2 * self.n_gen_disp_sh + self.nsl + self.nslcap + self.n_disp_hvdc))])
                H3 = sp.hstack([lil_matrix((self.n_gen_disp_sh, 2 * self.nbus)), Hqpgpg,
                                lil_matrix(
                                    (
                                        self.n_gen_disp_sh,
                                        self.n_gen_disp_sh + self.nsl + self.nslcap + self.n_disp_hvdc))])
                H4 = sp.hstack([lil_matrix((self.n_gen_disp_sh, 2 * self.nbus + self.n_gen_disp_sh)), Hqqgqg,
                                lil_matrix((self.n_gen_disp_sh, self.nsl + self.nslcap + self.n_disp_hvdc))])

                Hxx = sp.vstack(
                    [H1, H2, H3, H4, lil_matrix((self.nsl + self.nslcap + self.n_disp_hvdc, self.NV))]).tocsc()

            te_hxx = timeit.default_timer()
        else:
            # Return empty structures
            fxx = csc((self.NV, self.NV))
            Gxx = csc((self.NV, self.NV))
            Hxx = csc((self.NV, self.NV))
            ts_fxx = 0
            te_fxx = 0
            ts_gxx = 0
            te_gxx = 0
            ts_hxx = 0
            te_hxx = 0

        print(1000 * np.array([te_fx - ts_fx,
                               te_gx - ts_gx,
                               te_hx - ts_hx,
                               te_fxx - ts_fxx,
                               te_gxx - ts_gxx,
                               te_hxx - ts_hxx]), 100 * np.array([te_fx - ts_fx,
                                                                  te_gx - ts_gx,
                                                                  te_hx - ts_hx,
                                                                  te_fxx - ts_fxx,
                                                                  te_gxx - ts_gxx,
                                                                  te_hxx - ts_hxx]) / (te_hxx - ts_fx))

        return fx, Gx, Hx, fxx, Gxx, Hxx

    def compute_branch_power_derivatives(self) -> Tuple[
        csr_matrix, lil_matrix, lil_matrix, csr_matrix, lil_matrix, lil_matrix]:
        """
        TODO: Move outside of the class
        :return: First power derivatives with respect to the tap variables
                [dSbusdm, dSfdm, dStdm, dSbusdt, dSfdtau, dStdtau]
        """
        ys = 1.0 / (self.R + 1.0j * self.X + 1e-20)

        nbr = len(self.all_tap_m)
        dSfdm = lil_matrix((nbr, self.ntapm), dtype=complex)
        dStdm = lil_matrix((nbr, self.ntapm), dtype=complex)
        dSfdtau = lil_matrix((nbr, self.ntapt), dtype=complex)
        dStdtau = lil_matrix((nbr, self.ntapt), dtype=complex)

        for k_pos, k in enumerate(self.k_m):
            Vf = self.V[self.from_idx[k]]
            Vt = self.V[self.to_idx[k]]
            mp = self.all_tap_m[k]
            tau = self.all_tap_tau[k]
            yk = ys[k]
            mp2 = np.power(mp, 2)

            # First derivatives with respect to the tap module.
            # Each branch is computed individually and stored
            dSfdm[k, k_pos] = Vf * (
                    (-2 * np.conj(yk * Vf) / np.power(mp, 3)) + np.conj(yk * Vt) / (mp2 * np.exp(1j * tau)))
            dStdm[k, k_pos] = Vt * (np.conj(yk * Vf) / (mp2 * np.exp(-1j * tau)))

        for k_pos, k in enumerate(self.k_tau):
            Vf = self.V[self.from_idx[k]]
            Vt = self.V[self.to_idx[k]]
            mp = self.all_tap_m[k]
            tau = self.all_tap_tau[k]
            yk = ys[k]

            # First derivatives with respect to the tap phase.
            # Each branch is computed individually and stored
            dSfdtau[k, k_pos] = Vf * 1j * np.conj(yk * Vt) / (mp * np.exp(1j * tau))
            dStdtau[k, k_pos] = Vt * -1j * np.conj(yk * Vf) / (mp * np.exp(-1j * tau))

        # Bus power injection is computed using the 'from' and 'to' powers and their connectivity matrices
        dSbusdm = self.admittances.Cf.T @ dSfdm + self.admittances.Ct.T @ dStdm
        dSbusdt = self.admittances.Cf.T @ dSfdtau + self.admittances.Ct.T @ dStdtau

        return dSbusdm, dSfdm, dStdm, dSbusdt, dSfdtau, dStdtau

    def compute_branch_power_second_derivatives(self, lam: Vec, mu: Vec) -> Tuple[
        lil_matrix, lil_matrix, lil_matrix,
        lil_matrix, lil_matrix, lil_matrix,
        lil_matrix, lil_matrix, lil_matrix,
        lil_matrix, lil_matrix, lil_matrix,
        lil_matrix, lil_matrix, lil_matrix,
        lil_matrix, lil_matrix, lil_matrix,
        lil_matrix, lil_matrix, lil_matrix]:

        """
        TODO: Move outside of the class
        :param lam: Lambda multiplier
        :param mu: Mu multiplier
        :return: Power second derivatives with respect to tap variables

        """
        ys = 1.0 / (self.R + 1.0j * self.X + 1e-20)

        dSbusdmdm = lil_matrix((self.ntapm, self.ntapm))
        dSfdmdm = lil_matrix((self.ntapm, self.ntapm), dtype=complex)
        dStdmdm = lil_matrix((self.ntapm, self.ntapm), dtype=complex)

        dSbusdmdva = lil_matrix((self.nbus, self.ntapm))
        dSfdmdva = lil_matrix((self.nbus, self.ntapm), dtype=complex)
        dStdmdva = lil_matrix((self.nbus, self.ntapm), dtype=complex)

        dSbusdmdvm = lil_matrix((self.nbus, self.ntapm))
        dSfdmdvm = lil_matrix((self.nbus, self.ntapm), dtype=complex)
        dStdmdvm = lil_matrix((self.nbus, self.ntapm), dtype=complex)

        dSbusdtdt = lil_matrix((self.ntapt, self.ntapt))
        dSfdtdt = lil_matrix((self.ntapt, self.ntapt), dtype=complex)
        dStdtdt = lil_matrix((self.ntapt, self.ntapt), dtype=complex)

        dSbusdtdva = lil_matrix((self.nbus, self.ntapt))
        dSfdtdva = lil_matrix((self.nbus, self.ntapt), dtype=complex)
        dStdtdva = lil_matrix((self.nbus, self.ntapt), dtype=complex)

        dSbusdtdvm = lil_matrix((self.nbus, self.ntapt))
        dSfdtdvm = lil_matrix((self.nbus, self.ntapt), dtype=complex)
        dStdtdvm = lil_matrix((self.nbus, self.ntapt), dtype=complex)

        dSbusdmdt = lil_matrix((self.ntapt, self.ntapm))
        dSfdmdt = lil_matrix((self.ntapt, self.ntapm), dtype=complex)
        dStdmdt = lil_matrix((self.ntapt, self.ntapm), dtype=complex)

        for k_pos, k in enumerate(self.k_m):
            f = self.from_idx[k]
            t = self.to_idx[k]
            Vf = self.V[f]
            Vt = self.V[t]
            mp = self.all_tap_m[k]
            tau = self.all_tap_tau[k]
            yk = ys[k]
            tap_unit = np.exp(1j * tau)
            tap_unit_c = np.exp(-1j * tau)

            # For each line with a module controlled transformer, compute its second derivatives w.r.t. the tap module and
            # the rest of the variables.
            mp2 = mp * mp
            mp3 = mp2 * mp
            mp4 = mp3 * mp
            dSfdmdm_ = Vf * ((6 * np.conj(yk * Vf) / mp4) - 2 * np.conj(yk * Vt) / (mp3 * tap_unit))
            dStdmdm_ = - Vt * 2 * np.conj(yk * Vf) / (mp3 * tap_unit_c)

            dSfdmdva_f = Vf * 1j * np.conj(yk * Vt) / (mp2 * tap_unit)
            dSfdmdva_t = - Vf * 1j * np.conj(yk * Vt) / (mp2 * tap_unit)

            dStdmdva_f = - Vt * 1j * np.conj(yk * Vf) / (mp2 * tap_unit_c)
            dStdmdva_t = Vt * 1j * np.conj(yk * Vf) / (mp2 * tap_unit_c)

            dSfdmdvm_f = Vf * (1 / self.Vm[f]) * ((-4 * np.conj(yk * Vf) / mp3) + np.conj(yk * Vt) / (mp2 * tap_unit))
            dSfdmdvm_t = Vf * (1 / self.Vm[t]) * np.conj(yk * Vt) / (mp2 * tap_unit)

            dStdmdvm_f = Vt * (1 / self.Vm[f]) * np.conj(yk * Vf) / (mp2 * tap_unit_c)
            dStdmdvm_t = Vt * (1 / self.Vm[t]) * np.conj(yk * Vf) / (mp2 * tap_unit_c)

            lin = np.where(self.k_tau == k)[0]  # TODO: should pass along the control type and check that instead

            if len(lin) != 0:
                k_pos = lin[0]
                # If the trafo is controlled for both module and phase, compute these derivatives. Otherwise, they are 0
                dSfdmdt_ = - Vf * 1j * (np.conj(yk * Vt) / (mp2 * tap_unit))
                dStdmdt_ = Vt * 1j * (np.conj(yk * Vf) / (mp2 * tap_unit_c))

                dSbusdmdt[k_pos, k_pos] = ((dSfdmdt_ * lam[f]).real + (dSfdmdt_ * lam[f + self.nbus]).imag
                                           + (dStdmdt_ * lam[t]).real + (dStdmdt_ * lam[t + self.nbus]).imag)
                if k in self.br_mon_idx:
                    # This is only included if the branch is monitored.
                    li = np.where(self.br_mon_idx == k)[0]  # TODO: Why is this here?
                    dSfdmdt[k_pos, k_pos] = dSfdmdt_ * self.Sf[li].conj() * mu[li]
                    dStdmdt[k_pos, k_pos] = dStdmdt_ * self.St[li].conj() * mu[li + self.n_br_mon]

            # Compute the hessian terms merging Sf and St into Sbus
            dSbusdmdm[k_pos, k_pos] = ((dSfdmdm_ * lam[f]).real + (dSfdmdm_ * lam[f + self.nbus]).imag
                                       + (dStdmdm_ * lam[t]).real + (dStdmdm_ * lam[t + self.nbus]).imag)
            dSbusdmdva[f, k_pos] = ((dSfdmdva_f * lam[f]).real + (dSfdmdva_f * lam[f + self.nbus]).imag
                                    + (dStdmdva_f * lam[t]).real + (dStdmdva_f * lam[t + self.nbus]).imag)
            dSbusdmdva[t, k_pos] = ((dSfdmdva_t * lam[f]).real + (dSfdmdva_t * lam[f + self.nbus]).imag
                                    + (dStdmdva_t * lam[t]).real + (dStdmdva_t * lam[t + self.nbus]).imag)
            dSbusdmdvm[f, k_pos] = ((dSfdmdvm_f * lam[f]).real + (dSfdmdvm_f * lam[f + self.nbus]).imag
                                    + (dStdmdvm_f * lam[t]).real + (dStdmdvm_f * lam[t + self.nbus]).imag)
            dSbusdmdvm[t, k_pos] = ((dSfdmdvm_t * lam[f]).real + (dSfdmdvm_t * lam[f + self.nbus]).imag
                                    + (dStdmdvm_t * lam[t]).real + (dStdmdvm_t * lam[t + self.nbus]).imag)

            if k in self.br_mon_idx:
                # Hessian terms, only for monitored lines
                li = np.where(self.br_mon_idx == k)[0]  # TODO: Why is this here?
                dSfdmdm[k_pos, k_pos] = dSfdmdm_ * self.Sf[li].conj() * mu[li]
                dStdmdm[k_pos, k_pos] = dStdmdm_ * self.St[li].conj() * mu[li + self.n_br_mon]
                dSfdmdva[f, k_pos] = dSfdmdva_f * self.Sf[li].conj() * mu[li]
                dStdmdva[f, k_pos] = dStdmdva_f * self.St[li].conj() * mu[li + self.n_br_mon]
                dSfdmdva[t, k_pos] = dSfdmdva_t * self.Sf[li].conj() * mu[li]
                dStdmdva[t, k_pos] = dStdmdva_t * self.St[li].conj() * mu[li + self.n_br_mon]
                dSfdmdvm[f, k_pos] = dSfdmdvm_f * self.Sf[li].conj() * mu[li]
                dStdmdvm[f, k_pos] = dStdmdvm_f * self.St[li].conj() * mu[li + self.n_br_mon]
                dSfdmdvm[t, k_pos] = dSfdmdvm_t * self.Sf[li].conj() * mu[li]
                dStdmdvm[t, k_pos] = dStdmdvm_t * self.St[li].conj() * mu[li + self.n_br_mon]

        for k_pos, k in enumerate(self.k_tau):
            f = self.from_idx[k]
            t = self.to_idx[k]
            Vf = self.V[f]
            Vt = self.V[t]
            Vmf = abs(Vf)
            Vmt = abs(Vt)
            mp = self.all_tap_m[k]
            tau = self.all_tap_tau[k]
            yk = ys[k]
            tap = mp * np.exp(1j * tau)
            tap_c = mp * np.exp(-1j * tau)

            # Same procedure for phase controlled transformers
            dSfdtdt_ = Vf * np.conj(yk * Vt) / tap
            dStdtdt_ = Vt * np.conj(yk * Vf) / tap_c

            dSfdtdva_f = - Vf * np.conj(yk * Vt) / tap
            dSfdtdva_t = Vf * np.conj(yk * Vt) / tap

            dStdtdva_f = - Vt * np.conj(yk * Vf) / tap_c
            dStdtdva_t = Vt * np.conj(yk * Vf) / tap_c

            dSfdtdvm_f = 1.0j * Vf / Vmf * np.conj(yk * Vt) / tap
            dSfdtdvm_t = 1.0j * Vf / Vmt * np.conj(yk * Vt) / tap

            dStdtdvm_f = -1.0j * Vt / Vmf * np.conj(yk * Vf) / tap_c
            dStdtdvm_t = -1.0j * Vt / Vmt * np.conj(yk * Vf) / tap_c

            # Merge Sf and St in Sbus
            dSbusdtdt[k_pos, k_pos] = ((dSfdtdt_ * lam[f]).real + (dSfdtdt_ * lam[f + self.nbus]).imag
                                       + (dStdtdt_ * lam[t]).real + (dStdtdt_ * lam[t + self.nbus]).imag)
            dSbusdtdva[f, k_pos] = ((dSfdtdva_f * lam[f]).real + (dSfdtdva_f * lam[f + self.nbus]).imag
                                    + (dStdtdva_f * lam[t]).real + (dStdtdva_f * lam[t + self.nbus]).imag)
            dSbusdtdva[t, k_pos] = ((dSfdtdva_t * lam[f]).real + (dSfdtdva_t * lam[f + self.nbus]).imag
                                    + (dStdtdva_t * lam[t]).real + (dStdtdva_t * lam[t + self.nbus]).imag)
            dSbusdtdvm[f, k_pos] = ((dSfdtdvm_f * lam[f]).real + (dSfdtdvm_f * lam[f + self.nbus]).imag
                                    + (dStdtdvm_f * lam[t]).real + (dStdtdvm_f * lam[t + self.nbus]).imag)
            dSbusdtdvm[t, k_pos] = ((dSfdtdvm_t * lam[f]).real + (dSfdtdvm_t * lam[f + self.nbus]).imag
                                    + (dStdtdvm_t * lam[t]).real + (dStdtdvm_t * lam[t + self.nbus]).imag)
            dSbusdtdt[k_pos, k_pos] = ((dSfdtdt_ * lam[f]).real + (dSfdtdt_ * lam[f + self.nbus]).imag
                                       + (dStdtdt_ * lam[t]).real + (dStdtdt_ * lam[t + self.nbus]).imag)

            if k in self.br_mon_idx:
                li = np.where(self.br_mon_idx == k)[0]  # TODO: Why is this here?
                dSfdtdt[k_pos, k_pos] = dSfdtdt_ * self.Sf[li].conj() * mu[li]
                dStdtdt[k_pos, k_pos] = dStdtdt_ * self.St[li].conj() * mu[li + self.n_br_mon]
                dSfdtdva[f, k_pos] = dSfdtdva_f * self.Sf[li].conj() * mu[li]
                dStdtdva[f, k_pos] = dStdtdva_f * self.St[li].conj() * mu[li + self.n_br_mon]
                dSfdtdva[t, k_pos] = dSfdtdva_t * self.Sf[li].conj() * mu[li]
                dStdtdva[t, k_pos] = dStdtdva_t * self.St[li].conj() * mu[li + self.n_br_mon]
                dSfdtdvm[f, k_pos] = dSfdtdvm_f * self.Sf[li].conj() * mu[li]
                dStdtdvm[f, k_pos] = dStdtdvm_f * self.St[li].conj() * mu[li + self.n_br_mon]
                dSfdtdvm[t, k_pos] = dSfdtdvm_t * self.Sf[li].conj() * mu[li]
                dStdtdvm[t, k_pos] = dStdtdvm_t * self.St[li].conj() * mu[li + self.n_br_mon]
                dSfdtdt[k_pos, k_pos] = dSfdtdt_ * self.Sf[li].conj() * mu[li]
                dStdtdt[k_pos, k_pos] = dStdtdt_ * self.St[li].conj() * mu[li + self.n_br_mon]

        return (dSbusdmdm, dSfdmdm, dStdmdm,
                dSbusdmdvm, dSfdmdvm, dStdmdvm,
                dSbusdmdva, dSfdmdva, dStdmdva,
                dSbusdmdt, dSfdmdt, dStdmdt,
                dSbusdtdt, dSfdtdt, dStdtdt,
                dSbusdtdvm, dSfdtdvm, dStdtdvm,
                dSbusdtdva, dSfdtdva, dStdtdva)

    def get_solution(self, ips_results: IpsSolution, verbose: int = 0, plot_error: bool = False):
        """

        :param ips_results:
        :param verbose:
        :param plot_error:
        :return:
        """
        self.x2var(ips_results.x)

        # Save Results DataFrame for tests
        # pd.DataFrame(Va).transpose().to_csv('REEresth.csv')
        # pd.DataFrame(Vm).transpose().to_csv('REEresV.csv')
        # pd.DataFrame(Pg_dis).transpose().to_csv('REEresP.csv')
        # pd.DataFrame(Qg_dis).transpose().to_csv('REEresQ.csv')

        Pg = np.zeros(self.ngen)
        Qg = np.zeros(self.ngen)

        Pg[self.gen_disp_idx] = self.Pg
        Qg[self.gen_disp_idx] = self.Qg
        Pg[self.gen_nondisp_idx] = np.real(self.Sg_undis)
        Qg[self.gen_nondisp_idx] = np.imag(self.Sg_undis)

        # convert the lagrange multipliers to significant ones
        lam_p, lam_q = ips_results.lam[:self.nbus], ips_results.lam[self.nbus: 2 * self.nbus]

        loading = np.abs(self.allSf) / (self.rates + 1e-9)

        if self.options.acopf_mode == AcOpfMode.ACOPFslacks:
            overloads_sf = (np.power(np.power(self.rates[self.br_mon_idx], 2) + self.sl_sf, 0.5)
                            - self.rates[self.br_mon_idx]) * self.Sbase
            overloads_st = (np.power(np.power(self.rates[self.br_mon_idx], 2) + self.sl_st, 0.5)
                            - self.rates[self.br_mon_idx]) * self.Sbase

        else:
            overloads_sf = np.zeros_like(self.rates)
            overloads_st = np.zeros_like(self.rates)

        hvdc_power = self.nc.hvdc_data.Pset.copy()
        hvdc_power[self.hvdc_disp_idx] = self.Pfdc
        hvdc_loading = hvdc_power / (self.nc.hvdc_data.rates + 1e-9)
        tap_module = np.zeros(self.nc.nbr)
        tap_phase = np.zeros(self.nc.nbr)
        tap_module[self.k_m] = self.tap_m
        tap_phase[self.k_tau] = self.tap_tau
        Pcost = np.zeros(self.ngen + self.nsh)

        Pcost[self.gen_disp_idx] = (self.c0 + self.c1 * Pg[self.gen_disp_idx]
                                    + self.c2 * np.power(Pg[self.gen_disp_idx], 2.0))

        Pcost[self.gen_nondisp_idx] = (self.c0n + self.c1n * np.real(self.Sg_undis)
                                       + self.c2n * np.power(np.real(self.Sg_undis), 2.0))

        nodal_capacity = self.slcap * self.Sbase

        tend = timeit.default_timer()

        if self.options.verbose > 0:
            df_bus = pd.DataFrame(data={'Va (rad)': self.Va, 'Vm (p.u.)': self.Vm,
                                        'dual price (€/MW)': lam_p, 'dual price (€/MVAr)': lam_q})
            df_gen = pd.DataFrame(data={'P (MW)': Pg * self.Sbase, 'Q (MVAr)': Qg * self.Sbase})
            df_linkdc = pd.DataFrame(data={'P_dc (MW)': self.Pfdc * self.Sbase})

            df_slsf = pd.DataFrame(data={'Slacks Sf': self.sl_sf})
            df_slst = pd.DataFrame(data={'Slacks St': self.sl_st})
            df_slvmax = pd.DataFrame(data={'Slacks Vmax': self.sl_vmax})
            df_slvmin = pd.DataFrame(data={'Slacks Vmin': self.sl_vmin})
            df_trafo_m = pd.DataFrame(data={'V (p.u.)': self.tap_m}, index=self.k_m)
            df_trafo_tau = pd.DataFrame(data={'Tau (rad)': self.tap_tau}, index=self.k_tau)
            # df_times = pd.DataFrame(data=times[1:], index=list(range(result.iterations)),
            #                         columns=['t_modadm', 't_f', 't_g', 't_h', 't_fx', 't_gx',
            #                                  't_hx', 't_fxx', 't_gxx', 't_hxx', 't_nrstep',
            #                                  't_mult', 't_steps', 't_cond', 't_iter'])

            print("Bus:\n", df_bus)
            print("V-Trafos:\n", df_trafo_m)
            print("Tau-Trafos:\n", df_trafo_tau)
            print("Gen:\n", df_gen)
            print("Link DC:\n", df_linkdc)

            print('Qshunt min: ' + str(self.Qsh_min))

            if self.options.acopf_mode == AcOpfMode.ACOPFslacks:
                print("Slacks:\n", df_slsf)
                print("Slacks:\n", df_slst)
                print("Slacks:\n", df_slvmax)
                print("Slacks:\n", df_slvmin)

            if self.optimize_nodal_capacity:
                df_nodal_cap = pd.DataFrame(data={'Nodal capacity (MW)': self.slcap * self.Sbase},
                                            index=self.capacity_nodes_idx)
                print("Nodal Capacity:\n", df_nodal_cap)
            print("Error", ips_results.error)
            print("Gamma", ips_results.gamma)
            print("Sf", self.Sf)

            # if self.options.verbose > 1:
            #     print('Times:\n', df_times)
            #     print('Relative times:\n', 100 * df_times[['t_modadm', 't_f', 't_g', 't_h', 't_fx', 't_gx',
            #                                                't_hx', 't_fxx', 't_gxx', 't_hxx', 't_nrstep',
            #                                                't_mult', 't_steps', 't_cond', 't_iter']].div(
            #         df_times['t_iter'],
            #         axis=0))

        if plot_error:
            ips_results.plot_error()

        if not ips_results.converged or ips_results.converged:

            for i in range(self.nbus):
                if abs(ips_results.dlam[i]) >= 1e-3:
                    self.logger.add_warning('Nodal Power Balance convergence tolerance not achieved',
                                            device_property="dlam",
                                            device=str(i),
                                            value=str(ips_results.dlam[i]),
                                            expected_value='< 1e-3')

                if abs(ips_results.dlam[self.nbus + i]) >= 1e-3:  # TODO: What is the difference with the previous?
                    self.logger.add_warning('Nodal Power Balance convergence tolerance not achieved',
                                            device_property="dlam",
                                            device=str(i),
                                            value=str(ips_results.dlam[i + self.nbus]),
                                            expected_value='< 1e-3')

            for pvbus in range(self.npv):
                if abs(ips_results.dlam[2 * self.nbus + 1 + pvbus]) >= 1e-3:
                    self.logger.add_warning('PV voltage module convergence tolerance not achieved',
                                            device_property="dlam",
                                            device=str(self.pv[pvbus]),
                                            value=str((ips_results.dlam[2 * self.nbus + 1 + pvbus])),
                                            expected_value='< 1e-3')

            for k in range(self.n_br_mon):
                muz_f = abs(ips_results.z[k] * ips_results.mu[k])
                muz_t = abs(ips_results.z[k + self.n_br_mon] * ips_results.mu[k + self.n_br_mon])
                if muz_f >= 1e-3:
                    self.logger.add_warning('Branch rating "from" multipliers did not reach the tolerance',
                                            device_property="mu · z",
                                            device=str(self.br_mon_idx[k]),
                                            value=str(muz_f),
                                            expected_value='< 1e-3')
                if muz_t >= 1e-3:
                    self.logger.add_warning('Branch rating "to" multipliers did not reach the tolerance',
                                            device_property="mu · z",
                                            device=str(self.br_mon_idx[k]),
                                            value=str(muz_t),
                                            expected_value='< 1e-3')

            for link in range(self.n_disp_hvdc):
                muz_f = abs(ips_results.z[self.nineq - 2 * self.n_disp_hvdc + link] * ips_results.mu[
                    self.nineq - 2 * self.n_disp_hvdc + link])
                muz_t = abs(
                    ips_results.z[self.nineq - self.n_disp_hvdc + link] * ips_results.mu[
                        self.nineq - self.n_disp_hvdc + link])
                if muz_f >= 1e-3:
                    self.logger.add_warning('HVDC rating "from" multipliers did not reach the tolerance',
                                            device_property="mu · z",
                                            device=str(link),
                                            value=str(muz_f),
                                            expected_value='< 1e-3')
                if muz_t >= 1e-3:
                    self.logger.add_warning('HVDC rating "to" multipliers did not reach the tolerance',
                                            device_property="mu · z",
                                            device=str(link),
                                            value=str(muz_t),
                                            expected_value='< 1e-3')

            if self.options.acopf_mode == AcOpfMode.ACOPFslacks:
                for k in range(self.n_br_mon):
                    if overloads_sf[k] > self.options.ips_tolerance * self.Sbase:
                        self.logger.add_warning('Branch overload in the from sense (MVA)',
                                                device=str(self.br_mon_idx[k]),
                                                device_property="Slack",
                                                value=str(overloads_sf[k]),
                                                expected_value=f'< {self.options.ips_tolerance * self.Sbase}')

                    if overloads_st[k] > self.options.ips_tolerance * self.Sbase:
                        self.logger.add_warning('Branch overload in the to sense (MVA)',
                                                device=str(self.br_mon_idx[k]),
                                                device_property="Slack",
                                                value=str(overloads_st[k]),
                                                expected_value=f'< {self.options.ips_tolerance * self.Sbase}')

                for i in range(self.npq):
                    if self.sl_vmax[i] > self.options.ips_tolerance:
                        self.logger.add_warning('Overvoltage',
                                                device_property="Slack",
                                                device=str(self.pq[i]),
                                                value=str(self.sl_vmax[i]),
                                                expected_value=f'>{self.options.ips_tolerance}')
                    if self.sl_vmin[i] > self.options.ips_tolerance:
                        self.logger.add_warning('Undervoltage',
                                                device_property="Slack",
                                                device=str(self.pq[i]),
                                                value=str(self.sl_vmin[i]),
                                                expected_value=f'> {self.options.ips_tolerance}')

        if verbose > 0:
            if len(self.logger):
                self.logger.print()

        self.results = NonlinearOPFResults(Va=self.Va, Vm=self.Vm, S=self.Scalc,
                                           Sf=self.allSf, St=self.allSt, loading=loading,
                                           Pg=Pg[:self.ngen], Qg=Qg[:self.ngen], Qsh=Qg[self.ngen:],
                                           Pcost=Pcost[:self.ngen],
                                           tap_module=tap_module, tap_phase=tap_phase,
                                           hvdc_Pf=hvdc_power, hvdc_loading=hvdc_loading,
                                           lam_p=lam_p, lam_q=lam_q,
                                           sl_sf=self.sl_sf, sl_st=self.sl_st, sl_vmax=self.sl_vmax,
                                           sl_vmin=self.sl_vmin,
                                           nodal_capacity=nodal_capacity,
                                           error=ips_results.error,
                                           converged=ips_results.converged,
                                           iterations=ips_results.iterations)

        return self.results
