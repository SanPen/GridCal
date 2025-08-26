# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.power_system_resource import PowerSystemResource
from GridCalEngine.IO.cim.cgmes.cgmes_enums import CgmesProfileType


class Equipment(PowerSystemResource):
	def __init__(self, rdfid='', tpe='Equipment'):
		PowerSystemResource.__init__(self, rdfid, tpe)

		self.aggregate: bool = None
		self.normallyInService: bool = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.equipment_container import EquipmentContainer
		self.EquipmentContainer: EquipmentContainer | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.operational_limit_set import OperationalLimitSet
		self.OperationalLimitSet: OperationalLimitSet | None = None
		self.inService: bool = None

		self.register_property(
			name='aggregate',
			class_type=bool,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The aggregate flag provides an alternative way of representing an aggregated (equivalent) element. It is applicable in cases when the dedicated classes for equivalent equipment do not have all of the attributes necessary to represent the required level of detail.  In case the flag is set to �true� the single instance of equipment represents multiple pieces of equipment that have been modelled together as an aggregate equivalent obtained by a network reduction procedure. Examples would be power transformers or synchronous machines operating in parallel modelled as a single aggregate power transformer or aggregate synchronous machine.  
The attribute is not used for EquivalentBranch, EquivalentShunt and EquivalentInjection.''' ,
			profiles=[]
		)
		self.register_property(
			name='normallyInService',
			class_type=bool,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Specifies the availability of the equipment under normal operating conditions. True means the equipment is available for topology processing, which determines if the equipment is energized or not. False means that the equipment is treated by network applications as if it is not in the model.''',
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
		self.register_property(
			name='inService',
			class_type=bool,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Specifies the availability of the equipment. True means the equipment is available for topology processing, which determines if the equipment is energized or not. False means that the equipment is treated by network applications as if it is not in the model.''',
			profiles=[]
		)
