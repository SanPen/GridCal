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
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class Equipment(PowerSystemResource):
	def __init__(self, rdfid='', tpe='Equipment'):
		PowerSystemResource.__init__(self, rdfid, tpe)

		self.aggregate: bool = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.equipment_container import EquipmentContainer
		self.EquipmentContainer: EquipmentContainer | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.operational_limit_set import OperationalLimitSet
		self.OperationalLimitSet: OperationalLimitSet | None = None

		self.register_property(
			name='aggregate',
			class_type=bool,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The single instance of equipment represents multiple pieces of equipment that have been modeled together as an aggregate.  Examples would be power transformers or synchronous machines operating in parallel modeled as a single aggregate power transformer or aggregate synchronous machine.  This is not to be used to indicate equipment that is part of a group of interdependent equipment produced by a network production program.  ''',
			profiles=[]
		)
		self.register_property(
			name='EquipmentContainer',
			class_type=EquipmentContainer,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Container of this equipment.''',
			profiles=[]
		)
		self.register_property(
			name='OperationalLimitSet',
			class_type=OperationalLimitSet,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The operational limit sets associated with this equipment.''',
			profiles=[]
		)
