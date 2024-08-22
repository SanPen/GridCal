# GridCal
# Copyright (C) 2022 Santiago Peñate Vera
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
import math
import numpy as np
from GridCalEngine.Devices.profile import Profile, SparseArray, check_if_sparse


def test_sparse_array1():
    """
    Test that dense arrays translate properly
    :return:
    """
    n = 10
    x = np.sin(np.arange(n) + 1.0)

    s = SparseArray(data_type=float)
    s.create_from_array(x, default_value=0.0)

    all_ok = True
    for i in range(n):
        if x[i] != s[i]:
            all_ok = False

    assert all_ok

    # x is fully dense, there should be internally the same as x
    assert len(s._map) == n


def test_sparse_array2():
    """
    Test that sparse arrays translate properly
    :return:
    """
    n = 100
    x = np.zeros(n)
    for i in range(10, 30):
        x[i] = math.sin(i)

    s = SparseArray(data_type=float)
    s.create_from_array(x, default_value=0.0)

    all_ok = True
    for i in range(n):
        if x[i] != s[i]:
            all_ok = False

    assert all_ok

    # x is fully sparse, there are only 20 different values
    assert len(s._map) == 20  # 30 - 10 -> 20


def test_sparse_array3():
    """
    Test that sparse arrays translate properly
    :return:
    """
    n = 100
    x = np.full(n, 15)
    x[20] = 30

    is_sparse, most_frequent = check_if_sparse(arr=x)

    assert is_sparse  # should be sparse

    s = SparseArray(data_type=int)
    s.create_from_array(x, default_value=most_frequent)

    all_ok = True
    for i in range(n):
        if x[i] != s[i]:
            all_ok = False

    assert all_ok

    # x is fully sparse, the size should be 1
    assert len(s._map) == 1  # only one value is different


def test_sparse_array4():
    """
    Test that sparse arrays translate properly
    :return:
    """
    n = 100
    x = np.zeros(n)
    for i in range(10, 30):
        x[i] = math.sin(i)

    s = SparseArray(data_type=int)
    s.create_from_array(x, default_value=0)

    # generate rando indices
    indices = np.random.randint(low=0, high=n, size=n)

    # resample the sparse array
    s.resample(indices=indices)

    # resample the numpy array
    x2 = x[indices]

    all_ok = True
    for i in range(n):
        if x2[i] != s[i]:
            all_ok = False

    assert all_ok

    # x is fully sparse
    assert len(s._map) == len(x2[x2 != 0])  # should be 17


def test_profile1():
    """
    Test that sparse arrays translate properly
    :return:
    """
    n = 100
    x = np.zeros(n)
    for i in range(10, 30):  # 20 out of 100 has values (expected 80% sparsity)
        x[i] = math.sin(i)

    # we set the threshold to 90% sparsity, hence the profile will be considered dense
    profile = Profile(default_value=0.0, arr=x, sparsity_threshold=0.9, data_type=float)

    assert not profile.is_sparse

    all_ok = True
    for i in range(n):
        if x[i] != profile[i]:
            all_ok = False

    assert all_ok

    # now we set the threshhold to 75% sparsity, hence the array will be considered sparse
    profile = Profile(default_value=0.0, arr=x, sparsity_threshold=0.75, data_type=float)
    assert profile.is_sparse

    # x is fully sparse, there are only 20 different values
    assert len(profile._sparse_array._map) == 20  # 30 - 10 -> 20


def test_profile2():
    """
    Test that sparse arrays translate properly
    :return:
    """
    n = 100
    x = np.full(n, 15)
    x[20] = 30

    profile = Profile(default_value=15, arr=x, data_type=int)

    assert profile.is_sparse

    all_ok = True
    for i in range(n):
        if x[i] != profile[i]:
            all_ok = False

    assert all_ok

    # x is fully sparse, the size should be 1
    assert len(profile._sparse_array._map) == 1  # only one value is different
