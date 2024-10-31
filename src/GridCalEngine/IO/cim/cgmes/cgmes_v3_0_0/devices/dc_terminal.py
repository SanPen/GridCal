# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.dc_base_terminal import DCBaseTerminal
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class DCTerminal(DCBaseTerminal):
	def __init__(self, rdfid='', tpe='DCTerminal'):
		DCBaseTerminal.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.dc_conducting_equipment import DCConductingEquipment
		self.DCConductingEquipment: DCConductingEquipment | None = None

		self.register_property(
			name='DCConductingEquipment',
			class_type=DCConductingEquipment,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''An DC  terminal belong to a DC conducting equipment.''',
			profiles=[]
		)
