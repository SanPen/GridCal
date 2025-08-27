# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from VeraGridEngine.IO.iidm.devices.rte_object import RteObject, Unit


class Shunt(RteObject):
    def __init__(self, id: str, bus: str, g: float, b: float):
        super().__init__("Shunt")
        self.id = id
        self.bus = bus
        self.g = g
        self.b = b

        self.register_property("id", "shunt:id", str, description="Shunt ID")
        self.register_property("bus", "shunt:bus", str, description="Connected bus")
        self.register_property("g", "shunt:g", float, Unit("S"), description="Conductance")
        self.register_property("b", "shunt:b", float, Unit("S"), description="Susceptance")
