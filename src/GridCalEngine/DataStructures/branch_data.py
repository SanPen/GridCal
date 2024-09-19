# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
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
import GridCalEngine.Topology.topology as tp
from GridCalEngine.enumerations import WindingsConnection
from GridCalEngine.Utils.Sparse.sparse_array import SparseObjectArray
from GridCalEngine.basic_structures import Vec, IntVec, StrVec, ObjVec, CxVec, BoolVec
from typing import List, Tuple, Dict


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
        self.protection_rates: Vec = np.zeros(nelm, dtype=float)

        self.F: IntVec = np.zeros(self.nelm, dtype=int)  # indices of the "from" buses
        self.T: IntVec = np.zeros(self.nelm, dtype=int)  # indices of the "to" buses

        # reliability
        self.mttf: Vec = np.zeros(self.nelm, dtype=float)
        self.mttr: Vec = np.zeros(self.nelm, dtype=float)

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
        self.Beq: Vec = np.zeros(nelm, dtype=float)
        self.G0sw: Vec = np.zeros(nelm, dtype=float)

        self.virtual_tap_t: Vec = np.ones(self.nelm, dtype=float)
        self.virtual_tap_f: Vec = np.ones(self.nelm, dtype=float)

        self.Pset: Vec = np.zeros(nelm, dtype=float)  # always over the controlled side
        self.Qset: Vec = np.zeros(nelm, dtype=float)  # always over the controlled side
        self.vset: Vec = np.ones(nelm, dtype=float)  # always over the controlled side

        self.Kdp: Vec = np.ones(self.nelm, dtype=float)
        self.Kdp_va: Vec = np.ones(self.nelm, dtype=float)
        self.alpha1: Vec = np.zeros(self.nelm, dtype=float)  # converter losses parameter (alpha1)
        self.alpha2: Vec = np.zeros(self.nelm, dtype=float)  # converter losses parameter (alpha2)
        self.alpha3: Vec = np.zeros(self.nelm, dtype=float)  # converter losses parameter (alpha3)

        self.tap_module_control_mode: ObjVec = np.zeros(self.nelm, dtype=object)
        self.tap_phase_control_mode: ObjVec = np.zeros(self.nelm, dtype=object)
        self.tap_controlled_buses: IntVec = np.zeros(self.nelm, dtype=int)
        self.is_converter: BoolVec = np.zeros(self.nelm, dtype=bool)

        self.contingency_enabled: IntVec = np.ones(self.nelm, dtype=int)
        self.monitor_loading: IntVec = np.ones(self.nelm, dtype=int)

        # connectivity branch with their "from" bus
        self.C_branch_bus_f: sp.lil_matrix = sp.lil_matrix((self.nelm, nbus), dtype=int)
        # connectivity branch with their "to" bus
        self.C_branch_bus_t: sp.lil_matrix = sp.lil_matrix((self.nelm, nbus), dtype=int)

        self.overload_cost: Vec = np.zeros(nelm, dtype=float)

        self.original_idx: IntVec = np.zeros(nelm, dtype=int)

        self._any_pf_control = False

    def size(self) -> int:
        """
        Get size of the structure
        :return:
        """

        return self.nelm

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

        data.mttf = self.mttf[elm_idx]
        data.mttr = self.mttr[elm_idx]

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
        data.m_taps = self.m_taps.slice(elm_idx)
        data.tau_taps = self.tau_taps.slice(elm_idx)

        data.tap_phase_control_mode = self.tap_phase_control_mode[elm_idx]
        data.tap_module_control_mode = self.tap_module_control_mode[elm_idx]
        data.tap_controlled_buses = self.tap_controlled_buses[elm_idx]
        data.is_converter = self.is_converter[elm_idx]

        data.contingency_enabled = self.contingency_enabled[elm_idx]
        data.monitor_loading = self.monitor_loading[elm_idx]

        data.active = self.active[elm_idx]
        data.rates = self.rates[elm_idx]
        data.contingency_rates = self.contingency_rates[elm_idx]
        data.protection_rates = self.protection_rates[elm_idx]
        data.tap_module = self.tap_module[elm_idx]

        data.tap_module_min = self.tap_module_min[elm_idx]
        data.tap_module_max = self.tap_module_max[elm_idx]
        data.tap_angle = self.tap_angle[elm_idx]
        data.tap_angle_min = self.tap_angle_min[elm_idx]
        data.tap_angle_max = self.tap_angle_max[elm_idx]
        data.Beq = self.Beq[elm_idx]
        data.G0sw = self.G0sw[elm_idx]
        data.Pset = self.Pset[elm_idx]
        data.Qset = self.Qset[elm_idx]
        data.vset = self.vset[elm_idx]

        data.C_branch_bus_f = self.C_branch_bus_f[np.ix_(elm_idx, bus_idx)]
        data.C_branch_bus_t = self.C_branch_bus_t[np.ix_(elm_idx, bus_idx)]

        # first slice, then remap
        data.F = self.F[elm_idx]
        data.T = self.T[elm_idx]
        bus_map: Dict[int, int] = {o: i for i, o in enumerate(bus_idx)}
        for k in range(data.nelm):
            data.F[k] = bus_map[data.F[k]]
            data.T[k] = bus_map[data.T[k]]

        data.overload_cost = self.overload_cost[elm_idx]

        data.original_idx = elm_idx

        data._any_pf_control = self._any_pf_control

        return data

    def copy(self) -> "BranchData":
        """
        Get a deep copy of this object
        :return: new BranchData instance
        """

        data = BranchData(nelm=self.nelm, nbus=self.nbus)

        data.names = self.names.copy()
        data.idtag = self.idtag.copy()

        data.mttf = self.mttf.copy()
        data.mttr = self.mttr.copy()

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
        data.m_taps = self.m_taps.copy()
        data.tau_taps = self.tau_taps.copy()

        data.tap_phase_control_mode = self.tap_phase_control_mode.copy()
        data.tap_module_control_mode = self.tap_module_control_mode.copy()
        data.tap_controlled_buses = self.tap_controlled_buses.copy()
        data.is_converter = self.is_converter.copy()

        data.contingency_enabled = self.contingency_enabled.copy()
        data.monitor_loading = self.monitor_loading.copy()

        data.active = self.active.copy()
        data.rates = self.rates.copy()
        data.contingency_rates = self.contingency_rates.copy()
        data.protection_rates = self.protection_rates.copy()
        data.tap_module = self.tap_module.copy()

        data.tap_module_min = self.tap_module_min.copy()
        data.tap_module_max = self.tap_module_max.copy()
        data.tap_angle = self.tap_angle.copy()
        data.tap_angle_min = self.tap_angle_min.copy()
        data.tap_angle_max = self.tap_angle_max.copy()
        data.Beq = self.Beq.copy()
        data.G0sw = self.G0sw.copy()
        data.Pset = self.Pset.copy()
        data.Qset = self.Qset.copy()
        data.vset = self.vset.copy()

        data.C_branch_bus_f = self.C_branch_bus_f.copy()
        data.C_branch_bus_t = self.C_branch_bus_t.copy()

        data.F = self.F.copy()
        data.T = self.T.copy()

        data.overload_cost = self.overload_cost.copy()

        data.original_idx = self.original_idx.copy()

        data._any_pf_control = self._any_pf_control

        return data

    def get_series_admittance(self) -> CxVec:
        """
        Get the series admittance of the branches
        :return: complex vector
        """
        return 1.0 / (self.R + 1j * self.X)

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

    def get_series_admittance(self) -> CxVec:
        """

        :return:
        """
        return 1.0 / (self.R + 1.0j * self.X)

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

    @property
    def tap(self) -> CxVec:
        """

        :return:
        """
        return self.tap_module * np.exp(1.0j * self.tap_angle)

    def __len__(self) -> int:
        return self.nelm
