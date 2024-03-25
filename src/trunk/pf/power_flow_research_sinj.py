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
from typing import Tuple
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import GridCalEngine.api as gce

from GridCalEngine.basic_structures import Vec, CscMat, CxVec, IntVec
import GridCalEngine.Simulations.PowerFlow.NumericalMethods.common_functions as cf
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.ac_jacobian import AC_jacobian
from GridCalEngine.Utils.NumericalMethods.common import ConvexFunctionResult, ConvexMethodResult
from GridCalEngine.Utils.NumericalMethods.newton_raphson import newton_raphson
from GridCalEngine.Utils.NumericalMethods.powell import powell_dog_leg
from GridCalEngine.Utils.NumericalMethods.levenberg_marquadt import levenberg_marquardt
from GridCalEngine.Utils.NumericalMethods.autodiff import calc_autodiff_jacobian
from GridCalEngine.enumerations import SolverType
from GridCalEngine.Topology.admittance_matrices import compute_passive_admittances
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
    # Sbus = cf.compute_zip_power(S0=S0,
    #                             I0=I0,
    #                             Y0=Y0 + Yf_bus - Yt_bus,
    #                             Vm=Vm)
    # Scalc = V * np.conj(Ybus @ V)

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
    Sbus = cf.compute_zip_power(S0=S0,
                                I0=I0,
                                Y0=Y0,
                                Vm=Vm)
    Scalc = V * np.conj((Ybus + Ybus_ctrl) @ V)

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


def run_pf(grid: gce.MultiCircuit, pf_options: gce.PowerFlowOptions):
    """

    :param grid:
    :param pf_options:
    :return:
    """
    nc = gce.compile_numerical_circuit_at(grid, t_idx=None)

    adm = compute_passive_admittances(R=nc.branch_data.R,
                                      X=nc.branch_data.X,
                                      G=nc.branch_data.G,
                                      B=nc.branch_data.B,
                                      vtap_f=nc.branch_data.virtual_tap_f,
                                      vtap_t=nc.branch_data.virtual_tap_t,
                                      Cf=nc.branch_data.C_branch_bus_f.tocsc(),
                                      Ct=nc.branch_data.C_branch_bus_t.tocsc(),
                                      Yshunt_bus=nc.Yshunt_from_devices,
                                      conn=nc.branch_data.conn,
                                      seq=1,
                                      add_windings_phase=False)
    Ybus = adm.Ybus
    pq = nc.pq
    pvpq = np.r_[nc.pv, nc.pq]
    npvpq = len(pvpq)
    S0 = nc.Sbus
    I0 = nc.Ibus
    Y0 = nc.YLoadBus
    m = nc.branch_data.tap_module
    tau = nc.branch_data.tap_angle
    Cf = nc.branch_data.C_branch_bus_f
    Ct = nc.branch_data.C_branch_bus_t
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
