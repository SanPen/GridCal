# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.regulating_cond_eq import RegulatingCondEq
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile, UnitSymbol


class ShuntCompensator(RegulatingCondEq):
	def __init__(self, rdfid='', tpe='ShuntCompensator'):
		RegulatingCondEq.__init__(self, rdfid, tpe)

		self.aVRDelay: float = None
		self.grounded: bool = None
		self.maximumSections: int = None
		self.nomU: float = None
		self.normalSections: int = None
		self.switchOnCount: int = None
		import datetime
		self.switchOnDate: datetime.datetime | None = None
		self.voltageSensitivity: float = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.sv_shunt_compensator_sections import SvShuntCompensatorSections
		self.SvShuntCompensatorSections: SvShuntCompensatorSections | None = None
		self.sections: float = None

		self.register_property(
			name='aVRDelay',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.s,
			description='''Time, in seconds.''',
			profiles=[]
		)
		self.register_property(
			name='grounded',
			class_type=bool,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Used for Yn and Zn connections. True if the neutral is solidly grounded.''',
			profiles=[]
		)
		self.register_property(
			name='maximumSections',
			class_type=int,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The maximum number of sections that may be switched in. ''',
			profiles=[]
		)
		self.register_property(
			name='nomU',
			class_type=float,
			multiplier=UnitMultiplier.k,
			unit=UnitSymbol.V,
			description='''Electrical voltage, can be both AC and DC.''',
			profiles=[]
		)
		self.register_property(
			name='normalSections',
			class_type=int,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The normal number of sections switched in.''',
			profiles=[]
		)
		self.register_property(
			name='switchOnCount',
			class_type=int,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The switch on count since the capacitor count was last reset or initialized.''',
			profiles=[]
		)
		self.register_property(
			name='switchOnDate',
			class_type=datetime.datetime,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The date and time when the capacitor bank was last switched on.''',
			profiles=[]
		)
		self.register_property(
			name='voltageSensitivity',
			class_type=float,
			multiplier=UnitMultiplier.k,
			unit=UnitSymbol.V,
			description='''Voltage variation with reactive power.''',
			profiles=[]
		)
		self.register_property(
			name='SvShuntCompensatorSections',
			class_type=SvShuntCompensatorSections,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The state for the number of shunt compensator sections in service.''',
			profiles=[]
		)
		self.register_property(
			name='sections',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''A floating point number. The range is unspecified and not limited.''',
			profiles=[]
		)
