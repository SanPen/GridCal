# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class BusNameMarker(IdentifiedObject):
	def __init__(self, rdfid='', tpe='BusNameMarker'):
		IdentifiedObject.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.acdc_terminal import ACDCTerminal
		self.Terminal: ACDCTerminal | None = None
		self.priority: int = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.reporting_group import ReportingGroup
		self.ReportingGroup: ReportingGroup | None = None

		self.register_property(
			name='Terminal',
			class_type=ACDCTerminal,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The terminals associated with this bus name marker.''',
			profiles=[]
		)
		self.register_property(
			name='priority',
			class_type=int,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Priority of bus name marker for use as topology bus name.  Use 0 for do not care.  Use 1 for highest priority.  Use 2 as priority is less than 1 and so on.''',
			profiles=[]
		)
		self.register_property(
			name='ReportingGroup',
			class_type=ReportingGroup,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The reporting group to which this bus name marker belongs.''',
			profiles=[]
		)
