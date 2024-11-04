# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.power_system_resource import PowerSystemResource
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class SolarPowerPlant(PowerSystemResource):
	def __init__(self, rdfid='', tpe='SolarPowerPlant'):
		PowerSystemResource.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.solar_generating_unit import SolarGeneratingUnit
		self.SolarGeneratingUnits: SolarGeneratingUnit | None = None

		self.register_property(
			name='SolarGeneratingUnits',
			class_type=SolarGeneratingUnit,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''A solar generating unit or units may be a member of a solar power plant.''',
			profiles=[]
		)
