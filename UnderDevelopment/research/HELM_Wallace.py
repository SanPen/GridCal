
import numpy as np

np.set_printoptions(precision=6, suppress=True, linewidth=320)
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


def reduce_arrays(Y_series, Y_shunt, slack_indices, S, Vset, types):
    """

    Args:
        Y_series: series admittances matrix
        Y_shunt: shunt admittances vector
        slack_indices: array of slack indices
        S: power injections vector
        Vset: set voltages vector for the pv buses
        types: vector of types for every bus

    Returns:

    """

    n_bus = len(Y_shunt)

    # Compose the list of buses indices excluding the indices of the slack buses
    non_slack_indices = list(range(n_bus))
    for i in slack_indices[::-1]:
        non_slack_indices.pop(i)
    non_slack_indices = array(non_slack_indices)

    # Types of the non slack buses
    types_red = types[non_slack_indices]

    # Re-map the pq and pv lists
    pq_red = list()
    pv_red = list()
    for i in range(len(types_red)):
        if types_red[i] == NodeType.PQ.value[0]:  # PQ
            pq_red.append(i)
        elif types_red[i] == NodeType.PV.value[0]:  # PV
            pv_red.append(i)
    pq_red = array(pq_red, dtype=int)
    pv_red = array(pv_red, dtype=int)

    # Compose a reduced admittance matrix without the rows and columns that correspond to the slack buses
    Y_series_red = Y_series[non_slack_indices, :][:, non_slack_indices]

    # reduce the Y_shunt array
    Y_shunt_red = Y_shunt[non_slack_indices]

    M = Vset[non_slack_indices]

    S_red = S[non_slack_indices]

    # matrix of the columns of the admittance matrix that correspond to the slack buses
    Yslack = Y_series[non_slack_indices, :][:, slack_indices]

    # vector of slack voltages (Complex)
    Vslack = Vset[slack_indices]

    # vector of currents being injected by the slack nodes (Matrix vector product)
    Iind = -1 * np.ndarray.flatten(array(Yslack.dot(Vslack)))

    # create system matrix A of the model 4 of the Wallace article
    NPQ = len(pq_red)
    NPV = len(pv_red)
    NPQPV = NPQ + NPV

    dij_y = dia_matrix((Y_shunt_red, zeros(1)), shape=(NPQPV, NPQPV))

    dij_pq = coo_matrix((Y_shunt_red[pq_red], (linspace(0, NPQ - 1, NPQ).astype(int), pq_red)), shape=(NPQ, NPQPV)).tocsc()

    dij_pv = coo_matrix((ones(NPV) * 2, (linspace(0, NPV - 1, NPV), pv_red)), shape=(NPV, NPQPV)).tocsc()

    A1 = Y_series_red.real + dij_y.real

    A2 = Y_series_red.imag - dij_y.imag

    APQ3 = Y_series_red.imag[pq_red] - dij_pq.imag

    APQ4 = Y_series_red.real[pq_red] + dij_pq.real

    APV3 = dij_pv

    APV4 = csc_matrix((NPV, NPQPV))

    A = sp_vstack((
        sp_hstack((A1, A2)),
        sp_hstack((APQ3, APQ4)),
        sp_hstack((APV3, APV4))
    )).tocsc()

    return A, Y_series_red, Y_shunt_red, S_red, Iind, M, pq_red, pv_red, NPQPV


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


def get_rhs(n, npqpv, V, Y_series_red, Y_shunt_red, S_red, M, pq, pv):
    """
    Compute the right hand side vector (rhs)    
    Args:
        n: coefficient order
        V: Voltage coefficients matrix (rows: coeff. order, columns: reduced bus index)
        Y_series_red: Reduced series admittances matrix
        Y_shunt_red: Reduced shunt admittances vector
        S_red: Reduced power injections vector
        M: Reduced set voltages vector for the pv buses
        pq: array of reduced PQ bus numbers
        pv: array of reduced PV bus numbers

    Returns:
        Right hand side vector
    """

    if n == 0:
        r1 = S_red.real - Y_shunt_red.real
        rpq = S_red.imag[pq] - Y_shunt_red.imag[pq]
        rpv = L2(n, M[pv])
    else:
        m = array(range(n))
        val = (conj(V[m, :]) * Y_series_red.dot(V[-m, :][0])).sum(axis=0)
        r1 = - val.real
        rpq = -val.imag[pq]
        rpv = (conj(V[:, pv][m, :]) * V[:, pv][-m, :]).sum(axis=0).real + L2(n, M[pv])

    return np.hstack((r1, rpq, rpv))


def helmw(admittances_series, admittances_shunt, powerInjections, voltageSetPoints, types, ref, pqpv,
          eps=1e-3, maxcoefficientCount=50):
    """

    Args:
        admittances_series:
        admittances_shunt:
        maxcoefficientCount:
        powerInjections:
        voltageSetPoints:
        types:
        ref:
        eps:

    Returns:

    """
    # reduce the arrays and build the system matrix
    A, Y_series_red, Y_shunt_red, S_red, Iind, M, pq_red, pv_red, npqpv = reduce_arrays(Y_series=admittances_series,
                                                                                        Y_shunt=admittances_shunt,
                                                                                        slack_indices=ref,
                                                                                        S=powerInjections,
                                                                                        Vset=abs(voltageSetPoints),
                                                                                        types=types)
    print('\nA:\n', A.toarray())

    # factorize the system matrix only once
    Afac = factorized(A)

    # declare the voltages coefficient matrix
    V = zeros((0, npqpv), dtype=complex_type)

    for n in range(10):

        # compute the right hand side of the linear system
        rhs = get_rhs(n, npqpv, V, Y_series_red, Y_shunt_red, S_red, M, pq_red, pv_red)

        # solve the linear system
        x = Afac(rhs)

        # assign the solution to the voltages (convert floats to complex)
        r, i = np.split(x, 2)
        vn = r + 1j * i

        # stack the coefficients solution
        V = np.vstack((V, vn))

    # compute the voltages with Padè
    v_red = zeros(npqpv, dtype=complex_type)
    for j in range(npqpv):
        v_red[j], _, _ = pade_approximation(n, j, V)

    voltages = voltageSetPoints.copy()
    voltages[pqpv] = v_red

    print('\nVoltage coeff: \n', V)
    print('\nVoltage values: \n', voltages)
    return voltages


if __name__ == "__main__":
    from GridCal.grid.CalculationEngine import *

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
    cmax = 30
    V1 = helmw(admittances_series=circuit.power_flow_input.Yseries,
               admittances_shunt=circuit.power_flow_input.Yshunt,
               powerInjections=circuit.power_flow_input.Sbus,
               voltageSetPoints=circuit.power_flow_input.Vbus,
               types=circuit.power_flow_input.types,
               ref=circuit.power_flow_input.ref,
               pqpv=circuit.power_flow_input.pqpv,
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