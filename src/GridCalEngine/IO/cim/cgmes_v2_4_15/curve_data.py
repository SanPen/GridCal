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
from GridCalEngine.IO.cim.cgmes_v2_4_15.curve import Curve


class CurveData(object):
	def __init__(self, rdfid='', tpe='CurveData'):

		self.Curve: Curve | None = None
		self.xvalue: float = 0.0
		self.y1value: float = 0.0
		self.y2value: float = 0.0

		self.register_property(
			name='Curve',
			class_type=Curve,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='The point data values that define this curve.',
			profiles=[]
		)
		self.register_property(
			name='xvalue',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='A floating point number. The range is unspecified and not limited.',
			profiles=[]
		)
		self.register_property(
			name='y1value',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='A floating point number. The range is unspecified and not limited.',
			profiles=[]
		)
		self.register_property(
			name='y2value',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='A floating point number. The range is unspecified and not limited.',
			profiles=[]
		)
