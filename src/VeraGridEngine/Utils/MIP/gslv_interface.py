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
from pygslv import LpModel as gslvLpModel, LpResult, LpCst, LpVar, LpExp
from VeraGridEngine.enumerations import MIPSolvers
from VeraGridEngine.basic_structures import Logger


def get_available_mip_solvers() -> List[str]:
    """
    Get a list of candidate solvers
    :return:
    """
    # solvers = pulp.listSolvers(onlyAvailable=True)
    #
    # solvers2 = list()
    # for slv in solvers:
    #     if slv == 'SCIP_CMD':
    #         solvers2.append(MIPSolvers.SCIP.value)
    #     elif slv == 'CPLEX_CMD':
    #         solvers2.append(MIPSolvers.CPLEX.value)
    #     elif slv == 'GUROBI':
    #         solvers2.append(MIPSolvers.GUROBI.value)
    #     elif slv == 'XPRESS':
    #         solvers2.append(MIPSolvers.XPRESS.value)
    #     elif slv == 'HiGHS':
    #         solvers2.append(MIPSolvers.HIGHS.value)

    return [MIPSolvers.HIGHS.value]


class LpModel:
    """
    LPModel implementation for PuLP
    """
    OPTIMAL = True
    INFINITY = 1e20
    originally_infeasible = False

    def __init__(self, solver_type: MIPSolvers):

        self.solver_type: MIPSolvers = solver_type

        self.model = gslvLpModel(name="")

        self.relaxed_slacks = list()

        self.result: LpResult | None = None

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
        return self.model.add_var(name=name, lb=lb, ub=ub, is_int=True)

    def add_var(self, lb: float, ub: float, name: str = "") -> LpVar:
        """
        Make floating point LP var
        :param lb: lower bound
        :param ub: upper bound
        :param name: name (optional)
        :return: LpVar
        """
        return self.model.add_var(name=name, lb=lb, ub=ub, is_int=False)

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
            self.model.add_cst(cst, name=name)
            return cst

    @staticmethod
    def sum(cst) -> LpExp:
        """
        Add sum of the constraints to the model
        :param cst: constraint object (or general expression)
        :return: Constraint object
        """
        return sum(cst)

    def minimize(self, obj_function: LpExp):
        """
        Set the objective function with minimization sense
        :param obj_function: expression to minimize
        """
        self.model.minimize(obj_function)

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

        # self.model.print()

        # solve the model
        res = self.model.solve(solver="highs", verbose=False)

        if not res.optimal:
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

                # TODO: figure out the status thing in pygslv
                self.logger.add_error(msg="Base problem could not be solved", value="infeasible")

                # deep copy of the original model
                debug_model = self.model.copy()

                # modify the original to detect the bad constraints
                slacks = list()
                debugging_f_obj = 0
                for i, (cst_name, cst) in enumerate(debug_model.constraints.items()):
                    # create a new slack var in the problem
                    sl = debug_model.add_var(name=f'Relax_{cst_name}', low=0, up=1e20)

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
                res_d = debug_model.solve()

                # clear the relaxed slacks list
                self.relaxed_slacks = list()

                if res_d.optimal:

                    # pick the original objective function
                    cst_slack_map = list()
                    for i, (cst_name, sl) in enumerate(slacks):

                        # get the debugging slack value
                        val = sl.value()

                        if abs(val) > 1e-10:
                            # add the slack in the main model
                            sl2 = self.model.add_var(name=f'Relax_final_{cst_name}',
                                                     low=0,
                                                     up=1e20, )
                            self.relaxed_slacks.append((i, sl2, 0.0))  # the 0.0 value will be read later

                            # add the slack to the original objective function
                            self.model.objective += sl2

                            # alter the matching constraint
                            self.model.constraints[cst_name] += sl2

                        # register the relation for later
                        cst_slack_map.append(cst_name)

                    # set the modified (original) objective function
                    self.model.setObjective(self.model.objective)

                    # at this point we can delete_with_dialogue the debug model
                    del debug_model

                    if progress_text is not None:
                        progress_text(f"Solving relaxed model with {self.solver_type.value}...")

                    # solve the modified (original) model
                    res = self.model.solve()

                    if res.optimal:

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
                        self.logger.add_warning(msg="Relaxed problem is not optimal :(")

                else:
                    self.logger.add_warning("Unable to relax the model, the debug model failed :(")

        # assign the result object
        self.result = res

        return 1 if res.optimal else 0

    def fobj_value(self) -> float:
        """
        Get the objective function value
        :return:
        """
        return self.result.objective

    def set_var_bounds(self, var: LpVar, lb: float, ub: float):
        """
        Modify the bounds of a variable
        :param var: LpVar instance to modify
        :param lb: lower bound value
        :param ub: upper bound value
        """
        if isinstance(var, LpVar):
            self.model.set_var_bounds(var, lb, ub)

    def is_mip(self):
        """
        Is this model a MIP?
        :return:
        """
        return self.model.isMIP()

    def get_value(self, x: Union[float, int, LpVar, LpExp, LpCst, Any]) -> float:
        """
        Get the value of a variable stored in a numpy array of objects
        :param x: solver object (it may be a LP var or a number)
        :return: result or zero
        """
        if isinstance(x, LpVar):
            return self.result.getPrimal(x)
        elif isinstance(x, LpExp):
            return self.result.getExpValue(x)
        elif isinstance(x, LpCst):
            return self.result.getCstPrimal(x)
        elif isinstance(x, float) or isinstance(x, int):
            return x
        else:
            raise Exception("Unrecognized type {}".format(x))

    def get_dual_value(self, x: LpCst) -> float:
        """
        Get the dual value of a variable stored in a numpy array of objects
        :param x: constraint
        :return: result or zero
        """
        if x is None:
            return 0.0

        if isinstance(x, LpVar):
            return self.result.getDual(x)
        elif isinstance(x, LpCst):
            return self.result.getCstDual(x)
        elif isinstance(x, float) or isinstance(x, int):
            return x
        else:
            raise Exception("Unrecognized type {}".format(x))

    def status2string(self, val: int):
        if self.result is not None:
            return self.result.status_name
        else:
            return "not solved"
