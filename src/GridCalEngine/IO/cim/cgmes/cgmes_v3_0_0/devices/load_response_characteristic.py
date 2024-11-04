# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

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
