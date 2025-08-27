# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from VeraGridEngine.IO.iidm.devices.rte_object import RteObject, Unit
from VeraGridEngine.Devices.Substation.voltage_level import VoltageLevel


class RteVoltageLevel(RteObject):
    def __init__(self, _id, nominalV, topologyKind, name=""):
        super().__init__("VoltageLevel")
        self.id = _id
        self.name = name
        self.nominalV = nominalV
        self.topologyKind = topologyKind

        self.register_property("id", str, description="Voltage level ID")
        self.register_property("name", str, description="name")
        self.register_property("nominalV", float, unit=Unit.get_kv(), description="Nominal voltage")
        self.register_property("topologyKind", str, description="Topology type")

    def to_veragrid(self) -> VoltageLevel:
        """

        :return:
        """
        return VoltageLevel(
            name=self.name,
            idtag=None,
            code=self.id,
            Vnom=self.nominalV,
            substation=None
        )
