# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
This module abstracts the synthax of PuLP out
so that in the future it can be exchanged with some
other solver interface easily
"""
from __future__ import annotations

from numbers import Real
from typing import List, Union, Callable, Any
import platform
import subprocess
import pulp
from pulp import LpVariable as LpVar, LpConstraint as LpCst, LpAffineExpression as LpExp
from pulp import (HiGHS,
                  CPLEX_CMD, CPLEX_PY,
                  COIN_CMD,
                  COPT, COPT_CMD,
                  CUOPT,
                  GUROBI_CMD, GUROBI,
                  XPRESS_CMD, XPRESS_PY,
                  SCIP_CMD, SCIP_PY)
from pulp import LpContinuous, LpInteger
from VeraGridEngine.enumerations import MIPSolvers
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.Utils.MIP.mip_interface_template import AbstractLpModel


def make_highs_solver(mip: bool, show_logs: bool) -> HiGHS:
    """
    Build a PuLP HiGHS solver with conservative macOS settings.

    The macOS highspy wheel can crash in HiGHS worker/IPM code paths under
    Python 3.14. Linux keeps the default HiGHS settings.
    """
    if platform.system() == "Darwin":
        return HiGHS(
            mip=mip,
            msg=show_logs,
            threads=1,
            solver="simplex",
            parallel="off",
        )
    else:
        return HiGHS(mip=mip, msg=show_logs)


def get_optimal_status():
    """
    Return PuLP's optimal solve status for the installed API version.
    """
    solve_status = getattr(pulp, "LpSolveStatus", None)
    if solve_status is not None:
        return solve_status.Optimal

    return pulp.LpStatusOptimal


def get_infeasible_status():
    """
    Return PuLP's infeasible solve status for the installed API version.
    """
    solve_status = getattr(pulp, "LpSolveStatus", None)
    if solve_status is not None:
        return solve_status.Infeasible

    return pulp.LpStatusInfeasible


def get_not_solved_status():
    """
    Return PuLP's not-solved status for the installed API version.
    """
    solve_status = getattr(pulp, "LpSolveStatus", None)
    if solve_status is not None:
        return solve_status.NotSolved

    return pulp.LpStatusNotSolved


def normalize_solve_status(result: Any):
    """
    Convert PuLP 4 LpSolveStats results to their status enum.
    PuLP 3 already returns the integer status directly.
    """
    return getattr(result, "status", result)


def get_model_constraint_items(model: pulp.LpProblem) -> List[tuple[str, LpCst]]:
    """
    Return named constraints for both PuLP 3 and PuLP 4.
    """
    constraints = model.constraints
    if callable(constraints):
        return [(cst.name, cst) for cst in constraints()]

    return list(constraints.items())


def get_model_constraint_by_name(model: pulp.LpProblem, name: str) -> LpCst | None:
    """
    Return a constraint by name for both PuLP 3 and PuLP 4.
    """
    if hasattr(model, "get_constraint_by_name"):
        return model.get_constraint_by_name(name)

    return model.constraints.get(name)


def make_pulp_expression(value: LpExp | Real) -> LpExp:
    """
    Build an affine expression using the API supported by the installed PuLP.
    """
    if isinstance(value, Real):
        if hasattr(pulp.LpAffineExpression, "from_constant"):
            return pulp.LpAffineExpression.from_constant(value)

        return pulp.LpAffineExpression(value)

    return value


def get_lp_var_value(x: Union[float, LpVar]) -> float:
    """
    Get the value of a variable stored in a numpy array of objects
    :param x: soe object (it may be a LP var or a number)
    :return: result or previous numeric value
    """
    if isinstance(x, LpVar):
        return x.value()
    elif isinstance(x, LpExp):
        return x.value()
    elif isinstance(x, LpCst):
        return x.pi
    else:
        return x


def get_pulp_available_mip_solvers() -> List[str]:
    """
    Get a list of candidate solvers
    :return:
    """
    solvers = pulp.listSolvers(onlyAvailable=True)

    solvers2 = list()
    for slv in solvers:
        if slv == 'SCIP_CMD' or slv == 'SCIP_PY':
            solvers2.append(MIPSolvers.SCIP.value)
        elif slv == 'CPLEX_CMD' or slv == "CPLEX_PY":
            solvers2.append(MIPSolvers.CPLEX.value)
        elif slv == 'GUROBI_CMD' or slv == 'GUROBI':
            solvers2.append(MIPSolvers.GUROBI.value)
        elif slv == 'XPRESS' or slv == "XPRESS_PY":
            solvers2.append(MIPSolvers.XPRESS.value)
        elif slv == 'HiGHS':
            solvers2.append(MIPSolvers.HIGHS.value)
        elif slv == 'PULP_CBC_CMD' or slv == 'COIN_CMD':
            solvers2.append(MIPSolvers.CBC.value)
        elif slv == 'CUOPT':
            solvers2.append(MIPSolvers.CUOPT.value)
        elif slv == 'COPT_CMD' or slv == 'COPT':
            solvers2.append(MIPSolvers.COPT.value)
        else:
            print(f"PuLP solver not recognized {slv}")

    return solvers2


def add_pulp_variable(
        model: pulp.LpProblem,
        name: str,
        low_bound: float | int,
        up_bound: float | int,
        category: str,
) -> LpVar:
    """
    Add one PuLP variable using the newest model-owned API when available.

    :param model: PuLP problem that owns the variable.
    :param name: Variable name.
    :param low_bound: Lower variable bound.
    :param up_bound: Upper variable bound.
    :param category: PuLP variable category.
    :return: Created PuLP variable.
    """
    try:
        # PuLP 4 owns variable creation from the problem object, avoiding the
        # deprecated detached-variable constructor path.
        variable: LpVar = model.add_variable(name=name, lowBound=low_bound, upBound=up_bound, cat=category)
    except AttributeError:
        # PuLP 3 has no add_variable API, so construct the variable and attach
        # it immediately to keep the same ownership semantics.
        variable = pulp.LpVariable(name=name, lowBound=low_bound, upBound=up_bound, cat=category)
        model.addVariable(variable)

    return variable


class PulpLpModel(AbstractLpModel):
    """
    LPModel implementation for PuLP
    """
    __slots__ = ("model",)

    OPTIMAL = get_optimal_status()
    INFEASIBLE = get_infeasible_status()
    NOT_SOLVED = get_not_solved_status()
    INFINITY = 1e20

    def __init__(self, solver_type: MIPSolvers):
        """

        :param solver_type:
        """
        super().__init__(solver_type, name="PuLP")

        self.solver_type: MIPSolvers = solver_type

        self.model = pulp.LpProblem("myProblem", pulp.LpMinimize)

        self.relaxed_slacks = list()

        self.logger = Logger()

        if self.model is None:
            raise Exception("{} is not present".format(solver_type.value))

    @staticmethod
    def set_var_bounds(var: LpVar, lb: float, ub: float):
        """
        Modify the bounds of a variable
        :param var: LpVar instance to modify
        :param lb: lower bound value
        :param ub: upper bound value
        """
        if isinstance(var, LpVar):
            var.upBound = ub
            var.lowBound = lb

    def save_model(self, file_name: str = "ntc_opf_problem.lp") -> None:
        """
        Save problem in LP format
        :param file_name: name of the file (.lp or .mps supported)
        """
        # save the problem in LP format to debug
        if file_name.lower().endswith('.lp'):
            lp_content = self.model.writeLP(filename=file_name, max_length=10000)
        elif file_name.lower().endswith('.mps'):
            lp_content = self.model.writeMPS(filename=file_name)
        else:
            raise Exception('Unsupported file format')

    def add_int(self, lb: int, ub: int, name: str = "") -> LpVar:
        """
        Make integer LP var
        :param lb: lower bound
        :param ub: upper bound
        :param name: name (optional)
        :return: LpVar
        """
        var = add_pulp_variable(model=self.model, name=name, low_bound=lb, up_bound=ub, category=pulp.LpInteger)
        return var

    def add_bin(self, name: str = "") -> LpVar:
        """
        Make integer LP var
        :param name: name (optional)
        :return: LpVar
        """
        var = add_pulp_variable(model=self.model, name=name, low_bound=0, up_bound=1, category=pulp.LpInteger)
        return var

    def add_var(self, lb: float, ub: float, name: str = "") -> LpVar:
        """
        Make floating point LP var
        :param lb: lower bound
        :param ub: upper bound
        :param name: name (optional)
        :return: LpVar
        """
        var = add_pulp_variable(model=self.model, name=name, low_bound=lb, up_bound=ub, category=pulp.LpContinuous)
        return var

    def add_cst(self, cst: LpCst | bool, name: str = "") -> Union[LpCst, int]:
        """
        Add constraint to the model
        :param cst: constraint object (or general expression)
        :param name: name of the constraint (optional)
        :return: Constraint object
        """
        if isinstance(cst, bool):
            return 0
        else:
            self.model.addConstraint(constraint=cst, name=name)
            cst_name = name or getattr(cst, "name", "")
            added_cst = get_model_constraint_by_name(self.model, cst_name) if cst_name else None
            return added_cst if added_cst is not None else cst

    @staticmethod
    def sum(cst) -> LpExp:
        """
        Add sum of the constraints to the model
        :param cst: constraint object (or general expression)
        :return: Constraint object
        """
        return pulp.lpSum(cst)

    def minimize(self, obj_function: LpExp | Real) -> None:
        """
        Set the objective function with minimization sense
        :param obj_function: expression to minimize
        :return: None
        """
        self.model.setObjective(obj=make_pulp_expression(obj_function))

    def get_solver(self, show_logs: bool = False):
        """

        :param show_logs:
        :return:
        """
        if self.solver_type == MIPSolvers.HIGHS:
            return make_highs_solver(mip=self.model.isMIP(), show_logs=show_logs)

        elif self.solver_type == MIPSolvers.SCIP:

            solver = SCIP_CMD(mip=self.model.isMIP(), msg=show_logs)
            if solver.available() is not True:
                solver = SCIP_PY(mip=self.model.isMIP(), msg=show_logs)
            else:
                self.logger.add_error("No version of SCIP (cmd or python package was available)")
                solver = make_highs_solver(mip=self.model.isMIP(), show_logs=show_logs)
            return solver

        elif self.solver_type == MIPSolvers.CBC:
            bundled_cbc = getattr(pulp, "PULP_CBC_CMD", None)
            if bundled_cbc is not None:
                solver = bundled_cbc(mip=self.model.isMIP(), msg=show_logs)
                if solver.available() is not None:
                    return solver
                else:
                    pass

            solver = COIN_CMD(mip=self.model.isMIP(), msg=show_logs)
            if solver.available() is not None:
                return solver
            else:
                raise pulp.PulpSolverError("CBC was selected, but no CBC executable is available")

        elif self.solver_type == MIPSolvers.CUOPT:
            return CUOPT(mip=self.model.isMIP(), msg=show_logs)

        elif self.solver_type == MIPSolvers.CPLEX:
            solver = CPLEX_CMD(mip=self.model.isMIP(), msg=show_logs)
            if solver.available() is not True:
                solver = CPLEX_PY(mip=self.model.isMIP(), msg=show_logs)
            else:
                self.logger.add_error("No version of Cplex (cmd or python package was available)")
                solver = make_highs_solver(mip=self.model.isMIP(), show_logs=show_logs)
            return solver

        elif self.solver_type == MIPSolvers.GUROBI:
            solver = GUROBI(mip=self.model.isMIP(), msg=show_logs)
            if solver.available() is not True:
                solver = GUROBI_CMD(mip=self.model.isMIP(), msg=show_logs)
            else:
                self.logger.add_error("No version of Gurobi (cmd or python package was available)")
                solver = make_highs_solver(mip=self.model.isMIP(), show_logs=show_logs)
            return solver

        elif self.solver_type == MIPSolvers.XPRESS:
            solver = XPRESS_CMD(mip=self.model.isMIP(), msg=show_logs)
            if solver.available() is not True:
                solver = XPRESS_PY(mip=self.model.isMIP(), msg=show_logs)
            else:
                self.logger.add_error("No version of Xpress (cmd or python package was available)")
                solver = make_highs_solver(mip=self.model.isMIP(), show_logs=show_logs)
            return solver

        elif self.solver_type == MIPSolvers.COPT:
            solver = COPT_CMD(mip=self.model.isMIP(), msg=show_logs)
            if solver.available() is not True:
                solver = COPT(mip=self.model.isMIP(), msg=show_logs)
            else:
                self.logger.add_error("No version of Copt (cmd or python package was available)")
                solver = make_highs_solver(mip=self.model.isMIP(), show_logs=show_logs)
            return solver

        else:
            raise Exception('PuLP Unsupported MIP solver ' + self.solver_type.value)

    def solve(self, robust: bool = False, show_logs: bool = False,
              progress_text: Callable[[str], None] | None = None) -> int:
        """
        Solve the model
        :param robust: In this interface, this is useless
        :param show_logs: In this interface, this is useless
        :param progress_text: progress function pointer
        :return:
        """
        if progress_text is not None:
            progress_text(f"Solving model with {self.solver_type.value}...")

        # solve the model
        try:
            solver = self.get_solver(show_logs=show_logs)
            self.logger.add_info(msg="PuLP solver", value=solver.__class__.__name__)
            status = normalize_solve_status(self.model.solve(solver=solver))
        except pulp.PulpSolverError as e:
            self.logger.add_error(msg=str(e), )
            status = self.NOT_SOLVED

        except subprocess.CalledProcessError as e:
            self.logger.add_error(msg=str(e), )
            status = self.NOT_SOLVED
        except IndexError as e:
            print("Index error:")
            print(e)
            status = 1

        if status != self.OPTIMAL:
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

                self.logger.add_error(msg="Base problem could not be solved", value=self.status2string(status))

                # deep copy of the original model
                debug_model = self.model.deepcopy()

                # modify the original to detect the bad constraints
                slacks = list()
                debugging_f_obj = 0
                for i, (cst_name, cst) in enumerate(get_model_constraint_items(debug_model)):
                    # create a new slack var in the problem
                    sl = add_pulp_variable(
                        model=debug_model,
                        name=f'Relax_{cst_name}',
                        low_bound=0,
                        up_bound=1e20,
                        category=pulp.LpContinuous,
                    )

                    # add the variable to the new objective function
                    debugging_f_obj += sl

                    # add the variable to the current constraint
                    if cst.sense == pulp.LpConstraintLE:
                        cst += sl
                    elif cst.sense == pulp.LpConstraintGE:
                        cst -= sl
                    else:  # equality
                        cst += sl

                    # store for later
                    slacks.append((cst_name, sl))

                # set the objective function as the summation of the new slacks
                debug_model.setObjective(debugging_f_obj)

                if progress_text is not None:
                    progress_text(f"Solving debug model with {self.solver_type.value}...")

                # solve the debug model
                status_d = normalize_solve_status(debug_model.solve(solver=self.get_solver(show_logs=show_logs)))

                # clear the relaxed slacks list
                self.relaxed_slacks = list()

                if status_d == PulpLpModel.OPTIMAL:

                    # pick the original objective function
                    cst_slack_map = list()
                    for i, (cst_name, sl) in enumerate(slacks):

                        # get the debugging slack value
                        val = sl.value()

                        if abs(val) > 1e-10:
                            # add the slack in the main model
                            sl2 = add_pulp_variable(
                                model=self.model,
                                name=f'Relax_final_{cst_name}',
                                low_bound=0,
                                up_bound=1e20,
                                category=pulp.LpContinuous,
                            )
                            self.relaxed_slacks.append((i, sl2, 0.0))  # the 0.0 value will be read later

                            # add the slack to the original objective function
                            self.model.objective += sl2

                            # alter the matching constraint
                            cst = get_model_constraint_by_name(self.model, cst_name)
                            if cst is not None:
                                cst += sl2

                        # register the relation for later
                        cst_slack_map.append(cst_name)

                    # set the modified (original) objective function
                    self.model.setObjective(self.model.objective)

                    # at this point we can delete_with_dialogue the debug model
                    del debug_model

                    if progress_text is not None:
                        progress_text(f"Solving relaxed model with {self.solver_type.value}...")

                    # solve the modified (original) model
                    status = normalize_solve_status(self.model.solve(solver=self.get_solver(show_logs=show_logs)))

                    if status == PulpLpModel.OPTIMAL:

                        for i in range(len(self.relaxed_slacks)):
                            k, var, _ = self.relaxed_slacks[i]
                            val = var.value()
                            self.relaxed_slacks[i] = (k, var, val)

                            # logg this
                            if abs(val) > 1e-10:
                                relaxed_cst = get_model_constraint_by_name(self.model, cst_slack_map[i])
                                self.logger.add_warning(
                                    msg="Relaxed problem",
                                    device=relaxed_cst.name if relaxed_cst is not None else cst_slack_map[i],
                                    value=val
                                )

                    else:
                        self.logger.add_warning(msg="Relaxed probrem is not optimal :(")

                else:
                    self.logger.add_warning("Unable to relax the model, the debug model failed :(")

        return status

    def fobj_value(self) -> float:
        """
        Get the objective function value
        :return:
        """
        return self.model.objective.value()

    def is_mip(self):
        """
        Is this odel a MIP?
        :return:
        """
        return self.model.isMIP()

    @staticmethod
    def get_value(x: Union[float, int, LpVar, LpExp, LpCst, Any]) -> float:
        """
        Get the value of a variable stored in a numpy array of objects
        :param x: solver object (it may be a LP var or a number)
        :return: result or zero
        """
        if isinstance(x, LpVar):
            val = x.value()
        elif isinstance(x, LpExp):
            val = x.value()
        elif isinstance(x, LpCst):
            val = x.values()
        elif isinstance(x, float) or isinstance(x, int):
            return x
        else:
            raise Exception("Unrecognized type {}".format(x))

        if isinstance(val, float):
            return val
        else:
            return 0.0

    @staticmethod
    def get_dual_value(x: LpCst) -> float:
        """
        Get the dual value of a variable stored in a numpy array of objects
        :param x: constraint
        :return: result or zero
        """
        if x is None:
            return 0.0

        if isinstance(x, LpCst):
            # Unsolved models and integer solves may have no row dual.
            return float(x.pi) if x.pi is not None else 0.0
        elif isinstance(x, float):
            return x
        else:
            return 0.0

    def status2string(self, stat: int) -> str:
        """
        Convert the PuLP status to a string
        :param stat:
        :return:
        """
        if hasattr(stat, "status_str"):
            return stat.status_str

        stat = normalize_solve_status(stat)
        if hasattr(stat, "name"):
            return stat.name

        lp_status = getattr(pulp, "LpStatus", None)
        if lp_status is not None:
            return lp_status[stat]

        return pulp.LpSolveStatus(stat).name

    def model_as_string(self) -> str:
        """
        Return the LP representation
        :return: string
        """
        lp = self.model
        max_length = 1000000
        mip = True
        writeSOS = True

        f = ""
        f += "\\* " + lp.name + " *\\\n"
        if lp.sense == 1:
            f += "Minimize\n"
        else:
            f += "Maximize\n"
        wasNone, objectiveDummyVar = lp.fixObjective()
        assert lp.objective is not None
        objName = lp.objective.name
        if not objName:
            objName = "OBJ"
        f += lp.objective.asCplexLpAffineExpression(objName, include_constant=False)
        f += "Subject To\n"
        constraints = dict(get_model_constraint_items(lp))
        ks = sorted(constraints.keys())
        dummyWritten = False
        for k in ks:
            constraint = constraints[k]
            if not list(constraint.keys()):
                # empty constraint add the dummyVar
                dummyVar = lp.get_dummyVar()
                constraint += dummyVar
                # set this dummyvar to zero so infeasible problems are not made feasible
                if not dummyWritten:
                    f += (dummyVar == 0.0).asCplexLpConstraint("_dummy")
                    dummyWritten = True
            f += constraint.asCplexLpConstraint(k)
        # check if any names are longer than 100 characters
        lp.checkLengthVars(max_length)
        vs = lp.variables()
        # check for repeated names
        lp.checkDuplicateVars()
        # Bounds on non-"positive" variables
        # Note: XPRESS and CPLEX do not interpret integer variables without
        # explicit bounds
        if mip:
            vg = [
                v
                for v in vs
                if not (v.isPositive() and v.cat == LpContinuous) and not v.isBinary()
            ]
        else:
            vg = [v for v in vs if not v.isPositive()]
        if vg:
            f += "Bounds\n"
            for v in vg:
                f += f" {v.asCplexLpVariable()}\n"
        # Integer non-binary variables
        if mip:
            vg = [v for v in vs if v.cat == LpInteger and not v.isBinary()]
            if vg:
                f += "Generals\n"
                for v in vg:
                    f += f"{v.name}\n"
            # Binary variables
            vg = [v for v in vs if v.isBinary()]
            if vg:
                f += "Binaries\n"
                for v in vg:
                    f += f"{v.name}\n"
        # Special Ordered Sets
        sos1 = getattr(lp, "sos1", None)
        sos2 = getattr(lp, "sos2", None)
        if writeSOS and (sos1 or sos2):
            f += "SOS\n"
            if sos1:
                for sos in sos1.values():
                    f += "S1:: \n"
                    for v, val in sos.items():
                        f += f" {v.name}: {val:.12g}\n"
            if sos2:
                for sos in sos2.values():
                    f += "S2:: \n"
                    for v, val in sos.items():
                        f += f" {v.name}: {val:.12g}\n"
        f += "End\n"
        lp.restoreObjective(wasNone, objectiveDummyVar)

        return f
