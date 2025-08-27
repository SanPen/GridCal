# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import math
import os
import numpy as np
import VeraGridEngine.api as gce
from VeraGridEngine.Devices.profile import Profile, SparseArray, check_if_sparse


def test_sparse_array1():
    """
    Test that dense arrays translate properly
    :return:
    """
    n = 10
    x = np.sin(np.arange(n) + 1.0)

    s = SparseArray(data_type=float, default_value=0.0)
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

    s = SparseArray(data_type=float, default_value=0.0)
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

    s = SparseArray(data_type=int, default_value=0.0)
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

    s = SparseArray(data_type=int, default_value=0.0)
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

    # now we set the threshold to 75% sparsity, hence the array will be considered sparse
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


def test_grid_profile_initialization():
    """
    This test checks that when creating a profile, the profile slices are identical to the snapshot
    """
    fname1 = os.path.join('data', 'grids', 'Matpower', 'case14.m')
    fname2 = os.path.join('data', 'grids', 'ACTIVSg2000.gridcal')

    for fname in [fname1, fname2]:
        grid = gce.open_file(fname)

        # the original grid has no profiles for sure, so we create them
        grid.delete_profiles()
        grid.create_profiles(steps=5, step_length=1.0, step_unit="h")

        nc_base = gce.compile_numerical_circuit_at(circuit=grid, t_idx=None)

        for t_idx in range(grid.get_time_number()):
            nc_t = gce.compile_numerical_circuit_at(circuit=grid, t_idx=t_idx)

            ok, logger = nc_base.compare(nc_t)

            if not ok:
                logger.print()

            assert ok
