import numpy as np

np.set_printoptions(linewidth=320)
from numpy import zeros, ones, mod, conj, r_, linalg, Inf, complex128
from numpy.linalg import solve
from scipy.sparse.linalg import factorized

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


def helm_pq(
    *,
    bus_voltages, complex_bus_powers, Ibus, bus_admittances, series_admittances, shunt_admittances, pq_bus_indices, pv_bus_indices, slack_bus_indices, pq_and_pv_bus_indices, tolerance=1e-9
):
    """
    :param bus_voltages:
    :param complex_bus_powers:
    :param Ibus:
    :param bus_admittances:
    :param series_admittances:
    :param shunt_admittances:
    :param pq_bus_indices:
    :param pv_bus_indices:
    :param slack_bus_indices:
    :param pq_and_pv_bus_indices:
    :param tolerance:

    :param bus_voltages: List of bus voltages
    :param complex_bus_powers: List of power injections/extractions
    :param bus_admittances: Bus admittance matrix
    :param pq_bus_indices: list of pq node indices
    :param pv_bus_indices: list of pv node indices
    :param slack_bus_indices: list of slack node indices
    :param pq_and_pv_bus_indices: list of pq and pv node indices sorted
    :param tolerance: tolerance

    Returns:
    """

    # compose the slack nodes influence current
    Yslack = series_admittances[pq_and_pv_bus_indices, :][:, slack_bus_indices]
    Iref = Yslack.dot(bus_voltages[slack_bus_indices])

    nbus = len(bus_voltages)
    npqpv = len(pq_and_pv_bus_indices)
    npq = len(pq_bus_indices)
    npv = len(pv_bus_indices)

    # factorize the Yseries matrix only once
    Yseries_pqpv = series_admittances[pq_and_pv_bus_indices, :][:, pq_and_pv_bus_indices]
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

    while coeff_tol > tolerance:
        # add coefficients row
        Vcoeff = r_[Vcoeff, np.zeros((1, npqpv), dtype=complex_type)]
        Wcoeff = r_[Wcoeff, np.zeros((1, npqpv), dtype=complex_type)]

        if n == 0:
            RHS = Ibus[pq_and_pv_bus_indices] - Iref
        else:
            RHS = complex_bus_powers[pq_and_pv_bus_indices].conj() * Wcoeff[n - 1, :] + shunt_admittances[pq_and_pv_bus_indices] * Vcoeff[n - 1, :]

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
    voltage = bus_voltages
    # voltage[pqpv] = Vcoeff.sum(axis=0)

    for i, ii in enumerate(pq_and_pv_bus_indices):
        voltage[ii], _, _ = pade_approximation(n, Vcoeff[:, i])
        # voltage[ii] = continued_fraction(Vcoeff[:, i])

    print('\nVcoeff:\n', Vcoeff)

    # evaluate F(x)
    Scalc = voltage * conj(bus_admittances * voltage - Ibus)
    mis = Scalc - complex_bus_powers  # complex power mismatch
    F = r_[mis[pv_bus_indices].real, mis[pq_bus_indices].real, mis[pq_bus_indices].imag]  # concatenate again

    # check for convergence
    normF = linalg.norm(F, Inf)

    return voltage, normF
