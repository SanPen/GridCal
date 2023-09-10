# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

import numba as nb
import numpy as np
from scipy.sparse import csc_matrix
from typing import Tuple, Union
from GridCalEngine.basic_structures import Vec, CxVec, IntVec


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
    return S0 + np.conj(Y0 * Vm + I0) * Vm
    # return S0 + (Y0 * Vm + I0) * Vm


def compute_power(Ybus: csc_matrix, V: CxVec) -> CxVec:
    """
    Compute the power from the admittance matrix and the voltage
    :param Ybus: Admittance matrix
    :param V: Voltage vector
    :return: Calculated power injections
    """
    return V * np.conj(Ybus * V)


@nb.njit(cache=True, fastmath=True)
def compute_fx(Scalc: CxVec, Sbus: CxVec, pvpq: IntVec, pq: IntVec) -> Vec:
    """
    Compute the NR-like error function
    f = [∆P(pqpv), ∆Q(pq)]
    :param Scalc: Calculated power injections
    :param Sbus: Specified power injections
    :param pvpq: Array pf pq and pv node indices
    :param pq: Array of pq node indices
    :return: error
    """
    # dS = Scalc - Sbus  # compute the mismatch
    # return np.r_[dS[pvpq].real, dS[pq].imag]

    n = len(pvpq) + len(pq)

    fx = np.empty(n, dtype=float)

    k = 0
    for i in pvpq:
        # F1(x0) Power balance mismatch - Va
        # fx[k] = mis[i].real
        fx[k] = Scalc[i].real - Sbus[i].real
        k += 1

    for i in pq:
        # F2(x0) Power balance mismatch - Vm
        # fx[k] = mis[i].imag
        fx[k] = Scalc[i].imag - Sbus[i].imag
        k += 1

    return fx


def compute_fx_error(fx) -> float:
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
                    iPfsh: IntVec,
                    iQfma: IntVec,
                    iBeqz: IntVec,
                    iQtma: IntVec,
                    iPfdp: IntVec,
                    VfBeqbus: IntVec,
                    Vtmabus: IntVec) -> Vec:
    """
    Compute the increments vector
    :param Vm: Voltages module array
    :param Sbus: Array of specified bus power
    :param Scalc: Array of computed bus power
    :param Pfset: Array of Pf set values per branch
    :param Qfset: Array of Qf set values per branch
    :param Qtset: Array of Qt set values per branch
    :param Vmfset: Array of Vf module set values per branch
    :param Kdp: Array of branch droop value per branch
    :param F: Array of from bus indices of the Branches
    :param pvpq: Array of pv|pq bus indices
    :param pq: Array of pq indices
    :param iPfsh:
    :param iQfma:
    :param iBeqz:
    :param iQtma:
    :param iPfdp:
    :param VfBeqbus:
    :param Vtmabus:
    :return: mismatch vector, also known as fx or delta f
    """
    # mis = Scalc - Sbus  # F1(x0) & F2(x0) Power balance mismatch

    n = len(pvpq) + len(pq) + len(VfBeqbus) + len(Vtmabus) + len(iPfsh) + len(iQfma) + len(iBeqz) + len(iQtma) + len(
        iPfdp)

    fx = np.empty(n)

    k = 0
    for i in pvpq:
        # F1(x0) Power balance mismatch - Va
        # fx[k] = mis[i].real
        fx[k] = Scalc[i].real - Sbus[i].real
        k += 1

    for i in pq:
        # F2(x0) Power balance mismatch - Vm
        # fx[k] = mis[i].imag
        fx[k] = Scalc[i].imag - Sbus[i].imag
        k += 1

    for i in VfBeqbus:
        # F6(x0) Vf control mismatch
        fx[k] = Scalc[i].imag - Sbus[i].imag
        k += 1

    for i in Vtmabus:
        # F7(x0) Vt control mismatch
        fx[k] = Scalc[i].imag - Sbus[i].imag
        k += 1

    for i in iPfsh:
        # F3(x0) Pf control mismatch
        fx[k] = Sf[i].real - Pfset[i]
        k += 1

    for i in iQfma:
        # F4(x0) Qf control mismatch
        fx[k] = Sf[i].imag - Qfset[i]
        k += 1

    for i in iBeqz:
        # F5(x0) Qf control mismatch
        fx[k] = Sf[i].imag - 0
        k += 1

    for i in iQtma:
        # F8(x0) Qt control mismatch
        fx[k] = St[i].imag - Qtset[i]
        k += 1

    for i in iPfdp:
        # F9(x0) Pf control mismatch, Droop Pf - Pfset = Kdp*(Vmf - Vmfset)
        fx[k] = -Sf[i].real + Pfset[i] + Kdp[i] * (Vm[F[i]] - Vmfset[i])
        k += 1

    return fx
