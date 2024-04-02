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

"""
This module abstracts the synthax of ORTOOLS out
so that in the future it can be exchanged with some
other solver interface easily
"""

from typing import List, Union, Tuple, Iterable
import ortools.linear_solver.pywraplp as ort
from ortools.linear_solver.python import model_builder
from ortools.linear_solver.python.model_builder import BoundedLinearExpression as LpCstBounded
from ortools.linear_solver.python.model_builder import LinearConstraint as LpCst
from ortools.linear_solver.python.model_builder import LinearExpr as LpExp
from ortools.linear_solver.python.model_builder import Variable as LpVar
from ortools.linear_solver.python.model_builder import _Sum as LpSum
from ortools.init.python import init
from GridCalEngine.enumerations import MIPSolvers
from GridCalEngine.basic_structures import Logger


def get_available_mip_solvers() -> List[str]:
    """
    Get a list of candidate solvers
    :return:
    """
    init.CppBridge.init_logging("")  # this avoids displaying all the solver logger information
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
    if isinstance(var, LpVar):
        var.lower_bound = lb
        var.upper_bound = ub


class LpModel:
    """
    LPModel implementation for ORTOOLS
    """
    OPTIMAL = ort.Solver.OPTIMAL
    INFINITY = 1e20
    originally_infesible = False

    def __init__(self, solver_type: MIPSolvers):

        # self.model: ort.Solver = ort.Solver.CreateSolver(solver_type.value)

        self.solver = model_builder.Solver("scip")
        if not self.solver.solver_is_supported():
            raise Exception("The solver {} is not supported".format(solver_type.value))

        self.model = model_builder.Model()

        # self.model.SuppressOutput()

        self.logger = Logger()

        self.relaxed_slacks: List[Tuple[int, LpVar, float]] = list()

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

    def add_cst(self, cst: Union[LpCstBounded, LpExp, bool], name: str = "") -> Union[LpCst, int]:
        """
        Add constraint to the model
        :param cst: constraint object (or general expression)
        :param name: name of the constraint (optional)
        :return: Constraint object
        """
        if isinstance(cst, bool):
            return 0
        else:
            return self.model.add(ct=cst, name=name)

    @staticmethod
    def sum(cst: Union[LpExp, Iterable]) -> LpExp:
        """
        Add sum of the constraints to the model
        :param cst: constraint object (or general expression)
        :return: Constraint object
        """
        return sum(cst)

    def minimize(self, obj_function: Union[LpExp, LpSum]) -> None:
        """
        Set the objective function with minimization sense
        :param obj_function: expression to minimize
        """
        self.model.minimize(linear_expr=obj_function)

    def solve(self, robust=True) -> int:
        """
        Solve the model
        :param robust: Relax the problem if infeasible
        :return: integer value matching OPTIMAL or not
        """
        status = self.solver.solve(self.model)

        # if it failed...
        if status != LpModel.OPTIMAL:

            self.originally_infesible = True

            if robust:
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

                # deep copy of the original model
                debug_model = self.model.clone()

                # modify the original to detect the bad constraints
                slacks = list()
                debugging_f_obj = 0
                for i, cst in enumerate(debug_model.get_linear_constraints()):
                    # create a new slack var in the problem
                    sl = debug_model.new_var(0, 1e20, is_integer=False, name='Slackkk{}'.format(i))

                    # add the variable to the new objective function
                    debugging_f_obj += sl

                    # add the variable to the current constraint
                    cst.add_term(sl, 1.0)

                    # store for later
                    slacks.append(sl)

                # set the objective function as the summation of the new slacks
                debug_model.minimize(debugging_f_obj)

                # solve the debug model
                status_d = self.solver.solve(debug_model)

                # at this point we can delete the debug model
                del debug_model

                # clear the relaxed slacks list
                self.relaxed_slacks = list()

                if status_d == LpModel.OPTIMAL:

                    # pick the original objectve function
                    main_f = self.model.objective_expression()

                    for i, sl in enumerate(slacks):

                        # get the debugging slack value
                        val = self.solver.value(sl)

                        if val > 1e-10:
                            # add the slack in the main model
                            sl2 = self.model.new_var(0, 1e20, is_integer=False, name='Slackkk{}'.format(i))
                            self.relaxed_slacks.append((i, sl2, 0.0))  # the 0.0 value will be read later

                            # add the slack to the original objective function
                            main_f += sl2

                            # alter the matching constraint
                            self.model.linear_constraint_from_index(i).add_term(sl2, 1.0)

                            # logg this
                            # self.logger.add_warning("Relaxed problem",
                            #                         device=self.model.linear_constraint_from_index(i).name)

                    # set the modified (original) objective function
                    self.model.minimize(main_f)

                    # solve the modified (original) model
                    status = self.solver.solve(self.model)

                    if status == LpModel.OPTIMAL:

                        for i in range(len(self.relaxed_slacks)):
                            k, var, _ = self.relaxed_slacks[i]
                            val = self.solver.value(var)
                            self.relaxed_slacks[i] = (k, var, val)

                            # logg this
                            self.logger.add_warning("Relaxed problem",
                                                    device=self.model.linear_constraint_from_index(i).name,
                                                    value=val)

                else:
                    self.logger.add_warning("Unable to relax the model, the debug model failed")

            else:
                pass

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
        :return: result or zero
        """
        if isinstance(x, LpVar):
            val = self.solver.value(x)
        elif isinstance(x, LpExp):
            val = self.solver.value(x)
        elif isinstance(x, LpCstBounded):
            val = self.solver.value(x.expression)
        elif isinstance(x, float) or isinstance(x, int):
            return x
        else:
            raise Exception("Unrecognized type {}".format(x))

        if isinstance(val, float):
            return val
        else:
            return 0.0

    def get_dual_value(self, x: LpCst) -> float:
        """
        Get the dual value of a variable stored in a numpy array of objects
        :param x: constraint
        :return: result or zero
        """
        if isinstance(x, LpCst):
            val = self.solver.dual_value(x)
        else:
            raise Exception("Unrecognized type {}".format(x))

        if isinstance(val, float):
            return val
        else:
            return 0.0
