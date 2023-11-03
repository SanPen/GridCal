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
import ortools.linear_solver.pywraplp as ort
from ortools.linear_solver.pywraplp import LinearExpr as LpExp
from ortools.linear_solver.pywraplp import Variable as LpVar
from GridCalEngine.basic_structures import MIPSolvers


def get_lp_var_value(x: Union[float, LpVar, LpExp]) -> float:
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
    elif isinstance(x, ort.LinearExpr):
        return x.solution_value()
    else:
        return x



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


def set_var_bounds(var: LpVar, lb: float, ub: float):
    """
    Modify the bounds of a variable
    :param var: LpVar instance to modify
    :param lb: lower bound value
    :param ub: upper bound value
    """
    var.SetLb(lb)
    var.SetUb(ub)


class LpModel:
    """
    LPModel implementation for ORTOOLS
    """
    OPTIMAL = ort.Solver.OPTIMAL
    INFINITY = 1e20

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

    def add_int(self, lb: int, ub: int, name: str = "") -> LpVar:
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
