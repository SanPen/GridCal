# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations
import numpy as np
from GridCalEngine.DataStructures.branch_parent_data import BranchParentData
from GridCalEngine.enumerations import WindingsConnection
from GridCalEngine.Utils.Sparse.sparse_array import SparseObjectArray
from GridCalEngine.basic_structures import Vec, IntVec, ObjVec, CxVec, Logger
from typing import List, Tuple, Set


class PassiveBranchData(BranchParentData):
    """
    Structure to host all branches data for calculation
    """

    def __init__(self, nelm: int, nbus: int):
        """
        Branch data arrays
        :param nelm: number of elements
        :param nbus: number of buses
        """
        BranchParentData.__init__(self, nelm=nelm, nbus=nbus)

        self.R: Vec = np.zeros(self.nelm, dtype=float)
        self.X: Vec = np.zeros(self.nelm, dtype=float)
        self.G: Vec = np.zeros(self.nelm, dtype=float)
        self.B: Vec = np.zeros(self.nelm, dtype=float)

        self.R0: Vec = np.zeros(self.nelm, dtype=float)
        self.X0: Vec = np.zeros(self.nelm, dtype=float)
        self.G0: Vec = np.zeros(self.nelm, dtype=float)
        self.B0: Vec = np.zeros(self.nelm, dtype=float)

        self.R2: Vec = np.zeros(self.nelm, dtype=float)
        self.X2: Vec = np.zeros(self.nelm, dtype=float)
        self.G2: Vec = np.zeros(self.nelm, dtype=float)
        self.B2: Vec = np.zeros(self.nelm, dtype=float)

        self.conn: ObjVec = np.full(self.nelm, fill_value=WindingsConnection.GG, dtype=object)

        self.m_taps = SparseObjectArray(n=self.nelm)
        self.tau_taps = SparseObjectArray(n=self.nelm)

        self.k: Vec = np.ones(nelm, dtype=float)

        self.virtual_tap_t: Vec = np.ones(self.nelm, dtype=float)
        self.virtual_tap_f: Vec = np.ones(self.nelm, dtype=float)

    def size(self) -> int:
        """
        Get size of the structure
        :return:
        """

        return self.nelm

    def slice(self, elm_idx: IntVec, bus_idx: IntVec,
              bus_map: IntVec, logger: Logger | None) -> "PassiveBranchData":
        """
        Slice branch data by given indices
        :param elm_idx: array of branch indices
        :param bus_idx: array of bus indices
        :param bus_map: map from bus index to island bus index {int(o): i for i, o in enumerate(bus_idx)}
        :param logger: Logger
        :return: new BranchData instance
        """
        data, bus_map = super().slice(elm_idx, bus_idx, bus_map, logger)
        data.__class__ = PassiveBranchData
        data: PassiveBranchData = data

        data.R = self.R[elm_idx]
        data.X = self.X[elm_idx]
        data.G = self.G[elm_idx]
        data.B = self.B[elm_idx]

        data.R0 = self.R0[elm_idx]
        data.X0 = self.X0[elm_idx]
        data.G0 = self.G0[elm_idx]
        data.B0 = self.B0[elm_idx]

        data.R2 = self.R2[elm_idx]
        data.X2 = self.X2[elm_idx]
        data.G2 = self.G2[elm_idx]
        data.B2 = self.B2[elm_idx]

        data.conn = self.conn[elm_idx]  # winding connection

        data.m_taps = self.m_taps.slice(elm_idx)
        data.tau_taps = self.tau_taps.slice(elm_idx)

        data.k = self.k[elm_idx]

        data.virtual_tap_f = self.virtual_tap_f[elm_idx]
        data.virtual_tap_t = self.virtual_tap_t[elm_idx]

        return data

    def copy(self) -> "PassiveBranchData":
        """
        Get a deep copy of this object
        :return: new BranchData instance
        """
        data: PassiveBranchData = super().copy()
        data.__class__ = PassiveBranchData

        data.R = self.R.copy()
        data.X = self.X.copy()
        data.G = self.G.copy()
        data.B = self.B.copy()

        data.R0 = self.R.copy()
        data.X0 = self.X.copy()
        data.G0 = self.G.copy()
        data.B0 = self.B.copy()

        data.R2 = self.R.copy()
        data.X2 = self.X.copy()
        data.G2 = self.G.copy()
        data.B2 = self.B.copy()

        data.conn = self.conn.copy()  # winding connection
        data.m_taps = self.m_taps.copy()
        data.tau_taps = self.tau_taps.copy()
        data.k = self.k.copy()

        data.virtual_tap_f = self.virtual_tap_f.copy()
        data.virtual_tap_t = self.virtual_tap_t.copy()

        return data

    def get_series_admittance(self) -> CxVec:
        """
        Get the series admittance of the branches
        :return: complex vector
        """
        return 1.0 / (self.R + 1.0j * self.X + 1e-20)

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

    def detect_superconductor_at(self, k) -> None:
        """
        There is a beyond terrible practice of setting branches with R=0 and X=0 as "superconductor"....
        Those must be reduced of course
        :param k: index
        """
        # handle """superconductor branches"""
        if self.R[k] == 0.0 and self.X[k] == 0.0:
            self.reducible[k] = 1