"""
This helm version is implemented from the thesis of Muthu Subramanian

Implementation by Santiago Peñate Vera 2017
"""

import time
import numpy as np
np.set_printoptions(linewidth=320)
from numpy import zeros, ones, mod, conj, array, r_, linalg, Inf, complex128, c_, r_, angle
from itertools import product
from numpy.linalg import solve
from scipy.sparse.linalg import factorized
from scipy.sparse import issparse, csc_matrix as sparse
import pandas as pd

# Set the complex precision to use
complex_type = complex128


# @jit(cache=True)
def pre_process(n_bus, Yseries, Vset, pq, pv, vd):
    """
    Make the Helm System matrix
    @param n_bus: Number of buses of the circuit
    @param Yseries: Circuit admittance matrix of the series elements
    @param Vset: Vector of voltages of those nodes where the voltage is controlled (AKA Slack and PV buses)
    @param pq: list of PQ node indices
    @param pv: list of PV node indices
    @param vd: list of Slack node indices
    @return: 
    """
    npq = len(pq)
    npv = len(pv)
    nvd = len(vd)
    npqpv = npq + npv

    # now to have efficient arrays of coefficients, we create the array maps
    map_pqpv = zeros(n_bus, dtype=np.int)
    map_w = zeros(n_bus, dtype=np.int)
    map_pqpv[pq] = array(range(npq))
    map_pqpv[pv] = array(range(npv))
    map_w[r_[pq, pv]] = array(range(npqpv))

    # build the expanded system matrix
    Ysys = zeros((2*n_bus, 2*n_bus))

    # Yseries is a CRC sparse matrix, I pass it to coordinates to be able to vectorize the
    m = Yseries.tocoo()
    a = m.row
    b = m.col
    Ysys[2 * a, 2 * b] = m.data.real
    Ysys[2 * a, 2 * b + 1] = -m.data.imag
    Ysys[2 * a + 1, 2 * b] = m.data.imag
    Ysys[2 * a + 1, 2 * b + 1] = m.data.real

    # set pv columns
    Ysys[:, 2 * pv] = zeros((2 * n_bus, npv))
    Ysys[pv * 2 + 1, pv * 2] = ones(npv)

    # set vd elements
    Ysys[vd * 2, :] = zeros((nvd, 2 * n_bus))
    Ysys[vd * 2 + 1, :] = zeros((nvd, 2 * n_bus))
    Ysys[vd * 2, vd * 2] = ones(nvd)
    Ysys[vd * 2 + 1, vd * 2 + 1] = ones(nvd)

    # build the PV matrix
    Ysys_pv = zeros((2 * n_bus, npv))
    for a, b in product(r_[pq, pv], pv):
        kk = map_pqpv[b]
        Ysys_pv[2 * a, kk] = Yseries[a, b].real
        Ysys_pv[2 * a + 1, kk] = Yseries[a, b].imag

    # compute the voltage squared array
    Vset2 = Vset * Vset

    return sparse(Ysys), Ysys_pv, Vset2, map_pqpv, map_w, npq, npv, nvd


def RHS(n, nbus, npq, npv, nvd, Ysh, Ysys_pv, S, Vset, Vset_abs2, C, W, Q, pq, pv, vd, map_pv, map_w):
    """
    Compute the right hand side vector to solve the voltage and reactive power coefficients using the
    factorization of Ysys
    @param n: Order of the coefficients
    @param nbus: Number of buses (not counting the slack buses)
    @param npq: number of PQ nodes
    @param npv: number of PV nodes
    @param nvd: number of slack nodes
    @param Ysh: Vector of the shunt admittance matrix elements
    @param Ysys_pv: System matrix of the PV nodes: Needed to compute the real voltages vector
    @param S: Vector of power injections (nbus elements)
    @param Vset: Vector of set voltages
    @param Vset_abs2: Vector with the voltage set points squared. (nbus elements)
    @param C: Voltage coefficients (Ncoeff x nbus elements)
    @param W: Inverse coefficients structure (Ncoeff x nbus elements)
    @param Q: Reactive power coefficients (Ncoeff x nbus elements)
    @param pq: array of PQ indices
    @param pv: array of PV indices
    @param vd: array of Slack indices
    @param map_pv: map to the indices of the PV dependent structures
    @param map_w: map to the indices of the W structure
    @return: Right hand side vector to solve the coefficients (2 * nbus elements)
    """

    rhs = np.empty(2 * nbus)  # right hand side to solve the system matrix of coefficients
    Vre = ones(npv)  # real voltage vector

    # RHS for the PQ nodes (Vectorized)
    val = RHS_PQ(n, npq, pq, Ysh, C, S, W, map_w)
    rhs[2 * pq] = val.real
    rhs[2 * pq + 1] = val.imag

    # RHS for the VD (Slack) nodes (Vectorized)
    val = RHS_VD(n, nvd, vd, Vset)
    rhs[2 * vd] = val.real
    rhs[2 * vd + 1] = val.imag

    # RHS for the PV nodes (Vectorized)
    val = RHS_PV(n, npv, pv, Ysh, S, C, Q, W, map_pv, map_w)
    rhs[2 * pv] = val.real
    rhs[2 * pv + 1] = val.imag

    # correct RHS with the real part of the voltage in the PV nodes (Vectorized)
    kk = map_pv[pv]
    Vre[kk] = calc_Vre(n, npv, pv, C, Vset_abs2).real
    rhs -= Ysys_pv[:, kk].dot(Vre[kk])

    return rhs, Vre


def delta(n, k):
    return n == k  # is 1 for n==k, 0 otherwise


def RHS_VD(n, nvd, vd, Vset):
    """
    Right hand side calculation for the VD (Slack) nodes.
    @param n: Order of the coefficients
    @param nvd: number of slack nodes
    @param vd: array of Slack indices
    @param Vset: set voltage of the nodes
    @return: Right hand side value for slack nodes
    """

    o1 = ones(nvd, dtype=complex_type)
    if n == 0:
        return o1
    else:
        return (Vset[vd] - o1) * delta(n, 1)


def RHS_PQ(n, npq, pq, Ysh, C, S, W, map_w):
    """
    Right hand side calculation for the PQ nodes.
    @param n: Order of the coefficients
    @param npq: number of PQ nodes
    @param pq: array of PQ indices
    @param Ysh: Vector where every elements the sum of the corresponding row of the reduced admittance matrix)
    @param C: Voltage coefficients (Ncoeff x nbus elements)
    @param S: Vector of power injections (nbus elements)
    @param W: Inverse coefficients structure (Ncoeff x nbus elements)
    @param map_w: map to the indices of the W structure
    @return: Right hand side value for the PQ nodes
    """
    if n == 0:
        return zeros(npq)
    else:
        kw = map_w[pq]
        return conj(S[pq]) * conj(W[n - 1, kw]) - Ysh[pq] * C[n - 1, pq]  # ASU version


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


def RHS_PV(n, npv, pv, Ysh, S, C, Q, W, map_pv, map_w):
    """
    Right hand side for the PV nodes
    @param n: Order of the coefficients
    @param npv:
    @param pv: array of PV indices
    @param Ysh: Vector where every elements the sum of the corresponding row of the shunt admittance matrix
    @param S: Vector of power injections (nbus elements)
    @param C: Voltage coefficients (Ncoeff x nbus elements)
    @param Q: Reactive power coefficients (Ncoeff x nbus elements)
    @param W: Inverse coefficients structure (Ncoeff x nbus elements)
    @param map_pv: map to the indices of the PV dependent structures
    @param map_w: map to the indices of the W structure
    @return: Right hand side value for the pv nodes
    """

    if n == 0:
        return zeros(npv, dtype=complex_type)  # -1j * Q[0, kk] / conj(C[0, k])

    else:
        kk = map_pv[pv]
        kw = map_w[pv]

        # val = zeros(npv, dtype=complex_type)
        # for l in range(1, n):   # this includes the n-1
        #     val += Q[l, kk] * W[n-l, kw].conjugate()

        if n > 1:
            l = array(range(1, n))
            val = (Q[:, kk][l, :] * W[:, kw][n-l, :].conjugate()).sum(axis=0)
        else:
            val = zeros(npv, dtype=complex_type)

        n1 = n-1
        rhs = S[pv].real * W[n1, kw].conjugate() - (1j * val) - Ysh[pv] * C[n1, pv]

    return rhs


def calc_Vre(n, npv, pv, C, Vset_abs2):
    """
    Compute the real part of the voltage for PV nodes
    @param n: Order of the coefficients
    @param npv: number of PV nodes
    @param pv: array of PV indices
    @param C: Voltage coefficients (Ncoeff x nbus elements)
    @param Vset_abs2: Vector with the voltage set points squared. (nbus elements)
    @return: Real part of the voltage for the PV nodes
    """
    if n == 0:
        return ones(npv, dtype=complex_type)
    elif n == 1:
        return 0.5 * (Vset_abs2[pv] - 1) - 0.5 * calc_R(n, pv, C)
    else:
        return zeros(npv, dtype=complex_type)


def calc_R(n, pv, C):
    """
    Voltage convolution coefficients for the PV nodes
    @param n: Order of the coefficients
    @param pv: array of PV indices
    @param C: Voltage coefficients (Ncoeff x nbus elements)
    @return: Convolution coefficient of order n for the bus k
    """

    # result = zeros(npv, dtype=complex_type)
    # for l in range(n+1):
    #     result += C[l, pv] * C[n - l, pv].conjugate()

    l = array(range(n+1))
    result = (C[:, pv][l, :] * C[:, pv][n - l, :].conjugate()).sum(axis=0)

    return result


def epsilon(Sn, n, E):
    """
    Fast recursive Wynn's epsilon algorithm from:
        NONLINEAR SEQUENCE TRANSFORMATIONS FOR THE ACCELERATION OF CONVERGENCE
        AND THE SUMMATION OF DIVERGENT SERIES

        by Ernst Joachim Weniger
    Args:
        Sn: sum of coefficients
        n: order
        E: Coefficients structure copy that is modified in this algorithm

    Returns:

    """
    Zero = complex_type(0)
    One = complex_type(1)
    Tiny = np.finfo(complex_type).min
    Huge = np.finfo(complex_type).max

    E[n] = Sn

    if n == 0:
        estim = Sn
    else:
        AUX2 = Zero

        for j in range(n, 0, -1):  # range from n to 1 (both included)
            AUX1 = AUX2
            AUX2 = E[j-1]
            DIFF = E[j] - AUX2

            if abs(DIFF) <= Tiny:
                E[j-1] = Huge
            else:
                if DIFF == 0:
                    DIFF = Tiny
                E[j-1] = AUX1 + One / DIFF

        if mod(n, 2) == 0:
            estim = E[0]
        else:
            estim = E[1]

    return estim, E


def epsilonV(nbus, Sn, n, E):
    """
    Fast recursive Wynn's epsilon algorithm from:
        NONLINEAR SEQUENCE TRANSFORMATIONS FOR THE ACCELERATION OF CONVERGENCE
        AND THE SUMMATION OF DIVERGENT SERIES

        by Ernst Joachim Weniger
    Args:
        Sn: sum of coefficients (Vector)
        n: order
        E: Coefficients structure copy that is modified in this algorithm (Matrix)

    Returns:

    """
    Zero = zeros(nbus, dtype=complex_type)
    One = ones(nbus, dtype=complex_type)
    Tiny = np.finfo(complex_type).min
    Huge = np.finfo(complex_type).max

    E[n, :] = Sn

    if n == 0:
        estim = Sn
    else:
        AUX2 = Zero

        for j in range(n, 0, -1):  # range from n to 1 (both included)
            AUX1 = AUX2
            AUX2 = E[j-1, :]
            DIFF = E[j, :] - AUX2

            where_tiny = np.where(DIFF <= Tiny)[0]
            where_zero = np.where(DIFF == Zero)[0]

            if len(where_tiny) > 0:
                E[j-1, where_tiny] = Huge
            else:
                if len(where_zero) > 0:
                    DIFF[where_zero] = Tiny
                E[j-1, :] = AUX1 + One / DIFF

        if mod(n, 2) == 0:
            estim = E[0, :]
        else:
            estim = E[1, :]

    return estim, E


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


def interprete_solution(nbus, npv, pv, pqvd, x_sol, Vre, map_pv):
    """
    Assign the solution vector individual values to the correct places
    @param nbus: number of system nodes
    @param npv: number of pv nodes
    @param pv: array of PV node indices
    @param pqvd: array of PQ and Slack node indices
    @param x_sol: solution vector to analyze
    @param Vre: Vector or real part of the voltage for the PV nodes
    @param map_pv: mapping array from normal bus index to PV index
    @return: Voltages coefficients and reactive power coefficients for the PV nodes at the order of x_sol
    """
    C = zeros(nbus, dtype=complex_type)
    Q = zeros(npv)

    # set the PQ and Slack nodes
    C[pqvd] = x_sol[2 * pqvd] + 1j * x_sol[2 * pqvd + 1]

    # Set the PV nodes
    kk = map_pv[pv]
    Q[kk] = x_sol[2 * pv]
    C[pv] = Vre[kk] + 1j * x_sol[2 * pv + 1]

    return C, Q


def helm(Y, Ys, Ysh, max_coefficient_count, S, voltage_set_points, pq, pv, vd, eps=1e-3, use_pade=False):
    """
    Run the holomorphic embedding power flow
    @param Y: Circuit complete admittance matrix
    @param Ys: Circuit series elements admittance matrix
    @param Ysh: Circuit shunt elements admittance matrix
    @param max_coefficient_count: Maximum number of voltage coefficients to evaluate (Must be an odd number)
    @param S: Array of power injections matching the admittance matrix size
    @param voltage_set_points: Array of voltage set points matching the admittance matrix size
    @param pq: list of PQ node indices
    @param pv: list of PV node indices
    @param vd: list of Slack node indices
    @param eps: Tolerance
    @param use_pade: Use the Padè approximation? If False the Epsilon algorithm is used
    @return:
        Vred_last: voltage solution
        converged: Converged? True/False
        normF: Solution error
        Scalc: Power computed from the voltage solution
    """

    start = time.time()

    # number of nodes
    nbus = np.shape(Ys)[0]

    # The routines in this script are meant to handle sparse matrices, hence non-sparse ones are not allowed
    assert(issparse(Ys))

    # Make bus type lists combinations that are going to be used later
    pqvd = r_[pq, vd]
    pqvd.sort()
    pqpv = r_[pq, pv]
    pqpv.sort()

    # prepare the arrays
    Ysys, Ypv, Vset, map_pv, map_w, npq, npv, nvd = pre_process(n_bus=nbus, Yseries=Ys, Vset=voltage_set_points,
                                                                pq=pq, pv=pv, vd=vd)
    npqpv = npq + npv

    # declare the matrix of coefficients that will lead to the voltage computation
    C = zeros((0, nbus), dtype=complex_type)

    # auxiliary array for the epsilon algorithm
    E_v = zeros((0, nbus), dtype=complex_type)
    E_q = zeros((0, npv), dtype=complex_type)

    # Declare the inverse coefficients vector
    # (it is actually a matrix; a vector of coefficients per coefficient order)
    W = zeros((0, npq+npv), dtype=complex_type)

    # Reactive power on the PV nodes
    Q = zeros((0, npv), dtype=complex_type)

    # Squared values of the voltage module for the buses that are not of slack type
    Vset_abs2 = abs(voltage_set_points) ** 2

    # progressive calculation of coefficients
    n = 0
    converged = False
    inside_precision = True
    error = list()
    errors_PV_P = list()
    errors_PV_Q = list()
    errors_PQ_P= list()
    errors_PQ_Q = list()
    voltages = list()
    Sn_v = zeros(nbus, dtype=complex_type)
    Sn_q = zeros(npv, dtype=complex_type)
    voltages_vector = zeros(nbus, dtype=complex_type)
    Vred_last = zeros(nbus, dtype=complex_type)

    # LU factorization of the system matrix (Only needed once)
    solve = factorized(Ysys)

    # set the slack indices voltages
    voltages_vector[vd] = voltage_set_points[vd]

    while n <= max_coefficient_count and not converged and inside_precision:

        # Reserve coefficients memory space
        C = np.vstack((C, np.zeros((1, nbus), dtype=complex_type)))
        E_v = np.vstack((E_v, np.zeros((1, nbus), dtype=complex_type)))
        E_q = np.vstack((E_q, np.zeros((1, npv))))
        W = np.vstack((W, np.zeros((1, npq+npv), dtype=complex_type)))
        Q = np.vstack((Q, np.zeros((1, npv), dtype=complex_type)))

        # get the system independent term to solve the coefficients
        rhs, Vre = RHS(n, nbus, npq, npv, nvd, Ysh, Ypv, S, Vset, Vset_abs2, C, W, Q, pq, pv, vd, map_pv, map_w)

        # Solve the linear system to obtain the new coefficients
        x_sol = solve(rhs)

        # assign the voltages and the reactive power values correctly
        C[n, :], Q[n, :] = interprete_solution(nbus, npv, pv, pqvd, x_sol, Vre, map_pv)

        # copy variables for the epsilon algorithm
        if not use_pade:
            E_v[n, :] = C[n, :]
            E_q[n, :] = Q[n, :]
            Sn_v += C[n, :]
            Sn_q += Q[n, :]

        # Update the inverse voltage coefficients W for the non slack nodes (Vectorized)
        kw = map_w[pqpv]  # actual index in the coefficients structure
        W[n, kw] = calc_W(n, npqpv, pqpv, kw, C, W)

        # calculate the reactive power
        for k in pv:
            kk = map_pv[k]
            if use_pade:
                if mod(n, 2) == 0 and n > 2:
                    q, _, _ = pade_approximation(n, Q)
                    S[k] = S[k].real + 1j * q.real
            else:
                q, E_q[:, kk] = epsilon(Sn_q[kk], n, E_q[:, kk])
                S[k] = S[k].real + 1j * q

        # calculate the voltages
        for k in pqpv:
            if use_pade:
                if mod(n, 2) == 0 and n > 2:
                    v, _, _ = pade_approximation(n, C[:, k])
                    voltages_vector[k] = v
            else:
                # pass
                voltages_vector[k], E_v[:, k] = epsilon(Sn_v[k], n, E_v[:, k])

            if np.isnan(voltages_vector[k]):
                print('Maximum precision reached at ', n)
                voltages_vector = Vred_last
                inside_precision = False
                break

        # voltages_vector, E_v = epsilonV(nbus, Sn_v, n, E_v)

        # copy the voltages array to keep the last solution in case we encounter NaN's due to loss of precision
        Vred_last = voltages_vector.copy()

        # Compose the voltage values from the coefficient series
        voltages.append(voltages_vector.copy())

        # Calculate the error and check the convergence
        Scalc = voltages_vector * conj(Y * voltages_vector)
        # complex power mismatch
        power_mismatch = Scalc - S
        # concatenate error by type
        mismatch = r_[power_mismatch[pv].real, power_mismatch[pq].real, power_mismatch[pq].imag]

        # check for convergence
        normF = linalg.norm(mismatch, Inf)

        if npv > 0:
            a = linalg.norm(mismatch[pv].real, Inf)
        else:
            a = 0
        b = linalg.norm(mismatch[pq].real, Inf)
        c = linalg.norm(mismatch[pq].imag, Inf)
        error.append([a, b, c])

        if normF < eps:
            converged = True
        else:
            converged = False

        n += 1  # increase the coefficients order

    # errors_lst = [array(errors), array(errors_PV_P), array(errors_PV_Q), array(errors_PQ_P), array(errors_PQ_Q)]

    end = time.time()
    elapsed = end - start

    err_df = pd.DataFrame(array(error), columns=['PV_real', 'PQ_real', 'PQ_imag'])
    err_df.plot(logy=True)
    print('Err df:\n', err_df)

    return Vred_last, normF


def bifurcation_point(C, pqpv):
    """
    Computes the bifurcation point by solving the Padè approximation for other values of alpha (loading)
    @param C: voltage coefficients structure
    @param pqpv: array of PQ and PV nodes
    @return: Voltage collapse curves and the matching loading values
    """
    npoints = 100
    order_num, bus_num = np.shape(C)

    V = zeros((npoints, bus_num), dtype=complex_type)
    L = zeros((npoints, bus_num))
    for k in pqpv:

        # get the padè approximation polynomials
        _, p, q = pade_approximation(order_num, C[:, k])

        # compute the asymptotes to compute the voltage from zero to the first asymptote
        asymptotes = np.roots(q[::-1])
        asymptotes = np.sort(abs(asymptotes))
        asymptotes = asymptotes[asymptotes > 2]
        print('Asymptotes', asymptotes)

        # the bifurcation point is the first asymptote (in theory, with infinite numerical precision...)
        bifurc_pt = asymptotes[0]

        # compute a number of loading values to evaluate P(alpha) and Q(alpha)
        alpha = np.linspace(1, bifurc_pt, npoints+1)[:-1]

        # Evaluate the p and q polynomials at the computed loading points
        pval = np.polyval(p[::-1], alpha)
        qval = np.polyval(q[::-1], alpha)

        # Compute the voltage: V(alpha) = P(alpha)/Q(alpha)
        V[:, k] = pval / qval
        L[:, k] = alpha

    return V, L


def res_2_df(V, Sbus, tpe):
    """
    Create dataframe to display the results nicely
    :param V: Voltage complex vector
    :param Sbus: Power complex vector
    :param tpe: Types
    :return: Pandas DataFrame
    """
    vm = abs(V)
    va = np.angle(V)

    d = {1: 'PQ', 2: 'PV', 3: 'VD'}

    tpe_str = array([d[i] for i in tpe], dtype=object)
    data = c_[tpe_str, Sbus.real, Sbus.imag, vm, va]
    cols = ['Type', 'P', 'Q', '|V|', 'angle']
    df = pd.DataFrame(data=data, columns=cols)

    return df


if __name__ == '__main__':
    from GridCal.Engine.calculation_engine import MultiCircuit, PowerFlowOptions, PowerFlow, SolverType
    from matplotlib import pyplot as plt

    grid = MultiCircuit()
    # grid.load_file('lynn5buspq.xlsx')
    # grid.load_file('lynn5buspv.xlsx')
    # grid.load_file('IEEE30.xlsx')
    grid.load_file('/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE 14.xlsx')
    # grid.load_file('/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE39.xlsx')
    # grid.load_file('/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/1354 Pegase.xlsx')

    grid.compile()

    circuit = grid.circuits[0]

    print('\nYbus:\n', circuit.power_flow_input.Ybus.todense())
    print('\nSbus:\n', circuit.power_flow_input.Sbus)
    print('\nIbus:\n', circuit.power_flow_input.Ibus)
    print('\nVbus:\n', circuit.power_flow_input.Vbus)
    print('\ntypes:\n', circuit.power_flow_input.types)
    print('\npq:\n', circuit.power_flow_input.pq)
    print('\npv:\n', circuit.power_flow_input.pv)
    print('\nvd:\n', circuit.power_flow_input.ref)

    start_time = time.time()

    # Y, Ys, Ysh, max_coefficient_count, S, voltage_set_points, pq, pv, vd
    v, err = helm(Y=circuit.power_flow_input.Ybus,
                  Ys=circuit.power_flow_input.Yseries,
                  Ysh=circuit.power_flow_input.Yshunt,
                  max_coefficient_count=30,
                  S=circuit.power_flow_input.Sbus,
                  voltage_set_points=circuit.power_flow_input.Vbus,
                  pq=circuit.power_flow_input.pq,
                  pv=circuit.power_flow_input.pv,
                  vd=circuit.power_flow_input.ref,
                  eps=1e-15)

    print('HEM:')
    print("--- %s seconds ---" % (time.time() - start_time))
    print('Results:\n', res_2_df(v, circuit.power_flow_input.Sbus, circuit.power_flow_input.types))
    print('error: \t', err)

    # check the HELM solution: v against the NR power flow
    print('\nNR')
    options = PowerFlowOptions(SolverType.NR, verbose=False, robust=False, tolerance=1e-9, control_q=False)
    power_flow = PowerFlow(grid, options)

    start_time = time.time()
    power_flow.run()
    print("--- %s seconds ---" % (time.time() - start_time))
    vnr = circuit.power_flow_results.voltage

    print('Results:\n', res_2_df(vnr, circuit.power_flow_input.Sbus, circuit.power_flow_input.types))
    print('error: \t', circuit.power_flow_results.error)

    # check
    print('\ndiff:\t', v - vnr)

    plt.show()
