# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.regulating_cond_eq import RegulatingCondEq
from GridCalEngine.IO.cim.cgmes.cgmes_enums import CgmesProfileType, UnitSymbol


class ExternalNetworkInjection(RegulatingCondEq):
	def __init__(self, rdfid='', tpe='ExternalNetworkInjection'):
		RegulatingCondEq.__init__(self, rdfid, tpe)

		self.governorSCD: float = None
		self.maxP: float = None
		self.maxQ: float = None
		self.minP: float = None
		self.minQ: float = None
		self.ikSecond: bool = None
		self.maxInitialSymShCCurrent: float = None
		self.maxR0ToX0Ratio: float = None
		self.maxR1ToX1Ratio: float = None
		self.maxZ0ToZ1Ratio: float = None
		self.minInitialSymShCCurrent: float = None
		self.minR0ToX0Ratio: float = None
		self.minR1ToX1Ratio: float = None
		self.minZ0ToZ1Ratio: float = None
		self.voltageFactor: float = None
		self.referencePriority: int = None
		self.p: float = None
		self.q: float = None

		self.register_property(
			name='governorSCD',
			class_type=float,
			multiplier=UnitMultiplier.M,
			unit=UnitSymbol.WPers,
			description='''Active power variation with frequency.''',
			profiles=[]
		)
		self.register_property(
			name='maxP',
			class_type=float,
			multiplier=UnitMultiplier.M,
			unit=UnitSymbol.W,
			description='''Product of RMS value of the voltage and the RMS value of the in-phase component of the current.''',
			profiles=[]
		)
		self.register_property(
			name='maxQ',
			class_type=float,
			multiplier=UnitMultiplier.M,
			unit=UnitSymbol.VAr,
			description='''Product of RMS value of the voltage and the RMS value of the quadrature component of the current.''',
			profiles=[]
		)
		self.register_property(
			name='minP',
			class_type=float,
			multiplier=UnitMultiplier.M,
			unit=UnitSymbol.W,
			description='''Product of RMS value of the voltage and the RMS value of the in-phase component of the current.''',
			profiles=[]
		)
		self.register_property(
			name='minQ',
			class_type=float,
			multiplier=UnitMultiplier.M,
			unit=UnitSymbol.VAr,
			description='''Product of RMS value of the voltage and the RMS value of the quadrature component of the current.''',
			profiles=[]
		)
		self.register_property(
			name='ikSecond',
			class_type=bool,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Indicates whether initial symmetrical short-circuit current and power have been calculated according to IEC (Ik").  Used only if short circuit calculations are done according to superposition method.''',
			profiles=[]
		)
		self.register_property(
			name='maxInitialSymShCCurrent',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.A,
			description='''Electrical current with sign convention: positive flow is out of the conducting equipment into the connectivity node. Can be both AC and DC.''',
			profiles=[]
		)
		self.register_property(
			name='maxR0ToX0Ratio',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Maximum ratio of zero sequence resistance of Network Feeder to its zero sequence reactance (R(0)/X(0) max). Used for short circuit data exchange according to IEC 60909.''',
			profiles=[]
		)
		self.register_property(
			name='maxR1ToX1Ratio',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Maximum ratio of positive sequence resistance of Network Feeder to its positive sequence reactance (R(1)/X(1) max). Used for short circuit data exchange according to IEC 60909.''',
			profiles=[]
		)
		self.register_property(
			name='maxZ0ToZ1Ratio',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Maximum ratio of zero sequence impedance to its positive sequence impedance (Z(0)/Z(1) max). Used for short circuit data exchange according to IEC 60909.''',
			profiles=[]
		)
		self.register_property(
			name='minInitialSymShCCurrent',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.A,
			description='''Electrical current with sign convention: positive flow is out of the conducting equipment into the connectivity node. Can be both AC and DC.''',
			profiles=[]
		)
		self.register_property(
			name='minR0ToX0Ratio',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Indicates whether initial symmetrical short-circuit current and power have been calculated according to IEC (Ik"). Used for short circuit data exchange according to IEC 6090.''',
			profiles=[]
		)
		self.register_property(
			name='minR1ToX1Ratio',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Minimum ratio of positive sequence resistance of Network Feeder to its positive sequence reactance (R(1)/X(1) min). Used for short circuit data exchange according to IEC 60909.''',
			profiles=[]
		)
		self.register_property(
			name='minZ0ToZ1Ratio',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Minimum ratio of zero sequence impedance to its positive sequence impedance (Z(0)/Z(1) min). Used for short circuit data exchange according to IEC 60909.''',
			profiles=[]
		)
		self.register_property(
			name='voltageFactor',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Per Unit - a positive or negative value referred to a defined base. Values typically range from -10 to +10.''',
			profiles=[]
		)
		self.register_property(
			name='referencePriority',
			class_type=int,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Priority of unit for use as powerflow voltage phase angle reference bus selection. 0 = don t care (default) 1 = highest priority. 2 is less than 1 and so on.''',
			profiles=[]
		)
		self.register_property(
			name='p',
			class_type=float,
			multiplier=UnitMultiplier.M,
			unit=UnitSymbol.W,
			description='''Product of RMS value of the voltage and the RMS value of the in-phase component of the current.''',
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
