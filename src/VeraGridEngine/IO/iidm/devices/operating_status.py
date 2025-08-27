# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from VeraGridEngine.IO.iidm.devices.rte_object import RteObject


class OperatingStatus(RteObject):
    def __init__(self, id: str, inService: bool):
        super().__init__("OperatingStatus")
        self.id = id
        self.inService = inService

        self.register_property("id", "operatingStatus:id", str, description="Operating status ID")
        self.register_property("inService", "operatingStatus:inService", bool, description="Is the component in service?")
