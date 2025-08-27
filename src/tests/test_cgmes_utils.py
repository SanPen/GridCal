# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import pytest
from VeraGridEngine.IO.cim.cgmes.cgmes_utils import get_voltage_power_transformer_end, \
    get_pu_values_power_transformer_end, get_voltage_ac_line_segment, \
    get_pu_values_ac_line_segment, get_rate_ac_line_segment, get_voltage_terminal, get_nominal_voltage
from VeraGridEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.ac_line_segment import ACLineSegment
from VeraGridEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.base_voltage import BaseVoltage
from VeraGridEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.busbar_section import BusbarSection
from VeraGridEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.conducting_equipment import ConductingEquipment
from VeraGridEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.energy_consumer import EnergyConsumer
from VeraGridEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.identified_object import IdentifiedObject
from VeraGridEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.load_response_characteristic import LoadResponseCharacteristic
from VeraGridEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.power_transformer import PowerTransformer
from VeraGridEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.power_transformer_end import PowerTransformerEnd
from VeraGridEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.switch import Switch
from VeraGridEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.terminal import Terminal
from VeraGridEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.topological_node import TopologicalNode
from VeraGridEngine.data_logger import DataLogger

from VeraGridEngine.IO.cim.cgmes.cgmes_utils import get_pu_values_power_transformer


def test_get_windings_no_windings_returns_no_element():
    # Create a PowerTransformer instance with no references to PowerTransformerEnd
    power_transformer = PowerTransformer("a", "b")
    assert power_transformer.PowerTransformerEnd is None


# def test_get_windings_add_windings_returns_correct_element():
#     # Create a PowerTransformer instance with no references to PowerTransformerEnd
#     power_transformer = PowerTransformer("a", "b")
#     pte = PowerTransformerEnd()
#     power_transformer.PowerTransformerEnd = pte
#     assert power_transformer.PowerTransformerEnd[0] == pte


def test_get_pu_values_power_transformer_no_power_transformer():
    with pytest.raises(AttributeError) as excinfo:
        get_pu_values_power_transformer(None, 100.0)
        assert str(excinfo.value).index('NoneType') != -1
        assert str(excinfo.value).index('references_to_me') != -1


def test_get_pu_values_power_transformer_no_winding():
    power_transformer = PowerTransformer()
    power_transformer.PowerTransformerEnd = []
    (R, X, G, B, R0, X0, G0, B0) = get_pu_values_power_transformer(power_transformer, 100.0)
    assert R == 0
    assert X == 0
    assert G == 0
    assert B == 0
    assert R0 == 0
    assert X0 == 0
    assert G0 == 0
    assert B0 == 0


def test_get_pu_values_power_transformer_two_windings():
    power_transformer = PowerTransformer()

    power_transformer_end = PowerTransformerEnd()
    power_transformer_end.ratedS = 1
    power_transformer_end.ratedU = 2

    power_transformer_end.r = 1
    power_transformer_end.x = 1
    power_transformer_end.g = 1
    power_transformer_end.b = 1
    power_transformer_end.r0 = 1
    power_transformer_end.x0 = 1
    power_transformer_end.g0 = 1
    power_transformer_end.b0 = 1
    power_transformer_end.endNumber = 1
    power_transformer.PowerTransformerEnd = [power_transformer_end, power_transformer_end]
    (R, X, G, B, R0, X0, G0, B0) = get_pu_values_power_transformer(power_transformer, 100.0)
    assert R == 50
    assert X == 50
    assert G == 800
    assert B == 800
    assert R0 == 50
    assert X0 == 50
    assert G0 == 800
    assert B0 == 800


@pytest.fixture
def transformer_end_with_ratedU():
    pte = PowerTransformerEnd()
    pte.ratedU = 110
    pte.BaseVoltage = None
    return pte


@pytest.fixture
def transformer_end_with_BaseVoltage():
    pte = PowerTransformerEnd()
    pte.ratedU = 0
    pte.BaseVoltage = BaseVoltage()
    pte.BaseVoltage.nominalVoltage = 220
    return pte


@pytest.fixture
def transformer_end_without_voltage():
    pte = PowerTransformerEnd()
    pte.ratedU = 0
    pte.BaseVoltage = None
    return pte


def test_get_voltage_power_transformer_end_has_ratedU_value_returns_value(transformer_end_with_ratedU):
    assert get_voltage_power_transformer_end(transformer_end_with_ratedU) == 110


def test_get_voltage_power_transformer_end_has_BaseVoltage_value_returns_value(transformer_end_with_BaseVoltage):
    assert get_voltage_power_transformer_end(transformer_end_with_BaseVoltage) == 220


def test_get_voltage_power_transformer_end_has_no_voltage_returns_None(transformer_end_without_voltage):
    assert get_voltage_power_transformer_end(transformer_end_without_voltage) is None


def test_get_pu_values_power_transformer_end_no_ratedS_and_ratedU_returns_default():
    pte = PowerTransformerEnd()
    (R, X, G, B, R0, X0, G0, B0) = get_pu_values_power_transformer_end(pte)
    assert R == 1e-20
    assert X == 1e-20
    assert G == 1e-20
    assert B == 1e-20
    assert R0 == 1e-20
    assert X0 == 1e-20
    assert G0 == 1e-20
    assert B0 == 1e-20


def test_get_voltage_ac_line_segment_basevoltage_exists_returns_nominal_voltage():
    acl = ACLineSegment()
    acl.BaseVoltage = BaseVoltage()
    acl.BaseVoltage.nominalVoltage = 220
    assert get_voltage_ac_line_segment(acl, None) == 220


def test_get_voltage_ac_line_segment_basevoltage_None_Terminal_None_returns_None():
    acl = ACLineSegment()
    assert get_voltage_ac_line_segment(acl, None) is None


def test_get_voltage_ac_line_segment_basevoltage_None_Terminal_not_None_returns_first_elements_voltage():
    acl = ACLineSegment()
    t = Terminal()
    t.TopologicalNode = TopologicalNode()
    t.TopologicalNode.BaseVoltage = BaseVoltage()
    t.TopologicalNode.BaseVoltage.nominalVoltage = 220
    acl.references_to_me["Terminal"] = [t]
    assert get_voltage_ac_line_segment(acl, None) == 220


def test_get_voltage_ac_line_segment_basevoltage_None_Terminal_length_0_returns_None():
    acl = ACLineSegment()
    t = Terminal()
    t.TopologicalNode = TopologicalNode()
    t.TopologicalNode.BaseVoltage = BaseVoltage()
    t.TopologicalNode.BaseVoltage.nominalVoltage = 220
    acl.references_to_me["Terminal"] = []
    assert get_voltage_ac_line_segment(acl, None) is None


def test_get_pu_values_ac_line_segment_BaseVoltage_is_None_returns_zero():
    acls = ACLineSegment()
    (R, X, G, B, R0, X0, G0, B0) = get_pu_values_ac_line_segment(acls, None)
    assert R == 1e-20
    assert X == 0.00001
    assert G == 1e-20
    assert B == 1e-20
    assert R0 == 1e-20
    assert X0 == 1e-20
    assert G0 == 1e-20
    assert B0 == 1e-20


def test_get_pu_values_ac_line_segment_BaseVoltage_is_filled_returns_correct_values():
    acls = ACLineSegment()
    acls.BaseVoltage = BaseVoltage()
    acls.BaseVoltage.nominalVoltage = 10
    acls.r = 100
    acls.x = 100
    acls.gch = 100
    acls.bch = 100
    acls.r0 = 100
    acls.x0 = 100
    acls.g0ch = 100
    acls.b0ch = 100

    (R, X, G, B, R0, X0, G0, B0) = get_pu_values_ac_line_segment(acls, None)
    assert R == 100
    assert X == 100
    assert G == 100
    assert B == 100
    assert R0 == 100
    assert X0 == 100
    assert G0 == 100
    assert B0 == 100


def test_get_rate_ac_line_segment_returns_constant():
    assert get_rate_ac_line_segment() == 1e-20


def test_get_voltage_terminal_topologicalnode_nomivalvoltage_set_retuns_value()-> float | None:
    t = Terminal()
    t.TopologicalNode = TopologicalNode()
    t.TopologicalNode.BaseVoltage = BaseVoltage()
    t.TopologicalNode.BaseVoltage.nominalVoltage = 10
    assert get_voltage_terminal(t, None) == 10


def test_get_voltage_terminal_no_topologicalnode_retuns_None() -> float | None:
    t = Terminal()
    t.TopologicalNode = None
    assert get_voltage_terminal(t, None) is None


def test_get_nominal_voltage_correct_nominalvoltage_returns_value():
    tn = TopologicalNode()
    tn.BaseVoltage = BaseVoltage()
    tn.BaseVoltage.nominalVoltage = 220
    voltage = get_nominal_voltage(tn, None)
    assert voltage == 220
    assert isinstance(voltage, float)


def test_get_nominal_voltage_no_basevoltage_returns_0():
    tn = TopologicalNode()
    logger = DataLogger()
    voltage = get_nominal_voltage(tn, logger)
    assert voltage == 0
    assert isinstance(voltage, float)


def test_get_nominal_voltage_basevoltage_is_string_log_error():
    tn = TopologicalNode()
    tn.BaseVoltage = "str"
    logger = DataLogger()
    get_nominal_voltage(tn, logger)
    assert len(logger.entries) == 1
    assert logger.entries[0].msg == "Missing reference"
