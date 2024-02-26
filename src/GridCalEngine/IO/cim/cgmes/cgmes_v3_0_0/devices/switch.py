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
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.conducting_equipment import ConductingEquipment
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile, UnitSymbol


class Switch(ConductingEquipment):
	def __init__(self, rdfid='', tpe='Switch'):
		ConductingEquipment.__init__(self, rdfid, tpe)

		self.normalOpen: bool = None
		self.ratedCurrent: float = None
		self.retained: bool = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.sv_switch import SvSwitch
		self.SvSwitch: SvSwitch | None = None
		self.open: bool = None
		self.locked: bool = None

		self.register_property(
			name='normalOpen',
			class_type=bool,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The attribute is used in cases when no Measurement for the status value is present. If the Switch has a status measurement the Discrete.normalValue is expected to match with the Switch.normalOpen.''',
			profiles=[]
		)
		self.register_property(
			name='ratedCurrent',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.A,
			description='''Electrical current with sign convention: positive flow is out of the conducting equipment into the connectivity node. Can be both AC and DC.''',
			profiles=[]
		)
		self.register_property(
			name='retained',
			class_type=bool,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Branch is retained in the topological solution.  The flow through retained switches will normally be calculated in power flow.''',
			profiles=[]
		)
		self.register_property(
			name='SvSwitch',
			class_type=SvSwitch,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The switch state associated with the switch.''',
			profiles=[]
		)
		self.register_property(
			name='open',
			class_type=bool,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The attribute tells if the switch is considered open when used as input to topology processing.''',
			profiles=[]
		)
		self.register_property(
			name='locked',
			class_type=bool,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''If true, the switch is locked. The resulting switch state is a combination of locked and Switch.open attributes as follows:
<ul>
	<li>locked=true and Switch.open=true. The resulting state is open and locked;</li>
	<li>locked=false and Switch.open=true. The resulting state is open;</li>
	<li>locked=false and Switch.open=false. The resulting state is closed.</li>
</ul>''',
			profiles=[]
		)
