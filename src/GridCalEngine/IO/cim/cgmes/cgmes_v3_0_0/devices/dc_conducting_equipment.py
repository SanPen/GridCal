# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.equipment import Equipment
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile, UnitSymbol


class DCConductingEquipment(Equipment):
	def __init__(self, rdfid='', tpe='DCConductingEquipment'):
		Equipment.__init__(self, rdfid, tpe)

		self.ratedUdc: float = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.dc_terminal import DCTerminal
		self.DCTerminals: DCTerminal | None = None

		self.register_property(
			name='ratedUdc',
			class_type=float,
			multiplier=UnitMultiplier.k,
			unit=UnitSymbol.V,
			description='''Electrical voltage, can be both AC and DC.''',
			profiles=[]
		)
		self.register_property(
			name='DCTerminals',
			class_type=DCTerminal,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''A DC conducting equipment has DC terminals.''',
			profiles=[]
		)
