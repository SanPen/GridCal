# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
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
