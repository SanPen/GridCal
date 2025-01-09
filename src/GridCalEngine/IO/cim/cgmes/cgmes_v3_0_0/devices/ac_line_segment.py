# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.conductor import Conductor
from GridCalEngine.IO.cim.cgmes.cgmes_enums import UnitSymbol


class ACLineSegment(Conductor):
	def __init__(self, rdfid='', tpe='ACLineSegment'):
		Conductor.__init__(self, rdfid, tpe)

		self.bch: float = None
		self.gch: float = None
		self.r: float = None
		self.x: float = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.clamp import Clamp
		self.Clamp: Clamp | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.cut import Cut
		self.Cut: Cut | None = None
		self.b0ch: float = None
		self.g0ch: float = None
		self.r0: float = None
		self.shortCircuitEndTemperature: float = None
		self.x0: float = None

		self.register_property(
			name='bch',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.S,
			description='''Imaginary part of admittance.''',
			profiles=[]
		)
		self.register_property(
			name='gch',
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
			name='x',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.ohm,
			description='''Reactance (imaginary part of impedance), at rated frequency.''',
			profiles=[]
		)
		self.register_property(
			name='Clamp',
			class_type=Clamp,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The clamps connected to the line segment.''',
			profiles=[]
		)
		self.register_property(
			name='Cut',
			class_type=Cut,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Cuts applied to the line segment.''',
			profiles=[]
		)
		self.register_property(
			name='b0ch',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.S,
			description='''Imaginary part of admittance.''',
			profiles=[]
		)
		self.register_property(
			name='g0ch',
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
			name='shortCircuitEndTemperature',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.degC,
			description='''Value of temperature in degrees Celsius.''',
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
