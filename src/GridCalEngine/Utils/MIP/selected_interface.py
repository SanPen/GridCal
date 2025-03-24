# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

"""
Uncomment the appropriate interface imports to use: Pulp or OrTools
"""
from typing import List, Union, Tuple
import numpy as np
from scipy.sparse import csc_matrix
from GridCalEngine.basic_structures import ObjVec, ObjMat, Vec

# from GridCalEngine.Utils.MIP.SimpleMip import LpExp, LpVar, LpModel, get_available_mip_solvers, set_var_bounds
# from GridCalEngine.Utils.MIP.ortools_interface import LpExp, LpVar, LpModel, get_available_mip_solvers, set_var_bounds
from GridCalEngine.Utils.MIP.pulp_interface import LpExp, LpVar, LpModel, get_available_mip_solvers, set_var_bounds


def join(init: str, vals: List[int], sep="_"):
    """
    Generate naming string
    :param init: initial string
    :param vals: concatenation of indices
    :param sep: separator
    :return: naming string
    """
    return init + sep.join([str(x) for x in vals])


def lpDot(mat: csc_matrix, arr: Union[ObjVec, ObjMat]) -> Union[ObjVec, ObjMat]:
    """
    CSC matrix-vector or CSC matrix-matrix dot product (A x b)
    :param mat: CSC sparse matrix (A)
    :param arr: dense vector or matrix of object type (b)
    :return: vector or matrix result of the product
    """
    n_rows, n_cols = mat.shape

    # check dimensional compatibility
    assert (n_cols == arr.shape[0])

    # check that the sparse matrix is indeed of CSC format
    if mat.format != 'csc':
        raise Exception("lpDot: Sparse matrix must be in CSC format")

    if arr.ndim == 1:
        """
        Uni-dimensional sparse matrix - vector product
        """
        res = np.zeros(n_rows, dtype=arr.dtype)
        for i in range(n_cols):
            for ii in range(mat.indptr[i], mat.indptr[i + 1]):
                j = mat.indices[ii]  # row index
                res[j] += mat.data[ii] * arr[i]  # C.data[ii] is equivalent to C[i, j]

        return res

    elif arr.ndim == 2:
        """
        Multi-dimensional sparse matrix - matrix product
        """
        cols_vec = arr.shape[1]
        res = np.zeros((n_rows, cols_vec), dtype=arr.dtype)

        for k in range(cols_vec):  # for each column of the matrix "vec", do the matrix vector product
            for i in range(n_cols):
                for ii in range(mat.indptr[i], mat.indptr[i + 1]):
                    j = mat.indices[ii]  # row index
                    res[j, k] += mat.data[ii] * arr[i, k]  # C.data[ii] is equivalent to C[i, j]

        return res

    else:
        raise Exception("lpDot: Unsupported number of dimensions")
