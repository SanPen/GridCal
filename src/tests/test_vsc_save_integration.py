# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import os

from VeraGridEngine.api import *
from VeraGridEngine.IO.file_handler import FileOpen
from VeraGridEngine.enumerations import FaultType
import VeraGridEngine as gce


def test_vsc_save_integration():
    """
    Test case24_7_jb.m containing 7 converters
    """

    fname = os.path.join('data', 'grids', 'case24_7_jb.m')
    grid = FileOpen(fname).open()

    control1_vsc0 = grid.vsc_devices[0].control1
    control1_vsc1 = grid.vsc_devices[1].control1
    control1_vsc2 = grid.vsc_devices[2].control1
    control1_vsc3 = grid.vsc_devices[3].control1
    control1_vsc4 = grid.vsc_devices[4].control1
    control1_vsc5 = grid.vsc_devices[5].control1
    control1_vsc6 = grid.vsc_devices[6].control1

    control1_val_vsc0 = grid.vsc_devices[0].control1_val
    control1_val_vsc1 = grid.vsc_devices[1].control1_val
    control1_val_vsc2 = grid.vsc_devices[2].control1_val
    control1_val_vsc3 = grid.vsc_devices[3].control1_val
    control1_val_vsc4 = grid.vsc_devices[4].control1_val
    control1_val_vsc5 = grid.vsc_devices[5].control1_val
    control1_val_vsc6 = grid.vsc_devices[6].control1_val

    control2_vsc0 = grid.vsc_devices[0].control2
    control2_vsc1 = grid.vsc_devices[1].control2
    control2_vsc2 = grid.vsc_devices[2].control2
    control2_vsc3 = grid.vsc_devices[3].control2
    control2_vsc4 = grid.vsc_devices[4].control2
    control2_vsc5 = grid.vsc_devices[5].control2
    control2_vsc6 = grid.vsc_devices[6].control2

    control2_val_vsc0 = grid.vsc_devices[0].control2_val
    control2_val_vsc1 = grid.vsc_devices[1].control2_val
    control2_val_vsc2 = grid.vsc_devices[2].control2_val
    control2_val_vsc3 = grid.vsc_devices[3].control2_val
    control2_val_vsc4 = grid.vsc_devices[4].control2_val
    control2_val_vsc5 = grid.vsc_devices[5].control2_val
    control2_val_vsc6 = grid.vsc_devices[6].control2_val

    # save and reload grid
    gce.save_file(grid, "test_vsc_save_integration_temp.veragrid")
    grid_reload = gce.open_file("test_vsc_save_integration_temp.veragrid")

    try:
        assert control1_vsc0 == grid_reload.vsc_devices[0].control1
        assert control1_vsc1 == grid_reload.vsc_devices[1].control1
        assert control1_vsc2 == grid_reload.vsc_devices[2].control1
        assert control1_vsc3 == grid_reload.vsc_devices[3].control1
        assert control1_vsc4 == grid_reload.vsc_devices[4].control1
        assert control1_vsc5 == grid_reload.vsc_devices[5].control1
        assert control1_vsc6 == grid_reload.vsc_devices[6].control1

        assert control1_val_vsc0 == grid_reload.vsc_devices[0].control1_val
        assert control1_val_vsc1 == grid_reload.vsc_devices[1].control1_val
        assert control1_val_vsc2 == grid_reload.vsc_devices[2].control1_val
        assert control1_val_vsc3 == grid_reload.vsc_devices[3].control1_val
        assert control1_val_vsc4 == grid_reload.vsc_devices[4].control1_val
        assert control1_val_vsc5 == grid_reload.vsc_devices[5].control1_val
        assert control1_val_vsc6 == grid_reload.vsc_devices[6].control1_val

        assert control2_vsc0 == grid_reload.vsc_devices[0].control2
        assert control2_vsc1 == grid_reload.vsc_devices[1].control2
        assert control2_vsc2 == grid_reload.vsc_devices[2].control2
        assert control2_vsc3 == grid_reload.vsc_devices[3].control2
        assert control2_vsc4 == grid_reload.vsc_devices[4].control2
        assert control2_vsc5 == grid_reload.vsc_devices[5].control2
        assert control2_vsc6 == grid_reload.vsc_devices[6].control2

        assert control2_val_vsc0 == grid_reload.vsc_devices[0].control2_val
        assert control2_val_vsc1 == grid_reload.vsc_devices[1].control2_val
        assert control2_val_vsc2 == grid_reload.vsc_devices[2].control2_val
        assert control2_val_vsc3 == grid_reload.vsc_devices[3].control2_val
        assert control2_val_vsc4 == grid_reload.vsc_devices[4].control2_val
        assert control2_val_vsc5 == grid_reload.vsc_devices[5].control2_val
        assert control2_val_vsc6 == grid_reload.vsc_devices[6].control2_val

        # delete the temp file
        os.remove("test_vsc_save_integration_temp.veragrid")

    except Exception as e:
        os.remove("test_vsc_save_integration_temp.veragrid")
        raise e


if __name__ == '__main__':
    test_vsc_save_integration()
