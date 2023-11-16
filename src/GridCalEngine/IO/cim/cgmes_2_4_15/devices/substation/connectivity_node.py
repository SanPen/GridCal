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
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.topological_node import TopologicalNode
from GridCalEngine.IO.cim.cgmes_2_4_15.cgmes_enums import cgmesProfile
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.substation.connectivity_node_container import ConnectivityNodeContainer
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol


class ConnectivityNode(IdentifiedObject):
    """
    Connectivity nodes are points where terminals of AC conducting equipment are connected
    together with zero impedance. If the model is a TSO EQ, the ConnectivityNodes should be
    grouped under VoltageLevel; If the model is a Boundary EQ, the ConnectivityNodes should
    be grouped under Line; If the model is an assembled one, the ConnectivityNodes can be
    grouped under either VoltageLevel or Line. With this approach the Line is also in the
    Boundary set. Instances of ACLineSegment can be in the Boundary set instance of Line
    or in another instance of Line. Consequently, there can be instances of Line that contain
    only ConnectivityNodes, but no ACLineSegments.
    """

    def __init__(self, rdfid='', tpe='ConnectivityNode'):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.boundaryPoint: bool = False

        self.fromEndIsoCode: str = ''
        self.fromEndName: str = ''
        self.fromEndNameTso: str = ''

        self.toEndIsoCode: str = ''
        self.toEndName: str = ''
        self.toEndNameTso: str = ''

        self.TopologicalNode: TopologicalNode | None = None
        self.ConnectivityNodeContainer: ConnectivityNodeContainer | None = None  # use this instead of TopologicalNode?

        self.register_property(name='boundaryPoint',
                               class_type=bool,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="Identifies if a node is a BoundaryPoint. "
                                           "If boundaryPoint=true the ConnectivityNode"
                                           " or the TopologicalNode represents a "
                                           "BoundaryPoint",
                               mandatory=True,
                               profiles=[cgmesProfile.EQ_BD]
                               )

        self.register_property(name='fromEndIsoCode',
                               class_type=str,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="The attribute is used for an exchange of "
                                           "the ISO code of the region to which the "
                                           "'From' side of the Boundary point belongs"
                                           " to or it is connected to. The ISO code "
                                           "is two characters country code as "
                                           "defined by ISO 3166 "
                                           "(http://www.iso.org/iso/country_codes). "
                                           "The length of the string is 2 characters "
                                           "maximum.   The attribute is a required "
                                           "for the Boundary Model Authority Set "
                                           "where this attribute is used only for "
                                           "the TopologicalNode in the Boundary "
                                           "Topology profile and ConnectivityNode "
                                           "in the Boundary Equipment profile.",
                               max_chars=2,
                               mandatory=True,
                               profiles=[cgmesProfile.EQ_BD]
                               )

        self.register_property(name='fromEndName',
                               class_type=str,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description='The attribute is used for an exchange of a '
                                           'human readable name with length of the '
                                           'string 32 characters maximum. The attribute '
                                           'covers two cases:  '
                                           'if the Boundary point is placed on a '
                                           'tie-line the attribute is used for exchange '
                                           'of the geographical name of the substation '
                                           'to which the From side of the tie-line is '
                                           'connected to.  if the Boundary point is '
                                           'placed in a substation the attribute is '
                                           'used for exchange of the name of the element'
                                           ' (e.g. PowerTransformer, ACLineSegment, '
                                           'Switch, etc) to which the From side of the '
                                           'Boundary point is connected to. The '
                                           'attribute is required for the Boundary '
                                           'Model Authority Set where it is used only '
                                           'for the TopologicalNode in the Boundary '
                                           'Topology profile and ConnectivityNode in '
                                           'the Boundary Equipment profile.',
                               max_chars=32,
                               mandatory=True,
                               profiles=[cgmesProfile.EQ_BD]
                               )

        self.register_property(name='fromEndNameTso',
                               class_type=str,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="The attribute is used for an exchange of "
                                           "the name of the TSO to which the “From” "
                                           "side of the Boundary point belongs to or "
                                           "it is connected to. The length of the "
                                           "string is 32 characters maximum.  The "
                                           "attribute is required for the Boundary "
                                           "Model Authority Set where it is used "
                                           "only for the TopologicalNode in the "
                                           "Boundary Topology profile and "
                                           "ConnectivityNode in the Boundary "
                                           "Equipment profile.",
                               max_chars=32,
                               mandatory=True,
                               profiles=[cgmesProfile.EQ_BD]
                               )

        self.register_property(name='toEndIsoCode',
                               class_type=str,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="The attribute is used for an exchange of "
                                           "the ISO code of the region to which the "
                                           "“To” side of the Boundary point belongs "
                                           "to or it is connected to. The ISO code is "
                                           "two characters country code as defined by "
                                           "ISO 3166 (http://www.iso.org/iso/country_codes). "
                                           "The length of the string is 2 characters "
                                           "maximum. The attribute is a required for "
                                           "the Boundary Model Authority Set where "
                                           "this attribute is used only for the "
                                           "TopologicalNode in the Boundary Topology "
                                           "profile and ConnectivityNode in the "
                                           "Boundary Equipment profile.",
                               max_chars=2,
                               mandatory=True,
                               profiles=[cgmesProfile.EQ_BD])

        self.register_property(name='toEndName',
                               class_type=str,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="The attribute is used for an exchange of a "
                                           "human readable name with length of the string "
                                           "32 characters maximum. The attribute covers "
                                           "two cases:  if the Boundary point is placed "
                                           "on a tie-line the attribute is used for "
                                           "exchange of the geographical name of the "
                                           "substation to which the “To” side of the "
                                           "tie-line is connected to. if the Boundary "
                                           "point is placed in a substation the attribute "
                                           "is used for exchange of the name of the "
                                           "element (e.g. PowerTransformer, "
                                           "ACLineSegment, Switch, etc) to which the “To” "
                                           "side of the Boundary point is connected to. "
                                           "The attribute is required for the Boundary "
                                           "Model Authority Set where it is used only for "
                                           "the TopologicalNode in the Boundary Topology "
                                           "profile and ConnectivityNode in the Boundary "
                                           "Equipment profile.",
                               max_chars=32,
                               mandatory=True,
                               profiles=[cgmesProfile.EQ_BD]
                               )

        self.register_property(name='toEndNameTso',
                               class_type=str,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="The attribute is used for an exchange of "
                                           "the name of the TSO to which the “To” side "
                                           "of the Boundary point belongs to or it is "
                                           "connected to. The length of the string is "
                                           "32 characters maximum. The attribute is "
                                           "required for the Boundary Model Authority "
                                           "Set where it is used only for the "
                                           "TopologicalNode in the Boundary Topology "
                                           "profile and ConnectivityNode in the "
                                           "Boundary Equipment profile.",
                               max_chars=32,
                               mandatory=True,
                               profiles=[cgmesProfile.EQ_BD])

        self.register_property(name='TopologicalNode',
                               class_type=TopologicalNode,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="",
                               comment="Out of the standard",
                               profiles=[cgmesProfile.TP_BD, cgmesProfile.TP])

        self.register_property(name='ConnectivityNodeContainer',
                               class_type=ConnectivityNodeContainer,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="Container of this connectivity node",
                               profiles=[cgmesProfile.EQ, cgmesProfile.EQ_BD])
