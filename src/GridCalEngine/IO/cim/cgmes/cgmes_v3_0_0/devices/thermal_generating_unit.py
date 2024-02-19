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
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class ThermalGeneratingUnit(GeneratingUnit):
	def __init__(self, rdfid='', tpe='ThermalGeneratingUnit'):
		GeneratingUnit.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.caes_plant import CAESPlant
		self.CAESPlant: CAESPlant | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.cogeneration_plant import CogenerationPlant
		self.CogenerationPlant: CogenerationPlant | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.combined_cycle_plant import CombinedCyclePlant
		self.CombinedCyclePlant: CombinedCyclePlant | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.fossil_fuel import FossilFuel
		self.FossilFuels: FossilFuel | None = None

		self.register_property(
			name='CAESPlant',
			class_type=CAESPlant,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''A thermal generating unit may be a member of a compressed air energy storage plant.''',
			profiles=[]
		)
		self.register_property(
			name='CogenerationPlant',
			class_type=CogenerationPlant,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''A thermal generating unit may be a member of a cogeneration plant.''',
			profiles=[]
		)
		self.register_property(
			name='CombinedCyclePlant',
			class_type=CombinedCyclePlant,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''A thermal generating unit may be a member of a combined cycle plant.''',
			profiles=[]
		)
		self.register_property(
			name='FossilFuels',
			class_type=FossilFuel,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''A thermal generating unit may have one or more fossil fuels.''',
			profiles=[]
		)
