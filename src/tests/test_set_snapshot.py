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
import os
from GridCalEngine.api import *


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
