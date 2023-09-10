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
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.branches.transformer.phase_tap_changer_table import PhaseTapChangerTable
from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol


class PhaseTapChangerTablePoint(IdentifiedObject):
    """
    Describes each tap step in the ratio tap changer tabular curve.
    """

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.angle: float = 0.0
        self.PhaseTapChangerTable: PhaseTapChangerTable | None = None

        self.register_property(
            name='angle',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.deg,
            description="The angle difference in degrees.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='PhaseTapChangerTable',
            class_type=PhaseTapChangerTable,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="The table of this point.",
            profiles=[cgmesProfile.EQ])
