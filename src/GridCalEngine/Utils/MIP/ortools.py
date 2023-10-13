# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
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
This module abstracts the synthax of ORTOOLS out
so that in the future it can be exchanged with some
other solver interface easily
"""

from typing import List, Union
import numpy as np
from itertools import product
from scipy.sparse import csc_matrix
import ortools.linear_solver.pywraplp as ort
from ortools.linear_solver.pywraplp import LinearExpr as LpExp  # imported elsewhere do not delete
from ortools.linear_solver.pywraplp import Variable as LpVar  # imported elsewhere do not delete
# from ortools.linear_solver.pywraplp import Solver as LpModel  # imported elsewhere do not delete
from GridCalEngine.basic_structures import MIPSolvers


def get_lp_var_value(x: Union[float, ort.Variable]) -> float:
    """
    Get the value of a variable stored in a numpy array of objects
    :param x: soe object (it may be a LP var or a number)
    :return: result or previous numeric value
    """
    if isinstance(x, ort.Variable):
        return x.solution_value()
    elif isinstance(x, ort.SumArray):
        return x.solution_value()
    elif isinstance(x, ort.Constraint):
        return x.dual_value()
    else:
        return x


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
    if mat.format != 'csc':
        raise Exception("Sparse matrix must be in CSC format")

    if len(arr.shape) == 1:
        """
        Uni-dimensional sparse matrix - vector product
        """
        res = np.zeros(n_rows, dtype=arr.dtype)
        for i in range(n_cols):
            for ii in range(mat.indptr[i], mat.indptr[i + 1]):
                j = mat.indices[ii]  # row index
                res[j] += mat.data[ii] * arr[i]  # C.data[ii] is equivalent to C[i, j]
    else:
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


def get_available_mip_solvers() -> List[str]:
    """
    Get a list of candidate solvers
    :return:
    """
    candidates = ['SCIP', 'CBC', 'CPLEX', 'GUROBI', 'XPRESS', 'HIGHS', 'GLOP']
    res = list()
    for c in candidates:
        solver = ort.Solver.CreateSolver(c)
        if solver is not None:
            res.append(c)
    return res


class LpModel:
    """
    LPModel implementation for ORTOOLS
    """
    OPTIMAL = ort.Solver.OPTIMAL

    def __init__(self, solver_type: MIPSolvers):

        self.model: ort.Solver = ort.Solver.CreateSolver(solver_type.value)

        if self.model is None:
            raise Exception("{} is not present".format(solver_type.value))

        self.model.SuppressOutput()

    def save_model(self, file_name="ntc_opf_problem.lp"):
        """
        Save problem in LP format
        :param file_name: name of the file (.lp or .mps supported)
        """
        # save the problem in LP format to debug
        if file_name.lower().endswith('.lp'):
            lp_content = self.model.ExportModelAsLpFormat(obfuscated=False)
        elif file_name.lower().endswith('.mps'):
            lp_content = self.model.ExportModelAsMpsFormat(obfuscated=False, fixed_format=True)
        else:
            raise Exception('Unsupported file format')

        with open(file_name, "w") as f:
            f.write(lp_content)

    def make_int(self, lb: int, ub: int, name: str = "") -> LpVar:
        """
        Make integer LP var
        :param lb: lower bound
        :param ub: upper bound
        :param name: name (optional)
        :return: LpVar
        """
        return self.model.IntVar(lb=lb, ub=ub, name=name)

    def add_var(self, lb: float, ub: float, name: str = "") -> LpVar:
        """
        Make floating point LP var
        :param lb: lower bound
        :param ub: upper bound
        :param name: name (optional)
        :return: LpVar
        """
        return self.model.NumVar(lb=lb, ub=ub, name=name)

    def add_cst(self, cst, name: str = "") -> LpExp:
        """
        Add constraint to the model
        :param cst: constraint object (or general expression)
        :param name: name of the constraint (optional)
        :return: Constraint object
        """
        return self.model.Add(constraint=cst, name=name)

    def sum(self, cst) -> LpExp:
        """
        Add sum of the constraints to the model
        :param cst: constraint object (or general expression)
        :return: Constraint object
        """
        return self.model.Sum(cst)

    def minimize(self, obj_function):
        """
        Set the objective function with minimization sense
        :param obj_function: expression to minimize
        """
        self.model.Minimize(expr=obj_function)

    def solve(self) -> int:
        """
        Solve the model
        :return:
        """
        return self.model.Solve()

    def fobj_value(self) -> float:
        """
        Get the objective function value
        :return:
        """
        return self.model.Objective().Value()

    def is_mip(self):
        """
        Is this odel a MIP?
        :return:
        """
        return [var.Integer() for var in self.model.variables()]
