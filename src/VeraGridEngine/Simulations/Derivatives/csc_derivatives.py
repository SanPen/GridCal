# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0


import numpy as np
from numba import njit, complex128, int32
from typing import Tuple
from scipy.sparse import csc_matrix
from VeraGridEngine.basic_structures import CxVec, IntVec, Vec
from VeraGridEngine.Utils.NumericalMethods.common import make_lookup
from VeraGridEngine.Utils.Sparse.csc2 import CSC, CxCSC
from VeraGridEngine.Utils.Sparse.csc_numba import ialloc


@njit(cache=True)
def dSbus_dV_numba_sparse_csc(Yx: CxVec, Yp: IntVec, Yi: IntVec, V: CxVec, Vm: Vec) -> Tuple[CxVec, CxVec]:
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
        if Vm[j] != 0.0:  # this is because now we can have negative voltages at the negative DC poles
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
                dS_dVm_x[k] += buffer  # conj(I(j)) * E(j), after this it contains; diag(V) * conj(Ybus * diagE) + conj(diagIbus) * diagE

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
def dSbr_dm_csc(nbus, u_cbr_m, F_cbr, T_cbr, yff_cbr, yft_cbr, ytf_cbr, ytt_cbr, V, tap, tap_modules) -> CxCSC:
    """
    Derivative of the controllable branch power flows (and hence bus balance) w.r.t. m
    :param nbus: number of buses
    :param u_cbr_m: Array of indices where m is unknown
    :param F_cbr: Array of branch "from" bus indices
    :param T_cbr: Array of branch "to" bus indices
    :param yff_cbr: Array of branch primitive admittances
    :param yft_cbr: Array of branch primitive admittances
    :param ytf_cbr: Array of branch primitive admittances
    :param ytt_cbr: Array of branch primitive admittances
    :param V: Array of complex voltages
    :param tap: Array of branch complex taps (m * exp(1j * tau)
    :param tap_modules: Array of branch tap modules
    :return: dSbr_dm
    """

    max_nnz = len(yff_cbr) * 2
    n_cbr_m = len(u_cbr_m)
    mat = CxCSC(nbus, n_cbr_m, max_nnz, False)
    Tx = np.empty(max_nnz, dtype=np.complex128)
    Ti = np.empty(max_nnz, dtype=np.int32)
    Tj = np.empty(max_nnz, dtype=np.int32)

    tau = np.angle(tap)

    nnz = 0
    for k_count, k_idx in enumerate(u_cbr_m):  # for each controllable branch ...
        f = F_cbr[k_idx]
        t = T_cbr[k_idx]
        Vf = V[f]
        Vt = V[t]

        Vm_f = np.abs(Vf)
        Vm_t = np.abs(Vt)

        # dSf/dm
        dsf_dm = (-2 * Vm_f * Vm_f * np.conj(yff_cbr[k_idx]) / (
                    tap_modules[k_idx] * tap_modules[k_idx] * tap_modules[k_idx])
                  - 1 * Vf * np.conj(Vt) * np.conj(yft_cbr[k_idx]) * np.exp(-1j * tau[k_idx]) / (
                              tap_modules[k_idx] * tap_modules[k_idx]))

        # dSt/dm
        dst_dm = -1 * Vt * np.conj(Vf) * np.conj(ytf_cbr[k_idx]) * np.exp(1j * tau[k_idx]) / (
                    tap_modules[k_idx] * tap_modules[k_idx])

        # add to the triplets
        Tx[nnz] = dsf_dm
        Ti[nnz] = f
        Tj[nnz] = k_count
        nnz += 1

        Tx[nnz] = dst_dm
        Ti[nnz] = t
        Tj[nnz] = k_count
        nnz += 1

    # convert to csc
    mat.fill_from_coo(Ti, Tj, Tx, nnz)

    return mat


@njit()
def dSbr_dtau_csc(nbus, u_cbr_tau, F_cbr, T_cbr, yff_cbr, yft_cbr, ytf_cbr, ytt_cbr, V, tap, tap_modules) -> CxCSC:
    """
    Derivative of the controllable branch power flows (and hence bus balance) w.r.t. tau
    :param nbus: number of buses
    :param u_cbr_m: Array of indices where m is unknown
    :param F_cbr: Array of branch "from" bus indices
    :param T_cbr: Array of branch "to" bus indices
    :param yff_cbr: Array of branch primitive admittances
    :param yft_cbr: Array of branch primitive admittances
    :param ytf_cbr: Array of branch primitive admittances
    :param ytt_cbr: Array of branch primitive admittances
    :param V: Array of complex voltages
    :param tap: Array of branch complex taps (m * exp(1j * tau)
    :param tap_modules: Array of branch tap modules
    :return: dSbr_dtau
    """

    max_nnz = len(yff_cbr) * 2
    n_cbr_tau = len(u_cbr_tau)
    mat = CxCSC(nbus, n_cbr_tau, max_nnz, False)
    Tx = np.empty(max_nnz, dtype=np.complex128)
    Ti = np.empty(max_nnz, dtype=np.int32)
    Tj = np.empty(max_nnz, dtype=np.int32)

    tau = np.angle(tap)

    nnz = 0
    for k_count, k_idx in enumerate(u_cbr_tau):  # for each controllable branch ...
        f = F_cbr[k_idx]
        t = T_cbr[k_idx]
        Vf = V[f]
        Vt = V[t]

        Vm_f = np.abs(Vf)
        Vm_t = np.abs(Vt)

        # dSf/dtau
        dsf_dtau = -1j * Vf * np.conj(Vt) * np.conj(yft_cbr[k_idx]) * np.exp(-1j * tau[k_idx]) / tap_modules[k_idx]

        # dSt/dm
        dst_dtau = 1j * Vt * np.conj(Vf) * np.conj(ytf_cbr[k_idx]) * np.exp(1j * tau[k_idx]) / tap_modules[k_idx]

        # add to the triplets
        Tx[nnz] = dsf_dtau
        Ti[nnz] = f
        Tj[nnz] = k_count
        nnz += 1

        Tx[nnz] = dst_dtau
        Ti[nnz] = t
        Tj[nnz] = k_count
        nnz += 1

    # convert to csc
    mat.fill_from_coo(Ti, Tj, Tx, nnz)

    return mat


# ------------------------

@njit()
def csc_add_wrapper(A: CxCSC, B: CxCSC, alpha: float = 1.0, beta: float = 1.0) -> CxCSC:
    """
    Wrapper for csc_add_ff
    :param A: matrix A
    :param B: matrix B
    :param alpha: scalar alpha
    :param beta: scalar beta
    :return: matrix C = A * alpha + B * beta
    """
    Cm, Cn, Cp, Ci, Cx = csc_add_ff_comp(A.shape[0], A.shape[1], A.indptr, A.indices, A.data,
                                         B.shape[0], B.shape[1], B.indptr, B.indices, B.data, 1.0, 1.0)

    my_csc = CxCSC(Cm, Cn, len(Cx), False)
    return my_csc.set(Ci, Cp, Cx)


@njit(cache=True)
def csc_add_ff_comp(Am, An, Aindptr, Aindices, Adata,
                    Bm, Bn, Bindptr, Bindices, Bdata, alpha, beta):
    """
    C = alpha*A + beta*B

    @param A: column-compressed matrix
    @param B: column-compressed matrix
    @param alpha: scalar alpha
    @param beta: scalar beta
    @return: C=alpha*A + beta*B, null on error (Cm, Cn, Cp, Ci, Cx)
    """
    nz = 0

    m, anz, n, Bp, Bx = Am, Aindptr[An], Bn, Bindptr, Bdata

    bnz = Bp[n]

    w = np.zeros(m, dtype=np.int32)

    x = np.zeros(m, dtype=np.complex128)

    Cm, Cn, Cp, Ci, Cx, Cnzmax = csc_spalloc_f(m, n, anz + bnz)  # allocate result

    for j in range(n):
        Cp[j] = nz  # column j of C starts here

        nz = csc_scatter_f_comp(Aindptr, Aindices, Adata, j, alpha, w, x, j + 1, Ci, nz)  # alpha*A(:,j)

        nz = csc_scatter_f_comp(Bindptr, Bindices, Bdata, j, beta, w, x, j + 1, Ci, nz)  # beta*B(:,j)

        for p in range(Cp[j], nz):
            Cx[p] = x[Ci[p]]

    Cp[n] = nz  # finalize the last column of C

    return Cm, Cn, Cp, Ci, Cx  # success; free workspace, return C


@njit(cache=True)
def csc_spalloc_f(m, n, nzmax):
    """
    Allocate a sparse matrix (triplet form or compressed-column form).

    @param m: number of rows
    @param n: number of columns
    @param nzmax: maximum number of entries
    @return: m, n, Aindptr, Aindices, Adata, Anzmax
    """
    Anzmax = max(nzmax, 1)
    Aindptr = ialloc(n + 1)
    Aindices = ialloc(Anzmax)
    Adata = xalloc_comp(Anzmax)
    return m, n, Aindptr, Aindices, Adata, Anzmax


@njit(cache=True)
def xalloc_comp(n):
    return np.zeros(n, dtype=np.complex128)


@njit(cache=True)
def csc_scatter_f_comp(Ap, Ai, Ax, j, beta, w, x, mark, Ci, nz):
    """
    Scatters and sums a sparse vector A(:,j) into a dense vector, x = x + beta * A(:,j)
    :param Ap:
    :param Ai:
    :param Ax:
    :param j: the column of A to use
    :param beta: scalar multiplied by A(:,j)
    :param w: size m, node i is marked if w[i] = mark
    :param x: size m, ignored if null
    :param mark: mark value of w
    :param Ci: pattern of x accumulated in C.i
    :param nz: pattern of x placed in C starting at C.i[nz]
    :return: new value of nz, -1 on error, x and w are modified
    """

    for p in range(Ap[j], Ap[j + 1]):
        i = Ai[p]  # A(i,j) is nonzero
        if w[i] < mark:
            w[i] = mark  # i is new entry in column j
            Ci[nz] = i  # add i to pattern of C(:,j)
            nz += 1
            x[i] = beta * Ax[p]  # x(i) = beta*A(i,j)
        else:
            x[i] += beta * Ax[p]  # i exists in C(:,j) already
    return nz


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
def dSf_dVm_csc(nbus, br_indices, bus_indices, yff, yft, Vm, Va, F, T) -> CxCSC:
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
        # Vm_f = np.abs(Vm[f])
        # Vm_t = np.abs(Vm[t])
        # th_f = np.angle(Va[f])
        # th_t = np.angle(Va[t])
        ea = np.exp((Va[f] - Va[t]) * 1.0j)

        # from side
        if f_idx >= 0:
            Tx[nnz] = 2.0 * Vm[f] * np.conj(yff[k]) + Vm[t] * np.conj(yft[k]) * ea
            Ti[nnz] = k_counter
            Tj[nnz] = f_idx
            nnz += 1

        # to side
        if t_idx >= 0:
            Tx[nnz] = Vm[f] * np.conj(yft[k]) * ea
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
def dSf_dVa_csc(nbus, br_indices, bus_indices, yft, V, F, T) -> CxCSC:
    """

    :param nbus: number of buses
    :param br_indices:
    :param bus_indices:
    :param yft:
    :param V:
    :param F:
    :param T:
    :return:
    """
    n_row = len(br_indices)
    n_cols = len(bus_indices)
    max_nnz = len(yft) * 2
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

        if f_idx >= 0 and t_idx >= 0:
            Vm_f = np.abs(V[f])
            Vm_t = np.abs(V[t])
            th_f = np.angle(V[f])
            th_t = np.angle(V[t])
            ea = np.exp((th_f - th_t) * 1.0j)

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
def dSt_dVm_csc(nbus, br_indices, bus_indices, ytt, ytf, Vm, Va, F, T) -> CxCSC:
    """

    :param nbus
    :param br_indices:
    :param bus_indices:
    :param ytt:
    :param ytf:
    :param Vm:
    :param Va:
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
        # Vm_f = np.abs(V[f])
        # Vm_t = np.abs(V[t])
        # th_f = np.angle(V[f])
        # th_t = np.angle(V[t])
        ea = np.exp((Va[f] - Va[t]) * 1.0j)

        # from side
        if f_idx >= 0:
            Tx[nnz] = Vm[t] * np.conj(ytf[k]) * ea
            Ti[nnz] = k_counter
            Tj[nnz] = f_idx
            nnz += 1

        # to side
        if t_idx >= 0:
            Tx[nnz] = 2 * Vm[t] * np.conj(ytt[k]) + Vm[f] * np.conj(ytf[k]) * ea
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


# original one
@njit()
def dSbus_dtau_csc(nbus, bus_indices, tau_indices, F: IntVec, T: IntVec, Ys: CxVec,
                   tap: CxVec, V: CxVec) -> CxCSC:
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
            yft_dsh = -Ys[k] / (-1j * np.conj(tap[k]))
            Tx[nnz] = V[f] * np.conj(yft_dsh * V[t])
            Ti[nnz] = f_idx
            Tj[nnz] = k_counter
            nnz += 1

        # to side
        if t_idx >= 0:
            ytf_dsh = -Ys[k] / (1j * tap[k])
            Tx[nnz] = V[t] * np.conj(ytf_dsh * V[f])
            Ti[nnz] = t_idx
            Tj[nnz] = k_counter
            nnz += 1

    # convert to csc
    mat.fill_from_coo(Ti, Tj, Tx, nnz)

    return mat


@njit()
def dSf_dtau_csc(nbr, sf_indices, tau_indices, F: IntVec, T: IntVec, Ys: CxVec, tap: CxVec, V: CxVec) -> CxCSC:
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
            yft_dsh = -Ys[k] / (-1j * np.conj(tap[k]))

            # Partials of Sf w.r.t. Ɵ shift (makes sense that this is ∂Sbus/∂Pxsh assigned to the "from" bus)
            Tx[nnz] = V[f] * np.conj(yft_dsh * V[t])
            Ti[nnz] = i_idx
            Tj[nnz] = k_idx
            nnz += 1

    # convert to csc
    mat.fill_from_coo(Ti, Tj, Tx, nnz)

    return mat


@njit()
def dSt_dtau_csc(nbr, st_indices, tau_indices, F: IntVec, T: IntVec, Ys: CxVec, tap: CxVec, V: CxVec) -> CxCSC:
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
            ytf_dsh = -Ys[k] / (1j * tap[k])

            # Partials of Sf w.r.t. Ɵ shift (makes sense that this is ∂Sbus/∂Pxsh assigned to the "from" bus)
            Tx[nnz] = V[t] * np.conj(ytf_dsh * V[f])
            Ti[nnz] = i_idx
            Tj[nnz] = k_idx
            nnz += 1

    # convert to csc
    mat.fill_from_coo(Ti, Tj, Tx, nnz)

    return mat


@njit()
def derivatives_ma_csc_numba(nbus, nbr, iXxma, F, T, Ys, kconv, tap, tap_module, Bc, Beq, V) -> Tuple[
    CxCSC, CxCSC, CxCSC]:
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


# original one
@njit()
def dSbus_dm_csc(nbus, bus_indices, m_indices, F: IntVec, T: IntVec, Ys: CxVec, Bc: Vec,
                 tap: CxVec, tap_module: Vec, V: CxVec) -> CxCSC:
    """

    :param nbus:
    :param bus_indices: bus indices involved
    :param m_indices: branch indices where m is controlled
    :param F: Array of branch "from" bus indices
    :param T: Array of branch "to" bus indices
    :param Ys: Array of branch series admittances
    :param Bc: Array of branch total susceptance values (sum of the two legs)
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
            YttB = Ys[k] + 1j * (Bc[k] / 2)
            dyff_dm = -2 * YttB / np.power(tap_module[k], 3)
            dyft_dm = Ys[k] / (tap_module[k] * np.conj(tap[k]))
            Tx[nnz] = V[f] * np.conj(dyff_dm * V[f] + dyft_dm * V[t])
            Ti[nnz] = f_idx
            Tj[nnz] = k_counter
            nnz += 1

        # to side
        if t_idx >= 0:
            dytf_dm = Ys[k] / (tap_module[k] * tap[k])
            Tx[nnz] = V[t] * np.conj(dytf_dm * V[f])
            Ti[nnz] = t_idx
            Tj[nnz] = k_counter
            nnz += 1

    # convert to csc
    mat.fill_from_coo(Ti, Tj, Tx, nnz)

    return mat


@njit()
def dSf_dm_csc(nbr, sf_indices, m_indices, F: IntVec, T: IntVec, Ys: CxVec, Bc: Vec,
               tap: CxVec, tap_module: Vec, V: CxVec) -> CxCSC:
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

            YttB = Ys[k] + 1j * (Bc[k] / 2.0)

            # Partials of Ytt, Yff, Yft and Ytf w.r.t.ma
            dyff_dma = -2 * YttB /  np.power(tap_module[k], 3)
            dyft_dma = Ys[k] / ( tap_module[k] * np.conj(tap[k]))

            # Partials of Sf w.r.t. Ɵ shift (makes sense that this is ∂Sbus/∂Pxsh assigned to the "from" bus)
            Tx[nnz] = V[f] * np.conj(dyff_dma * V[f] + dyft_dma * V[t])
            Ti[nnz] = i_idx
            Tj[nnz] = k_idx
            nnz += 1

    # convert to csc
    mat.fill_from_coo(Ti, Tj, Tx, nnz)

    return mat


@njit()
def dSt_dm_csc(nbr, st_indices, m_indices, F: IntVec, T: IntVec, Ys: CxVec,
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

            dytf_dma = Ys[k] / (tap_module[k] * tap[k])

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


@njit()
def dLossvsc_dVm_csc(nvsc, nbus, i_u_vm, alpha2, alpha3, Vm, Pt, Qt, T) -> CSC:
    """
        pq = Pt[ig_plossacdc] * Pt[ig_plossacdc] + Qt[ig_plossacdc] * Qt[ig_plossacdc]
        pq_sqrt = np.sqrt(pq)
        pq_sqrt += 1e-20
        dLacdc_dVm = (alpha2[vsc_order] * pq_sqrt * Qt[ig_plossacdc] / (Vm[T_acdc] * Vm[T_acdc])
                      + 2 * alpha3[vsc_order] * (pq) / (
                              Vm[T_acdc[vsc_order]] * Vm[T_acdc[vsc_order]] * Vm[T_acdc[vsc_order]]))
    """
    n_cols = len(i_u_vm)
    n_rows = nvsc
    max_nnz = nvsc
    mat = CSC(n_rows, n_cols, max_nnz, False)
    Tx = np.empty(max_nnz, dtype=np.float64)
    Ti = np.empty(max_nnz, dtype=np.int32)
    Tj = np.empty(max_nnz, dtype=np.int32)
    nnz = 0

    j_lookup = make_lookup(nbus, i_u_vm)

    for kidx in range(nvsc):
        t = T[kidx]

        if j_lookup[t] >= 0:

            Vm_t = Vm[t]
            pq = Pt[kidx] * Pt[kidx] + Qt[kidx] * Qt[kidx]
            pq_sqrt = np.sqrt(pq) + 1e-20

            Tx[nnz] = - (alpha2[kidx] * pq_sqrt / (Vm_t * Vm_t) + 2 * alpha3[kidx] * pq / (Vm_t * Vm_t * Vm_t))
            Ti[nnz] = kidx
            Tj[nnz] = j_lookup[t]
            nnz += 1

    # convert to csc
    mat.fill_from_coo(Ti, Tj, Tx, nnz)

    return mat


@njit()
def dLosshvdc_dVm_csc(nhvdc: int, nbus: int, i_u_vm: IntVec, Vm: Vec, Pf_hvdc: Vec,
                      hvdc_r: Vec, F_hvdc: IntVec):
    """
    dLosshvdc = rpu * Pf_hvdc / Vm[F_hvdc]**2 - Pf_hvdc - Pt_hvdc
    """
    n_cols = len(i_u_vm)
    n_rows = nhvdc
    max_nnz = nhvdc
    mat = CSC(n_rows, n_cols, max_nnz, False)
    Tx = np.empty(max_nnz, dtype=np.float64)
    Ti = np.empty(max_nnz, dtype=np.int32)
    Tj = np.empty(max_nnz, dtype=np.int32)
    nnz = 0

    j_lookup = make_lookup(nbus, i_u_vm)

    for kidx in range(nhvdc):
        f = F_hvdc[kidx]

        if j_lookup[f] >= 0:

            Vm_f = Vm[f]
            dLosshvdc_dVmf = - 2 * hvdc_r[kidx] * Pf_hvdc[kidx] / (Vm_f * Vm_f * Vm_f)

            Tx[nnz] = dLosshvdc_dVmf
            Ti[nnz] = kidx
            Tj[nnz] = j_lookup[f]
            nnz += 1

    # convert to csc
    mat.fill_from_coo(Ti, Tj, Tx, nnz)

    return mat


@njit()
def dLosshvdc_dPfhvdc_csc(nhvdc, Vm, hvdc_r, F_hvdc):
    """
    dLosshvdc = rpu * Pf_hvdc / Vm[F_hvdc]**2 - Pf_hvdc - Pt_hvdc
    """
    n_cols = nhvdc
    n_rows = nhvdc
    max_nnz = nhvdc
    mat = CSC(n_rows, n_cols, max_nnz, False)
    Tx = np.empty(max_nnz, dtype=np.float64)
    Ti = np.empty(max_nnz, dtype=np.int32)
    Tj = np.empty(max_nnz, dtype=np.int32)
    nnz = 0

    for kidx in range(nhvdc):
        f = F_hvdc[kidx]
        Vm_f =Vm[f]
        dLosshvdc_dPfhvdc = hvdc_r[kidx] / (Vm_f * Vm_f) - 1

        Tx[nnz] = dLosshvdc_dPfhvdc
        Ti[nnz] = kidx
        Tj[nnz] = kidx
        nnz += 1

    # convert to csc
    mat.fill_from_coo(Ti, Tj, Tx, nnz)

    return mat


@njit()
def dLosshvdc_dPthvdc_csc(nhvdc):
    """
    dLosshvdc = rpu * Pf_hvdc / Vm[F_hvdc]**2 - Pf_hvdc - Pt_hvdc
    """
    n_cols = nhvdc
    n_rows = nhvdc
    max_nnz = nhvdc
    mat = CSC(n_rows, n_cols, max_nnz, False)
    Tx = np.empty(max_nnz, dtype=np.float64)
    Ti = np.empty(max_nnz, dtype=np.int32)
    Tj = np.empty(max_nnz, dtype=np.int32)
    nnz = 0

    for kidx in range(nhvdc):

        dLosshvdc_dPthvdc = - 1

        Tx[nnz] = dLosshvdc_dPthvdc
        Ti[nnz] = kidx
        Tj[nnz] = kidx
        nnz += 1

    # convert to csc
    mat.fill_from_coo(Ti, Tj, Tx, nnz)

    return mat


@njit()
def dInjhvdc_dPfhvdc_csc(nhvdc):
    """
    dInjhvdc = Pf_hvdc - Pset - droop(Va[f] - Va[t])
    """
    n_cols = nhvdc
    n_rows = nhvdc
    max_nnz = nhvdc
    mat = CSC(n_rows, n_cols, max_nnz, False)
    Tx = np.empty(max_nnz, dtype=np.float64)
    Ti = np.empty(max_nnz, dtype=np.int32)
    Tj = np.empty(max_nnz, dtype=np.int32)
    nnz = 0

    for kidx in range(nhvdc):

        dInjhvdc_dPthvdc = + 1

        Tx[nnz] = dInjhvdc_dPthvdc
        Ti[nnz] = kidx
        Tj[nnz] = kidx
        nnz += 1

    # convert to csc
    mat.fill_from_coo(Ti, Tj, Tx, nnz)

    return mat


@njit()
def dLossvsc_dPfvsc_csc(nvsc, u_vsc_pf) -> CSC:
    """
    Compute dLossvsc_dPfvsc in CSC format with column indices aligned to u_vsc_pf.

    :param nvsc: Total number of rows in the matrix (number of VSCs).
    :param u_vsc_pf: Indices to define the column indices for the sparse matrix.
    :return: Sparse matrix in CSC format.
    """
    n_cols = len(u_vsc_pf)  # Number of columns (length of u_vsc_pf).
    n_rows = nvsc  # Number of rows (equal to nvsc).
    max_nnz = len(u_vsc_pf)  # Maximum number of non-zero entries.

    mat = CSC(n_rows, n_cols, max_nnz, False)
    Tx = np.empty(max_nnz, dtype=np.float64)
    Ti = np.empty(max_nnz, dtype=np.int32)
    Tj = np.empty(max_nnz, dtype=np.int32)

    nnz = 0  # Counter for non-zero entries

    for k, vsc in enumerate(u_vsc_pf):

        # Populate COO format arrays
        Tx[nnz] = -1.0
        Ti[nnz] = vsc  # Row index corresponds to the current VSC
        Tj[nnz] = k  # Column index aligns with u_vsc_pf
        nnz += 1

    # Convert to CSC
    mat.fill_from_coo(Ti, Tj, Tx, nnz)

    return mat


@njit()
def dLossvsc_dPtvsc_csc(nvsc, u_vsc_pt, alpha2, alpha3, Vm, Pt, Qt, T_vsc) -> CSC:
    """
    Compute the sparse matrix for the derivative of loss with respect to Pt in CSC format.

    :param nvsc: Number of VSCs (rows of the matrix).
    :param u_vsc_pt: Column indices for the sparse matrix.
    :param alpha2: Array of alpha2 coefficients.
    :param alpha3: Array of alpha3 coefficients.
    :param Vm: Voltage magnitudes at buses.
    :param Pt: Active power flows.
    :param Qt: Reactive power flows.
    :param T_vsc: Indices for VSC buses.
    :return: Sparse matrix in CSC format.
    """

    n_cols = len(u_vsc_pt)  # Number of columns (length of i_u_pt).
    n_rows = nvsc  # Number of rows (equal to nvsc).
    max_nnz = len(u_vsc_pt)  # Maximum number of non-zero entries.

    mat = CSC(n_rows, n_cols, max_nnz, False)
    Tx = np.empty(max_nnz, dtype=np.float64)
    Ti = np.empty(max_nnz, dtype=np.int32)
    Tj = np.empty(max_nnz, dtype=np.int32)

    nnz = 0  # Counter for non-zero entries

    for k, vsc in enumerate(u_vsc_pt):
        t = T_vsc[vsc]
        Vm_t = Vm[t]
        val = (alpha2[vsc] / Vm_t * 1 / np.sqrt(Pt[vsc] * Pt[vsc] + Qt[vsc] * Qt[vsc] + 1e-20) * Pt[vsc]
               + 2 * alpha3[vsc] * Pt[vsc] / (Vm_t * Vm_t) - 1)

        # Populate COO format arrays
        Tx[nnz] = val
        Ti[nnz] = vsc  # Row index corresponds to the current VSC
        Tj[nnz] = k  # Column index aligns with u_vsc_pf, should be equal to k
        nnz += 1

    # Convert to CSC
    mat.fill_from_coo(Ti, Tj, Tx, nnz)

    return mat


@njit()
def dLossvsc_dQtvsc_csc(nvsc, u_vsc_qt, alpha2, alpha3, Vm, Pt, Qt, T_vsc) -> CSC:
    """
    Compute the sparse matrix for the derivative of loss with respect to Qt in CSC format.

    :param nvsc: Number of VSCs (rows of the matrix).
    :param u_vsc_pt: Column indices for the sparse matrix.
    :param alpha2: Array of alpha2 coefficients.
    :param alpha3: Array of alpha3 coefficients.
    :param Vm: Voltage magnitudes at buses.
    :param Pt: Active power flows.
    :param Qt: Reactive power flows.
    :param T_vsc: Indices for VSC buses.
    :return: Sparse matrix in CSC format.
    """

    n_cols = len(u_vsc_qt)  # Number of columns (length of i_u_qt).
    n_rows = nvsc  # Number of rows (equal to nvsc).
    max_nnz = len(u_vsc_qt)  # Maximum number of non-zero entries.

    mat = CSC(n_rows, n_cols, max_nnz, False)
    Tx = np.empty(max_nnz, dtype=np.float64)
    Ti = np.empty(max_nnz, dtype=np.int32)
    Tj = np.empty(max_nnz, dtype=np.int32)

    nnz = 0  # Counter for non-zero entries

    for k, vsc in enumerate(u_vsc_qt):
        t = T_vsc[vsc]
        Vm_t = Vm[t]
        val = (alpha2[vsc] / Vm_t * 1 / np.sqrt(Pt[vsc] * Pt[vsc] + Qt[vsc] * Qt[vsc] + 1e-20) * Qt[vsc]
               + 2 * alpha3[vsc] * Qt[vsc] / (Vm_t * Vm_t))

        # Populate COO format arrays
        Tx[nnz] = val
        Ti[nnz] = vsc  # Row index corresponds to the current VSC
        Tj[nnz] = k  # Column index aligns with u_vsc_pf, should be equal to k
        nnz += 1

    # Convert to CSC
    mat.fill_from_coo(Ti, Tj, Tx, nnz)

    return mat

@njit()
def dIvsc_dPfpvsc_csc(nvsc, u_vsc_pfp, Vm, Fdcn_vsc) -> CSC:
    """
    Compute dIvsc_dPfpvsc in CSC format.
    :param nvsc: Number of VSCs (rows of the matrix).
    :param u_vsc_pfp: Column indices for the sparse matrix.
    :param Vm: Voltage magnitudes at buses.
    :param Fdcn_vsc: From negative bus indices for VSCs.
    :return: Sparse matrix in CSC format.
    """
    n_cols = len(u_vsc_pfp)  # Number of columns (length of i_u_pfp).
    n_rows = nvsc  # Number of rows (equal to nvsc).
    max_nnz = len(u_vsc_pfp)  # Maximum number of non-zero entries.

    mat = CSC(n_rows, n_cols, max_nnz, False)
    Tx = np.empty(max_nnz, dtype=np.float64)
    Ti = np.empty(max_nnz, dtype=np.int32)
    Tj = np.empty(max_nnz, dtype=np.int32)

    nnz = 0  # Counter for non-zero entries

    for k, vsc in enumerate(u_vsc_pfp):
        fn = Fdcn_vsc[vsc]
        val = Vm[fn]

        # Populate COO format arrays
        Tx[nnz] = val
        Ti[nnz] = vsc  # Row index corresponds to the current VSC
        Tj[nnz] = k  # Column index aligns with u_vsc_pfp, should be equal to k
        nnz += 1

    # Convert to CSC
    mat.fill_from_coo(Ti, Tj, Tx, nnz)

    return mat

@njit()
def dIvsc_dPfnvsc_csc(nvsc, u_vsc_pfn, Vm, Fdcp_vsc) -> CSC:
    """
    Compute dIvsc_dPfnvsc in CSC format.
    :param nvsc: Number of VSCs (rows of the matrix).
    :param u_vsc_pfn: Column indices for the sparse matrix.
    :param Vm: Voltage magnitudes at buses.
    :param Fdcp_vsc: From positive bus indices for VSCs.
    :return: Sparse matrix in CSC format.
    """
    n_cols = len(u_vsc_pfn)  # Number of columns (length of i_u_pfn).
    n_rows = nvsc  # Number of rows (equal to nvsc).
    max_nnz = len(u_vsc_pfn)  # Maximum number of non-zero entries.

    mat = CSC(n_rows, n_cols, max_nnz, False)
    Tx = np.empty(max_nnz, dtype=np.float64)
    Ti = np.empty(max_nnz, dtype=np.int32)
    Tj = np.empty(max_nnz, dtype=np.int32)

    nnz = 0  # Counter for non-zero entries

    for k, vsc in enumerate(u_vsc_pfn):
        fp = Fdcp_vsc[vsc]
        val = Vm[fp]

        # Populate COO format arrays
        Tx[nnz] = val
        Ti[nnz] = vsc  # Row index corresponds to the current VSC
        Tj[nnz] = k  # Column index aligns with u_vsc_pfn, should be equal to k
        nnz += 1

    # Convert to CSC
    mat.fill_from_coo(Ti, Tj, Tx, nnz)

    return mat


@njit()
def dIvsc_dVm_csc(nvsc, nbus, i_u_vm, Pfp_vsc, Pfn_vsc, Fdcp_vsc, Fdcn_vsc) -> CSC:
    """
    Compute dIvsc_dVm in CSC format.
    :param nvsc: Number of VSCs (rows of the matrix).
    :param nbus: Number of buses.
    :param i_u_vm: Column indices for the sparse matrix.
    :param Pfp_vsc: Active power flows from positive bus to VSC.
    :param Pfn_vsc: Active power flows from negative bus to VSC.
    :param Fdcp_vsc: From positive bus indices for VSCs.
    :param Fdcn_vsc: From negative bus indices for VSCs.
    :return: Sparse matrix in CSC format.
    """
    n_cols = len(i_u_vm)  # Number of columns (length of i_u_vm).
    n_rows = nvsc  # Number of rows (equal to nvsc).
    max_nnz = 2 * nvsc  # Maximum number of non-zero entries.

    mat = CSC(n_rows, n_cols, max_nnz, False)
    Tx = np.empty(max_nnz, dtype=np.float64)
    Ti = np.empty(max_nnz, dtype=np.int32)
    Tj = np.empty(max_nnz, dtype=np.int32)

    nnz = 0

    j_lookup = make_lookup(nbus, i_u_vm)

    for kidx in range(nvsc):
        fp = Fdcp_vsc[kidx]
        fn = Fdcn_vsc[kidx]

        if j_lookup[fp] >= 0:
            Tx[nnz] = Pfn_vsc[kidx]
            Ti[nnz] = kidx
            Tj[nnz] = j_lookup[fp]
            nnz += 1

        if j_lookup[fn] >= 0:
            Tx[nnz] = Pfp_vsc[kidx]
            Ti[nnz] = kidx
            Tj[nnz] = j_lookup[fn]
            nnz += 1

    # # convert to csc
    mat.fill_from_coo(Ti, Tj, Tx, nnz)

    return mat


@njit()
def dImaxvsc_dVm_csc(nbus, k_vsc_imax, i_u_vm, Pt_vsc, Qt_vsc, Vm, T_vsc) -> CSC:
    """
    Compute dImaxvsc_dVm in CSC format.
    The equation is: (P**2 + Q**2) / Vm**2 - Imax**2 = 0
    :param nbus: Number of buses.
    :param k_vsc_imax: VSC indices working at maximum current.
    :param i_u_vm: Column indices for the sparse matrix.
    :param Pt_vsc: Active power flow on the AC side of the VSC.
    :param Qt_vsc: Reactive power flow on the AC side of the VSC.
    :param Vm: Voltage magnitude
    :param T_vsc: Bus index pointing to the AC bus of the VSC.
    :return: Sparse matrix in CSC format.
    """
    n_cols = len(i_u_vm)  # Number of columns (length of i_u_vm).
    n_rows = len(k_vsc_imax)  # Number of rows (equal to nvsc).
    max_nnz = len(k_vsc_imax)  # Maximum number of non-zero entries.

    mat = CSC(n_rows, n_cols, max_nnz, False)
    Tx = np.empty(max_nnz, dtype=np.float64)
    Ti = np.empty(max_nnz, dtype=np.int32)
    Tj = np.empty(max_nnz, dtype=np.int32)

    nnz = 0

    j_lookup = make_lookup(nbus, i_u_vm)

    for i, kidx in enumerate(k_vsc_imax):
        t_ac = T_vsc[kidx]

        if j_lookup[t_ac] >= 0:  # If Vm is unknown
            Tx[nnz] = -2 * (Pt_vsc[kidx]**2 + Qt_vsc[kidx]**2) / Vm[t_ac]**3
            Ti[nnz] = i
            Tj[nnz] = j_lookup[t_ac]
            nnz += 1

    # convert to csc
    mat.fill_from_coo(Ti, Tj, Tx, nnz)

    return mat


@njit()
def dImaxvsc_dPQ_csc(nvsc, k_vsc_imax, u_vsc_pqt, PQt_vsc, Vm, T_vsc) -> CSC:
    """
    Compute dImaxvsc_dPQ in CSC format.
    The equation is: (P**2 + Q**2) / Vm**2 - Imax**2 = 0
    :param nvsc: Number of VSCs (rows of the matrix).
    :param k_vsc_imax: VSC indices working at maximum current.
    :param u_vsc_pqt: P or Q indices where the AC side power is unknonw.
    :param PQt_vsc: Active or reactive power flow on the AC side of the VSC.
    :param Vm: Voltage magnitude
    :param T_vsc: Bus index pointing to the AC bus of the VSC.
    :return: Sparse matrix in CSC format.
    """
    n_cols = len(u_vsc_pqt)  # Number of columns (length of i_u_vm).
    n_rows = len(k_vsc_imax)  # Number of rows (equal to nvsc).
    max_nnz = len(k_vsc_imax)  # Maximum number of non-zero entries.

    mat = CSC(n_rows, n_cols, max_nnz, False)
    Tx = np.empty(max_nnz, dtype=np.float64)
    Ti = np.empty(max_nnz, dtype=np.int32)
    Tj = np.empty(max_nnz, dtype=np.int32)

    nnz = 0

    j_lookup = make_lookup(nvsc, u_vsc_pqt)

    for i, kidx in enumerate(k_vsc_imax):
        t_ac = T_vsc[kidx]

        if j_lookup[kidx] >= 0:  # If P or Q is unknown
            Tx[nnz] = 2 * PQt_vsc[kidx] / Vm[t_ac]**2
            Ti[nnz] = i
            Tj[nnz] = j_lookup[kidx]
            nnz += 1

    # # convert to csc
    mat.fill_from_coo(Ti, Tj, Tx, nnz)

    return mat


@njit()
def dP_dPfvsc_csc(i_k_p, u_vsc_pf, F_vsc) -> CSC:
    """
    Compute dP_dPfvsc in CSC format.

    :param i_k_p: Indices for the rows corresponding to the power injections.
    :param u_vsc_pf: Column indices for the sparse matrix.
    :param F_vsc: From bus indices for VSCs.
    :return: Sparse matrix in CSC format.
    """
    n_cols = len(u_vsc_pf)  # Number of columns (length of u_vsc_pf).
    n_rows = len(i_k_p)  # Number of rows (equal to nbus).
    max_nnz = len(u_vsc_pf)  # Maximum number of non-zero entries.

    mat = CxCSC(n_rows, n_cols, max_nnz, False)
    Tx = np.empty(max_nnz, dtype=np.float64)
    Ti = np.empty(max_nnz, dtype=np.int32)
    Tj = np.empty(max_nnz, dtype=np.int32)

    j_lookup = make_lookup(len(i_k_p), i_k_p)
    # i_k_p_set = set(i_k_p)
    nnz = 0  # Counter for non-zero entries

    # my way below
    for vsc_idx, vsc in enumerate(u_vsc_pf):
        f_bus = F_vsc[vsc]

        if j_lookup[f_bus] >= 0:
        # if f_bus in i_k_p_set:
            Tx[nnz] = 1.0
            # Ti[nnz] = f_bus
            Ti[nnz] = j_lookup[f_bus]
            Tj[nnz] = vsc_idx
            nnz += 1

    # Convert to CSC
    mat.fill_from_coo(Ti, Tj, Tx, nnz)

    return mat.real


@njit()
def dPQ_dPQft_csc(nbus: int, nvsc: int, i_k_pq: IntVec, u_dev_pq: IntVec, FT_dev: IntVec) -> CSC:
    """
    Calculate the derivatives of the power balance with respect to injections of branches
    The method works for vscs and transformers without loss of generality

    :param i_k_pq: Indices for the rows corresponding to the power injections.
    :param u_dev_pq: Column indices for the sparse matrix.
    :param FT_dev: From or To bus indices.
    :return: Sparse matrix in CSC format.
    """
    n_cols = len(u_dev_pq)  # Number of columns (length of u_vsc_pf).
    n_rows = len(i_k_pq)  # Number of rows (equal to nbus).
    max_nnz = len(u_dev_pq)  # Maximum number of non-zero entries.

    mat = CSC(n_rows, n_cols, max_nnz, False)
    Tx = np.empty(max_nnz, dtype=np.float64)
    Ti = np.empty(max_nnz, dtype=np.int32)
    Tj = np.empty(max_nnz, dtype=np.int32)

    j_lookup = make_lookup(nbus, i_k_pq)
    vsc_lookup = make_lookup(nvsc, u_dev_pq)
    nnz = 0  # Counter for non-zero entries

    # my way below
    for dev_idx, dev in enumerate(u_dev_pq):
        f_bus = FT_dev[dev]

        # if j_lookup[f_bus] >= 0: # this is always evaluated to true
        Tx[nnz] = 1.0
        Ti[nnz] = j_lookup[f_bus]
        Tj[nnz] = vsc_lookup[dev]
        nnz += 1

    # Convert to CSC
    mat.fill_from_coo(Ti, Tj, Tx, nnz)

    return mat


@njit()
def dInj_dVa_csc(nhvdc, i_u_va, hvdc_pset, hvdc_r, hvdc_droop, V, F_hvdc, T_hvdc) -> CSC:
    """
    Compute dInj_dVa in CSC format for HVDC systems.

    :param nhvdc: Number of HVDC systems (rows of the matrix).
    :param i_u_va: Column indices for the sparse matrix (corresponding to voltage angles Va).
    :param hvdc_pset: HVDC power setpoints.
    :param hvdc_r: HVDC resistance values.
    :param hvdc_droop: HVDC droop coefficients.
    :param V: Voltage magnitudes at buses.
    :param F_hvdc: From-bus indices for HVDC.
    :param T_hvdc: To-bus indices for HVDC.
    :return: Sparse matrix in CSC format.
    """
    n_cols = len(i_u_va)  # Number of columns (length of i_u_va).
    n_rows = nhvdc  # Number of rows (equal to nhvdc).
    max_nnz = 2 * nhvdc  # Maximum number of non-zero entries (2 per HVDC system).

    mat = CxCSC(n_rows, n_cols, max_nnz, False)
    Tx = np.empty(max_nnz, dtype=np.complex128)
    Ti = np.empty(max_nnz, dtype=np.int32)
    Tj = np.empty(max_nnz, dtype=np.int32)

    nnz = 0  # Counter for non-zero entries

    for k in range(nhvdc):
        from_bus = F_hvdc[k]  # From-bus index
        to_bus = T_hvdc[k]  # To-bus index

        # Row index for this HVDC system
        row_idx = k

        # From-side derivative (positive hvdc_droop)
        Tx[nnz] = hvdc_droop[k]
        Ti[nnz] = row_idx
        Tj[nnz] = from_bus
        nnz += 1

        # To-side derivative (negative hvdc_droop)
        Tx[nnz] = -hvdc_droop[k]
        Ti[nnz] = row_idx
        Tj[nnz] = to_bus
        nnz += 1

    # Convert to CSC
    mat.fill_from_coo(Ti[:nnz], Tj[:nnz], Tx[:nnz], nnz)

    return mat.real


@njit()
def dInjhvdc_dVa_csc(nhvdc, nbus, i_u_va, hvdc_droop, F_hvdc, T_hvdc) -> CSC:
    """
    Compute dInjhvdc_dVa in CSC format for HVDC systems.

    :param nhvdc: Number of HVDC systems (rows of the matrix).
    :param nbus: Number of buses in the system.
    :param i_u_va: Column indices for the sparse matrix (corresponding to voltage angles Va).
    :param hvdc_droop_idx: Indices corresponding to HVDC droop control.
    :param hvdc_droop: HVDC droop coefficients.
    :param F_hvdc: From-bus indices for HVDC.
    :param T_hvdc: To-bus indices for HVDC.
    :return: Sparse matrix in CSC format.
    """

    n_cols = len(i_u_va)
    n_rows = nhvdc  # Number of rows (equal to nhvdc).
    max_nnz = 2 * nhvdc  # Maximum number of non-zero entries (two for HVDC, touches 2 buses)

    mat = CSC(n_rows, n_cols, max_nnz, False)
    Tx = np.empty(max_nnz, dtype=np.float64)
    Ti = np.empty(max_nnz, dtype=np.int32)
    Tj = np.empty(max_nnz, dtype=np.int32)

    j_lookup = make_lookup(nbus, i_u_va)
    nnz = 0  # Counter for non-zero entries

    for k in range(nhvdc):

        # Compute the derivative for the from-side
        dInjhvdc_dVaf = -hvdc_droop[k]
        dInjhvdc_dVat = +hvdc_droop[k] 

        # Populate COO format arrays
        Tx[nnz] = dInjhvdc_dVaf
        Ti[nnz] = k  # Row index corresponds to the current HVDC system
        Tj[nnz] = j_lookup[F_hvdc[k]]  # Column index corresponds to the from-bus
        nnz += 1

        Tx[nnz] = dInjhvdc_dVat
        Ti[nnz] = k  # Row index corresponds to the current HVDC system
        Tj[nnz] = j_lookup[T_hvdc[k]]  # Column index corresponds to the from-bus
        nnz += 1

    # Convert to CSC
    mat.fill_from_coo(Ti, Tj, Tx, nnz)

    return mat
