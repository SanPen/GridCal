# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import numpy as np

from VeraGridEngine.DataStructures.numerical_circuit import NumericalCircuit
from VeraGridEngine.basic_structures import CxVec, IntVec, Vec
from VeraGridEngine.Simulations.PowerFlow.NumericalMethods.common_functions import voltage_q_droop


class StaticGeneratorDroop:
    """VSC-equivalent AC injections shared by balanced and ABC power flows."""

    __slots__ = ('idx', 'bus_idx', 'reference', 'snom', 'droop', 'vset', 'vmin', 'vmax', 'sbase', 'nbus')

    def __init__(self, nc: NumericalCircuit) -> None:
        """Select active droop devices without changing their fixed P/Q reference.

        :param nc: Compiled circuit with static generators in load data.
        """
        self.idx: IntVec = np.flatnonzero(nc.load_data.active & (nc.load_data.q_droop > 0.0))
        self.bus_idx: IntVec = nc.load_data.bus_idx[self.idx]
        self.reference: CxVec = -nc.load_data.S[self.idx] / nc.Sbase
        self.snom: Vec = nc.load_data.q_droop_snom[self.idx]
        self.droop: Vec = nc.load_data.q_droop[self.idx]
        self.vset: Vec = nc.load_data.q_droop_vset[self.idx]
        self.vmin: Vec = nc.load_data.q_droop_vmin[self.idx]
        self.vmax: Vec = nc.load_data.q_droop_vmax[self.idx]
        self.sbase: float = nc.Sbase
        self.nbus: int = nc.nbus

    def power(self, voltage: CxVec) -> CxVec:
        """Evaluate the existing VSC curve with the AC injection sign.

        :param voltage: Terminal positive-sequence voltage of each selected device, pu.
        :return: Total three-phase complex injection per device, system pu.
        """
        power: CxVec = self.reference.copy()
        k: int
        for k in range(len(self.idx)):
            # The VSC function uses absorbed Q; a static generator uses injected Q.
            # Keep its voltage clamps and its existing (unclipped) reactive-power law.
            power[k] = complex(self.reference[k].real, -voltage_q_droop(
                ut=voltage[k], u_setpoint_min=self.vmin[k], u_setpoint_max=self.vmax[k],
                u_setpoint=self.vset[k], Q_setpoint=-self.reference[k].imag,
                S_r=self.snom[k], droop=self.droop[k], Q_min=-np.inf, Q_max=np.inf, S_base=self.sbase))
        return power

    def delta_q_bus(self, voltage: CxVec) -> Vec:
        """Correct the fixed Q reference already present in balanced bus injections.

        :param voltage: Bus voltages in pu.
        :return: Additional injected Q per bus, system pu.
        """
        result: Vec = np.zeros(self.nbus)
        np.add.at(result, self.bus_idx, self.power(voltage[self.bus_idx]).imag - self.reference.imag)
        return result

