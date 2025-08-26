# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.tap_changer import TapChanger
from GridCalEngine.IO.cim.cgmes.cgmes_enums import CgmesProfileType


class PhaseTapChanger(TapChanger):
	def __init__(self, rdfid='', tpe='PhaseTapChanger'):
		TapChanger.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.transformer_end import TransformerEnd
		self.TransformerEnd: TransformerEnd | None = None

		self.register_property(
			name='TransformerEnd',
			class_type=TransformerEnd,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Phase tap changer associated with this transformer end.''',
			profiles=[]
		)
