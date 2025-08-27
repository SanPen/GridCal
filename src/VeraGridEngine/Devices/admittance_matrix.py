# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from typing import Dict, Union, List
import numpy as np
from VeraGridEngine.basic_structures import CxMat, Mat


def list_to_matrix(data: List[List[float]] | None, size: int) -> Mat:
    """
    Attempts converting a list of lists to matrix
    :param data: list of lists of floats representing a matrix
    :param size: size of the matrix (square)
    :return: Numpy array representing a matrix
    """
    if size > 0 and len(data) > 0:
        if data is None:
            return np.zeros((size, size), dtype=complex)
        else:

            candidate = np.array(data)

            if candidate.ndim == 2:
                if candidate.shape[1] == size and candidate.shape[0] == size:
                    return candidate
                else:
                    raise ValueError("AdmittanceMatrix values must be a square matrix")
            else:
                raise ValueError("AdmittanceMatrix values must be a matrix")
    else:
        return np.zeros((size, size), dtype=complex)


class AdmittanceMatrix:
    """
    This is the admittance matrix to store the three-phases admittance of a branch
    """

    def __init__(self, size: int = 0):
        """
        Constructor
        :param size: size of the matrix (0 to 4)
        """
        self.__size: int = size

        self.__values: CxMat = np.zeros((size, size), dtype=complex)

        self._phA: int = 0
        self._phB: int = 0
        self._phC: int = 0

    @property
    def phA(self):
        return self._phA

    @phA.setter
    def phA(self, val: int):
        if isinstance(val, int):
            self._phA = val
        else:
            raise ValueError(f'{val} is not an int')

    @property
    def phB(self):
        return self._phB

    @phB.setter
    def phB(self, val: int):
        if isinstance(val, int):
            self._phB = val
        else:
            raise ValueError(f'{val} is not an int')

    @property
    def phC(self):
        return self._phC

    @phC.setter
    def phC(self, val: int):
        if isinstance(val, int):
            self._phC = val
        else:
            raise ValueError(f'{val} is not an int')

    @property
    def size(self) -> int:
        return self.__size

    @size.setter
    def size(self, size: int) -> None:
        self.__size = size
        self.__values: CxMat = np.zeros((size, size), dtype=complex)

    @property
    def values(self) -> CxMat:
        return self.__values

    @values.setter
    def values(self, value: CxMat):
        if isinstance(value, np.ndarray):
            if value.dtype == complex:
                self.__values = value
                self.__size = value.shape[0]
            else:
                raise ValueError("AdmittanceMatrix only supports complex values")
        else:
            raise ValueError("AdmittanceMatrix only supports complex numpy arrays")

    def to_dict(self) -> Dict[str, Union[str, float]]:
        """
        Get a dictionary representation of the tap
        :return:
        """
        return {
            "size": self.__size,
            "values_r": self.__values.real.tolist(),
            "values_i": self.__values.imag.tolist(),
            "phase_a": self._phA,
            "phase_b": self._phB,
            "phase_c": self._phC,
        }

    def parse(self, data: Dict[str, Union[str, float, int]]) -> None:
        """
        Parse the tap data
        :param data: dictionary representation of the tap
        """

        self.__size: int = data.get("size", 3)

        data_r = list_to_matrix(data.get("values_r", None), self.__size)
        data_i = list_to_matrix(data.get("values_i", None), self.__size)
        self.phA = data.get("phase_a", 0)
        self.phB = data.get("phase_b", 0)
        self.phC = data.get("phase_c", 0)

        self.__values = data_r + 1j * data_i

    def __eq__(self, other: "AdmittanceMatrix") -> bool:

        if self.size != other.size:
            return False

        if not np.allclose(self.values, other.values, atol=1e-10):
            return False

        return True
