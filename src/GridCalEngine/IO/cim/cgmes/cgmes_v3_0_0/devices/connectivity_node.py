# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class ConnectivityNode(IdentifiedObject):
	def __init__(self, rdfid='', tpe='ConnectivityNode'):
		IdentifiedObject.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.boundary_point import BoundaryPoint
		self.BoundaryPoint: BoundaryPoint | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.terminal import Terminal
		self.Terminals: Terminal | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.connectivity_node_container import ConnectivityNodeContainer
		self.ConnectivityNodeContainer: ConnectivityNodeContainer | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.topological_node import TopologicalNode
		self.TopologicalNode: TopologicalNode | None = None

		self.register_property(
			name='BoundaryPoint',
			class_type=BoundaryPoint,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The boundary point associated with the connectivity node.''',
			profiles=[]
		)
		self.register_property(
			name='Terminals',
			class_type=Terminal,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Terminals interconnected with zero impedance at a this connectivity node. ''',
			profiles=[]
		)
		self.register_property(
			name='ConnectivityNodeContainer',
			class_type=ConnectivityNodeContainer,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Container of this connectivity node.''',
			profiles=[]
		)
		self.register_property(
			name='TopologicalNode',
			class_type=TopologicalNode,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The topological node to which this connectivity node is assigned.  May depend on the current state of switches in the network.''',
			profiles=[]
		)
