import numpy as np
np.set_printoptions(linewidth=320)
from numpy import zeros, ones, mod, conj, array, c_, r_, linalg, Inf, complex128
from itertools import product
from numpy.linalg import solve
from scipy.sparse.linalg import factorized
from scipy.sparse import issparse, csc_matrix as sparse

# Set the complex precision to use
complex_type = complex128


def calc_W(n, npqpv, C, W):
    """
    Calculation of the inverse coefficients W.
    @param n: Order of the coefficients
    @param npqpv: number of pq and pv nodes
    @param C: Structure of voltage coefficients (Ncoeff x nbus elements)
    @param W: Structure of inverse voltage coefficients (Ncoeff x nbus elements)
    @return: Array of inverse voltage coefficients for the order n
    """

    if n == 0:
        res = ones(npqpv, dtype=complex_type)
    else:
        l = arange(n)
        res = -(W[l, :] * C[n - l, :]).sum(axis=0)

    res /= conj(C[0, :])

    return res


def continued_fraction(seq):
    """
    Convert the simple continued fraction in `seq`
    into a fraction, num / den
    Args:
        seq:
    Returns:
    """
    num, den = complex_type(1), complex_type(0)
    for u in reversed(seq):
        num, den = den + num * u, num
    return num / den


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


def helm_pq(Vbus, Sbus, Ibus, Ybus, Yserie, Ysh, pq, pv, ref, pqpv, tol=1e-9):
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

    # compose the slack nodes influence current
    Yslack = Yserie[pqpv, :][:, ref]
    Iref = Yslack.dot(Vbus[ref])

    nbus = len(Vbus)
    npqpv = len(pqpv)
    npq = len(pq)
    npv = len(pv)

    # factorize the Yseries matrix only once
    Yseries_pqpv = Yserie[pqpv, :][:, pqpv]
    # Yseries_pqpv = Ybus[pqpv, :][:, pqpv]
    Ysolve = factorized(Yseries_pqpv)

    # declare the matrix of coefficients that will lead to the voltage computation
    Vcoeff = zeros((0, npqpv), dtype=complex_type)

    # Declare the inverse coefficients vector
    # (it is actually a matrix; a vector of coefficients per coefficient order)
    Wcoeff = zeros((0, npqpv), dtype=complex_type)

    # loop parameters
    n = 0
    coeff_tol = 10

    while coeff_tol > tol:
        # add coefficients row
        Vcoeff = r_[Vcoeff, np.zeros((1, npqpv), dtype=complex_type)]
        Wcoeff = r_[Wcoeff, np.zeros((1, npqpv), dtype=complex_type)]

        if n == 0:
            RHS = Ibus[pqpv] - Iref
        else:
            RHS = Sbus[pqpv].conj() * Wcoeff[n-1, :] + Ysh[pqpv] * Vcoeff[n-1, :]

        # solve the voltage coefficients
        Vcoeff[n, :] = Ysolve(RHS)

        # compute the inverse voltage coefficients
        Wcoeff[n, :] = calc_W(n=n, npqpv=npqpv, C=Vcoeff, W=Wcoeff)

        # the proposed HELM convergence is to check the voltage coefficients difference
        # here, I check the maximum of the absolute of the difference
        if n > 0:
            coeff_tol = max(abs(Vcoeff[n, :] - Vcoeff[n-1, :]))

        n += 1

    # compose the final voltage
    voltage = Vbus
    # voltage[pqpv] = Vcoeff.sum(axis=0)

    for i, ii in enumerate(pqpv):
        voltage[ii], _, _ = pade_approximation(n, Vcoeff[:, i])
        # voltage[ii] = continued_fraction(Vcoeff[:, i])

    print('\nVcoeff:\n', Vcoeff)

    # evaluate F(x)
    Scalc = voltage * conj(Ybus * voltage - Ibus)
    mis = Scalc - Sbus  # complex power mismatch
    F = r_[mis[pv].real, mis[pq].real, mis[pq].imag]  # concatenate again

    # check for convergence
    normF = linalg.norm(F, Inf)

    return voltage, normF

if __name__ == '__main__':
    from GridCal.Engine.calculation_engine import *

    grid = MultiCircuit()
    grid.load_file('lynn5buspq.xlsx')

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

    v, err = helm_pq(Vbus=circuit.power_flow_input.Vbus,
                     Sbus=circuit.power_flow_input.Sbus,
                     Ibus=circuit.power_flow_input.Ibus,
                     Ybus=circuit.power_flow_input.Ybus,
                     Yserie=circuit.power_flow_input.Yseries,
                     Ysh=circuit.power_flow_input.Yshunt,
                     pq=circuit.power_flow_input.pq,
                     pv=circuit.power_flow_input.pv,
                     ref=circuit.power_flow_input.ref,
                     pqpv=circuit.power_flow_input.pqpv)

    print('helm')
    print('V module:\t', abs(v))
    print('V angle: \t', angle(v))
    print('error: \t', err)

    # check the HELM solution: v against the NR power flow
    # print('\nNR')
    # options = PowerFlowOptions(SolverType.NR, verbose=False, robust=False, tolerance=1e-9)
    # power_flow = PowerFlowDriver(grid, options)
    # power_flow.run()
    # vnr = circuit.power_flow_results.voltage
    #
    # print('V module:\t', abs(vnr))
    # print('V angle: \t', angle(vnr))
    # print('error: \t', circuit.power_flow_results.error)
    #
    # # check
    # print('\ndiff:\t', v - vnr)