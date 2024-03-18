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
from typing import List, Tuple
import numpy as np


class LineLocations:
    """
    LineLocations
    """
    def __init__(self, n_points: int):
        """

        :param n_points:
        """
        self.data = np.zeros((n_points, 3))

    def parse(self, data: List[Tuple[float, float, float]]):
        """
        Parse Json data
        :param data: List of lists with (latitude, longitude, altitude)
        """
        if len(data) > 0:
            values = np.array(data)
            self.set(data=values)
        else:
            self.data = np.zeros((0, 3))

    def set(self, data: np.ndarray):
        """
        Parse Json data
        :param data: List of lists with (latitude, longitude, altitude)
        """
        if data.ndim == 2:
            if data.shape[1] == 3:
                self.data = data
            else:
                raise ValueError('Locations data does not have exactly 3 columns')
        else:
            raise ValueError('Location data must be 2-dimensional: (n_points, 3)')

    def to_list(self) -> List[Tuple[float, float, float]]:
        """
        Convert data to list of lists for Json usage
        :return: List[Tuple[float, float, float]] -> [(latitude, longitude, altitude)]
        """
        return self.data.tolist()

    def __eq__(self, other: "LineLocations") -> bool:
        """
        Equality compare
        In this case we check that the numerical data is close enough
        :param other: LineLocations object
        :return: Close enough?
        """
        return np.allclose(self.data, other.data, atol=1e-6)
