# PuLP : Python LP Modeler
# Version 2.4

# Copyright (c) 2002-2005, Jean-Sebastien Roy (js@jeannot.org)
# Modifications Copyright (c) 2007- Stuart Anthony Mitchell (s.mitchell@auckland.ac.nz)
# $Id:solvers.py 1791 2008-04-23 22:54:34Z smit023 $

# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:

# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE."""

# Modified by Sam Mathew (@samiit on Github)
# Users would need to install HiGHS on their machine and provide the path to the executable. Please look at this thread: https://github.com/ERGO-Code/HiGHS/issues/527#issuecomment-894852288
# More instructions on: https://www.highs.dev
from __future__ import annotations
from math import inf
from typing import Tuple, TYPE_CHECKING
import GridCalEngine.Utils.ThirdParty.pulp.constants as constants
from GridCalEngine.Utils.ThirdParty.pulp.apis.lp_solver_cmd import LpSolver

try:
    import highspy
    HIGHSPY_AVAILABLE = True
except ImportError:
    highspy = None
    HIGHSPY_AVAILABLE = False

if TYPE_CHECKING:
    from GridCalEngine.Utils.ThirdParty.pulp.model.lp_problem import LpProblem


def callback(logType, logMsg, callbackValue=""):
    """

    :param logType:
    :param logMsg:
    :param callbackValue:
    """
    print(f"[{logType.name}] {logMsg}")


class HiGHS(LpSolver):
    name = "HiGHS"

    # Note(maciej): It was surprising to me that higshpy wasn't logging out of the box,
    #  even with the different logging options set. This callback seems to work, but there
    #  are probably better ways of doing this ¯\_(ツ)_/¯
    # DEFAULT_CALLBACK = lambda logType, logMsg, callbackValue: print(
    #     f"[{logType.name}] {logMsg}"
    # )
    # DEFAULT_CALLBACK_VALUE = ""

    def __init__(self,
                 mip=True,
                 msg=True,
                 callbackTuple=None,
                 gapAbs=None,
                 gapRel=None,
                 threads=None,
                 timeLimit=None,
                 **solverParams):
        """
        :param bool mip: if False, assume LP even if integer variables
        :param bool msg: if False, no log is shown
        :param tuple callbackTuple: Tuple of log callback function (see DEFAULT_CALLBACK above for definition)
            and callbackValue (tag embedded in every callback)
        :param float gapRel: relative gap tolerance for the solver to stop (in fraction)
        :param float gapAbs: absolute gap tolerance for the solver to stop
        :param int threads: sets the maximum number of threads
        :param float timeLimit: maximum time for solver (in seconds)
        :param dict solverParams: list of named options to pass directly to the HiGHS solver
        """
        super().__init__(mip=mip, msg=msg, timeLimit=timeLimit, **solverParams)
        self.callbackTuple = callbackTuple
        self.gapAbs = gapAbs
        self.gapRel = gapRel
        self.threads = threads

    def available(self) -> bool:
        """
        True if the solver is available
        :return:
        """
        return HIGHSPY_AVAILABLE

    @staticmethod
    def callSolver(lp: LpProblem):
        """

        :param lp:
        :return:
        """
        if HIGHSPY_AVAILABLE:
            lp.solverModel.run()
        else:
            raise Exception("HIGHSPY not available")

    def createAndConfigureSolver(self, lp: LpProblem):
        """

        :param lp:
        :return:
        """
        if HIGHSPY_AVAILABLE:
            lp.solverModel = highspy.Highs()

            if self.msg and self.callbackTuple:
                callbackTuple = self.callbackTuple or (callback, "")
                lp.solverModel.setLogCallback(*callbackTuple)

            if not self.msg:
                lp.solverModel.setOptionValue("output_flag", False)

            if self.gapRel is not None:
                lp.solverModel.setOptionValue("mip_rel_gap", self.gapRel)

            if self.gapAbs is not None:
                lp.solverModel.setOptionValue("mip_abs_gap", self.gapAbs)

            if self.threads is not None:
                lp.solverModel.setOptionValue("threads", self.threads)

            if self.timeLimit is not None:
                lp.solverModel.setOptionValue("time_limit", float(self.timeLimit))

            # set remaining parameter values
            for key, value in self.optionsDict.items():
                lp.solverModel.setOptionValue(key, value)
        else:
            raise Exception("HIGHSPY not available")

    def buildSolverModel(self, lp: LpProblem):
        """

        :param lp:
        :return:
        """
        if HIGHSPY_AVAILABLE:
            inf = highspy.kHighsInf

            obj_mult = -1 if lp.sense == constants.LpMaximize else 1

            for i, var in enumerate(lp.variables()):
                lb = var.lowBound
                ub = var.upBound
                lp.solverModel.addCol(
                    obj_mult * lp.objective.get(var, 0.0),
                    -inf if lb is None else lb,
                    inf if ub is None else ub,
                    0,
                    [],
                    [],
                )
                var.index = i

                if var.cat == constants.LpInteger and self.mip:
                    lp.solverModel.changeColIntegrality(
                        var.index, highspy.HighsVarType.kInteger
                    )

            for constraint in lp.constraints.values():
                non_zero_constraint_items = [
                    (var.index, coefficient)
                    for var, coefficient in constraint.items()
                    if coefficient != 0
                ]

                if len(non_zero_constraint_items) == 0:
                    indices, coefficients = [], []
                else:
                    indices, coefficients = zip(*non_zero_constraint_items)

                lb = constraint.getLb()
                ub = constraint.getUb()
                lp.solverModel.addRow(
                    -inf if lb is None else lb,
                    inf if ub is None else ub,
                    len(indices),
                    indices,
                    coefficients,
                )
        else:
            raise Exception("HIGHSPY not available")

    @staticmethod
    def findSolutionValues(lp: LpProblem) -> Tuple[int, int]:
        """

        :param lp:
        :return:
        """
        status = lp.solverModel.getModelStatus()
        obj_value = lp.solverModel.getObjectiveValue()

        solution = lp.solverModel.getSolution()
        HighsModelStatus = highspy.HighsModelStatus

        status_dict = {
            HighsModelStatus.kNotset: (
                constants.LpStatusNotSolved,
                constants.LpSolutionNoSolutionFound,
            ),
            HighsModelStatus.kLoadError: (
                constants.LpStatusNotSolved,
                constants.LpSolutionNoSolutionFound,
            ),
            HighsModelStatus.kModelError: (
                constants.LpStatusNotSolved,
                constants.LpSolutionNoSolutionFound,
            ),
            HighsModelStatus.kPresolveError: (
                constants.LpStatusNotSolved,
                constants.LpSolutionNoSolutionFound,
            ),
            HighsModelStatus.kSolveError: (
                constants.LpStatusNotSolved,
                constants.LpSolutionNoSolutionFound,
            ),
            HighsModelStatus.kPostsolveError: (
                constants.LpStatusNotSolved,
                constants.LpSolutionNoSolutionFound,
            ),
            HighsModelStatus.kModelEmpty: (
                constants.LpStatusNotSolved,
                constants.LpSolutionNoSolutionFound,
            ),
            HighsModelStatus.kOptimal: (
                constants.LpStatusOptimal,
                constants.LpSolutionOptimal,
            ),
            HighsModelStatus.kInfeasible: (
                constants.LpStatusInfeasible,
                constants.LpSolutionInfeasible,
            ),
            HighsModelStatus.kUnboundedOrInfeasible: (
                constants.LpStatusInfeasible,
                constants.LpSolutionInfeasible,
            ),
            HighsModelStatus.kUnbounded: (
                constants.LpStatusUnbounded,
                constants.LpSolutionUnbounded,
            ),
            HighsModelStatus.kObjectiveBound: (
                constants.LpStatusOptimal,
                constants.LpSolutionIntegerFeasible,
            ),
            HighsModelStatus.kObjectiveTarget: (
                constants.LpStatusOptimal,
                constants.LpSolutionIntegerFeasible,
            ),
            HighsModelStatus.kTimeLimit: (
                constants.LpStatusOptimal,
                constants.LpSolutionIntegerFeasible,
            ),
            HighsModelStatus.kIterationLimit: (
                constants.LpStatusOptimal,
                constants.LpSolutionIntegerFeasible,
            ),
            HighsModelStatus.kUnknown: (
                constants.LpStatusNotSolved,
                constants.LpSolutionNoSolutionFound,
            ),
        }

        col_values = list(solution.col_value)

        # Assign values to the variables as with lp.assignVarsVals()
        for var in lp.variables():
            var.varValue = col_values[var.index]

        if obj_value == float(inf) and status in (HighsModelStatus.kTimeLimit, HighsModelStatus.kIterationLimit):
            return constants.LpStatusNotSolved, constants.LpSolutionNoSolutionFound
        else:
            return status_dict[status]

    def actualSolve(self, lp: LpProblem):
        """

        :param lp:
        :return:
        """
        if HIGHSPY_AVAILABLE:
            self.createAndConfigureSolver(lp)
            self.buildSolverModel(lp)
            self.callSolver(lp)

            status, sol_status = self.findSolutionValues(lp)

            for var in lp.variables():
                var.modified = False

            for constraint in lp.constraints.values():
                constraint.modifier = False

            lp.assignStatus(status, sol_status)

            return status
        else:
            raise Exception("HIGHSPY not available")

    def actualResolve(self, lp: LpProblem, **kwargs):
        """

        :param lp:
        :param kwargs:
        :return:
        """
        raise constants.PulpSolverError("HiGHS: Resolving is not supported")
