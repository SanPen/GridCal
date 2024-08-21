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
import numpy as np

from GridCalEngine.api import *


def test_multi_circuit_deep_copy() -> bool:
    """
    In this test we are going to:
    - make a deep copy of the original circuit
    - Make modifications to the copy
    - Check that the copy and the original are different
      by aplying the modification only to the original and
      checking that it is equal to the copy
    :return:
    """
    fname = os.path.join('data', 'grids', 'IEEE39_1W.gridcal')
    main_circuit = FileOpen(fname).open()

    main_circuit_cpy = main_circuit.copy()

    # modify the copy
    for elm in main_circuit_cpy.buses:
        elm.active = False

    for elm in main_circuit_cpy.get_loads():
        elm.P_prof *= 2.0

    for elm in main_circuit_cpy.get_generators():
        elm.P_prof *= 3.0

    # check that the copy and the original are still different by
    # changing the original in the same way and checking that both are the same
    for elm, elm_copy in zip(main_circuit.buses, main_circuit_cpy.buses):
        assert elm.active != elm_copy.active

    for elm, elm_copy in zip(main_circuit.get_loads(), main_circuit_cpy.get_loads()):
        assert np.all(np.isclose(elm.P_prof.toarray() * 2.0, elm_copy.P_prof.toarray()))

    for elm, elm_copy in zip(main_circuit.get_generators(), main_circuit_cpy.get_generators()):
        assert np.all(np.isclose(elm.P_prof.toarray() * 3.0, elm_copy.P_prof.toarray()))

    return True
