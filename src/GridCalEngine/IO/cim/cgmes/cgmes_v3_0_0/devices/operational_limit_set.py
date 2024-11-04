# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class OperationalLimitSet(IdentifiedObject):
	def __init__(self, rdfid='', tpe='OperationalLimitSet'):
		IdentifiedObject.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.acdc_terminal import ACDCTerminal
		self.Terminal: ACDCTerminal | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.equipment import Equipment
		self.Equipment: Equipment | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.operational_limit import OperationalLimit
		self.OperationalLimitValue: OperationalLimit | None = None

		self.register_property(
			name='Terminal',
			class_type=ACDCTerminal,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The terminal where the operational limit set apply.''',
			profiles=[]
		)
		self.register_property(
			name='Equipment',
			class_type=Equipment,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The equipment to which the limit set applies.''',
			profiles=[]
		)
		self.register_property(
			name='OperationalLimitValue',
			class_type=OperationalLimit,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Values of equipment limits.''',
			profiles=[]
		)
