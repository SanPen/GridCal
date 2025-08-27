# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from VeraGridEngine.IO.iidm.devices.rte_object import RteObject, Unit


class Load(RteObject):
    def __init__(self, id, bus, p0, q0):
        super().__init__("Load")
        self.id = id
        self.bus = bus
        self.p0 = p0
        self.q0 = q0

        self.register_property("id", "load:id", str, description="Load ID")
        self.register_property("bus", "load:bus", str, description="Connected bus")
        self.register_property("p0", "load:p0", float, Unit("MW"), description="Active power")
        self.register_property("q0", "load:q0", float, Unit("MVAr"), description="Reactive power")

