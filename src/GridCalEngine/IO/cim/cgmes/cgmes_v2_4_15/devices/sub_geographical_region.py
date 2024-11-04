# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class SubGeographicalRegion(IdentifiedObject):
	def __init__(self, rdfid='', tpe='SubGeographicalRegion'):
		IdentifiedObject.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.dc_line import DCLine
		self.DCLines: DCLine | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.geographical_region import GeographicalRegion
		self.Region: GeographicalRegion | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.line import Line
		self.Lines: Line | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.substation import Substation
		self.Substations: Substation | None = None

		self.register_property(
			name='DCLines',
			class_type=DCLine,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''None''',
			profiles=[]
		)
		self.register_property(
			name='Region',
			class_type=GeographicalRegion,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The geographical region to which this sub-geographical region is within.''',
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
