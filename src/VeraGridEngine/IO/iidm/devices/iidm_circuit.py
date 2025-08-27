# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from typing import List
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

class IidmCircuit:
    def __init__(self):
        self.substations: List[RteSubstation] = []
        self.voltage_levels: List[RteVoltageLevel] = []
        self.areas: List[RteArea] = []
        self.buses: List[RteBus] = []
        self.generators: List[Generator] = []
        self.loads: List[Load] = []
        self.lines: List[Line] = []
        self.transformers: List[TwoWindingsTransformer] = []
        self.dangling_lines: List[RteDanglingLine] = []
        self.shunts: List[Shunt] = []
        self.switches: List[Switch] = []
        self.busbar_sections: List[RteBusbarSection] = []
        self.svcs: List[StaticVarCompensator] = []