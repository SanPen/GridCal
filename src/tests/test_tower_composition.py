# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import numpy as np
import GridCalEngine.api as gce


def test_tower_composition():
    """
    This test performs the tower composition of the distribution grid demo
    :return:
    """
    tower = gce.OverheadLineType(name="Tower")

    wire = gce.Wire(name="AWG SLD",
                    gmr=0.001603,
                    r=1.485077,
                    x=0.0,
                    max_current=0.11)

    tower.add_wire_relationship(wire=wire, xpos=0.0, ypos=7.0, phase=1)
    tower.add_wire_relationship(wire=wire, xpos=0.4, ypos=7.0, phase=2)
    tower.add_wire_relationship(wire=wire, xpos=0.8, ypos=7.0, phase=3)

    tower.compute()

    R0, X0, Bsh0 = tower.get_zero_sequence_values(0)
    R1, X1, Bsh1 = tower.get_positive_sequence_values(0)

    print(f"R0: {R0}, X0: {X0}")
    print(f"R1: {R1}, X1: {X1}")

    assert np.isclose(R0, 1.5892070972018013, atol=1e-4)
    assert np.isclose(X0, 1.1989736994044684, atol=1e-4)
    assert np.isclose(R1, 1.485081882395359, atol=1e-4)
    assert np.isclose(X1, 0.3613207070253497, atol=1e-4)
