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

    external, boundary, internal, boundary_branches = grid.get_reduction_sets(reduction_bus_indices=remove_bus_idx)

    assert np.equal(expected_boundary_idx, boundary).all()

    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.DC)

    pf_res = gce.power_flow(grid=grid, options=pf_options)

    # gce.ward_reduction(grid=grid, reduction_bus_indices=remove_bus_idx, pf_res=pf_res)
    nc = gce.compile_numerical_circuit_at(circuit=grid, t_idx=None)
    lin = gce.LinearAnalysis(nc=nc)
    gce.ptdf_reduction(grid=grid, reduction_bus_indices=remove_bus_idx, PTDF=lin.PTDF)

    pf_res2 = gce.power_flow(grid=grid, options=pf_options)

    diff_sf = pf_res.get_branch_df() - pf_res2.get_branch_df()

    print()


if __name__ == '__main__':
    test_ward_reduction()
