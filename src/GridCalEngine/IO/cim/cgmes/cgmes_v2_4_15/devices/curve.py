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
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile, CurveStyle, UnitSymbol


class Curve(IdentifiedObject):
	def __init__(self, rdfid='', tpe='Curve'):
		IdentifiedObject.__init__(self, rdfid, tpe)

		self.curveStyle: CurveStyle = None
		self.xUnit: UnitSymbol = None
		self.y1Unit: UnitSymbol = None
		self.y2Unit: UnitSymbol = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.curve_data import CurveData
		self.CurveDatas: CurveData | None = None

		self.register_property(
			name='curveStyle',
			class_type=CurveStyle,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The style or shape of the curve.''',
			profiles=[]
		)
		self.register_property(
			name='xUnit',
			class_type=UnitSymbol,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The X-axis units of measure.''',
			profiles=[]
		)
		self.register_property(
			name='y1Unit',
			class_type=UnitSymbol,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The Y1-axis units of measure.''',
			profiles=[]
		)
		self.register_property(
			name='y2Unit',
			class_type=UnitSymbol,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The Y2-axis units of measure.''',
			profiles=[]
		)
		self.register_property(
			name='CurveDatas',
			class_type=CurveData,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The curve of  this curve data point.''',
			profiles=[]
		)
