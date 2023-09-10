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
from GridCalEngine.IO.cim.cgmes_2_4_15.cgmes_enums import RegulatingControlModeKind, cgmesProfile
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.terminal import Terminal
from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol


class RegulatingControl(IdentifiedObject):

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.mode: RegulatingControlModeKind = RegulatingControlModeKind.voltage

        self.discrete: bool = False
        self.enabled: bool = True
        self.targetDeadband: float = 0.0
        self.targetValue: float = 0.0
        self.targetValueUnitMultiplier: UnitMultiplier = UnitMultiplier.none

        self.Terminal: Terminal | None = None

        self.register_property(
            name='mode',
            class_type=RegulatingControlModeKind,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="The regulating control mode presently available. "
                        "This specification allows for determining the kind of regulation without need for "
                        "obtaining the units from a schedule.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='discrete',
            class_type=bool,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="The regulation is performed in a discrete mode. "
                        "This applies to equipment with discrete controls, e.g. tap changers and shunt compensators.",
            mandatory=True,
            profiles=[cgmesProfile.SSH])

        self.register_property(
            name='enabled',
            class_type=bool,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="The flag tells if regulation is enabled.",
            mandatory=True,
            profiles=[cgmesProfile.SSH])

        self.register_property(
            name='targetDeadband',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="This is a dead band used with discrete control to avoid excessive update of "
                        "controls like tap changers and shunt compensator banks while regulating. "
                        "The units of those appropriate for the mode.",
            profiles=[cgmesProfile.SSH])

        self.register_property(
            name='targetValue',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="The target value specified for case input. "
                        "This value can be used for the target value without the use of schedules. "
                        "The value has the units appropriate to the mode attribute.",
            profiles=[cgmesProfile.SSH])

        self.register_property(
            name='targetValueUnitMultiplier',
            class_type=UnitMultiplier,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Specify the multiplier for used for the targetValue.",
            profiles=[cgmesProfile.SSH])

        self.register_property(
            name='Terminal',
            class_type=Terminal,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="The controls regulating this terminal.",
            profiles=[cgmesProfile.EQ])
