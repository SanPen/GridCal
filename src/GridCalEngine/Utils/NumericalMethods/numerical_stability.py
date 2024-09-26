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
from scipy.sparse.linalg import svds
from scipy.sparse.linalg import splu
from scipy.sparse import csc_matrix


def sparse_instability_svd_test(A: csc_matrix, condition_number_thrshold: float = 1e7):
    """
    Test for numerical instability of a sparse matrix A by calculating its condition number.
    :param A:  The sparse coefficient matrix
    :param condition_number_thrshold: big number (1e7)
    :return: condition_number (float): The condition number of the matrix
             unstable (bool): 'stable' or 'unstable' based on the condition number
    """

    # Compute the singular values using the svds function (k=2 to get largest and smallest)
    u, s, vt = svds(A, k=2)  # Gets the smallest and largest singular values

    # Condition number is the ratio of largest to smallest singular value
    condition_number = s[-1] / s[0]

    print("SVD  rcond:", condition_number)

    # Determine stability
    unstable = condition_number > condition_number_thrshold

    return condition_number, unstable


def sparse_instability_lu_test(A: csc_matrix, condition_number_thrshold: float = 1e-7):
    """

    :param A: The sparse coefficient matrix
    :param condition_number_thrshold: small number (ie. 1e-7)
    :return: condition_number (float): The condition number of the matrix
             unstable (bool): 'stable' or 'unstable' based on the condition number
    """
    # Perform sparse LU decomposition
    try:
        lu = splu(A)
        # Estimate the reciprocal condition number from the LU decomposition
        # (typically `rcond` can be estimated from the smallest pivot in U or a more sophisticated estimate)
        # Here, we compute an estimate using `lu.U` directly for simplicity.
        U_diag = lu.U.diagonal()  # Diagonal elements of U
        rcond = np.min(np.abs(U_diag)) / np.max(np.abs(U_diag))

        # Determine stability
        unstable = rcond < condition_number_thrshold

        print("LU  decomposition ok, rcond:", rcond)
        return rcond, unstable

    except RuntimeError as e:
        print("LU  decomposition failed: ", str(e))
        return 0.0, True
