import math
import numpy as np
from scipy import sparse
from scipy.sparse import csc_matrix as csc
import GridCalEngine.api as gce
from GridCalEngine.basic_structures import Vec, CxVec
from GridCalEngine.Utils.MIPS.mips import solver, step_calculation
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
    grid.add_generator(b1, gce.Generator('G1', vset=1.00))
    grid.add_generator(b2, gce.Generator('G2', P=10, vset=0.995))

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


def var2x(vm, th, Pg, Qg):
    return np.r_[vm, th, Pg, Qg]


def eval_f(x, Yf, Cg, c1, c2):
    M, N = Yf.shape
    Ng = Cg.shape[1]  # Check

    vm, va, Pg, Qg = x2var(x, n_v=N - 1, n_th=N - 1, n_P=Ng, n_Q=Ng)

    fval = np.sum((c2 * Pg ** 2 + c1 * Pg))

    return np.array([fval])


def eval_g(x, Ybus, Yf, Cg, Sd, slack, pv, V_U):
    """

    :param x:
    :param Ybus:
    :param Yf:
    :param Cg:
    :param Sd:
    :param slack:
    :param pv:
    :param V_U:
    :return:
    """
    M, N = Yf.shape
    Ng = Cg.shape[1]  # Check

    vm, va, Pg, Qg = x2var(x, n_v=N - 1, n_th=N - 1, n_P=Ng, n_Q=Ng)
    vm = np.r_[1, vm]
    va = np.r_[0, va]
    V = vm * np.exp(1j * va)
    S = V * np.conj(Ybus @ V)

    Sg = Pg + 1j * Qg
    dS = S + Sd - (Cg @ Sg)

    gval = np.r_[dS.real, dS.imag]

    return gval


def eval_h(x, Yf, Yt, from_idx, to_idx, pqpv, pq, th_max, th_min, V_U, V_L, P_U, P_L, Q_U, Q_L, Cg, rates):
    """

    :param x:
    :param Yf:
    :param Yt:
    :param from_idx:
    :param to_idx:
    :param pqpv:
    :param pq:
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

    vm, va, Pg, Qg = x2var(x, n_v=N - 1, n_th=N - 1, n_P=Ng, n_Q=Ng)
    vm = np.r_[1.0, vm]
    va = np.r_[0.0, va]
    V = vm * np.exp(1j * va)

    If = np.conj(Yf @ V)
    Lf = If * If
    Sf = V[from_idx] * If
    St = V[to_idx] * np.conj(Yt @ V)

    hval = np.r_[Sf.real - rates,           # rates "lower limit"
                 St.real - rates,           # rates "upper limit"
                 vm[pqpv] - V_U[pqpv],      # voltage module upper limit
                 V_L[pqpv] - vm[pqpv],      # voltage module lower limit
                 va[pqpv] - th_max[pqpv],   # voltage angles upper limit
                 th_min[pqpv] - va[pqpv],   # voltage angles lower limit
                 Pg - P_U,                  # generatior P upper limits
                 P_L - Pg,                  # generation P lower limits
                 Qg - Q_U,                  # generatior Q upper limits
                 Q_L - Qg                   # generation Q lower limits
                 ]

    return hval


def calc_jacobian(func, x, arg=(), h=1e-5):
    """
    Compute the Jacobian matrix of `func` at `x` using finite differences.

    :param func: Linear map (R^n -> R^m). m is 1 for the objective function, NE (Number of Equalities) for
    G or NI (Number of inequalities) for H.
    :param x: Point at which to evaluate the Jacobian (numpy array).
    :param arg: Tuple of arguments to call func aside from x [func(x, *arg)]
    :param h: Small step for finite difference.
    :return: Jacobian matrix as a numpy array.
    """
    nx = len(x)
    f0 = func(x, *arg)
    jac = np.zeros((len(f0), nx))

    for i in range(nx):
        x_plus_h = np.copy(x)
        x_plus_h[i] += h
        f_plus_h = func(x_plus_h, *arg)
        jac[:, i] = (f_plus_h - f0) / h

    return jac


def calc_hessian(func, x, MULT, arg=(), h=1e-5):
    """
    Compute the Hessian matrix of `func` at `x` using finite differences.

    :param func: Linear map (R^n -> R^m). m is 1 for the objective function, NE (Number of Equalities) for
    G or NI (Number of inequalities) for H.
    :param x: Point at which to evaluate the Hessian (numpy array).
    :param MULT: Array of multipliers associated with the functions. The objective function passes value 1 (no action)
    :param arg: Tuple of arguments to call func aside from x [func(x, *arg)]
    :param h: Small step for finite difference.
    :return: Hessian matrix as a numpy array.
    """
    n = len(x)
    const = len(func(x, *arg))  # For objective function, it will be passed as 1. The MULT will be 1 aswell.
    hessians = np.zeros((n, n))

    for eq in range(const):
        hessian = np.zeros((n, n))
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

                a = MULT[0][eq] * (f_ijp - f_ijm - f_jim + f_jjm) / (4 * h ** 2)
                hessian[i][j] = a
        hessians += hessian
    return hessians


def evaluate_power_flow(x, LAMBDA, PI, Ybus, Yf, Cg, Sd, slack, pqpv, pq, pv, Yt, from_idx, to_idx,
                        th_max, th_min, V_U, V_L, P_U, P_L, Q_U, Q_L, c1, c2, rates, h=1e-5):
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
    :param pq:
    :param pv:
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
    G = csc((eval_g(x=x, Ybus=Ybus, Yf=Yf, Cg=Cg, Sd=Sd, slack=slack, pv=pv, V_U=V_U))).T
    H = csc((eval_h(x=x, Yf=Yf, Yt=Yt, from_idx=from_idx, to_idx=to_idx, pqpv=pqpv, pq=pq, th_max=th_max, th_min=th_min,
                    V_U=V_U, V_L=V_L, P_U=P_U, P_L=P_L, Q_U=Q_U, Q_L=Q_L, Cg=Cg, rates=rates))).T

    fx = csc((calc_jacobian(func=eval_f, x=x, arg=(Yf, Cg, c1, c2), h=h))).T
    Gx = csc((calc_jacobian(func=eval_g, x=x, arg=(Ybus, Yf, Cg, Sd, slack, pv, V_U)))).T
    Hx = csc((calc_jacobian(func=eval_h, x=x, arg=(Yf, Yt, from_idx, to_idx, pqpv, pq, th_max, th_min,
                                                   V_U, V_L, P_U, P_L, Q_U, Q_L, Cg, rates)))).T

    # TODO input the multipliers for each iteration
    fxx = csc((calc_hessian(func=eval_f, x=x, MULT=[[1]], arg=(Yf, Cg, c1, c2), h=h)))
    Gxx = csc((calc_hessian(func=eval_g, x=x, MULT=PI.toarray(), arg=(Ybus, Yf, Cg, Sd, slack, pv, V_U))))
    Hxx = csc((calc_hessian(func=eval_h, x=x, MULT=LAMBDA.toarray(), arg=(Yf, Yt, from_idx, to_idx, pqpv, pq, th_max,
                                                                          th_min, V_U, V_L, P_U, P_L, Q_U, Q_L, Cg,
                                                                          rates))))

    return f, G, H, fx, Gx, Hx, fxx, Gxx, Hxx


def power_flow_evaluation(grid: gce.MultiCircuit):
    """

    :param grid:
    :return:
    """
    nc = gce.compile_numerical_circuit_at(grid)
    # Numerical Circuit matrices (admittance and connectivity matrices)
    nc.generator_data.cost_2 = np.array([2, 3])
    c1 = nc.generator_data.cost_1
    c2 = nc.generator_data.cost_2

    Ybus = nc.Ybus
    Yf = nc.Yf
    Yt = nc.Yt
    Cg = nc.generator_data.C_bus_elm

    # Bus identification lists
    slack = nc.vd
    pq = nc.pq
    pv = nc.pv
    pqpv = nc.pqpv
    from_idx = nc.F
    to_idx = nc.T

    # Bus and line parameters
    Sbase = nc.Sbase
    Sd = nc.load_data.C_bus_elm @ nc.load_data.S / Sbase
    P_U = nc.generator_data.pmax / Sbase
    P_L = nc.generator_data.pmin / Sbase
    Q_U = nc.generator_data.qmax / Sbase
    Q_L = nc.generator_data.qmin / Sbase
    V_U = nc.bus_data.Vmax
    V_L = nc.bus_data.Vmin
    rates = nc.rates / Sbase
    th_max = nc.bus_data.angle_max
    th_min = nc.bus_data.angle_min

    M, N = Yf.shape
    Ng = Cg.shape[1]
    npq = len(pq)
    npv = len(pv)
    npqpv = len(pqpv)

    NV = 2 * (
                N - 1) + 2 * Ng  # V, th of all buses (slack reference in constraints), active and reactive of the generators
    NE = 2 * N  # Nodal power balances, the voltage module of slack and pv buses and the slack reference
    NI = 2 * M + 4 * npqpv + 4 * Ng  # Line ratings, max and min angle of buses, voltage module range and
    # active and reactive power generation range.

    ########

    # vm0 = np.array([1, 0.98, 0.95])
    # va0 = np.array([0, 0.05, -0.03])
    # Pg0 = np.array([0.5, 0.3])
    # Qg0 = np.array([0.2, 0.1])

    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR)
    pf_driver = gce.PowerFlowDriver(grid=grid,
                                    options=pf_options)
    pf_driver.run()

    # ignore power from Z and I of the load
    s0gen = pf_driver.results.Sbus / nc.Sbase - nc.load_data.C_bus_elm @ nc.load_data.S / nc.Sbase
    p0gen = nc.generator_data.C_bus_elm.T @ np.real(s0gen)
    q0gen = nc.generator_data.C_bus_elm.T @ np.imag(s0gen)

    # p0gen = nc.generator_data.C_bus_elm.T @ np.zeros(len(s0gen))
    # q0gen = nc.generator_data.C_bus_elm.T @ np.zeros(len(s0gen))

    x0 = np.zeros(NV)
    x0[0: npqpv] = abs(pf_driver.results.voltage[pqpv])  # e
    x0[npqpv: 2 * npqpv] = np.angle(pf_driver.results.voltage[pqpv])  # f
    x0[2 * npqpv: 2 * npqpv + Ng] = p0gen  # pgen
    x0[2 * npqpv + Ng: 2 * npqpv + 2 * Ng] = q0gen  # qgen

    print(x0)
    # x0 = var2x(vm0, va0, Pg0, Qg0)

    solution = solver(x0=x0, NV=NV, NE=NE, NI=NI,
                      func=evaluate_power_flow, arg=(Ybus, Yf, Cg, Sd, slack, pqpv, pq, pv, Yt, from_idx, to_idx,
                                                     th_max, th_min, V_U, V_L, P_U, P_L, Q_U, Q_L, c1, c2, rates),
                      step_calculator=step_calculation, verbose=1)

    return solution


def test_acopf():
    grid = build_grid_3bus()
    power_flow_evaluation(grid)
    return


if __name__ == '__main__':
    test_acopf()
