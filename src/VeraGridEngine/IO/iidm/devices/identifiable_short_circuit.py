# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from VeraGridEngine.IO.iidm.devices.rte_object import RteObject


class IdentifiableShortCircuit(RteObject):
    def __init__(self, id: str, voltageSource: bool):
        super().__init__("IdentifiableShortCircuit")
        self.id = id
        self.voltageSource = voltageSource

        self.register_property("id", "shortCircuit:id", str, description="Short-circuit object ID")
        self.register_property("voltageSource", "shortCircuit:voltageSource", bool, description="Is it a voltage source?")
