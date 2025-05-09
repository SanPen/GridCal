# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import warnings
import math
from typing import List
import numba as nb
from numba import types
from numba.experimental import jitclass
import numpy as np
from scipy.sparse import csc_matrix
from scipy.sparse.linalg._dsolve._superlu import gstrf, SuperLU
from GridCalEngine.basic_structures import IntVec, IntMat, Vec, CxVec


@jitclass([
    ('n_rows', nb.int32),
    ('n_cols', nb.int32),
    ('nnz', nb.int32),
    ('data', nb.float64[:]),
    ('indices', nb.int32[:]),
    ('indptr', nb.int32[:],),
    ('format', types.unicode_type)
])
class CSC:
    """
    numba CSC matrix struct
    """

    def __init__(self, n_rows: int, n_cols: int, nnz: int, force_zeros: bool):
        """
        Constructor
        :param n_rows:
        :param n_cols:
        :param nnz:
        :param force_zeros:
        """
        self.format = "csc"
        self.n_rows = n_rows  # n rows
        self.n_cols = n_cols  # n cols
        self.nnz = nnz

        if force_zeros:
            self.data = np.zeros(nnz, dtype=np.float64)
            self.indices = np.zeros(nnz, dtype=np.int32)
            self.indptr = np.zeros(n_cols + 1, dtype=np.int32)
        else:
            self.data = np.empty(nnz, dtype=np.float64)
            self.indices = np.empty(nnz, dtype=np.int32)
            self.indptr = np.empty(n_cols + 1, dtype=np.int32)

        self.indptr[0] = 0  # always

    def set(self, indices: IntVec, indptr: IntVec, data: Vec) -> "CSC":
        """
        Set the internal arrays
        :param indices:
        :param indptr:
        :param data:
        :return:
        """
        self.indices = indices
        self.indptr = indptr
        self.data = data
        self.nnz = len(self.data)
        self.indptr[0] = 0  # always
        return self

    def fill_from_coo(self, Ti: IntVec, Tj: IntVec, Tx: CxVec, nnz: int):
        """
        C = compressed-column form of a triplet matrix T.
        The columns of T are not sorted, and duplicate entries may be present in T.

        :param Ti: array of row indices (could be longer than nnz)
        :param Tj: array of column indices (could be longer than nnz)
        :param Tx: array of data (could be longer than nnz)
        :param nnz: number of non-zeros
        """
        self.nnz = nnz
        self.data = np.empty(self.nnz, dtype=np.float64)
        self.indices = np.empty(self.nnz, dtype=np.int32)
        self.indptr = np.empty(self.n_cols + 1, dtype=np.int32)
        self.indptr[0] = 0  # always

        w = np.zeros(self.n_cols, dtype=np.int32)  # get workspace

        for k in range(self.nnz):
            w[Tj[k]] += 1  # column counts

        csc_cumsum_i(self.indptr, w, self.n_cols)  # column pointers

        for k in range(self.nnz):
            p = w[Tj[k]]
            w[Tj[k]] += 1
            self.indices[p] = Ti[k]  # A(i,j) is the pth entry in C
            # if Cx is not None:
            self.data[p] = Tx[k]

    @property
    def shape(self):
        """
        Shape for scipy compatibility
        :return: n_rows, n_cols
        """
        return self.n_rows, self.n_cols

    def resize(self, nnz: np.int32):
        """
        Resize this matrix
        :param nnz: number of non-zeros
        """
        self.nnz = nnz
        self.data = self.data[:nnz]
        self.indices = self.indices[:nnz]  # np.resize is not suported by numba

    def todense(self):
        """
        Get dense array representation
        :return:
        """
        val = np.zeros((self.n_rows, self.n_cols), dtype=np.float64)

        for j in range(self.n_cols):
            for p in range(self.indptr[j], self.indptr[j + 1]):
                val[self.indices[p], j] = self.data[p]
        return val

    def toarray(self):
        """
        Get dense array representation
        :return:
        """
        return self.todense()

    def copy(self):
        """
        Create a copy of this matrix
        :return:
        """
        res = CSC(self.n_rows, self.n_cols, self.nnz, False)
        res.data = self.data.copy()
        res.indices = self.indices.copy()
        res.indptr = self.indptr.copy()
        return res

    def dot(self, x: np.ndarray):
        """
        Mat-vector multiplication
        :param x: vector
        :return:
        """
        return csc_matvec_ff(self, x)

    # @property
    # def T(self) -> "CSC":
    #     """
    #     Traspose
    #     :return:
    #     """
    #     return sp_transpose(self)

    def get_diag_max(self) -> float:
        """
        Get the maximum value of the diagonal
        :return: value
        """
        val = -1e20
        for j in range(self.n_cols):
            for p in range(self.indptr[j], self.indptr[j + 1]):
                if self.data[p] > val:
                    val = self.data[p]
        return val

    def add_val_to_diagonal(self, val: float) -> "CSC":
        """
        Add value to the diagonal in-place
        :param val: some value
        :return: copy with modified diagonal
        """
        A = self.copy()
        for j in range(A.n_cols):
            for p in range(A.indptr[j], A.indptr[j + 1]):
                if A.indices[p] == j:
                    A.data[p] += val
        return A

    def mul(self, B: "CSC") -> "CSC":
        """
        @ operator
        :param B: CSC matrix or ndarray
        :return: CSC matrix or ndarray
        """
        return csc_multiply_ff(self, B)

    def sum(self, B: "CSC") -> "CSC" | np.ndarray:
        """
        @ operator
        :param B: CSC matrix or ndarray
        :return: CSC matrix or ndarray
        """

        m = self.n_rows
        n = B.n_cols

        w = np.zeros(m, dtype=np.int32)

        x = np.zeros(n, dtype=np.float64)  # get workspace

        C = CSC(m, n, self.nnz + B.nnz, False)  # allocate result

        nz = 0

        for j in range(n):
            C.indptr[j] = nz  # column j of C starts here

            # nz = csc_scatter_f(self.indptr, self.indices, self.data, j, 1.0, w, x, j + 1, C.indices, nz)  # alpha*A(:,j)

            # nz = csc_scatter_f(B.indptr, B.indices, B.data, j, 1.0, w, x, j + 1, C.indices, nz)  # beta*B(:,j)

            mark = j + 1

            for p in range(self.indptr[j], self.indptr[j + 1]):
                i = self.indices[p]  # A(i,j) is nonzero
                if w[i] < mark:
                    w[i] = mark  # i is new entry in column j
                    C.indices[nz] = i  # add i to pattern of C(:,j)
                    nz = nz + 1
                    x[i] = self.data[p]  # x(i) = beta*A(i,j)
                else:
                    x[i] += self.data[p]  # i exists in C(:,j) already

            for p in range(B.indptr[j], B.indptr[j + 1]):
                i = B.indices[p]  # A(i,j) is nonzero
                if w[i] < mark:
                    w[i] = mark  # i is new entry in column j
                    C.indices[nz] = i  # add i to pattern of C(:,j)
                    nz = nz + 1
                    x[i] = B.data[p]  # x(i) = beta*A(i,j)
                else:
                    x[i] += B.data[p]  # i exists in C(:,j) already

            for p in range(C.indptr[j], nz):
                C.data[p] = x[C.indices[p]]

        C.indptr[n] = nz  # finalize the last column of C

        return C

    def add_scalar(self, val: float) -> "CSC":
        res = self.copy()
        res.data += val
        return res

    def prod_scalar(self, val: float) -> "CSC":
        res = self.copy()
        res.data *= val
        return res


@jitclass([
    ('n_rows', nb.int32),
    ('n_cols', nb.int32),
    ('nnz', nb.int32),
    ('data', nb.complex128[:]),
    ('indices', nb.int32[:]),
    ('indptr', nb.int32[:],),
    ('format', types.unicode_type)
])
class CxCSC:
    """
    numba CSC matrix struct
    """

    def __init__(self, n_rows: int, n_cols: int, nnz: int, force_zeros: bool):
        """
        Constructor
        :param n_rows:
        :param n_cols:
        :param nnz:
        :param force_zeros:
        """
        self.format = "csc"
        self.n_rows = n_rows  # n rows
        self.n_cols = n_cols  # n cols
        self.nnz = nnz

        if force_zeros:
            self.data = np.zeros(nnz, dtype=np.complex128)
            self.indices = np.zeros(nnz, dtype=np.int32)
            self.indptr = np.zeros(n_cols + 1, dtype=np.int32)
        else:
            self.data = np.empty(nnz, dtype=np.complex128)
            self.indices = np.empty(nnz, dtype=np.int32)
            self.indptr = np.empty(n_cols + 1, dtype=np.int32)

        self.indptr[0] = 0  # always

    def set(self, indices: IntVec, indptr: IntVec, data: CxVec) -> "CxCSC":
        """
        Set the internal arrays
        :param indices:
        :param indptr:
        :param data:
        :return:
        """
        self.indices = indices
        self.indptr = indptr
        self.data = data
        self.nnz = len(self.data)

        return self

    def fill_from_coo(self, Ti: IntVec, Tj: IntVec, Tx: CxVec, nnz: int):
        """
        C = compressed-column form of a triplet matrix T.
        The columns of T are not sorted, and duplicate entries may be present in T.

        :param Ti: array of row indices (could be longer than nnz)
        :param Tj: array of column indices (could be longer than nnz)
        :param Tx: array of data (could be longer than nnz)
        :param nnz: number of non-zeros
        """
        self.nnz = nnz
        self.data = np.empty(self.nnz, dtype=np.complex128)
        self.indices = np.empty(self.nnz, dtype=np.int32)
        self.indptr = np.empty(self.n_cols + 1, dtype=np.int32)
        self.indptr[0] = 0  # always

        w = np.zeros(self.n_cols, dtype=np.int32)  # get workspace

        for k in range(self.nnz):
            w[Tj[k]] += 1  # column counts

        # csc_cumsum_i(p, c, n)
        csc_cumsum_i(self.indptr, w, self.n_cols)  # column pointers
        # nz = 0
        # for i in range(self.n_cols):
        #     self.indptr[i] = nz
        #     nz += w[i]
        #     w[i] = self.indptr[i]  # also copy p[0..n-1] back into c[0..n-1]
        # self.indptr[self.n_cols] = nz

        for k in range(self.nnz):
            p = w[Tj[k]]
            w[Tj[k]] += 1
            self.indices[p] = Ti[k]  # A(i,j) is the pth entry in C
            # if Cx is not None:
            self.data[p] = Tx[k]

    @property
    def shape(self):
        """
        Shape for scipy compatibility
        :return: n_rows, n_cols
        """
        return self.n_rows, self.n_cols

    @property
    def real(self) -> CSC:
        """
        Get the real representation of this matrix
        :return: CSC
        """
        A = CSC(self.n_rows, self.n_cols, self.nnz, False)
        A.indptr = self.indptr
        A.indices = self.indices
        A.data = self.data.real
        return A

    @property
    def imag(self) -> CSC:
        """
        Get the imaginary representation of this matrix
        :return: CSC
        """
        A = CSC(self.n_rows, self.n_cols, self.nnz, False)
        A.indptr = self.indptr
        A.indices = self.indices
        A.data = self.data.imag
        return A

    def resize(self, nnz: nb.int32):
        """
        Resize this matrix
        :param nnz: number of non-zeros
        """
        self.nnz = nnz
        self.data = self.data[:nnz]
        self.indices = self.indices[:nnz]  # np.resize is not suported by numba

    def todense(self):
        """
        Get dense array representation
        :return:
        """
        val = np.zeros((self.n_rows, self.n_cols), dtype=np.complex128)

        for j in range(self.n_cols):
            for p in range(self.indptr[j], self.indptr[j + 1]):
                val[self.indices[p], j] = self.data[p]
        return val

    def toarray(self):
        """
        Get dense array representation
        :return:
        """
        return self.todense()

    def copy(self):
        """
        Create a copy of this matrix
        :return:
        """
        res = CSC(self.n_rows, self.n_cols, self.nnz, False)
        res.data = self.data.copy()
        res.indices = self.indices.copy()
        res.indptr = self.indptr.copy()
        return res

    def dot(self, x: np.ndarray) -> np.ndarray:
        """
        Mat-vector multiplication
        :param x: vector
        :return:
        """
        return csc_matvec_cx(self, x)

    def __matmul__(self, B: "CxCSC" | np.ndarray) -> "CxCSC" | np.ndarray:
        """

        :param B:
        :return:
        """
        if isinstance(B, CSC):
            return csc_multiply_cx(self, B)
        elif isinstance(B, np.ndarray):
            return csc_matvec_cx(self, B)
        else:
            raise TypeError

    def __add__(self, B: "CxCSC" | float) -> "CxCSC" | np.ndarray:
        """
        @ operator
        :param B: CSC matrix or ndarray
        :return: CSC matrix or ndarray
        """
        if isinstance(B, CxCSC):

            print(f"Adding CxCSC matrices: A.shape={self.shape}, B.shape={B.shape}")
            print(f"CxCSC Matrix Data Types: A.data={self.data.dtype}, B.data={B.data.dtype}")

            m = self.n_rows
            n = B.n_cols

            w = np.zeros(m, dtype=np.int32)

            x = np.zeros(n, dtype=np.complex128)  # get workspace

            C = CxCSC(m, n, self.nnz + B.nnz, False)  # allocate result

            nz = 0

            for j in range(n):
                C.indptr[j] = nz  # column j of C starts here

                # nz = csc_scatter_f(self.indptr, self.indices, self.data, j, 1.0, w, x, j + 1, C.indices, nz)  # alpha*A(:,j)

                # nz = csc_scatter_f(B.indptr, B.indices, B.data, j, 1.0, w, x, j + 1, C.indices, nz)  # beta*B(:,j)

                mark = j + 1

                for p in range(self.indptr[j], self.indptr[j + 1]):
                    i = self.indices[p]  # A(i,j) is nonzero
                    if w[i] < mark:
                        w[i] = mark  # i is new entry in column j
                        C.indices[nz] = i  # add i to pattern of C(:,j)
                        nz = nz + 1
                        x[i] = self.data[p]  # x(i) = beta*A(i,j)
                    else:
                        x[i] += self.data[p]  # i exists in C(:,j) already

                for p in range(B.indptr[j], B.indptr[j + 1]):
                    i = B.indices[p]  # A(i,j) is nonzero
                    if w[i] < mark:
                        w[i] = mark  # i is new entry in column j
                        C.indices[nz] = i  # add i to pattern of C(:,j)
                        nz = nz + 1
                        x[i] = B.data[p]  # x(i) = beta*A(i,j)
                    else:
                        x[i] += B.data[p]  # i exists in C(:,j) already

                for p in range(C.indptr[j], nz):
                    C.data[p] = x[C.indices[p]]

            C.indptr[n] = nz  # finalize the last column of C

            return C

        elif isinstance(B, float):
            res = self.copy()
            res.data += B
            return res
        else:
            raise TypeError

    def csc_matrix_matrix_addition(self, b: CxCSC) -> CxCSC:
        # Get the shape of the matrices
        m, n1 = self.shape
        n2, k = b.shape

        # Initialize the arrays that define the result matrix
        data = []
        indices = []
        indptr = [0]

        # Loop over the columns of the matrices
        for j in range(k):
            # Initialize a dictionary to store the non-zero elements of the j-th column of the result matrix
            col_dict = {}
            # Loop over the non-zero elements of the j-th column of the first matrix
            for ja in range(self.indptr[j], self.indptr[j + 1]):
                # Get the row index and value of the non-zero element
                ia = self.indices[ja]
                va = self.data[ja]
                # Add the non-zero element to the dictionary
                col_dict[ia] = va
            # Loop over the non-zero elements of the j-th column of the second matrix
            for jb in range(b.indptr[j], b.indptr[j + 1]):
                # Get the row index and value of the non-zero element
                ib = b.indices[jb]
                vb = b.data[jb]
                # Add the non-zero element to the dictionary
                if ib in col_dict:
                    col_dict[ib] += vb
                else:
                    col_dict[ib] = vb
            # Add the non-zero elements of the j-th column of the result matrix to the data and indices arrays
            for i, val in col_dict.items():
                data.append(val)
                indices.append(i)
            # Add the index of the next column to the indptr array of the result matrix
            indptr.append(len(data))

        # Create the CSC matrix from the data, indices, and indptr arrays of the result matrix
        data = np.array(data, dtype=np.complex128)
        indices = np.array(indices, dtype=np.int32)
        indptr = np.array(indptr, dtype=np.int32)

        my_mat = CxCSC(n_rows=m, n_cols=k, nnz=len(data), force_zeros=False)
        my_mat.set(indices, indptr, data)

        return my_mat


def mat_to_scipy(csc: CSC | CxCSC) -> csc_matrix:
    """
    CSC or CxCSC Matrix to Scipy
    :param csc:
    :return:
    """
    return csc_matrix((csc.data, csc.indices, csc.indptr), shape=(csc.n_rows, csc.n_cols))


def scipy_to_mat(mat: csc_matrix) -> CSC:
    """
    Scipy CSC matrix to CSC marix
    :param mat: Scipy CSC matrix
    :return: CSC marix
    """
    if not mat.format == 'csc':
        warnings.warn('scipy_to_cxmat: Converting matrix to CSC format...')
        mat = mat.tocsc()

    x = CSC(mat.shape[0], mat.shape[1], mat.nnz, False)
    x.data[:] = mat.data.astype(np.float64)
    x.indices[:] = mat.indices.astype(np.int32)
    x.indptr[:] = mat.indptr.astype(np.int32)
    return x


def scipy_to_cxmat(mat: csc_matrix) -> CxCSC:
    """
    Scipy CSC matrix to CxCSC marix
    :param mat: Scipy CSC matrix
    :return: CxCSC marix
    """
    if not mat.format == 'csc':
        warnings.warn('scipy_to_cxmat: Converting matrix to CSC format...')
        mat = mat.tocsc()

    x = CxCSC(mat.shape[0], mat.shape[1], mat.nnz, False)
    x.data = mat.data.astype(np.complex128)
    x.indices = mat.indices.astype(np.int32)
    x.indptr = mat.indptr.astype(np.int32)
    return x


def spfactor(A: CSC) -> None | SuperLU:
    """
    Sparse factorization with SuperLU
    :param A: CSC matrix
    :return: SuperLU factorization object
    """
    permc_spec = None
    diag_pivot_thresh = None
    relax = None
    panel_size = None
    _options = dict(DiagPivotThresh=diag_pivot_thresh,
                    ColPerm=permc_spec,
                    PanelSize=panel_size,
                    Relax=relax)

    if _options["ColPerm"] == "NATURAL":
        _options["SymmetricMode"] = True

    try:
        ret = gstrf(A.n_cols, A.nnz, A.data, A.indices, A.indptr,
                    ilu=False, options=_options, csc_construct_func=None)
        return ret
    except RuntimeError:
        return None


def spsolve_csc(A: CSC, x: Vec) -> Vec:
    """
    Sparse solution
    :param A: CSC matrix
    :param x: vector
    :return: solution
    """
    factor = spfactor(A)
    if factor is None:
        return np.full(len(x), np.nan), False
    else:
        return factor.solve(x), True


@nb.njit(cache=True)
def pack_4_by_4(A: CSC, B: CSC, C: CSC, D: CSC) -> CSC:
    """
    Stack 4 CSC matrices in a 2 by 2 structure
    stack csc sparse float matrices like this:
    | A | B |
    | C | D |
    :param A: Upper left matrix
    :param B: Upper right matrix
    :param C: Lower left matrix
    :param D: Lower right matrix
    :return: Stitched matrix
    """

    # check dimensional compatibility
    assert A.n_rows == B.n_rows
    assert C.n_rows == D.n_rows
    assert A.n_cols == C.n_cols
    assert B.n_cols == D.n_cols

    res = CSC(A.n_rows + C.n_rows,
              A.n_cols + B.n_cols,
              A.nnz + B.nnz + C.nnz + D.nnz, False)

    cnt = 0
    res.indptr[0] = 0
    for j in range(A.n_cols):  # for every column, same as range(cols + 1) For A and C
        for k in range(A.indptr[j], A.indptr[j + 1]):  # for every entry in the column from A
            res.indices[cnt] = A.indices[k]  # row index
            res.data[cnt] = A.data[k]
            cnt += 1

        for k in range(C.indptr[j], C.indptr[j + 1]):  # for every entry in the column from C
            res.indices[cnt] = C.indices[k] + A.n_rows  # row index
            res.data[cnt] = C.data[k]
            cnt += 1

        res.indptr[j + 1] = cnt

    for j in range(B.n_cols):  # for every column, same as range(cols + 1) For B and D
        for k in range(B.indptr[j], B.indptr[j + 1]):  # for every entry in the column from B
            res.indices[cnt] = B.indices[k]  # row index
            res.data[cnt] = B.data[k]
            cnt += 1

        for k in range(D.indptr[j], D.indptr[j + 1]):  # for every entry in the column from D
            res.indices[cnt] = D.indices[k] + B.n_rows  # row index
            res.data[cnt] = D.data[k]
            cnt += 1

        res.indptr[A.n_cols + j + 1] = cnt

    return res


@nb.njit(cache=True)
def pack_3_by_4(A: CSC, B: CSC, C: CSC) -> CSC:
    """
    Stack 3 CSC matrices in a 2 by 2 structure
    stack csc sparse float matrices like this:
    | A | B |
    | C | 0 |
    :param A: Upper left matrix
    :param B: Upper right matrix
    :param C: Lower left matrix
    :return: Stitched matrix
    """

    # check dimensional compatibility
    assert A.n_rows == B.n_rows
    assert A.n_cols == C.n_cols

    res = CSC(A.n_rows + C.n_rows,
              A.n_cols + B.n_cols,
              A.nnz + B.nnz + C.nnz, False)

    cnt = 0
    res.indptr[0] = 0
    for j in range(A.n_cols):  # for every column, same as range(cols + 1) For A and C
        for k in range(A.indptr[j], A.indptr[j + 1]):  # for every entry in the column from A
            res.indices[cnt] = A.indices[k]  # row index
            res.data[cnt] = A.data[k]
            cnt += 1

        for k in range(C.indptr[j], C.indptr[j + 1]):  # for every entry in the column from C
            res.indices[cnt] = C.indices[k] + A.n_rows  # row index
            res.data[cnt] = C.data[k]
            cnt += 1

        res.indptr[j + 1] = cnt

    for j in range(B.n_cols):  # for every column, same as range(cols + 1) For B and D
        for k in range(B.indptr[j], B.indptr[j + 1]):  # for every entry in the column from B
            res.indices[cnt] = B.indices[k]  # row index
            res.data[cnt] = B.data[k]
            cnt += 1

        res.indptr[A.n_cols + j + 1] = cnt

    return res


@nb.njit(cache=True)
def csc_cumsum_i(p, c, n):
    """
    p [0..n] = cumulative sum of c [0..n-1], and then copy p [0..n-1] into c

    @param p: size n+1, cumulative sum of c
    @param c: size n, overwritten with p [0..n-1] on output
    @param n: length of c
    @return: sum (c), null on error
    """
    nz = 0
    nz2 = 0.0

    for i in range(n):
        p[i] = nz
        nz += c[i]
        nz2 += c[i]  # also in double to avoid CS_INT overflow
        c[i] = p[i]  # also copy p[0..n-1] back into c[0..n-1]
    p[n] = nz
    return int(nz2)  # return sum (c [0..n-1])


@nb.njit(cache=True)
def sp_transpose(A: CSC) -> CSC:
    """
    Actual CSC transpose unlike scipy's
    :param A: CSC matrix
    :return: CSC transposed matrix
    """
    C = CSC(A.n_cols, A.n_rows, A.nnz, False)

    w = np.zeros(A.n_rows, dtype=np.int32)

    for p in range(A.indptr[A.n_cols]):
        w[A.indices[p]] += 1  # row counts

    csc_cumsum_i(C.indptr, w, A.n_rows)  # row pointers

    for j in range(A.n_cols):
        for p in range(A.indptr[j], A.indptr[j + 1]):
            q = w[A.indices[p]]
            w[A.indices[p]] += 1
            C.indices[q] = j  # place A(i,j) as entry C(j,i)
            C.data[q] = A.data[p]

    return C


@nb.njit(cache=True)
def sp_slice_cols(A: CSC, cols: IntMat) -> CSC:
    """
    Slice columns
    :param A: Matrix to slice
    :param cols: vector of columns
    :return: New sliced matrix
    """
    # pass1: determine the number of non-zeros
    nnz = 0
    for j in cols:
        for k in range(A.indptr[j], A.indptr[j + 1]):
            nnz += 1

    # pass2: size the vector and perform the slicing
    ncols = len(cols)

    res = CSC(A.n_rows, ncols, nnz, False)
    n = 0
    p = 0
    res.indptr[p] = 0

    for j in cols:
        for k in range(A.indptr[j], A.indptr[j + 1]):
            res.data[n] = A.data[k]
            res.indices[n] = A.indices[k]
            n += 1

        p += 1
        res.indptr[p] = n

    return res


@nb.njit(cache=True)
def sp_slice_rows(mat: CSC, rows: np.ndarray) -> CSC:
    """
    Slice rows
    :param mat:
    :param rows:
    :return: CSC matrix
    """
    B = sp_transpose(mat)
    A = sp_slice_cols(B, rows)
    return sp_transpose(A)


@nb.njit()
def sp_slice(A: CSC, rows: IntVec, cols: IntVec):
    """
    /*
     * This function performs the trivial slicing of the CSC sparse matrix A
     *
     * Steps:
     *  - Slice the columns with "sp_submat_c(A, cols)"
     *  - convert to CSR with .t() {transpose}
     *  - Slice the rows with sp_submat_c(B, rows), because it is a CSR now
     *  - Convert the result back to CSC with the final .t()
     * */
    :param A:
    :param rows:
    :param cols:
    :return:
    """
    n_rows = len(rows)
    n_cols = len(cols)

    nnz = 0
    p = 0
    B = CSC(n_rows, n_cols, A.nnz, False)
    B.indptr[p] = 0

    # generate lookup for the non-immediate axis (for CSC it is the rows) -> index lookup
    lookup = np.zeros(A.n_rows, dtype=np.int32)
    lookup[rows] = np.arange(n_rows, dtype=np.int32)

    for j in cols:  # sliced columns

        for k in range(A.indptr[j], A.indptr[j + 1]):  # rows of A[:, j]

            # row index translation to the "rows" space
            i = A.indices[k]
            ii = lookup[i]

            if rows[ii] == i:
                # entry found
                B.data[nnz] = A.data[k]
                B.indices[nnz] = ii
                nnz += 1

        p += 1
        B.indptr[p] = nnz

    B.indptr[p] = nnz
    B.resize(nnz)
    return B


@nb.njit()
def csc_stack_2d_ff(mats: List[CSC], n_rows: int = 1, n_cols: int = 1) -> CSC:
    """
    Assemble matrix from a list of matrices representing a "super matrix"

    |mat11 | mat12 | mat13 |
    |mat21 | mat22 | mat23 |

    turns into:

    [mat11, mat12, mat13, mat21, mat22, mat23]
    m_rows = 2
    m_cols = 3

    :param mats: list of CSC matrices arranged in row-major order (i.e. [mat11, mat12, mat13, mat21, mat22, mat23]
    :param n_rows: number of rows of the mats structure
    :param n_cols: number of cols of the mats structure
    :return: Final assembled matrix in CSC format
    """

    # pass 1: compute the number of non zero
    nnz = 0
    nrows = 0
    ncols = 0
    for r in range(n_rows):
        nrows += mats[r * n_cols].n_rows  # equivalent to mats[r, 0]
        for c in range(n_cols):
            col = mats[c + r * n_cols].n_cols  # equivalent to mats[r, c]
            nnz += mats[c + r * n_cols].nnz
            if r == 0:
                ncols += col

    # pass 2: fill in the data
    res = CSC(nrows, ncols, nnz, False)
    cnt = 0
    res.indptr[0] = 0
    offset_col = 0
    for c in range(n_cols):  # for each column of the array of matrices

        # number of columns
        n = mats[c].n_cols  # equivalent to mats[0, c]

        if n > 0:
            for j in range(n):  # for every column of the column of matrices

                offset_row = 0

                for r in range(n_rows):  # for each row of the array of rows

                    # get the current sub-matrix
                    A: CSC = mats[r * n_cols + c]  # equivalent to mats[r, c]

                    if A.n_rows > 0 and A.nnz > 0:

                        for k in range(A.indptr[j], A.indptr[j + 1]):  # for every entry in the column from A
                            res.indices[cnt] = A.indices[k] + offset_row  # row index
                            res.data[cnt] = A.data[k]
                            cnt += 1

                    offset_row += A.n_rows

                res.indptr[offset_col + j + 1] = cnt
            offset_col += n

    return res


@nb.njit(cache=True)
def diags(array: Vec) -> CSC:
    """
    Get diagonal sparse matrix from array
    :param array:
    :return:
    """
    m = len(array)
    res = CSC(m, m, m, False)

    for i in range(m):
        res.indptr[i] = i
        res.indices[i] = i
        res.data[i] = array[i]

    res.indptr[m] = m

    return res


@nb.njit(cache=True)
def diagc(m: int, value: float = 1.0) -> CSC:
    """
    Get diagonal sparse matrix from value
    :param m: size of the matrix
    :param value: value to set
    :return: CSC matrix
    """
    res = CSC(m, m, m, False)

    for i in range(m):
        res.indptr[i] = i
        res.indices[i] = i
        res.data[i] = value

    res.indptr[m] = m

    return res


@nb.njit(cache=False)
def extend(A: CSC, last_col: Vec, last_row: Vec, corner_val: float) -> CSC:
    """
    B = |   A       last_col |
        | last_row  val      |

    :param A: Original matrix
    :param last_col: last column to be added to A
    :param last_row: last row to be added to A | last_col
    :param corner_val: The botton-right corner value
    :return: Extended matrix
    """
    assert A.n_rows == len(last_col)
    assert A.n_cols == len(last_row)

    B = CSC(A.n_rows + 1,
            A.n_cols + 1,
            A.nnz + len(last_col) + len(last_row) + 1,
            False)

    nnz = 0
    p = 0
    B.indptr[p] = 0

    # Copy A
    for j in range(A.n_cols):  # columns

        for k in range(A.indptr[j], A.indptr[j + 1]):  # rows of A[:, j]

            # row index translation to the "rows" space
            i = A.indices[k]

            B.data[nnz] = A.data[k]
            B.indices[nnz] = i
            nnz += 1

        # add the last row value for this column
        if last_row[j] != 0:
            B.data[nnz] = last_row[j]
            B.indices[nnz] = A.n_rows
            nnz += 1

        p += 1
        B.indptr[p] = nnz

    # add the last column
    for i in range(A.n_rows):  # rows of A[:, j]
        if last_col[i] != 0.0:
            B.data[nnz] = last_col[i]
            B.indices[nnz] = i
            nnz += 1

    # add the corner value
    if corner_val != 0.0:
        B.data[nnz] = corner_val
        B.indices[nnz] = A.n_rows
        nnz += 1

    p += 1
    B.indptr[p] = nnz

    B.indptr[p] = nnz
    B.resize(nnz)

    return B


@nb.njit(cache=True)
def csc_multiply_ff(A: CSC, B: CSC) -> CSC:
    """
    Sparse matrix multiplication, C = A*B where A and B are CSC sparse matrices
    :param A:
    :param B:
    :return:
    """
    assert A.n_cols == B.n_rows
    nz = 0
    anz = A.indptr[A.n_cols]
    bnz = B.indptr[B.n_cols]
    Cm = A.n_rows
    Cn = B.n_cols

    w = np.zeros(Cn, dtype=np.int32)  # ialloc(m)  # get workspace
    x = np.empty(Cn, dtype=np.float64)  # xalloc(m)  # get workspace

    # allocate result

    Cnzmax = int(np.sqrt(Cm)) * anz + bnz  # the trick here is to allocate just enough memory to avoid reallocating
    Cp = np.empty(Cn + 1, dtype=np.int32)
    Ci = np.empty(Cnzmax, dtype=np.int32)
    Cx = np.empty(Cnzmax, dtype=np.float64)

    for j in range(Cn):

        # claim more space
        if nz + Cm > Cnzmax:
            # Ci, Cx, Cnzmax = csc_sprealloc_f(Cn, Cp, Ci, Cx, 2 * Cnzmax + m)
            # print('Re-Allocating')
            Cnzmax = 2 * Cnzmax + Cm
            if Cnzmax <= 0:
                Cnzmax = Cp[A.n_cols]

            length = min(Cnzmax, len(Ci))
            Cinew = np.empty(Cnzmax, dtype=np.int32)
            for i in range(length):
                Cinew[i] = Ci[i]
            Ci = Cinew

            length = min(Cnzmax, len(Cx))
            Cxnew = np.empty(Cnzmax, dtype=np.float64)
            for i in range(length):
                Cxnew[i] = Cx[i]
            Cx = Cxnew

        # column j of C starts here
        Cp[j] = nz

        # perform the multiplication
        for pb in range(B.indptr[j], B.indptr[j + 1]):
            for pa in range(A.indptr[B.indices[pb]], A.indptr[B.indices[pb] + 1]):
                ia = A.indices[pa]
                if w[ia] < j + 1:
                    w[ia] = j + 1
                    Ci[nz] = ia
                    nz += 1
                    x[ia] = B.data[pb] * A.data[pa]
                else:
                    x[ia] += B.data[pb] * A.data[pa]

        for pc in range(Cp[j], nz):
            Cx[pc] = x[Ci[pc]]

    Cp[Cn] = nz  # finalize the last column of C

    # cut the arrays to their nominal size nnz
    # Ci, Cx, Cnzmax = csc_sprealloc_f(Cn, Cp, Ci, Cx, 0)
    Cnzmax = Cp[Cn]
    C = CSC(Cm, Cn, Cnzmax, False)
    C.indptr = Cp
    C.indices = Ci[:Cnzmax]
    C.data = Cx[:Cnzmax]

    return C


@nb.njit(cache=True)
def csc_multiply_ff2(Am, An, Ap, Ai, Ax,
                     Bm, Bn, Bp, Bi, Bx):
    """
    Sparse matrix multiplication, C = A*B where A and B are CSC sparse matrices
    :param Am: number of rows in A
    :param An: number of columns in A
    :param Ap: column pointers of A
    :param Ai: indices of A
    :param Ax: data of A
    :param Bm: number of rows in B
    :param Bn: number of columns in B
    :param Bp: column pointers of B
    :param Bi: indices of B
    :param Bx: data of B
    :return: Cm, Cn, Cp, Ci, Cx, Cnzmax
    """
    assert An == Bm
    nz = 0
    anz = Ap[An]
    bnz = Bp[Bn]
    Cm = Am
    Cn = Bn

    w = np.zeros(Cn, dtype=np.int32)  # ialloc(m)  # get workspace
    x = np.empty(Cn, dtype=np.float64)  # xalloc(m)  # get workspace

    # allocate result

    Cnzmax = int(np.sqrt(Cm)) * anz + bnz  # the trick here is to allocate just enough memory to avoid reallocating
    Cp = np.empty(Cn + 1, dtype=np.int32)
    Ci = np.empty(Cnzmax, dtype=np.int32)
    Cx = np.empty(Cnzmax, dtype=np.float64)

    for j in range(Cn):

        # claim more space
        if nz + Cm > Cnzmax:
            # Ci, Cx, Cnzmax = csc_sprealloc_f(Cn, Cp, Ci, Cx, 2 * Cnzmax + m)
            print('Re-Allocating')
            Cnzmax = 2 * Cnzmax + Cm
            if Cnzmax <= 0:
                Cnzmax = Cp[An]

            length = min(Cnzmax, len(Ci))
            Cinew = np.empty(Cnzmax, dtype=np.int32)
            for i in range(length):
                Cinew[i] = Ci[i]
            Ci = Cinew

            length = min(Cnzmax, len(Cx))
            Cxnew = np.empty(Cnzmax, dtype=np.float64)
            for i in range(length):
                Cxnew[i] = Cx[i]
            Cx = Cxnew

        # column j of C starts here
        Cp[j] = nz

        # perform the multiplication
        for pb in range(Bp[j], Bp[j + 1]):
            for pa in range(Ap[Bi[pb]], Ap[Bi[pb] + 1]):
                ia = Ai[pa]
                if w[ia] < j + 1:
                    w[ia] = j + 1
                    Ci[nz] = ia
                    nz += 1
                    x[ia] = Bx[pb] * Ax[pa]
                else:
                    x[ia] += Bx[pb] * Ax[pa]

        for pc in range(Cp[j], nz):
            Cx[pc] = x[Ci[pc]]

    Cp[Cn] = nz  # finalize the last column of C

    # cut the arrays to their nominal size nnz
    # Ci, Cx, Cnzmax = csc_sprealloc_f(Cn, Cp, Ci, Cx, 0)
    Cnzmax = Cp[Cn]
    Cinew = Ci[:Cnzmax]
    Cxnew = Cx[:Cnzmax]

    return Cm, Cn, Cp, Cinew, Cxnew, Cnzmax


@nb.njit(cache=True)
def csc_multiply_cx(A: CxCSC, B: CSC) -> CxCSC:
    """
    Sparse matrix multiplication, C = A*B where A and B are CSC sparse matrices
    :param A:
    :param B:
    :return:
    """
    assert A.n_cols == B.n_rows
    nz = 0
    anz = A.indptr[A.n_cols]
    bnz = B.indptr[B.n_cols]
    Cm = A.n_rows
    Cn = B.n_cols

    w = np.zeros(Cn, dtype=np.int32)  # ialloc(m)  # get workspace
    x = np.empty(Cn, dtype=np.complex128)  # xalloc(m)  # get workspace

    # allocate result

    Cnzmax = int(np.sqrt(Cm)) * anz + bnz  # the trick here is to allocate just enough memory to avoid reallocating
    Cp = np.empty(Cn + 1, dtype=np.int32)
    Ci = np.empty(Cnzmax, dtype=np.int32)
    Cx = np.empty(Cnzmax, dtype=np.complex128)

    for j in range(Cn):

        # claim more space
        if nz + Cm > Cnzmax:
            # Ci, Cx, Cnzmax = csc_sprealloc_f(Cn, Cp, Ci, Cx, 2 * Cnzmax + m)
            # print('Re-Allocating')
            Cnzmax = 2 * Cnzmax + Cm
            if Cnzmax <= 0:
                Cnzmax = Cp[A.n_cols]

            length = min(Cnzmax, len(Ci))
            Cinew = np.empty(Cnzmax, dtype=np.int32)
            for i in range(length):
                Cinew[i] = Ci[i]
            Ci = Cinew

            length = min(Cnzmax, len(Cx))
            Cxnew = np.empty(Cnzmax, dtype=np.complex128)
            for i in range(length):
                Cxnew[i] = Cx[i]
            Cx = Cxnew

        # column j of C starts here
        Cp[j] = nz

        # perform the multiplication
        for pb in range(B.indptr[j], B.indptr[j + 1]):
            for pa in range(A.indptr[B.indices[pb]], A.indptr[B.indices[pb] + 1]):
                ia = A.indices[pa]
                if w[ia] < j + 1:
                    w[ia] = j + 1
                    Ci[nz] = ia
                    nz += 1
                    x[ia] = B.data[pb] * A.data[pa]
                else:
                    x[ia] += B.data[pb] * A.data[pa]

        for pc in range(Cp[j], nz):
            Cx[pc] = x[Ci[pc]]

    Cp[Cn] = nz  # finalize the last column of C

    # cut the arrays to their nominal size nnz
    # Ci, Cx, Cnzmax = csc_sprealloc_f(Cn, Cp, Ci, Cx, 0)
    Cnzmax = Cp[Cn]
    C = CxCSC(Cm, Cn, Cnzmax, False)
    C.indptr = Cp
    C.indices = Ci[:Cnzmax]
    C.data = Cx[:Cnzmax]

    return C


@nb.njit(cache=True)
def csc_matvec_ff(A: CSC, x: np.ndarray) -> np.ndarray:
    """

    :param A:
    :param x:
    :return:
    """
    assert A.n_cols == x.shape[0]
    if x.ndim == 1:

        y = np.zeros(A.n_rows, dtype=np.float64)
        for j in range(A.n_cols):
            for p in range(A.indptr[j], A.indptr[j + 1]):
                y[A.indices[p]] += A.data[p] * x[j]
        return y
    elif x.ndim == 2:
        ncols = x.shape[1]
        y = np.zeros((A.n_rows, ncols), dtype=np.float64)
        for k in range(ncols):
            for j in range(A.n_cols):
                for p in range(A.indptr[j], A.indptr[j + 1]):
                    y[A.indices[p], k] += A.data[p] * x[j, k]
        return y
    else:
        raise Exception("Wrong number of dimensions")


@nb.njit(cache=True)
def csc_matvec_cx(A: CxCSC, x: np.ndarray) -> np.ndarray:
    """

    :param A:
    :param x:
    :return:
    """
    assert A.n_cols == x.shape[0]
    if x.ndim == 1:

        y = np.zeros(A.n_rows, dtype=np.complex128)
        for j in range(A.n_cols):
            for p in range(A.indptr[j], A.indptr[j + 1]):
                y[A.indices[p]] += A.data[p] * x[j]
        return y
    elif x.ndim == 2:
        ncols = x.shape[1]
        y = np.zeros((A.n_rows, ncols), dtype=np.complex128)
        for k in range(ncols):
            for j in range(A.n_cols):
                for p in range(A.indptr[j], A.indptr[j + 1]):
                    y[A.indices[p], k] += A.data[p] * x[j, k]
        return y
    else:
        raise Exception("Wrong number of dimensions")


# @nb.njit("i8(i4[:], i4[:], f8[:], i8, f8, i4[:], f8[:], i8, i4[:], i8)")
@nb.njit(cache=True)
def csc_scatter_f(Ap, Ai, Ax, j, beta, w, x, mark, Ci, nz):
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


@nb.njit(cache=True)
def csc_scatter_cx(Ap, Ai, Ax, j, beta, w, x, mark, Ci, nz):
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

@nb.njit(cache=True)
def csc_spalloc_f(m, n, nzmax):
    """
    Allocate a sparse matrix (triplet form or compressed-column form).

    @param m: number of rows
    @param n: number of columns
    @param nzmax: maximum number of entries
    @return: m, n, Aindptr, Aindices, Adata, Anzmax
    """
    Anzmax = max(nzmax, 1)
    Aindptr = np.zeros(n + 1, dtype=np.int32)
    Aindices = np.zeros(Anzmax, dtype=np.int32)
    Adata = np.zeros(Anzmax, dtype=np.float64)
    return m, n, Aindptr, Aindices, Adata, Anzmax


@nb.njit(cache=True)
def csc_spalloc_cx(m, n, nzmax):
    """
    Allocate a sparse matrix (triplet form or compressed-column form).

    @param m: number of rows
    @param n: number of columns
    @param nzmax: maximum number of entries
    @return: m, n, Aindptr, Aindices, Adata, Anzmax
    """
    Anzmax = max(nzmax, 1)
    Aindptr = np.zeros(n + 1, dtype=np.int32)
    Aindices = np.zeros(Anzmax, dtype=np.int32)
    Adata = np.zeros(Anzmax, dtype=np.complex128)
    return m, n, Aindptr, Aindices, Adata, Anzmax

@nb.njit(cache=True)
def csc_add_ff(A: CSC, B: CSC, alpha = 1.0, beta = 1.0) -> CSC:
    """
    C = alpha*A + beta*B

    @param A: column-compressed matrix
    @param B: column-compressed matrix
    @param alpha: scalar alpha
    @param beta: scalar beta
    @return: C=alpha*A + beta*B, null on error (Cm, Cn, Cp, Ci, Cx)
    """

    m = A.n_rows
    n = B.n_cols

    w = np.zeros(m, dtype=np.int32)

    x = np.zeros(n, dtype=np.float64)  # get workspace

    C = CSC(m, n, A.nnz + B.nnz, False)  # allocate result

    nz = 0

    for j in range(n):
        C.indptr[j] = nz  # column j of C starts here

        nz = csc_scatter_f(A.indptr, A.indices, A.data, j, alpha, w, x, j + 1, C.indices, nz)  # alpha*A(:,j)

        nz = csc_scatter_f(B.indptr, B.indices, B.data, j, beta, w, x, j + 1, C.indices, nz)  # beta*B(:,j)

        for p in range(C.indptr[j], nz):
            C.data[p] = x[C.indices[p]]

    C.indptr[n] = nz  # finalize the last column of C

    return C  # success; free workspace, return C


@nb.njit(cache=True)
def csc_add_ff2(Am, An, Aindptr, Aindices, Adata, Bn, Bindptr, Bindices, Bdata):
    """
    C = A + B

    @param A: column-compressed matrix
    @param B: column-compressed matrix
    @return: C=alpha*A + beta*B, null on error (Cm, Cn, Cp, Ci, Cx)
    """
    nz = 0

    m, anz, n, Bp, Bx = Am, Aindptr[An], Bn, Bindptr, Bdata

    bnz = Bp[n]

    w = np.zeros(m, dtype=np.int32)

    x = np.zeros(m, dtype=np.float64)  # get workspace

    Cm, Cn, Cp, Ci, Cx, Cnzmax = csc_spalloc_f(m, n, anz + bnz)  # allocate result

    for j in range(n):
        Cp[j] = nz  # column j of C starts here

        nz = csc_scatter_f(Aindptr, Aindices, Adata, j, 1.0, w, x, j + 1, Ci, nz)  # alpha*A(:,j)

        nz = csc_scatter_f(Bindptr, Bindices, Bdata, j, 1.0, w, x, j + 1, Ci, nz)  # beta*B(:,j)

        for p in range(Cp[j], nz):
            Cx[p] = x[Ci[p]]

    Cp[n] = nz  # finalize the last column of C

    return Cm, Cn, Cp, Ci, Cx, nz  # success; free workspace, return C


@nb.njit(cache=True)
def csc_add_cx2(Am, An, Aindptr, Aindices, Adata, Bn, Bindptr, Bindices, Bdata):
    """
    C = A + B

    @param A: column-compressed matrix
    @param B: column-compressed matrix
    @return: C=alpha*A + beta*B, null on error (Cm, Cn, Cp, Ci, Cx)
    """
    nz = 0

    m, anz, n, Bp, Bx = Am, Aindptr[An], Bn, Bindptr, Bdata

    bnz = Bp[n]

    w = np.zeros(m, dtype=np.int32)

    x = np.zeros(m, dtype=np.complex128)  # get workspace

    Cm, Cn, Cp, Ci, Cx, Cnzmax = csc_spalloc_cx(m, n, anz + bnz)  # allocate result

    for j in range(n):
        Cp[j] = nz  # column j of C starts here

        nz = csc_scatter_cx(Aindptr, Aindices, Adata, j, 1.0, w, x, j + 1, Ci, nz)  # alpha*A(:,j)

        nz = csc_scatter_cx(Bindptr, Bindices, Bdata, j, 1.0, w, x, j + 1, Ci, nz)  # beta*B(:,j)

        for p in range(Cp[j], nz):
            Cx[p] = x[Ci[p]]

    Cp[n] = nz  # finalize the last column of C

    return Cm, Cn, Cp, Ci, Cx, nz  # success; free workspace, return C


def csc_add_cx3(A: CxCSC, B: CxCSC) -> CxCSC:
    Cm, Cn, Cp, Ci, Cx, nz = csc_add_cx2(
        A.n_rows, A.n_cols, A.indptr, A.indices, A.data,
        B.n_cols, B.indptr, B.indices, B.data
    )

    return CxCSC(Cm, Cn, nz, False).set(Ci, Cp, Cx)