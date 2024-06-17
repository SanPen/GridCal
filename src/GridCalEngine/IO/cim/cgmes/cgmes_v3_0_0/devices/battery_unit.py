# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
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
