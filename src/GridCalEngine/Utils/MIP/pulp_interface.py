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

from typing import List, Union, Callable, Any
import subprocess
import GridCalEngine.Utils.ThirdParty.pulp as pulp
from GridCalEngine.Utils.ThirdParty.pulp import HiGHS, CPLEX_CMD
from GridCalEngine.Utils.ThirdParty.pulp.model.lp_objects import LpAffineExpression as LpExp
from GridCalEngine.Utils.ThirdParty.pulp.model.lp_objects import LpConstraint as LpCst
from GridCalEngine.Utils.ThirdParty.pulp.model.lp_objects import LpVariable as LpVar
from GridCalEngine.enumerations import MIPSolvers
from GridCalEngine.basic_structures import Logger


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


def get_available_mip_solvers() -> List[str]:
    """
    Get a list of candidate solvers
    :return:
    """
    solvers = pulp.listSolvers(onlyAvailable=True)

    solvers2 = list()
    for slv in solvers:
        if slv == 'SCIP_CMD':
            solvers2.append(MIPSolvers.SCIP.value)
        elif slv == 'CPLEX_CMD':
            solvers2.append(MIPSolvers.CPLEX.value)
        elif slv == 'GUROBI':
            solvers2.append(MIPSolvers.GUROBI.value)
        elif slv == 'XPRESS':
            solvers2.append(MIPSolvers.XPRESS.value)
        elif slv == 'HiGHS':
            solvers2.append(MIPSolvers.HIGHS.value)

    return solvers2


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


class LpModel:
    """
    LPModel implementation for PuLP
    """
    OPTIMAL = pulp.LpStatusOptimal
    INFINITY = 1e20
    originally_infeasible = False

    def __init__(self, solver_type: MIPSolvers):

        self.solver_type: MIPSolvers = solver_type

        self.model = pulp.LpProblem("myProblem", pulp.LpMinimize)

        self.relaxed_slacks = list()

        self.logger = Logger()

        if self.model is None:
            raise Exception("{} is not present".format(solver_type.value))

    def save_model(self, file_name: str = "ntc_opf_problem.lp") -> None:
        """
        Save problem in LP format
        :param file_name: name of the file (.lp or .mps supported)
        """
        # save the problem in LP format to debug
        if file_name.lower().endswith('.lp'):
            lp_content = self.model.writeLP(filename=file_name)
        elif file_name.lower().endswith('.mps'):
            lp_content = self.model.writeMPS(filename=file_name)
        else:
            raise Exception('Unsupported file format')

        # with open(file_name, "w") as f:
        # f.write(lp_content)

    def add_int(self, lb: int, ub: int, name: str = "") -> LpVar:
        """
        Make integer LP var
        :param lb: lower bound
        :param ub: upper bound
        :param name: name (optional)
        :return: LpVar
        """
        var = pulp.LpVariable(name=name, lowBound=lb, upBound=ub, cat=pulp.LpInteger)
        self.model.addVariable(var)
        return var

    def add_var(self, lb: float, ub: float, name: str = "") -> LpVar:
        """
        Make floating point LP var
        :param lb: lower bound
        :param ub: upper bound
        :param name: name (optional)
        :return: LpVar
        """
        var = pulp.LpVariable(name=name, lowBound=lb, upBound=ub, cat=pulp.LpContinuous)
        self.model.addVariable(var)
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
            return self.model.addConstraint(constraint=cst, name=name)

    @staticmethod
    def sum(cst) -> LpExp:
        """
        Add sum of the constraints to the model
        :param cst: constraint object (or general expression)
        :return: Constraint object
        """
        return pulp.lpSum(cst)

    def minimize(self, obj_function: LpExp):
        """
        Set the objective function with minimization sense
        :param obj_function: expression to minimize
        """
        self.model.setObjective(obj=obj_function)

    def get_solver(self, show_logs: bool = False):
        """

        :param show_logs:
        :return:
        """
        if self.solver_type == MIPSolvers.HIGHS:
            return HiGHS(mip=self.model.isMIP(), msg=show_logs)

        elif self.solver_type == MIPSolvers.SCIP:
            return pulp.getSolver('SCIP_CMD')

        elif self.solver_type == MIPSolvers.CPLEX:
            return CPLEX_CMD(mip=self.model.isMIP(), msg=show_logs)

        elif self.solver_type == MIPSolvers.GUROBI:
            return pulp.getSolver('GUROBI')

        elif self.solver_type == MIPSolvers.XPRESS:
            return pulp.getSolver('XPRESS')

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
            status = self.model.solve(solver=self.get_solver(show_logs=show_logs))
        except pulp.PulpSolverError as e:
            self.logger.add_error(msg=str(e), )
            # Retry with Highs
            status = self.model.solve(solver=HiGHS(mip=self.model.isMIP(), msg=show_logs))

        except subprocess.CalledProcessError as e:
            self.logger.add_error(msg=str(e), )
            # Retry with Highs
            status = self.model.solve(solver=HiGHS(mip=self.model.isMIP(), msg=show_logs))

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

                self.logger.add_error(msg="Base probrem could not be solved", value=self.status2string(status))

                # deep copy of the original model
                debug_model = self.model.deepcopy()

                # modify the original to detect the bad constraints
                slacks = list()
                debugging_f_obj = 0
                for i, (cst_name, cst) in enumerate(debug_model.constraints.items()):

                    # create a new slack var in the problem
                    sl = pulp.LpVariable(name=f'Relax_{cst_name}', lowBound=0, upBound=1e20, cat=pulp.LpContinuous)
                    debug_model.addVariable(sl)

                    # add the variable to the new objective function
                    debugging_f_obj += sl

                    # add the variable to the current constraint
                    cst += sl

                    # store for later
                    slacks.append((cst_name, sl))

                # set the objective function as the summation of the new slacks
                debug_model.setObjective(debugging_f_obj)

                if progress_text is not None:
                    progress_text(f"Solving debug model with {self.solver_type.value}...")

                # solve the debug model
                status_d = debug_model.solve(solver=self.get_solver(show_logs=show_logs))

                # clear the relaxed slacks list
                self.relaxed_slacks = list()

                if status_d == LpModel.OPTIMAL:

                    # pick the original objective function
                    cst_slack_map = list()
                    for i, (cst_name, sl) in enumerate(slacks):

                        # get the debugging slack value
                        val = sl.value()

                        if abs(val) > 1e-10:
                            # add the slack in the main model
                            sl2 = pulp.LpVariable(name=f'Relax_final_{cst_name}',
                                                  lowBound=0,
                                                  upBound=1e20,
                                                  cat=pulp.LpContinuous)
                            self.model.addVariable(sl2)
                            self.relaxed_slacks.append((i, sl2, 0.0))  # the 0.0 value will be read later

                            # add the slack to the original objective function
                            self.model.objective += sl2

                            # alter the matching constraint
                            self.model.constraints[cst_name] += sl2

                        # register the relation for later
                        cst_slack_map.append(cst_name)

                    # set the modified (original) objective function
                    self.model.setObjective(self.model.objective)

                    # at this point we can delete the debug model
                    del debug_model

                    if progress_text is not None:
                        progress_text(f"Solving relaxed model with {self.solver_type.value}...")

                    # solve the modified (original) model
                    status = self.model.solve(solver=self.get_solver(show_logs=show_logs))

                    if status == LpModel.OPTIMAL:

                        for i in range(len(self.relaxed_slacks)):
                            k, var, _ = self.relaxed_slacks[i]
                            val = var.value()
                            self.relaxed_slacks[i] = (k, var, val)

                            # logg this
                            if abs(val) > 1e-10:
                                self.logger.add_warning(
                                    msg="Relaxed problem",
                                    device=self.model.constraints[cst_slack_map[i]].name,
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
            val = x.pi
        else:
            raise Exception("Unrecognized type {}".format(x))

        if isinstance(val, float):
            return val
        else:
            return 0.0

    def status2string(self, stat: int) -> str:
        """
        Convert the PuLP status to a string
        :param stat:
        :return:
        """
        return pulp.LpStatus[stat]
