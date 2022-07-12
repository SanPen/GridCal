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


def get_bus_indices(C_branch_bus):
    F = np.zeros(C_branch_bus.shape[0], dtype=int)

    for j in range(C_branch_bus.shape[1]):
        for l in range(C_branch_bus.indptr[j], C_branch_bus.indptr[j + 1]):
            i = C_branch_bus.indices[l]  # row index
            F[i] = j

    return F


class BranchData:

    def __init__(self, nbr, nbus, ntime=1):
        """
        Branch data arrays
        :param nbr: number of branches
        :param nbus: number of buses
        """
        self.nbr = nbr
        self.ntime = ntime

        self.branch_names = np.empty(self.nbr, dtype=object)

        self.branch_dc = np.zeros(self.nbr, dtype=int)

        self.branch_active = np.zeros((nbr, ntime), dtype=int)
        self.branch_rates = np.zeros((nbr, ntime), dtype=float)
        self.branch_contingency_rates = np.zeros((nbr, ntime), dtype=float)

        self.F = np.zeros(self.nbr, dtype=int)  # indices of the "from" buses
        self.T = np.zeros(self.nbr, dtype=int)  # indices of the "to" buses

        # composite losses curve (a * x^2 + b * x + c)
        self.a = np.zeros(self.nbr, dtype=float)
        self.b = np.zeros(self.nbr, dtype=float)
        self.c = np.zeros(self.nbr, dtype=float)

        self.R = np.zeros(self.nbr, dtype=float)
        self.X = np.zeros(self.nbr, dtype=float)
        self.G = np.zeros(self.nbr, dtype=float)
        self.B = np.zeros(self.nbr, dtype=float)
        self.k = np.ones(nbr, dtype=float)

        self.m = np.ones((nbr, ntime), dtype=float)
        self.m_min = 0.1 * np.ones(nbr, dtype=float)
        self.m_max = 1.5 * np.ones(nbr, dtype=float)
        self.theta = np.zeros((nbr, ntime), dtype=float)
        self.theta_min = - 6.28 * np.ones(nbr, dtype=float)
        self.theta_max = 6.28 * np.ones(nbr, dtype=float)
        self.Beq = np.zeros((nbr, ntime), dtype=float)
        self.G0 = np.zeros((nbr, ntime), dtype=float)

        self.tap_t = np.ones(self.nbr, dtype=float)
        self.tap_f = np.ones(self.nbr, dtype=float)

        self.Pfset = np.zeros((nbr, ntime))
        self.Qfset = np.zeros((nbr, ntime))
        self.Qtset = np.zeros((nbr, ntime))
        self.vf_set = np.ones((nbr, ntime))
        self.vt_set = np.ones((nbr, ntime))

        self.Kdp = np.ones(self.nbr)
        self.Kdp_va = np.ones(self.nbr)
        self.alpha1 = np.zeros(self.nbr)  # converter losses parameter (alpha1)
        self.alpha2 = np.zeros(self.nbr)  # converter losses parameter (alpha2)
        self.alpha3 = np.zeros(self.nbr)  # converter losses parameter (alpha3)
        self.control_mode = np.zeros(self.nbr, dtype=object)

        self.contingency_enabled = np.ones(self.nbr, dtype=int)
        self.monitor_loading = np.ones(self.nbr, dtype=int)

        self.C_branch_bus_f = sp.lil_matrix((self.nbr, nbus), dtype=int)  # connectivity branch with their "from" bus
        self.C_branch_bus_t = sp.lil_matrix((self.nbr, nbus), dtype=int)  # connectivity branch with their "to" bus

    def slice(self, elm_idx, bus_idx, time_idx=None):
        """
        Slice this class
        :param elm_idx: branch indices
        :param bus_idx: bus indices
        :param time_idx: array of time indices
        :return: new BranchData instance
        """

        if time_idx is None:
            tidx = elm_idx
        else:
            tidx = np.ix_(elm_idx, time_idx)

        data = BranchData(nbr=len(elm_idx), nbus=len(bus_idx))

        data.branch_names = self.branch_names[elm_idx]
        # data.F = self.F[elm_idx]
        # data.T = self.T[elm_idx]
        data.R = self.R[elm_idx]
        data.X = self.X[elm_idx]
        data.G = self.G[elm_idx]
        data.B = self.B[elm_idx]
        data.k = self.k[elm_idx]
        data.tap_t = self.tap_f[elm_idx]
        data.tap_f = self.tap_t[elm_idx]
        data.Kdp = self.Kdp[elm_idx]
        data.Kdp_va = self.Kdp_va[elm_idx]
        data.branch_dc = self.branch_dc[elm_idx]
        data.alpha1 = self.alpha1[elm_idx]
        data.alpha2 = self.alpha2[elm_idx]
        data.alpha3 = self.alpha3[elm_idx]

        data.control_mode = self.control_mode[elm_idx]
        data.contingency_enabled = self.contingency_enabled[elm_idx]
        data.monitor_loading = self.monitor_loading[elm_idx]

        data.branch_active = self.branch_active[tidx]
        data.branch_rates = self.branch_rates[tidx]
        data.branch_contingency_rates = self.branch_contingency_rates[tidx]
        data.m = self.m[tidx]

        data.m_min = self.m_min[elm_idx]
        data.m_max = self.m_max[elm_idx]
        data.theta = self.theta[tidx]
        data.theta_min = self.theta_min[elm_idx]
        data.theta_max = self.theta_max[elm_idx]
        data.Beq = self.Beq[tidx]
        data.G0 = self.G0[tidx]
        data.Pfset = self.Pfset[tidx]
        data.Qfset = self.Qfset[tidx]
        data.Qtset = self.Qtset[tidx]
        data.vf_set = self.vf_set[tidx]
        data.vt_set = self.vt_set[tidx]

        data.C_branch_bus_f = self.C_branch_bus_f[np.ix_(elm_idx, bus_idx)]
        data.C_branch_bus_t = self.C_branch_bus_t[np.ix_(elm_idx, bus_idx)]

        data.F = get_bus_indices(data.C_branch_bus_f)
        data.T = get_bus_indices(data.C_branch_bus_t)

        return data

    def get_island(self, bus_idx, t_idx=0):
        """
        get the array of branch indices that belong to the islands given by the bus indices
        :param bus_idx: array of bus indices
        :return: array of island branch indices
        """
        if self.nbr:
            return tp.get_elements_of_the_island(self.C_branch_bus_f + self.C_branch_bus_t,
                                                 island=bus_idx,
                                                 active=self.branch_active[:, t_idx])
        else:
            return np.zeros(0, dtype=int)

    def get_ac_indices(self):
        """

        :return:
        """
        return np.where(self.branch_dc == 0)[0]

    def get_dc_indices(self):
        """

        :return:
        """
        return np.where(self.branch_dc != 0)[0]

    def get_linear_series_admittance(self, t=0):
        """
        Get the linear version of the series admittance for ACDC systems
        :param t: time step index
        :return: Array of the length of the number of branches with 1/X or 1/R depending whether if it is AC or DC
        """
        dc = self.get_dc_indices()
        ac = self.get_ac_indices()
        m_abs = np.abs(self.m[:, t])
        if len(dc):
            # compose the vector for AC-DC grids where the R is needed for this matrix
            # even if conceptually we only want the susceptance
            b = np.zeros(self.nbr)
            active = self.branch_active[:, t]
            b[ac] = 1.0 / (m_abs[ac] * self.X[ac] * active[ac] + 1e-20)  # for ac branches
            b[dc] = 1.0 / (m_abs[dc] * self.R[dc] * active[dc] + 1e-20)  # for dc branches
        else:
            b = 1.0 / (m_abs * self.X * self.branch_active[:, t] + 1e-20)  # for ac branches

        return b

    def get_monitor_enabled_indices(self):
        """

        :return:
        """
        return np.where(self.monitor_loading == 1)[0]

    def get_contingency_enabled_indices(self):
        """

        :return:
        """
        return np.where(self.contingency_enabled == 1)[0]

    def to_df(self, t=0):
        """
        Create DataFrame with the compiled branches information
        :param t: time index, relevant for those magnitudes that change with time
        :return: Pandas DataFrame
        """
        data = {'names': self.branch_names,
                'active': self.branch_active[:, t],
                'F': self.F,
                'T': self.T,
                'Rates': self.branch_rates[:, t],
                'Contingency rates': self.branch_contingency_rates[:, t],
                'R': self.R,
                'X': self.X,
                'G': self.G,
                'B': self.B,
                'Vtap F': self.tap_f,
                'Vtap T': self.tap_t,
                'Tap module': self.m[:, t],
                'Tap angle': self.theta[:, t]}
        return pd.DataFrame(data=data)

    def __len__(self):
        return self.nbr


class BranchOpfData(BranchData):

    def __init__(self, nbr, nbus, ntime=1):
        """

        :param nbr:
        :param nbus:
        :param ntime:
        """
        BranchData.__init__(self, nbr, nbus, ntime)

        self.branch_cost = np.zeros((nbr, ntime), dtype=float)

    def slice(self, elm_idx, bus_idx, time_idx=None):
        """
        Slice this class
        :param elm_idx: branch indices
        :param bus_idx: bus indices
        :param time_idx: array of time indices
        :return: new BranchData instance
        """

        if time_idx is None:
            tidx = elm_idx
        else:
            tidx = np.ix_(elm_idx, time_idx)

        data = super().slice(elm_idx, bus_idx, time_idx)

        data.branch_cost = self.branch_cost[tidx]

        return data
