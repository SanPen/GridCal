# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.equipment_container import EquipmentContainer
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class Line(EquipmentContainer):
	def __init__(self, rdfid='', tpe='Line'):
		EquipmentContainer.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.sub_geographical_region import SubGeographicalRegion
		self.Region: SubGeographicalRegion | None = None

		self.register_property(
			name='Region',
			class_type=SubGeographicalRegion,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The sub-geographical region of the line.''',
			profiles=[]
		)
