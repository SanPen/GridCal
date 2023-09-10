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
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.injections.generation.reactive_capability_curve import ReactiveCapabilityCurve
from GridCalEngine.IO.cim.cgmes_2_4_15.cgmes_enums import cgmesProfile
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.equivalent_equipment import EquivalentEquipment
from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol


class EquivalentInjection(EquivalentEquipment):

    def __init__(self, rdfid, tpe):
        EquivalentEquipment.__init__(self, rdfid, tpe)

        self.regulationStatus: bool = False
        self.regulationTarget: float = 0.0  # kV
        self.p: float = 0.0
        self.q: float = 0.0
        self.maxP: float = 0.0
        self.maxQ: float = 0.0
        self.minP: float = 0.0
        self.minQ: float = 0.0
        self.r: float = 0.0
        self.r0: float = 0.0
        self.r2: float = 0.0
        self.x: float = 0.0
        self.x0: float = 0.0
        self.x2: float = 0.0
        self.regulationCapability: bool = False
        self.ReactiveCapabilityCurve: ReactiveCapabilityCurve | None = None

        # self.BaseVoltage: BaseVoltage = None  # TODO: out of the standard
        # self.EquipmentContainer: EquipmentContainer = None  # TODO: out of the standard

        self.register_property(name='regulationStatus',
                               class_type=bool,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description='Specifies the default regulation '
                                           'status of the EquivalentInjection. '
                                           'True is regulating. False is not '
                                           'regulating.',
                               profiles=[cgmesProfile.SSH])

        self.register_property(name='regulationTarget',
                               class_type=float,
                               multiplier=UnitMultiplier.k,
                               unit=UnitSymbol.V,
                               description="The target voltage for voltage "
                                           "regulation.",
                               comment='',
                               profiles=[cgmesProfile.SSH])

        self.register_property(name='p',
                               class_type=float,
                               multiplier=UnitMultiplier.M,
                               unit=UnitSymbol.W,
                               description="Equivalent active power injection. Load sign "
                                           "convention is used, i.e. positive sign means flow "
                                           "out from a node. Starting value for steady state "
                                           "solutions.",
                               comment='',
                               profiles=[cgmesProfile.SSH])

        self.register_property(name='q',
                               class_type=float,
                               multiplier=UnitMultiplier.M,
                               unit=UnitSymbol.VAr,
                               description="Equivalent reactive power injection. Load sign "
                                           "convention is used, i.e. positive sign means flow "
                                           "out from a node. Starting value for steady state "
                                           "solutions.",
                               comment='',
                               profiles=[cgmesProfile.SSH])

        self.register_property(name='maxP',
                               class_type=float,
                               multiplier=UnitMultiplier.M,
                               unit=UnitSymbol.W,
                               description="",
                               comment='',
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='minP',
                               class_type=float,
                               multiplier=UnitMultiplier.M,
                               unit=UnitSymbol.W,
                               description="",
                               comment='',
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='maxQ',
                               class_type=float,
                               multiplier=UnitMultiplier.M,
                               unit=UnitSymbol.VAr,
                               description="",
                               comment='',
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='minQ',
                               class_type=float,
                               multiplier=UnitMultiplier.M,
                               unit=UnitSymbol.VAr,
                               description="",
                               comment='',
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='r',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.ohm,
                               description="",
                               comment='',
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='r0',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.ohm,
                               description="",
                               comment='',
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='r2',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.ohm,
                               description="",
                               comment='',
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='x',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.ohm,
                               description="",
                               comment='',
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='x0',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.ohm,
                               description="",
                               comment='',
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='x2',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.ohm,
                               description="",
                               comment='',
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='regulationCapability',
                               class_type=bool,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="",
                               comment='out of the standard',
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='ReactiveCapabilityCurve',
                               class_type=ReactiveCapabilityCurve,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="",
                               profiles=[cgmesProfile.EQ])

        # self.register_property(name='BaseVoltage',
        #                        class_type=BaseVoltage,
        #                        multiplier=UnitMultiplier.none,
        #                        unit=UnitSymbol.none,
        #                        description="",
        #                        out_of_the_standard=True,
        #                        profiles=[cgmesProfile.EQ])
        #
        # self.register_property(name='EquipmentContainer',
        #                        class_type=EquipmentContainer,
        #                        multiplier=UnitMultiplier.none,
        #                        unit=UnitSymbol.none,
        #                        description="",
        #                        out_of_the_standard=True,
        #                        profiles=[cgmesProfile.EQ])
