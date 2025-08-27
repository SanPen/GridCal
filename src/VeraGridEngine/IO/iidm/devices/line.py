# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from VeraGridEngine.IO.iidm.devices.rte_object import RteObject, Unit


class Line(RteObject):
    def __init__(self, id: str, voltageLevelId1: str, bus1: str, voltageLevelId2: str, bus2: str,
                 r: float, x: float, g1: float, b1: float, g2: float, b2: float):
        super().__init__("Line")
        self.id = id
        self.voltageLevelId1 = voltageLevelId1
        self.bus1 = bus1
        self.voltageLevelId2 = voltageLevelId2
        self.bus2 = bus2
        self.r = r
        self.x = x
        self.g1 = g1
        self.b1 = b1
        self.g2 = g2
        self.b2 = b2

        self.register_property("id", "line:id", str, description="Line ID")
        self.register_property("voltageLevelId1", "line:voltageLevelId1", str, description="Voltage level 1")
        self.register_property("bus1", "line:bus1", str, description="Bus 1")
        self.register_property("voltageLevelId2", "line:voltageLevelId2", str, description="Voltage level 2")
        self.register_property("bus2", "line:bus2", str, description="Bus 2")
        self.register_property("r", "line:r", float, Unit("Ohm"), description="Resistance")
        self.register_property("x", "line:x", float, Unit("Ohm"), description="Reactance")
        self.register_property("g1", "line:g1", float, Unit("S"), description="Conductance at end 1")
        self.register_property("b1", "line:b1", float, Unit("S"), description="Susceptance at end 1")
        self.register_property("g2", "line:g2", float, Unit("S"), description="Conductance at end 2")
        self.register_property("b2", "line:b2", float, Unit("S"), description="Susceptance at end 2")

