# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from typing import Union, Dict, Tuple, List, Any
from collections import Counter
import numpy as np
import numba as nb

from GridCalEngine.basic_structures import Numeric, NumericVec, IntVec
from GridCalEngine.enumerations import DeviceType
from GridCalEngine.Utils.Sparse.sparse_array import SparseArray, PROFILE_TYPES, check_type


@nb.njit()
def compress_array_numba(arr, base):
    """
    Compress Array
    :param arr: array to compress
    :param base: base value to have the compressed array
    :return: list of values different from base, list of indices of those values
    """
    data = list()  # keep them as lists since I may want to compress arrays of objects
    indptr = list()
    for i, x in enumerate(arr):
        if x != base:
            data.append(x)
            indptr.append(i)
    return data, indptr


def check_if_sparse(arr: Union[NumericVec], sparsity: float = 0.8) -> Tuple[bool, Union[float, int]]:
    """
    Check if the array is sparse
    :param arr: vector
    :param sparsity: proportion of non-repeated elements
    :return: is sparse, most frequent value
    """
    # truncate the sparsity value
    if sparsity > 0.99:
        sparsity = 0.9

    # compute the minimum number of values to evaluate
    min_elements = int(float(len(arr)) * (1.0 - sparsity))
    if min_elements < 1:
        min_elements = 1

    # if less than min_elements elements, it cannot be sparse
    if len(arr) < min_elements:
        return False, 0

    # declare the map to keep the frequency counter
    cnt: Dict[Numeric, int] = dict()

    for i, val in enumerate(arr):

        # add entry / increase entry (in the C++ map this works)
        dval = cnt.get(val, 0)
        cnt[val] = dval + 1

        # do not check all the vector if the histogram size is telling us that it is not sparse
        if len(cnt) > min_elements:
            return False, 0.0

    if len(cnt) > min_elements:
        # is not sparse
        return False, 0.0
    else:
        # variables to compare and keep the most frequent
        max_val = 0  # value with the most frequency
        max_freq: int = 0  # frequency of max_val

        # determine the most frequent
        for value, count in cnt.items():
            if count > max_freq:
                max_val = value
                max_freq = count

        # it is sparse
        return True, max_val


class Profile:
    """
    Profile
    """

    __slots__ = (
        '_is_sparse',
        '_sparse_array',
        '_dense_array',
        '_sparsity_threshold',
        '_dtype',
        '_initialized',
    )

    def __init__(self,
                 default_value,
                 data_type: PROFILE_TYPES,
                 arr: Union[None, NumericVec] = None,
                 sparsity_threshold: float = 0.8,
                 is_sparse: bool = False):
        """
        Profile constructor
        :param default_value: Default value
        :param arr: Array to be set, if provided the array is analyzed and the default value is deduced from the array
        :param sparsity_threshold: Threshold to consider an array sparse (0.8 -> 80% sparse is the default)
        :param is_sparse: Is sparse? provide the value, if the array is provided, this is deduced from the array
        """

        self._is_sparse: bool = is_sparse

        self._sparse_array: Union[SparseArray, None] = None

        self._dense_array: Union[NumericVec, None] = None

        self._sparsity_threshold: float = sparsity_threshold

        self._dtype = data_type

        self._initialized: bool = False

        if arr is not None:
            self.set(arr=arr)

    def clear(self):
        """
        Clear the profile
        :return:
        """
        self._sparse_array: Union[SparseArray, None] = None
        self._dense_array: Union[NumericVec, None] = None
        self._initialized: bool = False

    def info(self):
        """
        Return dictionary with information about the profile object and its content
        :return:
        """
        return {
            "me": hex(id(self)),
            "initialized": self._initialized,
            "size": self.size(),
            "is_sparse": self._is_sparse,
            "sparsity_threshold": self._sparsity_threshold,
            "dense_array": {"me": hex(id(self._dense_array)),
                            "size": len(self._dense_array)} if self._dense_array is not None else "None",
            "sparse_array": self._sparse_array.info() if self._sparse_array is not None else "None",
        }

    def get_sparse_map(self) -> Dict[int, Numeric]:
        """
        Return the dictionary hosting the sparse data if this profile is sparse
        :return: Dict[int, Numeric]
        """
        if self._sparse_array is not None:
            return self._sparse_array.get_map()
        else:
            print("no sparse array!")
            return dict()

    @property
    def dtype(self) -> Union[bool, int, float, DeviceType]:
        """
        Get the declared data type
        :return: data type
        """
        return self._dtype

    @property
    def default_value(self) -> Union[bool, int, float, DeviceType]:
        """
        Get the declared type
        :return: default_value
        """
        if self.sparse_array is not None:
            return self.sparse_array.default_value
        else:
            return 0

    @default_value.setter
    def default_value(self, val):
        """

        :param val:
        :return:
        """
        if self.sparse_array is not None:
            self.sparse_array.default_value = self.default_value

    @property
    def is_sparse(self) -> bool:
        """
        is the profile sparse?
        :return: bool
        """
        return self._is_sparse

    @property
    def is_initialized(self) -> bool:
        """
        is the profile initialized?
        :return: bool
        """
        return self._initialized

    def set_initialized(self) -> None:
        """
        Set the profile to initialized
        :return:
        """
        self._initialized = True

    @property
    def sparse_array(self) -> Union[SparseArray, None]:
        """
        Sparse array getter
        :return: SparseArray or None
        """
        return self._sparse_array

    @property
    def dense_array(self) -> Union[np.ndarray, None]:
        """
        Dense array getter
        :return: numpy array or None
        """
        return self._dense_array

    def create_sparse(self, size: int, default_value: Numeric, map_data: Dict[int, Numeric] = None):
        """
        Build sparse from definition
        :param size: size
        :param default_value: default value
        :param map_data: map with the data
        """
        self._is_sparse = True

        try:
            # try casting the default value, if failing use a proper one
            if default_value is not None:
                a = self.dtype(default_value)
            self._sparse_array = SparseArray(data_type=self.dtype, default_value=default_value)
        except ValueError:
            self._sparse_array = SparseArray(data_type=self.dtype, default_value=self._sparse_array.default_value)

        if map_data is None:
            self._sparse_array.create(size=size, default_value=default_value)
        else:
            self._sparse_array.create_from_dict(default_value=default_value, size=size, map_data=map_data)
        self._initialized = True

    def create_dense(self, size: int, default_value: Numeric):
        """
        Create a dense profile
        :param size: size
        :param default_value: default value
        """
        self._is_sparse = False
        self._dense_array = np.full(size, default_value)
        self._sparse_array = None
        self._initialized = True

    @property
    def sparsity(self) -> float:
        """
        Get the profile sparsity
        :return: value (0 for fully dense, almost 1 for fully sparse)
        """
        if self._is_sparse:
            return self._sparse_array.get_sparsity()
        else:
            return 0.0

    def set(self, arr: NumericVec) -> bool:
        """
        Set array value
        :param arr: numpy array to set
        :return:
        """

        if not isinstance(arr, np.ndarray):
            print("You can only set numpy arrays")

        if arr.ndim != 1:
            print("You can only set 1D numpy arrays")

        if len(arr) == 0:
            # Nothing to do
            return False

        if not check_type(dtype=self.dtype, value=arr[0]):
            try:
                # try casting
                arr_mod = arr.astype(self.dtype)
            except ValueError:
                print("Cannot set dense array because the type cast failed")
                return False
            except:
                print("Cannot set dense array because the type check crashed")
                return False
        else:
            arr_mod = arr

        if self.size() > 0:
            if len(arr_mod) != self.size():
                raise ValueError("The array must have the same size as the profile")

        if len(arr_mod) > 0:

            # Count occurrences of each element in the array
            counts = Counter(arr_mod)

            # Find the most frequent element
            most_common_element, most_common_count = counts.most_common(1)[0]

            # compute the sparsity factor
            sparsity_factor = most_common_count / len(arr_mod)

            # if the sparsity is sufficient...
            if sparsity_factor >= self._sparsity_threshold:
                base = most_common_element  # this is the most frequent value
                if isinstance(base, np.bool_):
                    base = bool(base)

                self._is_sparse = True
                self._sparse_array = SparseArray(data_type=self.dtype, default_value=base)

                if most_common_count > 1:
                    if isinstance(arr_mod, np.ndarray):
                        data, indptr = compress_array_numba(arr_mod, base)
                        data_map = {i: x for i, x in zip(indptr, data)}  # this is to use a native python dict
                    else:
                        raise Exception('Unknown profile type' + str(type(arr_mod)))
                else:
                    data_map = dict()

                self._sparse_array.create(size=len(arr_mod),
                                          default_value=base,
                                          data=data_map)
            else:
                self._is_sparse = False
                self._dense_array = arr_mod

        else:
            self._is_sparse = False
            self._dense_array = arr_mod

        self._initialized = True
        return True

    def __eq__(self, other: "Profile") -> bool:
        """
        Compare two profiles
        :param other: Profile
        :return: equal?
        """
        if self._is_sparse == other._is_sparse:

            if self._is_sparse:
                if self._sparse_array is None and other._sparse_array is None:
                    return self.default_value == other.default_value
                else:
                    return self._sparse_array == other._sparse_array
            else:
                if self._dense_array is None and other._dense_array is None:
                    return self.default_value == other.default_value
                else:
                    if self.dtype == float:
                        return np.allclose(self._dense_array, other._dense_array, atol=1.e-10)
                    else:
                        return np.array_equal(self._dense_array, other._dense_array)

        else:
            return False

    def __ne__(self, other: "Profile") -> bool:
        return not self.__eq__(other)

    def __getitem__(self, key: int):
        """
        Get item
        :param key: index position
        :return: value at "key"
        """
        if self._is_sparse:
            return self._sparse_array[key]
        else:

            if self._dense_array is None:
                # Signal of a bug: initialize sparse
                self._is_sparse = True
                self._sparse_array = SparseArray(data_type=self.dtype, default_value=self.default_value)

                # NOTE: This may appear because you declared a profile but
                #       did not associate it with the snapshot property when registering
                print("Initializing sparse when querying, this signals a mis initialization")
                return self.default_value
            else:
                return self._dense_array[key]

    def __setitem__(self, key: int, value):
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

    def __imul__(self, other: Union["Profile", float, int]) -> "Profile":
        """
        Incremental multiplication
        :param other: float or int
        :return: self
        """

        if isinstance(other, (int, float)):

            self.scale(value=other)

        else:
            raise TypeError("Unsupported type {}".format(type(other)))

        return self

    def convert_sparse_to_dense(self) -> None:
        """
        Convert this profile to sparse
        :return: Nothing
        """
        if self._is_sparse:
            self._dense_array = self._sparse_array.toarray()
            self._sparse_array = None
            self._is_sparse = False

    def resize(self, n: int):
        """
        Resize the profile
        :param n: new size
        """
        if isinstance(n, int):
            if self._initialized:
                if self._is_sparse:
                    self._sparse_array.resize(n=n)
                else:
                    try:
                        self._dense_array.resize(n)
                    except ValueError:
                        new_arr = np.zeros(n, dtype=self._dense_array.dtype)
                        new_arr[:len(self._dense_array)] = self._dense_array
                        self._dense_array = new_arr  # this is to avoid ValueError when resizing a numpy array of Objects
            else:
                self._initialized = True
                self.create_sparse(size=n, default_value=self.default_value)
        else:
            raise TypeError("The size must be an integer")

    def resample(self, indices: IntVec):
        """
        Resample this profile in-place
        :param indices: new indices
        """
        if self._is_sparse:
            self._sparse_array.resample(indices=indices)
        else:
            self._dense_array = self._dense_array[indices]

    def fill(self, value: Any):
        """
        Fill this profile with the same value
        :param value: any value
        """
        check_type(dtype=self.dtype, value=value)

        self.default_value = value
        self._is_sparse = True
        if self._sparse_array is None:
            self._sparse_array = SparseArray(data_type=self.dtype, default_value=value)
        self._sparse_array.fill(value)
        self._dense_array = None

    def scale(self, value: Union[float, int]):
        """
        Scale this profile with the same value
        :param value: any value
        """
        if self._is_sparse:

            # Scale the map
            self._sparse_array._map = {key: val * value
                                       for key, val in self._sparse_array.get_map().items()}
        else:

            # Scale the dense array
            self._dense_array *= value

    def size(self) -> int:
        """
        Get the size
        :return: integer
        """
        if self._initialized:
            return self._sparse_array.size() if self._is_sparse else len(self._dense_array)
        else:
            return 0

    def toarray(self) -> NumericVec:
        """
        Get dense numpy array representation
        :return: NumericVec
        """
        if self.size() > 0:
            if self._is_sparse:
                return self._sparse_array.toarray()
            else:
                return self._dense_array
        else:
            return np.zeros(0)

    def tolist(self) -> List[Union[int, float]]:
        """
        Get dense list representation
        :return: List[Union[int, float]]
        """
        return self.toarray().tolist()

    def astype(self, tpe):
        """
        get the dense array as type specified by tpe
        :param tpe: type
        :return: array
        """
        return self.toarray().astype(tpe)

    def get_sparse_representation(self):
        """
        Get the sparse representation of the sparse data
        :return:
        """
        return self._sparse_array.get_sparse_representation()

    def set_sparse_data_from_data(self, indptr, data):
        """
        Set spasrse data from indices
        :param indptr: array of data indices
        :param data: array of data values
        """
        self._sparse_array.set_sparse_data_from_data(indptr=indptr, data=data)

    def fix_nan(self, default_value: float = 0.0):
        """
        Replace NaN values with default value in-place
        :param default_value: some value to replace the NaN with
        """
        if self.dtype == float:
            if not self._is_sparse:
                if self._dense_array is not None:
                    np.nan_to_num(self._dense_array, nan=default_value)  # this is supposed to happen in-place

    def copy(self):
        """
        Deep copy
        :return:
        """
        new_prof = Profile(
            default_value=self.default_value,
            data_type=self.dtype,
            arr=None,
            sparsity_threshold=self._sparsity_threshold,
            is_sparse=self.is_sparse
        )

        if self._sparse_array is not None:
            new_prof._sparse_array = self._sparse_array.copy()

        if self._dense_array is not None:
            new_prof._dense_array = self._dense_array.copy()

        return new_prof
