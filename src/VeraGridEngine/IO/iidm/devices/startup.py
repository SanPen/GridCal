# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from VeraGridEngine.IO.iidm.devices.rte_object import RteObject, Unit


class Startup(RteObject):
    def __init__(self, generatorId: str, startupTime: float):
        super().__init__("Startup")
        self.generatorId = generatorId
        self.startupTime = startupTime

        self.register_property("generatorId", "startup:generatorId", str, description="Associated generator ID")
        self.register_property("startupTime", "startup:startupTime", float, Unit("s"), description="Startup time")
