import numpy as np
np.set_printoptions(precision=6, suppress=True, linewidth=320)
from numpy import where, zeros, ones, mod, conj, array, dot, angle, complex128 #, complex256
from numpy.linalg import solve

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


# @jit(cache=True)
def helmz(Vbus, Sbus, Ibus, Ybus, pq, pv, ref, pqpv, tol=1e-9, max_ter=5):
    """

    Args:
        admittances: Circuit complete admittance matrix

        slackIndices: Indices of the slack buses (although most likely only one works)

        coefficientCount: Number of voltage coefficients to evaluate (Must be an odd number)

        powerInjections: Array of power injections matching the admittance matrix size

        voltageSetPoints: Array of voltage set points matching the admittance matrix size

        types: Array of bus types matching the admittance matrix size. types: {1-> PQ, 2-> PV, 3-> Slack}

    Output:
        Voltages vector
    """

    # reduced impedance matrix
    Zred = inv(Ybus[pqpv, :][:, pqpv]).toarray()

    # slack currents
    Ivd = -Ybus[pqpv, :][:, ref].dot(Vbus[ref])

    # slack voltages influence
    Ck = Zred.dot(Ivd)

    npqpv = len(pqpv)

    Vcoeff = zeros((0, npqpv), dtype=complex_type)
    Wcoeff = zeros((0, npqpv), dtype=complex_type)

    row = zeros((1, npqpv), dtype=complex_type)

    for n in range(max_ter):

        # reserve memory
        Vcoeff = r_[Vcoeff, row.copy()]
        Wcoeff = r_[Wcoeff, row.copy()]

        if n == 0:
            I = Ivd
        else:
            I = conj(Sbus[pqpv]) * Wcoeff[n-1, :]

        # solve the voltage coefficients
        Vcoeff[n, :] = Zred.dot(I)

        # compute the inverse voltage coefficients
        Wcoeff[n, :] = calc_W(n=n, npqpv=npqpv, C=Vcoeff, W=Wcoeff)

    # compose the final voltage
    voltage = Vbus.copy()

    for i, ii in enumerate(pqpv):
        voltage[ii], _, _ = pade_approximation(n, Vcoeff[:, i])

    # evaluate F(x)
    Scalc = voltage * conj(Ybus * voltage - Ibus)
    mis = Scalc - Sbus  # complex power mismatch
    normF = linalg.norm(r_[mis[pv].real, mis[pq].real, mis[pq].imag], Inf)

    print('Vcoeff:\n', Vcoeff)

    print('V:\n', abs(Vcoeff.sum(axis=0)))

    return voltage, normF


if __name__ == "__main__":
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

    import time
    print('HELM-Z')
    start_time = time.time()
    cmax = 40
    V1, err = helmz(Vbus=circuit.power_flow_input.Vbus,
                    Sbus=circuit.power_flow_input.Sbus,
                    Ibus=circuit.power_flow_input.Ibus,
                    Ybus=circuit.power_flow_input.Yseries,
                    pq=circuit.power_flow_input.pq,
                    pv=circuit.power_flow_input.pv,
                    ref=circuit.power_flow_input.ref,
                    pqpv=circuit.power_flow_input.pqpv,
                    max_ter=cmax)

    print("--- %s seconds ---" % (time.time() - start_time))
    # print_coeffs(C, W, R, X, H)

    print('V module:\t', abs(V1))
    print('V angle: \t', angle(V1))
    print('error: \t', err)

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
