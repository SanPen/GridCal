# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from VeraGridEngine.IO.base.units import UnitMultiplier, UnitSymbol
from VeraGridEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.generating_unit import GeneratingUnit
from VeraGridEngine.IO.cim.cgmes.cgmes_enums import CgmesProfileType, HydroEnergyConversionKind


class HydroGeneratingUnit(GeneratingUnit):
	def __init__(self, rdfid='', tpe='HydroGeneratingUnit'):
		GeneratingUnit.__init__(self, rdfid, tpe)

		self.energyConversionCapability: HydroEnergyConversionKind = None
		from VeraGridEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.hydro_power_plant import HydroPowerPlant
		self.HydroPowerPlant: HydroPowerPlant | None = None

		self.register_property(
			name='energyConversionCapability',
			class_type=HydroEnergyConversionKind,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Energy conversion capability for generating.''',
			profiles=[]
		)
		self.register_property(
			name='HydroPowerPlant',
			class_type=HydroPowerPlant,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The hydro generating unit belongs to a hydro power plant.''',
			profiles=[]
		)
