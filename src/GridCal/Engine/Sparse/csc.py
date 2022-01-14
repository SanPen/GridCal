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
from collections.abc import Iterable
import scipy.sparse.sparsetools as sptools
from scipy.sparse import csc_matrix

from GridCal.Engine.Sparse.utils import dense_to_str

from GridCal.Engine.Sparse.csc_numba import *


class CscMat(csc_matrix):
    """
    Matrix in compressed-column or triplet form.
    """

    def __init__(self, arg1, shape=None, dtype=None, copy=False):
        """
        CSC sparse matrix

        Format explanation example
             0  1  2
            _________
        0  | 4       |
        1  | 3  9    |
        2  |    7  8 |
        3  | 3     8 |
        4  |    8  9 |
        5  |    4    |
            ---------
         cols = 3
         rows = 6
                    0  1  2  3  4  5  6  7  8  9   <-- These are the positions indicated by indptr (just to illustrate)
         data =    [4, 3, 3, 9, 7, 8, 4, 8, 8, 9]      # stores the values
         indices = [0, 1, 3, 1, 2, 4, 5, 2, 3, 4]      # indicates the row index
         indptr  = [0, 3, 7, 10]                       # The length is cols + 1, stores the from and to indices that
                                                         delimit a column.
                                                         i.e. the first column takes the indices and data from the
                                                         positions 0 to 3-1, this is
                                                         column_idx = 0        # (j)
                                                         indices = [0 , 1, 3]  # row indices (i) of the column (j)
                                                         data    = [10, 3, 3]

         Typical loop:

         for j in range(n):  # for every column, same as range(cols)
            for k in range(indptr[j], indptr[j+1]): # for every entry in the column
                i = indices[k]
                value = data[k]
                print(i, j, value)

        For completeness, the CSR equivalent is
                   0  1  2  3  4  5  6  7  8  9
        data =    [4, 3, 9, 7, 8, 3, 8, 8, 9, 4]
        indices = [0, 0, 1, 1, 2, 0, 2, 1, 2, 1]
        indptr =  [0, 1, 3, 5, 7, 9, 10]

        @param m: number of rows
        @param n: number of columns
        @param nz_max: maximum number of entries
        """
        csc_matrix.__init__(self, arg1, shape, dtype, copy)

        # number of rows
        self.m = self.shape[0]

        # number of columns
        self.n = self.shape[1]

    def __add__(self, other) -> "CscMat":
        """
        Matrix addition
        :param other: CscMat instance
        :return: CscMat instance
        """

        if isinstance(other, CscMat):  # matrix-matrix addition
            assert (other.m == self.m)
            assert (other.n == self.n)

            nz_max = self.nnz + other.nnz
            indptr = np.zeros(self.n + 1, dtype=np.int32)

            # row indices, size nzmax
            indices = np.zeros(nz_max, dtype=np.int32)

            # numerical values, size nzmax
            data = np.zeros(nz_max, dtype=np.float64)

            sptools.csc_plus_csc(self.m, self.n,
                                 self.indptr, self.indices, self.data,
                                 other.indptr, other.indices, other.data,
                                 indptr, indices, data)
            return CscMat((data, indices, indptr), shape=self.shape)

        elif isinstance(other, float) or isinstance(other, int):
            raise NotImplementedError('Adding a nonzero scalar to a sparse matrix would make it a dense matrix.')
        else:
            raise NotImplementedError('Type not supported')

    def __sub__(self, other) -> "CscMat":
        """
        Matrix subtraction
        :param other: CscMat instance
        :return: CscMat instance
        """

        if isinstance(other, CscMat):  # subtract CSC matrix
            assert (other.m == self.m)
            assert (other.n == self.n)

            nz_max = self.nnz + other.nnz
            indptr = np.zeros(self.n + 1, dtype=np.int32)

            # row indices, size nzmax
            indices = np.zeros(nz_max, dtype=np.int32)

            # numerical values, size nzmax
            data = np.zeros(nz_max, dtype=np.float64)

            sptools.csc_minus_csc(self.m, self.n,
                                  self.indptr, self.indices, self.data,
                                  other.indptr, other.indices, other.data,
                                  indptr, indices, data)
            return CscMat((data, indices, indptr), shape=self.shape)

        elif isinstance(other, float) or isinstance(other, int):  # Add scalar value

            raise NotImplementedError('Adding a non-zero scalar to a sparse matrix would make it a dense matrix.')
        else:
            raise NotImplementedError('Type not supported')

    def __mul__(self, other):
        """
        Matrix multiplication
        :param other: CscMat instance
        :return: CscMat instance
        """
        if isinstance(other, CscMat):  # mat-mat multiplication
            # 2-pass matrix multiplication
            Cp = np.empty(self.n + 1, dtype=np.int32)

            sptools.csc_matmat_pass1(self.n, other.m,
                                     self.indptr, self.indices,
                                     other.indptr, other.indices, Cp)
            nnz = Cp[-1]
            Ci = np.empty(nnz, dtype=np.int32)
            Cx = np.empty(nnz, dtype=np.float64)

            sptools.csc_matmat_pass2(self.n, other.m,
                                     self.indptr, self.indices, self.data,
                                     other.indptr, other.indices, other.data,
                                     Cp, Ci, Cx)

            return CscMat((Cx, Ci, Cp), shape=self.shape)

        elif isinstance(other, np.ndarray):  # multiply by a vector or array of vectors

            if len(other.shape) == 1:
                y = np.zeros(self.m, dtype=np.float64)
                sptools.csc_matvec(self.m, self.n,
                                   self.indptr, self.indices, self.data,
                                   other, y)
                return y
            elif len(other.shape) == 2:

                '''

                 * Input Arguments:
                 *   I  n_row            - number of rows in A
                 *   I  n_col            - number of columns in A
                 *   I  n_vecs           - number of column vectors in X and Y
                 *   I  Ap[n_row+1]      - row pointer
                 *   I  Aj[nnz(A)]       - column indices
                 *   T  Ax[nnz(A)]       - nonzeros
                 *   T  Xx[n_col,n_vecs] - input vector
                 *
                 * Output Arguments:
                 *   T  Yx[n_row,n_vecs] - output vector
                 *
                 * Note:
                 *   Output array Yx must be preallocated
                 *

                void csc_matvecs(const I n_row,
                                 const I n_col,
                                 const I n_vecs,
                                 const I Ap[],
                                 const I Ai[],
                                 const T Ax[],
                                 const T Xx[],
                                       T Yx[])
                '''
                n_col, n_vecs = other.shape

                y = np.zeros((self.m, n_vecs), dtype=np.float64)
                sptools.csc_matvecs(self.m, self.n, n_vecs,
                                    self.indptr, self.indices, self.data,
                                    other, y)
                return y

        elif isinstance(other, float) or isinstance(other, int):  # multiply by a scalar value
            C = self.copy()
            C.data *= other
            return C

        else:
            raise Exception('Type not supported')

    def dot(self, o) -> "CscMat":
        """
        Dot product
        :param o: CscMat instance
        :return: CscMat instance
        """
        # 2-pass matrix multiplication
        Cp = np.empty(self.n + 1, dtype=np.int32)

        sptools.csc_matmat_pass1(self.n, o.m,
                                 self.indptr, self.indices,
                                 o.indptr, o.indices, Cp)
        nnz = Cp[-1]
        Ci = np.empty(nnz, dtype=np.int32)
        Cx = np.empty(nnz, dtype=np.float64)

        sptools.csc_matmat_pass2(self.n, o.m,
                                 self.indptr, self.indices, self.data,
                                 o.indptr, o.indices, o.data,
                                 Cp, Ci, Cx)

        return CscMat((Cx, Ci, Cp), shape=self.shape)

    # @property
    # def T(self):
    #     m, n, Cp, Ci, Cx = csc_transpose(self.m, self.n, self.indptr, self.indices, self.data)
    #     return CscMat((Cx, Ci, Cp), shape=(m, n))

    def islands(self):
        """
        Find islands in the matrix
        :return: list of islands
        """
        islands = find_islands(self.n, self.indptr, self.indices)
        return [np.sort(island) for island in islands]


def scipy_to_mat(scipy_mat: csc_matrix):
    """
    Build CsCMat from csc_matrix
    :param scipy_mat:
    :return: CscMat
    """
    return CscMat((scipy_mat.data, scipy_mat.indices, scipy_mat.indptr), shape=scipy_mat.shape)


def pack_4_by_4(A11: CscMat, A12: CscMat, A21: CscMat, A22: CscMat):
    """
    Stack 4 CSC matrices
    :param A11: Upper left matrix
    :param A12: Upper right matrix
    :param A21: Lower left matrix
    :param A22: Lower right matrix
    :return: Stitched matrix
    """

    m, n, Pi, Pp, Px = csc_stack_4_by_4_ff(A11.shape[0], A11.shape[1], A11.indices, A11.indptr, A11.data,
                                           A12.shape[0], A12.shape[1], A12.indices, A12.indptr, A12.data,
                                           A21.shape[0], A21.shape[1], A21.indices, A21.indptr, A21.data,
                                           A22.shape[0], A22.shape[1], A22.indices, A22.indptr, A22.data)
    return CscMat((Px, Pi, Pp), shape=(m, n))


def sp_transpose(mat: csc_matrix):
    """
    Actual CSC transpose unlike scipy's
    :param mat: CSC matrix
    :return: CSC transposed matrix
    """
    Cm, Cn, Cp, Ci, Cx = csc_transpose(m=mat.shape[0],
                                       n=mat.shape[1],
                                       Ap=mat.indptr,
                                       Ai=mat.indices,
                                       Ax=mat.data)
    return csc_matrix((Cx, Ci, Cp), shape=(Cm, Cn))


def sp_slice_cols(mat: csc_matrix, cols: np.ndarray):
    """
    Slice columns
    :param mat: Matrix to slice
    :param cols: vector of columns
    :return: New sliced matrix
    """
    new_indices, new_col_ptr, new_val, nrows, ncols = sp_submat_c_numba(nrows=mat.shape[0],
                                                                        ptrs=mat.indptr,
                                                                        indices=mat.indices,
                                                                        values=mat.data,
                                                                        cols=cols)
    return csc_matrix((new_val, new_indices, new_col_ptr), shape=(nrows, ncols))


def sp_slice_rows(mat: csc_matrix, rows: np.ndarray):
    """
    Slice rows
    :param mat:
    :param rows:
    :return: CSC matrix
    """
    # mat2 = sp_transpose(mat)
    # return sp_transpose(sp_slice_cols(mat2, rows))

    return sp_transpose(sp_slice_cols(sp_transpose(mat), np.array(rows)))


def sp_slice(mat: csc_matrix, rows, cols):
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
    :param mat:
    :param rows:
    :param cols:
    :return:
    """
    # mat2 = sp_transpose(sp_slice_cols(mat, cols))
    # return sp_transpose(sp_slice_cols(mat2, rows))

    new_val, new_row_ind, new_col_ptr, n_rows, n_cols, nnz = csc_sub_matrix(Am=mat.shape[0], Annz=mat.nnz,
                                                                            Ap=mat.indptr, Ai=mat.indices, Ax=mat.data,
                                                                            rows=rows, cols=cols)
    new_val = np.resize(new_val, nnz)
    new_row_ind = np.resize(new_row_ind, nnz)

    return csc_matrix((new_val, new_row_ind, new_col_ptr), shape=(n_rows, n_cols))


def csc_stack_2d_ff(mats, m_rows=1, m_cols=1, row_major=True):
    """
    Assemble matrix from a list of matrices representing a "super matrix"

    |mat11 | mat12 | mat13 |
    |mat21 | mat22 | mat23 |

    if row-major turns into:

        mats = [mat11, mat12, mat13, mat21, mat22, mat23]

    else: (it is column major)

        mats = [mat11, mat21, mat12, mat22, mat31, mat32]

    m_rows = 2
    m_cols = 3

    :param mats: array of CSC matrices arranged in row-major or column-major order into a list
    :param m_rows: number of rows of the mats structure
    :param m_cols: number of cols of the mats structure
    :param row_major: mats is sorted in row major, else it is sorted in column major
    :return: Final assembled matrix in CSC format
    """

    mats_data = List()
    mats_indptr = List()
    mats_indices = List()
    mats_cols = List()
    mats_rows = List()
    for x in mats:
        mats_data.append(x.data)
        mats_indptr.append(x.indptr)
        mats_indices.append(x.indices)
        mats_cols.append(x.shape[1])
        mats_rows.append(x.shape[0])

    if row_major:
        data, indices, indptr, nrows, ncols = csc_stack_2d_ff_row_major(mats_data,
                                                                        mats_indptr,
                                                                        mats_indices,
                                                                        mats_cols,
                                                                        mats_rows,
                                                                        m_rows,
                                                                        m_cols)
    else:
        data, indices, indptr, nrows, ncols = csc_stack_2d_ff_col_major(mats_data,
                                                                        mats_indptr,
                                                                        mats_indices,
                                                                        mats_cols,
                                                                        mats_rows,
                                                                        m_rows,
                                                                        m_cols)

    return csc_matrix((data, indices, indptr), shape=(nrows, ncols))




def csc_stack_2d_ff_old(mats, m_rows=1, m_cols=1):
    """
    Assemble matrix from a list of matrices representing a "super matrix"

    |mat11 | mat12 | mat13 |
    |mat21 | mat22 | mat23 |

    turns into:

    mats = [mat11, mat12, mat13, mat21, mat22, mat23]
    m_rows = 2
    m_cols = 3

    :param mats: array of CSC matrices arranged in row-major order into a list
    :param m_rows: number of rows of the mats structure
    :param m_cols: number of cols of the mats structure
    :return: Final assembled matrix
    """

    # pass 1: compute the number of non zero
    nnz = 0
    nrows = 0
    ncols = 0
    for r in range(m_rows):

        nrows += mats[r * m_cols].shape[0]  # equivalent to mats[r, 0]

        for c in range(m_cols):
            mat = mats[r * m_cols + c]  # equivalent to mats[r, c]
            nnz += mat.indptr[mat.shape[1]]

            if r == 0:
                ncols += mat.shape[1]

    # pass 2: fill in the data
    indptr = np.empty(ncols + 1, dtype=np.int32)
    indices = np.empty(nnz, dtype=np.int32)
    data = np.empty(nnz, dtype=np.float64)
    cnt = 0
    indptr[0] = 0
    offset_col = 0
    for c in range(m_cols):  # for each column of the array of matrices

        n = mats[c].shape[1]  # equivalent to mats[0, c]

        for j in range(n):  # for every column of the column of matrices

            offset_row = 0

            for r in range(m_rows):  # for each row of the array of rows

                mat = mats[r * m_cols + c]  # equivalent to mats[r, c]
                m = mat.shape[0]
                Ap = mat.indptr
                Ai = mat.indices
                Ax = mat.data

                for k in range(Ap[j], Ap[j + 1]):  # for every entry in the column from A
                    indices[cnt] = Ai[k] + offset_row  # row index
                    data[cnt] = Ax[k]
                    cnt += 1

                offset_row += m

            indptr[offset_col + j + 1] = cnt
        offset_col += n

    # return nrows, ncols, indices, indptr, data
    return csc_matrix((data, indices, indptr), shape=(nrows, ncols))
