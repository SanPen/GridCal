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
from GridCal.Engine.Sparse.csc import *
from scipy.sparse import csc_matrix


def test2():
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

    """
    m = 6
    n = 3
    data = np.array([4, 3, 3, 9, 7, 8, 4, 8, 8, 9]).astype(np.float64)
    indices = np.array([0, 1, 3, 1, 2, 4, 5, 2, 3, 4]).astype(np.int32)
    indptr = np.array([0, 3, 7, 10]).astype(np.int32)

    A1 = csc_matrix((data, indices, indptr), shape=(m, n))
    A2 = CscMat((data, indices, indptr), shape=(m, n))

    a = 1
    b = 2
    # # list_a = [5, 3, 3]
    list_a = [1, 2, 3]
    list_b = [1, 2]

    # (a, :) -> row a
    comp1 = A1[a, :].todense() == A2[a, :].todense()
    print('(a, :) -> ', comp1.all())

    # (:, b) -> column b
    comp2 = A1[:, b].todense() == A2[:, b].todense()
    print('(:, b) -> ', comp2.all())

    # (:, :) -> self
    comp3 = A1[:, :].todense() == A2[:, :].todense()
    print('(:, :) -> ', comp3.all())

    # (a, list_b) -> vector of row a and columns given by list_b
    comp4 = A1[a, :][:, list_b].todense() == A2[a, list_b].todense()
    print('(a, list_b) -> ', comp4.all())

    # (list_a, b) -> vector of column b and rows given by list_a
    comp5 = A1[list_a, :][:, b].todense() == A2[list_a, b].todense()
    print('(list_a, b) -> ', comp5.all())

    # (:, list_b) -> Submatrix with the columns given by list_b
    comp6 = A1[:, list_b].todense() == A2[:, list_b].todense()
    print('(:, list_b) -> ', comp6.all())

    # (list_a, :) -> Submatrix with the rows given by list_a
    comp7 = A1[list_a, :].todense() == A2[list_a, :].todense()
    print('(list_a, :) -> ', comp7.all())

    # (list_a, list_b)  -> non continuous sub-matrix
    comp8 = A1[list_a, :][:, list_b].todense() == A2[np.ix_(list_a, list_b)].todense()
    print('(list_a, list_b) -> ', comp8.all())

def test3():

    m = 6
    n = 3
    data = np.array([4, 3, 3, 9, 7, 8, 4, 8, 8, 9]).astype(np.float64)
    indices = np.array([0, 1, 3, 1, 2, 4, 5, 2, 3, 4]).astype(np.int32)
    indptr = np.array([0, 3, 7, 10]).astype(np.int32)

    A = csc_matrix((data, indices, indptr), shape=(m, n))

    list_a = np.array([1, 2, 5])
    list_b = np.array([0, 2])

    A1 = A[np.ix_(list_a, list_b)]
    A2 = sp_slice(A, list_a, list_b)

    ok = np.allclose(A1.toarray(), A2.toarray())

    print(ok)

    A3 = A[list_a, :]
    A4 = sp_slice_rows(A, list_a)

    ok2 = np.allclose(A3.toarray(), A4.toarray())

    print(ok2)


if __name__ == '__main__':

    test2()
