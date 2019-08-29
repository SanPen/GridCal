import numpy as np

np.set_printoptions(precision=6, suppress=True, linewidth=320)
from numpy import zeros, ones, mod, conj, complex128 #, complex256
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
def helm_z_pq(bus_voltages, complex_bus_powers, Ibus, Ybus, pq_bus_indices, pv_bus_indices, slack_bus_indices, pq_and_pv_bus_indices, tol=1e-9, max_ter=5):
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
    Zred = np.linalg.inv(Ybus[pq_and_pv_bus_indices, :][:, pq_and_pv_bus_indices]).toarray()

    # slack currents
    Ivd = -Ybus[pq_and_pv_bus_indices, :][:, slack_bus_indices].dot(bus_voltages[slack_bus_indices])

    # slack voltages influence
    Ck = Zred.dot(Ivd)

    npqpv = len(pq_and_pv_bus_indices)

    Vcoeff = zeros((0, npqpv), dtype=complex_type)
    Wcoeff = zeros((0, npqpv), dtype=complex_type)

    row = zeros((1, npqpv), dtype=complex_type)

    for n in range(max_ter):

        # reserve memory
        Vcoeff = np.r_[Vcoeff, row.copy()]
        Wcoeff = np.r_[Wcoeff, row.copy()]

        if n == 0:
            I = Ivd
        else:
            I = conj(complex_bus_powers[pq_and_pv_bus_indices]) * Wcoeff[n - 1, :]

        # solve the voltage coefficients
        Vcoeff[n, :] = reduced_impedance_matrix_Z.dot(I)

        # compute the inverse voltage coefficients
        Wcoeff[n, :] = calc_W(n=n, npqpv=npqpv, C=Vcoeff, W=Wcoeff)

    # compose the final voltage
    voltage = bus_voltages.copy()

    for i, ii in enumerate(pq_and_pv_bus_indices):
        voltage[ii], _, _ = pade_approximation(n, Vcoeff[:, i])

    # evaluate F(x)
    Scalc = voltage * conj(Ybus * voltage - Ibus)
    mis = Scalc - complex_bus_powers  # complex power mismatch
    normF = linalg.norm(np.r_[mis[pv_bus_indices].real, mis[pq_bus_indices].real, mis[pq_bus_indices].imag], Inf)

    print('Vcoeff:\n', Vcoeff)

    print('V:\n', abs(Vcoeff.sum(axis=0)))

    return voltage, normF
