# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.base import Base
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class CurveData(Base):
	def __init__(self, rdfid, tpe, resources=list(), class_replacements=dict()):
		Base.__init__(self, rdfid=rdfid, tpe=tpe, resources=resources, class_replacements=class_replacements)

		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.curve import Curve
		self.Curve: Curve | None = None
		self.xvalue: float = None
		self.y1value: float = None
		self.y2value: float = None

		self.register_property(
			name='Curve',
			class_type=Curve,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The curve of  this curve data point.''',
			profiles=[]
		)
		self.register_property(
			name='xvalue',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The data value of the X-axis variable,  depending on the X-axis units.''',
			profiles=[]
		)
		self.register_property(
			name='y1value',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The data value of the  first Y-axis variable, depending on the Y-axis units.''',
			profiles=[]
		)
		self.register_property(
			name='y2value',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The data value of the second Y-axis variable (if present), depending on the Y-axis units.''',
			profiles=[]
		)
