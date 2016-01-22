# -*- coding: utf-8 -*-
import numpy as np
np.set_printoptions(precision=6, suppress=True, linewidth=320)
from numpy import asscalar, where, zeros, ones, mod, conj, array, dot, complex64, complex128 #, complex256

from scipy.linalg import solve

from scipy.sparse.linalg import factorized, spsolve, inv
from scipy.sparse import issparse, csr_matrix as sparse

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

        Zred: Reduced impedance matrix

        C: Reduced voltage constant

        Sred: Array of power injections of the buses that are not of type slack

        Vset_red: Reduced set voltage module array

        pv_idx_red: indices of the PV nodes in the reduced schemae

        npv: Number of PV nodes

        Vslack: Slack voltages array

        non_slack_indices: Indices of the non-slack nodes in the complete scheme

        nbus: number of nodes in the reduced scheme
    """

    # Compose the list of buses indices excluding the indices of the slack buses
    non_slack_indices = list(range(n_bus))
    for i in slack_indices[::-1]:
        non_slack_indices.pop(i)
    non_slack_indices = array(non_slack_indices)
    nbus = len(non_slack_indices)

    # Types of the non slack buses
    types_red = types[non_slack_indices]

    # Compose a reduced admittance matrix without the rows and columns that correspond to the slack buses
    Yred = Ymat[non_slack_indices, :][:, non_slack_indices]

    # matrix of the columns of the admittance matrix that correspond to the slack buses
    Yslack = Ymat[non_slack_indices, :][:, slack_indices]

    # vector of slack voltages (Complex)
    Vslack = Vset[slack_indices]

    # vector of currents being injected by the slack nodes (Matrix vector product)
    Islack = -1 * Yslack.dot(Vslack)

    # Vector of reduced power values (Non slack power injections)
    Sred = S[non_slack_indices]

    # reduced impedance matrix
    Zred = inv(Yred)

    # Reduced voltage constant
    C = Zred.dot(Islack)

    # list of PV indices in the reduced scheme
    pv_idx_red = where(types_red == 2)[0]
    npv = len(pv_idx_red)

    # Set voltage modules in the reduced scheme
    Vset_red = abs(Vset)[non_slack_indices]

    return Zred, Yred, C, Sred, Vset_red, pv_idx_red, npv, Vslack, non_slack_indices, nbus


def update_bus_power(k, V, Y):
    """
    Computes the power for a PV or VD bus
    """
    return V[k] * conj(Y[k, :].dot(V))[0]

@jit
def update_all_powers(pv_idx_all, slack_idx_all,  V, Y, Sbus):
    """
    Computes the power for all the PV buses and VD buses
    """
    S = Sbus.copy().astype(complex_type)

    # update reactive power for all PV buses
    for k in pv_idx_all:
        Q = update_bus_power(k, V, Y).imag
        S[k] = Sbus[k].real + 1j * Q

    for k in slack_idx_all:
        S[k] = update_bus_power(k, V, Y)

    return S


@jit
def calc_error(admittances, V, powerInjections):
    """
    Calculates the power error for all the buses
    """
    v_mat = np.diag(V)
    vy_mat = conj(admittances.dot(V))
    return powerInjections - dot(v_mat, vy_mat)


# @jit
def zbus(admittances, slackIndices, maxIter, powerInjections, voltageSetPoints, types, Qlim, eps=1e-3, Vsol=None):
    """

    Args:
        admittances: Circuit complete admittance matrix

        slackIndices: Indices of the slack buses (although most likely only one works)

        maxIter: Number of maximum iterations

        powerInjections: Array of power injections matching the admittance matrix size

        voltageSetPoints: Array of voltage set points matching the admittance matrix size

        types: Array of bus types matching the admittance matrix size. types: {1-> PQ, 2-> PV, 3-> Slack}

        eps: Solution tolerance

        Vsol: Starting point voltage solution

    Output:
        Voltages vector
    """

    # The routines in this script are meant to handle sparse matrices, hence non-sparse ones are not allowed
    assert(issparse(admittances))

    # get the admittance matrix size AKA number of nodes
    n_original = np.shape(admittances)[0]

    # reduce the admittance matrix to omit the slack buses
    Zred, Yred, C, Sred, Vset_red, pv_idx_red, npv, Vslack, non_slack_indices, nbus = reduce_arrays(n_bus=n_original,
                                                                                                    Ymat=admittances,
                                                                                                    slack_indices=array(slackIndices, dtype=int),
                                                                                                    Vset=voltageSetPoints,
                                                                                                    S=powerInjections,
                                                                                                    types=types)

    # Solve variables
    n = 0
    converged = False
    errors = list()

    if Vsol is None:
        Vred = ones(nbus, dtype=complex_type)  # use the flat start solution
    else:
        if len(Vsol) == n_original:
            Vred = Vsol[non_slack_indices]  # use the given voltage solution
        else:
            Vred = ones(nbus, dtype=complex_type)  # use the flat start solution


    Vred_prev = zeros(nbus, dtype=complex_type)

    while n <= maxIter and not converged:

        # update reactive power
        if npv > 0:
            for k in pv_idx_red:
                qmin, qmax = Qlim[k]
                Q = update_bus_power(k, Vred, Yred).imag
                if Q > qmax:
                    Q = qmax
                elif Q<qmin:
                    Q = qmin
                Sred[k] = Sred[k].real + 1j * Q

        # compute the new current injections at the nodes
        I = conj(Sred) / conj(Vred)

        # compute the voltage
        Vred = Zred.dot(I) + C

        # correct the voltage for the PV buses
        if npv > 0:
            Vred[pv_idx_red] *= Vset_red[pv_idx_red] / abs(Vred[pv_idx_red])



#             for k in pv_idx_red:
#                 tmp = (Vred[k] * conj(Yred[k, :] * Vred)).imag  # reactive power
#                 Sred[k] = Sred[k].real + 1j * asscalar(tmp)
#                 tmp = (conj(Sred[k] / Vred[k]) - Yred[k, :] * Vred) / Yred[k, k]
#                 Vred[k] += asscalar(tmp)
# #               V[k] = Vm[k] * V[k] / abs(V[k])
#             Vred[pv_idx_red] = Vset_red[pv_idx_red] * Vred[pv_idx_red] / abs(Vred[pv_idx_red])

        # Calculate the error and check the convergence
        error = max(abs(Vred_prev - Vred))
        errors.append(error)

        converged = error < eps  # boolean result

        # print(n, Vred)

        # update the control voltage for the convergence check
        Vred_prev = Vred.copy()

        n += 1

    # Declare the vector of all the voltages
    voltages_vector = zeros(n_original, dtype=complex_type)
    # Assign the slack voltages
    voltages_vector[slackIndices] = Vslack
    # Assign the non-slack voltages
    voltages_vector[non_slack_indices] = Vred

    return voltages_vector, converged, error

