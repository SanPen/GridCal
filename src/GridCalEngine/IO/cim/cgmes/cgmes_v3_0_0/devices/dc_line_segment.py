# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.dc_conducting_equipment import DCConductingEquipment
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile, UnitSymbol


class DCLineSegment(DCConductingEquipment):
	def __init__(self, rdfid='', tpe='DCLineSegment'):
		DCConductingEquipment.__init__(self, rdfid, tpe)

		self.capacitance: float = None
		self.inductance: float = None
		self.resistance: float = None
		self.length: float = None

		self.register_property(
			name='capacitance',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.F,
			description='''Capacitive part of reactance (imaginary part of impedance), at rated frequency.''',
			profiles=[]
		)
		self.register_property(
			name='inductance',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.H,
			description='''Inductive part of reactance (imaginary part of impedance), at rated frequency.''',
			profiles=[]
		)
		self.register_property(
			name='resistance',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.ohm,
			description='''Resistance (real part of impedance).''',
			profiles=[]
		)
		self.register_property(
			name='length',
			class_type=float,
			multiplier=UnitMultiplier.k,
			unit=UnitSymbol.m,
			description='''Unit of length. It shall be a positive value or zero.''',
			profiles=[]
		)
