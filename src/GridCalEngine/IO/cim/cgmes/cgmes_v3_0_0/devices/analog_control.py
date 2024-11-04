# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.control import Control
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class AnalogControl(Control):
	def __init__(self, rdfid='', tpe='AnalogControl'):
		Control.__init__(self, rdfid, tpe)

		self.maxValue: float = None
		self.minValue: float = None

		self.register_property(
			name='maxValue',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Normal value range maximum for any of the Control.value. Used for scaling, e.g. in bar graphs.''',
			profiles=[]
		)
		self.register_property(
			name='minValue',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Normal value range minimum for any of the Control.value. Used for scaling, e.g. in bar graphs.''',
			profiles=[]
		)
