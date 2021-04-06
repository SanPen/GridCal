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

import os
import time

import numpy as np
import numba as nb
from scipy.sparse import lil_matrix, diags, csc_matrix


import GridCal.Engine.Simulations.PowerFlow.derivatives as deriv


@nb.njit()
def make_lookup(n, arr):
    lookup = np.zeros(n, dtype=np.int32)
    lookup[arr] = np.arange(len(arr), dtype=np.int32)
    return lookup


def fubm_jacobian(nb, nl, iPfsh, iPfdp, iQfma, iQtma, iVtma, iBeqz, iBeqv, VfBeqbus, Vtmabus,
                  F, T, Ys, k2, tap, ma, Bc, Beq, Kdp, V, Ybus, Yf, Yt, Cf, Ct, pvpq, pq):
    """
    Compute the FUBM jacobian in a dynamic fashion by only computing the derivatives that are needed
    :param nb: number of buses
    :param nl: Number of lines
    :param iPfsh: indices of the Pf controlled branches
    :param iPfdp: indices of the droop controlled branches
    :param iQfma: indices of the Qf controlled branches
    :param iQtma: Indices of the Qt controlled branches
    :param iVtma: Indices of the Vt controlled branches
    :param iBeqz: Indices of the Qf controlled branches
    :param iBeqv: Indices of the Vf Controlled branches
    :param F: Array of "from" bus indices
    :param T: Array of "to" bus indices
    :param Ys: Array of branch series admittances
    :param k2: Array of branch converter losses
    :param tap: Array of complex tap values {remember tap = ma * exp(1j * theta) }
    :param ma: Array of tap modules
    :param Bc: Array of branch full susceptances
    :param Beq: Array of brach equivalent (variable) susceptances
    :param Kdp: Array of branch converter droop constants
    :param V: Array of complex bus voltages
    :param Ybus: Admittance matrix
    :param Yf: Admittances matrix of the branches with the "from" buses
    :param Yt: Admittances matrix of the branches with the "to" buses
    :param Cf: Connectivity matrix of the branches with the "from" buses
    :param Ct: Connectivity matrix of the branches with the "to" buses
    :param pvpq: Array of pv and then pq bus indices (not sorted)
    :param pq: Array of PQ bus indices
    :return: FUBM Jacobian matrix
    """
    nPfsh = len(iPfsh)
    nPfdp = len(iPfdp)
    nQfma = len(iQfma)
    nQtma = len(iQtma)
    nVtma = len(iVtma)
    nBeqz = len(iBeqz)
    nBeqv = len(iBeqv)
    nVfBeqbus = len(VfBeqbus)
    nVtmabus = len(Vtmabus)
    npq = len(pq)
    npvpq = len(pvpq)
    nbus = Ybus.shape[0]
    nbr = Yf.shape[0]

    i2 = np.r_[pq, VfBeqbus, Vtmabus]
    i4 = np.r_[iQfma, iBeqz]
    ni2 = len(i2)
    ni4 = len(i4)

    # compose the derivatives of the power injections w.r.t Va and Vm
    dSbus_dVa, dSbus_dVm = deriv.dSbus_dV_csc(Ybus, V)

    # compose the derivatives of the branch flow w.r.t Va and Vm
    Vc = np.conj(V)
    E = V / np.abs(V)
    dSf_dVa, dSf_dVm = deriv.dSf_dV_fast(Yf, V, Vc, E, F, Cf)

    if nQtma:
        dSt_dVa, dSt_dVm = deriv.dSf_dV_fast(Yt, V, Vc, E, T, Ct)

    nnz = 0
    p = 0
    n_cols = npvpq + npq + nBeqz + nBeqv + nQfma + nQtma + nVtma + nPfsh + nPfdp
    n_rows = n_cols

    nnz_estimate = Ybus.nnz * 8
    Jx = np.empty(nnz_estimate, dtype=np.float64)  # data
    Ji = np.empty(nnz_estimate, dtype=np.int32)  # indices
    Jp = np.empty(n_cols + 1, dtype=np.int32)  # pointers
    Jp[p] = 0

    # generate lookup for the row slicing
    pvpq_lookup = make_lookup(nbus, pvpq)
    i2_lookup = make_lookup(nbus, i2)
    iPfsh_lookup = make_lookup(nbr, iPfsh)
    i4_lookup = make_lookup(nbr, i4)
    iQtma_lookup = make_lookup(nbr, iQtma)
    iPfdp_lookup = make_lookup(nbr, iPfdp)

    # column 1: derivatives w.r.t Va -----------------------------------------------------------------------------------
    for j in pvpq:  # sliced columns

        # J11
        if npvpq:
            for k in range(Ybus.indptr[j], Ybus.indptr[j + 1]):  # rows of A[:, j]

                # row index translation to the "rows" space
                i = Ybus.indices[k]
                ii = pvpq_lookup[i]

                if pvpq[ii] == i:
                    # entry found
                    Jx[nnz] = dSbus_dVa.data[k].real
                    Ji[nnz] = ii
                    nnz += 1

        # J21 J31 J41
        offset = npvpq
        if ni2:
            for k in range(Ybus.indptr[j], Ybus.indptr[j + 1]):  # rows of A[:, j]

                # row index translation to the "rows" space
                i = Ybus.indices[k]
                ii = i2_lookup[i]

                if i2[ii] == i:
                    # entry found
                    Jx[nnz] = dSbus_dVa.data[k].imag
                    Ji[nnz] = ii + offset
                    nnz += 1

        # J51
        offset += ni2
        if nPfsh:
            for k in range(dSf_dVa.indptr[j], dSf_dVa.indptr[j + 1]):  # rows of A[:, j]

                # row index translation to the "rows" space
                i = dSf_dVa.indices[k]
                ii = iPfsh_lookup[i]

                if iPfsh[ii] == i:
                    # entry found
                    Jx[nnz] = dSf_dVa.data[k].real
                    Ji[nnz] = ii + offset
                    nnz += 1

        # J61 J71
        offset += nPfsh
        if ni4:
            for k in range(dSf_dVa.indptr[j], dSf_dVa.indptr[j + 1]):  # rows of A[:, j]

                # row index translation to the "rows" space
                i = dSf_dVa.indices[k]
                ii = i4_lookup[i]

                if i4[ii] == i:
                    # entry found
                    Jx[nnz] = dSf_dVa.data[k].imag
                    Ji[nnz] = ii + offset
                    nnz += 1

        # J81
        offset += ni4
        if nQtma:
            for k in range(dSt_dVa.indptr[j], dSt_dVa.indptr[j + 1]):  # rows of A[:, j]

                # row index translation to the "rows" space
                i = dSt_dVa.indices[k]
                ii = iQtma_lookup[i]

                if iQtma[ii] == i:
                    # entry found
                    Jx[nnz] = dSt_dVa.data[k].imag
                    Ji[nnz] = ii + offset
                    nnz += 1

        # J91
        offset += nQtma
        if nPfdp:
            for k in range(dSf_dVa.indptr[j], dSf_dVa.indptr[j + 1]):  # rows of A[:, j]

                # row index translation to the "rows" space
                i = dSf_dVa.indices[k]
                ii = iPfdp_lookup[i]

                if iPfdp[ii] == i:
                    # entry found
                    Jx[nnz] = -dSf_dVa[k].real
                    Ji[nnz] = ii + offset
                    nnz += 1

        # finalize column
        p += 1
        Jp[p] = nnz

    # column 2: derivatives w.r.t Vm -----------------------------------------------------------------------------------
    for j in pq:  # sliced columns

        # J11
        if npvpq:
            for k in range(Ybus.indptr[j], Ybus.indptr[j + 1]):  # rows of A[:, j]

                # row index translation to the "rows" space
                i = Ybus.indices[k]
                ii = pvpq_lookup[i]

                if pvpq[ii] == i:
                    # entry found
                    Jx[nnz] = dSbus_dVm.data[k].real
                    Ji[nnz] = ii
                    nnz += 1

        # J21 J31 J41
        offset = npvpq
        if ni2:
            for k in range(Ybus.indptr[j], Ybus.indptr[j + 1]):  # rows of A[:, j]

                # row index translation to the "rows" space
                i = Ybus.indices[k]
                ii = i2_lookup[i]

                if i2[ii] == i:
                    # entry found
                    Jx[nnz] = dSbus_dVm.data[k].imag
                    Ji[nnz] = ii + offset
                    nnz += 1

        # J51
        offset += ni2
        if nPfsh:
            for k in range(dSf_dVm.indptr[j], dSf_dVm.indptr[j + 1]):  # rows of A[:, j]

                # row index translation to the "rows" space
                i = dSf_dVm.indices[k]
                ii = iPfsh_lookup[i]

                if iPfsh[ii] == i:
                    # entry found
                    Jx[nnz] = dSf_dVm.data[k].real
                    Ji[nnz] = ii + offset
                    nnz += 1

        # J61 J71
        offset += nPfsh
        if ni4:
            for k in range(dSf_dVm.indptr[j], dSf_dVm.indptr[j + 1]):  # rows of A[:, j]

                # row index translation to the "rows" space
                i = dSf_dVm.indices[k]
                ii = i4_lookup[i]

                if i4[ii] == i:
                    # entry found
                    Jx[nnz] = dSf_dVm.data[k].imag
                    Ji[nnz] = ii + offset
                    nnz += 1

        # J81
        offset += ni4
        if nQtma:
            for k in range(dSt_dVm.indptr[j], dSt_dVm.indptr[j + 1]):  # rows of A[:, j]

                # row index translation to the "rows" space
                i = dSt_dVm.indices[k]
                ii = iQtma_lookup[i]

                if iQtma[ii] == i:
                    # entry found
                    Jx[nnz] = dSt_dVm.data[k].imag
                    Ji[nnz] = ii + offset
                    nnz += 1

        # J91
        offset += nQtma
        if nPfdp:

            # compute the droop derivative
            dVmf_dVm = lil_matrix((nl, nb))
            dVmf_dVm[iPfdp, :] = Cf[iPfdp, :]
            dPfdp_dVm = -dSf_dVm.real + diags(Kdp) * dVmf_dVm

            for k in range(dPfdp_dVm.indptr[j], dPfdp_dVm.indptr[j + 1]):  # rows of A[:, j]

                # row index translation to the "rows" space
                i = dPfdp_dVm.indices[k]
                ii = iPfdp_lookup[i]

                if iPfdp[ii] == i:
                    # entry found
                    Jx[nnz] = dPfdp_dVm[k]
                    Ji[nnz] = ii + offset
                    nnz += 1

        # finalize column
        p += 1
        Jp[p] = nnz

    # Column 3: derivatives w.r.t Beq for iBeqz + iBeqv ----------------------------------------------------------------
    if nBeqz + nBeqv:
        dSbus_dBeqz, dSf_dBeqz, dSt_dBeqz = deriv.derivatives_Beq_csc_fast(nb, nl, np.r_[iBeqz, iBeqv],
                                                                           F, T, V, ma, k2)

        for j in range(nBeqz + nBeqv):  # sliced columns

            # J11
            if npvpq:
                for k in range(dSbus_dBeqz.indptr[j], dSbus_dBeqz.indptr[j + 1]):  # rows of A[:, j]

                    # row index translation to the "rows" space
                    i = dSbus_dBeqz.indices[k]
                    ii = pvpq_lookup[i]

                    if pvpq[ii] == i:
                        # entry found
                        Jx[nnz] = dSbus_dBeqz.data[k].real
                        Ji[nnz] = ii
                        nnz += 1

            # J21 J31 J41
            offset = npvpq
            if ni2:
                for k in range(dSbus_dBeqz.indptr[j], dSbus_dBeqz.indptr[j + 1]):  # rows of A[:, j]

                    # row index translation to the "rows" space
                    i = dSbus_dBeqz.indices[k]
                    ii = i2_lookup[i]

                    if i2[ii] == i:
                        # entry found
                        Jx[nnz] = dSbus_dBeqz.data[k].imag
                        Ji[nnz] = ii + offset
                        nnz += 1

            # J51
            offset += ni2
            if nPfsh:
                for k in range(dSf_dBeqz.indptr[j], dSf_dBeqz.indptr[j + 1]):  # rows of A[:, j]

                    # row index translation to the "rows" space
                    i = dSf_dBeqz.indices[k]
                    ii = iPfsh_lookup[i]

                    if iPfsh[ii] == i:
                        # entry found
                        Jx[nnz] = dSf_dBeqz.data[k].real
                        Ji[nnz] = ii + offset
                        nnz += 1

            # J61 J71
            offset += nPfsh
            if ni4:
                for k in range(dSf_dBeqz.indptr[j], dSf_dBeqz.indptr[j + 1]):  # rows of A[:, j]

                    # row index translation to the "rows" space
                    i = dSf_dBeqz.indices[k]
                    ii = i4_lookup[i]

                    if i4[ii] == i:
                        # entry found
                        Jx[nnz] = dSf_dBeqz.data[k].imag
                        Ji[nnz] = ii + offset
                        nnz += 1

            # J81
            offset += ni4
            if nQtma:
                for k in range(dSt_dBeqz.indptr[j], dSt_dBeqz.indptr[j + 1]):  # rows of A[:, j]

                    # row index translation to the "rows" space
                    i = dSt_dBeqz.indices[k]
                    ii = iQtma_lookup[i]

                    if iQtma[ii] == i:
                        # entry found
                        Jx[nnz] = dSt_dBeqz.data[k].imag
                        Ji[nnz] = ii + offset
                        nnz += 1

            # J91
            offset += nQtma
            if nPfdp:
                for k in range(dSf_dBeqz.indptr[j], dSf_dBeqz.indptr[j + 1]):  # rows of A[:, j]

                    # row index translation to the "rows" space
                    i = dSf_dBeqz.indices[k]
                    ii = iPfdp_lookup[i]

                    if iPfdp[ii] == i:
                        # entry found
                        Jx[nnz] = -dSf_dBeqz[k].real
                        Ji[nnz] = ii + offset
                        nnz += 1

            # finalize column
            p += 1
            Jp[p] = nnz

    # Column 4: derivative w.r.t ma for iQfma + iQfma + iVtma ----------------------------------------------------------
    if nQfma + nQtma + nVtma:

        dSbus_dQfma, dSf_dQfma, dSt_dQfma = deriv.derivatives_ma_csc_fast(nb, nl, np.r_[iQfma, iQtma, iVtma],
                                                                          F, T, Ys, k2, tap, ma, Bc, Beq, V)

        for j in range(nQfma + nQtma + nVtma):  # sliced columns

            # J11
            if npvpq:
                for k in range(dSbus_dQfma.indptr[j], dSbus_dQfma.indptr[j + 1]):  # rows of A[:, j]

                    # row index translation to the "rows" space
                    i = dSbus_dQfma.indices[k]
                    ii = pvpq_lookup[i]

                    if pvpq[ii] == i:
                        # entry found
                        Jx[nnz] = dSbus_dQfma.data[k].real
                        Ji[nnz] = ii
                        nnz += 1

            # J21 J31 J41
            offset = npvpq
            if ni2:
                for k in range(dSbus_dQfma.indptr[j], dSbus_dQfma.indptr[j + 1]):  # rows of A[:, j]

                    # row index translation to the "rows" space
                    i = dSbus_dQfma.indices[k]
                    ii = i2_lookup[i]

                    if i2[ii] == i:
                        # entry found
                        Jx[nnz] = dSbus_dQfma.data[k].imag
                        Ji[nnz] = ii + offset
                        nnz += 1

            # J51
            offset += ni2
            if nPfsh:
                for k in range(dSf_dQfma.indptr[j], dSf_dQfma.indptr[j + 1]):  # rows of A[:, j]

                    # row index translation to the "rows" space
                    i = dSf_dQfma.indices[k]
                    ii = iPfsh_lookup[i]

                    if iPfsh[ii] == i:
                        # entry found
                        Jx[nnz] = dSf_dQfma.data[k].real
                        Ji[nnz] = ii + offset
                        nnz += 1

            # J61 J71
            offset += nPfsh
            if ni4:
                for k in range(dSf_dQfma.indptr[j], dSf_dQfma.indptr[j + 1]):  # rows of A[:, j]

                    # row index translation to the "rows" space
                    i = dSf_dQfma.indices[k]
                    ii = i4_lookup[i]

                    if i4[ii] == i:
                        # entry found
                        Jx[nnz] = dSf_dQfma.data[k].imag
                        Ji[nnz] = ii + offset
                        nnz += 1

            # J81
            offset += ni4
            if nQtma:
                for k in range(dSt_dQfma.indptr[j], dSt_dQfma.indptr[j + 1]):  # rows of A[:, j]

                    # row index translation to the "rows" space
                    i = dSt_dQfma.indices[k]
                    ii = iQtma_lookup[i]

                    if iQtma[ii] == i:
                        # entry found
                        Jx[nnz] = dSt_dQfma.data[k].imag
                        Ji[nnz] = ii + offset
                        nnz += 1

            # J91
            offset += nQtma
            if nPfdp:
                for k in range(dSf_dQfma.indptr[j], dSf_dQfma.indptr[j + 1]):  # rows of A[:, j]

                    # row index translation to the "rows" space
                    i = dSf_dQfma.indices[k]
                    ii = iPfdp_lookup[i]

                    if iPfdp[ii] == i:
                        # entry found
                        Jx[nnz] = -dSf_dQfma[k].real
                        Ji[nnz] = ii + offset
                        nnz += 1

            # finalize column
            p += 1
            Jp[p] = nnz

    # Column 5: derivatives w.r.t theta sh for iPfsh + droop -----------------------------------------------------------
    if nPfsh + nPfdp > 0:

        dSbus_dPfx, dSf_dPfx, dSt_dPfx = deriv.derivatives_sh_csc_fast(nb, nl, np.r_[iPfsh, iPfdp],
                                                                       F, T, Ys, k2, tap, V)

        for j in range(nPfsh + nPfdp):  # sliced columns

            # J11
            if npvpq:
                for k in range(dSbus_dPfx.indptr[j], dSbus_dPfx.indptr[j + 1]):  # rows of A[:, j]

                    # row index translation to the "rows" space
                    i = dSbus_dPfx.indices[k]
                    ii = pvpq_lookup[i]

                    if pvpq[ii] == i:
                        # entry found
                        Jx[nnz] = dSbus_dPfx.data[k].real
                        Ji[nnz] = ii
                        nnz += 1

            # J21 J31 J41
            offset = npvpq
            if ni2:
                for k in range(dSbus_dPfx.indptr[j], dSbus_dPfx.indptr[j + 1]):  # rows of A[:, j]

                    # row index translation to the "rows" space
                    i = dSbus_dPfx.indices[k]
                    ii = i2_lookup[i]

                    if i2[ii] == i:
                        # entry found
                        Jx[nnz] = dSbus_dPfx.data[k].imag
                        Ji[nnz] = ii + offset
                        nnz += 1

            # J51
            offset += ni2
            if nPfsh:
                for k in range(dSf_dPfx.indptr[j], dSf_dPfx.indptr[j + 1]):  # rows of A[:, j]

                    # row index translation to the "rows" space
                    i = dSf_dPfx.indices[k]
                    ii = iPfsh_lookup[i]

                    if iPfsh[ii] == i:
                        # entry found
                        Jx[nnz] = dSf_dPfx.data[k].real
                        Ji[nnz] = ii + offset
                        nnz += 1

            # J61 J71
            offset += nPfsh
            if ni4:
                for k in range(dSf_dPfx.indptr[j], dSf_dPfx.indptr[j + 1]):  # rows of A[:, j]

                    # row index translation to the "rows" space
                    i = dSf_dPfx.indices[k]
                    ii = i4_lookup[i]

                    if i4[ii] == i:
                        # entry found
                        Jx[nnz] = dSf_dPfx.data[k].imag
                        Ji[nnz] = ii + offset
                        nnz += 1

            # J81
            offset += ni4
            if nQtma:
                for k in range(dSt_dPfx.indptr[j], dSt_dPfx.indptr[j + 1]):  # rows of A[:, j]

                    # row index translation to the "rows" space
                    i = dSt_dPfx.indices[k]
                    ii = iQtma_lookup[i]

                    if iQtma[ii] == i:
                        # entry found
                        Jx[nnz] = dSt_dPfx.data[k].imag
                        Ji[nnz] = ii + offset
                        nnz += 1

            # J91
            offset += nQtma
            if nPfdp:
                for k in range(dSf_dPfx.indptr[j], dSf_dPfx.indptr[j + 1]):  # rows of A[:, j]

                    # row index translation to the "rows" space
                    i = dSf_dPfx.indices[k]
                    ii = iPfdp_lookup[i]

                    if iPfdp[ii] == i:
                        # entry found
                        Jx[nnz] = -dSf_dPfx[k].real
                        Ji[nnz] = ii + offset
                        nnz += 1

            # finalize column
            p += 1
            Jp[p] = nnz

    # Finalize ----------------------------------------------------------------------------
    #  finalize the Jacobian Pointer
    Jp[p] = nnz

    Jx = np.resize(Jx, nnz)
    Ji = np.resize(Ji, nnz)

    J = csc_matrix((Jx, Ji, Jp), shape=(n_rows, n_cols))

    # if J.shape[0] != J.shape[1]:
    #     raise Exception('Invalid Jacobian shape!')
    # print(J.toarray())

    return J


# def fubm_jacobian(nb, nl, iPfsh, iPfdp, iQfma, iQtma, iVtma, iBeqz, iBeqv, VfBeqbus, Vtmabus,
#                   F, T, Ys, k2, tap, ma, Bc, Beq, Kdp, V, Ybus, Yf, Yt, Cf, Ct, pvpq, pq):
