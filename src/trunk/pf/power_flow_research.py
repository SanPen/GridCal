import os
import numpy as np
import GridCalEngine.api as gce

from GridCalEngine.basic_structures import Vec, CscMat, CxVec, IntVec
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.ac_jacobian import AC_jacobian
from GridCalEngine.Utils.NumericalMethods.common import ConvexFunctionResult, ConvexMethodResult
from GridCalEngine.Utils.NumericalMethods.newton_raphson import newton_raphson


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


def var2x(Va: Vec, Vm: Vec):
    """

    :param Va:
    :param Vm:
    :return:
    """
    return np.r_[Va, Vm]


def x2var(x: Vec, npvpq):
    """

    :param x:
    :param nbus:
    :return:
    """
    Va = x[:npvpq]
    Vm = x[npvpq:]

    return Va, Vm


def compute_g(V, Ybus: CscMat, Sesp: CxVec, pq: IntVec, pvpq: IntVec, Sbase: float):
    """

    :param V:
    :param Ybus:
    :param Sesp:
    :param pq:
    :param pvpq:
    :param Sbase:
    :return:
    """

    S = V * np.conj(Ybus @ V)
    dS = (S - Sesp) / Sbase

    g = np.r_[dS.real[pvpq], dS.imag[pq]]
    return g


def compute_gx(V, Ybus, pvpq, pq):
    """

    :param V:
    :param Ybus:
    :param pvpq:
    :param pq:
    :return:
    """
    return AC_jacobian(Ybus, V, pvpq, pq)


def pf_function(x: Vec, compute_jac: bool,
                Vm0: Vec, Va0: Vec, Ybus: CscMat, Sesp: CxVec,
                pq: IntVec, pvpq: IntVec, Sbase: float) -> ConvexFunctionResult:
    """

    :param x:
    :param compute_jac:
    :param Vm0:
    :param Va0:
    :param Ybus:
    :param Sesp:
    :param pq:
    :param pvpq:
    :param Sbase:
    :return:
    """
    npvpq = len(pvpq)
    Va = Va0.copy()
    Vm = Vm0.copy()
    Va[pvpq], Vm[pq] = x2var(x=x, npvpq=npvpq)
    V = Vm * np.exp(1j * Va)

    g = compute_g(V=V, Ybus=Ybus, Sesp=Sesp, pq=pq, pvpq=pvpq, Sbase=Sbase)

    if compute_jac:
        Gx = compute_gx(V=V, Ybus=Ybus, pvpq=pvpq, pq=pq)
    else:
        Gx = None

    return ConvexFunctionResult(g=g, Gx=Gx)


def run_pf(grid: gce.MultiCircuit, pf_options: gce.PowerFlowOptions):
    """

    :param grid:
    :param pf_options:
    :return:
    """
    nc = gce.compile_numerical_circuit_at(grid, t_idx=None)

    nbus = nc.nbus
    Ybus = nc.Ybus
    Sesp = nc.Sbus
    pq = nc.pq
    pvpq = np.r_[nc.pv, nc.pq]
    vd = nc.vd
    npvpq = len(pvpq)
    Sbase = nc.Sbase
    Vm0 = np.abs(nc.Vbus)
    Va0 = np.angle(nc.Vbus)
    x0 = var2x(Va=Va0[pvpq], Vm=Vm0[pq])

    logger = gce.Logger()

    ret: ConvexMethodResult = newton_raphson(func=pf_function,
                                             func_args=(Va0, Vm0, Ybus, Sesp, pq, pvpq, Sbase),
                                             x0=x0,
                                             tol=pf_options.tolerance,
                                             max_iter=pf_options.max_iter,
                                             mu0=pf_options.mu,
                                             acceleration_parameter=0.05,
                                             verbose=pf_options.verbose,
                                             logger=logger)

    Va = Va0.copy()
    Vm = Vm0.copy()
    Va[pvpq], Vm[pq] = x2var(x=ret.x, npvpq=npvpq)

    print("Err", ret.error)


if __name__ == '__main__':

    grid_ = linn5bus_example()
    run_pf(grid=grid_,
           pf_options=gce.PowerFlowOptions(solver_type=gce.SolverType.NR, verbose=1))
