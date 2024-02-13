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


class SubGeographicalRegion(IdentifiedObject):
	def __init__(self, rdfid='', tpe='SubGeographicalRegion'):
		IdentifiedObject.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.dc_line import DCLine
		self.DCLines: DCLine | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.geographical_region import GeographicalRegion
		self.Region: GeographicalRegion | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.line import Line
		self.Lines: Line | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.substation import Substation
		self.Substations: Substation | None = None

		self.register_property(
			name='DCLines',
			class_type=DCLine,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The DC lines in this sub-geographical region.''',
			profiles=[]
		)
		self.register_property(
			name='Region',
			class_type=GeographicalRegion,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The geographical region which this sub-geographical region is within.''',
			profiles=[]
		)
		self.register_property(
			name='Lines',
			class_type=Line,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The lines within the sub-geographical region.''',
			profiles=[]
		)
		self.register_property(
			name='Substations',
			class_type=Substation,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The substations in this sub-geographical region.''',
			profiles=[]
		)
