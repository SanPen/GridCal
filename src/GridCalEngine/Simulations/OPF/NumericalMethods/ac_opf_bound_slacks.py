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
from scipy import sparse as sp
from scipy.sparse import csc_matrix as csc
from scipy.sparse import csr_matrix as csr
from dataclasses import dataclass
from scipy.sparse import lil_matrix

from GridCalEngine.Utils.Sparse.csc import diags
from GridCalEngine.Utils.NumericalMethods.ips import interior_point_solver, IpsFunctionReturn
import GridCalEngine.Utils.NumericalMethods.autodiff as ad
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.DataStructures.numerical_circuit import compile_numerical_circuit_at, NumericalCircuit
from GridCalEngine.Simulations.PowerFlow.power_flow_worker import multi_island_pf_nc
from GridCalEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCalEngine.Simulations.OPF.opf_options import OptimalPowerFlowOptions
from GridCalEngine.enumerations import TransformerControlType, ReactivePowerControlMode
from typing import Tuple, Union
from GridCalEngine.basic_structures import Vec, CxVec, IntVec, Logger
from GridCalEngine.Simulations.OPF.NumericalMethods.ac_opf_derivatives_bound_slacks import (x2var, var2x, eval_f,
                                                                                            eval_g, eval_h,
                                                                                            jacobians_and_hessians)


def compute_autodiff_structures(x, mu, lam, compute_jac: bool, compute_hess: bool,
                                Ybus, Yf, Cg, Sd, slack, no_slack, Yt, from_idx, to_idx, pq, pv,
                                Va_max, Va_min, Vm_max, Vm_min, Pg_max, Pg_min, Qg_max, Qg_min,
                                c0, c1, c2, Sbase, rates, ig, nig, Sg_undis, h=1e-5) -> IpsFunctionReturn:
    """

    :param x:
    :param mu:
    :param lmbda:
    :param Ybus:
    :param Yf:
    :param Cg:
    :param Sd:
    :param slack:
    :param no_slack:
    :param Yt:
    :param from_idx:
    :param to_idx:
    :param Va_max:
    :param Va_min:
    :param Vm_max:
    :param Vm_min:
    :param Pg_max:
    :param Pg_min:
    :param Qg_max:
    :param Qg_min:
    :param c0:
    :param c1:
    :param c2:
    :param Sbase:
    :param rates:
    :param ig:
    :param nig:
    :param Sg_undis:
    :param h:
    :return:
    """

    # TODO: Fix this

    f = eval_f(x=x, Cg=Cg, c0=c0, c1=c1, c2=c2, ig=ig, Sbase=Sbase)
    G, Scalc = eval_g(x=x, Ybus=Ybus, Yf=Yf, Cg=Cg, Sd=Sd, ig=ig, nig=nig, Sg_undis=Sg_undis, slack=slack)
    H, Sf, St = eval_h(x=x, Yf=Yf, Yt=Yt, from_idx=from_idx, to_idx=to_idx, no_slack=no_slack, Va_max=Va_max,
                       Va_min=Va_min, Vm_max=Vm_max, Vm_min=Vm_min, Pg_max=Pg_max, Pg_min=Pg_min,
                       Qg_max=Qg_max, Qg_min=Qg_min, Cg=Cg,
                       rates=rates)

    if compute_jac:
        fx = ad.calc_autodiff_jacobian_f_obj(func=eval_f, x=x, arg=(Cg, c0, c1, c2, ig, Sbase), h=h).tocsc()
        Gx = ad.calc_autodiff_jacobian(func=eval_g, x=x, arg=(Ybus, Yf, Cg, Sd, ig, nig, Sg_undis, slack)).T.tocsc()
        Hx = ad.calc_autodiff_jacobian(func=eval_h, x=x, arg=(Yf, Yt, from_idx, to_idx, no_slack, Va_max, Va_min,
                                                              Vm_max, Vm_min, Pg_max, Pg_min, Qg_max, Qg_min, Cg,
                                                              rates)).T.tocsc()
    else:
        fx = None
        Gx = None
        Hx = None

    if compute_hess:
        fxx = ad.calc_autodiff_hessian_f_obj(func=eval_f, x=x, arg=(Cg, c0, c1, c2, ig, Sbase), h=h).tocsc()
        Gxx = ad.calc_autodiff_hessian(func=eval_g, x=x, mult=lam,
                                       arg=(Ybus, Yf, Cg, Sd, ig, nig, Sg_undis, slack)).tocsc()
        Hxx = ad.calc_autodiff_hessian(func=eval_h, x=x, mult=mu, arg=(Yf, Yt, from_idx, to_idx, no_slack, Va_max,
                                                                       Va_min, Vm_max, Vm_min, Pg_max, Pg_min,
                                                                       Qg_max, Qg_min, Cg, rates)).tocsc()
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


def compute_analytic_structures(x, mu, lmbda, compute_jac: bool, compute_hess: bool, admittances, Cg, R, X, Sd,
                                slack, from_idx, to_idx, fdc, tdc, ndc, pq, pv, Pdcmax, V_U, V_L, P_U, P_L, tanmax, Q_U,
                                Q_L, tapm_max, tapm_min, tapt_max, tapt_min, alltapm, alltapt, k_m, k_tau, c0, c1, c2,
                                c_s, c_v, Sbase, rates, il, nll, ig, nig, Sg_undis, ctQ) -> IpsFunctionReturn:
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
    :return:
    """
    M, N = admittances.Cf.shape
    Ng = len(ig)
    ntapm = len(k_m)
    ntapt = len(k_tau)
    npq = len(pq)

    alltapm0 = alltapm.copy()
    alltapt0 = alltapt.copy()

    _, _, _, _, _, tapm, tapt, _ = x2var(x=x, nVa=N, nVm=N, nPg=Ng, nQg=Ng, npq=npq, M=nll, ntapm=ntapm, ntapt=ntapt,
                                         ndc=ndc)

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
    G, Scalc = eval_g(x=x, Ybus=Ybus, Yf=Yf, Cg=Cg, Sd=Sd, ig=ig, nig=nig, nll=nll, npq=npq,
                      pv=pv, fdc=fdc, tdc=tdc, k_m=k_m, k_tau=k_tau, Vm_max=V_U, Sg_undis=Sg_undis, slack=slack)
    H, Sf, St = eval_h(x=x, Yf=Yf, Yt=Yt, from_idx=from_idx, to_idx=to_idx, pq=pq, k_m=k_m, k_tau=k_tau, Vm_max=V_U,
                       Vm_min=V_L, Pg_max=P_U, Pg_min=P_L, Qg_max=Q_U, Qg_min=Q_L, tapm_max=tapm_max, tapm_min=tapm_min,
                       tapt_max=tapt_max, tapt_min=tapt_min, Pdcmax=Pdcmax,
                       rates=rates, il=il, ig=ig, tanmax=tanmax, ctQ=ctQ)

    fx, Gx, Hx, fxx, Gxx, Hxx = jacobians_and_hessians(x=x, c1=c1, c2=c2, c_s=c_s, c_v=c_v, Cg=Cg, Cf=Cf, Ct=Ct, Yf=Yf,
                                                       Yt=Yt, Ybus=Ybus, Sbase=Sbase, il=il, ig=ig, slack=slack, pq=pq,
                                                       pv=pv, tanmax=tanmax, alltapm=alltapm, alltapt=alltapt, fdc=fdc,
                                                       tdc=tdc, k_m=k_m, k_tau=k_tau, mu=mu, lmbda=lmbda, R=R, X=X,
                                                       F=from_idx, T=to_idx, ctQ=ctQ, compute_jac=compute_jac,
                                                       compute_hess=compute_hess)

    return IpsFunctionReturn(f=f, G=G, H=H,
                             fx=fx, Gx=Gx, Hx=Hx,
                             fxx=fxx, Gxx=Gxx, Hxx=Hxx,
                             S=Scalc, St=St, Sf=Sf)


def evaluate_power_flow_debug(x, mu, lmbda, compute_jac: bool, compute_hess: bool,
                              Ybus, Yf, Cg, Cf, Ct, Sd, slack, no_slack, Yt, from_idx, to_idx, pq, pv,
                              th_max, th_min, V_U, V_L, P_U, P_L, Q_U, Q_L,
                              c0, c1, c2, Sbase, rates, il, ig, nig, Sg_undis, h=1e-5) -> IpsFunctionReturn:
    """

    :param x:
    :param mu:
    :param lmbda:
    :param Ybus:
    :param Yf:
    :param Cg:
    :param Cf:
    :param Ct:
    :param Sd:
    :param slack:
    :param no_slack:
    :param Yt:
    :param from_idx:
    :param to_idx:
    :param th_max:
    :param th_min:
    :param V_U:
    :param V_L:
    :param P_U:
    :param P_L:
    :param Q_U:
    :param Q_L:
    :param c0:
    :param c1:
    :param c2:
    :param Sbase:
    :param rates:
    :param il:
    :param ig:
    :param nig:
    :param Sg_undis:
    :param h:
    :return:
    """

    # TODO: Fix missing parameters

    mats_analytic = compute_analytic_structures(x, mu, lmbda, compute_jac, compute_hess,
                                                Ybus, Yf, Cg, Cf, Ct, Sd, slack, no_slack, Yt, from_idx,
                                                to_idx,
                                                th_max, th_min, V_U, V_L, P_U, P_L, Q_U, Q_L, c0, c1, c2, Sbase, rates,
                                                il, ig, nig, Sg_undis)

    mats_finite = compute_autodiff_structures(x, mu, lmbda, compute_jac, compute_hess,
                                              Ybus, Yf, Cg, Sd, slack, no_slack, Yt, from_idx, to_idx,
                                              th_max, th_min, V_U, V_L, P_U, P_L, Q_U, Q_L, c0, c1, c2, Sbase, rates,
                                              il, ig, nig, Sg_undis, h=h)

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
    lam_p: Vec = None
    lam_q: Vec = None
    error: float = None
    converged: bool = None
    iterations: int = None

    def initialize(self, nbus: int, nbr: int, ng: int) -> None:
        """
        Initialize the arrays
        :param nbus:
        :param nbr:
        :param ng:
        :return:
        """
        self.Va: Vec = np.zeros(nbus)
        self.Vm: Vec = np.zeros(nbus)
        self.S: CxVec = np.zeros(nbus, dtype=complex)
        self.Sf: CxVec = np.zeros(nbr, dtype=complex)
        self.St: CxVec = np.zeros(nbr, dtype=complex)
        self.loading: Vec = np.zeros(nbr)
        self.Pg: Vec = np.zeros(ng)
        self.Qg: Vec = np.zeros(ng)
        self.lam_p: Vec = np.zeros(nbus)
        self.lam_q: Vec = np.zeros(nbus)
        self.error: float = 0.0
        self.converged: bool = False
        self.iterations: int = 0

    def merge(self, other: "NonlinearOPFResults",
              bus_idx: IntVec, br_idx: IntVec, gen_idx: IntVec):
        """

        :param other:
        :param bus_idx:
        :param br_idx:
        :param gen_idx:
        """
        self.Va[bus_idx] = other.Va
        self.Vm[bus_idx] = other.Vm
        self.S[bus_idx] = other.S
        self.Sf[br_idx] = other.Sf
        self.St[br_idx] = other.St
        self.loading[br_idx] = other.loading
        self.Pg[gen_idx] = other.Pg
        self.Qg[gen_idx] = other.Qg
        self.lam_p[bus_idx] = other.lam_p
        self.lam_q[bus_idx] = other.lam_q
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
                          logger: Logger = Logger()) -> NonlinearOPFResults:
    """

    :param nc: NumericalCircuit
    :param pf_options: PowerFlowOptions
    :param opf_options: OptimalPowerFlowOptions
    :param debug: if true, the jacobians, hessians, etc are checked against finite difeerence versions of them
    :param use_autodiff: use the autodiff version of the structures
    :param pf_init: Initialize with power flow
    :param Sbus_pf: Sbus initial solution
    :param voltage_pf: Voltage initl solution
    :param plot_error: Plot the error?
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
    il = nc.branch_data.get_monitor_enabled_indices()
    ig = nc.generator_data.get_dispatchable_indices()
    ind_gens = np.arange(len(Pg_max))
    nig = np.where(~np.isin(ind_gens, ig))[0]
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

    c0 = nc.generator_data.cost_0[ig]
    c1 = nc.generator_data.cost_1[ig]
    c2 = nc.generator_data.cost_2[ig]

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
    nll = len(il)
    ngg = len(ig)

    ndc = nc.nhvdc
    fdc = nc.hvdc_data.F
    tdc = nc.hvdc_data.T
    Pdcmax = nc.hvdc_data.rate

    # Slack relaxations for constraints
    c_s = nc.branch_data.overload_cost[il]
    c_v = nc.bus_data.cost_v[pq]

    nsl = 2 * npq + 2 * nll

    # Number of equalities: Nodal power balances, the voltage module of slack and pv buses and the slack reference
    NE = 2 * nbus + n_slack + npv

    # Number of inequalities: Line ratings, max and min angle of buses, voltage module range and

    if pf_options.control_Q == ReactivePowerControlMode.NoControl:
        # Without Reactive power constraint (power curve)
        NI = 2 * nll + 2 * npq + 4 * ngg + 2 * ntapm + 2 * ntapt + 2 * ndc + nsl
    else:
        NI = 2 * nll + 2 * npq + 5 * ngg + 2 * ntapm + 2 * ntapt + 2 * ndc + nsl

    # ignore power from Z and I of the load

    if pf_init:
        s0gen = (Sbus_pf - nc.load_data.get_injections_per_bus()) / nc.Sbase
        p0gen = (nc.generator_data.C_bus_elm.T @ np.real(s0gen))[ig]
        q0gen = (nc.generator_data.C_bus_elm.T @ np.imag(s0gen))[ig]
        vm0 = np.abs(voltage_pf)
        va0 = np.angle(voltage_pf)
        tapm0 = nc.branch_data.tap_module[k_m]
        tapt0 = nc.branch_data.tap_angle[k_tau]
        Pfdc0 = np.zeros(ndc)

    # nc.Vbus  # dummy initialization
    else:
        p0gen = ((nc.generator_data.pmax + nc.generator_data.pmin) / (2 * nc.Sbase))[ig]
        q0gen = ((nc.generator_data.qmax + nc.generator_data.qmin) / (2 * nc.Sbase))[ig]
        va0 = np.angle(nc.bus_data.Vbus)
        vm0 = (Vm_max + Vm_min) / 2
        tapm0 = nc.branch_data.tap_module[k_m]
        tapt0 = nc.branch_data.tap_angle[k_tau]
        Pfdc0 = np.zeros(ndc)

    # compose the initial values
    x0 = var2x(Va=va0,
               Vm=vm0,
               Pg=p0gen,
               Qg=q0gen,
               sl=np.zeros(nsl),
               tapm=tapm0,
               tapt=tapt0,
               Pfdc=Pfdc0)

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
                                            k_m, k_tau, k_mtau, c0, c1, c2, Sbase, rates, il, ig, nig, Sg_undis,
                                            pf_options.control_Q),
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
                                                c0, c1, c2, Sbase, rates, il, ig, nig, Sg_undis, 1e-5),
                                           verbose=opf_options.verbose,
                                           max_iter=opf_options.ips_iterations,
                                           tol=opf_options.ips_tolerance,
                                           trust=opf_options.ips_trust_radius)
        else:
            # run the solver with the analytic derivatives
            result = interior_point_solver(x0=x0, n_x=NV, n_eq=NE, n_ineq=NI,
                                           func=compute_analytic_structures,
                                           arg=(admittances, Cg, R, X, Sd, slack, from_idx, to_idx, fdc, tdc, ndc, pq,
                                                pv, Pdcmax, Vm_max, Vm_min, Pg_max, Pg_min, tanmax, Qg_max, Qg_min,
                                                tapm_max, tapm_min, tapt_max, tapt_min, alltapm, alltapt, k_m, k_tau,
                                                c0, c1, c2, c_s, c_v, Sbase, rates, il, nll, ig, nig, Sg_undis,
                                                pf_options.control_Q),
                                           verbose=opf_options.verbose,
                                           max_iter=opf_options.ips_iterations,
                                           tol=opf_options.ips_tolerance,
                                           trust=opf_options.ips_trust_radius)

    # convert the solution to the problem variables
    Va, Vm, Pg_dis, Qg_dis, sl, tapm, tapt, Pfdc = x2var(result.x,
                                                         nVa=nbus, nVm=nbus, nPg=ngg, nQg=ngg,
                                                         M=nll, npq=npq, ntapm=ntapm, ntapt=ntapt, ndc=ndc)

    # Save Results DataFrame for tests
    # pd.DataFrame(Va).transpose().to_csv('pegase89resth.csv')
    # pd.DataFrame(Vm).transpose().to_csv('pegase89resV.csv')
    # pd.DataFrame(Pg_dis).transpose().to_csv('pegase89resP.csv')
    # pd.DataFrame(Qg_dis).transpose().to_csv('pegase89resQ.csv')

    Pg = np.zeros(len(ind_gens))
    Qg = np.zeros(len(ind_gens))

    Pg[ig] = Pg_dis
    Qg[ig] = Qg_dis
    Pg[nig] = np.real(Sg_undis)
    Qg[nig] = np.imag(Sg_undis)

    # convert the lagrange multipliers to significant ones
    lam_p, lam_q = result.lam[:nbus], result.lam[nbus:2 * nbus]

    S = result.structs.S
    Sf = result.structs.Sf
    St = result.structs.St
    loading = np.abs(Sf) / (rates + 1e-9)
    if opf_options.verbose > 0:
        df_bus = pd.DataFrame(data={'Va (rad)': Va, 'Vm (p.u.)': Vm,
                                    'dual price (€/MW)': lam_p, 'dual price (€/MVAr)': lam_q})
        df_gen = pd.DataFrame(data={'P (MW)': Pg * nc.Sbase, 'Q (MVAr)': Qg * nc.Sbase})
        df_linkdc = pd.DataFrame(data={'P_dc (MW)': Pfdc * nc.Sbase})

        df_slacks = pd.DataFrame(data={'Slacks': sl})

        df_trafo_m = pd.DataFrame(data={'V (p.u.)': tapm}, index=k_m)
        df_trafo_tau = pd.DataFrame(data={'Tau (rad)': tapt}, index=k_tau)

        print()
        print("Bus:\n", df_bus)
        print("V-Trafos:\n", df_trafo_m)
        print("Tau-Trafos:\n", df_trafo_tau)
        print("Gen:\n", df_gen)
        print("Link DC:\n", df_linkdc)
        print("Slacks:\n", df_slacks)
        print("Error", result.error)
        print("Gamma", result.gamma)
        print("Sf", result.structs.Sf)

    if plot_error:
        result.plot_error()

    if not result.converged or result.converged:
        for bus in range(nbus):
            if abs(result.dlam[bus]) >= 1e-3 or abs(result.dlam[nbus + bus]) >= 1e-3:
                logger.add_warning('Nodal Power Balance convergence tolerance not achieved', device=str(bus),
                                   value=str((result.dlam[bus], result.dlam[bus + nbus])), expected_value='< 1e-3')

        for pvbus in range(npv):
            if abs(result.dlam[2 * nbus + 1 + pvbus]) >= 1e-3:
                logger.add_warning('PV voltage module convergence tolerance not achieved', device=str(pv[pvbus]),
                                   value=str((result.dlam[2 * nbus + 1 + pvbus])), expected_value='< 1e-3')

        for l in range(nll):
            muz_f = abs(result.z[l] * result.mu[l])
            muz_t = abs(result.z[l + nll] * result.mu[l + nll])
            if muz_f >= 1e-3 or muz_t >= 1e-3:
                logger.add_warning('Line rating constraint violated', device=str(l),
                                   value=str((muz_f, muz_t)), expected_value='< 1e-3')
        for link in range(ndc):
            muz_f = abs(result.z[NI - 2 * ndc + link] * result.mu[NI - 2 * ndc + link])
            muz_t = abs(result.z[NI - ndc + link] * result.mu[NI - ndc + link])
            if muz_f >= 1e-3 or muz_t >= 1e-3:
                logger.add_warning('DC Link rating constraint violated', device=str(link),
                                   value=str((muz_f, muz_t)), expected_value='< 1e-3')

    logger.print()
    return NonlinearOPFResults(Va=Va, Vm=Vm, S=S, Sf=Sf, St=St, loading=loading,
                               Pg=Pg, Qg=Qg, lam_p=lam_p, lam_q=lam_q,
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
                      plot_error: bool = False,
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
    :param plot_error: Plot the error?
    :param logger: Logger object
    :return: NonlinearOPFResults
    """

    # compile the system
    nc = compile_numerical_circuit_at(circuit=grid, t_idx=t_idx)

    # run power flow to initialize
    if pf_init:
        pf_results = multi_island_pf_nc(nc=nc, options=pf_options)
        Sbus_pf = pf_results.Sbus
        voltage_pf = pf_results.voltage
    else:
        Sbus_pf = None
        voltage_pf = None

    islands = nc.split_into_islands(ignore_single_node_islands=True,
                                    consider_hvdc_as_island_links=True)

    results = NonlinearOPFResults()
    results.initialize(nbus=nc.nbus, nbr=nc.nbr, ng=nc.ngen)
    results.converged = True  # we assume this so that the "and" works later
    for island in islands:

        if pf_init:
            island_Sbus_pf = Sbus_pf[island.original_bus_idx]
            island_voltage_pf = voltage_pf[island.original_bus_idx]
        else:
            island_Sbus_pf = None
            island_voltage_pf = None

        island_res = ac_optimal_power_flow(nc=island,
                                           opf_options=opf_options,
                                           pf_options=pf_options,
                                           debug=debug,
                                           use_autodiff=use_autodiff,
                                           pf_init=pf_init,
                                           Sbus_pf=island_Sbus_pf,
                                           voltage_pf=island_voltage_pf,
                                           plot_error=plot_error,
                                           logger=logger)

        results.merge(other=island_res,
                      bus_idx=island.bus_data.original_idx,
                      br_idx=island.branch_data.original_idx,
                      gen_idx=island.generator_data.original_idx)
        results.error = max(results.error, island_res.error)
        results.iterations = max(results.iterations, island_res.iterations)
        results.converged = results.converged and island_res.converged

    return results
