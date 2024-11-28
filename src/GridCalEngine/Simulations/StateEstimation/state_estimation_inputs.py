# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from typing import Tuple
import numpy as np
from GridCalEngine.basic_structures import Vec


class StateEstimationInput:
    """
    StateEstimationInput
    """

    def __init__(self) -> None:
        """
        State estimation inputs constructor
        """

        # nz = n_pi + n_qi + n_vm + n_pf + n_qf + n_if
        # self.magnitudes = np.zeros(nz)
        # self.sigma = np.zeros(nz)

        # Node active power measurements vector of pointers
        self.p_inj = list()

        # Node  reactive power measurements vector of pointers
        self.q_inj = list()

        # Branch active power measurements vector of pointers
        self.p_flow = list()

        # Branch reactive power measurements vector of pointers
        self.q_flow = list()

        # Branch current module measurements vector of pointers
        self.i_flow = list()

        # Node voltage module measurements vector of pointers
        self.vm_m = list()

        # nodes with power injection measurements
        self.p_inj_idx = list()

        # Branches with power measurements
        self.p_flow_idx = list()

        # nodes with reactive power injection measurements
        self.q_inj_idx = list()

        # Branches with reactive power measurements
        self.q_flow_idx = list()

        # Branches with current measurements
        self.i_flow_idx = list()

        # nodes with voltage module measurements
        self.vm_m_idx = list()

    def consolidate(self) -> Tuple[Vec, Vec]:
        """
        consolidate the measurements into "measurements" and "sigma"
        ordering: Pinj, Pflow, Qinj, Qflow, Iflow, Vm
        :return: measurements vector, sigma vector
        """

        nz = len(self.p_inj) + len(self.p_flow) + len(self.q_inj) + len(self.q_flow) + len(self.i_flow) + len(self.vm_m)

        magnitudes = np.zeros(nz)
        sigma = np.zeros(nz)

        # go through the measurements in order and form the vectors
        k = 0
        for m in self.p_flow + self.p_inj + self.q_flow + self.q_inj + self.i_flow + self.vm_m:
            magnitudes[k] = m.value
            sigma[k] = m.sigma
            k += 1

        return magnitudes, sigma