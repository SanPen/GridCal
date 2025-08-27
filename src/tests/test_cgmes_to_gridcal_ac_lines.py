# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Dict, List, Any

import pytest

import VeraGridEngine.Devices as gcdev
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.IO.cim.cgmes.cgmes_circuit import CgmesCircuit
from VeraGridEngine.IO.cim.cgmes.cgmes_to_veragrid import get_gcdev_ac_lines
from VeraGridEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.ac_line_segment import ACLineSegment
from VeraGridEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.base_voltage import BaseVoltage
from VeraGridEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.connectivity_node import ConnectivityNode
from VeraGridEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.current_limit import CurrentLimit
from VeraGridEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.operational_limit_set import OperationalLimitSet
from VeraGridEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.operational_limit_type import OperationalLimitType
from VeraGridEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.terminal import Terminal
from VeraGridEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.topological_node import TopologicalNode
from VeraGridEngine.data_logger import DataLogger
from VeraGridEngine.enumerations import CGMESVersions

tn_test = TopologicalNode(rdfid="tn1")
cn_test = ConnectivityNode(rdfid="cn1")


def cgmes_object():
    circuit = CgmesCircuit(cgmes_version=CGMESVersions.v2_4_15)
    cl = CurrentLimit()
    cl.OperationalLimitSet = OperationalLimitSet()
    cl.OperationalLimitSet.Terminal = Terminal()
    cl.OperationalLimitSet.Terminal.TopologicalNode = tn_test
    cl.OperationalLimitSet.Terminal.ConductingEquipment = ACLineSegment()
    cl.OperationalLimitSet.Terminal.ConductingEquipment.uuid = "branch_id"
    cl.OperationalLimitType = OperationalLimitType()    # empty
    cl.value = 10
    circuit.add(cl)

    acl = ACLineSegment(rdfid="a")
    acl.BaseVoltage = BaseVoltage()
    acl.BaseVoltage.nominalVoltage = 10
    acl.r = 100
    acl.x = 100
    acl.gch = 100
    acl.bch = 100
    acl.r0 = 100
    acl.x0 = 100
    acl.g0ch = 100
    acl.b0ch = 100
    circuit.add(acl)
    return circuit


def calc_node_dict_object() -> Dict[str, gcdev.Bus]:
    d = dict()

    d["tn1"] = gcdev.Bus(Vnom=10)
    d["tn2"] = gcdev.Bus(Vnom=10)

    return d


def cn_dict_object() -> dict[str, list[ConnectivityNode | Any]]:
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


ac_line_test_params = [
    (cgmes_object(), calc_node_dict_object(), cn_dict_object(), device_to_terminal_dict_object(),
     10, 1000.0, 1000.0, 1e-20, 100.0,
     10.0, 10.0, 1e-20, 10.0,
     10, 10, 10.0, 10.0, 1e-20,
     9999.0, 20, 20)
]


@pytest.mark.parametrize(
    "cgmes_model,calc_node_dict,cn_dict,device_to_terminal_dict,"
    "s_base,expected_b,expected_b0,expected_b2,expected_cost,"
    "expected_r,expected_r0,expected_r2,expected_r_corrected,"
    "expected_vf,expected_vt,expected_x,expected_x0,expected_x2,"
    "expected_rate,expected_temp_base,expected_temp_oper",
    ac_line_test_params)
def test_ac_lines(cgmes_model, calc_node_dict, cn_dict, device_to_terminal_dict,
                  s_base, expected_b, expected_b0, expected_b2, expected_cost,
                  expected_r, expected_r0, expected_r2, expected_r_corrected,
                  expected_vf, expected_vt, expected_x, expected_x0, expected_x2,
                  expected_rate, expected_temp_base, expected_temp_oper):

    logger = DataLogger()
    multi_circuit = MultiCircuit()
    tn_test.BaseVoltage = BaseVoltage()
    tn_test.BaseVoltage.nominalVoltage = 100
    get_gcdev_ac_lines(cgmes_model=cgmes_model,
                       gcdev_model=multi_circuit,
                       bus_dict=calc_node_dict,
                       device_to_terminal_dict=device_to_terminal_dict,
                       logger=logger,
                       Sbase=s_base)
    generated_ac_line = multi_circuit.lines[0]

    assert generated_ac_line.B == expected_b
    assert generated_ac_line.B0 == expected_b0
    assert generated_ac_line.Cost == expected_cost
    assert generated_ac_line.R == expected_r
    assert generated_ac_line.R0 == expected_r0
    assert generated_ac_line.R_corrected == expected_r_corrected
    assert generated_ac_line.Vf == expected_vf
    assert generated_ac_line.Vt == expected_vt
    assert generated_ac_line.X == expected_x
    assert generated_ac_line.X0 == expected_x0
    assert generated_ac_line.rate == expected_rate
    assert generated_ac_line.temp_base == expected_temp_base
    assert generated_ac_line.temp_oper == expected_temp_oper
    # assert len(logger.entries) == 1
    # assert logger.entries[0].msg == 'Not exactly two terminals'
