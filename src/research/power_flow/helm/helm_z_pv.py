
import numpy as np

np.set_printoptions(precision=6, suppress=True, linewidth=320)
from numpy import where, zeros, ones, mod, conj, array, dot, complex128  # , complex256
from scipy.linalg import solve

from scipy.sparse.linalg import factorized
from scipy.sparse import issparse
from matplotlib import pyplot as plt

# Set the complex precision to use
complex_type = complex128


# @jit(cache=True)
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

    # Compose a reduced admittance matrix without the rows and columns that correspond to the slack buses
    Yred = Ymat[non_slack_indices, :][:, non_slack_indices]

    # matrix of the columns of the admittance matrix that correspond to the slack buses
    Yslack = Ymat[non_slack_indices, :][:, slack_indices]

    # vector of slack voltages (Complex)
    Vslack = Vset[slack_indices]

    # vector of currents being injected by the slack nodes (Matrix vector product)
    Iind = -1 * np.ndarray.flatten(array(Yslack.dot(Vslack)))
    # Iind /= abs(Iind)

    # Invert Yred: By storing into a factorization object we get a much better numerical performance
    # In the end, if Zred=Yred^-1,  Zred^-1 x I is the same as Yred_LU.solve(I)
    Zred = factorized(Yred)

    # Vind = Zred * Iind  # (not needed)

    # Vector of reduced power values (Non slack power injections)
    Sred = S[non_slack_indices]

    return Yred, Zred, Iind, Sred, Vslack, types_red, non_slack_indices, map_idx, npq, npv


# @jit(cache=True)
def I_n(n, nbus, Iind, S, Vset_abs2, C, H, R, W, types_red, map_idx):
    """
    Array of Intensity coefficients of order n
    @param n: Order of the coefficients
    @param nbus: Number of buses (not counting the slack buses)
    @param Iind: Vector of current injections (nbus elements)
    @param S: Vector of power injections (nbus elements)
    @param Vset_abs2: Vector with the voltage set points squared. (nbus elements)
    @param C: Voltage coefficients (order x node)
    @param H: R-X convolution structure (order x pv-node)
    @param R: Voltage convolution coefficients (order x pv-node)
    @param W: Inverse coefficients structure (order x pq-node)
    @param types_red: Types of the non slack buses (nbus elements)
    @param map_idx: node -> index map in the PQ or PV structures
    @return:
    """

    rhs = np.empty(nbus, dtype=complex_type)

    for k in range(nbus):
        kk = map_idx[k]
        if types_red[k] == 1:  # PQ
            rhs[k] = I_PQ(n, k, kk, Iind, S, W, map_idx)
        elif types_red[k] == 2:  # PV
            rhs[k] = I_PV(n, k, kk, S, Iind, Vset_abs2, C, H, R, map_idx)

    return rhs


# @jit(cache=True)
def I_PQ(n, k, kk, Iind, S, W, map_idx):
    """
    Value of the intensity coefficient of order n for a PQ node k
    @param n: Order of the coefficients
    @param k: Index of the bus
    @param Iind: Vector of reduced current injections (nbus elements)
    @param S: Vector of reduced power injections (nbus elements)
    @param W: Inverse coefficients structure (order x pq-node)
    @param map_idx: node -> index in the PQ-only structures map
    @return: complex value
    """

    if n == 0:
        return Iind[k]

    else:
        # kk = map_idx[k]
        return conj(S[k]) * W[n - 1, kk]


# @jit(cache=True)
def calc_W(n, k, kk, C, W, map_idx):
    """
    Calculation of the inverse coefficients W. (only applicable for PQ buses)
    @param n: Order of the coefficients
    @param k: Index of the bus
    @param C: Voltage coefficients (order x node)
    @param W: Inverse coefficients structure (order x pq-node)
    @param map_idx: node -> index in the PQ-only structures map
    @return: complex value
    """

    if n == 0:
        res = complex_type(1)

    else:
        # kk = map_idx[k]
        res = complex_type(0)
        for l in range(n):
            res -= W[l, kk] * conj(C[n - l, k])

    res /= conj(C[0, k])

    return res


# @jit(cache=True)
def I_PV(n, k, kk, Sred, Iind, Vset_abs2, C, H, R, map_idx):
    """
    Get the intensity coefficient of order n of the PV node k
    @param n: order of the coefficient
    @param k: index of the node
    @param Sred: reduced specified power array
    @param Iind: induced intensity in the non-slack nodes
    @param Vset_abs2: array of reduced set-voltages squared
    @param C: Voltage coefficients structure (order x node)
    @param H: R-X convolution (order x pv-node)
    @param R: Voltage convolution coefficients (order x pv-node)
    @param map_idx: node -> index in the PV-only structures map
    @return: complex value
    """

    if n == 0:
        return Iind[k]
    else:
        # kk = map_idx[k]
        rhs = (2.0 * Sred[k].real * C[n - 1, k] - H[n - 1, kk] + R[n - 1, kk] * conj(Iind[k])) / Vset_abs2[k]

    return rhs


# @jit(cache=True)
def calc_R(n, k, C):
    """
    Voltage convolution coefficient

    Args:
        n: Order of the coefficients

        k: Index of the bus

        C: Voltage coefficients (order x node)

    Output:
        Convolution coefficient of order n for the bus k
    """

    result = complex_type(0)
    for l in range(n + 1):
        result += C[l, k] * C[n - l, k]

    return result


# @jit(cache=True)
def calc_X(n, k, nbus, C, Yred):
    """
    Admittance weighted coefficient

    Args:
        n: Order of the coefficients

        k: Index of the bus

        nbus: Number of non-slack buses

        C: Voltage coefficients (Ncoeff x nbus elements)

        Yred: Reduced admittance matrix

    Output:
        Admittance weighted coefficient of order n for the bus k
    """
    result = complex_type(0)
    for i in range(nbus):
        if i != k:
            result += conj(Yred[k, i] * C[n, i])

    return result


# @jit(cache=True)
def calc_H(n, k, kk, X, R, C, Yred, Vset_abs2, map_idx):
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
    # kk = map_idx[k]
    #
    result = complex_type(0)
    for i in range(n + 1):
        result += X[n - i, kk] * R[i, kk]
    result += conj(Yred[k, k]) * C[n, k] * Vset_abs2[k]

    return result


# @jit(cache=True)
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
            AUX2 = E[j - 1]
            DIFF = E[j] - AUX2

            if abs(DIFF) <= Tiny:
                E[j - 1] = Huge
            else:
                if DIFF == 0.0:
                    DIFF = Tiny
                E[j - 1] = AUX1 + One / DIFF

        if mod(n, 2) == 0:
            estim = E[0]
        else:
            estim = E[1]

    return estim, E


# @jit(cache=True)
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


# @jit(cache=True)
def update_bus_power(k, V, Y):
    """
    Computes the power for a PV or VD bus
    """
    return V[k] * conj(Y[k, :].dot(V))


# @jit(cache=True)
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


# @jit(cache=True)
def calc_error(admittances, V, powerInjections):
    """
    Calculates the power error for all the buses
    """
    v_mat = np.diag(V)
    vy_mat = conj(admittances.dot(V))
    return powerInjections - dot(v_mat, vy_mat)


# @jit(cache=True)
def helmz(admittances, slackIndices, maxcoefficientCount, powerInjections, voltageSetPoints, types,
          eps=1e-3, usePade=True, inherited_pv=None):
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
    assert (issparse(admittances))

    # get the admittance matrix size AKA number of nodes
    n_original = np.shape(admittances)[0]

    # get array with the PV buses indices
    pq_idx_all = where(types == 1)[0]
    pv_idx_all = where(types == 2)[0]
    # reduce the admittance matrix to omit the slack buses
    Yred, Zred, Iind, Sred, Vslack, types_red, non_slack_indices, \
    map_idx, npq, npv = reduce_arrays(n_bus=n_original, Ymat=admittances.copy(),
                                      slack_indices=array(slackIndices, dtype=int),
                                      Vset=voltageSetPoints, S=powerInjections,
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
    Vset_abs2 = (abs(voltageSetPoints) ** 2)[non_slack_indices]

    # progressive calculation of coefficients
    n = 0
    converged = False
    inside_precission = True
    errors = list()
    errors_PV_P = list()
    errors_PV_Q = list()
    errors_PQ_P = list()
    errors_PQ_Q = list()
    voltages = list()
    Sn = zeros(nbus, dtype=complex_type)
    Vred = zeros(nbus, dtype=complex_type)
    Vred_last = zeros(nbus, dtype=complex_type)
    best_V = None
    last_err = 1e100

    # Declare the vector of all the voltages
    voltages_vector = zeros(n_original, dtype=complex_type)
    voltages_vector[slackIndices] = Vslack

    error = list()

    while n <= maxcoefficientCount and not converged and inside_precission:

        # Reserve coefficients memory space
        C = np.vstack((C, np.zeros((1, nbus), dtype=complex_type)))
        E = np.vstack((E, np.zeros((1, nbus), dtype=complex_type)))
        W = np.vstack((W, np.zeros((1, npq), dtype=complex_type)))
        R = np.vstack((R, np.zeros((1, npv), dtype=complex_type)))
        X = np.vstack((X, np.zeros((1, npv), dtype=complex_type)))
        H = np.vstack((H, np.zeros((1, npv), dtype=complex_type)))

        # get the system independent term to solve the coefficients
        I = I_n(n, nbus, Iind, Sred, Vset_abs2, C, H, R, W, types_red, map_idx)

        # C[n, :] = np.dot(Zred, I)
        C[n, :] = Zred(I)

        # check NaN's
        if not np.isnan(np.sum(C[n, :])):

            E[n, :] = C[n, :]
            Sn += C[n, :]

            # Update the auxiliary coefficients (Inverse, Squared and Admittance weighted)
            for j in range(nbus):
                if types_red[j] == 1:  # PQ
                    kk = map_idx[j]  # actual index in the coefficients structure
                    W[n, kk] = calc_W(n, j, kk, C, W, map_idx)
                elif types_red[j] == 2:  # PV
                    kk = map_idx[j]  # actual index in the coefficients structures
                    R[n, kk] = calc_R(n, j, C)
                    X[n, kk] = calc_X(n, j, nbus, C, Yred)
                    H[n, kk] = calc_H(n, j, kk, X, R, C, Yred, Vset_abs2, map_idx)

                # calculate the voltages
                if usePade:
                    if mod(n, 2) == 0 and n > 0:
                        Vred[j], _, _ = pade_approximation(n, j, C)

                else:
                    Vred[j], E[:, j] = epsilon(Sn[j], n, E[:, j])

                if np.isnan(Vred[j]):
                    print('Maximum precession reached at ', n)
                    Vred = Vred_last
                    inside_precission = False
                    break

            # check NaN's
            if np.isnan(np.sum(R[n, :]) + np.sum(X[n, :]) + np.sum(W[n, :]) + np.sum(H[n, :])):
                inside_precission = False
                print('Maximum precession reached at ', n)

            Vred_last = Vred.copy()
        else:
            inside_precission = False
            print('Maximum precession reached at ', n)

        # Assign the non-slack voltages
        voltages_vector[non_slack_indices] = Vred

        # Compose the voltage values from the coefficient series
        # voltages_vector = recompose_voltages(n, nbus, n_original, slackIndices, non_slack_indices, Vslack, C)
        voltages.append(voltages_vector.copy())

        # Calculate the missing power values (Q for PV buses and P, Q for slack buses)
        S = update_all_powers(pv_idx_all, slackIndices, voltages_vector, admittances, powerInjections)

        # Calculate the error and check the convergence
        mis = calc_error(admittances, voltages_vector, S)

        # check for convergence
        # Calculate the error and check the convergence
        Scalc = voltages_vector * conj(admittances * voltages_vector)

        # complex power mismatch
        power_mismatch = Scalc - S

        # concatenate error by type
        mismatch = r_[power_mismatch[pv_idx_all].real, power_mismatch[pq_idx_all].real, power_mismatch[pq_idx_all].imag]

        # check for convergence
        normF = linalg.norm(mismatch, Inf)
        errors.append(normF)

        if normF < last_err:
            last_err = normF
            best_V = voltages_vector

        converged = (normF < eps)

        if npv > 0:
            a = linalg.norm(mismatch[pv_idx_all].real, Inf)
        else:
            a = 0
        b = linalg.norm(mismatch[pq_idx_all].real, Inf)
        c = linalg.norm(mismatch[pq_idx_all].imag, Inf)
        error.append([a, b, c])

        n += 1

    errors_lst = [array(errors), array(errors_PV_P), array(errors_PV_Q), array(errors_PQ_P), array(errors_PQ_Q)]

    err_df = pd.DataFrame(array(error), columns=['PV_real', 'PQ_real', 'PQ_imag'])
    err_df.plot(logy=True)

    return best_V, C, W, X, R, H, Yred, errors_lst, converged, last_err, S, voltages


def bifurcation_point(C):
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
        _, p, q = pade_approximation(order_num, k, C)
        # print(k, 'P:', p)
        # print(k, 'Q:', q)
        asint = np.roots(q[::-1])
        asint = np.sort(abs(asint))
        asint = asint[asint > 2]
        print('Asymptotes', asint)
        # print('Asymptote:', asint[0])

        bpoint = asint[0]
        lmda = np.linspace(1, bpoint, npoints + 1)[:-1]
        # lmda = np.linspace(1, 100, npoints)

        pval = np.polyval(p[::-1], lmda)
        qval = np.polyval(q[::-1], lmda)

        V[:, k] = pval / qval
        L[:, k] = lmda

    return V, L


# @jit(cache=True)
def continued_fraction(n, k, C):
    """
    Pade approximation using continued fractions
    @param C: Voltage coefficients structure
    @param n: number of orders (rows of C)
    @param k: bus index (column of C)
    @return:
    """
    temp = complex_type(0)
    a = complex_type(1)

    for ni in range(n - 1, 0, -1):
        b = C[ni, k]

        # print(a, b, a/b)
        temp = b / (a + temp)

    return C[0, k] + temp


def print_coeffs(C, W, R, X, H):
    print('C')
    print(C.copy())
    print('W')
    print(W.copy())
    print('R')
    print(R.copy())
    print('X')
    print(X.copy())
    print('H')
    print(H.copy())


def print_polar(x):
    n = len(x)
    for i in range(n):
        print(abs(x[i]), ' < ', np.angle(x[i], True), 'd')


def to_latex(a, label='A'):
    import sys
    sys.stdout.write('\[ '
                     + label
                     + ' = \\left| \\begin{array}{'
                     + ('c' * a.shape[1])
                     + '}\n')
    for r in a:
        sys.stdout.write(str(r[0]))
        for c in r[1:]:
            sys.stdout.write(' & ' + str(c))
        sys.stdout.write('\\\\\n')
    sys.stdout.write('\\end{array} \\right| \]\n')


def plot_full_convergence(err, powerInjections, S, title, ext='.eps', save=True):
    plt.figure()

    titles = ['Maximum mismatch', 'PV nodes P mismatch', 'PV nodes Q mismatch', 'PQ nodes P mismatch',
              'PQ nodes Q mismatch']
    idx = [0, 1, 3, 4]
    k = 0
    for i in idx:
        k += 1
        plt.subplot(2, 2, k)
        if not np.all(err[i] == 0):
            plt.plot(err[i])
            plt.title(titles[i])
            try:
                plt.yscale('log')
            except:
                print()

    fig = plt.gcf()
    fig.suptitle(title, fontsize=14)

    # if save:
    #     plt.savefig(replace_non_ascii(title).replace(" ", "_") + ext)
    # else:
    #     plt.show()


if __name__ == "__main__":
    from GridCal.Engine.calculation_engine import *
    from matplotlib import pyplot as plt

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
    print('HELM-Z')
    start_time = time.time()
    cmax = 25
    V1, C, W, X, R, H, Yred, err, converged_, \
    best_err, S, Vlst = helmz(admittances=circuit.power_flow_input.Ybus,
                              slackIndices=circuit.power_flow_input.ref,
                              maxcoefficientCount=cmax,
                              powerInjections=circuit.power_flow_input.Sbus,
                              voltageSetPoints=circuit.power_flow_input.Vbus,
                              types=circuit.power_flow_input.types,
                              eps=1e-9,
                              usePade=True,
                              inherited_pv=None)

    print("--- %s seconds ---" % (time.time() - start_time))
    # print_coeffs(C, W, R, X, H)

    print('V module:\t', abs(V1))
    print('V angle: \t', np.angle(V1))
    print('error: \t', best_err)

    # check the HELM solution: v against the NR power flow
    print('\nNR')
    options = PowerFlowOptions(SolverType.NR, verbose=False, robust=False, tolerance=1e-9)
    power_flow = PowerFlow(grid, options)

    start_time = time.time()
    power_flow.run()
    print("--- %s seconds ---" % (time.time() - start_time))
    vnr = circuit.power_flow_results.voltage

    print('V module:\t', abs(vnr))
    print('V angle: \t', np.angle(vnr))
    print('error: \t', circuit.power_flow_results.error)

    # check
    print('\ndiff:\t', V1 - vnr)

    plt.show()
