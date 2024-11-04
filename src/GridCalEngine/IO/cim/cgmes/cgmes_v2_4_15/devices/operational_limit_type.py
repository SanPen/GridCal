# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile, OperationalLimitDirectionKind, LimitTypeKind, UnitSymbol


class OperationalLimitType(IdentifiedObject):
	def __init__(self, rdfid='', tpe='OperationalLimitType'):
		IdentifiedObject.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.operational_limit import OperationalLimit
		self.OperationalLimit: OperationalLimit | None = None
		self.acceptableDuration: float = None
		self.limitType: LimitTypeKind = None
		self.direction: OperationalLimitDirectionKind = None

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
			name='limitType',
			class_type=LimitTypeKind,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Types of limits defined in the ENTSO-E Operational Handbook Policy 3.''',
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
