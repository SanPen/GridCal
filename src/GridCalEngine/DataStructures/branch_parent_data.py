# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import numpy as np
import pandas as pd
import scipy.sparse as sp
import GridCalEngine.Topology.topology as tp
from GridCalEngine.basic_structures import Vec, IntVec, StrVec, Logger
from typing import List, Tuple, Dict, Set


class BranchParentData:
    """
    Structure to host all branches data for calculation
    """

    def __init__(self, nelm: int, nbus: int):
        """
        Branch data arrays
        :param nelm: number of elements
        :param nbus: number of buses
        """
        self.nelm: int = nelm
        self.nbus: int = nbus

        self.names: StrVec = np.empty(self.nelm, dtype=object)
        self.idtag: StrVec = np.empty(self.nelm, dtype=object)

        self.dc: IntVec = np.zeros(self.nelm, dtype=int)

        self.active: IntVec = np.zeros(nelm, dtype=int)
        self.rates: Vec = np.zeros(nelm, dtype=float)
        self.contingency_rates: Vec = np.zeros(nelm, dtype=float)
        self.protection_rates: Vec = np.zeros(nelm, dtype=float)

        self.F: IntVec = np.zeros(self.nelm, dtype=int)  # indices of the "from" buses
        self.T: IntVec = np.zeros(self.nelm, dtype=int)  # indices of the "to" buses

        # reliability
        self.mttf: Vec = np.zeros(self.nelm, dtype=float)
        self.mttr: Vec = np.zeros(self.nelm, dtype=float)

        self.contingency_enabled: IntVec = np.ones(self.nelm, dtype=int)
        self.monitor_loading: IntVec = np.ones(self.nelm, dtype=int)

        # connectivity branch with their "from" bus
        self.C_branch_bus_f: sp.lil_matrix = sp.lil_matrix((self.nelm, nbus), dtype=int)

        # connectivity branch with their "to" bus
        self.C_branch_bus_t: sp.lil_matrix = sp.lil_matrix((self.nelm, nbus), dtype=int)

        self.overload_cost: Vec = np.zeros(nelm, dtype=float)

        self.original_idx: IntVec = np.zeros(nelm, dtype=int)

    def size(self) -> int:
        """
        Get size of the structure
        :return:
        """

        return self.nelm

    def slice(self, elm_idx: IntVec, bus_idx: IntVec,
              logger: Logger | None) -> Tuple["BranchParentData", Dict[int, int]]:
        """
        Slice branch data by given indices
        :param elm_idx: array of branch indices
        :param bus_idx: array of bus indices
        :param logger: Logger
        :return: new BranchData instance
        """

        data = BranchParentData(nelm=len(elm_idx), nbus=len(bus_idx))

        if data.nelm == 0:
            return data, dict()

        data.names = self.names[elm_idx]
        data.idtag = self.idtag[elm_idx]

        data.mttf = self.mttf[elm_idx]
        data.mttr = self.mttr[elm_idx]

        data.dc = self.dc[elm_idx]
        data.contingency_enabled = self.contingency_enabled[elm_idx]
        data.monitor_loading = self.monitor_loading[elm_idx]

        data.active = self.active[elm_idx]
        data.rates = self.rates[elm_idx]
        data.contingency_rates = self.contingency_rates[elm_idx]
        data.protection_rates = self.protection_rates[elm_idx]

        data.C_branch_bus_f = self.C_branch_bus_f[np.ix_(elm_idx, bus_idx)]
        data.C_branch_bus_t = self.C_branch_bus_t[np.ix_(elm_idx, bus_idx)]

        # first slice, then remap
        data.F = self.F[elm_idx]
        data.T = self.T[elm_idx]
        bus_map: Dict[int, int] = {o: i for i, o in enumerate(bus_idx)}
        for k in range(data.nelm):
            data.F[k] = bus_map.get(data.F[k], -1)

            if data.F[k] == -1:
                if logger is not None:
                    logger.add_error(f"Branch {k}, {self.names[k]} is connected to a disconnected node",
                                     value=data.F[k])
                data.active[k] = 0

            data.T[k] = bus_map.get(data.T[k], -1)

            if data.T[k] == -1:
                if logger is not None:
                    logger.add_error(f"Branch {k}, {self.names[k]} is connected to a disconnected node",
                                     value=data.T[k])
                data.active[k] = 0

        data.overload_cost = self.overload_cost[elm_idx]

        data.original_idx = elm_idx

        return data, bus_map

    def copy(self) -> "BranchParentData":
        """
        Get a deep copy of this object
        :return: new BranchData instance
        """

        data = BranchParentData(nelm=self.nelm, nbus=self.nbus)

        data.names = self.names.copy()
        data.idtag = self.idtag.copy()

        data.mttf = self.mttf.copy()
        data.mttr = self.mttr.copy()

        data.contingency_enabled = self.contingency_enabled.copy()
        data.monitor_loading = self.monitor_loading.copy()

        data.active = self.active.copy()
        data.rates = self.rates.copy()
        data.contingency_rates = self.contingency_rates.copy()
        data.protection_rates = self.protection_rates.copy()

        data.C_branch_bus_f = self.C_branch_bus_f.copy()
        data.C_branch_bus_t = self.C_branch_bus_t.copy()

        data.F = self.F.copy()
        data.T = self.T.copy()

        data.overload_cost = self.overload_cost.copy()

        data.original_idx = self.original_idx.copy()

        return data

    def get_island(self, bus_idx: Vec) -> IntVec:
        """
        Get the array of branch indices that belong to the islands given by the bus indices
        :param bus_idx: array of bus indices
        :return: array of island branch indices
        """
        if self.nelm:
            return tp.get_elements_of_the_island(C_element_bus=self.C_branch_bus_f + self.C_branch_bus_t,
                                                 island=bus_idx,
                                                 active=self.active)
        else:
            return np.zeros(0, dtype=int)

    def get_ac_indices(self) -> IntVec:
        """
        Get ac branch indices
        :return:
        """
        return np.where(self.dc == 0)[0]

    def get_dc_indices(self) -> IntVec:
        """
        Get dc branch indices
        :return:
        """
        return np.where(self.dc != 0)[0]

    def get_monitor_enabled_indices(self) -> IntVec:
        """
        Get monitored branch indices
        :return:
        """
        return np.where(self.monitor_loading == 1)[0]

    def get_contingency_enabled_indices(self) -> IntVec:
        """
        Get contingency branch indices
        :return:
        """
        return np.where(self.contingency_enabled == 1)[0]

    def get_inter_areas(self, bus_idx_from: IntVec | Set[int], bus_idx_to: IntVec | Set[int]):
        """
        Get the Branches that join two areas
        :param bus_idx_from: Area from
        :param bus_idx_to: Area to
        :return: List of (branch index, flow sense w.r.t the area exchange)
        """

        lst: List[Tuple[int, float]] = list()
        for k in range(self.nelm):
            if self.F[k] in bus_idx_from and self.T[k] in bus_idx_to:
                lst.append((k, 1.0))
            elif self.F[k] in bus_idx_to and self.T[k] in bus_idx_from:
                lst.append((k, -1.0))
        return lst

    def to_df(self) -> pd.DataFrame:
        """
        Create DataFrame with the compiled Branches information
        :return: Pandas DataFrame
        """
        data = {
            'names': self.names,
            'active': self.active,
            'F': self.F,
            'T': self.T,
            'Rates': self.rates,
            'Contingency rates': self.contingency_rates,
        }
        return pd.DataFrame(data=data)

    def __len__(self) -> int:
        return self.nelm
