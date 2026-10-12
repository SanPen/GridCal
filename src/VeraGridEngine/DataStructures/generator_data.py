# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from typing import Tuple
import numpy as np
from scipy.sparse import csc_matrix, coo_matrix
import VeraGridEngine.Topology.topology as tp
from VeraGridEngine.basic_structures import CxVec, Vec, IntVec, BoolVec, StrVec, Logger
from VeraGridEngine.enumerations import GeneratorControlMode, ShuntConnectionType
from VeraGridEngine.Utils.compare import compare_arr


class GeneratorData:
    """
    GeneratorData
    """

    __slots__ = (
        "nelm",
        "nbus",
        "names",
        "idtag",
        "control_mode_int",
        "conn",
        "installed_p",
        "active",
        "is_static_generator",
        "p",
        "p3_star",
        "q",
        "v",
        "k_droop",
        "dead_band",
        "qmin",
        "qmax",
        "snom",
        "q_share",
        "mttf",
        "mttr",
        "bus_idx",
        "controllable_bus_idx",
        "r0",
        "r1",
        "r2",
        "x0",
        "x1",
        "x2",
        "Rs",
        "Xs",
        "Xm",
        "Rr",
        "Xr",
        "tpe_int",
        "dispatchable",
        "must_run",
        "pmax",
        "pmin",
        "cost_1",
        "cost_0",
        "cost_2",
        "startup_cost",
        "shut_down_cost",
        "ramp_up",
        "ramp_down",
        "min_time_up",
        "min_time_down",
        "capex",
        "discount_rate",
        "is_candidate",
        "shift_key",
        "scalable",
        "original_idx",
        "name_to_idx",
        "is_at_dc_bus",
    )

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

        self.control_mode_int: IntVec = np.zeros(nelm, dtype=int)  # int representation of GeneratorControlMode
        self.conn: IntVec = np.full(nelm, ShuntConnectionType.GroundedStar.idx(), dtype=int)
        self.installed_p: Vec = np.zeros(nelm, dtype=float)

        self.active: BoolVec = np.zeros(nelm, dtype=bool)
        self.is_static_generator: BoolVec = np.zeros(nelm, dtype=bool)
        self.p: Vec = np.zeros(nelm, dtype=float)

        self.p3_star = np.zeros(self.nelm * 3, dtype=float)

        self.q: Vec = np.zeros(nelm, dtype=float)

        self.v: Vec = np.zeros(nelm, dtype=float)
        self.k_droop: Vec = np.zeros(nelm, dtype=float)
        self.dead_band: Vec = np.zeros(nelm, dtype=float)

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

        # asynchronous generator impedance
        self.Rs: Vec = np.zeros(nelm, dtype=float)
        self.Xs: Vec = np.zeros(nelm, dtype=float)
        self.Xm: Vec = np.zeros(nelm, dtype=float)
        self.Rr: Vec = np.zeros(nelm, dtype=float)
        self.Xr: Vec = np.zeros(nelm, dtype=float)

        self.tpe_int: IntVec = np.zeros(self.nelm, dtype=int)  # GeneratorType values

        self.dispatchable: BoolVec = np.zeros(nelm, dtype=bool)
        self.must_run: BoolVec = np.zeros(nelm, dtype=bool)
        self.pmax: Vec = np.zeros(nelm, dtype=float)
        self.pmin: Vec = np.zeros(nelm, dtype=float)

        self.cost_1: Vec = np.zeros(nelm, dtype=float)
        self.cost_0: Vec = np.zeros(nelm, dtype=float)
        self.cost_2: Vec = np.zeros(nelm, dtype=float)
        self.startup_cost: Vec = np.zeros(nelm, dtype=float)
        self.shut_down_cost: Vec = np.zeros(nelm, dtype=float)
        self.ramp_up: Vec = np.zeros(nelm, dtype=float)
        self.ramp_down: Vec = np.zeros(nelm, dtype=float)
        self.min_time_up: Vec = np.zeros(nelm, dtype=float)
        self.min_time_down: Vec = np.zeros(nelm, dtype=float)

        self.capex: Vec = np.zeros(nelm, dtype=float)
        self.discount_rate: Vec = np.zeros(nelm, dtype=float)
        self.is_candidate: BoolVec = np.zeros(nelm, dtype=bool)

        self.shift_key: Vec = np.ones(nelm, dtype=float)
        self.scalable: BoolVec = np.ones(nelm, dtype=bool)

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

        data: GeneratorData = self.__class__(nelm=len(elm_idx),
                                              nbus=len(bus_idx))

        data.names = self.names[elm_idx]
        data.idtag = self.idtag[elm_idx]

        data.control_mode_int = self.control_mode_int[elm_idx]
        data.conn = self.conn[elm_idx]
        data.installed_p = self.installed_p[elm_idx]

        data.active = self.active[elm_idx]
        data.is_static_generator = self.is_static_generator[elm_idx]
        data.p = self.p[elm_idx]
        elm_idx_3 = ((elm_idx * 3)[:, np.newaxis] + np.arange(3)).flatten()
        data.p3_star = self.p3_star[elm_idx_3]
        data.q = self.q[elm_idx]
        data.v = self.v[elm_idx]
        data.k_droop = self.k_droop[elm_idx]
        data.dead_band = self.dead_band[elm_idx]

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

        data.Rs = self.Rs[elm_idx]
        data.Xs = self.Xs[elm_idx]
        data.Xm = self.Xm[elm_idx]
        data.Rr = self.Rr[elm_idx]
        data.Xr = self.Xr[elm_idx]

        data.tpe_int = self.tpe_int[elm_idx]

        data.dispatchable = self.dispatchable[elm_idx]
        data.must_run = self.must_run[elm_idx]
        data.pmax = self.pmax[elm_idx]
        data.pmin = self.pmin[elm_idx]

        data.cost_0 = self.cost_0[elm_idx]
        data.cost_1 = self.cost_1[elm_idx]
        data.cost_2 = self.cost_2[elm_idx]
        data.startup_cost = self.startup_cost[elm_idx]
        data.shut_down_cost = self.shut_down_cost[elm_idx]
        data.ramp_up = self.ramp_up[elm_idx]
        data.ramp_down = self.ramp_down[elm_idx]
        data.min_time_up = self.min_time_up[elm_idx]
        data.min_time_down = self.min_time_down[elm_idx]

        data.capex = self.capex[elm_idx]
        data.discount_rate = self.discount_rate[elm_idx]
        data.is_candidate = self.is_candidate[elm_idx]

        data.shift_key = self.shift_key[elm_idx]
        data.scalable = self.scalable[elm_idx]

        data.original_idx = elm_idx
        data.name_to_idx = {str(name): i for i, name in enumerate(data.names)}
        data.is_at_dc_bus = self.is_at_dc_bus[elm_idx]

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

            control_bus_idx = self.controllable_bus_idx[k]
            if control_bus_idx >= 0:
                self.controllable_bus_idx[k] = bus_map_arr[control_bus_idx]

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

        data: GeneratorData = self.__class__(nelm=self.nelm, nbus=self.nbus)

        data.names = self.names.copy()
        data.idtag = self.idtag.copy()

        data.control_mode_int = self.control_mode_int.copy()
        data.conn = self.conn.copy()
        data.installed_p = self.installed_p.copy()

        data.active = self.active.copy()
        data.is_static_generator = self.is_static_generator.copy()
        data.p = self.p.copy()
        data.p3_star = self.p3_star.copy()
        data.q = self.q.copy()
        data.v = self.v.copy()
        data.k_droop = self.k_droop.copy()
        data.dead_band = self.dead_band.copy()

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

        data.Rs = self.Rs.copy()
        data.Xs = self.Xs.copy()
        data.Xm = self.Xm.copy()
        data.Rr = self.Rr.copy()
        data.Xr = self.Xr.copy()

        data.tpe_int = self.tpe_int.copy()

        data.dispatchable = self.dispatchable.copy()
        data.must_run = self.must_run.copy()
        data.pmax = self.pmax.copy()
        data.pmin = self.pmin.copy()

        data.cost_0 = self.cost_0.copy()
        data.cost_1 = self.cost_1.copy()
        data.cost_2 = self.cost_2.copy()
        data.startup_cost = self.startup_cost.copy()
        data.shut_down_cost = self.shut_down_cost.copy()
        data.ramp_up = self.ramp_up.copy()
        data.ramp_down = self.ramp_down.copy()
        data.min_time_up = self.min_time_up.copy()
        data.min_time_down = self.min_time_down.copy()

        data.capex = self.capex.copy()
        data.discount_rate = self.discount_rate.copy()
        data.is_candidate = self.is_candidate.copy()

        data.shift_key = self.shift_key.copy()
        data.scalable = self.scalable.copy()

        data.original_idx = self.original_idx.copy()
        data.name_to_idx = self.name_to_idx.copy()
        data.is_at_dc_bus = self.is_at_dc_bus.copy()

        return data

    def compare(self, other: "GeneratorData", tol: float, logger: Logger) -> None:
        """
        Compare generator fields used by NumericalCircuit.compare().
        """
        compare_arr(self.active, other.active, tol, 'GenData', 'active', logger)
        compare_arr(self.p, other.p, tol, 'GenData', 'P', logger)
        compare_arr(self.v, other.v, tol, 'GenData', 'Vset', logger)
        compare_arr(self.qmin, other.qmin, tol, 'GenData', 'Qmin', logger)
        compare_arr(self.qmax, other.qmax, tol, 'GenData', 'Qmax', logger)

    def get_injections(self) -> CxVec:
        """
        Compute the active and reactive power of non-controlled generators (assuming all)
        :return:
        """
        c = np.empty(self.nelm, dtype=complex)
        c.real = self.p
        c.imag = self.q
        return c

    def get_q_at(self, i) -> float:
        """

        :param i:
        :return:
        """
        return float(self.q[i])

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
        v_idx = GeneratorControlMode.V.idx()
        return (np.where(self.control_mode_int == v_idx)[0],
                np.where(self.control_mode_int != v_idx)[0])

    def get_gen_indices_at_buses(self, bus_indices: IntVec) -> IntVec:

        res = list()
        for i in self.bus_idx:
            if i in bus_indices:
                res.append(i)
            else:
                pass
        return np.array(res)

    def get_dispatchable_active_indices_per_area(self,
                                                 bus_area_indices: IntVec,
                                                 area_count: int) -> list[IntVec]:
        """
        Get the active dispatchable generator indices grouped by area.

        :param bus_area_indices: Area index of each bus. A value of ``-1`` means
                                 that the bus does not belong to any area.
        :param area_count: Number of declared areas.
        :return: List where position ``a`` stores the generator-index array for area ``a``.
        """
        area_generators: list[list[int]] = list()
        for _ in range(area_count):
            area_generators.append(list())

        for gen_idx in range(self.nelm):
            if self.active[gen_idx] and self.dispatchable[gen_idx]:
                bus_idx = self.bus_idx[gen_idx]
                area_idx = bus_area_indices[bus_idx]

                if 0 <= area_idx < area_count:
                    area_generators[area_idx].append(gen_idx)
                else:
                    pass
            else:
                pass

        grouped_indices: list[IntVec] = list()
        for generator_indices in area_generators:
            grouped_indices.append(np.array(generator_indices, dtype=int))

        return grouped_indices

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

    def get_pf(self) -> Vec:
        """
        Get the array of power factors
        :return:
        """
        s = np.sqrt(self.p * self.p + self.q * self.q)
        idx = np.where(s != 0)
        pf = np.ones(self.nelm)
        pf[idx] = self.p[idx] / s[idx]
        return pf
