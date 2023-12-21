import math
import numpy as np
from scipy import sparse
from scipy.sparse import csc_matrix as csc
from acopf_functions import *
import GridCalEngine.api as gce
from GridCalEngine.basic_structures import Vec, CxVec


def x2var(x, n_v, n_th, n_P, n_Q, n_phi, n_Pf, n_Qf, n_Pt, n_Qt, n_Lf):
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

    phi = x[a: b]
    a += b
    b += n_Pf

    Pf = x[a: b]
    a += b
    b += n_Qf

    Qf = x[a: b]
    a += b
    b += n_Pt

    Pt= x[a: b]
    a += b
    b += n_Qt

    Qt= x[a: b]
    a += b
    b += n_Lf

    Lf = x[a: b]

    return vm, th, Pg, Qg, phi, Pf, Qf, Pt, Qt, Lf


def var2x(vm, th, Pg, Qg, phi, Pf, Qf, Pt, Qt, Lf):

    return np.r_[vm, th, Pg, Qg, phi, Pf, Qf, Pt, Qt, Lf]


def eval_f(x, Yf, Cg):
    M, N = Yf.shape
    Ng = Cg.shape[1]  # Check

    vm, th, Pg, Qg, phi, Pf, Qf, Pt, Qt, Lf = x2var(x, n_v=N, n_th=N, n_P=Ng, n_Q=Ng, n_phi=M, n_Pf=M,
                                                    n_Qf=M, n_Pt=M, n_Qt=M, n_Lf=M)

    fval = np.sum(Pg)

    return fval

def eval_g(x, Ybus, Yf, Cg, Sd, pvpq, pq):

    M, N = Yf.shape
    Ng = Cg.shape[1]  # Check

    vm, th, Pg, Qg, phi, Pf, Qf, Pt, Qt, Lf = x2var(x, n_v = N, n_th = N, n_P = Ng, n_Q = Ng, n_phi = M, n_Pf = M,
                                                    n_Qf = M, n_Pt = M, n_Qt = M, n_Lf = M)
    V = vm * np.exp(1j * th)
    S = V * np.conj(Ybus @ V)

    Sg = Pg + 1j * Qg
    dS = S + Sd - (Cg @ Sg)

    # Incrementos de las variables.
    # gxval = var2x(vm, th, Pg, Qg, phi, Pf, Qf, Pt, Qt, Lf)
    gval = np.r_[dS.real[pvpq], dS.imag[pq]] # Check, may not need slicing

    return gval

def eval_h(x, Yf, Yt, from_idx, to_idx, Cg, rates):

    M, N = Yf.shape
    Ng = Cg.shape[1]  # Check

    vm, th, Pg, Qg, phi, Pf, Qf, Pt, Qt, Lf = x2var(x, n_v = N, n_th = N, n_P = Ng, n_Q = Ng, n_phi = M, n_Pf = M,
                                                    n_Qf = M, n_Pt = M, n_Qt = M, n_Lf = M)

    V = vm * np.exp(1j * th)

    If = np.conj(Yf @ V)
    Lf = If * If
    Sf = V[from_idx] * If
    St = V[to_idx] * np.conj(Yt @ V)

    # Incrementos de las variables.
    hval = np.r_[Sf.real - rates, St.real - rates]

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


def calc_hessian(func, x, arg=(), h=1e-5):
    """
    Compute the Hessian matrix of `func` at `x` using finite differences.

    :param func: Scalar-valued function (R^n -> R).
    :param x: Point at which to evaluate the Hessian (numpy array).
    :param h: Small step for finite difference.
    :return: Hessian matrix as a numpy array.
    """
    n = len(x)
    hessian = np.zeros((n, n))

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

            hessian[i, j] = (f_ijp - f_ijm - f_jim + f_jjm) / (4 * h ** 2)

    return hessian


def evaluate_power_flow(x, Ybus, Yf, Cg, Sd, pvpq, pq, Yt, from_idx, to_idx, rates, h=1e-5):

    f = eval_f(x=x, Yf=Yf, Cg=Cg)
    G = eval_g(x=x, Ybus=Ybus, Yf=Yf, Cg=Cg, Sd=Sd, pvpq=pvpq, pq=pq)
    H = eval_h(x=x, Yf=Yf, Yt=Yt, from_idx=from_idx, to_idx=to_idx, Cg=Cg, rates=rates)

    fx = calc_jacobian(func=eval_f, x=x, arg=(Yf, Cg), h=h)
    Gx = calc_jacobian(func=eval_g, x=x, arg=(Ybus, Yf, Cg, Sd, pvpq, pq))
    Hx = calc_jacobian(func=eval_h, x=x, arg=(Yf, Yt, from_idx, to_idx, Cg, rates))

    fxx = calc_hessian(func=eval_f, x=x, arg=(Yf, Cg), h=h)
    Gxx = calc_hessian(func=eval_g, x=x, arg=(Ybus, Yf, Cg, Sd, pvpq, pq))
    Hxx = calc_hessian(func=eval_h, x=x, arg=(Yf, Yt, from_idx, to_idx, Cg, rates))

    return f, G, H, fx, Gx, Hx, fxx, Gxx, Hxx

















def power_flow_evaluation(nc: gce.NumericalCircuit, xk: Vec, N: int, L: int, NV: int, NE: int, NI: int):
    # For each iteration, we first calculate in matrix form the power flow using only voltage and angles. Later on,
    # we compute the values of the different gradient and hessians that appear for each constraint.

    # This should be done outside this functions, since this will loop for some iterations and it will slow the process.
    # In here just to keep track of all the variables, later on will be moved outside

    ybus = nc.Ybus
    yf = nc.Yf
    yt = nc.Yt
    cf = nc.Cf
    ct = nc.Ct

    ########

    # Reading the voltage magnitude and angle and expressing in polar form
    vm = xk[0:N]
    va = xk[N:2 * N]
    v = vm * np.exp(1j * va)

    # Bus injections calculation
    sbus = v * np.conj(ybus @ v)
    pbus = np.real(sbus)
    qbus = np.imag(sbus)

    #####

    for i in sbus.shape():
        vmdelta = np.copy(v)
        vadelta = np.copy(v)

        m = (np.real(v[i]) ** 2 + np.imag(v[i]) ** 2) ** (1 / 2)
        a = np.angle(v[i])

        vmdelta[i] = (m + 1e-5) * np.exp(1j * a)
        vadelta[i] = m * np.exp(1j * (a + 1e-5))

        smdelta = vmdelta * np.conj(ybus @ vmdelta)  # Vector dS/dvj for all j
        sadelta = vadelta * np.conj(ybus @ vadelta)  # Vector dS/dthj for all j

    ####

    # Compute nodal balance residual

    resPi = xk[id_P: id_Q] - pd - pbus
    resQi = xk[id_Q: id_phi] - qd - qbus

    # Branch power calculation
    vf = v[nc.branch_data.F]
    vt = v[nc.branch_data.T]

    s_from = vf * np.conj(yf @ v)
    s_to = vt * np.conj(yt @ v)

    p_from = np.real(s_from)
    q_from = np.imag(s_from)
    p_to = np.real(s_to)
    q_to = np.imag(s_to)

    # Compute branch power residuals

    resPfrom = xk[id_Pfrom: id_Qfrom] - p_from
    resQfrom = xk[id_Qfrom: id_Pto] - q_from
    resPto = xk[id_Pto: id_Qto] - p_to
    resQto = xk[id_Qto: id_lij] - q_to

    # Objective function

    f = xk[id_P: id_Q].power(2).multiply(c2).sum() + xk[id_P: id_Q].multiply(c1).sum()
    fx = 2 * xk[id_P: id_Q].multiply(c2)
    fxx = sparse.dia_matrix((2 * c2.toarray(), 0), shape=(NV, NV))

    # This is the structure they should have. Init as lists since modifying a csc matrix is expensive.

    # G = csc((NE, 1)) And we already computed the nodal and branch balances, we can initialize them stacked in G.
    # Gx = csc((NV, NE))
    # Gxx = csc((NV, NV))
    # H = csc((NI, 1))
    # Hx = csc((NV, NI))
    # Hxx = csc((NV, NV))

    G = np.array((NE, 1))
    G[0: 2 * N + 4 * L] = sparse.vstack([resPi, resQi, resPfrom, resQfrom, resPto, resQto]).toarray()
    Gx = np.array((NV, NE))
    Gxx = np.array((NV, NV))
    H = np.zeros((NI, 1))
    Hx = np.zeros((NV, NI))
    Hxx = np.zeros((NV, NV))

    for n in range(N):
        # Nodal balances are already evaluated, but we need to evaluate the gradients and hessians, which will
        # depend on each bus.

        grad_pi()
        grad_qi()
        hess_pi()  # Instead of leaving Pg = sum(Pij) + Pd, we are using the full expression in respect to the voltage
        # and angles, using expressions
        hess_qi()

        H[n] = xk[n] - V_U[n]
        H[n + N] = xk[n] - V_L[n] - xk[n]
        H[n + 2 * N] = xk[n + id_P] - P_

    for l in range(L):
        # We first get the nodes connected
        i, j = LINE[l]

    return
