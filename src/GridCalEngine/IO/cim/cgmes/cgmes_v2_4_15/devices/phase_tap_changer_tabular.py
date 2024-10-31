# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.phase_tap_changer import PhaseTapChanger
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class PhaseTapChangerTabular(PhaseTapChanger):
	def __init__(self, rdfid='', tpe='PhaseTapChangerTabular'):
		PhaseTapChanger.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.phase_tap_changer_table import PhaseTapChangerTable
		self.PhaseTapChangerTable: PhaseTapChangerTable | None = None

		self.register_property(
			name='PhaseTapChangerTable',
			class_type=PhaseTapChangerTable,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The phase tap changer table for this phase tap changer.''',
			profiles=[]
		)
