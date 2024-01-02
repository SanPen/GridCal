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
    grid.add_generator(b1, gce.Generator('G1', vset=1.001))
    grid.add_generator(b2, gce.Generator('G2', P=10, vset=0.995))

    options = gce.PowerFlowOptions(gce.SolverType.NR, verbose=False)
    power_flow = gce.PowerFlowDriver(grid, options)
    power_flow.run()

    print('\n\n', grid.name)
    print('\tConv:', power_flow.results.get_bus_df())
    print('\tConv:', power_flow.results.get_branch_df())

    nc = gce.compile_numerical_circuit_at(grid)

    return nc


def x2var(x, n_v, n_th, n_P, n_Q):

    a = 0
    b = n_v

    vm = x[a: b]
    a += b
    b += n_th

    th = x[a: b]
    a += b
    b += n_P

    Pg = x[a: b]
    a += b
    b += n_Q

    Qg = x[a: b]

    return vm, th, Pg, Qg


def var2x(vm, th, Pg, Qg):

    return np.r_[vm, th, Pg, Qg]


def eval_f(x, Yf, Cg):

    M, N = Yf.shape
    Ng = Cg.shape[1]  # Check

    vm, th, Pg, Qg = x2var(x, n_v=N, n_th=N, n_P=Ng, n_Q=Ng)

    fval = np.sum(Pg)

    return np.array([fval])


def eval_g(x, Ybus, Yf, Cg, Sd, slack, pv, V_U):

    M, N = Yf.shape
    Ng = Cg.shape[1]  # Check

    vm, th, Pg, Qg = x2var(x, n_v = N, n_th = N, n_P = Ng, n_Q = Ng)
    V = vm * np.exp(1j * th)
    S = V * np.conj(Ybus @ V)

    Sg = Pg + 1j * Qg
    dS = S + Sd - (Cg @ Sg)

    gval = np.r_[dS.real, dS.imag, vm[pv] - V_U[pv], vm[slack] - 1, va[slack]]  # Check, may not need slicing

    return gval


def eval_h(x, Yf, Yt, from_idx, to_idx, pqpv, pq, th_max, th_min, V_U, V_L, P_U, P_L, Q_U, Q_L, Cg, rates):

    M, N = Yf.shape
    Ng = Cg.shape[1]  # Check

    vm, th, Pg, Qg = x2var(x, n_v = N, n_th = N, n_P = Ng, n_Q = Ng)

    V = vm * np.exp(1j * th)

    If = np.conj(Yf @ V)
    Lf = If * If
    Sf = V[from_idx] * If
    St = V[to_idx] * np.conj(Yt @ V)

    hval = np.r_[Sf.real - rates, St.real - rates, vm[pq] - V_U[pq], V_L[pq] - vm[pq], th[pqpv] - th_max[pqpv],
    th_min[pqpv] - th[pqpv], Pg - P_U, P_L - Pg, Qg - Q_U, Q_L, - Qg]

    return hval


def calc_jacobian(func, x, arg = (), h=1e-5):
    """
    Compute the Jacobian matrix of `func` at `x` using finite differences.

    :param func: Linear map (R^n -> R^m). m is 1 for the objective function, NE (Number of Equalities) for
    G or NI (Number of inequalities) for H.
    :param x: Point at which to evaluate the Jacobian (numpy array).
    :param h: Small step for finite difference.
    :return: Jacobian matrix as a numpy array.
    """
    nx = len(x)
    f0 = func(x)
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
    :param h: Small step for finite difference.
    :return: Hessian matrix as a numpy array.
    """
    n = len(x)
    const = len(func(x)) # For objective function, it will be passed as 1. The MULT will be 1 aswell.
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

                a = MULT[eq] * (f_ijp - f_ijm - f_jim + f_jjm) / (4 * h ** 2)
                hessian[i, j] = a
        hessians += hessian
    return hessians


def evaluate_power_flow(x, PI, LAMBDA, Ybus, Yf, Cg, Sd, slack, pqpv, pq, pv, Yt, from_idx, to_idx,
                        th_max, th_min, V_U, V_L, P_U, P_L, Q_U, Q_L, rates, h=1e-5):

    f = eval_f(x=x, Yf=Yf, Cg=Cg)
    G = csc((eval_g(x=x, Ybus=Ybus, Yf=Yf, Cg=Cg, Sd=Sd, slack=slack, pv=pv, V_U=V_U)))
    H = csc((eval_h(x=x, Yf=Yf, Yt=Yt, from_idx=from_idx, to_idx=to_idx, pqpv=pqpv, pq=pq, th_max=th_max, th_min=th_min,
                    V_U=V_U, V_L=V_L, P_U=P_U, P_L=P_L, Q_U=Q_U, Q_L=Q_L, Cg=Cg, rates=rates)))

    fx = csc((calc_jacobian(func=eval_f, x=x, arg=(Yf, Cg), h=h)))
    Gx = csc((calc_jacobian(func=eval_g, x=x, arg=(Ybus, Yf, Cg, Sd, slack, pv, V_U))))
    Hx = csc((calc_jacobian(func=eval_h, x=x, arg=(Yf, Yt, from_idx, to_idx, slack, pqpv, pq, th_max, th_min,
                                                   V_U, V_L, P_U, P_L, Q_U, Q_L, Cg, rates))))

    # TODO input the multipliers for each iteration
    fxx = csc((calc_hessian(func=eval_f, x=x, MULT = [1], arg=(Yf, Cg), h=h)))
    Gxx = csc((calc_hessian(func=eval_g, x=x, MULT = PI, arg=(Ybus, Yf, Cg, Sd, slack, pv, V_U))))
    Hxx = csc((calc_hessian(func=eval_h, x=x, MULT = LAMBDA, arg=(Yf, Yt, from_idx, to_idx, slack, pqpv, pq, th_max,
                                                                  th_min, V_U, V_L, P_U, P_L, Q_U, Q_L, Cg, rates))))

    return f, G, H, fx, Gx, Hx, fxx, Gxx, Hxx


def power_flow_evaluation(nc: gce.NumericalCircuit):

    # Numerical Circuit matrices (admittance and connectivity matrices)
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
    Sd = nc.Sbus
    P_U = nc.generator_data.pmax
    P_L = nc.generator_data.pmin
    Q_U = nc.generator_data.qmax
    Q_L = nc.generator_data.qmin
    V_U = nc.bus_data.Vmax
    V_L = nc.bus_data.Vmin
    rates = nc.rates
    th_max = nc.bus_data.angle_max
    th_min = nc.bus_data.angle_min

    M, N = Yf.shape
    Ng = Cg.shape[1]
    npq = len(pq)
    npv = len(pv)

    NV = 2 * N + 2 * Ng  # V, th of all buses (slack reference in constraints), active and reactive of the generators
    NE = 2 + 2 * N + npv  # Nodal power balances, the voltage module of slack and pv buses and the slack reference
    NI = 2 * M + 2 * N + 2 * npq + 4 * Ng  # Line ratings, max and min angle of buses, voltage module range and
    # active and reactive power generation range.

    ########

    x0 = np.zeros(NV)

    # TODO request correct input and output items and types.
    solution = solver(x0=x0, NV=NV, NE=NE, NI=NI,
                      f_eval=evaluate_power_flow, arg=(Ybus, Yf, Cg, Sd, slack, pqpv, pq, pv, Yt, from_idx, to_idx,
                                                       th_max, th_min, V_U, V_L, P_U, P_L, Q_U, Q_L, rates),
                      step_calculator=step_calculation, verbose=1)

    return solution


def test_acopf():
    nc = build_grid_3bus()
    power_flow_evaluation(nc)
    return


if __name__  == '__main__':
    test_acopf()






