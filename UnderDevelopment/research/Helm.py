# -*- coding: utf-8 -*-
# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.

import Desarrollos.power_flow_research.example_grids as grids
import numpy as np
np.set_printoptions(linewidth=320)
# np.set_printoptions(precision=6, suppress=True, linewidth=320)
from numpy import where, zeros, ones, mod, conj, array, dot, complex128
from numpy import poly1d, r_, eye, hstack, diag, linalg, Inf
from enum import Enum
from itertools import product

from scipy import fftpack
from scipy.linalg import solve

from scipy.sparse.linalg import factorized, spsolve
from scipy.sparse import issparse, csc_matrix as sparse

# just in time compiler
# from numba import jit

# Set the complex precision to use
complex_type = complex128


class NodeType(Enum):
    PQ = 1,
    PV = 2,
    REF = 3,
    NONE = 4,
    STO_DISPATCH = 5  # Storage dispatch, in practice it is the same as REF


# @jit(cache=True)
def pre_process(n_bus, Yseries, Vset, pq, pv, vd):
    """
    Make the Helm System matrix
    @param n_bus: Number of buses of the circuit
    @param Yseries: Circuit admittance matrix of the series elements
    @param Vset: Vector of voltages of those nodes where the voltage is controlled (AKA Slack and PV buses)
    @param S: Vector of power injections at all the nodes
    @param pq: list of PQ node indices
    @param pv: list of PV node indices
    @param vd: list of Slack node indices
    @return: 
    """
    
    
    """
    Reduction of the circuit magnitudes.

    Args:
        n_bus: 

        Yseries: 

        slack_indices: Array of indices of the slack nodes

        Vset: 

        S: 

    Output:
        Yred: Reduced admittance matrix (Without the rows and columns belonging to slack buses)

        I: Matrix of currents (In practice only one slack bus is selected, hence it is a vector) injected by the slack buses

        Sred: Array of power injections of the buses that are not of type slack

        types_red: Array of types of the buses that are not of type slack

        non_slack_indices: Array of indices of the buses that are not of type slack
    """

    # now to have efficient arrays of coefficients
    map_idx = zeros(n_bus, dtype=np.int)
    map_w = zeros(n_bus, dtype=np.int)
    npq = 0
    npv = 0
    npqpv = 0

    for i in pq:
        map_idx[i] = npq
        map_w[i] = npqpv
        npq += 1
        npqpv += 1

    for i in pv:
        map_idx[i] = npv
        map_w[i] = npqpv
        npv += 1
        npqpv += 1

    # build the expanded system matrix
    Ysys = zeros((2*n_bus, 2*n_bus))

    for a, b in product(range(n_bus), range(n_bus)):
        Ysys[2*a, 2*b] = Yseries[a, b].real
        Ysys[2*a, 2*b+1] = -Yseries[a, b].imag
        Ysys[2*a+1, 2*b] = Yseries[a, b].imag
        Ysys[2*a+1, 2*b+1] = Yseries[a, b].real

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
        Ypv[2*a, kk] = Yseries[a, b].real
        Ypv[2*a+1, kk] = Yseries[a, b].imag
    # print('Ypv\n', Ypv)

    Vset2 = Vset * Vset

    return sparse(Ysys), Ypv, Vset2, map_idx, map_w, npq, npv


# @jit(cache=True)
def RHS(n, nbus, Ysh, Ypv, S, Vset, Vset_abs2, C, W, Q, pq, pv, vd, map_idx, map_w):
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
    Vre = ones(len(pv))

    for k in pq:
        val = RHS_PQ(n, k, Ysh, C, S, W, map_w)
        rhs[2 * k] = val.real
        rhs[2 * k + 1] = val.imag

    for k in vd:
        val = RHS_VD(n, k, Vset)
        rhs[2 * k] = val.real
        rhs[2 * k + 1] = val.imag

    for k in pv:
        val = RHS_PV(n, k, Ysh, S, C, Q, W, map_idx, map_w)
        rhs[2 * k] = val.real
        rhs[2 * k + 1] = val.imag

        kk = map_idx[k]
        Vre[kk] = calc_Vre(n, k, C, Vset_abs2).real
        rhs -= Ypv[:, kk] * Vre[kk]

    return rhs, Vre


def delta(n, k):
    return n == k  # is 1 for n==k, 0 otherwise


# @jit(cache=True)
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
    if n == 0:
        return complex_type(1) * delta(n, 0)
    else:
        return (Vset[k] - complex_type(1)) * delta(n, 1)


# @jit(cache=True)
def RHS_PQ(n, k, Ysh, C, S, W, map_w):
    """
    Right hand side calculation for a PQ bus.

    Args:
        n: Order of the coefficients

        k: Index of the bus

        Ysh: Vector where every elements the sum of the corresponding row of the reduced admittance matrix)

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
        return conj(S[k]) * conj(W[n-1, kw]) - Ysh[k] * C[n - 1, k]  # ASU version


def calc_W(n, k, kw, C, W):
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

    if n == 0:
        res = complex_type(1)
    else:
        res = complex_type(0)
        for l in range(n):
            res -= W[l, kw] * C[n-l, k]

    res /= conj(C[0, k])

    return res


def RHS_PV(n, k, Ysh, S, C, Q, W, map_idx, map_w):
    """
    Right hand side calculation for a PQ bus.

    Args:
        n: Order of the coefficients

        k: Index of the bus

        Ysh: Vector where every elements the sum of the corresponding row of the shunt admittance matrix

        S: Vector of power injections (nbus elements)

        C: Voltage coefficients (Ncoeff x nbus elements)

        Q: Reactive power coefficients (Ncoeff x nbus elements)

        W: Inverse coefficients structure (Ncoeff x nbus elements)
    Output:
        Right hand side value for the pv nodes
    """

    if n == 0:
        return 0  # -1j * Q[0, kk] / conj(C[0, k])

    else:
        kk = map_idx[k]
        kw = map_w[k]
        val = complex_type(0)
        for l in range(1, n):   # this includes the n-1
            val += Q[l, kk] * W[n-l, kw].conjugate()

        n1 = n-1
        rhs = S[k].real * W[n1, kw].conjugate() - (1j * val) - Ysh[k] * C[n1, k]

    return rhs


def calc_Vre(n, k, C, Vset_abs2):
    """
    Compute the real part of the voltage for PV ndes
    Args:
        n: order
        k: PV node index
        C: Structure of voltage coefficients
        Vset_abs2: Square of the set voltage module
    Returns:
        Real part of the voltage for the PV nodes

    """
    
    # vre = delta(n, 0) + 0.5 * delta(n, 1) * (Vset_abs2[k] - 1) - 0.5 * R

    if n == 0:
        return complex_type(1)
    elif n == 1:
        R = calc_R(n, k, C)
        return 0.5 * (Vset_abs2[k] - 1) - 0.5 * R
    else:
        return complex_type(0)

    return vre


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

    result = complex_type(0)
    for l in range(n+1):
        result += C[l, k] * C[n-l, k].conjugate()

    return result


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
    try:
        b = solve(C, -rhs)  # bn to b1
    except:
        print()
        return 0, zeros(L+1, dtype=complex_type), zeros(L+1, dtype=complex_type)
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


def interprete_solution(nbus, npv, pv, pqvd, x_sol, Vre, map_idx):
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
        Voltages coefficients and reactive power coefficients for the PV nodes at the order of x_sol
    """
    C = zeros(nbus, dtype=complex_type)
    Q = zeros(npv)

    # for k in pqvd:  # non vectorized code
    #     C[k] = x_sol[2 * k] + 1j * x_sol[2 * k + 1]

    # set the PQ and Slack nodes
    C[pqvd] = x_sol[2 * pqvd] + 1j * x_sol[2 * pqvd + 1]

    # for k in pv:  # non vectorized code
    #     kk = map_idx[k]
    #     Q[kk] = x_sol[2 * k]
    #     C[k] = Vre[kk] + 1j * x_sol[2 * k + 1]

    # Set the PV nodes
    kk = map_idx[pv]
    Q[kk] = x_sol[2 * pv]
    C[pv] = Vre[kk] + 1j * x_sol[2 * pv + 1]

    return C, Q


def helm(Y, Ys, Ysh, max_coefficient_count, S, voltage_set_points, pq, pv, vd, eps=1e-3, use_pade=True):
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
    """

    nbus = np.shape(Ys)[0]

    # The routines in this script are meant to handle sparse matrices, hence non-sparse ones are not allowed
    assert(issparse(Ys))
    # assert(not np.all((Ys + sparse(np.eye(nbus) * Ysh) != Y).data))

    # Make bus type lists combinations that are going to be used later
    pqvd = r_[pq, vd]
    pqvd.sort()
    pqpv = r_[pq, pv]
    pqpv.sort()

    print('Ymat:\n', Y.todense())
    print('Yseries:\n', Ys.todense())
    print('Yshunt:\n', Ysh)

    # prepare the arrays
    Ysys, Ypv, Vset, map_idx, map_w, npq, npv = pre_process(n_bus=nbus, Yseries=Ys, Vset=voltage_set_points,
                                                            pq=pq, pv=pv, vd=vd)

    print('Ysys:\n', Ysys.todense())

    # F = np.zeros(nbus, dtype=complex_type)
    # F[Ysh.indices] = Ysh.data

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
    errors = list()
    errors_PV_P = list()
    errors_PV_Q = list()
    errors_PQ_P= list()
    errors_PQ_Q = list()
    voltages = list()
    Sn_v = zeros(nbus, dtype=complex_type)
    Sn_q = zeros(npv, dtype=complex_type)
    voltages_vector = zeros(nbus, dtype=complex_type)
    Vred_last = zeros(nbus, dtype=complex_type)
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
        # n, nbus, F, Ypv, S, Vset, Vset_abs2, C, W, Q, pq, pv, vd, map_idx, map_w,
        rhs, Vre = RHS(n, nbus, Ysh, Ypv, S, Vset, Vset_abs2, C, W, Q, pq, pv, vd, map_idx, map_w)

        # Solve the linear system to obtain the new coefficients
        x_sol = solve(rhs)

        # assign the voltages and the reactive power values correctly
        C[n, :], Q[n, :] = interprete_solution(nbus, npv, pv, pqvd, x_sol, Vre, map_idx)

        # copy variables for the epsilon algorithm
        if not use_pade:
            E_v[n, :] = C[n, :]
            E_q[n, :] = Q[n, :]
            Sn_v += C[n, :]
            Sn_q += Q[n, :]

        # Update the inverse voltage coefficients W for the non slack nodes
        for k in pqpv:
            kw = map_w[k]  # actual index in the coefficients structure
            W[n, kw] = calc_W(n, k, kw, C, W)

        # calculate the reactive power
        for k in pv:
            kk = map_idx[k]
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
                voltages_vector[k], E_v[:, k] = epsilon(Sn_v[k], n, E_v[:, k])

            if np.isnan(voltages_vector[k]):
                print('Maximum precision reached at ', n)
                voltages_vector = Vred_last
                inside_precision = False
                break

        Vred_last = voltages_vector.copy()

        # Compose the voltage values from the coefficient series
        voltages.append(voltages_vector.copy())
        # print(voltages_vector)

        # Calculate the error and check the convergence
        Scalc = voltages_vector * conj(Y * voltages_vector)
        power_mismatch = Scalc - S  # complex power mismatch
        power_mismatch_ = r_[power_mismatch[pv].real, power_mismatch[pq].real, power_mismatch[pq].imag]  # concatenate error by type

        # check for convergence
        normF = linalg.norm(power_mismatch_, Inf)
        errors.append(normF)
        errors_PV_P.append(power_mismatch[pv].real)
        errors_PV_Q.append(power_mismatch[pv].imag)
        errors_PQ_P.append(power_mismatch[pq].real)
        errors_PQ_Q.append(power_mismatch[pq].imag)
        if normF < eps:
            converged = True
        else:
            converged = False

        n += 1  # increase the coefficients order

    # errors_lst = [array(errors), array(errors_PV_P), array(errors_PV_Q), array(errors_PQ_P), array(errors_PQ_Q)]

    return Vred_last, converged, normF, Scalc


def bifurcation_point(C, slackIndices):
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

            bpoint = asint[0]
            # bpoint = max(asint)
            lmda = np.linspace(1, bpoint, npoints+1)[:-1]
            # lmda = np.linspace(1, 100, npoints)

            pval = np.polyval(p[::-1], lmda)
            qval = np.polyval(q[::-1], lmda)

            V[:, k] = pval / qval
            L[:, k] = lmda

    return V, L

