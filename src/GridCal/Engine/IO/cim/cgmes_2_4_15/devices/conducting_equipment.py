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
from GridCal.Engine.IO.cim.cgmes_2_4_15.devices.terminal import Terminal
from GridCal.Engine.IO.cim.cgmes_2_4_15.cim_enums import cgmesProfile
from GridCal.Engine.IO.cim.cgmes_2_4_15.devices.substation.base_voltage import BaseVoltage
from GridCal.Engine.IO.cim.cgmes_2_4_15.devices.equipment import Equipment
from GridCal.Engine.IO.base.units import UnitMultiplier, UnitSymbol


class ConductingEquipment(Equipment):

    def __init__(self, rdfid, tpe):
        Equipment.__init__(self, rdfid, tpe)

        self.BaseVoltage: BaseVoltage = None
        self.Terminals: List[Terminal] = list()
        # self.SvStatus = SvStatus

        self.register_property(name='BaseVoltage',
                               class_type=BaseVoltage,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="BaseVoltage",
                               profiles=[cgmesProfile.EQ, ])
