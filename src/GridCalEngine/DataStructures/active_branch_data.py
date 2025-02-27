# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import numpy as np
from GridCalEngine.Utils.Sparse.sparse_array import SparseObjectArray
from GridCalEngine.basic_structures import Vec, IntVec, ObjVec, CxVec, Logger


class ActiveBranchData:
    """
    ControllableBranchData
    """

    def __init__(self, nelm: int, nbus: int):
        self.nelm: int = nelm
        self.nbus: int = nbus

        self.is_controlled: IntVec = np.zeros(self.nelm, dtype=int)

        self.m_taps = SparseObjectArray(n=self.nelm)
        self.tau_taps = SparseObjectArray(n=self.nelm)

        self.tap_module: Vec = np.ones(nelm, dtype=float)
        self.tap_module_min: Vec = np.full(nelm, fill_value=0.1, dtype=float)
        self.tap_module_max: Vec = np.full(nelm, fill_value=1.5, dtype=float)
        self.tap_angle: Vec = np.zeros(nelm, dtype=float)
        self.tap_angle_min: Vec = np.full(nelm, fill_value=-6.28, dtype=float)
        self.tap_angle_max: Vec = np.full(nelm, fill_value=6.28, dtype=float)
        self.tap_module_control_mode: ObjVec = np.zeros(self.nelm, dtype=object)
        self.tap_phase_control_mode: ObjVec = np.zeros(self.nelm, dtype=object)
        self.tap_controlled_buses: IntVec = np.zeros(self.nelm, dtype=int)

        self.Pset: Vec = np.zeros(nelm, dtype=float)  # always over the controlled side
        self.Qset: Vec = np.zeros(nelm, dtype=float)  # always over the controlled side
        self.vset: Vec = np.ones(nelm, dtype=float)  # always over the controlled side

        self._any_pf_control = False

    @property
    def any_pf_control(self):
        """

        :return:
        """
        return self._any_pf_control

    @any_pf_control.setter
    def any_pf_control(self, value):
        self._any_pf_control = value

    def size(self) -> int:
        """
        Get size of the structure
        :return:
        """

        return self.nelm

    def slice(self, elm_idx: IntVec, bus_idx: IntVec,
              bus_map: IntVec, logger: Logger | None) -> ActiveBranchData:
        """
        Slice branch data by given indices
        :param elm_idx: array of branch indices
        :param bus_idx: array of bus indices
        :return: new BranchData instance
        """

        data = ActiveBranchData(nelm=len(elm_idx), nbus=len(bus_idx))

        data.is_controlled = self.is_controlled[elm_idx]

        data.m_taps = self.m_taps.slice(elm_idx)
        data.tau_taps = self.tau_taps.slice(elm_idx)

        data.tap_module = self.tap_module[elm_idx]
        data.tap_module_min = self.tap_module_min[elm_idx]
        data.tap_module_max = self.tap_module_max[elm_idx]
        data.tap_angle = self.tap_angle[elm_idx]
        data.tap_angle_min = self.tap_angle_min[elm_idx]
        data.tap_angle_max = self.tap_angle_max[elm_idx]
        data.tap_phase_control_mode = self.tap_phase_control_mode[elm_idx]
        data.tap_module_control_mode = self.tap_module_control_mode[elm_idx]
        data.tap_controlled_buses = self.tap_controlled_buses[elm_idx]

        data.Pset = self.Pset[elm_idx]
        data.Qset = self.Qset[elm_idx]
        data.vset = self.vset[elm_idx]

        data.any_pf_control = self.any_pf_control

        for k in range(data.nelm):
            if data.tap_controlled_buses[k] != 0:
                data.tap_controlled_buses[k] = bus_map[data.tap_controlled_buses[k]]
                if data.tap_controlled_buses[k] == -1:
                    if logger is not None:
                        logger.add_error(f"Branch {k}, {self.names[k]} is controlling a bus from another island ",
                                         value=data.F[k])


        return data

    def copy(self) -> ActiveBranchData:
        """

        :return:
        """
        data = ActiveBranchData(nelm=self.nelm, nbus=self.nbus)

        data.is_controlled = self.is_controlled.copy()

        data.m_taps = self.m_taps.copy()
        data.tau_taps = self.tau_taps.copy()

        data.tap_module = self.tap_module.copy()
        data.tap_module_min = self.tap_module_min.copy()
        data.tap_module_max = self.tap_module_max.copy()
        data.tap_angle = self.tap_angle.copy()
        data.tap_angle_min = self.tap_angle_min.copy()
        data.tap_angle_max = self.tap_angle_max.copy()
        data.tap_module_control_mode = self.tap_module_control_mode.copy()
        data.tap_phase_control_mode = self.tap_phase_control_mode.copy()
        data.tap_controlled_buses = self.tap_controlled_buses.copy()

        data.Pset = self.Pset.copy()
        data.Qset = self.Qset.copy()
        data.vset = self.vset.copy()

        data.any_pf_control = self.any_pf_control

        return data

    @property
    def tap(self) -> CxVec:
        """

        :return:
        """
        return self.tap_module * np.exp(1.0j * self.tap_angle)

    def get_controlled_idx(self) -> IntVec:
        """
        Get the controlled device indices
        :return: IntVec
        """
        return np.where(self.is_controlled == 1)[0]
    
    def get_fixed_idx(self) -> IntVec:
        """
        Get the fixed device indices
        :return: IntVec
        """
        return np.where(self.is_controlled == 0)[0]


