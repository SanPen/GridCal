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
import pandas as pd
from typing import Union, Dict
from GridCalEngine.Utils.NumericalMethods.common import find_closest_number
from GridCalEngine.enumerations import TapChangerTypes


class TapChanger:
    """
    Tap changer
    """

    def __init__(self,
                 total_positions: int = 5,
                 neutral_position: int = 2,
                 dV: float = 0.01,
                 asymmetry_angle: float = 90.0,
                 tc_type: TapChangerTypes = TapChangerTypes.NoRegulation) -> None:
        """
        Tap changer
        :param total_positions: Total number of positions
        :param neutral_position: Neutral position
        :param dV: per unit of voltage increment (p.u.)
        :param asymmetry_angle: Asymmetry angle (deg)
        :param tc_type: Tap changer type
        """

        self.asymmetry_angle = asymmetry_angle  # assymetry angle (Theta)
        self._total_positions = total_positions  # total number of positions
        self.dV = dV  # voltage increment in p.u.
        self.neutral_position = neutral_position  # neutral position
        self._tap_position = neutral_position  # index with respect to the neutral position
        self.tc_type = tc_type  # tap changer mode

        # Calculated arrays
        self._ndv = np.zeros(total_positions)
        self._tau_array = np.zeros(total_positions)
        self._m_array = np.zeros(total_positions)
        self.recalc()

    @property
    def total_positions(self) -> int:
        """
        Tap changer total number of positions
        :return: int
        """
        return self._total_positions

    @total_positions.setter
    def total_positions(self, value: int):
        if isinstance(value, int):
            self._total_positions = value
            self.resize()
        else:
            raise TypeError(f'Expected int but got {type(value)}')

    @property
    def tap_position(self) -> int:
        """
        Get the tap position
        :return: int
        """
        return self._tap_position

    @tap_position.setter
    def tap_position(self, val: int):
        """
        Set the tap position
        :param val: tap value
        """
        self._tap_position = val

    @property
    def tap_modules_array(self):
        return self._m_array

    @property
    def tap_angles_array(self):
        return self._tau_array

    def resize(self) -> None:
        """
        Resize and recalc the tap positions array
        """
        self._ndv = np.zeros(self.total_positions)
        self._tau_array = np.zeros(self.total_positions)
        self._m_array = np.zeros(self.total_positions)
        self.recalc()

    def recalc(self) -> None:
        """
        Recalculate the phase and modules corresponding to each tap position
        """
        positions = np.arange(self.total_positions)
        self._ndv = (positions - self.neutral_position) * self.dV
        self._tau_array = self.get_tap_phase2(positions)
        self._m_array = self.get_tap_module2(positions)

    def to_dict(self) -> Dict[str, Union[str, float]]:
        """
        Get a dictionary representation of the tap
        :return:
        """
        return {
            "asymmetry_angle": self.asymmetry_angle,
            "total_positions": self.total_positions,
            "dV": self.dV,
            "neutral_position": self.neutral_position,
            "tap_position": self._tap_position,
            "type": str(self.tc_type)
        }

    def parse(self, data: Dict[str, Union[str, float]]):
        """
        Parse the tap data
        :param data: dictionary representation of the tap
        """
        self.asymmetry_angle = data.get("asymmetry_angle", 90.0)
        self.total_positions = data.get("total_positions", 5)
        self.dV = data.get("dV", 0.01)
        self.neutral_position = data.get("neutral_position", 2)
        self.tap_position = data.get("tap_position", 2)
        self.tc_type = TapChangerTypes(data.get("type", TapChangerTypes.NoRegulation.value))
        self.recalc()

    def to_df(self) -> pd.DataFrame:
        """
        Get DaraFrame of the values
        :return: DataFrame
        """
        return pd.DataFrame(data={'Steps': self._ndv, 'tau': self._tau_array, 'm': self._m_array})

    def reset(self) -> None:
        """
        Resets the tap changer to the neutral position
        """
        self.tap_position = self.neutral_position

    def tap_up(self) -> None:
        """
        Go to the next upper tap position
        """
        if self.tap_position + 1 < len(self._ndv):
            self.tap_position += 1

    def tap_down(self) -> None:
        """
        Go to the next upper tap position
        """
        if self.tap_position - 1 > 0:
            self.tap_position -= 1

    def get_tap_phase2(self, tap_position: Union[int, np.ndarray]) -> Union[float, np.ndarray]:
        """
        Get the tap phase in radians
        :return: phase in radians (single value or array)
        """
        if self.tc_type == TapChangerTypes.NoRegulation:
            if isinstance(tap_position, int):
                return 0.0
            elif isinstance(tap_position, np.ndarray):
                return np.zeros(len(tap_position))
            else:
                raise ValueError("tap position must be int or np.ndarray of int type")

        elif self.tc_type == TapChangerTypes.VoltageRegulation:
            if isinstance(tap_position, int):
                return 0.0
            elif isinstance(tap_position, np.ndarray):
                return np.zeros(len(tap_position))
            else:
                raise ValueError("tap position must be int or np.ndarray of int type")

        elif self.tc_type == TapChangerTypes.Asymmetrical:
            ndu = self._ndv[tap_position]
            theta = np.deg2rad(self.asymmetry_angle)
            a = ndu * np.sin(theta)
            b = ndu * np.cos(theta)
            alpha = np.arctan(a / (1.0 + b))
            return alpha

        elif self.tc_type == TapChangerTypes.Symmetrical:
            ndu = self._ndv[tap_position]
            alpha = 2.0 * np.arctan(ndu / 2.0)
            return alpha

        else:
            raise Exception("Unknown tap phase type")

    def get_tap_module2(self, tap_position: Union[int, np.ndarray]) -> Union[float, np.ndarray]:
        """
        Get the tap voltage regulation module
        :return: voltage regulation module (single value or array)
        """

        if self.tc_type == TapChangerTypes.NoRegulation:
            if isinstance(tap_position, int):
                return 1.0
            elif isinstance(tap_position, np.ndarray):
                return np.ones(len(tap_position))
            else:
                raise ValueError("tap position must be int or np.ndarray of int type")

        elif self.tc_type == TapChangerTypes.VoltageRegulation:
            ndu = self._ndv[tap_position]
            return 1.0 / (1.0 - ndu)

        elif self.tc_type == TapChangerTypes.Asymmetrical:
            ndu = self._ndv[tap_position]
            theta = np.deg2rad(self.asymmetry_angle)
            a = ndu * np.sin(theta)
            b = ndu * np.cos(theta)
            rho = 1.0 / np.sqrt(np.power(a, 2) + np.power(1.0 + b, 2))
            return rho

        elif self.tc_type == TapChangerTypes.Symmetrical:
            if isinstance(tap_position, int):
                return 1.0
            elif isinstance(tap_position, np.ndarray):
                return np.ones(len(tap_position))
            else:
                raise ValueError("tap position must be int or np.ndarray of int type")
        else:
            raise Exception("Unknown tap phase type")

    def get_tap_phase(self) -> float:
        """
        Get the tap phase in radians
        :return: phase in radians
        """
        return self._tau_array[self.tap_position]

    def get_tap_module(self) -> float:
        """
        Get the tap voltage regulation module
        :return: voltage regulation module
        """
        return self._m_array[self.tap_position]

    def set_tap_module(self, tap_module: float) -> float:
        """
        Set the tap position closest to the tap module
        :param tap_module: float value of the tap module
        """
        if self.tc_type != TapChangerTypes.NoRegulation:
            _, val = find_closest_number(arr=self._tau_array, target=tap_module)
            return val

    def get_tap_module_min(self) -> float:
        """
        Min tap module, computed on the fly
        :return: float
        """
        return self.get_tap_module2(tap_position=0)

    def get_tap_module_max(self) -> float:
        """
        Max tap module, computed on the fly
        :return: float
        """
        return self.get_tap_module2(tap_position=self.total_positions - 1)

    def get_tap_phase_min(self) -> float:
        """
        Min tap phase, cputed on the fly
        :return: float
        """
        return self.get_tap_phase2(tap_position=0)

    def get_tap_phase_max(self) -> float:
        """
        Maximum tap phase (calculated)
        :return: float
        """
        return self.get_tap_phase2(tap_position=self.total_positions - 1)

    def __eq__(self, other: "TapChanger") -> bool:
        """
        Equality check
        :param other: TapChanger
        :return: ok?
        """
        return ((self.asymmetry_angle == other.asymmetry_angle)
                and (self.total_positions == other.total_positions)
                and (self.dV == other.dV)
                and (self.neutral_position == other.neutral_position)
                and (self.tap_position == other.tap_position)
                and (self.tc_type == other.tc_type))

    def __str__(self) -> str:
        """
        String representation
        :return:
        """
        return "Tap changer"
