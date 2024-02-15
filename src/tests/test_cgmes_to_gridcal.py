from typing import Dict, List

import pytest

from GridCalEngine.Core import MultiCircuit
from GridCalEngine.IO.cim.cgmes.cgmes_circuit import CgmesCircuit
from GridCalEngine.IO.cim.cgmes.cgmes_to_gridcal import get_gcdev_generators
import GridCalEngine.Core.Devices as gcdev
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.terminal import Terminal
from GridCalEngine.data_logger import DataLogger


def cgmes_object():
    circuit = CgmesCircuit()
    circuit.SynchronousMachine_list = []
    return circuit


def multicircuit_object():
    circuit = MultiCircuit()
    return circuit


def calc_node_dict_object() -> Dict[str, gcdev.Bus]:
    d = dict(k='v')
    return d


def cn_dict_object() -> Dict[str, gcdev.ConnectivityNode]:
    d = dict(k='v')
    return d


def device_to_terminal_dict_object() -> Dict[str, List[Terminal]]:
    d = dict(k='v')
    return d


generators_test_params = [(cgmes_object(), multicircuit_object(), calc_node_dict_object(), cn_dict_object(),
                           device_to_terminal_dict_object())]


@pytest.mark.parametrize("cgmes_model,gcdev_model,calc_node_dict,cn_dict,device_to_terminal_dict",
                         generators_test_params)
def test_get_gcdev_generators(cgmes_model, gcdev_model, calc_node_dict, cn_dict, device_to_terminal_dict):
    logger = DataLogger()
    get_gcdev_generators(cgmes_model, gcdev_model, calc_node_dict, cn_dict, device_to_terminal_dict, logger)
