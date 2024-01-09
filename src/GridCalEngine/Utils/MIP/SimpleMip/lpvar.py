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
from typing import Union, TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from GridCalEngine.Utils.MIP.SimpleMip.lpexp import LpExp


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
        self.lower_bound = lower_bound
        self.upper_bound = upper_bound
        self.is_integer = is_integer  # Indicates if the variable is an integer
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

    def __hash__(self):
        # Makes Variable instances hashable so they can be used as dictionary keys
        return self._hash_id

    def __eq__(self, other):
        # Ensure that variables with the same name are considered equal
        return isinstance(other, LpVar) and self.name == other.name

    def __add__(self, other):
        return LpExp(self) + other

    def __radd__(self, other):
        return LpExp(self) + other

    def __mul__(self, other: Union[int, float]) -> "LpExp":
        """
        Multiply this variable with a int or float
        :param other:
        :return:
        """
        if isinstance(other, (int, float)):
            return LpExp(self, other)
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
            return LpExp(self) - LpExp(None, other)
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