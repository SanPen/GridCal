# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.power_electronics_unit import PowerElectronicsUnit
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile, BatteryStateKind, UnitSymbol


class BatteryUnit(PowerElectronicsUnit):
	def __init__(self, rdfid='', tpe='BatteryUnit'):
		PowerElectronicsUnit.__init__(self, rdfid, tpe)

		self.ratedE: float = None
		self.batteryState: BatteryStateKind = None
		self.storedE: float = None

		self.register_property(
			name='ratedE',
			class_type=float,
			multiplier=UnitMultiplier.M,
			unit=UnitSymbol.Wh,
			description='''Real electrical energy.''',
			profiles=[]
		)
		self.register_property(
			name='batteryState',
			class_type=BatteryStateKind,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The current state of the battery (charging, full, etc.).''',
			profiles=[]
		)
		self.register_property(
			name='storedE',
			class_type=float,
			multiplier=UnitMultiplier.M,
			unit=UnitSymbol.Wh,
			description='''Real electrical energy.''',
			profiles=[]
		)
