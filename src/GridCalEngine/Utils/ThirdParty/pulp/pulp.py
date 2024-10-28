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
from collections.abc import Iterable
from GridCalEngine.Utils.ThirdParty.pulp.model.lp_objects import (LpAffineExpression)

import json
from typing import List
from GridCalEngine.Utils.ThirdParty.pulp.apis.cplex_cmd import CPLEX_CMD
from GridCalEngine.Utils.ThirdParty.pulp.apis.cplex_py import CPLEX_PY
from GridCalEngine.Utils.ThirdParty.pulp.apis.gurobi_py import GUROBI
from GridCalEngine.Utils.ThirdParty.pulp.apis.gurobi_cmd import GUROBI_CMD
from GridCalEngine.Utils.ThirdParty.pulp.apis.scip_api import SCIP_PY, SCIP_CMD, FSCIP_CMD
from GridCalEngine.Utils.ThirdParty.pulp.apis.xpress_api import XPRESS_CMD, XPRESS, XPRESS_PY
from GridCalEngine.Utils.ThirdParty.pulp.apis.highs_py import HiGHS
from GridCalEngine.Utils.ThirdParty.pulp.apis.highs_cmd import HiGHS_CMD
from GridCalEngine.Utils.ThirdParty.pulp.apis.copt_api import COPT, COPT_DLL, COPT_CMD
from GridCalEngine.Utils.ThirdParty.pulp.apis.lp_solver_cmd import (Parser, config_filename, cplex_dll_path, coinMP_path)
from GridCalEngine.Utils.ThirdParty.pulp.constants import PulpSolverError

_all_solvers = [
    CPLEX_CMD,
    CPLEX_PY,
    GUROBI,
    GUROBI_CMD,
    XPRESS,
    XPRESS_CMD,
    XPRESS_PY,
    SCIP_CMD,
    FSCIP_CMD,
    SCIP_PY,
    HiGHS,
    HiGHS_CMD,
    COPT,
    COPT_DLL,
    COPT_CMD,
]


def setConfigInformation(**keywords):
    """
    set the data in the configuration file
    at the moment will only edit things in [locations]
    the keyword value pairs come from the keywords dictionary
    """
    # TODO: extend if we ever add another section in the config file
    # read the old configuration
    config = Parser()
    config.read(config_filename)
    # set the new keys
    for key, val in keywords.items():
        config.set("locations", key, val)
    # write the new configuration
    fp = open(config_filename, "w")
    config.write(fp)
    fp.close()


def configSolvers():
    """
    Configure the path the the solvers on the command line

    Designed to configure the file locations of the solvers from the
    command line after installation
    """
    configlist = [
        (cplex_dll_path, "cplexpath", "CPLEX: "),
        (coinMP_path, "coinmppath", "CoinMP dll (windows only): "),
    ]
    print(
        "Please type the full path including filename and extension \n"
        + "for each solver available"
    )
    configdict = {}
    for default, key, msg in configlist:
        value = input(msg + "[" + str(default) + "]")
        if value:
            configdict[key] = value
    setConfigInformation(**configdict)


def getSolver(solver, *args, **kwargs):
    """
    Instantiates a solver from its name

    :param str solver: solver name to create
    :param args: additional arguments to the solver
    :param kwargs: additional keyword arguments to the solver
    :return: solver of type :py:class:`LpSolver`
    """
    mapping = {k.name: k for k in _all_solvers}
    try:
        return mapping[solver](*args, **kwargs)
    except KeyError:
        raise PulpSolverError(
            "The solver {} does not exist in PuLP.\nPossible options are: \n{}".format(
                solver, mapping.keys()
            )
        )


def getSolverFromDict(data):
    """
    Instantiates a solver from a dictionary with its data

    :param dict data: a dictionary with, at least an "solver" key with the name
        of the solver to create
    :return: a solver of type :py:class:`LpSolver`
    :raises PulpSolverError: if the dictionary does not have the "solver" key
    :rtype: LpSolver
    """
    solver = data.pop("solver", None)
    if solver is None:
        raise PulpSolverError("The json file has no solver attribute.")
    return getSolver(solver, **data)


def getSolverFromJson(filename):
    """
    Instantiates a solver from a json file with its data

    :param str filename: name of the json file to read
    :return: a solver of type :py:class:`LpSolver`
    :rtype: LpSolver
    """
    with open(filename) as f:
        data = json.load(f)
    return getSolverFromDict(data)


def listSolvers(onlyAvailable: bool = False) -> List[str]:
    """
    List the names of all the existing solvers in PuLP

    :param bool onlyAvailable: if True, only show the available solvers
    :return: list of solver names
    :rtype: list
    """
    result = []
    for s in _all_solvers:
        solver = s(msg=False)
        if (not onlyAvailable) or solver.available():
            result.append(solver.name)
        del solver
    return result


def lpSum(vector):
    """
    Calculate the sum of a list of linear expressions

    :param vector: A list of linear expressions
    """
    return LpAffineExpression().addInPlace(vector)


def _vector_like(obj):
    return isinstance(obj, Iterable) and not isinstance(obj, LpAffineExpression)


def lpDot(v1, v2):
    """Calculate the dot product of two lists of linear expressions"""
    if not _vector_like(v1) and not _vector_like(v2):
        return v1 * v2
    elif not _vector_like(v1):
        return lpDot([v1] * len(v2), v2)
    elif not _vector_like(v2):
        return lpDot(v1, [v2] * len(v1))
    else:
        return lpSum([lpDot(e1, e2) for e1, e2 in zip(v1, v2)])
