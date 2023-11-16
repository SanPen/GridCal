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
from GridCalEngine.IO.cim.cgmes_2_4_15.cgmes_enums import cgmesProfile
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.aggregation.control_area import ControlArea
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.terminal import Terminal
from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol


class TieFlow(IdentifiedObject):

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.positiveFlowIn: bool = True
        self.ControlArea: ControlArea | None = None
        self.Terminal: Terminal | None = None

        self.register_property(
            name='positiveFlowIn',
            class_type=bool,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="True if the flow into the terminal (load convention) is also flow into the control area. "
                        "For example, this attribute should be true if using the tie line terminal further away from "
                        "the control area. For example to represent a tie to a shunt component "
                        "(like a load or generator) in another area, this is the near end of a branch and this "
                        "attribute would be specified as false.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='ControlArea',
            class_type=ControlArea,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="The control area of the tie flows.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='Terminal',
            class_type=Terminal,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="The terminal to which this tie flow belongs.",
            profiles=[cgmesProfile.EQ])
