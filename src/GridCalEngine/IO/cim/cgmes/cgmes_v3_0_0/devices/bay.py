# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.equipment_container import EquipmentContainer
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class Bay(EquipmentContainer):
	def __init__(self, rdfid='', tpe='Bay'):
		EquipmentContainer.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.voltage_level import VoltageLevel
		self.VoltageLevel: VoltageLevel | None = None

		self.register_property(
			name='VoltageLevel',
			class_type=VoltageLevel,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The voltage level containing this bay.''',
			profiles=[]
		)
