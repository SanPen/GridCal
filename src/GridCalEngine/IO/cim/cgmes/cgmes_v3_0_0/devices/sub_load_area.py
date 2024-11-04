# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.energy_area import EnergyArea
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class SubLoadArea(EnergyArea):
	def __init__(self, rdfid='', tpe='SubLoadArea'):
		EnergyArea.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.load_area import LoadArea
		self.LoadArea: LoadArea | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.load_group import LoadGroup
		self.LoadGroups: LoadGroup | None = None

		self.register_property(
			name='LoadArea',
			class_type=LoadArea,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The LoadArea where the SubLoadArea belongs.''',
			profiles=[]
		)
		self.register_property(
			name='LoadGroups',
			class_type=LoadGroup,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The Loadgroups in the SubLoadArea.''',
			profiles=[]
		)
