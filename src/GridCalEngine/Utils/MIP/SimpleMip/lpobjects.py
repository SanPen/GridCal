# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
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
from typing import Union, Dict, Tuple
from uuid import uuid4


class LpVar:
    """
    Variable
    """
    def __init__(self,
                 name: str,
                 lower_bound: float = 0.0,
                 upper_bound: float = 1e20,
                 is_integer: bool = False,
                 internal_idx: int = 0,
                 hash_id: Union[int, None] = None):
        """

        :param name: Variable name
        :param lower_bound: Lower bound (optional)
        :param upper_bound: Upper bound (optional)
        :param is_integer: is this an integer variable?  (optional)
        :param internal_idx: Internal solver index (not required)
        :param hash_id: internal unique Hash id so that this var can be used in a dictionary as key  (not required)
        """
        self.name = name
        self.lower_bound: float = lower_bound
        self.upper_bound: float = upper_bound
        self.is_integer: bool = is_integer  # Indicates if the variable is an integer
        self._index: int = internal_idx  # internal index to the solver
        self._hash_id: int = uuid4().int if hash_id is None else hash_id

    def set_index(self, index: int) -> None:
        """
        Set the internal indexing
        :param index: var index in the solver
        """
        self._index = index

    def get_index(self) -> int:
        """
        Get the internal indexing
        :return: int
        """
        return self._index

    def copy(self) -> "LpVar":
        """
        Make a deep copy of this variable
        :return:
        """
        return LpVar(name=self.name,
                     lower_bound=self.lower_bound,
                     upper_bound=self.upper_bound,
                     is_integer=self.is_integer,
                     internal_idx=self._index,
                     hash_id=self._hash_id)

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return self.name

    def __hash__(self) -> int:
        # Makes Variable instances hashable so they can be used as dictionary keys
        return self._hash_id

    def _comparison(self, sense: str, other: Union["LpExp", LpVar, float, int]) -> LpCst:

        if isinstance(other, (int, float)):
            combined_expression = LpExp(self)
            combined_expression.offset -= other
            return LpCst(combined_expression, sense, 0)

        elif isinstance(other, LpVar):
            combined_expression = LpExp(self) - LpExp(other)
            return LpCst(combined_expression, sense, 0)

        elif isinstance(other, LpExp):
            combined_expression = LpExp(self) - other
            return LpCst(linear_expression=combined_expression,
                         sense=sense,
                         coefficient=-combined_expression.offset)
        else:
            raise ValueError(f"Right-hand side of {sense} must be an int or float")

    def __le__(self, other: Union["LpExp", LpVar, float, int]) -> LpCst:
        return self._comparison(sense="<=", other=other)

    def __ge__(self, other: Union["LpExp", LpVar, float, int]) -> LpCst:
        return self._comparison(sense=">=", other=other)

    def __eq__(self, other: Union["LpExp", LpVar, float, int]) -> Union[LpCst, bool]:

        if isinstance(other, LpVar):
            return self._hash_id == other._hash_id
        else:
            return self._comparison(sense="==", other=other)

    def __add__(self, other):
        return LpExp(self) + other

    def __radd__(self, other):
        return LpExp(self) + other

    def __mul__(self, other: Union[int, float]) -> Union["LpExp", float]:
        """
        Multiply this variable with a int or float
        :param other:
        :return:
        """
        if isinstance(other, (int, float)):
            return LpExp(self, other) if other != 0 else 0.0

        raise ValueError("Can only multiply a Variable by a scalar")

    def __rmul__(self, other):
        return self.__mul__(other)

    def __sub__(self, other: Union[int, float, "LpVar", "LpExp"]) -> "LpExp":
        """

        :param other:
        :return:
        """
        if isinstance(other, LpVar):
            return LpExp(self) - LpExp(other)
        elif isinstance(other, LpExp):
            return LpExp(self) - other
        elif isinstance(other, (int, float)):
            e = LpExp(self)
            e.offset -= other
            return e
        else:
            raise ValueError("Unsupported operand type(s) for -: 'Variable' and '{}'".format(type(other)))

    def __rsub__(self, other: Union[int, float]):
        """

        :param other:
        :return:
        """
        if isinstance(other, (int, float)):
            return LpExp(None, other) - LpExp(self)
        else:
            raise ValueError("Unsupported operand type(s) for -: '{}' and 'Variable'".format(type(other)))


class LpCst:
    """
    Constraint
    """
    def __init__(self, linear_expression: LpExp, sense: str, coefficient: float,
                 name="", internal_index: int = 0):
        """
        constraint (<=, ==, >=) rhs

        :param linear_expression:
        :param sense: <=, ==, >=
        :param coefficient:
        :param name:
        :param internal_index:
        """
        assert sense in ["<=", "==", ">="]

        self.name = name
        self.linear_expression = linear_expression
        self.sense = sense
        self.coefficient = coefficient  # Right-hand side value
        self._index: int = internal_index  # internal index to the solver

    @property
    def terms(self):
        """
        Terms property of the linear expression
        :return:
        """
        return self.linear_expression.terms

    def copy(self) -> "LpCst":
        """
        Make a deep copy of this constraint
        :return: Constraint
        """
        return LpCst(linear_expression=self.linear_expression.copy(),
                     sense=self.sense,
                     coefficient=self.coefficient,
                     name=self.name,
                     internal_index=self._index)

    def get_bounds(self) -> Tuple[float, float]:
        """
        Get the constraint bounds
        :return: lhs <= constraint <= rhs
        """
        MIP_INF = 1e20
        if self.sense == '==':
            return self.coefficient, self.coefficient
        elif self.sense == '<=':
            return -MIP_INF, self.coefficient
        elif self.sense == '>=':
            return self.coefficient, MIP_INF
        else:
            raise Exception(f"Invalid sense: {self.sense}")

    def set_index(self, index: int) -> None:
        """
        Set the internal indexing
        :param index: constraint index in the solver
        """
        self._index = index

    def get_index(self) -> int:
        """
        Get internal index
        :return: int
        """
        return self._index

    def add_term(self, var: LpVar, coeff: float):
        """
        Add a term to the constraint
        :param var: Variable
        :param coeff: coefficient
        """
        self.linear_expression += coeff * var

    def add_var(self, var: LpVar):
        """
        Add a term to the constraint
        :param var: Variable
        """
        self.linear_expression += var


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

        e.terms = self.terms.copy()
        e.offset = self.offset

        return e

    def _comparison(self, sense: str, other: Union["LpExp", LpVar, float, int]) -> LpCst:

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

    def __le__(self, other: Union["LpExp", LpVar, float, int]) -> LpCst:
        return self._comparison(sense="<=", other=other)

    def __ge__(self, other: Union["LpExp", LpVar, float, int]) -> LpCst:
        return self._comparison(sense=">=", other=other)

    def __eq__(self, other: Union["LpExp", LpVar, float, int]) -> LpCst:
        return self._comparison(sense="==", other=other)

    def __add__(self, other: Union[LpVar, "LpExp", int, float]) -> "LpExp":
        new_expr = self.copy()

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

    def __radd__(self, other: Union[LpVar, "LpExp", int, float]) -> "LpExp":
        return self.__add__(other)

    def __iadd__(self, other: Union[LpVar, "LpExp", int, float]) -> "LpExp":
        return self.__add__(other)

    def __mul__(self, other: Union[float, int]) -> "LpExp":

        if isinstance(other, (int, float)):
            new_expr = LpExp()
            if other != 0:
                new_expr.offset = self.offset * other
                for var, coeff in self.terms.items():
                    new_expr.terms[var] = coeff * other
            else:
                # if we multiply by zero, the expression should remain empty
                pass

            return new_expr

        else:
            raise ValueError("Can only multiply by a scalar")

    def __rmul__(self, other: Union[float, int]) -> "LpExp":
        return self.__mul__(other)

    def __sub__(self, other: Union[LpVar, "LpExp", int, float]) -> "LpExp":
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

    def __rsub__(self, other: Union[LpVar, "LpExp", int, float]) -> "LpExp":
        return (-1 * self).__add__(other)

    def __isub__(self, other: Union[LpVar, "LpExp", int, float]) -> "LpExp":
        return self.__sub__(other)

    def __neg__(self) -> "LpExp":
        """
        Negate
        :return: LpExp with negative terms
        """
        e = LpExp()
        e.offset = self.offset
        for var, coeff in self.terms.items():
            e.terms[var] = -coeff
        return e
