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
from GridCalEngine.DataStructures.generator_data import GeneratorData
from GridCalEngine.basic_structures import Vec, IntVec


class BatteryData(GeneratorData):
    """
    Structure to host the battery compiled data
    """

    def __init__(self, nelm: int, nbus: int):
        """
        Battery data arrays
        :param nelm: number of batteries
        :param nbus: number of buses
        """

        GeneratorData.__init__(self, nelm=nelm, nbus=nbus)

        self.enom: Vec = np.zeros(nelm)
        self.e_min: Vec = np.zeros(nelm)
        self.e_max: Vec = np.zeros(nelm)
        self.min_soc: Vec = np.zeros(nelm)
        self.max_soc: Vec = np.ones(nelm)
        self.soc_0: Vec = np.ones(nelm)
        self.discharge_efficiency: Vec = np.ones(nelm)
        self.charge_efficiency: Vec = np.ones(nelm)
        self.efficiency: Vec = np.ones(nelm)

    def slice(self, elm_idx: IntVec, bus_idx: IntVec) -> "BatteryData":
        """
        Slice battery data by given indices
        :param elm_idx: array of element indices
        :param bus_idx: array of bus indices
        :return: new BatteryData instance
        """

        data = super().slice(elm_idx, bus_idx)

        data.enom = self.enom[elm_idx]
        data.e_min = self.e_min[elm_idx]
        data.e_max = self.e_max[elm_idx]
        data.min_soc = self.min_soc[elm_idx]
        data.max_soc = self.max_soc[elm_idx]
        data.soc_0 = self.soc_0[elm_idx]
        data.discharge_efficiency = self.discharge_efficiency[elm_idx]
        data.charge_efficiency = self.charge_efficiency[elm_idx]
        data.efficiency = self.efficiency[elm_idx]

        return data

    def copy(self) -> "BatteryData":
        """
        Get a deep copy of this object
        :return: new BatteryData instance
        """

        data = super().copy()

        data.enom = self.enom.copy()
        data.e_min = self.e_min.copy()
        data.e_max = self.e_max.copy()
        data.min_soc = self.min_soc.copy()
        data.max_soc = self.max_soc.copy()
        data.soc_0 = self.soc_0.copy()
        data.discharge_efficiency = self.discharge_efficiency.copy()
        data.charge_efficiency = self.charge_efficiency.copy()
        data.efficiency = self.efficiency.copy()

        return data
