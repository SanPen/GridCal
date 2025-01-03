# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import numpy as np
from typing import List, Tuple, Set
from GridCalEngine.DataStructures.branch_parent_data import BranchParentData
from GridCalEngine.enumerations import HvdcControlType
from GridCalEngine.basic_structures import Vec, IntVec, Logger


class HvdcData(BranchParentData):
    """
    HvdcData
    """

    def __init__(self, nelm: int, nbus: int):
        """
        Hvdc data arrays
        :param nelm: number of hvdcs
        :param nbus: number of buses
        """
        BranchParentData.__init__(self, nelm=nelm, nbus=nbus)

        self.dispatchable: IntVec = np.zeros(nelm, dtype=int)

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

    def size(self) -> int:
        """
        Get size of the structure
        :return:
        """

        return self.nelm

    def slice(self, elm_idx: IntVec, bus_idx: IntVec, bus_map: IntVec, logger: Logger | None) -> "HvdcData":
        """
        Make a deep copy of this structure
        :return: new HvdcData instance
        """
        data, bus_map = super().slice(elm_idx, bus_idx, bus_map, logger)
        data: HvdcData = data
        data.__class__ = HvdcData

        data.dispatchable = self.dispatchable[elm_idx]

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

        return data

    def remap(self, bus_map_arr: IntVec):
        """
        Remapping of the branch buses
        :param bus_map_arr: array of old-to-new buses
        """
        for k in range(self.nelm):
            f = self.F[k]
            t = self.T[k]
            new_f = bus_map_arr[f]
            new_t = bus_map_arr[t]
            self.F[k] = new_f
            self.T[k] = new_t

    def copy(self) -> "HvdcData":
        """
        Make a deep copy of this structure
        :return: new HvdcData instance
        """

        data: HvdcData = super().copy()
        data.__class__ = HvdcData

        data.dispatchable = self.dispatchable.copy()

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

        return data

    def get_bus_indices_f(self) -> IntVec:
        """
        Get bus indices "from"
        :return:
        """
        return self.F

    def get_bus_indices_t(self) -> IntVec:
        """
        Get bus indices "to"
        :return:
        """
        return self.T

    def get_qmax_from_per_bus(self) -> Vec:
        """
        Max reactive power in the From Bus
        :return: (nbus, nt) Qmax From
        """
        val = np.zeros(self.nbus)
        for k in range(self.nelm):
            i = self.F[k]
            val[i] += self.Qmax_f[k] * self.active[k]
        return val

    def get_qmin_from_per_bus(self) -> Vec:
        """
        Min reactive power in the From Bus
        :return: (nbus, nt) Qmin From
        """
        val = np.zeros(self.nbus)
        for k in range(self.nelm):
            i = self.F[k]
            val[i] += self.Qmin_f[k] * self.active[k]
        return val

    def get_qmax_to_per_bus(self) -> Vec:
        """
        Max reactive power in the To Bus
        :return: (nbus, nt) Qmax To
        """
        val = np.zeros(self.nbus)
        for k in range(self.nelm):
            i = self.T[k]
            val[i] += self.Qmax_t[k] * self.active[k]
        return val

    def get_qmin_to_per_bus(self) -> Vec:
        """
        Min reactive power in the To Bus
        :return: (nbus, nt) Qmin To
        """
        val = np.zeros(self.nbus)
        for k in range(self.nelm):
            i = self.T[k]
            val[i] += self.Qmin_t[k] * self.active[k]
        return val

    def get_angle_droop_in_pu_rad(self, Sbase: float):
        """
        Get the angle droop in pu/rad
        :param Sbase: base power
        :return:
        """
        # convert MW/deg to pu/rad
        # MW    180 deg    1
        # --- x ------- x ------ = 360 * 180 / pi / 100 = 206.26 aprox
        # deg   pi rad    100 MVA
        return self.angle_droop * 57.295779513 / Sbase

    def get_angle_droop_in_pu_rad_at(self, i: int, Sbase: float):
        """
        Get the angle droop in pu/rad
        :param i: index
        :param Sbase: base power
        :return:
        """
        # convert MW/deg to pu/rad
        # MW    180 deg    1
        # --- x ------- x ------ = 360 * 180 / pi / 100 = 206.26 aprox
        # deg   pi rad    100 MVA
        return self.angle_droop[i] * 57.295779513 / Sbase

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

                    if Pcalc > self.rates[i]:
                        Pcalc = self.rates[i]
                    if Pcalc < -self.rates[i]:
                        Pcalc = -self.rates[i]

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
                    Pt[i] = 0

                # compute loading
                loading[i] = Pf[i] / (self.rates[i] + 1e-20)

                # Pbus
                Pbus[self.F[i]] += Pf[i] / Sbase
                Pbus[self.T[i]] += Pt[i] / Sbase

        # to p.u.
        Pf /= Sbase
        Pt /= Sbase
        Losses /= Sbase

        # Shvdc, Losses_hvdc, Pf_hvdc, Pt_hvdc, loading_hvdc, n_free
        return Pbus, Losses, Pf, Pt, loading, nfree

    def get_inter_areas(self, bus_idx_from: IntVec | Set[int], bus_idx_to: IntVec | Set[int]):
        """
        Get the hvdcs that join two areas
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

    def __len__(self) -> int:
        """
        Get hvdc count
        :return:
        """
        return self.nelm
