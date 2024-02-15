from typing import Dict, List

import pytest

from GridCalEngine.Core import MultiCircuit
from GridCalEngine.IO.cim.cgmes import cgmes_enums
from GridCalEngine.IO.cim.cgmes.cgmes_circuit import CgmesCircuit
from GridCalEngine.IO.cim.cgmes.cgmes_to_gridcal import get_gcdev_generators
import GridCalEngine.Core.Devices as gcdev
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.base_voltage import BaseVoltage
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.connectivity_node import ConnectivityNode
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.equipment_container import EquipmentContainer
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.generating_unit import GeneratingUnit
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.synchronous_machine import SynchronousMachine
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.terminal import Terminal
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.topological_node import TopologicalNode
from GridCalEngine.IO.cim.cim16.cim_devices import RegulatingControl
from GridCalEngine.data_logger import DataLogger

tn_test = TopologicalNode()
cn_test = ConnectivityNode()


def cgmes_object():
    circuit = CgmesCircuit()
    generator = SynchronousMachine("sm_rdfid","tpe")
    generator.GeneratingUnit = GeneratingUnit()
    regulating_control = RegulatingControl("regulating_rdfid", "regulating_tpe")
    regulating_control.mode = cgmes_enums.RegulatingControlModeKind.voltage
    regulating_control.targetValue = 3.0
    generator.RegulatingControl = regulating_control
    generator.RegulatingControl.Terminal = Terminal()

    generator.EquipmentContainer = EquipmentContainer("equipmentcontainer_rdfid","VoltageLevel")
    generator.EquipmentContainer.BaseVoltage = BaseVoltage()
    generator.EquipmentContainer.BaseVoltage.nominalVoltage = 2.0

    circuit.SynchronousMachine_list = [generator]
    return circuit


def multicircuit_object():
    circuit = MultiCircuit()
    return circuit


def calc_node_dict_object() -> Dict[str, gcdev.Bus]:
    d = dict()
    d[tn_test] = tn_test #TODO ?
    return d


def cn_dict_object() -> Dict[str, gcdev.ConnectivityNode]:
    d = dict()
    d[cn_test] = cn_test  # TODO ?
    return d


def device_to_terminal_dict_object() -> Dict[str, List[Terminal]]:
    d = dict()
    t = Terminal("rdfterminal","tpeterminal")


    t.TopologicalNode = tn_test
    t.ConnectivityNode = cn_test
    d['smrdfid'] = [t]
    return d


generators_test_params = [(cgmes_object(), multicircuit_object(), calc_node_dict_object(), cn_dict_object(),
                           device_to_terminal_dict_object())]


@pytest.mark.parametrize("cgmes_model,gcdev_model,calc_node_dict,cn_dict,device_to_terminal_dict",
                         generators_test_params)
def test_get_gcdev_generators(cgmes_model, gcdev_model, calc_node_dict, cn_dict, device_to_terminal_dict):
    logger = DataLogger()
    get_gcdev_generators(cgmes_model, gcdev_model, calc_node_dict, cn_dict, device_to_terminal_dict, logger)
