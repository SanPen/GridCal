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
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class LoadResponseCharacteristic(IdentifiedObject):
	def __init__(self, rdfid='', tpe='LoadResponseCharacteristic'):
		IdentifiedObject.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.energy_consumer import EnergyConsumer
		self.EnergyConsumer: EnergyConsumer | None = None
		self.exponentModel: bool = None
		self.pConstantCurrent: float = None
		self.pConstantImpedance: float = None
		self.pConstantPower: float = None
		self.pFrequencyExponent: float = None
		self.pVoltageExponent: float = None
		self.qConstantCurrent: float = None
		self.qConstantImpedance: float = None
		self.qConstantPower: float = None
		self.qFrequencyExponent: float = None
		self.qVoltageExponent: float = None

		self.register_property(
			name='EnergyConsumer',
			class_type=EnergyConsumer,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The set of loads that have the response characteristics.''',
			profiles=[]
		)
		self.register_property(
			name='exponentModel',
			class_type=bool,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Indicates the exponential voltage dependency model is to be used. If false, the coefficient model is to be used.
The exponential voltage dependency model consist of the attributes:
- pVoltageExponent
- qVoltageExponent
- pFrequencyExponent
- qFrequencyExponent.
The coefficient model consist of the attributes:
- pConstantImpedance
- pConstantCurrent
- pConstantPower
- qConstantImpedance
- qConstantCurrent
- qConstantPower.
The sum of pConstantImpedance, pConstantCurrent and pConstantPower shall equal 1.
The sum of qConstantImpedance, qConstantCurrent and qConstantPower shall equal 1.''',
			profiles=[]
		)
		self.register_property(
			name='pConstantCurrent',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Portion of active power load modelled as constant current.''',
			profiles=[]
		)
		self.register_property(
			name='pConstantImpedance',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Portion of active power load modelled as constant impedance.''',
			profiles=[]
		)
		self.register_property(
			name='pConstantPower',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Portion of active power load modelled as constant power.''',
			profiles=[]
		)
		self.register_property(
			name='pFrequencyExponent',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Exponent of per unit frequency effecting active power.''',
			profiles=[]
		)
		self.register_property(
			name='pVoltageExponent',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Exponent of per unit voltage effecting real power.''',
			profiles=[]
		)
		self.register_property(
			name='qConstantCurrent',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Portion of reactive power load modelled as constant current.''',
			profiles=[]
		)
		self.register_property(
			name='qConstantImpedance',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Portion of reactive power load modelled as constant impedance.''',
			profiles=[]
		)
		self.register_property(
			name='qConstantPower',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Portion of reactive power load modelled as constant power.''',
			profiles=[]
		)
		self.register_property(
			name='qFrequencyExponent',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Exponent of per unit frequency effecting reactive power.''',
			profiles=[]
		)
		self.register_property(
			name='qVoltageExponent',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Exponent of per unit voltage effecting reactive power.''',
			profiles=[]
		)
