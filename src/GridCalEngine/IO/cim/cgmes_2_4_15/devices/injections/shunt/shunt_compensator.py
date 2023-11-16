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
import datetime
from GridCalEngine.IO.cim.cgmes_2_4_15.cgmes_enums import cgmesProfile
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.substation.base_voltage import BaseVoltage
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.injections.monopole import MonoPole
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.injections.regulating_control import RegulatingControl
from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol


class ShuntCompensator(MonoPole):

    def __init__(self, rdfid, tpe="LinearShuntCompensator"):
        MonoPole.__init__(self, rdfid, tpe)

        self.aVRDelay: float = 0.0
        self.grounded: bool = False

        self.maximumSections: int = 0
        self.nomU: float = 0
        self.normalSections: int = 0

        self.switchOnCount: int = 0
        self.switchOnDate: datetime.datetime | None = None

        self.voltageSensitivity: float = 0.0  # kV/MVAr

        self.controlEnabled: bool = False
        self.sections: int = 0

        self.RegulatingControl: RegulatingControl | None = None
        self.EquipmentContainer: IdentifiedObject | None = None
        self.BaseVoltage: BaseVoltage | None = None

        self.register_property(
            name='aVRDelay',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.s,
            description="Time delay required for the device to be connected or "
                        "disconnected by automatic voltage regulation (AVR).",
            profiles=[cgmesProfile.EQ]
        )

        self.register_property(
            name='grounded',
            class_type=bool,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Used for Yn and Zn connections. True if the neutral is solidly grounded.",
            profiles=[cgmesProfile.EQ]
        )

        self.register_property(
            name='maximumSections',
            class_type=int,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="The maximum number of sections that may be switched in.",
            profiles=[cgmesProfile.EQ]
        )

        self.register_property(
            name='nomU',
            class_type=float,
            multiplier=UnitMultiplier.k,
            unit=UnitSymbol.V,
            description="The voltage at which the nominal reactive power may be calculated. This should "
                        "normally be within 10% of the voltage at which the capacitor is connected to the network.",
            profiles=[cgmesProfile.EQ]
        )

        self.register_property(
            name='normalSections',
            class_type=int,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="The normal number of sections switched in.",
            profiles=[cgmesProfile.EQ]
        )

        self.register_property(
            name='switchOnCount',
            class_type=int,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="The switch on count since the capacitor count was last reset or initialized.",
            profiles=[cgmesProfile.EQ]
        )

        self.register_property(
            name='switchOnDate',
            class_type=datetime.datetime,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="The date and time when the capacitor bank was last switched on.",
            profiles=[cgmesProfile.EQ]
        )

        self.register_property(
            name='voltageSensitivity',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.kVperMVAr,
            description="Voltage sensitivity required for the device to regulate the bus "
                        "voltage, in voltage/reactive power.",
            profiles=[cgmesProfile.EQ]
        )

        self.register_property(
            name='sections',
            class_type=int,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="",
            profiles=[cgmesProfile.EQ]
        )

        self.register_property(
            name='controlEnabled',
            class_type=bool,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="",
            profiles=[cgmesProfile.EQ]
        )

        self.register_property(
            name='RegulatingControl',
            class_type=RegulatingControl,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="",
            profiles=[cgmesProfile.EQ]
        )

        self.register_property(
            name='EquipmentContainer',
            class_type=IdentifiedObject,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="",
            profiles=[cgmesProfile.EQ]
        )

        self.register_property(
            name='BaseVoltage',
            class_type=BaseVoltage,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="",
            profiles=[cgmesProfile.EQ]
        )
