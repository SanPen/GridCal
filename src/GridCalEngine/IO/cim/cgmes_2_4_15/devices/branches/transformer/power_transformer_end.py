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
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.branches.transformer.power_transformer import PowerTransformer
from GridCalEngine.IO.cim.cgmes_2_4_15.cgmes_enums import WindingConnection, cgmesProfile
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.substation.base_voltage import BaseVoltage
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.terminal import Terminal
from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol


class PowerTransformerEnd(IdentifiedObject):

    def __init__(self, rdfid="", tpe="PowerTransformerEnd"):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.b: float = 0.0
        self.g: float = 0.0
        self.r: float = 0.0
        self.x: float = 0.0

        self.b0: float = 0.0
        self.g0: float = 0.0
        self.r0: float = 0.0
        self.x0: float = 0.0

        self.rground: float = 0.0
        self.xground: float = 0.0
        self.grounded: bool = False

        self.ratedS: float = 0
        self.ratedU: float = 0

        self.endNumber: int = 0

        self.connectionKind: WindingConnection = WindingConnection.D

        self.phaseAngleClock: int = 0

        self.Terminal: Terminal | None = None
        self.BaseVoltage: BaseVoltage | None = None
        self.PowerTransformer: PowerTransformer | None = None

        self.register_property(name='b',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.S,
                               description="Positive sequence shunt (charging) susceptance, "
                                           "uniformly distributed, of the entire line section. "
                                           "This value represents the full charging over the "
                                           "full length of the line.",
                               profiles=[cgmesProfile.EQ])
        self.register_property(name='g',
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

        self.register_property(name='b0',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.S,
                               description="Zero sequence shunt (charging) susceptance, "
                                           "uniformly distributed, of the entire line section.",
                               profiles=[cgmesProfile.EQ])
        self.register_property(name='g0',
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

        self.register_property(name='rground',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.ohm,
                               description="(for Yn and Zn connections) Resistance part of "
                                           "neutral impedance where 'grounded' is true.",
                               profiles=[cgmesProfile.EQ]
                               )

        self.register_property(name='xground',
                               class_type=float,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.ohm,
                               description="(for Yn and Zn connections) Reactance part of "
                                           "neutral impedance where 'grounded' is true.",
                               profiles=[cgmesProfile.EQ]
                               )

        self.register_property(name='grounded',
                               class_type=bool,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="(for Yn and Zn connections) True if the "
                                           "neutral is solidly grounded.",
                               profiles=[cgmesProfile.EQ]
                               )

        self.register_property(name='endNumber',
                               class_type=int,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="(for Yn and Zn connections) True if the "
                                           "neutral is solidly grounded.",
                               profiles=[cgmesProfile.EQ]
                               )

        self.register_property(name='ratedS',
                               class_type=float,
                               multiplier=UnitMultiplier.M,
                               unit=UnitSymbol.VA,
                               description="Normal apparent power rating. "
                                           "The attribute shall be a positive value. "
                                           "For a two-winding transformer the values for "
                                           "the high and low voltage sides shall be "
                                           "identical.",
                               profiles=[cgmesProfile.EQ]
                               )

        self.register_property(name='ratedU',
                               class_type=float,
                               multiplier=UnitMultiplier.k,
                               unit=UnitSymbol.V,
                               description="Rated voltage: phase-phase for three-phase "
                                           "windings, and either phase-phase or "
                                           "phase-neutral for single-phase windings. A high "
                                           "voltage side, as given by "
                                           "TransformerEnd.endNumber, shall have a ratedU "
                                           "that is greater or equal than ratedU for the "
                                           "lower voltage sides.",
                               profiles=[cgmesProfile.EQ]
                               )

        self.register_property(name='connectionKind',
                               class_type=WindingConnection,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="Kind of connection.",
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='phaseAngleClock',
                               class_type=int,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="Terminal voltage phase angle "
                                           "displacement where 360 degrees are "
                                           "represented with clock hours. The valid "
                                           "values are 0 to 11. For example, for "
                                           "the secondary side end of a transformer "
                                           "with vector group code of 'Dyn11', "
                                           "specify the connection kind as wye with "
                                           "neutral and specify the phase angle of "
                                           "the clock as 11. The clock value of the "
                                           "transformer end number specified as 1, "
                                           "is assumed to be zero. Note the "
                                           "transformer end number is not assumed "
                                           "to be the same as the terminal sequence "
                                           "number.",
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='PowerTransformer',
                               class_type=PowerTransformer,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="The ends of this power transformer.",
                               mandatory=True,
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='Terminal',
                               class_type=Terminal,
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

    def get_voltage(self):

        if self.ratedU > 0:
            return self.ratedU
        else:
            if self.BaseVoltage is not None:
                return self.BaseVoltage.nominalVoltage
            else:
                return None

    def get_pu_values(self, Sbase_system=100):
        """
        Get the per-unit values of the equivalent PI model
        :return: R, X, Gch, Bch
        """
        if self.ratedS > 0 and self.ratedU > 0:
            Zbase = (self.ratedU * self.ratedU) / self.ratedS
            Ybase = 1.0 / Zbase
            machine_to_sys = Sbase_system / self.ratedS
            # at this point r, x, g, b are the complete values for all the line length
            R = self.r / Zbase * machine_to_sys
            X = self.x / Zbase * machine_to_sys
            G = self.g / Ybase * machine_to_sys
            B = self.b / Ybase * machine_to_sys
            R0 = self.r0 / Zbase * machine_to_sys
            X0 = self.x0 / Zbase * machine_to_sys
            G0 = self.g0 / Ybase * machine_to_sys
            B0 = self.b0 / Ybase * machine_to_sys
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
