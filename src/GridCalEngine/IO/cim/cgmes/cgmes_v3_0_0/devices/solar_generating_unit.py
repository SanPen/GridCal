# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.generating_unit import GeneratingUnit
from GridCalEngine.IO.cim.cgmes.cgmes_enums import CgmesProfileType


class SolarGeneratingUnit(GeneratingUnit):
	def __init__(self, rdfid='', tpe='SolarGeneratingUnit'):
		GeneratingUnit.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.solar_power_plant import SolarPowerPlant
		self.SolarPowerPlant: SolarPowerPlant | None = None

		self.register_property(
			name='SolarPowerPlant',
			class_type=SolarPowerPlant,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''A solar power plant may have solar generating units.''',
			profiles=[]
		)
