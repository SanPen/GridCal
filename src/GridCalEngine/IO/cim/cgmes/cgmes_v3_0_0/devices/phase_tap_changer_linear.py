# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.phase_tap_changer import PhaseTapChanger
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile, UnitSymbol


class PhaseTapChangerLinear(PhaseTapChanger):
	def __init__(self, rdfid='', tpe='PhaseTapChangerLinear'):
		PhaseTapChanger.__init__(self, rdfid, tpe)

		self.stepPhaseShiftIncrement: float = None
		self.xMax: float = None
		self.xMin: float = None

		self.register_property(
			name='stepPhaseShiftIncrement',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.deg,
			description='''Measurement of angle in degrees.''',
			profiles=[]
		)
		self.register_property(
			name='xMax',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.ohm,
			description='''Reactance (imaginary part of impedance), at rated frequency.''',
			profiles=[]
		)
		self.register_property(
			name='xMin',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.ohm,
			description='''Reactance (imaginary part of impedance), at rated frequency.''',
			profiles=[]
		)
