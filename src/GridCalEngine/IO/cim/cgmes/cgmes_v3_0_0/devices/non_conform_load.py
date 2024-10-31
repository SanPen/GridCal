# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.energy_consumer import EnergyConsumer
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class NonConformLoad(EnergyConsumer):
	def __init__(self, rdfid='', tpe='NonConformLoad'):
		EnergyConsumer.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.non_conform_load_group import NonConformLoadGroup
		self.LoadGroup: NonConformLoadGroup | None = None

		self.register_property(
			name='LoadGroup',
			class_type=NonConformLoadGroup,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Group of this ConformLoad.''',
			profiles=[]
		)
