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
import re
import warnings
import math
from collections import OrderedDict
from collections.abc import Iterable
from GridCalEngine.Utils.ThirdParty.pulp.utilities import value
import GridCalEngine.Utils.ThirdParty.pulp.constants as const


class LpElement:
    """Base class for LpVariable and LpConstraintVar"""

    def __init__(self, name):
        """

        :param name:
        """
        illegal_chars = "-+[] ->/"
        self.expression = re.compile(f"[{re.escape(illegal_chars)}]")
        self.trans = str.maketrans(illegal_chars, "________")

        self.__name = name
        # self.hash MUST be different for each variable
        # else dict() will call the comparison operators that are overloaded
        self.hash = id(self)
        self.modified = True

    @property
    def name(self):
        """

        :return:
        """
        return self.__name

    @name.setter
    def name(self, val):
        if val:
            if self.expression.match(val):
                warnings.warn(
                    "The name {} has illegal characters that will be replaced by _".format(
                        val
                    )
                )
            self.__name = str(val).translate(self.trans)
        else:
            self.__name = None

    def __hash__(self):
        return self.hash

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name

    def __neg__(self):
        return -LpAffineExpression(self)

    def __pos__(self):
        return self

    def __bool__(self):
        return True

    def __add__(self, other):
        return LpAffineExpression(self) + other

    def __radd__(self, other):
        return LpAffineExpression(self) + other

    def __sub__(self, other):
        return LpAffineExpression(self) - other

    def __rsub__(self, other):
        return other - LpAffineExpression(self)

    def __mul__(self, other):
        return LpAffineExpression(self) * other

    def __rmul__(self, other):
        return LpAffineExpression(self) * other

    def __div__(self, other):
        return LpAffineExpression(self) / other

    def __rdiv__(self, other):
        raise TypeError("Expressions cannot be divided by a variable")

    def __le__(self, other):
        return LpAffineExpression(self) <= other

    def __ge__(self, other):
        return LpAffineExpression(self) >= other

    def __eq__(self, other):
        return LpAffineExpression(self) == other

    def __ne__(self, other):
        if isinstance(other, LpVariable):
            return self.name is not other.name
        elif isinstance(other, LpAffineExpression):
            if other.isAtomic():
                return self is not other.atom()
            else:
                return 1
        else:
            return 1


class LpVariable(LpElement):
    """
    This class models an LP Variable with the specified associated parameters

    :param name: The name of the variable used in the output .lp file
    :param lowBound: The lower bound on this variable's range.
        Default is negative infinity
    :param upBound: The upper bound on this variable's range.
        Default is positive infinity
    :param cat: The category this variable is in, Integer, Binary or
        Continuous(default)
    :param e: Used for column based modelling: relates to the variable's
        existence in the objective function and constraints
    """

    def __init__(self, name, lowBound=None, upBound=None, cat=const.LpContinuous, e=None):
        LpElement.__init__(self, name)
        self._lowbound_original = self.lowBound = lowBound
        self._upbound_original = self.upBound = upBound
        self.cat = cat
        self.varValue = None
        self.dj = None
        if cat == const.LpBinary:
            self._lowbound_original = self.lowBound = 0
            self._upbound_original = self.upBound = 1
            self.cat = const.LpInteger
        # Code to add a variable to constraints for column based
        # modelling.
        if e:
            self.add_expression(e)

    def toDict(self):
        """
        Exports a variable into a dictionary with its relevant information

        :return: a dictionary with the variable information
        :rtype: dict
        """
        return dict(
            lowBound=self.lowBound,
            upBound=self.upBound,
            cat=self.cat,
            varValue=self.varValue,
            dj=self.dj,
            name=self.name,
        )

    to_dict = toDict

    @classmethod
    def fromDict(cls, dj=None, varValue=None, **kwargs):
        """
        Initializes a variable object from information that comes from a dictionary (kwargs)

        :param dj: shadow price of the variable
        :param float varValue: the value to set the variable
        :param kwargs: arguments to initialize the variable
        :return: a :py:class:`LpVariable`
        :rtype: :LpVariable
        """
        var = cls(**kwargs)
        var.dj = dj
        var.varValue = varValue
        return var

    from_dict = fromDict

    def add_expression(self, e):
        self.expression = e
        self.addVariableToConstraints(e)

    @classmethod
    def matrix(
            cls,
            name,
            indices=None,
            lowBound=None,
            upBound=None,
            cat=const.LpContinuous,
            indexStart=[],
    ):
        if not isinstance(indices, tuple):
            indices = (indices,)
        if "%" not in name:
            name += "_%s" * len(indices)

        index = indices[0]
        indices = indices[1:]
        if len(indices) == 0:
            return [
                LpVariable(name % tuple(indexStart + [i]), lowBound, upBound, cat)
                for i in index
            ]
        else:
            return [
                LpVariable.matrix(
                    name, indices, lowBound, upBound, cat, indexStart + [i]
                )
                for i in index
            ]

    @classmethod
    def dicts(
            cls,
            name,
            indices=None,
            lowBound=None,
            upBound=None,
            cat=const.LpContinuous,
            indexStart=[],
    ):
        """
        This function creates a dictionary of :py:class:`LpVariable` with the specified associated parameters.

        :param name: The prefix to the name of each LP variable created
        :param indices: A list of strings of the keys to the dictionary of LP
            variables, and the main part of the variable name itself
        :param lowBound: The lower bound on these variables' range. Default is
            negative infinity
        :param upBound: The upper bound on these variables' range. Default is
            positive infinity
        :param cat: The category these variables are in, Integer or
            Continuous(default)

        :return: A dictionary of :py:class:`LpVariable`
        """

        if not isinstance(indices, tuple):
            indices = (indices,)
        if "%" not in name:
            name += "_%s" * len(indices)

        index = indices[0]
        indices = indices[1:]
        d = {}
        if len(indices) == 0:
            for i in index:
                d[i] = LpVariable(
                    name % tuple(indexStart + [str(i)]), lowBound, upBound, cat
                )
        else:
            for i in index:
                d[i] = LpVariable.dicts(
                    name, indices, lowBound, upBound, cat, indexStart + [i]
                )
        return d

    @classmethod
    def dict(cls, name, indices, lowBound=None, upBound=None, cat=const.LpContinuous):
        if not isinstance(indices, tuple):
            indices = (indices,)
        if "%" not in name:
            name += "_%s" * len(indices)

        lists = indices

        if len(indices) > 1:
            # Cartesian product
            res = []
            while len(lists):
                first = lists[-1]
                nres = []
                if res:
                    if first:
                        for f in first:
                            nres.extend([[f] + r for r in res])
                    else:
                        nres = res
                    res = nres
                else:
                    res = [[f] for f in first]
                lists = lists[:-1]
            index = [tuple(r) for r in res]
        elif len(indices) == 1:
            index = indices[0]
        else:
            return {}

        d = {}
        for i in index:
            d[i] = cls(name % i, lowBound, upBound, cat)
        return d

    def getLb(self):
        return self.lowBound

    def getUb(self):
        return self.upBound

    def bounds(self, low, up):
        self.lowBound = low
        self.upBound = up
        self.modified = True

    def positive(self):
        self.bounds(0, None)

    def value(self):
        return self.varValue

    def round(self, epsInt=1e-5, eps=1e-7):
        if self.varValue is not None:
            if (
                    self.upBound != None
                    and self.varValue > self.upBound
                    and self.varValue <= self.upBound + eps
            ):
                self.varValue = self.upBound
            elif (
                    self.lowBound != None
                    and self.varValue < self.lowBound
                    and self.varValue >= self.lowBound - eps
            ):
                self.varValue = self.lowBound
            if (
                    self.cat == const.LpInteger
                    and abs(round(self.varValue) - self.varValue) <= epsInt
            ):
                self.varValue = round(self.varValue)

    def roundedValue(self, eps=1e-5):
        if (
                self.cat == const.LpInteger
                and self.varValue != None
                and abs(self.varValue - round(self.varValue)) <= eps
        ):
            return round(self.varValue)
        else:
            return self.varValue

    def valueOrDefault(self):
        """

        :return:
        """
        if self.varValue is not None:
            return self.varValue

        elif self.lowBound is not None:

            if self.upBound is not None:

                if 0 >= self.lowBound and 0 <= self.upBound:
                    return 0

                else:
                    if self.lowBound >= 0:
                        return self.lowBound
                    else:
                        return self.upBound
            else:
                if 0 >= self.lowBound:
                    return 0
                else:
                    return self.lowBound

        elif self.upBound is not None:
            if 0 <= self.upBound:
                return 0
            else:
                return self.upBound
        else:
            return 0

    def valid(self, eps):
        """

        :param eps:
        :return:
        """
        if self.name == "__dummy" and self.varValue is None:
            return True

        if self.varValue is None:
            return False

        if self.upBound is not None and self.varValue > self.upBound + eps:
            return False

        if self.lowBound is not None and self.varValue < self.lowBound - eps:
            return False

        if self.cat == const.LpInteger and abs(round(self.varValue) - self.varValue) > eps:
            return False

        return True

    def infeasibilityGap(self, mip=1):
        """

        :param mip:
        :return:
        """
        if self.varValue is None:
            raise ValueError("variable value is None")

        if self.upBound is not None and self.varValue > self.upBound:
            return self.varValue - self.upBound

        if self.lowBound is not None and self.varValue < self.lowBound:
            return self.varValue - self.lowBound

        if mip and self.cat == const.LpInteger and round(self.varValue) - self.varValue != 0:
            return round(self.varValue) - self.varValue

        return 0

    def isBinary(self):
        """

        :return:
        """
        return self.cat == const.LpInteger and self.lowBound == 0 and self.upBound == 1

    def isInteger(self):
        """

        :return:
        """
        return self.cat == const.LpInteger

    def isFree(self):
        """

        :return:
        """
        return self.lowBound is None and self.upBound is None

    def isConstant(self):
        """

        :return:
        """
        return self.lowBound is not None and self.upBound == self.lowBound

    def isPositive(self):
        """

        :return:
        """
        return self.lowBound == 0 and self.upBound is None

    def asCplexLpVariable(self):
        """

        :return:
        """
        if self.isFree():
            return self.name + " free"

        if self.isConstant():
            return self.name + f" = {self.lowBound:.12g}"

        if self.lowBound is None:
            s = "-inf <= "
        # Note: XPRESS and CPLEX do not interpret integer variables without
        # explicit bounds

        elif self.lowBound == 0 and self.cat == const.LpContinuous:
            s = ""
        else:
            s = f"{self.lowBound:.12g} <= "

        s += self.name

        if self.upBound is not None:
            s += f" <= {self.upBound:.12g}"

        return s

    def asCplexLpAffineExpression(self, name, constant=1):
        """

        :param name:
        :param constant:
        :return:
        """
        return LpAffineExpression(self).asCplexLpAffineExpression(name, constant)

    def __ne__(self, other):
        """

        :param other:
        :return:
        """
        if isinstance(other, LpElement):
            return self.name is not other.name
        elif isinstance(other, LpAffineExpression):
            if other.isAtomic():
                return self is not other.atom()
            else:
                return 1
        else:
            return 1

    def __bool__(self):
        return bool(self.roundedValue())

    def addVariableToConstraints(self, e):
        """adds a variable to the constraints indicated by
        the LpConstraintVars in e
        """
        for constraint, coeff in e.items():
            constraint.addVariable(self, coeff)

    def setInitialValue(self, val, check=True):
        """
        sets the initial value of the variable to `val`
        May be used for warmStart a solver, if supported by the solver

        :param float val: value to set to variable
        :param bool check: if True, we check if the value fits inside the variable bounds
        :return: True if the value was set
        :raises ValueError: if check=True and the value does not fit inside the bounds
        """
        lb = self.lowBound
        ub = self.upBound
        config = [
            ("smaller", "lowBound", lb, lambda: val < lb),
            ("greater", "upBound", ub, lambda: val > ub),
        ]

        for rel, bound_name, bound_value, condition in config:
            if bound_value is not None and condition():
                if not check:
                    return False
                raise ValueError(
                    "In variable {}, initial value {} is {} than {} {}".format(
                        self.name, val, rel, bound_name, bound_value
                    )
                )
        self.varValue = val
        return True

    def fixValue(self):
        """
        changes lower bound and upper bound to the initial value if exists.
        :return: None
        """
        val = self.varValue
        if val is not None:
            self.bounds(val, val)

    def isFixed(self):
        """

        :return: True if upBound and lowBound are the same
        :rtype: bool
        """
        return self.isConstant()

    def unfixValue(self):
        """
        un-fix value
        """
        self.bounds(self._lowbound_original, self._upbound_original)


class LpAffineExpression(OrderedDict):
    """
    A linear combination of :class:`LpVariables<LpVariable>`.
    Can be initialised with the following:

    #.   e = None: an empty Expression
    #.   e = dict: gives an expression with the values being the coefficients of the keys (order of terms is undetermined)
    #.   e = list or generator of 2-tuples: equivalent to dict.items()
    #.   e = LpElement: an expression of length 1 with the coefficient 1
    #.   e = other: the constant is initialised as e

    Examples:

       >>> f=LpAffineExpression(LpElement('x'))
       >>> f
       1*x + 0
       >>> x_name = ['x_0', 'x_1', 'x_2']
       >>> x = [LpVariable(x_name[i], lowBound = 0, upBound = 10) for i in range(3) ]
       >>> c = LpAffineExpression([ (x[0],1), (x[1],-3), (x[2],4)])
       >>> c
       1*x_0 + -3*x_1 + 4*x_2 + 0
    """

    def __init__(self, e=None, constant: float = 0.0, name: str | None = None):
        """

        :param e:
        :param constant:
        :param name:
        """
        # to remove illegal characters from the names
        illegal_chars = "-+[] ->/"
        self.expression = re.compile(f"[{re.escape(illegal_chars)}]")
        self.trans = str.maketrans("-+[] ", "_____")

        self.__name = name

        if e is None:
            e = {}
        if isinstance(e, LpAffineExpression):
            # Will not copy the name
            self.constant = e.constant
            super().__init__(list(e.items()))
        elif isinstance(e, dict):
            self.constant = constant
            super().__init__(list(e.items()))
        elif isinstance(e, Iterable):
            self.constant = constant
            super().__init__(e)
        elif isinstance(e, LpElement):
            self.constant = 0
            super().__init__([(e, 1)])
        else:
            self.constant = e
            super().__init__()

    @property
    def name(self):
        """

        :return:
        """
        return self.__name

    @name.setter
    def name(self, val):
        if val:
            if self.expression.match(val):
                warnings.warn(
                    "The name {} has illegal characters that will be replaced by _".format(
                        val
                    )
                )
            self.__name = str(val).translate(self.trans)
        else:
            self.__name = None

    def isAtomic(self) -> bool:
        """

        :return:
        """
        return len(self) == 1 and self.constant == 0 and list(self.values())[0] == 1

    def isNumericalConstant(self) -> bool:
        """

        :return:
        """
        return len(self) == 0

    def atom(self):
        """

        :return:
        """
        return list(self.keys())[0]

    # Functions on expressions

    def __bool__(self):
        return (float(self.constant) != 0.0) or (len(self) > 0)

    def value(self):
        """

        :return:
        """
        s = self.constant
        for v, x in self.items():
            if v.varValue is None:
                return None
            s += v.varValue * x
        return s

    def valueOrDefault(self):
        """

        :return:
        """
        s = self.constant
        for v, x in self.items():
            s += v.valueOrDefault() * x
        return s

    def addterm(self, key, value):
        """

        :param key:
        :param value:
        :return:
        """
        y = self.get(key, 0)
        if y:
            y += value
            self[key] = y
        else:
            self[key] = value

    def emptyCopy(self):
        """

        :return:
        """
        return LpAffineExpression()

    def copy(self):
        """Make a copy of self except the name which is reset"""
        # Will not copy the name
        return LpAffineExpression(self)

    def __str__(self, constant=1):
        s = ""
        for v in self.sorted_keys():
            val = self[v]
            if val < 0:
                if s != "":
                    s += " - "
                else:
                    s += "-"
                val = -val
            elif s != "":
                s += " + "
            if val == 1:
                s += str(v)
            else:
                s += str(val) + "*" + str(v)
        if constant:
            if s == "":
                s = str(self.constant)
            else:
                if self.constant < 0:
                    s += " - " + str(-self.constant)
                elif self.constant > 0:
                    s += " + " + str(self.constant)
        elif s == "":
            s = "0"
        return s

    def sorted_keys(self):
        """
        returns the list of keys sorted by name
        """
        result = [(v.name, v) for v in self.keys()]
        result.sort()
        result = [v for _, v in result]
        return result

    def __repr__(self):
        l = [str(self[v]) + "*" + str(v) for v in self.sorted_keys()]
        l.append(str(self.constant))
        s = " + ".join(l)
        return s

    @staticmethod
    def _count_characters(line):
        # counts the characters in a list of strings
        return sum(len(t) for t in line)

    def asCplexVariablesOnly(self, name):
        """
        helper for asCplexLpAffineExpression
        """
        result = []
        line = [f"{name}:"]
        notFirst = 0
        variables = self.sorted_keys()
        for v in variables:
            val = self[v]
            if val < 0:
                sign = " -"
                val = -val
            elif notFirst:
                sign = " +"
            else:
                sign = ""
            notFirst = 1
            if val == 1:
                term = f"{sign} {v.name}"
            else:
                # adding zero to val to remove instances of negative zero
                term = f"{sign} {val + 0:.12g} {v.name}"

            if self._count_characters(line) + len(term) > const.LpCplexLPLineSize:
                result += ["".join(line)]
                line = [term]
            else:
                line += [term]
        return result, line

    def asCplexLpAffineExpression(self, name, constant=1):
        """
        returns a string that represents the Affine Expression in lp format
        """
        # refactored to use a list for speed in iron python
        result, line = self.asCplexVariablesOnly(name)
        if not self:
            term = f" {self.constant}"
        else:
            term = ""
            if constant:
                if self.constant < 0:
                    term = " - %s" % (-self.constant)
                elif self.constant > 0:
                    term = f" + {self.constant}"
        if self._count_characters(line) + len(term) > const.LpCplexLPLineSize:
            result += ["".join(line)]
            line = [term]
        else:
            line += [term]
        result += ["".join(line)]
        result = "%s\n" % "\n".join(result)
        return result

    def addInPlace(self, other: "LpAffineExpression", sign=1):
        """
        :param other: Other expression
        :param int sign: the sign of the operation to do other.
            if we add other => 1
            if we subtract other => -1
        """
        if isinstance(other, int) and (other == 0):
            return self
        if other is None:
            return self
        if isinstance(other, LpElement):
            # if a variable, we add it to the dictionary
            self.addterm(other, sign)
        elif isinstance(other, LpAffineExpression):
            # if an expression, we add each variable and the constant
            self.constant += other.constant * sign
            for v, x in other.items():
                self.addterm(v, x * sign)
        elif isinstance(other, dict):
            # if a dictionary, we add each value
            for e in other.values():
                self.addInPlace(e, sign=sign)
        elif isinstance(other, list) or isinstance(other, Iterable):
            # if a list, we add each element of the list
            for e in other:
                self.addInPlace(e, sign=sign)
        # if we're here, other must be a number
        # we check if it's an actual number:
        elif not math.isfinite(other):
            raise const.PulpError("Cannot add/subtract NaN/inf values")
        # if it's indeed a number, we add it to the constant
        else:
            self.constant += other * sign
        return self

    def subInPlace(self, other: "LpAffineExpression"):
        """

        :param other:
        :return:
        """
        return self.addInPlace(other, sign=-1)

    def __neg__(self):
        """

        :return:
        """
        e = self.emptyCopy()
        e.constant = -self.constant
        for v, x in self.items():
            e[v] = -x
        return e

    def __pos__(self):
        return self

    def __add__(self, other: "LpAffineExpression"):
        return self.copy().addInPlace(other)

    def __radd__(self, other: "LpAffineExpression"):
        return self.copy().addInPlace(other)

    def __iadd__(self, other: "LpAffineExpression"):
        return self.addInPlace(other)

    def __sub__(self, other: "LpAffineExpression"):
        return self.copy().subInPlace(other)

    def __rsub__(self, other: "LpAffineExpression"):
        return (-self).addInPlace(other)

    def __isub__(self, other: "LpAffineExpression"):
        return self.subInPlace(other)

    def __mul__(self, other: "LpAffineExpression"):
        e = self.emptyCopy()
        if isinstance(other, LpAffineExpression):
            e.constant = self.constant * other.constant
            if len(other):
                if len(self):
                    raise TypeError("Non-constant expressions cannot be multiplied")
                else:
                    c = self.constant
                    if c != 0:
                        for v, x in other.items():
                            e[v] = c * x
            else:
                c = other.constant
                if c != 0:
                    for v, x in self.items():
                        e[v] = c * x
        elif isinstance(other, LpVariable):
            return self * LpAffineExpression(other)
        else:
            if not math.isfinite(other):
                raise const.PulpError("Cannot multiply variables with NaN/inf values")
            elif other != 0:
                e.constant = self.constant * other
                for v, x in self.items():
                    e[v] = other * x
        return e

    def __rmul__(self, other: "LpAffineExpression"):
        return self * other

    def __div__(self, other: "LpAffineExpression"):
        if isinstance(other, LpAffineExpression) or isinstance(other, LpVariable):
            if len(other):
                raise TypeError(
                    "Expressions cannot be divided by a non-constant expression"
                )
            other = other.constant
        if not math.isfinite(other):
            raise const.PulpError("Cannot divide variables with NaN/inf values")
        e = self.emptyCopy()
        e.constant = self.constant / other
        for v, x in self.items():
            e[v] = x / other
        return e

    def __truediv__(self, other: "LpAffineExpression"):
        return self.__div__(other)

    def __rdiv__(self, other: "LpAffineExpression"):
        e = self.emptyCopy()
        if len(self):
            raise TypeError(
                "Expressions cannot be divided by a non-constant expression"
            )
        c = self.constant
        if isinstance(other, LpAffineExpression):
            e.constant = other.constant / c
            for v, x in other.items():
                e[v] = x / c
        elif not math.isfinite(other):
            raise const.PulpError("Cannot divide variables with NaN/inf values")
        else:
            e.constant = other / c
        return e

    def __le__(self, other: "LpAffineExpression"):
        return LpConstraint(self - other, const.LpConstraintLE)

    def __ge__(self, other: "LpAffineExpression"):
        return LpConstraint(self - other, const.LpConstraintGE)

    def __eq__(self, other: "LpAffineExpression"):
        return LpConstraint(self - other, const.LpConstraintEQ)

    def toDict(self):
        """
        exports the :py:class:`LpAffineExpression` into a list of dictionaries with the coefficients
        it does not export the constant

        :return: list of dictionaries with the coefficients
        :rtype: list
        """
        return [dict(name=k.name, value=v) for k, v in self.items()]

    def to_dict(self):
        """
        exports the :py:class:`LpAffineExpression` into a list of dictionaries with the coefficients
        :return:
        """
        return self.toDict()


class LpConstraint(LpAffineExpression):
    """An LP constraint"""

    def __init__(self, e=None, sense=const.LpConstraintEQ, name=None, rhs=None):
        """
        :param e: an instance of :class:`LpAffineExpression`
        :param sense: one of :data:`~pulp.const.LpConstraintEQ`, :data:`~pulp.const.LpConstraintGE`, :data:`~pulp.const.LpConstraintLE` (0, 1, -1 respectively)
        :param name: identifying string
        :param rhs: numerical value of constraint target
        """
        LpAffineExpression.__init__(self, e, name=name)
        if rhs is not None:
            self.constant -= rhs
        self.sense = sense
        self.pi = None
        self.slack = None
        self.modified = True

    def getLb(self):
        if (self.sense == const.LpConstraintGE) or (self.sense == const.LpConstraintEQ):
            return -self.constant
        else:
            return None

    def getUb(self):
        if (self.sense == const.LpConstraintLE) or (self.sense == const.LpConstraintEQ):
            return -self.constant
        else:
            return None

    def __str__(self):
        s = LpAffineExpression.__str__(self, 0)
        if self.sense is not None:
            s += " " + const.LpConstraintSenses[self.sense] + " " + str(-self.constant)
        return s

    def asCplexLpConstraint(self, name):
        """
        Returns a constraint as a string
        """
        result, line = self.asCplexVariablesOnly(name)
        if not list(self.keys()):
            line += ["0"]
        c = -self.constant
        if c == 0:
            c = 0  # Supress sign
        term = f" {const.LpConstraintSenses[self.sense]} {c:.12g}"
        if self._count_characters(line) + len(term) > const.LpCplexLPLineSize:
            result += ["".join(line)]
            line = [term]
        else:
            line += [term]
        result += ["".join(line)]
        result = "%s\n" % "\n".join(result)
        return result

    def changeRHS(self, RHS):
        """
        alters the RHS of a constraint so that it can be modified in a resolve
        """
        self.constant = -RHS
        self.modified = True

    def __repr__(self):
        s = LpAffineExpression.__repr__(self)
        if self.sense is not None:
            s += " " + const.LpConstraintSenses[self.sense] + " 0"
        return s

    def copy(self):
        """Make a copy of self"""
        return LpConstraint(self, self.sense)

    def emptyCopy(self):
        return LpConstraint(sense=self.sense)

    def addInPlace(self, other, sign=1):
        """
        :param int sign: the sign of the operation to do other.
            if we add other => 1
            if we subtract other => -1
        """
        if isinstance(other, LpConstraint):
            if self.sense * other.sense >= 0:
                LpAffineExpression.addInPlace(self, other, 1)
                self.sense |= other.sense
            else:
                LpAffineExpression.addInPlace(self, other, -1)
                self.sense |= -other.sense
        elif isinstance(other, list):
            for e in other:
                self.addInPlace(e, sign)
        else:
            LpAffineExpression.addInPlace(self, other, sign)
            # raise TypeError, "Constraints and Expressions cannot be added"
        return self

    def subInPlace(self, other):
        return self.addInPlace(other, -1)

    def __neg__(self):
        c = LpAffineExpression.__neg__(self)
        c.sense = -c.sense
        return c

    def __add__(self, other):
        return self.copy().addInPlace(other)

    def __radd__(self, other):
        return self.copy().addInPlace(other)

    def __sub__(self, other):
        return self.copy().subInPlace(other)

    def __rsub__(self, other):
        return (-self).addInPlace(other)

    def __mul__(self, other):
        if isinstance(other, LpConstraint):
            c = LpAffineExpression.__mul__(self, other)
            if c.sense == 0:
                c.sense = other.sense
            elif other.sense != 0:
                c.sense *= other.sense
            return c
        else:
            return LpAffineExpression.__mul__(self, other)

    def __rmul__(self, other):
        return self * other

    def __div__(self, other):
        if isinstance(other, LpConstraint):
            c = LpAffineExpression.__div__(self, other)
            if c.sense == 0:
                c.sense = other.sense
            elif other.sense != 0:
                c.sense *= other.sense
            return c
        else:
            return LpAffineExpression.__mul__(self, other)

    def __rdiv__(self, other):
        if isinstance(other, LpConstraint):
            c = LpAffineExpression.__rdiv__(self, other)
            if c.sense == 0:
                c.sense = other.sense
            elif other.sense != 0:
                c.sense *= other.sense
            return c
        else:
            return LpAffineExpression.__mul__(self, other)

    def valid(self, eps=0):
        val = self.value()
        if self.sense == const.LpConstraintEQ:
            return abs(val) <= eps
        else:
            return val * self.sense >= -eps

    def makeElasticSubProblem(self, *args, **kwargs):
        """
        Builds an elastic subproblem by adding variables to a hard constraint

        uses FixedElasticSubProblem
        """
        return FixedElasticSubProblem(self, *args, **kwargs)

    def toDict(self):
        """
        exports constraint information into a dictionary

        :return: dictionary with all the constraint information
        """
        return dict(
            sense=self.sense,
            pi=self.pi,
            constant=self.constant,
            name=self.name,
            coefficients=LpAffineExpression.toDict(self),
        )


class LpFractionConstraint(LpConstraint):
    """
    Creates a constraint that enforces a fraction requirement a/b = c
    """

    def __init__(self,
                 numerator,
                 denominator=None,
                 sense=const.LpConstraintEQ,
                 RHS=1.0,
                 name=None,
                 complement=None):
        """
        creates a fraction Constraint to model constraints of
        the nature
        numerator/denominator {==, >=, <=} RHS
        numerator/(numerator + complement) {==, >=, <=} RHS

        :param numerator: the top of the fraction
        :param denominator: as described above
        :param sense: the sense of the relation of the constraint
        :param RHS: the target fraction value
        :param complement: as described above
        """
        self.numerator = numerator
        if denominator is None and complement is not None:
            self.complement = complement
            self.denominator = numerator + complement
        elif denominator is not None and complement is None:
            self.denominator = denominator
            self.complement = denominator - numerator
        else:
            self.denominator = denominator
            self.complement = complement
        lhs = self.numerator - RHS * self.denominator
        LpConstraint.__init__(self, lhs, sense=sense, rhs=0, name=name)
        self.RHS = RHS

    def findLHSValue(self):
        """
        Determines the value of the fraction in the constraint after solution
        """
        if abs(value(self.denominator)) >= const.EPS:
            return value(self.numerator) / value(self.denominator)
        else:
            if abs(value(self.numerator)) <= const.EPS:
                # zero divided by zero will return 1
                return 1.0
            else:
                raise ZeroDivisionError

    def makeElasticSubProblem(self, *args, **kwargs):
        """
        Builds an elastic subproblem by adding variables and splitting the
        hard constraint

        uses FractionElasticSubProblem
        """
        return FractionElasticSubProblem(self, *args, **kwargs)


class LpConstraintVar(LpElement):
    """
    A Constraint that can be treated as a variable when constructing
    a LpProblem by columns
    """

    def __init__(self, name=None, sense=None, rhs=None, e=None):
        LpElement.__init__(self, name)
        self.constraint = LpConstraint(name=self.name, sense=sense, rhs=rhs, e=e)

    def addVariable(self, var, coeff):
        """
        Adds a variable to the constraint with the
        activity coeff
        """
        self.constraint.addterm(var, coeff)

    def value(self):
        """

        :return:
        """
        return self.constraint.value()


def lp_constraint_from_dict(_dict) -> "LpConstraint":
    """
    Initializes a constraint object from a dictionary with necessary information

    :param dict _dict: dictionary with data
    :return: a new :py:class:`LpConstraint`
    """
    cst = LpConstraint(e=_dict["coefficients"],
                       sense=_dict["sense"],
                       rhs=-_dict["constant"],
                       name=_dict["name"])
    cst.pi = _dict["pi"]
    return cst
