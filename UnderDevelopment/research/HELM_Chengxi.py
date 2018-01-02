"""
Method implemented from the article:
Online voltage stability assessment for load areas based on the holomorphic embedding method
by Chengxi Liu, Bin Wang, Fengkai Hu, Kai Sun and Claus Leth Bak

Implemented by Santiago Peñate Vera 2018
"""
import numpy as np
np.set_printoptions(linewidth=32000, suppress=False)
from numpy import zeros, ones, mod, conj, array, c_, r_, linalg, Inf, complex128
from numpy.linalg import solve
from scipy.sparse.linalg import factorized
from scipy.sparse import lil_matrix
from scipy.sparse import hstack as hstack_s, vstack as vstack_s

# Set the complex precision to use
complex_type = complex128


def getWst(Vst_expanded, nbus):
    """
    Inverse voltage
    :param Vst_expanded: expanded vector of start voltages
    :param i: index in the non reduced scheme
    :return: Voltages complex vector, Inverse voltages complex vector
    """
    v = zeros(nbus, dtype=complex_type)
    for i in range(nbus):
        v[i] = complex_type(Vst_expanded[i] + 1j * Vst_expanded[i + 1])
    w = 1.0 / v
    return v, w


def prepare_system_matrices(Ybus, Vbus, pqpv, pq, pv, ref):
    """
    Prepare the system matrices
    :param Ybus:
    :param Vbus:
    :param pqpv:
    :param ref:
    :return:
    """
    n_bus = len(Vbus)
    n_bus2 = 2 * n_bus
    npv = len(pv)
    # ##################################################################################################################
    # Compute the starting voltages
    # ##################################################################################################################

    # System matrix
    A = lil_matrix((n_bus2, n_bus2))  # lil matrices are faster to populate

    # Expanded slack voltages
    Vslack = zeros(n_bus2)

    # Populate A
    for a in pqpv:  # rows
        for ii in range(Ybus.indptr[a], Ybus.indptr[a + 1]):  # columns in sparse format
            b = Ybus.indices[ii]

            A[2 * a + 0, 2 * b + 0] = Ybus[a, b].real
            A[2 * a + 0, 2 * b + 1] = -Ybus[a, b].imag
            A[2 * a + 1, 2 * b + 0] = Ybus[a, b].imag
            A[2 * a + 1, 2 * b + 1] = Ybus[a, b].real

    # set vd elements
    for a in ref:
        A[a * 2, a * 2] = 1.0
        A[a * 2 + 1, a * 2 + 1] = 1.0

        Vslack[a * 2] = Vbus[a].real
        Vslack[a * 2 + 1] = Vbus[a].imag

    # Solve starting point voltages
    Vst_expanded = factorized(A.tocsc())(Vslack)

    # Invert the voltages obtained: Get the complex voltage and voltage inverse vectors
    Vst, Wst = getWst(Vst_expanded, n_bus)

    # ##################################################################################################################
    # Compute the final system matrix
    # ##################################################################################################################

    # System matrices
    B = lil_matrix((n_bus2, 3 * npv))
    C = lil_matrix((3 * npv, n_bus2))
    D = lil_matrix((3 * npv, 3 * npv))

    for i, a in enumerate(pv):
        # "a" is the actual bus index
        # "i" is the number of the pv bus in the pv buses list

        B[2 * a + 0, 3 * i + 2] = Wst[a].imag
        B[2 * a + 1, 3 * i + 2] = Wst[a].real

        C[3 * i + 0, 2 * a + 0] = Wst[a].real
        C[3 * i + 0, 2 * a + 1] = -Wst[a].imag
        C[3 * i + 1, 2 * a + 0] = Wst[a].real
        C[3 * i + 1, 2 * a + 1] = Wst[a].imag
        C[3 * i + 2, 2 * a + 0] = Vst[a].real
        C[3 * i + 2, 2 * a + 1] = Vst[a].imag

        D[3 * i + 0, 3 * i + 0] = Vst[a].real
        D[3 * i + 0, 3 * i + 1] = -Vst[a].imag
        D[3 * i + 1, 3 * i + 0] = Vst[a].imag
        D[3 * i + 1, 3 * i + 1] = Vst[a].real

    Asys = vstack_s([
                    hstack_s([A, B]),
                    hstack_s([C, D])
                    ], format="csc")

    return Asys, Vst, Wst


def get_rhs(n, V, W, Q, Vbus, Vst, Pbus, nsys, nbus2, pv, pvpos):
    """
    Right hand side
    :param n: order of the coefficients
    :param V: Voltage coefficients (order, all buses)
    :param W: Inverse voltage coefficients (order, pv buses)
    :param Q: Reactive power coefficients  (order, pv buses)
    :param Vbus: Initial bus estimate (only used to pick the PV buses set voltage)
    :param Vst: Start voltage due to slack injections
    :param Pbus: Active power injections (all the buses)
    :param nsys: number of rows or cols in the system matrix A
    :param nbus2: two times the number of buses
    :param pv: list of pv indices in the grid
    :param pvpos: array from 0..npv
    :return: right hand side vector to solve the coefficients of order n
    """
    rhs = zeros(nsys)
    m = array(range(1, n), dtype=int)

    # Compute convolutions
    QW_convolution = (Q[n - m, :] * W[m, :].conjugate()).sum(axis=0)
    WV_convolution = (W[n - m, :] * V[m, :][:, pv]).sum(axis=0)
    VV_convolution = (V[m, :][:, pv] * V[n - m, :][:, pv].conjugate()).sum(axis=0)

    # compute the formulas
    f1 = Pbus[pv] * W[n - 1, :] + QW_convolution

    epsilon = -0.5 * VV_convolution
    if n == 1:
        epsilon += 0.5 * (abs(Vbus[pv]) ** 2 - abs(Vst[pv]) ** 2)

    # Assign the values to the right hand side vector
    idx1 = 2 * pv
    idx2 = 3 * pvpos + nbus2

    rhs[idx1 + 0] = f1.real
    rhs[idx1 + 1] = f1.imag
    rhs[idx2 + 0] = -WV_convolution.real
    rhs[idx2 + 1] = -WV_convolution.imag
    rhs[idx2 + 2] = epsilon.real

    return rhs


def assign_solution(x, bus_idx, nbus2, pvpos):
    """
    Assign the solution vector to the appropriate coefficients
    :param x: solution vector
    :param bus_idx: array from 0..nbus-1
    :param nbus2: two times the number of buses (integer)
    :param pvpos: array from 0..npv
    :return: Array of:
            - voltage coefficients
            - voltage inverse coefficients
            - reactive power
            of order n
    """

    v = x[2 * bus_idx] + 1j * x[2 * bus_idx + 1]

    w = x[nbus2 + 3 * pvpos] + 1j * x[nbus2 + 3 * pvpos + 1]

    q = x[nbus2 + 3 * pvpos + 2]

    return v, w, q


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
    if mod(nn, 2) == 0:
        nn -= 1

    L = nn
    M = nn

    an = np.ndarray.flatten(an)
    rhs = an[L + 1:L + M + 1]

    C = zeros((L, M), dtype=complex_type)
    for i in range(L):
        k = i + 1
        C[i, :] = an[L - M + k:L + k]

    try:
        b = solve(C, -rhs)  # bn to b1
    except:
        return 0, zeros(L + 1, dtype=complex_type), zeros(L + 1, dtype=complex_type)

    b = r_[1, b[::-1]]  # b0 = 1

    a = zeros(L + 1, dtype=complex_type)
    a[0] = an[0]
    for i in range(L):
        val = complex_type(0)
        k = i + 1
        for j in range(k + 1):
            val += an[k - j] * b[j]
        a[i + 1] = val

    p = complex_type(0)
    q = complex_type(0)
    for i in range(L + 1):
        p += a[i] * s ** i
        q += b[i] * s ** i

    return p / q, a, b


def helm_(Vbus, Sbus, Ibus, Ybus, pq, pv, ref, pqpv, tol=1e-9):
    """
    Args:
        Vbus:
        Sbus:
        Ibus:
        Ybus:
        Yserie:
        Ysh:
        pq:
        pv:
        ref:
        pqpv:
    Returns:
    """

    nbus = len(Vbus)
    npv = len(pv)
    bus_idx = array(range(nbus), dtype=int)
    pvpos = array(range(npv))

    # Prepare system matrices
    Asys, Vst, Wst = prepare_system_matrices(Ybus, Vbus, pqpv, pq, pv, ref)

    # Factorize the system matrix
    Afact = factorized(Asys)

    # get the shape
    nsys = Asys.shape[0]

    # declare the active power injections
    Pbus = Sbus.real

    # declare the matrix of coefficients: [order, bus index]
    V = zeros((1, nbus), dtype=complex_type)

    # Declare the inverse voltage coefficients: [order, pv bus index]
    W = zeros((1, npv), dtype=complex_type)

    # Reactive power coefficients on the PV nodes: [order, pv bus index]
    Q = zeros((1, npv), dtype=double)

    # Assign the initial values
    V[0, :] = Vst
    W[0, :] = Wst[pv]
    Q[0, :] = zeros(npv)

    for n in range(1, 15):

        # Reserve coefficients memory space
        V = np.vstack((V, np.zeros((1, nbus), dtype=complex_type)))
        W = np.vstack((W, np.zeros((1, npv), dtype=complex_type)))
        Q = np.vstack((Q, np.zeros((1, npv), dtype=double)))

        # Compute the free terms
        rhs = get_rhs(n=n, V=V, W=W, Q=Q,
                      Vbus=Vbus, Vst=Vst,
                      Pbus=Pbus, nsys=nsys,
                      nbus2=2 * nbus, pv=pv,
                      pvpos=pvpos)

        # Solve the linear system Asys x res = rhs
        res = Afact(rhs)

        # Assign solution to the coefficients
        V[n, :], W[n, :], Q[n, :] = assign_solution(x=res, bus_idx=bus_idx, nbus2=2 * nbus, pvpos=pvpos)

        # print('\nn:', n)
        # print('RHS:\n', rhs)
        # print('X:\n', res)

    print('V:\n', V)
    print('W:\n', W)
    print('Q:\n', Q)

    # Perform the Padè approximation
    # NOTE: Apparently the padé approximation is equivalent to the bare sum of coefficients !!
    # voltage = zeros(nbus, dtype=complex_type)
    # for i in range(nbus):
    #     voltage[i], _, _ = pade_approximation(n, V[:, i])

    voltage = V.sum(axis=0)

    # Calculate the error and check the convergence
    Scalc = voltage * conj(Ybus * voltage)
    mismatch = Scalc - Sbus  # complex power mismatch
    power_mismatch_ = r_[mismatch[pv].real, mismatch[pq].real, mismatch[pq].imag]

    # check for convergence
    normF = linalg.norm(power_mismatch_, Inf)

    return voltage, normF


if __name__ == '__main__':
    from GridCal.Engine.CalculationEngine import *

    grid = MultiCircuit()
    grid.load_file('lynn5buspv.xlsx')
    # grid.load_file('IEEE30.xlsx')
    # grid.load_file('/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE 14.xlsx')
    # grid.load_file('/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE39.xlsx')

    grid.compile()

    circuit = grid.circuits[0]

    print('\nYbus:\n', circuit.power_flow_input.Ybus.todense())
    # print('\nSbus:\n', circuit.power_flow_input.Sbus)
    # print('\nIbus:\n', circuit.power_flow_input.Ibus)
    # print('\nVbus:\n', circuit.power_flow_input.Vbus)
    # print('\ntypes:\n', circuit.power_flow_input.types)
    # print('\npq:\n', circuit.power_flow_input.pq)
    # print('\npv:\n', circuit.power_flow_input.pv)
    # print('\nvd:\n', circuit.power_flow_input.ref)

    v, err = helm_(Vbus=circuit.power_flow_input.Vbus,
                   Sbus=circuit.power_flow_input.Sbus,
                   Ibus=circuit.power_flow_input.Ibus,
                   Ybus=circuit.power_flow_input.Ybus,
                   pq=circuit.power_flow_input.pq,
                   pv=circuit.power_flow_input.pv,
                   ref=circuit.power_flow_input.ref,
                   pqpv=circuit.power_flow_input.pqpv)

    print('Voltage:\n', v, '\n', abs(v))

    print('Error:', err)