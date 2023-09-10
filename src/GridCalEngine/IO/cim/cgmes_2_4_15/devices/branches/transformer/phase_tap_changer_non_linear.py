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
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.branches.transformer.power_transformer_end import PowerTransformerEnd
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.branches.transformer.phase_tap_changer import PhaseTapChanger
from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol


class PhaseTapChangerNonLinear(PhaseTapChanger):

    def __init__(self, rdfid, tpe):
        PhaseTapChanger.__init__(self, rdfid, tpe)

        self.voltageStepIncrement: float = 0.0
        self.xMax: float = 0.0
        self.xMin: float = 0.0

        self.register_property(
            name='voltageStepIncrement',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="The voltage step increment on the out of phase winding specified in "
                        "percent of nominal voltage of the transformer end.",
            mandatory=True,
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='xMax',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="he reactance depend on the tap position according to a `u` shaped curve. "
                        "The maximum reactance (xMax) appear at the low and high tap positions.",
            mandatory=True,
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='xMin',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="The reactance depend on the tap position according to a `u` shaped curve. "
                        "The minimum reactance (xMin) appear at the mid tap position.",
            mandatory=True,
            profiles=[cgmesProfile.EQ])
