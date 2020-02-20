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
np.set_printoptions(linewidth=2000)
pd.set_option('display.max_rows', 500)
pd.set_option('display.max_columns', 500)
pd.set_option('display.width', 1000)
# --------------------------- END LIBRARIES


def conv(A, B, c, i, tipus):
    if tipus == 1:
        suma = [np.conj(A[k, i]) * B[c - k, i] for k in range(1, c + 1)]
        return sum(suma)
    elif tipus == 2:
        suma = [A[k, i] * B[c - 1 - k, i] for k in range(1, c)]
        return sum(suma)
    elif tipus == 3:
        suma = [A[k, i] * np.conj(B[c - k, i]) for k in range(1, c)]
        return sum(suma)


def helm_josep(Yseries, V0, S0, Ysh0, pq, pv, sl, pqpv, tolerance=1e-6, max_coeff=30):
    """
    Holomorphic Embedding LoadFlow Method as formulated by Josep Fanals Batllori in 2020

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
    vec_W = V0 * V0

    Yred = Yseries[np.ix_(pqpv, pqpv)]  # admittance matrix without slack buses
    Ysl = Yseries[np.ix_(pqpv, sl)]
    G = np.real(Yred)  # real parts of Yij
    B = np.imag(Yred)  # imaginary parts of Yij
    vec_P = S0.real
    vec_Q = S0.imag
    V_sl = V0[sl]

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
        U[0, :] = spsolve(Yred, Ysl.sum(axis=1))
    else:
        U[0, :] = spsolve(Yred, Ysl)

    X[0, :] = 1 / np.conj(U[0, :])
    U_re[0, :] = U[0, :].real
    U_im[0, :] = U[0, :].imag
    X_re[0, :] = X[0, :].real
    X_im[0, :] = X[0, :].imag

    # .......................CALCULATION OF TERMS [1] ------------------------------------------------------------------
    valor = np.zeros(npqpv, dtype=complex)

    I_inj_slack = Ysl[pqpv_, :] * V_sl[:]

    valor[pq_] = I_inj_slack[pq_] - Ysl[pq_].sum(axis=1).A1 + (vec_P[pq_] - vec_Q[pq_] * 1j) * X[0, pq_] + U[0, pq_] * Ysh0[pq_]
    valor[pv_] = I_inj_slack[pv_] - Ysl[pv_].sum(axis=1).A1 + (vec_P[pv_]) * X[0, pv_] + U[0, pv_] * Ysh0[pv_]

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
        valor[pv_] = conv(X, Q, c, pv_, 2) * -1j + U[c - 1, pv_] * Ysh0[pv_] + X[c - 1, pv_] * vec_P[pv_]

        RHS = np.r_[valor.real,
                    valor.imag,
                    -conv(U, U, c, pv_, 3).real]

        LHS = MAT_LU(RHS)

        U_re[c, :] = LHS[:npqpv]
        U_im[c, :] = LHS[npqpv:2 * npqpv]
        Q[c - 1, pv_] = LHS[2 * npqpv:]

        U[c, :] = U_re[c, :] + 1j * U_im[c, :]
        X[c, range_pqpv] = -conv(U, X, c, range_pqpv, 1) / np.conj(U[0, range_pqpv])
        X_re[c, :] = np.real(X[c, :])
        X_im[c, :] = np.imag(X[c, :])

        iter_ += 1

    # --------------------------- RESULTS COMPOSITION ------------------------------------------------------------------

    U_final = np.zeros(npqpv, dtype=complex)  # final voltages
    U_final[0:npqpv] = U.sum(axis=0)
    I_serie = Yred * U_final  # current flowing through series elements

    # current through shunts
    I_shunt = -U_final * Ysh0[pqpv]  # change the sign again
    I_gen_out = I_serie - I_inj_slack + I_shunt  # current leaving the bus

    # assembly the reactive power vector
    Qfinal = vec_Q[pqpv]
    Qfinal[pv_] = (Q[:, pv_] * 1j).sum(axis=0).imag

    # compute the current injections
    I_gen_in = (vec_P[pqpv] - Qfinal * 1j) / np.conj(U_final)

    U_fi = np.zeros(n, dtype=complex)
    Q_fi = np.zeros(n, dtype=complex)
    P_fi = np.zeros(n, dtype=complex)
    I_dif = np.zeros(n, dtype=complex)
    S_dif = np.zeros(n, dtype=complex)

    U_fi[pqpv] = U_final
    U_fi[sl] = V_sl

    Q_fi[pqpv] = Qfinal
    Q_fi[sl] = np.nan

    P_fi[pqpv] = vec_P[pqpv]
    P_fi[sl] = np.nan

    I_dif[pqpv] = I_gen_in - I_gen_out
    I_dif[sl] = np.nan

    Scalc = P_fi + 1j * Q_fi

    S_dif[pqpv] = np.conj(I_gen_in - I_gen_out) * U_final
    S_dif[sl] = np.nan

    # compute error
    norm_f = np.max(np.abs(S_dif[pqpv]))
    converged = norm_f < tolerance

    elapsed = time.time() - start_time

    return U_fi, converged, norm_f, Scalc, iter_, elapsed


if __name__ == '__main__':
    from GridCal.Engine import *
    import pandas as pd

    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE39_1W.gridcal'
    fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/lynn5buspv.xlsx'
    grid = FileOpen(fname).open()

    nc = grid.compile_snapshot()
    inputs = nc.compute()[0]  # pick the first island

    V, converged_, error, Scalc_, iter_, elapsed_ = helm_josep(Yseries=inputs.Yseries,
                                                               V0=inputs.Vbus,
                                                               S0=inputs.Sbus,
                                                               Ysh0=inputs.Ysh,
                                                               pq=inputs.pq,
                                                               pv=inputs.pv,
                                                               sl=inputs.ref,
                                                               pqpv=inputs.pqpv,
                                                               tolerance=1e-6,
                                                               max_coeff=10)
    Vm = np.abs(V)
    Va = np.angle(V)
    df = pd.DataFrame(data=np.c_[Vm, Va, Scalc_.real, Scalc_.imag],
                      columns=['Vm', 'Va', 'P', 'Q'])
    print(df)
    print('Error', error)
    print('Elapsed', elapsed_)