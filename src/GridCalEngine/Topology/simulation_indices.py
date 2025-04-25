# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0
import numpy as np
import numba as nb
from typing import Tuple, List
from GridCalEngine.enumerations import BusMode, TapPhaseControl, TapModuleControl
from GridCalEngine.basic_structures import Vec, IntVec, BoolVec


@nb.njit(cache=True)
def compile_types(Pbus: Vec,
                  types: IntVec,
                  pq_val =1,
                  pv_val=2,
                  vd_val=3,
                  pqv_val=4,
                  p_val=5) -> Tuple[IntVec, IntVec, IntVec, IntVec, IntVec, IntVec]:
    """
    Compile the types.
    :param Pbus: array of real power Injections per node used to choose the slack as
                 the node with greater generation if no slack is provided
    :param types: array of tentative node types (it may be modified internally)
    :param pq_val: value of PQ type
    :param pv_val: value of PV values to use
    :param vd_val: value of VD values to use
    :param pqv_val: value of PQ values to use
    :param p_val: value of PQ values to use
    :return: ref, pq, pv, pqpv
    """

    # check that Sbus is a 1D array
    assert (len(Pbus.shape) == 1)

    pq = np.where(types == pq_val)[0]
    pv = np.where(types == pv_val)[0]
    pqv = np.where(types == pqv_val)[0]
    p = np.where(types == p_val)[0]
    ref = np.where(types == vd_val)[0]

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

            # delete_with_dialogue the selected pv bus from the pv list and put it in the slack list
            pv = np.delete(pv, np.where(pv == i)[0])
            ref = np.array([i])

        for r in ref:
            types[r] = BusMode.Slack_tpe.value
    else:
        pass  # no problem :)

    no_slack = np.concatenate((pv, pq, p, pqv))
    no_slack.sort()

    return ref, pq, pv, pqv, p, no_slack

@nb.njit(cache=True)
def replace_bus_types(bus_types, pq_val =1, pv_val=2, pqv_val=4, p_val=5):

    for i in range(len(bus_types)):

        if bus_types[i] == pqv_val:
            bus_types[i] = pq_val

        elif bus_types[i] == p_val:
            bus_types[i] = pv_val


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
                 F: IntVec,
                 T: IntVec,
                 is_dc_bus: BoolVec,
                 force_only_pq_pv_vd_types=False):
        """

        :param bus_types: Array of Bus type initial guess
        :param Pbus: Array of Active power per bus
        :param tap_module_control_mode: Array of TapModuleControl control mode
        :param tap_phase_control_mode: Array of TapPhaseControl control mode
        :param tap_controlled_buses: Array of bus indices where the tap module control occurs
        :param is_dc_bus: Array of is DC ? per bus
        :param force_only_pq_pv_vd_types: if true, all bus types are forced into PQ PV or VD,
                                          for certain types of simulations that cannot handle other bus types
        """
        # master aray of bus types (nbus)
        self.bus_types = bus_types

        # arrays for branch control types (nbr)
        self.tap_module_control_mode = tap_module_control_mode
        self.tap_controlled_buses = tap_controlled_buses
        self.tap_phase_control_mode = tap_phase_control_mode
        self.F = F
        self.T = T

        # AC and DC indices
        self.ac: IntVec = np.where(~is_dc_bus)[0]
        self.dc: IntVec = np.where(is_dc_bus)[0]

        # determine the bus indices
        self.pq: IntVec = np.zeros(0, dtype=int)
        self.pv: IntVec = np.zeros(0, dtype=int)  # PV-local
        self.p: IntVec = np.zeros(0, dtype=int)  # PV-remote
        self.pqv: IntVec = np.zeros(0, dtype=int)  # PV-remote pair
        self.vd: IntVec = np.zeros(0, dtype=int)  # slack
        self.no_slack: IntVec = np.zeros(0, dtype=int)  # all bus indices that are not slack, sorted

        if force_only_pq_pv_vd_types:
            replace_bus_types(self.bus_types)

        self.vd, self.pq, self.pv, self.pqv, self.p, self.no_slack = compile_types(
            Pbus=Pbus,
            types=self.bus_types
        )

    def get_branch_controls_indices(self) -> Tuple[IntVec, IntVec, IntVec]:
        """
        Analyze the control branches and compute the indices
        :return:  k_m, k_tau, k_mtau
        """
        k_pf_tau = list()
        k_pt_tau = list()
        k_qf_m = list()
        k_qt_m = list()
        k_v_m = list()
        nbr = len(self.F)

        for k in range(nbr):

            ctrl_m = self.tap_module_control_mode[k]
            ctrl_tau = self.tap_phase_control_mode[k]

            # analyze tap-module controls
            if ctrl_m == TapModuleControl.Vm:

                # In any other case, the voltage is managed by the tap module
                k_v_m.append(k)

            elif ctrl_m == TapModuleControl.Qf:

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

            elif ctrl_tau == TapPhaseControl.Pt:
                k_pt_tau.append(k)

            elif ctrl_tau == TapPhaseControl.fixed:
                pass

            elif ctrl_tau == 0:
                pass

            else:
                raise Exception(f"Unknown tap phase control mode {ctrl_tau}")


        # convert lists to integer arrays
        k_pf_tau = np.array(k_pf_tau, dtype=int)
        k_pt_tau = np.array(k_pt_tau, dtype=int)
        k_qf_m = np.array(k_qf_m, dtype=int)
        k_qt_m = np.array(k_qt_m, dtype=int)
        k_v_m = np.array(k_v_m, dtype=int)

        k_m = np.r_[k_v_m, k_qf_m, k_qt_m]
        k_tau = np.r_[k_pf_tau, k_pt_tau]
        k_mtau = np.intersect1d(k_m, k_tau)

        return k_m, k_tau, k_mtau