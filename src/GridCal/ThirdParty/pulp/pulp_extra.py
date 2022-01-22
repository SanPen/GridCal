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

"""
This file includes extensions to the PuLP library
"""

import numpy as np
from .pulp import LpProblem, LpVariable
from itertools import product
from scipy.sparse import csc_matrix


def lpDot(mat, arr):
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
    if mat.format == 'csc':
        mat_2 = mat
    else:
        # convert the matrix to CSC sparse
        mat_2 = csc_matrix(mat)

    if len(arr.shape) == 1:
        """
        Uni-dimensional sparse matrix - vector product
        """
        res = np.zeros(n_rows, dtype=arr.dtype)
        for i in range(n_cols):
            for ii in range(mat_2.indptr[i], mat_2.indptr[i + 1]):
                j = mat_2.indices[ii]  # row index
                res[j] += mat_2.data[ii] * arr[i]  # C.data[ii] is equivalent to C[i, j]
    else:
        """
        Multi-dimensional sparse matrix - matrix product
        """
        cols_vec = arr.shape[1]
        res = np.zeros((n_rows, cols_vec), dtype=arr.dtype)

        for k in range(cols_vec):  # for each column of the matrix "vec", do the matrix vector product
            for i in range(n_cols):
                for ii in range(mat_2.indptr[i], mat_2.indptr[i + 1]):
                    j = mat_2.indices[ii]  # row index
                    res[j, k] += mat_2.data[ii] * arr[i, k]  # C.data[ii] is equivalent to C[i, j]
    return res


def lpAddRestrictions(problem: LpProblem, arr, name):
    """
    Add vector or matrix of restrictions to the problem
    :param problem: instance of LpProblem
    :param arr: 1D or 2D array
    :param name: name of the restriction
    """

    if len(arr.shape) == 1:

        for i, elm in enumerate(arr):
            problem.add(elm, name + '_' + str(i + 1))

    elif len(arr.shape) == 2:

        for i, j in product(range(arr.shape[0]), range(arr.shape[1])):
            problem.add(arr[i, j], name + '_' + str(i + 1) + '_' + str(j))


def lpAddRestrictions2(problem: LpProblem, lhs, rhs, name, op='='):
    """
    Add vector or matrix of restrictions to the problem
    :param problem: instance of LpProblem
    :param lhs: 1D array (left hand side)
    :param rhs: 1D or 2D array (right hand side)
    :param name: name of the restriction    
    :param op: type of restriction (=, <=, >=)
    """

    assert(lhs.shape == rhs.shape)

    arr = np.empty(lhs.shape, dtype=object)

    if len(lhs.shape) == 1:

        for i in range(lhs.shape[0]):
            if op == '=':
                arr[i] = lhs[i] == rhs[i]

            elif op == '<=':
                arr[i] = lhs[i] <= rhs[i]

            elif op == '>=':
                arr[i] = lhs[i] >= rhs[i]

    elif len(lhs.shape) == 2:

        for i, j in product(range(lhs.shape[0]), range(lhs.shape[1])):
            if op == '=':
                arr[i, j] = lhs[i, j] == rhs[i, j]

            elif op == '<=':
                arr[i, j] = lhs[i, j] <= rhs[i, j]

            elif op == '>=':
                arr[i, j] = lhs[i, j] >= rhs[i, j]

    lpAddRestrictions(problem=problem, arr=arr, name=name)

    return arr


def lpAddRestrictions3(problem: LpProblem, lhs, var, rhs, name):
    """
    Add vector or matrix of restrictions to the problem
    so that lhs <= var <= rhs
    :param problem: instance of LpProblem
    :param lhs: 1D array (left hand side)
    :param var: 1D or 2D array (right hand side)
    :param rhs: 1D or 2D array (right hand side)
    :param name: name of the restriction
    """

    assert (lhs.shape == rhs.shape)
    assert (var.shape == rhs.shape)

    arr_l = np.empty(lhs.shape, dtype=object)
    arr_r = np.empty(lhs.shape, dtype=object)

    if len(lhs.shape) == 1:

        for i in range(lhs.shape[0]):
            arr_r[i] = var[i] <= rhs[i]
            arr_l[i] = lhs[i] <= var[i]

    elif len(lhs.shape) == 2:

        for i, j in product(range(lhs.shape[0]), range(lhs.shape[1])):
            arr_r[i, j] = var[i, j] <= rhs[i, j]
            arr_l[i, j] = lhs[i, j] <= var[i, j]

    lpAddRestrictions(problem=problem, arr=arr_l, name=name + '_l')
    lpAddRestrictions(problem=problem, arr=arr_r, name=name + '_r')

    return arr_l, arr_r


def lpMakeVars(name, shape, lower=None, upper=None):
    """
    Declares 1D of 2D array of LpVars
    :param name: name of the variable
    :param shape: tuple with the shape (i.e. (3), or (4, 6))
    :param lower: Lower bound array. Must meet the shape
    :param upper: Upper bound array. must meet the shape
    :return: array of LpVars
    """

    var = np.empty(shape, dtype=object)

    if type(shape) == int:

        if lower is None and upper is not None:

            for i in range(shape):
                var[i] = LpVariable(name + '_' + str(i), lowBound=None, upBound=upper[i])

        elif lower is not None and upper is None:

            if type(lower) == int:
                for i in range(shape):
                    var[i] = LpVariable(name + '_' + str(i), lowBound=lower, upBound=None)
            else:
                for i in range(shape):
                    var[i] = LpVariable(name + '_' + str(i), lowBound=lower[i], upBound=None)

        elif lower is None and upper is None:
            for i in range(shape):
                var[i] = LpVariable(name + '_' + str(i), lowBound=None, upBound=None)

        else:

            if type(lower) in (float, int) and type(upper) in (float, int):
                for i in range(shape):
                    var[i] = LpVariable(name + '_' + str(i), lowBound=lower, upBound=upper)

            elif type(lower) not in (float, int) and type(upper) in (float, int):
                for i in range(shape):
                    var[i] = LpVariable(name + '_' + str(i), lowBound=lower[i], upBound=upper)

            elif type(lower) in (float, int) and type(upper) not in (float, int):
                for i in range(shape):
                    var[i] = LpVariable(name + '_' + str(i), lowBound=lower, upBound=upper[i])

            elif type(lower) not in (float, int) and type(upper) not in (float, int):
                for i in range(shape):
                    var[i] = LpVariable(name + '_' + str(i), lowBound=lower[i], upBound=upper[i])


            else:
                raise Exception('Cannot handle the indices...')

    else:

        if len(shape) == 1:
            if lower is None and upper is not None:

                for i in range(shape[0]):
                    var[i] = LpVariable(name + '_' + str(i), lowBound=None, upBound=upper[i])

            elif lower is not None and upper is None:

                for i in range(shape[0]):
                    var[i] = LpVariable(name + '_' + str(i), lowBound=lower[i], upBound=None)

            else:

                for i in range(shape[0]):
                    var[i] = LpVariable(name + '_' + str(i), lowBound=lower[i], upBound=upper[i])

        elif len(shape) == 2:

            if lower is None and upper is not None:

                if type(upper) in [float, int]:
                    for i, j in product(range(shape[0]), range(shape[1])):
                        var[i, j] = LpVariable(name + '_' + str(i) + '_' + str(j), lowBound=None, upBound=upper)
                else:
                    for i, j in product(range(shape[0]), range(shape[1])):
                        var[i, j] = LpVariable(name + '_' + str(i) + '_' + str(j), lowBound=None, upBound=upper[i])

            elif lower is not None and upper is None:

                if type(lower) in [float, int]:
                    for i, j in product(range(shape[0]), range(shape[1])):
                        var[i, j] = LpVariable(name + '_' + str(i) + '_' + str(j), lowBound=lower, upBound=None)
                else:
                    for i, j in product(range(shape[0]), range(shape[1])):
                        var[i, j] = LpVariable(name + '_' + str(i) + '_' + str(j), lowBound=lower[i], upBound=None)

            else:

                if type(lower) in [float, int] and type(upper) in [float, int]:
                    for i, j in product(range(shape[0]), range(shape[1])):
                        var[i, j] = LpVariable(name + '_' + str(i) + '_' + str(j), lowBound=lower, upBound=upper)

                elif len(lower.shape) == 2 and len(lower.shape) == 2:
                    for i, j in product(range(shape[0]), range(shape[1])):
                        var[i, j] = LpVariable(name + '_' + str(i) + '_' + str(j), lowBound=lower[i, j], upBound=upper[i, j])

                elif len(lower.shape) == 1 and len(lower.shape) == 2:
                    for i, j in product(range(shape[0]), range(shape[1])):
                        var[i, j] = LpVariable(name + '_' + str(i) + '_' + str(j), lowBound=lower[i], upBound=upper[i, j])

                elif len(lower.shape) == 2 and len(lower.shape) == 1:
                    for i, j in product(range(shape[0]), range(shape[1])):
                        var[i, j] = LpVariable(name + '_' + str(i) + '_' + str(j), lowBound=lower[i, j], upBound=upper[i])

                elif len(lower.shape) == 1 and len(lower.shape) == 1:
                    for i, j in product(range(shape[0]), range(shape[1])):
                        var[i, j] = LpVariable(name + '_' + str(i) + '_' + str(j), lowBound=lower[i], upBound=upper[i])
        else:
            pass

    return var


def lpGet2D(arr, make_abs=False):
    """
    Extract values fro the 2D array of LP variables
    :param arr: 2D array of LP variables
    :param make_abs: substitute the result by its abs value
    :return: 2D numpy array
    """
    val = np.zeros(arr.shape)
    for i, j in product(range(val.shape[0]), range(val.shape[1])):
        val[i, j] = arr[i, j].value()
    if make_abs:
        val = np.abs(val)

    return val
