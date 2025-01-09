# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
import pandas as pd
from typing import Union, Dict
from GridCalEngine.Utils.NumericalMethods.common import find_closest_number
from GridCalEngine.enumerations import TapChangerTypes
from GridCalEngine.basic_structures import Logger


class TapChanger:
    """
    Tap changer
    """

    def __init__(self,
                 total_positions: int = 5,
                 neutral_position: int = 2,
                 normal_position: int = 2,
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
        neutral_position = int(neutral_position)
        total_positions = int(total_positions)
        if neutral_position >= total_positions:
            neutral_position = total_positions - 1
            print(f"Neutral position exceeding the total positions {neutral_position} >= {total_positions}")

        # asymmetry angle (Theta)
        self._asymmetry_angle = float(asymmetry_angle)

        # total number of positions
        self._total_positions = int(total_positions)

        # voltage increment in p.u.
        self._dV = float(dV)

        # neutral position
        self._neutral_position = int(neutral_position)

        # normal position
        self._normal_position = int(normal_position)

        # index with respect to the neutral position
        self._tap_position = int(neutral_position)

        # tap changer mode
        self._tc_type: TapChangerTypes = tc_type

        # for CGMES compatibility we store if the low step is negative
        self._negative_low = False

        # Calculated arrays
        self._ndv = np.zeros(self._total_positions)  # increment of voltage positions
        self._tau_array = np.zeros(self._total_positions)  # tap phase positions
        self._m_array = np.zeros(self._total_positions)  # tap module positions
        self._k_re_array = np.ones(self._total_positions)  # impedance correction positions (real)
        self._k_im_array = np.ones(self._total_positions)  # impedance correction positions (imag)
        self.recalc()

    @property
    def asymmetry_angle(self) -> float:
        return self._asymmetry_angle

    @asymmetry_angle.setter
    def asymmetry_angle(self, asymmetry_angle: float) -> None:
        self._asymmetry_angle = float(asymmetry_angle)
        self.recalc()

    @property
    def dV(self) -> float:
        return self._dV

    @dV.setter
    def dV(self, dV: float) -> None:
        self._dV = float(dV)
        self.recalc()

    @property
    def neutral_position(self) -> int:
        return self._neutral_position

    @neutral_position.setter
    def neutral_position(self, neutral_position: int) -> None:
        self._neutral_position = int(neutral_position)
        self.recalc()

    @property
    def normal_position(self) -> int:
        return self._normal_position

    @normal_position.setter
    def normal_position(self, normal_position: int) -> None:
        self._normal_position = int(normal_position)
        self.recalc()

    @property
    def tc_type(self) -> TapChangerTypes:
        return self._tc_type

    @tc_type.setter
    def tc_type(self, tc_type: TapChangerTypes) -> None:
        self._tc_type = tc_type
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
        Set the tap position (zero indexing)
        :param val: tap value
        """
        if val < self._total_positions:
            self._tap_position = int(val)
            self.recalc()
        else:
            print(f"Max tap changer value exceeded {val} > {self._total_positions}")

    @property
    def neutral_position(self) -> int:
        """
        Get the neutral position
        :return: int
        """
        return self._neutral_position

    @neutral_position.setter
    def neutral_position(self, val: int):
        """
        Set the neutral position
        :param val: neutral position value
        """
        self._neutral_position = int(val)
        self.recalc()

    @property
    def tap_modules_array(self):
        """
        Get the tap modules array
        :return:
        """
        return self._m_array

    @property
    def tap_angles_array(self):
        """

        :return:
        """
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
            "normal_position": self.normal_position,
            "tap_position": self._tap_position,
            "type": str(self.tc_type),
            "negative_low": self._negative_low,
            "impedance_correction_real": self._k_re_array.tolist(),
            "impedance_correction_imag": self._k_im_array.tolist(),
        }

    def parse(self, data: Dict[str, Union[str, float]], logger: Logger = Logger()) -> None:
        """
        Parse the tap data
        :param data: dictionary representation of the tap
        :param logger: logger instance
        """
        self.asymmetry_angle = data.get("asymmetry_angle", 90.0)
        self.total_positions = data.get("total_positions", 5)
        self.dV = data.get("dV", 0.01)
        self.neutral_position = data.get("neutral_position", 2)
        self.normal_position = data.get("normal_position", 2)
        self.tap_position = data.get("tap_position", 2)
        self.tc_type = TapChangerTypes(data.get("type", TapChangerTypes.NoRegulation.value))
        self._negative_low = data.get("negative_low", False)

        # parse the impedance corerction factors

        _k_re_array = data.get("impedance_correction_real", None)
        if _k_re_array is not None:
            if len(_k_re_array) == self.total_positions:
                self._k_re_array = np.array(_k_re_array)
            else:
                self._k_re_array = np.ones(self._total_positions)
                logger.add_warning("Incorrect impedance table length")

        _k_im_array = data.get("impedance_correction_imag", None)
        if _k_im_array is not None:
            if len(_k_im_array) == self.total_positions:
                self._k_im_array = np.array(_k_im_array)
            else:
                self._k_im_array = np.ones(self._total_positions)
                logger.add_warning("Incorrect impedance table length")

        self.recalc()

    def to_df(self) -> pd.DataFrame:
        """
        Get DaraFrame of the values
        :return: DataFrame
        """
        return pd.DataFrame(data={
            'Steps': self._ndv,
            'tau': self._tau_array,
            'm': self._m_array,
            'impedance_correction_real': self._k_re_array,
            'impedance_correction_imag': self._k_im_array,
        })

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
        if self.tap_position < len(self._tau_array):
            return float(self._tau_array[self.tap_position])
        else:
            print("tap position out of range")
            return 0.0

    def get_tap_module(self) -> float:
        """
        Get the tap voltage regulation module
        :return: voltage regulation module
        """
        if self.tap_position < len(self._m_array):
            return float(self._m_array[self.tap_position])
        else:
            print("tap position out of range")
            return 1.0

    def set_tap_module(self, tap_module: float) -> float:
        """
        Set the tap position closest to the tap module
        :param tap_module: float value of the tap module
        """
        if self.tc_type != TapChangerTypes.NoRegulation:
            pos, val = find_closest_number(arr=self._m_array, target=tap_module)
            self.tap_position = pos
            return val
        else:
            return 1.0

    def set_tap_phase(self, tap_phase: float) -> float:
        """
        Set the tap position closest to the tap phase
        :param tap_phase: float value of the tap phase
        """
        if self.tc_type != TapChangerTypes.NoRegulation:
            pos, val = find_closest_number(arr=self._tau_array, target=tap_phase)
            self.tap_position = pos
            return val
        else:
            return 0.0

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
        Min tap phase, computed on the fly
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
                and np.allclose(self.dV, other.dV, atol=1e-06)
                and (self.neutral_position == other.neutral_position)
                and (self.normal_position == other.normal_position)
                and (self.tap_position == other.tap_position)
                and (self.tc_type == other.tc_type))

    def __str__(self) -> str:
        """
        String representation
        :return:
        """
        return "Tap changer"

    def init_from_cgmes(self,
                        low: int,
                        high: int,
                        normal: int,
                        neutral: int,
                        stepVoltageIncrement: float,
                        step: int,
                        asymmetry_angle: float = 0.0,
                        tc_type: TapChangerTypes = TapChangerTypes.NoRegulation) -> None:
        """
        Import TapChanger object from CGMES

        :param low:
        :param high:
        :param normal:
        :param neutral:
        :param stepVoltageIncrement:
        :param step:
        :param asymmetry_angle:
        :param tc_type:
        :return:
        """

        self._negative_low = low < 0

        if self._negative_low:
            self.asymmetry_angle = float(asymmetry_angle)  # asymmetry angle (Theta)
            self._total_positions = int(high - low + 1)  # total number of positions
            self.dV = float(stepVoltageIncrement / 100)  # voltage increment in p.u.
            self.neutral_position = int(neutral - low + 1)  # neutral position
            self.normal_position = int(normal - low + 1)  # normal position
            self._tap_position = int(self.neutral_position + step)  # index with respect to the neutral position
            self.tc_type = tc_type  # tap changer mode

        else:
            self.asymmetry_angle = float(asymmetry_angle)  # asymmetry angle (Theta)
            self._total_positions = int(high - low + 1)  # total number of positions
            self.dV = float(stepVoltageIncrement / 100)  # voltage increment in p.u.
            self.neutral_position = int(neutral)  # neutral position
            self.normal_position = int(normal)  # normal position
            self._tap_position = int(step)  # index with respect to the neutral position
            self.tc_type: TapChangerTypes = tc_type  # tap changer mode

        # Calculated arrays
        self._ndv = np.zeros(self._total_positions)
        self._tau_array = np.zeros(self._total_positions)
        self._m_array = np.zeros(self._total_positions)
        self._k_re_array = np.ones(self._total_positions)  # impedance correction positions (real)
        self._k_im_array = np.ones(self._total_positions)  # impedance correction positions (imag)
        self.recalc()

    def get_cgmes_values(self):
        """
        Returns with values of a Tap Changer in CGMES
        
        :return: 
        :rtype: 
        """

        if self._negative_low:
            low = -self.neutral_position + 1
            high = self.total_positions - self.neutral_position
            normal = self.normal_position + low - 1
            neutral = self.neutral_position + low - 1
            sVI = round(self.dV * 100, 6)
            step = self.tap_position + low - 1
        else:
            low = 0
            high = self.total_positions - 1
            normal = self.normal_position
            neutral = self.neutral_position
            sVI = round(self.dV * 100, 6)
            step = self.tap_position

        return low, high, normal, neutral, sVI, step
