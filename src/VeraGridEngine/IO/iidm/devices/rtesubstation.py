# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from VeraGridEngine.IO.iidm.devices.rte_object import RteObject


class RteSubstation(RteObject):
    def __init__(self, id, country, tso, geographicalTags):
        super().__init__("Substation")
        self.id = id
        self.country = country
        self.tso = tso
        self.geographicalTags = geographicalTags

        self.register_property("id", "substation:id", str, description="Substation ID")
        self.register_property("country", "substation:country", str, description="Country")
        self.register_property("tso", "substation:tso", str, description="TSO")
        self.register_property("geographicalTags", "substation:geographicalTags", str, description="Geographical tags")
