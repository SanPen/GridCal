# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.energy_area import EnergyArea
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class LoadArea(EnergyArea):
	def __init__(self, rdfid='', tpe='LoadArea'):
		EnergyArea.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.sub_load_area import SubLoadArea
		self.SubLoadAreas: SubLoadArea | None = None

		self.register_property(
			name='SubLoadAreas',
			class_type=SubLoadArea,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The SubLoadAreas in the LoadArea.''',
			profiles=[]
		)
