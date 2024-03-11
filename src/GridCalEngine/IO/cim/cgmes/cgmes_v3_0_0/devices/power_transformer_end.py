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
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.transformer_end import TransformerEnd
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile, UnitSymbol, WindingConnection


class PowerTransformerEnd(TransformerEnd):
	def __init__(self, rdfid='', tpe='PowerTransformerEnd'):
		TransformerEnd.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.power_transformer import PowerTransformer
		self.PowerTransformer: PowerTransformer | None = None
		self.b: float = None
		self.connectionKind: WindingConnection = None
		self.ratedS: float = None
		self.g: float = None
		self.ratedU: float = None
		self.r: float = None
		self.x: float = None

		self.register_property(
			name='PowerTransformer',
			class_type=PowerTransformer,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The power transformer of this power transformer end.''',
			profiles=[]
		)
		self.register_property(
			name='b',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.S,
			description='''Imaginary part of admittance.''',
			profiles=[]
		)
		self.register_property(
			name='connectionKind',
			class_type=WindingConnection,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Kind of connection.''',
			profiles=[]
		)
		self.register_property(
			name='ratedS',
			class_type=float,
			multiplier=UnitMultiplier.M,
			unit=UnitSymbol.VA,
			description='''Product of the RMS value of the voltage and the RMS value of the current.''',
			profiles=[]
		)
		self.register_property(
			name='g',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.S,
			description='''Factor by which voltage must be multiplied to give corresponding power lost from a circuit. Real part of admittance.''',
			profiles=[]
		)
		self.register_property(
			name='ratedU',
			class_type=float,
			multiplier=UnitMultiplier.k,
			unit=UnitSymbol.V,
			description='''Electrical voltage, can be both AC and DC.''',
			profiles=[]
		)
		self.register_property(
			name='r',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.ohm,
			description='''Resistance (real part of impedance).''',
			profiles=[]
		)
		self.register_property(
			name='x',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.ohm,
			description='''Reactance (imaginary part of impedance), at rated frequency.''',
			profiles=[]
		)
