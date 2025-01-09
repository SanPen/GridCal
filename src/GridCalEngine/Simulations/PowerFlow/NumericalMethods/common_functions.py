# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numba as nb
import numpy as np
from scipy.sparse import csc_matrix
from typing import Tuple, Union
from GridCalEngine.basic_structures import Vec, CxVec, IntVec, CscMat


@nb.njit(cache=True)
def csc_diagonal_from_array(m, array) -> Tuple[IntVec, IntVec, Union[Vec, CxVec, IntVec]]:
    """
    Generate CSC sparse diagonal matrix from array
    :param m: Size of array
    :param array: Array
    :return: indices, indptr, data
    """
    indptr = np.empty(m + 1, dtype=nb.int32)
    indices = np.empty(m, dtype=nb.int32)
    data = np.empty(m, dtype=nb.complex128)
    for i in range(m):
        indptr[i] = i
        indices[i] = i
        data[i] = array[i]
    indptr[m] = m

    return indices, indptr, data


def diag(x) -> csc_matrix:
    """
    CSC diagonal matrix from array
    :param x:
    :return: csc_matrix
    """
    m = x.shape[0]
    indices, indptr, data = csc_diagonal_from_array(m, x)
    return csc_matrix((data, indices, indptr), shape=(m, m))


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


@nb.jit(nopython=True, cache=True, fastmath=True)
def compute_converter_losses(V: CxVec,
                             It: CxVec,
                             F: IntVec,
                             alpha1: Vec,
                             alpha2: Vec,
                             alpha3: Vec,
                             iVscL: IntVec) -> Vec:
    """
    Compute the converter losses according to the IEC 62751-2
    :param V: array of voltages
    :param It: array of currents "to"
    :param F: array of "from" bus indices of every branch
    :param alpha1: array of alpha1 parameters
    :param alpha2: array of alpha2 parameters
    :param alpha3: array of alpha3 parameters
    :param iVscL: array of VSC converter indices
    :return: switching losses array
    """
    # # Standard IEC 62751-2 Ploss Correction for VSC losses
    # Ivsc = np.abs(It[iVscL])
    # PLoss_IEC = alpha3[iVscL] * np.power(Ivsc, 2)
    # PLoss_IEC += alpha2[iVscL] * np.power(Ivsc, 2)
    # PLoss_IEC += alpha1[iVscL]
    #
    # # compute G-switch
    # Gsw = np.zeros(len(F))
    # Gsw[iVscL] = PLoss_IEC / np.power(np.abs(V[F[iVscL]]), 2)

    Gsw = np.zeros(len(F))
    for i in iVscL:
        Ivsc = np.abs(It[i])
        Ivsc2 = Ivsc * Ivsc

        # Standard IEC 62751-2 Ploss Correction for VSC losses
        PLoss_IEC = alpha3[i] * Ivsc2 + alpha2[i] * Ivsc + alpha1[i]

        # compute G-switch
        Gsw[i] = PLoss_IEC / np.power(np.abs(V[F[i]]), 2)

    return Gsw


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


@nb.jit(nopython=True, cache=True, fastmath=True)
def compute_acdc_fx(Vm: Vec,
                    Sbus: CxVec,
                    Scalc: CxVec,
                    Sf: CxVec,
                    St: CxVec,
                    Pfset: Vec,
                    Qfset: Vec,
                    Qtset: Vec,
                    Vmfset: Vec,
                    Kdp: Vec,
                    F: IntVec,
                    pvpq: IntVec,
                    pq: IntVec,
                    k_pf_tau: IntVec,
                    k_qf_m: IntVec,
                    k_zero_beq: IntVec,
                    k_qt_m: IntVec,
                    k_pf_dp: IntVec,
                    i_vf_beq: IntVec,
                    i_vt_m: IntVec) -> Vec:
    """
    Compute the FUBM increments vector
    :param Vm: Voltages module array
    :param Sbus: Array of specified bus power
    :param Scalc: Array of computed bus power
    :param Sf: Array of calculated branch flows seen at the "from" bus
    :param St: Array of calculated branch flows seen at the "to" bus
    :param Pfset: Array of Pf set values per branch
    :param Qfset: Array of Qf set values per branch
    :param Qtset: Array of Qt set values per branch
    :param Vmfset: Array of Vf module set values per branch
    :param Kdp: Array of branch droop value per branch
    :param F: Array of from bus indices of the Branches
    :param pvpq: Array of pv|pq bus indices
    :param pq: Array of pq indices
    :param k_pf_tau: indices of the branches controlling Pf with tau (the tap angle)
    :param k_qf_m: indices of the branches controlling Qf with m (the tap module)
    :param k_zero_beq: indices of the branches making Qf=0 with Beq
    :param k_qt_m: indices of the branches controlling Qt with m (the tap module)
    :param k_pf_dp: indices of the branches controlling Pf with the droop equation
    :param i_vf_beq: indices of the "from" buses of the branches controlling Vf with Beq
    :param i_vt_m: indices of the "to" buses of the branches controlling Vt with m (the tap module)
    :return: mismatch vector, also known as fx or delta f
    """
    # mis = Scalc - Sbus  # F1(x0) & F2(x0) Power balance mismatch

    n = len(pvpq) + len(pq) + len(i_vf_beq) + len(i_vt_m) + len(k_pf_tau) + len(k_qf_m) + len(k_zero_beq) + len(
        k_qt_m) + len(
        k_pf_dp)

    fx = np.empty(n)

    k = 0
    for i in pvpq:
        # F1(x0) Power balance mismatch - Va
        fx[k] = Scalc[i].real - Sbus[i].real
        k += 1

    for i in pq:
        # F2a(x0) Power balance mismatch - Vm
        fx[k] = Scalc[i].imag - Sbus[i].imag
        k += 1

    for i in i_vf_beq:
        # F2b(x0) Vf control mismatch
        fx[k] = Scalc[i].imag - Sbus[i].imag
        k += 1

    for i in i_vt_m:
        # F2c(x0) Vt control mismatch
        fx[k] = Scalc[i].imag - Sbus[i].imag
        k += 1

    for i in k_qf_m:
        # F3a(x0) Qf control mismatch
        fx[k] = Sf[i].imag - Qfset[i]
        k += 1

    for i in k_zero_beq:
        # F3b(x0) Qf control mismatch
        fx[k] = Sf[i].imag - 0
        k += 1

    for i in k_qt_m:
        # F4(x0) Qt control mismatch
        fx[k] = St[i].imag - Qtset[i]
        k += 1

    for i in k_pf_tau:
        # F5(x0) Pf control mismatch
        fx[k] = Sf[i].real - Pfset[i]
        k += 1

    for i in k_pf_dp:
        # F6(x0) Pf control mismatch, Droop Pf - Pfset = Kdp*(Vmf - Vmfset)
        fx[k] = -Sf[i].real + Pfset[i] + Kdp[i] * (Vm[F[i]] - Vmfset[i])
        k += 1

    return fx


# def power_flow_post_process(
#         calculation_inputs: NumericalCircuit,
#         Sbus: CxVec,
#         V: CxVec,
#         branch_rates: CxVec,
#         Ybus: Union[CscMat, None] = None,
#         Yf: Union[CscMat, None] = None,
#         Yt: Union[CscMat, None] = None,
#         method: Union[None, SolverType] = None
# ) -> Tuple[CxVec, CxVec, CxVec, CxVec, CxVec, CxVec, CxVec, CxVec]:
#     """
#     Compute the power Sf trough the Branches.
#     :param calculation_inputs: NumericalCircuit
#     :param Sbus: Array of computed nodal injections
#     :param V: Array of computed nodal voltages
#     :param branch_rates: Array of branch rates
#     :param Ybus: Admittance matrix
#     :param Yf: Admittance-from matrix
#     :param Yt: Admittance-to matrix
#     :param method: SolverType (the non-linear and Linear flow calculations differ)
#     :return: Sf (MVA), St (MVA), If (p.u.), It (p.u.), Vbranch (p.u.), loading (p.u.), losses (MVA), Sbus(MVA)
#     """
#     # Compute the slack and pv buses power
#     vd = calculation_inputs.vd
#     pv = calculation_inputs.pv
#
#     if method not in [SolverType.DC]:
#         if Ybus is None:
#             Ybus = calculation_inputs.Ybus
#         if Yf is None:
#             Yf = calculation_inputs.Yf
#         if Yt is None:
#             Yt = calculation_inputs.Yt
#
#         # power at the slack nodes
#         Sbus[vd] = V[vd] * np.conj(Ybus[vd, :] @ V)
#
#         # Reactive power at the pv nodes
#         P_pv = Sbus[pv].real
#         Q_pv = (V[pv] * np.conj(Ybus[pv, :] @ V)).imag
#         Sbus[pv] = P_pv + 1j * Q_pv  # keep the original P injection and set the calculated reactive power for PV nodes
#
#         # Branches current, loading, etc
#         Vf = V[calculation_inputs.passive_branch_data.F]
#         Vt = V[calculation_inputs.passive_branch_data.T]
#         If = Yf @ V
#         It = Yt @ V
#         Sf = Vf * np.conj(If)
#         St = Vt * np.conj(It)
#
#         # Branch losses in MVA
#         losses = (Sf + St) * calculation_inputs.Sbase
#
#         # branch voltage increment
#         Vbranch = Vf - Vt
#
#         # Branch power in MVA
#         Sfb = Sf * calculation_inputs.Sbase
#         Stb = St * calculation_inputs.Sbase
#
#     else:
#         # DC power flow
#         theta = np.angle(V, deg=False)
#         theta_f = theta[calculation_inputs.F]
#         theta_t = theta[calculation_inputs.T]
#
#         b = 1.0 / (calculation_inputs.passive_branch_data.X * calculation_inputs.active_branch_data.tap_module)
#         # Pf = calculation_inputs.Bf @ theta - b * calculation_inputs.branch_data.tap_angle
#
#         Pf = b * (theta_f - theta_t - calculation_inputs.active_branch_data.tap_angle)
#
#         Sfb = Pf * calculation_inputs.Sbase
#         Stb = -Pf * calculation_inputs.Sbase
#
#         Vf = V[calculation_inputs.passive_branch_data.F]
#         Vt = V[calculation_inputs.passive_branch_data.T]
#         Vbranch = Vf - Vt
#         If = Pf / (Vf + 1e-20)
#         It = -If
#         # losses are not considered in the power flow computation
#         losses = np.zeros(calculation_inputs.nbr)
#
#     # Branch loading in p.u.
#     loading = Sfb / (branch_rates + 1e-9)
#
#     return Sfb, Stb, If, It, Vbranch, loading, losses, Sbus


def power_flow_post_process_nonlinear(Sbus: CxVec, V: CxVec, F: IntVec, T: IntVec,
                                      pv: IntVec, vd: IntVec, Ybus: CscMat, Yf: CscMat, Yt: CscMat,
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

    # Branches current, loading, etc
    Vf = V[F]
    Vt = V[T]
    If = Yf @ V
    It = Yt @ V
    Sf = Vf * np.conj(If)
    St = Vt * np.conj(It)

    # Branch losses in MVA
    losses = (Sf + St) * Sbase

    # branch voltage increment
    Vbranch = Vf - Vt

    # Branch power in MVA
    Sfb = Sf * Sbase
    Stb = St * Sbase

    # Branch loading in p.u.
    loading = Sfb / (branch_rates + 1e-9)

    return Sfb, Stb, If, It, Vbranch, loading, losses, Sbus


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
