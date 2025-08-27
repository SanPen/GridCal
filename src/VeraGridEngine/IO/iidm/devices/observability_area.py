# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from VeraGridEngine.IO.iidm.devices.rte_object import RteObject


class ObservabilityArea(RteObject):
    def __init__(self, id: str, name: str):
        super().__init__("ObservabilityArea")
        self.id = id
        self.name = name

        self.register_property("id", "observabilityArea:id", str, description="Observability area ID")
        self.register_property("name", "observabilityArea:name", str, description="Area name")
