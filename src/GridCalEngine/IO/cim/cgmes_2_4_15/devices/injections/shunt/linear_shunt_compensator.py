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
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.injections.shunt.shunt_compensator import ShuntCompensator
from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol


class LinearShuntCompensator(ShuntCompensator):

    def __init__(self, rdfid, tpe="LinearShuntCompensator"):
        ShuntCompensator.__init__(self, rdfid, tpe)

        self.bPerSection: float = 0
        self.gPerSection: float = 0

        self.b0PerSection: float = 0
        self.g0PerSection: float = 0

        self.register_property(
            name='b0PerSection',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.S,
            description="Zero sequence shunt (charging) susceptance per section.",
            profiles=[cgmesProfile.EQ]
        )

        self.register_property(
            name='bPerSection',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.S,
            description="Positive sequence shunt (charging) susceptance per section.",
            profiles=[cgmesProfile.EQ]
        )

        self.register_property(
            name='g0PerSection',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.S,
            description="Zero sequence shunt (charging) conductance per section.",
            profiles=[cgmesProfile.EQ]
        )

        self.register_property(
            name='gPerSection',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.S,
            description="Positive sequence shunt (charging) conductance per section.",
            profiles=[cgmesProfile.EQ]
        )
