# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
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
from GridCalEngine.enumerations import TapChangerTypes


class TapChanger:
    """
    Tap changer
    """

    def __init__(self,
                 total_positions: int = 5,
                 neutral_position: int = 2,
                 dV: float = 0.01,
                 asymmetry_angle=90,
                 tpe: TapChangerTypes = TapChangerTypes.Symmetrical) -> None:
        """

        :param total_positions:
        :param neutral_position:
        :param dV: per unit of voltage increment
        :param asymmetry_angle:
        :param tpe:
        """

        self.asymmetry_angle = np.deg2rad(asymmetry_angle)

        self.steps = np.array([dV * i for i in range(total_positions)]) - neutral_position * dV

        self.neutral_pos = neutral_position

        self.tap_position = neutral_position

        self.tpe = tpe

    def reset(self) -> None:
        """
        Resets the tap changer to the neutral position
        """
        self.tap_position = self.neutral_pos

    def tap_up(self) -> None:
        """
        Go to the next upper tap position
        """
        if self.tap_position + 1 < len(self.steps):
            self.tap_position += 1

    def tap_down(self) -> None:
        """
        Go to the next upper tap position
        """
        if self.tap_position - 1 > 0:
            self.tap_position -= 1

    def ndu(self) -> float:
        """
        Return the total tap voltage
        :return:
        """
        return self.steps[self.tap_position]

    def get_tap_phase(self) -> float:
        """
        Get the tap phase in radians
        :return: phase in radians
        """
        if self.tpe == TapChangerTypes.VoltageRegulation:
            return 0.0

        elif self.tpe == TapChangerTypes.Asymmetrical:
            ndu = self.ndu()
            a = np.arctan((ndu * np.sin(self.asymmetry_angle)) / (1.0 + ndu * np.cos(self.asymmetry_angle)))
            return a

        elif self.tpe == TapChangerTypes.Asymmetrical90:
            ndu = self.ndu()
            a = np.arctan(ndu)
            return a

        elif self.tpe == TapChangerTypes.Symmetrical:
            ndu = self.ndu()
            a = 2.0 * np.arctan(ndu / 2.0)
            return a

        else:
            raise Exception("Unknown tap phase type")

    def get_tap_module(self) -> float:
        """
        Get the tap voltage regulation module
        :return: voltage regulation module
        """

        if self.tpe == TapChangerTypes.VoltageRegulation:
            ndu = self.ndu()
            return 1.0 / (1.0 - ndu) if ndu != 0.0 else 0.0

        elif self.tpe == TapChangerTypes.Asymmetrical:
            ndu = self.ndu()
            rho = 1.0 / np.sqrt(
                (ndu * np.sin(self.asymmetry_angle)) ** 2 + (1.0 + ndu * np.cos(self.asymmetry_angle)) ** 2)
            return rho

        elif self.tpe == TapChangerTypes.Asymmetrical90:
            ndu = self.ndu()
            rho = 1.0 / np.sqrt(ndu ** 2 + 1.0)
            return rho

        elif self.tpe == TapChangerTypes.Symmetrical:
            return 1.0
        else:
            raise Exception("Unknown tap phase type")

    def set_tap_module(self, tap_module: float):
        """
        Set the integer tap position corresponding to a tap value

        Attribute:

            **tap_module** (float): Tap module centered around 1.0

        """
        if tap_module == 1.0:
            self.tap_position = 0
        elif tap_module > 1:
            self.tap_position = round((tap_module - 1.0) / self.inc_reg_up)
        elif tap_module < 1:
            self.tap_position = -round((1.0 - tap_module) / self.inc_reg_down)

    def __eq__(self, other: "TapChanger") -> bool:
        """
        Equality check
        :param other: TapChanger
        :return: ok?
        """
        return ((self.asymmetry_angle == other.asymmetry_angle)
                and (np.all(self.steps == other.steps))
                and (self.neutral_pos == other.neutral_pos)
                and (self.tap_position == other.tap_position)
                and (self.tpe == other.tpe))

    def __str__(self):

        return "Tap changer"
