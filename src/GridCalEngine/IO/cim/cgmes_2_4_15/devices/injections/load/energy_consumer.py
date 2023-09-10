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
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.injections.load.load_response_characteristic import LoadResponseCharacteristic
from GridCalEngine.IO.cim.cgmes_2_4_15.cgmes_enums import cgmesProfile
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.conducting_equipment import ConductingEquipment
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.injections.monopole import MonoPole
from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol


class EnergyConsumer(MonoPole, ConductingEquipment):

    def __init__(self, rdfid, tpe="EnergyConsumer"):
        MonoPole.__init__(self, rdfid, tpe)
        ConductingEquipment.__init__(self, rdfid, tpe)

        self.pfixed: float = 0.0
        self.pfixedPct: float = 0.0
        self.qfixed: float = 0.0
        self.qfixedPct: float = 0.0

        self.p: float = 0.0
        self.q: float = 0.0

        self.LoadResponse: LoadResponseCharacteristic | None = None
        # self.EquipmentContainer: EquipmentContainer = None
        # self.BaseVoltage: BaseVoltage = None

        self.register_property(
            name='pfixed',
            class_type=float,
            multiplier=UnitMultiplier.M,
            unit=UnitSymbol.W,
            description="Active power of the load that is a fixed quantity. Load sign convention is used, i.e. "
                        "positive sign means flow out from a node.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='pfixedPct',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.PerCent,
            description="Fixed active power as per cent of load group fixed active power. "
                        "Load sign convention is used, i.e. positive sign means flow out from a node.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='qfixed',
            class_type=float,
            multiplier=UnitMultiplier.M,
            unit=UnitSymbol.VAr,
            description="Reactive power of the load that is a fixed quantity. Load sign convention is used, i.e. "
                        "positive sign means flow out from a node.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='qfixedPct',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.PerCent,
            description="Fixed reactive power as per cent of load group fixed reactive power. "
                        "Load sign convention is used, i.e. positive sign means flow out from a node.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='p',
            class_type=float,
            multiplier=UnitMultiplier.M,
            unit=UnitSymbol.W,
            description="",
            comment='Out of the standard',
            profiles=[cgmesProfile.SSH])

        self.register_property(
            name='q',
            class_type=float,
            multiplier=UnitMultiplier.M,
            unit=UnitSymbol.VAr,
            description="",
            comment='Out of the standard',
            profiles=[cgmesProfile.SSH])

        self.register_property(name='LoadResponse',
                               class_type=LoadResponseCharacteristic,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="",
                               profiles=[cgmesProfile.EQ])

