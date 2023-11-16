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
from GridCalEngine.IO.cim.cgmes_2_4_15.cgmes_enums import ControlAreaTypeKind, cgmesProfile
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.aggregation.energy_area import EnergyArea
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.injections.generation.generating_unit import GeneratingUnit
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol


class ControlArea(IdentifiedObject):

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.type: ControlAreaTypeKind = ControlAreaTypeKind.AGC
        self.netInterchange: float = 0.0
        self.pTolerance: float = 0.0
        self.TieFlow: float = 0.0
        self.EnergyArea: EnergyArea | None = None
        self.ControlAreaGeneratingUnit: GeneratingUnit | None = None

        self.register_property(name='type',
                               class_type=ControlAreaTypeKind,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="The primary type of control area definition used "
                                           "to determine if this is used for automatic "
                                           "generation control, for planning interchange "
                                           "control, or other purposes. A control area "
                                           "specified with primary type of automatic "
                                           "generation control could still be forecast and "
                                           "used as an interchange area in power flow analysis.",
                               profiles=[cgmesProfile.EQ]
                               )

        self.register_property(name='netInterchange',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="",
                               comment='out of the standard',
                               profiles=[cgmesProfile.SSH])

        self.register_property(name='pTolerance',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="",
                               comment='out of the standard',
                               profiles=[cgmesProfile.SSH])

        self.register_property(name='TieFlow',
                               class_type=float,
                               multiplier=UnitMultiplier.M,
                               unit=UnitSymbol.W,
                               description="",
                               comment='out of the standard',
                               profiles=[cgmesProfile.SSH])

        self.register_property(name='EnergyArea',
                               class_type=EnergyArea,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="The energy area that is forecast from this "
                                           "control area specification.",
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='ControlAreaGeneratingUnit',
                               class_type=GeneratingUnit,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="",
                               profiles=[cgmesProfile.EQ])
