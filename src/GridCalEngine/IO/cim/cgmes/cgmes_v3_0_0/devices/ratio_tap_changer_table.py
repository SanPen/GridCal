# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class RatioTapChangerTable(IdentifiedObject):
	def __init__(self, rdfid='', tpe='RatioTapChangerTable'):
		IdentifiedObject.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.ratio_tap_changer import RatioTapChanger
		self.RatioTapChanger: RatioTapChanger | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.ratio_tap_changer_table_point import RatioTapChangerTablePoint
		self.RatioTapChangerTablePoint: RatioTapChangerTablePoint | None = None

		self.register_property(
			name='RatioTapChanger',
			class_type=RatioTapChanger,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The ratio tap changer of this tap ratio table.''',
			profiles=[]
		)
		self.register_property(
			name='RatioTapChangerTablePoint',
			class_type=RatioTapChangerTablePoint,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Points of this table.''',
			profiles=[]
		)
