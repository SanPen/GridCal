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
import numpy as np
from GridCalEngine.IO.cim.cgmes_2_4_15.cgmes_enums import cgmesProfile
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.data_logger import DataLogger


class LoadResponseCharacteristic(IdentifiedObject):

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.exponentModel: bool = False
        self.pVoltageExponent: float = 0.0
        self.qVoltageExponent: float = 0.0
        self.pFrequencyExponent: float = 0.0
        self.qFrequencyExponent: float = 0.0

        self.pConstantCurrent: float = 0.0
        self.pConstantImpedance: float = 0.0
        self.pConstantPower: float = 0.0

        self.qConstantCurrent: float = 0.0
        self.qConstantImpedance: float = 0.0
        self.qConstantPower: float = 0.0

        self.register_property(
            name='exponentModel',
            class_type=bool,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Indicates the exponential voltage dependency model is to be used. "
                        "If false, the coefficient model is to be used. "
                        "The exponential voltage dependency model consist of the attributes "
                        "- pVoltageExponent "
                        "- qVoltageExponent. "
                        "The coefficient model consist of the attributes "
                        "- pConstantImpedance "
                        "- pConstantCurrent "
                        "- pConstantPower "
                        "- qConstantImpedance "
                        "- qConstantCurrent "
                        "- qConstantPower."
                        "The sum of pConstantImpedance, pConstantCurrent and pConstantPower shall equal 1. "
                        "The sum of qConstantImpedance, qConstantCurrent and qConstantPower shall equal 1.",
            mandatory=True,
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='pVoltageExponent',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Exponent of per unit voltage effecting real power.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='qVoltageExponent',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Exponent of per unit voltage effecting reactive power.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='pFrequencyExponent',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Exponent of per unit frequency effecting active power.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='qFrequencyExponent',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Exponent of per unit frequency effecting reactive power.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='pConstantImpedance',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Portion of active power load modeled as constant impedance.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='pConstantCurrent',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Portion of active power load modeled as constant current.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='pConstantPower',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Portion of active power load modeled as constant power.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='qConstantImpedance',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Portion of reactive power load modeled as constant impedance.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='qConstantCurrent',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Portion of reactive power load modeled as constant current.",
            profiles=[cgmesProfile.EQ])

        self.register_property(
            name='qConstantPower',
            class_type=float,
            multiplier=UnitMultiplier.none,
            unit=UnitSymbol.none,
            description="Portion of reactive power load modeled as constant power.",
            profiles=[cgmesProfile.EQ])

    def check(self, logger: DataLogger):
        """
        Check OCL rules
        :param logger:
        :return:
        """
        err_counter = 0
        if self.exponentModel:
            if self.pVoltageExponent not in self.parsed_properties.keys():
                err_counter += 1
                logger.add_error(msg="OCL rule violation: pVoltageExponent not specified",
                                 device=self.rdfid,
                                 device_class="LoadResponseCharacteristic",
                                 expected_value="Existence of pVoltageExponent")

            if self.qVoltageExponent not in self.parsed_properties.keys():
                err_counter += 1
                logger.add_error(msg="OCL rule violation: qVoltageExponent not specified",
                                 device=self.rdfid,
                                 device_class="LoadResponseCharacteristic",
                                 expected_value="Existence of qVoltageExponent")
        else:
            if self.pConstantCurrent not in self.parsed_properties.keys():
                err_counter += 1
                logger.add_error(msg="OCL rule violation: pConstantCurrent not specified",
                                 device=self.rdfid,
                                 device_class="LoadResponseCharacteristic",
                                 expected_value="Existence of pConstantCurrent")

            if self.pConstantPower not in self.parsed_properties.keys():
                err_counter += 1
                logger.add_error(msg="OCL rule violation: pConstantPower not specified",
                                 device=self.rdfid,
                                 device_class="LoadResponseCharacteristic",
                                 expected_value="Existence of pConstantPower")

            if self.pConstantImpedance not in self.parsed_properties.keys():
                err_counter += 1
                logger.add_error(msg="OCL rule violation: pConstantImpedance not specified",
                                 device=self.rdfid,
                                 device_class="LoadResponseCharacteristic",
                                 expected_value="Existence of pConstantImpedance")

            if self.qConstantCurrent not in self.parsed_properties.keys():
                err_counter += 1
                logger.add_error(msg="OCL rule violation: qConstantCurrent not specified",
                                 device=self.rdfid,
                                 device_class="LoadResponseCharacteristic",
                                 expected_value="Existence of qConstantCurrent")

            if self.qConstantPower not in self.parsed_properties.keys():
                err_counter += 1
                logger.add_error(msg="OCL rule violation: qConstantPower not specified",
                                 device=self.rdfid,
                                 device_class="LoadResponseCharacteristic",
                                 expected_value="Existence of qConstantPower")

            if self.qConstantImpedance not in self.parsed_properties.keys():
                err_counter += 1
                logger.add_error(msg="OCL rule violation: qConstantImpedance not specified",
                                 device=self.rdfid,
                                 device_class="LoadResponseCharacteristic",
                                 expected_value="Existence of qConstantImpedance")

            p_factor = self.pConstantImpedance + self.pConstantCurrent + self.pConstantPower
            q_factor = self.qConstantImpedance + self.qConstantCurrent + self.qConstantPower
            if not np.isclose(p_factor, 1):
                err_counter += 1
                logger.add_error(msg="pConstantImpedance + pConstantCurrent + pConstantPower different from 1",
                                 device=self.rdfid,
                                 device_class="LoadResponseCharacteristic",
                                 expected_value="1.0")

            if not np.isclose(q_factor, 1):
                err_counter += 1
                logger.add_error(msg="qConstantImpedance + qConstantCurrent + qConstantPower different from 1",
                                 device=self.rdfid,
                                 device_class="LoadResponseCharacteristic",
                                 expected_value="1.0")

        return err_counter == 0
