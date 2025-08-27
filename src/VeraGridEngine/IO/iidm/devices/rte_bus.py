# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from typing import List, Dict
from VeraGridEngine.IO.iidm.devices.rte_object import RteObject
from VeraGridEngine.Devices.Substation.bus import Bus, Area


class RteBus(RteObject):
    def __init__(self, _id: str, area_number: int, status: str, nodes: List[int]):
        super().__init__("Bus")
        self.id = _id
        self.area_number: int = area_number
        self.status = status
        self.nodes: List[int] = nodes

        self.register_property("id", str, description="Bus ID")

    def to_veragrid(self, area_dict: Dict[int, Area]) -> Bus:
        """
        Convert
        """
        return Bus(
            name="",
            code=self.id,
            area=area_dict.get(self.area_number, None)
        )