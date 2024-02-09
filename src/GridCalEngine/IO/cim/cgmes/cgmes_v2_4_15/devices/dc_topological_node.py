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


class DCTopologicalNode(IdentifiedObject):
	def __init__(self, rdfid='', tpe='DCTopologicalNode'):
		IdentifiedObject.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.dc_topological_island import DCTopologicalIsland
		self.DCTopologicalIsland: DCTopologicalIsland | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.dc_base_terminal import DCBaseTerminal
		self.DCTerminals: DCBaseTerminal | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.dc_equipment_container import DCEquipmentContainer
		self.DCEquipmentContainer: DCEquipmentContainer | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.dc_node import DCNode
		self.DCNodes: DCNode | None = None

		self.register_property(
			name='DCTopologicalIsland',
			class_type=DCTopologicalIsland,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''None''',
			profiles=[]
		)
		self.register_property(
			name='DCTerminals',
			class_type=DCBaseTerminal,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''See association end Terminal.TopologicalNode.''',
			profiles=[]
		)
		self.register_property(
			name='DCEquipmentContainer',
			class_type=DCEquipmentContainer,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''None''',
			profiles=[]
		)
		self.register_property(
			name='DCNodes',
			class_type=DCNode,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''See association end ConnectivityNode.TopologicalNode.''',
			profiles=[]
		)
