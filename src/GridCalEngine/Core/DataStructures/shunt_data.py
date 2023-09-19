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
import scipy.sparse as sp
import GridCalEngine.Core.topology as tp
from GridCalEngine.basic_structures import Vec, CxVec, IntVec, StrVec


class ShuntData:
    """
    ShuntData
    """

    def __init__(self, nelm: int, nbus: int):
        """
        Shunt data arrays
        :param nelm: number of shunts
        :param nbus: number of buses
        """
        self.nelm: int = nelm
        self.nbus: int = nbus

        self.names: StrVec = np.empty(nelm, dtype=object)
        self.idtag: StrVec = np.empty(nelm, dtype=object)

        self.active: IntVec = np.zeros(nelm, dtype=bool)
        self.admittance: CxVec = np.zeros(nelm, dtype=complex)

        self.controlled: IntVec = np.zeros(nelm, dtype=bool)
        self.b_min: Vec = np.zeros(nelm, dtype=float)
        self.b_max: Vec = np.zeros(nelm, dtype=float)

        self.C_bus_elm: sp.lil_matrix = sp.lil_matrix((nbus, nelm), dtype=int)

        self.original_idx: IntVec = np.zeros(nelm, dtype=int)

    def slice(self, elm_idx: IntVec, bus_idx: IntVec) -> "ShuntData":
        """
        Slice shunt data by given indices
        :param elm_idx: array of branch indices
        :param bus_idx: array of bus indices
        :return: new ShuntData instance
        """

        data = ShuntData(nelm=len(elm_idx), nbus=len(bus_idx))

        data.names = self.names[elm_idx]
        data.idtag = self.idtag[elm_idx]

        data.controlled = self.controlled[elm_idx]
        data.b_min = self.b_min[elm_idx]
        data.b_max = self.b_max[elm_idx]

        data.active = self.active[elm_idx]
        data.admittance = self.admittance[elm_idx]

        data.C_bus_elm = self.C_bus_elm[np.ix_(bus_idx, elm_idx)]

        data.original_idx = elm_idx

        return data

    def copy(self) -> "ShuntData":
        """
        Get deep copy of this structure
        :return: new ShuntData instance
        """

        data = ShuntData(nelm=self.nelm, nbus=self.nbus)

        data.names = self.names.copy()
        data.idtag = self.idtag.copy()

        data.controlled = self.controlled.copy()
        data.b_min = self.b_min.copy()
        data.b_max = self.b_max.copy()

        data.active = self.active.copy()
        data.admittance = self.admittance.copy()

        data.C_bus_elm = self.C_bus_elm.copy()

        data.original_idx = self.original_idx.copy()

        return data

    def get_island(self, bus_idx: IntVec):
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

    def get_controlled_per_bus(self) -> IntVec:
        """
        Get controlled per bus
        :return:
        """
        return self.C_bus_elm * (self.controlled * self.active)

    def get_injections_per_bus(self) -> CxVec:
        """
        Get Injections per bus
        :return:
        """
        return self.C_bus_elm * (self.admittance * self.active)

    def get_b_max_per_bus(self) -> Vec:
        """
        Get Bmax per bus
        :return:
        """
        return self.C_bus_elm * (self.b_max * self.active)

    def get_b_min_per_bus(self) -> Vec:
        """
        Get Bmin per bus
        :return:
        """
        return self.C_bus_elm * (self.b_min * self.active)

    def __len__(self) -> int:
        return self.nelm

    def get_bus_indices(self) -> IntVec:
        """
        Get the bus indices
        :return: array with the bus indices
        """
        return tp.get_csr_bus_indices(self.C_bus_elm.tocsr())
