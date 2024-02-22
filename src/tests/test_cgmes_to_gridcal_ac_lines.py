from typing import Dict, List

import pytest

from GridCalEngine.Core import MultiCircuit
from GridCalEngine.IO.cim.cgmes import cgmes_enums
from GridCalEngine.IO.cim.cgmes.cgmes_circuit import CgmesCircuit
from GridCalEngine.IO.cim.cgmes.cgmes_to_gridcal import get_gcdev_generators, get_gcdev_ac_lines
import GridCalEngine.Core.Devices as gcdev
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.ac_line_segment import ACLineSegment
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.acdc_terminal import ACDCTerminal
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.base_voltage import BaseVoltage
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.connectivity_node import ConnectivityNode
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.current_limit import CurrentLimit
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.equipment_container import EquipmentContainer
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.generating_unit import GeneratingUnit
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.operational_limit_set import OperationalLimitSet
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.synchronous_machine import SynchronousMachine
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.terminal import Terminal
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.topological_node import TopologicalNode
from GridCalEngine.IO.cim.cim16.cim_devices import RegulatingControl
from GridCalEngine.data_logger import DataLogger

tn_test = TopologicalNode(rdfid="tn1")
cn_test = ConnectivityNode(rdfid="cn1")


def cgmes_object():
    circuit = CgmesCircuit()
    circuit.CurrentLimit_list = [CurrentLimit()]
    circuit.CurrentLimit_list[0].OperationalLimitSet = OperationalLimitSet()
    circuit.CurrentLimit_list[0].OperationalLimitSet.Terminal = ACDCTerminal()
    circuit.CurrentLimit_list[0].OperationalLimitSet.Terminal.ConductingEquipment = ACLineSegment()
    circuit.CurrentLimit_list[0].OperationalLimitSet.Terminal.ConductingEquipment.uuid = "branch_id"

    circuit.ACLineSegment_list = [ACLineSegment(rdfid="a"), ACLineSegment(rdfid="b")]

    return circuit


def calc_node_dict_object() -> Dict[str, gcdev.Bus]:
    d = dict()
    
    d["tn1"] = tn_test  # TODO ?
    d["tn2"] = tn_test
    return d


def cn_dict_object() -> Dict[str, gcdev.ConnectivityNode]:
    d = dict()
    d["cn1"] = [cn_test]  # TODO ?
    return d


def device_to_terminal_dict_object() -> Dict[str, List[Terminal]]:
    d = dict()
    t = Terminal("rdfterminal", "tpeterminal")

    t.TopologicalNode = tn_test
    t.ConnectivityNode = cn_test
    d['a'] = [t, t]
    d['b'] = [t]
    return d


generators_test_params = [(cgmes_object(), calc_node_dict_object(), cn_dict_object(),
                           device_to_terminal_dict_object(), 0)]


@pytest.mark.parametrize("cgmes_model,calc_node_dict,cn_dict,device_to_terminal_dict,s_base",
                         generators_test_params)
def test_ac_lines(cgmes_model, calc_node_dict, cn_dict, device_to_terminal_dict, s_base):
    logger = DataLogger()
    multi_circuit = MultiCircuit()
    tn_test.BaseVoltage = BaseVoltage()
    tn_test.BaseVoltage.nominalVoltage = 100
    get_gcdev_ac_lines(cgmes_model, multi_circuit, calc_node_dict, cn_dict, device_to_terminal_dict, logger, s_base)
