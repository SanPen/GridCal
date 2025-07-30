# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0
from typing import Tuple
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy.sparse as sp
import GridCalEngine.api as gce

from GridCalEngine.basic_structures import Vec, CscMat, CxVec, IntVec
import GridCalEngine.Simulations.PowerFlow.NumericalMethods.common_functions as cf
from GridCalEngine.Simulations.Derivatives.ac_jacobian import AC_jacobian
from GridCalEngine.Utils.NumericalMethods.common import ConvexFunctionResult, ConvexMethodResult
from GridCalEngine.Utils.NumericalMethods.newton_raphson import newton_raphson
from GridCalEngine.Utils.NumericalMethods.powell import powell_dog_leg
from GridCalEngine.Utils.NumericalMethods.levenberg_marquadt import levenberg_marquardt
from GridCalEngine.Utils.NumericalMethods.autodiff import calc_autodiff_jacobian
from GridCalEngine.enumerations import SolverType
from GridCalEngine.Topology.admittance_matrices import AdmittanceMatrices
from GridCalEngine.Utils.Sparse.csc import diags


def var2x(Va: Vec, Vm: Vec) -> Vec:
    """
    Compose the unknowns vector
    :param Va: Array of voltage angles for the PV and PQ nodes
    :param Vm: Array of voltage modules for the PQ nodes
    :return: [Va | Vm]
    """
    return np.r_[Va, Vm]


def x2var(x: Vec, npvpq: int) -> Tuple[Vec, Vec]:
    """
    get the physical variables from the unknowns vector
    :param x: vector of unknowns
    :param npvpq: number of non slack nodes
    :return: Va, Vm
    """
    Va = x[:npvpq]
    Vm = x[npvpq:]

    return Va, Vm


def compute_g(V: CxVec,
              Ybus: CscMat,
              S0: CxVec,
              I0: CxVec,
              Y0: CxVec,
              Vm: Vec,
              m: Vec,
              tau: Vec,
              Cf,
              Ct,
              F: IntVec,
              T: IntVec,
              pq: IntVec,
              pvpq: IntVec):
    """
    Compose the power flow function
    :param V:
    :param Ybus:
    :param S0:
    :param I0:
    :param Y0:
    :param Vm:
    :param m:
    :param tau:
    :param Cf:
    :param Ct:
    :param F:
    :param T:
    :param pq:
    :param pvpq:
    :return:
    """

    # yff, yft, ytf, ytt = compute_tap_control_admittances_injectins(tap_module=m,
    #                                                                tap_angle=tau,
    #                                                                Cf=Cf,
    #                                                                Ct=Ct,
    #                                                                seq=1,
    #                                                                conn=None,
    #                                                                add_windings_phase=False)
    yff = 1.0 / (m * m * np.exp(2j * tau))
    yft = -1.0 / m
    ytf = -1.0 / (m * np.exp(2j * tau))
    ytt = np.zeros(len(m))
    Yf_ctrl = diags(yff) * Cf + diags(yft) * Ct
    Yt_ctrl = diags(ytf) * Cf + diags(ytt) * Ct
    Ybus_ctrl = Cf.T * Yf_ctrl + Ct.T * Yt_ctrl

    Yf_bus = Cf.T @ yff + Ct.T @ yft
    Yt_bus = Cf.T @ ytf  # ytt is zero
    Y0c = Cf.T @ (yff - ytf) + Ct.T @ yft

    # Formulation 1
    # Sbus = cf.compute_zip_power(S0, I0, Y0, Vm)
    # Scalc = V * np.conj(Ybus @ V - Yf_bus * V + Yt_bus * V)

    # Formulation 2
    Sbus = cf.compute_zip_power(S0=S0,
                                I0=I0,
                                Y0=Y0 + Yf_bus - Yt_bus,
                                Vm=Vm)
    # Scalc = V * np.conj(Ybus @ V)
    Scalc = V * np.conj(Cf.T @ Yf_ctrl @ V + Ct.T @ Yt_ctrl @ V)

    # Formulation 2.5
    # Sbus = cf.compute_zip_power(S0=S0,
    #                             I0=I0,
    #                             Y0=Y0 + Y0c,
    #                             Vm=Vm)  # + (Yf_bus - Yt_bus) * Vm * Vm
    # Scalc = V * np.conj(Ybus @ V)

    # Formulation 3
    # Vm2 = Vm * Vm
    # Sf_inj = np.zeros(len(V), dtype=complex)
    # St_inj = np.zeros(len(V), dtype=complex)
    # Sf_inj += Cf.T @ (np.conj((yff - yft) * V[F]) * V[F])
    # St_inj += Ct.T @ (np.conj(ytf * V[T]) * V[T])
    # Sbus = cf.compute_zip_power(S0, I0, Y0, Vm) - Sf_inj + St_inj
    # Scalc = (V * np.conj(Ybus @ V))

    # Formulation 4
    # Sbus = cf.compute_zip_power(S0=S0,
    #                             I0=I0,
    #                             Y0=Y0,
    #                             Vm=Vm)
    # Scalc = V * np.conj((Ybus + Ybus_ctrl) @ V)

    g = cf.compute_fx(Scalc, Sbus, pvpq, pq)

    return g


def compute_gx(V: CxVec, Ybus: CscMat, pvpq: IntVec, pq: IntVec) -> CscMat:
    """
    Compute the Jacobian matrix of the power flow function
    :param V:
    :param Ybus:
    :param pvpq:
    :param pq:
    :return:
    """
    return AC_jacobian(Ybus, V, pvpq, pq)


def compute_gx_autodiff(x: Vec,
                        # these are the args:
                        Va0: Vec,
                        Vm0: Vec,
                        Ybus: CscMat,
                        S0: CxVec,
                        I0: CxVec,
                        Y0: CxVec,
                        m: Vec,
                        tau: Vec,
                        Cf,
                        Ct,
                        F: IntVec,
                        T: IntVec,
                        pq: IntVec,
                        pvpq: IntVec) -> ConvexFunctionResult:
    """

    :param x: vector of unknowns (handled by the solver)
    :param Va0:
    :param Vm0:
    :param Ybus:
    :param S0:
    :param I0:
    :param Y0:
    :param m:
    :param tau:
    :param Cf:
    :param Ct:
    :param F:
    :param T:
    :param pq:
    :param pvpq:
    :return:
    """
    npvpq = len(pvpq)
    Va = Va0.copy()
    Vm = Vm0.copy()
    Va[pvpq], Vm[pq] = x2var(x=x, npvpq=npvpq)
    V = Vm * np.exp(1j * Va)

    g = compute_g(V=V, Ybus=Ybus, S0=S0, I0=I0, Y0=Y0, Vm=Vm, m=m, tau=tau, Cf=Cf, Ct=Ct, F=F, T=T, pq=pq, pvpq=pvpq)

    return g


def pf_function(x: Vec,
                compute_jac: bool,
                # these are the args:
                Va0: Vec,
                Vm0: Vec,
                Ybus: CscMat,
                S0: CxVec,
                I0: CxVec,
                Y0: CxVec,
                m: Vec,
                tau: Vec,
                Cf,
                Ct,
                F: IntVec,
                T: IntVec,
                pq: IntVec,
                pvpq: IntVec) -> ConvexFunctionResult:
    """

    :param x: vector of unknowns (handled by the solver)
    :param compute_jac: compute the jacobian? (handled by the solver)
    :param Va0:
    :param Vm0:
    :param Ybus:
    :param S0:
    :param I0:
    :param Y0:
    :param m:
    :param tau:
    :param Cf:
    :param Ct:
    :param F:
    :param T:
    :param pq:
    :param pvpq:
    :return:
    """
    npvpq = len(pvpq)
    Va = Va0.copy()
    Vm = Vm0.copy()
    Va[pvpq], Vm[pq] = x2var(x=x, npvpq=npvpq)
    V = Vm * np.exp(1j * Va)

    g = compute_g(V=V, Ybus=Ybus, S0=S0, I0=I0, Y0=Y0, Vm=Vm, m=m, tau=tau, Cf=Cf, Ct=Ct, F=F, T=T, pq=pq, pvpq=pvpq)

    if compute_jac:
        # Gx = compute_gx(V=V, Ybus=Ybus, pvpq=pvpq, pq=pq)

        Gx = calc_autodiff_jacobian(func=compute_gx_autodiff,
                                    x=x,
                                    arg=(Va0, Vm0, Ybus, S0, I0, Y0, m, tau, Cf, Ct, F, T, pq, pvpq))

    else:
        Gx = None

    return ConvexFunctionResult(f=g, J=Gx)


def compute_passive_admittances(R: Vec,
                                X: Vec,
                                G: Vec,
                                B: Vec,
                                vtap_f: Vec,
                                vtap_t: Vec,
                                Cf: sp.csc_matrix,
                                Ct: sp.csc_matrix,
                                Yshunt_bus: CxVec,
                                conn: Union[List[WindingsConnection], ObjVec],
                                seq: int,
                                add_windings_phase: bool = False) -> AdmittanceMatrices:
    """
    Compute the complete admittance matrices only using passive elements

    :param R: array of branch resistance (p.u.)
    :param X: array of branch reactance (p.u.)
    :param G: array of branch conductance (p.u.)
    :param B: array of branch susceptance (p.u.)
    :param vtap_f: array of virtual taps at the "from" side
    :param vtap_t: array of virtual taps at the "to" side
    :param Cf: Connectivity branch-bus "from" with the branch states computed
    :param Ct: Connectivity branch-bus "to" with the branch states computed
    :param Yshunt_bus: array of shunts equivalent power per bus, from the shunt devices (p.u.)
    :param seq: Sequence [0, 1, 2]
    :param conn: array of windings connections (numpy array of WindingsConnection)
    :param add_windings_phase: Add the phases of the transformer windings (for short circuits mainly)
    :return: Admittance instance
    """

    # form the admittance matrices
    ys = 1.0 / (R + 1.0j * X + 1e-20)  # series admittance
    bc2 = (G + 1j * B) / 2.0  # shunt admittance

    # compose the primitives
    if add_windings_phase:
        r30_deg = np.exp(1.0j * np.pi / 6.0)

        if seq == 0:  # zero sequence
            # add always the shunt term, the series depends on the connection
            # one ys vector for the from side, another for the to side, and the shared one
            ysf = np.zeros(len(ys), dtype=complex)
            yst = np.zeros(len(ys), dtype=complex)
            ysft = np.zeros(len(ys), dtype=complex)

            for i, con in enumerate(conn):
                if con == WindingsConnection.GG:
                    ysf[i] = ys[i]
                    yst[i] = ys[i]
                    ysft[i] = ys[i]
                elif con == WindingsConnection.GD:
                    ysf[i] = ys[i]

            yff = (ysf + bc2) / (vtap_f * vtap_f)
            yft = -ysft / (vtap_f * vtap_t)
            ytf = -ysft / (vtap_t * vtap_f)
            ytt = (yst + bc2) / (vtap_t * vtap_t)

        elif seq == 2:  # negative sequence
            # only need to include the phase shift of +-30 degrees
            factor_psh = np.array([r30_deg if con == WindingsConnection.GD or con == WindingsConnection.SD else 1
                                   for con in conn])

            yff = (ys + bc2) / (vtap_f * vtap_f)
            yft = -ys / (vtap_f * vtap_t) * factor_psh
            ytf = -ys / (vtap_t * vtap_f) * np.conj(factor_psh)
            ytt = (ys + bc2) / (vtap_t * vtap_t)

        elif seq == 1:  # positive sequence

            # only need to include the phase shift of +-30 degrees
            factor_psh = np.array([r30_deg if con == WindingsConnection.GD or con == WindingsConnection.SD else 1.0
                                   for con in conn])

            yff = (ys + bc2) / (vtap_f * vtap_f)
            yft = -ys / (vtap_f * vtap_t) * factor_psh
            ytf = -ys / (vtap_t * vtap_f) * np.conj(factor_psh)
            ytt = (ys + bc2) / (vtap_t * vtap_t)
        else:
            raise Exception('Unsupported sequence when computing the admittance matrix sequence={}'.format(seq))

    else:  # original
        yff = (ys + bc2) / (vtap_f * vtap_f)
        yft = -ys / (vtap_f * vtap_t)
        ytf = -ys / (vtap_t * vtap_f)
        ytt = (ys + bc2) / (vtap_t * vtap_t)

    # compose the matrices
    Yf = sp.diags(yff) * Cf + sp.diags(yft) * Ct
    Yt = sp.diags(ytf) * Cf + sp.diags(ytt) * Ct
    Ybus = Cf.T * Yf + Ct.T * Yt + sp.diags(Yshunt_bus)

    return AdmittanceMatrices(Ybus, Yf, Yt, Cf, Ct, yff, yft, ytf, ytt, Yshunt_bus)

def run_pf(grid: gce.MultiCircuit, pf_options: gce.PowerFlowOptions):
    """

    :param grid:
    :param pf_options:
    :return:
    """
    nc = gce.compile_numerical_circuit_at(grid, t_idx=None)

    adm = compute_passive_admittances(R=nc.passive_branch_data.R,
                                      X=nc.passive_branch_data.X,
                                      G=nc.passive_branch_data.G,
                                      B=nc.passive_branch_data.B,
                                      vtap_f=nc.passive_branch_data.virtual_tap_f,
                                      vtap_t=nc.passive_branch_data.virtual_tap_t,
                                      Cf=nc.passive_branch_data.Cf.tocsc(),
                                      Ct=nc.passive_branch_data.Ct.tocsc(),
                                      Yshunt_bus=nc.Yshunt_from_devices,
                                      conn=nc.passive_branch_data.conn,
                                      seq=1,
                                      add_windings_phase=False)
    Ybus = adm.Ybus
    pq = nc.pq
    pvpq = np.r_[nc.pv, nc.pq]
    npvpq = len(pvpq)
    S0 = nc.Sbus
    I0 = nc.Ibus
    Y0 = nc.YLoadBus
    m = nc.passive_branch_data.tap_module
    tau = nc.passive_branch_data.tap_angle
    Cf = nc.passive_branch_data.Cf
    Ct = nc.passive_branch_data.Ct
    F = nc.F
    T = nc.T
    Vm0 = np.abs(nc.Vbus)
    Va0 = np.angle(nc.Vbus)
    x0 = var2x(Va=Va0[pvpq], Vm=Vm0[pq])

    logger = gce.Logger()

    if pf_options.solver_type == SolverType.NR:
        ret: ConvexMethodResult = newton_raphson(func=pf_function,
                                                 func_args=(Va0, Vm0, Ybus, S0, Y0, I0, m, tau, Cf, Ct, F, T, pq, pvpq),
                                                 x0=x0,
                                                 tol=pf_options.tolerance,
                                                 max_iter=pf_options.max_iter,
                                                 trust=pf_options.trust_radius,
                                                 verbose=pf_options.verbose,
                                                 logger=logger)

    elif pf_options.solver_type == SolverType.PowellDogLeg:
        ret: ConvexMethodResult = powell_dog_leg(func=pf_function,
                                                 func_args=(Va0, Vm0, Ybus, S0, Y0, I0, m, tau, Cf, Ct, F, T, pq, pvpq),
                                                 x0=x0,
                                                 tol=pf_options.tolerance,
                                                 max_iter=pf_options.max_iter,
                                                 trust_region_radius=pf_options.trust_radius,
                                                 verbose=pf_options.verbose,
                                                 logger=logger)

    elif pf_options.solver_type == SolverType.LM:
        ret: ConvexMethodResult = levenberg_marquardt(func=pf_function,
                                                      func_args=(
                                                          Va0, Vm0, Ybus, S0, Y0, I0, m, tau, Cf, Ct, F, T, pq, pvpq),
                                                      x0=x0,
                                                      tol=pf_options.tolerance,
                                                      max_iter=pf_options.max_iter,
                                                      verbose=pf_options.verbose,
                                                      logger=logger)

    else:
        raise Exception(f"Solver not implemented {pf_options.solver_type.value}")

    Va = Va0.copy()
    Vm = Vm0.copy()
    Va[pvpq], Vm[pq] = x2var(x=ret.x, npvpq=npvpq)

    df = pd.DataFrame(data={"Vm": Vm, "Va": Va})
    print(df)

    print("Info:")
    ret.print_info()

    print("Logger:")
    logger.print()
    ret.plot_error()

    plt.show()


if __name__ == '__main__':
    import os

    # grid_ = linn5bus_example()

    # fname = os.path.join('..', '..', '..', 'Grids_and_profiles', 'grids', '2869 Pegase.gridcal')
    # fname = os.path.join('..', '..', '..', 'Grids_and_profiles', 'grids', '1951 Bus RTE.xlsx')
    # fname = os.path.join('..', '..', '..', 'Grids_and_profiles', 'grids', "GB Network.gridcal")
    # fname = os.path.join('..', '..', '..', 'Grids_and_profiles', 'grids', "Iwamoto's 11 Bus.xlsx")
    fname = os.path.join('..', '..', '..', 'Grids_and_profiles', 'grids', "case14.m")
    # fname = os.path.join('..', '..', '..', 'Grids_and_profiles', 'grids', "Illinois 200 Bus.gridcal")
    grid_ = gce.open_file(fname)

    pf_options_ = gce.PowerFlowOptions(solver_type=gce.SolverType.NR,
                                       max_iter=50,
                                       trust_radius=5.0,
                                       tolerance=1e-6,
                                       verbose=0)
    run_pf(grid=grid_, pf_options=pf_options_)
