# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from VeraGridEngine.IO.base.units import UnitMultiplier, UnitSymbol
from VeraGridEngine.IO.cim.cgmes.base import Base
from VeraGridEngine.IO.cim.cgmes.cgmes_enums import CgmesProfileType


class RatioTapChangerTablePoint(Base):
	def __init__(self, rdfid, tpe, resources=list(), class_replacements=dict()):
		Base.__init__(self, rdfid=rdfid, tpe=tpe, resources=resources, class_replacements=class_replacements)

		from VeraGridEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.ratio_tap_changer_table import RatioTapChangerTable
		self.RatioTapChangerTable: RatioTapChangerTable | None = None

		self.register_property(
			name='RatioTapChangerTable',
			class_type=RatioTapChangerTable,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Points of this table.''',
			profiles=[]
		)
