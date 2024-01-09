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
from typing import Tuple, TYPE_CHECKING

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from GridCalEngine.Utils.MIP.SimpleMip.lpexp import LpExp
    from GridCalEngine.Utils.MIP.SimpleMip.lpvar import LpVar


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