# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from VeraGridEngine.IO.base.units import UnitMultiplier, UnitSymbol
from VeraGridEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.equipment_container import EquipmentContainer
from VeraGridEngine.IO.cim.cgmes.cgmes_enums import CgmesProfileType


class Line(EquipmentContainer):
	def __init__(self, rdfid='', tpe='Line'):
		EquipmentContainer.__init__(self, rdfid, tpe)

		from VeraGridEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.sub_geographical_region import SubGeographicalRegion
		self.Region: SubGeographicalRegion | None = None

		self.register_property(
			name='Region',
			class_type=SubGeographicalRegion,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The sub-geographical region of the line.''',
			profiles=[]
		)
