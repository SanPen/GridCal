# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class ControlAreaGeneratingUnit(IdentifiedObject):
	def __init__(self, rdfid='', tpe='ControlAreaGeneratingUnit'):
		IdentifiedObject.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.generating_unit import GeneratingUnit
		self.GeneratingUnit: GeneratingUnit | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.control_area import ControlArea
		self.ControlArea: ControlArea | None = None

		self.register_property(
			name='GeneratingUnit',
			class_type=GeneratingUnit,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The generating unit specified for this control area.  Note that a control area should include a GeneratingUnit only once.''',
			profiles=[]
		)
		self.register_property(
			name='ControlArea',
			class_type=ControlArea,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The parent control area for the generating unit specifications.''',
			profiles=[]
		)
