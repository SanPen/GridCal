# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from VeraGridEngine.IO.base.units import UnitMultiplier, UnitSymbol
from VeraGridEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.control import Control
from VeraGridEngine.IO.cim.cgmes.cgmes_enums import CgmesProfileType


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
			description='''A floating point number. The range is unspecified and not limited.''',
			profiles=[]
		)
		self.register_property(
			name='minValue',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''A floating point number. The range is unspecified and not limited.''',
			profiles=[]
		)
