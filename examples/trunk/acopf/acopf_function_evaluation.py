import math
import numpy as np
from scipy import sparse
from scipy.sparse import csc_matrix as csc
from acopf_functions import *
import GridCalEngine.api as gce
from GridCalEngine.basic_structures import Vec, CxVec
from GridCalEngine.Utils.MIPS.mips import solver, step_calculation


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
    a += b
    b += n_phi


    return vm, th, Pg, Qg


def var2x(vm, th, Pg, Qg):

    return np.r_[vm, th, Pg, Qg]


def eval_f(x, Yf, Cg):
    M, N = Yf.shape
    Ng = Cg.shape[1]  # Check

    vm, th, Pg, Qg = x2var(x, n_v=N, n_th=N, n_P=Ng, n_Q=Ng)

    fval = np.sum(Pg)

    return fval


def eval_g(x, Ybus, Yf, Cg, Sd, slack, pqpv, pq):

    M, N = Yf.shape
    Ng = Cg.shape[1]  # Check

    vm, th, Pg, Qg = x2var(x, n_v = N, n_th = N, n_P = Ng, n_Q = Ng)
    V = vm * np.exp(1j * th)
    S = V * np.conj(Ybus @ V)

    Sg = Pg + 1j * Qg
    dS = S + Sd - (Cg @ Sg)

    # Incrementos de las variables. También se incluyen las tensiones de los buses PQPV. Usamos V_U, aunque es igual
    # que V_L en este caso al ser nodos de tensión fija. Tambien fijamos la tensión del slack.
    # gxval = var2x(vm, th, Pg, Qg, phi, Pf, Qf, Pt, Qt, Lf)
    gval = np.r_[dS.real, dS.imag, vm[pv] - V_U[pv], vm[slack] - 1, va[slack]]  # Check, may not need slicing

    return gval


def eval_h(x, Yf, Yt, from_idx, to_idx, slack, pqpv, pq, Cg, rates):

    M, N = Yf.shape
    Ng = Cg.shape[1]  # Check

    vm, th, Pg, Qg = x2var(x, n_v = N, n_th = N, n_P = Ng, n_Q = Ng)

    V = vm * np.exp(1j * th)

    If = np.conj(Yf @ V)
    Lf = If * If
    Sf = V[from_idx] * If
    St = V[to_idx] * np.conj(Yt @ V)

    # Incrementos de las variables. Los límites de las varianbles también se cuentan, en este caso serán las V,th de los
    # buses PQ y las potencias de generador de los buses PQPV, así como sus angulos.
    hval = np.r_[Sf.real - rates, St.real - rates, vm[pq] - V_U, V_L - vm[pq], th - angle_max, angle_min - th,
    Pg - P_U, P_L - Pg, Qg - Q_U, Q_L, - Qg]

    return hval


def calc_jacobian(func, x, arg = (), h=1e-5):
    """
    Compute the Jacobian matrix of `func` at `x` using finite differences.

    :param func: Vector-valued function (R^n -> R^m).
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

    :param func: Scalar-valued function (R^n -> R).
    :param x: Point at which to evaluate the Hessian (numpy array).
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


def evaluate_power_flow(x, Ybus, Yf, Cg, Sd, slack, pqpv, pq, Yt, from_idx, to_idx, rates, h=1e-5):

    f = eval_f(x=x, Yf=Yf, Cg=Cg)
    G = eval_g(x=x, Ybus=Ybus, Yf=Yf, Cg=Cg, Sd=Sd, slack=slack, pqpv=pqpv, pq=pq)
    H = eval_h(x=x, Yf=Yf, Yt=Yt, from_idx=from_idx, to_idx=to_idx, slack=slack, pqpv=pqpv, pq=pq, Cg=Cg, rates=rates)

    fx = calc_jacobian(func=eval_f, x=x, arg=(Yf, Cg), h=h)
    Gx = calc_jacobian(func=eval_g, x=x, arg=(Ybus, Yf, Cg, Sd, slack, pqpv, pq))
    Hx = calc_jacobian(func=eval_h, x=x, arg=(Yf, Yt, from_idx, to_idx, slack, pqpv, pq, Cg, rates))

    # TODO input the multipliers for each iteration
    fxx = calc_hessian(func=eval_f, x=x, MULT = [], arg=(Yf, Cg), h=h)
    Gxx = calc_hessian(func=eval_g, x=x, MULT = [], arg=(Ybus, Yf, Cg, Sd, slack, pqpv, pq))
    Hxx = calc_hessian(func=eval_h, x=x, MULT = [], arg=(Yf, Yt, from_idx, to_idx, slack, pqpv, pq, Cg, rates))

    return f, G, H, fx, Gx, Hx, fxx, Gxx, Hxx


def power_flow_evaluation(nc: gce.NumericalCircuit):

    # Numerical Circuit matrices (admittance and connectivity matrices)
    Ybus = nc.Ybus
    Yf = nc.Yf
    Yt = nc.Yt
    Cf = nc.Cf
    Ct = nc.Ct
    Cg = nc.generator_data.C_bus_elm

    # Bus identification lists
    slack = nc.vd
    pq = nc.pq
    pv = nc.pv
    pqpv = nc.pqpv
    from_idx = nc.F
    to_idx = nc.T

    #Bus and line parameters
    Sd = nc.Sbus
    P_U = nc.generator_data.pmax
    P_L = nc.generator_data.pmin
    Q_U = nc.generator_data.qmax
    Q_L = nc.generator_data.qmin
    V_U = nc.bus_data.Vmax
    V_L = nc.bus_data.Vmin
    rates = nc.rates
    angle_max = nc.bus_data.angle_max
    angle_min = nc.bus_data.angle_min

    M, N = Yf.shape
    Ng = Cg.shape[1]
    npq = len(pq)
    npv = len(pv)

    NV = 2 * N + 2 * Ng  # V, th of all buses, active and reactive of the generators
    NE = 2 + 2 * N + npv  # Nodal power balances, the voltage module of slack and pv buses and the slack reference
    NI = 2 * M + 2 * N + 2 * npq + 4 * Ng  # Line ratings, max and min angle of buses, voltage module range and
    # active and reactive power generation range.

    ########

    x0 = []

    # TODO request correct input and output items and types.
    solution = solver(x0=x0, NV=NV, NE=NE, NI=NI,
           f_eval=evaluate_power_flow(xk, Ybus, Yf, Cg, Sd, slack, pqpv,
                                      pq, Yt, from_idx, to_idx, rates, h=1e-5),
           step_calculator=step_calculation, verbose=1)


    return
