# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
from typing import List, Dict
from VeraGridEngine.basic_structures import IntVec, BoolVec
from VeraGridEngine.Devices.measurement import (PfMeasurement, QfMeasurement,
                                                PtMeasurement, QtMeasurement,
                                                PiMeasurement, QiMeasurement,
                                                PgMeasurement, QgMeasurement,
                                                VmMeasurement, VaMeasurement,
                                                IfMeasurement, ItMeasurement,
                                                MeasurementTemplate)


def slice_pair(obj_measurements: List[MeasurementTemplate],
               obj_indices: List[int],
               index_map: Dict[int, int]):
    """
    Slice obj_measurements and obj_indices using an index->island index map
    :param obj_measurements: list of measurements
    :param obj_indices: list of device indices where the measurement applies
    :param index_map: main index -> island index mapping
    :return: new_obj_measurement, new_obj_index
    """

    new_obj_measurement = list()
    new_obj_indices = list()

    for main_index, measurement in zip(obj_indices, obj_measurements):
        island_index = index_map.get(main_index, None)
        if island_index is not None:
            new_obj_indices.append(island_index)
            new_obj_measurement.append(measurement)

    return new_obj_measurement, new_obj_indices


class StateEstimationInput:
    """
    StateEstimationInput
    """

    def __init__(self) -> None:
        """
        State estimation inputs constructor
        """
        self.p_inj: List[PiMeasurement] = list()  # Node active power measurements vector of pointers
        self.p_idx: List[int] = list()  # nodes with power injection measurements

        self.q_inj: List[QiMeasurement] = list()  # Node  reactive power measurements vector of pointers
        self.q_idx: List[int] = list()  # nodes with reactive power injection measurements

        self.pg_inj: List[PgMeasurement] = list()  # Node active power measurements vector of pointers
        self.pg_idx: List[int] = list()  # nodes with power injection measurements

        self.qg_inj: List[QgMeasurement] = list()  # Node  reactive power measurements vector of pointers
        self.qg_idx: List[int] = list()  # nodes with reactive power injection measurements

        self.pf_value: List[PfMeasurement] = list()  # Branch active power measurements vector of pointers
        self.pf_idx: List[int] = list()  # Branches with power measurements

        self.pt_value: List[PtMeasurement] = list()  # Branch active power measurements vector of pointers
        self.pt_idx: List[int] = list()  # Branches with power measurements

        self.qf_value: List[QfMeasurement] = list()  # Branch reactive power measurements vector of pointers
        self.qf_idx: List[int] = list()  # Branches with reactive power measurements

        self.qt_value: List[QtMeasurement] = list()  # Branch reactive power measurements vector of pointers
        self.qt_idx: List[int] = list()  # Branches with reactive power measurements

        self.if_value: List[IfMeasurement] = list()  # Branch current module measurements vector of pointers
        self.if_idx: List[int] = list()  # Branches with current measurements

        self.it_value: List[ItMeasurement] = list()  # Branch current module measurements vector of pointers
        self.it_idx: List[int] = list()  # Branches with current measurements

        self.vm_value: List[VmMeasurement] = list()  # Node voltage module measurements vector of pointers
        self.vm_idx: List[int] = list()  # nodes with voltage module measurements

        self.va_value: List[VaMeasurement] = list()  # Node voltage angle measurements vector of pointers
        self.va_idx: List[int] = list()  # nodes with voltage angle measurements

        nz = self.size()
        self.flags = np.ones(nz, dtype=int)

    def size(self):
        return (len(self.p_inj)
                + len(self.q_inj)
                + len(self.pg_inj)
                + len(self.qg_inj)
                + len(self.pf_value)
                + len(self.pt_value)
                + len(self.qf_value)
                + len(self.qt_value)
                + len(self.if_value)
                + len(self.it_value)
                + len(self.vm_value)
                + len(self.va_value))

    def slice(self, bus_idx: IntVec, branch_idx: IntVec) -> "StateEstimationInput":
        """
        Slice this object given the island branch and bus indices
        :param bus_idx: array of bus indices of an island
        :param branch_idx: array of branch indices of an island
        :return: new sliced StateEstimationInput
        """
        se = StateEstimationInput()

        # Map old indices → new indices
        bus_index_map = {main_idx: island_idx for island_idx, main_idx in enumerate(bus_idx)}
        branch_index_map = {main_idx: island_idx for island_idx, main_idx in enumerate(branch_idx)}

        se.p_inj, se.p_idx = slice_pair(self.p_inj, self.p_idx, bus_index_map)
        se.q_inj, se.q_idx = slice_pair(self.q_inj, self.q_idx, bus_index_map)

        se.pg_inj, se.pg_idx = slice_pair(self.pg_inj, self.pg_idx, bus_index_map)
        se.qg_inj, se.qg_idx = slice_pair(self.qg_inj, self.qg_idx, bus_index_map)

        se.vm_value, se.vm_idx = slice_pair(self.vm_value, self.vm_idx, bus_index_map)
        se.va_value, se.va_idx = slice_pair(self.va_value, self.va_idx, bus_index_map)

        se.pf_value, se.pf_idx = slice_pair(self.pf_value, self.pf_idx, branch_index_map)
        se.qf_value, se.qf_idx = slice_pair(self.qf_value, self.qf_idx, branch_index_map)
        se.if_value, se.if_idx = slice_pair(self.if_value, self.if_idx, branch_index_map)

        se.pt_value, se.pt_idx = slice_pair(self.pt_value, self.pt_idx, branch_index_map)
        se.qt_value, se.qt_idx = slice_pair(self.qt_value, self.qt_idx, branch_index_map)
        se.it_value, se.it_idx = slice_pair(self.it_value, self.it_idx, branch_index_map)

        return se

    def slice_with_mask(self, mask: BoolVec) -> "StateEstimationInput":
        """
        Get a new StateEstimationInput without the measurements that fall in the mask marked with a 0
        :param mask: mask of measurements to keep
        :return: StateEstimationInput
        """
        mask = np.asarray(mask, dtype=bool)

        new_obj = StateEstimationInput()

        k = 0
        for m_here, m_there, idx_here, idx_there in [(self.p_inj, new_obj.p_inj, self.p_idx, new_obj.p_idx),
                                                     (self.q_inj, new_obj.q_inj, self.q_idx, new_obj.q_idx),
                                                     (self.pg_inj, new_obj.pg_inj, self.pg_idx, new_obj.pg_idx),
                                                     (self.qg_inj, new_obj.qg_inj, self.qg_idx, new_obj.qg_idx),
                                                     (self.pf_value, new_obj.pf_value, self.pf_idx, new_obj.pf_idx),
                                                     (self.pt_value, new_obj.pt_value, self.pt_idx, new_obj.pt_idx),
                                                     (self.qf_value, new_obj.qf_value, self.qf_idx, new_obj.qf_idx),
                                                     (self.qt_value, new_obj.qt_value, self.qt_idx, new_obj.qt_idx),
                                                     (self.if_value, new_obj.if_value, self.if_idx, new_obj.if_idx),
                                                     (self.it_value, new_obj.it_value, self.it_idx, new_obj.it_idx),
                                                     (self.vm_value, new_obj.vm_value, self.vm_idx, new_obj.vm_idx),
                                                     (self.va_value, new_obj.va_value, self.va_idx, new_obj.va_idx)]:

            for m, i in zip(m_here, idx_here):
                if mask[k]:
                    m_there.append(m)
                    idx_there.append(i)
                k += 1

        return new_obj
