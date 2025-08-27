# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from VeraGridEngine.IO.iidm.devices.rte_object import RteObject


class DiscreteMeasurement(RteObject):
    def __init__(self, id: str, equipmentId: str, value: bool):
        super().__init__("DiscreteMeasurement")
        self.id = id
        self.equipmentId = equipmentId
        self.value = value

        self.register_property("id", "discreteMeasurement:id", str, description="Measurement ID")
        self.register_property("equipmentId", "discreteMeasurement:equipmentId", str, description="Referenced equipment ID")
        self.register_property("value", "discreteMeasurement:value", bool, description="Boolean value of the measurement")
