# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.generating_unit import GeneratingUnit
from GridCalEngine.IO.cim.cgmes.cgmes_enums import CgmesProfileType, HydroEnergyConversionKind, HydroTurbineKind, UnitSymbol


class HydroGeneratingUnit(GeneratingUnit):
	def __init__(self, rdfid='', tpe='HydroGeneratingUnit'):
		GeneratingUnit.__init__(self, rdfid, tpe)

		self.energyConversionCapability: HydroEnergyConversionKind = None
		self.dropHeight: float = None
		self.turbineType: HydroTurbineKind = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.hydro_power_plant import HydroPowerPlant
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
			name='dropHeight',
			class_type=float,
			multiplier=UnitMultiplier.k,
			unit=UnitSymbol.m,
			description='''Unit of length. It shall be a positive value or zero.''',
			profiles=[]
		)
		self.register_property(
			name='turbineType',
			class_type=HydroTurbineKind,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Type of turbine.''',
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
