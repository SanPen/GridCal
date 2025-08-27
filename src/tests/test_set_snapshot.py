# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os
from VeraGridEngine.api import *


def test_set_snapshot():
    """

    :return:
    """
    fname = os.path.join('data', 'grids', 'IEEE39_1W.gridcal')

    main_circuit = FileOpen(fname).open()

    # for every time step in the profile...
    for t_idx in range(main_circuit.get_time_number()):

        # set the snapshot value
        main_circuit.set_state(t=t_idx)

        # check that indeed the snapshot values match the profile at t_idx
        for elm in main_circuit.items():
            for prop_name, prop in elm.registered_properties.items():
                if prop.has_profile():
                    # get the snapshot
                    val = getattr(elm, prop.name)

                    # get the profile value at the position
                    val_p = elm.get_profile(prop_name)[t_idx]

                    # check that they're equal
                    ok = (val == val_p)
                    assert ok
