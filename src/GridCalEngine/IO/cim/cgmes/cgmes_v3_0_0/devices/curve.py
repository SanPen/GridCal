# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile, CurveStyle, UnitSymbol


class Curve(IdentifiedObject):
	def __init__(self, rdfid='', tpe='Curve'):
		IdentifiedObject.__init__(self, rdfid, tpe)

		self.curveStyle: CurveStyle = None
		self.xUnit: UnitSymbol = None
		self.y1Unit: UnitSymbol = None
		self.y2Unit: UnitSymbol = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.curve_data import CurveData
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
			description='''The point data values that define this curve.''',
			profiles=[]
		)
