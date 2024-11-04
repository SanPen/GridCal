# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.equipment import Equipment
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class DCConductingEquipment(Equipment):
	def __init__(self, rdfid='', tpe='DCConductingEquipment'):
		Equipment.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.dc_terminal import DCTerminal
		self.DCTerminals: DCTerminal | None = None

		self.register_property(
			name='DCTerminals',
			class_type=DCTerminal,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''None''',
			profiles=[]
		)
