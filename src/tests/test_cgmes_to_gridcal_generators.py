from typing import Dict, List

import pytest

from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.IO.cim.cgmes import cgmes_enums
from GridCalEngine.IO.cim.cgmes.cgmes_circuit import CgmesCircuit
from GridCalEngine.IO.cim.cgmes.cgmes_to_gridcal import get_gcdev_generators
import GridCalEngine.Devices as gcdev
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.base_voltage import BaseVoltage
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.connectivity_node import ConnectivityNode
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.equipment_container import EquipmentContainer
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.generating_unit import GeneratingUnit
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.synchronous_machine import SynchronousMachine
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.terminal import Terminal
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.topological_node import TopologicalNode
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.regulating_control import RegulatingControl
from GridCalEngine.data_logger import DataLogger
from GridCalEngine.enumerations import CGMESVersions

tn_test = TopologicalNode()
cn_test = ConnectivityNode()


def cgmes_object(p):
    circuit = CgmesCircuit(cgmes_version=CGMESVersions.v2_4_15)
    generator = SynchronousMachine("sm_rdfid", "tpe")
    generator.GeneratingUnit = GeneratingUnit()
    regulating_control = RegulatingControl("regulating_rdfid", "regulating_tpe")
    regulating_control.mode = cgmes_enums.RegulatingControlModeKind.voltage
    regulating_control.targetValue = 5000.0
    generator.RegulatingControl = regulating_control
    generator.RegulatingControl.Terminal = Terminal()
    generator.RegulatingControl.Terminal.TopologicalNode = TopologicalNode()
    generator.RegulatingControl.Terminal.TopologicalNode.BaseVoltage = BaseVoltage()
    generator.RegulatingControl.Terminal.TopologicalNode.BaseVoltage.nominalVoltage = 3

    generator.EquipmentContainer = EquipmentContainer("equipmentcontainer_rdfid", "VoltageLevel")
    generator.EquipmentContainer.BaseVoltage = BaseVoltage()
    generator.EquipmentContainer.BaseVoltage.nominalVoltage = 2.0

    circuit.SynchronousMachine_list = [generator]

    generator.GeneratingUnit = GeneratingUnit("generating_rdfid")
    generator.description = "test description"
    generator.name = "test name"
    generator.ratedS = 10
    generator.p = p
    generator.q = 3
    generator.GeneratingUnit.minOperatingP = 30
    generator.GeneratingUnit.maxOperatingP = 40
    generator.maxQ = 50
    generator.minQ = 60

    return circuit


def calc_node_dict_object() -> Dict[str, gcdev.Bus]:
    d = dict()
    d[tn_test] = tn_test  # TODO ?
    return d


def cn_dict_object() -> Dict[str, gcdev.ConnectivityNode]:
    d = dict()
    d[cn_test] = cn_test  # TODO ?
    return d


def device_to_terminal_dict_object() -> Dict[str, List[Terminal]]:
    d = dict()
    t = Terminal("rdfterminal", "tpeterminal")

    t.TopologicalNode = tn_test
    t.TopologicalNode.BaseVoltage = BaseVoltage('b', 'v')
    t.TopologicalNode.BaseVoltage.nominalVoltage = 100
    t.ConnectivityNode = cn_test
    d['smrdfid'] = [t]
    return d


generators_test_params = [(cgmes_object(2), calc_node_dict_object(), cn_dict_object(),
                           device_to_terminal_dict_object(), 0.55),
                          (cgmes_object(0), calc_node_dict_object(), cn_dict_object(),
                           device_to_terminal_dict_object(), 0.8)]


@pytest.mark.parametrize("cgmes_model,calc_node_dict,cn_dict,device_to_terminal_dict,expected_power_factor",
                         generators_test_params)
def test_get_gcdev_generators(cgmes_model, calc_node_dict, cn_dict, device_to_terminal_dict, expected_power_factor):
    logger = DataLogger()
    multi_circuit = MultiCircuit()
    get_gcdev_generators(cgmes_model, multi_circuit, calc_node_dict, cn_dict, device_to_terminal_dict, logger)
    created_generator = multi_circuit.generators[0]
    cgmes_syncronous_machine = cgmes_model.SynchronousMachine_list[0]
    assert created_generator.idtag == cgmes_syncronous_machine.uuid
    assert created_generator.code == cgmes_syncronous_machine.description
    assert created_generator.name == cgmes_syncronous_machine.name
    assert created_generator.active
    assert created_generator.Snom == cgmes_syncronous_machine.ratedS
    assert created_generator.P == -cgmes_syncronous_machine.p
    assert created_generator.Pmin == cgmes_syncronous_machine.GeneratingUnit.minOperatingP
    assert created_generator.Pmax == cgmes_syncronous_machine.GeneratingUnit.maxOperatingP
    assert created_generator.Qmax == cgmes_syncronous_machine.maxQ
    assert created_generator.Qmin == cgmes_syncronous_machine.minQ
    assert created_generator.Pf == pytest.approx(expected_power_factor, abs=0.01)


def test_get_gcdev_generators_zero_terminals_log_error():
    device_terminal_dict = dict()
    device_terminal_dict[tn_test] = tn_test
    logger = DataLogger()
    multi_circuit = MultiCircuit()
    cgmes = cgmes_object(p=2)
    get_gcdev_generators(cgmes, multi_circuit, calc_node_dict_object(), cn_dict_object(),
                         device_terminal_dict, logger)
    assert len(logger.entries) == 2
    assert logger.entries[0].msg == 'No terminal for the device'
    assert logger.entries[1].msg == 'Not exactly one terminal'


def test_get_gcdev_generators_generating_unit_is_none_log_error():
    logger = DataLogger()
    multi_circuit = MultiCircuit()
    cgmes = cgmes_object(p=2)
    cgmes.SynchronousMachine_list[0].GeneratingUnit = None
    get_gcdev_generators(cgmes, multi_circuit, calc_node_dict_object(), cn_dict_object(),
                         device_to_terminal_dict_object(), logger)
    assert len(logger.entries) == 1
    assert logger.entries[0].msg == 'SynchronousMachine has no generating unit'


def test_get_gcdev_generators_regulating_controls_none_log_warning():
    logger = DataLogger()
    multi_circuit = MultiCircuit()
    cgmes = cgmes_object(p=2)
    cgmes.SynchronousMachine_list[0].RegulatingControl = None
    get_gcdev_generators(cgmes, multi_circuit, calc_node_dict_object(), cn_dict_object(),
                         device_to_terminal_dict_object(), logger)
    assert len(logger.entries) == 1
    assert logger.entries[0].msg == 'RegulatingCondEq has no control'


def test_get_gcdev_generators_regulating_control_mode_kind_not_voltage_log_warning():
    logger = DataLogger()
    multi_circuit = MultiCircuit()
    cgmes = cgmes_object(p=2)
    cgmes.SynchronousMachine_list[0].RegulatingControl.mode = "aaa"
    get_gcdev_generators(cgmes, multi_circuit, calc_node_dict_object(), cn_dict_object(),
                         device_to_terminal_dict_object(), logger)
    assert len(logger.entries) == 1
    assert logger.entries[0].msg == 'RegulatingCondEq has control, but not voltage'
