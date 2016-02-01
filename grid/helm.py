import numpy as np
np.set_printoptions(precision=6, suppress=True, linewidth=256)
from numpy import where, zeros, ones, mod, conj, array, dot, linalg, r_, Inf, complex128 #, complex256

from scipy.linalg import solve

from scipy.sparse.linalg import factorized
from scipy.sparse import issparse, csr_matrix as sparse
from scipy import fftpack

from numba import jit

# Set the complex precision to use
complex_type = complex128


def reduce_arrays(n_bus, Ymat, slack_indices, Vset, S, types):
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
    types_red = types[non_slack_indices]

    # now to have efficient arrays of coefficients
    map_idx = zeros(len(types_red), dtype=np.int)
    npq = 0
    npv = 0
    for i in range(len(types_red)):
        if types_red[i] == 1:  # PQ
            map_idx[i] = npq
            npq += 1
        elif types_red[i] == 2:  # PV
            map_idx[i] = npv
            npv += 1

    # obtain the vector of the sums per row of the admittance matrix
    Yrow = np.ndarray.flatten(np.array(Ymat.sum(axis=1)))
    Yrow = Yrow[non_slack_indices]

    # Compose a reduced admittance matrix without the rows and columns that correspond to the slack buses
    Yred = Ymat[non_slack_indices, :][:, non_slack_indices]


    # matrix of the columns of the admittance matrix that correspond to the slack buses
    Yslack = Ymat[non_slack_indices, :][:, slack_indices]

    # vector of slack voltages (Complex)
    Vslack = Vset[slack_indices]

    # vector of currents being injected by the slack nodes (Matrix vector product)
    I = -1 * np.ndarray.flatten((Yslack.dot(Vslack)))

    # Vector of reduced power values (Non slack power injections)
    Sred = S[non_slack_indices]

    return Yred, Yrow, I, Sred, Vslack, types_red, non_slack_indices, map_idx, npq, npv

@jit(cache=True)
def RHS(n, nbus, Yrow, I, S, Vset_abs2, C, X, R, H, W, types_red, map_idx):
    """
    Right hand side calculation.

    Args:
        n: Order of the coefficients

        nbus: Number of buses (not counting the slack buses)

        Yrow: Vector where every elements the sum of the corresponding row of the reduced admittance matrix)

        I: Vector of current injections (nbus elements)

        S: Vector of power injections (nbus elements)

        Vset_abs2: Vetor with the voltage set points squared. (nbus elements)

        C: Voltage coefficients (Ncoeff x nbus elements)

        X: Weighted coefficients (Ncoeff x nbus elements)

        R: Voltage convolution coefficients (Ncoeff x nbus elements)

        W: Inverse coefficients structure (Ncoeff x nbus elements)

        types_red: Types of the non slack buses (nbus elements)

    Output:
        rhs: Right hand side vector to solve the coefficients (nbus elements)
    """
    rhs = np.empty(nbus, dtype=complex_type)

    for k in range(nbus):

        if types_red[k] == 1:  # PQ
            rhs[k] = RHS_PQ(n, k, Yrow, I, S, W, map_idx)
        elif types_red[k] == 2:  # PV
            rhs[k] = RHS_PV(n, k, Yrow, I, S, Vset_abs2, C, X, R, H, map_idx)

    return rhs

@jit(cache=True)
def RHS_PQ(n, k, Yrow, I, S, W, map_idx):
    """
    Right hand side calculation for a PQ bus.

    Args:
        n: Order of the coefficients

        k: Index of the bus

        Yrow: Vector where every elements the sum of the corresponding row of the reduced admittance matrix)

        I: Vector of current injections (nbus elements)

        S: Vector of power injections (nbus elements)

        W: Inverse coefficients structure (Ncoeff x nbus elements)
    Output:
        Right hand side value
    """
    if n == 0:
        return I[k] - Yrow[k]

    elif n == 1:
        kk = map_idx[k]
        return conj(S[k]) * W[0, kk] + Yrow[k]

    elif n > 1:
        kk = map_idx[k]
        return conj(S[k]) * W[n-1, kk]

@jit
def calc_W(n, k, C, W, map_idx):
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
        # if k==1:
        #     print('w[',n,',',k,']: ', res)
    else:
        # if k==1:
        #     print('w[',n,',',k,']: ')
        kk = map_idx[k]
        # res = complex_type(0)
        # for l in range(n):
        #     res -= W[l, kk] * conj(C[n-l, k])

        # faster and actually the same:
        a = fftpack.fft(W[:, kk])
        b = fftpack.fft(conj(C[:, k]))
        c = a * b
        e = fftpack.ifft(c)
        res = -e[n]

    res /= conj(C[0, k])

    return res

@jit(cache=True)
def RHS_PV(n, k, Yrow, I, S, Vset_abs2, C, X, R, H, map_idx):
    """
    Right hand side calculation for a PQ bus.

    Args:
        n: Order of the coefficients

        k: Index of the bus

        Yrow: Vector where every elements the sum of the corresponding row of the reduced admittance matrix)

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

    if n == 0:
        return Yrow[k] + I[k]

    else:
        kk = map_idx[k]
        rhs = (2.0 * S[k].real * C[n-1, k] - H[n-1, kk] + R[n-1, kk] * conj(I[k])) / Vset_abs2[k]

        if n == 1:
            rhs -= Yrow[k]

    return rhs

@jit
def calc_R(n, k, C):
    """
    Convolution coefficient

    Args:
        n: Order of the coefficients

        k: Index of the bus

        C: Voltage coefficients (Ncoeff x nbus elements)

    Output:
        Convolution coefficient of order n for the bus k
    """

    # result = complex_type(0)
    # for l in range(n+1):
    #     result += C[l, k] * C[n-l, k]

    a = fftpack.fft(C[:, k])
    e = fftpack.ifft(a *a)
    result = e[n]

    return result

# @jit
def calc_X(n, k, nbus, R, C, Yred):
    """
    Admittance weighted coefficient

    Args:
        n: Order of the coefficients

        k: Index of the bus

        nbus: Number of non-slack buses

        R: Convolution coefficient (Ncoeff x nbus elements)

        C: Voltage coefficients (Ncoeff x nbus elements)

        Yred: Reduced admittance matrix

    Output:
        Admittance weighted coefficient of order n for the bus k
    """
    # result = complex_type(0)
    # idx = Yred.indices[Yred.indptr[k]:Yred.indptr[k+1]]
    # # for i in range(nbus):
    # for i in idx:
    #     if i != k:
    #         result += conj(Yred[k, i] * C[n, i])

    result = (conj(Yred[k, :] * C[n, :]) - conj(Yred[k, k] * C[n, k]))[0]

    return result

# @jit
def calc_H(n, k, X, R, C, Yred, Vset_abs2, map_idx):
    """
    Calculate the combined coefficient
    Args:
        n: Order of the coefficients

        k: Index of the bus

        X: Weighted coefficients (Ncoeff x nbus elements)

        R: Convolution coefficient (Ncoeff x nbus elements)

        C: Voltage coefficients (Ncoeff x nbus elements)

        Yred: Reduced admittance matrix

        Vset_abs2: Vector with the voltage set points squared. (nbus elements)

    Output:
        Returns the H coefficient of order n for the bus of index k
    """
    # result = complex_type(0)
    kk = map_idx[k]
    # for i in range(n+1):
    #     result += X[n-i, kk] * R[i, kk]

    a = fftpack.fft(X[:, kk])
    b = fftpack.fft(R[:, kk])
    c = a * b
    e = fftpack.ifft(c)
    result = e[n]

    result += conj(Yred[k, k]) * C[n, k] * Vset_abs2[k]  # to account for the set voltage

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
                E[j-1] = AUX1 + One/DIFF

        if mod(n, 2) == 0:
            estim = E[0]
        else:
            estim = E[1]

    return estim, E


def update_bus_power(k, V, Y):
    """
    Computes the power for a PV or VD bus
    """
    return V[k] * conj(Y[k, :].dot(V))


@jit(cache=True)
def update_all_powers(pv_idx_all, slack_idx_all,  V, Y, Sbus):
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


# @jit
def helm(admittances, slackIndices, maxcoefficientCount, powerInjections, voltageSetPoints, types, eps=1e-3):
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
    n_original = np.shape(admittances)[0]

    # get array with the PV buses indices
    pv_idx_all = np.where(types == 2)[0]

    # reduce the admittance matrix to omit the slack buses
    Yred, Yrow, Iinj, Sred, Vslack, types_red, non_slack_indices, map_idx, npq, npv = reduce_arrays(n_bus=n_original,
                                                                                                    Ymat=admittances,
                                                                                                    slack_indices=array(slackIndices, dtype=int),
                                                                                                    Vset=voltageSetPoints,
                                                                                                    S=powerInjections,
                                                                                                    types=types)

    # get the new dimension AKA number of nodes minus the slack nodes
    nbus = len(non_slack_indices)

    # declare the matrix of coefficients that will lead to the voltage computation
    C = zeros((0, nbus), dtype=complex_type)

    # auxiliary array for the epsilon algorithm
    E = zeros((0, nbus), dtype=complex_type)

    # Declare the inverse coefficients vector
    # (it is actually a matrix; a vector of coefficients per coefficient order)
    W = zeros((0, npq), dtype=complex_type)

    # Admittance weighted coefficients
    X = zeros((0, npv), dtype=complex_type)

    # Convolution coefficients
    R = zeros((0, npv), dtype=complex_type)

    # Convolution coefficients
    H = zeros((0, npv), dtype=complex_type)

    # Squared values of the voltage module for the buses that are not of slack type
    Vset_abs2 = (abs(voltageSetPoints) **2)[non_slack_indices]

    # progressive calculation of coefficients
    n = 0
    converged = False
    errors = list()
    voltages = list()
    voltages.append([])
    Sn = zeros(nbus, dtype=complex_type)
    Vred = zeros(nbus, dtype=complex_type)
    solve =factorized(Yred)
    correct = True
    inside_precission= True
    error = 0
    while n <= maxcoefficientCount and not converged and inside_precission:
        # get the system independent term to solve the coefficients
        rhs = RHS(n, nbus, Yrow, Iinj, Sred, Vset_abs2, C, X, R, H, W, types_red, map_idx)

        # Reserve coefficients memory space
        C = np.vstack((C, np.zeros((1, nbus), dtype=complex_type)))
        E = np.vstack((E, np.zeros((1, nbus), dtype=complex_type)))
        W = np.vstack((W, np.zeros((1, npq), dtype=complex_type)))
        R = np.vstack((R, np.zeros((1, npv), dtype=complex_type)))
        X = np.vstack((X, np.zeros((1, npv), dtype=complex_type)))
        H = np.vstack((H, np.zeros((1, npv), dtype=complex_type)))

        # Solve the linear system to obtain the new coefficients
        C[n, :] = solve(rhs)
        if n == 0:
            #if sum(abs(1 - abs(C[n, :])) > 0.1):  # if any of the values is greater than 1 with a tolerance of 0.1
            if correct:
                mmod = rhs - Yred.dot(ones(nbus))
                Yrow += mmod
                # rhs[pv_idx_red] -= mmod[pv_idx_red]
                rhs = RHS(n, nbus, Yrow, Iinj, Sred, Vset_abs2, C, X, R, H, W, types_red, map_idx)
                C[n, :] = solve(rhs)

        E[n, :] = C[n, :]  # usar SSOR
        Sn += C[n, :]

        # Update the auxiliary coefficients (Inverse, Squared and Admittance weighted)
        valid = True
        for j in range(nbus):
            if types_red[j] == 1:  # PQ
                kk = map_idx[j]  # actual index in the coefficients structure
                W[n, kk] = calc_W(n, j, C, W, map_idx)
            elif types_red[j] == 2:  # PV
                kk = map_idx[j]  # actual index in the coefficients structures
                R[n, kk] = calc_R(n, j, C)
                X[n, kk] = calc_X(n, j, nbus, R, C, Yred)
                H[n, kk] = calc_H(n, j, X, R, C, Yred, Vset_abs2, map_idx)

            # calculate the voltages
            Vred[j], E[:, j] = epsilon(Sn[j], n, E[:, j])


            if np.isnan(Vred[j]):
                print('Maximum precission reached')
                Vred = Vred_last
                inside_precission = False
                break

        Vred_last = Vred.copy()


        # Declare the vector of all the voltages
        voltages_vector = zeros(n_original, dtype=complex_type)
        # Assign the slack voltages
        voltages_vector[slackIndices] = Vslack
        # Assign the non-slack voltages
        voltages_vector[non_slack_indices] = Vred

        # Compose the voltage values from the coefficient series
        # voltages_vector = recompose_voltages(n, nbus, n_original, slackIndices, non_slack_indices, Vslack, C)
        voltages.append([n, voltages_vector])

        # Calculate the missing power values (Q for PV buses and P, Q for slack buses)
        S = update_all_powers(pv_idx_all, slackIndices, voltages_vector, admittances, powerInjections)

        # Calculate the error and check the convergence
        error = calc_error(admittances, voltages_vector, S)
        normF = linalg.norm(error, Inf)
        errors.append(max(error))

        if max(error) < eps:
            converged = True
        else:
            converged = False

        n += 1

    print('\nC:')
    print(C)

    print('\nv=')
    print(abs(Vred))
    print('Error', max(error))
    print('converged', converged)
    print('Done.')

    return voltages_vector, converged, normF  #, C, W, X, R, H, Yred, Yrow, Iinj, errors