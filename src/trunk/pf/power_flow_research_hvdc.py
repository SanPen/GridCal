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
import GridCalEngine.api as gce

from GridCalEngine.basic_structures import Vec, CscMat, CxVec, IntVec
import GridCalEngine.Utils.NumericalMethods.autodiff as ad
import GridCalEngine.Simulations.PowerFlow.NumericalMethods.common_functions as cf
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.ac_jacobian import AC_jacobian
from GridCalEngine.Utils.NumericalMethods.common import ConvexFunctionResult, ConvexMethodResult
from GridCalEngine.Utils.NumericalMethods.newton_raphson import newton_raphson
from GridCalEngine.Utils.NumericalMethods.powell import powell_dog_leg
from GridCalEngine.Utils.NumericalMethods.levenberg_marquadt import levenberg_marquardt
from GridCalEngine.enumerations import SolverType


def var2x(Va: Vec, Vm: Vec, Pf_hvdc: Vec, Pt_hvdc: Vec) -> Vec:
    """
    Compose the unknowns vector
    :param Va: Array of voltage angles for the PV and PQ nodes
    :param Vm: Array of voltage modules for the PQ nodes
    :param Pf_hvdc: Array of "from" power at HVDC branches
    :param Pt_hvdc: Array of "to" power at HVDC branches
    :return: [Va | Vm, Pf_hvdc | Pt_hvdc]
    """
    return np.r_[Va, Vm, Pf_hvdc, Pt_hvdc]


def x2var(x: Vec, npvpq: int, npq: int, nhvdc: int) -> Tuple[Vec, Vec, Vec, Vec]:
    """
    get the physical variables from the unknowns vector
    :param x: vector of unknowns
    :param npvpq: number of non slack nodes
    :param npq: number of PQ nodes
    :param nhvdc: number of decoupled branches (i.e. simple HVDC devices)
    :return: Va, Vm, Pf_hvdc, Pt_hvdc
    """
    a = 0
    b = npvpq
    Va = x[a:b]

    a = b
    b = a + npq
    Vm = x[a:b]

    a = b
    b = a + nhvdc
    Pf_hvdc = x[a:b]

    a = b
    b = a + nhvdc
    Pt_hvdc = x[a:b]

    return Va, Vm, Pf_hvdc, Pt_hvdc


def compute_g(V: CxVec, Ybus: CscMat,
              S0: CxVec, I0: CxVec, Y0: CxVec, Vm: Vec, pq: IntVec, pvpq: IntVec,
              Pset_hvdc: Vec, Pf_hvdc: Vec, Pt_hvdc: Vec,
              Cf_hvdc: CscMat, Ct_hvdc: CscMat):
    """
    Compose the power flow function
    :param V:
    :param Ybus:
    :param S0:
    :param I0:
    :param Y0:
    :param Vm:
    :param pq:
    :param pvpq:
    :param Pset_hvdc:
    :param Pf_hvdc
    :param Pt_hvdc:
    :param Cf_hvdc:
    :param Ct_hvdc:
    :return:
    """

    Sbus = cf.compute_zip_power(S0, I0, Y0, Vm)
    Scalc = cf.compute_power(Ybus, V)
    dPf_hvdc = Pf_hvdc + Pset_hvdc
    dPt_hvdc = Pt_hvdc - Pset_hvdc
    dS = Sbus - Scalc - Cf_hvdc.T @ dPf_hvdc + Ct_hvdc.T @ dPt_hvdc
    g = np.r_[dS[pvpq].real, dS[pq].imag, dPf_hvdc, dPt_hvdc]

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
    J = AC_jacobian(Ybus, V, pvpq, pq)

    return J


def g_for_autdiff(x: Vec,
                  # these are the args:
                  Va0: Vec,
                  Vm0: Vec,
                  Ybus: CscMat,
                  S0: CxVec,
                  I0: CxVec,
                  Y0: CxVec,
                  pq: IntVec,
                  pvpq: IntVec,
                  Pset_hvdc,
                  Cf_hvdc: CscMat,
                  Ct_hvdc: CscMat) -> ConvexFunctionResult:
    """

    :param x: vector of unknowns (handled by the solver)
    :param Va0:
    :param Vm0:
    :param Ybus:
    :param S0:
    :param I0:
    :param Y0:
    :param pq:
    :param pvpq:
    :param Pset_hvdc:
    :param Cf_hvdc
    :param Ct_hvdc
    :return:
    """
    npvpq = len(pvpq)
    npq = len(pq)
    nhvdc = len(Pset_hvdc)
    Va = Va0.copy()
    Vm = Vm0.copy()
    Va[pvpq], Vm[pq], Pf_hvdc, Pt_hvdc = x2var(x=x, npvpq=npvpq, npq=npq, nhvdc=nhvdc)
    V = Vm * np.exp(1j * Va)

    g = compute_g(V=V, Ybus=Ybus, S0=S0, I0=I0, Y0=Y0, Vm=Vm, pq=pq, pvpq=pvpq,
                  Pset_hvdc=Pset_hvdc, Pf_hvdc=Pf_hvdc, Pt_hvdc=Pt_hvdc, Cf_hvdc=Cf_hvdc, Ct_hvdc=Ct_hvdc)

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
                pq: IntVec,
                pvpq: IntVec,
                Pset_hvdc,
                Cf_hvdc,
                Ct_hvdc) -> ConvexFunctionResult:
    """

    :param x: vector of unknowns (handled by the solver)
    :param compute_jac: compute the jacobian? (handled by the solver)
    :param Va0:
    :param Vm0:
    :param Ybus:
    :param S0:
    :param I0:
    :param Y0:
    :param pq:
    :param pvpq:
    :param nhvdc:
    :return:
    """
    npvpq = len(pvpq)
    npq = len(pq)
    nhvdc = len(Pset_hvdc)
    Va = Va0.copy()
    Vm = Vm0.copy()
    Va[pvpq], Vm[pq], Pf_hvdc, Pt_hvdc = x2var(x=x, npvpq=npvpq, npq=npq, nhvdc=nhvdc)
    V = Vm * np.exp(1j * Va)

    g = compute_g(V=V, Ybus=Ybus, S0=S0, I0=I0, Y0=Y0, Vm=Vm, pq=pq, pvpq=pvpq,
                  Pset_hvdc=Pset_hvdc, Pf_hvdc=Pf_hvdc, Pt_hvdc=Pt_hvdc, Cf_hvdc=Cf_hvdc, Ct_hvdc=Ct_hvdc)

    if compute_jac:
        # Gx = compute_gx(V=V, Ybus=Ybus, pvpq=pvpq, pq=pq)
        Gx = ad.calc_autodiff_jacobian(func=g_for_autdiff, x=x,
                                       arg=(Va0, Vm0, Ybus, S0, I0, Y0, pq, pvpq, Pset_hvdc, Cf_hvdc, Ct_hvdc)
                                       ).T.tocsc()
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

    Ybus = nc.Ybus
    pq = nc.pq
    pvpq = np.r_[nc.pv, nc.pq]
    npvpq = len(pvpq)
    npq = len(pq)
    nhvdc = nc.nhvdc
    S0 = (nc.generator_data.get_injections_per_bus() - nc.load_data.get_injections_per_bus()) / nc.Sbase
    I0 = nc.Ibus
    Y0 = nc.YLoadBus
    Vm0 = np.abs(nc.Vbus)
    Va0 = np.angle(nc.Vbus)
    Pset_hvdc = nc.hvdc_data.Pset / nc.Sbase
    Pf_hvdc0 = -Pset_hvdc * 0
    Pt_hvdc0 = Pset_hvdc * 0
    Cf_hvdc = nc.hvdc_data.C_hvdc_bus_f
    Ct_hvdc = nc.hvdc_data.C_hvdc_bus_t

    x0 = var2x(Va=Va0[pvpq], Vm=Vm0[pq], Pf_hvdc=Pf_hvdc0, Pt_hvdc=Pt_hvdc0)

    logger = gce.Logger()

    if pf_options.solver_type == SolverType.NR:
        ret: ConvexMethodResult = newton_raphson(func=pf_function,
                                                 func_args=(Va0, Vm0, Ybus, S0, Y0, I0, pq, pvpq,
                                                            Pset_hvdc, Cf_hvdc, Ct_hvdc),
                                                 x0=x0,
                                                 tol=pf_options.tolerance,
                                                 max_iter=pf_options.max_iter,
                                                 trust=pf_options.trust_radius,
                                                 verbose=pf_options.verbose,
                                                 logger=logger)

    elif pf_options.solver_type == SolverType.PowellDogLeg:
        ret: ConvexMethodResult = powell_dog_leg(func=pf_function,
                                                 func_args=(Va0, Vm0, Ybus, S0, Y0, I0, pq, pvpq,
                                                            Pset_hvdc, Cf_hvdc, Ct_hvdc),
                                                 x0=x0,
                                                 tol=pf_options.tolerance,
                                                 max_iter=pf_options.max_iter,
                                                 trust_region_radius=pf_options.trust_radius,
                                                 verbose=pf_options.verbose,
                                                 logger=logger)

    elif pf_options.solver_type == SolverType.LM:
        ret: ConvexMethodResult = levenberg_marquardt(func=pf_function,
                                                      func_args=(Va0, Vm0, Ybus, S0, Y0, I0, pq, pvpq,
                                                                 Pset_hvdc, Cf_hvdc, Ct_hvdc),
                                                      x0=x0,
                                                      tol=pf_options.tolerance,
                                                      max_iter=pf_options.max_iter,
                                                      verbose=pf_options.verbose,
                                                      logger=logger)

    else:
        raise Exception(f"Solver not implemented {pf_options.solver_type.value}")

    Va = Va0.copy()
    Vm = Vm0.copy()
    Va[pvpq], Vm[pq], Pf_hvdc, Pt_hvdc = x2var(x=ret.x, npvpq=npvpq, npq=npq, nhvdc=nhvdc)

    print("Info:")
    ret.print_info()

    print("Logger:")
    logger.print()
    ret.plot_error()

    plt.show()


if __name__ == '__main__':
    import os

    fname = os.path.join('..', '..', '..', 'Grids_and_profiles', 'grids', '8_nodes_2_islands_hvdc.gridcal')
    # fname = os.path.join('..', '..', '..', 'Grids_and_profiles', 'grids', '1951 Bus RTE.xlsx')
    # fname = os.path.join('..', '..', '..', 'Grids_and_profiles', 'grids', "GB Network.gridcal")
    # fname = os.path.join('..', '..', '..', 'Grids_and_profiles', 'grids', "Iwamoto's 11 Bus.xlsx")
    # fname = os.path.join('..', '..', '..', 'Grids_and_profiles', 'grids', "case14.m")
    # fname = os.path.join('..', '..', '..', 'Grids_and_profiles', 'grids', "Illinois 200 Bus.gridcal")
    grid_ = gce.open_file(fname)

    pf_options_ = gce.PowerFlowOptions(solver_type=gce.SolverType.NR,
                                       max_iter=20,
                                       trust_radius=1.0,
                                       tolerance=1e-6,
                                       verbose=1)
    run_pf(grid=grid_, pf_options=pf_options_)
