
import numpy as np
from numpy import where, zeros, ones, mod, conj, array, dot, complex128, linspace  # , complex256
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


def make_A(Y_series, Y_shunt, pq, pv, pqpv, types):
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


def calc_W(n, npqpv, pqpv, kw, C, W):
    """
    Calculation of the inverse coefficients W.
    @param n: Order of the coefficients
    @param npqpv: number of pq and pv nodes
    @param pqpv: array with the PQ and PV node indices
    @param kw: indices that correspond to PQPV in the W structure
    @param C: Structure of voltage coefficients (Ncoeff x nbus elements)
    @param W: Structure of inverse voltage coefficients (Ncoeff x nbus elements)
    @return: Array of inverse voltage coefficients for the order n
    """

    if n == 0:
        res = ones(npqpv, dtype=complex_type)
    else:
        # res = zeros(npqpv, dtype=complex_type)
        # for l in range(n):
        #     res -= W[l, kw] * C[n - l, pqpv]

        l = array(range(n))
        res = -(W[:, kw][l, :] * C[:, pqpv][n - l, :]).sum(axis=0)

    res /= conj(C[0, pqpv])

    return res


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
        rpq = Sbus.imag[pq] - Y_shunt.imag[pq]
        rpv = L(n, M[pv])**2
    else:

        nbus = Y_series.shape[0]
        val = zeros(nbus, dtype=complex_type)
        for i in pqpv:
            for m in range(n):
                s = 0 + 0j
                for k in range(nbus):
                    s += Y_series[i, k] * V[n - m, k]
                val[i] += conj(V[m, i]) * s

        valpv = zeros(nbus, dtype=complex_type)
        for i in pv:
            for m in range(n):
                valpv[i] += conj(V[m, i]) * V[n - m, i]

        r1 = - val.real[pqpv]
        rpq = -val.imag[pq]
        rpv = valpv.real[pv] + L(n, M[pv])**2

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

    for n in range(1, maxcoefficientCount):

        # compute the right hand side of the linear system
        rhs = get_rhs(n, npqpv, V, Y_series, Y_shunt, Sbus, M, pq, pv, pqpv)

        # solve the linear system
        x = Afac(rhs)

        # assign the solution to the voltages (convert floats to complex)
        r, i = np.split(x, 2)
        vn = r + 1j * i

        # stack the coefficients solution
        V[n, pqpv] = vn

    # compute the voltages with Padè
    print('\nVoltage coeff: \n', V)
    voltages = voltageSetPoints.copy()
    for j in pqpv:
        voltages[j], _, _ = pade_approximation(n, j, V)

    # print('\nVoltage coeff: \n', V)
    print('\nVoltage values: \n', voltages)
    return voltages


if __name__ == "__main__":
    from GridCal.grid.CalculationEngine import *
    np.set_printoptions(suppress=True, linewidth=320, formatter={'float': '{: 0.4f}'.format})

    grid = MultiCircuit()
    grid.load_file('lynn5buspv.xlsx')
    # grid.load_file('IEEE30.xlsx')

    grid.compile()

    circuit = grid.circuits[0]

    print('\nYbus:\n', circuit.power_flow_input.Ybus.todense())
    print('\nYseries:\n', circuit.power_flow_input.Yseries.todense())
    print('\nYshunt:\n', circuit.power_flow_input.Yshunt)
    print('\nSbus:\n', circuit.power_flow_input.Sbus)
    print('\nIbus:\n', circuit.power_flow_input.Ibus)
    print('\nVbus:\n', circuit.power_flow_input.Vbus)
    print('\ntypes:\n', circuit.power_flow_input.types)
    print('\npq:\n', circuit.power_flow_input.pq)
    print('\npv:\n', circuit.power_flow_input.pv)
    print('\nvd:\n', circuit.power_flow_input.ref)

    import time
    print('HELM model 4')
    start_time = time.time()
    cmax = 15
    V1 = helmw(Y_series=circuit.power_flow_input.Yseries,
               Y_shunt=circuit.power_flow_input.Yshunt,
               Sbus=circuit.power_flow_input.Sbus,
               voltageSetPoints=circuit.power_flow_input.Vbus,
               pq=circuit.power_flow_input.pq,
               pv=circuit.power_flow_input.pv,
               ref=circuit.power_flow_input.ref,
               pqpv=circuit.power_flow_input.pqpv,
               types=circuit.power_flow_input.types,
               eps=1e-9,
               maxcoefficientCount=cmax)

    print("--- %s seconds ---" % (time.time() - start_time))
    # print_coeffs(C, W, R, X, H)

    print('V module:\t', abs(V1))
    print('V angle: \t', angle(V1))
    #print('error: \t', best_err)

    # check the HELM solution: v against the NR power flow
    print('\nNR')
    options = PowerFlowOptions(SolverType.NR, verbose=False, robust=False, tolerance=1e-9)
    power_flow = PowerFlow(grid, options)

    start_time = time.time()
    power_flow.run()
    print("--- %s seconds ---" % (time.time() - start_time))
    vnr = circuit.power_flow_results.voltage

    print('V module:\t', abs(vnr))
    print('V angle: \t', angle(vnr))
    print('error: \t', circuit.power_flow_results.error)

    # check
    print('\ndiff:\t', V1 - vnr)