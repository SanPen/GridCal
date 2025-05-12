# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from GridCalEngine.IO.iidm.devices.rte_object import RteObject, Unit


class VoltageLevel(RteObject):
    def __init__(self, id, nominalV, topologyKind):
        super().__init__("VoltageLevel")
        self.id = id
        self.nominalV = nominalV
        self.topologyKind = topologyKind

        self.register_property("id", "voltageLevel:id", str, description="Voltage level ID")
        self.register_property("nominalV", "voltageLevel:nominalV", float, Unit("kV"), description="Nominal voltage")
        self.register_property("topologyKind", "voltageLevel:topologyKind", str, description="Topology type")

