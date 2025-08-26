# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.regulating_control import RegulatingControl
from GridCalEngine.IO.cim.cgmes.cgmes_enums import CgmesProfileType


class TapChangerControl(RegulatingControl):
	def __init__(self, rdfid='', tpe='TapChangerControl'):
		RegulatingControl.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.tap_changer import TapChanger
		self.TapChanger: TapChanger | None = None

		self.register_property(
			name='TapChanger',
			class_type=TapChanger,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The regulating control scheme in which this tap changer participates.''',
			profiles=[]
		)
