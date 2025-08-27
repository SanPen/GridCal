# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from VeraGridEngine.IO.iidm.devices.rte_object import RteObject, Unit



class GeneratorShortCircuit(RteObject):
    def __init__(self, generatorId: str, voltageFactor: float, k: float):
        super().__init__("GeneratorShortCircuit")
        self.generatorId = generatorId
        self.voltageFactor = voltageFactor
        self.k = k

        self.register_property("generatorId", "generatorShortCircuit:generatorId", str, description="Associated generator ID")
        self.register_property("voltageFactor", "generatorShortCircuit:voltageFactor", float, description="Voltage factor")
        self.register_property("k", "generatorShortCircuit:k", float, description="Short circuit ratio k")


class Generator(RteObject):
    def __init__(self, id, bus, targetP, targetQ, targetV):
        super().__init__("Generator")
        self.id = id
        self.bus = bus
        self.targetP = targetP
        self.targetQ = targetQ
        self.targetV = targetV

        self.register_property("id", "generator:id", str, description="Generator ID")
        self.register_property("bus", "generator:bus", str, description="Connected bus")
        self.register_property("targetP", "generator:targetP", float, Unit("MW"), description="Active power setpoint")
        self.register_property("targetQ", "generator:targetQ", float, Unit("MVAr"), description="Reactive power setpoint")
        self.register_property("targetV", "generator:targetV", float, Unit("kV"), description="Voltage setpoint")
