# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class TieFlow(IdentifiedObject):
	def __init__(self, rdfid='', tpe='TieFlow'):
		IdentifiedObject.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.control_area import ControlArea
		self.ControlArea: ControlArea | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.terminal import Terminal
		self.Terminal: Terminal | None = None
		self.positiveFlowIn: bool = None

		self.register_property(
			name='ControlArea',
			class_type=ControlArea,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The control area of the tie flows.''',
			profiles=[]
		)
		self.register_property(
			name='Terminal',
			class_type=Terminal,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The terminal to which this tie flow belongs.''',
			profiles=[]
		)
		self.register_property(
			name='positiveFlowIn',
			class_type=bool,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Specifies the sign of the tie flow associated with a control area. True if positive flow into the terminal (load convention) is also positive flow into the control area.  See the description of ControlArea for further explanation of how TieFlow.positiveFlowIn is used.''',
			profiles=[]
		)
