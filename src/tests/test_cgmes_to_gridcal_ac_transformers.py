from typing import Dict, List

import pytest

import GridCalEngine.Devices as gcdev
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.DataStructures import BusData
from GridCalEngine.IO.cim.cgmes.cgmes_circuit import CgmesCircuit
from GridCalEngine.IO.cim.cgmes.cgmes_to_gridcal import get_gcdev_ac_transformers
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.connectivity_node import ConnectivityNode
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.power_transformer import PowerTransformer
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.power_transformer_end import PowerTransformerEnd
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.terminal import Terminal
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.topological_node import TopologicalNode
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.base_voltage import BaseVoltage
from GridCalEngine.data_logger import DataLogger
from GridCalEngine.enumerations import CGMESVersions

tn_test = TopologicalNode(rdfid="tn1")
cn_test = ConnectivityNode(rdfid="cn1")


def cgmes_object():
    circuit = CgmesCircuit(cgmes_version=CGMESVersions.v2_4_15)
    circuit.PowerTransformer_list = [PowerTransformer()]
    ptend = PowerTransformerEnd()
    ptend.BaseVoltage = BaseVoltage("a", "b")
    ptend.BaseVoltage.nominalVoltage = 100
    ptend.endNumber = 1

    circuit.PowerTransformer_list[0].references_to_me["PowerTransformerEnd"] = [ptend, ptend]
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


def device_to_terminal_dict_object_2_terminals() -> Dict[str, List[Terminal]]:
    d = dict()
    t = Terminal("rdfterminal", "tpeterminal")

    t.TopologicalNode = tn_test
    t.ConnectivityNode = cn_test
    d['a'] = [t, t]
    d['b'] = [t]
    return d


def device_to_terminal_dict_object_3_terminals() -> Dict[str, List[Terminal]]:
    d = dict()
    t = Terminal("rdfterminal", "tpeterminal")

    t.TopologicalNode = tn_test
    t.ConnectivityNode = cn_test
    d['a'] = [t, t, t]
    return d


def test_ac_transformers_one_power_transofmer_end_log_error():
    logger = DataLogger()
    multi_circuit = MultiCircuit()

    cgmes = CgmesCircuit(cgmes_version=CGMESVersions.v2_4_15)
    cgmes.PowerTransformer_list = [PowerTransformer()]
    power_transformer_end = PowerTransformerEnd()
    power_transformer_end.endNumber = 1
    cgmes.PowerTransformer_list[0].references_to_me["PowerTransformerEnd"] = [power_transformer_end]
    get_gcdev_ac_transformers(cgmes, multi_circuit, None, None, None, logger,
                              0)
    assert len(logger.entries) == 1
    assert logger.entries[0].msg == 'Transformers with 1 windings not supported yet'


def test_ac_transformers_zero_calc_node_log_error():
    logger = DataLogger()
    multi_circuit = MultiCircuit()
    calc_node_dict = dict()
    bus_data = BusData(1)
    bus_data.Vnom = 10
    calc_node_dict["tn1"] = bus_data

    cgmes = CgmesCircuit(cgmes_version=CGMESVersions.v2_4_15)
    cgmes.PowerTransformer_list = [PowerTransformer()]
    power_transformer_end = PowerTransformerEnd()
    power_transformer_end.endNumber = 1
    cgmes.PowerTransformer_list[0].references_to_me["PowerTransformerEnd"] = [power_transformer_end,
                                                                              power_transformer_end]

    get_gcdev_ac_transformers(cgmes, multi_circuit, calc_node_dict, cn_dict_object(),
                              device_to_terminal_dict_object_2_terminals(),
                              logger,
                              10)
    assert len(logger.entries) == 2
    assert logger.entries[0].msg == 'No terminal for the device'
    assert logger.entries[1].msg == 'Not exactly two terminals'


def test_ac_transformers2w():
    logger = DataLogger()
    multi_circuit = MultiCircuit()

    cgmes = CgmesCircuit(cgmes_version=CGMESVersions.v2_4_15)
    cgmes.PowerTransformer_list = [PowerTransformer("a")]
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
    power_transformer_end.BaseVoltage = BaseVoltage("a", "b")
    power_transformer_end.BaseVoltage.nominalVoltage = 100
    cgmes.PowerTransformer_list[0].references_to_me["PowerTransformerEnd"] = [power_transformer_end,
                                                                              power_transformer_end]
    get_gcdev_ac_transformers(cgmes, multi_circuit, calc_node_dict_object(), cn_dict_object(),
                              device_to_terminal_dict_object_2_terminals(), logger,
                              10)
    generated_transtormer2w = multi_circuit.transformers2w[0]
    assert generated_transtormer2w.B == 80.0
    assert generated_transtormer2w.B0 == 80.0
    assert generated_transtormer2w.B2 == 1e-20
    assert generated_transtormer2w.Cost == 100.0
    assert generated_transtormer2w.G == 80.0
    assert generated_transtormer2w.G0 == 80.0
    assert generated_transtormer2w.G2 == 1e-20
    assert generated_transtormer2w.HV == 100
    assert generated_transtormer2w.I0 == 0
    assert generated_transtormer2w.LV == 100
    assert generated_transtormer2w.Pcu == 0
    assert generated_transtormer2w.Pfe == 0
    assert generated_transtormer2w.Pset == 0
    assert generated_transtormer2w.R == 5.0
    assert generated_transtormer2w.R0 == 5.0
    assert generated_transtormer2w.R2 == 1e-20
    assert generated_transtormer2w.R_corrected == 5.0
    assert generated_transtormer2w.Sn == 0.001
    assert generated_transtormer2w.Vf == 10
    assert generated_transtormer2w.Vsc == 0.0
    assert generated_transtormer2w.Vt == 10
    assert generated_transtormer2w.X == 5.0
    assert generated_transtormer2w.X0 == 5.0
    assert generated_transtormer2w.X2 == 1e-20
    assert generated_transtormer2w.alpha == 0.0033
    assert generated_transtormer2w.rate == 1
    assert generated_transtormer2w.tap_module == 1.0
    assert generated_transtormer2w.tap_module_max == 1.2
    assert generated_transtormer2w.tap_module_min == 0.5
    assert generated_transtormer2w.tap_phase == 0
    assert generated_transtormer2w.tap_phase_max == 6.28
    assert generated_transtormer2w.tap_phase_min == -6.28
    assert generated_transtormer2w.temp_base == 20
    assert generated_transtormer2w.temp_oper == 20


def test_ac_transformers3w_only_two_terminals_log_error():
    logger = DataLogger()
    multi_circuit = MultiCircuit()

    cgmes = CgmesCircuit(cgmes_version=CGMESVersions.v2_4_15)
    cgmes.PowerTransformer_list = [PowerTransformer("a")]
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
    power_transformer_end.BaseVoltage = BaseVoltage("a", "b")
    power_transformer_end.BaseVoltage.nominalVoltage = 100
    cgmes.PowerTransformer_list[0].references_to_me["PowerTransformerEnd"] = [power_transformer_end,
                                                                              power_transformer_end,
                                                                              power_transformer_end]
    get_gcdev_ac_transformers(cgmes, multi_circuit, calc_node_dict_object(), cn_dict_object(),
                              device_to_terminal_dict_object_2_terminals(), logger,
                              10)
    assert len(logger.entries) == 1
    assert logger.entries[0].msg == 'Not exactly three terminals'


def test_ac_transformers3w():
    logger = DataLogger()
    multi_circuit = MultiCircuit()

    cgmes = CgmesCircuit(cgmes_version=CGMESVersions.v2_4_15)
    power_transformer = PowerTransformer("a")
    power_transformer.name = "pt_name"
    cgmes.PowerTransformer_list = [power_transformer]
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
    power_transformer_end.BaseVoltage = BaseVoltage("a", "b")
    power_transformer_end.BaseVoltage.nominalVoltage = 100
    power_transformer_end.endNumber = 1
    cgmes.PowerTransformer_list[0].references_to_me["PowerTransformerEnd"] = [power_transformer_end,
                                                                              power_transformer_end,
                                                                              power_transformer_end]
    get_gcdev_ac_transformers(cgmes, multi_circuit, calc_node_dict_object(), cn_dict_object(),
                              device_to_terminal_dict_object_3_terminals(), logger,
                              10)
    generated_transformers3w = multi_circuit.transformers3w[0]
    assert len(logger.entries) == 0
    assert generated_transformers3w.V1 == 100
    assert generated_transformers3w.V2 == 100
    assert generated_transformers3w.V3 == 100
    assert generated_transformers3w.r12 == 5.0
    assert generated_transformers3w.r23 == 5.0
    assert generated_transformers3w.r31 == 5.0
    assert generated_transformers3w.rate12 == 1
    assert generated_transformers3w.rate23 == 1
    assert generated_transformers3w.rate31 == 1
    assert generated_transformers3w.x == 0.0
    assert generated_transformers3w.x12 == 5.0
    assert generated_transformers3w.x23 == 5.0
    assert generated_transformers3w.x31 == 5.0
    assert generated_transformers3w.y == 0.0
