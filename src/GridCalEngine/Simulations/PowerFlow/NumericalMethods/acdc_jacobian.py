# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
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

import numpy as np
import numba as nb
from typing import Tuple
from scipy.sparse import lil_matrix, diags, csc_matrix
import GridCalEngine.Simulations.PowerFlow.NumericalMethods.derivatives as deriv
from GridCalEngine.basic_structures import Vec, IntVec, CxVec


class AcDcSolSlicer:

    def __init__(self, pvpq, pq, k_zero_beq, k_vf_beq, k_qf_m, k_qt_m, k_vt_m, k_pf_tau, k_pf_dp):
        """
        Declare the slicing limits in the same order as the Jacobian rows
        :param pvpq: 
        :param pq: 
        :param k_zero_beq: 
        :param k_vf_beq: 
        :param k_qf_m: 
        :param k_qt_m: 
        :param k_vt_m: 
        :param k_pf_tau: 
        :param k_pf_dp: 
        """

        self.va_idx = pvpq
        self.vm_idx = pq
        self.beq_idx = np.r_[k_zero_beq, k_vf_beq]
        self.m_idx = np.r_[k_qf_m, k_qt_m, k_vt_m]
        self.tau_idx = np.r_[k_pf_tau, k_pf_dp]

        n_col_block1 = len(pvpq)
        n_col_block2 = len(pq)
        n_col_block3 = len(k_zero_beq) + len(k_vf_beq)
        n_col_block4 = len(k_qf_m) + len(k_qt_m) + len(k_vt_m)
        n_col_block5 = len(k_pf_tau) + len(k_pf_dp)

        self.a0 = 0
        self.a1 = self.a0 + n_col_block1
        self.a2 = self.a1 + n_col_block2
        self.a3 = self.a2 + n_col_block3
        self.a4 = self.a3 + n_col_block4
        self.a5 = self.a4 + n_col_block5

    def split(self, dx):
        """
        Split the linear system solution
        :param dx: linear system solution
        :return: dVa, dVm, dBeq, dm, dtau
        """
        dVa = dx[self.a0:self.a1]
        dVm = dx[self.a1:self.a2]
        dBeq = dx[self.a2:self.a3]
        dm = dx[self.a3:self.a4]
        dtau = dx[self.a4:self.a5]

        return dVa, dVm, dBeq, dm, dtau

    def assign(self, dx, Va, Vm, Beq, m, tau, mu=1.0):
        dVa = dx[self.a0:self.a1]
        dVm = dx[self.a1:self.a2]
        dBeq = dx[self.a2:self.a3]
        dm = dx[self.a3:self.a4]
        dtau = dx[self.a4:self.a5]

        # assign the new values
        if mu != 1.0:
            Va[self.va_idx] -= dVa * mu
            Vm[self.vm_idx] -= dVm * mu
            Beq[self.beq_idx] -= dBeq * mu
            m[self.m_idx] -= dm * mu
            tau[self.tau_idx] -= dtau * mu
        else:
            Va[self.va_idx] -= dVa
            Vm[self.vm_idx] -= dVm
            Beq[self.beq_idx] -= dBeq
            m[self.m_idx] -= dm
            tau[self.tau_idx] -= dtau

@nb.njit(cache=True)
def make_lookup(n, arr):
    """

    :param n: size of the lookup
    :param arr: positions of the elemnts in an array of size n
    :return:
    """
    lookup = np.zeros(n, dtype=np.int32)
    lookup[arr] = np.arange(len(arr), dtype=np.int32)
    return lookup


@nb.njit(cache=True)
def fill_acdc_jacobian_data(Jx: Vec, Ji: IntVec, Jp: IntVec,
                            Yp, Yi: IntVec,
                            Ys: CxVec,
                            dSbus_dVa_x: Vec,
                            dSbus_dVm_x: Vec,
                            dSf_dVa_x: Vec, dSf_dVa_i: IntVec, dSf_dVa_p: IntVec,
                            dSf_dVm_x: Vec, dSf_dVm_i: IntVec, dSf_dVm_p: IntVec,
                            dSt_dVa_x: Vec, dSt_dVa_i: IntVec, dSt_dVa_p: IntVec,
                            dSt_dVm_x: Vec, dSt_dVm_i: IntVec, dSt_dVm_p: IntVec,
                            dPfdp_dVm_x: Vec, dPfdp_dVm_i: IntVec, dPfdp_dVm_p: IntVec,
                            pvpq: IntVec, pq: IntVec,
                            k_pf_tau: IntVec,
                            k_qt_m: IntVec,
                            k_qf_m: IntVec,
                            k_vt_m: IntVec,
                            k_pf_dp: IntVec,
                            k_zero_beq: IntVec,
                            k_vf_beq: IntVec,
                            i_vf_beq: IntVec,
                            i_vt_m: IntVec,
                            F: IntVec, T: IntVec, V: CxVec,
                            tap_modules_m: Vec, tap_complex: CxVec,
                            k2: Vec, Bc: Vec, b_eq: Vec) -> Tuple[int, Vec, IntVec, IntVec]:
    """
    Compute the ACDC jacobian using Numba
    :param Jx: Jacobian CSC data array (to be filled)
    :param Ji: Jacobian CSC row indices array (to be filled)
    :param Jp: Jacobian CSC pointer array (to be filled)
    :param Yp: Ybus CSC pointer array
    :param Yi: Ybus CSC row indices array
    :param Ys: Branches' series admittance array
    :param dSbus_dVa_x: dSbus_dVa CSC data array
    :param dSbus_dVm_x: dSbus_dVm CSC data array
    :param dSf_dVa_x: dSf_dVa CSC data array
    :param dSf_dVa_i: dSf_dVa CSC row indices array
    :param dSf_dVa_p: dSf_dVa CSC pointer array
    :param dSf_dVm_x: dSf_dVm CSC data array
    :param dSf_dVm_i: dSf_dVm CSC row indices array
    :param dSf_dVm_p: dSf_dVm CSC pointer array
    :param dSt_dVa_x: dSt_dVa CSC data array
    :param dSt_dVa_i: dSt_dVa CSC row indices array
    :param dSt_dVa_p: dSt_dVa CSC pointer array
    :param dSt_dVm_x: dSt_dVm CSC data array
    :param dSt_dVm_i: dSt_dVm CSC row indices array
    :param dSt_dVm_p: dSt_dVm CSC pointer array
    :param dPfdp_dVm_x: dPfdp_dVm CSC data array
    :param dPfdp_dVm_i: dPfdp_dVm CSC row indices array
    :param dPfdp_dVm_p: dPfdp_dVm CSC pointer array
    :param pvpq: Array of pv and then pq bus indices (not sorted)
    :param pq: Array of PQ bus indices
    :param k_pf_tau: Indices of the Pf controlled with the shunt susceptance Branches
    :param k_qt_m: Indices of the Qt controlled with ma Branches
    :param k_qf_m: Indices of the Qf controlled with ma Branches
    :param k_vt_m: Indices of the Vt controlled with ma Branches
    :param k_pf_dp: indices of the Pf-droop controlled Branches
    :param k_zero_beq: Indices of the Qf made zero with the equivalent susceptance Branches
    :param k_vf_beq: Indices of the Vf Controlled with the equivalent susceptance Branches
    :param i_vf_beq: Indices of the buses where Vf is controlled with Beq
    :param i_vt_m: Indices of the buses where Vt is controlled with m
    :param F: Array of "from" bus indices
    :param T: Array of "to" bus indices
    :param V: Array of complex bus voltages
    :param tap_modules_m: Array of tap modules
    :param k2: Array of branch converter k2 parameters
    :param tap_complex: Array of complex tap values {remember tap = ma * exp(1j * theta) }
    :param Bc: Array of branch full susceptances
    :param b_eq: Array of branch equivalent (variable) susceptances
    :return: nnz, Jx, Ji, Jp
    """
    n_pf_tau = len(k_pf_tau)
    n_pf_dp = len(k_pf_dp)
    n_qt_m = len(k_qt_m)

    nbus = len(V)
    nbr = len(Ys)

    row_block2 = np.concatenate((pq, i_vf_beq, i_vt_m))
    row_block3 = np.concatenate((k_qf_m, k_zero_beq))

    col_block3 = np.concatenate((k_zero_beq, k_vf_beq))
    n_col_block3 = len(col_block3)

    col_block4 = np.concatenate((k_qf_m, k_qt_m, k_vt_m))
    n_col_block4 = len(col_block4)

    col_block5 = np.concatenate((k_pf_tau, k_pf_dp))
    n_col_block5 = len(col_block5)

    # generate lookup for the row slicing (these follow the structure of the residuals vector)
    row_block1_lookup = make_lookup(nbus, pvpq)  # in: bus index, out: index in pvpq
    row_block2_lookup = make_lookup(nbus, row_block2)  # in: bus index, out: index in row_block2
    row_block3_lookup = make_lookup(nbr, row_block3)  # in: branch index, out: index in row_block3
    row_block4_lookup = make_lookup(nbr, k_qt_m)  # in: branch index, out: index in k_qt_m
    row_block5_lookup = make_lookup(nbr, k_pf_tau)  # in: branch index, out: index in k_pf_tau
    row_block6_lookup = make_lookup(nbr, k_pf_dp)  # in: branch index, out: index in k_pf_dp

    n_row_block1 = len(pvpq)
    n_row_block2 = len(row_block2)
    n_row_block3 = len(row_block3)
    n_row_block4 = len(k_qt_m)
    n_row_block5 = len(k_pf_tau)
    n_row_block6 = len(k_pf_dp)

    nnz = 0
    p = 0
    Jp[p] = 0

    # column 1: derivatives w.r.t Va -----------------------------------------------------------------------------------
    for j in pvpq:  # sliced columns

        # J11
        if n_row_block1:
            for k in range(Yp[j], Yp[j + 1]):  # rows of A[:, j]

                # row index translation to the "rows" space
                i = Yi[k]  # bus index (row index in Ybus)
                ii = row_block1_lookup[i]  # jacobian row index

                if pvpq[ii] == i:
                    # entry found
                    Jx[nnz] = dSbus_dVa_x[k].real  # dP/dƟ
                    Ji[nnz] = ii
                    nnz += 1

        # J21
        offset = n_row_block1
        if n_row_block2:
            for k in range(Yp[j], Yp[j + 1]):  # rows of A[:, j]

                # row index translation to the "rows" space
                i = Yi[k]
                ii = row_block2_lookup[i]  # in: bus index, out: index in row_block2

                if row_block2[ii] == i:
                    # entry found
                    Jx[nnz] = dSbus_dVa_x[k].imag  # dQ/dƟ
                    Ji[nnz] = ii + offset
                    nnz += 1

        # J31
        offset += n_row_block2
        if n_row_block3:
            for k in range(dSf_dVa_p[j], dSf_dVa_p[j + 1]):  # rows of A[:, j]

                # row index translation to the "rows" space
                i = dSf_dVa_i[k]
                ii = row_block3_lookup[i]  # in: branch index, out: index in row_block3

                if row_block3[ii] == i:
                    # entry found
                    Jx[nnz] = dSf_dVa_x[k].imag   # dQf/dƟ
                    Ji[nnz] = ii + offset
                    nnz += 1

        # J41
        offset += n_row_block3
        if n_qt_m:
            for k in range(dSt_dVa_p[j], dSt_dVa_p[j + 1]):  # rows of A[:, j]

                # row index translation to the "rows" space
                i = dSt_dVa_i[k]
                ii = row_block4_lookup[i]

                if k_qt_m[ii] == i:
                    # entry found
                    Jx[nnz] = dSt_dVa_x[k].imag   # dQt/dƟ
                    Ji[nnz] = ii + offset
                    nnz += 1

        # J51
        offset += n_row_block4
        if n_pf_tau:
            for k in range(dSf_dVa_p[j], dSf_dVa_p[j + 1]):  # rows of A[:, j]

                # row index translation to the "rows" space
                i = dSf_dVa_i[k]
                ii = row_block5_lookup[i]

                if k_pf_tau[ii] == i:
                    # entry found
                    Jx[nnz] = dSf_dVa_x[k].real  # dPf/dƟ
                    Ji[nnz] = ii + offset
                    nnz += 1

        # J61
        offset += n_row_block5
        if n_pf_dp:
            for k in range(dSf_dVa_p[j], dSf_dVa_p[j + 1]):  # rows of A[:, j]

                # row index translation to the "rows" space
                i = dSf_dVa_i[k]
                ii = row_block6_lookup[i]

                if k_pf_dp[ii] == i:
                    # entry found
                    Jx[nnz] = -dSf_dVa_x[k].real    # dPf/dƟ
                    Ji[nnz] = ii + offset
                    nnz += 1

        # finalize column
        p += 1
        Jp[p] = nnz

    # column 2: derivatives w.r.t Vm -----------------------------------------------------------------------------------
    for j in pq:  # sliced columns

        # J12
        if n_row_block1:
            for k in range(Yp[j], Yp[j + 1]):  # rows of A[:, j]

                # row index translation to the "rows" space
                i = Yi[k]
                ii = row_block1_lookup[i]

                if pvpq[ii] == i:
                    # entry found
                    Jx[nnz] = dSbus_dVm_x[k].real  # dP/dVm
                    Ji[nnz] = ii
                    nnz += 1

        # J22
        offset = n_row_block1
        if n_row_block2:
            for k in range(Yp[j], Yp[j + 1]):  # rows of A[:, j]

                # row index translation to the "rows" space
                i = Yi[k]
                ii = row_block2_lookup[i]

                if row_block2[ii] == i:
                    # entry found
                    Jx[nnz] = dSbus_dVm_x[k].imag  # dQ/dVm
                    Ji[nnz] = ii + offset
                    nnz += 1

        # J32
        offset += n_row_block2
        if n_row_block3:
            for k in range(dSf_dVm_p[j], dSf_dVm_p[j + 1]):  # rows of A[:, j]

                # row index translation to the "rows" space
                i = dSf_dVm_i[k]
                ii = row_block3_lookup[i]

                if row_block3[ii] == i:
                    # entry found
                    Jx[nnz] = dSf_dVm_x[k].imag  # dQf/dVm
                    Ji[nnz] = ii + offset
                    nnz += 1

        # J42
        offset += n_row_block3
        if n_qt_m:
            for k in range(dSt_dVm_p[j], dSt_dVm_p[j + 1]):  # rows of A[:, j]

                # row index translation to the "rows" space
                i = dSt_dVm_i[k]
                ii = row_block4_lookup[i]

                if k_qt_m[ii] == i:
                    # entry found
                    Jx[nnz] = dSt_dVm_x[k].imag  # dQt/dVm
                    Ji[nnz] = ii + offset
                    nnz += 1

        # J52
        offset += n_row_block4
        if n_pf_tau:
            for k in range(dSf_dVm_p[j], dSf_dVm_p[j + 1]):  # rows of A[:, j]

                # row index translation to the "rows" space
                i = dSf_dVm_i[k]
                ii = row_block5_lookup[i]

                if k_pf_tau[ii] == i:
                    # entry found
                    Jx[nnz] = dSf_dVm_x[k].real  # dPf/dVm
                    Ji[nnz] = ii + offset
                    nnz += 1

        # J62
        offset += n_row_block5
        if n_pf_dp:

            for k in range(dPfdp_dVm_p[j], dPfdp_dVm_p[j + 1]):  # rows of A[:, j]

                # row index translation to the "rows" space
                i = dPfdp_dVm_i[k]
                ii = row_block6_lookup[i]

                if k_pf_dp[ii] == i:
                    # entry found
                    Jx[nnz] = dPfdp_dVm_x[k]  # dPfdp/dVm
                    Ji[nnz] = ii + offset
                    nnz += 1

        # finalize column
        p += 1
        Jp[p] = nnz

    # Column 3: derivatives w.r.t Beq for iBeqz + iBeqv ----------------------------------------------------------------
    if n_col_block3:

        (dSbus_dBeq_data,
         dSbus_dBeq_indices,
         dSbus_dBeq_indptr,
         dSf_dBeqx_data,
         dSf_dBeqx_indices,
         dSf_dBeqx_indptr) = deriv.derivatives_Beq_csc_numba(iBeqx=col_block3, F=F, V=V, ma=tap_modules_m, k2=k2)

        for j in range(n_col_block3):  # sliced columns

            # J13
            if n_row_block1:
                for k in range(dSbus_dBeq_indptr[j], dSbus_dBeq_indptr[j + 1]):  # rows of A[:, j]

                    # row index translation to the "rows" space
                    i = dSbus_dBeq_indices[k]
                    ii = row_block1_lookup[i]

                    if pvpq[ii] == i:
                        # entry found
                        Jx[nnz] = dSbus_dBeq_data[k].real  # dP/dBeq
                        Ji[nnz] = ii
                        nnz += 1

            # J23
            offset = n_row_block1
            if n_row_block2:
                for k in range(dSbus_dBeq_indptr[j], dSbus_dBeq_indptr[j + 1]):  # rows of A[:, j]

                    # row index translation to the "rows" space
                    i = dSbus_dBeq_indices[k]
                    ii = row_block2_lookup[i]

                    if row_block2[ii] == i:
                        # entry found
                        Jx[nnz] = dSbus_dBeq_data[k].imag  # dQ/dBeq
                        Ji[nnz] = ii + offset
                        nnz += 1

            # J33
            offset += n_row_block2
            if n_row_block3:
                for k in range(dSf_dBeqx_indptr[j], dSf_dBeqx_indptr[j + 1]):  # rows of A[:, j]

                    # row index translation to the "rows" space
                    i = dSf_dBeqx_indices[k]
                    ii = row_block3_lookup[i]

                    if row_block3[ii] == i:
                        # entry found
                        Jx[nnz] = dSf_dBeqx_data[k].imag  # dQf/dBeq
                        Ji[nnz] = ii + offset
                        nnz += 1

            # J43
            offset += n_row_block3
            # if n_row_block4:  # --> The Jacobian is always zero :|
            #     for k in range(dSt_dBeqz.indptr[j], dSt_dBeqz.indptr[j + 1]):  # rows of A[:, j]
            #
            #         # row index translation to the "rows" space
            #         i = dSt_dBeqz.indices[k]
            #         ii = iQtma_lookup[i]
            #
            #         if iQtma[ii] == i:
            #             # entry found
            #             Jx[nnz] = dSt_dBeqz.data[k].imag
            #             Ji[nnz] = ii + offset
            #             nnz += 1

            # J53
            offset += n_row_block4
            if n_row_block5:
                for k in range(dSf_dBeqx_indptr[j], dSf_dBeqx_indptr[j + 1]):  # rows of A[:, j]

                    # row index translation to the "rows" space
                    i = dSf_dBeqx_indices[k]
                    ii = row_block5_lookup[i]

                    if k_pf_tau[ii] == i:
                        # entry found
                        Jx[nnz] = dSf_dBeqx_data[k].real  # dPf/dBeq
                        Ji[nnz] = ii + offset
                        nnz += 1

            # J63
            offset += n_row_block5
            if n_row_block6:
                for k in range(dSf_dBeqx_indptr[j], dSf_dBeqx_indptr[j + 1]):  # rows of A[:, j]

                    # row index translation to the "rows" space
                    i = dSf_dBeqx_indices[k]
                    ii = row_block6_lookup[i]

                    if k_pf_dp[ii] == i:
                        # entry found
                        Jx[nnz] = -dSf_dBeqx_data[k].real  # dPf/dBeq
                        Ji[nnz] = ii + offset
                        nnz += 1

            # finalize column
            p += 1
            Jp[p] = nnz

    # Column 4: derivative w.r.t "m" for iQfma + iQfma + iVtma ---------------------------------------------------------
    if n_col_block4:

        (dSbus_dm_data,
         dSbus_dm_indices,
         dSbus_dm_indptr,
         dSf_dm_data,
         dSf_dm_indices,
         dSf_dm_indptr,
         dSt_dm_data,
         dSt_dm_indices,
         dSt_dm_indptr) = deriv.derivatives_ma_csc_numba(iXxma=col_block4, F=F, T=T, Ys=Ys, k2=k2,
                                                         tap=tap_complex, ma=tap_modules_m, Bc=Bc, 
                                                         Beq=b_eq, V=V)

        for j in range(n_col_block4):  # sliced columns

            # J14
            if n_row_block1:
                for k in range(dSbus_dm_indptr[j], dSbus_dm_indptr[j + 1]):  # rows of A[:, j]

                    # row index translation to the "rows" space
                    i = dSbus_dm_indices[k]
                    ii = row_block1_lookup[i]

                    if pvpq[ii] == i:
                        # entry found
                        Jx[nnz] = dSbus_dm_data[k].real  # dP/dm
                        Ji[nnz] = ii
                        nnz += 1

            # J24
            offset = n_row_block1
            if n_row_block2:
                for k in range(dSbus_dm_indptr[j], dSbus_dm_indptr[j + 1]):  # rows of A[:, j]

                    # row index translation to the "rows" space
                    i = dSbus_dm_indices[k]
                    ii = row_block2_lookup[i]

                    if row_block2[ii] == i:
                        # entry found
                        Jx[nnz] = dSbus_dm_data[k].imag  # dQ/dm
                        Ji[nnz] = ii + offset
                        nnz += 1

            # J34
            offset += n_row_block2
            if n_row_block3:
                for k in range(dSf_dm_indptr[j], dSf_dm_indptr[j + 1]):  # rows of A[:, j]

                    # row index translation to the "rows" space
                    i = dSf_dm_indices[k]
                    ii = row_block3_lookup[i]

                    if row_block3[ii] == i:
                        # entry found
                        Jx[nnz] = dSf_dm_data[k].imag  # dQf/dm
                        Ji[nnz] = ii + offset
                        nnz += 1

            # J44
            offset += n_row_block3
            if n_row_block4:
                for k in range(dSt_dm_indptr[j], dSt_dm_indptr[j + 1]):  # rows of A[:, j]

                    # row index translation to the "rows" space
                    i = dSt_dm_indices[k]
                    ii = row_block4_lookup[i]

                    if k_qt_m[ii] == i:
                        # entry found
                        Jx[nnz] = dSt_dm_data[k].imag  # dQt/dm
                        Ji[nnz] = ii + offset
                        nnz += 1

            # J54
            offset += n_row_block4
            if n_row_block5:
                for k in range(dSf_dm_indptr[j], dSf_dm_indptr[j + 1]):  # rows of A[:, j]

                    # row index translation to the "rows" space
                    i = dSf_dm_indices[k]
                    ii = row_block5_lookup[i]

                    if k_pf_tau[ii] == i:
                        # entry found
                        Jx[nnz] = dSf_dm_data[k].real  # dPf/dm
                        Ji[nnz] = ii + offset
                        nnz += 1

            # J64
            offset += n_row_block5
            if n_row_block6:
                for k in range(dSf_dm_indptr[j], dSf_dm_indptr[j + 1]):  # rows of A[:, j]

                    # row index translation to the "rows" space
                    i = dSf_dm_indices[k]
                    ii = row_block6_lookup[i]

                    if k_pf_dp[ii] == i:
                        # entry found
                        Jx[nnz] = -dSf_dm_data[k].real  # dPf/dm
                        Ji[nnz] = ii + offset
                        nnz += 1

            # finalize column
            p += 1
            Jp[p] = nnz

    # Column 5: derivatives w.r.t theta sh for iPfsh + droop -----------------------------------------------------------
    if n_col_block5:

        (dSbus_dtau_data,
         dSbus_dtau_indices,
         dSbus_dtau_indptr,
         dSf_dtau_data,
         dSf_dtau_indices,
         dSf_dtau_indptr,
         dSt_dtau_data,
         dSt_dtau_indices,
         dSt_dtau_indptr) = deriv.derivatives_tau_csc_numba(iPxsh=col_block5,
                                                            F=F, T=T, Ys=Ys,
                                                            k2=k2, tap=tap_complex, V=V)

        for j in range(n_col_block5):  # sliced columns

            # J15
            if n_row_block1:
                for k in range(dSbus_dtau_indptr[j], dSbus_dtau_indptr[j + 1]):  # rows of A[:, j]

                    # row index translation to the "rows" space
                    i = dSbus_dtau_indices[k]
                    ii = row_block1_lookup[i]

                    if pvpq[ii] == i:
                        # entry found
                        Jx[nnz] = dSbus_dtau_data[k].real  # dP/dtau
                        Ji[nnz] = ii
                        nnz += 1

            # J25
            offset = n_row_block1
            if n_row_block2:
                for k in range(dSbus_dtau_indptr[j], dSbus_dtau_indptr[j + 1]):  # rows of A[:, j]

                    # row index translation to the "rows" space
                    i = dSbus_dtau_indices[k]
                    ii = row_block2_lookup[i]

                    if row_block2[ii] == i:
                        # entry found
                        Jx[nnz] = dSbus_dtau_data[k].imag  # dQ/dtau
                        Ji[nnz] = ii + offset
                        nnz += 1


            # J35
            offset += n_row_block2
            if n_row_block3:
                for k in range(dSf_dtau_indptr[j], dSf_dtau_indptr[j + 1]):  # rows of A[:, j]

                    # row index translation to the "rows" space
                    i = dSf_dtau_indices[k]
                    ii = row_block3_lookup[i]

                    if row_block3[ii] == i:
                        # entry found
                        Jx[nnz] = dSf_dtau_data[k].imag  # dQf/dtau
                        Ji[nnz] = ii + offset
                        nnz += 1

            # J45
            offset += n_row_block3
            if n_row_block4:
                for k in range(dSt_dtau_indptr[j], dSt_dtau_indptr[j + 1]):  # rows of A[:, j]

                    # row index translation to the "rows" space
                    i = dSt_dtau_indices[k]
                    ii = row_block4_lookup[i]

                    if k_qt_m[ii] == i:
                        # entry found
                        Jx[nnz] = dSt_dtau_data[k].imag  # dQt/dtau
                        Ji[nnz] = ii + offset
                        nnz += 1

            # J55
            offset += n_row_block4
            if n_row_block5:
                for k in range(dSf_dtau_indptr[j], dSf_dtau_indptr[j + 1]):  # rows of A[:, j]

                    # row index translation to the "rows" space
                    i = dSf_dtau_indices[k]
                    ii = row_block5_lookup[i]

                    if k_pf_tau[ii] == i:
                        # entry found
                        Jx[nnz] = dSf_dtau_data[k].real  # dPf/dtau
                        Ji[nnz] = ii + offset
                        nnz += 1

            # J65
            offset += n_row_block6
            if n_row_block6:
                for k in range(dSf_dtau_indptr[j], dSf_dtau_indptr[j + 1]):  # rows of A[:, j]

                    # row index translation to the "rows" space
                    i = dSf_dtau_indices[k]
                    ii = row_block6_lookup[i]

                    if k_pf_dp[ii] == i:
                        # entry found
                        Jx[nnz] = -dSf_dtau_data[k].real  # - dPf/dtau
                        Ji[nnz] = ii + offset
                        nnz += 1

            # finalize column
            p += 1
            Jp[p] = nnz

    # Finalize ----------------------------------------------------------------------------
    #  finalize the Jacobian Pointer
    Jp[p] = nnz

    return nnz, Jx, Ji, Jp


def fubm_jacobian(nb, nl, k_pf_tau, k_pf_dp, k_qf_m, k_qt_m, k_vt_m, k_zero_beq, k_vf_beq, i_vf_beq, i_vt_m,
                  F, T, Ys, k2, complex_tap, tap_modules, Bc, Beq, Kdp, V, Ybus, Yf, Yt, Cf, Ct, pvpq, pq):
    """
    Compute the FUBM jacobian in a dynamic fashion by only computing the derivatives that are needed
    :param nb: number of buses
    :param nl: Number of lines
    :param k_pf_tau: indices of the Pf controlled with the shunt susceptance Branches
    :param k_pf_dp: indices of the Pf-droop controlled Branches
    :param k_qf_m: indices of the Qf controlled with ma Branches
    :param k_qt_m: Indices of the Qt controlled with ma Branches
    :param k_vt_m: Indices of the Vt controlled with ma Branches
    :param k_zero_beq: Indices of the Qf made zero with the equivalent susceptance Branches
    :param k_vf_beq: Indices of the Vf Controlled with the equivalent susceptance Branches
    :param i_vf_beq: Indices of the buses where Vf is controlled with Beq
    :param i_vt_m: Indices of the buses where Vt is controlled with ma
    :param F: Array of "from" bus indices
    :param T: Array of "to" bus indices
    :param Ys: Array of branch series admittances
    :param k2: Array of branch converter k2 parameters
    :param complex_tap: Array of complex tap values {remember tap = ma * exp(1j * theta) }
    :param tap_modules: Array of tap modules
    :param Bc: Array of branch full susceptances
    :param Beq: Array of branch equivalent (variable) susceptances
    :param Kdp: Array of branch converter droop constants
    :param V: Array of complex bus voltages
    :param Ybus: Admittance matrix
    :param Yf: Admittances matrix of the Branches with the "from" buses
    :param Yt: Admittances matrix of the Branches with the "to" buses
    :param Cf: Connectivity matrix of the Branches with the "from" buses
    :param Ct: Connectivity matrix of the Branches with the "to" buses
    :param pvpq: Array of pv and then pq bus indices (not sorted)
    :param pq: Array of PQ bus indices
    :return: FUBM Jacobian matrix
    """
    n_pf_tau = len(k_pf_tau)
    n_pf_dp = len(k_pf_dp)
    n_qf_m = len(k_qf_m)
    n_qt_m = len(k_qt_m)
    n_vt_m = len(k_vt_m)
    n_zero_beq = len(k_zero_beq)
    n_vf_beq = len(k_vf_beq)
    nVfBeqbus = len(i_vf_beq)
    nVtmabus = len(i_vt_m)
    npq = len(pq)
    npvpq = len(pvpq)
    nbus = Ybus.shape[0]
    nbr = Yf.shape[0]

    # i2 = np.r_[pq, i_vf_beq, i_vt_m]
    # i4 = np.r_[k_qf_m, k_zero_beq]
    # ni2 = len(i2)
    # ni4 = len(i4)
    E = V / np.abs(V)

    # compose the derivatives of the power Injections w.r.t Va and Vm
    dSbus_dVm_x, dSbus_dVa_x = deriv.dSbus_dV_numba_sparse_csc(Ybus.data, Ybus.indptr, Ybus.indices, V, E)

    # compose the derivatives of the branch flow w.r.t Va and Vm
    dSf_dVm, dSf_dVa = deriv.dSf_dV_csc(Yf, V, F, T)

    if len(k_qt_m):
        dSt_dVm, dSt_dVa = deriv.dSt_dV_csc(Yt, V, F, T)
    else:
        dSt_dVa = csc_matrix((nl, nb))
        dSt_dVm = csc_matrix((nl, nb))

    if n_pf_dp:
        # compute the droop derivative
        dVmf_dVm = lil_matrix((nl, nb))
        dVmf_dVm[k_pf_dp, :] = Cf[k_pf_dp, :]
        dPfdp_dVm = -dSf_dVm.real + diags(Kdp) * dVmf_dVm
    else:
        dPfdp_dVm = csc_matrix((n_pf_dp, nb))

    n_cols = npvpq + npq + n_zero_beq + n_vf_beq + n_qf_m + n_qt_m + n_vt_m + n_pf_tau + n_pf_dp
    n_rows = n_cols

    nnz_estimate = Ybus.nnz * 8
    Jx = np.empty(nnz_estimate, dtype=np.float64)  # data
    Ji = np.empty(nnz_estimate, dtype=np.int32)  # indices
    Jp = np.empty(n_cols + 1, dtype=np.int32)  # pointers

    # fill the jacobian data with numba
    nnz, Jx, Ji, Jp = fill_acdc_jacobian_data(Jx=Jx, Ji=Ji, Jp=Jp,
                                              Yp=Ybus.indptr, Yi=Ybus.indices, Ys=Ys,
                                              dSbus_dVa_x=dSbus_dVa_x, dSbus_dVm_x=dSbus_dVm_x,
                                              dSf_dVa_x=dSf_dVa.data, dSf_dVa_i=dSf_dVa.indices, dSf_dVa_p=dSf_dVa.indptr,
                                              dSf_dVm_x=dSf_dVm.data, dSf_dVm_i=dSf_dVm.indices, dSf_dVm_p=dSf_dVm.indptr,
                                              dSt_dVa_x=dSt_dVa.data, dSt_dVa_i=dSt_dVa.indices, dSt_dVa_p=dSt_dVa.indptr,
                                              dSt_dVm_x=dSt_dVm.data, dSt_dVm_i=dSt_dVm.indices, dSt_dVm_p=dSt_dVm.indptr,
                                              dPfdp_dVm_x=dPfdp_dVm.data, dPfdp_dVm_i=dPfdp_dVm.indices, dPfdp_dVm_p=dPfdp_dVm.indptr,
                                              pvpq=pvpq,
                                              pq=pq,
                                              k_pf_tau=k_pf_tau,
                                              k_qt_m=k_qt_m,
                                              k_qf_m=k_qf_m,
                                              k_vt_m=k_vt_m,
                                              k_pf_dp=k_pf_dp,
                                              k_zero_beq=k_zero_beq,
                                              k_vf_beq=k_vf_beq,
                                              i_vf_beq=i_vf_beq,
                                              i_vt_m=i_vt_m,
                                              F=F, T=T, V=V,
                                              tap_modules_m=tap_modules, tap_complex=complex_tap,
                                              k2=k2, Bc=Bc, b_eq=Beq)

    Jx = np.resize(Jx, nnz)
    Ji = np.resize(Ji, nnz)

    J = csc_matrix((Jx, Ji, Jp), shape=(n_rows, n_cols))

    return J


