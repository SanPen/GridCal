# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

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

    def slice(self, elm_idx: IntVec, bus_idx: IntVec, bus_map: IntVec) -> "BatteryData":
        """
        Slice battery data by given indices
        :param elm_idx: array of element indices
        :param bus_idx: array of bus indices
        :param bus_map: map from bus to index
        :return: new BatteryData instance
        """

        data = super().slice(elm_idx, bus_idx, bus_map)

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
