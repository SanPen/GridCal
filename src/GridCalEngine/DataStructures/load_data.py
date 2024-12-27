# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

import numpy as np
import GridCalEngine.Topology.topology as tp
from GridCalEngine.basic_structures import Vec, CxVec, IntVec, StrVec, BoolVec


class LoadData:
    """
    Structure to host the load calculation information
    """

    def __init__(self, nelm: int, nbus: int):
        """
        Load data arrays
        :param nelm: number of load
        :param nbus: number of buses
        """
        self.nelm: int = nelm
        self.nbus: int = nbus

        self.names: StrVec = np.empty(nelm, dtype=object)
        self.idtag: StrVec = np.empty(nelm, dtype=object)

        self.active: BoolVec = np.zeros(nelm, dtype=bool)
        self.S: Vec = np.zeros(nelm, dtype=complex)
        self.I: Vec = np.zeros(nelm, dtype=complex)
        self.Y: Vec = np.zeros(nelm, dtype=complex)

        # reliability
        self.mttf: Vec = np.zeros(nelm, dtype=float)
        self.mttr: Vec = np.zeros(nelm, dtype=float)

        self.bus_idx = np.zeros(nelm, dtype=int)

        self.cost: Vec = np.zeros(nelm, dtype=float)  # load shedding cost

        self.original_idx = np.zeros(nelm, dtype=int)

    def size(self) -> int:
        """
        Get size of the structure
        :return:
        """

        return self.nelm

    def slice(self, elm_idx: IntVec, bus_idx: IntVec, bus_map: IntVec) -> "LoadData":
        """
        Slice load data by given indices
        :param elm_idx: array of branch indices
        :param bus_idx: array of bus indices
        :param bus_map: map from bus index to island bus index {int(o): i for i, o in enumerate(bus_idx)}
        :return: new LoadData instance
        """

        data = LoadData(nelm=len(elm_idx), nbus=len(bus_idx))

        data.names = self.names[elm_idx]
        data.idtag = self.idtag[elm_idx]

        data.active = self.active[elm_idx]
        data.S = self.S[elm_idx]
        data.I = self.I[elm_idx]
        data.Y = self.Y[elm_idx]

        data.mttf = self.mttf[elm_idx]
        data.mttr = self.mttr[elm_idx]

        data.bus_idx = self.bus_idx[elm_idx]

        # Remapping of the buses
        for k in range(data.nelm):
            data.bus_idx[k] = bus_map[data.bus_idx[k]]

            if data.bus_idx[k] == -1:
                data.active[k] = 0

        data.cost = self.cost[elm_idx]

        data.original_idx = elm_idx

        return data

    def remap(self, bus_map_arr: IntVec):
        """
        Remapping of the elm buses
        :param bus_map_arr: array of old-to-new buses
        """
        for k in range(self.nelm):
            i = self.bus_idx[k]
            new_i = bus_map_arr[i]
            self.bus_idx[k] = new_i

    def copy(self) -> "LoadData":
        """
        Get a deep copy of this structure
        :return: new LoadData instance
        """

        data = LoadData(nelm=self.nelm, nbus=self.nbus)

        data.names = self.names.copy()
        data.idtag = self.idtag.copy()

        data.active = self.active.copy()
        data.S = self.S.copy()
        data.I = self.I.copy()
        data.Y = self.Y.copy()

        data.mttf = self.mttf.copy()
        data.mttr = self.mttr.copy()

        data.bus_idx = self.bus_idx.copy()

        data.cost = self.cost.copy()

        data.original_idx = self.original_idx.copy()

        return data

    def get_effective_load(self) -> CxVec:
        """
        Get effective load
        :return:
        """
        return self.S * self.active.astype(int)

    def get_linear_effective_load(self) -> Vec:
        """
        Get effective load
        :return:
        """
        return self.S.real * self.active

    def get_injections_per_bus(self) -> CxVec:
        """
        Get Injections per bus with sign
        :return:
        """
        return -tp.sum_per_bus_cx(self.nbus, self.bus_idx, self.get_effective_load())

    def get_linear_injections_per_bus(self) -> Vec:
        """
        Get Injections per bus with sign
        :return:
        """
        return -tp.sum_per_bus(self.nbus, self.bus_idx, self.get_linear_effective_load())

    def get_array_per_bus(self, arr: Vec) -> Vec:
        """
        Get generator array per bus
        :param arr:
        :return:
        """
        assert len(arr) == self.nelm
        return tp.sum_per_bus(self.nbus, self.bus_idx, arr)

    def get_array_per_bus_obj(self, arr: Vec) -> Vec:
        """
        Sum per bus in python mode (it can add objects)
        :param arr: any array of size nelm
        :return: array of size nbus
        """
        assert len(arr) == self.nelm
        res = np.zeros(self.nbus, dtype=arr.dtype)
        for i in range(self.nelm):
            res[self.bus_idx[i]] += arr[i]
        return res

    def get_current_injections_per_bus(self) -> CxVec:
        """
        Get current Injections per bus with sign
        :return:
        """
        return -tp.sum_per_bus_cx(self.nbus, self.bus_idx, self.I * self.active.astype(int))

    def get_admittance_injections_per_bus(self) -> CxVec:
        """
        Get admittance Injections per bus with sign
        :return:
        """
        return -tp.sum_per_bus_cx(self.nbus, self.bus_idx, self.Y * self.active.astype(int))

    def __len__(self) -> int:
        return self.nelm

    def get_bus_indices(self) -> IntVec:
        """
        Get the bus indices
        :return: array with the bus indices
        """
        return self.bus_idx
