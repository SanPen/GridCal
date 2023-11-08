# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
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

# AUTHORS: Josep Fanals Batllori and Santiago Peñate Vera
# CONTACT:  u1946589@campus.udg.edu and santiago.penate.vera@gmail.com
# thanks to Llorenç Fanals Batllori for his help at coding
import pandas as pd
import numpy as np
import numba as nb
from numba.np.linalg import solve_impl
import time
from warnings import warn
from scipy.sparse import csc_matrix, coo_matrix
from scipy.sparse import hstack as hs, vstack as vs
from scipy.sparse.linalg import spsolve, factorized
from GridCalEngine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
import GridCalEngine.Simulations.PowerFlow.NumericalMethods.common_functions as cf
from GridCalEngine.basic_structures import Logger


def epsilon(Sn, n, E):
    """
    Fast recursive Wynn's epsilon algorithm from:
        NONLINEAR SEQUENCE TRANSFORMATIONS FOR THE ACCELERATION OF CONVERGENCE
        AND THE SUMMATION OF DIVERGENT SERIES

        by Ernst Joachim Weniger
    Args:
        Sn: sum of coefficients
        n: order
        E: Coefficients structure copy that is modified in this algorithm

    Returns:

    """
    Zero = complex(0)
    One = complex(1)
    Tiny = np.finfo(complex).tiny  # np.finfo(complex).min
    Huge = np.finfo(complex).max

    E[n] = Sn

    if n == 0:
        estim = Sn
    else:
        AUX2 = Zero

        for j in range(n, 0, -1):  # range from n to 1 (both included)
            AUX1 = AUX2
            AUX2 = E[j - 1]
            DIFF = E[j] - AUX2

            if abs(DIFF) <= Tiny:
                E[j - 1] = Huge
            else:
                if DIFF == 0:
                    DIFF = Tiny
                E[j - 1] = AUX1 + One / DIFF

        if np.mod(n, 2) == 0:
            estim = E[0]
        else:
            estim = E[1]

    return estim, E


# @nb.njit("(c16[:])(i8, c16[:, :], f8)")
def pade4all(order, coeff_mat, s=1.0):
    """
    Computes the "order" Padè approximant of the coefficients at the approximation point s

    Arguments:
        coeff_mat: coefficient matrix (order, buses)
        order:  order of the series
        s: point of approximation (at 1 you get the voltage)

    Returns:
        Padè approximation at s for all the series
    """
    nbus = coeff_mat.shape[1]

    # complex_type = nb.complex128
    complex_type = np.complex128

    voltages = np.zeros(nbus, dtype=complex_type)

    nn = int(order / 2)
    L = nn
    M = nn

    for d in range(nbus):

        # formation of the linear system right hand side
        rhs = coeff_mat[L + 1:L + M + 1, d]

        # formation of the coefficients matrix
        C = np.zeros((L, M), dtype=complex_type)
        for i in range(L):
            k = i + 1
            C[i, :] = coeff_mat[L - M + k:L + k, d]

        # Obtaining of the b coefficients for orders greater than 0
        b = np.zeros(rhs.shape[0] + 1, dtype=complex_type)
        x = np.linalg.solve(C, -rhs)  # bn to b1
        b[0] = 1
        b[1:] = x[::-1]

        # Obtaining of the coefficients 'a'
        a = np.zeros(L + 1, dtype=complex_type)
        a[0] = coeff_mat[0, d]
        for i in range(L):
            val = complex_type(0)
            k = i + 1
            for j in range(k + 1):
                val += coeff_mat[k - j, d] * b[j]
            a[i + 1] = val

        # evaluation of the function for the value 's'
        p = complex_type(0)
        q = complex_type(0)
        for i in range(L + 1):
            p += a[i] * s ** i
            q += b[i] * s ** i

        voltages[d] = p / q

    return voltages


# @nb.njit("(c16[:])(c16[:, :], c16[:, :], i8, c16[:])")
@nb.njit(cache=True)
def sigma_function(coeff_matU, coeff_matX, order, V_slack):
    """

    :param coeff_matU: array with voltage coefficients
    :param coeff_matX: array with inverse conjugated voltage coefficients
    :param order: should be prof - 1
    :param V_slack: slack bus voltage vector. Must contain only 1 slack bus
    :return: sigma complex value
    """
    if len(V_slack) > 1:
        print('Sigma values may not be correct')
    V0 = V_slack[0]
    coeff_matU = coeff_matU / V0
    coeff_matX = coeff_matX / V0
    nbus = coeff_matU.shape[1]
    complex_type = nb.complex128
    # complex_type = complex
    sigmas = np.zeros(nbus, dtype=complex_type)

    if order % 2 == 0:
        M = int(order / 2) - 1
    else:
        M = int(order / 2)

    for d in range(nbus):
        a = coeff_matU[1:2 * M + 2, d]
        b = coeff_matX[0:2 * M + 1, d]
        C = np.zeros((2 * M + 1, 2 * M + 1), dtype=complex_type)

        for i in range(2 * M + 1):
            if i < M:
                C[1 + i:, i] = a[:2 * M - i]
            else:
                C[i - M:, i] = - b[:3 * M - i + 1]

        lhs = np.linalg.solve(C, -a)

        sigmas[d] = np.sum(lhs[M:]) / (np.sum(lhs[:M]) + 1)

    return sigmas


# @nb.njit("(c16[:])(c16[:, :], c16[:, :], i8, i8[:])")
@nb.njit(cache=True)
def conv1_old(A, B, c, indices):
    """
    Performs the convolution of A* and B
    :param A: Coefficients matrix 1 (orders, buses)
    :param B: Coefficients matrix 2 (orders, buses)
    :param c: order of the coefficients
    :param indices: bus indices array
    :return: Array with the convolution for the buses given by "indices"
    """
    suma = np.zeros(len(indices), dtype=nb.complex128)
    for k in range(1, c + 1):
        for i, d in enumerate(indices):
            suma[i] += np.conj(A[k, d]) * B[c - k, d]
    return suma


# @nb.njit("(c16[:])(c16[:, :], c16[:, :], i8)")
@nb.njit(cache=True)
def conv1(A, B, c):
    """
    Performs the convolution of A* and B
    :param A: Coefficients matrix 1 (orders, buses)
    :param B: Coefficients matrix 2 (orders, buses)
    :param c: order of the coefficients
    :param indices: bus indices array
    :return: Array with the convolution for the buses given by "indices"
    """
    suma = np.zeros(A.shape[1], dtype=nb.complex128)
    for k in range(1, c + 1):
        for i in range(A.shape[1]):
            suma[i] += np.conj(A[k, i]) * B[c - k, i]
    return suma


# @nb.njit("(c16[:])(c16[:, :], c16[:, :], i8, i8[:])")
@nb.njit(cache=True)
def conv2(A, B, c, indices):
    """
    Performs the convolution of A and B
    :param A: Coefficients matrix 1 (orders, buses)
    :param B: Coefficients matrix 2 (orders, buses)
    :param c: order of the coefficients
    :param indices: bus indices array
    :return: Array with the convolution for the buses given by "indices"
    """
    suma = np.zeros(len(indices), dtype=nb.complex128)
    for k in range(1, c):
        for i, d in enumerate(indices):
            suma[i] += A[k, d] * B[c - 1 - k, d]
    return suma


# @nb.njit("(c16[:])(c16[:, :], c16[:, :], i8, i8[:])")
@nb.njit(cache=True)
def conv3(A, B, c, indices):
    """
    Performs the convolution of A and B*
    :param A: Coefficients matrix 1 (orders, buses)
    :param B: Coefficients matrix 2 (orders, buses)
    :param c: order of the coefficients
    :param indices: bus indices array
    :return: Array with the convolution for the buses given by "indices"
    """
    suma = np.zeros(len(indices), dtype=nb.complex128)
    for k in range(1, c):
        for i, d in enumerate(indices):
            suma[i] += A[k, d] * np.conj(B[c - k, d])
    return suma


def helm_coefficients_josep(Ybus, Yseries, V0, S0, Ysh0, pq, pv, sl, pqpv, tolerance=1e-6, max_coeff=30, verbose=False,
                            logger: Logger = None):
    """
    Holomorphic Embedding LoadFlow Method as formulated by Josep Fanals Batllori in 2020
    THis function just returns the coefficients for further usage in other routines
    :param Yseries: Admittance matrix of the series elements
    :param V0: vector of specified voltages
    :param S0: vector of specified power
    :param Ysh0: vector of shunt admittances (including the shunts of the Branches)
    :param pq: list of pq nodes
    :param pv: list of pv nodes
    :param sl: list of slack nodes
    :param pqpv: sorted list of pq and pv nodes
    :param tolerance: target error (or tolerance)
    :param max_coeff: maximum number of coefficients
    :param verbose: print intermediate information
    :param logger: Logger object to store the debug info
    :return: U, X, Q, V, iterations
    """

    npqpv = len(pqpv)
    npv = len(pv)
    nsl = len(sl)
    n = Yseries.shape[0]

    # --------------------------- PREPARING IMPLEMENTATION -------------------------------------------------------------
    U = np.zeros((max_coeff + 1, npqpv), dtype=complex)  # voltages
    X = np.zeros((max_coeff + 1, npqpv), dtype=complex)  # compute X=1/conj(U)
    Q = np.zeros((max_coeff + 1, npqpv), dtype=complex)  # unknown reactive powers

    if n < 2:
        return U, X, Q, 0

    if verbose:
        logger.add_debug('Yseries', Yseries.toarray())

        df = pd.DataFrame(data=np.c_[Ysh0.imag, S0.real, S0.imag, np.abs(V0)],
                          columns=['Ysh', 'P0', 'Q0', 'V0'])
        logger.add_debug(df.to_string())

    # build the reduced system
    Yred = Yseries[np.ix_(pqpv, pqpv)]  # admittance matrix without slack buses
    Yslack = -Yseries[np.ix_(pqpv, sl)]  # yes, it is the negative of this
    G = Yred.real.copy()  # real parts of Yij
    B = Yred.imag.copy()  # imaginary parts of Yij
    vec_P = S0.real[pqpv]
    vec_Q = S0.imag[pqpv]
    Vslack = V0[sl]
    Ysh = Ysh0[pqpv]
    Vm0 = np.abs(V0[pqpv])
    vec_W = Vm0 * Vm0

    # indices 0 based in the internal scheme
    nsl_counted = np.zeros(n, dtype=int)
    compt = 0
    for i in range(n):
        if i in sl:
            compt += 1
        nsl_counted[i] = compt

    pq_ = pq - nsl_counted[pq]
    pv_ = pv - nsl_counted[pv]
    pqpv_ = np.sort(np.r_[pq_, pv_])

    # .......................CALCULATION OF TERMS [0] ------------------------------------------------------------------

    if nsl > 1:
        U[0, :] = spsolve(Yred, Yslack.sum(axis=1))
    else:
        U[0, :] = spsolve(Yred, Yslack)

    X[0, :] = 1 / np.conj(U[0, :])

    # .......................CALCULATION OF TERMS [1] ------------------------------------------------------------------
    valor = np.zeros(npqpv, dtype=complex)

    # get the current Injections that appear due to the slack buses reduction
    I_inj_slack = Yslack[pqpv_, :] * Vslack

    valor[pq_] = I_inj_slack[pq_] - Yslack[pq_].sum(axis=1).A1 + (vec_P[pq_] - vec_Q[pq_] * 1j) * X[0, pq_] - U[
        0, pq_] * Ysh[pq_]
    valor[pv_] = I_inj_slack[pv_] - Yslack[pv_].sum(axis=1).A1 + (vec_P[pv_]) * X[0, pv_] - U[0, pv_] * Ysh[pv_]

    # compose the right-hand side vector
    RHS = np.r_[valor.real,
    valor.imag,
    vec_W[pv_] - (U[0, pv_] * U[0, pv_]).real  # vec_W[pv_] - 1.0
    ]

    # Form the system matrix (MAT)
    Upv = U[0, pv_]
    Xpv = X[0, pv_]
    VRE = coo_matrix((2 * Upv.real, (np.arange(npv), pv_)), shape=(npv, npqpv)).tocsc()
    VIM = coo_matrix((2 * Upv.imag, (np.arange(npv), pv_)), shape=(npv, npqpv)).tocsc()
    XIM = coo_matrix((-Xpv.imag, (pv_, np.arange(npv))), shape=(npqpv, npv)).tocsc()
    XRE = coo_matrix((Xpv.real, (pv_, np.arange(npv))), shape=(npqpv, npv)).tocsc()
    EMPTY = csc_matrix((npv, npv))

    MAT = vs((hs((G, -B, XIM)),
              hs((B, G, XRE)),
              hs((VRE, VIM, EMPTY))), format='csc')

    if verbose:
        logger.add_debug("MAT", MAT.toarray())

    # factorize (only once)
    # MAT_LU = factorized(MAT.tocsc())

    # solve
    mat_factorized = factorized(MAT)
    LHS = mat_factorized(RHS)
    # LHS = spsolve(MAT, RHS)

    # update coefficients
    U[1, :] = LHS[:npqpv] + 1j * LHS[npqpv:2 * npqpv]
    Q[0, pv_] = LHS[2 * npqpv:]
    X[1, :] = -X[0, :] * np.conj(U[1, :]) / np.conj(U[0, :])

    # .......................CALCULATION OF TERMS [>=2] ----------------------------------------------------------------
    iter_ = 1
    c = 2
    converged = False
    V = np.empty(n, dtype=complex)
    V[sl] = V0[sl]
    V[pqpv] = U[:c, :].sum(axis=0)
    while c <= max_coeff and not converged:  # c defines the current depth

        valor[pq_] = (vec_P[pq_] - vec_Q[pq_] * 1j) * X[c - 1, pq_] - U[c - 1, pq_] * Ysh[pq_]
        valor[pv_] = -1j * conv2(X, Q, c, pv_) - U[c - 1, pv_] * Ysh[pv_] + X[c - 1, pv_] * vec_P[pv_]

        RHS = np.r_[valor.real,
        valor.imag,
        -conv3(U, U, c, pv_).real]

        # LHS = spsolve(MAT, RHS)
        LHS = mat_factorized(RHS)

        # update voltage coefficients
        U[c, :] = LHS[:npqpv] + 1j * LHS[npqpv:2 * npqpv]

        # update reactive power
        Q[c - 1, pv_] = LHS[2 * npqpv:]

        # update voltage inverse coefficients
        X[c, :] = -conv1(U, X, c) / np.conj(U[0, :])

        # compute power mismatch
        V[pqpv] += U[c, :]

        if V.real.max() < 10:
            Scalc = cf.compute_power(Ybus, V)
            norm_f = cf.compute_fx_error(cf.compute_fx(Scalc, S0, pqpv, pq))
            converged = (norm_f <= tolerance) and (c % 2)  # we want an odd amount of coefficients
        else:
            # completely erroneous
            break

        iter_ += 1
        c += 1

    return U, X, Q, V, iter_, converged


class HelmPreparation:

    def __init__(self, sys_mat_factorization, Uini, Xini, Yslack, Vslack,
                 vec_P, vec_Q, Ysh, vec_W, pq, pv, pqpv, sl,
                 npqpv, nbus):
        self.sys_mat_factorization = sys_mat_factorization
        self.Uini = Uini
        self.Xini = Xini
        self.Yslack = Yslack
        self.Vslack = Vslack
        self.vec_P = vec_P
        self.vec_Q = vec_Q
        self.Ysh = Ysh
        self.vec_W = vec_W
        self.pq = pq
        self.pv = pv
        self.sl = sl
        self.pqpv = pqpv
        self.npqpv = npqpv
        self.nbus = nbus


def helm_preparation_dY(Yseries, V0, S0, Ysh0, pq, pv, sl, pqpv, verbose=False,
                        logger: Logger = None) -> HelmPreparation:
    """
    This function returns the constant objects to run many HELM simulations

    Based on the paper: Novel AC Distribution Factor for Efficient Outage Analysis
                        Rui Yao, Senior Member, IEEE, and Feng Qiu, Senior Member, IEEE

    :param Yseries: Admittance matrix of the series elements
    :param V0: vector of specified voltages
    :param S0: vector of specified power
    :param Ysh0: vector of shunt admittances (including the shunts of the Branches)
    :param pq: list of pq nodes
    :param pv: list of pv nodes
    :param sl: list of slack nodes
    :param pqpv: sorted list of pq and pv nodes
    :param verbose: print intermediate information
    :param logger: Logger object to store the debug info
    :return: U, X, Q, V, iterations
    """

    npqpv = len(pqpv)
    npv = len(pv)
    nsl = len(sl)
    nbus = Yseries.shape[0]

    # --------------------------- PREPARING IMPLEMENTATION -------------------------------------------------------------

    # build the reduced system
    Yred = Yseries[np.ix_(pqpv, pqpv)]  # admittance matrix without slack buses
    Yslack = -Yseries[np.ix_(pqpv, sl)]  # yes, it is the negative of this
    G = Yred.real.copy()  # real parts of Yij
    B = Yred.imag.copy()  # imaginary parts of Yij
    vec_P = S0.real[pqpv]
    vec_Q = S0.imag[pqpv]
    Vslack = V0[sl]
    Ysh = Ysh0[pqpv]
    Vm0 = np.abs(V0[pqpv])
    vec_W = Vm0 * Vm0

    # indices 0 based in the internal scheme
    nsl_counted = np.zeros(nbus, dtype=int)
    compt = 0
    for i in range(nbus):
        if i in sl:
            compt += 1
        nsl_counted[i] = compt

    pq_ = pq - nsl_counted[pq]
    pv_ = pv - nsl_counted[pv]
    pqpv_ = np.sort(np.r_[pq_, pv_])

    # .......................CALCULATION OF TERMS [0] ------------------------------------------------------------------
    if nsl > 1:
        Uini = spsolve(Yred, Yslack.sum(axis=1))
    else:
        Uini = spsolve(Yred, Yslack)

    Xini = 1 / Uini

    # .......................CALCULATION OF THE MATRIX -----------------------------------------------------------------
    Upv = Uini[pv_]
    Xpv = Xini[pv_]
    VRE = coo_matrix((2 * Upv.real, (np.arange(npv), pv_)), shape=(npv, npqpv)).tocsc()
    VIM = coo_matrix((2 * Upv.imag, (np.arange(npv), pv_)), shape=(npv, npqpv)).tocsc()
    XIM = coo_matrix((-Xpv.imag, (pv_, np.arange(npv))), shape=(npqpv, npv)).tocsc()
    XRE = coo_matrix((Xpv.real, (pv_, np.arange(npv))), shape=(npqpv, npv)).tocsc()
    EMPTY = csc_matrix((npv, npv))

    MAT = vs((hs((G, -B, XIM)),
              hs((B, G, XRE)),
              hs((VRE, VIM, EMPTY))), format='csc')

    if verbose:
        logger.add_debug("MAT", MAT.toarray())

    # solve
    mat_factorized = factorized(MAT)

    return HelmPreparation(mat_factorized, Uini, Xini, Yslack, Vslack, vec_P, vec_Q, Ysh, vec_W,
                           pq_, pv_, pqpv_, sl, npqpv, nbus)


def helm_coefficients_dY(dY, sys_mat_factorization, Uini, Xini, Yslack, Ysh, Ybus, vec_P, vec_Q, S0,
                         vec_W, V0, Vslack, pq, pv, pqpv, npqpv, nbus, sl,
                         tolerance=1e-6, max_coeff=10):
    """
    Holomorphic Embedding LoadFlow Method as formulated by Josep Fanals Batllori in 2020
    This function just returns the coefficients for further usage in other routines

    Based on the paper: Novel AC Distribution Factor for Efficient Outage Analysis
                        Rui Yao, Senior Member, IEEE, and Feng Qiu, Senior Member, IEEE

    :param dY:
    :param sys_mat_factorization: factorized HELM system matrix
    :param Uini:
    :param Xini:
    :param Yslack:
    :param Ysh:
    :param Ybus:
    :param vec_P:
    :param vec_Q:
    :param S0: vector of specified power
    :param vec_W:
    :param V0: vector of specified voltages
    :param Vslack:
    :param pq: reduced scheme list of pq nodes
    :param pv: reduced scheme list of pv nodes
    :param pqpv: reduced scheme list of pq|pv nodes
    :param npqpv: number of pq and pv nodes
    :param nbus: number of nodes
    :param pqpv: sorted list of pq and pv nodes
    :param pq:list of pq nodes
    :param sl: list of slack nodes
    :param tolerance: target error (or tolerance)
    :param max_coeff: maximum number of coefficients
    :return: U, V, iter_, norm_f
    """

    AYred = dY[np.ix_(pqpv, pqpv)]  # difference admittance matrix without slack buses

    # --------------------------- PREPARING IMPLEMENTATION -------------------------------------------------------------
    U = np.zeros((max_coeff + 1, npqpv), dtype=complex)  # voltages
    X = np.zeros((max_coeff + 1, npqpv), dtype=complex)  # compute X=1/conj(U)
    Q = np.zeros((max_coeff + 1, npqpv), dtype=complex)  # unknown reactive powers

    # .......................CALCULATION OF TERMS [0] ------------------------------------------------------------------
    U[0, :] = Uini
    X[0, :] = Xini

    # .......................CALCULATION OF TERMS [1] ------------------------------------------------------------------
    dval = np.zeros(npqpv, dtype=complex)

    # get the current Injections that appear due to the slack buses reduction
    I_inj_slack = Yslack[pqpv, :] * Vslack
    AIred = AYred @ U[0, :]

    Ysl_sum = Yslack.sum(axis=1).A1

    dval[pq] = I_inj_slack[pq] - Ysl_sum[pq] + (vec_P[pq] - vec_Q[pq] * 1j) * X[0, pq] - U[0, pq] * Ysh[pq] - AIred[pq]
    dval[pv] = I_inj_slack[pv] - Ysl_sum[pv] + (vec_P[pv]) * X[0, pv] - U[0, pv] * Ysh[pv] - AIred[pv]

    # compose the right-hand side vector
    RHS = np.r_[dval.real, dval.imag, vec_W[pv] - (U[0, pv] * U[0, pv]).real]  # vec_W[pv_] - 1.0

    LHS = sys_mat_factorization(RHS)

    # update coefficients
    U[1, :] = LHS[:npqpv] + 1j * LHS[npqpv:2 * npqpv]
    Q[0, pv] = LHS[2 * npqpv:]
    X[1, :] = -X[0, :] * np.conj(U[1, :]) / np.conj(U[0, :])

    # .......................CALCULATION OF TERMS [>=2] ----------------------------------------------------------------
    iter_ = 1
    c = 2
    converged = False
    V = np.empty(nbus, dtype=complex)
    V[sl] = V0[sl]
    V[pqpv] = U[:c, :].sum(axis=0)
    norm_f = 0.0

    while c <= max_coeff and not converged:  # c defines the current depth

        AIred = AYred * U[c - 1, :]

        dval[pq] = (vec_P[pq] - vec_Q[pq] * 1j) * X[c - 1, pq] - U[c - 1, pq] * Ysh[pq] - AIred[pq]
        dval[pv] = -1j * conv2(X, Q, c, pv) - U[c - 1, pv] * Ysh[pv] + X[c - 1, pv] * vec_P[pv] - AIred[pv]

        RHS = np.r_[dval.real, dval.imag, -conv3(U, U, c, pv).real]

        # LHS = spsolve(MAT, RHS)
        LHS = sys_mat_factorization(RHS)

        # update 
        U[c, :] = LHS[:npqpv] + 1j * LHS[npqpv:2 * npqpv]
        Q[c - 1, pv] = LHS[2 * npqpv:]
        X[c, :] = -conv1(U, X, c) / np.conj(U[0, :])

        # compute power mismatch
        V[pqpv] += U[c, :]

        if V.real.max() < 10:
            Scalc = cf.compute_power(Ybus, V)
            norm_f = cf.compute_fx_error(cf.compute_fx(Scalc, S0, pqpv, pq))
            converged = (norm_f <= tolerance) and (c % 2)  # we want an odd amount of coefficients
        else:
            # completely erroneous
            break

        iter_ += 1
        c += 1

    return U, V, iter_, norm_f


def helm_josep(Ybus, Yseries, V0, S0, Ysh0, pq, pv, sl, pqpv, tolerance=1e-6, max_coefficients=30, use_pade=True,
               verbose=False, logger: Logger = None) -> NumericPowerFlowResults:
    """
    Holomorphic Embedding LoadFlow Method as formulated by Josep Fanals Batllori in 2020
    :param Ybus: Complete admittance matrix
    :param Yseries: Admittance matrix of the series elements
    :param V0: vector of specified voltages
    :param S0: vector of specified power
    :param Ysh0: vector of shunt admittances (including the shunt "legs" of the pi Branches)
    :param pq: list of pq nodes
    :param pv: list of pv nodes
    :param sl: list of slack nodes
    :param pqpv: sorted list of pq and pv nodes
    :param tolerance: target error (or tolerance)
    :param max_coefficients: maximum number of coefficients
    :param use_pade: Use the Padè approximation? otherwise, a simple summation is done
    :param verbose: print intermediate information
    :param logger: Logger object to store the debug info
    :return: V, converged, norm_f, Scalc, iter_, elapsed
    """

    start_time = time.time()

    n = Yseries.shape[0]
    if n < 2:
        # return NumericPowerFlowResults(V0, True, 0.0, S0, None, None, None, None, None, None, 0, 0.0)
        return NumericPowerFlowResults(V=V0, converged=True, norm_f=0.0,
                                       Scalc=S0, ma=None, theta=None, Beq=None,
                                       Ybus=None, Yf=None, Yt=None,
                                       iterations=0, elapsed=0.0)

    # compute the series of coefficients
    U, X, Q, V, iter_, converged = helm_coefficients_josep(Ybus=Ybus,
                                                           Yseries=Yseries,
                                                           V0=V0,
                                                           S0=S0,
                                                           Ysh0=Ysh0,
                                                           pq=pq,
                                                           pv=pv,
                                                           sl=sl,
                                                           pqpv=pqpv,
                                                           tolerance=tolerance,
                                                           max_coeff=max_coefficients,
                                                           verbose=verbose,
                                                           logger=logger)

    # --------------------------- RESULTS COMPOSITION ------------------------------------------------------------------
    if verbose:
        logger.add_debug('V coefficients\n', U)

    # compute the final voltage vector
    if use_pade:
        V = V0.copy()
        try:
            V[pqpv] = pade4all(max_coefficients - 1, U, 1)
        except:
            warn('Padè failed :(, using coefficients summation')
            V[pqpv] = U.sum(axis=0)

    # compute power mismatch
    Scalc = cf.compute_power(Ybus, V)
    norm_f = cf.compute_fx_error(cf.compute_fx(Scalc, S0, pqpv, pq))

    # check convergence
    converged = norm_f < tolerance

    elapsed = time.time() - start_time

    # return NumericPowerFlowResults(V, converged, norm_f, Scalc, None, None, None, None, None, None, iter_, elapsed)
    return NumericPowerFlowResults(V=V, converged=converged, norm_f=norm_f,
                                   Scalc=Scalc, ma=None, theta=None, Beq=None,
                                   Ybus=None, Yf=None, Yt=None,
                                   iterations=iter_, elapsed=elapsed)
