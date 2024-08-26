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
import numba as nb
from typing import Tuple, List
from GridCalEngine.enumerations import BusMode, TapPhaseControl, TapModuleControl
from GridCalEngine.basic_structures import Vec, IntVec, BoolVec


@nb.njit(cache=True)
def compile_types(Pbus: Vec,
                  types: IntVec) -> Tuple[IntVec, IntVec, IntVec, IntVec, IntVec, IntVec]:
    """
    Compile the types.
    :param Pbus: array of real power Injections per node used to choose the slack as
                 the node with greater generation if no slack is provided
    :param types: array of tentative node types (it may be modified internally)
    :return: ref, pq, pv, pqpv
    """

    # check that Sbus is a 1D array
    assert (len(Pbus.shape) == 1)

    pq = np.where(types == BusMode.PQ_tpe.value)[0]
    pv = np.where(types == BusMode.PV_tpe.value)[0]
    pqv = np.where(types == BusMode.PQV_tpe.value)[0]
    p = np.where(types == BusMode.P_tpe.value)[0]
    ref = np.where(types == BusMode.Slack_tpe.value)[0]

    if len(ref) == 0:  # there is no slack!

        if len(pv) == 0:  # there are no pv neither -> blackout grid
            pass
        else:  # select the first PV generator as the slack

            mx = max(Pbus[pv])
            if mx > 0:
                # find the generator that is injecting the most
                i = np.where(Pbus == mx)[0][0]

            else:
                # all the generators are injecting zero, pick the first pv
                i = pv[0]

            # delete the selected pv bus from the pv list and put it in the slack list
            pv = np.delete(pv, np.where(pv == i)[0])
            ref = np.array([i])

        for r in ref:
            types[r] = BusMode.Slack_tpe.value
    else:
        pass  # no problem :)

    no_slack = np.concatenate((pv, pq, p, pqv))
    no_slack.sort()

    return ref, pq, pv, pqv, p, no_slack


class SimulationIndices:
    """
    Class to handle the simulation indices
    """

    def __init__(self,
                 bus_types: IntVec,
                 Pbus: Vec,
                 tap_module_control_mode: List[TapModuleControl],
                 tap_phase_control_mode: List[TapPhaseControl],
                 tap_controlled_buses: IntVec,
                 is_converter: BoolVec,
                 F: IntVec,
                 T: IntVec,
                 is_dc_bus: BoolVec):
        """

        :param bus_types: Bus type initial guess array
        :param Pbus: Active power per bus array
        :param tap_module_control_mode: TapModuleControl control mode array
        :param tap_phase_control_mode: TapPhaseControl control mode array
        :param tap_controlled_buses: Array of bus indices where the tap module control occurs
        :param is_converter: Array of is converter per branch?
        :param is_dc_bus: Array of is DC ? per bus
        """
        # master aray of bus types (nbus)
        self.bus_types = bus_types

        # arrays for branch control types (nbr)
        self.tap_module_control_mode = tap_module_control_mode
        self.tap_controlled_buses = tap_controlled_buses
        self.tap_phase_control_mode = tap_phase_control_mode
        self.is_converter = is_converter
        self.F = F
        self.T = T

        # AC and DC indices
        self.ac: IntVec = np.where(~is_dc_bus)[0]
        self.dc: IntVec = np.where(is_dc_bus)[0]

        # branch control indices
        self.any_control: bool = False

        # indices of the Branches controlling Pf flow with tau
        self.k_pf_tau: IntVec = np.zeros(0, dtype=int)
        self.k_pt_tau: IntVec = np.zeros(0, dtype=int)
        self.k_qf_m: IntVec = np.zeros(0, dtype=int)
        self.k_qt_m: IntVec = np.zeros(0, dtype=int)
        self.k_qf_beq: IntVec = np.zeros(0, dtype=int)  # make Qf = 0 for DC grids
        self.k_v_m: IntVec = np.zeros(0, dtype=int)
        self.k_v_beq: IntVec = np.zeros(0, dtype=int)

        self.k_vsc: IntVec = np.zeros(0, dtype=int)
        self.analyze_branch_controls()

        # determine the bus indices
        self.pq: IntVec = np.zeros(0, dtype=int)
        self.pv: IntVec = np.zeros(0, dtype=int)  # PV-local
        self.p: IntVec = np.zeros(0, dtype=int)  # PV-remote
        self.pqv: IntVec = np.zeros(0, dtype=int)  # PV-remote pair
        self.vd: IntVec = np.zeros(0, dtype=int)  # slack
        self.no_slack: IntVec = np.zeros(0, dtype=int)  # all bus indices that are not slack, sorted
        self.vd, self.pq, self.pv, self.pqv, self.p, self.no_slack = compile_types(
            Pbus=Pbus,
            types=self.bus_types
        )

    @property
    def k_m(self):
        """
        Return a composition of all indices affected by m
        :return: k_v_m | k_qf_m | k_qt_m
        """
        return np.r_[self.k_v_m, self.k_qf_m, self.k_qt_m]

    @property
    def k_tau(self):
        """
        Return a composition of all indices affected by tau
        :return: k_pf_tau | k_pt_tau
        """
        return np.r_[self.k_pf_tau, self.k_pt_tau]

    @property
    def k_mtau(self):
        """
        Return a composition of all indices affected by the intersection of "m" and "tau"
        :return:
        """
        return np.intersect1d(self.k_m, self.k_tau)

    def analyze_branch_controls(self) -> None:
        """
        Analyze the control branches and compute the indices
        :return: None
        """
        k_pf_tau = list()
        k_pt_tau = list()
        k_qf_m = list()
        k_qt_m = list()
        k_qfzero_beq = list()
        k_v_m = list()
        k_v_beq = list()
        k_vsc = list()

        nbr = len(self.tap_phase_control_mode)
        for k in range(nbr):

            ctrl_m = self.tap_module_control_mode[k]
            ctrl_tau = self.tap_phase_control_mode[k]
            is_conv = self.is_converter[k]

            conv_type = 1 if is_conv else 0

            # analyze tap-module controls
            if ctrl_m == TapModuleControl.Vm:

                # Every bus controlled by m has to become a PQV bus
                bus_idx = self.tap_controlled_buses[k]
                self.bus_types[bus_idx] = BusMode.PQV_tpe.value

                if is_conv and bus_idx == self.F[k]:
                    # if this is a converter,
                    # the voltage can be managed with Beq
                    # if the control bus is the "From" bus
                    k_v_beq.append(k)
                    conv_type = 2
                else:
                    # In any other case, the voltage is managed by the tap module
                    k_v_m.append(k)

            elif ctrl_m == TapModuleControl.Qf:

                if not is_conv:
                    k_qf_m.append(k)

            elif ctrl_m == TapModuleControl.Qt:
                k_qt_m.append(k)

            elif ctrl_m == TapModuleControl.fixed:
                pass

            elif ctrl_m == 0:
                pass

            else:
                raise Exception(f"Unknown tap phase module mode {ctrl_m}")

            # analyze tap-phase controls
            if ctrl_tau == TapPhaseControl.Pf:
                k_pf_tau.append(k)
                conv_type = 1

            elif ctrl_tau == TapPhaseControl.Pt:
                k_pt_tau.append(k)
                conv_type = 1

            elif ctrl_tau == TapPhaseControl.fixed:
                if ctrl_m == TapModuleControl.fixed:
                    conv_type = 1

            # elif ctrl_tau == TapPhaseControl.Droop:
            #     pass

            elif ctrl_tau == 0:
                pass

            else:
                raise Exception(f"Unknown tap phase control mode {ctrl_tau}")

            # Beq->qf=0
            if conv_type == 1:
                k_qfzero_beq.append(k)

            if is_conv:
                k_vsc.append(k)

        # determine if there is any control
        self.any_control = bool(len(k_pf_tau)
                                + len(k_pt_tau)
                                + len(k_qf_m)
                                + len(k_qt_m)
                                + len(k_qfzero_beq)
                                + len(k_v_m))

        # convert lists to integer arrays
        self.k_pf_tau = np.array(k_pf_tau, dtype=int)
        self.k_pt_tau = np.array(k_pt_tau, dtype=int)
        self.k_qf_m = np.array(k_qf_m, dtype=int)
        self.k_qt_m = np.array(k_qt_m, dtype=int)
        self.k_qf_beq = np.array(k_qfzero_beq, dtype=int)
        self.k_v_m = np.array(k_v_m, dtype=int)
        self.k_v_beq = np.array(k_v_beq, dtype=int)
        self.k_vsc = np.array(k_vsc, dtype=int)
