# AUTHORS: Santiago Peñate Vera and Josep Fanals Batllori
# CONTACT:  santiago.penate.vera@gmail.com, u1946589@campus.udg.edu
# thanks to Llorenç Fanals Batllori for his help at coding

# --------------------------- LIBRARIES
import numpy as np
import pandas as pd
import time
from scipy.sparse import csc_matrix, coo_matrix
from scipy.sparse import lil_matrix, diags, hstack as hs, vstack as vs
from scipy.sparse.linalg import spsolve, factorized
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
            AUX2 = E[j-1]
            DIFF = E[j] - AUX2

            if abs(DIFF) <= Tiny:
                E[j-1] = Huge
            else:
                if DIFF == 0:
                    DIFF = Tiny
                E[j-1] = AUX1 + One / DIFF

        if np.mod(n, 2) == 0:
            estim = E[0]
        else:
            estim = E[1]

    return estim, E


def pade_approximation(n, an, s=1):
    """
    Computes the n/2 pade approximant of the series an at the approximation
    point s

    Arguments:
        an: coefficient matrix, (number of coefficients, number of series)
        n:  order of the series
        s: point of approximation

    Returns:
        pade approximation at s
    """
    nn = int(n / 2)
    if np.mod(nn, 2) == 0:
        nn -= 1

    L = nn
    M = nn

    an = np.ndarray.flatten(an)
    rhs = an[L + 1:L + M + 1]

    C = zeros((L, M), dtype=complex)
    for i in range(L):
        k = i + 1
        C[i, :] = an[L - M + k:L + k]

    try:
        b = solve(C, -rhs)  # bn to b1
    except:
        return 0, zeros(L + 1, dtype=complex), zeros(L + 1, dtype=complex)

    b = r_[1, b[::-1]]  # b0 = 1

    a = zeros(L + 1, dtype=complex)
    a[0] = an[0]
    for i in range(L):
        val = complex(0)
        k = i + 1
        for j in range(k + 1):
            val += an[k - j] * b[j]
        a[i + 1] = val

    p = complex(0)
    q = complex(0)
    for i in range(L + 1):
        p += a[i] * s ** i
        q += b[i] * s ** i

    return p / q, a, b

def conv1(A, B, c, i):
    suma = [np.conj(A[k, i]) * B[c - k, i] for k in range(1, c + 1)]
    return sum(suma)

def conv2(A, B, c, i):
    suma = [A[k, i] * B[c - 1 - k, i] for k in range(1, c)]
    return sum(suma)

def conv3(A, B, c, i):
    suma = [A[k, i] * np.conj(B[c - k, i]) for k in range(1, c)]
    return sum(suma)

def helm_josep(Ybus, Yseries, V0, S0, Ysh0, pq, pv, sl, pqpv, tolerance=1e-6, max_coeff=30, verbose=False):
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
    :param pqpv: list of pq and pv nodes sorted
    :param tolerance: target error (or tolerance)
    :param max_coeff: maximum number of coefficients
    :return: V, converged, norm_f, Scalc, iter_, elapsed
    """

    start_time = time.time()

    npqpv = len(pqpv)
    npv = len(pv)
    nsl = len(sl)
    n = Yseries.shape[0]

    # --------------------------- PREPARING IMPLEMENTATION
    U = np.zeros((max_coeff, npqpv), dtype=complex)  # voltages
    U_re = np.zeros((max_coeff, npqpv), dtype=float)  # real part of voltages
    U_im = np.zeros((max_coeff, npqpv), dtype=float)  # imaginary part of voltages
    X = np.zeros((max_coeff, npqpv), dtype=complex)  # compute X=1/conj(U)
    X_re = np.zeros((max_coeff, npqpv), dtype=float)  # real part of X
    X_im = np.zeros((max_coeff, npqpv), dtype=float)  # imaginary part of X
    Q = np.zeros((max_coeff, npqpv), dtype=complex)  # unknown reactive powers
    Vm0 = np.abs(V0)
    vec_W = Vm0 * Vm0

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
    U_re[0, :] = U[0, :].real
    U_im[0, :] = U[0, :].imag
    X_re[0, :] = X[0, :].real
    X_im[0, :] = X[0, :].imag

    # .......................CALCULATION OF TERMS [1] ------------------------------------------------------------------
    valor = np.zeros(npqpv, dtype=complex)

    I_inj_slack = Yslack[pqpv_, :] * Vslack

    valor[pq_] = I_inj_slack[pq_] - Yslack[pq_].sum(axis=1).A1 + (vec_P[pq_] - vec_Q[pq_] * 1j) * X[0, pq_] + U[0, pq_] * Ysh0[pq_]
    valor[pv_] = I_inj_slack[pv_] - Yslack[pv_].sum(axis=1).A1 + (vec_P[pv_]) * X[0, pv_] + U[0, pv_] * Ysh0[pv_]

    # compose the right-hand side vector
    RHS = np.r_[valor.real,
                valor.imag,
                vec_W[pv] - 1.0]

    # Form the system matrix (MAT)
    VRE = coo_matrix((2 * U_re[0, pv_], (np.arange(npv), pv_)), shape=(npv, npqpv)).tocsc()
    VIM = coo_matrix((2 * U_im[0, pv_], (np.arange(npv), pv_)), shape=(npv, npqpv)).tocsc()
    XIM = coo_matrix((-X_im[0, pv_], (pv_, np.arange(npv))), shape=(npqpv, npv)).tocsc()
    XRE = coo_matrix((X_re[0, pv_], (pv_, np.arange(npv))), shape=(npqpv, npv)).tocsc()
    EMPTY = csc_matrix((npv, npv))

    MAT = vs((hs((G,   -B,   XIM)),
              hs((B,    G,   XRE)),
              hs((VRE,  VIM, EMPTY))), format='csc')

    if verbose:
        print('MAT')
        print(MAT.toarray())

    # factorize (only once)
    MAT_LU = factorized(MAT.tocsc())

    # solve
    LHS = MAT_LU(RHS)

    U_re[1, :] = LHS[:npqpv]
    U_im[1, :] = LHS[npqpv:2 * npqpv]
    Q[0, pv_] = LHS[2 * npqpv:]

    U[1, :] = U_re[1, :] + U_im[1, :] * 1j
    X[1, :] = (-X[0, :] * np.conj(U[1, :])) / np.conj(U[0, :])
    X_re[1, :] = X[1, :].real
    X_im[1, :] = X[1, :].imag

    # .......................CALCULATION OF TERMS [>=2] ----------------------------------------------------------------
    iter_ = 1
    range_pqpv = np.arange(npqpv)
    for c in range(2, max_coeff):  # c defines the current depth

        valor[pq_] = (vec_P[pq_] - vec_Q[pq_] * 1j) * X[c - 1, pq_] + U[c - 1, pq_] * Ysh0[pq_]
        valor[pv_] = conv2(X, Q, c, pv_) * -1j + U[c - 1, pv_] * Ysh0[pv_] + X[c - 1, pv_] * vec_P[pv_]

        RHS = np.r_[valor.real,
                    valor.imag,
                    -conv3(U, U, c, pv_).real]

        LHS = MAT_LU(RHS)

        U_re[c, :] = LHS[:npqpv]
        U_im[c, :] = LHS[npqpv:2 * npqpv]
        Q[c - 1, pv_] = LHS[2 * npqpv:]

        U[c, :] = U_re[c, :] + 1j * U_im[c, :]
        X[c, range_pqpv] = -conv1(U, X, c, range_pqpv) / np.conj(U[0, range_pqpv])
        X_re[c, :] = np.real(X[c, :])
        X_im[c, :] = np.imag(X[c, :])

        iter_ += 1

    # --------------------------- RESULTS COMPOSITION ------------------------------------------------------------------
    if verbose:
        print('V coefficients')
        print(U)

    # compute the final voltage
    Vpqpv = U.sum(axis=0)

    # ensemble the voltage
    V = np.zeros(n, dtype=complex)
    V[pqpv] = Vpqpv
    V[sl] = Vslack

    # compute power mismatch
    Scalc = V * np.conj(Ybus * V)
    diff = S0 - Scalc
    norm_f = np.linalg.norm(np.r_[diff[pqpv].real, diff[pq].imag], np.inf)  # same as max(abs())

    # check convergence
    converged = norm_f < tolerance

    elapsed = time.time() - start_time

    return V, converged, norm_f, Scalc, iter_, elapsed


if __name__ == '__main__':
    from GridCal.Engine import *
    import pandas as pd

    np.set_printoptions(linewidth=2000)
    pd.set_option('display.max_rows', 500)
    pd.set_option('display.max_columns', 500)
    pd.set_option('display.width', 1000)

    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE39_1W.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE 14.xlsx'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/lynn5buspv.xlsx'
    fname = 'helm_data1.gridcal'

    grid = FileOpen(fname).open()

    nc = grid.compile_snapshot()
    inputs = nc.compute()[0]  # pick the first island

    V, converged_, error, Scalc_, iter_, elapsed_ = helm_josep(Ybus=inputs.Ybus,
                                                               Yseries=inputs.Yseries,
                                                               V0=inputs.Vbus,
                                                               S0=inputs.Sbus,
                                                               Ysh0=-inputs.Ysh,
                                                               pq=inputs.pq,
                                                               pv=inputs.pv,
                                                               sl=inputs.ref,
                                                               pqpv=inputs.pqpv,
                                                               tolerance=1e-6,
                                                               max_coeff=10,
                                                               verbose=True)
    Vm = np.abs(V)
    Va = np.angle(V)
    df = pd.DataFrame(data=np.c_[Vm, Va, np.abs(inputs.Vbus), inputs.Sbus.real, Scalc_.real, inputs.Sbus.imag, Scalc_.imag],
                      columns=['Vm', 'Va', 'Vset', 'P0', 'P', 'Q0', 'Q'])
    print(df)
    print('Error', error)
    print('Elapsed', elapsed_)