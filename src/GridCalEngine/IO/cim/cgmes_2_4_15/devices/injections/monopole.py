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
import GridCalEngine.IO.cim.cgmes_2_4_15.devices.topological_node
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.identified_object import IdentifiedObject


class MonoPole(IdentifiedObject):

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

    def get_topological_node(self):
        """
        Get the TopologyNodes of this branch
        :return: two TopologyNodes or nothing
        """
        try:
            terminals = list(self.references_to_me['Terminal'])

            if len(terminals) == 1:
                n1 = terminals[0].TopologicalNode
                return n1
            else:
                return None

        except KeyError:
            return None

    def get_bus(self):
        """
        Get the associated bus
        :return:
        """
        tp = self.get_topological_node()
        if tp is None:
            return None
        else:
            return tp.get_bus()

    def get_dict(self):
        """
        Get dictionary with the data
        :return: Dictionary
        """
        tp = self.get_topological_node()
        bus = tp.get_bus() if tp is not None else None

        d = super().get_dict()
        d['TopologicalNode'] = '' if tp is None else tp.uuid
        d['BusbarSection'] = '' if bus is None else bus.uuid
        return d
