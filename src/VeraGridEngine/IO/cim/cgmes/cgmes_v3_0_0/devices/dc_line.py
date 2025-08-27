# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from VeraGridEngine.IO.base.units import UnitMultiplier, UnitSymbol
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.dc_equipment_container import DCEquipmentContainer
from VeraGridEngine.IO.cim.cgmes.cgmes_enums import CgmesProfileType


class DCLine(DCEquipmentContainer):
	def __init__(self, rdfid='', tpe='DCLine'):
		DCEquipmentContainer.__init__(self, rdfid, tpe)

		from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.sub_geographical_region import SubGeographicalRegion
		self.Region: SubGeographicalRegion | None = None

		self.register_property(
			name='Region',
			class_type=SubGeographicalRegion,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The SubGeographicalRegion containing the DC line.''',
			profiles=[]
		)
