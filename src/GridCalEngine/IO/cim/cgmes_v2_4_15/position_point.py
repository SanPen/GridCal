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
from GridCalEngine.IO.cim.cgmes_v2_4_15.cgmes_enums import cgmesProfile
from GridCalEngine.IO.cim.cgmes_v2_4_15.location import Location


class PositionPoint(object):
	def __init__(self, rdfid='', tpe='PositionPoint'):

		self.Location: Location | None = None
		self.sequenceNumber: int = 0
		self.xPosition: str = ''
		self.yPosition: str = ''
		self.zPosition: str = ''

		self.register_property(
			name='Location',
			class_type=Location,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='Location described by this position point.',
			profiles=[]
		)
		self.register_property(
			name='sequenceNumber',
			class_type=int,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='Zero-relative sequence number of this point within a series of points.',
			profiles=[]
		)
		self.register_property(
			name='xPosition',
			class_type=str,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='X axis position.',
			profiles=[]
		)
		self.register_property(
			name='yPosition',
			class_type=str,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='Y axis position.',
			profiles=[]
		)
		self.register_property(
			name='zPosition',
			class_type=str,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='(if applicable) Z axis position.',
			profiles=[]
		)
