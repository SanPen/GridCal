# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.base import Base
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class SvSwitch(Base):
	def __init__(self, rdfid, tpe, resources=list(), class_replacements=dict()):
		Base.__init__(self, rdfid=rdfid, tpe=tpe, resources=resources, class_replacements=class_replacements)

		self.open: bool = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.switch import Switch
		self.Switch: Switch | None = None

		self.register_property(
			name='open',
			class_type=bool,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The attribute tells if the computed state of the switch is considered open.''',
			profiles=[]
		)
		self.register_property(
			name='Switch',
			class_type=Switch,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The switch associated with the switch state.''',
			profiles=[]
		)
