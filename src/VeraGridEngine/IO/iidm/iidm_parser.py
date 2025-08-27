# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from typing import List
import bz2
import xml.etree.ElementTree as ET
from VeraGridEngine.IO.iidm.devices.rtesubstation import RteSubstation
from VeraGridEngine.IO.iidm.devices.voltage_level import RteVoltageLevel
from VeraGridEngine.IO.iidm.devices.rte_area import RteArea
from VeraGridEngine.IO.iidm.devices.rte_bus import RteBus
from VeraGridEngine.IO.iidm.devices.generator import Generator
from VeraGridEngine.IO.iidm.devices.load import Load
from VeraGridEngine.IO.iidm.devices.line import Line
from VeraGridEngine.IO.iidm.devices.two_winding_transformer import TwoWindingsTransformer
from VeraGridEngine.IO.iidm.devices.rte_dangling_line import RteDanglingLine
from VeraGridEngine.IO.iidm.devices.shunt import Shunt
from VeraGridEngine.IO.iidm.devices.switch import Switch
from VeraGridEngine.IO.iidm.devices.rte_busbar_section import RteBusbarSection
from VeraGridEngine.IO.iidm.devices.static_var_compensator import StaticVarCompensator
from VeraGridEngine.IO.iidm.devices.iidm_circuit import IidmCircuit

"""
# See: 
    https://powsybl.readthedocs.io/projects/pypowsybl/en/latest/reference/network.html
    https://powsybl.readthedocs.io/projects/powsybl-core/en/stable/grid_model/network_subnetwork.html
"""

def strip_ns(tag: str) -> str:
    """

    :param tag:
    :return:
    """
    return tag.split("}")[-1] if "}" in tag else tag


def parse_xiidm_file(file_path: str) -> IidmCircuit:
    """
    Parse Xiidm to IidmCircuit
    :param file_path: xiidm file path
    :return: IidmCircuit
    """

    # Read as a text file (assuming UTF-8 encoding)
    if file_path.endswith(".bz2"):
        with bz2.open(file_path, mode='rt', encoding='utf-8') as file:
            tree = ET.parse(file)
    else:
        tree = ET.parse(file_path)

    root = tree.getroot()
    circuit = IidmCircuit()

    for elem in root.iter():
        tag = strip_ns(elem.tag)

        if tag == "substation":
            circuit.substations.append(RteSubstation(
                id=elem.attrib.get("id", ""),
                country=elem.attrib.get("country", ""),
                tso=elem.attrib.get("tso", ""),
                geographicalTags=elem.attrib.get("geographicalTags", "")
            ))

        elif tag == "voltageLevel":
            circuit.voltage_levels.append(RteVoltageLevel(
                _id=elem.attrib.get("id", ""),
                name=elem.attrib.get("name", ""),
                nominalV=float(elem.attrib.get("nominalV", 0)),
                topologyKind=elem.attrib.get("topologyKind", "")
            ))

        elif tag == "area":
            circuit.areas.append(RteArea(
                _id=elem.attrib.get("id", ""),
                name=elem.attrib.get("Name", ""),
                area_type=elem.attrib.get("AreaType", ""),
                interchange_target=float(elem.attrib.get("interchangeTarget", 0)),
            ))

        elif tag == "bus":
            circuit.buses.append(RteBus(
                _id=elem.attrib.get("id", ""),
                area_number=elem.attrib.get("areaNumber", -1),
                status=elem.attrib.get("status", ""),
                nodes=[int(e) for e in elem.attrib.get("nodes", []).split(",")],
            ))

        elif tag == "generator":
            circuit.generators.append(Generator(
                id=elem.attrib.get("id", ""),
                bus=elem.attrib.get("bus", ""),
                targetP=float(elem.attrib.get("targetP", 0)),
                targetQ=float(elem.attrib.get("targetQ", 0)),
                targetV=float(elem.attrib.get("targetV", 0))
            ))

        elif tag == "load":
            circuit.loads.append(Load(
                id=elem.attrib.get("id", ""),
                bus=elem.attrib.get("bus", ""),
                p0=float(elem.attrib.get("p0", 0)),
                q0=float(elem.attrib.get("q0", 0))
            ))

        elif tag == "line":
            circuit.lines.append(Line(
                id=elem.attrib.get("id", ""),
                voltageLevelId1=elem.attrib.get("voltageLevelId1", ""),
                bus1=elem.attrib.get("bus1", ""),
                voltageLevelId2=elem.attrib.get("voltageLevelId2", ""),
                bus2=elem.attrib.get("bus2", ""),
                r=float(elem.attrib.get("r", 0)),
                x=float(elem.attrib.get("x", 0)),
                g1=float(elem.attrib.get("g1", 0)),
                b1=float(elem.attrib.get("b1", 0)),
                g2=float(elem.attrib.get("g2", 0)),
                b2=float(elem.attrib.get("b2", 0))
            ))

        elif tag == "twoWindingsTransformer":
            circuit.transformers.append(TwoWindingsTransformer(
                id=elem.attrib.get("id", ""),
                voltageLevelId1=elem.attrib.get("voltageLevelId1", ""),
                bus1=elem.attrib.get("bus1", ""),
                voltageLevelId2=elem.attrib.get("voltageLevelId2", ""),
                bus2=elem.attrib.get("bus2", ""),
                r=float(elem.attrib.get("r", 0)),
                x=float(elem.attrib.get("x", 0)),
                g=float(elem.attrib.get("g", 0)),
                b=float(elem.attrib.get("b", 0)),
                ratedU1=float(elem.attrib.get("ratedU1", 0)),
                ratedU2=float(elem.attrib.get("ratedU2", 0))
            ))

        elif tag == "danglingLine":
            circuit.dangling_lines.append(RteDanglingLine(
                _id=elem.attrib.get("id", ""),
                bus=elem.attrib.get("bus", ""),
                p0=float(elem.attrib.get("p0", 0)),
                q0=float(elem.attrib.get("q0", 0)),
                u0=float(elem.attrib.get("u0", 0)),
                r=float(elem.attrib.get("r", 0)),
                x=float(elem.attrib.get("x", 0)),
                g=float(elem.attrib.get("g", 0)),
                b=float(elem.attrib.get("b", 0))
            ))

        elif tag == "shunt":
            circuit.shunts.append(Shunt(
                id=elem.attrib.get("id", ""),
                bus=elem.attrib.get("bus", ""),
                g=float(elem.attrib.get("g", 0)),
                b=float(elem.attrib.get("b", 0))
            ))

        elif tag == "switch":
            circuit.switches.append(Switch(
                id=elem.attrib.get("id", ""),
                bus1=elem.attrib.get("bus1", ""),
                bus2=elem.attrib.get("bus2", ""),
                kind=elem.attrib.get("kind", ""),
                open=elem.attrib.get("open", "false").lower() == "true",
                retained=elem.attrib.get("retained", "false").lower() == "true"
            ))

        elif tag == "busbarSection":
            circuit.busbar_sections.append(RteBusbarSection(
                _id=elem.attrib.get("id", "")
            ))

        elif tag == "staticVarCompensator":
            circuit.svcs.append(StaticVarCompensator(
                id=elem.attrib.get("id", ""),
                bus=elem.attrib.get("bus", ""),
                bMin=float(elem.attrib.get("bMin", 0)),
                bMax=float(elem.attrib.get("bMax", 0)),
                voltageSetPoint=float(elem.attrib.get("voltageSetPoint", 0))
            ))

    return circuit


if __name__ == "__main__":



    # fname = "/home/santi/Documentos/Git/GitHub/RTE7000/2021/01/01/recollement-auto-20210101-0000-enrichi.xiidm"
    fname = "/home/santi/Documentos/Git/GitHub/RTE7000/2021/01/01/recollement-auto-20210101-0000-enrichi.xiidm.bz2"

    # import pypowsybl as pp
    # grid = pp.network.load(fname)
    # res = pp.loadflow.run_dc(grid, pp.loadflow.Parameters(distributed_slack=False))

    iidm_circuit = parse_xiidm_file(fname)

    print()

