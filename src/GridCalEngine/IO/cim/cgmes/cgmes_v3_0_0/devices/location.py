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
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class Location(IdentifiedObject):
	def __init__(self, rdfid='', tpe='Location'):
		IdentifiedObject.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.coordinate_system import CoordinateSystem
		self.CoordinateSystem: CoordinateSystem | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.power_system_resource import PowerSystemResource
		self.PowerSystemResources: PowerSystemResource | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.position_point import PositionPoint
		self.PositionPoints: PositionPoint | None = None

		self.register_property(
			name='CoordinateSystem',
			class_type=CoordinateSystem,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Coordinate system used to describe position points of this location.''',
			profiles=[]
		)
		self.register_property(
			name='PowerSystemResources',
			class_type=PowerSystemResource,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''All power system resources at this location.''',
			profiles=[]
		)
		self.register_property(
			name='PositionPoints',
			class_type=PositionPoint,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Sequence of position points describing this location, expressed in coordinate system 'Location.CoordinateSystem'.''',
			profiles=[]
		)
