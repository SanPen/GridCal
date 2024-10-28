# PuLP : Python LP Modeler
# Version 1.4.2

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
from __future__ import annotations
from typing import TYPE_CHECKING
import sys
import warnings

from time import monotonic as clock
from GridCalEngine.Utils.ThirdParty.pulp.apis.lp_solver_cmd import LpSolver
from GridCalEngine.Utils.ThirdParty.pulp.apis.lp_solver_cmd import gurobi_path
import GridCalEngine.Utils.ThirdParty.pulp.constants as constants


if TYPE_CHECKING:
    from GridCalEngine.Utils.ThirdParty.pulp.model.lp_problem import LpProblem

# to import the gurobipy name into the module scope
gp = None


class GUROBI(LpSolver):
    """
    The Gurobi LP/MIP solver (via its python interface)

    The Gurobi variables are available (after a solve) in var.solverVar
    Constraints in constraint.solverConstraint
    and the Model is in prob.solverModel
    """

    name = "GUROBI"
    env = None

    try:
        sys.path.append(gurobi_path)
        # to import the name into the module scope
        global gp
        import gurobipy as gp
    except ImportError:  # FIXME: Bug because gurobi returns
        #  a gurobi exception on failed imports
        def available(self):
            """True if the solver is available"""
            return False

        def actualSolve(self, lp, callback=None):
            """Solve a well formulated lp problem"""
            raise constants.PulpSolverError("GUROBI: Not Available")

    else:

        def __init__(
            self,
            mip=True,
            msg=True,
            timeLimit=None,
            gapRel=None,
            warmStart=False,
            logPath=None,
            env=None,
            envOptions=None,
            manageEnv=False,
            **solverParams,
        ):
            """
            :param bool mip: if False, assume LP even if integer variables
            :param bool msg: if False, no log is shown
            :param float timeLimit: maximum time for solver (in seconds)
            :param float gapRel: relative gap tolerance for the solver to stop (in fraction)
            :param bool warmStart: if True, the solver will use the current value of variables as a start
            :param str logPath: path to the log file
            :param gp.Env env: Gurobi environment to use. Default None.
            :param dict envOptions: environment options.
            :param bool manageEnv: if False, assume the environment is handled by the user.


            If ``manageEnv`` is set to True, the ``GUROBI`` object creates a
            local Gurobi environment and manages all associated Gurobi
            resources. Importantly, this enables Gurobi licenses to be freed
            and connections terminated when the ``.close()`` function is called
            (this function always disposes of the Gurobi model, and the
            environment)::

                solver = GUROBI(manageEnv=True)
                prob.solve(solver)
                solver.close() # Must be called to free Gurobi resources.
                # All Gurobi models and environments are freed

            ``manageEnv=True`` is required when setting license or connection
            parameters. The ``envOptions`` argument is used to pass parameters
            to the Gurobi environment. For example, to connect to a Gurobi
            Cluster Manager::

                options = {
                    "CSManager": "<url>",
                    "CSAPIAccessID": "<access-id>",
                    "CSAPISecret": "<api-key>",
                }
                solver = GUROBI(manageEnv=True, envOptions=options)
                solver.close()
                # Compute server connection terminated

            Alternatively, one can also pass a ``gp.Env`` object. In this case,
            to be safe, one should still call ``.close()`` to dispose of the
            model::

                with gp.Env(params=options) as env:
                    # Pass environment as a parameter
                    solver = GUROBI(env=env)
                    prob.solve(solver)
                    solver.close()
                    # Still call `close` as this disposes the model which is required to correctly free env

            If ``manageEnv`` is set to False (the default), the ``GUROBI``
            object uses the global default Gurobi environment which will be
            freed once the object is deleted. In this case, one can still call
            ``.close()`` to dispose of the model::

                solver = GUROBI()
                prob.solve(solver)
                # The global default environment and model remain active
                solver.close()
                # Only the global default environment remains active
            """
            self.env = env
            self.env_options = envOptions if envOptions else {}
            self.manage_env = False if self.env is not None else manageEnv
            self.solver_params = solverParams

            self.model = None
            self.init_gurobi = False  # whether env and model have been initialised

            LpSolver.__init__(
                self,
                mip=mip,
                msg=msg,
                timeLimit=timeLimit,
                gapRel=gapRel,
                logPath=logPath,
                warmStart=warmStart,
            )

            # set the output of gurobi
            if not self.msg:
                if self.manage_env:
                    self.env_options["OutputFlag"] = 0
                else:
                    self.env_options["OutputFlag"] = 0
                    self.solver_params["OutputFlag"] = 0

        def __del__(self):
            self.close()

        def close(self):
            """
            Must be called when internal Gurobi model and/or environment
            requires disposing. The environment (default or otherwise) will be
            disposed only if ``manageEnv`` is set to True.
            """
            if not self.init_gurobi:
                return
            self.model.dispose()
            if self.manage_env:
                self.env.dispose()

        def findSolutionValues(self, lp: LpProblem):
            """

            :param lp:
            :return:
            """
            model = lp.solverModel
            solutionStatus = model.Status
            GRB = gp.GRB
            # TODO: check status for Integer Feasible
            gurobiLpStatus = {
                GRB.OPTIMAL: constants.LpStatusOptimal,
                GRB.INFEASIBLE: constants.LpStatusInfeasible,
                GRB.INF_OR_UNBD: constants.LpStatusInfeasible,
                GRB.UNBOUNDED: constants.LpStatusUnbounded,
                GRB.ITERATION_LIMIT: constants.LpStatusNotSolved,
                GRB.NODE_LIMIT: constants.LpStatusNotSolved,
                GRB.TIME_LIMIT: constants.LpStatusNotSolved,
                GRB.SOLUTION_LIMIT: constants.LpStatusNotSolved,
                GRB.INTERRUPTED: constants.LpStatusNotSolved,
                GRB.NUMERIC: constants.LpStatusNotSolved,
            }
            if self.msg:
                print("Gurobi status=", solutionStatus)
            lp.resolveOK = True
            for var in lp.get_variables():
                var.isModified = False
            status = gurobiLpStatus.get(solutionStatus, constants.LpStatusUndefined)
            lp.assignStatus(status)
            if model.SolCount >= 1:
                # populate pulp solution values
                for var, value in zip(lp.get_variables(), model.getAttr(GRB.Attr.X, model.getVars())):
                    var.varValue = value
                # populate pulp constraints slack
                for constr, value in zip(
                    lp.constraints.values(),
                    model.getAttr(GRB.Attr.Slack, model.getConstrs()),
                ):
                    constr.slack = value
                # put pi and slack variables against the constraints
                if not model.IsMIP:
                    for var, value in zip(lp.get_variables(), model.getAttr(GRB.Attr.RC, model.getVars())):
                        var.dj = value

                    for constr, value in zip(
                        lp.constraints.values(),
                        model.getAttr(GRB.Attr.Pi, model.getConstrs()),
                    ):
                        constr.pi = value
            return status

        def available(self) -> bool:
            """True if the solver is available"""
            try:
                with gp.Env(params=self.env_options):
                    pass
            except gp.GurobiError as e:
                warnings.warn(f"GUROBI error: {e}.")
                return False
            return True

        def initGurobi(self):
            """

            :return:
            """
            if self.init_gurobi:
                return
            else:
                self.init_gurobi = True
            try:
                if self.manage_env:
                    self.env = gp.Env(params=self.env_options)
                    self.model = gp.Model(env=self.env)
                # Environment handled by user or default Env
                else:
                    self.model = gp.Model(env=self.env)
                # Set solver parameters
                for param, value in self.solver_params.items():
                    self.model.setParam(param, value)
            except gp.GurobiError as e:
                raise e

        def callSolver(self, lp: LpProblem, callback=None):
            """Solves the problem with gurobi"""
            # solve the problem
            self.solveTime = -clock()
            lp.solverModel.optimize(callback=callback)
            self.solveTime += clock()

        def buildSolverModel(self, lp: LpProblem):
            """
            Takes the pulp lp model and translates it into a gurobi model
            """
            constants.debug_log("create the gurobi model")
            self.initGurobi()
            self.model.ModelName = lp.name
            lp.solverModel = self.model
            constants.debug_log("set the sense of the problem")
            if lp.sense == constants.LpMaximize:
                lp.solverModel.setAttr("ModelSense", -1)
            if self.timeLimit:
                lp.solverModel.setParam("TimeLimit", self.timeLimit)
            gapRel = self.optionsDict.get("gapRel")
            logPath = self.optionsDict.get("logPath")
            if gapRel:
                lp.solverModel.setParam("MIPGap", gapRel)
            if logPath:
                lp.solverModel.setParam("LogFile", logPath)

            constants.debug_log("add the variables to the problem")
            lp.solverModel.update()
            nvars = lp.solverModel.NumVars
            for var in lp.variables():
                lowBound = var.lowBound
                if lowBound is None:
                    lowBound = -gp.GRB.INFINITY
                upBound = var.upBound
                if upBound is None:
                    upBound = gp.GRB.INFINITY
                obj = lp.objective.get(var, 0.0)
                varType = gp.GRB.CONTINUOUS
                if var.cat == constants.LpInteger and self.mip:
                    varType = gp.GRB.INTEGER
                # only add variable once, ow new variable will be created.
                if not hasattr(var, "solverVar") or nvars == 0:
                    var.solverVar = lp.solverModel.addVar(
                        lowBound, upBound, vtype=varType, obj=obj, name=var.name
                    )
            if self.optionsDict.get("warmStart", False):
                # Once lp.variables() has been used at least once in the building of the model.
                # we can use the lp.get_variables() with the cache.
                for var in lp.get_variables():
                    if var.varValue is not None:
                        var.solverVar.start = var.varValue

            lp.solverModel.update()
            constants.debug_log("add the Constraints to the problem")
            for name, constraint in lp.constraints.items():
                # build the expression
                expr = gp.LinExpr(
                    list(constraint.values()), [v.solverVar for v in constraint.keys()]
                )
                if constraint.sense == constants.LpConstraintLE:
                    constraint.solverConstraint = lp.solverModel.addConstr(
                        expr <= -constraint.constant, name=name
                    )
                elif constraint.sense == constants.LpConstraintGE:
                    constraint.solverConstraint = lp.solverModel.addConstr(
                        expr >= -constraint.constant, name=name
                    )
                elif constraint.sense == constants.LpConstraintEQ:
                    constraint.solverConstraint = lp.solverModel.addConstr(
                        expr == -constraint.constant, name=name
                    )
                else:
                    raise constants.PulpSolverError("Detected an invalid constraint type")
            lp.solverModel.update()

        def actualSolve(self, lp: LpProblem, callback=None):
            """
            Solve a well formulated lp problem

            creates a gurobi model, variables and constraints and attaches
            them to the lp model which it then solves
            """
            self.buildSolverModel(lp)
            # set the initial solution
            constants.debug_log("Solve the Model using gurobi")
            self.callSolver(lp, callback=callback)
            # get the solution information
            solutionStatus = self.findSolutionValues(lp)
            for var in lp.get_variables():
                var.modified = False
            for constraint in lp.constraints.values():
                constraint.modified = False
            return solutionStatus

        def actualResolve(self, lp: LpProblem, callback=None):
            """
            Solve a well formulated lp problem

            uses the old solver and modifies the rhs of the modified constraints
            """
            constants.debug_log("Resolve the Model using gurobi")
            for constraint in lp.constraints.values():
                if constraint.modified:
                    constraint.solverConstraint.setAttr(
                        gp.GRB.Attr.RHS, -constraint.constant
                    )
            lp.solverModel.update()
            self.callSolver(lp, callback=callback)
            # get the solution information
            solutionStatus = self.findSolutionValues(lp)
            for var in lp.get_variables():
                var.modified = False
            for constraint in lp.constraints.values():
                constraint.modified = False
            return solutionStatus

