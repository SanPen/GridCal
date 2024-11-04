# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.power_system_resource import PowerSystemResource
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile, HydroPlantStorageKind


class HydroPowerPlant(PowerSystemResource):
	def __init__(self, rdfid='', tpe='HydroPowerPlant'):
		PowerSystemResource.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.hydro_generating_unit import HydroGeneratingUnit
		self.HydroGeneratingUnits: HydroGeneratingUnit | None = None
		self.hydroPlantStorageType: HydroPlantStorageKind = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.hydro_pump import HydroPump
		self.HydroPumps: HydroPump | None = None

		self.register_property(
			name='HydroGeneratingUnits',
			class_type=HydroGeneratingUnit,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The hydro generating unit belongs to a hydro power plant.''',
			profiles=[]
		)
		self.register_property(
			name='hydroPlantStorageType',
			class_type=HydroPlantStorageKind,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The type of hydro power plant water storage.''',
			profiles=[]
		)
		self.register_property(
			name='HydroPumps',
			class_type=HydroPump,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The hydro pump may be a member of a pumped storage plant or a pump for distributing water.''',
			profiles=[]
		)
