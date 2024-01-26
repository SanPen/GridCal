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
from GridCalEngine.IO.cim.cgmes_v2_4_15.identified_object import IdentifiedObject
from GridCalEngine.IO.cim.cgmes_v2_4_15.reporting_group import ReportingGroup
from GridCalEngine.IO.cim.cgmes_v2_4_15.acdc_terminal import ACDCTerminal


class BusNameMarker(IdentifiedObject):
	def __init__(self, rdfid='', tpe='BusNameMarker'):
		IdentifiedObject.__init__(self, rdfid, tpe)

		self.priority: int = 0
		self.ReportingGroup: ReportingGroup | None = None
		self.Terminal: ACDCTerminal | None = None

		self.register_property(
			name='priority',
			class_type=int,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='Priority of bus name marker for use as topology bus name.  Use 0 for don t care.  Use 1 for highest priority.  Use 2 as priority is less than 1 and so on.',
			profiles=[]
		)
		self.register_property(
			name='ReportingGroup',
			class_type=ReportingGroup,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='The bus name markers that belong to this reporting group.',
			profiles=[]
		)
		self.register_property(
			name='Terminal',
			class_type=ACDCTerminal,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='The terminals associated with this bus name marker.',
			profiles=[]
		)
