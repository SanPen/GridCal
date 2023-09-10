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
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.injections.generation.hydro_power_plant import HydroPowerPlant
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.injections.generation.rotating_machine import RotatingMachine
from GridCalEngine.IO.cim.cgmes_2_4_15.cgmes_enums import cgmesProfile
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.equipment import Equipment
from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol


class HydroPump(Equipment):

    def __init__(self, rdfid, tpe):
        Equipment.__init__(self, rdfid, tpe)
        self.HydroPowerPlant: HydroPowerPlant | None = None
        self.RotatingMachine: RotatingMachine | None = None

        self.register_property(name='HydroPowerPlant',
                               class_type=HydroPowerPlant,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="HydroPowerPlant",
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='RotatingMachine',
                               class_type=RotatingMachine,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="RotatingMachine",
                               profiles=[cgmesProfile.EQ])
