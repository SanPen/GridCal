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
import GridCalEngine
from GridCalEngine.IO.cim.cgmes_2_4_15.cgmes_enums import cgmesProfile
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.substation.base_voltage import BaseVoltage
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol


class BusbarSection(IdentifiedObject):

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.ipMax: float = 0.0

        self.EquipmentContainer: IdentifiedObject = None
        self.BaseVoltage: BaseVoltage = None

        self.register_property(name='ipMax',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.A,
                               description="Maximum allowable peak short-circuit current of "
                                           "busbar (Ipmax in the IEC 60909-0). Mechanical "
                                           "limit of the busbar in the substation itself. "
                                           "Used for short circuit data exchange according "
                                           "to IEC 60909",
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='EquipmentContainer',
                               class_type=IdentifiedObject,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="",
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='BaseVoltage',
                               class_type=BaseVoltage,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="",
                               profiles=[cgmesProfile.EQ])

    def get_topological_nodes(self):
        """
        Get the associated TopologicalNode instances
        :return: list of TopologicalNode instances
        """
        try:
            terms = self.references_to_me['Terminal']
            return [GridCalEngine.IO.cim.cgmes_2_4_15.devices.topological_node.TopologicalNode for term in terms]
        except KeyError:
            return list()

    def get_topological_node(self):
        """
        Get the first TopologicalNode found
        :return: first TopologicalNode found
        """
        try:
            terms = self.references_to_me['Terminal']
            for term in terms:
                return GridCalEngine.IO.cim.cgmes_2_4_15.devices.topological_node.TopologicalNode
        except KeyError:
            return list()
