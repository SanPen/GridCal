# GridCal
# Copyright (C) 2022 Santiago Peñate Vera
# 
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
import numpy as np
import pandas as pd
import scipy.sparse as sp
import GridCal.Engine.Core.topology as tp
from GridCal.Engine.Devices.enumerations import WindingsConnection


def get_bus_indices(C_branch_bus):
    F = np.zeros(C_branch_bus.shape[0], dtype=int)

    for j in range(C_branch_bus.shape[1]):
        for l in range(C_branch_bus.indptr[j], C_branch_bus.indptr[j + 1]):
            i = C_branch_bus.indices[l]  # row index
            F[i] = j

    return F


class BranchData:

    def __init__(
            self,
            nelm:int,
            nbus:int
    ):
        """
        Branch data arrays
        :param nelm: number of elements
        :param nbus: number of buses
        """
        self.nelm: int = nelm

        self.names: np.ndarray = np.empty(self.nelm, dtype=object)

        self.dc: np.ndarray = np.zeros(self.nelm, dtype=int)

        self.active: np.ndarray = np.zeros(nelm, dtype=int)
        self.rates: np.ndarray = np.zeros(nelm, dtype=float)
        self.contingency_rates: np.ndarray = np.zeros(nelm, dtype=float)

        self.F: np.ndarray = np.zeros(self.nelm, dtype=int)  # indices of the "from" buses
        self.T: np.ndarray = np.zeros(self.nelm, dtype=int)  # indices of the "to" buses

        # composite losses curve (a * x^2 + b * x + c)
        self.a: np.ndarray = np.zeros(self.nelm, dtype=float)
        self.b: np.ndarray = np.zeros(self.nelm, dtype=float)
        self.c: np.ndarray = np.zeros(self.nelm, dtype=float)

        self.R: np.ndarray = np.zeros(self.nelm, dtype=float)
        self.X: np.ndarray = np.zeros(self.nelm, dtype=float)
        self.G: np.ndarray = np.zeros(self.nelm, dtype=float)
        self.B: np.ndarray = np.zeros(self.nelm, dtype=float)

        self.R0: np.ndarray = np.zeros(self.nelm, dtype=float)
        self.X0: np.ndarray = np.zeros(self.nelm, dtype=float)
        self.G0: np.ndarray = np.zeros(self.nelm, dtype=float)
        self.B0: np.ndarray = np.zeros(self.nelm, dtype=float)

        self.R2: np.ndarray = np.zeros(self.nelm, dtype=float)
        self.X2: np.ndarray = np.zeros(self.nelm, dtype=float)
        self.G2: np.ndarray = np.zeros(self.nelm, dtype=float)
        self.B2: np.ndarray = np.zeros(self.nelm, dtype=float)

        self.conn: np.ndarray = np.array([WindingsConnection.GG] * self.nelm)

        self.k: np.ndarray = np.ones(nelm, dtype=float)

        self.tap_module: np.ndarray = np.ones(nelm, dtype=float)
        self.tap_module_min: np.ndarray = np.full(nelm, fill_value=0.1, dtype=float)
        self.tap_module_max: np.ndarray = np.full(nelm, fill_value=1.5, dtype=float)
        self.tap_angle: np.ndarray = np.zeros(nelm, dtype=float)
        self.tap_angle_min: np.ndarray = np.full(nelm, fill_value=-6.28, dtype=float)
        self.tap_angle_max: np.ndarray = np.full(nelm, fill_value=6.28, dtype=float)
        self.Beq: np.ndarray = np.zeros(nelm, dtype=float)
        self.G0sw: np.ndarray = np.zeros(nelm, dtype=float)

        self.virtual_tap_t: np.ndarray = np.ones(self.nelm, dtype=float)
        self.virtual_tap_f: np.ndarray = np.ones(self.nelm, dtype=float)

        self.Pfset: np.ndarray = np.zeros(nelm, dtype=float)
        self.Qfset: np.ndarray = np.zeros(nelm, dtype=float)
        self.Qtset: np.ndarray = np.zeros(nelm, dtype=float)
        self.vf_set: np.ndarray = np.ones(nelm, dtype=float)
        self.vt_set: np.ndarray = np.ones(nelm, dtype=float)

        self.Kdp: np.ndarray = np.ones(self.nelm, dtype=float)
        self.Kdp_va: np.ndarray = np.ones(self.nelm, dtype=float)
        self.alpha1: np.ndarray = np.zeros(self.nelm, dtype=float)  # converter losses parameter (alpha1)
        self.alpha2: np.ndarray = np.zeros(self.nelm, dtype=float)  # converter losses parameter (alpha2)
        self.alpha3: np.ndarray = np.zeros(self.nelm, dtype=float)  # converter losses parameter (alpha3)
        self.control_mode: np.ndarray = np.zeros(self.nelm, dtype=object)

        self.contingency_enabled: np.ndarray = np.ones(self.nelm, dtype=int)
        self.monitor_loading: np.ndarray = np.ones(self.nelm, dtype=int)

        self.C_branch_bus_f: sp.lil_matrix = sp.lil_matrix((self.nelm, nbus),
                                                           dtype=int)  # connectivity branch with their "from" bus
        self.C_branch_bus_t: sp.lil_matrix = sp.lil_matrix((self.nelm, nbus),
                                                           dtype=int)  # connectivity branch with their "to" bus

        self.branch_cost: np.ndarray = np.zeros(nelm, dtype=float)

        self.original_idx = np.zeros(nelm, dtype=int)

    def slice(self, elm_idx, bus_idx):
        """
        Slice branch data by given indices
        :param elm_idx: array of branch indices
        :param bus_idx: array of bus indices
        :return: new BranchData instance
        """

        data = BranchData(nelm=len(elm_idx), nbus=len(bus_idx))

        data.names = self.names[elm_idx]

        data.R = self.R[elm_idx]
        data.X = self.X[elm_idx]
        data.G = self.G[elm_idx]
        data.B = self.B[elm_idx]

        data.R0 = self.R[elm_idx]
        data.X0 = self.X[elm_idx]
        data.G0 = self.G[elm_idx]
        data.B0 = self.B[elm_idx]

        data.R2 = self.R[elm_idx]
        data.X2 = self.X[elm_idx]
        data.G2 = self.G[elm_idx]
        data.B2 = self.B[elm_idx]

        data.k = self.k[elm_idx]
        data.virtual_tap_t = self.virtual_tap_f[elm_idx]
        data.virtual_tap_f = self.virtual_tap_t[elm_idx]
        data.Kdp = self.Kdp[elm_idx]
        data.Kdp_va = self.Kdp_va[elm_idx]
        data.dc = self.dc[elm_idx]
        data.alpha1 = self.alpha1[elm_idx]
        data.alpha2 = self.alpha2[elm_idx]
        data.alpha3 = self.alpha3[elm_idx]

        data.conn = self.conn[elm_idx]  # winding connection

        data.control_mode = self.control_mode[elm_idx]
        data.contingency_enabled = self.contingency_enabled[elm_idx]
        data.monitor_loading = self.monitor_loading[elm_idx]

        data.active = self.active[elm_idx]
        data.rates = self.rates[elm_idx]
        data.contingency_rates = self.contingency_rates[elm_idx]
        data.tap_module = self.tap_module[elm_idx]

        data.tap_module_min = self.tap_module_min[elm_idx]
        data.tap_module_max = self.tap_module_max[elm_idx]
        data.tap_angle = self.tap_angle[elm_idx]
        data.tap_angle_min = self.tap_angle_min[elm_idx]
        data.tap_angle_max = self.tap_angle_max[elm_idx]
        data.Beq = self.Beq[elm_idx]
        data.G0sw = self.G0sw[elm_idx]
        data.Pfset = self.Pfset[elm_idx]
        data.Qfset = self.Qfset[elm_idx]
        data.Qtset = self.Qtset[elm_idx]
        data.vf_set = self.vf_set[elm_idx]
        data.vt_set = self.vt_set[elm_idx]

        data.C_branch_bus_f = self.C_branch_bus_f[np.ix_(elm_idx, bus_idx)]
        data.C_branch_bus_t = self.C_branch_bus_t[np.ix_(elm_idx, bus_idx)]

        data.F = get_bus_indices(data.C_branch_bus_f)
        data.T = get_bus_indices(data.C_branch_bus_t)

        data.branch_cost = self.branch_cost[elm_idx]

        data.original_idx = elm_idx

        return data

    def get_island(self, bus_idx):
        """
        Get the array of branch indices that belong to the islands given by the bus indices
        :param bus_idx: array of bus indices
        :return: array of island branch indices
        """
        if self.nelm:
            return tp.get_elements_of_the_island(
                self.C_branch_bus_f + self.C_branch_bus_t,
                island=bus_idx,
                active=self.active)
        else:
            return np.zeros(0, dtype=int)

    def get_ac_indices(self):
        """
        Get ac branch indices
        :return:
        """
        return np.where(self.dc == 0)[0]

    def get_dc_indices(self):
        """
        Get dc branch indices
        :return:
        """
        return np.where(self.dc != 0)[0]

    def get_linear_series_admittance(self):
        """
        Get the linear version of the series admittance for ACDC systems
        :return: Array of the length of the number of branches with 1/X or 1/R depending whether if it is AC or DC
        """
        dc = self.get_dc_indices()
        ac = self.get_ac_indices()
        m_abs = np.abs(self.tap_module)
        if len(dc):
            # compose the vector for AC-DC grids where the R is needed for this matrix
            # even if conceptually we only want the susceptance
            b = np.zeros(self.nelm)
            active = self.active
            b[ac] = 1.0 / (m_abs[ac] * self.X[ac] * active[ac] + 1e-20)  # for ac branches
            b[dc] = 1.0 / (m_abs[dc] * self.R[dc] * active[dc] + 1e-20)  # for dc branches
        else:
            b = 1.0 / (m_abs * self.X * self.active + 1e-20)  # for ac branches

        return b

    def get_monitor_enabled_indices(self):
        """
        Get monitored branch indices
        :return:
        """
        return np.where(self.monitor_loading == 1)[0]

    def get_contingency_enabled_indices(self):
        """
        Get contingency branch indices
        :return:
        """
        return np.where(self.contingency_enabled == 1)[0]

    def to_df(self):
        """
        Create DataFrame with the compiled branches information
        :param t: time index, relevant for those magnitudes that change with time
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

    def __len__(self):
        return self.nelm
