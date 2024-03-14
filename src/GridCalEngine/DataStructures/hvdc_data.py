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
from typing import List, Tuple
import scipy.sparse as sp
import GridCalEngine.Topology.topology as tp
from GridCalEngine.enumerations import HvdcControlType
from GridCalEngine.basic_structures import Vec, IntVec, BoolVec, StrVec


class HvdcData:
    """
    HvdcData
    """

    def __init__(self, nelm: int, nbus: int):
        """
        Hvdc data arrays
        :param nelm: number of hvdcs
        :param nbus: number of buses
        """
        self.nbus: int = nbus
        self.nelm: int = nelm

        self.names: StrVec = np.zeros(nelm, dtype=object)
        self.idtag: StrVec = np.zeros(nelm, dtype=object)

        self.active: BoolVec = np.zeros(nelm, dtype=int)
        self.dispatchable: IntVec = np.zeros(nelm, dtype=int)
        self.F: IntVec = np.zeros(nelm, dtype=int)
        self.T: IntVec = np.zeros(nelm, dtype=int)

        self.rate: Vec = np.zeros(nelm, dtype=float)
        self.contingency_rate: Vec = np.zeros(nelm, dtype=float)
        self.protection_rates: Vec = np.zeros(nelm, dtype=float)

        self.r: Vec = np.zeros(nelm, dtype=float)

        self.Pset: Vec = np.zeros(nelm, dtype=float)
        self.Pt: Vec = np.zeros(nelm, dtype=float)

        # voltage p.u. set points
        self.Vset_f: Vec = np.zeros(nelm, dtype=float)
        self.Vset_t: Vec = np.zeros(nelm, dtype=float)

        # nominal bus voltages at the from and to ends
        self.Vnf: Vec = np.zeros(nelm, dtype=float)
        self.Vnt: Vec = np.zeros(nelm, dtype=float)

        self.angle_droop: Vec = np.zeros(nelm, dtype=float)
        self.control_mode: np.ndarray = np.zeros(nelm, dtype=object)

        self.Qmin_f: Vec = np.zeros(nelm, dtype=float)
        self.Qmax_f: Vec = np.zeros(nelm, dtype=float)
        self.Qmin_t: Vec = np.zeros(nelm, dtype=float)
        self.Qmax_t: Vec = np.zeros(nelm, dtype=float)

        self.C_hvdc_bus_f: sp.lil_matrix = sp.lil_matrix((nelm, nbus),
                                                         dtype=int)  # this ons is just for splitting islands
        self.C_hvdc_bus_t: sp.lil_matrix = sp.lil_matrix((nelm, nbus),
                                                         dtype=int)  # this ons is just for splitting islands

        self.original_idx = np.zeros(nelm, dtype=int)

    def size(self) -> int:
        """
        Get size of the structure
        :return:
        """

        return self.nelm

    def slice(self, elm_idx, bus_idx) -> "HvdcData":
        """
        Make a deep copy of this structure
        :return: new HvdcData instance
        """

        data = HvdcData(nelm=len(elm_idx),
                        nbus=len(bus_idx))

        data.names = self.names[elm_idx]
        data.idtag = self.idtag[elm_idx]

        data.active = self.active[elm_idx]
        data.dispatchable = self.dispatchable[elm_idx]

        data.rate = self.rate[elm_idx]
        data.contingency_rate = self.contingency_rate[elm_idx]
        data.protection_rates = self.protection_rates[elm_idx]

        data.r = self.r[elm_idx]

        data.Pset = self.Pset[elm_idx]
        data.Pt = self.Pt[elm_idx]

        data.Vset_f = self.Vset_f[elm_idx]
        data.Vset_t = self.Vset_t[elm_idx]

        data.Vnf = self.Vnf[elm_idx]
        data.Vnt = self.Vnt[elm_idx]

        data.angle_droop = self.angle_droop[elm_idx]
        data.control_mode = self.control_mode[elm_idx]

        data.Qmin_f = self.Qmin_f[elm_idx]
        data.Qmax_f = self.Qmax_f[elm_idx]
        data.Qmin_t = self.Qmin_t[elm_idx]
        data.Qmax_t = self.Qmax_t[elm_idx]

        data.C_hvdc_bus_f = self.C_hvdc_bus_f[np.ix_(elm_idx, bus_idx)]
        data.C_hvdc_bus_t = self.C_hvdc_bus_t[np.ix_(elm_idx, bus_idx)]

        data.original_idx = elm_idx

        # first slice, then remap
        data.F = self.F[elm_idx]
        data.T = self.T[elm_idx]
        bus_map = {o: i for i, o in enumerate(bus_idx)}
        for k in range(data.nelm):
            data.F[k] = bus_map[data.F[k]]
            data.T[k] = bus_map[data.T[k]]

        return data

    def copy(self) -> "HvdcData":
        """
        Make a deep copy of this structure
        :return: new HvdcData instance
        """

        data = HvdcData(nelm=self.nelm, nbus=self.nbus)

        data.names = self.names.copy()
        data.idtag = self.idtag.copy()

        data.active = self.active.copy()
        data.dispatchable = self.dispatchable.copy()
        data.F = self.F.copy()
        data.T = self.T.copy()

        data.rate = self.rate.copy()
        data.contingency_rate = self.contingency_rate.copy()
        data.protection_rates = self.protection_rates.copy()

        data.r = self.r.copy()

        data.Pset = self.Pset.copy()
        data.Pt = self.Pt.copy()

        data.Vset_f = self.Vset_f.copy()
        data.Vset_t = self.Vset_t.copy()

        data.Vnf = self.Vnf.copy()
        data.Vnt = self.Vnt.copy()

        data.angle_droop = self.angle_droop.copy()
        data.control_mode = self.control_mode.copy()

        data.Qmin_f = self.Qmin_f.copy()
        data.Qmax_f = self.Qmax_f.copy()
        data.Qmin_t = self.Qmin_t.copy()
        data.Qmax_t = self.Qmax_t.copy()

        data.C_hvdc_bus_f = self.C_hvdc_bus_f.copy()
        data.C_hvdc_bus_t = self.C_hvdc_bus_t.copy()

        data.original_idx = self.original_idx.copy()

        return data

    def get_bus_indices_f(self) -> IntVec:
        """
        Get bus indices "from"
        :return:
        """
        return self.C_hvdc_bus_f * np.arange(self.C_hvdc_bus_f.shape[1])

    def get_bus_indices_t(self) -> IntVec:
        """
        Get bus indices "to"
        :return:
        """
        return self.C_hvdc_bus_t * np.arange(self.C_hvdc_bus_t.shape[1])

    def get_island(self, bus_idx: IntVec):
        """
        Get HVDC indices of the island given by the bus indices
        :param bus_idx: list of bus indices
        :return: list of HVDC lines indices
        """
        if self.nelm:
            return tp.get_elements_of_the_island(self.C_hvdc_bus_f + self.C_hvdc_bus_t, bus_idx, active=self.active)
        else:
            return np.zeros(0, dtype=int)

    def get_qmax_from_per_bus(self) -> Vec:
        """
        Max reactive power in the From Bus
        :return: (nbus, nt) Qmax From
        """
        return self.C_hvdc_bus_f.T * (self.Qmax_f * self.active).T

    def get_qmin_from_per_bus(self) -> Vec:
        """
        Min reactive power in the From Bus
        :return: (nbus, nt) Qmin From
        """
        return self.C_hvdc_bus_f.T * (self.Qmin_f * self.active).T

    def get_qmax_to_per_bus(self) -> Vec:
        """
        Max reactive power in the To Bus
        :return: (nbus, nt) Qmax To
        """
        return self.C_hvdc_bus_t.T * (self.Qmax_t * self.active).T

    def get_qmin_to_per_bus(self) -> Vec:
        """
        Min reactive power in the To Bus
        :return: (nbus, nt) Qmin To
        """
        return self.C_hvdc_bus_t.T * (self.Qmin_t * self.active).T

    def get_angle_droop_in_pu_rad(self, Sbase: float):
        """
        Get the angle droop in pu/rad
        :param Sbase: base power
        :return:
        """
        return self.angle_droop * 57.295779513 / Sbase

    def get_power(self, Sbase: float, theta: Vec) -> Tuple[Vec, Vec, Vec, Vec, Vec, int]:
        """
        Get hvdc power
        :param Sbase: base power
        :param theta: bus angles array
        :return: Pbus, Losses, Pf, Pt, loading, nfree
        """
        Pbus = np.zeros(self.nbus)
        Losses = np.zeros(self.nelm)
        loading = np.zeros(self.nelm)
        Pf = np.zeros(self.nelm)
        Pt = np.zeros(self.nelm)
        nfree = 0

        for i in range(self.nelm):

            if self.active[i]:

                if self.control_mode[i] == HvdcControlType.type_1_Pset:
                    Pcalc = self.Pset[i]

                elif self.control_mode[i] == HvdcControlType.type_0_free:
                    Pcalc = self.Pset[i] + self.angle_droop[i] * np.rad2deg(theta[self.F[i]] - theta[self.T[i]])

                    nfree += 1

                    if Pcalc > self.rate[i]:
                        Pcalc = self.rate[i]
                    if Pcalc < -self.rate[i]:
                        Pcalc = -self.rate[i]

                else:
                    Pcalc = 0.0

                # depending on the value of Pcalc, assign the from and to values
                if Pcalc > 0.0:
                    I = Pcalc / (self.Vnf[i] * self.Vset_f[i])  # current in kA
                    Losses[i] = self.r[i] * I * I  # losses in MW
                    Pf[i] = -Pcalc
                    Pt[i] = Pcalc - Losses[i]

                elif Pcalc < 0.0:
                    I = Pcalc / (self.Vnt[i] * self.Vset_t[i])  # current in kA
                    Losses[i] = self.r[i] * I * I  # losses in MW
                    Pf[i] = -Pcalc - Losses[i]
                    Pt[i] = Pcalc
                else:
                    Losses[i] = 0
                    Pf[i] = 0
                    Pt[0] = 0

                # compute loading
                loading[i] = Pf[i] / (self.rate[i] + 1e-20)

                # Pbus
                Pbus[self.F[i]] += Pf[i] / Sbase
                Pbus[self.T[i]] += Pt[i] / Sbase

        # to p.u.
        Pf /= Sbase
        Pt /= Sbase
        Losses /= Sbase

        # Shvdc, Losses_hvdc, Pf_hvdc, Pt_hvdc, loading_hvdc, n_free
        return Pbus, Losses, Pf, Pt, loading, nfree

    def get_inter_areas(self, buses_areas_1, buses_areas_2):
        """
        Get the hvdcs that join two areas
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

    def __len__(self) -> int:
        """
        Get hvdc count
        :return:
        """
        return self.nelm
