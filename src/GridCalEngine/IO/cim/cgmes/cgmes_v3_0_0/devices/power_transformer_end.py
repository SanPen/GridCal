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
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile, WindingConnection, UnitSymbol


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
		self.b0: float = None
		self.phaseAngleClock: int = None
		self.g0: float = None
		self.r0: float = None
		self.x0: float = None

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
		self.register_property(
			name='b0',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.S,
			description='''Imaginary part of admittance.''',
			profiles=[]
		)
		self.register_property(
			name='phaseAngleClock',
			class_type=int,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Terminal voltage phase angle displacement where 360 degrees are represented with clock hours. The valid values are 0 to 11. For example, for the secondary side end of a transformer with vector group code of 'Dyn11', specify the connection kind as wye with neutral and specify the phase angle of the clock as 11.  The clock value of the transformer end number specified as 1, is assumed to be zero.  Note the transformer end number is not assumed to be the same as the terminal sequence number.''',
			profiles=[]
		)
		self.register_property(
			name='g0',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.S,
			description='''Factor by which voltage must be multiplied to give corresponding power lost from a circuit. Real part of admittance.''',
			profiles=[]
		)
		self.register_property(
			name='r0',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.ohm,
			description='''Resistance (real part of impedance).''',
			profiles=[]
		)
		self.register_property(
			name='x0',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.ohm,
			description='''Reactance (imaginary part of impedance), at rated frequency.''',
			profiles=[]
		)
