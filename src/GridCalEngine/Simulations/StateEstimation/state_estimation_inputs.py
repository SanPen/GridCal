# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from typing import Tuple, List
import numpy as np
from GridCalEngine.basic_structures import Vec
from GridCalEngine.Devices.measurement import (PfMeasurement, QfMeasurement,
                                               PiMeasurement, QiMeasurement,
                                               VmMeasurement, IfMeasurement)


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

        self.pf_value: List[PfMeasurement] = list()  # Branch active power measurements vector of pointers
        self.pf_idx: List[int] = list()  # Branches with power measurements

        self.qf_value: List[QfMeasurement] = list()  # Branch reactive power measurements vector of pointers
        self.qf_idx: List[int] = list()  # Branches with reactive power measurements

        self.i_flow: List[IfMeasurement] = list()  # Branch current module measurements vector of pointers
        self.i_flow_idx: List[int] = list()  # Branches with current measurements

        self.vm_m: List[VmMeasurement] = list()  # Node voltage module measurements vector of pointers
        self.vm_m_idx: List[int] = list()  # nodes with voltage module measurements

    def get_measurements_and_deviations(self) -> Tuple[Vec, Vec]:
        """
        get_measurements_and_deviations the measurements into "measurements" and "sigma"
        ordering: Pinj, Pflow, Qinj, Qflow, Iflow, Vm
        :return: measurements vector, sigma vector
        """

        nz = (
                len(self.p_inj)
                + len(self.pf_value)
                + len(self.q_inj)
                + len(self.qf_value)
                + len(self.i_flow)
                + len(self.vm_m)
        )

        magnitudes = np.zeros(nz)
        sigma = np.zeros(nz)

        # go through the measurements in order and form the vectors
        k = 0
        for m in self.pf_value + self.p_inj + self.qf_value + self.q_inj + self.i_flow + self.vm_m:
            magnitudes[k] = m.value
            sigma[k] = m.sigma
            k += 1

        return magnitudes, sigma
