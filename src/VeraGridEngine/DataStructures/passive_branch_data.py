# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations
import numpy as np
from VeraGridEngine.DataStructures.branch_parent_data import BranchParentData
from VeraGridEngine.enumerations import WindingsConnection
from VeraGridEngine.Utils.Sparse.sparse_array import SparseObjectArray
from VeraGridEngine.basic_structures import Vec, IntVec, ObjVec, CxVec, Logger
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

        self.virtual_tap_t: Vec = np.ones(self.nelm, dtype=float)
        self.virtual_tap_f: Vec = np.ones(self.nelm, dtype=float)

        self.Yff3 = np.zeros((self.nelm * 3, 3), dtype=complex)
        self.Yft3 = np.zeros((self.nelm * 3, 3), dtype=complex)
        self.Ytf3 = np.zeros((self.nelm * 3, 3), dtype=complex)
        self.Ytt3 = np.zeros((self.nelm * 3, 3), dtype=complex)

        self.phA: IntVec = np.zeros(self.nelm, dtype=int)
        self.phB: IntVec = np.zeros(self.nelm, dtype=int)
        self.phC: IntVec = np.zeros(self.nelm, dtype=int)

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

        data.virtual_tap_f = self.virtual_tap_f[elm_idx]
        data.virtual_tap_t = self.virtual_tap_t[elm_idx]

        elm_idx_3 = ((elm_idx * 3)[:, np.newaxis] + np.arange(3)).flatten()
        
        data.Yff3 = self.Yff3[elm_idx_3, :]
        data.Yft3 = self.Yft3[elm_idx_3, :]
        data.Ytt3 = self.Ytt3[elm_idx_3, :]
        data.Ytf3 = self.Ytf3[elm_idx_3, :]

        data.phA = self.phA[elm_idx]
        data.phB = self.phB[elm_idx]
        data.phC = self.phC[elm_idx]

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

        data.virtual_tap_f = self.virtual_tap_f.copy()
        data.virtual_tap_t = self.virtual_tap_t.copy()

        data.phA = self.phA.copy()
        data.phB = self.phB.copy()
        data.phC = self.phC.copy()

        return data

    def get_series_admittance(self) -> CxVec:
        """
        Get the series admittance of the branches
        :return: complex vector
        """
        return 1.0 / (self.R + 1.0j * self.X + 1e-20)

    def detect_superconductor_at(self, k) -> None:
        """
        There is a beyond terrible practice of setting branches with R=0 and X=0 as "superconductor"....
        Those must be reduced of course
        :param k: index
        """
        # handle """superconductor branches"""
        if self.R[k] == 0.0 and self.X[k] == 0.0:
            self.reducible[k] = 1