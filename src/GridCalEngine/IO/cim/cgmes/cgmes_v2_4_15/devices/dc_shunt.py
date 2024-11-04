# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.dc_conducting_equipment import DCConductingEquipment
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile, UnitSymbol


class DCShunt(DCConductingEquipment):
	def __init__(self, rdfid='', tpe='DCShunt'):
		DCConductingEquipment.__init__(self, rdfid, tpe)

		self.capacitance: float = None
		self.resistance: float = None
		self.ratedUdc: float = None

		self.register_property(
			name='capacitance',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.F,
			description='''Capacitive part of reactance (imaginary part of impedance), at rated frequency.''',
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
			name='ratedUdc',
			class_type=float,
			multiplier=UnitMultiplier.k,
			unit=UnitSymbol.V,
			description='''Electrical voltage, can be both AC and DC.''',
			profiles=[]
		)
