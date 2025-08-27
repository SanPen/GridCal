# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Dict, List
import VeraGridEngine.Devices as gcdev
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.DataStructures import BusData
from VeraGridEngine.IO.cim.cgmes.cgmes_circuit import CgmesCircuit
from VeraGridEngine.IO.cim.cgmes.cgmes_to_veragrid import get_gcdev_ac_transformers, get_gcdev_device_to_terminal_dict
from VeraGridEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.connectivity_node import ConnectivityNode
from VeraGridEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.power_transformer import PowerTransformer
from VeraGridEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.power_transformer_end import PowerTransformerEnd
from VeraGridEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.terminal import Terminal
from VeraGridEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.topological_node import TopologicalNode
from VeraGridEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.base_voltage import BaseVoltage
from VeraGridEngine.data_logger import DataLogger
from VeraGridEngine.enumerations import CGMESVersions

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
    d["tn1"] = gcdev.Bus(Vnom=10)
    d["tn2"] = gcdev.Bus(Vnom=10)
    return d


def cn_dict_object() -> Dict[str, List[ConnectivityNode]]:
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


def test_ac_transformers_one_power_transformer_end_log_error():
    logger = DataLogger()
    multi_circuit = MultiCircuit()

    cgmes = CgmesCircuit(cgmes_version=CGMESVersions.v2_4_15)
    cgmes.cgmes_assets.PowerTransformer_list = [PowerTransformer()]
    power_transformer_end = PowerTransformerEnd()
    power_transformer_end.endNumber = 1
    cgmes.cgmes_assets.PowerTransformer_list[0].PowerTransformerEnd = [power_transformer_end]
    get_gcdev_ac_transformers(
        cgmes,
        multi_circuit,
        None,
        get_gcdev_device_to_terminal_dict(cgmes_model=cgmes, logger=logger),
        logger,
        0
    )
    assert len(logger.entries) > 0
    assert any(d.msg == 'Transformers with 1 windings not supported yet' for d in logger)


def test_ac_transformers_zero_calc_node_log_error():
    logger = DataLogger()
    multi_circuit = MultiCircuit()
    calc_node_dict = dict()
    bus_data = BusData(1)
    bus_data.Vnom = 10
    calc_node_dict["tn1"] = bus_data

    cgmes = CgmesCircuit(cgmes_version=CGMESVersions.v2_4_15)
    cgmes.cgmes_assets.PowerTransformer_list = [PowerTransformer()]
    power_transformer_end1 = PowerTransformerEnd()
    power_transformer_end1.endNumber = 1
    power_transformer_end2 = PowerTransformerEnd()
    power_transformer_end2.endNumber = 2
    cgmes.cgmes_assets.PowerTransformer_list[0].PowerTransformerEnd = [power_transformer_end1,
                                                                       power_transformer_end2]

    get_gcdev_ac_transformers(cgmes, multi_circuit, calc_node_dict,
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
    cgmes.cgmes_assets.PowerTransformer_list = [PowerTransformer("a")]
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

    power_transformer_end2 = PowerTransformerEnd()
    power_transformer_end2.ratedS = 1
    power_transformer_end2.ratedU = 2
    power_transformer_end2.r = 1
    power_transformer_end2.x = 1
    power_transformer_end2.g = 1
    power_transformer_end2.b = 1
    power_transformer_end2.r0 = 1
    power_transformer_end2.x0 = 1
    power_transformer_end2.g0 = 1
    power_transformer_end2.b0 = 1
    power_transformer_end2.BaseVoltage = BaseVoltage("a", "b")
    power_transformer_end2.BaseVoltage.nominalVoltage = 100
    power_transformer_end2.endNumber = 2
    cgmes.cgmes_assets.PowerTransformer_list[0].PowerTransformerEnd = [power_transformer_end,
                                                                       power_transformer_end2]
    get_gcdev_ac_transformers(cgmes, multi_circuit, calc_node_dict_object(),
                              device_to_terminal_dict_object_2_terminals(), logger,
                              10)
    generated_transtormer2w = multi_circuit.transformers2w[0]
    assert generated_transtormer2w.B == 80.0
    assert generated_transtormer2w.B0 == 80.0
    assert generated_transtormer2w.Cost == 100.0
    assert generated_transtormer2w.G == 80.0
    assert generated_transtormer2w.G0 == 80.0
    assert generated_transtormer2w.HV == 2
    assert generated_transtormer2w.I0 == 0
    assert generated_transtormer2w.LV == 2
    assert generated_transtormer2w.Pcu == 0
    assert generated_transtormer2w.Pfe == 0
    assert generated_transtormer2w.Pset == 0
    assert generated_transtormer2w.R == 5.0
    assert generated_transtormer2w.R0 == 5.0
    assert generated_transtormer2w.R_corrected == 5.0
    assert generated_transtormer2w.Sn == 1
    assert generated_transtormer2w.Vf == 10
    assert generated_transtormer2w.Vsc == 0.0
    assert generated_transtormer2w.Vt == 10
    assert generated_transtormer2w.X == 5.0
    assert generated_transtormer2w.X0 == 5.0
    assert generated_transtormer2w.alpha == 0.0033
    assert generated_transtormer2w.rate == 9999.0
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
    cgmes.cgmes_assets.PowerTransformer_list = [PowerTransformer("a")]
    power_transformer_end = PowerTransformerEnd()
    power_transformer_end2 = PowerTransformerEnd()
    power_transformer_end3 = PowerTransformerEnd()
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

    power_transformer_end2.ratedS = 1
    power_transformer_end2.ratedU = 2

    power_transformer_end2.r = 1
    power_transformer_end2.x = 1
    power_transformer_end2.g = 1
    power_transformer_end2.b = 1
    power_transformer_end2.r0 = 1
    power_transformer_end2.x0 = 1
    power_transformer_end2.g0 = 1
    power_transformer_end2.b0 = 1
    power_transformer_end2.endNumber = 2
    power_transformer_end2.BaseVoltage = BaseVoltage("a", "b")
    power_transformer_end2.BaseVoltage.nominalVoltage = 100

    power_transformer_end3.ratedS = 1
    power_transformer_end3.ratedU = 2

    power_transformer_end3.r = 1
    power_transformer_end3.x = 1
    power_transformer_end3.g = 1
    power_transformer_end3.b = 1
    power_transformer_end3.r0 = 1
    power_transformer_end3.x0 = 1
    power_transformer_end3.g0 = 1
    power_transformer_end3.b0 = 1
    power_transformer_end3.endNumber = 3
    power_transformer_end3.BaseVoltage = BaseVoltage("a", "b")
    power_transformer_end3.BaseVoltage.nominalVoltage = 100

    cgmes.cgmes_assets.PowerTransformer_list[0].PowerTransformerEnd = [power_transformer_end,
                                                                       power_transformer_end2,
                                                                       power_transformer_end3]
    get_gcdev_ac_transformers(cgmes, multi_circuit, calc_node_dict_object(),
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
    cgmes.cgmes_assets.PowerTransformer_list = [power_transformer]
    power_transformer_end = PowerTransformerEnd()
    power_transformer_end2 = PowerTransformerEnd()
    power_transformer_end3 = PowerTransformerEnd()
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

    power_transformer_end2.ratedS = 1
    power_transformer_end2.ratedU = 2

    power_transformer_end2.r = 1
    power_transformer_end2.x = 1
    power_transformer_end2.g = 1
    power_transformer_end2.b = 1
    power_transformer_end2.r0 = 1
    power_transformer_end2.x0 = 1
    power_transformer_end2.g0 = 1
    power_transformer_end2.b0 = 1
    power_transformer_end2.endNumber = 2
    power_transformer_end2.BaseVoltage = BaseVoltage("a", "b")
    power_transformer_end2.BaseVoltage.nominalVoltage = 100

    power_transformer_end3.ratedS = 1
    power_transformer_end3.ratedU = 2

    power_transformer_end3.r = 1
    power_transformer_end3.x = 1
    power_transformer_end3.g = 1
    power_transformer_end3.b = 1
    power_transformer_end3.r0 = 1
    power_transformer_end3.x0 = 1
    power_transformer_end3.g0 = 1
    power_transformer_end3.b0 = 1
    power_transformer_end3.endNumber = 3
    power_transformer_end3.BaseVoltage = BaseVoltage("a", "b")
    power_transformer_end3.BaseVoltage.nominalVoltage = 100

    cgmes.cgmes_assets.PowerTransformer_list[0].PowerTransformerEnd = [power_transformer_end,
                                                                       power_transformer_end2,
                                                                       power_transformer_end3]
    get_gcdev_ac_transformers(cgmes, multi_circuit, calc_node_dict_object(),
                              device_to_terminal_dict_object_3_terminals(), logger,
                              10)
    generated_transformers3w = multi_circuit.transformers3w[0]
    assert len(logger.entries) == 2
    assert generated_transformers3w.V1 == 2
    assert generated_transformers3w.V2 == 2
    assert generated_transformers3w.V3 == 2
    assert generated_transformers3w.r12 == 7.5
    assert generated_transformers3w.r23 == 7.5
    assert generated_transformers3w.r31 == 7.5
    assert generated_transformers3w.rate1 == 1
    assert generated_transformers3w.rate2 == 1
    assert generated_transformers3w.rate3 == 1
    assert generated_transformers3w.x == 0.0
    assert generated_transformers3w.x12 == 7.5
    assert generated_transformers3w.x23 == 7.5
    assert generated_transformers3w.x31 == 7.5
    assert generated_transformers3w.y == 0.0
