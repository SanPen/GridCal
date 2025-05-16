# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from typing import List
import xml.etree.ElementTree as ET
from GridCalEngine.IO.iidm.devices.substation import Substation
from GridCalEngine.IO.iidm.devices.voltage_level import VoltageLevel
from GridCalEngine.IO.iidm.devices.bus import Bus
from GridCalEngine.IO.iidm.devices.generator import Generator
from GridCalEngine.IO.iidm.devices.load import Load
from GridCalEngine.IO.iidm.devices.line import Line
from GridCalEngine.IO.iidm.devices.two_winding_transformer import TwoWindingsTransformer
from GridCalEngine.IO.iidm.devices.dangling_line import DanglingLine
from GridCalEngine.IO.iidm.devices.shunt import Shunt
from GridCalEngine.IO.iidm.devices.switch import Switch
from GridCalEngine.IO.iidm.devices.busbar_section import BusbarSection
from GridCalEngine.IO.iidm.devices.static_var_compensator import StaticVarCompensator
from GridCalEngine.IO.iidm.devices.iidm_circuit import IidmCircuit


def strip_ns(tag: str) -> str:
    """

    :param tag:
    :return:
    """
    return tag.split("}")[-1] if "}" in tag else tag


def parse_xiidm_file_to_circuit_non_recursive(file_path: str) -> IidmCircuit:
    tree = ET.parse(file_path)
    root = tree.getroot()
    circuit = IidmCircuit()

    for elem in root.iter():
        tag = strip_ns(elem.tag)

        if tag == "substation":
            circuit.substations.append(Substation(
                id=elem.attrib.get("id", ""),
                country=elem.attrib.get("country", ""),
                tso=elem.attrib.get("tso", ""),
                geographicalTags=elem.attrib.get("geographicalTags", "")
            ))

        elif tag == "voltageLevel":
            circuit.voltage_levels.append(VoltageLevel(
                id=elem.attrib.get("id", ""),
                nominalV=float(elem.attrib.get("nominalV", 0)),
                topologyKind=elem.attrib.get("topologyKind", "")
            ))

        elif tag == "bus":
            circuit.buses.append(Bus(id=elem.attrib.get("id", "")))

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
            circuit.dangling_lines.append(DanglingLine(
                id=elem.attrib.get("id", ""),
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
            circuit.busbar_sections.append(BusbarSection(
                id=elem.attrib.get("id", "")
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

    # See: https://powsybl.readthedocs.io/projects/pypowsybl/en/latest/reference/network.html

    fname = "/home/santi/Documentos/Git/GitHub/RTE7000/2021/01/01/recollement-auto-20210101-0000-enrichi.xiidm"
    # parse_xiidm_file_to_circuit_non_recursive(fname)
    import pypowsybl as pp

    grid = pp.network.load(fname)

    res = pp.loadflow.run_dc(grid, pp.loadflow.Parameters(distributed_slack=False))

    print()

