# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from VeraGridEngine.IO.base.units import UnitMultiplier, UnitSymbol
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.load_group import LoadGroup
from VeraGridEngine.IO.cim.cgmes.cgmes_enums import CgmesProfileType


class ConformLoadGroup(LoadGroup):
	def __init__(self, rdfid='', tpe='ConformLoadGroup'):
		LoadGroup.__init__(self, rdfid, tpe)

		from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.conform_load import ConformLoad
		self.EnergyConsumers: ConformLoad | None = None

		self.register_property(
			name='EnergyConsumers',
			class_type=ConformLoad,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Conform loads assigned to this ConformLoadGroup.''',
			profiles=[]
		)
