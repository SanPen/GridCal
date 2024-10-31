# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class PhaseTapChangerTable(IdentifiedObject):
	def __init__(self, rdfid='', tpe='PhaseTapChangerTable'):
		IdentifiedObject.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.phase_tap_changer_table_point import PhaseTapChangerTablePoint
		self.PhaseTapChangerTablePoint: PhaseTapChangerTablePoint | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.phase_tap_changer_tabular import PhaseTapChangerTabular
		self.PhaseTapChangerTabular: PhaseTapChangerTabular | None = None

		self.register_property(
			name='PhaseTapChangerTablePoint',
			class_type=PhaseTapChangerTablePoint,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The points of this table.''',
			profiles=[]
		)
		self.register_property(
			name='PhaseTapChangerTabular',
			class_type=PhaseTapChangerTabular,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The phase tap changers to which this phase tap table applies.''',
			profiles=[]
		)
