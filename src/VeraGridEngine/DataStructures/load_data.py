# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

import numpy as np
import VeraGridEngine.Topology.topology as tp
from VeraGridEngine.basic_structures import Vec, CxVec, IntVec, StrVec, BoolVec, Logger
from VeraGridEngine.Utils.compare import compare_arr


class LoadData:
    """
    Structure to host the load calculation information
    """

    __slots__ = (
        "nelm",
        "nbus",
        "names",
        "idtag",
        "active",
        "is_static_generator",
        "q_droop", "q_droop_snom", "q_droop_vset", "q_droop_vmin", "q_droop_vmax",
        "S",
        "is_positive_sequence",
        "I",
        "Y",
        "S3_delta",
        "S3_star",
        "S3_floatingstar",
        "A_floatingstar",
        "B_floatingstar",
        "C_floatingstar",
        "I3_delta",
        "I3_star",
        "I3_floatingstar",
        "Y3_delta",
        "Y3_star",
        "mttf",
        "mttr",
        "bus_idx",
        "cost",
        "shift_key",
        "scalable",
        "original_idx",
    )

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
        self.is_static_generator: BoolVec = np.zeros(nelm, dtype=bool)
        # Zero droop marks ordinary fixed-power devices; only controlled static injections populate these arrays.
        self.q_droop: Vec = np.zeros(nelm)
        self.q_droop_snom: Vec = np.zeros(nelm)
        self.q_droop_vset: Vec = np.ones(nelm)
        self.q_droop_vmin: Vec = np.full(nelm, 0.9)
        self.q_droop_vmax: Vec = np.full(nelm, 1.1)
        self.S: Vec = np.zeros(nelm, dtype=complex)
        # Use S as a positive-sequence power source in ABC, retaining the load sign.
        self.is_positive_sequence: BoolVec = np.zeros(nelm, dtype=bool)
        self.I: Vec = np.zeros(nelm, dtype=complex)
        self.Y: Vec = np.zeros(nelm, dtype=complex)

        self.S3_delta = np.zeros(self.nelm * 4, dtype=complex)
        self.S3_star = np.zeros(self.nelm * 4, dtype=complex)
        self.S3_floatingstar = np.zeros(self.nelm * 4, dtype=complex)

        self.A_floatingstar = np.zeros(self.nelm, dtype=complex)
        self.B_floatingstar = np.zeros(self.nelm, dtype=complex)
        self.C_floatingstar = np.zeros(self.nelm, dtype=complex)

        self.I3_delta = np.zeros(self.nelm * 4, dtype=complex)
        self.I3_star = np.zeros(self.nelm * 4, dtype=complex)
        self.I3_floatingstar = np.zeros(self.nelm * 4, dtype=complex)

        self.Y3_delta = np.zeros(self.nelm * 4, dtype=complex)
        self.Y3_star = np.zeros((self.nelm * 4, 4), dtype=complex)

        # reliability
        self.mttf: Vec = np.zeros(nelm, dtype=float)
        self.mttr: Vec = np.zeros(nelm, dtype=float)

        self.bus_idx = np.zeros(nelm, dtype=int)

        self.cost: Vec = np.zeros(nelm, dtype=float)  # load shedding cost

        self.shift_key: Vec = np.ones(nelm, dtype=float)
        self.scalable: BoolVec = np.ones(nelm, dtype=bool)

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
        data.is_static_generator = self.is_static_generator[elm_idx]
        data.q_droop = self.q_droop[elm_idx]
        data.q_droop_snom = self.q_droop_snom[elm_idx]
        data.q_droop_vset = self.q_droop_vset[elm_idx]
        data.q_droop_vmin = self.q_droop_vmin[elm_idx]
        data.q_droop_vmax = self.q_droop_vmax[elm_idx]
        data.S = self.S[elm_idx]
        data.is_positive_sequence = self.is_positive_sequence[elm_idx]
        data.I = self.I[elm_idx]
        data.Y = self.Y[elm_idx]

        elm_idx_4 = ((elm_idx * 4)[:, np.newaxis] + np.arange(4)).flatten()

        data.S3_delta = self.S3_delta[elm_idx_4]
        data.S3_star = self.S3_star[elm_idx_4]
        data.S3_floatingstar = self.S3_floatingstar[elm_idx_4]

        data.A_floatingstar = self.A_floatingstar[elm_idx]
        data.B_floatingstar = self.B_floatingstar[elm_idx]
        data.C_floatingstar = self.C_floatingstar[elm_idx]

        data.I3_delta = self.I3_delta[elm_idx_4]
        data.I3_star = self.I3_star[elm_idx_4]
        data.I3_floatingstar = self.I3_floatingstar[elm_idx_4]

        data.Y3_delta = self.Y3_delta[elm_idx_4]
        data.Y3_star = self.Y3_star[elm_idx_4]

        data.mttf = self.mttf[elm_idx]
        data.mttr = self.mttr[elm_idx]

        data.bus_idx = self.bus_idx[elm_idx]

        # Remapping of the buses
        for k in range(data.nelm):
            data.bus_idx[k] = bus_map[data.bus_idx[k]]

            if data.bus_idx[k] == -1:
                data.active[k] = 0

        data.cost = self.cost[elm_idx]

        data.shift_key = self.shift_key[elm_idx]
        data.scalable = self.scalable[elm_idx]

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
        # TODO: review that we are copying everything
        data = LoadData(nelm=self.nelm, nbus=self.nbus)

        data.names = self.names.copy()
        data.idtag = self.idtag.copy()

        data.active = self.active.copy()
        data.is_static_generator = self.is_static_generator.copy()
        data.q_droop = self.q_droop.copy()
        data.q_droop_snom = self.q_droop_snom.copy()
        data.q_droop_vset = self.q_droop_vset.copy()
        data.q_droop_vmin = self.q_droop_vmin.copy()
        data.q_droop_vmax = self.q_droop_vmax.copy()
        data.S = self.S.copy()
        data.is_positive_sequence = self.is_positive_sequence.copy()
        data.I = self.I.copy()
        data.Y = self.Y.copy()

        data.S3_delta = self.S3_delta.copy()
        data.S3_star = self.S3_star.copy()
        data.S3_floatingstar = self.S3_floatingstar.copy()

        data.A_floatingstar = self.A_floatingstar.copy()
        data.B_floatingstar = self.B_floatingstar.copy()
        data.C_floatingstar = self.C_floatingstar.copy()

        data.I3_delta = self.I3_delta.copy()
        data.I3_star = self.I3_star.copy()
        data.I3_floatingstar = self.I3_floatingstar.copy()

        data.Y3_delta = self.Y3_delta.copy()
        data.Y3_star = self.Y3_star.copy()

        data.mttf = self.mttf.copy()
        data.mttr = self.mttr.copy()

        data.bus_idx = self.bus_idx.copy()

        data.cost = self.cost.copy()

        data.original_idx = self.original_idx.copy()
        data.shift_key = self.shift_key.copy()
        data.scalable = self.scalable.copy()

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

    def get_static_generator_injections_per_bus(self) -> CxVec:
        """
        Get the static generator injections per bus with sign.
        Static generators are stored in the load data structure with negative load values.
        :return:
        """
        return -tp.sum_per_bus_cx(
            self.nbus,
            self.bus_idx,
            self.get_effective_load() * self.is_static_generator.astype(int)
        )

    def get_non_static_generator_injections_per_bus(self) -> CxVec:
        """
        Get the non-static-generator injections per bus with sign.
        :return:
        """
        return -tp.sum_per_bus_cx(
            self.nbus,
            self.bus_idx,
            self.get_effective_load() * (~self.is_static_generator).astype(int)
        )

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

    def compare(self, other: "LoadData", tol: float, logger: Logger) -> None:
        """
        Compare load fields used by NumericalCircuit.compare().
        """
        compare_arr(self.active, other.active, tol, 'LoadData', 'active', logger)
        compare_arr(self.S, other.S, tol, 'LoadData', 'S', logger)
        compare_arr(self.I, other.I, tol, 'LoadData', 'I', logger)
        compare_arr(self.Y, other.Y, tol, 'LoadData', 'Y', logger)
        compare_arr(self.q_droop, other.q_droop, tol, 'LoadData', 'q_droop', logger)
        compare_arr(self.q_droop_snom, other.q_droop_snom, tol, 'LoadData', 'q_droop_snom', logger)
        compare_arr(self.q_droop_vset, other.q_droop_vset, tol, 'LoadData', 'q_droop_vset', logger)
        compare_arr(self.q_droop_vmin, other.q_droop_vmin, tol, 'LoadData', 'q_droop_vmin', logger)
        compare_arr(self.q_droop_vmax, other.q_droop_vmax, tol, 'LoadData', 'q_droop_vmax', logger)
