# GridCal Helm Formulation Tests - 25/04/2020
# Andre Lazaro Souza

# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.

# AUTHORS: Josep Fanals Batllori and Santiago Peñate Vera
# CONTACT:  u1946589@campus.udg.edu and santiago.penate.vera@gmail.com
# thanks to Llorenç Fanals Batllori for his help at coding
import pandas as pd
import numpy as np
import numba as nb
import time
from warnings import warn
from scipy.sparse import csc_matrix, coo_matrix
from scipy.sparse import hstack as hs, vstack as vs
from scipy.sparse.linalg import spsolve, factorized


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
    Tiny = np.finfo(complex).min
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


@nb.njit("(c16[:])(i8, c16[:, :], f8)", cache=True)
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

    complex_type = nb.complex128

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


@nb.njit("(c16[:])(c16[:, :], c16[:, :], i8, c16[:])", cache=True)
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
    sigmes = np.zeros(nbus, dtype=complex_type)

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

        sigmes[d] = np.sum(lhs[M:]) / (np.sum(lhs[:M]) + 1)

    return sigmes


@nb.njit("(c16[:])(c16[:, :], c16[:, :], i8, i8[:])", cache=True)
def conv1(A, B, c, indices):
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


@nb.njit("(c16[:])(c16[:, :], c16[:, :], i8, i8[:])", cache=True)
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


@nb.njit("(c16[:])(c16[:, :], c16[:, :], i8, i8[:])", cache=True)
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


def helm_coefficients_josep(Yseries, V0, S0, Ysh0, pq, pv, sl, pqpv, tolerance=1e-6, max_coeff=30, verbose=False):
    """
    Holomorphic Embedding LoadFlow Method as formulated by Josep Fanals Batllori in 2020
    
    (----Without Slack Embedding and other tweaks----) 
                                                                                 
    THis function just returns the coefficients for further usage in other routines
    :param Yseries: Admittance matrix of the series elements
    :param V0: vector of specified voltages
    :param S0: vector of specified power
    :param Ysh0: vector of shunt admittances (including the shunts of the branches)
    :param pq: list of pq nodes
    :param pv: list of pv nodes
    :param sl: list of slack nodes
    :param pqpv: sorted list of pq and pv nodes
    :param tolerance: target error (or tolerance)
    :param max_coeff: maximum number of coefficients
    :param verbose: print intermediate information
    :return: U, X, Q, iterations
    """

    npqpv = len(pqpv)
    npv = len(pv)
    nsl = len(sl)
    n = Yseries.shape[0]

    # --------------------------- PREPARING IMPLEMENTATION -------------------------------------------------------------
    U = np.zeros((max_coeff, npqpv), dtype=complex)  # voltages
    U_re = np.zeros((max_coeff, npqpv), dtype=float)  # real part of voltages
    U_im = np.zeros((max_coeff, npqpv), dtype=float)  # imaginary part of voltages
    X = np.zeros((max_coeff, npqpv), dtype=complex)  # compute X=1/conj(U)
    X_re = np.zeros((max_coeff, npqpv), dtype=float)  # real part of X
    X_im = np.zeros((max_coeff, npqpv), dtype=float)  # imaginary part of X
    Q = np.zeros((max_coeff, npqpv), dtype=complex)  # unknown reactive powers
    Vm0 = np.abs(V0)
    vec_W = Vm0 * Vm0

    if n < 2:
        return U, X, Q, 0

    if verbose:
        print('Yseries')
        print(Yseries.toarray())
        df = pd.DataFrame(data=np.c_[Ysh0.imag, S0.real, S0.imag, Vm0],
                          columns=['Ysh', 'P0', 'Q0', 'V0'])
        print(df)

    Yred = Yseries[np.ix_(pqpv, pqpv)]  # admittance matrix without slack buses
    Yslack = -Yseries[np.ix_(pqpv, sl)]  # yes, it is the negative of this
    G = np.real(Yred)  # real parts of Yij
    B = np.imag(Yred)  # imaginary parts of Yij
    vec_P = S0.real[pqpv]
    vec_Q = S0.imag[pqpv]
    Vslack = V0[sl]
    Ysh = -Ysh0[pqpv]

    # indices 0 based in the internal scheme
    nsl_counted = np.zeros(n, dtype=int)
    compt = 0
    for i in range(n):
        if i in sl:
            compt += 1
        nsl_counted[i] = compt

    pq_ = pq - nsl_counted[pq]
    pv_ = pv - nsl_counted[pv]
    #pqpv_ = np.sort(np.r_[pq_, pv_])
    pqpv_ = np.arange(0,npqpv,dtype=np.int64)

    # .......................CALCULATION OF TERMS [0] ------------------------------------------------------------------

    #if nsl > 1:
    #    U[0, :] = spsolve(Yred, Yslack.sum(axis=1))
    #else:
    #    U[0, :] = spsolve(Yred, Yslack)
    U[0, :] = spsolve(Yred, Yslack * Vslack)

    X[0, :] = 1 / np.conj(U[0, :])
    U_re[0, :] = U[0, :].real
    U_im[0, :] = U[0, :].imag
    X_re[0, :] = X[0, :].real
    X_im[0, :] = X[0, :].imag

    # .......................CALCULATION OF TERMS [1] ------------------------------------------------------------------
    valor = np.zeros(npqpv, dtype=complex)

    # get the current injections that appear due to the slack buses reduction
    #I_inj_slack = Yslack[pqpv_, :] * Vslack

    #valor[pq_] = I_inj_slack[pq_] - Yslack[pq_].sum(axis=1).A1 + (vec_P[pq_] - vec_Q[pq_] * 1j) * X[0, pq_] + U[0, pq_] * Ysh[pq_]
    #valor[pv_] = I_inj_slack[pv_] - Yslack[pv_].sum(axis=1).A1 + (vec_P[pv_]) * X[0, pv_] + U[0, pv_] * Ysh[pv_]

    valor[pq_] = (vec_P[pq_] - vec_Q[pq_] * 1j) * X[0, pq_] + U[0, pq_] * Ysh[pq_]
    valor[pv_] = (vec_P[pv_]) * X[0, pv_] + U[0, pv_] * Ysh[pv_]

    # compose the right-hand side vector
    RHS = np.r_[valor.real,
                valor.imag,
                vec_W[pv] - (U[0, pv_] * U[0, pv_]).real]

    # Form the system matrix (MAT)
    Upv = U[0, pv_]
    Xpv = X[0, pv_]
    #VRE = coo_matrix((2 * Upv.real, (np.arange(npv), pv_)), shape=(npv, npqpv)).tocsc()
    #VIM = coo_matrix((2 * Upv.imag, (np.arange(npv), pv_)), shape=(npv, npqpv)).tocsc()
    VRE = coo_matrix((Upv.real, (np.arange(npv), pv_)), shape=(npv, npqpv)).tocsc()
    VIM = coo_matrix((Upv.imag, (np.arange(npv), pv_)), shape=(npv, npqpv)).tocsc()
    XIM = coo_matrix((-Xpv.imag, (pv_, np.arange(npv))), shape=(npqpv, npv)).tocsc()
    XRE = coo_matrix((Xpv.real, (pv_, np.arange(npv))), shape=(npqpv, npv)).tocsc()
    EMPTY = csc_matrix((npv, npv))

    #MAT = vs((hs((G,  -B,   XIM)),
    #          hs((B,   G,   XRE)),
    #          hs((VRE, VIM, EMPTY))), format='csc')
    MAT = vs((hs((G,  -B,   XIM), format='csr'),
              hs((B,   G,   XRE), format='csr'),
              hs((VRE, VIM, EMPTY), format='csr')), format='csc')

    if verbose:
        print('MAT')
        print(MAT.toarray())

    # factorize (only once)
    #MAT_LU = factorized(MAT.tocsc())
    MAT_LU = factorized(MAT)

    # solve
    LHS = MAT_LU(RHS)

    # update coefficients
    U[1, :] = LHS[:npqpv] + 1j * LHS[npqpv:2 * npqpv]
    Q[0, pv_] = LHS[2 * npqpv:]
    X[1, :] = -X[0, :] * np.conj(U[1, :]) / np.conj(U[0, :])

    # .......................CALCULATION OF TERMS [>=2] ----------------------------------------------------------------
    iter_ = 1
    range_pqpv = np.arange(npqpv, dtype=np.int64)
    for c in range(2, max_coeff):  # c defines the current depth

        valor[pq_] = (vec_P[pq_] - vec_Q[pq_] * 1j) * X[c - 1, pq_] + U[c - 1, pq_] * Ysh[pq_]
        valor[pv_] = conv2(X, Q, c, pv_) * -1j + U[c - 1, pv_] * Ysh[pv_] + X[c - 1, pv_] * vec_P[pv_]

        RHS = np.r_[valor.real,
                    valor.imag,
                    -aaux_conv3(U, c, pv_)]
                    #-aux_conv3(U[:,pv_], c, npv)]
                    #-conv3(U, U, c, pv_).real]

        LHS = MAT_LU(RHS)

        # update voltage coefficients
        U[c, :] = LHS[:npqpv] + 1j * LHS[npqpv:2 * npqpv]

        # update reactive power
        Q[c - 1, pv_] = LHS[2 * npqpv:]

        # update voltage inverse coefficients
        X[c, range_pqpv] = -conv1(U, X, c, range_pqpv) / np.conj(U[0, range_pqpv])

        iter_ += 1

    return U, X, Q, iter_


def helm_josep(Ybus, Yseries, V0, S0, Ysh0, pq, pv, sl, pqpv, tolerance=1e-6, max_coeff=30, use_pade=True,
               verbose=False):
    """
    Holomorphic Embedding LoadFlow Method as formulated by Josep Fanals Batllori in 2020
    
    (----Without Slack Embedding and other tweaks----) 
    
    :param Ybus: Complete admittance matrix
    :param Yseries: Admittance matrix of the series elements
    :param V0: vector of specified voltages
    :param S0: vector of specified power
    :param Ysh0: vector of shunt admittances (including the shunts of the branches)
    :param pq: list of pq nodes
    :param pv: list of pv nodes
    :param sl: list of slack nodes
    :param pqpv: sorted list of pq and pv nodes
    :param tolerance: target error (or tolerance)
    :param max_coeff: maximum number of coefficients
    :param use_pade: Use the Padè approximation? otherwise a simple summation is done
    :param verbose: print intermediate information
    :return: V, converged, norm_f, Scalc, iter_, elapsed
    """

    start_time = time.time()

    # compute the series of coefficients
    U, X, Q, iter_ = helm_coefficients_josep(Yseries, V0, S0, Ysh0, pq, pv, sl, pqpv,
                                             tolerance=tolerance, max_coeff=max_coeff, verbose=verbose)

    # --------------------------- RESULTS COMPOSITION ------------------------------------------------------------------
    if verbose:
        print('V coefficients')
        print(U)

    # compute the final voltage vector
    V = V0.copy()
    if use_pade:
        try:
            V[pqpv] = pade4all(max_coeff - 1, U, 1)
        except:
            warn('Padè failed :(, using coefficients summation')
            V[pqpv] = U.sum(axis=0)
    else:
        V[pqpv] = U.sum(axis=0)

    # compute power mismatch
    Scalc = V * np.conj(Ybus * V)
    dP = np.abs(S0[pqpv].real - Scalc[pqpv].real)
    dQ = np.abs(S0[pq].imag - Scalc[pq].imag)
    norm_f = np.linalg.norm(np.r_[dP, dQ], np.inf)  # same as max(abs())

    # check convergence
    converged = norm_f < tolerance

    elapsed = time.time() - start_time

    return V, converged, norm_f, Scalc, iter_, elapsed


@nb.njit("(f8[:])(c16[:, :], i8, i8)", cache=True)  # Input argument types
def aux_conv3(A, c, b):                 # Function with Numba Parallelization
    """
    Performs the convolution of A and A* divided by 2 (vectorized)
    :param A: coefficients matrix 1 (orders, selected buses)
    :param b: number of selected buses
    :param c: last order of the coefficients in while loop
    :param indices: bus indices array
    :return: Array with the convolution for the buses given by "indices"
    """

    # To remember: Python indexing doesn't support float

    is_even = c % 2 == 0

    d = (c + 1) // 2

    suma_xy = np.zeros(b, dtype=nb.complex128)
    
    for m in range(1, d):
        suma_xy += A[m, :] * np.conj(A[c-m, :])

    if is_even:
        suma_xy += 0.5 * A[d, :] * np.conj(A[d, :])

    return suma_xy.real


@nb.njit("(f8[:])(c16[:, :], i8, i8[:])", cache=True)
def aaux_conv3(A, c, b):
    """
    Performs the convolution of A and A* divided by 2 (enumerate-for-loop)
    :param A: coefficients matrix 1 (orders, buses)
    :param b: bus indices array
    :param c: last order of the coefficients in while loop
    :param indices: bus indices array
    :return: Array with the convolution for the buses given by "indices"
    """

    is_even = c % 2 == 0

    d = (c + 1) // 2

    suma_xy = np.zeros(len(b), dtype=nb.complex128)
    
    for m in range(1, d):                                # for m = 1:(d-1)     # | -> RANGE FOR
        for i, k in enumerate(b):                        #   i = 0;            # | -----
            suma_xy[i] += A[m, k] * np.conj(A[c-m, k])   #   for k = indices   # | -> ENUMERATE FOR
                                                         #      i = i + 1;     # | -----
    if is_even:
        for i, k in enumerate(b):
            suma_xy[i] += 0.5 * A[d, k] * np.conj(A[d, k])

    return suma_xy.real


@nb.njit("(f8[:])(c16[:, :], c16[:, :], i8, i8[:])", cache=True)
def conv4(A, B, n, idx):
    """
    Performs the convolution of A and B where B = A* divided by 2 (enumerate-for-loop)
    :param A: Coefficients matrix 1 (orders, buses)
    :param B: Coefficients matrix 2 (orders, buses)
    :param n: last order of the coefficients in while loop
    :param idx: bus indices array
    :return: Array with the convolution for the buses given by "idx"
    """

    is_even = n % 2 == 0

    nn = (n + 1) // 2

    sum_xy = np.zeros(len(idx), dtype=nb.complex128)
    
    for m in range(1, nn):
        for i, k in enumerate(idx):
            sum_xy[i] += A[m, k] * B[n-m, k]

    if is_even:
        for i, k in enumerate(idx):
            sum_xy[i] += 0.5 * A[nn, k] * B[nn, k]

    return sum_xy.real


@nb.njit("(f8[:])(c16[:, :], c16[:, :], i8, i8[:])", cache=True)
def aux_conv4(A, B, n, idx):
    """
    Performs the convolution of A and B where B = A* divided by 2 (enumerate-for-loop)
    :param A: Coefficients matrix 1 (orders, buses)
    :param B: Coefficients matrix 2 (orders, buses)
    :param n: last order of the coefficients in while loop
    :param idx: bus indices array
    :return: Array with the convolution for the buses given by "idx"
    """
    suma = np.zeros(len(idx), dtype=nb.complex128)
    
    for m in range(1, n):
        for i, k in enumerate(idx):
            suma[i] += A[m, k] * B[n-m, k]

    return 0.5 * suma.real


@nb.njit("(f8[:])(c16[:, :], c16[:, :], i8, i8[:])", cache=True)
def conv5(A, B, n, idx):
    
    """
    Performs the convolution of A and B where B = A* (enumerate-for-loop)
    :param A: Coefficients matrix 1 (orders, buses)
    :param B: Coefficients matrix 2 (orders, buses)
    :param n: last order of the coefficients in while loop
    :param idx: bus indices array
    :return: Array with the convolution for the buses given by "idx"
    """

    is_odd = n % 2 != 0

    nn = n // 2

    sum_xy = np.zeros(len(idx), dtype=nb.complex128)
    
    for m in range(0, nn):
        for i, k in enumerate(idx):
            sum_xy[i] += A[m, k] * B[n-1-m, k]

    if is_odd:
        for i, k in enumerate(idx):
            sum_xy[i] += 0.5 * A[nn, k] * B[nn, k]

    return 2 * sum_xy.real


@nb.njit("(f8[:])(c16[:, :], c16[:, :], i8, i8[:])", cache=True)
def aux_conv5(A, B, n, idx):
    """
    Performs the convolution of A and B where B = A* (enumerate-for-loop)
    :param A: Coefficients matrix 1 (orders, buses)
    :param B: Coefficients matrix 2 (orders, buses)
    :param c: last order of the coefficients in while loop
    :param indices: bus indices array
    :return: Array with the convolution for the buses given by "indices"
    """
    suma = np.zeros(len(idx), dtype=nb.complex128)
    
    for m in range(0, n):
        for i, k in enumerate(idx):
            suma[i] += A[m, k] * B[n-1-m, k]

    return suma.real


def conv6(U, conjU, Yrr, nb, n):
    
    suma = np.zeros(nb,dtype=np.complex128)
    
    for m in range(1,n):
            suma += conjU[m,:] * ( Yrr * U[n-m,:] )
            
    return suma


def helm_coefficients_andre(Yseries, V0, S0, Ysh0, pq, pv, sl, pqpv, tolerance=1e-6, max_coeff=30, verbose=False):
    """
    Holomorphic Embedding LoadFlow Method as formulated by Josep Fanals Batllori in 2020
    
    (----Reformulation to avoid Qk[n], Wk[n] calculation----)
    
    This function just returns the coefficients for further usage in other routines
    :param Yseries: Admittance matrix of the series elements
    :param V0: vector of specified voltages (complex)
    :param S0: vector of specified power (complex)
    :param Ysh0: vector of shunt admittances (including the shunts of the branches)
    :param pq: list of pq nodes
    :param pv: list of pv nodes
    :param sl: list of slack nodes
    :param pqpv: sorted list of pq and pv nodes
    :param tolerance: target error (or tolerance)
    :param max_coeff: maximum number of coefficients
    :param verbose: print intermediate information
    :return: U, "iterations"
    """

    npqpv = len(pqpv)     # number of non-slack buses
    npq = len(pq)         # number of pq buses
    npv = len(pv)         # number of pv buses
    nsl = len(sl)         # number of slack buses
    n = Yseries.shape[0]  # number of buses; size(Yseries,n) = Yseries.shape[n-1]; size(Yseries) = Yseries.shape;

    # --------------------------- PREPARING IMPLEMENTATION -------------------------------------------------------------
    
    U = np.zeros((max_coeff, npqpv), dtype=complex, order='C')  # voltage series coefficients
    conjU = np.zeros((max_coeff, npqpv), dtype=complex, order='C')  # conjugate voltage series coefficients
    Vsp  = np.abs(V0[pqpv])  # Specified voltage magnitude for PV-Buses
    Vsp_2 = Vsp * Vsp  # Specified voltage magnitude for PV-Buses Squared

    if n < 2:
        return U, 0

    if verbose:
        print('Yseries')
        print(Yseries.toarray())
        df = pd.DataFrame(data=np.c_[Ysh0.imag,S0.real,S0.imag,np.abs(V0)],
                          columns=['Ysh', 'P0', 'Q0', 'V0'])
        print(df)

    Yrr = Yseries[np.ix_(pqpv, pqpv)]  # Y_RED-RED; Yseries(pqpv,pqpv)
    Yrs = Yseries[np.ix_(pqpv, sl)]    # Y_RED-SLK
    Vs = V0[sl]                        # V_SLK
    Isl = Yrs * Vs                     # I_SLK
    Ssp = S0[pqpv]                     # Specified apparent power (Active for PQ and PV; Reactive for PQ)
    Ysh = Ysh0[pqpv]                   # Y_RED

    # indices 0 based in the internal scheme
    nsl_counted = np.zeros(n, dtype=int)
    compt = 0
    for i in range(n):        
        if i in sl:           
            compt += 1        
        nsl_counted[i] = compt

    pq_ = pq - nsl_counted[pq]
    pv_ = pv - nsl_counted[pv]
    pqpv_ = np.arange(0,npqpv,dtype=np.int64)

    # .......................CALCULATION OF TERMS [0] ------------------------------------------------------------------

    U[0, :] = spsolve(Yrr, -Isl)

    conjU[0, :] = np.conj(U[0, :])

    # .......................LINEAR SYSTEM MATRIX (MAT) ---------------------------------------------------------------- 

    YV = Yrr.multiply(conjU[0, :].reshape(npqpv, 1))
    YV = YV.tocsc()

    # | Re{YxconjV} -Im{YxconjV} | * |LHS_ReU [PQ,PV]|  = |RHS_P [PQ,PV]|
    # | Im{YxconjV}  Re{YxconjV} |   |LHS_ImU [PQ,PV]|    |RHS_Q [PQ]   |
    # | Re{V}              Im{V} |                        |RHS_V [PV]   |
    
    ReYVp = YV.real
    ImYVp = YV.imag
    ReYVq = ReYVp[np.ix_(pq_, pqpv_)]
    ImYVq = ImYVp[np.ix_(pq_, pqpv_)]
    ReV = coo_matrix((U[0, pv_].real, (np.arange(0, npv, dtype=np.int64), pv_)), shape=(npv, npqpv)).tocsc()
    ImV = coo_matrix((U[0, pv_].imag, (np.arange(0, npv, dtype=np.int64), pv_)), shape=(npv, npqpv)).tocsc()

    # sparse matrix concatenation
    MAT = vs((hs((ReYVp, -ImYVp), format='csr'),
              hs((ImYVq, ReYVq), format='csr'),
              hs((ReV  ,   ImV), format='csr')), format='csc')

    if verbose:
        print('MAT')
        print(MAT.toarray())

    # factorize (only once)
    MAT_LU = factorized(MAT)

    # .......................CALCULATION OF TERMS [>=1] ----------------------------------------------------------------

    for c in range(1, max_coeff):  # max_coeff_order

        if c == 1:
            UconjU   = U[0, :] * conjU[0, :]
            UconjU   = UconjU.real
            valor_v  = 0.5 * (Vsp_2[pv_] - UconjU[pv_])
            valor_pq = np.conj(Ssp) - Ysh * UconjU
        else:
            conjU[c-1, :] = np.conj(U[c-1, :])
            valor_v  = - conv4(U, conjU, c, pv_)
            valor_pq = - Ysh * conv5(U, conjU, c, pqpv_) - conv6(U, conjU, Yrr, npqpv, c)

        # compose the right-hand side vector
        RHS = np.r_[valor_pq.real, valor_pq[pq_].imag, valor_v]

        # solve
        LHS = MAT_LU(RHS)

        # update voltage coefficients
        U[c, :] = LHS[0:npqpv] + 1j * LHS[npqpv:2*npqpv]

    return U, max_coeff - 1


def helm_andre(Ybus, Yseries, V0, S0, Ysh0, pq, pv, sl, pqpv, tolerance=1e-6, max_coeff=30, use_pade=True,
               verbose=False):
    """
    Holomorphic Embedding LoadFlow Method as formulated by Josep Fanals Batllori in 2020
    
    (----Reformulation to avoid Qk[n], Wk[n] calculation----)
    
    :param Ybus: Complete admittance matrix
    :param Yseries: Admittance matrix of the series elements
    :param V0: vector of specified voltages
    :param S0: vector of specified power
    :param Ysh0: vector of shunt admittances (including the shunts of the branches)
    :param pq: list of pq nodes
    :param pv: list of pv nodes
    :param sl: list of slack nodes
    :param pqpv: sorted list of pq and pv nodes
    :param tolerance: target error (or tolerance)
    :param max_coeff: maximum number of coefficients
    :param use_pade: Use the Padè approximation? otherwise a simple summation is done
    :param verbose: print intermediate information
    :return: V, converged, norm_f, Scalc, iter_, elapsed
    """

    start_time = time.time()

    # compute the series of coefficients
    U, iter_ = helm_coefficients_andre(Yseries, V0, S0, Ysh0, pq, pv, sl, pqpv,
                                       tolerance=tolerance, max_coeff=max_coeff, verbose=verbose)

    # --------------------------- RESULTS COMPOSITION ------------------------------------------------------------------
    if verbose:
        print('V coefficients')
        print(U)

    # compute the final voltage vector
    V = V0.copy()
    if use_pade:
        try:
            V[pqpv] = pade4all(max_coeff - 1, U, 1)
        except:
            warn('Padè failed :(, using coefficients summation')
            V[pqpv] = U.sum(axis=0)
    else:
        V[pqpv] = U.sum(axis=0)

    # compute power mismatch
    Scalc = V * np.conj(Ybus * V)
    dP = np.abs(S0[pqpv].real - Scalc[pqpv].real)
    dQ = np.abs(S0[pq].imag - Scalc[pq].imag)
    norm_f = np.linalg.norm(np.r_[dP, dQ], np.inf)  # same as max(abs())

    # check convergence
    converged = norm_f < tolerance

    elapsed = time.time() - start_time

    return V, converged, norm_f, Scalc, iter_, elapsed


if __name__ == '__main__':
    from GridCal.Engine import FileOpen
    import pandas as pd

    np.set_printoptions(linewidth=2000, suppress=True)
    pd.set_option('display.max_rows', 500)
    pd.set_option('display.max_columns', 500)
    pd.set_option('display.width', 1000)

    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE39_1W.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE 14.xlsx'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/lynn5buspv.xlsx'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE 118.xlsx'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/1354 Pegase.xlsx'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/Pegase 2869.xlsx'
    #fname = 'helm_data1.gridcal'
    fname = "/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/Iwamoto's 11 Bus.gridcal"
    # fname = 'C:/Users/Lazaro/Downloads/Pegase 2869.xlsx'
    #fname = 'C:/Users/Lazaro/Downloads/IEEE 14_nopv.xlsx'
    #fname = 'C:/Users/Lazaro/Downloads/IEEE 14.xlsx'

    grid = FileOpen(fname).open()

    nc = grid.compile_snapshot()
    inputs = nc.compute()[0]  # pick the first island

    V, converged_, error, Scalc_, iter_, elapsed_ = helm_josep(Ybus=inputs.Ybus,
                                                               Yseries=inputs.Yseries,
                                                               V0=inputs.Vbus,
                                                               S0=inputs.Sbus,
                                                               Ysh0=inputs.Ysh,
                                                               pq=inputs.pq,
                                                               pv=inputs.pv,
                                                               sl=inputs.ref,
                                                               pqpv=inputs.pqpv,
                                                               tolerance=1e-6,
                                                               max_coeff=30,
                                                               use_pade=True,
                                                               verbose=False)
    Vm = np.abs(V)
    Va = np.angle(V)
    dP = np.abs(inputs.Sbus.real - Scalc_.real)
    dP[inputs.ref] = np.nan
    dQ = np.abs(inputs.Sbus.imag - Scalc_.imag)
    dQ[inputs.pv] = np.nan
    dQ[inputs.ref] = np.nan
    df = pd.DataFrame(data=np.c_[inputs.types, Vm, Va, np.abs(inputs.Vbus), dP, dQ],
                      columns=['Types', 'Vm', 'Va', 'Vset', 'P mismatch', 'Q mismatch'])
    # print(df)
    print('Josep (implicit slack):')
    print('Error', error)
    print('Elapsed', elapsed_)

    V, converged_, error, Scalc_, iter_, elapsed_ = helm_andre(Ybus=inputs.Ybus,
                                                               Yseries=inputs.Yseries,
                                                               V0=inputs.Vbus,
                                                               S0=inputs.Sbus,
                                                               Ysh0=inputs.Ysh,
                                                               pq=inputs.pq,
                                                               pv=inputs.pv,
                                                               sl=inputs.ref,
                                                               pqpv=inputs.pqpv,
                                                               tolerance=1e-6,
                                                               max_coeff=30,
                                                               use_pade=True,
                                                               verbose=False)
    Vm = np.abs(V)
    Va = np.angle(V)
    dP = np.abs(inputs.Sbus.real - Scalc_.real)
    dP[inputs.ref] = np.nan
    dQ = np.abs(inputs.Sbus.imag - Scalc_.imag)
    dQ[inputs.pv] = np.nan
    dQ[inputs.ref] = np.nan
    df = pd.DataFrame(data=np.c_[inputs.types, Vm, Va, np.abs(inputs.Vbus), dP, dQ],
                      columns=['Types', 'Vm', 'Va', 'Vset', 'P mismatch', 'Q mismatch'])
    # print(df)
    print('Andre (explicit slack):')
    print('Error', error)
    print('Elapsed', elapsed_)
