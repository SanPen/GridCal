# AUTHORS: Josep Fanals Batllori and Santiago Peñate Vera
# CONTACT:  santiago.penate.vera@gmail.com, u1946589@campus.udg.edu
# thanks to Llorenç Fanals Batllori for his help at coding

# --------------------------- LIBRARIES
import numpy as np
import pandas as pd
import numba as nb
import time
from scipy.sparse import coo_matrix, csc_matrix
from scipy.sparse import hstack as hs, vstack as vs
from scipy.sparse.linalg import factorized, spsolve

np.set_printoptions(linewidth=2000, edgeitems=1000)
pd.set_option('display.max_rows', 500)
pd.set_option('display.max_columns', 500)
pd.set_option('display.width', 1000)


@nb.njit("(c16[:])(i8, c16[:, :], i8)")
def pade4all(order, coeff_mat, s=1):
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


# def conv1(A, B, c, indices):
#     suma = np.zeros(len(indices), dtype=np.complex128)
#     for k in range(1, c + 1):
#         suma += np.conj(A[k, indices]) * B[c - k, indices]
#     return suma
#
#
# def conv2(A, B, c, indices):
#     suma = np.zeros(len(indices), dtype=np.complex128)
#     for k in range(1, c):
#         suma += A[k, indices] * B[c - 1 - k, indices]
#     return suma
#
#
# def conv3(A, B, c, indices):
#     suma = np.zeros(len(indices), dtype=np.complex128)
#     for k in range(1, c):
#         suma += A[k, indices] * np.conj(B[c - k, indices])
#     return suma


def helm_josep(Ybus, Yseries, V0, S0, Ysh0, pq, pv, sl, pqpv, tolerance=1e-6, max_coeff=30, use_pade=True, verbose=False):
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
    :param verbose: Print intermediate objects and calculations?
    :return: V, converged, norm_f, Scalc, iter_, elapsed
    """

    start_time = time.time()

    npqpv = len(pqpv)
    npv = len(pv)
    nsl = len(sl)
    n = Yseries.shape[0]

    if n < 2:
        # V, converged, norm_f, Scalc, iter_, elapsed
        return V0, True, 0.0, S0, 0, 0.0

    # --------------------------- PREPARING IMPLEMENTATION--------------------------------------------------------------
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

    # get the current injections that appear due to the slack buses reduction
    I_inj_slack = Yslack[pqpv_, :] * Vslack

    valor[pq_] = I_inj_slack[pq_] - Yslack[pq_].sum(axis=1).A1 + (vec_P[pq_] - vec_Q[pq_] * 1j) * X[0, pq_] + U[0, pq_] * Ysh0[pq_]
    valor[pv_] = I_inj_slack[pv_] - Yslack[pv_].sum(axis=1).A1 + (vec_P[pv_]) * X[0, pv_] + U[0, pv_] * Ysh0[pv_]

    # compose the right-hand side vector
    RHS = np.r_[valor.real,
                valor.imag,
                vec_W[pv] - 1.0]

    # Form the system matrix (MAT)
    Upv = U[0, pv_]
    Xpv = X[0, pv_]
    VRE = coo_matrix((2 * Upv.real, (np.arange(npv), pv_)), shape=(npv, npqpv)).tocsc()
    VIM = coo_matrix((2 * Upv.imag, (np.arange(npv), pv_)), shape=(npv, npqpv)).tocsc()
    XIM = coo_matrix((-Xpv.imag, (pv_, np.arange(npv))), shape=(npqpv, npv)).tocsc()
    XRE = coo_matrix((Xpv.real, (pv_, np.arange(npv))), shape=(npqpv, npv)).tocsc()
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

    # update coefficients
    Q[0, pv_] = LHS[2 * npqpv:]
    U[1, :] = LHS[:npqpv] + 1j * LHS[npqpv:2 * npqpv]
    X[1, :] = -X[0, :] * np.conj(U[1, :]) / np.conj(U[0, :])

    # .......................CALCULATION OF TERMS [>=2] ----------------------------------------------------------------
    iter_ = 1
    range_pqpv = np.arange(npqpv, dtype=np.int64)
    for c in range(2, max_coeff):  # c defines the current depth

        valor[pq_] = (vec_P[pq_] - vec_Q[pq_] * 1j) * X[c - 1, pq_] + U[c - 1, pq_] * Ysh0[pq_]
        valor[pv_] = conv2(X, Q, c, pv_) * -1j + U[c - 1, pv_] * Ysh0[pv_] + X[c - 1, pv_] * vec_P[pv_]

        RHS = np.r_[valor.real,
                    valor.imag,
                    -conv3(U, U, c, pv_).real]

        LHS = MAT_LU(RHS)

        # update voltage coefficients
        U[c, :] = LHS[:npqpv] + 1j * LHS[npqpv:2 * npqpv]

        # update reactive power
        Q[c - 1, pv_] = LHS[2 * npqpv:]

        # update voltage inverse coefficients
        X[c, range_pqpv] = -conv1(U, X, c, range_pqpv) / np.conj(U[0, range_pqpv])

        iter_ += 1

    # --------------------------- RESULTS COMPOSITION ------------------------------------------------------------------
    if verbose:
        print('V coefficients')
        print(U)

    # compute the final voltage
    V = np.zeros(n, dtype=complex)
    if use_pade:
        V[pqpv] = pade4all(max_coeff - 1, U, 1)
    else:
        V[pqpv] = U.sum(axis=0)

    V[sl] = Vslack  # copy the slack buses

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
    fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE 14.xlsx'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/lynn5buspv.xlsx'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE 118.xlsx'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/1354 Pegase.xlsx'
    # fname = 'helm_data1.gridcal'

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
                                                               max_coeff=40,
                                                               use_pade=False,
                                                               verbose=False)
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
