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
from typing import Union
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.topological_node import TopologicalNode
from GridCalEngine.IO.cim.cgmes_2_4_15.cgmes_enums import cgmesProfile
from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol


class FuelType(IdentifiedObject):
    """
    TopologicalIsland
    """

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.EnergySource: Union[TopologicalNode, None] = None
        # self.TopologicalNodes = TopologicalNodes

        self.register_property(name='FuelType',
                               class_type=TopologicalNode,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="",
                               profiles=[cgmesProfile.EQ, cgmesProfile.EQ_BD])