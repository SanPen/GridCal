# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

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
# from ortools.init.python import init
from GridCalEngine.enumerations import MIPSolvers
from GridCalEngine.basic_structures import Logger


# this avoids displaying all the solver logger information, should only be called once
# init.CppBridge.init_logging("")


def get_available_mip_solvers() -> List[str]:
    """
    Get a list of candidate solvers
    :return:
    """
    candidates = ['SCIP', 'CBC', 'CPLEX', 'GUROBI', 'XPRESS', 'HIGHS', 'GLOP', 'PDLP']
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
    originally_infeasible = False

    def __init__(self, solver_type: MIPSolvers):

        # self.model: ort.Solver = ort.Solver.CreateSolver(solver_type.value)

        self.solver = model_builder.Solver(solver_type.value)
        if not self.solver.solver_is_supported():
            raise Exception(f"The solver {solver_type.value} is not supported")

        self.model = model_builder.Model()

        # self.model.SuppressOutput()

        self.logger = Logger()

        self.relaxed_slacks: List[Tuple[int, LpVar, float]] = list()

        self._var_names = set()

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
        if name in self._var_names:
            raise Exception(f'Variable name already defined: {name}')
        else:
            self._var_names.add(name)

        return self.model.new_var(lb=lb, ub=ub, is_integer=False, name=name)

    def add_cst(self, cst: Union[LpCstBounded, LpExp, bool], name: str = "") -> Union[LpCst, int]:
        """
        Add constraint to the model
        :param cst: constraint object (or general expression)
        :param name: name of the constraint (optional)
        :return: Constraint object
        """
        if name in self._var_names:
            raise Exception(f'Constraint name already defined: {name}')
        else:
            self._var_names.add(name)

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

    def pass_through_file(self, fname="pass_thought_file.lp"):
        """

        :param fname:
        :return:
        """
        self.save_model(fname)

        mdl = model_builder.Model()

        if fname.lower().endswith('.lp'):
            mdl.import_from_lp_file(fname)
        elif fname.lower().endswith('.mps'):
            mdl.import_from_mps_file(fname)
        else:
            raise Exception('Unsupported file format')
        return mdl

    def solve(self, robust=True) -> int:
        """
        Solve the model
        :param robust: Relax the problem if infeasible
        :return: integer value matching OPTIMAL or not
        """

        print("SOLVING ORIGINAL MODEL ------------------------------")
        # original_mdl = self.model
        original_mdl = self.pass_through_file(fname="pass_thought_file.mps")
        status = self.solver.solve(original_mdl)

        # if it failed...
        if status != LpModel.OPTIMAL:

            self.originally_infeasible = True

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
                debug_model = original_mdl.clone()

                # modify the original to detect the bad constraints
                slacks = list()
                debugging_f_obj = 0
                for i, cst in enumerate(debug_model.get_linear_constraints()):
                    # create a new slack var in the problem
                    sl = debug_model.new_var(lb=0.0, ub=1e20, is_integer=False,
                                             name=f'Slk_{i}_{cst.name}')

                    # add the variable to the new objective function
                    debugging_f_obj += sl

                    # add the variable to the current constraint
                    cst.add_term(sl, 1.0)

                    # store for later
                    slacks.append(sl)

                # set the objective function as the summation of the new slacks
                debug_model.minimize(debugging_f_obj)

                # solve the debug model
                print("SOLVING DEBUG MODEL ------------------------------")
                status_d = self.solver.solve(debug_model)

                # at this point we can delete the debug model
                del debug_model

                # clear the relaxed slacks list
                self.relaxed_slacks.clear()

                if status_d == LpModel.OPTIMAL:

                    # pick the original objective function
                    main_f = original_mdl.objective_expression()

                    for i, sl in enumerate(slacks):

                        # get the debugging slack value
                        val = self.solver.value(sl)

                        if val > 1e-10:
                            cst_name = original_mdl.linear_constraint_from_index(i).name

                            # add the slack in the main model
                            sl2 = original_mdl.new_var(0, 1e20, is_integer=False,
                                                       name=f'Slk_rlx_{i}_{cst_name}')
                            self.relaxed_slacks.append((i, sl2, 0.0))  # the 0.0 value will be read later

                            # add the slack to the original objective function
                            main_f += sl2

                            # alter the matching constraint
                            original_mdl.linear_constraint_from_index(i).add_term(sl2, 1.0)

                    # set the modified (original) objective function
                    original_mdl.minimize(main_f)

                    # solve the modified (original) model
                    print("SOLVING RELAXED MODEL ------------------------------")
                    status = self.solver.solve(original_mdl)

                    if status == LpModel.OPTIMAL:

                        for i in range(len(self.relaxed_slacks)):
                            k, var, _ = self.relaxed_slacks[i]
                            val = self.solver.value(var)
                            self.relaxed_slacks[i] = (k, var, val)

                            # logg this
                            self.logger.add_warning("Relaxed problem",
                                                    device=original_mdl.linear_constraint_from_index(i).name,
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
