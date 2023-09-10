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
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.injections.generation.reactive_capability_curve import \
    ReactiveCapabilityCurve
from GridCalEngine.IO.cim.cgmes_2_4_15.cgmes_enums import ShortCircuitRotorKind, SynchronousMachineKind, \
    SynchronousMachineOperatingMode, cgmesProfile
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.substation.base_voltage import BaseVoltage
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.injections.generation.generating_unit import GeneratingUnit
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.injections.monopole import MonoPole
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.injections.regulating_control import RegulatingControl
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.injections.generation.rotating_machine import RotatingMachine
from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol


class SynchronousMachine(MonoPole, RotatingMachine):

    def __init__(self, rdfid='', tpe='SynchronousMachine'):
        MonoPole.__init__(self, rdfid, tpe)
        RotatingMachine.__init__(self, rdfid, tpe)

        self.earthing: bool = False
        self.earthingStarPointR: float = 0.0
        self.earthingStarPointX: float = 0.0
        self.ikk: float = 0.0
        self.maxQ: float = 0
        self.minQ: float = 0
        self.mu: float = 0.0

        self.qPercent: float = 0
        self.r: float = 0.0
        self.r0: float = 0.0
        self.r2: float = 0.0

        # self.x: float = 0.0  # TODO: out of the standard...
        self.x0: float = 0.0
        self.x2: float = 0.0

        self.satDirectSubtransX: float = 0.0
        self.satDirectSyncX: float = 0.0
        self.satDirectTransX: float = 0.0
        self.shortCircuitRotorType: ShortCircuitRotorKind = ShortCircuitRotorKind.salientPole1

        self.type: SynchronousMachineKind = SynchronousMachineKind.generator

        self.voltageRegulationRange: float = 0.0

        self.ratedPowerFactor: float = 1.0
        self.ratedS: float = 0.0
        self.ratedU: float = 0.0

        self.operatingMode: SynchronousMachineOperatingMode = SynchronousMachineOperatingMode.generator
        self.referencePriority = 0

        self.InitialReactiveCapabilityCurve: ReactiveCapabilityCurve | None = None
        self.GeneratingUnit: GeneratingUnit | None = None
        self.RegulatingControl: RegulatingControl | None = None
        self.BaseVoltage: BaseVoltage | None = None
        self.EquipmentContainer: IdentifiedObject | None = None

        self.register_property(
            name='earthing',
            class_type=bool,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Indicates whether or not the generator is earthed. "
                        "Used for short circuit data exchange according to IEC 60909",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='earthingStarPointR',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.ohm,
            description="Generator star point earthing resistance (Re). "
                        "Used for short circuit data exchange according to IEC 60909",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='earthingStarPointX',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.ohm,
            description="Generator star point earthing reactance (Xe). "
                        "Used for short circuit data exchange according to IEC 60909",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='ikk',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.A,
            description="Steady-state short-circuit current (in A for the profile) "
                        "of generator with compound excitation during 3-phase short circuit. "
                        "- Ikk=0: Generator with no compound excitation. "
                        "- Ikk?0: Generator with compound excitation. "
                        "Ikk is used to calculate the minimum steady-state short-circuit current for "
                        "generators with compound excitation (Section 4.6.1.2 in the IEC 60909-0) "
                        "Used only for single fed short circuit on a generator. (Section 4.3.4.2. in the IEC 60909-0)",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='maxQ',
            class_type=float,
            multiplier=UnitMultiplier.M,
            unit=UnitSymbol.VAr,
            description="Maximum reactive power limit. This is the maximum (nameplate) limit for the unit.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='minQ',
            class_type=float,
            multiplier=UnitMultiplier.M,
            unit=UnitSymbol.VAr,
            description="Minimum reactive power limit for the unit.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='mu',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Factor to calculate the breaking current (Section 4.5.2.1 in the IEC 60909-0). "
                        "Used only for single fed short circuit on a generator (Section 4.3.4.2. in the IEC 60909-0).",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='qPercent',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Percent of the coordinated reactive control that comes from this machine.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='r',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.ohm,
            description="Equivalent resistance (RG) of generator. "
                        "RG is considered for the calculation of all currents, except for the "
                        "calculation of the peak current ip. Used for short circuit data exchange "
                        "according to IEC 60909",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='r0',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.pu,
            description="Zero sequence resistance of the synchronous machine.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='r2',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.pu,
            description="Negative sequence resistance.",
            profiles=[cgmesProfile.EQ])

        # self.register_property(
        #     name='x',
        #     class_type=float,
        #     multiplier=UnitMultiplier.none,
        #     unit=UnitSymbol.ohm,
        #     description="Equivalent reactance (RG) of generator. "
        #                 "RG is considered for the calculation of all currents, except for the "
        #                 "calculation of the peak current ip. Used for short circuit data exchange "
        #                 "according to IEC 60909")

        self.register_property(
            name='x0',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.pu,
            description="Zero sequence reactance of the synchronous machine.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='x2',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.pu,
            description="Negative sequence reactance.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='satDirectSubtransX',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.pu,
            description="Direct-axis subtransient reactance saturated, also known as Xd''sat.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='satDirectSyncX',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.pu,
            description="Direct-axes saturated synchronous reactance (xdsat); reciprocal of short-circuit ration. "
                        "Used for short circuit data exchange, only for single fed short circuit on a generator. "
                        "(Section 4.3.4.2. in the IEC 60909-0).",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='satDirectTransX',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.pu,
            description="Saturated Direct-axis transient reactance. "
                        "The attribute is primarily used for short circuit calculations according to ANSI.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='shortCircuitRotorType',
            class_type=ShortCircuitRotorKind,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Type of rotor, used by short circuit applications, "
                        "only for single fed short circuit according to IEC 60909.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='type',
            class_type=SynchronousMachineKind,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Modes that this synchronous machine can operate in.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='voltageRegulationRange',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.PerCent,
            description="Range of generator voltage regulation (PG in the IEC 60909-0) used for calculation "
                        "of the impedance correction factor KG defined in IEC 60909-0 This attribute is used "
                        "to describe the operating voltage of the generating unit.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='ratedPowerFactor',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Power factor (nameplate data). "
                        "It is primarily used for short circuit data exchange according to IEC 60909.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='ratedS',
            class_type=float,
            multiplier=UnitMultiplier.M,
            unit=UnitSymbol.VA,
            description="Nameplate apparent power rating for the unit. "
                        "The attribute shall have a positive value.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='ratedU',
            class_type=float,
            multiplier=UnitMultiplier.k,
            unit=UnitSymbol.V,
            description="Rated voltage (nameplate data, Ur in IEC 60909-0). "
                        "It is primarily used for short circuit data exchange according to IEC 60909.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='operatingMode',
            class_type=SynchronousMachineOperatingMode,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="",
            profiles=[cgmesProfile.SSH])

        self.register_property(
            name='referencePriority',
            class_type=int,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Tells if this generator is marked as a slack generator (1.0) or not (0.0) "
                        "other numbers determine the slack share.",
            profiles=[cgmesProfile.SSH])
        #
        # self.register_property(
        #     name='EquipmentContainer',
        #     class_type=EquipmentContainer,
        #     multiplier=UnitMultiplier.none,
        #     unit=UnitSymbol.none,
        #     description="")
        #
        # self.register_property(
        #     name='EquipmentContainer',
        #     class_type=EquipmentContainer,
        #     multiplier=UnitMultiplier.none,
        #     unit=UnitSymbol.none,
        #     description="")
        #
        # self.register_property(
        #     name='EquipmentContainer',
        #     class_type=EquipmentContainer,
        #     multiplier=UnitMultiplier.none,
        #     unit=UnitSymbol.none,
        #     description="")

        self.register_property(
            name='InitialReactiveCapabilityCurve',
            class_type=ReactiveCapabilityCurve,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Synchronous machines using this curve as default.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='GeneratingUnit',
            class_type=GeneratingUnit,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='RegulatingControl',
            class_type=RegulatingControl,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='BaseVoltage',
            class_type=BaseVoltage,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='EquipmentContainer',
            class_type=IdentifiedObject,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="",
            profiles=[cgmesProfile.EQ])
