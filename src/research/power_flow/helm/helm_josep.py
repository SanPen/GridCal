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
# CONTACT:  u1946589@campus.udg.edu, santiago.penate.vera@gmail.com
# thanks to Llorenç Fanals Batllori for his help at coding

# --------------------------- LIBRARIES
import numpy as np
import pandas as pd
import numba as nb
import time
from warnings import warn
from scipy.sparse import coo_matrix, csc_matrix
from scipy.sparse import hstack as hs, vstack as vs
from scipy.sparse.linalg import factorized, spsolve
from matplotlib import pyplot as plt

np.set_printoptions(linewidth=2000, edgeitems=1000)
pd.set_option('display.max_rows', 500)
pd.set_option('display.max_columns', 500)
pd.set_option('display.width', 1000)


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


@nb.njit("(c16[:])(i8, c16[:, :], f8)")
def pade4all(order, coeff_mat, s=1.0):
    """
    Computes the "order" Padè approximant of the coefficients at the approximation point s

    Arguments:
        coeff_mat: coefficient matrix (order, buses)
        order:  order of the series
        s: point of approximation

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


@nb.njit("(c16[:])(c16[:, :], c16[:, :], i8, c16[:])")
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


def sigma_distance(a, b):
    """
    Distance to the collapse in the sigma space

    The boundary curve is given by y = sqrt(1/4 + x)

    the distance is d = sqrt((x-a)^2 + (sqrt(1/4+ x) - b)^2)

    the derivative of this is d'=(2 (-a + x) + (-b + sqrt(1/4 + x))/sqrt(1/4 + x))/(2 sqrt((-a + x)^2 + (-b + sqrt(1/4 + x))^2))

    Making d'=0, and solving for x, we obtain:

    x1 = 1/12 (-64 a^3 + 48 a^2 + 12 sqrt(3) sqrt(-64 a^3 b^2 + 48 a^2 b^2 - 12 a b^2 + 108 b^4 + b^2) - 12 a + 216 b^2 + 1)^(1/3) - (-256 a^2 + 128 a - 16)/
         (192 (-64 a^3 + 48 a^2 + 12 sqrt(3) sqrt(-64 a^3 b^2 + 48 a^2 b^2 - 12 a b^2 + 108 b^4 + b^2) - 12 a + 216 b^2 + 1)^(1/3)) + 1/12 (8 a - 5)

    x2 = 1/12 (-64 a^3 + 48 a^2 + 12 sqrt(3) sqrt(-64 a^3 b^2 + 48 a^2 b^2 - 12 a b^2 + 108 b^4 + b^2) - 12 a + 216 b^2 + 1)^(1/3) - (-256 a^2 + 128 a - 16)/
         (192 (-64 a^3 + 48 a^2 + 12 sqrt(3) sqrt(-64 a^3 b^2 + 48 a^2 b^2 - 12 a b^2 + 108 b^4 + b^2) - 12 a + 216 b^2 + 1)^(1/3)) + 1/12 (8 a - 5)
    :param a: Sigma real
    :param b: Sigma imag
    :return: distance of the sigma point to the curve sqrt(0.25 + x)
    """

    t1 = (-64 * a**3
          + 48 * a**2
          + 12 * np.sqrt(3)*np.sqrt(-64 * a**3 * b**2
                                    + 48 * a**2 * b**2
                                    - 12 * a * b**2
                                    + 108 * b**4 + b**2)
          - 12 * a + 216 * b**2 + 1)**(1 / 3)

    x1 = 1 / 12 * t1 - (-256 * a**2 + 128*a - 16) / (192 * t1) + 1 / 12 * (8 * a - 5)
    return x1


@nb.njit("(c16[:])(c16[:, :], c16[:, :], i8, i8[:])")
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


@nb.njit("(c16[:])(c16[:, :], c16[:, :], i8, i8[:])")
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


@nb.njit("(c16[:])(c16[:, :], c16[:, :], i8, i8[:])")
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


def helm_coefficients_josep(Ybus, Yseries, V0, S0, Ysh0, pq, pv, sl, pqpv, tolerance=1e-6, max_coeff=30, verbose=False):
    """
    Holomorphic Embedding LoadFlow Method as formulated by Josep Fanals Batllori in 2020
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
    W = np.zeros((max_coeff, npqpv), dtype=complex)  # compute X=1/conj(U)
    Q = np.zeros((max_coeff, npqpv), dtype=complex)  # unknown reactive powers
    Vm0 = np.abs(V0)
    Vm2 = Vm0 * Vm0

    if n < 2:
        return U, W, Q, 0

    if verbose:
        print('Yseries')
        print(Yseries.toarray())
        df = pd.DataFrame(data=np.c_[Ysh0.imag, S0.real, S0.imag, Vm0],
                          columns=['Ysh', 'P0', 'Q0', 'V0'])
        print(df)

    Yred = Yseries[np.ix_(pqpv, pqpv)]  # admittance matrix without slack buses
    Yslack = -Yseries[np.ix_(pqpv, sl)]  # yes, it is the negative of this
    Yslack_vec = Yslack.sum(axis=1).A1
    G = np.real(Yred)  # real parts of Yij
    B = np.imag(Yred)  # imaginary parts of Yij
    P_red = S0.real[pqpv]
    Q_red = S0.imag[pqpv]
    Vslack = V0[sl]
    Ysh_red = Ysh0[pqpv]

    # indices 0 based in the internal scheme
    nsl_counted = np.zeros(n, dtype=int)
    compt = 0
    for i in range(n):
        if i in sl:
            compt += 1
        nsl_counted[i] = compt

    pq_ = pq - nsl_counted[pq]
    pv_ = pv - nsl_counted[pv]

    # .......................CALCULATION OF TERMS [0] ------------------------------------------------------------------

    U[0, :] = spsolve(Yred, Yslack_vec)
    W[0, :] = 1 / np.conj(U[0, :])

    # .......................CALCULATION OF TERMS [1] ------------------------------------------------------------------
    valor = np.zeros(npqpv, dtype=complex)

    # get the current injections that appear due to the slack buses reduction
    I_inj_slack = Yslack * Vslack

    valor[pq_] = I_inj_slack[pq_] - Yslack_vec[pq_] + (P_red[pq_] - Q_red[pq_] * 1j) * W[0, pq_] - U[0, pq_] * Ysh_red[pq_]
    valor[pv_] = I_inj_slack[pv_] - Yslack_vec[pv_] + P_red[pv_] * W[0, pv_] - U[0, pv_] * Ysh_red[pv_]

    # compose the right-hand side vector
    RHS = np.r_[valor.real,
                valor.imag,
                Vm2[pv] - (U[0, pv_] * U[0, pv_]).real]

    # Form the system matrix (MAT)
    Upv = U[0, pv_]
    Xpv = W[0, pv_]
    VRE = coo_matrix((2 * Upv.real, (np.arange(npv), pv_)), shape=(npv, npqpv)).tocsc()
    VIM = coo_matrix((2 * Upv.imag, (np.arange(npv), pv_)), shape=(npv, npqpv)).tocsc()
    XIM = coo_matrix((-Xpv.imag, (pv_, np.arange(npv))), shape=(npqpv, npv)).tocsc()
    XRE = coo_matrix((Xpv.real, (pv_, np.arange(npv))), shape=(npqpv, npv)).tocsc()
    EMPTY = csc_matrix((npv, npv))

    MAT = vs((hs((G,  -B,   XIM)),
              hs((B,   G,   XRE)),
              hs((VRE, VIM, EMPTY))), format='csc')

    if verbose:
        print('MAT')
        print(MAT.toarray())

    # factorize (only once)
    MAT_LU = factorized(MAT.tocsc())

    # solve
    LHS = MAT_LU(RHS)

    # update coefficients
    U[1, :] = LHS[:npqpv] + 1j * LHS[npqpv:2 * npqpv]
    Q[0, pv_] = LHS[2 * npqpv:]
    W[1, :] = -W[0, :] * np.conj(U[1, :]) / np.conj(U[0, :])

    # .......................CALCULATION OF TERMS [>=2] ----------------------------------------------------------------
    iter_ = 1
    range_pqpv = np.arange(npqpv, dtype=np.int64)
    V = V0.copy()
    c = 2
    converged = False
    norm_f = tolerance + 1.0  # any number that violates the convergence

    while c < max_coeff and not converged:  # c defines the current depth

        valor[pq_] = (P_red[pq_] - Q_red[pq_] * 1j) * W[c - 1, pq_] - U[c - 1, pq_] * Ysh_red[pq_]
        valor[pv_] = -1j * conv2(W, Q, c, pv_) - U[c - 1, pv_] * Ysh_red[pv_] + W[c - 1, pv_] * P_red[pv_]

        RHS = np.r_[valor.real,
                    valor.imag,
                    -conv3(U, U, c, pv_).real]

        LHS = MAT_LU(RHS)

        # update voltage coefficients
        U[c, :] = LHS[:npqpv] + 1j * LHS[npqpv:2 * npqpv]

        # update reactive power
        Q[c - 1, pv_] = LHS[2 * npqpv:]

        # update voltage inverse coefficients
        W[c, range_pqpv] = -conv1(U, W, c, range_pqpv) / np.conj(U[0, range_pqpv])

        # compute power mismatch
        if not np.mod(c, 2):  # check the mismatch every 4 iterations
            V[pqpv] = U.sum(axis=0)
            Scalc = V * np.conj(Ybus * V)
            dP = np.abs(S0[pqpv].real - Scalc[pqpv].real)
            dQ = np.abs(S0[pq].imag - Scalc[pq].imag)
            norm_f = np.linalg.norm(np.r_[dP, dQ], np.inf)  # same as max(abs())

            # check convergence
            converged = norm_f < tolerance
            print('mismatch check at c=', c)

        c += 1
        iter_ += 1

    return U, W, Q, iter_, norm_f


def helm_josep(Ybus, Yseries, V0, S0, Ysh0, pq, pv, sl, pqpv, tolerance=1e-6, max_coeff=30, use_pade=True,
               verbose=False):
    """
    Holomorphic Embedding LoadFlow Method as formulated by Josep Fanals Batllori in 2020
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
    U, X, Q, iter_, norm_f = helm_coefficients_josep(Ybus, Yseries, V0, S0, Ysh0, pq, pv, sl, pqpv,
                                                     tolerance=tolerance, max_coeff=max_coeff, verbose=verbose)

    # --------------------------- RESULTS COMPOSITION ------------------------------------------------------------------
    if verbose:
        print('V coefficients')
        print(U)

    # compute the final voltage vector
    V = V0.copy()
    if use_pade:
        try:
            V[pqpv] = pade4all(iter_, U, 1.0)
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


def test_voltage(grid):
    """
    Grid solution test
    :param grid: MultiCircuit instance
    :return: True/False
    """
    nc = grid.compile_snapshot()
    inputs = nc.compute()[0]  # pick the first island
    tolerance = 1e-6

    V, converged_, error, Scalc_, iter_, elapsed_ = helm_josep(Ybus=inputs.Ybus,
                                                               Yseries=inputs.Yseries,
                                                               V0=inputs.Vbus,
                                                               S0=inputs.Sbus,
                                                               Ysh0=inputs.Ysh_helm,
                                                               pq=inputs.pq,
                                                               pv=inputs.pv,
                                                               sl=inputs.ref,
                                                               pqpv=inputs.pqpv,
                                                               tolerance=tolerance,
                                                               max_coeff=50,
                                                               use_pade=True,
                                                               verbose=True)
    Vm = np.abs(V)
    Va = np.angle(V)
    dP = np.abs(inputs.Sbus.real - Scalc_.real)
    dP[inputs.ref] = 0
    dQ = np.abs(inputs.Sbus.imag - Scalc_.imag)
    dQ[inputs.pv] = np.nan
    dQ[inputs.ref] = np.nan

    df = pd.DataFrame(data=np.c_[inputs.types, Vm, Va, np.abs(inputs.Vbus), dP, dQ],
                      columns=['Types', 'Vm', 'Va', 'Vset', 'P mismatch', 'Q mismatch'])
    print(df)
    print('Error', error)
    print('P error', np.max(np.abs(dP)))
    print('Elapsed', elapsed_)
    print('Iterations', iter_)

    return error < tolerance


def test_sigma(grid):
    """
    Sigma-distances test
    :param grid:
    :return:
    """
    nc = grid.compile_snapshot()
    inputs = nc.compute()[0]  # pick the first island

    U_, X_, Q_, iter_, normF = helm_coefficients_josep(Ybus=inputs.Ybus,
                                                       Yseries=inputs.Yseries,
                                                       V0=inputs.Vbus,
                                                       S0=inputs.Sbus,
                                                       Ysh0=-inputs.Ysh_helm,
                                                       pq=inputs.pq,
                                                       pv=inputs.pv,
                                                       sl=inputs.ref,
                                                       pqpv=inputs.pqpv,
                                                       tolerance=1e-6,
                                                       max_coeff=50,
                                                       verbose=False)

    n = inputs.nbus
    Sig_re = np.zeros(n, dtype=float)
    Sig_im = np.zeros(n, dtype=float)
    Sigma = sigma_function(U_, X_, iter_ - 1, inputs.Vbus[inputs.ref])
    Sig_re[inputs.pqpv] = np.real(Sigma)
    Sig_im[inputs.pqpv] = np.imag(Sigma)
    sigma_distances = sigma_distance(Sig_re, Sig_im)

    # sigma plot
    sx = np.linspace(-0.25, np.max(Sig_re)+0.1, 100)
    sy1 = np.sqrt(0.25 + sx)
    sy2 = -np.sqrt(0.25 + sx)

    fig = plt.figure(figsize=(8, 7))
    ax = fig.add_subplot(111)
    ax.plot(Sig_re, Sig_im, 'o')
    ax.plot(sx, sy1, 'b')
    ax.plot(sx, sy2, 'r')
    ax.set_title('Sigma plot')
    ax.set_xlabel('$\sigma_{re}$')
    ax.set_ylabel('$\sigma_{im}$')
    plt.show()

    return sigma_distances


def test_pade(grid):
    """
    Sigma-distances test
    :param grid:
    :return:
    """
    nc = grid.compile_snapshot()
    inputs = nc.compute()[0]  # pick the first island

    U_, X_, Q_, iter_, normF = helm_coefficients_josep(Ybus=inputs.Ybus,
                                                       Yseries=inputs.Yseries,
                                                       V0=inputs.Vbus,
                                                       S0=inputs.Sbus,
                                                       Ysh0=-inputs.Ysh_helm,
                                                       pq=inputs.pq,
                                                       pv=inputs.pv,
                                                       sl=inputs.ref,
                                                       pqpv=inputs.pqpv,
                                                       tolerance=1e-6,
                                                       max_coeff=50,
                                                       verbose=False)

    alphas = np.arange(0, 1.1, 0.01)
    n = inputs.nbus
    na = len(alphas)
    V = np.zeros((na, n))
    V[:, inputs.ref] = np.abs(inputs.Vbus[inputs.ref])
    for i, alpha in enumerate(alphas):
        V[i, inputs.pqpv] = np.abs(pade4all(order=iter_, coeff_mat=U_, s=alpha))

    plt.axvline(0, c='k')
    plt.axvline(1, c='k')
    plt.plot(alphas, V)
    plt.ylabel('Voltage (p.u.)')
    plt.xlabel('$\lambda$')
    plt.show()


if __name__ == '__main__':
    from GridCal.Engine import FileOpen
    import pandas as pd

    np.set_printoptions(linewidth=2000, suppress=True)
    pd.set_option('display.max_rows', 500)
    pd.set_option('display.max_columns', 500)
    pd.set_option('display.width', 1000)

    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE39_1W.gridcal'
    fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE 14.xlsx'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/lynn5buspv.xlsx'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE 118.xlsx'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/1354 Pegase.xlsx'
    # fname = 'helm_data1.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE 14 PQ only.gridcal'
    # fname = 'IEEE 14 PQ only full.gridcal'
    grid = FileOpen(fname).open()

    # test_voltage(grid=grid)

    # test_sigma(grid=grid)

    test_pade(grid)
