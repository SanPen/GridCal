# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from typing import Dict, Union
import numpy as np
from GridCalEngine.basic_structures import CxMat


class AdmittanceMatrix:
    """
    This is the admittance matrix to store the three-phases admittance of a branch
    """

    def __init__(self, size: int = 3):
        """
        Constructor
        :param size: size of the matrix (3 or 4
        """
        self.__size: int = size

        self.__values: CxMat = np.zeros((size, size), dtype=complex)

    @property
    def values(self) -> CxMat:
        return self.__values

    @values.setter
    def values(self, value: CxMat):
        if isinstance(value, np.ndarray):
            if value.dtype == complex:
                self.__values = value
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
            "values": self.__values.tolist(),
        }

    def parse(self, data: Dict[str, Union[str, float]]) -> None:
        """
        Parse the tap data
        :param data: dictionary representation of the tap
        """

        self.__size: int = data.get("size", 3)

        data = data.get("values", None)

        if data is None:
            self.__values = np.zeros((self.__size, self.__size), dtype=complex)
        else:
            candidate = np.array(data)

            if candidate.ndim == 2:
                if candidate.shape[1] == self.__size and candidate.shape[0] == self.__size:
                    self.values = candidate
                else:
                    raise ValueError("AdmittanceMatrix values must be a square matrix")
            else:
                raise ValueError("AdmittanceMatrix values must be a matrix")
