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
from GridCal.Engine.Core.DataStructures.generator_data import GeneratorData
from typing import Union

class BatteryData(GeneratorData):

    def __init__(
            self,
            nelm:int,
            nbus:int
    ):
        """
        Battery data arrays
        :param nelm: number of batteries
        :param nbus: number of buses
        """

        GeneratorData.__init__(
            self,
            nelm=nelm,
            nbus=nbus,
        )

        self.enom: np.ndarray = np.zeros(nelm)
        self.min_soc: np.ndarray = np.zeros(nelm)
        self.max_soc: np.ndarray = np.zeros(nelm)
        self.soc_0: np.ndarray = np.zeros(nelm)
        self.discharge_efficiency: np.ndarray = np.zeros(nelm)
        self.charge_efficiency: np.ndarray = np.zeros(nelm)

    def slice(
            self,
            elm_idx: np.ndarray,
            bus_idx: np.ndarray,
            time_idx: Union[int, None] = None):
        """
        Slice battery data by given indices
        :param elm_idx: array of element indices
        :param bus_idx: array of bus indices
        :param time_idx: array of time indices
        :return: new BatteryData instance
        """

        data = super().slice(elm_idx, bus_idx)

        data.enom = self.enom[elm_idx]
        data.min_soc = self.min_soc[elm_idx]
        data.max_soc = self.max_soc[elm_idx]
        data.soc_0 = self.soc_0[elm_idx]
        data.discharge_efficiency = self.discharge_efficiency[elm_idx]
        data.charge_efficiency = self.charge_efficiency[elm_idx]

        return data

