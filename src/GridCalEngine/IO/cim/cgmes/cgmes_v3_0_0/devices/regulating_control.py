# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.power_system_resource import PowerSystemResource
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile, UnitMultiplier, RegulatingControlModeKind


class RegulatingControl(PowerSystemResource):
	def __init__(self, rdfid='', tpe='RegulatingControl'):
		PowerSystemResource.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.regulating_cond_eq import RegulatingCondEq
		self.RegulatingCondEq: RegulatingCondEq | None = None
		self.mode: RegulatingControlModeKind = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.terminal import Terminal
		self.Terminal: Terminal | None = None
		self.discrete: bool = None
		self.enabled: bool = None
		self.targetDeadband: float = None
		self.targetValue: float = None
		self.targetValueUnitMultiplier: UnitMultiplier = None
		self.maxAllowedTargetValue: float = None
		self.minAllowedTargetValue: float = None

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
			name='Terminal',
			class_type=Terminal,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The terminal associated with this regulating control.  The terminal is associated instead of a node, since the terminal could connect into either a topological node or a connectivity node.  Sometimes it is useful to model regulation at a terminal of a bus bar object. ''',
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
			description='''This is a deadband used with discrete control to avoid excessive update of controls like tap changers and shunt compensator banks while regulating.  The units of those appropriate for the mode. The attribute shall be a positive value or zero. If RegulatingControl.discrete is set to "false", the RegulatingControl.targetDeadband is to be ignored.
Note that for instance, if the targetValue is 100 kV and the targetDeadband is 2 kV the range is from 99 to 101 kV.''',
			profiles=[]
		)
		self.register_property(
			name='targetValue',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The target value specified for case input.   This value can be used for the target value without the use of schedules. The value has the units appropriate to the mode attribute.''',
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
		self.register_property(
			name='maxAllowedTargetValue',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Maximum allowed target value (RegulatingControl.targetValue).''',
			profiles=[]
		)
		self.register_property(
			name='minAllowedTargetValue',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Minimum allowed target value (RegulatingControl.targetValue).''',
			profiles=[]
		)
