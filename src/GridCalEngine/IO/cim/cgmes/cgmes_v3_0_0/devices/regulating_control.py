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
