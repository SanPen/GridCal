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
from cmath import rect
import GridCalEngine.Simulations.Derivatives.csc_derivatives as deriv
from GridCalEngine.basic_structures import Vec, IntVec, CxVec
from GridCalEngine.Utils.Sparse.csc2 import CSC, CxCSC, make_lookup, sp_slice, csc_stack_2d_ff, sp_slice_rows


# @nb.njit()
# def rect(mod, ang):
#
#     return nb.complex128(mod * np.sin(ang), mod * np.cos(ang))


class AcDcSolSlicer:
    """
    AcDcSolSlicer
    """

    def __init__(self, block1, block2, k_zero_beq, k_vf_beq, k_qf_m, k_qt_m, k_vt_m, k_pf_tau, k_pf_dp):
        """
        Declare the slicing limits in the same order as the Jacobian rows
        :param block1: no-slack (pv + pq + pqv + p)
        :param block2: pq + p
        :param k_zero_beq: 
        :param k_vf_beq: 
        :param k_qf_m: 
        :param k_qt_m: 
        :param k_vt_m: 
        :param k_pf_tau: 
        :param k_pf_dp: 
        """

        self.va_idx = block1
        self.vm_idx = block2
        self.beq_idx = np.r_[k_zero_beq, k_vf_beq]
        self.m_idx = np.r_[k_qf_m, k_qt_m, k_vt_m]
        self.tau_idx = np.r_[k_pf_tau, k_pf_dp]

        n_col_block1 = len(block1)
        n_col_block2 = len(block2)
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
def fill_acdc_jacobian_data(Y_indptr: IntVec, Y_indices: IntVec, Yx: CxVec,
                            Yf_indptr: IntVec, Yf_indices: IntVec, Yfx: CxVec,
                            Yt_indptr: IntVec, Yt_indices: IntVec, Ytx: CxVec,
                            yff: CxVec, yft: CxVec, ytf: CxVec, ytt: CxVec,
                            Yseries_br: CxVec,
                            idx_dtheta: IntVec,
                            idx_dvm: IntVec,
                            idx_dm: IntVec,
                            idx_dtau: IntVec,
                            idx_dbeq: IntVec,
                            idx_dP: IntVec,
                            idx_dQ: IntVec,
                            idx_dQf: IntVec,
                            idx_dQt: IntVec,
                            idx_dPf: IntVec,
                            idx_dPdp: IntVec,
                            F: IntVec,
                            T: IntVec,
                            V: CxVec,
                            Vm: Vec,
                            Va: Vec,
                            tap_modules_m: Vec,
                            tap_complex: CxVec,
                            k2: Vec,
                            Bc: Vec,
                            b_eq: Vec,
                            Kdp: Vec) -> CSC:
    """
    Compute the ACDC jacobian using Numba
    :param Y_indptr: Ybus CSC pointer array
    :param Y_indices: Ybus CSC row indices array
    :param Yx:
    :param Yf_indptr:
    :param Yf_indices:
    :param Yfx:
    :param Yt_indptr:
    :param Yt_indices:
    :param Ytx:
    :param Yseries_br: Branches' series admittance array
    :param idx_dtheta:
    :param idx_dvm:
    :param idx_dm:
    :param idx_dtau:
    :param idx_dbeq:
    :param idx_dP:
    :param idx_dQ:
    :param idx_dQf:
    :param idx_dQt:
    :param idx_dPf:
    :param idx_dPdp:
    :param F: Array of "from" bus indices
    :param T: Array of "to" bus indices
    :param V: Array of complex bus voltages
    :param Vm:
    :param Va:
    :param tap_modules_m: Array of tap modules
    :param tap_complex: Array of complex tap values {remember tap = ma * exp(1j * theta) }
    :param k2: Array of branch converter k2 parameters
    :param Bc: Array of branch full susceptances
    :param b_eq: Array of branch equivalent (variable) susceptances
    :param Kdp:
    :return: Jacobian matrix
    """

    n_idx_dtheta = len(idx_dtheta)  # notice that idx_dtheta is the same as idx_dP
    n_idx_dvm = len(idx_dvm)
    n_idx_dm = len(idx_dm)
    n_idx_dtau = len(idx_dtau)
    n_idx_dbeq = len(idx_dbeq)

    n_idx_dP = len(idx_dP)
    n_idx_dQ = len(idx_dQ)
    n_idx_dQf = len(idx_dQf)
    n_idx_dQt = len(idx_dQt)
    n_idx_dPf = len(idx_dPf)
    n_idx_dPdp = len(idx_dPdp)

    n_cols = n_idx_dtheta + n_idx_dvm + n_idx_dm + n_idx_dtau + n_idx_dbeq
    n_rows = n_idx_dP + n_idx_dQ + n_idx_dQf + n_idx_dQt + n_idx_dPf + n_idx_dPdp
    assert n_cols == n_rows

    nbus = len(V)
    nbr = len(Yseries_br)

    # compose the derivatives of the power Injections w.r.t Va and Vm
    dSbus_dVm_x, dSbus_dVa_x = deriv.dSbus_dV_numba_sparse_csc(Yx, Y_indptr, Y_indices, V, np.abs(V))

    # declare the Jacobian matrix
    nnz_estimate = len(Yx) * 8
    J = CSC(n_rows, n_cols, nnz_estimate, False)

    # generate lookup for the row slicing (these follow the structure of the residuals vector)
    lookup_idx_dP = make_lookup(nbus, idx_dP)
    lookup_idx_dQ = make_lookup(nbus, idx_dQ)
    lookup_idx_dQf = make_lookup(nbr, idx_dQf)
    lookup_idx_dQt = make_lookup(nbr, idx_dQt)
    lookup_idx_dPf = make_lookup(nbr, idx_dPf)
    lookup_idx_dPdp = make_lookup(nbr, idx_dPdp)

    nnz = 0
    p = 0
    J.indptr[p] = 0

    # column 1: derivatives w.r.t Va -----------------------------------------------------------------------------------
    for j in idx_dtheta:  # sliced columns

        # J11: dP/dθ
        if n_idx_dP:
            for pos in range(Y_indptr[j], Y_indptr[j + 1]):  # rows of A[:, j]

                # row index translation to the "rows" space
                i = Y_indices[pos]  # bus index (row index in Ybus)
                ii = lookup_idx_dP[i]  # jacobian row index

                if idx_dP[ii] == i:
                    # entry found
                    J.data[nnz] = dSbus_dVa_x[pos].real  # dP/dƟ
                    J.indices[nnz] = ii
                    nnz += 1

        # J21: dQ/dθ
        offset = n_idx_dP
        if n_idx_dQ:
            for pos in range(Y_indptr[j], Y_indptr[j + 1]):  # rows of A[:, j]

                # row index translation to the "rows" space
                i = Y_indices[pos]
                ii = lookup_idx_dQ[i]  # in: bus index, out: index in row_block2

                if idx_dQ[ii] == i:
                    # entry found
                    J.data[nnz] = dSbus_dVa_x[pos].imag  # dQ/dƟ
                    J.indices[nnz] = ii + offset
                    nnz += 1

        # J31: dQf/dθ
        offset += n_idx_dQ
        if n_idx_dQf:
            for pos in range(Yf_indptr[j], Yf_indptr[j + 1]):

                k = Yf_indices[pos]
                f = F[k]
                t = T[k]

                if f == j or f == t:

                    val = 1j * Vm[f] * Vm[t] * rect(1.0, Va[f] - Va[t]) * np.conj(yft[k])  # dSf/dθf

                    if f == j:
                        J.data[nnz] = val.imag
                    elif t == j:
                        J.data[nnz] = -val.imag

                    J.indices[nnz] = lookup_idx_dQf[k] + offset
                    nnz += 1

        # J41: dQt/dθ
        offset += n_idx_dQf
        if n_idx_dQt:

            for pos in range(Yt_indptr[j], Yt_indptr[j + 1]):  # rows of A[:, j]

                k = Yt_indices[pos]
                f = F[k]
                t = T[k]

                if f == j or f == t:

                    val = 1j * Vm[f] * Vm[t] * rect(1.0, Va[f] - Va[t]) * np.conj(ytf[k])  # dSf/dθf

                    if f == j:
                        J.data[nnz] = -val.imag
                    elif t == j:
                        J.data[nnz] = val.imag

                    J.indices[nnz] = lookup_idx_dQt[k] + offset
                    nnz += 1

        # J51: dPf/dθ
        offset += n_idx_dQt
        if n_idx_dPf:
            for pos in range(Yf_indptr[j], Yf_indptr[j + 1]):  # rows of A[:, j]

                k = Yf_indices[pos]
                f = F[k]
                t = T[k]

                if f == j or f == t:

                    val = 1j * Vm[f] * Vm[t] * rect(1.0, Va[f] - Va[t]) * np.conj(yft[k])  # dSf/dθf

                    if f == j:
                        J.data[nnz] = val.real
                    elif t == j:
                        J.data[nnz] = -val.real

                    J.indices[nnz] = lookup_idx_dPf[k] + offset
                    nnz += 1

        # J61: -dPf/dƟ
        offset += n_idx_dPf
        if n_idx_dPdp:
            for pos in range(Yf_indptr[j], Yf_indptr[j + 1]):  # rows of A[:, j]

                k = Yf_indices[pos]
                f = F[k]
                t = T[k]

                if f == j or f == t:

                    val = 1j * Vm[f] * Vm[t] * rect(1.0, Va[f] - Va[t]) * np.conj(yft[k])  # dSf/dθf

                    if f == j:
                        J.data[nnz] = -val.real
                    elif t == j:
                        J.data[nnz] = val.real

                    J.indices[nnz] = lookup_idx_dPdp[k] + offset
                    nnz += 1

        # finalize column
        p += 1
        J.indptr[p] = nnz

    # column 2: derivatives w.r.t Vm -----------------------------------------------------------------------------------
    for j in idx_dvm:  # sliced columns

        # J12: dP/dVm
        if n_idx_dP:
            for pos in range(Y_indptr[j], Y_indptr[j + 1]):  # rows of A[:, j]

                # row index translation to the "rows" space
                i = Y_indices[pos]
                ii = lookup_idx_dP[i]

                if idx_dP[ii] == i:
                    # entry found
                    J.data[nnz] = dSbus_dVm_x[pos].real  # dP/dVm
                    J.indices[nnz] = ii
                    nnz += 1

        # J22: dQ/dVm
        offset = n_idx_dP
        if n_idx_dQ:
            for pos in range(Y_indptr[j], Y_indptr[j + 1]):  # rows of A[:, j]

                # row index translation to the "rows" space
                i = Y_indices[pos]
                ii = lookup_idx_dQ[i]

                if idx_dQ[ii] == i:
                    # entry found
                    J.data[nnz] = dSbus_dVm_x[pos].imag  # dQ/dVm
                    J.indices[nnz] = ii + offset
                    nnz += 1

        # J32: dQf/dVm
        offset += n_idx_dQ
        if n_idx_dQf:
            for pos in range(Yf_indptr[j], Yf_indptr[j + 1]):  # rows of A[:, j]

                k = Yf_indices[pos]
                f = F[k]
                t = T[k]

                if f == j or f == t:

                    if f == j:
                        # dSf/dvf
                        val = 2.0 * Vm[f] * np.conj(yff[k]) + rect(Vm[t], Va[f] - Va[t]) * np.conj(yft[k])
                        J.data[nnz] = val.imag
                    elif t == j:
                        val = rect(Vm[f], Va[f] - Va[t]) * np.conj(yft[k])  # dSf/dvt
                        J.data[nnz] = -val.imag

                    J.indices[nnz] = lookup_idx_dQf[k] + offset
                    nnz += 1

        # J42: dQt/dVm
        offset += n_idx_dQf
        if n_idx_dQt:
            for pos in range(Yt_indptr[j], Yt_indptr[j + 1]):  # rows of A[:, j]

                k = Yf_indices[pos]
                f = F[k]
                t = T[k]

                if f == j or f == t:

                    if f == j:
                        val = rect(Vm[t], Va[t] - Va[f]) * np.conj(ytf[k])  # dSf/dvt
                        J.data[nnz] = val.imag
                    elif t == j:
                        # dSf/dvf
                        val = 2.0 * Vm[t] * np.conj(ytt[k]) + rect(Vm[f], Va[t] - Va[f]) * np.conj(ytf[k])
                        J.data[nnz] = -val.imag

                    J.indices[nnz] = lookup_idx_dQt[k] + offset
                    nnz += 1

        # J52: dPf/dVm
        offset += n_idx_dQt
        if n_idx_dPf:
            for pos in range(Yf_indptr[j], Yf_indptr[j + 1]):

                k = Yf_indices[pos]
                f = F[k]
                t = T[k]

                if f == j or f == t:

                    if f == j:
                        val = 2.0 * Vm[f] * np.conj(yff[k]) + rect(Vm[t], Va[f] - Va[t]) * np.conj(yft[k])  # dPf/dVmf
                        J.data[nnz] = val.real
                    elif t == j:
                        val = rect(Vm[f], Va[f] - Va[t]) * np.conj(yft[k])  # dPf/dVmt
                        J.data[nnz] = val.real

                    J.indices[nnz] = lookup_idx_dPf[k] + offset
                    nnz += 1

        # J62: dPfdp/dVm
        offset += n_idx_dPf
        if n_idx_dPdp:

            # # compute the droop derivative
            # dVmf_dVm = lil_matrix((nl, nb))
            # dVmf_dVm[k_pf_dp, :] = Cf[k_pf_dp, :]
            # dPfdp_dVm = -dSf_dVm.real + diags(Kdp) * dVmf_dVm
            #
            for pos in range(Yf_indptr[j], Yf_indptr[j + 1]):

                k = Yf_indices[pos]
                f = F[k]
                t = T[k]

                if f == j or f == t:

                    if f == j:
                        val = 2.0 * Vm[f] * np.conj(yff[k]) + rect(Vm[t], Va[f] - Va[t]) * np.conj(yft[k])  # dPf/dVmf
                        J.data[nnz] = val.real - Kdp[k]
                    elif t == j:
                        val = rect(Vm[f], Va[f] - Va[t]) * np.conj(yft[k])  # dPf/dVmt
                        J.data[nnz] = val.real

                    J.indices[nnz] = lookup_idx_dPdp[k] + offset
                    nnz += 1
            pass

        # finalize column
        p += 1
        J.indptr[p] = nnz

    # Column 3: derivatives w.r.t Beq ----------------------------------------------------------------

    for k in idx_dbeq:  # sliced columns

        # J13: dP/dBeq
        if n_idx_dP:
            for pos in range(Y_indptr[k], Y_indptr[k + 1]):  # rows of A[:, j]

                # row index translation to the "rows" space
                i = Y_indices[pos]  # bus index (row index in Ybus)
                f = F[k]
                t = T[k]
                if f == i:
                    # entry found
                    val = Vm[f] * np.conj((Vm[t]) / (k2[k] * k2[k] * tap_modules_m[k]))
                    J.data[nnz] = val.real
                    J.indices[nnz] = lookup_idx_dP[i]  # jacobian row index
                    nnz += 1
                elif t == i:
                    pass  # the derivative is 0

        # J23: dQ/dBeq
        offset = n_idx_dP
        if n_idx_dQ:
            for pos in range(Y_indptr[k], Y_indptr[k + 1]):  # rows of A[:, j]

                # row index translation to the "rows" space
                i = Y_indices[pos]  # bus index (row index in Ybus)
                f = F[k]
                t = T[k]
                if f == i:
                    # entry found
                    val = Vm[f] * np.conj((Vm[t]) / (k2[k] * k2[k] * tap_modules_m[k]))
                    J.data[nnz] = val.imag
                    J.indices[nnz] = lookup_idx_dQ[i]  # jacobian row index
                    nnz += 1
                elif t == i:
                    pass  # the derivative is 0

        # J33: dQf/dBeq
        offset += n_idx_dQ
        if n_idx_dQf:
            for pos in range(Yf_indptr[k], Yf_indptr[k + 1]):

                k_row = Yf_indices[pos]
                f_col = F[k]
                t_col = T[k]
                f_row = F[k_row]
                t_row = T[k_row]

                if f_col == f_row or t_col == t_row:

                    if f_col == f_row:
                        # dSf/dvf
                        val = Vm[f] * np.conj((Vm[t]) / (k2[k] * k2[k] * tap_modules_m[k]))
                        J.data[nnz] = val.imag

                    elif t_col == t_row:
                        val = rect(Vm[f], Va[f] - Va[t]) * np.conj(yft[k])  # dSf/dvt
                        J.data[nnz] = -val.imag

                    J.indices[nnz] = lookup_idx_dQf[k] + offset
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
        #             J.data[nnz] = dSt_dBeqz.data[k].imag
        #             J.indices[nnz] = ii + offset
        #             nnz += 1

        # J53
        offset += n_row_block4
        if n_row_block5:
            for pos in range(dSf_dBeq.indptr[j], dSf_dBeq.indptr[j + 1]):  # rows of A[:, j]

                # row index translation to the "rows" space
                i = dSf_dBeq.indices[pos]
                ii = row_block5_lookup[i]

                if k_pf_tau[ii] == i:
                    # entry found
                    J.data[nnz] = dSf_dBeq.data[pos].real  # dPf/dBeq
                    J.indices[nnz] = ii + offset
                    nnz += 1

        # J63
        offset += n_row_block5
        if n_row_block6:
            for pos in range(dSf_dBeq.indptr[j], dSf_dBeq.indptr[j + 1]):  # rows of A[:, j]

                # row index translation to the "rows" space
                i = dSf_dBeq.indices[pos]
                ii = row_block6_lookup[i]

                if k_pf_dp[ii] == i:
                    # entry found
                    J.data[nnz] = -dSf_dBeq.data[pos].real  # dPf/dBeq
                    J.indices[nnz] = ii + offset
                    nnz += 1

        # finalize column
        p += 1
        J.indptr[p] = nnz

    # Column 4: derivative w.r.t "m" for iQfma + iQfma + iVtma ---------------------------------------------------------
    # if n_col_block4:
    #
    #     dSbus_dm, dSf_dm, dSt_dm = deriv.derivatives_ma_csc_numba(nb=nbus, nl=nbr, iXxma=col_block4,
    #                                                               F=F, T=T, Ys=Yseries_br, k2=k2,
    #                                                               tap=tap_complex, ma=tap_modules_m,
    #                                                               Bc=Bc, Beq=b_eq, V=V)

    for j in idx_dm:  # sliced columns

        # J14
        if n_row_block1:
            for pos in range(dSbus_dm.indptr[j], dSbus_dm.indptr[j + 1]):  # rows of A[:, j]

                # row index translation to the "rows" space
                i = dSbus_dm.indices[pos]
                ii = lookup_block1[i]

                if i_block1[ii] == i:
                    # entry found
                    J.data[nnz] = dSbus_dm.data[pos].real  # dP/dm
                    J.indices[nnz] = ii
                    nnz += 1

        # J24
        offset = n_row_block1
        if n_row_block2:
            for pos in range(dSbus_dm.indptr[j], dSbus_dm.indptr[j + 1]):  # rows of A[:, j]

                # row index translation to the "rows" space
                i = dSbus_dm.indices[pos]
                ii = row_block2_lookup[i]

                if row_block2[ii] == i:
                    # entry found
                    J.data[nnz] = dSbus_dm.data[pos].imag  # dQ/dm
                    J.indices[nnz] = ii + offset
                    nnz += 1

        # J34
        offset += n_row_block2
        if n_row_block3:
            for pos in range(dSf_dm.indptr[j], dSf_dm.indptr[j + 1]):  # rows of A[:, j]

                # row index translation to the "rows" space
                i = dSf_dm.indices[pos]
                ii = row_block3_lookup[i]

                if row_block3[ii] == i:
                    # entry found
                    J.data[nnz] = dSf_dm.data[pos].imag  # dQf/dm
                    J.indices[nnz] = ii + offset
                    nnz += 1

        # J44
        offset += n_row_block3
        if n_row_block4:
            for pos in range(dSt_dm.indptr[j], dSt_dm.indptr[j + 1]):  # rows of A[:, j]

                # row index translation to the "rows" space
                i = dSt_dm.indices[pos]
                ii = row_block4_lookup[i]

                if k_qt_m[ii] == i:
                    # entry found
                    J.data[nnz] = dSt_dm.data[pos].imag  # dQt/dm
                    J.indices[nnz] = ii + offset
                    nnz += 1

        # J54
        offset += n_row_block4
        if n_row_block5:
            for pos in range(dSf_dm.indptr[j], dSf_dm.indptr[j + 1]):  # rows of A[:, j]

                # row index translation to the "rows" space
                i = dSf_dm.indices[pos]
                ii = row_block5_lookup[i]

                if k_pf_tau[ii] == i:
                    # entry found
                    J.data[nnz] = dSf_dm.data[pos].real  # dPf/dm
                    J.indices[nnz] = ii + offset
                    nnz += 1

        # J64
        offset += n_row_block5
        if n_row_block6:
            for pos in range(dSf_dm.indptr[j], dSf_dm.indptr[j + 1]):  # rows of A[:, j]

                # row index translation to the "rows" space
                i = dSf_dm.indices[pos]
                ii = row_block6_lookup[i]

                if k_pf_dp[ii] == i:
                    # entry found
                    J.data[nnz] = -dSf_dm.data[pos].real  # dPf/dm
                    J.indices[nnz] = ii + offset
                    nnz += 1

        # finalize column
        p += 1
        J.indptr[p] = nnz

    # Column 5: derivatives w.r.t theta sh for iPfsh + droop -----------------------------------------------------------
    # if n_col_block5:
    #
    #     dSbus_dtau, dSf_dtau, dSt_dtau = deriv.derivatives_tau_csc_numba(nb=nbus, nl=nbr,
    #                                                                      iPxsh=col_block5,
    #                                                                      F=F, T=T, Ys=Yseries_br, k2=k2,
    #                                                                      tap=tap_complex, V=V)

    for j in idx_dtau:  # sliced columns

        # J15
        if n_row_block1:
            for pos in range(dSbus_dtau.indptr[j], dSbus_dtau.indptr[j + 1]):  # rows of A[:, j]

                # row index translation to the "rows" space
                i = dSbus_dtau.indices[pos]
                ii = lookup_block1[i]

                if i_block1[ii] == i:
                    # entry found
                    J.data[nnz] = dSbus_dtau.data[pos].real  # dP/dtau
                    J.indices[nnz] = ii
                    nnz += 1

        # J25
        offset = n_row_block1
        if n_row_block2:
            for pos in range(dSbus_dtau.indptr[j], dSbus_dtau.indptr[j + 1]):  # rows of A[:, j]

                # row index translation to the "rows" space
                i = dSbus_dtau.indices[pos]
                ii = row_block2_lookup[i]

                if row_block2[ii] == i:
                    # entry found
                    J.data[nnz] = dSbus_dtau.data[pos].imag  # dQ/dtau
                    J.indices[nnz] = ii + offset
                    nnz += 1

        # J35
        offset += n_row_block2
        if n_row_block3:
            for pos in range(dSf_dtau.indptr[j], dSf_dtau.indptr[j + 1]):  # rows of A[:, j]

                # row index translation to the "rows" space
                i = dSf_dtau.indices[pos]
                ii = row_block3_lookup[i]

                if row_block3[ii] == i:
                    # entry found
                    J.data[nnz] = dSf_dtau.data[pos].imag  # dQf/dtau
                    J.indices[nnz] = ii + offset
                    nnz += 1

        # J45
        offset += n_row_block3
        if n_row_block4:
            for pos in range(dSt_dtau.indptr[j], dSt_dtau.indptr[j + 1]):  # rows of A[:, j]

                # row index translation to the "rows" space
                i = dSt_dtau.indices[pos]
                ii = row_block4_lookup[i]

                if k_qt_m[ii] == i:
                    # entry found
                    J.data[nnz] = dSt_dtau.data[pos].imag  # dQt/dtau
                    J.indices[nnz] = ii + offset
                    nnz += 1

        # J55
        offset += n_row_block4
        if n_row_block5:
            for pos in range(dSf_dtau.indptr[j], dSf_dtau.indptr[j + 1]):  # rows of A[:, j]

                # row index translation to the "rows" space
                i = dSf_dtau.indices[pos]
                ii = row_block5_lookup[i]

                if k_pf_tau[ii] == i:
                    # entry found
                    J.data[nnz] = dSf_dtau.data[pos].real  # dPf/dtau
                    J.indices[nnz] = ii + offset
                    nnz += 1

        # J65
        offset += n_row_block6
        if n_row_block6:
            for pos in range(dSf_dtau.indptr[j], dSf_dtau.indptr[j + 1]):  # rows of A[:, j]

                # row index translation to the "rows" space
                i = dSf_dtau.indices[pos]
                ii = row_block6_lookup[i]

                if k_pf_dp[ii] == i:
                    # entry found
                    J.data[nnz] = -dSf_dtau.data[pos].real  # - dPf/dtau
                    J.indices[nnz] = ii + offset
                    nnz += 1

        # finalize column
        p += 1
        J.indptr[p] = nnz

    # Finalize ----------------------------------------------------------------------------
    #  finalize the Jacobian Pointer
    J.indptr[p] = nnz
    J.resize(nnz)

    return J


def fubm_jacobian_old(nb, nl,
                      idx_dtheta: IntVec,
                      idx_dvm: IntVec,
                      idx_dm: IntVec,
                      idx_dtau: IntVec,
                      idx_dbeq: IntVec,
                      idx_dP: IntVec,
                      idx_dQ: IntVec,
                      idx_dQf: IntVec,
                      idx_dQt: IntVec,
                      idx_dPf: IntVec,
                      idx_dPdp: IntVec,
                      F, T, Ys, k2, complex_tap, tap_modules, Bc, Beq, Kdp, V,
                      Ybus, Yf, Yt, yff, yft, ytf, ytt) -> CSC:
    """
    Compute the FUBM jacobian in a dynamic fashion by only computing the derivatives that are needed
    :param nb: number of buses
    :param nl: Number of lines
    :param k_pf_tau: indices of the Pf controlled with the shunt susceptance Branches
    :param k_pf_dp: indices of the Pf-droop controlled Branches
    :param k_qf_m: indices of the Qf controlled with ma Branches
    :param k_qt_m: Indices of the Qt controlled with ma Branches
    :param k_v_m: Indices of the Vt controlled with ma Branches
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

    # fill the jacobian data with numba
    J = fill_acdc_jacobian_data(Y_indptr=Ybus.indptr, Y_indices=Ybus.indices, Yx=Ybus.data,
                                Yf_indptr=Yf.indptr, Yf_indices=Yf.indices, Yfx=Yf.data,
                                Yt_indptr=Yt.indptr, Yt_indices=Yt.indices, Ytx=Yt.data,
                                yff=yff, yft=yft, ytf=ytf, ytt=ytt,
                                Yseries_br=Ys,
                                idx_dtheta=idx_dtheta,
                                idx_dvm=idx_dvm,
                                idx_dm=idx_dm,
                                idx_dtau=idx_dtau,
                                idx_dbeq=idx_dbeq,
                                idx_dP=idx_dP,
                                idx_dQ=idx_dQ,
                                idx_dQf=idx_dQf,
                                idx_dQt=idx_dQt,
                                idx_dPf=idx_dPf,
                                idx_dPdp=idx_dPdp,
                                F=F,
                                T=T,
                                V=V,
                                tap_modules_m=tap_modules,
                                tap_complex=complex_tap,
                                k2=k2,
                                Bc=Bc,
                                b_eq=Beq,
                                Kdp=Kdp)

    return J


# @nb.njit()
def fubm_jacobian(nbus: int,
                  nbr: int,
                  idx_dtheta: IntVec,
                  idx_dvm: IntVec,
                  idx_dm: IntVec,
                  idx_dtau: IntVec,
                  idx_dbeq: IntVec,
                  idx_dP: IntVec,
                  idx_dQ: IntVec,
                  idx_dQf: IntVec,
                  idx_dPf: IntVec,
                  F: IntVec,
                  T: IntVec,
                  Ys: CxVec,
                  kconv: Vec,
                  complex_tap: CxVec,
                  tap_modules: Vec,
                  Bc: Vec,
                  Beq: Vec,
                  Kdp: Vec,
                  V: CxVec,
                  Vm: Vec,
                  Ybus_x: CxVec,
                  Ybus_p: IntVec,
                  Ybus_i: IntVec,
                  yff: CxVec,
                  yft: CxVec,
                  ytf: CxVec,
                  ytt: CxVec) -> CSC:
    """

    :param nbus:
    :param idx_dtheta:
    :param idx_dvm:
    :param idx_dm:
    :param idx_dtau:
    :param idx_dbeq:
    :param idx_dP:
    :param idx_dQ:
    :param idx_dQf:
    :param idx_dPf:
    :param F:
    :param T:
    :param Ys:
    :param kconv:
    :param complex_tap:
    :param tap_modules:
    :param Bc:
    :param Beq:
    :param Kdp:
    :param V:
    :param Vm:
    :param Ybus_x:
    :param Ybus_p:
    :param Ybus_i:
    :param yff:
    :param yft:
    :param ytf:
    :param ytt:
    :return:
    """
    n_rows = len(idx_dP) + len(idx_dQ) + len(idx_dQf) + len(idx_dPf)
    n_cols = len(idx_dtheta) + len(idx_dvm) + len(idx_dm) + len(idx_dtau) + len(idx_dbeq)

    if not np.all(idx_dtau == idx_dPf):
        raise ValueError("Pf indices must be equal to tau indices!")

    if n_cols != n_rows:
        raise ValueError("Incorrect J indices!")

    # bus-bus derivatives (always needed)
    dS_dVm_x, dS_dVa_x = deriv.dSbus_dV_numba_sparse_csc(Ybus_x, Ybus_p, Ybus_i, V, Vm)

    dS_dVm = CxCSC(nbus, nbus, len(dS_dVm_x), False)
    dS_dVm.set(Ybus_i, Ybus_p, dS_dVm_x)

    dS_dVa = CxCSC(nbus, nbus, len(dS_dVa_x), False)
    dS_dVa.set(Ybus_i, Ybus_p, dS_dVa_x)

    dP_dVa__ = sp_slice(dS_dVa.real, idx_dP, idx_dtheta)
    dQ_dVa__ = sp_slice(dS_dVa.imag, idx_dQ, idx_dtheta)
    dPf_dVa_ = deriv.dSf_dVa_csc(nbus, idx_dPf, idx_dtheta, yff, yft, V, F, T).real
    dQf_dVa_ = deriv.dSf_dVa_csc(nbus, idx_dQf, idx_dtheta, yff, yft, V, F, T).imag
    # dQt_dVa_ = deriv.dSt_dVa_csc(nbus, idx_dQt, idx_dtheta, ytf, V, F, T).imag
    # dPdp_dVa = deriv.dSf_dVa_csc(nbus, idx_dPdp, idx_dtheta, yff, yft, V, F, T).real

    dP_dVm__ = sp_slice(dS_dVm.real, idx_dP, idx_dvm)
    dQ_dVm__ = sp_slice(dS_dVm.imag, idx_dQ, idx_dvm)
    dPf_dVm_ = deriv.dSf_dVm_csc(nbus, idx_dPf, idx_dtheta, yff, yft, V, F, T).real
    dQf_dVm_ = deriv.dSf_dVm_csc(nbus, idx_dQf, idx_dtheta, yff, yft, V, F, T).imag
    # dQt_dVm_ = deriv.dSt_dVm_csc(nbus, idx_dQt, idx_dtheta, ytt, ytf, V, F, T).imag
    # dPdp_dVm = deriv.dPfdp_dVm_csc(nbus, idx_dPdp, idx_dtheta, yff, yft, Kdp, V, F, T)

    dP_dm__ = deriv.dSbus_dm_csc(nbus, idx_dP, idx_dm, F, T, Ys, Bc, Beq, kconv, complex_tap, tap_modules, V).real
    dQ_dm__ = deriv.dSbus_dm_csc(nbus, idx_dQ, idx_dm, F, T, Ys, Bc, Beq, kconv, complex_tap, tap_modules, V).imag
    dPf_dm_ = deriv.dSf_dm_csc(nbr, idx_dPf, idx_dm, F, T, Ys, Bc, Beq, kconv, complex_tap, tap_modules, V).real
    dQf_dm_ = deriv.dSf_dm_csc(nbr, idx_dQf, idx_dm, F, T, Ys, Bc, Beq, kconv, complex_tap, tap_modules, V).imag
    # dQt_dm_ = deriv.dSt_dm_csc(idx_dQt, idx_dm, F, T, Ys, kconv, complex_tap, tap_modules, V).imag
    # dPdp_dm = deriv.dSf_dm_csc(idx_dPdp, idx_dm, F, T, Ys, Bc, Beq, kconv, complex_tap, tap_modules, V).real

    dP_dtau__ = deriv.dSbus_dtau_csc(nbus, idx_dP, idx_dtau, F, T, Ys, kconv, complex_tap, V).real
    dQ_dtau__ = deriv.dSbus_dtau_csc(nbus, idx_dQ, idx_dtau, F, T, Ys, kconv, complex_tap, V).imag
    dPf_dtau_ = deriv.dSf_dtau_csc(nbr, idx_dPf, idx_dtau, F, T, Ys, kconv, complex_tap, V).real
    dQf_dtau_ = deriv.dSf_dtau_csc(nbr, idx_dQf, idx_dtau, F, T, Ys, kconv, complex_tap, V).imag
    # dQt_dtau_ = deriv.dSt_dtau_csc(idx_dQt, idx_dtau, F, T, Ys, kconv, complex_tap, V).imag
    # dPdp_dtau = deriv.dSf_dtau_csc(idx_dPdp, idx_dtau, F, T, Ys, kconv, complex_tap, V).real

    dP_dbeq__ = deriv.dSbus_dbeq_csc(nbus, idx_dP, idx_dbeq, F, kconv, tap_modules, V).real
    dQ_dbeq__ = deriv.dSbus_dbeq_csc(nbus, idx_dQ, idx_dbeq, F, kconv, tap_modules, V).imag
    dPf_dbeq_ = deriv.dSf_dbeq_csc(nbr, idx_dPf, idx_dbeq, F, kconv, tap_modules, V).real
    dQf_dbeq_ = deriv.dSf_dbeq_csc(nbr, idx_dQf, idx_dbeq, F, kconv, tap_modules, V).imag
    # dQt_dbeq_ = CSC(len(idx_dQt), len(idx_dbeq), 0, False)
    # dPdp_dbeq = deriv.dSf_dbeq_csc(idx_dPdp, idx_dbeq, F, kconv, tap_modules, V).real

    # compose the Jacobian
    # J = csc_stack_2d_ff(mats=
    #                     [dP_dVa__, dP_dVm__, dP_dbeq__, dP_dm__, dP_dtau__,
    #                      dQ_dVa__, dQ_dVm__, dQ_dbeq__, dQ_dm__, dQ_dtau__,
    #                      dQf_dVa_, dQf_dVm_, dQf_dbeq_, dQf_dm_, dQf_dtau_,
    #                      dQt_dVa_, dQt_dVm_, dQt_dbeq_, dQt_dm_, dQt_dtau_,
    #                      dPf_dVa_, dPf_dVm_, dPf_dbeq_, dPf_dm_, dPf_dtau_,
    #                      dPdp_dVa, dPdp_dVm, dPdp_dbeq, dPdp_dm, dPdp_dtau],
    #                     n_rows=6, n_cols=5)

    J = csc_stack_2d_ff(mats=
                        [dP_dVa__, dP_dVm__, dP_dm__, dP_dtau__, dP_dbeq__,
                         dQ_dVa__, dQ_dVm__, dQ_dm__, dQ_dtau__, dQ_dbeq__,
                         dPf_dVa_, dPf_dVm_, dPf_dm_, dPf_dtau_, dPf_dbeq_,
                         dQf_dVa_, dQf_dVm_, dQf_dm_, dQf_dtau_, dQf_dbeq_,],
                        n_rows=4, n_cols=5)

    if J.n_cols != J.n_rows:
        raise ValueError("J is not square!")

    return J
