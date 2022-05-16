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

import numpy as np
import numba as nb
import scipy.sparse as sp
from scipy.sparse import lil_matrix, diags


def dSbus_dV(Ybus, V):
    """
    Derivatives of the power injections w.r.t the voltage
    :param Ybus: Admittance matrix
    :param V: complex voltage arrays
    :return: dSbus_dVa, dSbus_dVm
    """
    diagV = diags(V)
    diagE = diags(V / np.abs(V))
    Ibus = Ybus * V
    diagIbus = diags(Ibus)

    dSbus_dVa = 1j * diagV * np.conj(diagIbus - Ybus * diagV)  # dSbus / dVa
    dSbus_dVm = diagV * np.conj(Ybus * diagE) + np.conj(diagIbus) * diagE  # dSbus / dVm

    return dSbus_dVa, dSbus_dVm


@nb.njit(cache=True)
def dSbus_dV_numba_sparse_csc(Yx, Yp, Yi, V, E):
    """
    Compute the power injection derivatives w.r.t the voltage module and angle
    :param Yx: data of Ybus in CSC format
    :param Yp: indptr of Ybus in CSC format
    :param Yi: indices of Ybus in CSC format
    :param V: Voltages vector
    :return: dS_dVm, dS_dVa data ordered in the CSC format to match the indices of Ybus
    """

    """
    The matrix operations that this is performing are:

    diagV = diags(V)
    diagE = diags(V / np.abs(V))
    Ibus = Ybus * V
    diagIbus = diags(Ibus)

    dSbus_dVa = 1j * diagV * np.conj(diagIbus - Ybus * diagV)
    dSbus_dVm = diagV * np.conj(Ybus * diagE) + np.conj(diagIbus) * diagE    
    """

    # init buffer vector
    n = len(Yp) - 1
    Ibus = np.zeros(n, dtype=np.complex128)
    dS_dVm = Yx.copy()
    dS_dVa = Yx.copy()

    # pass 1: perform the matrix-vector products
    for j in range(n):  # for each column ...
        for k in range(Yp[j], Yp[j + 1]):  # for each row ...
            # row index
            i = Yi[k]

            # Ibus = Ybus * V
            Ibus[i] += Yx[k] * V[j]  # Yx[k] -> Y(i,j)

            # Ybus * diagE
            dS_dVm[k] = Yx[k] * E[j]

            # Ybus * diag(V)
            dS_dVa[k] = Yx[k] * V[j]

    # pass 2: finalize the operations
    for j in range(n):  # for each column ...

        # set buffer variable:
        # this operation cannot be done in the pass1
        # because Ibus is not fully formed, but here it is.
        buffer = np.conj(Ibus[j]) * E[j]

        for k in range(Yp[j], Yp[j + 1]):  # for each row ...

            # row index
            i = Yi[k]

            # diag(V) * conj(Ybus * diagE)
            dS_dVm[k] = V[i] * np.conj(dS_dVm[k])

            if j == i:
                # diagonal elements
                dS_dVa[k] -= Ibus[j]
                dS_dVm[k] += buffer

            # 1j * diagV * conj(diagIbus - Ybus * diagV)
            dS_dVa[k] = np.conj(-dS_dVa[k]) * (1j * V[i])

    return dS_dVm, dS_dVa


@nb.jit(nopython=True, cache=True)
def dSbus_dV_numba_sparse_csr(Yx, Yp, Yj, V, E):  # pragma: no cover
    """
    partial derivatives of power injection w.r.t. voltage.
    :param Yx: Ybus data in CSC format
    :param Yp: Ybus indptr in CSC format
    :param Yj: Ybus indices in CSC format
    :param V: Voltage vector
    :param E: Normalized voltage vector
    :return: dS_dVm, dS_dVa data in CSR format, index pointer and indices are the same as the ones from Ybus
    """

    # init buffer vector
    n = len(V)
    buffer = np.zeros(n, dtype=nb.complex128)
    Ibus = np.zeros(n, dtype=nb.complex128)

    # buffer = np.zeros(n, dtype=complex)
    # Ibus = np.zeros(n, dtype=complex)

    dS_dVm = Yx.copy()
    dS_dVa = Yx.copy()

    # iterate through sparse matrix
    for r in range(len(Yp) - 1):
        for k in range(Yp[r], Yp[r + 1]):
            # Ibus = Ybus * V
            buffer[r] += Yx[k] * V[Yj[k]]

            # Ybus * diag(Vnorm)
            dS_dVm[k] *= E[Yj[k]]

            # Ybus * diag(V)
            dS_dVa[k] *= V[Yj[k]]

        Ibus[r] += buffer[r]

        # conj(diagIbus) * diagVnorm
        buffer[r] = np.conj(buffer[r]) * E[r]

    for r in range(len(Yp) - 1):
        for k in range(Yp[r], Yp[r + 1]):
            # diag(V) * conj(Ybus * diagVnorm)
            dS_dVm[k] = np.conj(dS_dVm[k]) * V[r]

            if r == Yj[k]:
                # diagonal elements
                dS_dVa[k] = -Ibus[r] + dS_dVa[k]
                dS_dVm[k] += buffer[r]

            # 1j * diagV * conj(diagIbus - Ybus * diagV)
            dS_dVa[k] = np.conj(-dS_dVa[k]) * (1j * V[r])

    return dS_dVm, dS_dVa


def dSbus_dV_csc(Ybus, V, E):
    """
    Call the numba sparse constructor of the derivatives
    :param Ybus: Ybus in CSC format
    :param V: Voltages vector
    :param E: Voltages unitary vector
    :return: dS_dVm, dS_dVa in CSC format
    """
    # compute the derivatives' data fast
    dS_dVm, dS_dVa = dSbus_dV_numba_sparse_csc(Ybus.data, Ybus.indptr, Ybus.indices, V, E)

    # generate sparse CSC matrices with computed data and return them
    return sp.csc_matrix((dS_dVa, Ybus.indices, Ybus.indptr)), \
           sp.csc_matrix((dS_dVm, Ybus.indices, Ybus.indptr))


def dSbus_dV_csr(Ybus, V):
    """
    Calls functions to calculate dS/dV depending on whether Ybus is sparse or not
    :param Ybus: Ybus in CSC
    :param V: Voltages vector
    :param I: Currents vector
    :return: dS_dVm, dS_dVa in CSR format
    """

    # I is subtracted from Y*V,
    # therefore it must be negative for numba version of dSbus_dV if it is not zeros anyways
    # calculates sparse data
    dS_dVm, dS_dVa = dSbus_dV_numba_sparse_csr(Ybus.data, Ybus.indptr, Ybus.indices, V, V / np.abs(V))

    # generate sparse CSR matrices with computed data and return them
    return sp.csr_matrix((dS_dVm, Ybus.indices, Ybus.indptr)), \
           sp.csr_matrix((dS_dVa, Ybus.indices, Ybus.indptr))


def dSbr_dV(Yf, Yt, V, F, T, Cf, Ct):
    """
    Derivatives of the branch power w.r.t the branch voltage modules and angles
    :param Yf: Admittances matrix of the branches with the "from" buses
    :param Yt: Admittances matrix of the branches with the "to" buses
    :param V: Array of voltages
    :param F: Array of branch "from" bus indices
    :param T: Array of branch "to" bus indices
    :param Cf: Connectivity matrix of the branches with the "from" buses
    :param Ct: Connectivity matrix of the branches with the "to" buses
    :return: dSf_dVa, dSf_dVm, dSt_dVa, dSt_dVm
    """
    Yfc = np.conj(Yf)
    Ytc = np.conj(Yt)
    Vc = np.conj(V)
    Ifc = Yfc * Vc  # conjugate  of "from"  current
    Itc = Ytc * Vc  # conjugate of "to" current

    diagIfc = diags(Ifc)
    diagItc = diags(Itc)
    Vf = V[F]
    Vt = V[T]
    diagVf = diags(Vf)
    diagVt = diags(Vt)
    diagVc = diags(Vc)

    Vnorm = V / np.abs(V)
    diagVnorm = diags(Vnorm)
    diagV = diags(V)

    CVf = Cf * diagV
    CVt = Ct * diagV
    CVnf = Cf * diagVnorm
    CVnt = Ct * diagVnorm

    dSf_dVa = 1j * (diagIfc * CVf - diagVf * Yfc * diagVc)
    dSf_dVm = diagVf * np.conj(Yf * diagVnorm) + diagIfc * CVnf
    dSt_dVa = 1j * (diagItc * CVt - diagVt * Ytc * diagVc)
    dSt_dVm = diagVt * np.conj(Yt * diagVnorm) + diagItc * CVnt

    return dSf_dVa.tocsc(), dSf_dVm.tocsc(), dSt_dVa.tocsc(), dSt_dVm.tocsc()


def dSf_dV(Yf, V, F, Cf, Vc, diagVc, diagE, diagV):
    """
    Derivatives of the branch power "from" w.r.t the branch voltage modules and angles
    :param Yf: Admittances matrix of the branches with the "from" buses
    :param V: Array of voltages
    :param F: Array of branch "from" bus indices
    :param Cf: Connectivity matrix of the branches with the "from" buses
    :param Vc: array of conjugate voltages
    :param diagVc: diagonal matrix of conjugate voltages
    :param diagE: diagonal matrix of normalized voltages
    :param diagV: diagonal matrix of voltages
    :return: dSf_dVa, dSf_dVm
    """

    Yfc = np.conj(Yf)
    Ifc = Yfc * Vc  # conjugate  of "from"  current

    diagIfc = diags(Ifc)
    Vf = V[F]
    diagVf = diags(Vf)

    CVf = Cf * diagV
    CVnf = Cf * diagE

    dSf_dVa = 1j * (diagIfc * CVf - diagVf * Yfc * diagVc)
    dSf_dVm = diagVf * np.conj(Yf * diagE) + diagIfc * CVnf

    return dSf_dVa.tocsc(), dSf_dVm.tocsc()


def dSt_dV(Yt, V, T, Ct, Vc, diagVc, diagE, diagV):
    """
    Derivatives of the branch power "to" w.r.t the branch voltage modules and angles
    :param Yt: Admittances matrix of the branches with the "to" buses
    :param V: Array of voltages
    :param T: Array of branch "to" bus indices
    :param Ct: Connectivity matrix of the branches with the "to" buses
    :param Vc: array of conjugate voltages
    :param diagVc: diagonal matrix of conjugate voltages
    :param diagE: diagonal matrix of normalized voltages
    :param diagV: diagonal matrix of voltages
    :return: dSf_dVa, dSf_dVm, dSt_dVa, dSt_dVm
    """
    Ytc = np.conj(Yt)
    Itc = Ytc * Vc  # conjugate of "to" current

    diagItc = diags(Itc)
    Vt = V[T]
    diagVt = diags(Vt)

    CVt = Ct * diagV
    CVnt = Ct * diagE

    dSt_dVa = 1j * (diagItc * CVt - diagVt * Ytc * diagVc)
    dSt_dVm = diagVt * np.conj(Yt * diagE) + diagItc * CVnt

    return dSt_dVa.tocsc(), dSt_dVm.tocsc()


@nb.njit(cache=True)
def data_1_4(Cf_data, Cf_indptr, Cf_indices, Ifc, V, E, n_cols):
    """
    Performs the operations:
        op1 = [diagIfc * Cf * diagV]
        op4 = [diagIfc * Cf * diagE]
    :param Cf_data:
    :param Cf_indptr:
    :param Cf_indices:
    :param Ifc:
    :param V: Array of voltages
    :param E: Array of voltages unitary vectors
    :param n_cols:
    :return:
    """
    data1 = np.empty(len(Cf_data), dtype=nb.complex128)
    data4 = np.empty(len(Cf_data), dtype=nb.complex128)
    for j in range(n_cols):  # column j ...
        for k in range(Cf_indptr[j], Cf_indptr[j + 1]):  # for each column entry k ...
            i = Cf_indices[k]  # row i
            data1[k] = Cf_data[k] * Ifc[i] * V[j]
            data4[k] = Cf_data[k] * Ifc[i] * E[j]

    return data1, data4


@nb.njit(cache=True)
def data_2_3(Yf_data, Yf_indptr, Yf_indices, V, F, Vc, E, n_cols):
    """
    Performs the operations:
        op2 = [diagVf * Yfc * diagVc]
        op3 = [diagVf * np.conj(Yf * diagE)]
    :param Yf_data:
    :param Yf_indptr:
    :param Yf_indices:
    :param V: Array of voltages
    :param F: Array of branch "from" bus indices
    :param Vc: Array of voltages conjugates
    :param E: Array of voltages unitary vectors
    :param n_cols:
    :return:
    """
    data2 = np.empty(len(Yf_data), dtype=nb.complex128)
    data3 = np.empty(len(Yf_data), dtype=nb.complex128)
    for j in range(n_cols):  # column j ...
        for k in range(Yf_indptr[j], Yf_indptr[j + 1]):  # for each column entry k ...
            i = Yf_indices[k]  # row i
            data2[k] = np.conj(Yf_data[k]) * V[F[i]] * Vc[j]
            data3[k] = V[F[i]] * np.conj(Yf_data[k] * E[j])
    return data2, data3


def dSf_dV_fast(Yf, V, Vc, E, F, Cf):
    """
    Derivatives of the branch power w.r.t the branch voltage modules and angles
    Works for dSf with Yf, F, Cf and for dSt with Yt, T, Ct
    :param Yf: Admittance matrix of the branches with the "from" buses
    :param V: Array of voltages
    :param Vc: Array of voltages conjugates
    :param E: Array of voltages unitary vectors
    :param F: Array of branch "from" bus indices
    :param Cf: Connectivity matrix of the branches with the "from" buses
    :return: dSf_dVa, dSf_dVm
    """

    Ifc = np.conj(Yf) * Vc  # conjugate  of "from"  current

    # Perform the following operations
    # op1 = [diagIfc * Cf * diagV]
    # op4 = [diagIfc * Cf * diagE]
    data1, data4 = data_1_4(Cf.data, Cf.indptr, Cf.indices, Ifc, V, E, Cf.shape[1])
    op1 = sp.csc_matrix((data1, Cf.indices, Cf.indptr), shape=Cf.shape)
    op4 = sp.csc_matrix((data4, Cf.indices, Cf.indptr), shape=Cf.shape)

    # Perform the following operations
    # op2 = [diagVf * Yfc * diagVc]
    # op3 = [diagVf * np.conj(Yf * diagE)]
    data2, data3 = data_2_3(Yf.data, Yf.indptr, Yf.indices, V, F, Vc, E, Yf.shape[1])
    op2 = sp.csc_matrix((data2, Yf.indices, Yf.indptr), shape=Yf.shape)
    op3 = sp.csc_matrix((data3, Yf.indices, Yf.indptr), shape=Yf.shape)

    dSf_dVa = 1j * (op1 - op2)
    dSf_dVm = op3 + op4

    return dSf_dVa, dSf_dVm


def dSt_dV_fast(Yt, V, Vc, E, T, Ct):
    """
    Derivatives of the branch power w.r.t the branch voltage modules and angles
    note: Works for dSf with Yf, F, Cf and for dSt with Yt, T, Ct
          The operations are identical to dSf_dV_fast, only changing Cf by Ct and Yf by Yt
    :param Yt: Admittance matrix of the branches with the "to" buses
    :param V: Array of voltages
    :param Vc: Array of voltages conjugates
    :param E: Array of voltages unitary vectors
    :param T: Array of branch "to" bus indices
    :param Ct: Connectivity matrix of the branches with the "to" buses
    :return: dSf_dVa, dSf_dVm
    """

    Ifc = np.conj(Yt) * Vc  # conjugate  of "from"  current

    # Perform the following operations
    # op1 = [diagIfc * Cf * diagV]
    # op4 = [diagIfc * Cf * diagE]
    data1, data4 = data_1_4(Ct.data, Ct.indptr, Ct.indices, Ifc, V, E, Ct.shape[1])
    op1 = sp.csc_matrix((data1, Ct.indices, Ct.indptr), shape=Ct.shape)
    op4 = sp.csc_matrix((data4, Ct.indices, Ct.indptr), shape=Ct.shape)

    # Perform the following operations
    # op2 = [diagVf * Yfc * diagVc]
    # op3 = [diagVf * np.conj(Yf * diagE)]
    data2, data3 = data_2_3(Yt.data, Yt.indptr, Yt.indices, V, T, Vc, E, Yt.shape[1])
    op2 = sp.csc_matrix((data2, Yt.indices, Yt.indptr), shape=Yt.shape)
    op3 = sp.csc_matrix((data3, Yt.indices, Yt.indptr), shape=Yt.shape)

    dSt_dVa = 1j * (op1 - op2)
    dSt_dVm = op3 + op4

    return dSt_dVa, dSt_dVm


def derivatives_sh(nb, nl, iPxsh, F, T, Ys, k2, tap, V):
    """
    This function computes the derivatives of Sbus, Sf and St w.r.t. Ɵsh
    - dSbus_dPfsh, dSf_dPfsh, dSt_dPfsh -> if iPxsh=iPfsh
    - dSbus_dPfdp, dSf_dPfdp, dSt_dPfdp -> if iPxsh=iPfdp

    :param nb: number of buses
    :param nl: number of branches
    :param iPxsh: array of indices {iPfsh or iPfdp}, this is the indices of the phase shifting branches
    :param F: Array of branch "from" bus indices
    :param T: Array of branch "to" bus indices
    :param Ys: Array of branch series admittances
    :param k2: Array of "k2" parameters
    :param tap: Array of branch complex taps (ma * exp(1j * theta_sh)
    :param V: Array of complex voltages
    :return:
        - dSbus_dPfsh, dSf_dPfsh, dSt_dPfsh -> if iPxsh=iPfsh
        - dSbus_dPfdp, dSf_dPfdp, dSt_dPfdp -> if iPxsh=iPfdp
    """
    dSbus_dPxsh = lil_matrix((nb, len(iPxsh)), dtype=complex)
    dSf_dshx2 = lil_matrix((nl, len(iPxsh)), dtype=complex)
    dSt_dshx2 = lil_matrix((nl, len(iPxsh)), dtype=complex)

    for k, idx in enumerate(iPxsh):
        f = F[idx]
        t = T[idx]

        # Partials of Ytt, Yff, Yft and Ytf w.r.t. Ɵ shift
        ytt_dsh = 0.0
        yff_dsh = 0.0
        yft_dsh = -Ys[idx] / (-1j * k2[idx] * np.conj(tap[idx]))
        ytf_dsh = -Ys[idx] / (1j * k2[idx] * tap[idx])

        # Partials of S w.r.t. Ɵ shift
        val_f = V[f] * np.conj(yft_dsh * V[t])
        val_t = V[t] * np.conj(ytf_dsh * V[f])

        dSbus_dPxsh[f, k] = val_f
        dSbus_dPxsh[t, k] = val_t

        # Partials of Sf w.r.t. Ɵ shift (makes sense that this is ∂Sbus/∂Pxsh assigned to the "from" bus)
        dSf_dshx2[idx, k] = val_f

        # Partials of St w.r.t. Ɵ shift (makes sense that this is ∂Sbus/∂Pxsh assigned to the "to" bus)
        dSt_dshx2[idx, k] = val_t

    return dSbus_dPxsh.tocsc(), dSf_dshx2.tocsc(), dSt_dshx2.tocsc()


@nb.njit(cache=True)
def derivatives_sh_csc_numba(iPxsh, F, T, Ys, k2, tap, V):
    """
    This function computes the derivatives of Sbus, Sf and St w.r.t. Ɵsh
    - dSbus_dPfsh, dSf_dPfsh, dSt_dPfsh -> if iPxsh=iPfsh
    - dSbus_dPfdp, dSf_dPfdp, dSt_dPfdp -> if iPxsh=iPfdp

    :param iPxsh: array of indices {iPfsh or iPfdp}
    :param F: Array of branch "from" bus indices
    :param T: Array of branch "to" bus indices
    :param Ys: Array of branch series admittances
    :param k2: Array of "k2" parameters
    :param tap: Array of branch complex taps (ma * exp(1j * theta_sh)
    :param V: Array of complex voltages
    :return:
        - dSbus_dPfsh, dSf_dPfsh, dSt_dPfsh -> if iPxsh=iPfsh
        - dSbus_dPfdp, dSf_dPfdp, dSt_dPfdp -> if iPxsh=iPfdp
    """
    ndev = len(iPxsh)

    # dSbus_dPxsh = lil_matrix((nb, ndev), dtype=complex)
    dSbus_dsh_data = np.empty(ndev * 2, dtype=np.complex128)
    dSbus_dsh_indices = np.empty(ndev * 2, dtype=np.int32)
    dSbus_dsh_indptr = np.empty(ndev + 1, dtype=np.int32)

    # dSf_dsh = lil_matrix((nl, ndev), dtype=complex)
    dSf_dsh_data = np.empty(ndev, dtype=np.complex128)
    dSf_dsh_indices = np.empty(ndev, dtype=np.int32)
    dSf_dsh_indptr = np.empty(ndev + 1, dtype=np.int32)

    # dSt_dsh = lil_matrix((nl, ndev), dtype=complex)
    dSt_dsh_data = np.empty(ndev, dtype=np.complex128)
    dSt_dsh_indices = np.empty(ndev, dtype=np.int32)
    dSt_dsh_indptr = np.empty(ndev + 1, dtype=np.int32)

    for k, idx in enumerate(iPxsh):
        f = F[idx]
        t = T[idx]

        # Partials of Ytt, Yff, Yft and Ytf w.r.t. Ɵ shift
        yft_dsh = -Ys[idx] / (-1j * k2[idx] * np.conj(tap[idx]))
        ytf_dsh = -Ys[idx] / (1j * k2[idx] * tap[idx])

        # Partials of S w.r.t. Ɵ shift
        val_f = V[f] * np.conj(yft_dsh * V[t])
        val_t = V[t] * np.conj(ytf_dsh * V[f])

        # dSbus_dPxsh[f, k] = val_f
        # dSbus_dPxsh[t, k] = val_t
        dSbus_dsh_data[2 * k] = val_f
        dSbus_dsh_indices[2 * k] = f
        dSbus_dsh_data[2 * k + 1] = val_t
        dSbus_dsh_indices[2 * k + 1] = t
        dSbus_dsh_indptr[k] = 2 * k

        # Partials of Sf w.r.t. Ɵ shift (makes sense that this is ∂Sbus/∂Pxsh assigned to the "from" bus)
        # dSf_dshx2[idx, k] = val_f
        dSf_dsh_data[k] = val_f
        dSf_dsh_indices[k] = idx
        dSf_dsh_indptr[k] = k

        # Partials of St w.r.t. Ɵ shift (makes sense that this is ∂Sbus/∂Pxsh assigned to the "to" bus)
        # dSt_dshx2[idx, k] = val_t
        dSt_dsh_data[k] = val_t
        dSt_dsh_indices[k] = idx
        dSt_dsh_indptr[k] = k

    dSbus_dsh_indptr[ndev] = ndev * 2
    dSf_dsh_indptr[ndev] = ndev
    dSt_dsh_indptr[ndev] = ndev

    return dSbus_dsh_data, dSbus_dsh_indices, dSbus_dsh_indptr, \
           dSf_dsh_data, dSf_dsh_indices, dSf_dsh_indptr, \
           dSt_dsh_data, dSt_dsh_indices, dSt_dsh_indptr


def derivatives_sh_csc_fast(nb, nl, iPxsh, F, T, Ys, k2, tap, V):
    """
    This function computes the derivatives of Sbus, Sf and St w.r.t. Ɵsh
    - dSbus_dPfsh, dSf_dPfsh, dSt_dPfsh -> if iPxsh=iPfsh
    - dSbus_dPfdp, dSf_dPfdp, dSt_dPfdp -> if iPxsh=iPfdp

    :param nb: number of buses
    :param nl: number of branches
    :param iPxsh: array of indices {iPfsh or iPfdp}
    :param F: Array of branch "from" bus indices
    :param T: Array of branch "to" bus indices
    :param Ys: Array of branch series admittances
    :param k2: Array of "k2" parameters
    :param tap: Array of branch complex taps (ma * exp(1j * theta_sh)
    :param V: Array of complex voltages
    :return:
        - dSbus_dPfsh, dSf_dPfsh, dSt_dPfsh -> if iPxsh=iPfsh
        - dSbus_dPfdp, dSf_dPfdp, dSt_dPfdp -> if iPxsh=iPfdp
    """
    ndev = len(iPxsh)

    dSbus_dsh_data, dSbus_dsh_indices, dSbus_dsh_indptr, \
    dSf_dsh_data, dSf_dsh_indices, dSf_dsh_indptr, \
    dSt_dsh_data, dSt_dsh_indices, dSt_dsh_indptr = derivatives_sh_csc_numba(iPxsh, F, T, Ys, k2, tap, V)

    dSbus_dsh = sp.csc_matrix((dSbus_dsh_data, dSbus_dsh_indices, dSbus_dsh_indptr), shape=(nb, ndev))
    dSf_dsh = sp.csc_matrix((dSf_dsh_data, dSf_dsh_indices, dSf_dsh_indptr), shape=(nl, ndev))
    dSt_dsh = sp.csc_matrix((dSt_dsh_data, dSt_dsh_indices, dSt_dsh_indptr), shape=(nl, ndev))

    return dSbus_dsh, dSf_dsh, dSt_dsh


def derivatives_ma(nb, nl, iXxma, F, T, Ys, k2, tap, ma, Bc, Beq, V):
    """
    Useful for the calculation of
    - dSbus_dQfma, dSf_dQfma, dSt_dQfma  -> wih iXxma=iQfma
    - dSbus_dQtma, dSf_dQtma, dSt_dQtma  -> wih iXxma=iQtma
    - dSbus_dVtma, dSf_dVtma, dSt_dVtma  -> wih iXxma=iVtma

    :param nb: Number of buses
    :param nl: Number of branches
    :param iXxma: Array of indices {iQfma, iQtma, iVtma}
    :param F: Array of branch "from" bus indices
    :param T: Array of branch "to" bus indices
    :param Ys: Array of branch series admittances
    :param k2: Array of "k2" parameters
    :param tap: Array of branch complex taps (ma * exp(1j * theta_sh)
    :param ma: Array of tap modules (this is to avoid extra calculations)
    :param Bc: Array of branch total shunt susceptance values (sum of the two legs)
    :param Beq: Array of regulation susceptance of the FUBM model
    :param V:Array of complex voltages

    :return:
    - dSbus_dQfma, dSf_dQfma, dSt_dQfma  -> if iXxma=iQfma
    - dSbus_dQtma, dSf_dQtma, dSt_dQtma  -> if iXxma=iQtma
    - dSbus_dVtma, dSf_dVtma, dSt_dVtma  -> if iXxma=iVtma
    """
    # Declare the derivative
    dSbus_dmax2 = lil_matrix((nb, len(iXxma)), dtype=complex)
    dSf_dmax2 = lil_matrix((nl, len(iXxma)), dtype=complex)
    dSt_dmax2 = lil_matrix((nl, len(iXxma)), dtype=complex)

    for k, idx in enumerate(iXxma):
        f = F[idx]
        t = T[idx]

        YttB = Ys[idx] + 1j * Bc[idx] / 2 + 1j * Beq[idx]

        # Partials of Ytt, Yff, Yft and Ytf w.r.t.ma
        dyff_dma = -2 * YttB / (np.power(k2[idx], 2) * np.power(ma[idx], 3))
        dyft_dma = Ys[idx] / (k2[idx] * ma[idx] * np.conj(tap[idx]))
        dytf_dma = Ys[idx] / (k2[idx] * ma[idx] * tap[idx])
        dytt_dma = 0

        # Partials of S w.r.t.ma
        val_f = V[f] * np.conj(dyff_dma * V[f] + dyft_dma * V[t])
        val_t = V[t] * np.conj(dytf_dma * V[f] + dytt_dma * V[t])
        dSbus_dmax2[f, k] = val_f
        dSbus_dmax2[t, k] = val_t

        dSf_dmax2[idx, k] = val_f
        dSt_dmax2[idx, k] = val_t

    return dSbus_dmax2.tocsc(), dSf_dmax2.tocsc(), dSt_dmax2.tocsc()


@nb.njit(cache=True)
def derivatives_ma_csc_numba(iXxma, F, T, Ys, k2, tap, ma, Bc, Beq, V):
    """
    Useful for the calculation of
    - dSbus_dQfma, dSf_dQfma, dSt_dQfma  -> wih iXxma=iQfma
    - dSbus_dQtma, dSf_dQtma, dSt_dQtma  -> wih iXxma=iQtma
    - dSbus_dVtma, dSf_dVtma, dSt_dVtma  -> wih iXxma=iVtma

    :param iXxma: Array of indices {iQfma, iQtma, iVtma}
    :param F: Array of branch "from" bus indices
    :param T: Array of branch "to" bus indices
    :param Ys: Array of branch series admittances
    :param k2: Array of "k2" parameters
    :param tap: Array of branch complex taps (ma * exp(1j * theta_sh)
    :param ma: Array of tap modules (this is to avoid extra calculations)
    :param Bc: Array of branch total shunt susceptance values (sum of the two legs)
    :param Beq: Array of regulation susceptance of the FUBM model
    :param V:Array of complex voltages

    :return:
    - dSbus_dQfma, dSf_dQfma, dSt_dQfma  -> if iXxma=iQfma
    - dSbus_dQtma, dSf_dQtma, dSt_dQtma  -> if iXxma=iQtma
    - dSbus_dVtma, dSf_dVtma, dSt_dVtma  -> if iXxma=iVtma
    """
    # Declare the derivative
    ndev = len(iXxma)
    ndev2 = ndev * 2

    # dSbus_dma = lil_matrix((nb, ndev), dtype=complex)
    dSbus_dma_data = np.empty(ndev2, dtype=np.complex128)
    dSbus_dma_indices = np.empty(ndev2, dtype=np.int32)
    dSbus_dma_indptr = np.empty(ndev + 1, dtype=np.int32)

    # dSf_dma = lil_matrix((nl, ndev), dtype=complex)
    dSf_dma_data = np.empty(ndev, dtype=np.complex128)
    dSf_dma_indices = np.empty(ndev, dtype=np.int32)
    dSf_dma_indptr = np.empty(ndev + 1, dtype=np.int32)

    # dSt_dma = lil_matrix((nl, ndev), dtype=complex)
    dSt_dma_data = np.empty(ndev, dtype=np.complex128)
    dSt_dma_indices = np.empty(ndev, dtype=np.int32)
    dSt_dma_indptr = np.empty(ndev + 1, dtype=np.int32)

    for k, idx in enumerate(iXxma):
        f = F[idx]
        t = T[idx]

        YttB = Ys[idx] + 1j * (Bc[idx] / 2 + Beq[idx])

        # Partials of Ytt, Yff, Yft and Ytf w.r.t.ma
        dyff_dma = -2 * YttB / (np.power(k2[idx], 2) * np.power(ma[idx], 3))
        dyft_dma = Ys[idx] / (k2[idx] * ma[idx] * np.conj(tap[idx]))
        dytf_dma = Ys[idx] / (k2[idx] * ma[idx] * tap[idx])

        val_f = V[f] * np.conj(dyff_dma * V[f] + dyft_dma * V[t])
        val_t = V[t] * np.conj(dytf_dma * V[f])

        # Partials of S w.r.t.ma
        # dSbus_dma[f, k] = val_f
        # dSbus_dma[t, k] = val_t
        dSbus_dma_data[2 * k] = val_f
        dSbus_dma_indices[2 * k] = f
        dSbus_dma_data[2 * k + 1] = val_t
        dSbus_dma_indices[2 * k + 1] = t
        dSbus_dma_indptr[k] = 2 * k

        # dSf_dma[idx, k] = val_f
        dSf_dma_data[k] = val_f
        dSf_dma_indices[k] = idx
        dSf_dma_indptr[k] = k

        # dSt_dma[idx, k] = val_f
        dSt_dma_data[k] = val_t
        dSt_dma_indices[k] = idx
        dSt_dma_indptr[k] = k

    dSbus_dma_indptr[ndev] = ndev * 2
    dSf_dma_indptr[ndev] = ndev
    dSt_dma_indptr[ndev] = ndev

    return dSbus_dma_data, dSbus_dma_indices, dSbus_dma_indptr, \
           dSf_dma_data, dSf_dma_indices, dSf_dma_indptr, \
           dSt_dma_data, dSt_dma_indices, dSt_dma_indptr


def derivatives_ma_csc_fast(nb, nl, iXxma, F, T, Ys, k2, tap, ma, Bc, Beq, V):
    """
    Useful for the calculation of
    - dSbus_dQfma, dSf_dQfma, dSt_dQfma  -> wih iXxma=iQfma
    - dSbus_dQtma, dSf_dQtma, dSt_dQtma  -> wih iXxma=iQtma
    - dSbus_dVtma, dSf_dVtma, dSt_dVtma  -> wih iXxma=iVtma

    :param nb: Number of buses
    :param nl: Number of branches
    :param iXxma: Array of indices {iQfma, iQtma, iVtma}
    :param F: Array of branch "from" bus indices
    :param T: Array of branch "to" bus indices
    :param Ys: Array of branch series admittances
    :param k2: Array of "k2" parameters
    :param tap: Array of branch complex taps (ma * exp(1j * theta_sh)
    :param ma: Array of tap modules (this is to avoid extra calculations)
    :param Bc: Array of branch total shunt susceptance values (sum of the two legs)
    :param Beq: Array of regulation susceptance of the FUBM model
    :param V:Array of complex voltages

    :return:
    - dSbus_dQfma, dSf_dQfma, dSt_dQfma  -> if iXxma=iQfma
    - dSbus_dQtma, dSf_dQtma, dSt_dQtma  -> if iXxma=iQtma
    - dSbus_dVtma, dSf_dVtma, dSt_dVtma  -> if iXxma=iVtma
    """
    # Declare the derivative
    ndev = len(iXxma)

    dSbus_dma_data, dSbus_dma_indices, dSbus_dma_indptr, \
    dSf_dma_data, dSf_dma_indices, dSf_dma_indptr, \
    dSt_dma_data, dSt_dma_indices, dSt_dma_indptr = derivatives_ma_csc_numba(iXxma, F, T, Ys, k2, tap, ma, Bc, Beq, V)

    dSbus_dma = sp.csc_matrix((dSbus_dma_data, dSbus_dma_indices, dSbus_dma_indptr), shape=(nb, ndev))
    dSf_dma = sp.csc_matrix((dSf_dma_data, dSf_dma_indices, dSf_dma_indptr), shape=(nl, ndev))
    dSt_dma = sp.csc_matrix((dSt_dma_data, dSt_dma_indices, dSt_dma_indptr), shape=(nl, ndev))

    return dSbus_dma, dSf_dma, dSt_dma


def derivatives_Beq(nb, nl, iBeqx, F, T, V, ma, k2):
    """
    Compute the derivatives of:
    - dSbus_dBeqz, dSf_dBeqz, dSt_dBeqz -> iBeqx=iBeqz
    - dSbus_dBeqv, dSf_dBeqv, dSt_dBeqv -> iBeqx=iBeqv

    :param nb: Number of buses
    :param nl: Number of branches
    :param iBeqx: array of indices {iBeqz, iBeqv}
    :param F: Array of branch "from" bus indices
    :param T: Array of branch "to" bus indices
    :param V:Array of complex voltages
    :param ma: Array of branch taps modules
    :param k2: Array of "k2" parameters

    :return:
    - dSbus_dBeqz, dSf_dBeqz, dSt_dBeqz -> if iBeqx=iBeqz
    - dSbus_dBeqv, dSf_dBeqv, dSt_dBeqv -> if iBeqx=iBeqv
    """
    # Declare the derivative
    dSbus_dBeqx = lil_matrix((nb, len(iBeqx)), dtype=complex)
    dSf_dBeqx = lil_matrix((nl, len(iBeqx)), dtype=complex)
    dSt_dBeqx = lil_matrix((nl, len(iBeqx)), dtype=complex)

    for k, idx in enumerate(iBeqx):
        f = F[idx]
        t = T[idx]

        # Partials of Ytt, Yff, Yft and Ytf w.r.t.Beq
        dyff_dBeq = 1j / np.power(k2[idx] * ma[idx], 2.0)
        dyft_dBeq = 0
        dytf_dBeq = 0
        dytt_dBeq = 0

        # Partials of S w.r.t.Beq
        val_f = V[f] * np.conj(dyff_dBeq * V[f] + dyft_dBeq * V[t])
        val_t = V[t] * np.conj(dytf_dBeq * V[f] + dytt_dBeq * V[t])

        dSbus_dBeqx[f, k] = val_f
        dSbus_dBeqx[t, k] = val_t

        # Partials of Sf w.r.t.Beq
        dSf_dBeqx[idx, k] = val_f

        # Partials of St w.r.t.Beq
        dSt_dBeqx[idx, k] = val_t

    return dSbus_dBeqx.tocsc(), dSf_dBeqx.tocsc(), dSt_dBeqx.tocsc()


@nb.njit(cache=True)
def derivatives_Beq_csc_numba(iBeqx, F, V, ma, k2):
    """
    Compute the derivatives of:
    - dSbus_dBeqz, dSf_dBeqz, dSt_dBeqz -> iBeqx=iBeqz
    - dSbus_dBeqv, dSf_dBeqv, dSt_dBeqv -> iBeqx=iBeqv

    :param iBeqx: array of indices {iBeqz, iBeqv}
    :param F: Array of branch "from" bus indices
    :param V:Array of complex voltages
    :param ma: Array of branch taps modules
    :param k2: Array of "k2" parameters

    :return:
    - dSbus_dBeqz, dSf_dBeqz, dSt_dBeqz -> if iBeqx=iBeqz
    - dSbus_dBeqv, dSf_dBeqv, dSt_dBeqv -> if iBeqx=iBeqv
    """

    ndev = len(iBeqx)

    dSbus_dBeq_data = np.empty(ndev, dtype=np.complex128)
    dSbus_dBeq_indices = np.empty(ndev, dtype=np.int32)
    dSbus_dBeq_indptr = np.empty(ndev + 1, dtype=np.int32)

    dSf_dBeqx_data = np.empty(ndev, dtype=np.complex128)
    dSf_dBeqx_indices = np.empty(ndev, dtype=np.int32)
    dSf_dBeqx_indptr = np.empty(ndev + 1, dtype=np.int32)

    for k, idx in enumerate(iBeqx):
        # k: 0, 1, 2, 3, 4, ...
        # idx: actual branch index in the general branches schema

        f = F[idx]

        # Partials of Ytt, Yff, Yft and Ytf w.r.t.Beq
        dyff_dBeq = 1j / np.power(k2[idx] * ma[idx], 2.0)

        # Partials of S w.r.t.Beq
        val_f = V[f] * np.conj(dyff_dBeq * V[f])

        # dSbus_dBeqx[f, k] = val_f
        dSbus_dBeq_data[k] = val_f
        dSbus_dBeq_indices[k] = f
        dSbus_dBeq_indptr[k] = k

        # dSbus_dBeqx[t, k] = val_t
        # (no need to store this one)

        # Partials of Sf w.r.t.Beq
        # dSf_dBeqx[idx, k] = val_f
        dSf_dBeqx_data[k] = val_f
        dSf_dBeqx_indices[k] = idx
        dSf_dBeqx_indptr[k] = k

        # Partials of St w.r.t.Beq
        # dSt_dBeqx[idx, k] = val_t
        # (no need to store this one)

    dSbus_dBeq_indptr[ndev] = ndev
    dSf_dBeqx_indptr[ndev] = ndev

    return dSbus_dBeq_data, dSbus_dBeq_indices, dSbus_dBeq_indptr, dSf_dBeqx_data, dSf_dBeqx_indices, dSf_dBeqx_indptr


def derivatives_Beq_csc_fast(nb, nl, iBeqx, F, T, V, ma, k2):
    """
    Compute the derivatives of:
    - dSbus_dBeqz, dSf_dBeqz, dSt_dBeqz -> iBeqx=iBeqz
    - dSbus_dBeqv, dSf_dBeqv, dSt_dBeqv -> iBeqx=iBeqv

    :param nb: Number of buses
    :param nl: Number of branches
    :param iBeqx: array of indices {iBeqz, iBeqv}
    :param F: Array of branch "from" bus indices
    :param T: Array of branch "to" bus indices
    :param V:Array of complex voltages
    :param ma: Array of branch taps modules
    :param k2: Array of "k2" parameters

    :return:
    - dSbus_dBeqz, dSf_dBeqz, dSt_dBeqz -> if iBeqx=iBeqz
    - dSbus_dBeqv, dSf_dBeqv, dSt_dBeqv -> if iBeqx=iBeqv
    """

    ndev = len(iBeqx)

    dSbus_dBeq_data, dSbus_dBeq_indices, dSbus_dBeq_indptr, \
    dSf_dBeqx_data, dSf_dBeqx_indices, dSf_dBeqx_indptr = derivatives_Beq_csc_numba(iBeqx, F, V, ma, k2)

    dSbus_dBeqx = sp.csc_matrix((dSbus_dBeq_data, dSbus_dBeq_indices, dSbus_dBeq_indptr), shape=(nb, ndev))
    dSf_dBeqx = sp.csc_matrix((dSf_dBeqx_data, dSf_dBeqx_indices, dSf_dBeqx_indptr), shape=(nl, ndev))
    dSt_dBeqx = sp.csc_matrix((nl, ndev), dtype=complex)

    return dSbus_dBeqx, dSf_dBeqx, dSt_dBeqx

