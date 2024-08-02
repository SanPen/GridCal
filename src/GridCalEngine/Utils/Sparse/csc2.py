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
from typing import List
from numba import njit, int32, float64
from numba import types
from numba.experimental import jitclass
import numpy as np
from scipy.sparse import csc_matrix
from scipy.sparse.linalg._dsolve._superlu import gstrf, SuperLU
from GridCalEngine.basic_structures import IntVec, IntMat, Vec


@jitclass([
    ('n_rows', int32),
    ('n_cols', int32),
    ('nnz', int32),
    ('data', float64[:]),
    ('indices', int32[:]),
    ('indptr', int32[:],),
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
        else:
            self.data = np.empty(nnz, dtype=np.float64)
            self.indices = np.empty(nnz, dtype=np.int32)

        # must always be zeros
        self.indptr = np.zeros(n_cols + 1, dtype=np.int32)

    @property
    def shape(self):
        """
        Shape for scipy compatibility
        :return: n_rows, n_cols
        """
        return self.n_rows, self.n_cols

    def resize(self, nnz: int32):
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

    def dot(self, x: Vec):
        """
        Mat-vector multiplication
        :param x: vector
        :return:
        """
        assert self.n_cols == x.shape[0]
        assert x.ndim == 1

        y = np.zeros(self.n_rows, dtype=float64)
        for j in range(self.n_cols):
            for p in range(self.indptr[j], self.indptr[j + 1]):
                y[self.indices[p]] += self.data[p] * x[j]
        return y


def mat_to_scipy(csc: CSC) -> csc_matrix:
    """

    :param csc:
    :return:
    """
    return csc_matrix((csc.data, csc.indices, csc.indptr), shape=(csc.n_rows, csc.n_cols))


def scipy_to_mat(mat: csc_matrix) -> CSC:
    """

    :param mat:
    :return:
    """
    x = CSC(mat.shape[0], mat.shape[1], mat.nnz, False)
    x.data = mat.data.astype(float)
    x.indices = mat.indices.astype(np.int32)
    x.indptr = mat.indptr.astype(np.int32)
    return x


def spfactor(A: CSC) -> SuperLU:
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

    ret = gstrf(A.n_cols, A.nnz, A.data, A.indices, A.indptr,
                ilu=False, options=_options, csc_construct_func=None)

    return ret


def spsolve_csc(A: CSC, x: Vec) -> Vec:
    """
    Sparse solution
    :param A: CSC matrix
    :param x: vector
    :return: solution
    """
    return spfactor(A).solve(x)


@njit(cache=True)
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


@njit(cache=True)
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


@njit(cache=True)
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


@njit(cache=True)
def sp_transpose(A: CSC) -> CSC:
    """
    Actual CSC transpose unlike scipy's
    :param A: CSC matrix
    :return: CSC transposed matrix
    """
    C = CSC(A.n_cols, A.n_rows, A.nnz, False)

    w = np.zeros(A.n_rows, dtype=int32)

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


@njit(cache=True)
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


@njit(cache=True)
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


@njit(cache=True)
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

    # generate lookup for the non immediate axis (for CSC it is the rows) -> index lookup
    lookup = np.zeros(A.n_rows, dtype=int32)
    lookup[rows] = np.arange(n_rows, dtype=int32)

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


@njit(cache=True)
def csc_stack_2d_ff(mats: List[CSC], m_rows: int = 1, m_cols: int = 1) -> CSC:
    """
    Assemble matrix from a list of matrices representing a "super matrix"

    |mat11 | mat12 | mat13 |
    |mat21 | mat22 | mat23 |

    turns into:

    [mat11, mat12, mat13, mat21, mat22, mat23]
    m_rows = 2
    m_cols = 3

    :param mats: list of CSC matrices arranged in row-major order (i.e. [mat11, mat12, mat13, mat21, mat22, mat23]
    :param m_rows: number of rows of the mats structure
    :param m_cols: number of cols of the mats structure
    :return: Final assembled matrix in CSC format
    """

    # pass 1: compute the number of non zero
    nnz = 0
    nrows = 0
    ncols = 0
    for r in range(m_rows):
        nrows += mats[r * m_cols].n_rows  # equivalent to mats[r, 0]
        for c in range(m_cols):
            col = mats[c + r * m_cols].n_cols  # equivalent to mats[r, c]
            nnz += mats[c + r * m_cols].nnz
            if r == 0:
                ncols += col

    # pass 2: fill in the data
    res = CSC(nrows, ncols, nnz, False)
    cnt = 0
    res.indptr[0] = 0
    offset_col = 0
    for c in range(m_cols):  # for each column of the array of matrices

        # number of columns
        n = mats[c].n_cols  # equivalent to mats[0, c]

        if n > 0:
            for j in range(n):  # for every column of the column of matrices

                offset_row = 0

                for r in range(m_rows):  # for each row of the array of rows

                    # get the current sub-matrix
                    A: CSC = mats[r * m_cols + c]  # equivalent to mats[r, c]

                    if A.n_rows > 0:

                        for k in range(A.indptr[j], A.indptr[j + 1]):  # for every entry in the column from A
                            res.indices[cnt] = A.indices[k] + offset_row  # row index
                            res.data[cnt] = A.data[k]
                            cnt += 1

                        offset_row += A.n_rows

                res.indptr[offset_col + j + 1] = cnt
            offset_col += n

    return res


@njit(cache=True)
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


@njit(cache=True)
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


@njit(cache=True)
def create_lookup(size: int, indices: IntVec) -> IntVec:
    """
    Create a lookup array
    :param size: Size of the thing (i.e. number of buses)
    :param indices: indices to map (i.e. pq indices)
    :return: lookup array
    """
    lookup = np.zeros(size, dtype=int32)
    lookup[indices] = np.arange(len(indices), dtype=int32)
    return lookup


@njit(cache=False)
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
