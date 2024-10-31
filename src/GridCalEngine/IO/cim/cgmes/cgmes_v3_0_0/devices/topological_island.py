# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class TopologicalIsland(IdentifiedObject):
	def __init__(self, rdfid='', tpe='TopologicalIsland'):
		IdentifiedObject.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.topological_node import TopologicalNode
		self.AngleRefTopologicalNode: TopologicalNode | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.topological_node import TopologicalNode
		self.TopologicalNodes: TopologicalNode | None = None

		self.register_property(
			name='AngleRefTopologicalNode',
			class_type=TopologicalNode,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The angle reference for the island.   Normally there is one TopologicalNode that is selected as the angle reference for each island.   Other reference schemes exist, so the association is typically optional.''',
			profiles=[]
		)
		self.register_property(
			name='TopologicalNodes',
			class_type=TopologicalNode,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''A topological node belongs to a topological island.''',
			profiles=[]
		)
