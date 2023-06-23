# GridCal
# Copyright (C) 2022 Santiago Peñate Vera
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
import scipy.sparse as sp
import GridCal.Engine.Core.topology as tp


class ShuntData:

    def __init__(
            self,
            nelm: int,
            nbus: int,
    ):
        """
        Shunt data arrays
        :param nelm: number of shunts
        :param nbus: number of buses
        :param ntime: time index
        """
        self.nelm: int = nelm

        self.names: np.ndarray = np.empty(nelm, dtype=object)

        self.active: np.ndarray = np.zeros(nelm, dtype=bool)
        self.admittance: np.ndarray = np.zeros(nelm, dtype=complex)

        self.controlled: np.ndarray = np.zeros(nelm, dtype=bool)
        self.b_min: np.ndarray = np.zeros(nelm, dtype=float)
        self.b_max: np.ndarray = np.zeros(nelm, dtype=float)

        self.C_bus_elm: sp.lil_matrix = sp.lil_matrix((nbus, nelm), dtype=int)

        self.original_idx = np.zeros(nelm, dtype=int)

    def slice(
            self,
            elm_idx: np.ndarray,
            bus_idx: np.ndarray,
    ):
        """
        Slice shunt data by given indices
        :param elm_idx: array of branch indices
        :param bus_idx: array of bus indices
        :return: new ShuntData instance
        """

        data = ShuntData(
            nelm=len(elm_idx),
            nbus=len(bus_idx),
        )

        data.names = self.names[elm_idx]

        data.controlled = self.controlled[elm_idx]
        data.b_min = self.b_min[elm_idx]
        data.b_max = self.b_max[elm_idx]

        data.active = self.active[elm_idx]
        data.admittance = self.admittance[elm_idx]

        data.C_bus_elm = self.C_bus_elm[np.ix_(bus_idx, elm_idx)]

        data.original_idx = elm_idx

        return data

    def get_island(
            self,
            bus_idx: np.ndarray,
    ):
        """
        Get the array of shunt indices that belong to the islands given by the bus indices
        :param bus_idx: array of bus indices
        :return: array of island branch indices
        """
        if self.nelm:
            return tp.get_elements_of_the_island(
                C_element_bus=self.C_bus_elm.T,
                island=bus_idx,
                active=self.active,
            )
        else:
            return np.zeros(0, dtype=int)

    def get_controlled_per_bus(self):
        """
        Get controlled per bus
        :return:
        """
        return self.C_bus_elm * (self.controlled * self.active)

    def get_injections_per_bus(self):
        """
        Get Injections per bus
        :return:
        """
        return self.C_bus_elm * (self.admittance * self.active)

    def get_b_max_per_bus(self):
        """
        Get Bmax per bus
        :return:
        """
        return self.C_bus_elm * (self.b_max * self.active)

    def get_b_min_per_bus(self):
        """
        Get Bmin per bus
        :return:
        """
        return self.C_bus_elm * (self.b_min * self.active)

    def __len__(self):
        return self.nelm

