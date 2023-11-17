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
from ortools.linear_solver.python import model_builder
from ortools.linear_solver.python.model_builder import BoundedLinearExpression as LpCstBounded
from ortools.linear_solver.python.model_builder import LinearConstraint as LpCst
from ortools.linear_solver.python.model_builder import LinearExpr as LpExp
from ortools.linear_solver.python.model_builder import Variable as LpVar
from GridCalEngine.basic_structures import MIPSolvers, Logger





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
    var.lower_bound = lb
    var.upper_bound = ub


class LpModel:
    """
    LPModel implementation for ORTOOLS
    """
    OPTIMAL = ort.Solver.OPTIMAL
    INFINITY = 1e20

    def __init__(self, solver_type: MIPSolvers):

        # self.model: ort.Solver = ort.Solver.CreateSolver(solver_type.value)

        self.solver = model_builder.Solver("scip")
        if not self.solver.solver_is_supported():
            raise Exception("The solver {} is not supported".format(solver_type.value))

        self.model = model_builder.Model()

        # self.model.SuppressOutput()

        self.logger = Logger()

    def save_model(self, file_name="ntc_opf_problem.lp"):
        """
        Save problem in LP format
        :param file_name: name of the file (.lp or .mps supported)
        """
        # save the problem in LP format to debug
        if file_name.lower().endswith('.lp'):
            lp_content = self.model.export_to_lp_string(obfuscate=False)
        elif file_name.lower().endswith('.mps'):
            lp_content = self.model.export_to_mps_string(obfuscate=False)
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
        return self.model.new_int_var(lb=lb, ub=ub, name=name)

    def add_var(self, lb: float, ub: float, name: str = "") -> LpVar:
        """
        Make floating point LP var
        :param lb: lower bound
        :param ub: upper bound
        :param name: name (optional)
        :return: LpVar
        """
        return self.model.new_var(lb=lb, ub=ub, is_integer=False, name=name)

    def add_cst(self, cst: LpCst, name: str = "") -> Union[LpExp, float]:
        """
        Add constraint to the model
        :param cst: constraint object (or general expression)
        :param name: name of the constraint (optional)
        :return: Constraint object
        """

        try:
            return self.model.add(ct=cst, name=name)
        except AttributeError:
            self.logger.add_warning("Kirchoff 0=0", name, comment='Cannot enforce Pcalc zero=Pset zero')
            return 0

    def sum(self, cst: LpExp) -> LpExp:
        """
        Add sum of the constraints to the model
        :param cst: constraint object (or general expression)
        :return: Constraint object
        """
        return sum(cst)

    def minimize(self, obj_function: LpExp) -> None:
        """
        Set the objective function with minimization sense
        :param obj_function: expression to minimize
        """
        self.model.minimize(linear_expr=obj_function)

    def solve(self) -> int:
        """
        Solve the model
        :return:
        """
        return self.solver.solve(self.model)

    def robust_solve(self) -> int:
        """

        :return:
        """
        status = self.solver.solve(self.model)

        # if it failed...
        if status != LpModel.OPTIMAL:

            """
            We are going to create a deep clone of the model,
            add a slack variable to each constraint and minimize
            the sum of the newly added slack vars.
            This LP model will be always optimal.
            After the solution, we inspect the slack vars added
            if any of those is > 0, then the constraint where it
            was added needs "slacking", therefore we add that slack
            to the original model, and add the slack to the original 
            objective function. This way we relax the model while
            bringing it to optimality.
            """
            model_copy = self.model.clone()

            for cst in model_copy.get_linear_constraints():
                print()

        return status

    def fobj_value(self) -> float:
        """
        Get the objective function value
        :return:
        """
        return self.solver.objective_value

    def is_mip(self):
        """
        Is this odel a MIP?
        :return:
        """

        return [var.Integer() for var in self.model.get_variables()]

    def get_value(self, x: Union[float, int, LpVar, LpExp, LpCst, LpCstBounded]) -> float:
        """
        Get the value of a variable stored in a numpy array of objects
        :param x: solver object (it may be a LP var or a number)
        :return: result or previous numeric value
        """
        if isinstance(x, LpVar):
            return self.solver.value(x)
        elif isinstance(x, LpExp):
            return self.solver.value(x)
        elif isinstance(x, LpCst):
            return self.solver.dual_value(x)
        elif isinstance(x, LpCstBounded):
            return self.solver.value(x.expression)
        elif isinstance(x, float) or isinstance(x, int):
            return x
        else:
            raise Exception("Unrecognized type {}".format(x))

    def get_dual_value(self, x: LpCst) -> float:
        """
        Get the value of a variable stored in a numpy array of objects
        :param x: constraint
        :return: result or previous numeric value
        """
        if isinstance(x, LpCst):
            return self.solver.dual_value(x)
        else:
            raise Exception("Unrecognized type {}".format(x))
