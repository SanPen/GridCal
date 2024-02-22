from typing import Dict, List

import pytest

import GridCalEngine.Core.Devices as gcdev
from GridCalEngine.Core import MultiCircuit
from GridCalEngine.Core.DataStructures import BusData
from GridCalEngine.IO.cim.cgmes.cgmes_circuit import CgmesCircuit
from GridCalEngine.IO.cim.cgmes.cgmes_to_gridcal import get_gcdev_ac_transformers
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.connectivity_node import ConnectivityNode
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.power_transformer import PowerTransformer
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.power_transformer_end import PowerTransformerEnd
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.terminal import Terminal
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.topological_node import TopologicalNode
from GridCalEngine.data_logger import DataLogger

tn_test = TopologicalNode(rdfid="tn1")
cn_test = ConnectivityNode(rdfid="cn1")


def cgmes_object():
    circuit = CgmesCircuit()
    circuit.PowerTransformer_list = [PowerTransformer()]
    circuit.PowerTransformer_list[0].references_to_me["PowerTransformerEnd"] = [PowerTransformerEnd()]
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
                           device_to_terminal_dict_object(), 10)]


def test_ac_transformers_one_power_transofmer_end_log_error():
    logger = DataLogger()
    multi_circuit = MultiCircuit()

    cgmes = CgmesCircuit()
    cgmes.PowerTransformer_list = [PowerTransformer()]
    cgmes.PowerTransformer_list[0].references_to_me["PowerTransformerEnd"] = [PowerTransformerEnd()]
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

    cgmes = CgmesCircuit()
    cgmes.PowerTransformer_list = [PowerTransformer()]
    cgmes.PowerTransformer_list[0].references_to_me["PowerTransformerEnd"] = [PowerTransformerEnd(),
                                                                              PowerTransformerEnd()]
    get_gcdev_ac_transformers(cgmes, multi_circuit, calc_node_dict, cn_dict_object(), device_to_terminal_dict_object(),
                              logger,
                              10)
    assert len(logger.entries) == 2
    assert logger.entries[0].msg == 'No terminal for the device'
    assert logger.entries[1].msg == 'Not exactly two terminals'


@pytest.mark.parametrize(
    "cgmes_model,calc_node_dict,cn_dict,device_to_terminal_dict,s_base",
    generators_test_params)
def test_ac_transformers2(cgmes_model, calc_node_dict, cn_dict, device_to_terminal_dict, s_base):
    logger = DataLogger()
    multi_circuit = MultiCircuit()

    cgmes = CgmesCircuit()
    cgmes.PowerTransformer_list = [PowerTransformer()]
    cgmes.PowerTransformer_list[0].references_to_me["PowerTransformerEnd"] = [PowerTransformerEnd(),
                                                                              PowerTransformerEnd()]
    get_gcdev_ac_transformers(cgmes, multi_circuit, calc_node_dict, cn_dict, device_to_terminal_dict, logger,
                              s_base)
