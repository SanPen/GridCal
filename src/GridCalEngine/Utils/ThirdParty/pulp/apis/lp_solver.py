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

"""
This file contains the solver classes for PuLP
Note that the solvers that require a compiled extension may not work in
the current version
"""
from __future__ import annotations
import ctypes
import json
from typing import TYPE_CHECKING
import GridCalEngine.Utils.ThirdParty.pulp.sparse as sparse
import GridCalEngine.Utils.ThirdParty.pulp.constants as const
from GridCalEngine.Utils.ThirdParty.pulp.constants import to_string

if TYPE_CHECKING:
    from GridCalEngine.Utils.ThirdParty.pulp.model.lp_problem import LpProblem


def ctypesArrayFill(myList, tpe=ctypes.c_double):
    """
    Creates a c array with ctypes from a python list
    type is the type of the c array
    """
    ctype = tpe * len(myList)
    cList = ctype()
    for i, elem in enumerate(myList):
        cList[i] = elem
    return cList


class LpSolver:
    """A generic LP Solver"""

    name = "LpSolver"

    def __init__(self, mip=True, msg=True, options=None, timeLimit=None, *args, **kwargs):
        """
        :param bool mip: if False, assume LP even if integer variables
        :param bool msg: if False, no log is shown
        :param list options:
        :param float timeLimit: maximum time for solver (in seconds)
        :param args:
        :param kwargs: optional named options to pass to each solver,
                        e.g. gapRel=0.1, gapAbs=10, logPath="",
        """
        if options is None:
            options = list()
        self.mip = mip
        self.msg = msg
        self.options = options
        self.timeLimit = timeLimit

        # here we will store all other relevant information including:
        # gapRel, gapAbs, maxMemory, maxNodes, threads, logPath, timeMode
        self.optionsDict = {k: v for k, v in kwargs.items() if v is not None}

        # pointer to the solver model
        self.solverModel = None

        # solving time
        self.solveTime = 0.0

        self.addedVars = 0
        self.addedRows = 0
        self.v2n = dict()
        self.vname2n = dict()
        self.n2v = dict()
        self.c2n = dict()
        self.n2c = dict()

    def available(self):
        """True if the solver is available"""
        raise NotImplementedError

    def actualSolve(self, lp):
        """
        Solve a well formulated lp problem
        """
        raise NotImplementedError

    def actualResolve(self, lp, **kwargs):
        """
        uses existing problem information and solves the problem
        If it is not implemented in the solver
        just solve again
        """
        self.actualSolve(lp)

    def copy(self):
        """
        Make a copy of self
        """

        aCopy = self.__class__()
        aCopy.mip = self.mip
        aCopy.msg = self.msg
        aCopy.options = self.options
        return aCopy

    def solve(self, lp):
        """Solve the problem lp"""
        # Always go through the solve method of LpProblem
        return lp.solve(self)

    # TODO: Not sure if this code should be here or in a child class
    def getCplexStyleArrays(self, lp: LpProblem, senseDict=None, LpVarCategories=None, LpObjSenses=None, infBound=1e20):
        """returns the arrays suitable to pass to a cdll Cplex
        or other solvers that are similar

        Copyright (c) Stuart Mitchell 2007
        """
        if senseDict is None:
            senseDict = {
                const.LpConstraintEQ: "E",
                const.LpConstraintLE: "L",
                const.LpConstraintGE: "G",
            }
        if LpVarCategories is None:
            LpVarCategories = {const.LpContinuous: "C", const.LpInteger: "I"}
        if LpObjSenses is None:
            LpObjSenses = {const.LpMaximize: -1, const.LpMinimize: 1}

        rangeCount = 0
        variables = list(lp.variables())
        numVars = len(variables)

        # associate each variable with a ordinal
        self.v2n = {variables[i]: i for i in range(numVars)}
        self.vname2n = {variables[i].name: i for i in range(numVars)}
        self.n2v = {i: variables[i] for i in range(numVars)}

        # objective values
        objSense = LpObjSenses[lp.sense]
        NumVarDoubleArray = ctypes.c_double * numVars
        objectCoeffs = NumVarDoubleArray()

        # print "Get objective Values"
        for v, val in lp.objective.items():
            objectCoeffs[self.v2n[v]] = val

        # values for variables
        objectConst = ctypes.c_double(0.0)
        NumVarStrArray = ctypes.c_char_p * numVars
        colNames = NumVarStrArray()
        lowerBounds = NumVarDoubleArray()
        upperBounds = NumVarDoubleArray()
        initValues = NumVarDoubleArray()

        for v in lp.variables():
            colNames[self.v2n[v]] = to_string(v.name)
            initValues[self.v2n[v]] = 0.0
            if v.lowBound is not None:
                lowerBounds[self.v2n[v]] = v.lowBound
            else:
                lowerBounds[self.v2n[v]] = -infBound
            if v.upBound is not None:
                upperBounds[self.v2n[v]] = v.upBound
            else:
                upperBounds[self.v2n[v]] = infBound
        # values for constraints
        numRows = len(lp.constraints)
        NumRowDoubleArray = ctypes.c_double * numRows
        NumRowStrArray = ctypes.c_char_p * numRows
        NumRowCharArray = ctypes.c_char * numRows
        rhsValues = NumRowDoubleArray()
        rangeValues = NumRowDoubleArray()
        rowNames = NumRowStrArray()
        rowType = NumRowCharArray()
        self.c2n = dict()
        self.n2c = dict()
        i = 0
        for c in lp.constraints:
            rhsValues[i] = -lp.constraints[c].constant
            # for ranged constraints a<= constraint >=b
            rangeValues[i] = 0.0
            rowNames[i] = to_string(c)
            rowType[i] = to_string(senseDict[lp.constraints[c].sense])
            self.c2n[c] = i
            self.n2c[i] = c
            i = i + 1

        # return the coefficient matrix as a series of vectors
        coeffs = lp.coefficients()
        sparseMatrix = sparse.Matrix(list(range(numRows)), list(range(numVars)))
        for var, row, coeff in coeffs:
            sparseMatrix.add(self.c2n[row], self.vname2n[var], coeff)

        (numels,
         mystartsBase,
         mylenBase,
         myindBase,
         myelemBase) = sparseMatrix.col_based_arrays()

        elemBase = ctypesArrayFill(myelemBase, ctypes.c_double)
        indBase = ctypesArrayFill(myindBase, ctypes.c_int)
        startsBase = ctypesArrayFill(mystartsBase, ctypes.c_int)
        lenBase = ctypesArrayFill(mylenBase, ctypes.c_int)

        # MIP Variables
        NumVarCharArray = ctypes.c_char * numVars
        columnType = NumVarCharArray()
        if lp.isMIP():
            for v in lp.variables():
                columnType[self.v2n[v]] = to_string(LpVarCategories[v.cat])

        self.addedVars = numVars
        self.addedRows = numRows

        return (
            numVars,
            numRows,
            numels,
            rangeCount,
            objSense,
            objectCoeffs,
            objectConst,
            rhsValues,
            rangeValues,
            rowType,
            startsBase,
            lenBase,
            indBase,
            elemBase,
            lowerBounds,
            upperBounds,
            initValues,
            colNames,
            rowNames,
            columnType,
            self.n2v,
            self.n2c,
        )

    def toDict(self):
        """

        :return:
        """
        data = dict(solver=self.name)
        for k in ["mip", "msg", "keepFiles"]:
            try:
                data[k] = getattr(self, k)
            except AttributeError:
                pass
        for k in ["timeLimit", "options"]:
            # with these ones, we only export if it has some content:
            try:
                value = getattr(self, k)
                if value:
                    data[k] = value
            except AttributeError:
                pass
        data.update(self.optionsDict)
        return data

    to_dict = toDict

    def toJson(self, filename, *args, **kwargs):
        """

        :param filename:
        :param args:
        :param kwargs:
        :return:
        """
        with open(filename, "w") as f:
            json.dump(self.toDict(), f, *args, **kwargs)

    to_json = toJson
