# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

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
