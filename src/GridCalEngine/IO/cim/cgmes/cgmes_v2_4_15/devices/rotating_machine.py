# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.regulating_cond_eq import RegulatingCondEq
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile, UnitSymbol


class RotatingMachine(RegulatingCondEq):
	def __init__(self, rdfid='', tpe='RotatingMachine'):
		RegulatingCondEq.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.generating_unit import GeneratingUnit
		self.GeneratingUnit: GeneratingUnit | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.hydro_pump import HydroPump
		self.HydroPump: HydroPump | None = None
		self.ratedPowerFactor: float = None
		self.ratedS: float = None
		self.ratedU: float = None
		self.p: float = None
		self.q: float = None

		self.register_property(
			name='GeneratingUnit',
			class_type=GeneratingUnit,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''A synchronous machine may operate as a generator and as such becomes a member of a generating unit.''',
			profiles=[]
		)
		self.register_property(
			name='HydroPump',
			class_type=HydroPump,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The synchronous machine drives the turbine which moves the water from a low elevation to a higher elevation. The direction of machine rotation for pumping may or may not be the same as for generating.''',
			profiles=[]
		)
		self.register_property(
			name='ratedPowerFactor',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''A floating point number. The range is unspecified and not limited.''',
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
			name='ratedU',
			class_type=float,
			multiplier=UnitMultiplier.k,
			unit=UnitSymbol.V,
			description='''Electrical voltage, can be both AC and DC.''',
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
