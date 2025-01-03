# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os
import GridCalEngine.api as gce


def test_load_save_load() -> None:
    """
    This test checks if the saving and load process is correct

    The test consists in:
    - loading grids in different gridcal variations (grid1)
    - saving the grid with a different name
    - loading the saved grid (grid2)
    - comparing that grid1 == grid2

    """
    folder = os.path.join('data', 'grids')

    if not os.path.exists("output"):
        os.makedirs("output")

    for name in ['IEEE39_1W.gridcal',
                 'hydro_grid_IEEE39.gridcal',
                 'IEEE57.gridcal',
                 'fubm_caseHVDC_vt.gridcal',
                 'Test_SRAP.gridcal']:

        fname = os.path.join(folder, name)

        # open the main grid
        grid1 = gce.open_file(fname)

        name, ext = os.path.splitext(os.path.basename(fname))

        fname2 = os.path.join("output", name + '_to_save' + ext)

        gce.save_file(grid=grid1, filename=fname2)

        # open the main grid again
        grid2 = gce.open_file(fname2)

        # compare the original grid with the saved one to check that they are equal
        equal, logger = grid1.compare_circuits(grid2, detailed_profile_comparison=True)

        if not equal:
            logger.print()

        # asset for failing
        assert equal

        # if all ok, we can remove the test file
        os.remove(fname2)


def test_load_save_load2() -> None:
    """
    This test checks if the saving and load process is correct with sparse profile changing.
    This is according to issue #309
    :return:
    """
    grid1 = gce.MultiCircuit()
    grid1.set_unix_time([0, 3600])
    b1 = grid1.add_bus()
    b2 = grid1.add_bus()
    b3 = grid1.add_bus()
    l1 = grid1.add_line(gce.Line(name='l1', bus_from=b1, bus_to=b2, rate=10.0))
    l2 = grid1.add_line(gce.Line(name='l2', bus_from=b2, bus_to=b3, rate=10.0))
    l3 = grid1.add_line(gce.Line(name='l3', bus_from=b3, bus_to=b1, rate=10.0))

    l1.rate_prof[1] = 20.0
    l2.rate_prof[1] = 30.0
    l3.rate_prof[1] = 40.0

    if not os.path.exists("output"):
        os.makedirs("output")

    o_file = os.path.join("output", "test_load_save_load2.gridcal")

    gce.save_file(grid=grid1, filename=o_file)

    grid2 = gce.open_file(o_file)

    equal, logger = grid2.compare_circuits(grid1, detailed_profile_comparison=True)

    assert equal

    os.remove(o_file)
