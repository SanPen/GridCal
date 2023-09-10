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
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.substation.base_voltage import BaseVoltage
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.substation.substation import Substation
from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol


class VoltageLevel(IdentifiedObject):

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.highVoltageLimit: float = 0.0
        self.lowVoltageLimit: float = 0.0

        self.Substation: Substation | None = None
        self.BaseVoltage: BaseVoltage | None = None

        self.register_property(name='highVoltageLimit',
                               class_type=float,
                               multiplier=UnitMultiplier.k,
                               unit=UnitSymbol.V,
                               description="The bus bar's high voltage limit",
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='lowVoltageLimit',
                               class_type=float,
                               multiplier=UnitMultiplier.k,
                               unit=UnitSymbol.V,
                               description="The bus bar's low voltage limit",
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='Substation',
                               class_type=Substation,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="",
                               mandatory=True,
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='BaseVoltage',
                               class_type=BaseVoltage,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="",
                               mandatory=True,
                               profiles=[cgmesProfile.EQ])
