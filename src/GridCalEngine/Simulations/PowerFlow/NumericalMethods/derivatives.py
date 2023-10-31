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

import numpy as np
import numba as nb
from typing import Tuple
import scipy.sparse as sp
from scipy.sparse import lil_matrix, diags, csc_matrix, csr_matrix
from GridCalEngine.basic_structures import Vec, CxVec, IntVec


def dSbus_dV(Ybus: csc_matrix, V: CxVec) -> Tuple[csc_matrix, csc_matrix]:
    """
    Derivatives of the power Injections w.r.t the voltage
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
def dSbus_dV_numba_sparse_csc(Yx: CxVec, Yp: IntVec, Yi: IntVec, V: CxVec, E: CxVec) -> Tuple[CxVec, CxVec]:
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
def dSbus_dV_numba_sparse_csr(Yx: CxVec, Yp: IntVec, Yj: IntVec, V: CxVec, E: CxVec) -> Tuple[CxVec, CxVec]:  # pragma: no cover
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


def dSbus_dV_csc(Ybus: csc_matrix, V: CxVec, E: CxVec) -> Tuple[csc_matrix, csc_matrix]:
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
    return (sp.csc_matrix((dS_dVa, Ybus.indices, Ybus.indptr)),
            sp.csc_matrix((dS_dVm, Ybus.indices, Ybus.indptr)))


def dSbus_dV_csr(Ybus: csc_matrix, V: CxVec) -> Tuple[csr_matrix, csr_matrix]:
    """
    Calls functions to calculate dS/dV depending on whether Ybus is sparse or not
    :param Ybus: Ybus in CSC
    :param V: Voltages vector
    :return: dS_dVm, dS_dVa in CSR format
    """

    # I is subtracted from Y*V,
    # therefore it must be negative for numba version of dSbus_dV if it is not zeros anyways
    # calculates sparse data
    dS_dVm, dS_dVa = dSbus_dV_numba_sparse_csr(Ybus.data, Ybus.indptr, Ybus.indices, V, V / np.abs(V))

    # generate sparse CSR matrices with computed data and return them
    return (sp.csr_matrix((dS_dVm, Ybus.indices, Ybus.indptr)),
            sp.csr_matrix((dS_dVa, Ybus.indices, Ybus.indptr)))


def dSbr_dV_matpower(Yf: csc_matrix, Yt: csc_matrix, V: CxVec,
                     F: IntVec, T: IntVec,
                     Cf: csc_matrix, Ct: csc_matrix) -> Tuple[csc_matrix, csc_matrix, csc_matrix, csc_matrix]:
    """
    Derivatives of the branch power w.r.t the branch voltage modules and angles
    :param Yf: Admittances matrix of the Branches with the "from" buses
    :param Yt: Admittances matrix of the Branches with the "to" buses
    :param V: Array of voltages
    :param F: Array of branch "from" bus indices
    :param T: Array of branch "to" bus indices
    :param Cf: Connectivity matrix of the Branches with the "from" buses
    :param Ct: Connectivity matrix of the Branches with the "to" buses
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


def dSf_dV_matpower(Yf: csc_matrix, V: CxVec, F: IntVec,
                    Cf: csc_matrix, Vc: CxVec,
                    diagVc: csc_matrix,
                    diagE: csc_matrix,
                    diagV: csc_matrix) -> Tuple[csc_matrix, csc_matrix]:
    """
    Derivatives of the branch power "from" w.r.t the branch voltage modules and angles
    :param Yf: Admittances matrix of the Branches with the "from" buses
    :param V: Array of voltages
    :param F: Array of branch "from" bus indices
    :param Cf: Connectivity matrix of the Branches with the "from" buses
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


def dSt_dV_matpower(Yt, V, T, Ct, Vc, diagVc, diagE, diagV):
    """
    Derivatives of the branch power "to" w.r.t the branch voltage modules and angles
    :param Yt: Admittances matrix of the Branches with the "to" buses
    :param V: Array of voltages
    :param T: Array of branch "to" bus indices
    :param Ct: Connectivity matrix of the Branches with the "to" buses
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


# ----------------------------------------------------------------------------------------------------------------------


@nb.jit(cache=True, nopython=True)
def map_coordinates_numba(nrows, ncols, indptr, indices, F, T):
    """

    :param nrows:
    :param ncols:
    :param indptr:
    :param indices:
    :param F:
    :param T:
    :return:
    """
    idx_f = np.zeros(nrows, dtype=nb.int32)
    idx_t = np.zeros(nrows, dtype=nb.int32)
    for j in range(ncols):  # para cada columna j ...
        for k in range(indptr[j], indptr[j + 1]):  # para cada entrada de la columna ....
            i = indices[k]  # obtener el índice de la fila

            if j == F[i]:
                idx_f[i] = k
            elif j == T[i]:
                idx_t[i] = k

    return idx_f, idx_t


@nb.jit(cache=True, nopython=True)
def dSf_dV_numba(Yf_nrows, Yf_nnz, Yf_data, V, F, T, idx_f, idx_t):
    """

    :param Yf_nrows:
    :param Yf_nnz:
    :param Yf_data:
    :param V:
    :param F:
    :param T:
    :param idx_f:
    :param idx_t:
    :return:
    """
    dSf_dVm = np.zeros(Yf_nnz, dtype=nb.complex128)
    dSf_dVa = np.zeros(Yf_nnz, dtype=nb.complex128)
    for k in range(Yf_nrows):  # number of Branches (rows), actually k is the branch index
        f = F[k]
        t = T[k]
        kf = idx_f[k]
        kt = idx_t[k]

        Vm_f = np.abs(V[f])
        Vm_t = np.abs(V[t])
        th_f = np.angle(V[f])
        th_t = np.angle(V[t])
        ea = np.exp((th_f - th_t) * 1j)

        dSf_dVm[kf] = 2 * Vm_f * np.conj(Yf_data[kf]) + Vm_t * np.conj(Yf_data[kt]) * ea
        dSf_dVm[kt] = Vm_f * np.conj(Yf_data[kt]) * ea
        dSf_dVa[kf] = Vm_f * Vm_t * np.conj(Yf_data[kt]) * ea * 1j
        dSf_dVa[kt] = -dSf_dVa[kf]

    return dSf_dVm, dSf_dVa


@nb.jit(cache=True, nopython=True)
def dSt_dV_numba(Yt_nrows, Yt_nnz, Yt_data, V, F, T, idx_f, idx_t):
    """

    :param Yt_nrows:
    :param Yt_nnz:
    :param Yt_data:
    :param V:
    :param F:
    :param T:
    :param idx_f:
    :param idx_t:
    :return:
    """
    dSt_dVm = np.zeros(Yt_nnz, dtype=nb.complex128)
    dSt_dVa = np.zeros(Yt_nnz, dtype=nb.complex128)
    for k in range(Yt_nrows):  # number of Branches (rows), actually k is the branch index
        f = F[k]
        t = T[k]
        kf = idx_f[k]
        kt = idx_t[k]

        Vm_f = np.abs(V[f])
        Vm_t = np.abs(V[t])
        th_f = np.angle(V[f])
        th_t = np.angle(V[t])
        ea = np.exp((th_t - th_f) * 1j)

        dSt_dVm[kf] = Vm_t * np.conj(Yt_data[kf]) * ea
        dSt_dVm[kt] = 2 * Vm_t * np.conj(Yt_data[kt]) + Vm_f * np.conj(Yt_data[kf]) * ea
        dSt_dVa[kf] = - Vm_f * Vm_t * np.conj(Yt_data[kf]) * ea * 1j
        dSt_dVa[kt] = - dSt_dVa[kf]

    return dSt_dVm, dSt_dVa


def dSf_dV_csc(Yf, V, F, T):
    """
    Flow "from" derivative w.r.t the voltage
    :param Yf:
    :param V:
    :param F:
    :param T:
    :return:
    """
    # map the i, j coordinates
    idx_f, idx_t = map_coordinates_numba(nrows=Yf.shape[0],
                                         ncols=Yf.shape[1],
                                         indptr=Yf.indptr,
                                         indices=Yf.indices,
                                         F=F,
                                         T=T)

    dSf_dVm_data, dSf_dVa_data = dSf_dV_numba(Yf_nrows=Yf.shape[0],
                                              Yf_nnz=Yf.nnz,
                                              Yf_data=Yf.data,
                                              V=V,
                                              F=F,
                                              T=T,
                                              idx_f=idx_f,
                                              idx_t=idx_t)

    return csc_matrix((dSf_dVm_data, Yf.indices, Yf.indptr), shape=Yf.shape), \
           csc_matrix((dSf_dVa_data, Yf.indices, Yf.indptr), shape=Yf.shape)


def dSt_dV_csc(Yt, V, F, T):
    """
    Flow "to" derivative w.r.t the voltage
    :param Yt:
    :param V:
    :param F:
    :param T:
    :return:
    """

    # map the i, j coordinates
    idx_f, idx_t = map_coordinates_numba(nrows=Yt.shape[0],
                                         ncols=Yt.shape[1],
                                         indptr=Yt.indptr,
                                         indices=Yt.indices,
                                         F=F,
                                         T=T)

    dSt_dVm_data, dSt_dVa_data = dSt_dV_numba(Yt_nrows=Yt.shape[0],
                                              Yt_nnz=Yt.nnz,
                                              Yt_data=Yt.data,
                                              V=V,
                                              F=F,
                                              T=T,
                                              idx_f=idx_f,
                                              idx_t=idx_t)

    return csc_matrix((dSt_dVm_data, Yt.indices, Yt.indptr), shape=Yt.shape), \
           csc_matrix((dSt_dVa_data, Yt.indices, Yt.indptr), shape=Yt.shape)


# ----------------------------------------------------------------------------------------------------------------------

def derivatives_sh(nb, nl, iPxsh, F, T, Ys, k2, tap, V):
    """
    This function computes the derivatives of Sbus, Sf and St w.r.t. Ɵsh
    - dSbus_dPfsh, dSf_dPfsh, dSt_dPfsh -> if iPxsh=iPfsh
    - dSbus_dPfdp, dSf_dPfdp, dSt_dPfdp -> if iPxsh=iPfdp

    :param nb: number of buses
    :param nl: number of Branches
    :param iPxsh: array of indices {iPfsh or iPfdp}, this is the indices of the phase shifting Branches
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
def derivatives_tau_csc_numba(iPxsh, F: IntVec, T: IntVec, Ys: CxVec, k2, tap, V):
    """
    This function computes the derivatives of Sbus, Sf and St w.r.t. the tap angle (tau)
    - dSbus_dPfsh, dSf_dPfsh, dSt_dPfsh -> if iPxsh=iPfsh
    - dSbus_dPfdp, dSf_dPfdp, dSt_dPfdp -> if iPxsh=iPfdp

    :param iPxsh: array of indices {iPfsh or iPfdp}
    :param F: Array of branch "from" bus indices
    :param T: Array of branch "to" bus indices
    :param Ys: Array of branch series admittances
    :param k2: Array of "k2" parameters
    :param tap: Array of branch complex taps (m * exp(1j * tau)
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
        dSbus_dsh_data[2 * k + 1] = val_t
        dSbus_dsh_indices[2 * k] = f
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
    :param nl: number of Branches
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
    dSt_dsh_data, dSt_dsh_indices, dSt_dsh_indptr = derivatives_tau_csc_numba(iPxsh, F, T, Ys, k2, tap, V)

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
    :param nl: Number of Branches
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
    :param nl: Number of Branches
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
    :param nl: Number of Branches
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
        val_t = V[t] * np.conj(dytf_dBeq * V[f] + dytt_dBeq * V[t])  # 0

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
        # idx: actual branch index in the general Branches schema

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
    :param nl: Number of Branches
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

