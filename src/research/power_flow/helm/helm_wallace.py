
import numpy as np
from numpy import zeros, ones, conj, array, \
    complex128, linspace  # , complex256
from scipy.linalg import solve
from scipy.sparse import dia_matrix, coo_matrix, csc_matrix, hstack as sp_hstack, vstack as sp_vstack
from scipy.sparse.linalg import factorized
# Set the complex precision to use

complex_type = complex128


def pade_approximation(n, d, an, s=1):
    """
    Computes the n/2 pade approximant of the series an at the approximation
    point s

    Arguments:
        an: coefficient series
        n:  order of the series
        d:  bus index
        s: point of approximation

    Returns:
        pade approximation at s
    """
    nn = int(n / 2)
    L = nn
    M = nn

    # formation of the linear system right hand side
    rhs = an[L + 1:L + M + 1, d]

    # formation of the coefficients matrix
    C = zeros((L, M), dtype=complex_type)
    for i in range(L):
        k = i + 1
        C[i, :] = an[L - M + k:L + k, d]

    # Obtaining of the b coefficients for orders greater than 0
    b = solve(C, -rhs)  # bn to b1
    b = r_[1, b[::-1]]  # b0 = 1

    # Obtaining of the coefficients 'a'
    a = zeros(L + 1, dtype=complex_type)
    a[0] = an[0, d]
    for i in range(L):
        val = complex_type(0)
        k = i + 1
        for j in range(k + 1):
            val += an[k - j, d] * b[j]
        a[i + 1] = val

    # evaluation of the function for the value 's'
    p = complex_type(0)
    q = complex_type(0)
    for i in range(L + 1):
        p += a[i] * s ** i
        q += b[i] * s ** i

    return p / q, a, b


def make_A2(Y_series, Y_shunt, pq, pv, pqpv, types):
    """

    Args:
        Y_series: series admittances matrix
        Y_shunt: shunt admittances vector
        pq:
        pv:
    Returns:

    """

    # create system matrix A of the model 4 of the Wallace article
    NPQ = len(pq)
    NPV = len(pv)
    NPQPV = NPQ + NPV

    dij_y = dia_matrix((Y_shunt[pqpv], zeros(1)), shape=(NPQPV, NPQPV)).tocsc()
    dij_pv = coo_matrix((ones(NPV) * 2, (linspace(0, NPV - 1, NPV), pv)), shape=(NPV, NPQPV)).tocsc()

    G = Y_series.real[pqpv, :][:, pqpv]
    B = Y_series.imag[pqpv, :][:, pqpv]

    Gpq = csc_matrix((NPQ, NPQPV))
    Bpq = csc_matrix((NPQ, NPQPV))
    dij_y_pq = csc_matrix((NPQ, NPQPV), dtype=complex_type)
    ii = 0
    for i, ti in enumerate(types):
        if ti == 1:
            jj = 0
            for j, tj in enumerate(types):
                if tj == 1:
                    Gpq[ii, jj] = Y_series.real[i, j]
                    Bpq[ii, jj] = Y_series.imag[i, j]
                    if ii == jj:
                        dij_y_pq[ii, jj] = Y_shunt[i]
                if tj == 1 or tj == 2:
                    jj += 1
            ii += 1

    print('G:\n', Y_series.real.toarray())
    print('B:\n', Y_series.imag.toarray())
    print('dij_y_pq:\n', dij_y_pq.toarray())

    A1 = G + dij_y.real
    print('\nA1:\n', G.toarray(), '\n+\n', dij_y.real.toarray())

    A2 = B - dij_y.imag
    print('\nA2:\n', B.toarray(), '\n-\n', dij_y.imag.toarray())

    APQ3 = Bpq - dij_y_pq.imag
    print('\nA_PQ3:\n', Bpq.toarray(), '\n-\n', dij_y_pq.imag.toarray())

    APQ4 = Gpq + dij_y_pq.real
    print('\nA_PQ4:\n', Gpq.toarray(), '\n+\n', dij_y_pq.real.toarray())

    APV3 = dij_pv
    print('\nA_PV3:\n', dij_pv.toarray())

    APV4 = csc_matrix((NPV, NPQPV))
    print('\nA_PV4:\n', APV4.toarray())

    A = sp_vstack((
        sp_hstack((A1, A2)),
        sp_hstack((APQ3, APQ4)),
        sp_hstack((APV3, APV4))
    )).tocsc()

    return A, NPQPV


def make_A(Y_series, Y_shunt, pq, pv, pqpv, types):

    # create system matrix A of the model 4 of the Wallace article
    N = len(Y_shunt)
    NPQ = len(pq)
    NPV = len(pv)
    NPQPV = NPQ + NPV

    dij_y = dia_matrix((Y_shunt, zeros(1)), shape=(N, N)).tocsc()
    dij = dia_matrix((ones(N), zeros(1)), shape=(N, N)).tocsc()
    G = Y_series.real
    B = Y_series.imag

    A1 = (G + dij_y.real)[pqpv, :][:, pqpv]
    A2 = (B - dij_y.imag)[pqpv, :][:, pqpv]

    M = (B - dij_y.imag)
    M[:, pv] = zeros((N, 1))
    APQ3 = M[pq, :][:, pqpv]

    M = (G + dij_y.imag)
    M[:, pv] = zeros((N, 1))
    APQ4 = M[pq, :][:, pqpv]

    APV3 = (2 * dij)[pv, :][:, pqpv]
    APV4 = csc_matrix((NPV, NPQPV))

    A = sp_vstack((
        sp_hstack((A1, A2)),
        sp_hstack((APQ3, APQ4)),
        sp_hstack((APV3, APV4))
    )).tocsc()

    print("\ndij_y:\n", dij_y.toarray())
    print("\ndij:\n", dij.toarray())

    print("\nA1:\n", A1.toarray())
    print("\nA2:\n", A2.toarray())

    print("\nAPQ3:\n", APQ3.toarray())
    print("\nAPQ4:\n", APQ4.toarray())

    print("\nAPV3:\n", APV3.toarray())
    print("\nAPV4:\n", APV4.toarray())

    return A, NPQPV


def L2(n, M):
    """
    
    Args:
        n: coefficient order
        M: Reduced set voltages vector for the pv buses

    Returns:
        The L vector
    """
    if n == 0:
        return ones(len(M))
    elif n == 1:
        return 2 * M - 2
    elif n == 2:
        return M * M - 2 * M + 1
    else:
        return zeros(len(M))


def L(n, M):
    """

    Args:
        n: coefficient order
        M: Reduced set voltages vector for the pv buses

    Returns:
        The L vector
    """
    if n == 0:
        return ones(len(M))
    elif n == 1:
        return M - 1
    else:
        return zeros(len(M))


def get_rhs(n, npqpv, V, Y_series, Y_shunt, Sbus, M, pq, pv, pqpv):
    """
    Compute the right hand side vector (rhs)    
    Args:
        n: coefficient order
        V: Voltage coefficients matrix (rows: coeff. order, columns: reduced bus index)
        Y_series: Reduced series admittances matrix
        Y_shunt: Reduced shunt admittances vector
        Sbus: Reduced power injections vector
        M: Reduced set voltages vector for the pv buses
        pq: array of reduced PQ bus numbers
        pv: array of reduced PV bus numbers

    Returns:
        Right hand side vector
    """

    if n == 1:
        r1 = Sbus.real[pqpv] - Y_shunt.real[pqpv]
        rpq = -Sbus.imag[pq] - Y_shunt.imag[pq]
        rpv = L(n, M[pv])**2

    else:

        nbus = Y_series.shape[0]
        val = zeros(nbus, dtype=complex_type)
        valpv = zeros(nbus, dtype=complex_type)
        for m in range(1, n):
            val += conj(V[m, :]) * (Y_series * V[n - m, :])
            valpv += conj(V[m, :]) * V[n - m, :]

        r1 = -val.real[pqpv]
        rpq = -val.imag[pq]
        rpv = -valpv.real[pv] + L(n, M[pv])**2

    return np.hstack((r1, rpq, rpv))


def helmw(Y_series, Y_shunt, Sbus, voltageSetPoints, pq, pv, ref, pqpv, types, eps=1e-3, maxcoefficientCount=50):
    """

    Args:
        Y_series:
        Y_shunt:
        Sbus:
        voltageSetPoints:
        pq:
        pv:
        ref:
        pqpv:
        eps:
        maxcoefficientCount:

    Returns:

    """

    nbus = len(Y_shunt)
    nref = len(ref)

    # reduce the arrays and build the system matrix
    A, npqpv = make_A(Y_series=Y_series, Y_shunt=Y_shunt, pq=pq, pv=pv, pqpv=pqpv, types=types)
    print('\nA:\n', A.toarray())

    # get the set points array
    M = abs(voltageSetPoints)

    # factorize the system matrix only once
    Afac = factorized(A)

    # declare the voltages coefficient matrix
    V = ones((maxcoefficientCount, nbus), dtype=complex_type)

    error = list()
    npv = len(pv)

    for n in range(1, maxcoefficientCount):

        # compute the right hand side of the linear system
        rhs = get_rhs(n, npqpv, V, Y_series, Y_shunt, Sbus, M, pq, pv, pqpv)
        print('\nn:', n, ', rhs:\n', rhs)

        # solve the linear system
        x = Afac(rhs)

        # assign the solution to the voltages (convert floats to complex)
        r, i = np.split(x, 2)
        vn = r + 1j * i

        print('voltage coeff (n):\n', vn)

        # stack the coefficients solution
        V[n, pqpv] = vn

        # compute the voltages with Padè
        # print('\nVoltage coeff: \n', V)
        voltages = voltageSetPoints.copy()
        for j in pqpv:
            voltages[j], _, _ = pade_approximation(n, j, V)

        # print('\nVoltage coeff: \n', V)
        # print('\nVoltage values: \n', voltages)

        # evaluate the solution error F(x0)
        Scalc = voltages * conj(Y_series * voltages)
        mis = Scalc - Sbus  # compute the mismatch
        dx = r_[mis[pv].real, mis[pq].real, mis[pq].imag]  # mismatch in the Jacobian order
        normF = np.linalg.norm(dx, np.Inf)

        if npv > 0:
            a = linalg.norm(mis[pv].real, Inf)
        else:
            a = 0
        b = linalg.norm(mis[pq].real, Inf)
        c = linalg.norm(mis[pq].imag, Inf)
        error.append([a, b, c])

    err_df = pd.DataFrame(array(error), columns=['PV_real', 'PQ_real', 'PQ_imag'])
    err_df.plot(logy=True)

    return voltages, normF
