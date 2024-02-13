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
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile, UnitSymbol


class BasicIntervalSchedule(IdentifiedObject):
	def __init__(self, rdfid='', tpe='BasicIntervalSchedule'):
		IdentifiedObject.__init__(self, rdfid, tpe)

		import datetime
		self.startTime: datetime.datetime | None = None
		self.value1Unit: UnitSymbol = None
		self.value2Unit: UnitSymbol = None

		self.register_property(
			name='startTime',
			class_type=datetime.datetime,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The time for the first time point.''',
			profiles=[]
		)
		self.register_property(
			name='value1Unit',
			class_type=UnitSymbol,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Value1 units of measure.''',
			profiles=[]
		)
		self.register_property(
			name='value2Unit',
			class_type=UnitSymbol,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Value2 units of measure.''',
			profiles=[]
		)
