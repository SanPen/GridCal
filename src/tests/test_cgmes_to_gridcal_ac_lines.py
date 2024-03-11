from typing import Dict, List

import pytest

import GridCalEngine.Devices as gcdev
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.DataStructures import BusData
from GridCalEngine.IO.cim.cgmes.cgmes_circuit import CgmesCircuit
from GridCalEngine.IO.cim.cgmes.cgmes_to_gridcal import get_gcdev_ac_lines
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.ac_line_segment import ACLineSegment
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.acdc_terminal import ACDCTerminal
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.base_voltage import BaseVoltage
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.connectivity_node import ConnectivityNode
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.current_limit import CurrentLimit
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.operational_limit_set import OperationalLimitSet
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.terminal import Terminal
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.topological_node import TopologicalNode
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
    circuit.CurrentLimit_list[0].value = 10
    circuit.ACLineSegment_list = [ACLineSegment(rdfid="a"), ACLineSegment(rdfid="b")]

    circuit.ACLineSegment_list[0].BaseVoltage = BaseVoltage()
    circuit.ACLineSegment_list[0].BaseVoltage.nominalVoltage = 10
    circuit.ACLineSegment_list[0].r = 100
    circuit.ACLineSegment_list[0].x = 100
    circuit.ACLineSegment_list[0].gch = 100
    circuit.ACLineSegment_list[0].bch = 100
    circuit.ACLineSegment_list[0].r0 = 100
    circuit.ACLineSegment_list[0].x0 = 100
    circuit.ACLineSegment_list[0].g0ch = 100
    circuit.ACLineSegment_list[0].b0ch = 100
    return circuit


def calc_node_dict_object() -> Dict[str, gcdev.Bus]:
    d = dict()

    bus_data = BusData(1)
    bus_data.Vnom = 10
    d["tn1"] = bus_data
    d["tn2"] = bus_data

    return d


def cn_dict_object() -> Dict[str, gcdev.ConnectivityNode]:
    d = dict()
    d["cn1"] = [cn_test]
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
                           device_to_terminal_dict_object(), 10, 1000.0, 1000.0, 1e-20, 100.0, 10.0, 10.0, 1e-20, 10.0, 10,
                           10, 10.0, 10.0, 1e-20, 1e-20, 20, 20)]


@pytest.mark.parametrize(
    "cgmes_model,calc_node_dict,cn_dict,device_to_terminal_dict,s_base,expected_b,expected_b0,expected_b2,expected_cost,expected_r,expected_r0,expected_r2,expected_r_corrected,expected_vf,expected_vt,expected_x,expected_x0,expected_x2,expected_rate,expected_temp_base,expected_temp_oper",
    generators_test_params)
def test_ac_lines(cgmes_model, calc_node_dict, cn_dict, device_to_terminal_dict, s_base, expected_b, expected_b0,
                  expected_b2, expected_cost, expected_r, expected_r0,
                  expected_r2, expected_r_corrected, expected_vf, expected_vt, expected_x, expected_x0, expected_x2,
                  expected_rate, expected_temp_base, expected_temp_oper):
    logger = DataLogger()
    multi_circuit = MultiCircuit()
    tn_test.BaseVoltage = BaseVoltage()
    tn_test.BaseVoltage.nominalVoltage = 100
    get_gcdev_ac_lines(cgmes_model, multi_circuit, calc_node_dict, cn_dict, device_to_terminal_dict, logger, s_base)
    generated_ac_line = multi_circuit.lines[0]

    assert generated_ac_line.B == expected_b
    assert generated_ac_line.B0 == expected_b0
    assert generated_ac_line.B2 == expected_b2
    assert generated_ac_line.Cost == expected_cost
    assert generated_ac_line.R == expected_r
    assert generated_ac_line.R0 == expected_r0
    assert generated_ac_line.R2 == expected_r2
    assert generated_ac_line.R_corrected == expected_r_corrected
    assert generated_ac_line.Vf == expected_vf
    assert generated_ac_line.Vt == expected_vt
    assert generated_ac_line.X == expected_x
    assert generated_ac_line.X0 == expected_x0
    assert generated_ac_line.X2 == expected_x2
    assert generated_ac_line.rate == expected_rate
    assert generated_ac_line.temp_base == expected_temp_base
    assert generated_ac_line.temp_oper == expected_temp_oper
    assert len(logger.entries) == 1
    assert logger.entries[0].msg == 'Not exactly two terminals'
