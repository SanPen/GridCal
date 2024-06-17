
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

from typing import Dict, Any, Union
import numpy as np
from GridCalEngine.enumerations import DeviceType
from GridCalEngine.basic_structures import Numeric, NumericVec, IntVec


PROFILE_TYPES = Union[type(bool), type(int), type(float), DeviceType]


def check_type(dtype: PROFILE_TYPES, value: Any) -> bool:
    """
    Checks that the type of value is the declared type in the profile
    :param dtype: expected type
    :param value: Any value
    :return:
    """
    tpe = type(value)
    if tpe in [bool, np.bool_]:
        assert dtype == bool
    elif tpe in [int, np.int32, np.int64]:
        assert dtype == int or dtype == float
    elif tpe in [float, np.float32, np.float64]:
        assert dtype == float
    else:
        assert isinstance(dtype, DeviceType)

    return True


class SparseArray:
    """
    SparseArray
    """

    def __init__(self, data_type: PROFILE_TYPES) -> None:
        """

        """
        self._dtype = data_type
        self._default_value: Numeric = 0
        self._size: int = 0
        self._map: Dict[int, Numeric] = dict()

    @property
    def dtype(self) -> Union[bool, int, float, DeviceType]:
        """
        Get the declared type
        :return: type
        """
        return self._dtype

    @property
    def default_value(self):
        """
        Default value getter
        :return: numeric value
        """
        return self._default_value

    @default_value.setter
    def default_value(self, val):
        """

        :param val:
        :return:
        """
        if isinstance(self.dtype, DeviceType):
            if val == "None":
                val2 = None
            else:
                val2 = val
        else:
            val2 = val
        check_type(dtype=self.dtype, value=val2)
        self._default_value = val2

    def info(self):
        """
        Return dictionary with information about the profile object and its content
        :return:
        """
        return {
            "me": hex(id(self)),
            "default_value": self._default_value,
            "size": self._size,
            "map": hex(id(self._map)),
        }

    def get_map(self) -> Dict[int, Numeric]:
        """
        Return the dictionary hosting the sparse data
        :return: Dict[int, Numeric]
        """
        return self._map

    def insert(self, i: int, x: Numeric):
        """
        Insert an element in the data dictionary
        :param i:
        :param x:
        :return:
        """
        self._map[i] = x

    def get_sparsity(self) -> float:
        """
        Get the sparsity of this profile
        :return: Sparsity metric
        """
        return float(len(self._map)) / float(self._size)

    def create(self, size: int, default_value: Numeric, data: Union[Dict[int, Numeric], None] = None):
        """
        Build sparse from definition
        :param size: size
        :param default_value: default value
        :param data: data map
        """
        self.default_value = default_value
        self._size = size
        self._map = data if data is not None else dict()

    def create_from_array(self, array: NumericVec, default_value: Numeric):
        """
        Build sparse from array
        :param array: NumericVec
        :param default_value: defult value of the array
        """
        self.default_value = default_value
        self._size = len(array)
        self._map: Dict[int, Numeric] = dict()

        for i, val in enumerate(array):
            if val != default_value:
                self._map[i] = val

    def create_from_dict(self, default_value: Numeric, size: int, map_data: Dict[int, Numeric]):
        """
        Create this array from dict data
        :param default_value:
        :param size:
        :param map_data:
        :return:
        """
        self.default_value = default_value
        self._size = size
        self._map = map_data

    def fill(self, value: Any):
        """
        Fill the sparse array with the same value
        :param value: any value
        """
        self.default_value = value
        self._map = dict()

    def toarray(self) -> NumericVec:
        """
        Get numpy vector from this sparse structure
        :return: NumericVec
        """
        arr = np.full(self._size, self._default_value)

        for key, val in self._map.items():
            arr[key] = val

        return arr

    def at(self, idx: int) -> Any:
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

    def __getitem__(self, key: int) -> Any:
        return self.at(idx=key)

    def __setitem__(self, key: int, value: Any) -> None:

        if isinstance(key, int):

            assert key < self._size

            if value != self._default_value:
                self._map[key] = value

        else:
            raise TypeError("Key must be an integer")

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

    def get_sparse_representation(self):
        """
        Get the sparse representation of the sparse data
        :return:
        """
        indptr = list()
        data = list()
        for i, x in self._map:
            indptr.append(i)
            data.append(x)

        return indptr, data

    def set_sparse_data_from_data(self, indptr, data):
        """

        :param indptr:
        :param data:
        :return:
        """
        for i, x in zip(indptr, data):
            self._map[i] = x

