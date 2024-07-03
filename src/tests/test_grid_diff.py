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
