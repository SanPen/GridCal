# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.load_group import LoadGroup
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class ConformLoadGroup(LoadGroup):
	def __init__(self, rdfid='', tpe='ConformLoadGroup'):
		LoadGroup.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.conform_load import ConformLoad
		self.EnergyConsumers: ConformLoad | None = None

		self.register_property(
			name='EnergyConsumers',
			class_type=ConformLoad,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Conform loads assigned to this ConformLoadGroup.''',
			profiles=[]
		)
