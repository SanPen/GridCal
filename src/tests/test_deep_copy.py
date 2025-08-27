# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os
import numpy as np

from VeraGridEngine.api import *


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
