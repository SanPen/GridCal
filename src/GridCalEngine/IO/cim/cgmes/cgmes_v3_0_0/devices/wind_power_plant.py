# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.power_system_resource import PowerSystemResource
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class WindPowerPlant(PowerSystemResource):
	def __init__(self, rdfid='', tpe='WindPowerPlant'):
		PowerSystemResource.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.wind_generating_unit import WindGeneratingUnit
		self.WindGeneratingUnits: WindGeneratingUnit | None = None

		self.register_property(
			name='WindGeneratingUnits',
			class_type=WindGeneratingUnit,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''A wind generating unit or units may be a member of a wind power plant.''',
			profiles=[]
		)
