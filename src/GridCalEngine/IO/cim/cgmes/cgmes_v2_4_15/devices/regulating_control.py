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
