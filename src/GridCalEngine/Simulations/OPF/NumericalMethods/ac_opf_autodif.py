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
from scipy.sparse import csc_matrix as csc
from scipy.sparse import lil_matrix
import GridCalEngine.api as gce
from GridCalEngine.basic_structures import Vec
import GridCalEngine.Utils.NumericalMethods.autodiff as ad
from GridCalEngine.Utils.NumericalMethods.ips import interior_point_solver, IpsFunctionReturn
from GridCalEngine.Simulations.PowerFlow.power_flow_worker import multi_island_pf_nc
from GridCalEngine.DataStructures.numerical_circuit import NumericalCircuit
from typing import Callable, Tuple


def x2var(x, n_vm, n_va, n_P, n_Q):
    a = 0
    b = n_vm

    vm = x[a: b]
    a = b
    b += n_va

    th = x[a: b]
    a = b
    b += n_P

    Pg = x[a: b]
    a = b
    b += n_Q

    Qg = x[a: b]

    return vm, th, Pg, Qg


def var2x(vm, va, Pg, Qg):
    return np.r_[vm, va, Pg, Qg]


def eval_f(x, Yf, Cg, c0, c1, c2, Sbase, no_slack) -> Vec:
    """

    :param x:
    :param Yf:
    :param Cg:
    :param c1:
    :param c2:
    :param no_slack:
    :return:
    """
    M, N = Yf.shape
    Ng = Cg.shape[1]  # Check

    _, _, Pg, Qg = x2var(x, n_vm=N, n_va=N, n_P=Ng, n_Q=Ng)

    # fval = np.sum((c2 * np.power(Pg * Sbase, 2) + c1 * Pg * Sbase + c0))
    # fval = np.sum((c2 * np.power(Pg, 2) + c1 * Pg + c0))
    fval = np.sum((c0 + c1 * Pg * Sbase + c2 * np.power(Pg * Sbase, 2))) * 1e-4

    return fval


def eval_g(x, Ybus, Yf, Cg, Sd, slack, no_slack) -> Vec:
    """

    :param x:
    :param Ybus:
    :param Yf:
    :param Cg:
    :param Sd:
    :param slack:
    :param no_slack:
    :return:
    """
    M, N = Yf.shape
    Ng = Cg.shape[1]  # Check

    va = np.zeros(N)
    vm, va, Pg, Qg = x2var(x, n_vm=N, n_va=N, n_P=Ng, n_Q=Ng)

    V = vm * np.exp(1j * va)
    S = V * np.conj(Ybus @ V)

    Sg = Pg + 1j * Qg
    dS = S + Sd - (Cg @ Sg)

    gval = np.r_[dS.real, dS.imag, va[slack]]

    return gval


def eval_h(x, Yf, Yt, from_idx, to_idx, slack, no_slack, th_max, th_min, V_U, V_L, P_U, P_L, Q_U, Q_L, Cg,
           rates) -> Vec:
    """

    :param x:
    :param Yf:
    :param Yt:
    :param from_idx:
    :param to_idx:
    :param slack:
    :param no_slack:
    :param th_max:
    :param th_min:
    :param V_U:
    :param V_L:
    :param P_U:
    :param P_L:
    :param Q_U:
    :param Q_L:
    :param Cg:
    :param rates:
    :return:
    """
    M, N = Yf.shape
    Ng = Cg.shape[1]  # Check

    vm, va, Pg, Qg = x2var(x, n_vm=N, n_va=N, n_P=Ng, n_Q=Ng)

    V = vm * np.exp(1j * va)
    If = np.conj(Yf @ V)
    Lf = If * If
    Sf = V[from_idx] * If
    St = V[to_idx] * np.conj(Yt @ V)

    hval = np.r_[abs(Sf) - rates,  # rates "lower limit"
                 abs(St) - rates,  # rates "upper limit"
                 vm - V_U,  # voltage module upper limit
                 V_L - vm,  # voltage module lower limit
                 va[no_slack] - th_max[no_slack],  # voltage angles upper limit
                 th_min[no_slack] - va[no_slack],  # voltage angles lower limit
                 Pg - P_U,  # generator P upper limits
                 P_L - Pg,  # generator P lower limits
                 Qg - Q_U,  # generator Q upper limits
                 Q_L - Qg  # generation Q lower limits
    ]

    return hval


def evaluate_power_flow(x, mu, lmbda, Ybus, Yf, Cg, Sd, slack, no_slack, Yt, from_idx, to_idx,
                        th_max, th_min, V_U, V_L, P_U, P_L, Q_U, Q_L,
                        c0, c1, c2, Sbase, rates, h=1e-5) -> IpsFunctionReturn:
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
    :param h:
    :return:
    """
    f = eval_f(x=x, Yf=Yf, Cg=Cg, c0=c0, c1=c1, c2=c2, Sbase=Sbase, no_slack=no_slack)
    G = eval_g(x=x, Ybus=Ybus, Yf=Yf, Cg=Cg, Sd=Sd, slack=slack, no_slack=no_slack)
    H = eval_h(x=x, Yf=Yf, Yt=Yt, from_idx=from_idx, to_idx=to_idx, slack=slack, no_slack=no_slack, th_max=th_max,
               th_min=th_min, V_U=V_U, V_L=V_L, P_U=P_U, P_L=P_L, Q_U=Q_U, Q_L=Q_L, Cg=Cg, rates=rates)

    fx = ad.calc_autodiff_jacobian_f_obj(func=eval_f, x=x, arg=(Yf, Cg, c0, c1, c2, Sbase, no_slack), h=h)
    Gx = ad.calc_autodiff_jacobian(func=eval_g, x=x, arg=(Ybus, Yf, Cg, Sd, slack, no_slack)).T
    Hx = ad.calc_autodiff_jacobian(func=eval_h, x=x, arg=(Yf, Yt, from_idx, to_idx, slack, no_slack, th_max, th_min,
                                                          V_U, V_L, P_U, P_L, Q_U, Q_L, Cg, rates)).T

    fxx = ad.calc_autodiff_hessian_f_obj(func=eval_f, x=x, arg=(Yf, Cg, c0, c1, c2, Sbase, no_slack), h=h)
    Gxx = ad.calc_autodiff_hessian(func=eval_g, x=x, mult=lmbda, arg=(Ybus, Yf, Cg, Sd, slack, no_slack))
    Hxx = ad.calc_autodiff_hessian(func=eval_h, x=x, mult=mu, arg=(Yf, Yt, from_idx, to_idx, slack, no_slack, th_max,
                                                                   th_min, V_U, V_L, P_U, P_L, Q_U, Q_L, Cg, rates))

    return IpsFunctionReturn(f=f, G=G, H=H,
                             fx=fx, Gx=Gx.tocsc(), Hx=Hx.tocsc(),
                             fxx=fxx.tocsc(), Gxx=Gxx.tocsc(), Hxx=Hxx.tocsc())


def ac_optimal_power_flow(nc: NumericalCircuit, pf_options: gce.PowerFlowOptions, verbose=2):
    """

    :param nc:
    :param pf_options:
    :return:
    """

    # compile the grid snapshot
    Sbase = nc.Sbase
    c0 = nc.generator_data.cost_0
    c1 = nc.generator_data.cost_1
    c2 = nc.generator_data.cost_2

    Ybus = nc.Ybus
    Yf = nc.Yf
    Yt = nc.Yt
    Cg = nc.generator_data.C_bus_elm

    # Bus identification lists
    slack = nc.vd
    no_slack = nc.pqpv
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
    rates = nc.rates / Sbase
    Va_max = nc.bus_data.angle_max
    Va_min = nc.bus_data.angle_min

    nbr = nc.branch_data.nelm
    nbus = nc.bus_data.nbus
    ngen = nc.generator_data.nelm
    n_no_slack = len(no_slack)
    n_slack = len(slack)

    # Nodal power balances, the voltage module of slack and pv buses and the slack reference
    NE = 2 * nbus + n_slack

    # Line ratings, max and min angle of buses, voltage module range and
    NI = 2 * nbr + 2 * n_no_slack + 2 * nbus + 4 * ngen

    # active and reactive power generation range.

    ########

    # run power flow to initialize
    pf_results = multi_island_pf_nc(nc=nc, options=pf_options)

    # ignore power from Z and I of the load
    s0gen = (pf_results.Sbus - nc.load_data.get_injections_per_bus()) / nc.Sbase
    p0gen = nc.generator_data.C_bus_elm.T @ np.real(s0gen)
    q0gen = nc.generator_data.C_bus_elm.T @ np.imag(s0gen)

    # compose the initial values
    x0 = var2x(vm=np.abs(pf_results.voltage),
               va=np.angle(pf_results.voltage),
               Pg=p0gen,
               Qg=q0gen)

    NV = len(x0)

    if verbose > 0:
        print("x0:", x0)
    result = interior_point_solver(x0=x0, n_x=NV, n_eq=NE, n_ineq=NI,
                                   func=evaluate_power_flow,
                                   arg=(Ybus, Yf, Cg, Sd, slack, no_slack, Yt, from_idx, to_idx, Va_max,
                                        Va_min, Vm_max, Vm_min, Pg_max, Pg_min, Qg_max, Qg_min, c0, c1,
                                        c2, Sbase,
                                        rates),
                                   verbose=verbose)

    vm, va, Pg, Qg = x2var(result.x, n_vm=nbus, n_va=nbus, n_P=ngen, n_Q=ngen)

    lam_p, lam_q = result.lam[:nbus], result.lam[nbus:2 * nbus]

    df_bus = pd.DataFrame(data={'Vm (p.u.)': vm, 'Va (rad)': va,
                                'dual price (€/MW)': lam_p, 'dual price (€/MVAr)': lam_q})
    df_gen = pd.DataFrame(data={'P (MW)': Pg * nc.Sbase, 'Q (MVAr)': Qg * nc.Sbase})

    if verbose > 0:
        print()
        print("Bus:\n", df_bus)
        print("Gen:\n", df_gen)
        print("Error", result.error)

    return result.x


def example_3bus_acopf():
    """

    :return:
    """

    grid = gce.MultiCircuit()

    b1 = gce.Bus(is_slack=True)
    b2 = gce.Bus()
    b3 = gce.Bus()

    grid.add_bus(b1)
    grid.add_bus(b2)
    grid.add_bus(b3)

    grid.add_line(gce.Line(bus_from=b1, bus_to=b2, name='line 1-2', r=0.001, x=0.05, rate=100))
    grid.add_line(gce.Line(bus_from=b2, bus_to=b3, name='line 2-3', r=0.001, x=0.05, rate=100))
    grid.add_line(gce.Line(bus_from=b3, bus_to=b1, name='line 3-1_1', r=0.001, x=0.05, rate=100))
    # grid.add_line(gce.Line(bus_from=b3, bus_to=b1, name='line 3-1_2', r=0.001, x=0.05, rate=100))

    grid.add_load(b3, gce.Load(name='L3', P=50, Q=20))
    grid.add_generator(b1, gce.Generator('G1', vset=1.00, Cost=1.0, Cost2=2.0))
    grid.add_generator(b2, gce.Generator('G2', P=10, vset=0.995, Cost=1.0, Cost2=3.0))

    options = gce.PowerFlowOptions(gce.SolverType.NR, verbose=False)
    power_flow = gce.PowerFlowDriver(grid, options)
    power_flow.run()

    # print('\n\n', grid.name)
    # print('\tConv:\n', power_flow.results.get_bus_df())
    # print('\tConv:\n', power_flow.results.get_branch_df())

    nc = gce.compile_numerical_circuit_at(grid)
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR)
    ac_optimal_power_flow(nc=nc, pf_options=pf_options)
    return


def linn5bus_example():
    """
    Grid from Lynn Powel's book
    """
    # declare a circuit object
    grid = gce.MultiCircuit()

    # Add the buses and the generators and loads attached
    bus1 = gce.Bus('Bus 1', Vnom=20)
    # bus1.is_slack = True  # we may mark the bus a slack
    grid.add_bus(bus1)

    # add a generator to the bus 1
    gen1 = gce.Generator('Slack Generator', vset=1.0, Pmin=0, Pmax=1000,
                         Qmin=-1000, Qmax=1000, Cost=15, Cost2=0)

    grid.add_generator(bus1, gen1)

    # add bus 2 with a load attached
    bus2 = gce.Bus('Bus 2', Vnom=20)
    grid.add_bus(bus2)
    grid.add_load(bus2, gce.Load('load 2', P=40, Q=20))

    # add bus 3 with a load attached
    bus3 = gce.Bus('Bus 3', Vnom=20)
    grid.add_bus(bus3)
    grid.add_load(bus3, gce.Load('load 3', P=25, Q=15))

    # add bus 4 with a load attached
    bus4 = gce.Bus('Bus 4', Vnom=20)
    grid.add_bus(bus4)
    grid.add_load(bus4, gce.Load('load 4', P=40, Q=20))

    # add bus 5 with a load attached
    bus5 = gce.Bus('Bus 5', Vnom=20)
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

    nc = gce.compile_numerical_circuit_at(grid)
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR)
    ac_optimal_power_flow(nc=nc, pf_options=pf_options)


def two_grids_of_3bus():
    """
    3 bus grid two times
    for solving islands at the same time
    """
    grid = gce.MultiCircuit()

    # 3 bus grid
    b1 = gce.Bus(is_slack=True)
    b2 = gce.Bus()
    b3 = gce.Bus()

    grid.add_bus(b1)
    grid.add_bus(b2)
    grid.add_bus(b3)

    grid.add_line(gce.Line(bus_from=b1, bus_to=b2, name='line 1-2', r=0.001, x=0.05, rate=100))
    grid.add_line(gce.Line(bus_from=b2, bus_to=b3, name='line 2-3', r=0.001, x=0.05, rate=100))
    grid.add_line(gce.Line(bus_from=b3, bus_to=b1, name='line 3-1_1', r=0.001, x=0.05, rate=100))
    # grid.add_line(gce.Line(bus_from=b3, bus_to=b1, name='line 3-1_2', r=0.001, x=0.05, rate=100))

    grid.add_load(b3, gce.Load(name='L3', P=50, Q=20))
    grid.add_generator(b1, gce.Generator('G1', vset=1.00, Cost=1.0, Cost2=2.0))
    grid.add_generator(b2, gce.Generator('G2', P=10, vset=0.995, Cost=1.0, Cost2=3.0))

    # 3 bus grid
    b11 = gce.Bus(is_slack=True)
    b21 = gce.Bus()
    b31 = gce.Bus()

    grid.add_bus(b11)
    grid.add_bus(b21)
    grid.add_bus(b31)

    grid.add_line(gce.Line(bus_from=b11, bus_to=b21, name='line 1-2 (2)', r=0.001, x=0.05, rate=100))
    grid.add_line(gce.Line(bus_from=b21, bus_to=b31, name='line 2-3 (2)', r=0.001, x=0.05, rate=100))
    grid.add_line(gce.Line(bus_from=b31, bus_to=b11, name='line 3-1 (2)', r=0.001, x=0.05, rate=100))

    grid.add_load(b31, gce.Load(name='L3 (2)', P=50, Q=20))
    grid.add_generator(b11, gce.Generator('G1 (2)', vset=1.00, Cost=1.0, Cost2=2.0))
    grid.add_generator(b21, gce.Generator('G2 (2)', P=10, vset=0.995, Cost=1.0, Cost2=3.0))

    options = gce.PowerFlowOptions(gce.SolverType.NR, verbose=False)
    power_flow = gce.PowerFlowDriver(grid, options)
    power_flow.run()

    # print('\n\n', grid.name)
    # print('\tConv:\n', power_flow.results.get_bus_df())
    # print('\tConv:\n', power_flow.results.get_branch_df())

    nc = gce.compile_numerical_circuit_at(grid)
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR)
    ac_optimal_power_flow(nc=nc, pf_options=pf_options)
    return


def case9():
    import os
    cwd = os.getcwd()
    print(cwd)

    # Go back two directories
    new_directory = os.path.abspath(os.path.join(cwd, '..', '..', '..'))
    file_path = os.path.join(new_directory, 'Grids_and_profiles', 'grids', 'case9.m')

    grid = gce.FileOpen(file_path).open()
    nc = gce.compile_numerical_circuit_at(grid)
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR)
    ac_optimal_power_flow(nc=nc, pf_options=pf_options)
    return


def case14():
    import os
    cwd = os.getcwd()
    print(cwd)

    # Go back two directories
    new_directory = os.path.abspath(os.path.join(cwd, '..', '..', '..'))
    file_path = os.path.join(new_directory, 'Grids_and_profiles', 'grids', 'case14.m')

    grid = gce.FileOpen(file_path).open()
    nc = gce.compile_numerical_circuit_at(grid)
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR)
    ac_optimal_power_flow(nc=nc, pf_options=pf_options)
    return


if __name__ == '__main__':
    # example_3bus_acopf()
    linn5bus_example()
    # two_grids_of_3bus()
    # case9()
    # case14()
