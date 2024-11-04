# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class DCNode(IdentifiedObject):
	def __init__(self, rdfid='', tpe='DCNode'):
		IdentifiedObject.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.dc_base_terminal import DCBaseTerminal
		self.DCTerminals: DCBaseTerminal | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.dc_equipment_container import DCEquipmentContainer
		self.DCEquipmentContainer: DCEquipmentContainer | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.dc_topological_node import DCTopologicalNode
		self.DCTopologicalNode: DCTopologicalNode | None = None

		self.register_property(
			name='DCTerminals',
			class_type=DCBaseTerminal,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''DC base terminals interconnected with zero impedance at a this DC connectivity node. ''',
			profiles=[]
		)
		self.register_property(
			name='DCEquipmentContainer',
			class_type=DCEquipmentContainer,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The DC container for the DC nodes.''',
			profiles=[]
		)
		self.register_property(
			name='DCTopologicalNode',
			class_type=DCTopologicalNode,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The DC topological node to which this DC connectivity node is assigned.  May depend on the current state of switches in the network.''',
			profiles=[]
		)
