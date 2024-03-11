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
