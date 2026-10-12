# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations
import numpy as np
from scipy.sparse import csc_matrix

from VeraGridEngine.DataStructures.branch_parent_data import BranchParentData
from VeraGridEngine.Utils.Sparse.sparse_array import SparseObjectArray
from VeraGridEngine.Utils.compare import compare_arr
from VeraGridEngine.basic_structures import Vec, IntVec, CxVec, BoolVec, Logger


class PassiveBranchData(BranchParentData):
    """
    Structure to host all branches data for calculation
    """

    __slots__ = (
        "R",
        "X",
        "G",
        "B",
        "R0",
        "X0",
        "G0",
        "B0",
        "R2",
        "X2",
        "G2",
        "B2",
        "tau_taps",
        "m_taps",
        "virtual_tap_f",
        "virtual_tap_t",
        "phA",
        "phB",
        "phC",
        "phN",
        "conn_f",
        "conn_t",
        "conn",
        "Yff3",
        "Yft3",
        "Ytf3",
        "Ytt3",
        "Ycoupling3",
    )

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

        self.conn: IntVec = np.zeros(self.nelm,  dtype=int)
        self.conn_f: IntVec = np.zeros(self.nelm,  dtype=int)
        self.conn_t: IntVec = np.zeros(self.nelm,  dtype=int)

        self.m_taps = SparseObjectArray(n=self.nelm)
        self.tau_taps = SparseObjectArray(n=self.nelm)

        self.virtual_tap_t: Vec = np.ones(self.nelm, dtype=float)
        self.virtual_tap_f: Vec = np.ones(self.nelm, dtype=float)

        self.Yff3 = np.zeros((self.nelm * 4, 4), dtype=complex)
        self.Yft3 = np.zeros((self.nelm * 4, 4), dtype=complex)
        self.Ytf3 = np.zeros((self.nelm * 4, 4), dtype=complex)
        self.Ytt3 = np.zeros((self.nelm * 4, 4), dtype=complex)
        # Mutual terminal admittances: all from NABC rows, then all to NABC rows.
        self.Ycoupling3: csc_matrix = csc_matrix((8 * nelm, 8 * nelm), dtype=complex)

        self.phN: BoolVec = np.zeros(self.nelm, dtype=bool)
        self.phA: BoolVec = np.zeros(self.nelm, dtype=bool)
        self.phB: BoolVec = np.zeros(self.nelm, dtype=bool)
        self.phC: BoolVec = np.zeros(self.nelm, dtype=bool)

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
        data.conn_f = self.conn_f[elm_idx]
        data.conn_t = self.conn_t[elm_idx]

        data.m_taps = self.m_taps.slice(elm_idx)
        data.tau_taps = self.tau_taps.slice(elm_idx)

        data.virtual_tap_f = self.virtual_tap_f[elm_idx]
        data.virtual_tap_t = self.virtual_tap_t[elm_idx]

        elm_idx_4 = ((elm_idx * 4)[:, np.newaxis] + np.arange(4)).flatten()

        data.Yff3 = self.Yff3[elm_idx_4, :]
        data.Yft3 = self.Yft3[elm_idx_4, :]
        data.Ytt3 = self.Ytt3[elm_idx_4, :]
        data.Ytf3 = self.Ytf3[elm_idx_4, :]
        terminal_idx: IntVec = np.r_[elm_idx_4, 4 * self.nelm + elm_idx_4]
        data.Ycoupling3 = self.Ycoupling3[terminal_idx, :][:, terminal_idx].tocsc()

        data.phN = self.phN[elm_idx]
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

        data.R = self.R.copy()
        data.X = self.X.copy()
        data.G = self.G.copy()
        data.B = self.B.copy()

        data.R0 = self.R0.copy()
        data.X0 = self.X0.copy()
        data.G0 = self.G0.copy()
        data.B0 = self.B0.copy()

        data.R2 = self.R2.copy()
        data.X2 = self.X2.copy()
        data.G2 = self.G2.copy()
        data.B2 = self.B2.copy()

        data.conn = self.conn.copy()  # winding connection
        data.conn_f = self.conn_f.copy()
        data.conn_t = self.conn_t.copy()

        data.m_taps = self.m_taps.copy()
        data.tau_taps = self.tau_taps.copy()

        data.virtual_tap_f = self.virtual_tap_f.copy()
        data.virtual_tap_t = self.virtual_tap_t.copy()

        data.Yff3 = self.Yff3.copy()
        data.Yft3 = self.Yft3.copy()
        data.Ytf3 = self.Ytf3.copy()
        data.Ytt3 = self.Ytt3.copy()
        data.Ycoupling3 = self.Ycoupling3.copy()

        data.phN = self.phN.copy()
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

    def compare(self, other: "PassiveBranchData", tol: float, logger: Logger) -> None:
        """
        Compare passive-branch fields used by NumericalCircuit.compare().
        """
        super().compare(other=other, tol=tol, logger=logger)
        compare_arr(self.R, other.R, tol, 'BranchData', 'r', logger)
        compare_arr(self.X, other.X, tol, 'BranchData', 'x', logger)
        compare_arr(self.G, other.G, tol, 'BranchData', 'g', logger)
        compare_arr(self.B, other.B, tol, 'BranchData', 'b', logger)
        compare_arr(self.G0, other.G0, tol, 'BranchData', 'g0', logger)
        compare_arr(self.virtual_tap_f, other.virtual_tap_f, tol, 'BranchData', 'vtap_f', logger)
        compare_arr(self.virtual_tap_t, other.virtual_tap_t, tol, 'BranchData', 'vtap_t', logger)
