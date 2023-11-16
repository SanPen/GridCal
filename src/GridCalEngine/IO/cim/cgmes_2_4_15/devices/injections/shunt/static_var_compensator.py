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
from GridCalEngine.IO.cim.cgmes_2_4_15.cgmes_enums import SVCControlMode, cgmesProfile
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.substation.base_voltage import BaseVoltage
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.injections.regulating_cond_eq import RegulatingCondEq
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.injections.regulating_control import RegulatingControl
from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol


class StaticVarCompensator(RegulatingCondEq):

    def __init__(self, rdfid, tpe):
        RegulatingCondEq.__init__(self, rdfid, tpe)

        self.q: float = 0.0
        self.capacitiveRating: float = 0.0  # S
        self.inductiveRating: float = 0.0  # S
        self.slope: float = 0.0  # kV/MVAr
        self.sVCControlMode: SVCControlMode = SVCControlMode.volt
        self.voltageSetPoint: float = 0.0

        self.RegulatingControl: RegulatingControl | None = None
        self.EquipmentContainer: IdentifiedObject | None = None
        self.BaseVoltage: BaseVoltage | None = None

        self.register_property(
            name='q',
            class_type=float,
            multiplier=UnitMultiplier.M,
            unit=UnitSymbol.VAr,
            description="",
            profiles=[cgmesProfile.SSH])

        self.register_property(
            name='capacitiveRating',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.ohm,
            description="Maximum available capacitive reactance.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='inductiveRating',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.ohm,
            description="Maximum available inductive reactance.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='slope',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.kVperMVAr,
            description="The characteristics slope of an SVC defines how the reactive "
                        "power output changes in proportion to the difference between the "
                        "regulated bus voltage and the voltage set point.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='sVCControlMode',
            class_type=SVCControlMode,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="SVC control mode.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='voltageSetPoint',
            class_type=float,
            multiplier=UnitMultiplier.k,
            unit=UnitSymbol.V,
            description="The reactive power output of the SVC is proportional to the difference between "
                        "the voltage at the regulated bus and the voltage setpoint. When the regulated bus "
                        "voltage is equal to the voltage setpoint, the reactive power output is zero.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='RegulatingControl',
            class_type=RegulatingControl,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='BaseVoltage',
            class_type=BaseVoltage,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='EquipmentContainer',
            class_type=IdentifiedObject,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="",
            profiles=[cgmesProfile.EQ])
