# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
This module abstracts the synthax of ORTOOLS out
so that in the future it can be exchanged with some
other solver interface easily
"""
from __future__ import annotations

from typing import List, Union, Tuple, Iterable, Callable
from ortools.linear_solver.python import model_builder
# Check required constructors during import so selected_interface can disable an incompatible backend.
from ortools.linear_solver.python.model_builder import Model, Solver
from ortools.linear_solver.python.model_builder import BoundedLinearExpression as LpCstBounded
from ortools.linear_solver.python.model_builder import LinearConstraint as LpCst
from ortools.linear_solver.python.model_builder import LinearExpr as LpExp
from ortools.linear_solver.python.model_builder import Variable as LpVar
from ortools.linear_solver.python.model_builder_helper import SolveStatus
from VeraGridEngine.enumerations import MIPSolvers
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.Utils.MIP.mip_interface_template import AbstractLpModel


# this avoids displaying all the solver logger information, should only be called once
# init.CppBridge.init_logging("")


def get_ortools_available_mip_solvers() -> List[str]:
    """
    Get a list of candidate solvers
    :return:
    """
    candidates = ['SCIP', 'CBC', 'CPLEX', 'GUROBI', 'XPRESS', 'HIGHS', 'GLOP', 'PDLP']
    res = list()
    for c in candidates:
        solver = model_builder.Solver(c)
        if solver is not None:
            if solver.solver_is_supported():
                res.append(c)
    return res


def get_solver_params_string(
        solver: str,
        relative_gap: float = 1e-10,
        abs_gap: float = 1e-10,
        primal_feasibility_tolerance: float = 1e-10,
        dual_feasibility_tolerance: float = 1e-10,
        optimality_tolerance: float = 1e-10,
        time_limit: float | None = None,
        verbose: bool = False
) -> str:
    """
    Returns a string of solver-specific parameters suitable for
    model_builder.Solver.SetSolverSpecificParametersAsString(...).
    :param solver: one of "SCIP", "CBC", "CPLEX", "GUROBI", "XPRESS", "HIGHS", "GLOP", "PDLP"
    :param relative_gap: relative optimality gap tolerance
    :param abs_gap: absolute optimality gap tolerance
    :param primal_feasibility_tolerance:
    :param dual_feasibility_tolerance:
    :param optimality_tolerance:
    :param time_limit: time limit in seconds (if supported)
    :param verbose: whether to enable verbose solver output
    :return: parameter string
    """
    s = ""
    if solver == "HIGHS":
        # https://ergo-code.github.io/HiGHS/dev/options/definitions/
        # also: https://www.gams.com/50/docs/S_HIGHS.html
        s += f"primal_residual_tolerance = {relative_gap}\n"
        s += f"mip_abs_gap = {abs_gap}\n"
        s += f"primal_feasibility_tolerance = {primal_feasibility_tolerance}\n"
        s += f"dual_feasibility_tolerance = {dual_feasibility_tolerance}\n"
        s += f"optimality_tolerance = {optimality_tolerance}\n"
        if time_limit is not None:
            s += f"time_limit = {time_limit}\n"
        if verbose:
            s += "log_to_console = true\n"

    elif solver == "CBC":
        s += f"RELATIVE_MIP_GAP = {relative_gap}\n"
        s += f"ABSOLUTE_MIP_GAP = {abs_gap}\n"
        if time_limit is not None:
            s += f"MAX_TIME_IN_SECONDS = {time_limit}\n"
        if verbose:
            s += "VERBOSE = 1\n"

    elif solver == "SCIP":
        s += f"limits/gap = {relative_gap}\n"
        s += f"limits/absgap = {abs_gap}\n"
        if time_limit is not None:
            s += f"limits/time = {time_limit}\n"
        if verbose:
            s += "display/verblevel = 4\n"
        s += f"numerics/feastol = {primal_feasibility_tolerance}\n"
        s += f"numerics/dualfeastol = {dual_feasibility_tolerance}\n"

    elif solver == "GLOP":
        # GLOP is for continuous LP; gap tolerances less relevant, focus on feasibility tolerance
        s += f"primal_tolerance = {primal_feasibility_tolerance}\n"
        s += f"dual_tolerance = {dual_feasibility_tolerance}\n"
        if time_limit is not None:
            s += f"time_limit = {time_limit}\n"
        if verbose:
            s += "log_to_console = true\n"

    elif solver == "CPLEX":
        # Use CPLEX parameter names in the string
        s += f"CPXPARAM_MIP_Tolerances_MIPGap = {relative_gap}\n"
        s += f"CPXPARAM_MIP_Tolerances_AbsMIPGap = {abs_gap}\n"
        if time_limit is not None:
            s += f"CPXPARAM_TimeLimit = {time_limit}\n"
        if verbose:
            s += "CPXPARAM_MIP_Display = 4\n"
        s += "CPXPARAM_Simplex_Tolerances_Feasibility = 1e-7\n"
        s += "CPXPARAM_Simplex_Tolerances_Optimality = 1e-7\n"

    elif solver == "GUROBI":
        # Use Gurobi parameter names in string
        s += f"MIPGap = {relative_gap}\n"
        s += f"MIPGapAbs = {abs_gap}\n"
        if time_limit is not None:
            s += f"TimeLimit = {time_limit}\n"
        if verbose:
            s += "OutputFlag = 1\n"
        s += "FeasibilityTol = 1e-8\n"
        s += "OptimalityTol = 1e-8\n"

    elif solver == "XPRESS":
        s += f"miprelstop = {relative_gap}\n"
        s += f"mipabsstop = {abs_gap}\n"
        if time_limit is not None:
            s += f"maxtime = {time_limit}\n"
        if verbose:
            s += "outputlog = 1\n"
        s += f"feastol = {primal_feasibility_tolerance}\n"
        s += "opt_tol = 1e-8\n"

    elif solver == "PDLP":
        s += f"relative_optimality_tolerance = {relative_gap}\n"
        s += f"absolute_optimality_tolerance = {abs_gap}\n"
        if time_limit is not None:
            s += f"time_limit = {time_limit}\n"
        if verbose:
            s += "log_to_console = true\n"
        s += "termination_check_frequency = 1000\n"

    else:
        s = ""

    return s


class OrToolsLpModel(AbstractLpModel):
    """
    LPModel implementation for ORTOOLS
    """
    __slots__ = (
        "solver",
        "model",
        "_var_names",
    )

    OPTIMAL = SolveStatus.OPTIMAL
    INFEASIBLE: SolveStatus = SolveStatus.INFEASIBLE
    NOT_SOLVED: SolveStatus = SolveStatus.NOT_SOLVED
    INFINITY = 1e20

    def __init__(self, solver_type: MIPSolvers):
        super().__init__(solver_type, name="OrTools")

        self.solver_type: MIPSolvers = solver_type

        self.solver = model_builder.Solver(solver_type.value)
        self.solver.set_solver_specific_parameters(
            get_solver_params_string(solver=solver_type.value)
        )

        if not self.solver.solver_is_supported():
            raise Exception(f"The solver {solver_type.value} is not supported")

        self.model = model_builder.Model()

        # self.model.SuppressOutput()

        self.logger = Logger()

        self.relaxed_slacks: List[Tuple[int, LpVar, float]] = list()

        self._var_names = set()

    @staticmethod
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

    def save_model(self, file_name: str = "ntc_opf_problem.lp") -> None:
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

    def model_as_string(self) -> str:
        """
        Model as string
        """
        lp_content = self.model.export_to_lp_string(obfuscate=False)
        return lp_content

    def add_int(self, lb: int, ub: int, name: str = "") -> LpVar:
        """
        Make integer LP var
        :param lb: lower bound
        :param ub: upper bound
        :param name: name (optional)
        :return: LpVar
        """
        return self.model.new_int_var(lb=lb, ub=ub, name=name)

    def add_bin(self, name: str = "") -> LpVar:
        """
        Make integer LP var
        :param name: name (optional)
        :return: LpVar
        """
        return self.model.new_int_var(lb=0, ub=1, name=name)

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

    def minimize(self, obj_function: Union[LpExp]) -> None:
        """
        Set the objective function with minimization sense
        :param obj_function: expression to minimize
        """
        self.model.minimize(linear_expr=obj_function)

    def pass_through_file(self, fname: str = "pass_thought_file.lp") -> model_builder.Model:
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

    def solve(self, robust=True, show_logs: bool = False,
              progress_text: Callable[[str], None] | None = None) -> int:
        """
        Solve the model
        :param robust: Relax the problem if infeasible
        :param show_logs
        :param progress_text:
        :return: integer value matching OPTIMAL or not
        """
        self.solver.enable_output(show_logs)

        if progress_text is not None:
            progress_text(f"Solving model with {self.solver_type.value}...")

        original_mdl = self.model
        status = self.solver.solve(original_mdl)

        # if it failed...
        if status != OrToolsLpModel.OPTIMAL:

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
                    sl = debug_model.new_var(lb=0.0, ub=self.INFINITY, is_integer=False,
                                             name=f'Slk_{i}_{cst.name}')

                    # add the variable to the new objective function
                    debugging_f_obj += sl

                    # add the variable to the current constraint
                    # cst.add_term(sl, 1.0)
                    if cst.lower_bound <= -self.INFINITY and cst.upper_bound < self.INFINITY:
                        # upper-bounded only  →  aᵗx ≤ ub  → relax upward
                        cst.add_term(sl, +1.0)

                    elif cst.lower_bound > -self.INFINITY and cst.upper_bound >= self.INFINITY:
                        # lower-bounded only  →  aᵗx ≥ lb  → relax downward
                        cst.add_term(sl, -1.0)

                    else:
                        # both bounds finite (equality or double-sided) → relax upward
                        cst.add_term(sl, +1.0)

                    # store for later
                    slacks.append(sl)

                # set the objective function as the summation of the new slacks
                debug_model.minimize(debugging_f_obj)

                # solve the debug model
                if progress_text is not None:
                    progress_text(f"Solving debug model with {self.solver_type.value}...")

                # we create a new solver to handle the debug model
                debug_solver = model_builder.Solver(self.solver_type.value)
                debug_solver.set_solver_specific_parameters(get_solver_params_string(...))
                status_d = debug_solver.solve(debug_model)
                # status_d = self.solver.solve(debug_model)

                # at this point we can delete the debug model
                del debug_model

                # clear the relaxed slacks list
                self.relaxed_slacks.clear()

                if status_d == OrToolsLpModel.OPTIMAL:

                    # pick the original objective function
                    main_f = original_mdl.objective_expression()

                    for i, sl in enumerate(slacks):

                        # get the debugging slack value
                        val = debug_solver.value(sl)

                        if val > 1e-10:
                            cst_name = original_mdl.linear_constraint_from_index(i).name

                            # add the slack in the main model
                            sl2 = original_mdl.new_var(0, self.INFINITY, is_integer=False,
                                                       name=f'Slk_rlx_{i}_{cst_name}')
                            self.relaxed_slacks.append((i, sl2, 0.0))  # the 0.0 value will be read later

                            # add the slack to the original objective function
                            main_f += sl2

                            # alter the matching constraint
                            original_mdl.linear_constraint_from_index(i).add_term(sl2, 1.0)

                    # set the modified (original) objective function
                    original_mdl.minimize(main_f)

                    # solve the modified (original) model
                    if progress_text is not None:
                        progress_text(f"Solving relaxed model with {self.solver_type.value}...")
                    status = self.solver.solve(original_mdl)

                    if status == OrToolsLpModel.OPTIMAL:

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
        return float(self.solver.objective_value)

    def is_mip(self):
        """
        Is this Model a MIP?
        :return: Bool
        """
        for var in self.model.get_variables():
            if var.Integer():
                return True

        return False

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
            # val = self.solver.value(x.expression)
            val = sum(self.solver.values(x.vars).values * x.coeffs)
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

    def status2string(self, stat: SolveStatus) -> str:
        """
        Convert ortools status to string
        :param stat:
        :return:
        """
        if stat == SolveStatus.OPTIMAL:
            return "optimal"
        if stat == SolveStatus.FEASIBLE:
            return "feasible"
        if stat == SolveStatus.INFEASIBLE:
            return "infeasible"
        if stat == SolveStatus.UNBOUNDED:
            return "unbounded"
        if stat == SolveStatus.ABNORMAL:
            return "abnormal"
        if stat == SolveStatus.MODEL_INVALID:
            return "model invalid"
        if stat == SolveStatus.NOT_SOLVED:
            return "not solved"
        if stat == SolveStatus.INVALID_SOLVER_PARAMETERS:
            return "invalid solver params"
        if stat == SolveStatus.MODEL_IS_VALID:
            return "model is valid"
        return 'unknown'
