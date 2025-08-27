# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from VeraGridEngine.IO.iidm.devices.rte_object import RteObject


class StandbyAutomaton(RteObject):
    def __init__(self, id: str, enabled: bool):
        super().__init__("StandbyAutomaton")
        self.id = id
        self.enabled = enabled

        self.register_property("id", "standbyAutomaton:id", str, description="Standby automaton ID")
        self.register_property("enabled", "standbyAutomaton:enabled", bool, description="Is standby automaton enabled?")
