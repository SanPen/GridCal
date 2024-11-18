# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import numpy as np
import pandas as pd
import GridCalEngine.Topology.topology as tp
from GridCalEngine.DataStructures.branch_parent_data import BranchParentData
from GridCalEngine.enumerations import WindingsConnection
from GridCalEngine.Utils.Sparse.sparse_array import SparseObjectArray
from GridCalEngine.basic_structures import Vec, IntVec, ObjVec, CxVec, Logger
from typing import List, Tuple, Set


class BranchData(BranchParentData):
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

        self.branch_idx: IntVec = np.zeros(nelm, dtype=int)

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

        self.tap_module: Vec = np.ones(nelm, dtype=float)
        self.tap_module_min: Vec = np.full(nelm, fill_value=0.1, dtype=float)
        self.tap_module_max: Vec = np.full(nelm, fill_value=1.5, dtype=float)
        self.tap_angle: Vec = np.zeros(nelm, dtype=float)
        self.tap_angle_min: Vec = np.full(nelm, fill_value=-6.28, dtype=float)
        self.tap_angle_max: Vec = np.full(nelm, fill_value=6.28, dtype=float)
        self.tap_module_control_mode: ObjVec = np.zeros(self.nelm, dtype=object)
        self.tap_phase_control_mode: ObjVec = np.zeros(self.nelm, dtype=object)
        self.tap_controlled_buses: IntVec = np.zeros(self.nelm, dtype=int)

        self.virtual_tap_t: Vec = np.ones(self.nelm, dtype=float)
        self.virtual_tap_f: Vec = np.ones(self.nelm, dtype=float)

        self.Pset: Vec = np.zeros(nelm, dtype=float)  # always over the controlled side
        self.Qset: Vec = np.zeros(nelm, dtype=float)  # always over the controlled side
        self.vset: Vec = np.ones(nelm, dtype=float)  # always over the controlled side

    def size(self) -> int:
        """
        Get size of the structure
        :return:
        """

        return self.nelm

    def slice(self, elm_idx: IntVec, bus_idx: IntVec, logger: Logger | None) -> "BranchData":
        """
        Slice branch data by given indices
        :param elm_idx: array of branch indices
        :param bus_idx: array of bus indices
        :param logger: Logger
        :return: new BranchData instance
        """
        data, bus_map = super().slice(elm_idx, bus_idx, logger)
        data.__class__ = BranchData
        data: BranchData = data

        data.branch_idx = self.branch_idx[elm_idx]

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

        data.tap_module = self.tap_module[elm_idx]
        data.tap_module_min = self.tap_module_min[elm_idx]
        data.tap_module_max = self.tap_module_max[elm_idx]
        data.tap_angle = self.tap_angle[elm_idx]
        data.tap_angle_min = self.tap_angle_min[elm_idx]
        data.tap_angle_max = self.tap_angle_max[elm_idx]
        data.tap_phase_control_mode = self.tap_phase_control_mode[elm_idx]
        data.tap_module_control_mode = self.tap_module_control_mode[elm_idx]
        data.tap_controlled_buses = self.tap_controlled_buses[elm_idx]

        data.virtual_tap_f = self.virtual_tap_f[elm_idx]
        data.virtual_tap_t = self.virtual_tap_t[elm_idx]

        data.Pset = self.Pset[elm_idx]
        data.Qset = self.Qset[elm_idx]
        data.vset = self.vset[elm_idx]

        return data

    def copy(self) -> "BranchData":
        """
        Get a deep copy of this object
        :return: new BranchData instance
        """
        data: BranchData = super().copy()
        data.__class__ = BranchData

        data.branch_idx = self.branch_idx.copy()

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

        data.tap_module = self.tap_module.copy()
        data.tap_module_min = self.tap_module_min.copy()
        data.tap_module_max = self.tap_module_max.copy()
        data.tap_angle = self.tap_angle.copy()
        data.tap_angle_min = self.tap_angle_min.copy()
        data.tap_angle_max = self.tap_angle_max.copy()
        data.tap_module_control_mode = self.tap_module_control_mode.copy()
        data.tap_phase_control_mode = self.tap_phase_control_mode.copy()
        data.tap_controlled_buses = self.tap_controlled_buses.copy()

        data.virtual_tap_f = self.virtual_tap_f.copy()
        data.virtual_tap_t = self.virtual_tap_t.copy()

        data.Pset = self.Pset.copy()
        data.Qset = self.Qset.copy()
        data.vset = self.vset.copy()

        return data

    def get_series_admittance(self) -> CxVec:
        """
        Get the series admittance of the branches
        :return: complex vector
        """
        return 1.0 / (self.R + 1.0j * self.X + 1e-20)

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

    def get_linear_series_admittance(self) -> Vec:
        """
        Get the linear version of the series admittance for ACDC systems
        :return: Array of the length of the number of Branches with 1/X or 1/R depending whether if it is AC or DC
        """
        dc = self.get_dc_indices()
        ac = self.get_ac_indices()
        m_abs = np.abs(self.tap_module)
        if len(dc):
            # compose the vector for AC-DC grids where the R is needed for this matrix
            # even if conceptually we only want the susceptance
            b = np.zeros(self.nelm)
            active = self.active
            b[ac] = 1.0 / (m_abs[ac] * self.X[ac] * active[ac] + 1e-20)  # for ac Branches
            b[dc] = 1.0 / (m_abs[dc] * self.R[dc] * active[dc] + 1e-20)  # for dc Branches
        else:
            b = 1.0 / (m_abs * self.X * self.active + 1e-20)  # for ac Branches

        return b

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
            'R': self.R,
            'X': self.X,
            'G': self.G,
            'B': self.B,
            'Vtap F': self.virtual_tap_f,
            'Vtap T': self.virtual_tap_t,
            'Tap module': self.tap_module,
            'Tap angle': self.tap_angle
        }
        return pd.DataFrame(data=data)

    @property
    def tap(self) -> CxVec:
        """

        :return:
        """
        return self.tap_module * np.exp(1.0j * self.tap_angle)

