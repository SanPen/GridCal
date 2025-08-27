# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from VeraGridEngine.IO.iidm.devices.rte_object import RteObject
from VeraGridEngine.Devices.Aggregation.area import Area


class RteArea(RteObject):
    def __init__(self, _id: str, name: str = "", area_type: str = "", interchange_target: float = 0.0):
        super().__init__("Area")
        self.id = _id
        self.name = name
        self.area_type: str = area_type
        self.interchange_target: float = interchange_target

        self.register_property("id", str, description="Bus ID")
        self.register_property("name", str, description="Human-readable name of the Area")
        self.register_property("area_type", str, description="The type of Area.")
        self.register_property("interchange_target", float,
                               description="The optional target interchange of this area in MW, using load sign convention (negative is export, positive is import)")

    def to_veragrid(self) -> Area:
        """
        Convert
        """
        return Area(
            name=self.name,
            code=self.id
        )
