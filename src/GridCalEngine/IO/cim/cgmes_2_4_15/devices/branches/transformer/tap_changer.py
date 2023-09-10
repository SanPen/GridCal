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
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.branches.transformer.tap_changer_control import TapChangerControl
from GridCalEngine.IO.cim.cgmes_2_4_15.cgmes_enums import cgmesProfile
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.injections.power_systems_resource import PowerSystemResource
from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol


class TapChanger(PowerSystemResource):

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.controlEnabled: bool = False
        self.step: int = 0
        self.highStep: int = 0
        self.lowStep: int = 0
        self.ltcFlag: bool = False
        self.neutralStep: int = 0
        self.neutralU: float = 0.0
        self.normalStep: int = 0

        self.TapChangerControl: TapChangerControl | None = None

        # self.TapSchedules = TapSchedules
        # self.SvTapStep = SvTapStep

        self.register_property(
            name='controlEnabled',
            class_type=bool,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="controlEnabled.",
            profiles=[cgmesProfile.SSH])

        self.register_property(
            name='step',
            class_type=int,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="step",
            profiles=[cgmesProfile.SSH])

        self.register_property(
            name='highStep',
            class_type=int,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Highest possible tap step position, advance from neutral. "
                        "The attribute shall be greater than lowStep.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='lowStep',
            class_type=int,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Lowest possible tap step position, retard from neutral.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='ltcFlag',
            class_type=bool,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Specifies whether or not a TapChanger has load tap changing capabilities.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='neutralStep',
            class_type=int,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="The neutral tap step position for this winding. "
                        "The attribute shall be equal or greater than lowStep and equal or less than highStep.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='neutralU',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Voltage at which the winding operates at the neutral tap setting.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='normalStep',
            class_type=int,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="The tap step position used in 'normal' network operation for this winding. "
                        "For a 'Fixed' tap changer indicates the current physical tap setting. "
                        "The attribute shall be equal or greater than lowStep and equal or less than highStep.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='TapChangerControl',
            class_type=TapChangerControl,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description=".",
            profiles=[cgmesProfile.EQ])
