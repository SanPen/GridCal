# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from unittest.mock import patch
from VeraGridEngine.Devices.Branches.overhead_line_type import OverheadLineType
from VeraGridEngine.Devices.Branches.underground_line_type import UndergroundLineType
from VeraGridEngine.Devices.Branches.sequence_line_type import SequenceLineType
from VeraGridEngine.Devices.Branches.line import Line
from VeraGridEngine import VeraGridEngine as gce


def test_valid_circuit_idx():
    line = Line()
    tower = gce.OverheadLineType(name="400 kV quadruple circuit triplex")
    tower.Vnom = 400
    tower.earth_resistivity = 200

    wire = gce.Wire(
        name="402-AL1/52-ST1A",
        code="LA 455 CONDOR",
        diameter=27.72,
        r=0.0718,
        max_current=0.799,
        material="ACSR"
    )

    neutral_wire = gce.Wire(
        name="OPGW 25kA 17.10",
        code="OPGW",
        diameter=17.1,
        r=0.373,
        max_current=25,
        is_tube=True,
        diameter_internal=9.7,
        material="ACS"
    )

    # triplex wires A1
    tower.add_wire_relationship(wire=wire, xpos=-13 - 0.2, ypos=22, phase=1)
    tower.add_wire_relationship(wire=wire, xpos=-13 + 0.2, ypos=22, phase=1)
    tower.add_wire_relationship(wire=wire, xpos=-13, ypos=22 - 0.34, phase=1)

    # triplex wires B1
    tower.add_wire_relationship(wire=wire, xpos=-13 - 0.2, ypos=29, phase=2)
    tower.add_wire_relationship(wire=wire, xpos=-13 + 0.2, ypos=29, phase=2)
    tower.add_wire_relationship(wire=wire, xpos=-13, ypos=29 - 0.34, phase=2)

    # triplex wires C1
    tower.add_wire_relationship(wire=wire, xpos=-13 - 0.2, ypos=36, phase=3)
    tower.add_wire_relationship(wire=wire, xpos=-13 + 0.2, ypos=36, phase=3)
    tower.add_wire_relationship(wire=wire, xpos=-13, ypos=36 - 0.34, phase=3)

    # triplex wires A2
    tower.add_wire_relationship(wire=wire, xpos=-7 - 0.2, ypos=22, phase=4)
    tower.add_wire_relationship(wire=wire, xpos=-7 + 0.2, ypos=22, phase=4)
    tower.add_wire_relationship(wire=wire, xpos=-7, ypos=22 - 0.34, phase=4)

    # triplex wires B2
    tower.add_wire_relationship(wire=wire, xpos=-7 - 0.2, ypos=29, phase=5)
    tower.add_wire_relationship(wire=wire, xpos=-7 + 0.2, ypos=29, phase=5)
    tower.add_wire_relationship(wire=wire, xpos=-7, ypos=29 - 0.34, phase=5)

    # triplex wires C2
    tower.add_wire_relationship(wire=wire, xpos=-7 - 0.2, ypos=36, phase=6)
    tower.add_wire_relationship(wire=wire, xpos=-7 + 0.2, ypos=36, phase=6)
    tower.add_wire_relationship(wire=wire, xpos=-7, ypos=36 - 0.34, phase=6)

    # triplex wires A3
    tower.add_wire_relationship(wire=wire, xpos=7 - 0.2, ypos=22, phase=7)
    tower.add_wire_relationship(wire=wire, xpos=7 + 0.2, ypos=22, phase=7)
    tower.add_wire_relationship(wire=wire, xpos=7, ypos=22 - 0.34, phase=7)

    # triplex wires B3
    tower.add_wire_relationship(wire=wire, xpos=7 - 0.2, ypos=29, phase=8)
    tower.add_wire_relationship(wire=wire, xpos=7 + 0.2, ypos=29, phase=8)
    tower.add_wire_relationship(wire=wire, xpos=7, ypos=29 - 0.34, phase=8)

    # triplex wires C3
    tower.add_wire_relationship(wire=wire, xpos=7 - 0.2, ypos=36, phase=9)
    tower.add_wire_relationship(wire=wire, xpos=7 + 0.2, ypos=36, phase=9)
    tower.add_wire_relationship(wire=wire, xpos=7, ypos=36 - 0.34, phase=9)

    # triplex wires A4
    tower.add_wire_relationship(wire=wire, xpos=13 - 0.2, ypos=22, phase=10)
    tower.add_wire_relationship(wire=wire, xpos=13 + 0.2, ypos=22, phase=10)
    tower.add_wire_relationship(wire=wire, xpos=13, ypos=22 - 0.34, phase=10)

    # triplex wires B4
    tower.add_wire_relationship(wire=wire, xpos=13 - 0.2, ypos=29, phase=11)
    tower.add_wire_relationship(wire=wire, xpos=13 + 0.2, ypos=29, phase=11)
    tower.add_wire_relationship(wire=wire, xpos=13, ypos=29 - 0.34, phase=11)

    # triplex wires C4
    tower.add_wire_relationship(wire=wire, xpos=13 - 0.2, ypos=36, phase=12)
    tower.add_wire_relationship(wire=wire, xpos=13 + 0.2, ypos=36, phase=12)
    tower.add_wire_relationship(wire=wire, xpos=13, ypos=36 - 0.34, phase=12)

    # neutral/optic
    tower.add_wire_relationship(wire=neutral_wire, xpos=-6, ypos=41, phase=0)
    tower.add_wire_relationship(wire=neutral_wire, xpos=6, ypos=41, phase=0)

    tower.compute()

    line.set_circuit_idx(2, tower)

    assert line._circuit_idx == 2


def test_invalid_template_none():
    line = Line()

    try:
        line.set_circuit_idx(1, None)
    except Exception as e:
        assert str(e) == "Template must be set before changing the circuit index."


def test_invalid_template_type():
    line = Line()

    try:
        line.set_circuit_idx(1, "InvalidTemplate")
    except Exception as e:
        assert str(e) == "Invalid template type. Must be OverheadLineType, UndergroundLineType, or SequenceLineType."


def test_circuit_idx_exceeds_n_circuits():
    line = Line()
    template = UndergroundLineType()
    template.n_circuits = 2

    try:
        line.set_circuit_idx(3, template)
    except Exception as e:
        assert str(e) == "Circuit index exceeds the number of circuits in the template."


def test_circuit_idx_less_than_or_equal_to_zero():
    line = Line()
    template = SequenceLineType()
    template.n_circuits = 4

    try:
        line.set_circuit_idx(0, template)
    except Exception as e:
        assert str(e) == "Circuit index must be greater than 0."


def test_valid_circuit_idx_with_different_template():
    line = Line()
    template = UndergroundLineType()
    template.n_circuits = 2

    line.set_circuit_idx(1, template)
    assert line._circuit_idx == 1


def test_circuit_idx_setter():
    line = Line()
    line.enable_auto_updates()  # Enable auto-update for testing

    # Test with a valid value
    with patch('builtins.print') as mock_print:
        line.circuit_idx = 2
        assert line._circuit_idx == 2
        mock_print.assert_called_once_with(
            "No impedance updates are being done, use the apply_template method to update the impedance values"
        )

    # Test with an invalid value (<= 0)
    line.disable_auto_updates()  # Disable auto-update for this test
    line.circuit_idx = 0
    assert line._circuit_idx == 2  # Value should remain unchanged


if __name__ == '__main__':
    test_valid_circuit_idx()
    test_invalid_template_none()
    test_invalid_template_type()
    test_circuit_idx_exceeds_n_circuits()
    test_circuit_idx_less_than_or_equal_to_zero()
    test_valid_circuit_idx_with_different_template()
    test_circuit_idx_setter()