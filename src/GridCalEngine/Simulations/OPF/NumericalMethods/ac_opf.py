# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
import numpy as np
import pandas as pd
from dataclasses import dataclass
from GridCalEngine.Utils.NumericalMethods.ips import interior_point_solver, IpsFunctionReturn
import GridCalEngine.Utils.NumericalMethods.autodiff as ad
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.DataStructures.numerical_circuit import compile_numerical_circuit_at, NumericalCircuit
from GridCalEngine.Simulations.PowerFlow.power_flow_worker import multi_island_pf_nc
from GridCalEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCalEngine.Simulations.OPF.opf_options import OptimalPowerFlowOptions
from GridCalEngine.enumerations import ReactivePowerControlMode
from typing import Union
from GridCalEngine.basic_structures import Vec, CxVec, IntVec, Logger
from GridCalEngine.Simulations.OPF.NumericalMethods.ac_opf_derivatives import (x2var, var2x, eval_f,
                                                                               eval_g, eval_h,
                                                                               jacobians_and_hessians)


def compute_autodiff_structures(x, mu, lmbda, compute_jac, compute_hess, admittances, Cg, R, X, Sd, slack, from_idx,
                                to_idx, fdc, tdc, ndc, pq, pv, Pdcmax, V_U, V_L, P_U, P_L, tanmax, Q_U, Q_L, tapm_max,
                                tapm_min, tapt_max, tapt_min, alltapm, alltapt, k_m, k_tau, c0, c1, c2, c_s, c_v, Sbase,
                                rates, il, nll, ig, nig, Sg_undis, ctQ, h=1e-5) -> IpsFunctionReturn:
    """

    :param x:
    :param mu:
    :param lmbda:
    :param compute_jac:
    :param compute_hess:
    :param admittances:
    :param Cg:
    :param R:
    :param X:
    :param Sd:
    :param slack:
    :param from_idx:
    :param to_idx:
    :param fdc:
    :param tdc:
    :param ndc:
    :param pq:
    :param pv:
    :param Pdcmax:
    :param V_U:
    :param V_L:
    :param P_U:
    :param P_L:
    :param tanmax:
    :param Q_U:
    :param Q_L:
    :param tapm_max:
    :param tapm_min:
    :param tapt_max:
    :param tapt_min:
    :param alltapm:
    :param alltapt:
    :param k_m:
    :param k_tau:
    :param c0:
    :param c1:
    :param c2:
    :param c_s:
    :param c_v:
    :param Sbase:
    :param rates:
    :param il:
    :param nll:
    :param ig:
    :param nig:
    :param Sg_undis:
    :param ctQ:
    :param h:
    :return:
    """
    M, N = admittances.Cf.shape
    Ng = len(ig)
    ntapm = len(k_m)
    ntapt = len(k_tau)
    npq = len(pq)

    alltapm0 = alltapm.copy()
    alltapt0 = alltapt.copy()

    _, _, _, _, _, _, _, _, tapm, tapt, _ = x2var(x, nVa=N, nVm=N, nPg=Ng, nQg=Ng, npq=npq,
                                                  M=nll, ntapm=ntapm, ntapt=ntapt, ndc=ndc)

    alltapm[k_m] = tapm
    alltapt[k_tau] = tapt

    admittances.modify_taps(alltapm0, alltapm, alltapt0, alltapt)

    Ybus = admittances.Ybus
    Yf = admittances.Yf
    Yt = admittances.Yt
    Cf = admittances.Cf
    Ct = admittances.Ct

    f = eval_f(x=x, Cg=Cg, k_m=k_m, k_tau=k_tau, nll=nll, c0=c0, c1=c1, c2=c2, c_s=c_s, c_v=c_v,
               ig=ig, npq=npq, ndc=ndc, Sbase=Sbase)
    G, Scalc = eval_g(x=x, Ybus=Ybus, Yf=Yf, Cg=Cg, Sd=Sd, ig=ig, nig=nig, nll=nll, npq=npq, pv=pv, fdc=fdc, tdc=tdc,
                      k_m=k_m, k_tau=k_tau, Vm_max=V_U, Sg_undis=Sg_undis, slack=slack)
    H, Sf, St = eval_h(x=x, Yf=Yf, Yt=Yt, from_idx=from_idx, to_idx=to_idx, pq=pq, k_m=k_m, k_tau=k_tau, Vm_max=V_U,
                       Vm_min=V_L, Pg_max=P_U, Pg_min=P_L, Qg_max=Q_U, Qg_min=Q_L, tapm_max=tapm_max,
                       tapm_min=tapm_min, tapt_max=tapt_max, tapt_min=tapt_min, Pdcmax=Pdcmax, rates=rates, il=il,
                       ig=ig, tanmax=tanmax, ctQ=ctQ)

    if compute_jac:
        fx = ad.calc_autodiff_jacobian_f_obj(func=eval_f, x=x, arg=(Cg, k_m, k_tau, nll, c0, c1, c2,
                                                                    c_s, c_v, ig, npq, ndc, Sbase), h=h).tocsc()
        Gx = ad.calc_autodiff_jacobian(func=eval_g, x=x, arg=(Ybus, Yf, Cg, Sd, ig, nig, nll, npq, pv, fdc,
                                                              tdc, k_m, k_tau, V_U, Sg_undis, slack)).T.tocsc()
        Hx = ad.calc_autodiff_jacobian(func=eval_h, x=x, arg=(Yf, Yt, from_idx, to_idx, pq, k_m, k_tau, V_U,
                                                              V_L, P_U, P_L, Q_U, Q_L, tapm_max,
                                                              tapm_min, tapt_max, tapt_min, Pdcmax, rates, il, ig,
                                                              tanmax, ctQ)).T.tocsc()
    else:
        fx = None
        Gx = None
        Hx = None

    if compute_hess:
        fxx = ad.calc_autodiff_hessian_f_obj(func=eval_f, x=x, arg=(Cg, k_m, k_tau, nll, c0, c1, c2,
                                                                    c_s, c_v, ig, npq, ndc, Sbase), h=h).tocsc()
        Gxx = ad.calc_autodiff_hessian(func=eval_g, x=x, mult=lmbda,
                                       arg=(Ybus, Yf, Cg, Sd, ig, nig, nll, npq, pv, fdc, tdc, k_m, k_tau, V_U,
                                            Sg_undis, slack)).T.tocsc()
        Hxx = ad.calc_autodiff_hessian(func=eval_h, x=x, mult=mu,
                                       arg=(Yf, Yt, from_idx, to_idx, pq, k_m, k_tau, V_U, V_L, P_U, P_L,
                                            Q_U, Q_L, tapm_max, tapm_min, tapt_max, tapt_min, Pdcmax, rates, il,
                                            ig, tanmax, ctQ)).T.tocsc()
    else:
        fxx = None
        Gxx = None
        Hxx = None

    # approximate the Hessian using the Gauss-Newton matrix
    # Gxx = Gx @ Gx.T
    # Hxx = Hx @ Hx.T

    return IpsFunctionReturn(f=f, G=G, H=H,
                             fx=fx, Gx=Gx, Hx=Hx,
                             fxx=fxx, Gxx=Gxx, Hxx=Hxx,
                             S=Scalc, St=St, Sf=Sf)


def compute_analytic_structures(x, mu, lmbda, compute_jac: bool, compute_hess: bool, admittances, Cg, R, X, Sd, slack,
                                from_idx, to_idx, f_nd_dc, t_nd_dc, fdc, tdc, ndc, pq, pv, Pf_nondisp, Pdcmax, V_U, V_L,
                                P_U, P_L, tanmax, Q_U, Q_L, tapm_max, tapm_min, tapt_max, tapt_min, alltapm, alltapt,
                                k_m, k_tau, c0, c1, c2, c_s, c_v, Sbase, rates, il, nll, ig, nig, Sg_undis, ctQ,
                                use_bound_slacks) -> IpsFunctionReturn:
    """
    A function that computes the optimization model for a NumericalCircuit object and returns the values of the
    equations and their derivatives computed analyitically
    :param x: State vector
    :param mu: Vector of mu multipliers
    :param lmbda: Vector of lambda multipliers
    :param compute_jac: Boolean that indicates if the Jacobians have to be calculated
    :param compute_hess: Boolean that indicates if the Hessians have to be calculated
    :param admittances: Object with all the admittance parameters stored
    :param Cg: Generator connectivity matrix
    :param R: Line Resistance
    :param X: Line inductance
    :param Sd: Load powers
    :param slack: Index of slack buses
    :param from_idx: Index of 'from' buses for each line
    :param to_idx: Index of 'to' buses for each line
    :param fdc: Index of the 'from' buses for the dispatchable DC links
    :param tdc: Index of the 'to' buses for the dispatchable DC links
    :param ndc: Number of dispatchable DC links
    :param pq: Index of PQ buses
    :param pv: Index of PV buses
    :param Pdcmax: Bound for power transmission in a DC link
    :param V_U: upper bound for voltage module per bus
    :param V_L: lower bound for voltage module per bus
    :param P_U: upper bound for active power generation per generator
    :param P_L: lower bound for active power generation per generator
    :param Q_U: upper bound for reactive power generation per generator
    :param Q_L: lower bound for reactive power generation per generator
    :param tapm_max: Upper bound for tap module per transformer
    :param tapm_min: Lower bound for tap module per transformer
    :param tapt_max: Upper bound for tap phase per transformer
    :param tapt_min: Lower bound for tap phase per transformer
    :param tanmax: Maximum value of tan(phi), where phi is the angle of the complex generation, for each generator
    :param alltapm: value of all the tap modules, including the non controlled ones
    :param alltapt: value of all the tap phases, including the non controlled ones
    :param k_m: Index of module controlled transformers
    :param k_tau: Index of phase controlles transformers
    :param c0: Base cost of each generator
    :param c1: Linear cost of each generator
    :param c2: Quadratic cost of each generator
    :param c_s: Cost of overloading each line
    :param c_v: Cost of over or undervoltage for each bus
    :param Sbase: Base power
    :param rates: Line loading limits
    :param il: Index of monitored lines
    :param nll: Number of monitored lines
    :param ig: Index of dispatchable generators
    :param nig: Number of dispatchable generators
    :param Sg_undis: undispatchable complex power
    :param ctQ: Boolean that indicates if the Reactive control applies
    :param use_bound_slacks: Determine if there will be bound slacks in the optimization model
    :return: Object with all the model equations and derivatives stored
    """
    M, N = admittances.Cf.shape
    Ng = len(ig)
    ntapm = len(k_m)
    ntapt = len(k_tau)
    npq = len(pq)

    alltapm0 = alltapm.copy()
    alltapt0 = alltapt.copy()

    _, _, _, _, _, _, _, _, tapm, tapt, _ = x2var(x, nVa=N, nVm=N, nPg=Ng, nQg=Ng, npq=npq,
                                                  M=nll, ntapm=ntapm, ntapt=ntapt, ndc=ndc,
                                                  use_bound_slacks=use_bound_slacks)

    alltapm[k_m] = tapm
    alltapt[k_tau] = tapt

    admittances.modify_taps(alltapm0, alltapm, alltapt0, alltapt)

    Ybus = admittances.Ybus
    Yf = admittances.Yf
    Yt = admittances.Yt
    Cf = admittances.Cf
    Ct = admittances.Ct

    f = eval_f(x=x, Cg=Cg, k_m=k_m, k_tau=k_tau, nll=nll, c0=c0, c1=c1, c2=c2, c_s=c_s, c_v=c_v,
               ig=ig, npq=npq, ndc=ndc, Sbase=Sbase, use_bound_slacks=use_bound_slacks)
    G, Scalc = eval_g(x=x, Ybus=Ybus, Yf=Yf, Cg=Cg, Sd=Sd, ig=ig, nig=nig, nll=nll, npq=npq, pv=pv, f_nd_dc=f_nd_dc,
                      t_nd_dc=t_nd_dc, fdc=fdc, tdc=tdc, Pf_nondisp=Pf_nondisp, k_m=k_m, k_tau=k_tau, Vm_max=V_U,
                      Sg_undis=Sg_undis, slack=slack, use_bound_slacks=use_bound_slacks)
    H, Sf, St = eval_h(x=x, Yf=Yf, Yt=Yt, from_idx=from_idx, to_idx=to_idx, pq=pq, k_m=k_m, k_tau=k_tau, Vm_max=V_U,
                       Vm_min=V_L, Pg_max=P_U, Pg_min=P_L, Qg_max=Q_U, Qg_min=Q_L, tapm_max=tapm_max, tapm_min=tapm_min,
                       tapt_max=tapt_max, tapt_min=tapt_min, Pdcmax=Pdcmax,
                       rates=rates, il=il, ig=ig, tanmax=tanmax, ctQ=ctQ, use_bound_slacks=use_bound_slacks)

    fx, Gx, Hx, fxx, Gxx, Hxx = jacobians_and_hessians(x=x, c1=c1, c2=c2, c_s=c_s, c_v=c_v, Cg=Cg, Cf=Cf, Ct=Ct, Yf=Yf,
                                                       Yt=Yt, Ybus=Ybus, Sbase=Sbase, il=il, ig=ig, slack=slack, pq=pq,
                                                       pv=pv, tanmax=tanmax, alltapm=alltapm, alltapt=alltapt, fdc=fdc,
                                                       tdc=tdc, k_m=k_m, k_tau=k_tau, mu=mu, lmbda=lmbda, R=R, X=X,
                                                       F=from_idx, T=to_idx, ctQ=ctQ, use_bound_slacks=use_bound_slacks,
                                                       compute_jac=compute_jac, compute_hess=compute_hess)

    return IpsFunctionReturn(f=f, G=G, H=H,
                             fx=fx, Gx=Gx, Hx=Hx,
                             fxx=fxx, Gxx=Gxx, Hxx=Hxx,
                             S=Scalc, St=St, Sf=Sf)


def evaluate_power_flow_debug(x, mu, lmbda, compute_jac, compute_hess, admittances, Cg, R, X, Sd, slack, from_idx,
                              to_idx, fdc, tdc, ndc, pq, pv, Pdcmax, V_U, V_L, P_U, P_L, tanmax, Q_U, Q_L, tapm_max,
                              tapm_min, tapt_max, tapt_min, alltapm, alltapt, k_m, k_tau, c0, c1, c2, c_s, c_v, Sbase,
                              rates, il, nll, ig, nig, Sg_undis, ctQ, use_bound_slacks, h=1e-5) -> IpsFunctionReturn:
    """

    :param x: State vector
    :param mu: Vector of mu multipliers
    :param lmbda: Vector of lambda multipliers
    :param compute_jac: Boolean that indicates if the Jacobians have to be calculated
    :param compute_hess: Boolean that indicates if the Hessians have to be calculated
    :param admittances: Object with all the admittance parameters stored
    :param Cg: Generator connectivity matrix
    :param R: Line Resistance
    :param X: Line inductance
    :param Sd: Load powers
    :param slack: Index of slack buses
    :param from_idx: Index of 'from' buses for each line
    :param to_idx: Index of 'to' buses for each line
    :param fdc: Index of the 'from' buses for the dispatchable DC links
    :param tdc: Index of the 'to' buses for the dispatchable DC links
    :param ndc: Number of dispatchable DC links
    :param pq: Index of PQ buses
    :param pv: Index of PV buses
    :param Pdcmax: Bound for power transmission in a DC link
    :param V_U: upper bound for voltage module per bus
    :param V_L: lower bound for voltage module per bus
    :param P_U: upper bound for active power generation per generator
    :param P_L: lower bound for active power generation per generator
    :param Q_U: upper bound for reactive power generation per generator
    :param Q_L: lower bound for reactive power generation per generator
    :param tapm_max: Upper bound for tap module per transformer
    :param tapm_min: Lower bound for tap module per transformer
    :param tapt_max: Upper bound for tap phase per transformer
    :param tapt_min: Lower bound for tap phase per transformer
    :param tanmax: Maximum value of tan(phi), where phi is the angle of the complex generation, for each generator
    :param alltapm: value of all the tap modules, including the non controlled ones
    :param alltapt: value of all the tap phases, including the non controlled ones
    :param k_m: Index of module controlled transformers
    :param k_tau: Index of phase controlles transformers
    :param c0: Base cost of each generator
    :param c1: Linear cost of each generator
    :param c2: Quadratic cost of each generator
    :param c_s: Cost of overloading each line
    :param c_v: Cost of over or undervoltage for each bus
    :param Sbase: Base power
    :param rates: Line loading limits
    :param il: Index of monitored lines
    :param nll: Number of monitored lines
    :param ig: Index of dispatchable generators
    :param nig: Number of dispatchable generators
    :param Sg_undis: undispatchable complex power
    :param ctQ: Boolean that indicates if the Reactive control applies
    :param use_bound_slacks: Determine if there will be bound slacks in the optimization model
    :param h: Tolerance used for the autodiferentiation
    :return: return the resulting error between the autodif and the analytic derivation
    """

    mats_analytic = compute_analytic_structures(x, mu, lmbda, compute_jac, compute_hess, admittances, Cg, R, X, Sd,
                                                slack, from_idx, to_idx, fdc, tdc, ndc, pq, pv, Pdcmax, V_U, V_L, P_U,
                                                P_L, tanmax, Q_U, Q_L, tapm_max, tapm_min, tapt_max, tapt_min, alltapm,
                                                alltapt, k_m, k_tau, c0, c1, c2, c_s, c_v, Sbase, rates, il, nll, ig,
                                                nig, Sg_undis, ctQ, use_bound_slacks=use_bound_slacks)

    mats_finite = compute_autodiff_structures(x, mu, lmbda, compute_jac, compute_hess, admittances, Cg, R, X, Sd,
                                              slack, from_idx, to_idx, fdc, tdc, ndc, pq, pv, Pdcmax, V_U, V_L, P_U,
                                              P_L, tanmax, Q_U, Q_L, tapm_max, tapm_min, tapt_max, tapt_min, alltapm,
                                              alltapt, k_m, k_tau, c0, c1, c2, c_s, c_v, Sbase, rates, il, nll, ig,
                                              nig, Sg_undis, ctQ, h=h)

    errors = mats_finite.compare(mats_analytic, h=h)

    if len(errors) > 0:
        for key, struct in errors.items():
            print(key + "\n", struct)

        raise Exception('The analytic structures differ from the finite differences: {}'.format(errors))

    return mats_analytic


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
    error: float = None
    converged: bool = None
    iterations: int = None

    def initialize(self, nbus: int, nbr: int, ng: int, nhvdc: int):
        """
        Initialize the arrays
        :param nbus: number of buses
        :param nbr: number of branches
        :param ng: number of generators
        :param nhvdc: number of HVDC
        """
        self.Va: Vec = np.zeros(nbus)
        self.Vm: Vec = np.zeros(nbus)
        self.S: CxVec = np.zeros(nbus, dtype=complex)
        self.Sf: CxVec = np.zeros(nbr, dtype=complex)
        self.St: CxVec = np.zeros(nbr, dtype=complex)
        self.loading: Vec = np.zeros(nbr)
        self.Pg: Vec = np.zeros(ng)
        self.Qg: Vec = np.zeros(ng)
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
        self.error: float = 0.0
        self.converged: bool = False
        self.iterations: int = 0

    def merge(self, other: "NonlinearOPFResults",
              bus_idx: IntVec, br_idx: IntVec, il_idx: IntVec, gen_idx: IntVec, hvdc_idx: IntVec,
              use_bound_slacks):
        """

        :param other:
        :param bus_idx:
        :param br_idx:
        :param gen_idx:
        :param hvdc_idx:
        """
        self.Va[bus_idx] = other.Va
        self.Vm[bus_idx] = other.Vm
        self.S[bus_idx] = other.S
        self.Sf[br_idx] = other.Sf
        self.St[br_idx] = other.St
        self.loading[br_idx] = other.loading
        self.Pg[gen_idx] = other.Pg
        self.Qg[gen_idx] = other.Qg
        self.Pcost[gen_idx] = other.Pcost
        self.tap_module[br_idx] = other.tap_module
        self.tap_phase[br_idx] = other.tap_phase
        self.hvdc_Pf[hvdc_idx] = other.hvdc_Pf
        self.hvdc_loading[hvdc_idx] = other.hvdc_loading
        self.lam_p[bus_idx] = other.lam_p
        self.lam_q[bus_idx] = other.lam_q
        if use_bound_slacks:
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


def ac_optimal_power_flow(nc: NumericalCircuit,
                          pf_options: PowerFlowOptions,
                          opf_options: OptimalPowerFlowOptions,
                          debug: bool = False,
                          use_autodiff: bool = False,
                          pf_init: bool = False,
                          Sbus_pf: Union[CxVec, None] = None,
                          voltage_pf: Union[CxVec, None] = None,
                          plot_error: bool = False,
                          use_bound_slacks: bool = True,
                          logger: Logger = Logger()) -> NonlinearOPFResults:
    """

    :param nc: NumericalCircuit
    :param pf_options: PowerFlowOptions
    :param opf_options: OptimalPowerFlowOptions
    :param debug: if true, the jacobians, hessians, etc are checked against finite difeerence versions of them
    :param use_autodiff: use the autodiff version of the structures
    :param pf_init: Initialize with power flow
    :param Sbus_pf: Sbus initial solution
    :param voltage_pf: Voltage initial solution
    :param plot_error: Plot the error evolution. Default: False
    :param use_bound_slacks: add voltage module and branch loading slack variables? (default true)
    :param logger: Logger
    :return: NonlinearOPFResults
    """

    # Grab the base power and the costs associated to generation
    Sbase = nc.Sbase

    # Compute the admittance elements, including the Ybus, Yf, Yt and connectivity matrices
    admittances = nc.get_admittance_matrices()
    Cg = nc.generator_data.C_bus_elm
    from_idx = nc.F
    to_idx = nc.T

    # Bus and line parameters
    Sd = - nc.load_data.get_injections_per_bus() / Sbase
    Pg_max = nc.generator_data.pmax / Sbase
    Pg_min = nc.generator_data.pmin / Sbase
    Qg_max = nc.generator_data.qmax / Sbase
    Qg_min = nc.generator_data.qmin / Sbase
    Vm_max = nc.bus_data.Vmax
    Vm_min = nc.bus_data.Vmin
    pf = nc.generator_data.pf
    tanmax = ((1 - pf ** 2) ** (1 / 2)) / (pf + 1e-15)

    # PV buses are identified by those who have the same upper and lower limits for the voltage. Slack obtained from nc
    pv = np.flatnonzero(Vm_max == Vm_min)
    pq = np.flatnonzero(Vm_max != Vm_min)
    slack = nc.vd

    # Check the active elements and their operational limits.
    br_mon_idx = nc.branch_data.get_monitor_enabled_indices()
    gen_disp_idx = nc.generator_data.get_dispatchable_indices()
    ind_gens = np.arange(len(Pg_max))
    nig = np.where(~np.isin(ind_gens, gen_disp_idx))[0]
    Sg_undis = (nc.generator_data.get_injections() / nc.Sbase)[nig]
    rates = nc.rates / Sbase  # Line loading limits. If the grid is not well conditioned, add constant value (i.e. +100)
    Va_max = nc.bus_data.angle_max  # This limits are not really used as of right now.
    Va_min = nc.bus_data.angle_min

    # Transformer control modes and line parameters to calculate the associated derivatives w.r.t the tap variables.
    k_m = nc.k_m
    k_tau = nc.k_tau
    k_mtau = nc.k_mtau
    R = nc.branch_data.R
    X = nc.branch_data.X

    c0 = nc.generator_data.cost_0[gen_disp_idx]
    c1 = nc.generator_data.cost_1[gen_disp_idx]
    c2 = nc.generator_data.cost_2[gen_disp_idx]

    # Transformer operational limits
    tapm_max = nc.branch_data.tap_module_max[k_m]
    tapm_min = nc.branch_data.tap_module_min[k_m]
    tapt_max = nc.branch_data.tap_angle_max[k_tau]
    tapt_min = nc.branch_data.tap_angle_min[k_tau]
    alltapm = nc.branch_data.tap_module  # We grab all tapm even when uncontrolled since the indexing is needed
    # if the tapt of the same trafo is variable.
    alltapt = nc.branch_data.tap_angle  # We grab all tapt even when uncontrolled since the indexing is needed if
    # the tapm of the same trafo is variable.

    # Sizing of the problem
    nbus = nc.bus_data.nbus
    n_slack = len(slack)
    ntapm = len(k_m)
    ntapt = len(k_tau)
    npv = len(pv)
    npq = len(pq)
    n_br_mon = len(br_mon_idx)
    n_gen_disp = len(gen_disp_idx)

    hvdc_nondisp_idx = np.where(nc.hvdc_data.dispatchable == 0)[0]
    hvdc_disp_idx = np.where(nc.hvdc_data.dispatchable == 1)[0]

    f_nd_hvdc = nc.hvdc_data.F[hvdc_nondisp_idx]
    t_nd_hvdc = nc.hvdc_data.T[hvdc_nondisp_idx]
    Pf_nondisp = nc.hvdc_data.Pset[hvdc_nondisp_idx]

    n_disp_hvdc = len(hvdc_disp_idx)
    f_disp_hvdc = nc.hvdc_data.F[hvdc_disp_idx]
    t_disp_hvdc = nc.hvdc_data.T[hvdc_disp_idx]
    P_hvdc_max = nc.hvdc_data.rate[hvdc_disp_idx]

    if use_bound_slacks:
        nsl = 2 * npq + 2 * n_br_mon
        # Slack relaxations for constraints
        c_s = 0.0000001 * nc.branch_data.overload_cost[br_mon_idx] + 1e-9
        c_v = 1000 * nc.bus_data.cost_v[pq] + 1e-9
        sl_sf0 = np.ones(n_br_mon)
        sl_st0 = np.ones(n_br_mon)
        sl_vmax0 = np.ones(npq)
        sl_vmin0 = np.ones(npq)

    else:
        nsl = 0
        c_s = np.array([])
        c_v = np.array([])
        sl_sf0 = np.array([])
        sl_st0 = np.array([])
        sl_vmax0 = np.array([])
        sl_vmin0 = np.array([])

    # Number of equalities: Nodal power balances, the voltage module of slack and pv buses and the slack reference
    NE = 2 * nbus + n_slack + npv

    # Number of inequalities: Line ratings, max and min angle of buses, voltage module range and

    if pf_options.control_Q == ReactivePowerControlMode.NoControl:
        NI = 2 * n_br_mon + 2 * npq + 4 * n_gen_disp + 2 * ntapm + 2 * ntapt + 2 * n_disp_hvdc + nsl  # No Reactive constraint (power curve)
    else:
        NI = 2 * n_br_mon + 2 * npq + 5 * n_gen_disp + 2 * ntapm + 2 * ntapt + 2 * n_disp_hvdc + nsl

    # ignore power from Z and I of the load

    if pf_init:
        p0gen = nc.generator_data.p[gen_disp_idx]
        q0gen = (nc.generator_data.C_bus_elm.T @ np.imag(Sbus_pf / nc.Sbase))[gen_disp_idx]
        vm0 = np.abs(voltage_pf)
        va0 = np.angle(voltage_pf)
        tapm0 = nc.branch_data.tap_module[k_m]
        tapt0 = nc.branch_data.tap_angle[k_tau]
        Pf0_hvdc = nc.hvdc_data.Pset[hvdc_disp_idx]

    else:
        p0gen = (nc.generator_data.pmax[gen_disp_idx] + nc.generator_data.pmin[gen_disp_idx]) / (2 * nc.Sbase)
        q0gen = (nc.generator_data.qmax[gen_disp_idx] + nc.generator_data.qmin[gen_disp_idx]) / (2 * nc.Sbase)
        va0 = np.angle(nc.bus_data.Vbus)
        vm0 = (Vm_max + Vm_min) / 2
        tapm0 = nc.branch_data.tap_module[k_m]
        tapt0 = nc.branch_data.tap_angle[k_tau]
        Pf0_hvdc = np.zeros(n_disp_hvdc)

    # compose the initial values
    x0 = var2x(Va=va0,
               Vm=vm0,
               Pg=p0gen,
               Qg=q0gen,
               sl_sf=sl_sf0,
               sl_st=sl_st0,
               sl_vmax=sl_vmax0,
               sl_vmin=sl_vmin0,
               tapm=tapm0,
               tapt=tapt0,
               Pfdc=Pf0_hvdc)

    # number of variables
    NV = len(x0)

    if opf_options.verbose > 0:
        print("x0:", x0)

    if debug:
        # run the solver with the function that checks the derivatives
        # against their finite differences equivalent
        result = interior_point_solver(x0=x0, n_x=NV, n_eq=NE, n_ineq=NI,
                                       func=evaluate_power_flow_debug,
                                       arg=(admittances, Cg, Sd, slack, from_idx, to_idx,
                                            pq, pv, Va_max, Va_min, Vm_max, Vm_min, Pg_max, Pg_min,
                                            Qg_max, Qg_min, tapm_max, tapm_min, tapt_max, tapt_min, alltapm, alltapt,
                                            k_m, k_tau, k_mtau, c0, c1, c2, Sbase, rates, br_mon_idx, gen_disp_idx, nig, Sg_undis,
                                            pf_options.control_Q, use_bound_slacks),
                                       verbose=opf_options.verbose,
                                       max_iter=opf_options.ips_iterations,
                                       tol=opf_options.ips_tolerance,
                                       trust=opf_options.ips_trust_radius)

    else:
        if use_autodiff:
            # run the solver with the autodiff derivatives
            result = interior_point_solver(x0=x0, n_x=NV, n_eq=NE, n_ineq=NI,
                                           func=compute_autodiff_structures,
                                           arg=(admittances, Cg, Sd, slack, from_idx, to_idx, pq, pv,
                                                Va_max, Va_min, Vm_max, Vm_min, Pg_max, Pg_min, Qg_max, Qg_min,
                                                tapm_max, tapm_min, tapt_max, tapt_min, k_m, k_tau, k_mtau,
                                                c0, c1, c2, Sbase, rates, br_mon_idx, gen_disp_idx, nig, Sg_undis,
                                                use_bound_slacks, 1e-5),
                                           verbose=opf_options.verbose,
                                           max_iter=opf_options.ips_iterations,
                                           tol=opf_options.ips_tolerance,
                                           trust=opf_options.ips_trust_radius)
        else:
            # run the solver with the analytic derivatives
            result = interior_point_solver(x0=x0, n_x=NV, n_eq=NE, n_ineq=NI,
                                           func=compute_analytic_structures,
                                           arg=(admittances, Cg, R, X, Sd, slack, from_idx, to_idx, f_nd_hvdc, t_nd_hvdc,
                                                f_disp_hvdc, t_disp_hvdc, n_disp_hvdc, pq, pv, Pf_nondisp, P_hvdc_max, Vm_max, Vm_min, Pg_max,
                                                Pg_min, tanmax, Qg_max, Qg_min, tapm_max, tapm_min, tapt_max, tapt_min,
                                                alltapm, alltapt, k_m, k_tau, c0, c1, c2, c_s, c_v, Sbase, rates, br_mon_idx,
                                                n_br_mon, gen_disp_idx, nig, Sg_undis, pf_options.control_Q, use_bound_slacks),
                                           verbose=opf_options.verbose,
                                           max_iter=opf_options.ips_iterations,
                                           tol=opf_options.ips_tolerance,
                                           trust=opf_options.ips_trust_radius)

    # convert the solution to the problem variables
    (Va, Vm, Pg_dis, Qg_dis, sl_sf, sl_st,
     sl_vmax, sl_vmin, tapm, tapt, Pfdc) = x2var(result.x, nVa=nbus, nVm=nbus, nPg=n_gen_disp, nQg=n_gen_disp,
                                                 M=n_br_mon, npq=npq, ntapm=ntapm, ntapt=ntapt, ndc=n_disp_hvdc,
                                                 use_bound_slacks=use_bound_slacks)

    # Save Results DataFrame for tests
    # pd.DataFrame(Va).transpose().to_csv('pegase89resth.csv')
    # pd.DataFrame(Vm).transpose().to_csv('pegase89resV.csv')
    # pd.DataFrame(Pg_dis).transpose().to_csv('pegase89resP.csv')
    # pd.DataFrame(Qg_dis).transpose().to_csv('pegase89resQ.csv')

    Pg = np.zeros(len(ind_gens))
    Qg = np.zeros(len(ind_gens))

    Pg[gen_disp_idx] = Pg_dis
    Qg[gen_disp_idx] = Qg_dis
    Pg[nig] = np.real(Sg_undis)
    Qg[nig] = np.imag(Sg_undis)

    # convert the lagrange multipliers to significant ones
    lam_p, lam_q = result.lam[:nbus], result.lam[nbus:2 * nbus]

    S = result.structs.S
    Sf = result.structs.Sf
    St = result.structs.St
    loading = np.abs(Sf) / (rates + 1e-9)
    hvdc_power = nc.hvdc_data.Pset.copy()
    hvdc_power[hvdc_disp_idx] = Pfdc
    hvdc_loading = hvdc_power / (nc.hvdc_data.rate + 1e-9)
    tap_module = np.zeros(nc.nbr)
    tap_phase = np.zeros(nc.nbr)
    tap_module[k_m] = tapm
    tap_phase[k_tau] = tapt
    Pcost = np.zeros(nc.ngen)
    Pcost[gen_disp_idx] = c0 + c1 * Pg[gen_disp_idx] + c2 * np.power(Pg[gen_disp_idx], 2.0)

    if opf_options.verbose > 0:
        df_bus = pd.DataFrame(data={'Va (rad)': Va, 'Vm (p.u.)': Vm,
                                    'dual price (€/MW)': lam_p, 'dual price (€/MVAr)': lam_q})
        df_gen = pd.DataFrame(data={'P (MW)': Pg * nc.Sbase, 'Q (MVAr)': Qg * nc.Sbase})
        df_linkdc = pd.DataFrame(data={'P_dc (MW)': Pfdc * nc.Sbase})

        df_slsf = pd.DataFrame(data={'Slacks Sf': sl_sf})
        df_slst = pd.DataFrame(data={'Slacks St': sl_st})
        df_slvmax = pd.DataFrame(data={'Slacks Vmax': sl_vmax})
        df_slvmin = pd.DataFrame(data={'Slacks Vmin': sl_vmin})
        df_trafo_m = pd.DataFrame(data={'V (p.u.)': tapm}, index=k_m)
        df_trafo_tau = pd.DataFrame(data={'Tau (rad)': tapt}, index=k_tau)

        print()
        print("Bus:\n", df_bus)
        print("V-Trafos:\n", df_trafo_m)
        print("Tau-Trafos:\n", df_trafo_tau)
        print("Gen:\n", df_gen)
        print("Link DC:\n", df_linkdc)
        print("Slacks:\n", df_slsf)
        print("Slacks:\n", df_slst)
        print("Slacks:\n", df_slvmax)
        print("Slacks:\n", df_slvmin)
        print("Error", result.error)
        print("Gamma", result.gamma)
        print("Sf", result.structs.Sf)

    if plot_error:
        result.plot_error()

    if not result.converged or result.converged:
        for bus in range(nbus):
            if abs(result.dlam[bus]) >= 1e-3:
                logger.add_warning('Nodal Power Balance convergence tolerance not achieved',
                                   device_property="dlam",
                                   device=str(bus),
                                   value=str(result.dlam[bus]),
                                   expected_value='< 1e-3')

            if abs(result.dlam[nbus + bus]) >= 1e-3:  # TODO: What is the difference with the previous?
                logger.add_warning('Nodal Power Balance convergence tolerance not achieved',
                                   device_property="dlam",
                                   device=str(bus),
                                   value=str(result.dlam[bus + nbus]),
                                   expected_value='< 1e-3')

        for pvbus in range(npv):
            if abs(result.dlam[2 * nbus + 1 + pvbus]) >= 1e-3:
                logger.add_warning('PV voltage module convergence tolerance not achieved',
                                   device_property="dlam",
                                   device=str(pv[pvbus]),
                                   value=str((result.dlam[2 * nbus + 1 + pvbus])),
                                   expected_value='< 1e-3')

        for k in range(n_br_mon):
            muz_f = abs(result.z[k] * result.mu[k])
            muz_t = abs(result.z[k + n_br_mon] * result.mu[k + n_br_mon])
            if muz_f >= 1e-3:
                logger.add_warning('Branch rating "from" multipliers did not reach the tolerance',
                                   device_property="mu · z",
                                   device=str(br_mon_idx[k]),
                                   value=str(muz_f),
                                   expected_value='< 1e-3')
            if muz_t >= 1e-3:
                logger.add_warning('Branch rating "to" multipliers did not reach the tolerance',
                                   device_property="mu · z",
                                   device=str(br_mon_idx[k]),
                                   value=str(muz_t),
                                   expected_value='< 1e-3')

        for link in range(n_disp_hvdc):
            muz_f = abs(result.z[NI - 2 * n_disp_hvdc + link] * result.mu[NI - 2 * n_disp_hvdc + link])
            muz_t = abs(result.z[NI - n_disp_hvdc + link] * result.mu[NI - n_disp_hvdc + link])
            if muz_f >= 1e-3:
                logger.add_warning('HVDC rating "from" multipliers did not reach the tolerance',
                                   device_property="mu · z",
                                   device=str(link),
                                   value=str(muz_f),
                                   expected_value='< 1e-3')
            if muz_t >= 1e-3:
                logger.add_warning('HVDC rating "to" multipliers did not reach the tolerance',
                                   device_property="mu · z",
                                   device=str(link),
                                   value=str(muz_t),
                                   expected_value='< 1e-3')

        if use_bound_slacks:
            for k in range(n_br_mon):
                if sl_sf[k] > opf_options.ips_tolerance:
                    logger.add_warning('Branch overload in the from sense',
                                       device=str(br_mon_idx[k]),
                                       device_property="Slack",
                                       value=str(sl_sf[k]),
                                       expected_value=f'< {opf_options.ips_tolerance}')

                if sl_st[k] > opf_options.ips_tolerance:
                    logger.add_warning('Branch overload in the to sense',
                                       device=str(br_mon_idx[k]),
                                       device_property="Slack",
                                       value=str(sl_st[k]),
                                       expected_value=f'< {opf_options.ips_tolerance}')

            for i in range(npq):
                if sl_vmax[i] > opf_options.ips_tolerance:
                    logger.add_warning('Overvoltage',
                                       device_property="Slack",
                                       device=str(pq[i]),
                                       value=str(sl_vmax[i]),
                                       expected_value=f'>{opf_options.ips_tolerance}')
                if sl_vmin[i] > opf_options.ips_tolerance:
                    logger.add_warning('Undervoltage',
                                       device_property="Slack",
                                       device=str(pq[i]),
                                       value=str(sl_vmin[i]),
                                       expected_value=f'> {opf_options.ips_tolerance}')

    if opf_options.verbose:
        if len(logger):
            logger.print()

    return NonlinearOPFResults(Va=Va, Vm=Vm, S=S,
                               Sf=Sf, St=St, loading=loading,
                               Pg=Pg, Qg=Qg, Pcost=Pcost,
                               tap_module=tap_module, tap_phase=tap_phase,
                               hvdc_Pf=hvdc_power, hvdc_loading=hvdc_loading,
                               lam_p=lam_p, lam_q=lam_q,
                               sl_sf=sl_sf, sl_st=sl_st, sl_vmax=sl_vmax, sl_vmin=sl_vmin,
                               error=result.error,
                               converged=result.converged,
                               iterations=result.iterations)


def run_nonlinear_opf(grid: MultiCircuit,
                      opf_options: OptimalPowerFlowOptions,
                      pf_options: PowerFlowOptions,
                      t_idx: Union[None, int] = None,
                      debug: bool = False,
                      use_autodiff: bool = False,
                      pf_init=False,
                      Sbus_pf0: Union[CxVec, None] = None,
                      voltage_pf0: Union[CxVec, None] = None,
                      plot_error: bool = False,
                      use_bound_slacks: bool = True,
                      logger: Logger = Logger()) -> NonlinearOPFResults:
    """
    Run optimal power flow for a MultiCircuit
    :param grid: MultiCircuit
    :param opf_options: OptimalPowerFlowOptions
    :param pf_options: PowerFlowOptions
    :param t_idx: Time index
    :param debug: debug? when active the autodiff is activated
    :param use_autodiff: Use autodiff?
    :param pf_init: Initialize with a power flow?
    :param Sbus_pf0: Sbus initial solution
    :param voltage_pf0: Voltage initial solution
    :param plot_error: Plot the error evolution
    :param use_bound_slacks: add voltage module and branch loading slack variables? (default true)
    :param logger: Logger object
    :return: NonlinearOPFResults
    """

    # compile the system
    nc = compile_numerical_circuit_at(circuit=grid, t_idx=t_idx)

    if pf_init:
        if Sbus_pf0 is None:
            # run power flow to initialize
            pf_results = multi_island_pf_nc(nc=nc, options=pf_options)
            Sbus_pf = pf_results.Sbus
            voltage_pf = pf_results.voltage
        else:
            # pick the passed values
            Sbus_pf = Sbus_pf0
            voltage_pf = voltage_pf0
    else:
        # initialize with sensible values
        Sbus_pf = nc.bus_data.installed_power
        voltage_pf = nc.bus_data.Vbus

    # split into islands, but considering the HVDC lineas as actual links
    islands = nc.split_into_islands(ignore_single_node_islands=True,
                                    consider_hvdc_as_island_links=True)

    # create and initialize results
    results = NonlinearOPFResults()
    results.initialize(nbus=nc.nbus, nbr=nc.nbr, ng=nc.ngen, nhvdc=nc.nhvdc)

    for i, island in enumerate(islands):
        island_res = ac_optimal_power_flow(nc=island,
                                           opf_options=opf_options,
                                           pf_options=pf_options,
                                           debug=debug,
                                           use_autodiff=use_autodiff,
                                           pf_init=pf_init,
                                           Sbus_pf=Sbus_pf[island.original_bus_idx],
                                           voltage_pf=voltage_pf[island.original_bus_idx],
                                           plot_error=plot_error,
                                           use_bound_slacks=use_bound_slacks,
                                           logger=logger)

        if pf_init and not island_res.converged:
            # if we were initializing with the power flow results and it failed, try without power flow initialization

            logger.add_warning(msg="Trying flat start because power flow initialization did not converge")

            island_res = ac_optimal_power_flow(nc=island,
                                               opf_options=opf_options,
                                               pf_options=pf_options,
                                               debug=debug,
                                               use_autodiff=use_autodiff,
                                               pf_init=False,
                                               Sbus_pf=Sbus_pf[island.original_bus_idx],
                                               voltage_pf=voltage_pf[island.original_bus_idx],
                                               plot_error=plot_error,
                                               use_bound_slacks=use_bound_slacks,
                                               logger=logger)

        results.merge(other=island_res,
                      bus_idx=island.bus_data.original_idx,
                      br_idx=island.branch_data.original_idx,
                      il_idx=island.branch_data.get_monitor_enabled_indices(),
                      gen_idx=island.generator_data.original_idx,
                      hvdc_idx=island.hvdc_data.original_idx,
                      use_bound_slacks=use_bound_slacks)
        if i > 0:
            results.error = max(results.error, island_res.error)
            results.iterations = max(results.iterations, island_res.iterations)
            results.converged = results.converged and island_res.converged if i > 0 else island_res.converged
        else:
            results.error = island_res.error
            results.iterations = island_res.iterations
            results.converged = island_res.converged

    return results
