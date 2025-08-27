# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0


import numpy as np
import numba as nb
import scipy.sparse as sp
from typing import Union, Tuple, List
from VeraGridEngine.enumerations import WindingsConnection
from VeraGridEngine.basic_structures import ObjVec, Vec, CxVec, IntVec


def csc_equal(A: sp.csc_matrix,
              B: sp.csc_matrix,
              tol: float = 0.0) -> bool:
    """
    Return True iff two CSC matrices are equal
    (up-to a tolerance for floating–point data).

    Parameters
    ----------
    A, B : scipy.sparse.csc_matrix
        The matrices to compare.
    tol : float, optional
        Absolute tolerance.  If 0.0 an exact match is required
        otherwise the test is |A-B| > tol  element-wise.

    Notes
    -----
    * Both matrices are sorted first (`sort_indices`) so the
      result is independent of internal index ordering.
    * Works for any SciPy sparse subtype (CSR, COO …) after
      `.tocsc()`.
    """
    # 1. quick rejections
    if A.shape != B.shape or A.dtype != B.dtype:
        return False

    # 2. canonicalise index ordering
    A = A.copy()
    A.sort_indices()
    B = B.copy()
    B.sort_indices()

    # 3. exact or approximate test
    if tol == 0.0:
        return (A != B).nnz == 0  # :contentReference[oaicite:0]{index=0}
    else:
        return (abs(A - B) > tol).nnz == 0  # :contentReference[oaicite:1]{index=1}


@nb.njit(cache=True)
def _prepare_branch_maps(nbus: int, nbranch: int, F: IntVec, T: IntVec,
                         Yf_indices: IntVec, Yf_indptr: IntVec,
                         Ybus_indices: IntVec, Ybus_indptr: IntVec):
    """
    Build a map to the matrices to update (Ybus, Yf, Yt)

    Preconditions:
        * Yf / Yt were built with the 'row == branch index' pattern.
        * Yf and Yt share the same indices / indptr (as produced earlier).
        * Ybus contains exactly one entry per (row,col) pair.

    :param nbus: number of buses
    :param F: Array of from indices
    :param T: Array of to indices
    :param Yf_indices: CSC indices of Yf
    :param Yf_indptr: CSC index pointers of Yf
    :param Ybus_indices: CSC indices of Ybus
    :param Ybus_indptr: CSC index pointers of Ybus
    :return: pos_yff, pos_yft, pos_ytf, pos_ytt   (nbranch,) int32
             pos_b_ii, pos_b_ij, pos_b_ji, pos_b_jj  (nbranch,) int32
    """

    pos_yff = np.empty(nbranch, np.int32)
    pos_yft = np.empty(nbranch, np.int32)
    pos_ytf = np.empty(nbranch, np.int32)
    pos_ytt = np.empty(nbranch, np.int32)

    # ------- locate branch rows in Yf / Yt --------------------------
    for col in range(nbus):
        start = Yf_indptr[col]
        end = Yf_indptr[col + 1]
        for p in range(start, end):
            br = Yf_indices[p]  # row == branch
            if col == F[br]:
                pos_yff[br] = p  # Yf  (k,fbus)
                pos_ytf[br] = p  # Yt  (k,fbus)
            else:  # must be to-bus
                pos_yft[br] = p  # Yf  (k,tbus)
                pos_ytt[br] = p  # Yt  (k,tbus)

    # ------- build (row,col) → position map for Ybus ---------------
    # key = col*nbus + row  (fits in int64 for any realistic grid)
    pos_bus = dict()
    for col in range(nbus):
        start = Ybus_indptr[col]
        end = Ybus_indptr[col + 1]
        for p in range(start, end):
            row = Ybus_indices[p]
            pos_bus[col * nbus + row] = p

    pos_b_ii = np.empty(nbranch, np.int32)
    pos_b_ij = np.empty(nbranch, np.int32)
    pos_b_ji = np.empty(nbranch, np.int32)
    pos_b_jj = np.empty(nbranch, np.int32)

    for k in range(nbranch):
        i = F[k]
        j = T[k]
        pos_b_ii[k] = pos_bus[i * nbus + i]  # self @ from-bus
        pos_b_jj[k] = pos_bus[j * nbus + j]  # self @ to-bus
        pos_b_ij[k] = pos_bus[j * nbus + i]  # mutual j,i  (note: column = j)
        pos_b_ji[k] = pos_bus[i * nbus + j]  # mutual i,j

    return pos_yff, pos_yft, pos_ytf, pos_ytt, pos_b_ii, pos_b_ij, pos_b_ji, pos_b_jj


@nb.njit(cache=True)
def update_branch_admittances(idx: IntVec,
                              new_yff: CxVec, new_yft: CxVec, new_ytf: CxVec, new_ytt: CxVec,
                              Yf_data: CxVec, Yt_data: CxVec, Ybus_data: CxVec,
                              pos_yff: IntVec, pos_yft: IntVec, pos_ytf: IntVec, pos_ytt: IntVec,
                              pos_b_ii: IntVec, pos_b_ij: IntVec, pos_b_ji: IntVec, pos_b_jj: IntVec):
    """
    Update Yf, Yt, Ybus *in place*.  All arrays are pre-allocated.
    :param idx: branches you change
    :param new_yff:
    :param new_yft:
    :param new_ytf:
    :param new_ytt:
    :param Yf_data:
    :param Yt_data:
    :param Ybus_data:
    :param pos_yff:
    :param pos_yft:
    :param pos_ytf:
    :param pos_ytt:
    :param pos_b_ii:
    :param pos_b_ij:
    :param pos_b_ji:
    :param pos_b_jj:
    :return:
    """

    for k_idx, k in enumerate(idx):
        # ---- Yf ----------------------------------------------------
        p_ff = pos_yff[k]
        p_ft = pos_yft[k]
        d_ff = new_yff[k_idx] - Yf_data[p_ff]
        d_ft = new_yft[k_idx] - Yf_data[p_ft]
        Yf_data[p_ff] = new_yff[k_idx]
        Yf_data[p_ft] = new_yft[k_idx]

        # ---- Yt ----------------------------------------------------
        p_tf = pos_ytf[k]
        p_tt = pos_ytt[k]
        d_tf = new_ytf[k_idx] - Yt_data[p_tf]
        d_tt = new_ytt[k_idx] - Yt_data[p_tt]
        Yt_data[p_tf] = new_ytf[k_idx]
        Yt_data[p_tt] = new_ytt[k_idx]

        # ---- Ybus (add deltas) ------------------------------------
        Ybus_data[pos_b_ii[k]] += d_ff
        Ybus_data[pos_b_jj[k]] += d_tt
        Ybus_data[pos_b_ji[k]] += d_ff * 0  # placeholder if needed
        Ybus_data[pos_b_ji[k]] += d_tf
        Ybus_data[pos_b_ij[k]] += d_ft


class AdmittanceMatrices:
    """
    Class to store admittance matrices
    """

    def __init__(self,
                 Ybus: sp.csc_matrix,
                 Yf: sp.csc_matrix,
                 Yt: sp.csc_matrix,
                 Cf: sp.csc_matrix,
                 Ct: sp.csc_matrix,
                 yff: CxVec,
                 yft: CxVec,
                 ytf: CxVec,
                 ytt: CxVec,
                 Yshunt_bus: CxVec):
        """
        Constructor
        :param Ybus: Admittance matrix
        :param Yf: Admittance matrix of the branches with their "from" bus
        :param Yt: Admittance matrix of the branches with their "to" bus
        :param Cf: Connectivity matrix of the branches with their "from" bus
        :param Ct: Connectivity matrix of the branches with their "to" bus
        :param yff: admittance from-from primitives vector
        :param yft: admittance from-to primitives vector
        :param ytf: admittance to-from primitives vector
        :param ytt: admittance to-to primitives vector
        :param Yshunt_bus: array of shunt admittances per bus
        """
        self.Ybus = Ybus if Ybus.format == 'csc' else Ybus.tocsc()

        self.Yf = Yf if Yf.format == 'csc' else Yf.tocsc()

        self.Yt = Yt if Yt.format == 'csc' else Yt.tocsc()

        self.Cf = Cf if Cf.format == 'csc' else Cf.tocsc()

        self.Ct = Ct if Ct.format == 'csc' else Ct.tocsc()

        self.yff = yff

        self.yft = yft

        self.ytf = ytf

        self.ytt = ytt

        self.Yshunt_bus = Yshunt_bus

    def modify_taps_all(self,
                        m: Vec, m2: Vec,
                        tau: Vec, tau2: Vec) -> Tuple[sp.csc_matrix, sp.csc_matrix, sp.csc_matrix]:
        """
        Compute the new admittance matrix given the tap variation
        :param m: previous tap module (nbr)
        :param m2: new tap module (nbr)
        :param tau: previous tap angle (nbr)
        :param tau2: new tap angle (nbr)
        :return: Ybus, Yf, Yt
        """

        # update all primitives
        self.yff = (self.yff * (m * m) / (m2 * m2))
        self.yft = self.yft * (m * np.exp(-1.0j * tau)) / (m2 * np.exp(-1.0j * tau2))
        self.ytf = self.ytf * (m * np.exp(1.0j * tau)) / (m2 * np.exp(1.0j * tau2))
        self.ytt = self.ytt

        # update the matrices
        self.Yf = (sp.diags(self.yff) * self.Cf + sp.diags(self.yft) * self.Ct).tocsc()
        self.Yt = (sp.diags(self.ytf) * self.Cf + sp.diags(self.ytt) * self.Ct).tocsc()
        self.Ybus = (self.Cf.T * self.Yf + self.Ct.T * self.Yt + sp.diags(self.Yshunt_bus)).tocsc()

        return self.Ybus, self.Yf, self.Yt

    def modify_taps(self,
                    m_prev: Vec, m_new: Vec,
                    tau_prev: Vec, tau_new: Vec,
                    idx: IntVec) -> Tuple[sp.csc_matrix, sp.csc_matrix, sp.csc_matrix]:
        """
        Compute the new admittance matrix given the tap variation
        :param m_prev: previous tap module (length of idx)
        :param m_new: new tap module (length of idx)
        :param tau_prev: previous tap angle (length of idx)
        :param tau_new: new tap angle (length of idx)
        :param idx: branch indices that modify either m or tau. 
                    There has to be a single indices array because it is 
                    very hard to maintain indices that apply only to m, 
                    indices that apply only to tau and indices that apply to both
        :return: Ybus, Yf, Yt
        """

        # add arrays must have the same size as idx
        lidx = len(idx)
        assert len(m_prev) == lidx
        assert len(m_new) == lidx
        assert len(tau_prev) == lidx
        assert len(tau_new) == lidx

        # update primitives signaled by idx
        self.yff[idx] = (self.yff[idx] * (m_prev * m_prev) / (m_new * m_new))
        self.yft[idx] = self.yft[idx] * (m_prev * np.exp(-1.0j * tau_prev)) / (m_new * np.exp(-1.0j * tau_new))
        self.ytf[idx] = self.ytf[idx] * (m_prev * np.exp(1.0j * tau_prev)) / (m_new * np.exp(1.0j * tau_new))
        self.ytt[idx] = self.ytt[idx]

        # update the matrices
        self.Yf = (sp.diags(self.yff) * self.Cf + sp.diags(self.yft) * self.Ct).tocsc()
        self.Yt = (sp.diags(self.ytf) * self.Cf + sp.diags(self.ytt) * self.Ct).tocsc()
        self.Ybus = (self.Cf.T * self.Yf + self.Ct.T * self.Yt + sp.diags(self.Yshunt_bus)).tocsc()

        return self.Ybus, self.Yf, self.Yt

    def copy(self) -> "AdmittanceMatrices":
        """
        Get a deep copy
        """
        return AdmittanceMatrices(Ybus=self.Ybus.copy(),
                                  Yf=self.Yf.copy(),
                                  Yt=self.Yt.copy(),
                                  Cf=self.Cf.copy(),
                                  Ct=self.Ct.copy(),
                                  yff=self.yff.copy(),
                                  yft=self.yft.copy(),
                                  ytf=self.ytf.copy(),
                                  ytt=self.ytt.copy(),
                                  Yshunt_bus=self.Yshunt_bus.copy())

    def __eq__(self, other: "AdmittanceMatrices"):
        ok = True
        ok = ok and np.isclose(self.yff, other.yff).all()
        ok = ok and np.isclose(self.yft, other.yft).all()
        ok = ok and np.isclose(self.ytf, other.ytf).all()
        ok = ok and np.isclose(self.ytt, other.ytt).all()
        ok = ok and csc_equal(self.Ybus, other.Ybus, tol=1e-10)
        ok = ok and csc_equal(self.Yf, other.Yf, tol=1e-10)
        ok = ok and csc_equal(self.Yt, other.Yt, tol=1e-10)
        return ok


def compute_admittances(R: Vec,
                        X: Vec,
                        G: Vec,
                        B: Vec,
                        tap_module: Vec,
                        vtap_f: Vec,
                        vtap_t: Vec,
                        tap_angle: Vec,
                        Cf: sp.csc_matrix,
                        Ct: sp.csc_matrix,
                        Yshunt_bus: CxVec,
                        conn: Union[List[WindingsConnection], ObjVec],
                        seq: int,
                        add_windings_phase: bool = False) -> AdmittanceMatrices:
    """
    Compute the complete admittance matrices for the general power flow methods (Newton-Raphson based)

    :param R: array of branch resistance (p.u.)
    :param X: array of branch reactance (p.u.)
    :param G: array of branch conductance (p.u.)
    :param B: array of branch susceptance (p.u.)
    :param tap_module: array of tap modules (for all Branches, regardless of their type)
    :param vtap_f: array of virtual taps at the "from" side
    :param vtap_t: array of virtual taps at the "to" side
    :param tap_angle: array of tap angles (for all Branches, regardless of their type)
    :param Cf: Connectivity branch-bus "from" with the branch states computed
    :param Ct: Connectivity branch-bus "to" with the branch states computed
    :param Yshunt_bus: array of shunts equivalent power per bus, from the shunt devices (p.u.)
    :param seq: Sequence [0, 1, 2]
    :param conn: array of windings connections (numpy array of WindingsConnection)
    :param add_windings_phase: Add the phases of the transformer windings (for short circuits mainly)
    :return: Admittance instance
    """
    # form the admittance matrices
    ys = 1.0 / (R + 1.0j * (X + 1e-20))  # series admittance
    ysh_2 = (G + 1j * B) / 2.0  # shunt admittance

    # compose the primitives
    if add_windings_phase:

        r30_deg = np.exp(1.0j * np.pi / 6.0)

        if seq == 0:  # zero sequence
            # add always the shunt term, the series depends on the connection
            # one ys vector for the from side, another for the to side, and the shared one
            ysf = np.zeros(len(ys), dtype=complex)
            yst = np.zeros(len(ys), dtype=complex)
            ysft = np.zeros(len(ys), dtype=complex)

            for i, con in enumerate(conn):
                if con == WindingsConnection.GG:
                    ysf[i] = ys[i]
                    yst[i] = ys[i]
                    ysft[i] = ys[i]
                elif con == WindingsConnection.GD:
                    ysf[i] = ys[i]

            yff = (ysf + ysh_2) / (tap_module * tap_module * vtap_f * vtap_f)
            yft = -ysft / (tap_module * np.exp(-1.0j * tap_angle) * vtap_f * vtap_t)
            ytf = -ysft / (tap_module * np.exp(+1.0j * tap_angle) * vtap_t * vtap_f)
            ytt = (yst + ysh_2) / (vtap_t * vtap_t)

        elif seq == 2:  # negative sequence
            # only need to include the phase shift of +-30 degrees
            factor_psh = np.array([r30_deg if con == WindingsConnection.GD or con == WindingsConnection.SD else 1
                                   for con in conn])

            yff = (ys + ysh_2) / (tap_module * tap_module * vtap_f * vtap_f)
            yft = -ys / (tap_module * np.exp(+1.0j * tap_angle) * vtap_f * vtap_t) * np.conj(factor_psh)
            ytf = -ys / (tap_module * np.exp(-1.0j * tap_angle) * vtap_t * vtap_f) * factor_psh
            ytt = (ys + ysh_2) / (vtap_t * vtap_t)

        elif seq == 1:  # positive sequence

            # only need to include the phase shift of +-30 degrees
            factor_psh = np.array([r30_deg if con == WindingsConnection.GD or con == WindingsConnection.SD else 1.0
                                   for con in conn])

            yff = (ys + ysh_2) / (tap_module * tap_module * vtap_f * vtap_f)
            yft = -ys / (tap_module * np.exp(-1.0j * tap_angle) * vtap_f * vtap_t) * factor_psh
            ytf = -ys / (tap_module * np.exp(1.0j * tap_angle) * vtap_t * vtap_f) * np.conj(factor_psh)
            ytt = (ys + ysh_2) / (vtap_t * vtap_t)
        else:
            raise Exception('Unsupported sequence when computing the admittance matrix sequence={}'.format(seq))

    else:  # original

        yff = (ys + ysh_2) / (tap_module * tap_module * vtap_f * vtap_f)
        yft = -ys / (tap_module * np.exp(-1.0j * tap_angle) * vtap_f * vtap_t)
        ytf = -ys / (tap_module * np.exp(1.0j * tap_angle) * vtap_t * vtap_f)
        ytt = (ys + ysh_2) / (vtap_t * vtap_t)

    # compose the matrices
    Yf = sp.diags(yff) * Cf + sp.diags(yft) * Ct
    Yt = sp.diags(ytf) * Cf + sp.diags(ytt) * Ct
    Ybus = Cf.T * Yf + Ct.T * Yt + sp.diags(Yshunt_bus)

    return AdmittanceMatrices(Ybus.tocsc(), Yf.tocsc(), Yt.tocsc(), Cf.tocsc(), Ct.tocsc(),
                              yff, yft, ytf, ytt, Yshunt_bus)


@nb.njit(cache=True, inline="always")
def _sum_in_place(arr):
    """
    exclusive prefix-sum in-place
    :param arr: some array, it is modified in-place
    :return: total of arr
    """
    s = 0
    for i in range(arr.size):
        tmp = arr[i]
        arr[i] = s
        s += tmp
    return s


@nb.njit(cache=True)
def _build_Yf_Yt(nbus, nbr: int, F: IntVec, T: IntVec, yff: CxVec, yft: CxVec, ytf: CxVec, ytt: CxVec):
    """
    branch matrices (identical pattern ⇒ share indices/indptr)
    :param nbus:
    :param nbr:
    :param F:
    :param T:
    :param yff:
    :param yft:
    :param ytf:
    :param ytt:
    :return:
    """
    # 1. count nnz per column
    nnz_col = np.zeros(nbus, np.int64)
    for k in range(nbr):
        nnz_col[F[k]] += 1
        nnz_col[T[k]] += 1

    # 2. build indptr (length nb+1!)
    indptr = np.empty(nbus + 1, np.int64)
    indptr[0] = 0
    for j in range(nbus):
        indptr[j + 1] = indptr[j] + nnz_col[j]
    nnz = indptr[-1]

    # 3. allocate arrays
    indices = np.empty(nnz, np.int32)
    data_F = np.empty(nnz, np.complex128)
    data_T = np.empty(nnz, np.complex128)

    # 4. cursors that advance inside each column
    head = indptr[:-1].copy()  # length nb, one cursor per column

    for k in range(nbr):
        i = F[k]
        j = T[k]

        p = head[i]
        indices[p] = k
        data_F[p] = yff[k]
        data_T[p] = ytf[k]
        head[i] += 1

        p = head[j]
        indices[p] = k
        data_F[p] = yft[k]
        data_T[p] = ytt[k]
        head[j] += 1

    return data_F, data_T, indices, indptr  # <- length nb+1


@nb.njit(cache=True)
def _build_Ybus(nbus: int, nbr: int, F: IntVec, T: IntVec,
                yff: CxVec, yft: CxVec, ytf: CxVec, ytt: CxVec, Ysh: CxVec) -> Tuple[CxVec, IntVec, IntVec]:
    """
    Build Ybus
    :param nbus:
    :param nbr:
    :param F:
    :param T:
    :param yff:
    :param yft:
    :param ytf:
    :param ytt:
    :param Ysh:
    :return: (data, indices, indptr)
    """

    raw_nnz = 4 * nbr + nbus  # i-i, i-j, j-i, j-j + shunts

    rows_raw = np.empty(raw_nnz, np.int32)
    cols_raw = np.empty(raw_nnz, np.int32)
    data_raw = np.empty(raw_nnz, np.complex128)

    p = 0
    for k in range(nbr):
        i = F[k]
        j = T[k]

        # self admittances
        rows_raw[p] = i
        cols_raw[p] = i
        data_raw[p] = yff[k]
        p += 1

        rows_raw[p] = j
        cols_raw[p] = j
        data_raw[p] = ytt[k]
        p += 1

        # mutuals
        rows_raw[p] = i
        cols_raw[p] = j
        data_raw[p] = yft[k]
        p += 1

        rows_raw[p] = j
        cols_raw[p] = i
        data_raw[p] = ytf[k]
        p += 1

    # shunts
    for b in range(nbus):
        rows_raw[p] = b
        cols_raw[p] = b
        data_raw[p] = Ysh[b]
        p += 1

    # ---------- sort (col,row) ---------------------------------------
    key = cols_raw * nbus + rows_raw
    order = np.argsort(key)

    rows_s = rows_raw[order]
    cols_s = cols_raw[order]
    data_s = data_raw[order]

    # ---------- merge duplicates & count per column ------------------
    data = np.empty(raw_nnz, np.complex128)
    indices = np.empty(raw_nnz, np.int32)
    indptr = np.zeros(nbus + 1, np.int64)  # counts per column

    last_col = -1
    last_row = -1
    w = 0  # write cursor

    for idx in range(raw_nnz):
        r = rows_s[idx]
        c = cols_s[idx]
        v = data_s[idx]

        if c != last_col:  # new column
            last_col = c
            last_row = -1

        if r == last_row:  # same (c,r) → accumulate
            data[w - 1] += v
        else:  # new entry
            last_row = r
            data[w] = v
            indices[w] = r
            indptr[c] += 1
            w += 1

    # ---------- convert counts → pointers ----------------------------
    _sum_in_place(indptr)  # in-place prefix sum
    indptr[-1] = w  # set final nnz pointer

    # slice to size w
    data = data[:w]
    indices = indices[:w]

    return data, indices, indptr


class AdmittanceMatricesFast:
    """
    Class to store admittance matrices
    """

    def __init__(self,
                 Ybus: sp.csc_matrix,
                 Yf: sp.csc_matrix,
                 Yt: sp.csc_matrix,
                 F: IntVec,
                 T: IntVec,
                 ys: CxVec,
                 ysh2: CxVec,
                 vtap_f: Vec,
                 vtap_t: Vec,
                 yff: CxVec,
                 yft: CxVec,
                 ytf: CxVec,
                 ytt: CxVec,
                 Yshunt_bus: CxVec):
        """
        Constructor
        :param Ybus: Admittance matrix
        :param Yf: Admittance matrix of the branches with their "from" bus
        :param Yt: Admittance matrix of the branches with their "to" bus
        :param F: Branches array of "from" bus
        :param T: CBranches array of "to" bus
        :param ys: series admittance {ys = 1.0 / (R + 1.0j * (X + 1e-20))}
        :param ysh2: shunt admittance {ysh_2 = (G + 1j * B) / 2.0}
        :param vtap_f: array of from virtual taps
        :param vtap_t: array of to virtual taps
        :param yff: admittance from-from primitives vector
        :param yft: admittance from-to primitives vector
        :param ytf: admittance to-from primitives vector
        :param ytt: admittance to-to primitives vector
        :param Yshunt_bus: array of shunt admittances per bus
        """
        self.Ybus = Ybus if Ybus.format == 'csc' else Ybus.tocsc()
        self.Yf = Yf if Yf.format == 'csc' else Yf.tocsc()
        self.Yt = Yt if Yt.format == 'csc' else Yt.tocsc()

        self.F = F
        self.T = T

        self.ys = ys  # ys = 1.0 / (R + 1.0j * (X + 1e-20))  #
        self.ysh2 = ysh2  # ysh_2 = (G + 1j * B) / 2.0  # shunt admittance

        self.vtap_f = vtap_f
        self.vtap_t = vtap_t

        self.yff = yff
        self.yft = yft
        self.ytf = ytf
        self.ytt = ytt

        self.Yshunt_bus = Yshunt_bus

        self.pos_yff = np.zeros(0, dtype=int)
        self.pos_yft = np.zeros(0, dtype=int)
        self.pos_ytf = np.zeros(0, dtype=int)
        self.pos_ytt = np.zeros(0, dtype=int)
        self.pos_b_ii = np.zeros(0, dtype=int)
        self.pos_b_ij = np.zeros(0, dtype=int)
        self.pos_b_ji = np.zeros(0, dtype=int)
        self.pos_b_jj = np.zeros(0, dtype=int)

    def initialize_update(self):
        """
        Build the indices to later update the matrix easily
        :return:
        """
        (self.pos_yff,
         self.pos_yft,
         self.pos_ytf,
         self.pos_ytt,
         self.pos_b_ii,
         self.pos_b_ij,
         self.pos_b_ji,
         self.pos_b_jj) = _prepare_branch_maps(nbus=self.Ybus.shape[0],
                                               nbranch=len(self.F),
                                               F=self.F, T=self.T,
                                               Yf_indices=self.Yf.indices,
                                               Yf_indptr=self.Yf.indptr,
                                               Ybus_indices=self.Ybus.indices,
                                               Ybus_indptr=self.Ybus.indptr)

    def modify_taps_fast(self, idx, tap_module: Vec, tap_angle: Vec) -> None:
        """
        Modify in-place Ybus, Yf and Yt
        :param idx: indices of the branches to modify. Both the tap angle and module are updated for every index.
        :param tap_module: Tap modules of the positions given by idx
        :param tap_angle: Tap angles of the positions given by idx
        """
        if len(self.pos_yff) == 0 and self.yff != 0:
            self.initialize_update()  # your forgot to initialize...

        mf = self.vtap_f[idx]
        mt = self.vtap_t[idx]
        new_yff = (self.ys[idx] + self.ysh2[idx]) / (tap_module * tap_module * mf * mf)
        new_yft = -self.ys[idx] / (tap_module * np.exp(-1.0j * tap_angle) * mf * mt)
        new_ytf = -self.ys[idx] / (tap_module * np.exp(1.0j * tap_angle) * mt * mf)
        new_ytt = (self.ys[idx] + self.ysh2[idx]) / (mt * mt)

        # update the primitives
        self.yff[idx] = new_yff
        self.yft[idx] = new_yft
        self.ytf[idx] = new_ytf
        self.ytt[idx] = new_ytt

        # Update in-place
        update_branch_admittances(
            idx=idx,
            new_yff=new_yff,
            new_yft=new_yft,
            new_ytf=new_ytf,
            new_ytt=new_ytt,
            Yf_data=self.Yf.data,
            Yt_data=self.Yt.data,
            Ybus_data=self.Ybus.data,
            pos_yff=self.pos_yff,
            pos_yft=self.pos_yft,
            pos_ytf=self.pos_ytf,
            pos_ytt=self.pos_ytt,
            pos_b_ii=self.pos_b_ii,
            pos_b_ij=self.pos_b_ij,
            pos_b_ji=self.pos_b_ji,
            pos_b_jj=self.pos_b_jj
        )

    def copy(self) -> "AdmittanceMatricesFast":
        """
        Get a deep copy
        """
        res = AdmittanceMatricesFast(Ybus=self.Ybus.copy(),
                                     Yf=self.Yf.copy(),
                                     Yt=self.Yt.copy(),
                                     F=self.F.copy(),
                                     T=self.T.copy(),
                                     ys=self.ys.copy(),
                                     ysh2=self.ysh2.copy(),
                                     vtap_f=self.vtap_f.copy(),
                                     vtap_t=self.vtap_t.copy(),
                                     yff=self.yff.copy(),
                                     yft=self.yft.copy(),
                                     ytf=self.ytf.copy(),
                                     ytt=self.ytt.copy(),
                                     Yshunt_bus=self.Yshunt_bus.copy())
        res.pos_yff = self.pos_yff.copy()
        res.pos_yft = self.pos_yft.copy()
        res.pos_ytf = self.pos_ytf.copy()
        res.pos_ytt = self.pos_ytt.copy()
        res.pos_b_ii = self.pos_b_ii.copy()
        res.pos_b_ij = self.pos_b_ij.copy()
        res.pos_b_ji = self.pos_b_ji.copy()
        res.pos_b_jj = self.pos_b_jj.copy()
        return res

    def __eq__(self, other: "AdmittanceMatricesFast"):
        ok = True
        ok = ok and csc_equal(self.Ybus, other.Ybus, tol=1e-10)
        ok = ok and csc_equal(self.Yf, other.Yf, tol=1e-10)
        ok = ok and csc_equal(self.Yt, other.Yt, tol=1e-10)
        return ok


def compute_admittances_fast(nbus,
                             R: Vec,
                             X: Vec,
                             G: Vec,
                             B: Vec,
                             tap_module: Vec,
                             vtap_f: Vec,
                             vtap_t: Vec,
                             tap_angle: Vec,
                             Yshunt_bus: CxVec,
                             F: IntVec,
                             T: IntVec) -> AdmittanceMatricesFast:
    """
    Hardcore build of admittance matrices
    :param nbus: number of nodes
    :param R: array of branch resistance (p.u.)
    :param X: array of branch reactance (p.u.)
    :param G: array of branch conductance (p.u.)
    :param B: array of branch susceptance (p.u.)
    :param tap_module: array of tap modules (for all Branches, regardless of their type)
    :param vtap_f: array of virtual taps at the "from" side
    :param vtap_t: array of virtual taps at the "to" side
    :param tap_angle: array of tap angles (for all Branches, regardless of their type)
    :param Yshunt_bus: array of shunts equivalent power per bus, from the shunt devices (p.u.)
    :param F: Array of branch-from bus indices
    :param T: Array of branch-to bus indices
    :param Cf: Cf to pass along
    :param Ct: Ct to pass along
    :return: Yf, Yt, Ybus
    """

    ys = 1.0 / (R + 1.0j * (X + 1e-20))  # series admittance
    ysh_2 = (G + 1j * B) / 2.0  # shunt admittance
    yff = (ys + ysh_2) / (tap_module * tap_module * vtap_f * vtap_f)
    yft = -ys / (tap_module * np.exp(-1.0j * tap_angle) * vtap_f * vtap_t)
    ytf = -ys / (tap_module * np.exp(1.0j * tap_angle) * vtap_t * vtap_f)
    ytt = (ys + ysh_2) / (vtap_t * vtap_t)

    # ---------- branch matrices --------------------------------------
    nbr = len(F)
    data_F, data_T, idx_FT, ptr_FT = _build_Yf_Yt(nbus, nbr, F, T, yff, yft, ytf, ytt)

    Yf = sp.csc_matrix((data_F, idx_FT, ptr_FT), shape=(nbr, nbus))
    Yt = sp.csc_matrix((data_T, idx_FT, ptr_FT), shape=(nbr, nbus))

    # ---------- bus matrix -------------------------------------------
    data_B, idx_B, ptr_B = _build_Ybus(nbus, nbr, F, T, yff, yft, ytf, ytt, Yshunt_bus)
    Ybus = sp.csc_matrix((data_B, idx_B, ptr_B), shape=(nbus, nbus))

    return AdmittanceMatricesFast(Ybus=Ybus.tocsc(),
                                  Yf=Yf.tocsc(),
                                  Yt=Yt.tocsc(),
                                  F=F,
                                  T=T,
                                  ys=ys,
                                  ysh2=ysh_2,
                                  vtap_f=vtap_f,
                                  vtap_t=vtap_t,
                                  yff=yff,
                                  yft=yft,
                                  ytf=ytf,
                                  ytt=ytt,
                                  Yshunt_bus=Yshunt_bus)


class SeriesAdmittanceMatrices:
    """
    Admittance matrices for HELM and the AC linear methods
    """

    def __init__(self, Yseries: sp.csc_matrix, Yshunt: CxVec):
        self.Yseries = Yseries
        self.Yshunt = Yshunt


def compute_split_admittances(R: Vec,
                              X: Vec,
                              G: Vec,
                              B: Vec,
                              active: IntVec,
                              tap_module: Vec,
                              vtap_f: Vec,
                              vtap_t: Vec,
                              tap_angle: Vec,
                              Cf: sp.csc_matrix,
                              Ct: sp.csc_matrix,
                              Yshunt_bus: CxVec) -> SeriesAdmittanceMatrices:
    """
    Compute the complete admittance matrices for the helm method and others that may require them
    :param R: array of branch resistance (p.u.)
    :param X: array of branch reactance (p.u.)
    :param G: array of branch conductance (p.u.)
    :param B: array of branch susceptance (p.u.)
    :param active: array of active branches (bool)
    :param tap_module: array of tap modules (for all Branches, regardless of their type)
    :param vtap_f: array of virtual taps at the "from" side
    :param vtap_t: array of virtual taps at the "to" side
    :param tap_angle: array of tap angles (for all Branches, regardless of their type)
    :param Cf: Connectivity branch-bus "from" with the branch states computed
    :param Ct: Connectivity branch-bus "to" with the branch states computed
    :param Yshunt_bus: array of shunts equivalent power per bus (p.u.)
    :return: Yseries, Yshunt
    """

    ys = 1.0 / (R + 1.0j * X + 1e-20)  # series admittance
    ysh = (G + 1j * B) / 2  # shunt admittance

    # k is already filled with the appropriate value for each type of branch
    tap = tap_module * np.exp(1.0j * tap_angle)

    # compose the primitives
    yff = ys / (tap * np.conj(tap) * vtap_f * vtap_f)
    yft = - ys / (np.conj(tap) * vtap_f * vtap_t)
    ytf = - ys / (tap * vtap_t * vtap_f)
    ytt = ys / (vtap_t * vtap_t)

    yff *= active
    yft *= active
    ytf *= active
    ytt *= active

    # compose the matrices
    Yfs = sp.diags(yff) * Cf + sp.diags(yft) * Ct
    Yts = sp.diags(ytf) * Cf + sp.diags(ytt) * Ct
    Yseries = Cf.T * Yfs + Ct.T * Yts
    Yshunt = Cf.T * ysh + Ct.T * ysh + Yshunt_bus

    # GBc = G + 1.0j * B
    # Gsh = GBc / 2.0
    # Ysh = Yshunt_bus + Cf.T * Gsh + Ct.T * Gsh

    return SeriesAdmittanceMatrices(Yseries, Yshunt)


class FastDecoupledAdmittanceMatrices:
    """
    Admittance matrices for Fast decoupled method
    """

    def __init__(self, B1: sp.csc_matrix, B2: sp.csc_matrix):
        self.B1 = B1
        self.B2 = B2


def compute_fast_decoupled_admittances(X: Vec,
                                       B: Vec,
                                       tap_module: Vec,
                                       active: IntVec,
                                       vtap_f: Vec,
                                       vtap_t: Vec,
                                       Cf: sp.csc_matrix,
                                       Ct: sp.csc_matrix) -> FastDecoupledAdmittanceMatrices:
    """
    Compute the admittance matrices for the fast decoupled method
    :param X: array of branch reactance (p.u.)
    :param B: array of branch susceptance (p.u.)
    :param tap_module: array of tap modules (for all Branches, regardless of their type)
    :param active: array of active branches (bool)
    :param vtap_f: array of virtual taps at the "from" side
    :param vtap_t: array of virtual taps at the "to" side
    :param Cf: Connectivity branch-bus "from" with the branch states computed
    :param Ct: Connectivity branch-bus "to" with the branch states computed
    :return: B' and B''
    """

    b1 = active / (X + 1e-20)
    b1_tt = sp.diags(b1)
    B1f = b1_tt * Cf - b1_tt * Ct
    B1t = -b1_tt * Cf + b1_tt * Ct
    B1 = Cf.T * B1f + Ct.T * B1t

    b2 = b1 + B
    b2_ff = -(b2 / (tap_module * np.conj(tap_module)) * vtap_f * vtap_f).real
    b2_ft = -(b1 / (np.conj(tap_module) * vtap_f * vtap_t)).real
    b2_tf = -(b1 / (tap_module * vtap_t * vtap_f)).real
    b2_tt = - b2 / (vtap_t * vtap_t)

    B2f = -sp.diags(b2_ff) * Cf + sp.diags(b2_ft) * Ct
    B2t = sp.diags(b2_tf) * Cf - sp.diags(b2_tt) * Ct
    B2 = Cf.T * B2f + Ct.T * B2t

    return FastDecoupledAdmittanceMatrices(B1=B1.tocsc(), B2=B2.tocsc())


class LinearAdmittanceMatrices:
    """
    Admittance matrices for linear methods (DC power flow, PTDF, ...)
    """

    def __init__(self, Bbus: sp.csc_matrix, Bf: sp.csc_matrix, Gbus: sp.csc_matrix, Gf: sp.csc_matrix):
        self.Bbus = Bbus
        self.Bf = Bf
        self.Gbus = Gbus
        self.Gf = Gf

    def get_Bred(self, pqpv: IntVec) -> sp.csc_matrix:
        """
        Get Bred or Bpqpv for the PTDF and DC power flow
        :param pqpv: list of non-slack indices
        :return: B[pqpv, pqpv]
        """
        return self.Bbus[np.ix_(pqpv, pqpv)].tocsc()

    def get_Bslack(self, pqpv: IntVec, vd: IntVec) -> sp.csc_matrix:
        """
        Get Bslack for the PTDF and DC power flow
        :param pqpv: list of non-slack indices
        :param vd: list of slack ndices
        :return: B[pqpv, vd]
        """
        return self.Bbus[np.ix_(pqpv, vd)].tocsc()


def compute_linear_admittances(nbr: int,
                               X: Vec,
                               R: Vec,
                               m: Vec,
                               active: IntVec,
                               Cf: sp.csc_matrix,
                               Ct: sp.csc_matrix,
                               ac: IntVec,
                               dc: IntVec) -> LinearAdmittanceMatrices:
    """
    Compute the linear admittances for methods such as the "DC power flow" of the PTDF
    :param nbr: Number of Branches
    :param X: array of branch reactance (p.u.)
    :param R: array of branch resistance (p.u.)
    :param m: array of branch tap modules (p.u.)
    :param active: array of branch active (bool)
    :param Cf: Connectivity branch-bus "from" with the branch states computed
    :param Ct: Connectivity branch-bus "to" with the branch states computed
    :param ac: array of ac Branches indices
    :param dc: array of dc Branches indices
    :return: Bbus, Bf
    """
    b = 1.0 / (X * active * m + 1e-20)  # for ac Branches
    b_tt = sp.diags(b)  # This is Bd from the
    Bf = b_tt * Cf - b_tt * Ct
    Bt = -b_tt * Cf + b_tt * Ct
    Bbus = Cf.T * Bf + Ct.T * Bt

    g = 1.0 / (R * active + 1e-20)  # for dc Branches
    g_tt = sp.diags(g)  # This is Bd from the
    Gf = g_tt * Cf - g_tt * Ct
    Gt = -g_tt * Cf + g_tt * Ct
    Gbus = Cf.T * Gf + Ct.T * Gt

    """
    According to the KULeuven document "DC power flow in unit commitment models"
    The DC power flow is:
    
    Pbus = (A^T x Bd x A) x bus_angles + (Bd x A)^T x branch_angles
    
    Identifying the already computed matrices, it becomes:
    
    Pbus = Bbus x bus_angles + Btau x branch_angles
    
    If we solve for bus angles:
    
    bus_angles = Bbus^-1 x (Pbus - Btau x branch_angles)
    """

    return LinearAdmittanceMatrices(Bbus=Bbus, Bf=Bf, Gbus=Gbus, Gf=Gf)
