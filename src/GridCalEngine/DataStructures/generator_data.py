# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from typing import Tuple
import numpy as np
from scipy.sparse import csc_matrix, coo_matrix
import GridCalEngine.Topology.topology as tp
from GridCalEngine.basic_structures import CxVec, Vec, IntVec, BoolVec, StrVec


class GeneratorData:
    """
    GeneratorData
    """

    def __init__(self, nelm: int, nbus: int):
        """
        Generator data arrays
        :param nelm: number of generator
        :param nbus: number of buses
        """
        self.nelm: int = nelm
        self.nbus: int = nbus
        self.names: StrVec = np.empty(nelm, dtype=object)
        self.idtag: StrVec = np.empty(nelm, dtype=object)

        self.controllable: BoolVec = np.zeros(nelm, dtype=bool)
        self.installed_p: Vec = np.zeros(nelm, dtype=float)

        self.active: BoolVec = np.zeros(nelm, dtype=bool)
        self.p: Vec = np.zeros(nelm, dtype=float)
        self.pf: Vec = np.zeros(nelm, dtype=float)
        self.v: Vec = np.zeros(nelm, dtype=float)

        self.qmin: Vec = np.zeros(nelm, dtype=float)
        self.qmax: Vec = np.zeros(nelm, dtype=float)
        self.snom: Vec = np.zeros(nelm, dtype=float)
        self.q_share: Vec = np.zeros(nelm, dtype=float)

        # reliability
        self.mttf: Vec = np.zeros(nelm, dtype=float)
        self.mttr: Vec = np.zeros(nelm, dtype=float)

        self.bus_idx: IntVec = np.zeros(nelm, dtype=int)
        self.controllable_bus_idx = np.zeros(nelm, dtype=int)

        # r0, r1, r2, x0, x1, x2
        self.r0: Vec = np.zeros(nelm, dtype=float)
        self.r1: Vec = np.zeros(nelm, dtype=float)
        self.r2: Vec = np.zeros(nelm, dtype=float)

        self.x0: Vec = np.zeros(nelm, dtype=float)
        self.x1: Vec = np.zeros(nelm, dtype=float)
        self.x2: Vec = np.zeros(nelm, dtype=float)

        self.dispatchable: BoolVec = np.zeros(nelm, dtype=bool)
        self.pmax: Vec = np.zeros(nelm, dtype=float)
        self.pmin: Vec = np.zeros(nelm, dtype=float)

        self.cost_1: Vec = np.zeros(nelm, dtype=float)
        self.cost_0: Vec = np.zeros(nelm, dtype=float)
        self.cost_2: Vec = np.zeros(nelm, dtype=float)
        self.startup_cost: Vec = np.zeros(nelm, dtype=float)
        self.ramp_up: Vec = np.zeros(nelm, dtype=float)
        self.ramp_down: Vec = np.zeros(nelm, dtype=float)
        self.min_time_up: Vec = np.zeros(nelm, dtype=float)
        self.min_time_down: Vec = np.zeros(nelm, dtype=float)

        self.original_idx = np.zeros(nelm, dtype=int)

        self.name_to_idx: dict = dict()
        self.is_at_dc_bus: BoolVec = np.zeros(nelm, dtype=bool)  # purpose? why not for VSC?

    def slice(self, elm_idx: IntVec, bus_idx: IntVec, bus_map: IntVec):
        """
        Slice generator data by given indices
        :param elm_idx: array of element indices
        :param bus_idx: array of bus indices
        :param bus_map: map from bus index to element index
        :return: new GeneratorData instance
        """

        data = GeneratorData(nelm=len(elm_idx),
                             nbus=len(bus_idx))

        data.names = self.names[elm_idx]
        data.idtag = self.idtag[elm_idx]

        data.controllable = self.controllable[elm_idx]
        data.installed_p = self.installed_p[elm_idx]

        data.active = self.active[elm_idx]
        data.p = self.p[elm_idx]
        data.pf = self.pf[elm_idx]
        data.v = self.v[elm_idx]

        data.qmin = self.qmin[elm_idx]
        data.qmax = self.qmax[elm_idx]
        data.snom = self.snom[elm_idx]
        data.q_share = self.q_share[elm_idx]

        data.mttf = self.mttf[elm_idx]
        data.mttr = self.mttr[elm_idx]

        data.bus_idx = self.bus_idx[elm_idx]
        data.controllable_bus_idx = self.controllable_bus_idx[elm_idx]

        # Remapping of the buses
        for k in range(data.nelm):
            data.bus_idx[k] = bus_map[data.bus_idx[k]]

            if data.bus_idx[k] == -1:
                data.active[k] = 0

            if data.controllable_bus_idx[k] > -1:
                data.controllable_bus_idx[k] = bus_map[data.controllable_bus_idx[k]]

        data.r0 = self.r0[elm_idx]
        data.r1 = self.r1[elm_idx]
        data.r2 = self.r2[elm_idx]

        data.x0 = self.x0[elm_idx]
        data.x1 = self.x1[elm_idx]
        data.x2 = self.x2[elm_idx]

        data.dispatchable = self.dispatchable[elm_idx]
        data.pmax = self.pmax[elm_idx]
        data.pmin = self.pmin[elm_idx]

        data.cost_0 = self.cost_0[elm_idx]
        data.cost_1 = self.cost_1[elm_idx]
        data.cost_2 = self.cost_2[elm_idx]
        data.startup_cost = self.startup_cost[elm_idx]
        data.ramp_up = self.ramp_up[elm_idx]
        data.ramp_down = self.ramp_down[elm_idx]
        data.min_time_up = self.min_time_up[elm_idx]
        data.min_time_down = self.min_time_down[elm_idx]

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

    def size(self) -> int:
        """
        Get size of the structure
        :return:
        """

        return self.nelm

    def copy(self):
        """
        Get a deep copy of this object
        :return: new GeneratorData instance
        """

        data = GeneratorData(nelm=self.nelm, nbus=self.nbus)

        data.names = self.names.copy()
        data.idtag = self.idtag.copy()

        data.controllable = self.controllable.copy()
        data.installed_p = self.installed_p.copy()

        data.active = self.active.copy()
        data.p = self.p.copy()
        data.pf = self.pf.copy()
        data.v = self.v.copy()

        data.qmin = self.qmin.copy()
        data.qmax = self.qmax.copy()
        data.snom = self.snom.copy()
        data.q_share = self.q_share.copy()

        data.mttf = self.mttf.copy()
        data.mttr = self.mttr.copy()

        data.bus_idx = self.bus_idx.copy()
        data.controllable_bus_idx = self.controllable_bus_idx.copy()

        data.r0 = self.r0.copy()
        data.r1 = self.r1.copy()
        data.r2 = self.r2.copy()

        data.x0 = self.x0.copy()
        data.x1 = self.x1.copy()
        data.x2 = self.x2.copy()

        data.dispatchable = self.dispatchable.copy()
        data.pmax = self.pmax.copy()
        data.pmin = self.pmin.copy()

        data.cost_0 = self.cost_0.copy()
        data.cost_1 = self.cost_1.copy()
        data.cost_2 = self.cost_2.copy()
        data.startup_cost = self.startup_cost.copy()
        data.ramp_up = self.ramp_up.copy()
        data.ramp_down = self.ramp_down.copy()
        data.min_time_up = self.min_time_up.copy()
        data.min_time_down = self.min_time_down.copy()

        data.original_idx = self.original_idx

        return data

    def get_injections(self) -> CxVec:
        """
        Compute the active and reactive power of non-controlled generators (assuming all)
        :return:
        """
        pf2 = np.power(self.pf, 2.0)
        pf_sign = (self.pf + 1e-20) / np.abs(self.pf + 1e-20)
        Q = pf_sign * self.p * np.sqrt((1.0 - pf2) / (pf2 + 1e-20))
        return self.p + 1.0j * Q

    def get_q_at(self, i) -> float:
        """

        :param i:
        :return:
        """
        pf2 = np.power(self.pf[i], 2.0)
        pf_sign = (self.pf[i] + 1e-20) / np.abs(self.pf[i] + 1e-20)
        Q = pf_sign * self.p[i] * np.sqrt((1.0 - pf2) / (pf2 + 1e-20))
        return Q

    def get_Yshunt(self, seq: int = 1) -> CxVec:
        """
        Obtain the vector of shunt admittances of a given sequence per bus
        :param seq: sequence (0, 1 or 2)
        """
        if seq == 0:
            y = (1.0 / (self.r0 + 1j * self.x0))
        elif seq == 1:
            y = (1.0 / (self.r1 + 1j * self.x1))
        elif seq == 2:
            y = (1.0 / (self.r2 + 1j * self.x2))
        else:
            raise Exception('Sequence must be 0, 1, 2')

        return tp.sum_per_bus_cx(nbus=self.nbus, bus_indices=self.bus_idx, magnitude=y)

    def get_effective_generation(self) -> Vec:
        """
        Get generator effective power
        :return:
        """
        return self.p * self.active

    def get_array_per_bus(self, arr: Vec) -> Vec:
        """
        Get generator array per bus
        :param arr:
        :return:
        """
        assert len(arr) == self.nelm
        return tp.sum_per_bus(nbus=self.nbus, bus_indices=self.bus_idx, magnitude=arr)

    def get_injections_per_bus(self) -> CxVec:
        """
        Get generator Injections per bus
        :return:
        """
        return tp.sum_per_bus_cx(nbus=self.nbus, bus_indices=self.bus_idx,
                                 magnitude=self.get_injections() * self.active)

    def get_dispatchable_per_bus(self) -> BoolVec:
        """
        Get generator Injections per bus
        :return:
        """
        return tp.sum_per_bus_bool(nbus=self.nbus, bus_indices=self.bus_idx, magnitude=self.dispatchable)

    def get_installed_power_per_bus(self) -> Vec:
        """
        Get generator installed power per bus
        :return:
        """
        return tp.sum_per_bus(nbus=self.nbus, bus_indices=self.bus_idx, magnitude=self.installed_p)

    def get_qmax_per_bus(self) -> Vec:
        """
        Get generator Qmax per bus
        :return:
        """
        return tp.sum_per_bus(nbus=self.nbus, bus_indices=self.bus_idx, magnitude=self.qmax * self.active)

    def get_qmin_per_bus(self) -> Vec:
        """
        Get generator Qmin per bus
        :return:
        """
        return tp.sum_per_bus(nbus=self.nbus, bus_indices=self.bus_idx, magnitude=self.qmin * self.active)

    def get_pmax_per_bus(self) -> Vec:
        """
        Get generator Pmax per bus
        :return:
        """
        return tp.sum_per_bus(nbus=self.nbus, bus_indices=self.bus_idx, magnitude=self.pmax * self.active)

    def get_pmin_per_bus(self) -> Vec:
        """
        Get generator Pmin per bus
        :return:
        """
        return tp.sum_per_bus(nbus=self.nbus, bus_indices=self.bus_idx, magnitude=self.pmin * self.active)

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

    def dev_per_bus(self) -> IntVec:
        """
        Get number of devices per bus
        :return: array with the number of elements per bus
        """
        return tp.dev_per_bus(nbus=self.nbus, bus_indices=self.bus_idx)

    def __len__(self) -> int:
        """
        Get generator count
        :return:
        """
        return self.nelm

    def get_bus_indices(self) -> IntVec:
        """
        Get the bus indices
        :return: array with the bus indices
        """
        return self.bus_idx

    def get_dispatchable_indices(self) -> IntVec:
        """
        Get the indices of dispatchable generators
        :return:
        """
        return np.where(self.dispatchable == 1)[0]

    def get_dispatchable_active_indices(self) -> IntVec:
        """
        Get the indices of dispatchable generators
        :return:
        """
        x = (self.dispatchable * self.active).astype(int)
        return np.where(x == 1)[0]

    def get_non_dispatchable_indices(self) -> IntVec:
        """
        Get the indices of dispatchable generators
        :return:
        """
        x = (~self.dispatchable * self.active).astype(int)
        return np.where(x == 1)[0]

    def get_controllable_and_not_controllable_indices(self) -> Tuple[IntVec, IntVec]:
        """
        Get the indices of controllable generators
        :return: idx_controllable, idx_non_controllable
        """
        return np.where(self.controllable == 1)[0], np.where(self.controllable == 0)[0]

    def get_gen_indices_at_buses(self, bus_indices: IntVec) -> IntVec:

        res = list()
        for i in self.bus_idx:
            if i in bus_indices:
                res.append(i)
        return np.array(res)

    def get_C_bus_elm(self) -> csc_matrix:
        """
        Get the connectivity matrix
        :return: CSC matrix
        """
        # C_bus_elm = lil_matrix((self.nbus, self.nelm), dtype=int)
        # for k, i in enumerate(self.bus_idx):
        #     C_bus_elm[i, k] = 1
        # return C_bus_elm.tocsc()
        j = np.arange(self.nelm, dtype=int)
        data = np.ones(self.nelm, dtype=int)
        return coo_matrix((data, (self.bus_idx, j)), shape=(self.nbus, self.nelm), dtype=int).tocsc()
