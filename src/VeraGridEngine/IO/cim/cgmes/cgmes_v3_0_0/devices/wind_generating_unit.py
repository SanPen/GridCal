# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from VeraGridEngine.IO.base.units import UnitMultiplier, UnitSymbol
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.generating_unit import GeneratingUnit
from VeraGridEngine.IO.cim.cgmes.cgmes_enums import CgmesProfileType, WindGenUnitKind


class WindGeneratingUnit(GeneratingUnit):
	def __init__(self, rdfid='', tpe='WindGeneratingUnit'):
		GeneratingUnit.__init__(self, rdfid, tpe)

		self.windGenUnitType: WindGenUnitKind = None
		from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.wind_power_plant import WindPowerPlant
		self.WindPowerPlant: WindPowerPlant | None = None

		self.register_property(
			name='windGenUnitType',
			class_type=WindGenUnitKind,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The kind of wind generating unit.''',
			profiles=[]
		)
		self.register_property(
			name='WindPowerPlant',
			class_type=WindPowerPlant,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''A wind power plant may have wind generating units.''',
			profiles=[]
		)
