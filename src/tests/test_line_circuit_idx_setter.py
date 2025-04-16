# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from unittest.mock import patch
from GridCalEngine.Devices.Branches.overhead_line_type import OverheadLineType, Wire
from GridCalEngine.Devices.Branches.underground_line_type import UndergroundLineType
from GridCalEngine.Devices.Branches.sequence_line_type import SequenceLineType
from src.GridCalEngine.Devices.Branches.line import Line


def test_valid_circuit_idx():
    """
    Create a 3 circuit tower, assign the circuit 2 to a line, check that it is what we said
    :return:
    """
    line = Line()
    wire = Wire()
    template = OverheadLineType()

    for i in range(9):
        template.add_wire_relationship(wire, i, 7, i + 1)

    assert template.n_circuits == 3

    line.set_circuit_idx(2, template)
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
