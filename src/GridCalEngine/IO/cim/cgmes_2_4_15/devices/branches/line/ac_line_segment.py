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
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.branches.dipole import DiPole
from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.data_logger import DataLogger


class ACLineSegment(DiPole):

    def __init__(self, rdfid, tpe="ACLineSegment"):
        DiPole.__init__(self, rdfid, tpe)

        self.bch: float = 0.0
        self.gch: float = 0.0
        self.r: float = 0.0
        self.x: float = 0.0

        self.bch0: float = 0.0
        self.gch0: float = 0.0
        self.r0: float = 0.0
        self.x0: float = 0.0

        self.shortCircuitEndTemperature: float = 0.0

        self.length: float = 0.0

        self.BaseVoltage: BaseVoltage | None = None
        # self.EquipmentContainer: EquipmentContainer = None

        self.register_property(name='bch',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.S,
                               description="Positive sequence shunt (charging) susceptance, "
                                           "uniformly distributed, of the entire line section. "
                                           "This value represents the full charging over the "
                                           "full length of the line.",
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='gch',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.S,
                               description="Positive sequence shunt (charging) conductance, "
                                           "uniformly distributed, of the entire line section.",
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='r',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.ohm,
                               description="Positive sequence series resistance of the entire "
                                           "line section.",
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='x',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.ohm,
                               description="Positive sequence series reactance of the entire "
                                           "line section.",
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='bch0',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.S,
                               description="Zero sequence shunt (charging) susceptance, "
                                           "uniformly distributed, of the entire line section.",
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='gch0',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.S,
                               description="Zero sequence shunt (charging) conductance, "
                                           "uniformly distributed, of the entire line section.",
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='r',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.ohm,
                               description="Zero sequence series resistance of the entire "
                                           "line section.",
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='x0',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.ohm,
                               description="Zero sequence series reactance of the entire "
                                           "line section.",
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='length',
                               class_type=float,
                               multiplier=UnitMultiplier.k,
                               unit=UnitSymbol.m,
                               description="Segment length for calculating line "
                                           "section capabilities",
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='shortCircuitEndTemperature',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.degC,
                               description="Maximum permitted temperature"
                                           " at the end of SC for the "
                                           "calculation of minimum "
                                           "short-circuit currents. "
                                           "Used for short circuit data "
                                           "exchange according to IEC "
                                           "60909",
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='BaseVoltage',
                               class_type=BaseVoltage,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="",
                               profiles=[cgmesProfile.EQ])

        # self.register_property(name='EquipmentContainer',
        #                        class_type=EquipmentContainer,
        #                        multiplier=UnitMultiplier.none,
        #                        unit=UnitSymbol.none,
        #                        description="")

    def get_voltage(self, logger: DataLogger):

        if self.BaseVoltage is not None:
            return self.BaseVoltage.nominalVoltage
        else:
            if 'Terminal' in self.references_to_me.keys():
                tps = list(self.references_to_me['Terminal'])

                if len(tps) > 0:
                    tp = tps[0]

                    return tp.get_voltage(logger=logger)
                else:
                    return None
            else:
                return None

    def get_pu_values(self, logger: DataLogger, Sbase: float = 100.0):
        """
        Get the per-unit values of the equivalent PI model
        :param Sbase: Sbase in MVA
        :return: R, X, Gch, Bch
        """
        if self.BaseVoltage is not None:
            Vnom = self.get_voltage(logger=logger)

            if Vnom is not None:

                Zbase = (Vnom * Vnom) / Sbase
                Ybase = 1.0 / Zbase

                # at this point r, x, g, b are the complete values for all the line length
                R = self.r / Zbase
                X = self.x / Zbase
                G = self.gch / Ybase
                B = self.bch / Ybase
                R0 = self.r0 / Zbase
                X0 = self.x0 / Zbase
                G0 = self.gch0 / Ybase
                B0 = self.bch0 / Ybase
            else:
                R = 0
                X = 0
                G = 0
                B = 0
                R0 = 0
                X0 = 0
                G0 = 0
                B0 = 0
        else:
            R = 0
            X = 0
            G = 0
            B = 0
            R0 = 0
            X0 = 0
            G0 = 0
            B0 = 0

        return R, X, G, B, R0, X0, G0, B0

    def get_rate(self):
        return 1e-20
