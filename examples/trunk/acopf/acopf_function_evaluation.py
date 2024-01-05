
import numpy as np
from scipy.sparse import csc_matrix as csc
from scipy.sparse import lil_matrix
import GridCalEngine.api as gce
from GridCalEngine.basic_structures import Vec
from GridCalEngine.Utils.MIPS.mips import solver
from GridCalEngine.Simulations.PowerFlow.power_flow_worker import multi_island_pf_nc
from typing import Callable, Tuple


def build_grid_3bus():
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

    print('\n\n', grid.name)
    print('\tConv:\n', power_flow.results.get_bus_df())
    print('\tConv:\n', power_flow.results.get_branch_df())

    nc = gce.compile_numerical_circuit_at(grid)

    return grid


def x2var(x, n_v, n_th, n_P, n_Q):
    a = 0
    b = n_v

    vm = x[a: b]
    a = b
    b += n_th

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


def eval_f(x, Yf, Cg, c1, c2) -> Vec:
    """

    :param x:
    :param Yf:
    :param Cg:
    :param c1:
    :param c2:
    :return:
    """
    M, N = Yf.shape
    Ng = Cg.shape[1]  # Check

    vm, va, Pg, Qg = x2var(x, n_v=N - 1, n_th=N - 1, n_P=Ng, n_Q=Ng)

    fval = np.sum((c2 * Pg ** 2 + c1 * Pg))

    return fval


def eval_g(x, Ybus, Yf, Cg, Sd, slack, pqpv) -> Vec:
    """

    :param x:
    :param Ybus:
    :param Yf:
    :param Cg:
    :param Sd:
    :param slack:
    :param pqpv:
    :return:
    """
    M, N = Yf.shape
    Ng = Cg.shape[1]  # Check

    vm = np.zeros(N)
    va = np.zeros(N)
    vm[pqpv], va[pqpv], Pg, Qg = x2var(x, n_v=N - 1, n_th=N - 1, n_P=Ng, n_Q=Ng)
    vm[slack] = 1.0
    va[slack] = 0.0

    V = vm * np.exp(1j * va)
    S = V * np.conj(Ybus @ V)

    Sg = Pg + 1j * Qg
    dS = S + Sd - (Cg @ Sg)

    gval = np.r_[dS.real, dS.imag]

    return gval


def eval_h(x, Yf, Yt, from_idx, to_idx, slack, pqpv, th_max, th_min, V_U, V_L, P_U, P_L, Q_U, Q_L, Cg, rates) -> Vec:
    """

    :param x:
    :param Yf:
    :param Yt:
    :param from_idx:
    :param to_idx:
    :param slack:
    :param pqpv:
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

    vm = np.zeros(N)
    va = np.zeros(N)
    vm[pqpv], va[pqpv], Pg, Qg = x2var(x, n_v=N - 1, n_th=N - 1, n_P=Ng, n_Q=Ng)
    vm[slack] = 1.0
    va[slack] = 0.0

    V = vm * np.exp(1j * va)
    If = np.conj(Yf @ V)
    Lf = If * If
    Sf = V[from_idx] * If
    St = V[to_idx] * np.conj(Yt @ V)

    hval = np.r_[abs(Sf) - rates,  # rates "lower limit"
                 abs(St) - rates,  # rates "upper limit"
                 vm[pqpv] - V_U[pqpv],  # voltage module upper limit
                 V_L[pqpv] - vm[pqpv],  # voltage module lower limit
                 va[pqpv] - th_max[pqpv],  # voltage angles upper limit
                 th_min[pqpv] - va[pqpv],  # voltage angles lower limit
                 Pg - P_U,  # generatior P upper limits
                 P_L - Pg,  # generation P lower limits
                 Qg - Q_U,  # generatior Q upper limits
                 Q_L - Qg  # generation Q lower limits
    ]

    return hval


def calc_jacobian_f_obj(func, x: Vec, arg=(), h=1e-5) -> Vec:
    """
    Compute the Jacobian matrix of `func` at `x` using finite differences.
    This considers that the output is a single value, such as is the case of the objective function f
    :param func: Linear map (R^n -> R^m). m is 1 for the objective function, NE (Number of Equalities) for
    G or NI (Number of inequalities) for H.
    :param x: Point at which to evaluate the Jacobian (numpy array).
    :param arg: Tuple of arguments to call func aside from x [func(x, *arg)]
    :param h: Small step for finite difference.
    :return: Jacobian as a vector, because the objective function is a single value.
    """
    nx = len(x)
    f0 = func(x, *arg)

    jac = np.zeros(nx)

    for j in range(nx):
        x_plus_h = np.copy(x)
        x_plus_h[j] += h
        f_plus_h = func(x_plus_h, *arg)
        jac[j] = (f_plus_h - f0) / h

    return jac


def calc_jacobian(func, x: Vec, arg=(), h=1e-5) -> csc:
    """
    Compute the Jacobian matrix of `func` at `x` using finite differences.

    :param func: Linear map (R^n -> R^m). m is 1 for the objective function, NE (Number of Equalities) for
    G or NI (Number of inequalities) for H.
    :param x: Point at which to evaluate the Jacobian (numpy array).
    :param arg: Tuple of arguments to call func aside from x [func(x, *arg)]
    :param h: Small step for finite difference.
    :return: Jacobian matrix as a CSC matrix.
    """
    nx = len(x)
    f0 = func(x, *arg)
    n_rows = len(f0)

    jac = lil_matrix((n_rows, nx))

    for j in range(nx):
        x_plus_h = np.copy(x)
        x_plus_h[j] += h
        f_plus_h = func(x_plus_h, *arg)
        row = (f_plus_h - f0) / h
        for i in range(n_rows):
            if row[i] != 0.0:
                jac[i, j] = row[i]

    return jac.tocsc()


def calc_hessian_f_obj(func, x: Vec, arg=(), h=1e-5) -> csc:
    """
    Compute the Hessian matrix of `func` at `x` using finite differences.
    This considers that the output is a single value, such as is the case of the objective function f

    :param func: Linear map (R^n -> R^m). m is 1 for the objective function, NE (Number of Equalities) for
    G or NI (Number of inequalities) for H.
    :param x: Point at which to evaluate the Hessian (numpy array).
    :param arg: Tuple of arguments to call func aside from x [func(x, *arg)]
    :param h: Small step for finite difference.
    :return: Hessian matrix as a CSC matrix.
    """
    n = len(x)
    hessian = lil_matrix((n, n))
    for i in range(n):
        for j in range(n):
            x_ijp = np.copy(x)
            x_ijp[i] += h
            x_ijp[j] += h
            f_ijp = func(x_ijp, *arg)

            x_ijm = np.copy(x)
            x_ijm[i] += h
            x_ijm[j] -= h
            f_ijm = func(x_ijm, *arg)

            x_jim = np.copy(x)
            x_jim[i] -= h
            x_jim[j] += h
            f_jim = func(x_jim, *arg)

            x_jjm = np.copy(x)
            x_jjm[i] -= h
            x_jjm[j] -= h
            f_jjm = func(x_jjm, *arg)

            a = (f_ijp - f_ijm - f_jim + f_jjm) / (4 * h ** 2)

            if a != 0.0:
                hessian[i, j] = a

    return hessian.tocsc()


def calc_hessian(func, x: Vec, mult: Vec, arg=(), h=1e-5) -> csc:
    """
    Compute the Hessian matrix of `func` at `x` using finite differences.

    :param func: Linear map (R^n -> R^m). m is 1 for the objective function, NE (Number of Equalities) for
    G or NI (Number of inequalities) for H.
    :param x: Point at which to evaluate the Hessian (numpy array).
    :param mult: Array of multipliers associated with the functions. The objective function passes value 1 (no action)
    :param arg: Tuple of arguments to call func aside from x [func(x, *arg)]
    :param h: Small step for finite difference.
    :return: Hessian matrix as a CSC matrix.
    """
    n = len(x)
    const = len(func(x, *arg))  # For objective function, it will be passed as 1. The MULT will be 1 aswell.
    hessians = lil_matrix((n, n))

    for eq in range(const):
        hessian = lil_matrix((n, n))
        for i in range(n):
            for j in range(n):
                x_ijp = np.copy(x)
                x_ijp[i] += h
                x_ijp[j] += h
                f_ijp = func(x_ijp, *arg)[eq]

                x_ijm = np.copy(x)
                x_ijm[i] += h
                x_ijm[j] -= h
                f_ijm = func(x_ijm, *arg)[eq]

                x_jim = np.copy(x)
                x_jim[i] -= h
                x_jim[j] += h
                f_jim = func(x_jim, *arg)[eq]

                x_jjm = np.copy(x)
                x_jjm[i] -= h
                x_jjm[j] -= h
                f_jjm = func(x_jjm, *arg)[eq]

                a = mult[eq] * (f_ijp - f_ijm - f_jim + f_jjm) / (4 * h ** 2)

                if a != 0.0:
                    hessian[i, j] = a

        hessians += hessian

    return hessians.tocsc()


def evaluate_power_flow(x, LAMBDA, PI, Ybus, Yf, Cg, Sd, slack, pqpv, Yt, from_idx, to_idx,
                        th_max, th_min, V_U, V_L, P_U, P_L, Q_U, Q_L, c1, c2, rates, h=1e-5) -> (
        Tuple)[Vec, Vec, Vec, Vec, csc, csc, csc, csc, csc]:
    """

    :param x:
    :param LAMBDA:
    :param PI:
    :param Ybus:
    :param Yf:
    :param Cg:
    :param Sd:
    :param slack:
    :param pqpv:
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
    :param c1:
    :param c2:
    :param rates:
    :param h:
    :return:
    """
    f = eval_f(x=x, Yf=Yf, Cg=Cg, c1=c1, c2=c2)
    G = eval_g(x=x, Ybus=Ybus, Yf=Yf, Cg=Cg, Sd=Sd, slack=slack, pqpv=pqpv)
    H = eval_h(x=x, Yf=Yf, Yt=Yt, from_idx=from_idx, to_idx=to_idx, slack=slack, pqpv=pqpv, th_max=th_max,
               th_min=th_min, V_U=V_U, V_L=V_L, P_U=P_U, P_L=P_L, Q_U=Q_U, Q_L=Q_L, Cg=Cg, rates=rates)

    fx = calc_jacobian_f_obj(func=eval_f, x=x, arg=(Yf, Cg, c1, c2), h=h)  # this is a vector because f_obj is a value
    Gx = calc_jacobian(func=eval_g, x=x, arg=(Ybus, Yf, Cg, Sd, slack, pqpv)).T
    Hx = calc_jacobian(func=eval_h, x=x, arg=(Yf, Yt, from_idx, to_idx, slack, pqpv, th_max, th_min,
                                              V_U, V_L, P_U, P_L, Q_U, Q_L, Cg, rates)).T

    fxx = calc_hessian_f_obj(func=eval_f, x=x, arg=(Yf, Cg, c1, c2), h=h)
    Gxx = calc_hessian(func=eval_g, x=x, mult=PI, arg=(Ybus, Yf, Cg, Sd, slack, pqpv))
    Hxx = calc_hessian(func=eval_h, x=x, mult=LAMBDA, arg=(Yf, Yt, from_idx, to_idx, slack, pqpv, th_max,
                                                           th_min, V_U, V_L, P_U, P_L, Q_U, Q_L, Cg, rates))

    return f, G, H, fx, Gx, Hx, fxx, Gxx, Hxx


def power_flow_evaluation(nc: gce.NumericalCircuit, pf_options:gce.PowerFlowOptions):
    """

    :param nc:
    :param pf_options:
    :return:
    """

    # compile the grid snapshot
    c1 = nc.generator_data.cost_1
    c2 = nc.generator_data.cost_2

    Ybus = nc.Ybus
    Yf = nc.Yf
    Yt = nc.Yt
    Cg = nc.generator_data.C_bus_elm

    # Bus identification lists
    slack = nc.vd
    pqpv = nc.pqpv
    from_idx = nc.F
    to_idx = nc.T

    # Bus and line parameters
    Sbase = nc.Sbase
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
    nbus = nc.branch_data.nelm
    ngen = nc.generator_data.nelm
    npqpv = len(pqpv)

    # Nodal power balances, the voltage module of slack and pv buses and the slack reference
    NE = 2 * nbus

    # Line ratings, max and min angle of buses, voltage module range and
    NI = 2 * nbr + 4 * npqpv + 4 * ngen

    # active and reactive power generation range.

    ########

    # run power flow to initialize
    pf_results = multi_island_pf_nc(nc=nc, options=pf_options)

    # ignore power from Z and I of the load
    s0gen = (pf_results.Sbus - nc.load_data.get_injections_per_bus()) / nc.Sbase
    p0gen = nc.generator_data.C_bus_elm.T @ np.real(s0gen)
    q0gen = nc.generator_data.C_bus_elm.T @ np.imag(s0gen)

    # compose the initial values
    x0 = var2x(vm=np.abs(pf_results.voltage[pqpv]),
               va=np.angle(pf_results.voltage[pqpv]),
               Pg=p0gen,
               Qg=q0gen)

    NV = len(x0)

    print("x0:", x0)
    x, error, gamma = solver(x0=x0, NV=NV, NE=NE, NI=NI,
                             func=evaluate_power_flow,
                             arg=(Ybus, Yf, Cg, Sd, slack, pqpv, Yt, from_idx, to_idx, Va_max,
                                  Va_min, Vm_max, Vm_min, Pg_max, Pg_min, Qg_max, Qg_min, c1, c2, rates),
                             verbose=2)

    return x


def example_3bus_acopf():
    """

    :return:
    """
    grid = build_grid_3bus()
    nc = gce.compile_numerical_circuit_at(grid)
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR)
    power_flow_evaluation(nc=nc, pf_options=pf_options)
    return


def  linn5bus_example():

    # declare a circuit object
    grid = gce.MultiCircuit()

    # Add the buses and the generators and loads attached
    bus1 = gce.Bus('Bus 1', vnom=20)
    # bus1.is_slack = True  # we may mark the bus a slack
    grid.add_bus(bus1)

    # add a generator to the bus 1
    gen1 = gce.Generator('Slack Generator', vset=1.0)
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
    grid.add_line(gce.Line(bus1, bus2, 'line 1-2', r=0.05, x=0.11, b=0.02))
    grid.add_line(gce.Line(bus1, bus3, 'line 1-3', r=0.05, x=0.11, b=0.02))
    grid.add_line(gce.Line(bus1, bus5, 'line 1-5', r=0.03, x=0.08, b=0.02))
    grid.add_line(gce.Line(bus2, bus3, 'line 2-3', r=0.04, x=0.09, b=0.02))
    grid.add_line(gce.Line(bus2, bus5, 'line 2-5', r=0.04, x=0.09, b=0.02))
    grid.add_line(gce.Line(bus3, bus4, 'line 3-4', r=0.06, x=0.13, b=0.03))
    grid.add_line(gce.Line(bus4, bus5, 'line 4-5', r=0.04, x=0.09, b=0.02))

    nc = gce.compile_numerical_circuit_at(grid)
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR)
    power_flow_evaluation(nc=nc, pf_options=pf_options)


if __name__ == '__main__':
    example_3bus_acopf()
    # linn5bus_example()
