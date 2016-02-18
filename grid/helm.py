import numpy as np
from numpy import where, zeros, ones, mod, conj, array, dot, complex128
from numpy import poly1d, r_, eye, hstack, diag, linalg, Inf

from itertools import product

from scipy import fftpack
from scipy.linalg import solve

from scipy.sparse.linalg import factorized, spsolve
from scipy.sparse import issparse, csr_matrix as sparse

# just in time compiler
from numba import jit

# Set the complex precision to use
complex_type = complex128

# @jit(cache=True)
def pre_process(n_bus, Ymat, slack_indices, Vset, S, types):
    """
    Reduction of the circuit magnitudes.

    Args:
        n_bus: Number of buses of the circuit

        Ymat: Circuit admittance matrix

        slack_indices: Array of indices of the slack nodes

        Vset: Vector of voltages of those nodes where the voltage is controlled (AKA Slack and PV buses)

        S: Vector of power injections at all the nodes

        types: Vector of nde types

    Output:
        Yred: Reduced admittance matrix (Without the rows and columns belonging to slack buses)

        I: Matrix of currents (In practice only one slack bus is selected, hence it is a vector) injected by the slack buses

        Sred: Array of power injections of the buses that are not of type slack

        types_red: Array of types of the buses that are not of type slack

        non_slack_indices: Array of indices of the buses that are not of type slack
    """

    # Compose the list of buses indices excluding the indices of the slack buses
    non_slack_indices = list(range(n_bus))
    for i in slack_indices[::-1]:
        non_slack_indices.pop(i)
    non_slack_indices = array(non_slack_indices)

    # Types of the non slack buses
    # types_red = types[non_slack_indices]

    # now to have efficient arrays of coefficients
    map_idx = zeros(len(types), dtype=np.int)
    map_w = zeros(len(types), dtype=np.int)
    npq = 0
    npv = 0
    npqpv = 0

    pq = where(types == 1)[0]
    pv = where(types == 2)[0]
    vd = where(types == 3)[0]

    for i in range(len(types)):
        if types[i] == 1:  # PQ
            map_idx[i] = npq
            map_w[i] = npqpv
            npq += 1
            npqpv += 1
        elif types[i] == 2:  # PV
            map_idx[i] = npv
            map_w[i] = npqpv
            npv += 1
            npqpv += 1

    # correction factor
    F = np.ndarray.flatten(Ymat * ones(n_bus, dtype=complex_type)) * 2

    # create the modified admittance matrix (Ytrans)
    Ytrans = Ymat.copy() - np.diag(F/2)

    # print(types)

    # build the expanded system reduced matrix
    Ysys = zeros((2*n_bus, 2*n_bus))

    for a,b in product(range(n_bus), range(n_bus)):
        Ysys[2*a, 2*b] = Ytrans[a, b].real
        Ysys[2*a, 2*b+1] = -Ytrans[a, b].imag
        Ysys[2*a+1, 2*b] = Ytrans[a, b].imag
        Ysys[2*a+1, 2*b+1] = Ytrans[a, b].real
    # print('Ymat\n', Ytrans)
    # print('Ysys\n', Ysys)

    # set pv column
    for a in pv:
        b = a
        Ysys[:, 2*b] = zeros(2 * n_bus)
        # Ysys[a*2, b*2+1] = 0
        Ysys[a*2+1, b*2] = 1

    # set vd elements
    for a in vd:
        Ysys[a*2, :] = zeros(2 * n_bus)
        Ysys[a*2 + 1, :] = zeros(2 * n_bus)
        Ysys[a*2, a*2] = 1
        Ysys[a*2+1, a*2+1] = 1
    # print('Ysys\n', Ysys)

    # build the PV matrix
    Ypv = zeros((2 * n_bus, npv))
    for a, b in product(r_[pq, pv], pv):
        kk = map_idx[b]
        Ypv[2*a, kk] = Ytrans[a, b].real
        Ypv[2*a+1, kk] = Ytrans[a, b].imag
    # print('Ypv\n', Ypv)


    Vset2 = Vset.copy()

    S2 = S.copy()

    return Ysys, Ypv, F, types, Vset2, S2, non_slack_indices, map_idx, map_w, npq, npv, pv, pq

@jit(cache=True)
def RHS(n, nbus, pv, F, Ypv, S, Vset, Vset_abs2, C, W, Q, types, map_idx, map_w, useFFT):
    """
    Right hand side calculation.

    Args:
        n: Order of the coefficients

        nbus: Number of buses (not counting the slack buses)

        Yrow: Vector where every elements the sum of the corresponding row of the reduced admittance matrix)

        I: Vector of current injections (nbus elements)

        S: Vector of power injections (nbus elements)

        Vset: Vector of set voltages

        Vset_abs2: Vetor with the voltage set points squared. (nbus elements)

        C: Voltage coefficients (Ncoeff x nbus elements)

        X: Weighted coefficients (Ncoeff x nbus elements)

        R: Voltage convolution coefficients (Ncoeff x nbus elements)

        W: Inverse coefficients structure (Ncoeff x nbus elements)

        types: Types of the non slack buses (nbus elements)

    Output:
        rhs: Right hand side vector to solve the coefficients (2 * nbus elements)
    """

    rhs = np.empty(2 * nbus)

    # print('\n\n n = ', n)

    for k in range(nbus):

        if types[k] == 1:  # PQ
            val = RHS_PQ(n, k, F, C, S, W, map_w)
            # print("RHS_PQ("+str(k) + ", " + str(n) + ")" + str(val))
        elif types[k] == 2:  # PV
            val = RHS_PV(n, k, F, S, C, Q, W, map_idx, map_w, useFFT)
            # print("RHS_PV("+str(k) + ", " + str(n) + ")" + str(val))
        elif types[k] == 3:  # VD
            val = RHS_VD(n, k, Vset)
            # print("RHS_PVD("+str(k) + ", " + str(n) + ")" + str(val))

        rhs[2 * k] = val.real
        rhs[2 * k + 1] = val.imag

    Vre = ones(len(pv))
    # if n>0:
    for k in pv:
        kk = map_idx[k]
        Vre[kk] = calc_Vre(n, k, C, Vset_abs2, useFFT).real
        rhs -= Ypv[:, kk] * Vre[kk]
    # print('vre[' + str(n) + '] = ' + str(Vre))

    return rhs, Vre


def delta(n, k):
    return n == k # is 1 for n==k, 0 otherwise


@jit(cache=True)
def RHS_VD(n, k, Vset):
    """
    Right hand side calculation for a PQ bus.

    Args:
        n: Order of the coefficients

        k: Index of the bus

        Vset: set voltage of the node
    Output:
        Right hand side value for slack nodes
    """
    if n==0:
        return complex_type(1) * delta(n, 0)
    else:
        return (Vset[k] - complex_type(1)) * delta(n, 1)


@jit(cache=True)
def RHS_PQ(n, k, F, C, S, W, map_w):
    """
    Right hand side calculation for a PQ bus.

    Args:
        n: Order of the coefficients

        k: Index of the bus

        F: Vector where every elements the sum of the corresponding row of the reduced admittance matrix)

        I: Vector of current injections (nbus elements)

        S: Vector of power injections (nbus elements)

        W: Inverse coefficients structure (Ncoeff x nbus elements)
    Output:
        Right hand side value
    """
    if n == 0:
        return 0

    else:
        kw = map_w[k]
        return conj(S[k]) * conj(W[n-1, kw]) - F[k] * C[n-1, k]  # ASU version


@jit(cache=True)
def calc_W(n, k, kw, C, W, map_idx, useFFT):
    """
    Calculation of the inverse coefficients W. (only applicable for PQ buses)

    Args:
        n: Order of the coefficients

        k: Index of the bus

        C: Voltage coefficients (Ncoeff x nbus elements)

        W: Inverse coefficients structure (Ncoeff x nbus elements)

    Output:
        Inverse coefficient of order n for the bus k
    """

    # if n == 0:
    #     res = complex_type(1)
    # else:
    #     res = complex_type(0)
    #     kk = map_idx[k]
    #     for l in range(n):
    #         res -= W[l, kk] * conj(C[n-l, k])
    #
    # res /= conj(C[0, k])

    if n == 0:
        res = complex_type(1)
    else:
        # kk = map_idx[k]

        if useFFT:
            a = fftpack.fft(W[:, kw])
            b = fftpack.fft(conj(C[:, k]))
            c = a * b
            e = fftpack.ifft(c)
            res = -e[n]
        else:
            res = complex_type(0)
            for l in range(n):
                res -= W[l, kw] * C[n-l, k]
                # print('### W['+str(l)+',' + str(k)+'] * V[' + str(n-l) + ',' + str(k) + '] = ' + str(W[l, kw] * C[n-l, k]))

    res /= conj(C[0, k])

    # print('# W[' + str(n)+',' + str(k)+'] = ' + str(res))

    return res


@jit(cache=True)
def RHS_PV(n, k, F, S, C, Q, W, map_idx, map_w, useFFT):
    """
    Right hand side calculation for a PQ bus.

    Args:
        n: Order of the coefficients

        k: Index of the bus

        F: Vector where every elements the sum of the corresponding row of the reduced admittance matrix)

        I: Vector of current injections (nbus elements)

        S: Vector of power injections (nbus elements)

        Vset_abs2: Vector with the voltage set points squared. (nbus elements)

        C: Voltage coefficients (Ncoeff x nbus elements)

        X: Weighted coefficients (Ncoeff x nbus elements)

        R: Voltage convolution coefficients (Ncoeff x nbus elements)

        W: Inverse coefficients structure (Ncoeff x nbus elements)
    Output:
        Right hand side value
    """
    kk = map_idx[k]
    if n == 0:
        return 0  # -1j * Q[0, kk] / conj(C[0, k])

    else:
        kw = map_w[k]
        # qw = calc_QW(n, k, kk, kw, Q, W, useFFT)
        # rhs = S[k].real * conj(W[n-1, kw]) - 1j * qw - F[k] * C[n-1, k]


        val = complex_type(0)
        for l in range(1, n):   # this includes the n-1
            val += Q[l, kk] * W[n-l, kw].conjugate()

        P = S[k].real
        n1 = n-1
        rhs = P * W[n1, kw].conjugate() - (1j * val) - F[k] * C[n1, k]

    return rhs


@jit(cache=True)
def calc_Vre(n, k, C, Vset_abs2, useFFT):
    """
    Compute the real part of the voltage for PV ndes
    Args:
        n: order
        k: PV node index
        Vset_abs2: Square of the set voltage module
        R: Vo
        map_idx: Voltage convolutions

    Returns:
        Real part of the voltage for the PV nodes

    """
    R = calc_R(n, k, C, useFFT)
    vre = delta(n, 0) + 0.5 * delta(n, 1) * (Vset_abs2[k] - 1) - 0.5 * R
    return vre


@jit(cache=True)
def calc_R(n, k, C, useFFT):
    """
    Convolution coefficient

    Args:
        n: Order of the coefficients

        k: Index of the bus

        C: Voltage coefficients (Ncoeff x nbus elements)

    Output:
        Convolution coefficient of order n for the bus k
    """

    if useFFT:
        a = fftpack.fft(C[:, k])
        e = fftpack.ifft(a * a.conjugate())
        # e = fftpack.ifft(a * a)
        result = e[n]
    else:
        result = complex_type(0)
        for l in range(n+1):
            result += C[l, k] * C[n-l, k].conjugate()

    return result


@jit(cache=True)
def calc_QW(n, k, kk, kw,  Q, W, useFFT):
    """
    Convolution coefficient

    Args:
        n: Order of the coefficients

        k: Index of the bus

        C: Voltage coefficients (Ncoeff x nbus elements)

    Output:
        Convolution coefficient of order n for the bus k
    """

    if useFFT:
        a = fftpack.fft(Q[:, kk])
        b = fftpack.fft(conj(W[:, kw]))
        e = fftpack.ifft(a * b)
        result = e[n]
    else:
        result = complex_type(0)
        for l in range(n):
            result += Q[l, kk] * conj(W[n-l, kw])

    return result


@jit(cache=True)
def epsilon(Sn, n, E):
    """
    Fast recursive Wynn's epsilon algorithm from:
        NONLINEAR SEQUENCE TRANSFORMATIONS FOR THE ACCELERATION OF CONVERGENCE
        AND THE SUMMATION OF DIVERGENT SERIES

        by Ernst Joachim Weniger
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


@jit(cache=True)
def pade_approximation(n, an, s=1):
    """
    Computes the n/2 pade approximant of the series an at the approximation
    point s

    Arguments:
        an: coefficient series
        n:  order of the series
        s: point of approximation

    Returns:
        pade approximation at s
    """
    nn = int(n/2)
    if mod(nn, 2) == 0:
        nn -= 1

    L = nn
    M = nn

    an = np.ndarray.flatten(an)
    rhs = an[L+1:L+M+1]

    C = zeros((L, M), dtype=complex_type)
    for i in range(L):
        k = i + 1
        C[i, :] = an[L-M+k:L+k]

    b = solve(C, -rhs)  # bn to b1
    b = r_[1, b[::-1]]  # b0 = 1

    a = zeros(L+1, dtype=complex_type)
    a[0] = an[0]
    for i in range(L):
        val = complex_type(0)
        k = i + 1
        for j in range(k+1):
            val += an[k-j] * b[j]
        a[i+1] = val

    p = complex_type(0)
    q = complex_type(0)
    for i in range(L+1):
        p += a[i] * s**i
        q += b[i] * s**i

    return p/q, a, b


@jit(cache=True)
def update_bus_power(k, V, Y):
    """
    Computes the power for a PV or VD bus
    """
    return V[k] * conj(Y[k, :].dot(V))


@jit(cache=True)
def update_all_powers(pv_idx_all, slack_idx_all, V, Y, Sbus):
    """
    Computes the power for all the PV buses and VD buses
    """
    S = Sbus.copy().astype(complex_type)

    # update reactive power for all PV buses
    for k in pv_idx_all:
        Q = update_bus_power(k, V, Y)[0].imag
        S[k] = Sbus[k].real + 1j * Q

    for k in slack_idx_all:
        S[k] = update_bus_power(k, V, Y)[0]

    return S


@jit(cache=True)
def calc_error(admittances, V, powerInjections):
    """
    Calculates the power error for all the buses
    """
    v_mat = np.diag(V)
    vy_mat = conj(admittances.dot(V))
    return powerInjections - dot(v_mat, vy_mat)


@jit(cache=True)
def interprete_solution(nbus, npv, types, x_sol, Vre, map_idx):
    """
    Assign the solution vector individual values to the correct places
    Args:
        nbus: number of system nodes
        npv: number of pv nodes
        types: types of each node
        x_sol: solution vector to analyze
        Vre: Vector or real part of the voltage for the PV nodes
        map_idx: mapping array from normal bus index to PV index

    Returns:
        Voltages coeffients and reactive power coefficients for the PV nodes at the order of x_sol
    """
    C = zeros(nbus, dtype=complex_type)
    Q = zeros(npv)

    for k in range(nbus):
        if types[k] == 2:
            kk = map_idx[k]
            Q[kk] = x_sol[2 * k]
            C[k] = Vre[kk] + 1j * x_sol[2 * k+1]
        else:
            C[k] = x_sol[2 * k] + 1j * x_sol[2 * k+1]

    return C, Q


# @jit(cache=True)
def helm(admittances, slackIndices, maxcoefficientCount, powerInjections, voltageSetPoints, types,
         eps=1e-3, usePade=True, useFFT=False):
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

    # The routines in this script are meant to handle sparse matrices, hence non-sparse ones are not allowed
    assert(issparse(admittances))

    # get the admittance matrix size AKA number of nodes
    nbus = np.shape(admittances)[0]

    # get array with the PV buses indices
    pv_idx_all = np.where(types == 2)[0]

    # reduce the admittance matrix to omit the slack buses
    Ytrans, Ypv, F, types, Vset, S, non_slack_indices,\
    map_idx, map_w, npq, npv, pv, pq = pre_process(n_bus=nbus,Ymat=admittances.copy(),
                                               slack_indices=array(slackIndices, dtype=int),
                                               Vset=voltageSetPoints, S=powerInjections,
                                               types=types)
    nbus_red = np.shape(Ytrans)[0]

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
    Vset_abs2 = abs(voltageSetPoints) **2

    # progressive calculation of coefficients
    n = 0
    converged = False
    inside_precission = True
    errors = list()
    voltages = list()
    Sn_v = zeros(nbus, dtype=complex_type)
    Sn_q = zeros(npv, dtype=complex_type)
    voltages_vector = zeros(nbus, dtype=complex_type)
    Vred_last = zeros(nbus, dtype=complex_type)
    solve = factorized(Ytrans)

    # set the slack indices voltages
    voltages_vector[slackIndices] = voltageSetPoints[slackIndices]

    while n <= maxcoefficientCount and not converged and inside_precission:

        # Reserve coefficients memory space
        C = np.vstack((C, np.zeros((1, nbus), dtype=complex_type)))
        E_v = np.vstack((E_v, np.zeros((1, nbus), dtype=complex_type)))
        E_q = np.vstack((E_q, np.zeros((1, npv))))
        W = np.vstack((W, np.zeros((1, npq+npv), dtype=complex_type)))
        Q = np.vstack((Q, np.zeros((1, npv), dtype=complex_type)))

        # get the system independent term to solve the coefficients
        rhs, Vre = RHS(n, nbus, pv, F, Ypv, S, Vset, Vset_abs2, C, W, Q, types, map_idx, map_w, useFFT)

        # Solve the linear system to obtain the new coefficients
        x_sol = solve(rhs)

        # assign the voltages and the reactive power values correctly
        C[n, :], Q[n, :] = interprete_solution(nbus, npv, types, x_sol, Vre, map_idx)

        # copy variables for the epsilon algorithm
        if not usePade:
            E_v[n, :] = C[n, :]
            E_q[n, :] = Q[n, :]
            Sn_v += C[n, :]
            Sn_q += Q[n, :]

        # Update the inverse voltage coefficients W for the non slack nodes
        for k in non_slack_indices:
            kw = map_w[k]  # actual index in the coefficients structure
            W[n, kw] = calc_W(n, k, kw, C, W, map_idx, useFFT)

        # calculate the reactive power
        for k in pv:
            kk = map_idx[k]
            if usePade:
                if mod(n, 2) == 0 and n > 2:
                    q, _ , _ = pade_approximation(n, Q)
                    S[k] = S[k].real + 1j * q.real
            else:
                q, E_q[:, kk] = epsilon(Sn_q[kk], n, E_q[:, kk])
                S[k] = S[k].real + 1j * q

        # calculate the voltages
        for k in non_slack_indices:
            if usePade:
                if mod(n, 2) == 0 and n > 2:
                    v, _, _ = pade_approximation(n, C[:, k])
                    voltages_vector[k] = v
            else:
                voltages_vector[k], E_v[:, k] = epsilon(Sn_v[k], n, E_v[:, k])

            if np.isnan(voltages_vector[k]):
                print('Maximum precission reached at ', n)
                voltages_vector = Vred_last
                inside_precission = False
                break

        Vred_last = voltages_vector.copy()

        # Compose the voltage values from the coefficient series
        # voltages_vector = recompose_voltages(n, nbus, n_original, slackIndices, non_slack_indices, Vslack, C)
        voltages.append([n, voltages_vector])
        # print(voltages_vector)

        # Calculate the missing power values (Q for PV buses and P, Q for slack buses)
        # S = update_all_powers(pv_idx_all, slackIndices, voltages_vector, admittances, powerInjections)

        # Calculate the error and check the convergence
        mis = voltages_vector * conj(admittances * voltages_vector) - S  # complex power mismatch
        missF = r_[mis[pv].real, mis[pq].real, mis[pq].imag]  # concatenate again
        # missF = r_[mis[pq].real]  # concatenate again

        # check for convergence
        normF = linalg.norm(missF, Inf)
        errors.append(normF)
        if normF < eps:
            converged = True
        else:
            converged = False

        n += 1

    # return Vred_last, Ytrans, F, C, W, Q, errors, converged

    return Vred_last, converged, normF, C, #W, X, R, H, Yred, Yrow, Iinj, errors


def helm_bifurcation_point(C, slackIndices):
    """
    Computes the bifurcation point
    @param C:
    @return:
    """
    npoints = 100
    order_num, bus_num = np.shape(C)
    # V(S) = P(S)/Q(S)
    V = zeros((npoints, bus_num), dtype=complex_type)
    L = zeros((npoints, bus_num))
    for k in range(bus_num):
        if k not in slackIndices:
            _, p, q = pade_approximation(order_num, C[:, k])
            # print(k, 'P:', p)
            # print(k, 'Q:', q)
            asint = np.roots(q[::-1])
            asint = np.sort(abs(asint))
            asint = asint[asint > 2]
            print('Asymptotes', asint)
            # print('Asymptote:', asint[0])

            n = len(asint)
            bpoint = asint[n-1]  # the theoretical index is 0
            # bpoint = max(asint)
            lmda = np.linspace(1, bpoint, npoints+1)[:-1]
            # lmda = np.linspace(1, 100, npoints)

            pval = np.polyval(p[::-1], lmda)
            qval = np.polyval(q[::-1], lmda)

            V[:, k] = pval / qval
            L[:, k] = lmda

    return V, L