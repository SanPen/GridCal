# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
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
import GridCalEngine.Core.topology as tp
from GridCalEngine.enumerations import WindingsConnection
from GridCalEngine.basic_structures import Vec, IntVec, StrVec, ObjVec
from typing import List, Tuple


def get_bus_indices(C_branch_bus: sp.csc_matrix):
    """

    :param C_branch_bus: 
    :return: 
    """
    assert (isinstance(C_branch_bus, sp.csc_matrix))
    F = np.zeros(C_branch_bus.shape[0], dtype=int)

    for j in range(C_branch_bus.shape[1]):
        for l in range(C_branch_bus.indptr[j], C_branch_bus.indptr[j + 1]):
            i = C_branch_bus.indices[l]  # row index
            F[i] = j

    return F


class BranchData:
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

        self.F: IntVec = np.zeros(self.nelm, dtype=int)  # indices of the "from" buses
        self.T: IntVec = np.zeros(self.nelm, dtype=int)  # indices of the "to" buses

        # composite losses curve (a * x^2 + b * x + c)
        self.a: Vec = np.zeros(self.nelm, dtype=float)
        self.b: Vec = np.zeros(self.nelm, dtype=float)
        self.c: Vec = np.zeros(self.nelm, dtype=float)

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

        self.conn: ObjVec = np.array([WindingsConnection.GG] * self.nelm)

        self.k: Vec = np.ones(nelm, dtype=float)

        self.tap_module: Vec = np.ones(nelm, dtype=float)
        self.tap_module_min: Vec = np.full(nelm, fill_value=0.1, dtype=float)
        self.tap_module_max: Vec = np.full(nelm, fill_value=1.5, dtype=float)
        self.tap_angle: Vec = np.zeros(nelm, dtype=float)
        self.tap_angle_min: Vec = np.full(nelm, fill_value=-6.28, dtype=float)
        self.tap_angle_max: Vec = np.full(nelm, fill_value=6.28, dtype=float)
        self.Beq: Vec = np.zeros(nelm, dtype=float)
        self.G0sw: Vec = np.zeros(nelm, dtype=float)

        self.virtual_tap_t: Vec = np.ones(self.nelm, dtype=float)
        self.virtual_tap_f: Vec = np.ones(self.nelm, dtype=float)

        self.Pfset: Vec = np.zeros(nelm, dtype=float)
        self.Qfset: Vec = np.zeros(nelm, dtype=float)
        self.Qtset: Vec = np.zeros(nelm, dtype=float)
        self.vf_set: Vec = np.ones(nelm, dtype=float)
        self.vt_set: Vec = np.ones(nelm, dtype=float)

        self.Kdp: Vec = np.ones(self.nelm, dtype=float)
        self.Kdp_va: Vec = np.ones(self.nelm, dtype=float)
        self.alpha1: Vec = np.zeros(self.nelm, dtype=float)  # converter losses parameter (alpha1)
        self.alpha2: Vec = np.zeros(self.nelm, dtype=float)  # converter losses parameter (alpha2)
        self.alpha3: Vec = np.zeros(self.nelm, dtype=float)  # converter losses parameter (alpha3)
        self.control_mode: ObjVec = np.zeros(self.nelm, dtype=object)

        self.contingency_enabled: IntVec = np.ones(self.nelm, dtype=int)
        self.monitor_loading: IntVec = np.ones(self.nelm, dtype=int)

        self.C_branch_bus_f: sp.lil_matrix = sp.lil_matrix((self.nelm, nbus),
                                                           dtype=int)  # connectivity branch with their "from" bus
        self.C_branch_bus_t: sp.lil_matrix = sp.lil_matrix((self.nelm, nbus),
                                                           dtype=int)  # connectivity branch with their "to" bus

        self.overload_cost: Vec = np.zeros(nelm, dtype=float)

        self.original_idx: IntVec = np.zeros(nelm, dtype=int)

    def slice(self, elm_idx: IntVec, bus_idx: IntVec) -> "BranchData":
        """
        Slice branch data by given indices
        :param elm_idx: array of branch indices
        :param bus_idx: array of bus indices
        :return: new BranchData instance
        """

        data = BranchData(nelm=len(elm_idx), nbus=len(bus_idx))

        data.names = self.names[elm_idx]
        data.idtag = self.idtag[elm_idx]

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
        data.virtual_tap_f = self.virtual_tap_f[elm_idx]
        data.virtual_tap_t = self.virtual_tap_t[elm_idx]
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

        data.F = get_bus_indices(data.C_branch_bus_f.tocsc())
        data.T = get_bus_indices(data.C_branch_bus_t.tocsc())

        data.overload_cost = self.overload_cost[elm_idx]

        data.original_idx = elm_idx

        return data

    def copy(self) -> "BranchData":
        """
        Get a deep copy of this object
        :return: new BranchData instance
        """

        data = BranchData(nelm=self.nelm, nbus=self.nbus)

        data.names = self.names.copy()
        data.idtag = self.idtag.copy()

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

        data.k = self.k.copy()
        data.virtual_tap_f = self.virtual_tap_f.copy()
        data.virtual_tap_t = self.virtual_tap_t.copy()
        data.Kdp = self.Kdp.copy()
        data.Kdp_va = self.Kdp_va.copy()
        data.dc = self.dc.copy()
        data.alpha1 = self.alpha1.copy()
        data.alpha2 = self.alpha2.copy()
        data.alpha3 = self.alpha3.copy()

        data.conn = self.conn.copy()  # winding connection

        data.control_mode = self.control_mode.copy()
        data.contingency_enabled = self.contingency_enabled.copy()
        data.monitor_loading = self.monitor_loading.copy()

        data.active = self.active.copy()
        data.rates = self.rates.copy()
        data.contingency_rates = self.contingency_rates.copy()
        data.tap_module = self.tap_module.copy()

        data.tap_module_min = self.tap_module_min.copy()
        data.tap_module_max = self.tap_module_max.copy()
        data.tap_angle = self.tap_angle.copy()
        data.tap_angle_min = self.tap_angle_min.copy()
        data.tap_angle_max = self.tap_angle_max.copy()
        data.Beq = self.Beq.copy()
        data.G0sw = self.G0sw.copy()
        data.Pfset = self.Pfset.copy()
        data.Qfset = self.Qfset.copy()
        data.Qtset = self.Qtset.copy()
        data.vf_set = self.vf_set.copy()
        data.vt_set = self.vt_set.copy()

        data.C_branch_bus_f = self.C_branch_bus_f.copy()
        data.C_branch_bus_t = self.C_branch_bus_t.copy()

        data.F = get_bus_indices(data.C_branch_bus_f.tocsc())
        data.T = get_bus_indices(data.C_branch_bus_t.tocsc())

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

    def get_inter_areas(self, buses_areas_1, buses_areas_2):
        """
        Get the Branches that join two areas
        :param buses_areas_1: Area from
        :param buses_areas_2: Area to
        :return: List of (branch index, flow sense w.r.t the area exchange)
        """

        lst: List[Tuple[int, float]] = list()
        for k in range(self.nelm):
            if self.F[k] in buses_areas_1 and self.T[k] in buses_areas_2:
                lst.append((k, 1.0))
            elif self.F[k] in buses_areas_2 and self.T[k] in buses_areas_1:
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

    def __len__(self) -> int:
        return self.nelm
