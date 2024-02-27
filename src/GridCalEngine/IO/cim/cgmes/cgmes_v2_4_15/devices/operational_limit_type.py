# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
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
