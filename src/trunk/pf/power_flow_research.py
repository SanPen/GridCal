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
import GridCalEngine.Simulations.PowerFlow.NumericalMethods.common_functions as cf
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.ac_jacobian import AC_jacobian
from GridCalEngine.Utils.NumericalMethods.common import ConvexFunctionResult, ConvexMethodResult
from GridCalEngine.Utils.NumericalMethods.newton_raphson import newton_raphson
from GridCalEngine.Utils.NumericalMethods.powell import powell_dog_leg
from GridCalEngine.Utils.NumericalMethods.levenberg_marquadt import levenberg_marquardt
from GridCalEngine.enumerations import SolverType


def linn5bus_example():
    """
    Grid from Lynn Powel's book
    """
    # declare a circuit object
    grid = gce.MultiCircuit()

    # Add the buses and the generators and loads attached
    bus1 = gce.Bus('Bus 1', vnom=20)
    # bus1.is_slack = True  # we may mark the bus a slack
    grid.add_bus(bus1)

    # add a generator to the bus 1
    gen1 = gce.Generator('Slack Generator', vset=1.0, Pmin=0, Pmax=1000,
                         Qmin=-1000, Qmax=1000, Cost=15, Cost2=0.0)

    grid.add_generator(bus1, gen1)

    # add bus 2 with a load attached
    bus2 = gce.Bus('Bus 2', vnom=20)
    grid.add_bus(bus2)
    grid.add_load(bus2, gce.Load('load 2', P=40, Q=20))

    # add bus 3 with a load attached
    bus3 = gce.Bus('Bus 3', vnom=20)
    grid.add_bus(bus3)
    grid.add_load(bus3, gce.Load('load 3', P=25, Q=15))

    # add bus 4 with a load attached
    bus4 = gce.Bus('Bus 4', vnom=20)
    grid.add_bus(bus4)
    grid.add_load(bus4, gce.Load('load 4', P=40, Q=20))

    # add bus 5 with a load attached
    bus5 = gce.Bus('Bus 5', vnom=20)
    grid.add_bus(bus5)
    grid.add_load(bus5, gce.Load('load 5', P=50, Q=20))

    # add Lines connecting the buses
    grid.add_line(gce.Line(bus1, bus2, 'line 1-2', r=0.05, x=0.11, b=0.02, rate=1000))
    grid.add_line(gce.Line(bus1, bus3, 'line 1-3', r=0.05, x=0.11, b=0.02, rate=1000))
    grid.add_line(gce.Line(bus1, bus5, 'line 1-5', r=0.03, x=0.08, b=0.02, rate=1000))
    grid.add_line(gce.Line(bus2, bus3, 'line 2-3', r=0.04, x=0.09, b=0.02, rate=1000))
    grid.add_line(gce.Line(bus2, bus5, 'line 2-5', r=0.04, x=0.09, b=0.02, rate=1000))
    grid.add_line(gce.Line(bus3, bus4, 'line 3-4', r=0.06, x=0.13, b=0.03, rate=1000))
    grid.add_line(gce.Line(bus4, bus5, 'line 4-5', r=0.04, x=0.09, b=0.02, rate=1000))

    return grid


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


def compute_g(V, Ybus: CscMat, S0: CxVec, I0: CxVec, Y0: CxVec, Vm, pq: IntVec, pvpq: IntVec):
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
    :return:
    """

    Sbus = cf.compute_zip_power(S0, I0, Y0, Vm)
    Scalc = cf.compute_power(Ybus, V)
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
    :param pq:
    :param pvpq:
    :return:
    """
    npvpq = len(pvpq)
    Va = Va0.copy()
    Vm = Vm0.copy()
    Va[pvpq], Vm[pq] = x2var(x=x, npvpq=npvpq)
    V = Vm * np.exp(1j * Va)

    g = compute_g(V=V, Ybus=Ybus, S0=S0, I0=I0, Y0=Y0, Vm=Vm, pq=pq, pvpq=pvpq)

    if compute_jac:
        Gx = compute_gx(V=V, Ybus=Ybus, pvpq=pvpq, pq=pq)
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
    S0 = nc.Sbus
    I0 = nc.Ibus
    Y0 = nc.YLoadBus
    Vm0 = np.abs(nc.Vbus)
    Va0 = np.angle(nc.Vbus)
    x0 = var2x(Va=Va0[pvpq], Vm=Vm0[pq])

    logger = gce.Logger()

    if pf_options.solver_type == SolverType.NR:
        ret: ConvexMethodResult = newton_raphson(func=pf_function,
                                                 func_args=(Va0, Vm0, Ybus, S0, Y0, I0, pq, pvpq),
                                                 x0=x0,
                                                 tol=pf_options.tolerance,
                                                 max_iter=pf_options.max_iter,
                                                 trust=pf_options.trust_radius,
                                                 verbose=pf_options.verbose,
                                                 logger=logger)

    elif pf_options.solver_type == SolverType.PowellDogLeg:
        ret: ConvexMethodResult = powell_dog_leg(func=pf_function,
                                                 func_args=(Va0, Vm0, Ybus, S0, Y0, I0, pq, pvpq),
                                                 x0=x0,
                                                 tol=pf_options.tolerance,
                                                 max_iter=pf_options.max_iter,
                                                 trust_region_radius=pf_options.trust_radius,
                                                 verbose=pf_options.verbose,
                                                 logger=logger)

    elif pf_options.solver_type == SolverType.LM:
        ret: ConvexMethodResult = levenberg_marquardt(func=pf_function,
                                                      func_args=(Va0, Vm0, Ybus, S0, Y0, I0, pq, pvpq),
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

    ret.print_info()

    ret.plot_error()

    plt.show()


if __name__ == '__main__':
    import os

    # grid_ = linn5bus_example()

    # fname = os.path.join('..', '..', '..', 'Grids_and_profiles', 'grids', '2869 Pegase.gridcal')
    fname = os.path.join('..', '..', '..', 'Grids_and_profiles', 'grids', '1951 Bus RTE.xlsx')
    # fname = os.path.join('..', '..', '..', 'Grids_and_profiles', 'grids', "GB Network.gridcal")
    # fname = os.path.join('..', '..', '..', 'Grids_and_profiles', 'grids', "Iwamoto's 11 Bus.xlsx")
    # fname = os.path.join('..', '..', '..', 'Grids_and_profiles', 'grids', "case14.m")
    # fname = os.path.join('..', '..', '..', 'Grids_and_profiles', 'grids', "Illinois 200 Bus.gridcal")
    grid_ = gce.open_file(fname)

    pf_options_ = gce.PowerFlowOptions(solver_type=gce.SolverType.PowellDogLeg,
                                       max_iter=50,
                                       trust_radius=1.0,
                                       tolerance=1e-6,
                                       verbose=0)
    run_pf(grid=grid_, pf_options=pf_options_)
