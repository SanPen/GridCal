# Copyright (c) 2002-2005, Jean-Sebastien Roy
# Modifications Copyright (c) 2007- Stuart Anthony Mitchell
# Modifications Copyright (c) 2014- Santiago Peñate Vera
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
from __future__ import annotations
from typing import TYPE_CHECKING
import warnings
from time import monotonic as clock
from GridCalEngine.Utils.ThirdParty.pulp.apis.lp_solver import LpSolver
import GridCalEngine.Utils.ThirdParty.pulp.constants as constants

if TYPE_CHECKING:
    from GridCalEngine.Utils.ThirdParty.pulp.model.lp_problem import LpProblem


def cplex_var_types(var):
    """

    :param var:
    :return:
    """
    if var.cat == constants.LpInteger:
        return "I"
    else:
        return "C"


def cplex_var_ub(var):
    """

    :param var:
    :return:
    """
    if var.upBound is not None:
        return float(var.upBound)
    else:
        return cplex.infinity


def cplex_var_lb(var):
    """

    :param var:
    :return:
    """
    if var.lowBound is not None:
        return float(var.lowBound)
    else:
        return -cplex.infinity


class CPLEX_PY(LpSolver):
    """
    The CPLEX LP/MIP solver (via a Python Binding)

    This solver wraps the python api of cplex.
    It has been tested against cplex 12.3.
    For api functions that have not been wrapped in this solver please use
    the base cplex classes
    """

    name = "CPLEX_PY"
    try:
        global cplex
        import cplex
    except Exception as e:
        err = e
        """The CPLEX LP/MIP solver from python. Something went wrong!!!!"""

        def available(self):
            """True if the solver is available"""
            return False

        def actualSolve(self, lp):
            """Solve a well formulated lp problem"""
            raise constants.PulpSolverError(f"CPLEX_PY: Not Available:\n{self.err}")

    else:

        def __init__(self,
                     mip=True,
                     msg=True,
                     timeLimit=None,
                     gapRel=None,
                     warmStart=False,
                     logPath=None,
                     threads=None):
            """
            :param bool mip: if False, assume LP even if integer variables
            :param bool msg: if False, no log is shown
            :param float timeLimit: maximum time for solver (in seconds)
            :param float gapRel: relative gap tolerance for the solver to stop (in fraction)
            :param bool warmStart: if True, the solver will use the current value of variables as a start
            :param str logPath: path to the log file
            :param int threads: number of threads to be used by CPLEX to solve a problem (default None uses all available)
            """

            LpSolver.__init__(
                self,
                gapRel=gapRel,
                mip=mip,
                msg=msg,
                timeLimit=timeLimit,
                warmStart=warmStart,
                logPath=logPath,
                threads=threads,
            )

        def available(self) -> bool:
            """True if the solver is available"""
            return True

        def actualSolve(self, lp: LpProblem, callback=None):
            """
            Solve a well formulated lp problem

            creates a cplex model, variables and constraints and attaches
            them to the lp model which it then solves
            """
            self.buildSolverModel(lp)
            # set the initial solution
            constants.debug_log("Solve the Model using cplex")
            self.callSolver(lp)
            # get the solution information
            solutionStatus = self.findSolutionValues(lp)
            for var in lp.get_variables():
                var.modified = False
            for constraint in lp.constraints.values():
                constraint.modified = False
            return solutionStatus

        def buildSolverModel(self, lp: LpProblem):
            """
            Takes the pulp lp model and translates it into a cplex model
            """
            model_variables = lp.variables()
            self.n2v = {var.name: var for var in model_variables}
            if len(self.n2v) != len(model_variables):
                raise constants.PulpSolverError(
                    "Variables must have unique names for cplex solver"
                )
            constants.debug_log("create the cplex model")
            self.solverModel = lp.solverModel = cplex.Cplex()
            constants.debug_log("set the name of the problem")
            if not self.mip:
                self.solverModel.set_problem_name(lp.name)
            constants.debug_log("set the sense of the problem")
            if lp.sense == constants.LpMaximize:
                lp.solverModel.objective.set_sense(
                    lp.solverModel.objective.sense.maximize
                )
            obj = [float(lp.objective.get(var, 0.0)) for var in model_variables]

            lb = [cplex_var_lb(var) for var in model_variables]

            ub = [cplex_var_ub(var) for var in model_variables]
            colnames = [var.name for var in model_variables]

            ctype = [cplex_var_types(var) for var in model_variables]
            ctype = "".join(ctype)
            lp.solverModel.variables.add(
                obj=obj, lb=lb, ub=ub, types=ctype, names=colnames
            )
            rows = []
            senses = []
            rhs = []
            rownames = []
            for name, constraint in lp.constraints.items():
                # build the expression
                expr = [(var.name, float(coeff)) for var, coeff in constraint.items()]
                if not expr:
                    # if the constraint is empty
                    rows.append(([], []))
                else:
                    rows.append(list(zip(*expr)))
                if constraint.sense == constants.LpConstraintLE:
                    senses.append("L")
                elif constraint.sense == constants.LpConstraintGE:
                    senses.append("G")
                elif constraint.sense == constants.LpConstraintEQ:
                    senses.append("E")
                else:
                    raise constants.PulpSolverError("Detected an invalid constraint type")
                rownames.append(name)
                rhs.append(float(-constraint.constant))
            lp.solverModel.linear_constraints.add(
                lin_expr=rows, senses=senses, rhs=rhs, names=rownames
            )
            constants.debug_log("set the type of the problem")
            if not self.mip:
                self.solverModel.set_problem_type(cplex.Cplex.problem_type.LP)
            constants.debug_log("set the logging")
            if not self.msg:
                self.setlogfile(None)
            logPath = self.optionsDict.get("logPath")
            if logPath is not None:
                if self.msg:
                    warnings.warn(
                        "`logPath` argument replaces `msg=1`. The output will be redirected to the log file."
                    )
                self.setlogfile(open(logPath, "w"))
            gapRel = self.optionsDict.get("gapRel")
            if gapRel is not None:
                self.changeEpgap(gapRel)
            if self.timeLimit is not None:
                self.setTimeLimit(self.timeLimit)
            self.setThreads(self.optionsDict.get("threads", None))
            if self.optionsDict.get("warmStart", False):
                # We assume "auto" for the effort_level
                effort = self.solverModel.MIP_starts.effort_level.auto
                start = [
                    (k, v.value()) for k, v in self.n2v.items() if v.value() is not None
                ]
                if not start:
                    warnings.warn("No variable with value found: mipStart aborted")
                    return
                ind, val = zip(*start)
                self.solverModel.MIP_starts.add(
                    cplex.SparsePair(ind=ind, val=val), effort, "1"
                )

        def setlogfile(self, fileobj):
            """
            sets the logfile for cplex output
            """
            self.solverModel.set_error_stream(fileobj)
            self.solverModel.set_log_stream(fileobj)
            self.solverModel.set_warning_stream(fileobj)
            self.solverModel.set_results_stream(fileobj)

        def setThreads(self, threads=None):
            """
            Change cplex thread count used (None is default which uses all available resources)
            """
            self.solverModel.parameters.threads.set(threads or 0)

        def changeEpgap(self, epgap=10 ** -4):
            """
            Change cplex solver integer bound gap tolerence
            """
            self.solverModel.parameters.mip.tolerances.mipgap.set(epgap)

        def setTimeLimit(self, timeLimit=0.0):
            """
            Make cplex limit the time it takes --added CBM 8/28/09
            """
            self.solverModel.parameters.timelimit.set(timeLimit)

        def callSolver(self, isMIP):
            """Solves the problem with cplex"""
            # solve the problem
            self.solveTime = -clock()
            self.solverModel.solve()
            self.solveTime += clock()

        def findSolutionValues(self, lp: LpProblem):
            """
            
            :param lp: 
            :return: 
            """
            CplexLpStatus = {
                lp.solverModel.solution.status.MIP_optimal: constants.LpStatusOptimal,
                lp.solverModel.solution.status.optimal: constants.LpStatusOptimal,
                lp.solverModel.solution.status.optimal_tolerance: constants.LpStatusOptimal,
                lp.solverModel.solution.status.infeasible: constants.LpStatusInfeasible,
                lp.solverModel.solution.status.infeasible_or_unbounded: constants.LpStatusInfeasible,
                lp.solverModel.solution.status.MIP_infeasible: constants.LpStatusInfeasible,
                lp.solverModel.solution.status.MIP_infeasible_or_unbounded: constants.LpStatusInfeasible,
                lp.solverModel.solution.status.unbounded: constants.LpStatusUnbounded,
                lp.solverModel.solution.status.MIP_unbounded: constants.LpStatusUnbounded,
                lp.solverModel.solution.status.abort_dual_obj_limit: constants.LpStatusNotSolved,
                lp.solverModel.solution.status.abort_iteration_limit: constants.LpStatusNotSolved,
                lp.solverModel.solution.status.abort_obj_limit: constants.LpStatusNotSolved,
                lp.solverModel.solution.status.abort_relaxed: constants.LpStatusNotSolved,
                lp.solverModel.solution.status.abort_time_limit: constants.LpStatusNotSolved,
                lp.solverModel.solution.status.abort_user: constants.LpStatusNotSolved,
                lp.solverModel.solution.status.MIP_abort_feasible: constants.LpStatusOptimal,
                lp.solverModel.solution.status.MIP_time_limit_feasible: constants.LpStatusOptimal,
                lp.solverModel.solution.status.MIP_time_limit_infeasible: constants.LpStatusInfeasible,
            }
            lp.cplex_status = lp.solverModel.solution.get_status()
            status = CplexLpStatus.get(lp.cplex_status, constants.LpStatusUndefined)
            CplexSolStatus = {
                lp.solverModel.solution.status.MIP_time_limit_feasible: constants.LpSolutionIntegerFeasible,
                lp.solverModel.solution.status.MIP_abort_feasible: constants.LpSolutionIntegerFeasible,
                lp.solverModel.solution.status.MIP_feasible: constants.LpSolutionIntegerFeasible,
            }
            # TODO: I did not find the following status: CPXMIP_NODE_LIM_FEAS, CPXMIP_MEM_LIM_FEAS
            sol_status = CplexSolStatus.get(lp.cplex_status)
            lp.assignStatus(status, sol_status)
            var_names = [var.name for var in lp._variables]
            con_names = [con for con in lp.constraints]
            try:
                objectiveValue = lp.solverModel.solution.get_objective_value()
                variablevalues = dict(
                    zip(var_names, lp.solverModel.solution.get_values(var_names))
                )
                lp.assignVarsVals(variablevalues)
                constraintslackvalues = dict(
                    zip(con_names, lp.solverModel.solution.get_linear_slacks(con_names))
                )
                lp.assignConsSlack(constraintslackvalues)
                if lp.solverModel.get_problem_type() == cplex.Cplex.problem_type.LP:
                    variabledjvalues = dict(
                        zip(
                            var_names,
                            lp.solverModel.solution.get_reduced_costs(var_names),
                        )
                    )
                    lp.assignVarsDj(variabledjvalues)
                    constraintpivalues = dict(
                        zip(
                            con_names,
                            lp.solverModel.solution.get_dual_values(con_names),
                        )
                    )
                    lp.assignConsPi(constraintpivalues)
            except cplex.exceptions.CplexSolverError:
                # raises this error when there is no solution
                pass
            # put pi and slack variables against the constraints
            # TODO: clear up the name of self.n2c
            if self.msg:
                print("Cplex status=", lp.cplex_status)
            lp.resolveOK = True
            for var in lp.get_variables():
                var.isModified = False
            return status

        def actualResolve(self, lp: LpProblem, **kwargs):
            """
            looks at which variables have been modified and changes them
            """
            raise NotImplementedError("Resolves in CPLEX_PY not yet implemented")
