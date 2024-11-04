# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.base import Base
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile, UnitSymbol


class PhaseTapChangerTablePoint(Base):
	def __init__(self, rdfid, tpe, resources=list(), class_replacements=dict()):
		Base.__init__(self, rdfid=rdfid, tpe=tpe, resources=resources, class_replacements=class_replacements)

		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.phase_tap_changer_table import PhaseTapChangerTable
		self.PhaseTapChangerTable: PhaseTapChangerTable | None = None
		self.angle: float = None

		self.register_property(
			name='PhaseTapChangerTable',
			class_type=PhaseTapChangerTable,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The table of this point.''',
			profiles=[]
		)
		self.register_property(
			name='angle',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.deg,
			description='''Measurement of angle in degrees.''',
			profiles=[]
		)
