
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

from typing import Union, Dict
import numpy as np
from GridCalEngine.basic_structures import Numeric, NumericVec, IntVec


class SparseArray:
    """
    SparseArray
    """

    def __init__(self):
        """

        """
        self._default_value: Numeric = 0
        self._size: int = 0
        self._map: Dict[int, Numeric] = dict()

    def create(self, size: int, default_value: Numeric, data: Dict[int, Numeric] = dict()):
        """
        Build sparse from definition
        :param size: size
        :param default_value: default value
        :param data: data map
        """
        self._default_value = default_value
        self._size = size
        self._map = data

    def create_from_array(self, array: NumericVec, default_value: Numeric):
        """
        Build sparse from array
        :param array: NumericVec
        :param default_value: defult value of the array
        """
        self._default_value = default_value
        self._size = len(array)
        self._map: Dict[int, Numeric] = dict()

        for i, val in enumerate(array):
            if val != default_value:
                self._map[i] = val

    def get_vactor(self) -> NumericVec:
        """
        Get numpy vector from this sparse structure
        :return: NumericVec
        """
        arr = np.full(self._size, self._default_value)

        for key, val in self._map.items():
            arr[key] = val

        return arr

    def at(self, idx: int) -> Numeric:
        """
        Get the array at a position
        :param idx: index
        :return: Numeric value
        """
        if len(self._map) == 0:
            return self._default_value

        else:

            val = self._map.get(idx, None)

            if val is None:
                return self._default_value
            else:
                return val

    def __getitem__(self, key):
        if isinstance(key, int):
            return self.at(key)
        else:
            raise TypeError("Key must be an integer")

    def __setitem__(self, key, value):

        if isinstance(key, int):

            assert key < self._size

            if value != self._default_value:
                self._map[key] = value

        else:
            raise TypeError("Key must be an integer")

    def size(self) -> int:
        """
        Get the size
        :return: integer
        """
        return self._size

    def resize(self, n: int):
        """
        Resize the array
        :param n:number of elements.
                 If n is smaller than the current container size, the content is
                 reduced to its first n elements, removing those beyond (and destroying them)
        """
        if n < self._size:  # we need to remove the elements out of range

            for key, val in self._map.items():

                if key >= n:
                    # remove elements whose index is now out of bounds from
                    # the index -> value map.
                    del self._map[key]

        self._size = n

    def resample(self, indices: IntVec):
        """
        Resample this sparse array in-place
        :param indices: array of integer indices (not repeated)
        """
        self._size = len(indices)

        """
        We need to re-index the sparse entries
                                0  1  2  3  4  5  6  7  8
        original dense vector [0, 0, 2, 0, 7, 0, 0, 0, 3]
        
        map: {{2: 2}, {4: 7}, {8: 3}}
        
        Now we resample with indices [2, 5, 8]
        
                                  old idx   2  5  8  -> indices
                                  new idx   0  1  2  -> indices' positions
        the supposedly modified vector is: [2, 0, 3]
        
        the new map is: {{0: 2:}, {2: 3}}
        """

        new_map: Dict[int, Numeric] = dict()

        for i, idx in enumerate(indices):

            it = self._map.get(idx, None)

            if it is not None:
                # found, keep the value at the new index
                new_map[i] = it

        self._map = new_map

    def __eq__(self, other: "SparseArray") -> bool:
        """
        Equality operator
        :param other: SparseArray
        :return: bool
        """
        if self._default_value != other._default_value:
            return False

        if self._size != other._size:
            return False

        if self._map != other._map:
            return False

        return True
