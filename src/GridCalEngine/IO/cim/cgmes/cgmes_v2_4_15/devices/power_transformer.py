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
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.conducting_equipment import ConductingEquipment
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile, UnitSymbol


class PowerTransformer(ConductingEquipment):
	def __init__(self, rdfid='', tpe='PowerTransformer'):
		ConductingEquipment.__init__(self, rdfid, tpe)

		self.beforeShCircuitHighestOperatingCurrent: float = None
		self.beforeShCircuitHighestOperatingVoltage: float = None
		self.beforeShortCircuitAnglePf: float = None
		self.highSideMinOperatingU: float = None
		self.isPartOfGeneratorUnit: bool = None
		self.operationalValuesConsidered: bool = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.power_transformer_end import PowerTransformerEnd
		self.PowerTransformerEnd: PowerTransformerEnd | None = None

		self.register_property(
			name='beforeShCircuitHighestOperatingCurrent',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.A,
			description='''Electrical current with sign convention: positive flow is out of the conducting equipment into the connectivity node. Can be both AC and DC.''',
			profiles=[]
		)
		self.register_property(
			name='beforeShCircuitHighestOperatingVoltage',
			class_type=float,
			multiplier=UnitMultiplier.k,
			unit=UnitSymbol.V,
			description='''Electrical voltage, can be both AC and DC.''',
			profiles=[]
		)
		self.register_property(
			name='beforeShortCircuitAnglePf',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.deg,
			description='''Measurement of angle in degrees.''',
			profiles=[]
		)
		self.register_property(
			name='highSideMinOperatingU',
			class_type=float,
			multiplier=UnitMultiplier.k,
			unit=UnitSymbol.V,
			description='''Electrical voltage, can be both AC and DC.''',
			profiles=[]
		)
		self.register_property(
			name='isPartOfGeneratorUnit',
			class_type=bool,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Indicates whether the machine is part of a power station unit. Used for short circuit data exchange according to IEC 60909''',
			profiles=[]
		)
		self.register_property(
			name='operationalValuesConsidered',
			class_type=bool,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''It is used to define if the data (other attributes related to short circuit data exchange) defines long term operational conditions or not. Used for short circuit data exchange according to IEC 60909.''',
			profiles=[]
		)
		self.register_property(
			name='PowerTransformerEnd',
			class_type=PowerTransformerEnd,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The power transformer of this power transformer end.''',
			profiles=[]
		)
