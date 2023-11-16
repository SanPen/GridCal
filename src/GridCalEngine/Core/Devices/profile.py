
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
import numba as nb
from GridCalEngine.basic_structures import Numeric, NumericVec, IntVec
from GridCalEngine.Core.Devices.sparse_array import SparseArray


@nb.njit()
def compress_array_numba(value, base):
    """

    :param value:
    :param base:
    :return:
    """
    data = list()
    indptr = list()
    for i, x in enumerate(value):
        if x != base:
            data.append(x)
            indptr.append(i)
    return data, indptr


@nb.njit()
def compress_array_numba_map(value, base) -> Dict[int, Numeric]:
    """

    :param value:
    :param base:
    :return:
    """
    data = dict()
    for i, x in enumerate(value):
        if x != base:
            data[i] = x
    return data


class Profile:
    """
    Profile
    """

    def __init__(self):

        self._is_sparse: bool = False

        self._sparse_array: Union[SparseArray, None] = None

        self._dense_array: Union[NumericVec, None] = None

        self._sparsity: float = 0.8

    def create_sparse(self, size: int, default_value: Numeric):
        """
        Build sparse from definition
        :param size: size
        :param default_value: default value
        """
        self._is_sparse = True
        self._sparse_array = SparseArray()
        self._sparse_array.create(size=size, default_value=default_value)

    def create_dense(self, size: int, default_value: Numeric):
        """
        Create a dense profile
        :param size: size
        :param default_value: default value
        """
        self._is_sparse = False
        self._dense_array = np.full(size, default_value)
        self._sparse_array = None

    def set(self, arr: NumericVec):
        """
        Set array value
        :param arr:
        :return:
        """
        if len(arr) > 0:
            u, counts = np.unique(arr, return_counts=True)
            f = len(u) / len(arr)  # sparsity factor
            if f < self._sparsity:
                ind = np.argmax(counts)
                base = u[ind]  # this is the most frequent value
                if isinstance(base, np.bool_):
                    base = bool(base)

                self._is_sparse = True
                self._sparse_array = SparseArray()

                if len(u) > 1:
                    if isinstance(arr, np.ndarray):
                        data_map = compress_array_numba_map(arr, base)
                    else:
                        raise Exception('Unknown profile type' + str(type(arr)))
                else:
                    data_map = dict()

                self._sparse_array.create(size=len(arr),
                                          default_value=base,
                                          data=data_map)
            else:
                self._is_sparse = False
                self._dense_array = arr
        else:
            self._is_sparse = False
            self._dense_array = arr

    def __getitem__(self, key):
        """
        Get item
        :param key: index position
        :return: value at "key"
        """
        if isinstance(key, int):

            if self._is_sparse:
                return self._sparse_array[key]
            else:
                return self._dense_array[key]
        else:
            raise TypeError("Key must be an integer")

    def __setitem__(self, key, value):
        """
        Set item
        :param key: item index
        :param value: value to set
        """
        if isinstance(key, int):

            if self._is_sparse:
                assert key < self._sparse_array.size()
                self._sparse_array[key] = value
            else:
                assert key < len(self._dense_array)
                self._dense_array[key] = value

        else:
            raise TypeError("Key must be an integer")

    def size(self) -> int:
        """
        Get the size
        :return: integer
        """
        return self._sparse_array.size() if self._is_sparse else len(self._dense_array)
