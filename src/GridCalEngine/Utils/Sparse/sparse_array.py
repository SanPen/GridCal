# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Dict, Any, Union
import numpy as np
from enum import Enum
from GridCalEngine.enumerations import DeviceType
from GridCalEngine.basic_structures import Numeric, NumericVec, IntVec, Vec

PROFILE_TYPES = Union[type(bool), type(int), type(float), DeviceType, type(Vec)]


def check_type(dtype: PROFILE_TYPES, value: Any) -> bool:
    """
    Checks that the type of value is the declared type in the profile
    :param dtype: expected type
    :param value: Any value
    :return:
    """
    tpe = type(value)
    if tpe in [bool, np.bool_]:
        return dtype == bool
    elif tpe in [int, np.int32, np.int64]:
        return dtype == int or dtype == float
    elif tpe in [float, np.float32, np.float64]:
        return dtype == float
    elif issubclass(tpe, Enum):
        return tpe == dtype  # check that the enum type is the same

    elif isinstance(dtype, DeviceType):
        return True

    elif dtype == Vec:
        return isinstance(value, np.ndarray) or value is None

    else:
        raise Exception("Sparse array type value Not recognized")


class SparseArray:
    """
    SparseArray
    """

    __slots__ = (
        '_dtype',
        '_default_value',
        '_size',
        '_map',
    )

    def __init__(self, data_type: PROFILE_TYPES, default_value: Any, size: int = 0) -> None:
        """

        :param data_type:
        :param default_value:
        :param size:
        """
        self._dtype = data_type
        self._default_value: Any | None = self._dtype(default_value) if default_value is not None else None
        self._size: int = size
        self._map: Dict[int, Any] = dict()

    def copy(self) -> "SparseArray":
        """
        Get a deep copy of this object
        :return: A new SparseArray copy of this object
        """
        cpy = SparseArray(data_type=self._dtype, default_value=self._default_value, size=self._size)
        cpy._map = self._map.copy()
        return cpy

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
        elif issubclass(self._dtype, Enum):
            # if it is an Enum type, cast the value to the Enum
            val2 = self._dtype(val)
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

    def create(self, size: int, default_value: PROFILE_TYPES,
               data: Union[Dict[int, Numeric], None] = None) -> "SparseArray":
        """
        Build sparse from definition
        :param size: size
        :param default_value: default value
        :param data: data map
        """
        self.default_value = self._dtype(default_value) if default_value is not None else None
        self._size = size
        self._map = data if data is not None else dict()
        return self

    def create_from_array(self, array: NumericVec,
                          default_value: PROFILE_TYPES) -> "SparseArray":
        """
        Build sparse from array
        :param array: NumericVec
        :param default_value: default value of the array
        """
        self.default_value = self._dtype(default_value) if default_value is not None else None
        self._size = len(array)
        self._map: Dict[int, Numeric] = dict()

        for i, val in enumerate(array):
            if val != default_value:
                self._map[i] = val

        return self

    def create_from_dict(self, default_value: PROFILE_TYPES, size: int,
                         map_data: Dict[int, Numeric]) -> "SparseArray":
        """
        Create this array from dict data
        :param default_value:
        :param size:
        :param map_data:
        :return:
        """
        self.default_value = self._dtype(default_value) if default_value is not None else None
        self._size = size
        self._map = map_data
        return self

    def fill(self, value: Any):
        """
        Fill the sparse array with the same value
        :param value: any value
        """
        self.default_value = self._dtype(value) if value is not None else None
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

    def clear(self):
        """
        Clear the sparse array
        :return:
        """
        self._map.clear()
        self._size = 0

    def set_data(self, d: Dict[int, Any]):

        self._map = d

    def resize(self, n: int):
        """
        Resize the array
        :param n:number of elements.
                 If n is smaller than the current container size, the content is
                 reduced to its first n elements, removing those beyond (and destroying them)
        """
        if n < self._size:  # we need to delete the elements out of range

            for key, val in self._map.items():

                if key >= n:
                    # delete elements whose index is now out of bounds from
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

    def slice(self, indices: IntVec) -> "SparseArray":
        """
        Get a resampled copy of this sparse array
        :param indices: array of integer indices (not repeated)
        """
        cpy = self.copy()
        cpy.resample(indices)
        return cpy

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


class SparseObjectArray:
    """
    SparseArray
    """

    def __init__(self, n: int) -> None:
        """

        :param n: Number of elements
        """
        self._size: int = n
        self._map: Dict[int, object] = dict()

    def copy(self) -> "SparseObjectArray":
        """
        Get a deep copy of this object
        :return: A new SparseObjectArray copy of this object
        """
        cpy = SparseObjectArray(n=self._size)
        cpy._size = self._size
        cpy._map = self._map.copy()
        return cpy

    def info(self):
        """
        Return dictionary with information about the profile object and its content
        :return:
        """
        return {
            "me": hex(id(self)),
            "size": self._size,
            "map": hex(id(self._map)),
        }

    def get_map(self) -> Dict[int, object]:
        """
        Return the dictionary hosting the sparse data
        :return: Dict[int, Numeric]
        """
        return self._map

    def insert(self, i: int, x: object):
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

    def at(self, idx: int) -> Any:
        """
        Get the array at a position
        :param idx: index
        :return: Numeric value
        """
        if len(self._map) == 0:
            return None
        else:
            return self._map.get(idx, None)

    def __getitem__(self, key: int) -> Any:
        return self.at(idx=key)

    def __setitem__(self, key: int, value: Any) -> None:

        if isinstance(key, int):

            assert key < self._size

            if value is not None:
                self._map[key] = value

        else:
            raise TypeError("Key must be an integer")

    def __eq__(self, other: "SparseObjectArray") -> bool:
        """
        Equality operator
        :param other: SparseArray
        :return: bool
        """

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
        if n < self._size:  # we need to delete the elements out of range

            for key, val in self._map.items():

                if key >= n:
                    # delete elements whose index is now out of bounds from
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

    def slice(self, indices: IntVec) -> "SparseObjectArray":
        """
        Get a resampled copy of this sparse array
        :param indices: array of integer indices (not repeated)
        """
        cpy = self.copy()
        cpy.resample(indices)
        return cpy
