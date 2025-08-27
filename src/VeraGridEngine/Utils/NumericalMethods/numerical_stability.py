# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
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
    if A.shape[0] != 0:
        # Compute the singular values using the svds function (k=2 to get largest and smallest)
        u, s, vt = svds(A, k=2)  # Gets the smallest and largest singular values

        # Condition number is the ratio of largest to smallest singular value
        condition_number = s[-1] / s[0]

        print("SVD  rcond:", condition_number)

        # Determine stability
        unstable = condition_number > condition_number_thrshold

        return condition_number, unstable
    else:
        return 0, False


def sparse_instability_lu_test(A: csc_matrix, condition_number_thrshold: float = 1e-7):
    """

    :param A: The sparse coefficient matrix
    :param condition_number_thrshold: small number (ie. 1e-7)
    :return: condition_number (float): The condition number of the matrix
             unstable (bool): 'stable' or 'unstable' based on the condition number
    """
    if A.shape[0] != 0:
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
    else:
        return 0.0, True
