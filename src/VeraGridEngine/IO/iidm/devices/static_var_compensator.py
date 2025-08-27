# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from VeraGridEngine.IO.iidm.devices.rte_object import RteObject, Unit


class StaticVarCompensator(RteObject):
    def __init__(self, id: str, bus: str, bMin: float, bMax: float, voltageSetPoint: float):
        super().__init__("StaticVarCompensator")
        self.id = id
        self.bus = bus
        self.bMin = bMin
        self.bMax = bMax
        self.voltageSetPoint = voltageSetPoint

        self.register_property("id", "svc:id", str, description="SVC ID")
        self.register_property("bus", "svc:bus", str, description="Connected bus")
        self.register_property("bMin", "svc:bMin", float, Unit("S"), description="Minimum susceptance")
        self.register_property("bMax", "svc:bMax", float, Unit("S"), description="Maximum susceptance")
        self.register_property("voltageSetPoint", "svc:voltageSetPoint", float, Unit("kV"), description="Voltage setpoint")