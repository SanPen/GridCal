# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0
import os
import GridCalEngine.api as gce


def test_add_stuff_roundtrip() -> None:
    """
    This test does the following:
    We open IEEE57 twice, one for modification and another as baseline
    We open Lynn5bus and add it to the IEEE57 for modification
    We compute the difference between the modified grid and the baseline,
    The difference should be equal to what we added: i.e Lynn5bus
    """
    original = gce.open_file(filename=os.path.join("data", "grids", "IEEE57.gridcal"))  # we use this for diff
    # gce.save_file(original, os.path.join("data", "grids", "IEEE57.gridcal"))  # it may fail if new properties are added, just save the original file

    grid1 = gce.open_file(filename=os.path.join("data", "grids", "IEEE57.gridcal"))  # we modify this one in place

    # add stuff
    lynn_original = gce.open_file(filename=os.path.join("data", "grids", "lynn5node.gridcal"))
    lynn_original.delete_profiles()

    # add elements one by one
    for elm in lynn_original.items():
        grid1.add_element(obj=elm)

    # calculate the difference of the modified grid with the original
    ok_diff, diff_logger, diff = grid1.differentiate_circuits(base_grid=original)

    # the calculated difference should be equal to the grid we added
    ok_compare, comp_logger = diff.compare_circuits(grid2=lynn_original, skip_internals=True)

    if not ok_compare:
        comp_logger.print()

    assert ok_compare
