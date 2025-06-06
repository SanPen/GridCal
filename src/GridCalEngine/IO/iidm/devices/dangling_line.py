# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from GridCalEngine.IO.iidm.devices.rte_object import RteObject, Unit


class DanglingLine(RteObject):
    def __init__(self, id: str, bus: str, p0: float, q0: float, u0: float, r: float, x: float, g: float, b: float):
        super().__init__("DanglingLine")
        self.id = id
        self.bus = bus
        self.p0 = p0
        self.q0 = q0
        self.u0 = u0
        self.r = r
        self.x = x
        self.g = g
        self.b = b

        self.register_property("id", "danglingLine:id", str, description="Dangling line ID")
        self.register_property("bus", "danglingLine:bus", str, description="Connected bus")
        self.register_property("p0", "danglingLine:p0", float, Unit("MW"), description="Active power")
        self.register_property("q0", "danglingLine:q0", float, Unit("MVAr"), description="Reactive power")
        self.register_property("u0", "danglingLine:u0", float, Unit("kV"), description="Voltage at terminal")
        self.register_property("r", "danglingLine:r", float, Unit("Ohm"), description="Resistance")
        self.register_property("x", "danglingLine:x", float, Unit("Ohm"), description="Reactance")
        self.register_property("g", "danglingLine:g", float, Unit("S"), description="Conductance")
        self.register_property("b", "danglingLine:b", float, Unit("S"), description="Susceptance")
