# GridCal
# Copyright (C) 2022 Santiago Peñate Vera
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
import scipy.sparse as sp
from scipy.sparse import csc_matrix


# @nb.njit("c16[:](i8, i4[:], i4[:], c16[:], c16[:], c16[:], i8)", parallel=True)
@nb.njit(cache=True)
def calc_power_csr_numba(n, Yp, Yj, Yx, V, I, n_par=500):
    """
    Compute the power vector from the CSR admittance matrix
    :param m: number of rows
    :param n: number of columns
    :param Yp: pointers
    :param Yj: indices
    :param Yx: data
    :param V: vector x (n)
    :param I
    :param n_par: Number upon which the computation is done in parallel
    :return: vector y (m)
    """

    assert n == V.shape[0]
    S = np.zeros(n, dtype=nb.complex128)

    if n < n_par:
        # serial version
        for i in range(n):  # for every row
            s = complex(0, 0)
            for p in range(Yp[i], Yp[i+1]):  # for every column
                s += Yx[p] * V[Yj[p]]
            S[i] = V[i] * np.conj(s - I[i])
    else:
        # parallel version
        for i in nb.prange(n):  # for every row
            s = complex(0, 0)
            for p in range(Yp[i], Yp[i+1]):  # for every column
                s += Yx[p] * V[Yj[p]]
            S[i] = V[i] * np.conj(s - I[i])
    return S


# @nb.njit("Tuple((i4[:], i4[:], c16[:]))(i8, c16[:])")
@nb.njit(cache=True)
def csc_diagonal_from_array(m, array):
    """

    :param m:
    :param array:
    :return:
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


def diag(x):
    """
    CSC diagonal matrix from array
    :param x:
    :return:
    """
    m = x.shape[0]
    indices, indptr, data = csc_diagonal_from_array(m, x)
    return csc_matrix((data, indices, indptr), shape=(m, m))


@nb.njit(cache=True, fastmath=True)
def polar_to_rect(Vm, Va):
    return Vm * np.exp(1.0j * Va)


@nb.njit(cache=True, fastmath=True)
def compute_zip_power(S0, I0, Y0, Vm):
    """

    :param S0:
    :param I0:
    :param Y0:
    :param Vm:
    :return:
    """
    return S0 + I0 * Vm + Y0 * np.power(Vm, 2)


def compute_power(Ybus, V):
    """

    :param Ybus:
    :param V:
    :return:
    """

    # with warnings.catch_warnings():
    #     warnings.filterwarnings('error')
    #
    #     try:
    #         return V * np.conj(Ybus * V)
    #     except Warning as e:
    #         print()

    return V * np.conj(Ybus * V)


@nb.njit(cache=True, fastmath=True)
def compute_fx(Scalc, Sbus, pvpq, pq):
    """

    :param Scalc:
    :param Sbus:
    :param pvpq:
    :param pq:
    :return:
    """
    # dS = Scalc - Sbus  # compute the mismatch
    # return np.r_[dS[pvpq].real, dS[pq].imag]

    n = len(pvpq) + len(pq)

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

    return fx


def compute_fx_error(fx):
    """

    :param fx:
    :return:
    """
    return np.linalg.norm(fx, np.inf)


@nb.jit(nopython=True, cache=True, fastmath=True)
def compute_converter_losses(V, It, F, alpha1, alpha2, alpha3, iVscL):
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
def compute_acdc_fx(Vm, Sbus, Scalc, Sf, St, Pfset, Qfset, Qtset, Vmfset, Kdp, F,
                    pvpq, pq, iPfsh, iQfma, iBeqz, iQtma, iPfdp, VfBeqbus, Vtmabus):
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
    :param F: Array of from bus indices of the branches
    :param T: Array of to bus indices of the branches
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

    n = len(pvpq) + len(pq) + len(VfBeqbus) + len(Vtmabus) + len(iPfsh) + len(iQfma) + len(iBeqz) + len(iQtma) + len(iPfdp)

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


def compute_acdc_fx_old(Vm, Sbus, Scalc, Sf, St, Pfset, Qfset, Qtset, Vmfset, Kdp, F,
                        pvpq, pq, iPfsh, iQfma, iBeqz, iQtma, iPfdp, VfBeqbus, Vtmabus):
    """
    Compute the increments vector
    :param Vm: Voltages module array
    :param Sbus: Array of bus power matrix
    :param Pfset: Array of Pf set values per branch
    :param Qfset: Array of Qf set values per branch
    :param Qtset: Array of Qt set values per branch
    :param Vmfset: Array of Vf module set values per branch
    :param Kdp: Array of branch droop value per branch
    :param F:
    :param T:
    :param pvpq:
    :param pq:
    :param iPfsh:
    :param iQfma:
    :param iBeqz:
    :param iQtma:
    :param iPfdp:
    :param VfBeqbus:
    :param Vtmabus:
    :return:
    """
    mis = Scalc - Sbus  # F1(x0) & F2(x0) Power balance mismatch

    misPbus = mis[pvpq].real  # F1(x0) Power balance mismatch - Va
    misQbus = mis[pq].imag  # F2(x0) Power balance mismatch - Vm
    misBeqv = mis[VfBeqbus].imag  # F6(x0) Vf control mismatch
    misVtma = mis[Vtmabus].imag  # F7(x0) Vt control mismatch

    misPfsh = Sf[iPfsh].real - Pfset[iPfsh]  # F3(x0) Pf control mismatch
    misQfma = Sf[iQfma].imag - Qfset[iQfma]  # F4(x0) Qf control mismatch
    misBeqz = Sf[iBeqz].imag - 0  # F5(x0) Qf control mismatch
    misQtma = St[iQtma].imag - Qtset[iQtma]  # F8(x0) Qt control mismatch
    misPfdp = -Sf[iPfdp].real + Pfset[iPfdp] + Kdp[iPfdp] * (Vm[F[iPfdp]] - Vmfset[iPfdp])  # F9(x0) Pf control mismatch, Droop Pf - Pfset = Kdp*(Vmf - Vmfset)
    # -------------------------------------------------------------------------

    #  Create F vector
    # FUBM ---------------------------------------------------------------------

    fx = np.r_[misPbus,  # F1(x0) Power balance mismatch - Va
               misQbus,  # F2(x0) Power balance mismatch - Vm
               misBeqv,  # F5(x0) Qf control    mismatch - Beq
               misVtma,  # F6(x0) Vf control    mismatch - Beq
               misPfsh,  # F4(x0) Qf control    mismatch - ma
               misQfma,  # F8(x0) Qt control    mismatch - ma
               misBeqz,  # F7(x0) Vt control    mismatch - ma
               misQtma,  # F3(x0) Pf control    mismatch - Theta_shift
               misPfdp]  # F9(x0) Pf control    mismatch - Theta_shift Droop

    return fx



