# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
from __future__ import annotations
from typing import Dict, TYPE_CHECKING

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from GridCalEngine.Utils.MIP.SimpleMip.lpvar import LpVar
    from GridCalEngine.Utils.MIP.SimpleMip.lpcst import LpCst


class LpExp:
    """
    Expression
    """
    def __init__(self, variable: LpVar = None, coefficient: float = 1.0, offset: float = 0.0):
        """

        :param variable:
        :param coefficient:
        """
        self.terms: Dict[LpVar, float] = {}

        self.offset = offset

        if variable is not None:
            self.terms[variable] = coefficient

    def copy(self) -> "LpExp":
        """
        Make a deep copy of this expression
        :return: Expression
        """
        e = LpExp()

        for var, coefficient in self.terms.items():
            e.terms[var.copy()] = coefficient

        e.offset = self.offset

        return e

    def __le__(self, other):
        sense = "<="

        if isinstance(other, (int, float)):
            return LpCst(linear_expression=self,
                         sense=sense,
                         coefficient=other - self.offset)

        elif isinstance(other, LpVar):
            other = LpExp(variable=other)
            combined_expression = self - other
            return LpCst(combined_expression, sense, 0)

        elif isinstance(other, LpExp):
            combined_expression = self - other
            return LpCst(linear_expression=combined_expression,
                         sense=sense,
                         coefficient=-combined_expression.offset)

        raise ValueError(f"Right-hand side of {sense} must be an int or float")

    def __ge__(self, other):

        sense = ">="

        if isinstance(other, (int, float)):
            return LpCst(linear_expression=self,
                         sense=sense,
                         coefficient=other - self.offset)

        elif isinstance(other, LpVar):
            other = LpExp(variable=other)
            combined_expression = self - other
            return LpCst(combined_expression, sense, 0)

        elif isinstance(other, LpExp):
            combined_expression = self - other
            return LpCst(linear_expression=combined_expression,
                         sense=sense,
                         coefficient=-combined_expression.offset)

        raise ValueError(f"Right-hand side of {sense} must be an int or float")

    def __eq__(self, other):
        sense = "=="

        if isinstance(other, (int, float)):
            return LpCst(linear_expression=self,
                         sense=sense,
                         coefficient=other - self.offset)

        elif isinstance(other, LpVar):
            other = LpExp(variable=other)
            combined_expression = self - other
            return LpCst(combined_expression, sense, 0)

        elif isinstance(other, LpExp):
            combined_expression = self - other
            return LpCst(linear_expression=combined_expression,
                         sense=sense,
                         coefficient=-combined_expression.offset)

        raise ValueError(f"Right-hand side of {sense} must be an int or float")

    def __add__(self, other):
        new_expr = LpExp()
        new_expr.terms = self.terms.copy()

        if isinstance(other, LpVar):
            other = LpExp(other)

        if isinstance(other, LpExp):

            new_expr.offset += other.offset
            for var, coeff in other.terms.items():
                if var in new_expr.terms:
                    new_expr.terms[var] += coeff
                else:
                    new_expr.terms[var] = coeff

        elif isinstance(other, (int, float)):  # Handling constants in expressions
            new_expr.offset += other

        else:
            raise ValueError("Operands must be of type Variable, Expression, int, or float")

        return new_expr

    def __radd__(self, other):
        return self.__add__(other)

    def __mul__(self, other):

        if isinstance(other, (int, float)):
            new_expr = LpExp()
            new_expr.offset *= other
            for var, coeff in self.terms.items():
                new_expr.terms[var] = coeff * other
            return new_expr

        else:
            raise ValueError("Can only multiply by a scalar")

    def __rmul__(self, other):
        return self.__mul__(other)

    def __sub__(self, other):
        if isinstance(other, LpVar):
            other = LpExp(variable=other)

        if isinstance(other, LpExp):
            new_expr = self.copy()
            new_expr.offset -= other.offset
            for var, coeff in other.terms.items():
                if var in new_expr.terms:
                    new_expr.terms[var] -= coeff
                else:
                    new_expr.terms[var] = -coeff
            return new_expr

        elif isinstance(other, (int, float)):
            new_expr = self.copy()
            new_expr.offset -= other
            return new_expr

        else:
            raise ValueError("Unsupported operand type(s) for -: 'Expression' and '{}'".format(type(other)))

    def __rsub__(self, other):
        return (-1 * self).__add__(other)
