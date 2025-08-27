# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from VeraGridEngine.IO.base.units import UnitMultiplier, UnitSymbol
from VeraGridEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.earth_fault_compensator import EarthFaultCompensator
from VeraGridEngine.IO.cim.cgmes.cgmes_enums import CgmesProfileType, UnitSymbol


class GroundingImpedance(EarthFaultCompensator):
	def __init__(self, rdfid='', tpe='GroundingImpedance'):
		EarthFaultCompensator.__init__(self, rdfid, tpe)

		self.x: float = None

		self.register_property(
			name='x',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.ohm,
			description='''Reactance (imaginary part of impedance), at rated frequency.''',
			profiles=[]
		)
