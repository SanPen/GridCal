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
from typing import List
from GridCalEngine.IO.cim.cgmes_2_4_15.cgmes_enums import cgmesProfile
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.conducting_equipment import ConductingEquipment
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.branches.dipole import DiPole
from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.data_logger import DataLogger

class PowerTransformer(DiPole, ConductingEquipment):

    def __init__(self, rdfid, tpe="PowerTransformer"):
        DiPole.__init__(self, rdfid, tpe)
        ConductingEquipment.__init__(self, rdfid, tpe)

        self.beforeShCircuitHighestOperatingCurrent: float = 0.0
        self.beforeShCircuitHighestOperatingVoltage: float = 0.0
        self.beforeShortCircuitAnglePf: float = 0.0
        self.highSideMinOperatingU: float = 0.0
        self.isPartOfGeneratorUnit: bool = False
        self.operationalValuesConsidered: bool = False

        # self.EquipmentContainer: EquipmentContainer = None
        # self.BaseVoltage: BaseVoltage = None  # TODO: This is VERY wrong. A transformer does not have an intrinsic voltage, however this comes in the CGMES standard

        self.register_property(
            name='beforeShCircuitHighestOperatingCurrent',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.A,
            description="The highest operating current (Ib in the IEC 60909-0) before short circuit "
                        "(depends on network configuration and relevant reliability philosophy). "
                        "It is used for calculation of the impedance correction factor KT defined in IEC 60909-0.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='beforeShCircuitHighestOperatingVoltage',
            class_type=float,
            multiplier=UnitMultiplier.k,
            unit=UnitSymbol.V,
            description="The highest operating voltage (Ub in the IEC 60909-0) before short circuit. "
                        "It is used for calculation of the impedance correction factor KT defined in IEC 60909-0. "
                        "This is worst case voltage on the low side winding (Section 3.7.1 in the standard). "
                        "Used to define operating conditions.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='beforeShortCircuitAnglePf',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.deg,
            description="The angle of power factor before short circuit (phib in the IEC 60909-0). "
                        "It is used for calculation of the impedance correction factor KT defined in IEC 60909-0. "
                        "This is the worst case power factor. Used to define operating conditions.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='highSideMinOperatingU',
            class_type=float,
            multiplier=UnitMultiplier.k,
            unit=UnitSymbol.V,
            description="The minimum operating voltage (uQmin in the IEC 60909-0) at the high voltage side (Q side) "
                        "of the unit transformer of the power station unit. A value well established from long-term "
                        "operating experience of the system. It is used for calculation of the impedance correction "
                        "factor KG defined in IEC 60909-0",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='isPartOfGeneratorUnit',
            class_type=bool,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Indicates whether the machine is part of a power station unit. "
                        "Used for short circuit data exchange according to IEC 60909",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='operationalValuesConsidered',
            class_type=bool,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="It is used to define if the data (other attributes related to short circuit data exchange) "
                        "defines long term operational conditions or not. Used for short circuit data exchange "
                        "according to IEC 60909.",
            profiles=[cgmesProfile.EQ])

        # self.register_property(name='BaseVoltage',
        #                        class_type=BaseVoltage,
        #                        multiplier=UnitMultiplier.none,
        #                        unit=UnitSymbol.none,
        #                        description="",
        #                        profiles=[cgmesProfile.EQ])
        #
        # self.register_property(name='EquipmentContainer',
        #                        class_type=EquipmentContainer,
        #                        multiplier=UnitMultiplier.none,
        #                        unit=UnitSymbol.none,
        #                        description="",
        #                        profiles=[cgmesProfile.EQ])

    def get_windings_number(self):
        """
        Get the number of windings
        :return: # number of associated windings
        """
        try:
            return len(self.references_to_me['PowerTransformerEnd'])
        except KeyError:
            return 0

    def get_windings(self) -> List["PowerTransformerEnd"]:
        """
        Get list of windings
        :return: list of winding objects
        """
        try:
            return list(self.references_to_me['PowerTransformerEnd'])
        except KeyError:
            return list()

    def get_pu_values(self, System_Sbase):
        """
        Get the transformer p.u. values
        :return:
        """
        try:
            windings = self.get_windings()

            R, X, G, B = 0, 0, 0, 0
            R0, X0, G0, B0 = 0, 0, 0, 0
            if len(windings) == 2:
                for winding in windings:
                    r, x, g, b, r0, x0, g0, b0 = winding.get_pu_values(System_Sbase)
                    R += r
                    X += x
                    G += g
                    B += b
                    R0 += r0
                    X0 += x0
                    G0 += g0
                    B0 += b0

        except KeyError:
            R, X, G, B = 0, 0, 0, 0
            R0, X0, G0, B0 = 0, 0, 0, 0

        return R, X, G, B, R0, X0, G0, B0

    def get_voltages(self, logger: DataLogger):
        """

        :return:
        """
        return [x.get_voltage(logger=logger) for x in self.get_windings()]

    def get_rate(self):

        rating = 0
        for winding in self.get_windings():
            if winding.ratedS > rating:
                rating = winding.ratedS

        return rating
