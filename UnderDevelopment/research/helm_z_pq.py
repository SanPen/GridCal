import numpy as np
np.set_printoptions(linewidth=320)
from numpy import zeros, ones, mod, conj, array, c_, r_, linalg, Inf, complex128
from itertools import product
from numpy.linalg import solve
from scipy.sparse.linalg import factorized
import pandas as pd
from scipy.sparse import issparse, csc_matrix as sparse

# Set the complex precision to use
complex_type = complex128


def make_z_i3(df_br, df_bus, df_gen, df_load):
    """
    Make the pseudo impedance matrix (where the voltage is known, the row contains a 1 at that node)
    :param df_br: Branches DataFrame
    :param df_bus: Buses DataFrame
    :param df_gen: Generators DataFrame
    :param df_load: Loads DataFrame
    :return:
    """

    # declare the length of the arrays
    nb = len(df_bus)
    ng = len(df_gen)
    nbr = len(df_br)
    nl = len(df_load)
    SBASE = 100

    # declare the arrays
    n = nb + 1  # number of buses plus the ground node
    z = np.zeros((n, n), dtype=complex)  # system matrix
    vnom = np.zeros(n, dtype=float)  # nominal voltages
    sinj = np.zeros(n, dtype=complex)  # power injections
    ii = np.zeros(n, dtype=complex)  # independent variables term

    # set the ground node
    z[0, 0] = complex(1)

    pqpv = list()
    vd = [0]

    # go through the buses and build the bus numbering dictionary
    bus_dict = dict()
    for i in range(nb):
        bus_dict[df_bus['name'].values[i]] = i + 1  # the +1 in the indices is to skip the ground node later
        vnom[i+1] = df_bus['Vnom'].values[i]  # the +1 in the indices is to skip the ground node
        z[i+1, i+1] = complex(0)  # the +1 in the indices is to skip the ground node
        pqpv.append(i+1)

    # include the branches
    for i in range(nbr):
        f = bus_dict[df_br['bus_from'].values[i]]
        t = bus_dict[df_br['bus_to'].values[i]]

        zz = df_br['R'].values[i] + 1j * df_br['X'].values[i]
        z[f, t] = -zz
        z[t, f] = -zz
        z[f, f] += zz
        z[t, t] += zz

    # include the voltage sources (slacks only where the full voltage is known)
    for i in range(ng):
        t = bus_dict[df_gen['bus'].values[i]]
        if bool(df_bus['is_slack'].values[t-1]):
            vd.append(t)
            pqpv.remove(t)  # remove by value, not by index
            row = np.zeros(n, dtype=complex)
            row[t] = 1
            z[t, :] = row  # substitute the row with an all-zero row but at t, t
            ii[t] = df_gen['Vset'].values[i]  # set the independent term to the node voltage

    # include the loads as linearized currents
    for i in range(nl):
        t = bus_dict[df_load['bus'].values[i]]
        sinj[t] = complex(df_load['S'].values[i]) / SBASE

    print('pqpv:', pqpv, '  vd:', vd)

    # Current injections by the slack and ground nodes
    # Dot product of the impedances of the slack nodes with the rest of the nodes Z[pqpv, vd], and the slack voltages
    i_vd = z[pqpv, :][:, vd].dot(ii[vd])

    # reduced impedance matrix
    z_red = z[pqpv, :][:, pqpv]

    return z_red, i_vd, sinj[pqpv], vnom[pqpv]


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
    Iref = Yserie[pqpv, :][:, ref].dot(Vbus[ref])

    nbus = len(Vbus)
    npqpv = len(pqpv)
    npq = len(pq)
    npv = len(pv)

    # factorize the Yseries matrix only once
    Yseries_pqpv = Yserie[pqpv, :][:, pqpv]
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

    # # evaluate F(x)
    # Scalc = voltage * conj(Ybus * voltage - Ibus)
    # mis = Scalc - Sbus  # complex power mismatch
    # F = r_[mis[pv].real, mis[pq].real, mis[pq].imag]  # concatenate again
    #
    # # check for convergence
    # normF = linalg.norm(F, Inf)
    #
    # return voltage, normF
    return 0, 0

if __name__ == '__main__':
    print('\nHelmZ:\n')

    fname = 'lynn5buspq.xlsx'

    # branch
    # name	bus_from	bus_to	is_enabled	rate	mttf	mttr	R	X	G	B
    branches_df = pd.read_excel(fname, 'branch')

    # bus
    # name	is_enabled	is_slack	Vnom	Vmin	Vmax	Zf	x	y
    bus_df = pd.read_excel(fname, 'bus')

    # Gen
    # name	bus	P	Vset	Snom	Qmin	Qmax
    gen_df = pd.read_excel(fname, 'controlled_generator')

    # Load
    # name	bus	Z	I	S
    load_df = pd.read_excel(fname, 'load')

    # make the impedance matrix
    Zred, Ivd, Sred, Vnom_red = make_z_i3(df_br=branches_df, df_bus=bus_df, df_gen=gen_df, df_load=load_df)

    print('Z:\n', Zred)
    print('Ivd:\n', Ivd)
    print('S:\n', Sred)