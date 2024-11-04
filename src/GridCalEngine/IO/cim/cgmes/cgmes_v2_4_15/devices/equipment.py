# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

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
