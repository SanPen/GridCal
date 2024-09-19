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
from numba import njit, complex128, int32
from typing import Tuple
from scipy.sparse import csc_matrix
from GridCalEngine.basic_structures import CxVec, IntVec, Vec
from GridCalEngine.Utils.Sparse.csc2 import CSC, CxCSC, make_lookup


@njit(cache=True)
def dSbus_dV_numba_sparse_csc(Yx: CxVec, Yp: IntVec, Yi: IntVec, V: CxVec, Vm: CxVec) -> Tuple[CxVec, CxVec]:
    """
    Compute the power injection derivatives w.r.t the voltage module and angle
    :param Yx: data of Ybus in CSC format
    :param Yp: indptr of Ybus in CSC format
    :param Yi: indices of Ybus in CSC format
    :param V: Voltages vector
    :param Vm: voltage modules vector
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
    Ibus = np.zeros(n, dtype=complex128)
    dS_dVm_x = Yx.copy()
    dS_dVa_x = Yx.copy()
    E = V.copy()

    # pass 1: perform the matrix-vector products
    for j in range(n):  # for each column ...

        # compute the unitary vector of the voltage
        if Vm[j] > 0.0:
            E[j] /= Vm[j]

        for k in range(Yp[j], Yp[j + 1]):  # for each row ...
            # row index
            i = Yi[k]

            # Ibus = Ybus * V
            I = Yx[k] * V[j]

            # store in the Ibus vector
            Ibus[i] += I  # Yx[k] -> Y(i,j)

            # Ybus * diagE
            dS_dVm_x[k] = Yx[k] * E[j]

            # - Ybus * diag(V)
            dS_dVa_x[k] = -I

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
            dS_dVm_x[k] = V[i] * np.conj(dS_dVm_x[k])

            if j == i:
                # diagonal elements
                dS_dVa_x[k] += Ibus[j]  # diagIbus, after this it contains: diagIbus - Ybus * diagV
                dS_dVm_x[
                    k] += buffer  # conj(I(j)) * E(j), after this it contains; diag(V) * conj(Ybus * diagE) + conj(diagIbus) * diagE

            # 1j * diagV * conj(diagIbus - Ybus * diagV)
            dS_dVa_x[k] = (1j * V[i]) * np.conj(dS_dVa_x[k])

    return dS_dVm_x, dS_dVa_x


def dSbus_dV_csc(Ybus: csc_matrix, V: CxVec, Vm) -> Tuple[CxCSC, CxCSC]:
    """
    Call the numba sparse constructor of the derivatives
    :param Ybus: Ybus in CSC format
    :param V: Voltages vector
    :param Vm: Voltages modules
    :return: dS_dVm, dS_dVa in CSC format
    """
    # compute the derivatives' data fast
    dS_dVm_x, dS_dVa_x = dSbus_dV_numba_sparse_csc(Ybus.data, Ybus.indptr, Ybus.indices, V, Vm)

    dS_dVm = CxCSC(Ybus.shape[0], Ybus.shape[1], len(dS_dVm_x), False)
    dS_dVm.set(Ybus.indices, Ybus.indptr, dS_dVm_x)

    dS_dVa = CxCSC(Ybus.shape[0], Ybus.shape[1], len(dS_dVa_x), False)
    dS_dVa.set(Ybus.indices, Ybus.indptr, dS_dVa_x)

    # generate sparse CSC matrices with computed data and return them
    return dS_dVm, dS_dVa


# ----------------------------------------------------------------------------------------------------------------------


@njit()
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
    idx_f = np.zeros(nrows, dtype=int32)
    idx_t = np.zeros(nrows, dtype=int32)
    for j in range(ncols):  # para cada columna j ...
        for k in range(indptr[j], indptr[j + 1]):  # para cada entrada de la columna ....
            i = indices[k]  # obtener el índice de la fila

            if j == F[i]:
                idx_f[i] = k
            elif j == T[i]:
                idx_t[i] = k

    return idx_f, idx_t


@njit()
def dSf_dV_numba(Yf_nrows, Yf_ncols, Yf_indices, Yf_indptr, Yf_data, V, F, T) -> Tuple[CxCSC, CxCSC]:
    """

    :param Yf_nrows:
    :param Yf_ncols:
    :param Yf_indices:
    :param Yf_indptr:
    :param Yf_data:
    :param V:
    :param F:
    :param T:
    :return:
    """
    # map the i, j coordinates
    idx_f, idx_t = map_coordinates_numba(nrows=Yf_nrows,
                                         ncols=Yf_ncols,
                                         indptr=Yf_indptr,
                                         indices=Yf_indices,
                                         F=F,
                                         T=T)
    Yf_nnz = len(Yf_data)

    dSf_dVm = CxCSC(Yf_nrows, Yf_ncols, Yf_nnz, False)
    dSf_dVm.indptr = Yf_indptr
    dSf_dVm.indices = Yf_indices

    dSf_dVa = CxCSC(Yf_nrows, Yf_ncols, Yf_nnz, False)
    dSf_dVa.indptr = Yf_indptr
    dSf_dVa.indices = Yf_indices

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

        dSf_dVm.data[kf] = 2 * Vm_f * np.conj(Yf_data[kf]) + Vm_t * np.conj(Yf_data[kt]) * ea
        dSf_dVm.data[kt] = Vm_f * np.conj(Yf_data[kt]) * ea
        dSf_dVa.data[kf] = Vm_f * Vm_t * np.conj(Yf_data[kt]) * ea * 1j
        dSf_dVa.data[kt] = -dSf_dVa.data[kf]

    return dSf_dVm, dSf_dVa


@njit()
def dSt_dV_numba(Yt_nrows, Yt_ncols, Yt_indices, Yt_indptr, Yt_data, V, F, T) -> Tuple[CxCSC, CxCSC]:
    """

    :param Yt_nrows:
    :param Yt_ncols:
    :param Yt_indices:
    :param Yt_indptr:
    :param Yt_data:
    :param V:
    :param F:
    :param T:
    :return:
    """
    # map the i, j coordinates
    idx_f, idx_t = map_coordinates_numba(nrows=Yt_nrows,
                                         ncols=Yt_ncols,
                                         indptr=Yt_indptr,
                                         indices=Yt_indices,
                                         F=F,
                                         T=T)
    Yt_nnz = len(Yt_data)

    dSt_dVm = CxCSC(Yt_nrows, Yt_ncols, Yt_nnz, False)
    dSt_dVm.indptr = Yt_indptr
    dSt_dVm.indices = Yt_indices

    dSt_dVa = CxCSC(Yt_nrows, Yt_ncols, Yt_nnz, False)
    dSt_dVa.indptr = Yt_indptr
    dSt_dVa.indices = Yt_indices

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

        dSt_dVm.data[kf] = Vm_t * np.conj(Yt_data[kf]) * ea
        dSt_dVm.data[kt] = 2 * Vm_t * np.conj(Yt_data[kt]) + Vm_f * np.conj(Yt_data[kf]) * ea
        dSt_dVa.data[kf] = - Vm_f * Vm_t * np.conj(Yt_data[kf]) * ea * 1j
        dSt_dVa.data[kt] = - dSt_dVa.data[kf]

    return dSt_dVm, dSt_dVa


def dSf_dV_csc(Yf, V, F, T) -> Tuple[CxCSC, CxCSC]:
    """
    Flow "from" derivative w.r.t the voltage
    :param Yf:
    :param V:
    :param F:
    :param T:
    :return:
    """

    dSf_dVm, dSf_dVa = dSf_dV_numba(Yf_nrows=Yf.shape[0],
                                    Yf_ncols=Yf.shape[1],
                                    Yf_indices=Yf.indices,
                                    Yf_indptr=Yf.indptr,
                                    Yf_data=Yf.data,
                                    V=V,
                                    F=F,
                                    T=T)

    return dSf_dVm, dSf_dVa


def dSt_dV_csc(Yt, V, F, T) -> Tuple[CxCSC, CxCSC]:
    """
    Flow "to" derivative w.r.t the voltage
    :param Yt:
    :param V:
    :param F:
    :param T:
    :return:
    """

    dSt_dVm, dSt_dVa = dSt_dV_numba(Yt_nrows=Yt.shape[0],
                                    Yt_ncols=Yt.shape[1],
                                    Yt_indices=Yt.indices,
                                    Yt_indptr=Yt.indptr,
                                    Yt_data=Yt.data,
                                    V=V,
                                    F=F,
                                    T=T)

    return dSt_dVm, dSt_dVa


@njit()
def dSf_dVm_csc(nbus, br_indices, bus_indices, yff, yft, V, F, T) -> CxCSC:
    """
    dSf_dVm[br_indices, bus_indices]
    checked agins matpower derivatives
    :param nbus: number of buses
    :param br_indices: Branch indices
    :param bus_indices: Bus indices
    :param yff: yff primitives array
    :param yft: yft primitives array
    :param V: Voltages array
    :param F: Array of "from" indices
    :param T: Array of "to" indices
    :return: dSf_dVm
    """
    n_row = len(br_indices)
    n_cols = len(bus_indices)
    max_nnz = len(yff) * 2
    mat = CxCSC(n_row, n_cols, max_nnz, False)
    Tx = np.empty(max_nnz, dtype=np.complex128)
    Ti = np.empty(max_nnz, dtype=np.int32)
    Tj = np.empty(max_nnz, dtype=np.int32)

    j_lookup = make_lookup(nbus, bus_indices)

    nnz = 0
    # for j_counter, j in enumerate(bus_indices):  # para cada columna j ...
    for k_counter, k in enumerate(br_indices):
        f = F[k]
        t = T[k]
        f_idx = j_lookup[f]
        t_idx = j_lookup[t]
        Vm_f = np.abs(V[f])
        Vm_t = np.abs(V[t])
        th_f = np.angle(V[f])
        th_t = np.angle(V[t])
        ea = np.exp((th_f - th_t) * 1.0j)

        # from side
        if f_idx >= 0:
            Tx[nnz] = 2.0 * Vm_f * np.conj(yff[k]) + Vm_t * np.conj(yft[k]) * ea
            Ti[nnz] = k_counter
            Tj[nnz] = f_idx
            nnz += 1

        # to side
        if t_idx >= 0:
            Tx[nnz] = Vm_f * np.conj(yft[k]) * ea
            Ti[nnz] = k_counter
            Tj[nnz] = t_idx
            nnz += 1

    # convert to csc
    mat.fill_from_coo(Ti, Tj, Tx, nnz)

    return mat


@njit()
def dPfdp_dVm_csc(nbus, br_indices, bus_indices, yff, yft, kdp, V, F, T) -> CSC:
    """
    dSf_dVm[br_indices, bus_indices]
    checked agins matpower derivatives
    :param nbus: number of buses
    :param br_indices: Branch indices
    :param bus_indices: Bus indices
    :param yff: yff primitives array
    :param yft: yft primitives array
    :param V: Voltages array
    :param F: Array of "from" indices
    :param T: Array of "to" indices
    :return: dSf_dVm
    """

    """
    # # compute the droop derivative
    # dVmf_dVm = lil_matrix((nl, nb))
    # dVmf_dVm[k_pf_dp, :] = Cf[k_pf_dp, :]
    # dPfdp_dVm = -dSf_dVm.real + diags(Kdp) * dVmf_dVm
    """

    n_row = len(br_indices)
    n_cols = len(bus_indices)
    max_nnz = len(yff) * 2
    mat = CSC(n_row, n_cols, max_nnz, False)
    Tx = np.empty(max_nnz, dtype=np.float64)
    Ti = np.empty(max_nnz, dtype=np.int32)
    Tj = np.empty(max_nnz, dtype=np.int32)

    j_lookup = make_lookup(nbus, bus_indices)

    nnz = 0
    # for j_counter, j in enumerate(bus_indices):  # para cada columna j ...
    for k_counter, k in enumerate(br_indices):
        f = F[k]
        t = T[k]
        f_idx = j_lookup[f]
        t_idx = j_lookup[t]
        Vm_f = np.abs(V[f])
        Vm_t = np.abs(V[t])
        th_f = np.angle(V[f])
        th_t = np.angle(V[t])
        ea = np.exp((th_f - th_t) * 1.0j)

        # from side
        if f_idx >= 0:
            dSf_dvm = 2.0 * Vm_f * np.conj(yff[k]) + Vm_t * np.conj(yft[k]) * ea
            Tx[nnz] = - dSf_dvm.real + kdp[k]
            Ti[nnz] = k_counter
            Tj[nnz] = f_idx
            nnz += 1

        # to side
        if t_idx >= 0:
            dSf_dvm = Vm_f * np.conj(yft[k]) * ea
            Tx[nnz] = - dSf_dvm.real
            Ti[nnz] = k_counter
            Tj[nnz] = t_idx
            nnz += 1

    # convert to csc
    mat.fill_from_coo(Ti, Tj, Tx, nnz)

    return mat


@njit()
def dSf_dVa_csc(nbus, br_indices, bus_indices, yff, yft, V, F, T) -> CxCSC:
    """

    :param nbus: number of buses
    :param br_indices:
    :param bus_indices:
    :param yff:
    :param yft:
    :param V:
    :param F:
    :param T:
    :return:
    """
    n_row = len(br_indices)
    n_cols = len(bus_indices)
    max_nnz = len(yff) * 2
    mat = CxCSC(n_row, n_cols, max_nnz, False)
    Tx = np.empty(max_nnz, dtype=np.complex128)
    Ti = np.empty(max_nnz, dtype=np.int32)
    Tj = np.empty(max_nnz, dtype=np.int32)

    j_lookup = make_lookup(nbus, bus_indices)

    nnz = 0
    # for j_counter, j in enumerate(bus_indices):  # para cada columna j ...
    for k_counter, k in enumerate(br_indices):
        f = F[k]
        t = T[k]
        f_idx = j_lookup[f]
        t_idx = j_lookup[t]
        Vm_f = np.abs(V[f])
        Vm_t = np.abs(V[t])
        th_f = np.angle(V[f])
        th_t = np.angle(V[t])
        ea = np.exp((th_f - th_t) * 1.0j)

        if f_idx >= 0 or t_idx >= 0:
            val = Vm_f * Vm_t * np.conj(yft[k]) * ea * 1.0j

            # from side
            if f_idx >= 0:
                Tx[nnz] = val
                Ti[nnz] = k_counter
                Tj[nnz] = f_idx
                nnz += 1

            # to side
            if t_idx >= 0:
                Tx[nnz] = -val
                Ti[nnz] = k_counter
                Tj[nnz] = t_idx
                nnz += 1

    # convert to csc
    mat.fill_from_coo(Ti, Tj, Tx, nnz)

    return mat


@njit()
def dSt_dVm_csc(nbus, br_indices, bus_indices, ytt, ytf, V, F, T) -> CxCSC:
    """

    :param nbus
    :param br_indices:
    :param bus_indices:
    :param ytt:
    :param ytf:
    :param V:
    :param F:
    :param T:
    :return:
    """
    n_row = len(br_indices)
    n_cols = len(bus_indices)
    max_nnz = len(ytt) * 2
    mat = CxCSC(n_row, n_cols, max_nnz, False)
    Tx = np.empty(max_nnz, dtype=np.complex128)
    Ti = np.empty(max_nnz, dtype=np.int32)
    Tj = np.empty(max_nnz, dtype=np.int32)

    j_lookup = make_lookup(nbus, bus_indices)

    nnz = 0
    # for j_counter, j in enumerate(bus_indices):  # para cada columna j ...
    for k_counter, k in enumerate(br_indices):
        f = F[k]
        t = T[k]
        f_idx = j_lookup[f]
        t_idx = j_lookup[t]
        Vm_f = np.abs(V[f])
        Vm_t = np.abs(V[t])
        th_f = np.angle(V[f])
        th_t = np.angle(V[t])
        ea = np.exp((th_f - th_t) * 1.0j)

        # from side
        if f_idx >= 0:
            Tx[nnz] = Vm_t * np.conj(ytf[k]) * ea
            Ti[nnz] = k_counter
            Tj[nnz] = f_idx
            nnz += 1

        # to side
        if t_idx >= 0:
            Tx[nnz] = 2 * Vm_t * np.conj(ytt[k]) + Vm_f * np.conj(ytf[k]) * ea
            Ti[nnz] = k_counter
            Tj[nnz] = t_idx
            nnz += 1

    # convert to csc
    mat.fill_from_coo(Ti, Tj, Tx, nnz)

    return mat


@njit()
def dSt_dVa_csc(nbus, br_indices, bus_indices, ytf, V, F, T) -> CxCSC:
    """

    :param nbus
    :param br_indices:
    :param bus_indices:
    :param ytf:
    :param V:
    :param F:
    :param T:
    :return:
    """
    n_row = len(br_indices)
    n_cols = len(bus_indices)
    max_nnz = len(ytf) * 2
    mat = CxCSC(n_row, n_cols, max_nnz, False)
    Tx = np.empty(max_nnz, dtype=np.complex128)
    Ti = np.empty(max_nnz, dtype=np.int32)
    Tj = np.empty(max_nnz, dtype=np.int32)

    j_lookup = make_lookup(nbus, bus_indices)

    nnz = 0
    # for j_counter, j in enumerate(bus_indices):  # para cada columna j ...
    for k_counter, k in enumerate(br_indices):
        f = F[k]
        t = T[k]
        f_idx = j_lookup[f]
        t_idx = j_lookup[t]
        Vm_f = np.abs(V[f])
        Vm_t = np.abs(V[t])
        th_f = np.angle(V[f])
        th_t = np.angle(V[t])
        ea = np.exp((th_f - th_t) * 1.0j)

        if f_idx >= 0 or t_idx >= 0:
            val = Vm_f * Vm_t * np.conj(ytf[k]) * ea * 1j

            # from side
            if f_idx >= 0:
                Tx[nnz] = -val
                Ti[nnz] = k_counter
                Tj[nnz] = f_idx
                nnz += 1

            # to side
            if t_idx >= 0:
                Tx[nnz] = val
                Ti[nnz] = k_counter
                Tj[nnz] = t_idx
                nnz += 1

    # convert to csc
    mat.fill_from_coo(Ti, Tj, Tx, nnz)

    return mat


# ----------------------------------------------------------------------------------------------------------------------


@njit()
def derivatives_tau_csc_numba(nbus, nbr, iPxsh,
                              F: IntVec, T: IntVec,
                              Ys: CxVec, kconv, tap, V) -> Tuple[CxCSC, CxCSC, CxCSC]:
    """
    This function computes the derivatives of Sbus, Sf and St w.r.t. the tap angle (tau)
    - dSbus_dPfsh, dSf_dPfsh, dSt_dPfsh -> if iPxsh=iPfsh
    - dSbus_dPfdp, dSf_dPfdp, dSt_dPfdp -> if iPxsh=iPfdp

    :param nbus:
    :param nbr:
    :param iPxsh: array of indices {iPfsh or iPfdp}
    :param F: Array of branch "from" bus indices
    :param T: Array of branch "to" bus indices
    :param Ys: Array of branch series admittances
    :param kconv: Array of "k2" parameters
    :param tap: Array of branch complex taps (m * exp(1j * tau)
    :param V: Array of complex voltages
    :return:
        - dSbus_dPfsh, dSf_dPfsh, dSt_dPfsh -> if iPxsh=iPfsh
        - dSbus_dPfdp, dSf_dPfdp, dSt_dPfdp -> if iPxsh=iPfdp
    """
    ndev = len(iPxsh)

    # dSbus_dPxsh = lil_matrix((nb, ndev), dtype=complex)
    dSbus_dsh = CxCSC(nbus, ndev, ndev * 2, False)
    # dSbus_dsh_data = np.empty(ndev * 2, dtype=np.complex128)
    # dSbus_dsh_indices = np.empty(ndev * 2, dtype=np.int32)
    # dSbus_dsh_indptr = np.empty(ndev + 1, dtype=np.int32)

    # dSf_dsh = lil_matrix((nl, ndev), dtype=complex)
    dSf_dsh = CxCSC(nbr, ndev, ndev, False)
    # dSf_dsh_data = np.empty(ndev, dtype=np.complex128)
    # dSf_dsh_indices = np.empty(ndev, dtype=np.int32)
    # dSf_dsh_indptr = np.empty(ndev + 1, dtype=np.int32)

    # dSt_dsh = lil_matrix((nl, ndev), dtype=complex)
    dSt_dsh = CxCSC(nbr, ndev, ndev, False)
    # dSt_dsh_data = np.empty(ndev, dtype=np.complex128)
    # dSt_dsh_indices = np.empty(ndev, dtype=np.int32)
    # dSt_dsh_indptr = np.empty(ndev + 1, dtype=np.int32)

    for k, idx in enumerate(iPxsh):
        f = F[idx]
        t = T[idx]

        # Partials of Ytt, Yff, Yft and Ytf w.r.t. Ɵ shift
        yft_dsh = -Ys[idx] / (-1j * kconv[idx] * np.conj(tap[idx]))
        ytf_dsh = -Ys[idx] / (1j * kconv[idx] * tap[idx])

        # Partials of S w.r.t. Ɵ shift
        val_f = V[f] * np.conj(yft_dsh * V[t])
        val_t = V[t] * np.conj(ytf_dsh * V[f])

        # dSbus_dPxsh[f, k] = val_f
        # dSbus_dPxsh[t, k] = val_t
        dSbus_dsh.data[2 * k] = val_f
        dSbus_dsh.data[2 * k + 1] = val_t
        dSbus_dsh.indices[2 * k] = f
        dSbus_dsh.indices[2 * k + 1] = t
        dSbus_dsh.indptr[k] = 2 * k

        # Partials of Sf w.r.t. Ɵ shift (makes sense that this is ∂Sbus/∂Pxsh assigned to the "from" bus)
        # dSf_dshx2[idx, k] = val_f
        dSf_dsh.data[k] = val_f
        dSf_dsh.indices[k] = idx
        dSf_dsh.indptr[k] = k

        # Partials of St w.r.t. Ɵ shift (makes sense that this is ∂Sbus/∂Pxsh assigned to the "to" bus)
        # dSt_dshx2[idx, k] = val_t
        dSt_dsh.data[k] = val_t
        dSt_dsh.indices[k] = idx
        dSt_dsh.indptr[k] = k

    dSbus_dsh.indptr[ndev] = ndev * 2
    dSf_dsh.indptr[ndev] = ndev
    dSt_dsh.indptr[ndev] = ndev

    return dSbus_dsh, dSf_dsh, dSt_dsh


@njit()
def dSbus_dtau_csc(nbus, bus_indices, tau_indices, F: IntVec, T: IntVec, Ys: CxVec,
                   kconv: Vec, tap: CxVec, V: CxVec) -> CxCSC:
    """
    This function computes the derivatives of Sbus, Sf and St w.r.t. the tap angle (tau)
    - dSbus_dPfsh, dSf_dPfsh, dSt_dPfsh -> if iPxsh=iPfsh
    - dSbus_dPfdp, dSf_dPfdp, dSt_dPfdp -> if iPxsh=iPfdp

    :param nbus:
    :param bus_indices:
    :param tau_indices: array of indices {iPfsh or iPfdp}
    :param F: Array of branch "from" bus indices
    :param T: Array of branch "to" bus indices
    :param Ys: Array of branch series admittances
    :param kconv: Array of "k2" parameters
    :param tap: Array of branch complex taps (m * exp(1j * tau)
    :param V: Array of complex voltages
    :return: dSbus_dsh
    """
    n_cols = len(tau_indices)
    n_rows = len(bus_indices)
    max_nnz = len(tau_indices) * 2
    mat = CxCSC(n_rows, n_cols, max_nnz, False)
    Tx = np.empty(max_nnz, dtype=np.complex128)
    Ti = np.empty(max_nnz, dtype=np.int32)
    Tj = np.empty(max_nnz, dtype=np.int32)

    i_lookup = make_lookup(nbus, bus_indices)

    nnz = 0
    # for j_counter, j in enumerate(bus_indices):  # para cada columna j ...
    for k_counter, k in enumerate(tau_indices):
        f = F[k]
        t = T[k]
        f_idx = i_lookup[f]
        t_idx = i_lookup[t]

        # from side
        if f_idx >= 0:
            yft_dsh = -Ys[k] / (-1j * kconv[k] * np.conj(tap[k]))
            Tx[nnz] = V[f] * np.conj(yft_dsh * V[t])
            Ti[nnz] = f_idx
            Tj[nnz] = k_counter
            nnz += 1

        # to side
        if t_idx >= 0:
            ytf_dsh = -Ys[k] / (1j * kconv[k] * tap[k])
            Tx[nnz] = V[t] * np.conj(ytf_dsh * V[f])
            Ti[nnz] = t_idx
            Tj[nnz] = k_counter
            nnz += 1

    # convert to csc
    mat.fill_from_coo(Ti, Tj, Tx, nnz)

    return mat


@njit()
def dSf_dtau_csc(nbr, sf_indices, tau_indices, F: IntVec, T: IntVec, Ys: CxVec, kconv: Vec, tap: CxVec, V: CxVec) -> CxCSC:
    """
    This function computes the derivatives of Sbus, Sf and St w.r.t. the tap angle (tau)
    - dSbus_dPfsh, dSf_dPfsh, dSt_dPfsh -> if iPxsh=iPfsh
    - dSbus_dPfdp, dSf_dPfdp, dSt_dPfdp -> if iPxsh=iPfdp

    :param nbr: number of branches
    :param sf_indices: array of sf indices
    :param tau_indices: array of branch indices with tau control (must be equal to sf_indices)
    :param F: Array of branch "from" bus indices
    :param T: Array of branch "to" bus indices
    :param Ys: Array of branch series admittances
    :param kconv: Array of "k2" parameters
    :param tap: Array of branch complex taps (m * exp(1j * tau)
    :param V: Array of complex voltages
    :return: dSf_dsh
    """
    n_cols = len(tau_indices)
    n_rows = len(sf_indices)
    max_nnz = len(tau_indices)
    mat = CxCSC(n_rows, n_cols, max_nnz, False)
    Tx = np.empty(max_nnz, dtype=np.complex128)
    Ti = np.empty(max_nnz, dtype=np.int32)
    Tj = np.empty(max_nnz, dtype=np.int32)
    i_lookup = make_lookup(nbr, sf_indices)
    nnz = 0
    for k_idx, k in enumerate(tau_indices):

        i_idx = i_lookup[k]

        if i_idx > -1:
            f = F[k]
            t = T[k]

            # Partials of Ytt, Yff, Yft and Ytf w.r.t. Ɵ shift
            yft_dsh = -Ys[k] / (-1j * kconv[k] * np.conj(tap[k]))

            # Partials of Sf w.r.t. Ɵ shift (makes sense that this is ∂Sbus/∂Pxsh assigned to the "from" bus)
            Tx[nnz] = V[f] * np.conj(yft_dsh * V[t])
            Ti[nnz] = i_idx
            Tj[nnz] = k_idx
            nnz += 1

    # convert to csc
    mat.fill_from_coo(Ti, Tj, Tx, nnz)

    return mat


@njit()
def dSt_dtau_csc(nbr, st_indices, tau_indices, F: IntVec, T: IntVec, Ys: CxVec, kconv: Vec, tap: CxVec, V: CxVec) -> CxCSC:
    """
    This function computes the derivatives of Sbus, Sf and St w.r.t. the tap angle (tau)
    - dSbus_dPfsh, dSf_dPfsh, dSt_dPfsh -> if iPxsh=iPfsh
    - dSbus_dPfdp, dSf_dPfdp, dSt_dPfdp -> if iPxsh=iPfdp

    :param nbr: number of branches
    :param st_indices: array of st indices
    :param tau_indices: array of branch indices with tau control
    :param F: Array of branch "from" bus indices
    :param T: Array of branch "to" bus indices
    :param Ys: Array of branch series admittances
    :param kconv: Array of "k2" parameters
    :param tap: Array of branch complex taps (m * exp(1j * tau)
    :param V: Array of complex voltages
    :return: dSf_dsh
    :return: dSt_dtau
    """

    n_cols = len(tau_indices)
    n_rows = len(st_indices)
    max_nnz = len(tau_indices)
    mat = CxCSC(n_rows, n_cols, max_nnz, False)
    Tx = np.empty(max_nnz, dtype=np.complex128)
    Ti = np.empty(max_nnz, dtype=np.int32)
    Tj = np.empty(max_nnz, dtype=np.int32)
    i_lookup = make_lookup(nbr, st_indices)
    nnz = 0
    for k_idx, k in enumerate(tau_indices):
        i_idx = i_lookup[k]

        if i_idx > -1:
            f = F[k]
            t = T[k]

            # Partials of Ytt, Yff, Yft and Ytf w.r.t. Ɵ shift
            ytf_dsh = -Ys[k] / (1j * kconv[k] * tap[k])

            # Partials of Sf w.r.t. Ɵ shift (makes sense that this is ∂Sbus/∂Pxsh assigned to the "from" bus)
            Tx[nnz] = V[t] * np.conj(ytf_dsh * V[f])
            Ti[nnz] = i_idx
            Tj[nnz] = k_idx
            nnz += 1

    # convert to csc
    mat.fill_from_coo(Ti, Tj, Tx, nnz)

    return mat


@njit()
def derivatives_ma_csc_numba(nbus, nbr, iXxma, F, T, Ys, kconv, tap, tap_module, Bc, Beq, V) -> Tuple[CxCSC, CxCSC, CxCSC]:
    """
    Useful for the calculation of
    - dSbus_dQfma, dSf_dQfma, dSt_dQfma  -> wih iXxma=iQfma
    - dSbus_dQtma, dSf_dQtma, dSt_dQtma  -> wih iXxma=iQtma
    - dSbus_dVtma, dSf_dVtma, dSt_dVtma  -> wih iXxma=iVtma

    :param nbus: Number of buses
    :param nbr: Number of Branches
    :param iXxma: Array of indices {iQfma, iQtma, iVtma}
    :param F: Array of branch "from" bus indices
    :param T: Array of branch "to" bus indices
    :param Ys: Array of branch series admittances
    :param kconv: Array of "k2" parameters
    :param tap: Array of branch complex taps (ma * exp(1j * theta_sh)
    :param tap_module: Array of tap modules (this is to avoid extra calculations)
    :param Bc: Array of branch total shunt susceptance values (sum of the two legs)
    :param Beq: Array of regulation susceptance of the FUBM model
    :param V:Array of complex voltages

    :return: dSbus_dma, dSf_dma, dSt_dma
    """
    # Declare the derivative
    ndev = len(iXxma)

    # dSbus_dma = lil_matrix((nb, ndev), dtype=complex)
    dSbus_dma = CxCSC(nbus, ndev, ndev * 2, False)
    # dSbus_dma_data = np.empty(ndev2, dtype=np.complex128)
    # dSbus_dma_indices = np.empty(ndev2, dtype=np.int32)
    # dSbus_dma_indptr = np.empty(ndev + 1, dtype=np.int32)

    # dSf_dma = lil_matrix((nl, ndev), dtype=complex)
    dSf_dma = CxCSC(nbr, ndev, ndev, False)
    # dSf_dma_data = np.empty(ndev, dtype=np.complex128)
    # dSf_dma_indices = np.empty(ndev, dtype=np.int32)
    # dSf_dma_indptr = np.empty(ndev + 1, dtype=np.int32)

    # dSt_dma = lil_matrix((nl, ndev), dtype=complex)
    dSt_dma = CxCSC(nbr, ndev, ndev, False)
    # dSt_dma_data = np.empty(ndev, dtype=np.complex128)
    # dSt_dma_indices = np.empty(ndev, dtype=np.int32)
    # dSt_dma_indptr = np.empty(ndev + 1, dtype=np.int32)

    for k, idx in enumerate(iXxma):
        f = F[idx]
        t = T[idx]

        YttB = Ys[idx] + 1j * (Bc[idx] / 2 + Beq[idx])

        # Partials of Ytt, Yff, Yft and Ytf w.r.t.ma
        dyff_dma = -2 * YttB / (np.power(kconv[idx], 2) * np.power(tap_module[idx], 3))
        dyft_dma = Ys[idx] / (kconv[idx] * tap_module[idx] * np.conj(tap[idx]))
        dytf_dma = Ys[idx] / (kconv[idx] * tap_module[idx] * tap[idx])

        val_f = V[f] * np.conj(dyff_dma * V[f] + dyft_dma * V[t])
        val_t = V[t] * np.conj(dytf_dma * V[f])

        # Partials of S w.r.t.ma
        # dSbus_dma[f, k] = val_f
        # dSbus_dma[t, k] = val_t
        dSbus_dma.data[2 * k] = val_f
        dSbus_dma.indices[2 * k] = f
        dSbus_dma.data[2 * k + 1] = val_t
        dSbus_dma.indices[2 * k + 1] = t
        dSbus_dma.indptr[k] = 2 * k

        # dSf_dma[idx, k] = val_f
        dSf_dma.data[k] = val_f
        dSf_dma.indices[k] = idx
        dSf_dma.indptr[k] = k

        # dSt_dma[idx, k] = val_f
        dSt_dma.data[k] = val_t
        dSt_dma.indices[k] = idx
        dSt_dma.indptr[k] = k

    dSbus_dma.indptr[ndev] = ndev * 2
    dSf_dma.indptr[ndev] = ndev
    dSt_dma.indptr[ndev] = ndev

    return dSbus_dma, dSf_dma, dSt_dma


@njit()
def dSbus_dm_csc(nbus, bus_indices, m_indices, F: IntVec, T: IntVec, Ys: CxVec, Bc: CxVec, Beq: Vec,
                 kconv: Vec, tap: CxVec, tap_module: Vec, V: CxVec) -> CxCSC:
    """

    :param nbus:
    :param bus_indices:
    :param m_indices:
    :param F: Array of branch "from" bus indices
    :param T: Array of branch "to" bus indices
    :param Ys: Array of branch series admittances
    :param Bc: Array of branch total susceptance values (sum of the two legs)
    :param Beq: Array of regulation susceptance of the FUBM model
    :param kconv: Array of "k2" parameters
    :param tap: Array of branch complex taps (m * exp(1j * tau)
    :param tap_module: Array of tap modules
    :param V: Array of complex voltages
    :return:
    """
    n_cols = len(m_indices)
    n_rows = len(bus_indices)
    max_nnz = len(m_indices) * 2
    mat = CxCSC(n_rows, n_cols, max_nnz, False)
    Tx = np.empty(max_nnz, dtype=np.complex128)
    Ti = np.empty(max_nnz, dtype=np.int32)
    Tj = np.empty(max_nnz, dtype=np.int32)

    j_lookup = make_lookup(nbus, bus_indices)

    nnz = 0
    # for j_counter, j in enumerate(bus_indices):  # para cada columna j ...
    for k_counter, k in enumerate(m_indices):
        f = F[k]
        t = T[k]
        f_idx = j_lookup[f]
        t_idx = j_lookup[t]

        # from side
        if f_idx >= 0:
            YttB = Ys[k] + 1j * (Bc[k] / 2 + Beq[k])
            dyff_dm = -2 * YttB / (np.power(kconv[k], 2) * np.power(tap_module[k], 3))
            dyft_dm = Ys[k] / (kconv[k] * tap_module[k] * np.conj(tap[k]))
            Tx[nnz] = V[f] * np.conj(dyff_dm * V[f] + dyft_dm * V[t])
            Ti[nnz] = f_idx
            Tj[nnz] = k_counter
            nnz += 1

        # to side
        if t_idx >= 0:
            dytf_dm = Ys[k] / (kconv[k] * tap_module[k] * tap[k])
            Tx[nnz] = V[t] * np.conj(dytf_dm * V[f])
            Ti[nnz] = t_idx
            Tj[nnz] = k_counter
            nnz += 1

    # convert to csc
    mat.fill_from_coo(Ti, Tj, Tx, nnz)

    return mat


@njit()
def dSf_dm_csc(nbr, sf_indices, m_indices, F: IntVec, T: IntVec, Ys: CxVec, Bc: CxVec, Beq: Vec,
               kconv: Vec, tap: CxVec, tap_module: Vec, V: CxVec) -> CxCSC:
    """
    This function computes the derivatives of Sbus, Sf and St w.r.t. the tap angle (tau)
    - dSbus_dPfsh, dSf_dPfsh, dSt_dPfsh -> if iPxsh=iPfsh
    - dSbus_dPfdp, dSf_dPfdp, dSt_dPfdp -> if iPxsh=iPfdp

    :param nbr
    :param sf_indices: array of sf indices
    :param m_indices: array of branch indices with tau control
    :param F: Array of branch "from" bus indices
    :param T: Array of branch "to" bus indices
    :param Ys: Array of branch series admittances
    :param Bc: Array of branch total susceptance values
    :param Beq: Array of regulation susceptance of the FUBM model
    :param kconv: Array of "k2" parameters
    :param tap: Array of branch complex taps (m * exp(1j * tau)
    :param tap_module: Array of tap modules
    :param V: Array of complex voltages
    :return: dSf_dsh
    """
    n_cols = len(m_indices)
    n_rows = len(sf_indices)
    max_nnz = len(m_indices)
    mat = CxCSC(n_rows, n_cols, max_nnz, False)
    Tx = np.empty(max_nnz, dtype=np.complex128)
    Ti = np.empty(max_nnz, dtype=np.int32)
    Tj = np.empty(max_nnz, dtype=np.int32)
    i_lookup = make_lookup(nbr, sf_indices)
    nnz = 0
    for k_idx, k in enumerate(m_indices):
        i_idx = i_lookup[k]

        if i_idx > -1:
            f = F[k]
            t = T[k]

            YttB = Ys[k] + 1j * ((Bc[k] / 2.0) + Beq[k])

            # Partials of Ytt, Yff, Yft and Ytf w.r.t.ma
            dyff_dma = -2 * YttB / (np.power(kconv[k], 2) * np.power(tap_module[k], 3))
            dyft_dma = Ys[k] / (kconv[k] * tap_module[k] * np.conj(tap[k]))

            # Partials of Sf w.r.t. Ɵ shift (makes sense that this is ∂Sbus/∂Pxsh assigned to the "from" bus)
            Tx[nnz] = V[f] * np.conj(dyff_dma * V[f] + dyft_dma * V[t])
            Ti[nnz] = i_idx
            Tj[nnz] = k_idx
            nnz += 1

    # convert to csc
    mat.fill_from_coo(Ti, Tj, Tx, nnz)

    return mat


@njit()
def dSt_dm_csc(nbr, st_indices, m_indices, F: IntVec, T: IntVec, Ys: CxVec, kconv: Vec,
               tap: CxVec, tap_module: Vec, V: CxVec) -> CxCSC:
    """
    This function computes the derivatives of Sbus, Sf and St w.r.t. the tap angle (tau)
    - dSbus_dPfsh, dSf_dPfsh, dSt_dPfsh -> if iPxsh=iPfsh
    - dSbus_dPfdp, dSf_dPfdp, dSt_dPfdp -> if iPxsh=iPfdp

    :param nbr:
    :param st_indices: array of st indices
    :param m_indices: array of branch indices with tau control
    :param F: Array of branch "from" bus indices
    :param T: Array of branch "to" bus indices
    :param Ys: Array of branch series admittances
    :param kconv: Array of "k2" parameters
    :param tap: Array of branch complex taps (m * exp(1j * tau)
    :param tap_module
    :param V: Array of complex voltages
    :return: dSf_dsh
    :return: dSt_dtau
    """

    n_cols = len(m_indices)
    n_rows = len(st_indices)
    max_nnz = len(m_indices)
    mat = CxCSC(n_rows, n_cols, max_nnz, False)
    Tx = np.empty(max_nnz, dtype=np.complex128)
    Ti = np.empty(max_nnz, dtype=np.int32)
    Tj = np.empty(max_nnz, dtype=np.int32)
    i_lookup = make_lookup(nbr, st_indices)
    nnz = 0
    for k_idx, k in enumerate(m_indices):
        i_idx = i_lookup[k]

        if i_idx > -1:
            f = F[k]
            t = T[k]

            dytf_dma = Ys[k] / (kconv[k] * tap_module[k] * tap[k])

            # Partials of Sf w.r.t. Ɵ shift (makes sense that this is ∂Sbus/∂Pxsh assigned to the "from" bus)
            Tx[nnz] = V[t] * np.conj(dytf_dma * V[f])
            Ti[nnz] = i_idx
            Tj[nnz] = k_idx
            nnz += 1

    # convert to csc
    mat.fill_from_coo(Ti, Tj, Tx, nnz)

    return mat


@njit()
def derivatives_Beq_csc_numba(nbus, nbr, iBeqx, F, V, tap_module, kconv):
    """
    Compute the derivatives of:
    - dSbus_dBeqz, dSf_dBeqz, dSt_dBeqz -> iBeqx=iBeqz
    - dSbus_dBeqv, dSf_dBeqv, dSt_dBeqv -> iBeqx=iBeqv

    :param nbus: Number of buses
    :param nbr: Number of Branches
    :param iBeqx: array of indices {iBeqz, iBeqv}
    :param F: Array of branch "from" bus indices
    :param V:Array of complex voltages
    :param tap_module: Array of branch taps modules
    :param kconv: Array of "k2" parameters

    :return:
    - dSbus_dBeqz, dSf_dBeqz, dSt_dBeqz -> if iBeqx=iBeqz
    - dSbus_dBeqv, dSf_dBeqv, dSt_dBeqv -> if iBeqx=iBeqv
    """

    ndev = len(iBeqx)

    dSbus_dBeq = CxCSC(nbus, ndev, ndev, False)
    dSf_dBeq = CxCSC(nbr, ndev, ndev, False)
    dSt_dBeq = CxCSC(nbr, ndev, 0, True)

    for k, idx in enumerate(iBeqx):
        # k: 0, 1, 2, 3, 4, ...
        # idx: actual branch index in the general Branches schema

        f = F[idx]

        # Partials of Ytt, Yff, Yft and Ytf w.r.t.Beq
        dyff_dBeq = 1j / np.power(kconv[idx] * tap_module[idx], 2.0)

        # Partials of S w.r.t.Beq
        val_f = V[f] * np.conj(dyff_dBeq * V[f])

        # dSbus_dBeqx[f, k] = val_f
        dSbus_dBeq.data[k] = val_f
        dSbus_dBeq.indices[k] = f
        dSbus_dBeq.indptr[k] = k

        # dSbus_dBeqx[t, k] = val_t
        # (no need to store this one)

        # Partials of Sf w.r.t.Beq
        # dSf_dBeqx[idx, k] = val_f
        dSf_dBeq.data[k] = val_f
        dSf_dBeq.indices[k] = idx
        dSf_dBeq.indptr[k] = k

        # Partials of St w.r.t.Beq
        # dSt_dBeqx[idx, k] = val_t
        # (no need to store this one)

    dSbus_dBeq.indptr[ndev] = ndev
    dSf_dBeq.indptr[ndev] = ndev

    return dSbus_dBeq, dSf_dBeq, dSt_dBeq


@njit()
def dSbus_dbeq_csc(nbus, bus_indices, beq_indices, F: IntVec, kconv: Vec, tap_module: Vec, V: CxVec) -> CxCSC:
    """

    :param nbus:
    :param bus_indices:
    :param beq_indices:
    :param F: Array of branch "from" bus indices
    :param kconv: Array of "k2" parameters
    :param tap_module: Array of tap modules
    :param V: Array of complex voltages
    :return:
    """
    n_cols = len(beq_indices)
    n_rows = len(bus_indices)
    max_nnz = len(beq_indices)
    mat = CxCSC(n_rows, n_cols, max_nnz, False)
    Tx = np.empty(max_nnz, dtype=np.complex128)
    Ti = np.empty(max_nnz, dtype=np.int32)
    Tj = np.empty(max_nnz, dtype=np.int32)

    j_lookup = make_lookup(nbus, bus_indices)

    nnz = 0
    # for j_counter, j in enumerate(bus_indices):  # para cada columna j ...
    for k_counter, k in enumerate(beq_indices):
        f = F[k]
        f_idx = j_lookup[f]

        # from side
        if f_idx >= 0:
            """
            # Partials of Ytt, Yff, Yft and Ytf w.r.t.Beq
            dyff_dBeq = 1j / np.power(kconv[idx] * tap_module[idx], 2.0)
    
            # Partials of S w.r.t.Beq
            val_f = V[f] * np.conj(dyff_dBeq * V[f])
            """

            dyff_dBeq = 1.0j / np.power(kconv[k] * tap_module[k] + 1e-20, 2.0)
            Tx[nnz] = V[f] * np.conj(dyff_dBeq * V[f])
            Ti[nnz] = f_idx
            Tj[nnz] = k_counter
            nnz += 1

        # to side: it is zero

    # convert to csc
    mat.fill_from_coo(Ti, Tj, Tx, nnz)

    return mat


@njit()
def dSf_dbeq_csc(nbr, sf_indices, beq_indices, F: IntVec, kconv: Vec, tap_module: Vec, V: CxVec) -> CxCSC:
    """
    This function computes the derivatives of Sbus, Sf and St w.r.t. the tap angle (tau)
    - dSbus_dPfsh, dSf_dPfsh, dSt_dPfsh -> if iPxsh=iPfsh
    - dSbus_dPfdp, dSf_dPfdp, dSt_dPfdp -> if iPxsh=iPfdp

    :param nbr: Number of branches
    :param sf_indices: array of sf indices
    :param beq_indices: array of branch indices with tau control
    :param F: Array of branch "from" bus indices
    :param kconv: Array of "k2" parameters
    :param tap_module: Array of tap modules
    :param V: Array of complex voltages
    :return: dSf_dsh
    """
    n_cols = len(beq_indices)
    n_rows = len(sf_indices)
    max_nnz = len(beq_indices)
    mat = CxCSC(n_rows, n_cols, max_nnz, False)
    Tx = np.empty(max_nnz, dtype=np.complex128)
    Ti = np.empty(max_nnz, dtype=np.int32)
    Tj = np.empty(max_nnz, dtype=np.int32)
    i_lookup = make_lookup(nbr, sf_indices)
    nnz = 0
    for k_idx, k in enumerate(beq_indices):
        i_idx = i_lookup[k]

        if i_idx > -1:
            f = F[k]

            # Partials of Ytt, Yff, Yft and Ytf w.r.t.Beq
            dyff_dBeq = 1j / np.power(kconv[k] * tap_module[k] + 1e-20, 2.0)

            # Partials of Sf w.r.t. Ɵ shift (makes sense that this is ∂Sbus/∂Pxsh assigned to the "from" bus)
            Tx[nnz] = V[f] * np.conj(dyff_dBeq * V[f])
            Ti[nnz] = i_idx
            Tj[nnz] = k_idx
            nnz += 1

    # convert to csc
    mat.fill_from_coo(Ti, Tj, Tx, nnz)

    return mat


@njit()
def dSt_dbeq_csc(sf_indices, beq_indices) -> CxCSC:
    """
    This function computes the derivatives of Sbus, Sf and St w.r.t. the tap angle (tau)
    - dSbus_dPfsh, dSf_dPfsh, dSt_dPfsh -> if iPxsh=iPfsh
    - dSbus_dPfdp, dSf_dPfdp, dSt_dPfdp -> if iPxsh=iPfdp

    :param sf_indices: array of sf indices
    :param beq_indices: array of branch indices with tau control
    :return: dSf_dsh
    :return: dSt_dtau
    """

    n_cols = len(beq_indices)
    n_rows = len(sf_indices)
    mat = CxCSC(n_rows, n_cols, 0, False)

    # the whole thing is zero

    return mat
