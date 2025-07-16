# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os
import numpy as np
import GridCalEngine.api as gce


def test_ward_reduction():
    fname = os.path.join('data', 'grids', 'case89pegase.m')
    grid = gce.open_file(filename=fname)

    remove_bus_idx = np.array([21, 36, 44, 50, 53])
    expected_boundary_idx = np.sort(np.array([20, 77, 15, 32]))

    external, boundary, internal = grid.get_reduction_sets(reduction_bus_indices=remove_bus_idx)

    assert np.equal(expected_boundary_idx, boundary).all()

    pf_res = gce.power_flow(grid=grid)

    gce.ward_reduction(grid=grid, reduction_bus_indices=remove_bus_idx, pf_res=pf_res)

    pf_res2 = gce.power_flow(grid=grid)

    diff_sf = pf_res.get_branch_df() - pf_res2.get_branch_df()

    print()


if __name__ == '__main__':
    test_ward_reduction()
