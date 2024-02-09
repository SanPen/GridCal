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
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.generating_unit import GeneratingUnit
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile, WindGenUnitKind


class WindGeneratingUnit(GeneratingUnit):
	def __init__(self, rdfid='', tpe='WindGeneratingUnit'):
		GeneratingUnit.__init__(self, rdfid, tpe)

		self.windGenUnitType: WindGenUnitKind = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.wind_power_plant import WindPowerPlant
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
