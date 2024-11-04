# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.regulating_cond_eq import RegulatingCondEq
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile, UnitSymbol, SVCControlMode


class StaticVarCompensator(RegulatingCondEq):
	def __init__(self, rdfid='', tpe='StaticVarCompensator'):
		RegulatingCondEq.__init__(self, rdfid, tpe)

		self.capacitiveRating: float = None
		self.inductiveRating: float = None
		self.slope: float = None
		self.sVCControlMode: SVCControlMode = None
		self.voltageSetPoint: float = None
		self.q: float = None

		self.register_property(
			name='capacitiveRating',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.ohm,
			description='''Reactance (imaginary part of impedance), at rated frequency.''',
			profiles=[]
		)
		self.register_property(
			name='inductiveRating',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.ohm,
			description='''Reactance (imaginary part of impedance), at rated frequency.''',
			profiles=[]
		)
		self.register_property(
			name='slope',
			class_type=float,
			multiplier=UnitMultiplier.k,
			unit=UnitSymbol.V,
			description='''Voltage variation with reactive power.''',
			profiles=[]
		)
		self.register_property(
			name='sVCControlMode',
			class_type=SVCControlMode,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''SVC control mode.''',
			profiles=[]
		)
		self.register_property(
			name='voltageSetPoint',
			class_type=float,
			multiplier=UnitMultiplier.k,
			unit=UnitSymbol.V,
			description='''Electrical voltage, can be both AC and DC.''',
			profiles=[]
		)
		self.register_property(
			name='q',
			class_type=float,
			multiplier=UnitMultiplier.M,
			unit=UnitSymbol.VAr,
			description='''Product of RMS value of the voltage and the RMS value of the quadrature component of the current.''',
			profiles=[]
		)
