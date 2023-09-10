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
import GridCalEngine.IO.cim.cgmes_2_4_15.devices.branches.transformer.phase_tap_changer_tabular
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes_2_4_15.cgmes_enums import cgmesProfile


class PhaseTapChangerTable(IdentifiedObject):
    """
    Describes a curve for how the voltage magnitude and impedance varies with the tap step.
    """

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.PhaseTapChangerTabular: GridCalEngine.IO.cim.cgmes_2_4_15.devices.branches.transformer.phase_tap_changer_tabular.PhaseTapChanger = None

        self.register_property(name='PhaseTapChangerTabular',
                               class_type=GridCalEngine.IO.cim.cgmes_2_4_15.devices.branches.transformer.phase_tap_changer_tabular.PhaseTapChanger,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="The phase tap changers to which this phase tap table applies.",
                               profiles=[cgmesProfile.EQ])
