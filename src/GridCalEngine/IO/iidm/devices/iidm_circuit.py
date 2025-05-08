# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from typing import List
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

class IidmCircuit:
    def __init__(self):
        self.substations: List[Substation] = []
        self.voltage_levels: List[VoltageLevel] = []
        self.buses: List[Bus] = []
        self.generators: List[Generator] = []
        self.loads: List[Load] = []
        self.lines: List[Line] = []
        self.transformers: List[TwoWindingsTransformer] = []
        self.dangling_lines: List[DanglingLine] = []
        self.shunts: List[Shunt] = []
        self.switches: List[Switch] = []
        self.busbar_sections: List[BusbarSection] = []
        self.svcs: List[StaticVarCompensator] = []