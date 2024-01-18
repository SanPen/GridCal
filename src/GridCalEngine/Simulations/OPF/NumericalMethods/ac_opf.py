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
from scipy import sparse
from scipy.sparse import csc_matrix as csc
from scipy.sparse import lil_matrix
import GridCalEngine.api as gce
from GridCalEngine.basic_structures import Vec
from GridCalEngine.Utils.Sparse.csc import diags
from GridCalEngine.Utils.MIPS.mips import solver
from GridCalEngine.Simulations.PowerFlow.power_flow_worker import multi_island_pf_nc
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
    Sf2 = np.conj(Sf) * Sf
    St2 = np.conj(St) * St
    hval = np.r_[Sf2.real - (rates ** 2),  # rates "lower limit"
                 St2.real - (rates ** 2),  # rates "upper limit"
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


def jacobians(x, c1, c2, Cg, Cf, Ct, Yf, Yt, Ybus, Sbase, slack, no_slack, mu, lmbda):

    M, N = Yf.shape
    Ng = Cg.shape[1]  # Check
    NV = len(x)

    vm, va, Pg, Qg = x2var(x, n_vm=N, n_va=N, n_P=Ng, n_Q=Ng)
    V = vm * np.exp(1j * va)
    Vmat = diags(V)
    vm_inv = diags(1/vm)
    E = Vmat @ vm_inv
    Ibus = Ybus @ V
    IbusCJmat = diags(np.conj(Ibus))

    fx = np.zeros(NV)

    fx[2 * N : 2 * N + Ng] = (2 * c2 * Pg * (Sbase ** 2) + c1 * Sbase) * 1e-4

    #########

    GSvm = Vmat @ (IbusCJmat + np.conj(Ybus) @ np.conj(Vmat)) @ vm_inv
    GSva = 1j * Vmat @ (IbusCJmat - np.conj(Ybus) @ np.conj(Vmat))
    GSpg = -Cg
    GSqg = -1j * Cg

    GTH = np.zeros(len(x))
    GTH[slack + N] = 1

    GS = sparse.hstack([GSvm, GSva, GSpg, GSqg])
    Gx = sparse.vstack([GS.real, GS.imag, GTH])

    #############

    IfCJmat = np.conj(diags(Yf @ V))
    ItCJmat = np.conj(diags(Yt @ V))
    Sfmat = diags(diags(Cf @ V) @ np.conj(Yf @ V))
    Stmat = diags(diags(Ct @ V) @ np.conj(Yt @ V))

    Sfvm = IfCJmat @ Cf @ E + diags(Cf @ V) @ np.conj(Yf) @ np.conj(E)
    Stvm = ItCJmat @ Ct @ E + diags(Ct @ V) @ np.conj(Yt) @ np.conj(E)

    Sfva = 1j * (IfCJmat @ Cf @ Vmat - diags(Cf @ V) @ np.conj(Yf) @ np.conj(Vmat))
    Stva = 1j * (ItCJmat @ Ct @ Vmat - diags(Ct @ V) @ np.conj(Yt) @ np.conj(Vmat))

    SfX = sparse.hstack([Sfvm, Sfva, lil_matrix((M, 2 * Ng))])
    StX = sparse.hstack([Stvm, Stva, lil_matrix((M, 2 * Ng))])

    HSf = 2 * (Sfmat.real @ SfX.real + Sfmat.imag @ SfX.imag)
    HSt = 2 * (Stmat.real @ StX.real + Stmat.imag @ StX.imag)

    Hvu = np.zeros(N)
    Hvl = np.zeros(N)
    Hvau = np.zeros(N)
    Hval = np.zeros(N)
    Hpu = np.zeros(Ng)
    Hpl = np.zeros(Ng)
    Hqu = np.zeros(Ng)
    Hql = np.zeros(Ng)

    Hvu[0 : N] = 1
    Hvl[0 : N] = -1
    #Hvau[no_slack] = 1
    #Hval[no_slack] = -1
    Hvau = csc(([1] * (N - len(slack)), (list(range(N - len(slack))), no_slack)))
    Hval = csc(([-1] * (N - len(slack)), (list(range(N - len(slack))), no_slack)))

    Hpu[0 : N] = 1
    Hpl[0 : Ng] = -1
    Hqu[0 : Ng] = 1
    Hql[0 : Ng] = -1

    Hvu = sparse.hstack([diags(Hvu), lil_matrix((N, N + 2 * Ng))])
    Hvl = sparse.hstack([diags(Hvl), lil_matrix((N, N + 2 * Ng))])
    Hvau = sparse.hstack([lil_matrix((N - len(slack), N)), Hvau, lil_matrix((N - len(slack), 2 * Ng))])
    Hval = sparse.hstack([lil_matrix((N - len(slack), N)), Hval, lil_matrix((N - len(slack), 2 * Ng))])
    Hpu = sparse.hstack([lil_matrix((Ng, 2 * N)), diags(Hpu), lil_matrix((Ng, Ng))])
    Hpl = sparse.hstack([lil_matrix((Ng, 2 * N)), diags(Hpl), lil_matrix((Ng, Ng))])
    Hqu = sparse.hstack([lil_matrix((Ng, 2 * N + Ng)), diags(Hqu)])
    Hql = sparse.hstack([lil_matrix((Ng, 2 * N + Ng)), diags(Hql)])

    Hx = sparse.vstack([HSf, HSt, Hvu, Hvl, Hvau, Hval, Hpu, Hpl, Hqu, Hql])

    ##########

    fxx = diags((np.r_[np.zeros(2*N), 2 * c2 * (Sbase**2), np.zeros(Ng)]) * 1e-4)

    ##########


    '''
    lmbda_mat = diags(lmbda[0 : 2 * N])
    Ad = lmbda[0 : 2 * N] * np.r_[V.real, V.imag]
    A = diags(Ad[0 : N] + 1j * Ad[N : 2 * N])
    B = Ybus @ Vmat
    C = A @ np.conj(B)
    D = np.conj(Ybus).T @ Vmat
    F = 1j * (diags(lmbda[0 : N]) @ GSva.real + 1j * diags(lmbda[N : 2 * N]) @ GSva.imag)
    DLmat = D.real @ diags(lmbda[0 : N]) + 1j * D.imag @ diags(lmbda[N : 2 * N])
    DL = D.real @ lmbda[0 : N] + 1j * D.imag @ lmbda[N : 2 * N]
    I = np.conj(Vmat) @ (DLmat - diags(DL))

    GSvava_d = I + F
    GSvmva_d = 1j * vm_inv @ (I - F)
    GSvavm_d = GSvmva_d.T
    GSvmvm_d = vm_inv @ (C + C.T) @ vm_inv

    GSvava = GSvava_d.real + GSvava_d.imag
    GSvmva = GSvmva_d.real + GSvmva_d.imag
    GSvavm = GSvavm_d.real + GSvavm_d.imag
    GSvmvm = GSvmvm_d.real + GSvmvm_d.imag

    G1 = sparse.hstack([GSvmvm, GSvmva, lil_matrix((N, 2 * Ng))])
    G2 = sparse.hstack([GSvavm, GSvava, lil_matrix((N, 2 * Ng))])
    Gxx = sparse.vstack([G1, G2, lil_matrix((2 * Ng, NV))])

    #########
    mu_mat = diags(mu[0 : M]) # Check if we have to grab just the from branches
    Af = np.conj(Yf).T @ mu_mat @ Cf
    Bf = np.conj(Vmat) @ Af @ Vmat
    Df = diags(Af @ V) @ np.conj(Vmat)
    Ef = diags(Af.T @ np.conj(V)) @ Vmat
    Ff = Bf + Bf.T
    Sfvava = Ff - Df - Ef
    Sfvmva = 1j * vm_inv @ (Bf - Bf.T - Df + Ef)
    Sfvavm = Sfvmva.T
    Sfvmvm = vm_inv @ Ff @ vm_inv

    Hfvava = 2 * (Sfvava @ (np.conj(Sfmat) @ mu[0 : M]) + Sfva.T @ mu_mat @ np.conj(Sfva)).real
    Hfvmva = 2 * (Sfvmva @ (np.conj(Sfmat) @ mu[0 : M]) + Sfvm.T @ mu_mat @ np.conj(Sfva)).real
    Hfvavm = 2 * (Sfvavm @ (np.conj(Sfmat) @ mu[0 : M]) + Sfva.T @ mu_mat @ np.conj(Sfvm)).real
    Hfvmvm = 2 * (Sfvmvm @ (np.conj(Sfmat) @ mu[0 : M]) + Sfvm.T @ mu_mat @ np.conj(Sfvm)).real

    mu_mat = diags(mu[M: 2 * M])  # Check same
    At = np.conj(Yt).T @ mu_mat @ Ct
    Bt = np.conj(Vmat) @ At @ Vmat
    Dt = diags(At @ V) @ np.conj(Vmat)
    Et = diags(At.T @ np.conj(V)) @ Vmat
    Ft = Bt + Bt.T
    Stvava = Ft - Dt - Et
    Stvmva = 1j * vm_inv @ (Bt - Bt.T - Dt + Et)
    Stvavm = Stvmva.T
    Stvmvm = vm_inv @ Ft @ vm_inv

    Htvava = 2 * (Stvava @ (np.conj(Stmat) @ mu[M : 2 * M]) + Stva.T @ mu_mat @ np.conj(Stva)).real
    Htvmva = 2 * (Stvmva @ (np.conj(Stmat) @ mu[M : 2 * M]) + Stvm.T @ mu_mat @ np.conj(Stva)).real
    Htvavm = 2 * (Stvavm @ (np.conj(Stmat) @ mu[M : 2 * M]) + Stva.T @ mu_mat @ np.conj(Stvm)).real
    Htvmvm = 2 * (Stvmvm @ (np.conj(Stmat) @ mu[M : 2 * M]) + Stvm.T @ mu_mat @ np.conj(Stvm)).real

    H1 = sparse.hstack([Hfvmvm + Htvmvm, Hfvmva + Htvmva, lil_matrix((N, 2 * Ng))])
    H2 = sparse.hstack([Hfvavm + Htvavm, Hfvava + Htvava, lil_matrix((N, 2 * Ng))])
    Hxx = sparse.vstack([H1, H2, lil_matrix((2 * Ng, NV))])
    '''

    lmbda_mat = diags(lmbda[0: 2 * N])
    Ad = lmbda[0: 2 * N] * np.r_[V.real, V.imag]
    A = diags(Ad[0: N] + 1j * Ad[N: 2 * N])
    B = Ybus @ Vmat
    C = A @ np.conj(B)
    D = np.conj(Ybus).T @ Vmat
    F = 1j * (diags(lmbda[0: N]) @ GSva.real + 1j * diags(lmbda[N: 2 * N]) @ GSva.imag)
    DLmat = D.real @ diags(lmbda[0: N]) + 1j * D.imag @ diags(lmbda[N: 2 * N])
    DL = D.real @ lmbda[0: N] + 1j * D.imag @ lmbda[N: 2 * N]
    I = np.conj(Vmat) @ (DLmat - diags(DL))

    GSvava_d = I + F
    GSvmva_d = 1j * vm_inv @ (I - F)
    GSvavm_d = GSvmva_d.T
    GSvmvm_d = vm_inv @ (C + C.T) @ vm_inv

    GSvava = GSvava_d.real + GSvava_d.imag
    GSvmva = GSvmva_d.real + GSvmva_d.imag
    GSvavm = GSvavm_d.real + GSvavm_d.imag
    GSvmvm = GSvmvm_d.real + GSvmvm_d.imag

    G1 = sparse.hstack([GSvmvm, GSvmva, lil_matrix((N, 2 * Ng))])
    G2 = sparse.hstack([GSvavm, GSvava, lil_matrix((N, 2 * Ng))])
    Gxx = sparse.vstack([G1, G2, lil_matrix((2 * Ng, NV))])

    #########

    mu_mat = diags(np.conj(Sfmat) @ mu[0: M])  # Check if we have to grab just the from branches
    Af = np.conj(Yf).T @ mu_mat @ Cf
    Bf = np.conj(Vmat) @ Af @ Vmat
    Df = diags(Af @ V) @ np.conj(Vmat)
    Ef = diags(Af.T @ np.conj(V)) @ Vmat
    Ff = Bf + Bf.T
    Sfvava = Ff - Df - Ef
    Sfvmva = 1j * vm_inv @ (Bf - Bf.T - Df + Ef)
    Sfvavm = Sfvmva.T
    Sfvmvm = vm_inv @ Ff @ vm_inv

    mu_mat = diags(mu[0:M])
    Hfvava = 2 * (Sfvava + Sfva.T @ mu_mat @ np.conj(Sfva)).real
    Hfvmva = 2 * (Sfvmva + Sfvm.T @ mu_mat @ np.conj(Sfva)).real
    Hfvavm = 2 * (Sfvavm + Sfva.T @ mu_mat @ np.conj(Sfvm)).real
    Hfvmvm = 2 * (Sfvmvm + Sfvm.T @ mu_mat @ np.conj(Sfvm)).real

    mu_mat = diags(np.conj(Stmat) @ mu[M: 2 * M])  # Check same
    At = np.conj(Yt).T @ mu_mat @ Ct
    Bt = np.conj(Vmat) @ At @ Vmat
    Dt = diags(At @ V) @ np.conj(Vmat)
    Et = diags(At.T @ np.conj(V)) @ Vmat
    Ft = Bt + Bt.T
    Stvava = Ft - Dt - Et
    Stvmva = 1j * vm_inv @ (Bt - Bt.T - Dt + Et)
    Stvavm = Stvmva.T
    Stvmvm = vm_inv @ Ft @ vm_inv

    mu_mat = diags(mu[M:2*M])
    Htvava = 2 * (Stvava + Stva.T @ mu_mat @ np.conj(Stva)).real
    Htvmva = 2 * (Stvmva + Stvm.T @ mu_mat @ np.conj(Stva)).real
    Htvavm = 2 * (Stvavm + Stva.T @ mu_mat @ np.conj(Stvm)).real
    Htvmvm = 2 * (Stvmvm + Stvm.T @ mu_mat @ np.conj(Stvm)).real

    H1 = sparse.hstack([Hfvmvm + Htvmvm, Hfvmva + Htvmva, lil_matrix((N, 2 * Ng))])
    H2 = sparse.hstack([Hfvavm + Htvavm, Hfvava + Htvava, lil_matrix((N, 2 * Ng))])
    Hxx = sparse.vstack([H1, H2, lil_matrix((2 * Ng, NV))])

    return fx, Gx.tocsc().T, Hx.tocsc().T, fxx, Gxx, Hxx


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

            a = (f_ijp - f_ijm - f_jim + f_jjm) / (4 * np.power(h, 2))

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

                a = mult[eq] * (f_ijp - f_ijm - f_jim + f_jjm) / (4 * np.power(h, 2))

                if a != 0.0:
                    hessian[i, j] = a

        hessians += hessian

    return hessians.tocsc()


def evaluate_power_flow(x, mu, lmbda, Ybus, Yf, Cg, Cf, Ct, Sd, slack, no_slack, Yt, from_idx, to_idx,
                        th_max, th_min, V_U, V_L, P_U, P_L, Q_U, Q_L, c0, c1, c2, Sbase, rates, h=1e-5) -> (
        Tuple)[Vec, Vec, Vec, Vec, csc, csc, csc, csc, csc]:
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
    :param c1:
    :param c2:
    :param rates:
    :param h:
    :return:
    """
    f = eval_f(x=x, Yf=Yf, Cg=Cg, c0=c0, c1=c1, c2=c2, Sbase=Sbase, no_slack=no_slack)
    G = eval_g(x=x, Ybus=Ybus, Yf=Yf, Cg=Cg, Sd=Sd, slack=slack, no_slack=no_slack)
    H = eval_h(x=x, Yf=Yf, Yt=Yt, from_idx=from_idx, to_idx=to_idx, slack=slack, no_slack=no_slack, th_max=th_max,
               th_min=th_min, V_U=V_U, V_L=V_L, P_U=P_U, P_L=P_L, Q_U=Q_U, Q_L=Q_L, Cg=Cg, rates=rates)

    #fx_long = calc_jacobian_f_obj(func=eval_f, x=x, arg=(Yf, Cg, c0, c1, c2, Sbase, no_slack), h=h)
    #Gx_long = calc_jacobian(func=eval_g, x=x, arg=(Ybus, Yf, Cg, Sd, slack, no_slack)).T
    #Hx_long = calc_jacobian(func=eval_h, x=x, arg=(Yf, Yt, from_idx, to_idx, slack, no_slack, th_max, th_min,
    #                                               V_U, V_L, P_U, P_L, Q_U, Q_L, Cg, rates)).T

    fx, Gx, Hx, fxx, Gxx, Hxx = jacobians(x=x, c1=c1, c2=c2, Cg=Cg, Cf=Cf, Ct=Ct, Yf=Yf, Yt=Yt,
                                          Ybus=Ybus, Sbase=Sbase, slack=slack, no_slack=no_slack, mu=mu, lmbda=lmbda)

    #fxx_long = calc_hessian_f_obj(func=eval_f, x=x, arg=(Yf, Cg, c0, c1, c2, Sbase, no_slack), h=h)
    #Gxx_long = calc_hessian(func=eval_g, x=x, mult=lmbda, arg=(Ybus, Yf, Cg, Sd, slack, no_slack))
    #Hxx_long = calc_hessian(func=eval_h, x=x, mult=mu, arg=(Yf, Yt, from_idx, to_idx, slack, no_slack, th_max,
    #                                                   th_min, V_U, V_L, P_U, P_L, Q_U, Q_L, Cg, rates))

    return f, G, H, fx, Gx, Hx, fxx, Gxx, Hxx


def ac_optimal_power_flow(nc: gce.NumericalCircuit, pf_options: gce.PowerFlowOptions, verbose = 2):
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
    Cf = nc.Cf
    Ct = nc.Ct

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

    if verbose>0:
        print("x0:", x0)
    x, error, gamma, lam = solver(x0=x0, n_x=NV, n_eq=NE, n_ineq=NI,
                                  func=evaluate_power_flow,
                                  arg=(Ybus, Yf, Cg, Cf, Ct, Sd, slack, no_slack, Yt, from_idx, to_idx, Va_max,
                                       Va_min, Vm_max, Vm_min, Pg_max, Pg_min, Qg_max, Qg_min, c0, c1, c2, Sbase, rates),
                                  verbose=verbose)

    vm, va, Pg, Qg = x2var(x, n_vm=nbus, n_va=nbus, n_P=ngen, n_Q=ngen)

    lam_p, lam_q = lam[:nbus], lam[nbus:2*nbus]

    df_bus = pd.DataFrame(data={'Vm (p.u.)': vm, 'Va (rad)': va,
                                'dual price (€/MW)': lam_p, 'dual price (€/MVAr)': lam_q})
    df_gen = pd.DataFrame(data={'P (MW)': Pg * nc.Sbase, 'Q (MVAr)': Qg * nc.Sbase})

    if verbose>0:
        print()
        print("Bus:\n", df_bus)
        print("Gen:\n", df_gen)
        print("Error", error)

    return x


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
    new_directory = os.path.abspath(os.path.join(cwd, '..', '..', '..', '..', '..'))
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
    new_directory = os.path.abspath(os.path.join(cwd, '..', '..', '..', '..', '..'))

    file_path = os.path.join(new_directory, 'Grids_and_profiles', 'grids', 'case14.m')

    grid = gce.FileOpen(file_path).open()
    nc = gce.compile_numerical_circuit_at(grid)
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR)
    ac_optimal_power_flow(nc=nc, pf_options=pf_options)
    return

if __name__ == '__main__':
    # example_3bus_acopf()
    # linn5bus_example()
    # two_grids_of_3bus()
    # case9()
    case14()
