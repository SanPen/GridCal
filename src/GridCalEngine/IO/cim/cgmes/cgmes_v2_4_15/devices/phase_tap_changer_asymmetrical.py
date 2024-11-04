# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.phase_tap_changer_non_linear import PhaseTapChangerNonLinear
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile, UnitSymbol


class PhaseTapChangerAsymmetrical(PhaseTapChangerNonLinear):
	def __init__(self, rdfid='', tpe='PhaseTapChangerAsymmetrical'):
		PhaseTapChangerNonLinear.__init__(self, rdfid, tpe)

		self.windingConnectionAngle: float = None

		self.register_property(
			name='windingConnectionAngle',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.deg,
			description='''Measurement of angle in degrees.''',
			profiles=[]
		)
