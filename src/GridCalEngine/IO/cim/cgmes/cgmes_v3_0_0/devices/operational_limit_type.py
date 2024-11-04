# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile, UnitSymbol, LimitKind, OperationalLimitDirectionKind


class OperationalLimitType(IdentifiedObject):
	def __init__(self, rdfid='', tpe='OperationalLimitType'):
		IdentifiedObject.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.operational_limit import OperationalLimit
		self.OperationalLimit: OperationalLimit | None = None
		self.acceptableDuration: float = None
		self.direction: OperationalLimitDirectionKind = None
		self.isInfiniteDuration: bool = None
		self.kind: LimitKind = None

		self.register_property(
			name='OperationalLimit',
			class_type=OperationalLimit,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The operational limits associated with this type of limit.''',
			profiles=[]
		)
		self.register_property(
			name='acceptableDuration',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.s,
			description='''Time, in seconds.''',
			profiles=[]
		)
		self.register_property(
			name='direction',
			class_type=OperationalLimitDirectionKind,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The direction of the limit.''',
			profiles=[]
		)
		self.register_property(
			name='isInfiniteDuration',
			class_type=bool,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Defines if the operational limit type has infinite duration. If true, the limit has infinite duration. If false, the limit has definite duration which is defined by the attribute acceptableDuration.''',
			profiles=[]
		)
		self.register_property(
			name='kind',
			class_type=LimitKind,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Types of limits defined in the ENTSO-E Operational Handbook Policy 3.''',
			profiles=[]
		)
