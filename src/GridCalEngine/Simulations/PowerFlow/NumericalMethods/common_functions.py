# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numba as nb
import numpy as np
from scipy.sparse import csc_matrix
from typing import Tuple, Union
from GridCalEngine.basic_structures import Vec, CxVec, IntVec, CscMat


# @nb.njit(cache=True)
# def csc_diagonal_from_array(m, array) -> Tuple[IntVec, IntVec, Union[Vec, CxVec, IntVec]]:
#     """
#     Generate CSC sparse diagonal matrix from array
#     :param m: Size of array
#     :param array: Array
#     :return: indices, indptr, data
#     """
#     indptr = np.empty(m + 1, dtype=nb.int32)
#     indices = np.empty(m, dtype=nb.int32)
#     data = np.empty(m, dtype=nb.complex128)
#     for i in range(m):
#         indptr[i] = i
#         indices[i] = i
#         data[i] = array[i]
#     indptr[m] = m
#
#     return indices, indptr, data


# def diag(x) -> csc_matrix:
#     """
#     CSC diagonal matrix from array
#     :param x:
#     :return: csc_matrix
#     """
#     m = x.shape[0]
#     indices, indptr, data = csc_diagonal_from_array(m, x)
#     return csc_matrix((data, indices, indptr), shape=(m, m))


@nb.njit(cache=True, fastmath=True)
def polar_to_rect(Vm, Va) -> CxVec:
    """
    Convert polar to rectangular corrdinates
    :param Vm: Module
    :param Va: Angle in radians
    :return: Polar vector
    """
    return Vm * np.exp(1.0j * Va)


def expand(n, arr: Vec, idx: IntVec, default: float) -> Vec:
    """
    Expand array
    :param n: number of elements
    :param arr: short array
    :param idx: indices in the longer array
    :param default: default value for the longer array
    :return: longer array
    """
    x = np.full(n, default)
    if len(arr):
        x[idx] = arr
    return x


@nb.njit(cache=True, fastmath=True)
def compute_zip_power(S0: CxVec, I0: CxVec, Y0: CxVec, Vm: Vec) -> CxVec:
    """
    Compute the equivalent power injection
    :param S0: Base power (P + jQ)
    :param I0: Base current (Ir + jIi)
    :param Y0: Base admittance (G + jB)
    :param Vm: voltage module
    :return: complex power injection
    """
    return S0 + np.conj(I0 + Y0 * Vm) * Vm


def compute_power(Ybus: csc_matrix, V: CxVec) -> CxVec:
    """
    Compute the power from the admittance matrix and the voltage
    :param Ybus: Admittance matrix
    :param V: Voltage vector
    :return: Calculated power injections
    """
    return V * np.conj(Ybus @ V)


@nb.njit(cache=True, fastmath=True)
def compute_fx(Scalc: CxVec, Sbus: CxVec, idx_dP: IntVec, idx_dQ: IntVec) -> Vec:
    """
    Compute the NR-like error function
    f = [∆P(pqpv), ∆Q(pq)]
    :param Scalc: Calculated power injections
    :param Sbus: Specified power injections
    :param idx_dP: Array of node indices updated with dP (pvpq)
    :param idx_dQ: Array of node indices updated with dQ (pq)
    :return: error
    """
    # dS = Scalc - Sbus  # compute the mismatch
    # return np.r_[dS[idx_dP].real, dS[idx_dQ].imag]

    n = len(idx_dP) + len(idx_dQ)

    fx = np.empty(n, dtype=float)

    k = 0
    for i in idx_dP:
        # F1(x0) Power balance mismatch - Va
        # fx[k] = mis[i].real
        fx[k] = Scalc[i].real - Sbus[i].real
        k += 1

    for i in idx_dQ:
        # F2(x0) Power balance mismatch - Vm
        # fx[k] = mis[i].imag
        fx[k] = Scalc[i].imag - Sbus[i].imag
        k += 1

    return fx


def compute_fx_error(fx: Vec) -> float:
    """
    Compute the infinite norm of fx
    this is the same as max(abs(fx))
    :param fx: vector
    :return: infinite norm
    """
    return np.linalg.norm(fx, np.inf)


@nb.njit()
def get_Sf(k: IntVec, Vm: Vec, V: CxVec, yff: CxVec, yft: CxVec, F: IntVec, T: IntVec):
    """

    :param k:
    :param Vm:
    :param V:
    :param yff:
    :param yft:
    :param F:
    :param T:
    :return:
    """
    f = F[k]
    t = T[k]
    return np.power(Vm[f], 2.0) * np.conj(yff[k]) + V[f] * np.conj(V[t]) * np.conj(yft[k])


@nb.njit()
def get_St(k: IntVec, Vm: Vec, V: CxVec, ytf: CxVec, ytt: CxVec, F: IntVec, T: IntVec):
    """

    :param k:
    :param Vm:
    :param V:
    :param ytf:
    :param ytt:
    :param F:
    :param T:
    :return:
    """
    f = F[k]
    t = T[k]
    return np.power(Vm[t], 2.0) * np.conj(ytt[k]) + V[t] * np.conj(V[f]) * np.conj(ytf[k])


@nb.njit()
def get_If(k: IntVec, V: CxVec, yff: CxVec, yft: CxVec, F: IntVec, T: IntVec):
    """

    :param k:
    :param V:
    :param yff:
    :param yft:
    :param F:
    :param T:
    :return:
    """
    f = F[k]
    t = T[k]
    return np.conj(V[f]) * np.conj(yff[k]) + np.conj(V[t]) * np.conj(yft[k])


@nb.njit()
def get_It(k: IntVec, V: CxVec, ytf: CxVec, ytt: CxVec, F: IntVec, T: IntVec):
    """

    :param k:
    :param V:
    :param ytf:
    :param ytt:
    :param F:
    :param T:
    :return:
    """
    f = F[k]
    t = T[k]
    return np.conj(V[t]) * np.conj(ytt[k]) + np.conj(V[f]) * np.conj(ytf[k])


def power_flow_post_process_nonlinear(Sbus: CxVec, V: CxVec, F: IntVec, T: IntVec,
                                      pv: IntVec, vd: IntVec, Ybus: CscMat, Yf: CscMat, Yt: CscMat, Yshunt_bus: CxVec,
                                      branch_rates: Vec, Sbase: float):
    """

    :param Sbus:
    :param V:
    :param F:
    :param T:
    :param pv:
    :param vd:
    :param Ybus:
    :param Yf:
    :param Yt:
    :param Yshunt_bus:
    :param branch_rates:
    :param Sbase:
    :return:
    """

    # power at the slack nodes
    Sbus[vd] = V[vd] * np.conj(Ybus[vd, :] @ V)

    # Reactive power at the pv nodes
    P_pv = Sbus[pv].real
    Q_pv = (V[pv] * np.conj(Ybus[pv, :] @ V)).imag
    Sbus[pv] = P_pv + 1j * Q_pv  # keep the original P injection and set the calculated reactive power for PV nodes

    # Add the shunt power V^2 x Y^*
    Vm = np.abs(V)
    Sbus += Vm * Vm * np.conj(Yshunt_bus)

    # Branches current, loading, etc
    Vf = V[F]
    Vt = V[T]
    If = Yf @ V
    It = Yt @ V
    Sf = Vf * np.conj(If) * Sbase
    St = Vt * np.conj(It) * Sbase

    # Branch losses in MVA
    losses = (Sf + St)

    # branch voltage increment
    Vbranch = Vf - Vt

    # Branch loading in p.u.
    loading = Sf / (branch_rates + 1e-9)

    return Sf, St, If, It, Vbranch, loading, losses, Sbus


def power_flow_post_process_linear(Sbus: CxVec, V: CxVec,
                                   active: IntVec, X: Vec, tap_module: Vec, tap_angle: Vec,
                                   F: IntVec, T: IntVec,
                                   branch_rates: Vec, Sbase: float):
    """

    :param Sbus:
    :param V:
    :param active:
    :param X:
    :param tap_module:
    :param tap_angle:
    :param F:
    :param T:
    :param branch_rates:
    :param Sbase:
    :return:
    """

    # DC power flow
    theta = np.angle(V, deg=False)
    theta_f = theta[F]
    theta_t = theta[T]

    b = active.astype(float) / (X * tap_module)
    # Pf = calculation_inputs.Bf @ theta - b * calculation_inputs.branch_data.tap_angle

    Pf = b * (theta_f - theta_t - tap_angle)

    Sfb = Pf * Sbase
    Stb = -Pf * Sbase

    Vf = V[F]
    Vt = V[T]
    Vbranch = Vf - Vt
    If = Pf / (Vf + 1e-20)
    It = -If

    # losses are not considered in the power flow computation
    losses = np.zeros(len(X))

    # Branch loading in p.u.
    loading = Sfb / (branch_rates + 1e-9)

    return Sfb, Stb, If, It, Vbranch, loading, losses, Sbus
