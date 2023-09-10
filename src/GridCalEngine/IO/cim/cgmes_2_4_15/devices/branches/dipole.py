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
from typing import Tuple
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.substation.bus_bar_section import BusbarSection
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.identified_object import IdentifiedObject


class DiPole(IdentifiedObject):

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

    def get_topological_nodes(self) -> Tuple["TopologicalNode", "TopologicalNode"]:
        """
        Get the TopologyNodes of this branch
        :return: (TopologyNodes, TopologyNodes) or (None, None)
        """
        try:
            terminals = list(self.references_to_me['Terminal'])

            if len(terminals) == 2:
                n1 = terminals[0].TopologicalNode
                n2 = terminals[1].TopologicalNode
                return n1, n2
            else:
                return None, None

        except KeyError:
            return None, None

    def get_buses(self) -> Tuple["BusbarSection", "BusbarSection"]:
        """
        Get the associated bus
        :return: (BusbarSection, BusbarSection) or (None, None)
        """
        t1, t2 = self.get_topological_nodes()
        b1 = t1.get_bus() if t1 is not None else None
        b2 = t2.get_bus() if t2 is not None else None
        return b1, b2

    def get_nodes(self) -> Tuple["TopologicalNode", "TopologicalNode"]:
        """
        Get the TopologyNodes of this branch
        :return: two TopologyNodes or nothing
        """
        try:
            terminals = list(self.references_to_me['Terminal'])

            if len(terminals) == 2:
                n1 = terminals[0].TopologicalNode
                n2 = terminals[1].TopologicalNode
                return n1, n2
            else:
                return None, None

        except KeyError:
            return None, None
