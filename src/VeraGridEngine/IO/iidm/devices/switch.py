# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from VeraGridEngine.IO.iidm.devices.rte_object import RteObject


class Switch(RteObject):
    def __init__(self, id: str, bus1: str, bus2: str, kind: str, open: bool, retained: bool):
        super().__init__("Switch")
        self.id = id
        self.bus1 = bus1
        self.bus2 = bus2
        self.kind = kind
        self.open = open
        self.retained = retained

        self.register_property("id", "switch:id", str, description="Switch ID")
        self.register_property("bus1", "switch:bus1", str, description="Bus 1")
        self.register_property("bus2", "switch:bus2", str, description="Bus 2")
        self.register_property("kind", "switch:kind", str, description="Switch type")
        self.register_property("open", "switch:open", bool, description="Is switch open?")
        self.register_property("retained", "switch:retained", bool, description="Is switch retained?")