# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

import numpy as np
from GridCalEngine.basic_structures import CxVec, Vec, IntVec, BoolVec, StrVec
from GridCalEngine.enumerations import BusMode

class BusData:
    """
    BusData
    """

    def __init__(self, nbus: int):
        """
        Bus data arrays
        :param nbus: number of buses
        """
        self.nbus: int = nbus
        self.idtag: StrVec = np.empty(nbus, dtype=object)
        self.names: StrVec = np.empty(nbus, dtype=object)
        self.active: IntVec = np.ones(nbus, dtype=int)
        self.Vbus: CxVec = np.ones(nbus, dtype=complex)
        self.Vmin: Vec = np.ones(nbus, dtype=float)
        self.Vmax: Vec = np.ones(nbus, dtype=float)
        self.Vnom: Vec = np.ones(nbus, dtype=float)
        self.cost_v: Vec = np.ones(nbus, dtype=float)
        self.angle_min: Vec = np.full(nbus, fill_value=-3.14, dtype=float)
        self.angle_max: Vec = np.full(nbus, fill_value=3.14, dtype=float)
        self.bus_types: IntVec = np.empty(nbus, dtype=int)
        self.is_p_controlled = np.zeros(nbus, dtype=bool)
        self.is_q_controlled = np.zeros(nbus, dtype=bool)
        self.is_vm_controlled = np.zeros(nbus, dtype=bool)
        self.is_va_controlled = np.zeros(nbus, dtype=bool)
        self.installed_power: Vec = np.zeros(nbus, dtype=float)
        self.srap_availbale_power: Vec = np.zeros(nbus, dtype=float)
        self.is_dc: BoolVec = np.empty(nbus, dtype=bool)
        self.areas: IntVec = np.empty(nbus, dtype=int)
        self.substations: IntVec = np.empty(nbus, dtype=int)

        # This is the total value used to compute the q_share in generators, batteries and shunts
        self.q_shared_total = np.zeros(nbus, dtype=float)

        # This is the fixed amount of Q that is Subtrated from Qbus to compute
        # the Q of each generator, battery and shunt controlling
        self.q_fixed = np.zeros(nbus, dtype=float)
        self.ii_fixed = np.zeros(nbus, dtype=float)  # same concept, but imag current from loads
        self.b_fixed = np.zeros(nbus, dtype=float)  # same concept, but susceptance from shunts

        self.original_idx: IntVec = np.zeros(nbus, dtype=int)


    def slice(self, elm_idx: IntVec) -> "BusData":
        """
        Slice this data structure
        :param elm_idx: array of bus indices
        :return: instance of BusData
        """

        data = BusData(nbus=len(elm_idx))

        data.names = self.names[elm_idx]
        data.idtag = self.idtag[elm_idx]
        data.active = self.active[elm_idx]

        data.Vbus = self.Vbus[elm_idx]
        data.Vmin = self.Vmin[elm_idx]
        data.Vmax = self.Vmax[elm_idx]
        data.Vnom = self.Vnom[elm_idx]
        data.cost_v = self.cost_v[elm_idx]
        data.angle_min = self.angle_min[elm_idx]
        data.angle_max = self.angle_max[elm_idx]

        data.bus_types = self.bus_types[elm_idx]
        data.is_p_controlled = self.is_p_controlled[elm_idx]
        data.is_q_controlled = self.is_q_controlled[elm_idx]
        data.is_vm_controlled = self.is_vm_controlled[elm_idx]
        data.is_va_controlled = self.is_va_controlled[elm_idx]
        data.installed_power = self.installed_power[elm_idx]
        data.srap_availbale_power = self.srap_availbale_power[elm_idx]
        data.is_dc = self.is_dc[elm_idx]
        data.areas = self.areas[elm_idx]
        data.substations = self.substations[elm_idx]

        data.q_shared_total = self.q_shared_total[elm_idx]
        data.q_fixed = self.q_fixed[elm_idx]
        data.ii_fixed = self.ii_fixed[elm_idx]
        data.b_fixed = self.b_fixed[elm_idx]

        data.original_idx = elm_idx

        return data

    def size(self) -> int:
        """
        Get size of the structure
        :return:
        """

        return self.nbus

    def copy(self) -> "BusData":
        """
        Deep copy of this structure
        :return: instance of BusData
        """

        data = BusData(nbus=self.nbus)

        data.names = self.names.copy()
        data.idtag = self.idtag.copy()
        data.active = self.active.copy()

        data.Vbus = self.Vbus.copy()
        data.Vmin = self.Vmin.copy()
        data.Vmax = self.Vmax.copy()
        data.Vnom = self.Vnom.copy()
        data.cost_v = self.cost_v.copy()
        data.angle_min = self.angle_min.copy()
        data.angle_max = self.angle_max.copy()

        data.bus_types = self.bus_types.copy()
        data.is_p_controlled = self.is_p_controlled.copy()
        data.is_q_controlled = self.is_q_controlled.copy()
        data.is_vm_controlled = self.is_vm_controlled.copy()
        data.is_va_controlled = self.is_va_controlled.copy()
        data.installed_power = self.installed_power.copy()
        data.srap_availbale_power = self.srap_availbale_power.copy()
        data.is_dc = self.is_dc.copy()
        data.areas = self.areas.copy()
        data.substations = self.substations.copy()

        data.q_shared_total = self.q_shared_total.copy()
        data.q_fixed = self.q_fixed.copy()
        data.ii_fixed = self.ii_fixed.copy()
        data.b_fixed = self.b_fixed.copy()

        data.original_idx = self.original_idx.copy()

        return data

    def set_bus_mode(self, idx: int, val: BusMode):
        """
        Set bus mode
        :param idx: int
        :param val: BusMode
        """
        self.bus_types[idx] = val.value
        is_dc = self.is_dc[idx]
        if val == BusMode.PQ_tpe:
            if is_dc:
                self.is_p_controlled[idx] = True
                self.is_q_controlled[idx] = False
                self.is_vm_controlled[idx] = False
                self.is_va_controlled[idx] = True
            else:
                self.is_p_controlled[idx] = True
                self.is_q_controlled[idx] = True
                self.is_vm_controlled[idx] = False
                self.is_va_controlled[idx] = False
        elif val == BusMode.PV_tpe:
            if is_dc:
                self.is_p_controlled[idx] = True
                self.is_q_controlled[idx] = False
                self.is_vm_controlled[idx] = True
                self.is_va_controlled[idx] = True
            else:
                self.is_p_controlled[idx] = True
                self.is_q_controlled[idx] = False
                self.is_vm_controlled[idx] = True
                self.is_va_controlled[idx] = False

        elif val == BusMode.Slack_tpe:
            if is_dc:
                self.is_p_controlled[idx] = False
                self.is_q_controlled[idx] = False
                self.is_vm_controlled[idx] = True
                self.is_va_controlled[idx] = True
            else:
                self.is_p_controlled[idx] = False
                self.is_q_controlled[idx] = False
                self.is_vm_controlled[idx] = True
                self.is_va_controlled[idx] = True
        elif val == BusMode.PQV_tpe:
            if is_dc:
                self.is_p_controlled[idx] = True
                self.is_q_controlled[idx] = False
                self.is_vm_controlled[idx] = True
                self.is_va_controlled[idx] = True
            else:
                self.is_p_controlled[idx] = True
                self.is_q_controlled[idx] = True
                self.is_vm_controlled[idx] = True
                self.is_va_controlled[idx] = False
        elif val == BusMode.P_tpe:
            if is_dc:
                self.is_p_controlled[idx] = True
                self.is_q_controlled[idx] = False
                self.is_vm_controlled[idx] = False
                self.is_va_controlled[idx] = True
            else:
                self.is_p_controlled[idx] = True
                self.is_q_controlled[idx] = False
                self.is_vm_controlled[idx] = False
                self.is_va_controlled[idx] = False

        else:
            raise ValueError("Unexpected bus mode")

    def __len__(self) -> int:
        return self.nbus
