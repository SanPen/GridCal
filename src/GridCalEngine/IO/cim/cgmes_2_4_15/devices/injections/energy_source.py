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
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.conducting_equipment import ConductingEquipment
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.injections.regulating_control import RegulatingControl
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.injections.energy_scheduling_type import EnergySchedulingType
from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol


class EnergySource(ConductingEquipment):

    def __init__(self, rdfid, tpe):
        ConductingEquipment.__init__(self, rdfid, tpe)

        self.activePower: float = 0.0  # [cgmesProfile.SSH.value, ],
        self.reactivePower: float = 0.0  # [cgmesProfile.SSH.value, ],
        self.EnergySchedulingType: EnergySchedulingType = None  # [cgmesProfile.EQ.value, cgmesProfile.EQ_BD.value, ],
        self.nominalVoltage: float = 0.0  # [cgmesProfile.EQ.value, ],
        self.r: float = 0.0  # [cgmesProfile.EQ.value, ],
        self.r0: float = 0.0  # [cgmesProfile.EQ.value, ],
        self.rn: float = 0.0  # [cgmesProfile.EQ.value, ],
        self.voltageAngle: float = 0.0  # [cgmesProfile.EQ.value, ],
        self.voltageMagnitude: float = 0.0  # [cgmesProfile.EQ.value, ],
        self.x: float = 0.0  # [cgmesProfile.EQ.value, ],
        self.x0: float = 0.0  # [cgmesProfile.EQ.value, ],
        self.xn: float = 0.0  # [cgmesProfile.EQ.value, ],
        # self.WindTurbineType3or4Dynamics: WindTurbineType3or4Dynamics = None  # [cgmesProfile.DY.value, ],

        self.register_property(name='activePower',
                               class_type=float,
                               multiplier=UnitMultiplier.M,
                               unit=UnitSymbol.W,
                               description="",
                               profiles=[cgmesProfile.SSH])

        self.register_property(name='reactivePower',
                               class_type=float,
                               multiplier=UnitMultiplier.M,
                               unit=UnitSymbol.VAr,
                               description="",
                               profiles=[cgmesProfile.SSH])

        self.register_property(name='EnergySchedulingType',
                               class_type=EnergySchedulingType,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="",
                               profiles=[cgmesProfile.EQ, cgmesProfile.EQ_BD])

        self.register_property(name='nominalVoltage',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.V,
                               description="",
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='r',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.pu,
                               description="",
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='r0',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.pu,
                               description="",
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='rn',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.pu,
                               description="",
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='x',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.pu,
                               description="",
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='x0',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.pu,
                               description="",
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='xn',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.pu,
                               description="",
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='voltageAngle',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.deg,
                               description="",
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='voltageMagnitude',
                               class_type=float,
                               multiplier=UnitMultiplier.k,
                               unit=UnitSymbol.V,
                               description="",
                               profiles=[cgmesProfile.EQ])

        # self.register_property(name='WindTurbineType3or4Dynamics',
        #                        class_type=WindTurbineType3or4Dynamics,
        #                        multiplier=UnitMultiplier.none,
        #                        unit=UnitSymbol.none,
        #                        description="",
        #                        profiles=[cgmesProfile.DY])