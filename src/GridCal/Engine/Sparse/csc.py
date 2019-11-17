# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.

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
