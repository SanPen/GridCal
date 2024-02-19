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
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class TopologicalNode(IdentifiedObject):
	def __init__(self, rdfid='', tpe='TopologicalNode'):
		IdentifiedObject.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.sv_injection import SvInjection
		self.SvInjection: SvInjection | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.sv_voltage import SvVoltage
		self.SvVoltage: SvVoltage | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.topological_island import TopologicalIsland
		self.AngleRefTopologicalIsland: TopologicalIsland | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.topological_island import TopologicalIsland
		self.TopologicalIsland: TopologicalIsland | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.base_voltage import BaseVoltage
		self.BaseVoltage: BaseVoltage | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.connectivity_node import ConnectivityNode
		self.ConnectivityNodes: ConnectivityNode | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.connectivity_node_container import ConnectivityNodeContainer
		self.ConnectivityNodeContainer: ConnectivityNodeContainer | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.reporting_group import ReportingGroup
		self.ReportingGroup: ReportingGroup | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.terminal import Terminal
		self.Terminal: Terminal | None = None

		self.register_property(
			name='SvInjection',
			class_type=SvInjection,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The topological node associated with the flow injection state variable.''',
			profiles=[]
		)
		self.register_property(
			name='SvVoltage',
			class_type=SvVoltage,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The topological node associated with the voltage state.''',
			profiles=[]
		)
		self.register_property(
			name='AngleRefTopologicalIsland',
			class_type=TopologicalIsland,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The island for which the node is an angle reference.   Normally there is one angle reference node for each island.''',
			profiles=[]
		)
		self.register_property(
			name='TopologicalIsland',
			class_type=TopologicalIsland,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''A topological node belongs to a topological island.''',
			profiles=[]
		)
		self.register_property(
			name='BaseVoltage',
			class_type=BaseVoltage,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The base voltage of the topologocial node.''',
			profiles=[]
		)
		self.register_property(
			name='ConnectivityNodes',
			class_type=ConnectivityNode,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The topological node to which this connectivity node is assigned.  May depend on the current state of switches in the network.''',
			profiles=[]
		)
		self.register_property(
			name='ConnectivityNodeContainer',
			class_type=ConnectivityNodeContainer,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The connectivity node container to which the toplogical node belongs.''',
			profiles=[]
		)
		self.register_property(
			name='ReportingGroup',
			class_type=ReportingGroup,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The topological nodes that belong to the reporting group.''',
			profiles=[]
		)
		self.register_property(
			name='Terminal',
			class_type=Terminal,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The topological node associated with the terminal.   This can be used as an alternative to the connectivity node path to topological node, thus making it unneccesary to model connectivity nodes in some cases.   Note that the if connectivity nodes are in the model, this association would probably not be used as an input specification.''',
			profiles=[]
		)
