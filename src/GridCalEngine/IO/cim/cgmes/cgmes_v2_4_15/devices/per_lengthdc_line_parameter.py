# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.base import Base
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile, UnitSymbol


class PerLengthDCLineParameter(Base):
	def __init__(self, rdfid, tpe, resources=list(), class_replacements=dict()):
		Base.__init__(self, rdfid=rdfid, tpe=tpe, resources=resources, class_replacements=class_replacements)

		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.dc_line_segment import DCLineSegment
		self.DCLineSegments: DCLineSegment | None = None
		self.capacitance: float = None
		self.inductance: float = None
		self.resistance: float = None

		self.register_property(
			name='DCLineSegments',
			class_type=DCLineSegment,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''All line segments described by this set of per-length parameters.''',
			profiles=[]
		)
		self.register_property(
			name='capacitance',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.F,
			description='''Capacitance per unit of length.''',
			profiles=[]
		)
		self.register_property(
			name='inductance',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.H,
			description='''Inductance per unit of length.''',
			profiles=[]
		)
		self.register_property(
			name='resistance',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.ohm,
			description='''Resistance (real part of impedance) per unit of length.''',
			profiles=[]
		)
