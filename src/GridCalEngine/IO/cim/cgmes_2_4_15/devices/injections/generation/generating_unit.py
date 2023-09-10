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
from GridCalEngine.IO.cim.cgmes_2_4_15.cgmes_enums import GeneratorControlSource, cgmesProfile
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol


class GeneratingUnit(IdentifiedObject):

    def __init__(self, rdfid, tpe="GeneratingUnit"):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.genControlSource: GeneratorControlSource = None
        self.governorSCD: float = 0.0
        self.initialP: float = 0.0
        self.longPF: float = 0.0
        self.maximumAllowableSpinningReserve: float = 0.0

        self.maxOperatingP: float = 0.0
        self.minOperatingP: float = 0.0
        self.nominalP: float = 0.0

        self.ratedGrossMaxP: float = 0.0
        self.ratedGrossMinP: float = 0.0
        self.ratedNetMaxP: float = 0.0

        self.shortPF: float = 0.0
        self.startupCost: float = 0.0
        self.variableCost: float = 0.0
        self.totalEfficiency: float = 0.0

        self.normalPF: float = 0.0

        self.EquipmentContainer: IdentifiedObject | None = None

        self.register_property(
            name='genControlSource',
            class_type=GeneratorControlSource,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="The ratio tap changer of this tap ratio table.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='governorSCD',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.PerCent,
            description="Governor Speed Changer Droop. "
                        "This is the change in generator power output divided by the change in frequency "
                        "normalized by the nominal power of the generator and the nominal frequency and "
                        "expressed in percent and negated. A positive value of speed change droop provides "
                        "additional generator output upon a drop in frequency.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='initialP',
            class_type=float,
            multiplier=UnitMultiplier.M,
            unit=UnitSymbol.W,
            description="Default initial active power which is used to store a powerflow result for the initial "
                        "active power for this unit in this network configuration.",
            mandatory=True,
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='longPF',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Generating unit long term economic participation factor.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='maximumAllowableSpinningReserve',
            class_type=float,
            multiplier=UnitMultiplier.M,
            unit=UnitSymbol.W,
            description="Maximum allowable spinning reserve. Spinning reserve will never be considered "
                        "greater than this value regardless of the current operating point.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='maxOperatingP',
            class_type=float,
            multiplier=UnitMultiplier.M,
            unit=UnitSymbol.W,
            description="This is the maximum operating active power limit the dispatcher can enter for this unit.",
            mandatory=True,
            profiles=[cgmesProfile.EQ]
        )

        self.register_property(
            name='minOperatingP',
            class_type=float,
            multiplier=UnitMultiplier.M,
            unit=UnitSymbol.W,
            description="This is the minimum operating active power limit the dispatcher can enter for this unit.",
            mandatory=True,
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='nominalP',
            class_type=float,
            multiplier=UnitMultiplier.M,
            unit=UnitSymbol.W,
            description="The nominal power of the generating unit. "
                        "Used to give precise meaning to percentage based attributes such as "
                        "the governor speed change droop (governorSCD attribute). The attribute shall be "
                        "a positive value equal or less than RotatingMachine.ratedS.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='ratedGrossMaxP',
            class_type=float,
            multiplier=UnitMultiplier.M,
            unit=UnitSymbol.W,
            description="The unit's gross rated maximum capacity (book value).",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='ratedGrossMinP',
            class_type=float,
            multiplier=UnitMultiplier.M,
            unit=UnitSymbol.W,
            description="The gross rated minimum generation level which the unit can safely operate "
                        "at while delivering power to the transmission grid.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='ratedNetMaxP',
            class_type=float,
            multiplier=UnitMultiplier.M,
            unit=UnitSymbol.W,
            description="The net rated maximum capacity determined by subtracting the auxiliary power used to "
                        "operate the internal plant machinery from the rated gross maximum capacity.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='shortPF',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Generating unit short term economic participation factor.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='startupCost',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.Money,
            description="The initial startup cost incurred for each start of the GeneratingUnit.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='variableCost',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.Money,
            description="The variable cost component of production per unit of ActivePower.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='totalEfficiency',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.PerCent,
            description="The efficiency of the unit in converting the fuel into electrical energy.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='normalPF',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Generating unit economic participation factor..",
            profiles=[cgmesProfile.SSH])

        self.register_property(
            name='EquipmentContainer',
            class_type=IdentifiedObject,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="",
            profiles=[cgmesProfile.EQ])
