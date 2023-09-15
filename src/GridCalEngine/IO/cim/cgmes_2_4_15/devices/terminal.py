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
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.substation.connectivity_node import ConnectivityNode
from GridCalEngine.IO.cim.cgmes_2_4_15.cgmes_enums import PhaseCode, cgmesProfile
import GridCalEngine.IO.cim.cgmes_2_4_15.devices.substation.acdc_terminal as acdc_terminal  # the other type of import has a circular dependency ...
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.data_logger import DataLogger


class Terminal(acdc_terminal.ACDCTerminal):

    def __init__(self, rdfid="", tpe="Terminal"):
        acdc_terminal.ACDCTerminal.__init__(self, rdfid, tpe)

        self.phases: PhaseCode = PhaseCode.ABC
        self.sequenceNumber: int = 0

        # self.connected: bool = True
        self.TopologicalNode: TopologicalNode | None = None
        self.ConnectivityNode: ConnectivityNode | None = None
        self.ConductingEquipment: IdentifiedObject | None = None  # pointer to the Bus (use instead of TopologicalNode?)
        # self.BusNameMarker: BusNameMarker = None

        self.register_property(name='phases',
                               class_type=PhaseCode,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="Represents the normal network phasing condition. "
                                           "If the attribute is missing three phases (ABC or "
                                           "ABCN) shall be assumed. Primarily used for the PetersonCoil model.",
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='sequenceNumber',
                               class_type=int,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="The orientation of the terminal "
                                           "connections for a multiple terminal "
                                           "conducting equipment. The sequence "
                                           "numbering starts with 1 and additional "
                                           "terminals should follow in increasing "
                                           "order. The first terminal is the "
                                           "'starting point' for a two terminal "
                                           "branch.",
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='TopologicalNode',
                               class_type=TopologicalNode,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="",
                               comment="Out of the standard. "
                                       "Should use ConductingEquipment instead",
                               profiles=[cgmesProfile.TP])

        self.register_property(name='ConnectivityNode',
                               class_type=ConnectivityNode,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="",
                               comment="Terminals interconnected with zero "
                                       "impedance at a this connectivity node.",
                               mandatory=True,
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='ConductingEquipment',
                               class_type=IdentifiedObject,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="The conducting equipment of the "
                                           "terminal. Conducting equipment have "
                                           "terminals that may be connected to "
                                           "other conducting equipment terminals"
                                           " via connectivity nodes or "
                                           "topological nodes.",
                               mandatory=True,
                               profiles=[cgmesProfile.EQ, cgmesProfile.DY, cgmesProfile.EQ_BD])

    def get_voltage(self, logger: DataLogger):
        """
        Get the voltage of this terminal
        :return: Voltage or None
        """
        if self.TopologicalNode is not None:
            return self.TopologicalNode.get_nominal_voltage(logger=logger)
        else:
            return None

    def check(self, logger: DataLogger):
        """

        :param logger:
        :return:
        """

        """
        OCL constraint:Sequence Number is required for EquivalentBranch and ACLineSegments with MutualCoupling
        """

        # TODO: exceedingly hard to check: must know the sequence of concatenated AcLineSegment that do not have branching
        pass
