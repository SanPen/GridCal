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
from GridCalEngine.IO.cim.cgmes_2_4_15.cgmes_enums import CurveStyle, cgmesProfile
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.base.units import UnitSymbol, UnitMultiplier


class ReactiveCapabilityCurve(IdentifiedObject):
    """
    Reactive power rating envelope versus the synchronous machine's active power, in both the
    generating and motoring modes. For each active power value there is a corresponding high and
    low reactive power limit value. Typically there will be a separate curve for each coolant condition,
    such as hydrogen pressure. The Y1 axis values represent reactive minimum and the Y2 axis
    values represent reactive maximum.
    """

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.curveStyle: CurveStyle = CurveStyle.straightLineYValues
        self.xUnit: UnitSymbol = UnitSymbol.none
        self.y1Unit: UnitSymbol = UnitSymbol.none
        self.y2Unit: UnitSymbol = UnitSymbol.none

        self.register_property(
            name='curveStyle',
            class_type=CurveStyle,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="The style or shape of the curve.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='xUnit',
            class_type=UnitSymbol,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="The X-axis units of measure.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='y1Unit',
            class_type=UnitSymbol,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="The Y1-axis units of measure.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='y2Unit',
            class_type=UnitSymbol,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="The Y2-axis units of measure.",
            profiles=[cgmesProfile.EQ])
