# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.transformer_end import TransformerEnd
from GridCalEngine.IO.cim.cgmes.cgmes_enums import CgmesProfileType, UnitSymbol, WindingConnection


class PowerTransformerEnd(TransformerEnd):
	def __init__(self, rdfid='', tpe='PowerTransformerEnd'):
		TransformerEnd.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.power_transformer import PowerTransformer
		self.PowerTransformer: PowerTransformer | None = None
		self.b: float = None
		self.connectionKind: WindingConnection = None
		self.b0: float = None
		self.phaseAngleClock: int = None
		self.ratedS: float = None
		self.g: float = None
		self.ratedU: float = None
		self.g0: float = None
		self.r: float = None
		self.r0: float = None
		self.x: float = None
		self.x0: float = None

		self.register_property(
			name='PowerTransformer',
			class_type=PowerTransformer,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The ends of this power transformer.''',
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
			name='g0',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.S,
			description='''Factor by which voltage must be multiplied to give corresponding power lost from a circuit. Real part of admittance.''',
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
			name='r0',
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
			name='x0',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.ohm,
			description='''Reactance (imaginary part of impedance), at rated frequency.''',
			profiles=[]
		)
