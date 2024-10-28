#! /usr/bin/env python
# PuLP : Python LP Modeler


# Copyright (c) 2002-2005, Jean-Sebastien Roy (js@jeannot.org)
# Modifications Copyright (c) 2007- Stuart Anthony Mitchell (s.mitchell@auckland.ac.nz)
# $Id: pulp.py 1791 2008-04-23 22:54:34Z smit023 $

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
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""
PuLP is an linear and mixed integer programming modeler written in Python.

With PuLP, it is simple to create MILP optimisation problems and solve them with the
latest open-source (or proprietary) solvers.  PuLP can generate MPS or LP files and
call solvers such as GLPK_, COIN-OR CLP/`CBC`_, CPLEX_, GUROBI_, MOSEK_, XPRESS_,
CHOCO_, MIPCL_, HiGHS_, SCIP_/FSCIP_.

The documentation for PuLP can be `found here <https://coin-or.github.io/pulp/>`_.

Many examples are shown in the `documentation <https://coin-or.github.io/pulp/CaseStudies/index.html>`_
and pure code examples are available in `examples/ directory <https://github.com/coin-or/pulp/tree/master/examples>`_ .
The examples require at least a solver in your PATH or a shared library file.

Quickstart
------------
Use ``LpVariable`` to create new variables. To create a variable x with 0  ≤  x  ≤  3::

     from pulp import *
     x = LpVariable("x", 0, 3)

To create a binary variable, y, with values either 0 or 1::

     y = LpVariable("y", cat="Binary")

Use ``LpProblem`` to create new problems. Create a problem called "myProblem" like so::

     prob = LpProblem("myProblem", LpMinimize)

Combine variables in order to create expressions and constraints, and then add them to
the problem.::

     prob += x + y <= 2

An expression is a constraint without a right-hand side (RHS) sense (one of ``=``,
``<=`` or ``>=``). If you add an expression to a problem, it will become the
objective::

     prob += -4*x + y

To solve the problem  with the default included solver::

     status = prob.solve()

If you want to try another solver to solve the problem::

     status = prob.solve(GLPK(msg = 0))

Display the status of the solution::

     LpStatus[status]
     > 'Optimal'

You can get the value of the variables using ``value``. ex::

     value(x)
     > 2.0

Useful Classes and Functions
-----------------------------

Exported classes:

* ``LpProblem`` -- Container class for a Linear or Integer programming problem
* ``LpVariable`` -- Variables that are added into constraints in the LP problem
* ``LpConstraint`` -- Constraints of the general form

      a1x1 + a2x2 + ... + anxn (<=, =, >=) b

* ``LpConstraintVar`` -- A special type of constraint for constructing column of the model in column-wise modelling

Exported functions:

* ``value()`` -- Finds the value of a variable or expression
* ``lpSum()`` -- Given a list of the form [a1*x1, a2*x2, ..., an*xn] will construct a linear expression to be used as a constraint or variable
* ``lpDot()`` -- Given two lists of the form [a1, a2, ..., an] and [x1, x2, ..., xn] will construct a linear expression to be used as a constraint or variable

Contributing to PuLP
-----------------------
Instructions for making your first contribution to PuLP are given
`here <https://coin-or.github.io/pulp/develop/contribute.html>`_.

**Comments, bug reports, patches and suggestions are very welcome!**

* Comments and suggestions: https://github.com/coin-or/pulp/discussions
* Bug reports: https://github.com/coin-or/pulp/issues
* Patches: https://github.com/coin-or/pulp/pulls

References
----------
[1] http://www.gnu.org/software/glpk/glpk.html
[2] http://www.coin-or.org/
[3] http://www.cplex.com/
[4] http://www.gurobi.com/
[5] http://www.mosek.com/

"""
from typing import List
from collections import Counter
import warnings
from time import time
import json
from time import monotonic as clock
from collections import OrderedDict
from GridCalEngine.Utils.ThirdParty.pulp.apis.highs_py import HiGHS

from GridCalEngine.Utils.ThirdParty.pulp.utilities import value
import GridCalEngine.Utils.ThirdParty.pulp.constants as const
import GridCalEngine.Utils.ThirdParty.pulp.mps_lp as mpslp
from GridCalEngine.Utils.ThirdParty.pulp.model.lp_objects import (LpVariable, LpConstraint, LpAffineExpression,
                                                                  LpFractionConstraint, LpConstraintVar,
                                                                  lp_constraint_from_dict)

# Default solver selection
LpSolverDefault = HiGHS(msg=False)


class LpProblem:
    """
    An LP Problem
    """

    def __init__(self, name="NoName", sense=const.LpMinimize):
        """
        Creates an LP Problem

        This function creates a new LP Problem  with the specified associated parameters

        :param name: name of the problem used in the output .lp file
        :param sense: of the LP problem objective.  \
                Either :data:`~pulp.const.LpMinimize` (default) \
                or :data:`~pulp.const.LpMaximize`.
        :return: An LP Problem
        """
        if " " in name:
            warnings.warn("Spaces are not permitted in the name. Converted to '_'")
            name = name.replace(" ", "_")

        self.objective = None
        self.constraints = OrderedDict()
        self.name = name
        self.sense = sense
        self.sos1 = dict()
        self.sos2 = dict()
        self.status = const.LpStatusNotSolved
        self.sol_status = const.LpSolutionNoSolutionFound
        self.noOverlap = 1
        self.solver = None
        self.modifiedVariables: List[LpVariable] = list()
        self.modifiedConstraints: List[LpConstraint] = list()
        self.resolveOK = False
        self._variables: List[LpVariable] = list()
        self._variable_ids = {}  # old school using dict.keys() for a set
        self.dummyVar = None
        self.solutionTime = 0
        self.solutionCpuTime = 0
        self.solverModel = None  # pointer to the implementation

        # locals
        self.lastUnused = 0

    def get_variables(self) -> List[LpVariable]:
        """

        :return:
        """
        return self._variables

    def __repr__(self) -> str:
        """
        Representation
        :return:
        """
        s = self.name + ":\n"
        if self.sense == 1:
            s += "MINIMIZE\n"
        else:
            s += "MAXIMIZE\n"
        s += repr(self.objective) + "\n"

        if self.constraints:
            s += "SUBJECT TO\n"
            for n, c in self.constraints.items():
                s += c.asCplexLpConstraint(n) + "\n"
        s += "VARIABLES\n"
        for v in self.variables():
            s += v.asCplexLpVariable() + " " + const.LpCategories[v.cat] + "\n"
        return s

    def __getstate__(self):
        # Remove transient data prior to pickling.
        state = self.__dict__.copy()
        del state["_variable_ids"]
        return state

    def __setstate__(self, state):
        # Update transient data prior to unpickling.
        self.__dict__.update(state)
        self._variable_ids = {}
        for v in self._variables:
            self._variable_ids[v.hash] = v

    def copy(self):
        """
        Make a copy of self. Expressions are copied by reference
        """
        lpcopy = LpProblem(name=self.name, sense=self.sense)
        lpcopy.objective = self.objective
        lpcopy.constraints = self.constraints.copy()
        lpcopy.sos1 = self.sos1.copy()
        lpcopy.sos2 = self.sos2.copy()
        return lpcopy

    def deepcopy(self):
        """
        Make a copy of self. Expressions are copied by value
        """
        lpcopy = LpProblem(name=self.name, sense=self.sense)
        if self.objective is not None:
            lpcopy.objective = self.objective.copy()
        lpcopy.constraints = {}
        for k, v in self.constraints.items():
            lpcopy.constraints[k] = v.copy()
        lpcopy.sos1 = self.sos1.copy()
        lpcopy.sos2 = self.sos2.copy()
        return lpcopy

    def toDict(self):
        """
        creates a dictionary from the model with as much data as possible.
        It replaces variables by variable names.
        So it requires to have unique names for variables.

        :return: dictionary with model data
        :rtype: dict
        """
        try:
            self.checkDuplicateVars()
        except const.PulpError:
            raise const.PulpError(
                "Duplicated names found in variables:\nto export the model, variable names need to be unique"
            )
        self.fixObjective()
        variables = self.variables()
        return dict(
            objective=dict(
                name=self.objective.name,
                coefficients=self.objective.toDict()
            ),
            constraints=[v.toDict() for v in self.constraints.values()],
            variables=[v.toDict() for v in variables],
            parameters=dict(
                name=self.name,
                sense=self.sense,
                status=self.status,
                sol_status=self.sol_status,
            ),
            sos1=list(self.sos1.values()),
            sos2=list(self.sos2.values()),
        )

    to_dict = toDict

    @classmethod
    def fromDict(cls, _dict):
        """
        Takes a dictionary with all necessary information to build a model.
        And returns a dictionary of variables and a problem object

        :param _dict: dictionary with the model stored
        :return: a tuple with a dictionary of variables and a :py:class:`LpProblem`
        """

        # we instantiate the problem
        params = _dict["parameters"]
        pb_params = {"name", "sense"}
        args = {k: params[k] for k in pb_params}
        pb = cls(**args)
        pb.status = params["status"]
        pb.sol_status = params["sol_status"]

        # recreate the variables.
        var = {v["name"]: LpVariable.fromDict(**v) for v in _dict["variables"]}

        # objective function.
        # we change the names for the objects:
        obj_e = {var[v["name"]]: v["value"] for v in _dict["objective"]["coefficients"]}
        pb += LpAffineExpression(e=obj_e, name=_dict["objective"]["name"])

        # constraints
        # we change the names for the objects:
        def edit_const(values_dict):
            """

            :param values_dict:
            :return:
            """
            values_dict = dict(values_dict)
            values_dict["coefficients"] = {
                var[v["name"]]: v["value"] for v in values_dict["coefficients"]
            }
            return const

        constraints = [edit_const(v) for v in _dict["constraints"]]
        for cst in constraints:
            pb += lp_constraint_from_dict(cst)

        # last, parameters, other options
        def list2dict(lst):
            """

            :param lst:
            :return:
            """
            return {k: v for k, v in enumerate(lst)}

        # list_to_dict = lambda v: {k: v for k, v in enumerate(v)}
        pb.sos1 = list2dict(_dict["sos1"])
        pb.sos2 = list2dict(_dict["sos2"])

        return var, pb

    from_dict = fromDict

    def toJson(self, filename):
        """
        Creates a json file from the LpProblem information

        :param str filename: filename to write json
        :return: None
        """
        with open(filename, "w") as fp:
            json.dump(self.toDict(), fp, indent=4)

    to_json = toJson

    @classmethod
    def fromJson(cls, filename):
        """
        Creates a new Lp Problem from a json file with information

        :param str filename: json file name
        :return: a tuple with a dictionary of variables and an LpProblem
        :rtype: (dict, :py:class:`LpProblem`)
        """
        with open(filename) as f:
            data = json.load(f)
        return cls.fromDict(data)

    from_json = fromJson

    @classmethod
    def fromMPS(cls, filename, sense=const.LpMinimize, **kwargs):
        """

        :param filename:
        :param sense:
        :param kwargs:
        :return:
        """
        data = mpslp.readMPS(filename, sense=sense, **kwargs)
        return cls.fromDict(data)

    def normalisedNames(self):
        """

        :return:
        """
        constraintsNames = {k: "C%07d" % i for i, k in enumerate(self.constraints)}
        _variables = self.variables()
        variablesNames = {k.name: "X%07d" % i for i, k in enumerate(_variables)}
        return constraintsNames, variablesNames, "OBJ"

    def isMIP(self) -> bool:
        """

        :return:
        """
        for v in self.variables():
            if v.cat == const.LpInteger:
                return True
        return False

    def roundSolution(self, epsInt=1e-5, eps=1e-7):
        """
        Rounds the lp variables

        Inputs:
            - none

        Side Effects:
            - The lp variables are rounded
        """
        for v in self.variables():
            v.round(epsInt, eps)

    def unusedConstraintName(self):
        """

        :return:
        """
        self.lastUnused += 1
        while 1:
            s = "_C%d" % self.lastUnused
            if s not in self.constraints:
                break
            self.lastUnused += 1
        return s

    def valid(self, eps=0):
        """

        :param eps:
        :return:
        """
        for v in self.variables():
            if not v.valid(eps):
                return False
        for c in self.constraints.values():
            if not c.valid(eps):
                return False
        else:
            return True

    def infeasibilityGap(self, mip=1):
        """

        :param mip:
        :return:
        """
        gap = 0
        for v in self.variables():
            gap = max(abs(v.infeasibilityGap(mip)), gap)
        for c in self.constraints.values():
            if not c.valid(0):
                gap = max(abs(c.value()), gap)
        return gap

    def addVariable(self, variable: LpVariable):
        """
        Adds a variable to the problem before a constraint is added

        :param variable: the variable to be added
        """
        if variable.hash not in self._variable_ids:
            self._variables.append(variable)
            self._variable_ids[variable.hash] = variable

    def addVariables(self, variables: List[LpVariable]):
        """
        Adds variables to the problem before a constraint is added

        :param variables: the variables to be added
        """
        for v in variables:
            self.addVariable(v)

    def variables(self) -> List[LpVariable]:
        """
        Returns the problem variables

        :return: A list containing the problem variables
        :rtype: (list, :py:class:`LpVariable`)
        """
        if self.objective:
            self.addVariables(list(self.objective.keys()))
        for c in self.constraints.values():
            self.addVariables(list(c.keys()))
        self._variables.sort(key=lambda v: v.name)
        return self._variables

    def variablesDict(self):
        """

        :return:
        """
        variables = dict()
        if self.objective:
            for v in self.objective:
                variables[v.name] = v
        for c in list(self.constraints.values()):
            for v in c:
                variables[v.name] = v
        return variables

    def add(self, constraint: LpConstraint, name=None):
        """
        Adds a constraint to the problem.
        :param constraint:
        :param name:
        :return:
        """
        self.addConstraint(constraint, name)

    def addConstraint(self, constraint: LpConstraint, name=None):
        """

        :param constraint:
        :param name:
        :return:
        """
        if not isinstance(constraint, LpConstraint):
            raise TypeError("Can only add LpConstraint objects")
        if name:
            constraint.name = name
        try:
            if constraint.name:
                name = constraint.name
            else:
                name = self.unusedConstraintName()
        except AttributeError:
            raise TypeError("Can only add LpConstraint objects")
            # removed as this test fails for empty constraints
        #        if len(constraint) == 0:
        #            if not constraint.valid():
        #                raise ValueError, "Cannot add false constraints"
        if name in self.constraints:
            if self.noOverlap:
                raise const.PulpError("overlapping constraint names: " + name)
            else:
                print("Warning: overlapping constraint names:", name)
        self.constraints[name] = constraint
        self.modifiedConstraints.append(constraint)
        self.addVariables(list(constraint.keys()))

    def setObjective(self, obj: LpAffineExpression | LpVariable | LpConstraintVar):
        """
        Sets the input variable as the objective function. Used in Columnwise Modelling

        :param obj: the objective function of type :class:`LpConstraintVar`

        Side Effects:
            - The objective function is set
        """
        if isinstance(obj, LpVariable):
            # allows the user to add a LpVariable as an objective
            obj = obj + 0.0

        try:
            obj = obj.constraint
            name = obj.name
            self.objective.name = name
        except AttributeError:
            name = None

        self.objective = obj
        self.resolveOK = False

    def __iadd__(self, other):
        if isinstance(other, tuple):
            other, name = other
        else:
            name = None
        if other is True:
            return self
        elif other is False:
            raise TypeError("A False object cannot be passed as a constraint")
        elif isinstance(other, LpConstraintVar):
            self.addConstraint(other.constraint)
        elif isinstance(other, LpConstraint):
            self.addConstraint(other, name)
        elif isinstance(other, LpAffineExpression):
            if self.objective is not None:
                warnings.warn("Overwriting previously set objective.")
            self.objective = other
            if name is not None:
                # we may keep the LpAffineExpression name
                self.objective.name = name
        elif isinstance(other, LpVariable) or isinstance(other, (int, float)):
            if self.objective is not None:
                warnings.warn("Overwriting previously set objective.")
            self.objective = LpAffineExpression(other)
            self.objective.name = name
        else:
            raise TypeError(
                "Can only add LpConstraintVar, LpConstraint, LpAffineExpression or True objects"
            )
        return self

    def extend(self, other, use_objective=True):
        """
        extends an LpProblem by adding constraints either from a dictionary
        a tuple or another LpProblem object.

        :param bool use_objective: determines whether the objective is imported from
        the other problem

        For dictionaries the constraints will be named with the keys
        For tuples an unique name will be generated
        For LpProblems the name of the problem will be added to the constraints
        name
        """
        if isinstance(other, dict):
            for name in other:
                self.constraints[name] = other[name]
        elif isinstance(other, LpProblem):
            for v in set(other.variables()).difference(self.variables()):
                v.name = other.name + v.name
            for name, c in other.constraints.items():
                c.name = other.name + name
                self.addConstraint(c)
            if use_objective:
                self.objective += other.objective
        else:
            for c in other:
                if isinstance(c, tuple):
                    name = c[0]
                    c = c[1]
                else:
                    name = None
                if not name:
                    name = c.name
                if not name:
                    name = self.unusedConstraintName()
                self.constraints[name] = c

    def coefficients(self, translation=None):
        coefs = []
        if translation == None:
            for c in self.constraints:
                cst = self.constraints[c]
                coefs.extend([(v.name, c, cst[v]) for v in cst])
        else:
            for c in self.constraints:
                ctr = translation[c]
                cst = self.constraints[c]
                coefs.extend([(translation[v.name], ctr, cst[v]) for v in cst])
        return coefs

    def writeMPS(
            self, filename, mpsSense=0, rename=0, mip=1, with_objsense: bool = False
    ):
        """
        Writes an mps files from the problem information

        :param str filename: name of the file to write
        :param int mpsSense:
        :param bool rename: if True, normalized names are used for variables and constraints
        :param mip: variables and variable renames
        :return:

        Side Effects:
            - The file is created
        """
        return mpslp.writeMPS(
            self,
            filename,
            mpsSense=mpsSense,
            rename=rename,
            mip=mip,
            with_objsense=with_objsense,
        )

    def writeLP(self, filename, writeSOS=1, mip=1, max_length=100):
        """
        Write the given Lp problem to a .lp file.

        This function writes the specifications (objective function,
        constraints, variables) of the defined Lp problem to a file.

        :param str filename: the name of the file to be created.
        :return: variables

        Side Effects:
            - The file is created
        """
        return mpslp.writeLP(
            self, filename=filename, writeSOS=writeSOS, mip=mip, max_length=max_length
        )

    def checkDuplicateVars(self) -> None:
        """
        Checks if there are at least two variables with the same name
        :return: 1
        :raises `const.PulpError`: if there ar duplicates
        """
        name_counter = Counter(variable.name for variable in self.variables())
        repeated_names = {
            (name, count) for name, count in name_counter.items() if count >= 2
        }
        if repeated_names:
            raise const.PulpError(f"Repeated variable names: {repeated_names}")

    def checkLengthVars(self, max_length: int) -> None:
        """
        Checks if variables have names smaller than `max_length`
        :param int max_length: max size for variable name
        :return:
        :raises const.PulpError: if there is at least one variable that has a long name
        """
        long_names = [
            variable.name
            for variable in self.variables()
            if len(variable.name) > max_length
        ]
        if long_names:
            raise const.PulpError(
                f"Variable names too long for Lp format: {long_names}"
            )

    def assignVarsVals(self, values):
        variables = self.variablesDict()
        for name in values:
            if name != "__dummy":
                variables[name].varValue = values[name]

    def assignVarsDj(self, values):
        variables = self.variablesDict()
        for name in values:
            if name != "__dummy":
                variables[name].dj = values[name]

    def assignConsPi(self, values):
        for name in values:
            try:
                self.constraints[name].pi = values[name]
            except KeyError:
                pass

    def assignConsSlack(self, values, activity=False):
        for name in values:
            try:
                if activity:
                    # reports the activity not the slack
                    self.constraints[name].slack = -1 * (
                            self.constraints[name].constant + float(values[name])
                    )
                else:
                    self.constraints[name].slack = float(values[name])
            except KeyError:
                pass

    def get_dummyVar(self):
        if self.dummyVar is None:
            self.dummyVar = LpVariable("__dummy", 0, 0)
        return self.dummyVar

    def fixObjective(self):
        if self.objective is None:
            self.objective = 0
            wasNone = 1
        else:
            wasNone = 0
        if not isinstance(self.objective, LpAffineExpression):
            self.objective = LpAffineExpression(self.objective)
        if self.objective.isNumericalConstant():
            dummyVar = self.get_dummyVar()
            self.objective += dummyVar
        else:
            dummyVar = None
        return wasNone, dummyVar

    def restoreObjective(self, wasNone, dummyVar):
        if wasNone:
            self.objective = None
        elif not dummyVar is None:
            self.objective -= dummyVar

    def solve(self, solver=None, **kwargs):
        """
        Solve the given Lp problem.

        This function changes the problem to make it suitable for solving
        then calls the solver.actualSolve() method to find the solution

        :param solver:  Optional: the specific solver to be used, defaults to the
              default solver.

        Side Effects:
            - The attributes of the problem object are changed in
              :meth:`~pulp.solver.LpSolver.actualSolve()` to reflect the Lp solution
        """

        if not solver:
            solver = self.solver

        if not solver:
            solver = LpSolverDefault

        wasNone, dummyVar = self.fixObjective()
        # time it
        self.startClock()
        status = solver.actualSolve(self, **kwargs)
        self.stopClock()
        self.restoreObjective(wasNone, dummyVar)
        self.solver = solver
        return status

    def startClock(self) -> None:
        "initializes properties with the current time"
        self.solutionCpuTime = -clock()
        self.solutionTime = -time()

    def stopClock(self) -> None:
        "updates time wall time and cpu time"
        self.solutionTime += time()
        self.solutionCpuTime += clock()

    def sequentialSolve(self, objectives, absoluteTols=None, relativeTols=None, solver=None, debug=False):
        """
        Solve the given Lp problem with several objective functions.

        This function sequentially changes the objective of the problem
        and then adds the objective function as a constraint

        :param objectives: the list of objectives to be used to solve the problem
        :param absoluteTols: the list of absolute tolerances to be applied to
           the constraints should be +ve for a minimise objective
        :param relativeTols: the list of relative tolerances applied to the constraints
        :param solver: the specific solver to be used, defaults to the default solver.
        :param debug
        """
        # TODO Add a penalty variable to make problems elastic
        # TODO add the ability to accept different status values i.e. infeasible etc

        if not solver:
            solver = self.solver
        if not solver:
            solver = LpSolverDefault
        if not absoluteTols:
            absoluteTols = [0] * len(objectives)
        if not relativeTols:
            relativeTols = [1] * len(objectives)
        # time it
        self.startClock()
        statuses = []
        for i, (obj, absol, rel) in enumerate(
                zip(objectives, absoluteTols, relativeTols)
        ):
            self.setObjective(obj)
            status = solver.actualSolve(self)
            statuses.append(status)
            if debug:
                self.writeLP(f"{i}Sequence.lp")
            if self.sense == const.LpMinimize:
                self += obj <= value(obj) * rel + absol, f"Sequence_Objective_{i}"
            elif self.sense == const.LpMaximize:
                self += obj >= value(obj) * rel + absol, f"Sequence_Objective_{i}"
        self.stopClock()
        self.solver = solver
        return statuses

    def resolve(self, solver=None, **kwargs):
        """
        resolves an Problem using the same solver as previously
        """
        if not solver:
            solver = self.solver
        if self.resolveOK:
            return self.solver.actualResolve(self, **kwargs)
        else:
            return self.solve(solver=solver, **kwargs)

    def setSolver(self, solver=LpSolverDefault):
        """Sets the Solver for this problem useful if you are using
        resolve
        """
        self.solver = solver

    def numVariables(self):
        """

        :return: number of variables in model
        """
        return len(self._variable_ids)

    def numConstraints(self):
        """

        :return: number of constraints in model
        """
        return len(self.constraints)

    def getSense(self):
        """

        :return:
        """
        return self.sense

    def assignStatus(self, status: int, sol_status: int = None) -> bool:
        """
        Sets the status of the model after solving.
        :param status: code for the status of the model
        :param sol_status: code for the status of the solution
        :return:
        """
        if status not in const.LpStatus:
            raise const.PulpError("Invalid status code: " + str(status))

        if sol_status is not None and sol_status not in const.LpSolution:
            raise const.PulpError("Invalid solution status code: " + str(sol_status))

        self.status = status
        if sol_status is None:
            sol_status = const.LpStatusToSolution.get(
                status, const.LpSolutionNoSolutionFound
            )
        self.sol_status = sol_status
        return True


class FixedElasticSubProblem(LpProblem):
    """
    Contains the subproblem generated by converting a fixed constraint
    :math:`\\sum_{i}a_i x_i = b` into an elastic constraint.

    :param constraint: The LpConstraint that the elastic constraint is based on
    :param penalty: penalty applied for violation (+ve or -ve) of the constraints
    :param proportionFreeBound:
        the proportional bound (+ve and -ve) on
        constraint violation that is free from penalty
    :param proportionFreeBoundList: the proportional bound on \
        constraint violation that is free from penalty, expressed as a list\
        where [-ve, +ve]
    """

    def __init__(
            self,
            constraint,
            penalty=None,
            proportionFreeBound=None,
            proportionFreeBoundList=None,
    ):
        subProblemName = f"{constraint.name}_elastic_SubProblem"
        LpProblem.__init__(self, subProblemName, const.LpMinimize)
        self.objective = LpAffineExpression()
        self.constraint = constraint
        self.constant = constraint.constant
        self.RHS = -constraint.constant
        self.objective = LpAffineExpression()
        self += constraint, "_Constraint"
        # create and add these variables but disabled
        self.freeVar = LpVariable("_free_bound", upBound=0, lowBound=0)
        self.upVar = LpVariable("_pos_penalty_var", upBound=0, lowBound=0)
        self.lowVar = LpVariable("_neg_penalty_var", upBound=0, lowBound=0)
        constraint.addInPlace(self.freeVar + self.lowVar + self.upVar)
        if proportionFreeBound:
            proportionFreeBoundList = [proportionFreeBound, proportionFreeBound]
        if proportionFreeBoundList:
            # add a costless variable
            self.freeVar.upBound = abs(constraint.constant * proportionFreeBoundList[0])
            self.freeVar.lowBound = -abs(
                constraint.constant * proportionFreeBoundList[1]
            )
            # Note the reversal of the upbound and lowbound due to the nature of the
            # variable
        if penalty is not None:
            # activate these variables
            self.upVar.upBound = None
            self.lowVar.lowBound = None
            self.objective = penalty * self.upVar - penalty * self.lowVar

    def _findValue(self, attrib):
        """
        safe way to get the value of a variable that may not exist
        """
        var = getattr(self, attrib, 0)
        if var:
            if value(var) is not None:
                return value(var)
            else:
                return 0.0
        else:
            return 0.0

    def isViolated(self):
        """
        returns true if the penalty variables are non-zero
        """
        upVar = self._findValue("upVar")
        lowVar = self._findValue("lowVar")
        freeVar = self._findValue("freeVar")
        result = abs(upVar + lowVar) >= const.EPS
        if result:
            const.debug_log(
                f"isViolated {self.name}, upVar {upVar}, lowVar {lowVar}, freeVar {freeVar} result {result}")
            const.debug_log(f"isViolated value lhs {self.findLHSValue()} constant {self.RHS}")
        return result

    def findDifferenceFromRHS(self):
        """
        The amount the actual value varies from the RHS (sense: LHS - RHS)
        """
        return self.findLHSValue() - self.RHS

    def findLHSValue(self):
        """
        for elastic constraints finds the LHS value of the constraint without
        the free variable and or penalty variable assumes the constant is on the
        rhs
        """
        upVar = self._findValue("upVar")
        lowVar = self._findValue("lowVar")
        freeVar = self._findValue("freeVar")
        return self.constraint.value() - self.constant - upVar - lowVar - freeVar

    def deElasticize(self):
        """de-elasticize constraint"""
        self.upVar.upBound = 0
        self.lowVar.lowBound = 0

    def reElasticize(self):
        """
        Make the Subproblem elastic again after deElasticize
        """
        self.upVar.lowBound = 0
        self.upVar.upBound = None
        self.lowVar.upBound = 0
        self.lowVar.lowBound = None

    def alterName(self, name):
        """
        Alters the name of anonymous parts of the problem

        """
        self.name = f"{name}_elastic_SubProblem"
        if hasattr(self, "freeVar"):
            self.freeVar.name = self.name + "_free_bound"
        if hasattr(self, "upVar"):
            self.upVar.name = self.name + "_pos_penalty_var"
        if hasattr(self, "lowVar"):
            self.lowVar.name = self.name + "_neg_penalty_var"


class FractionElasticSubProblem(FixedElasticSubProblem):
    """
    FractionElasticSubProblem

    Contains the subproblem generated by converting a Fraction constraint
    numerator/(numerator+complement) = b
    into an elastic constraint
    """

    def __init__(self,
                 name,
                 numerator,
                 RHS,
                 sense,
                 complement=None,
                 denominator=None,
                 penalty=None,
                 proportionFreeBound=None,
                 proportionFreeBoundList=None, ):
        """

        :param name: The name of the elastic subproblem
        :param numerator:
        :param RHS:
        :param sense:
        :param complement:
        :param denominator:
        :param penalty: penalty applied for violation (+ve or -ve) of the constraints
        :param proportionFreeBound: the proportional bound (+ve and -ve) on
        constraint violation that is free from penalty
        :param proportionFreeBoundList: the proportional bound on
        constraint violation that is free from penalty, expressed as a list
        where [-ve, +ve]
        """
        subProblemName = f"{name}_elastic_SubProblem"

        self.numerator = numerator

        if denominator is None and complement is not None:
            self.complement = complement
            self.denominator = numerator + complement

        elif denominator is not None and complement is None:
            self.denominator = denominator
            self.complement = denominator - numerator

        else:
            raise const.PulpError("only one of denominator and complement must be specified")

        self.RHS = RHS
        self.lowTarget = self.upTarget = None

        LpProblem.__init__(self, subProblemName, const.LpMinimize)

        self.freeVar = LpVariable("_free_bound", upBound=0, lowBound=0)
        self.upVar = LpVariable("_pos_penalty_var", upBound=0, lowBound=0)
        self.lowVar = LpVariable("_neg_penalty_var", upBound=0, lowBound=0)

        if proportionFreeBound:
            proportionFreeBoundList = [proportionFreeBound, proportionFreeBound]
        if proportionFreeBoundList:
            upProportionFreeBound, lowProportionFreeBound = proportionFreeBoundList
        else:
            upProportionFreeBound, lowProportionFreeBound = (0, 0)

        # create an objective
        self += LpAffineExpression()

        # There are three cases if the constraint.sense is ==, <=, >=
        if sense in [const.LpConstraintEQ, const.LpConstraintLE]:
            # create a constraint the sets the upper bound of target
            self.upTarget = RHS + upProportionFreeBound
            self.upConstraint = LpFractionConstraint(self.numerator,
                                                     self.complement,
                                                     const.LpConstraintLE,
                                                     self.upTarget,
                                                     denominator=self.denominator)
            if penalty is not None:
                self.lowVar.lowBound = None
                self.objective += -1 * penalty * self.lowVar
                self.upConstraint += self.lowVar

            self += self.upConstraint, "_upper_constraint"

        if sense in [const.LpConstraintEQ, const.LpConstraintGE]:
            # create a constraint the sets the lower bound of target
            self.lowTarget = RHS - lowProportionFreeBound
            self.lowConstraint = LpFractionConstraint(
                self.numerator,
                self.complement,
                const.LpConstraintGE,
                self.lowTarget,
                denominator=self.denominator,
            )

            if penalty is not None:
                self.upVar.upBound = None
                self.objective += penalty * self.upVar
                self.lowConstraint += self.upVar

            self += self.lowConstraint, "_lower_constraint"

    def findLHSValue(self):
        """
        for elastic constraints finds the LHS value of the constraint without
        the free variable and or penalty variable assumes the constant is on the
        rhs
        """
        # uses code from LpFractionConstraint
        if abs(value(self.denominator)) >= const.EPS:
            return value(self.numerator) / value(self.denominator)
        else:
            if abs(value(self.numerator)) <= const.EPS:
                # zero divided by zero will return 1
                return 1.0
            else:
                raise ZeroDivisionError

    def isViolated(self):
        """
        returns true if the penalty variables are non-zero
        """
        if abs(value(self.denominator)) >= const.EPS:
            if self.lowTarget is not None:
                if self.lowTarget > self.findLHSValue():
                    return True
            if self.upTarget is not None:
                if self.findLHSValue() > self.upTarget:
                    return True
        else:
            # if the denominator is zero the constraint is satisfied
            return False
