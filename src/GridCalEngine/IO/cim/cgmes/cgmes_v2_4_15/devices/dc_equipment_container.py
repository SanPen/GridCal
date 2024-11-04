# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.equipment_container import EquipmentContainer
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class DCEquipmentContainer(EquipmentContainer):
	def __init__(self, rdfid='', tpe='DCEquipmentContainer'):
		EquipmentContainer.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.dc_node import DCNode
		self.DCNodes: DCNode | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.dc_topological_node import DCTopologicalNode
		self.DCTopologicalNode: DCTopologicalNode | None = None

		self.register_property(
			name='DCNodes',
			class_type=DCNode,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''None''',
			profiles=[]
		)
		self.register_property(
			name='DCTopologicalNode',
			class_type=DCTopologicalNode,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''None''',
			profiles=[]
		)
