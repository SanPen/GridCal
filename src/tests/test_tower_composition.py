# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import numpy as np
import GridCalEngine.api as gce


def test_acha():
    """

    # 3 conductors
    bundle = 0.46  # [m]
    Rdc = 0.1363  # [Ohm/km]
    r_ext = 10.5e-3  # [m]
    r_int = 4.5e-3  # [m]

    Ya = 27.5
    Yb = 27.5
    Yc = 27.5

    Xa = -12.65
    Xb = 0
    Xc = 12.65

    # Overhead line parameters (Single circuit tower with an overhead earth wire)

    :return:
    """
    tower = gce.OverheadLineType(name="Tower")

    wire = gce.Wire(name="Panther 30/7 ACSR",
                    diameter=21e-3,
                    diameter_internal=9e-3,
                    is_tube=True,
                    r=0.1363,
                    max_current=1)

    tower.add_wire_relationship(wire=wire, xpos=-12.65 - 0.23, ypos=27.5 + 0.23, phase=1)
    tower.add_wire_relationship(wire=wire, xpos=-12.65 + 0.23, ypos=27.5 + 0.23, phase=1)
    tower.add_wire_relationship(wire=wire, xpos=-12.65 - 0.23, ypos=27.5 - 0.23, phase=1)
    tower.add_wire_relationship(wire=wire, xpos=-12.65 + 0.23, ypos=27.5 - 0.23, phase=1)

    tower.add_wire_relationship(wire=wire, xpos=0 - 0.23, ypos=27.5 + 0.23, phase=2)
    tower.add_wire_relationship(wire=wire, xpos=0 + 0.23, ypos=27.5 + 0.23, phase=2)
    tower.add_wire_relationship(wire=wire, xpos=0 - 0.23, ypos=27.5 - 0.23, phase=2)
    tower.add_wire_relationship(wire=wire, xpos=0 + 0.23, ypos=27.5 - 0.23, phase=2)

    tower.add_wire_relationship(wire=wire, xpos=12.65 - 0.23, ypos=27.5 + 0.23, phase=3)
    tower.add_wire_relationship(wire=wire, xpos=12.65 + 0.23, ypos=27.5 + 0.23, phase=3)
    tower.add_wire_relationship(wire=wire, xpos=12.65 - 0.23, ypos=27.5 - 0.23, phase=3)
    tower.add_wire_relationship(wire=wire, xpos=12.65 + 0.23, ypos=27.5 - 0.23, phase=3)

    tower.compute()

    R1, X1, B1 = tower.get_sequence_values(circuit_idx=0, seq=1)
    R0, X0, B0 = tower.get_sequence_values(circuit_idx=0, seq=0)
    print(f"R0: {R0}, X0: {X0}")
    print(f"R1: {R1}, X1: {X1}")

    Z = tower.z_abcn
    print("Z [ohm/km] =\n", Z)

    Ysh = tower.y_abcn * 1e6 # pass from S/km to uS/km
    print("Y [uS/km] =\n", Ysh)

    Z_expected = np.array([[0.08034301 + 0.53832056j, 0.04625667 + 0.27333481j, 0.04622869 + 0.22981391j],
                           [0.04624575 + 0.27333481j, 0.08034882 + 0.53830903j, 0.04625667 + 0.27333481j],
                           [0.04618743 + 0.22981395j, 0.04624575 + 0.27333481j, 0.08034301 + 0.53832056j]])

    # in [uS/km]
    Ysh_expected = np.array([[0. + 3.35962813j, 0. - 0.80958316j, 0. - 0.30514186j],
                             [0. - 0.80958316j, 0. + 3.52714236j, 0. - 0.80958316j],
                             [0. - 0.30514186j, 0. - 0.80958316j, 0. + 3.35962813j]])

    assert np.allclose(Z, Z_expected, atol=1e-4)
    assert np.allclose(Ysh, Ysh_expected)
