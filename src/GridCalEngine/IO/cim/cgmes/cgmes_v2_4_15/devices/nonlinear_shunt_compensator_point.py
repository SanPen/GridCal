# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.base import Base
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile, UnitSymbol


class NonlinearShuntCompensatorPoint(Base):
	def __init__(self, rdfid, tpe='NonlinearShuntCompensatorPoint', resources=list(), class_replacements=dict()):
		Base.__init__(self, rdfid=rdfid, tpe=tpe, resources=resources, class_replacements=class_replacements)

		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.nonlinear_shunt_compensator import NonlinearShuntCompensator
		self.NonlinearShuntCompensator: NonlinearShuntCompensator | None = None
		self.b: float = None
		self.b0: float = None
		self.g: float = None
		self.g0: float = None
		self.sectionNumber: int = None

		self.register_property(
			name='NonlinearShuntCompensator',
			class_type=NonlinearShuntCompensator,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Non-linear shunt compensator owning this point.''',
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
			name='b0',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.S,
			description='''Imaginary part of admittance.''',
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
			name='g0',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.S,
			description='''Factor by which voltage must be multiplied to give corresponding power lost from a circuit. Real part of admittance.''',
			profiles=[]
		)
		self.register_property(
			name='sectionNumber',
			class_type=int,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The number of the section.''',
			profiles=[]
		)
