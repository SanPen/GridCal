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
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile, FuelType


class FossilFuel(IdentifiedObject):
	def __init__(self, rdfid='', tpe='FossilFuel'):
		IdentifiedObject.__init__(self, rdfid, tpe)

		self.fossilFuelType: FuelType = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.thermal_generating_unit import ThermalGeneratingUnit
		self.ThermalGeneratingUnit: ThermalGeneratingUnit | None = None

		self.register_property(
			name='fossilFuelType',
			class_type=FuelType,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The type of fossil fuel, such as coal, oil, or gas.''',
			profiles=[]
		)
		self.register_property(
			name='ThermalGeneratingUnit',
			class_type=ThermalGeneratingUnit,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''A thermal generating unit may have one or more fossil fuels.''',
			profiles=[]
		)
