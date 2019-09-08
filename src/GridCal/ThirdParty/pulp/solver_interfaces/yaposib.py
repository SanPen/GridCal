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

from GridCal.ThirdParty.pulp.solvers import *


yaposib = None


class YAPOSIB(LpSolver):
    """
    COIN OSI (via its python interface)

    Copyright Christophe-Marie Duquesne 2012

    The yaposib variables are available (after a solve) in var.solverVar
    The yaposib constraints are available in constraint.solverConstraint
    The Model is in prob.solverModel
    """
    try:
        # import the model into the global scope
        global yaposib
        import yaposib
    except ImportError:
        def available(self):
            """
            True if the solver is available
            """
            return False

        def actualSolve(self, lp, callback = None):
            """
            Solve a well formulated lp problem
            """
            raise PulpSolverError("YAPOSIB: Not Available")
    else:
        def __init__(self, mip=True, msg=True, timeLimit=None, epgap=None, solverName=None, **solverParams):
            """
            Initializes the yaposib solver.

            @param mip:          if False the solver will solve a MIP as
                                 an LP
            @param msg:          displays information from the solver to
                                 stdout
            @param timeLimit:    not supported
            @param epgap:        not supported
            @param solverParams: not supported
            """
            LpSolver.__init__(self, mip, msg)
            if solverName:
                self.solverName = solverName
            else:
                self.solverName = yaposib.available_solvers()[0]

        def findSolutionValues(self, lp):
            model = lp.solverModel
            solutionStatus = model.status
            yaposibLpStatus = {"optimal": LpStatusOptimal,
                               "undefined": LpStatusUndefined,
                               "abandoned": LpStatusInfeasible,
                               "infeasible": LpStatusInfeasible,
                               "limitreached": LpStatusInfeasible}

            # populate pulp solution values
            for var in lp.variables():
                var.varValue = var.solverVar.solution
                var.dj = var.solverVar.reducedcost

            # put pi and slack variables against the constraints
            for constr in lp.constraints.values():
                constr.pi = constr.solverConstraint.dual
                constr.slack = -constr.constant - constr.solverConstraint.activity
            if self.msg:
                print("yaposib status=", solutionStatus)
            lp.resolveOK = True
            for var in lp.variables():
                var.isModified = False
            lp.status = yaposibLpStatus.get(solutionStatus, LpStatusUndefined)
            return lp.status

        def available(self):
            """True if the solver is available"""
            return True

        def callSolver(self, lp, callback = None):
            """Solves the problem with yaposib
            """
            if self.msg == 0:
                # close stdout to get rid of messages
                tempfile = open(mktemp(),'w')
                savestdout = os.dup(1)
                os.close(1)
                if os.dup(tempfile.fileno()) != 1:
                    raise PulpSolverError("couldn't redirect stdout - dup() error")
            self.solveTime = -clock()
            lp.solverModel.solve(self.mip)
            self.solveTime += clock()
            if self.msg == 0:
                #reopen stdout
                os.close(1)
                os.dup(savestdout)
                os.close(savestdout)

        def buildSolverModel(self, lp):
            """
            Takes the pulp lp model and translates it into a yaposib model
            """
            log.debug("create the yaposib model")
            lp.solverModel = yaposib.Problem(self.solverName)
            prob = lp.solverModel
            prob.name = lp.name

            log.debug("set the sense of the problem")
            if lp.sense == LpMaximize:
                prob.obj.maximize = True

            log.debug("add the variables to the problem")
            for var in lp.variables():
                col = prob.cols.add(yaposib.vec([]))
                col.name = var.name
                if not var.lowBound is None:
                    col.lowerbound = var.lowBound
                if not var.upBound is None:
                    col.upperbound = var.upBound
                if var.cat == LpInteger:
                    col.integer = True
                prob.obj[col.index] = lp.objective.get(var, 0.0)
                var.solverVar = col

            log.debug("add the Constraints to the problem")
            for name, constraint in lp.constraints.items():
                row = prob.rows.add(yaposib.vec([(var.solverVar.index,
                    value) for var, value in constraint.items()]))
                if constraint.sense == LpConstraintLE:
                    row.upperbound = -constraint.constant
                elif constraint.sense == LpConstraintGE:
                    row.lowerbound = -constraint.constant
                elif constraint.sense == LpConstraintEQ:
                    row.upperbound = -constraint.constant
                    row.lowerbound = -constraint.constant
                else:
                    raise PulpSolverError('Detected an invalid constraint type')
                row.name = name
                constraint.solverConstraint = row

        def actualSolve(self, lp, callback = None):
            """
            Solve a well formulated lp problem

            creates a yaposib model, variables and constraints and attaches
            them to the lp model which it then solves
            """
            self.buildSolverModel(lp)

            # set the initial solution
            log.debug("Solve the model using yaposib")
            self.callSolver(lp, callback=callback)

            # get the solution information
            solution_status = self.findSolutionValues(lp)
            for var in lp.variables():
                var.modified = False

            for constraint in lp.constraints.values():
                constraint.modified = False

            return solution_status

        def actualResolve(self, lp, callback = None):
            """
            Solve a well formulated lp problem

            uses the old solver and modifies the rhs of the modified
            constraints
            """
            log.debug("Resolve the model using yaposib")
            for constraint in lp.constraints.values():

                row = constraint.solverConstraint

                if constraint.modified:
                    if constraint.sense == LpConstraintLE:
                        row.upperbound = -constraint.constant

                    elif constraint.sense == LpConstraintGE:
                        row.lowerbound = -constraint.constant

                    elif constraint.sense == LpConstraintEQ:
                        row.upperbound = -constraint.constant
                        row.lowerbound = -constraint.constant

                    else:
                        raise PulpSolverError('Detected an invalid constraint type')

            self.callSolver(lp, callback=callback)

            # get the solution information
            solution_status = self.findSolutionValues(lp)

            for var in lp.variables():
                var.modified = False

            for constraint in lp.constraints.values():
                constraint.modified = False

            return solution_status

