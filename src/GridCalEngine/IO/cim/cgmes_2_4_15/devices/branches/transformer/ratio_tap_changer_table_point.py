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
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.branches.transformer.ratio_tap_changer_table import RatioTapChangerTable
from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol


class RatioTapChangerTablePoint(IdentifiedObject):
    """
    Describes each tap step in the ratio tap changer tabular curve.
    """

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.ratio: float = 0.0
        self.step: int = 0

        self.r: float = 0.0
        self.x: float = 0.0
        self.b: float = 0.0
        self.g: float = 0.0

        self.RatioTapChangerTable: RatioTapChangerTable | None = None

        self.register_property(
            name='b',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.PerCent,
            description="The magnetizing branch susceptance deviation in percent of nominal value. "
                        "The actual susceptance is calculated as follows: calculated magnetizing "
                        "susceptance = b(nominal) * (1 + b(from this class)/100). The b(nominal) is "
                        "defined as the static magnetizing susceptance on the associated power "
                        "transformer end or ends. This model assumes the star impedance (pi model) form.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='g',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.PerCent,
            description="The magnetizing branch conductance deviation in percent of nominal value. "
                        "The actual conductance is calculated as follows: calculated magnetizing "
                        "conductance = g(nominal) * (1 + g(from this class)/100). The g(nominal) is "
                        "defined as the static magnetizing conductance on the associated power "
                        "transformer end or ends. This model assumes the star impedance (pi model) form.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='r',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.PerCent,
            description="The resistance deviation in percent of nominal value. "
                        "The actual reactance is calculated as follows: calculated "
                        "resistance = r(nominal) * (1 + r(from this class)/100). The r(nominal) is "
                        "defined as the static resistance on the associated power transformer end or ends. "
                        "This model assumes the star impedance (pi model) form.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='x',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.PerCent,
            description="The series reactance deviation in percent of nominal value. "
                        "The actual reactance is calculated as follows: "
                        "calculated reactance = x(nominal) * (1 + x(from this class)/100). "
                        "The x(nominal) is defined as the static series reactance on the associated power "
                        "transformer end or ends. This model assumes the star impedance (pi model) form.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='ratio',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="The voltage ratio in per unit. Hence this is a value close to one.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='step',
            class_type=int,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="The tap step.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='RatioTapChangerTable',
            class_type=RatioTapChangerTable,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="",
            profiles=[cgmesProfile.EQ])
