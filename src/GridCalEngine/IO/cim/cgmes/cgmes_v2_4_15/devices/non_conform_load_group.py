# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.load_group import LoadGroup
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class NonConformLoadGroup(LoadGroup):
	def __init__(self, rdfid='', tpe='NonConformLoadGroup'):
		LoadGroup.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.non_conform_load import NonConformLoad
		self.EnergyConsumers: NonConformLoad | None = None

		self.register_property(
			name='EnergyConsumers',
			class_type=NonConformLoad,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Group of this ConformLoad.''',
			profiles=[]
		)
