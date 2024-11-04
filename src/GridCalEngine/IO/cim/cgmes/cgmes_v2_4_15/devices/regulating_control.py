# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.power_system_resource import PowerSystemResource
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile, RegulatingControlModeKind, UnitMultiplier


class RegulatingControl(PowerSystemResource):
	def __init__(self, rdfid='', tpe='RegulatingControl'):
		PowerSystemResource.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.terminal import Terminal
		self.Terminal: Terminal | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.regulating_cond_eq import RegulatingCondEq
		self.RegulatingCondEq: RegulatingCondEq | None = None
		self.mode: RegulatingControlModeKind = None
		self.discrete: bool = None
		self.enabled: bool = None
		self.targetDeadband: float = None
		self.targetValue: float = None
		self.targetValueUnitMultiplier: UnitMultiplier = None

		self.register_property(
			name='Terminal',
			class_type=Terminal,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The controls regulating this terminal.''',
			profiles=[]
		)
		self.register_property(
			name='RegulatingCondEq',
			class_type=RegulatingCondEq,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The equipment that participates in this regulating control scheme.''',
			profiles=[]
		)
		self.register_property(
			name='mode',
			class_type=RegulatingControlModeKind,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The regulating control mode presently available.  This specification allows for determining the kind of regulation without need for obtaining the units from a schedule.''',
			profiles=[]
		)
		self.register_property(
			name='discrete',
			class_type=bool,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The regulation is performed in a discrete mode. This applies to equipment with discrete controls, e.g. tap changers and shunt compensators.''',
			profiles=[]
		)
		self.register_property(
			name='enabled',
			class_type=bool,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The flag tells if regulation is enabled.''',
			profiles=[]
		)
		self.register_property(
			name='targetDeadband',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''A floating point number. The range is unspecified and not limited.''',
			profiles=[]
		)
		self.register_property(
			name='targetValue',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''A floating point number. The range is unspecified and not limited.''',
			profiles=[]
		)
		self.register_property(
			name='targetValueUnitMultiplier',
			class_type=UnitMultiplier,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Specify the multiplier for used for the targetValue.''',
			profiles=[]
		)
