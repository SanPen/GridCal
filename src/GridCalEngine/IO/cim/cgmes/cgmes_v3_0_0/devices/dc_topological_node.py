# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class DCTopologicalNode(IdentifiedObject):
	def __init__(self, rdfid='', tpe='DCTopologicalNode'):
		IdentifiedObject.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.dc_topological_island import DCTopologicalIsland
		self.DCTopologicalIsland: DCTopologicalIsland | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.dc_base_terminal import DCBaseTerminal
		self.DCTerminals: DCBaseTerminal | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.dc_equipment_container import DCEquipmentContainer
		self.DCEquipmentContainer: DCEquipmentContainer | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.dc_node import DCNode
		self.DCNodes: DCNode | None = None

		self.register_property(
			name='DCTopologicalIsland',
			class_type=DCTopologicalIsland,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''A DC topological node belongs to a DC topological island.''',
			profiles=[]
		)
		self.register_property(
			name='DCTerminals',
			class_type=DCBaseTerminal,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''See association end TopologicalNode.Terminal.''',
			profiles=[]
		)
		self.register_property(
			name='DCEquipmentContainer',
			class_type=DCEquipmentContainer,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The connectivity node container to which the topological node belongs.''',
			profiles=[]
		)
		self.register_property(
			name='DCNodes',
			class_type=DCNode,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The DC connectivity nodes combined together to form this DC topological node.  May depend on the current state of switches in the network.''',
			profiles=[]
		)
