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
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.injections.generation.generating_unit import GeneratingUnit
# from GridCalEngine.IO.cim.cgmes_2_4_15.devices.injections.generation.hydro_pump import HydroPump
import GridCalEngine.IO.cim.cgmes_2_4_15.devices.injections.generation.hydro_pump
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.injections.regulating_cond_eq import RegulatingCondEq
from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol


class RotatingMachine(RegulatingCondEq):

    def __init__(self, rdfid, tpe):
        RegulatingCondEq.__init__(self, rdfid, tpe)

        self.p: float = 0
        self.q: float = 0
        self.GeneratingUnit: GeneratingUnit | None = None
        self.HydroPump: GridCalEngine.IO.cim.cgmes_2_4_15.devices.injections.generation.hydro_pump.HydroPump | None = None
        self.ratedPowerFactor: float = 0.0
        self.ratedS: float = 0.0
        self.ratedU: float = 0.0

        # self.EquipmentContainer: EquipmentContainer = None
        # self.BaseVoltage: BaseVoltage = None

        self.register_property(name='p',
                               class_type=float,
                               multiplier=UnitMultiplier.M,
                               unit=UnitSymbol.W,
                               description="",
                               profiles=[cgmesProfile.SSH])

        self.register_property(name='q',
                               class_type=float,
                               multiplier=UnitMultiplier.M,
                               unit=UnitSymbol.VAr,
                               description="",
                               profiles=[cgmesProfile.SSH])

        self.register_property(name='GeneratingUnit',
                               class_type=GeneratingUnit,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="GeneratingUnit",
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='HydroPump',
                               class_type=GridCalEngine.IO.cim.cgmes_2_4_15.devices.injections.generation.hydro_pump.HydroPump,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="HydroPump",
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='ratedPowerFactor',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.pu,
                               description="ratedPowerFactor",
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='ratedS',
                               class_type=float,
                               multiplier=UnitMultiplier.M,
                               unit=UnitSymbol.VA,
                               description="ratedS",
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='ratedU',
                               class_type=float,
                               multiplier=UnitMultiplier.k,
                               unit=UnitSymbol.V,
                               description="ratedU",
                               profiles=[cgmesProfile.EQ])
