# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import timeit
import numpy as np
import timeit
import pandas as pd
from scipy import sparse as sp
from typing import Tuple, Union
from scipy import sparse as sp
from scipy.sparse import csc_matrix as csc
from scipy.sparse import lil_matrix

from GridCalEngine.Utils.Sparse.csc import diags
from GridCalEngine.basic_structures import Vec, CxVec, IntVec, csr_matrix, csc_matrix, Vec
from GridCalEngine.Utils.NumericalMethods.ips import interior_point_solver, IpsFunctionReturn
import GridCalEngine.Utils.NumericalMethods.autodiff as ad
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Compilers.circuit_to_data import compile_numerical_circuit_at, NumericalCircuit
from GridCalEngine.Simulations.PowerFlow.power_flow_worker import multi_island_pf_nc
from GridCalEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCalEngine.Simulations.OPF.opf_options import OptimalPowerFlowOptions
from GridCalEngine.enumerations import AcOpfMode
from GridCalEngine.basic_structures import Vec, CxVec, IntVec, Logger


class NonLinearOptimalPfProblem:

    def __init__(self,
                 nc: NumericalCircuit,
                 options: OptimalPowerFlowOptions,
                 logger: Logger,
                 pf_init: bool = True,
                 Sbus_pf: Union[CxVec, None] = None,
                 voltage_pf: Union[CxVec, None] = None,
                 optimize_nodal_capacity: bool = False,
                 capacity_nodes_idx: Union[IntVec, None] = None,
                 ):

        self.options = options
        self.nc = nc
        self.logger = logger

        # Parameters

        self.Sbase = nc.Sbase
        self.from_idx = nc.passive_branch_data.F
        self.to_idx = nc.passive_branch_data.T
        self.indices = nc.get_simulation_indices(Sbus=Sbus_pf)
        self.Cgen = nc.generator_data.get_C_bus_elm()  # TODO: Should we ever use Cgen?
        self.slack = self.indices.vd
        self.slackgens = np.where(self.Cgen[self.slack, :].toarray() == 1)[1]  # TODO: Redo without Cgen

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
        self.nsh = len(self.id_sh)

        # Since controllable shunts will be treated as generators, we deactivate them to avoid its computation in the
        # Admittance matrix. Then, the admittance elements are stored.

        nc.shunt_data.Y[self.id_sh] = 0 + 0j
        self.admittances = nc.get_admittance_matrices()

        self.Csh = nc.shunt_data.get_C_bus_elm()[:, self.id_sh]  # TODO: Change this completely
        self.Cg = sp.hstack([self.Cgen, self.Csh])

        self.Qsh_max = nc.shunt_data.qmax[self.id_sh] / self.Sbase
        self.Qsh_min = nc.shunt_data.qmin[self.id_sh] / self.Sbase

        self.Pg_max = np.r_[self.Pg_max, np.zeros(self.nsh)]
        self.Pg_min = np.r_[self.Pg_min, np.zeros(self.nsh)]

        self.Qg_max = np.r_[self.Qg_max, self.Qsh_max]
        self.Qg_min = np.r_[self.Qg_min, self.Qsh_min]

        self.Inom = nc.generator_data.snom / self.Sbase

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
        self.br_mon_idx = nc.passive_branch_data.get_monitor_enabled_indices()
        self.gen_disp_idx = np.r_[
            nc.generator_data.get_dispatchable_active_indices(), np.array([*range(self.ngen, self.ngen + self.nsh)],
                                                                          dtype=int)]
        self.ind_gens = np.arange(len(self.Pg_max))
        self.gen_nondisp_idx = nc.generator_data.get_non_dispatchable_indices()
        self.Sg_undis = (nc.generator_data.get_injections() / self.Sbase)[self.gen_nondisp_idx]
        self.rates = nc.passive_branch_data.rates / self.Sbase  # Line loading limits. If the grid is not well conditioned, add constant value (i.e. +100)
        self.Va_max = nc.bus_data.angle_max  # This limits are not really used as of right now.
        self.Va_min = nc.bus_data.angle_min

        self.k_m = self.indices.k_m
        self.k_tau = self.indices.k_tau
        self.k_mtau = self.indices.k_mtau
        self.R = nc.passive_branch_data.R
        self.X = nc.passive_branch_data.X

        self.c0 = np.r_[nc.generator_data.cost_0[self.gen_disp_idx[:self.ngen]], np.zeros(self.nsh)]
        self.c1 = np.r_[nc.generator_data.cost_1[self.gen_disp_idx[:self.ngen]], np.zeros(self.nsh)]
        self.c2 = np.r_[nc.generator_data.cost_2[self.gen_disp_idx[:self.ngen]], np.zeros(self.nsh)]

        self.c0n = nc.generator_data.cost_0[self.gen_nondisp_idx]
        self.c1n = nc.generator_data.cost_1[self.gen_nondisp_idx]
        self.c2n = nc.generator_data.cost_2[self.gen_nondisp_idx]

        # Transformer operational limits
        self.tapm_max = nc.active_branch_data.tap_module_max[self.k_m]
        self.tapm_min = nc.active_branch_data.tap_module_min[self.k_m]
        self.tapt_max = nc.active_branch_data.tap_angle_max[self.k_tau]
        self.tapt_min = nc.active_branch_data.tap_angle_min[self.k_tau]

        # We grab all tapm even when uncontrolled since the indexing is needed
        self.alltapm = nc.active_branch_data.tap_module
        # if the tapt of the same trafo is variable.
        # We grab all tapt even when uncontrolled since the indexing is needed if
        self.alltapt = nc.active_branch_data.tap_angle
        # the tapm of the same trafo is variable.

        # Sizing of the problem
        self.nbus = nc.bus_data.nbus
        self.n_slack = len(self.slack)
        self.ntapm = len(self.k_m)
        self.ntapt = len(self.k_tau)
        self.npv = len(self.pv)
        self.npq = len(self.pq)
        self.n_br_mon = len(self.br_mon_idx)
        self.n_gen_disp = len(self.gen_disp_idx)

        self.hvdc_nondisp_idx = np.where(nc.hvdc_data.dispatchable == 0)[
            0]  # TODO: Simplify this using a method in the hvdc_data class
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
            self.c_s = np.power(nc.passive_branch_data.overload_cost[self.br_mon_idx] + 0.1,
                                1.0)  # Cost squared since the slack is also squared
            self.c_v = nc.bus_data.cost_v[self.pq] + 0.1

        else:
            self.nsl = 0
            self.c_s = np.array([])
            self.c_v = np.array([])

        if optimize_nodal_capacity:
            self.nslcap = len(capacity_nodes_idx)
            self.slcap0 = np.zeros(self.nslcap)

        else:
            self.nslcap = 0
            self.slcap0 = np.array([])

        self.neq = 2 * self.nbus + self.n_slack + self.npv

        if options.ips_control_q_limits:
            self.nineq = (2 * self.n_br_mon + 2 * self.npq + self.ngen + 4 * self.n_gen_disp + 2 * self.ntapm
                          + 2 * self.ntapt + 2 * self.n_disp_hvdc + self.nsl)
        else:
            # No Reactive constraint (power curve)
            self.nineq = (2 * self.n_br_mon + 2 * self.npq + 4 * self.n_gen_disp + 2 * self.ntapm + 2 * self.ntapt
                          + 2 * self.n_disp_hvdc + self.nsl)

        # Variables

        if pf_init:

            # TODO: Determine the call to the PF when pf_init = True
            # TODO: try to substitute by using nc.generator_data.get_injections_per_bus()
            gen_in_bus = np.zeros(self.nbus)
            for i in range(self.Cgen.shape[0]):
                gen_in_bus[i] = np.sum(self.Cgen[i])
            ngenforgen = self.Cgen.T @ gen_in_bus
            allPgen = self.Cgen.T @ np.real(Sbus_pf / self.Sbase) / ngenforgen
            allQgen = self.Cgen.T @ np.imag(Sbus_pf / self.Sbase) / ngenforgen
            self.Sg_undis = allPgen[self.gen_nondisp_idx] + 1j * allQgen[self.gen_nondisp_idx]
            self.Pg = np.r_[allPgen[self.gen_disp_idx[:self.ngen]], np.zeros(self.nsh)]
            self.Qg = np.r_[allQgen[self.gen_disp_idx[:self.ngen]], np.zeros(self.nsh)]
            self.Vm = np.abs(voltage_pf)
            self.Va = np.angle(voltage_pf)
            self.tapm = nc.active_branch_data.tap_module[self.k_m]
            self.tapt = nc.active_branch_data.tap_angle[self.k_tau]
            self.Pfdc = nc.hvdc_data.Pset[self.hvdc_disp_idx]

        else:

            self.Pg = np.r_[(nc.generator_data.pmax[self.gen_disp_idx[:self.ngen]] +
                             nc.generator_data.pmin[self.gen_disp_idx[:self.ngen]])
                            / (2 * self.Sbase), np.zeros(self.nsh)]
            self.Qg = np.r_[(nc.generator_data.qmax[self.gen_disp_idx[:self.ngen]] +
                             nc.generator_data.qmin[self.gen_disp_idx[:self.ngen]])
                            / (2 * self.Sbase), np.zeros(self.nsh)]
            self.Va = np.angle(nc.bus_data.Vbus)
            self.Vm = (self.Vm_max + self.Vm_min) / 2
            self.tapm = nc.active_branch_data.tap_module[self.k_m]
            self.tapt = nc.active_branch_data.tap_angle[self.k_tau]
            self.Pfdc = np.zeros(self.n_disp_hvdc)

        if options.acopf_mode == AcOpfMode.ACOPFslacks:
            self.sl_sf = np.ones(self.n_br_mon)
            self.sl_st = np.ones(self.n_br_mon)
            self.sl_vmax = np.ones(self.npq)
            self.sl_vmin = np.ones(self.npq)
        else:
            self.sl_sf = np.array([])
            self.sl_st = np.array([])
            self.sl_vmax = np.array([])
            self.sl_vmin = np.array([])

        if optimize_nodal_capacity:
            self.slcap = np.zeros(self.nslcap)
        else:
            self.slcap = np.array([])

        self.x0 = self.var2x()
        self.NV = len(self.x0)


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
            self.tapm,
            self.tapt,
            self.Pfdc,
        ]

    def x2var(self, x: Vec):
        a = 0
        b = len(self.Va)

        Va = x[a: b]
        a = b
        b += len(self.Vm)

        Vm = x[a: b]
        a = b
        b += len(self.Pg)

        Pg = x[a: b]
        a = b
        b += len(self.Qg)

        Qg = x[a: b]
        a = b

        if self.options.acopf_mode == AcOpfMode.ACOPFslacks:
            b += M

            sl_sf = x[a: b]
            a = b
            b += M

            sl_st = x[a: b]
            a = b
            b += npq

            sl_vmax = x[a: b]
            a = b
            b += npq

            sl_vmin = x[a: b]
            a = b
            b += nslcap

        else:
            b += nslcap
            # Create empty arrays for not used variables
            sl_sf = np.zeros(0)
            sl_st = np.zeros(0)
            sl_vmax = np.zeros(0)
            sl_vmin = np.zeros(0)

        slcap = x[a:b]
        a = b
        b += ntapm

        tapm = x[a: b]
        a = b
        b += ntapt

        tapt = x[a: b]
        a = b
        b += ndc

        Pfdc = x[a: b]

    def update(self, x: Vec):
        pass

    def getJacobian(self):
        pass

    def getHessian(self):
        pass
