# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0


from typing import Set
import numpy as np
import numba as nb
from GridCalEngine.enumerations import (TapPhaseControl, TapModuleControl, BusMode, HvdcControlType,
                                        ConverterControlType)
from GridCalEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCalEngine.DataStructures.numerical_circuit import NumericalCircuit
from GridCalEngine.DataStructures.vsc_data import VscData
from GridCalEngine.basic_structures import Logger, BoolVec, IntVec, Vec
from typing import Tuple, List

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
    print("Hello from compile_types")

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


# @nb.njit(cache=True)
def generalized_compile_types(Pbus: Vec,
                  is_p_controlled: BoolVec,
                  is_q_controlled: BoolVec,
                  is_vm_controlled: BoolVec,
                  is_va_controlled: BoolVec) -> Tuple[IntVec, IntVec, IntVec, IntVec, IntVec, IntVec]:
    """
    Compile the types.
    :param Pbus: array of real power Injections per node used to choose the slack as
                 the node with greater generation if no slack is provided
    :param types: array of tentative node types (it may be modified internally)
    :return: ref, pq, pv, pqpv
    """
    print("Hello from compile_types")

    # check that Sbus is a 1D array
    assert (len(Pbus.shape) == 1)

    # pq = np.where(types == BusMode.PQ_tpe.value)[0]
    # pv = np.where(types == BusMode.PV_tpe.value)[0]
    # pqv = np.where(types == BusMode.PQV_tpe.value)[0]
    # p = np.where(types == BusMode.P_tpe.value)[0]
    # ref = np.where(types == BusMode.Slack_tpe.value)[0]

    pv = np.where(is_p_controlled & is_vm_controlled)[0]
    ref = np.where(is_vm_controlled & is_va_controlled)[0]

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
            is_p_controlled[i] = False
            is_q_controlled[i] = False
            is_vm_controlled[i] = True
            is_va_controlled[i] = True

        # for r in ref:
        #     types[r] = BusMode.Slack_tpe.value
    else:
        pass  # no problem :)


class GeneralizedSimulationIndices:
    """
    GeneralizedSimulationIndices
    """

    def __init__(self,
                 nc: NumericalCircuit,
                 pf_options: PowerFlowOptions,
                 logger: Logger) -> None:
        """
        Pass now the data classes, maybe latter on pass only the necessary attributes
        Specified sets of indices represent those indices where we know the value of the variable.
        Unspecified sets can be obtained by subtracting the specified sets from the total set of indices.
        Sets can only be of two types: bus indices or branch indices.
        We need in each device data to have the corresponding bus_idx and branch_idx accordingly.

        g_sets = [cg_pac, cg_qac, cg_pdc, cg_acdc, cg_hvdc, cg_pftr, cg_pttr, cg_qftr, cg_qtktr]
        x_sets = [cx_va, cx_vm, cx_tau, cx_m, cx_pzip, cx_qzip, cx_pfa, cx_pta, cx_qfa, cx_qta]

        g_sets identify the indices where the equations are specified
        x_sets identify the indices of the unknowns that we know (the ones we have to solve for are the negation)

        Mapping between devices and g_sets:
        --------------------------------------
        cg_pac = All AC buses (AC P balance)
        cg_qac = All AC buses (AC Q balance)
        cg_pdc = All DC buses (DC P balance)
        cg_acdc = All VSCs (loss equation)
        cg_hvdc = All HVDC lines (loss equation + control equation such as Pf = Pset + kdroop * (angle_F - angle_T))
        cg_pftr = All controllable transformers (Pf relationship with transformer admittances)
        cg_pttr = All controllable transformers (Pt relationship with transformer admittances)
        cg_qftr = All controllable transformers (Qf relationship with transformer admittances)
        cg_qttr = All controllable transformers (Qt relationship with transformer admittances)

        Much of the complexity is in finding the x_sets, this is where Raiyan was using the negation

        Mapping between devices and x_sets:
        --------------------------------------
        cx_va = All slack buses
        cx_vm = All slack buses, generators, controlled shunts, batteries, HVDC lines, VSCs, transformers (check collision)
        cx_tau = All controllable transformers that do not use the tap phase control mode
        cx_m = All controllable transformers that do not use the tap module control mode
        cx_pzip = All generators, all batteries, all loads (check collision)
        cx_qzip = Non-controllable generators, non_controllable batteries, all loads (check collision)
        cx_pfa = VSCs controlling Pf, transformers controlling Pf
        cx_pta = VSCs controlling Pt, transformers controlling Pt
        cx_qfa = VSCs controlling Qf, transformers controlling Qf
        cx_qta = VSCs controlling Qt, transformers controlling Qt

        Potential collisions to check:
        --------------------------------------
        - Active elements setting simultaneous Vm: generators, controlled shunts, batteries, HVDC lines, VSCs, transformers, slack buses
        - Qzip: the Q of an AC bus becomes unknown if the bus is slack or contains a controllable generator/battery/shunt
        - Pzip: specified in all buses unless slack

        For each potential collision type:
        - Pzip: store all bus indices except for the slack ones (sort of ~bus_data.is_slack[:])
        - Qzip: store the bus indices of devices acting as controllable injections (generators, batteries, controlled shunts)
                then run Pzip - bus_vm_source_used to get the Qzip set
        - Vm: store the indices of already controlled buses, raising an error if we try to set the same bus twice, stopping the program there

        :param nc: NumericalCircuit
        return si.SimulationIndices(bus_types=self.bus_data.bus_types,
                                    Pbus=self.Sbus.real,
                                    tap_module_control_mode=self.active_branch_data.tap_module_control_mode,
                                    tap_phase_control_mode=self.active_branch_data.tap_phase_control_mode,
                                    tap_controlled_buses=self.active_branch_data.tap_controlled_buses,
                                    is_converter=np.zeros(self.nbr, dtype=bool),
                                    F=self.passive_branch_data.F,
                                    T=self.passive_branch_data.T,
                                    is_dc_bus=self.bus_data.is_dc)
        """

        self.nc = nc
        self.logger = logger

        # arrays for branch control types (nbr)
        self.tap_module_control_mode = nc.active_branch_data.tap_module_control_mode
        self.tap_controlled_buses = nc.active_branch_data.tap_phase_control_mode
        self.tap_phase_control_mode = nc.active_branch_data.tap_controlled_buses
        self.F = nc.passive_branch_data.F
        self.T = nc.passive_branch_data.T

        # Bus indices
        self.bus_types = nc.bus_data.bus_types.copy()
        self.is_p_controlled = nc.bus_data.is_p_controlled.copy()
        self.is_q_controlled = nc.bus_data.is_q_controlled.copy()
        self.is_vm_controlled = nc.bus_data.is_vm_controlled.copy()
        self.is_va_controlled = nc.bus_data.is_va_controlled.copy()
        self.i_u_vm = np.where(self.is_vm_controlled == 0)[0]
        self.i_u_va = np.where(self.is_va_controlled == 0)[0]
        self.i_k_p = np.where(self.is_p_controlled == 1)[0]
        self.i_k_q = np.where(self.is_q_controlled == 1)[0]

        # Controllable Branch Indices
        self.cbr_m = []
        self.cbr_tau = []
        self.cbr = []
        self.k_cbr_pf = []
        self.k_cbr_pt = []
        self.k_cbr_qf = []
        self.k_cbr_qt = []
        self.cbr_pf_set = []
        self.cbr_pt_set = []
        self.cbr_qf_set = []
        self.cbr_qt_set = []

        # VSC Indices
        self.vsc = []
        self.u_vsc_pf = []
        self.u_vsc_pt = []
        self.u_vsc_qt = []
        self.k_vsc_pf = []
        self.k_vsc_pt = []
        self.k_vsc_qt = []
        self.vsc_pf_set = []
        self.vsc_pt_set = []
        self.vsc_qt_set = []

        # HVDC Indices
        self.hvdc = []

        # Analyze Branch controls
        self.analyze_branch_controls()

        # Check that controlled magnitudes are 2 on average across all buses
        total_controlled_magnitudes = np.sum(
            self.is_p_controlled.astype(int) + self.is_q_controlled.astype(int) + self.is_vm_controlled.astype(int) + self.is_va_controlled.astype(int))
        print("total_controlled_magnitudes", total_controlled_magnitudes)
        print("self.is_p_controlled", self.is_p_controlled)
        print("self.is_q_controlled", self.is_q_controlled)
        print("self.is_vm_controlled", self.is_vm_controlled)
        print("self.is_va_controlled", self.is_va_controlled)
        print("element wise sum", self.is_p_controlled.astype(int) + self.is_q_controlled.astype(int) + self.is_vm_controlled.astype(int) + self.is_va_controlled.astype(int))
        assert total_controlled_magnitudes == self.nc.bus_data.nbus*2, f"Sum of all control flags must be equal to 2 times the number of buses, which is {self.nc.bus_data.nbus*2}, got {total_controlled_magnitudes}"


        # # setpoints that correspond to the ck sets, P and Q in MW
        # self.va_setpoints = list()
        # self.vm_setpoints = list()
        # self.tau_setpoints = list()
        # self.m_setpoints = list()
        # self.pzip_setpoints = list()
        # self.qzip_setpoints = list()
        # self.pf_setpoints = list()
        # self.pt_setpoints = list()
        # self.qf_setpoints = list()
        # self.qt_setpoints = list()

        # Ancilliary
        # Source refers to the bus with the controlled device directly connected
        # Pointer refers to the bus where we control the voltage magnitude
        # Unspecified zqip is true if slack or bus with controllable gen/batt/shunt
        self.bus_vm_source_used: BoolVec | None = None
        self.bus_vm_pointer_used: BoolVec | None = None
        self.bus_unspecified_qzip: BoolVec | None = None

        # 1 if free mode (P as a function of angle drop), 0 if fixed mode (Pset)
        self.hvdc_mode: BoolVec | None = None

        # Run the search to get the indices
        # self.fill_gx_sets(nc=nc, pf_options=pf_options)

    def analyze_bus_types(self) -> None:
        """
        Analyze the bus types and compute the indices
        :return: None
        """
        for i, bus_type in enumerate(self.bus_types):
            if bus_type == BusMode.PQ_tpe.value:
                self.p_control[i] = 1
                self.q_control[i] = 1

            elif bus_type == BusMode.PV_tpe.value:
                self.p_control[i] = 1
                self.vm_control[i] = 1

            elif bus_type == BusMode.Slack_tpe.value:
                self.vm_control[i] = 1
                self.va_control[i] = 1

            elif bus_type == BusMode.PQV_tpe.value:
                self.p_control[i] = 1
                self.q_control[i] = 1
                self.vm_control[i] = 1

            elif bus_type == BusMode.P_tpe.value:
                self.p_control[i] = 1



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

        i = 0

        # CONTROLLABLE BRANCH LOOP
        for k in range(self.nc.passive_branch_data.nelm):

            ctrl_m = self.tap_module_control_mode[k]
            ctrl_tau = self.tap_phase_control_mode[k]

            # analyze tap-module controls
            if ctrl_m == TapModuleControl.Vm:

                # Every bus controlled by m has to become a PQV bus
                bus_idx = self.tap_controlled_buses[k]
                self.is_p_controlled[bus_idx] = True
                self.is_q_controlled[bus_idx] = True
                self.is_vm_controlled[bus_idx] = True
                self.is_va_controlled[bus_idx] = False

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
            i += 1

        # VSC LOOP
        for k in range(self.nc.vsc_data.nelm):
            self.vsc.append(i)
            control1 = self.nc.vsc_data.control1[k]
            control2 = self.nc.vsc_data.control2[k]
            assert control1 != control2, f"VSC control types must be different for VSC indexed at {k}"
            control1_magnitude = self.nc.vsc_data.control1_val[k]
            control2_magnitude = self.nc.vsc_data.control2_val[k]
            control1_bus_device = self.nc.vsc_data.control1_bus_idx[k]
            control2_bus_device = self.nc.vsc_data.control2_bus_idx[k]
            control1_branch_device = self.nc.vsc_data.control1_branch_idx[k]
            control2_branch_device = self.nc.vsc_data.control2_branch_idx[k]

            """"    
        
            Vm_dc = 'Vm_dc'
            Vm_ac = 'Vm_ac'
            Va_ac = 'Va_ac'
            Qac = 'Q_ac'
            Pdc = 'P_dc'
            Pac = 'P_ac'
            
            
            """
            if control1 == ConverterControlType.Vm_dc:
                if control2 == ConverterControlType.Vm_dc:
                    self.logger.add_error(
                        f"VSC control1 and control2 are the same for VSC indexed at {k},"
                        f" control1: {control1}, control2: {control2}")
                elif control2 == ConverterControlType.Vm_ac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                elif control2 == ConverterControlType.Va_ac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        self.is_va_controlled[control2_bus_device] = True
                elif control2 == ConverterControlType.Qac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                        pass

                    if control1_branch_device > -1:
                        # self.u_vsc_pf.append(control1_branch_device)
                        # self.u_vsc_pt.append(control1_branch_device)
                        # self.u_vsc_qt.append(control1_branch_device)

                        # self.k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)

                        # self.vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                        pass

                    if control2_branch_device > -1:
                        self.u_vsc_pf.append(control2_branch_device)
                        self.u_vsc_pt.append(control2_branch_device)
                        # self.u_vsc_qt.append(control2_branch_device)

                        # self.k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        self.k_vsc_qt.append(control2_branch_device)

                        # self.vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        self.vsc_qt_set.append(control2_magnitude)

                elif control2 == ConverterControlType.Pdc:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                        pass

                    if control1_branch_device > -1:
                        # self.u_vsc_pf.append(control1_branch_device)
                        # self.u_vsc_pt.append(control1_branch_device)
                        # self.u_vsc_qt.append(control1_branch_device)

                        # self.k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)

                        # self.vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                        pass

                    if control2_branch_device > -1:
                        # self.u_vsc_pf.append(control2_branch_device)
                        self.u_vsc_pt.append(control2_branch_device)
                        self.u_vsc_qt.append(control2_branch_device)

                        self.k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)

                        self.vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)

                elif control2 == ConverterControlType.Pac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                        pass
                    if control1_branch_device > -1:
                        # self.u_vsc_pf.append(control1_branch_device)
                        # self.u_vsc_pt.append(control1_branch_device)
                        # self.u_vsc_qt.append(control1_branch_device)
                        # self.k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)
                        # self.vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                        pass
                    if control2_branch_device > -1:
                        self.u_vsc_pf.append(control2_branch_device)
                        # self.u_vsc_pt.append(control2_branch_device)
                        self.u_vsc_qt.append(control2_branch_device)

                        # self.k_vsc_pf.append(control2_branch_device)
                        self.k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)

                        # self.vsc_pf_set.append(control2_magnitude)
                        self.vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)

                else:
                    raise Exception(f"Unknown control type {control2}")

            elif control1 == ConverterControlType.Vm_ac:
                if control2 == ConverterControlType.Vm_dc:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                elif control2 == ConverterControlType.Vm_ac:
                    self.logger.add_error(
                        f"VSC control1 and control2 are the same for VSC indexed at {k},"
                        f" control1: {control1}, control2: {control2}")

                elif control2 == ConverterControlType.Va_ac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        self.is_va_controlled[control2_bus_device] = True

                elif control2 == ConverterControlType.Qac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                        pass
                    if control1_branch_device > -1:
                        # self.u_vsc_pf.append(control1_branch_device)
                        # self.u_vsc_pt.append(control1_branch_device)
                        # self.u_vsc_qt.append(control1_branch_device)
                        # self.k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)
                        # self.vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                        pass
                    if control2_branch_device > -1:
                        self.u_vsc_pf.append(control2_branch_device)
                        self.u_vsc_pt.append(control2_branch_device)
                        # self.u_vsc_qt.append(control2_branch_device)

                        # self.k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        self.k_vsc_qt.append(control2_branch_device)

                        # self.vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        self.vsc_qt_set.append(control2_magnitude)

                elif control2 == ConverterControlType.Pdc:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                        pass
                    if control1_branch_device > -1:
                        # self.u_vsc_pf.append(control1_branch_device)
                        # self.u_vsc_pt.append(control1_branch_device)
                        # self.u_vsc_qt.append(control1_branch_device)
                        # self.k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)
                        # self.vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                        pass
                    if control2_branch_device > -1:
                        # self.u_vsc_pf.append(control2_branch_device)
                        self.u_vsc_pt.append(control2_branch_device)
                        self.u_vsc_qt.append(control2_branch_device)

                        self.k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)

                        self.vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)

                elif control2 == ConverterControlType.Pac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                        pass
                    if control1_branch_device > -1:
                        # self.u_vsc_pf.append(control1_branch_device)
                        # self.u_vsc_pt.append(control1_branch_device)
                        # self.u_vsc_qt.append(control1_branch_device)
                        # self.k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)
                        # self.vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                        pass
                    if control2_branch_device > -1:
                        self.u_vsc_pf.append(control2_branch_device)
                        # self.u_vsc_pt.append(control2_branch_device)
                        self.u_vsc_qt.append(control2_branch_device)

                        # self.k_vsc_pf.append(control2_branch_device)
                        self.k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)

                        # self.vsc_pf_set.append(control2_magnitude)
                        self.vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)

                else:
                    raise Exception(f"Unknown control type {control2}")

            elif control1 == ConverterControlType.Va_ac:
                if control2 == ConverterControlType.Vm_dc:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        self.is_va_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True

                elif control2 == ConverterControlType.Vm_ac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        self.is_va_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True

                elif control2 == ConverterControlType.Va_ac:
                    self.logger.add_error(
                        f"VSC control1 and control2 are the same for VSC indexed at {k},"
                        f" control1: {control1}, control2: {control2}")

                elif control2 == ConverterControlType.Qac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        self.is_va_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                        pass
                    if control1_branch_device > -1:
                        # self.u_vsc_pf.append(control1_branch_device)
                        # self.u_vsc_pt.append(control1_branch_device)
                        # self.u_vsc_qt.append(control1_branch_device)
                        # self.k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)
                        # self.vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                        pass
                    if control2_branch_device > -1:
                        self.u_vsc_pf.append(control2_branch_device)
                        self.u_vsc_pt.append(control2_branch_device)
                        # self.u_vsc_qt.append(control2_branch_device)

                        # self.k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        self.k_vsc_qt.append(control2_branch_device)

                        # self.vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        self.vsc_qt_set.append(control2_magnitude)

                elif control2 == ConverterControlType.Pdc:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        self.is_va_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                        pass
                    if control1_branch_device > -1:
                        # self.u_vsc_pf.append(control1_branch_device)
                        # self.u_vsc_pt.append(control1_branch_device)
                        # self.u_vsc_qt.append(control1_branch_device)
                        # self.k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)
                        # self.vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                        pass
                    if control2_branch_device > -1:
                        # self.u_vsc_pf.append(control2_branch_device)
                        self.u_vsc_pt.append(control2_branch_device)
                        self.u_vsc_qt.append(control2_branch_device)

                        self.k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)

                        self.vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)

                elif control2 == ConverterControlType.Pac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        self.is_va_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                        pass
                    if control1_branch_device > -1:
                        # self.u_vsc_pf.append(control1_branch_device)
                        # self.u_vsc_pt.append(control1_branch_device)
                        # self.u_vsc_qt.append(control1_branch_device)
                        # self.k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)
                        # self.vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                        pass
                    if control2_branch_device > -1:
                        self.u_vsc_pf.append(control2_branch_device)
                        # self.u_vsc_pt.append(control2_branch_device)
                        self.u_vsc_qt.append(control2_branch_device)

                        # self.k_vsc_pf.append(control2_branch_device)
                        self.k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)

                        # self.vsc_pf_set.append(control2_magnitude)
                        self.vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)

                else:
                    raise Exception(f"Unknown control type {control2}")

            elif control1 == ConverterControlType.Qac:
                if control2 == ConverterControlType.Vm_dc:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                        pass
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                    if control1_branch_device > -1:
                        self.u_vsc_pf.append(control1_branch_device)
                        self.u_vsc_pt.append(control1_branch_device)
                        # self.u_vsc_qt.append(control1_branch_device)

                        # self.k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        self.k_vsc_qt.append(control1_branch_device)

                        # self.vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        self.vsc_qt_set.append(control1_magnitude)
                    if control2_branch_device > -1:
                        # self.u_vsc_pf.append(control2_branch_device)
                        # self.u_vsc_pt.append(control2_branch_device)
                        # self.u_vsc_qt.append(control2_branch_device)
                        # self.k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)
                        # self.vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)
                        pass


                elif control2 == ConverterControlType.Vm_ac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                        pass
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                    if control1_branch_device > -1:
                        self.u_vsc_pf.append(control1_branch_device)
                        self.u_vsc_pt.append(control1_branch_device)
                        # self.u_vsc_qt.append(control1_branch_device)

                        # self.k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        self.k_vsc_qt.append(control1_branch_device)

                        # self.vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        self.vsc_qt_set.append(control1_magnitude)
                    if control2_branch_device > -1:
                        # self.u_vsc_pf.append(control2_branch_device)
                        # self.u_vsc_pt.append(control2_branch_device)
                        # self.u_vsc_qt.append(control2_branch_device)
                        # self.k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)
                        # self.vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)
                        pass

                elif control2 == ConverterControlType.Va_ac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                        pass
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        self.is_va_controlled[control2_bus_device] = True
                    if control1_branch_device > -1:
                        self.u_vsc_pf.append(control1_branch_device)
                        self.u_vsc_pt.append(control1_branch_device)
                        # self.u_vsc_qt.append(control1_branch_device)

                        # self.k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        self.k_vsc_qt.append(control1_branch_device)

                        # self.vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        self.vsc_qt_set.append(control1_magnitude)
                    if control2_branch_device > -1:
                        # self.u_vsc_pf.append(control2_branch_device)
                        # self.u_vsc_pt.append(control2_branch_device)
                        # self.u_vsc_qt.append(control2_branch_device)
                        # self.k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)
                        # self.vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)
                        pass
                elif control2 == ConverterControlType.Qac:
                    self.logger.add_error(
                        f"VSC control1 and control2 are the same for VSC indexed at {k},"
                        f" control1: {control1}, control2: {control2}")
                elif control2 == ConverterControlType.Pdc:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                        pass
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                        pass
                    if control1_branch_device > -1:
                        self.u_vsc_pf.append(control1_branch_device)
                        self.u_vsc_pt.append(control1_branch_device)
                        # self.u_vsc_qt.append(control1_branch_device)

                        # self.k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        self.k_vsc_qt.append(control1_branch_device)

                        # self.vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        self.vsc_qt_set.append(control1_magnitude)
                    if control2_branch_device > -1:
                        # self.u_vsc_pf.append(control2_branch_device)
                        self.u_vsc_pt.append(control2_branch_device)
                        self.u_vsc_qt.append(control2_branch_device)

                        self.k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)

                        self.vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)
                        pass
                elif control2 == ConverterControlType.Pac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                        pass
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                        pass
                    if control1_branch_device > -1:
                        self.u_vsc_pf.append(control1_branch_device)
                        self.u_vsc_pt.append(control1_branch_device)
                        # self.u_vsc_qt.append(control1_branch_device)

                        # self.k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        self.k_vsc_qt.append(control1_branch_device)

                        # self.vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        self.vsc_qt_set.append(control1_magnitude)
                    if control2_branch_device > -1:
                        self.u_vsc_pf.append(control2_branch_device)
                        # self.u_vsc_pt.append(control2_branch_device)
                        self.u_vsc_qt.append(control2_branch_device)

                        # self.k_vsc_pf.append(control2_branch_device)
                        self.k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)

                        # self.vsc_pf_set.append(control2_magnitude)
                        self.vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)
                else:
                    raise Exception(f"Unknown control type {control2}")

            elif control1 == ConverterControlType.Pdc:
                if control2 == ConverterControlType.Vm_dc:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                        pass
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                    if control1_branch_device > -1:
                        # self.u_vsc_pf.append(control1_branch_device)
                        self.u_vsc_pt.append(control1_branch_device)
                        self.u_vsc_qt.append(control1_branch_device)

                        self.k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)

                        self.vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                    if control2_branch_device > -1:
                        # self.u_vsc_pf.append(control2_branch_device)
                        # self.u_vsc_pt.append(control2_branch_device)
                        # self.u_vsc_qt.append(control2_branch_device)
                        # self.k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)
                        # self.vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)
                        pass
                elif control2 == ConverterControlType.Vm_ac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                        pass
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                    if control1_branch_device > -1:
                        # self.u_vsc_pf.append(control1_branch_device)
                        self.u_vsc_pt.append(control1_branch_device)
                        self.u_vsc_qt.append(control1_branch_device)

                        self.k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)

                        self.vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                    if control2_branch_device > -1:
                        # self.u_vsc_pf.append(control2_branch_device)
                        # self.u_vsc_pt.append(control2_branch_device)
                        # self.u_vsc_qt.append(control2_branch_device)
                        # self.k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)
                        # self.vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)
                        pass
                elif control2 == ConverterControlType.Va_ac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                        pass
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        self.is_va_controlled[control2_bus_device] = True
                    if control1_branch_device > -1:
                        # self.u_vsc_pf.append(control1_branch_device)
                        self.u_vsc_pt.append(control1_branch_device)
                        self.u_vsc_qt.append(control1_branch_device)

                        self.k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)

                        self.vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                    if control2_branch_device > -1:
                        # self.u_vsc_pf.append(control2_branch_device)
                        # self.u_vsc_pt.append(control2_branch_device)
                        # self.u_vsc_qt.append(control2_branch_device)
                        # self.k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)
                        # self.vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)
                        pass
                elif control2 == ConverterControlType.Qac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                        pass
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                        pass
                    if control1_branch_device > -1:
                        # self.u_vsc_pf.append(control1_branch_device)
                        self.u_vsc_pt.append(control1_branch_device)
                        self.u_vsc_qt.append(control1_branch_device)

                        self.k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)

                        self.vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                    if control2_branch_device > -1:
                        self.u_vsc_pf.append(control2_branch_device)
                        self.u_vsc_pt.append(control2_branch_device)
                        # self.u_vsc_qt.append(control2_branch_device)

                        # self.k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        self.k_vsc_qt.append(control2_branch_device)

                        # self.vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        self.vsc_qt_set.append(control2_magnitude)

                elif control2 == ConverterControlType.Pdc:
                    self.logger.add_error(
                        f"VSC control1 and control2 are the same for VSC indexed at {k},"
                        f" control1: {control1}, control2: {control2}")
                elif control2 == ConverterControlType.Pac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                        pass
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                        pass
                    if control1_branch_device > -1:
                        # self.u_vsc_pf.append(control1_branch_device)
                        self.u_vsc_pt.append(control1_branch_device)
                        self.u_vsc_qt.append(control1_branch_device)

                        self.k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)

                        self.vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                    if control2_branch_device > -1:
                        self.u_vsc_pf.append(control2_branch_device)
                        # self.u_vsc_pt.append(control2_branch_device)
                        self.u_vsc_qt.append(control2_branch_device)

                        # self.k_vsc_pf.append(control2_branch_device)
                        self.k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)

                        # self.vsc_pf_set.append(control2_magnitude)
                        self.vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)

                else:
                    raise Exception(f"Unknown control type {control2}")

            elif control1 == ConverterControlType.Pac:
                if control2 == ConverterControlType.Vm_dc:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                        pass
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                    if control1_branch_device > -1:
                        self.u_vsc_pf.append(control1_branch_device)
                        # self.u_vsc_pt.append(control1_branch_device)
                        self.u_vsc_qt.append(control1_branch_device)

                        # self.k_vsc_pf.append(control1_branch_device)
                        self.k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)

                        # self.vsc_pf_set.append(control1_magnitude)
                        self.vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                    if control2_branch_device > -1:
                        # self.u_vsc_pf.append(control2_branch_device)
                        # self.u_vsc_pt.append(control2_branch_device)
                        # self.u_vsc_qt.append(control2_branch_device)
                        # self.k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)
                        # self.vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)
                        pass
                elif control2 == ConverterControlType.Vm_ac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                        pass
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                    if control1_branch_device > -1:
                        self.u_vsc_pf.append(control1_branch_device)
                        # self.u_vsc_pt.append(control1_branch_device)
                        self.u_vsc_qt.append(control1_branch_device)

                        # self.k_vsc_pf.append(control1_branch_device)
                        self.k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)

                        # self.vsc_pf_set.append(control1_magnitude)
                        self.vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                    if control2_branch_device > -1:
                        # self.u_vsc_pf.append(control2_branch_device)
                        # self.u_vsc_pt.append(control2_branch_device)
                        # self.u_vsc_qt.append(control2_branch_device)
                        # self.k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)
                        # self.vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)
                        pass
                elif control2 == ConverterControlType.Va_ac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                        pass
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        self.is_va_controlled[control2_bus_device] = True
                    if control1_branch_device > -1:
                        self.u_vsc_pf.append(control1_branch_device)
                        # self.u_vsc_pt.append(control1_branch_device)
                        self.u_vsc_qt.append(control1_branch_device)

                        # self.k_vsc_pf.append(control1_branch_device)
                        self.k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)

                        # self.vsc_pf_set.append(control1_magnitude)
                        self.vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                    if control2_branch_device > -1:
                        # self.u_vsc_pf.append(control2_branch_device)
                        # self.u_vsc_pt.append(control2_branch_device)
                        # self.u_vsc_qt.append(control2_branch_device)
                        # self.k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)
                        # self.vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)
                        pass
                elif control2 == ConverterControlType.Qac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                        pass
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                        pass
                    if control1_branch_device > -1:
                        self.u_vsc_pf.append(control1_branch_device)
                        # self.u_vsc_pt.append(control1_branch_device)
                        self.u_vsc_qt.append(control1_branch_device)

                        # self.k_vsc_pf.append(control1_branch_device)
                        self.k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)

                        # self.vsc_pf_set.append(control1_magnitude)
                        self.vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                    if control2_branch_device > -1:
                        self.u_vsc_pf.append(control2_branch_device)
                        self.u_vsc_pt.append(control2_branch_device)
                        # self.u_vsc_qt.append(control2_branch_device)

                        # self.k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        self.k_vsc_qt.append(control2_branch_device)

                        # self.vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        self.vsc_qt_set.append(control2_magnitude)
                elif control2 == ConverterControlType.Pdc:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                        pass
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                        pass
                    if control1_branch_device > -1:
                        self.u_vsc_pf.append(control1_branch_device)
                        # self.u_vsc_pt.append(control1_branch_device)
                        self.u_vsc_qt.append(control1_branch_device)

                        # self.k_vsc_pf.append(control1_branch_device)
                        self.k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)

                        # self.vsc_pf_set.append(control1_magnitude)
                        self.vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                    if control2_branch_device > -1:
                        self.u_vsc_pf.append(control2_branch_device)
                        # self.u_vsc_pt.append(control2_branch_device)
                        self.u_vsc_qt.append(control2_branch_device)

                        # self.k_vsc_pf.append(control2_branch_device)
                        self.k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)

                        # self.vsc_pf_set.append(control2_magnitude)
                        self.vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)

                elif control2 == ConverterControlType.Pac:
                    self.logger.add_error(
                        f"VSC control1 and control2 are the same for VSC indexed at {k},"
                        f" control1: {control1}, control2: {control2}")
                else:
                    raise Exception(f"Unknown control type {control2}")

            else:
                raise Exception(f"Unknown control type {control1}")
            i += 1

        # convert lists to integer arrays
        self.k_pf_tau = np.array(k_pf_tau, dtype=int)
        self.k_pt_tau = np.array(k_pt_tau, dtype=int)
        self.k_qf_m = np.array(k_qf_m, dtype=int)
        self.k_qt_m = np.array(k_qt_m, dtype=int)
        self.k_qf_beq = np.array(k_qfzero_beq, dtype=int)
        self.k_v_m = np.array(k_v_m, dtype=int)
        self.k_v_beq = np.array(k_v_beq, dtype=int)
        self.k_vsc = np.array(k_vsc, dtype=int)

    def add_branch_control(self,
                           branch_name: str,
                           phase_mode: TapPhaseControl,
                           module_mode: TapModuleControl,
                           branch_idx: int,
                           bus_idx: int,
                           m: float,
                           tap_phase: float,
                           Pset: float,
                           Vm: float,
                           Qset: float,
                           pf_opt: PowerFlowOptions):
        """

        :param branch_name:
        :param phase_mode:
        :param module_mode:
        :param branch_idx:
        :param bus_idx:
        :param m:
        :param tap_phase:
        :param Pset:
        :param Vm:
        :param Qset:
        :param pf_opt: PowerFlowOptions
        :return:
        """

        # def register_controllable_br():
        self.cg_pftr.add(branch_idx)
        self.cg_pttr.add(branch_idx)
        self.cg_qftr.add(branch_idx)
        self.cg_qttr.add(branch_idx)

        # Check the module_mode first
        if module_mode == TapModuleControl.fixed or not pf_opt.control_taps_modules or module_mode == 0:

            # in this case we have to add the tap_phase to the tau set
            self.ck_m.add(branch_idx)
            self.tau_setpoints.append(m)

            if phase_mode == TapPhaseControl.fixed or not pf_opt.control_taps_phase or phase_mode == 0:
                self.ck_tau.add(branch_idx)
                self.tau_setpoints.append(tap_phase)

                # self.cx_m.add(branch_idx)
                self.cx_qfa.add(branch_idx)
                self.cx_qta.add(branch_idx)
                # self.cx_tau.add(branch_idx)
                self.cx_pfa.add(branch_idx)
                self.cx_pta.add(branch_idx)

                # register_controllable_br()

            elif phase_mode == TapPhaseControl.Pf:
                self.ck_pfa.add(branch_idx)
                self.pf_setpoints.append(Pset)

                # self.cx_m.add(branch_idx)
                self.cx_qfa.add(branch_idx)
                self.cx_qta.add(branch_idx)
                self.cx_tau.add(branch_idx)
                # self.cx_pfa.add(branch_idx)
                self.cx_pta.add(branch_idx)

                # register_controllable_br()

            elif phase_mode == TapPhaseControl.Pt:
                self.ck_pta.add(branch_idx)
                self.pt_setpoints.append(Pset)

                # self.cx_m.add(branch_idx)
                self.cx_qfa.add(branch_idx)
                self.cx_qta.add(branch_idx)
                self.cx_tau.add(branch_idx)
                self.cx_pfa.add(branch_idx)
                # self.cx_pta.add(branch_idx)

                # register_controllable_br()
            else:
                raise Exception("Undefined TapPhaseControl")

        elif module_mode == TapModuleControl.Vm:
            self.set_bus_vm_simple(bus_local=bus_idx, device_name=branch_name)
            self.ck_vm.add(bus_idx)
            self.vm_setpoints.append(Vm)

            if phase_mode == TapPhaseControl.fixed or not pf_opt.control_taps_phase or phase_mode == 0:
                # self.ck_m.add(branch_idx)
                # self.m_setpoints.append(tap_phase)

                self.cx_m.add(branch_idx)
                self.cx_qfa.add(branch_idx)
                self.cx_qta.add(branch_idx)
                # self.cx_tau.add(branch_idx)
                self.cx_pfa.add(branch_idx)
                self.cx_pta.add(branch_idx)

                # register_controllable_br()

            elif phase_mode == TapPhaseControl.Pf:
                self.ck_pfa.add(branch_idx)
                self.pf_setpoints.append(Pset)

                # self.cx_m.add(branch_idx)
                self.cx_qfa.add(branch_idx)
                self.cx_qta.add(branch_idx)
                self.cx_tau.add(branch_idx)
                # self.cx_pfa.add(branch_idx)
                self.cx_pta.add(branch_idx)

                # register_controllable_br()

            elif phase_mode == TapPhaseControl.Pt:
                self.ck_pta.add(branch_idx)
                self.pt_setpoints.append(Pset)

                # self.cx_m.add(branch_idx)
                self.cx_qfa.add(branch_idx)
                self.cx_qta.add(branch_idx)
                self.cx_tau.add(branch_idx)
                self.cx_pfa.add(branch_idx)
                # self.cx_pta.add(branch_idx)

                # register_controllable_br()
            else:
                raise Exception("Undefined TapPhaseControl")

        elif module_mode == TapModuleControl.Qf:
            self.ck_qfa.add(branch_idx)
            self.qf_setpoints.append(Qset)

            if phase_mode == TapPhaseControl.fixed or not pf_opt.control_taps_phase or phase_mode == 0:
                self.ck_tau.add(branch_idx)
                self.tau_setpoints.append(tap_phase)

                self.cx_m.add(branch_idx)
                # self.cx_qfa.add(branch_idx)
                self.cx_qta.add(branch_idx)
                # self.cx_tau.add(branch_idx)
                self.cx_pfa.add(branch_idx)
                self.cx_pta.add(branch_idx)

                # register_controllable_br()

            elif phase_mode == TapPhaseControl.Pf:
                self.ck_pfa.add(branch_idx)
                self.pf_setpoints.append(Pset)

                self.cx_m.add(branch_idx)
                # self.cx_qfa.add(branch_idx)
                self.cx_qta.add(branch_idx)
                self.cx_tau.add(branch_idx)
                # self.cx_pfa.add(branch_idx)
                self.cx_pta.add(branch_idx)

                # register_controllable_br()

            elif phase_mode == TapPhaseControl.Pt:
                self.ck_pta.add(branch_idx)
                self.pt_setpoints.append(Pset)

                self.cx_m.add(branch_idx)
                # self.cx_qfa.add(branch_idx)
                self.cx_qta.add(branch_idx)
                self.cx_tau.add(branch_idx)
                self.cx_pfa.add(branch_idx)
                # self.cx_pta.add(branch_idx)

                # register_controllable_br()
            else:
                raise Exception("Undefined TapPhaseControl")

        elif module_mode == TapModuleControl.Qt:
            self.ck_qta.add(branch_idx)
            self.qt_setpoints.append(Qset)

            if phase_mode == TapPhaseControl.fixed or not pf_opt.control_taps_phase or phase_mode == 0:
                self.ck_tau.add(branch_idx)
                self.tau_setpoints.append(tap_phase)

                self.cx_m.add(branch_idx)
                self.cx_qfa.add(branch_idx)
                # self.cx_qta.add(branch_idx)
                # self.cx_tau.add(branch_idx)
                self.cx_pfa.add(branch_idx)
                self.cx_pta.add(branch_idx)

                # register_controllable_br()

            elif phase_mode == TapPhaseControl.Pf:
                self.ck_pfa.add(branch_idx)
                self.pf_setpoints.append(Pset)

                self.cx_m.add(branch_idx)
                self.cx_qfa.add(branch_idx)
                # self.cx_qta.add(branch_idx)
                self.cx_tau.add(branch_idx)
                # self.cx_pfa.add(branch_idx)
                self.cx_pta.add(branch_idx)

                # register_controllable_br()

            elif phase_mode == TapPhaseControl.Pt:
                self.ck_pta.add(branch_idx)
                self.pt_setpoints.append(Pset)

                self.cx_m.add(branch_idx)
                self.cx_qfa.add(branch_idx)
                # self.cx_qta.add(branch_idx)
                self.cx_tau.add(branch_idx)
                self.cx_pfa.add(branch_idx)
                # self.cx_pta.add(branch_idx)

                # register_controllable_br()
            else:
                raise Exception("Undefined TapPhaseControl")

        else:
            raise Exception("Undefined TapModuleControl")

    def add_converter_control(self, vsc_data: VscData, branch_idx: int, ii: int):
        """
        Add controls for a VSC to the appropriate unknown sets based on control types.
        In here, you should only be changing the following five attributes:
         - self.i_u_vm: because a vsc can control the voltage magnitude of a bus
         - self.i_u_va: because a vsc can control the voltage angle of a bus
        - self.i_k_p: because a vsc can control (or rather, not control) the active power of a branch
        - self.i_k_q: because a vsc can control (or rather, not control) the reactive power of a branch
        - self.i_k_q: because a vsc can control (or rather, not control) the reactive power of a branch

        :param branch_idx: branch index
        :param vsc_data: VscData object containing VSC-related data.
        :param ii: Index of the current VSC being processed.
        """

        # Initialize a boolean array for the six control types, defaulting to False
        control_flags = np.zeros(len(ConverterControlType), dtype=bool)

        # Extract control types
        control1_type = vsc_data.control1[ii]
        control2_type = vsc_data.control2[ii]

        # Extract control magnitudes
        magnitude1 = vsc_data.control1_val[ii]
        magnitude2 = vsc_data.control2_val[ii]

        # Set flags for active controls
        for control, control_magnitude in zip([control1_type, control2_type], [magnitude1, magnitude2]):
            try:
                control_index = list(ConverterControlType).index(control)
                control_flags[control_index] = True

                if control == ConverterControlType.Vm_dc:
                    bus_idx = vsc_data.F[ii]
                    self.ck_vm.add(int(bus_idx))
                    self.set_bus_vm_simple(bus_local=int(bus_idx))
                    self.vm_setpoints.append(control_magnitude)
                elif control == ConverterControlType.Vm_ac:
                    bus_idx = vsc_data.T[ii]
                    self.ck_vm.add(int(bus_idx))
                    self.set_bus_vm_simple(bus_local=int(bus_idx))
                    self.vm_setpoints.append(control_magnitude)
                elif control == ConverterControlType.Va_ac:
                    bus_idx = vsc_data.T[ii]
                    self.ck_va.add(int(bus_idx))
                    self.va_setpoints.append(control_magnitude)

                elif control == ConverterControlType.Pac:
                    self.ck_pta.add(int(branch_idx))
                    self.pt_setpoints.append(control_magnitude)

                elif control == ConverterControlType.Qac:
                    self.ck_qta.add(int(branch_idx))
                    self.qt_setpoints.append(control_magnitude)

                elif control == ConverterControlType.Pdc:
                    self.ck_pfa.add(int(branch_idx))
                    self.pf_setpoints.append(control_magnitude)

            except ValueError:
                return  # Skip processing this VSC if control type is invalid

        # Ensure exactly two controls are active
        active_control_count = control_flags.sum()
        assert active_control_count == 2, (  # magic number 2, replace with a constant?
            f"VSC '{vsc_data.names[ii]}' must have exactly two active controls, "
            f"but {active_control_count} were found."
        )

        # Add to unknown sets based on inactive control flags
        for index, is_controlled in enumerate(control_flags):
            control_type = list(ConverterControlType)[index]  # Map index to control type
            if not is_controlled:  # If control is inactive
                if control_type == ConverterControlType.Vm_dc:
                    bus_idx = vsc_data.F[ii]
                    # self.cx_vm.add(bus_idx)
                if control_type == ConverterControlType.Vm_ac:
                    bus_idx = vsc_data.T[ii]
                    # self.cx_vm.add(bus_idx)
                if control_type == ConverterControlType.Va_ac:
                    bus_idx: int = vsc_data.T[ii]
                    # self.cx_va.add(bus_idx)
                if control_type == ConverterControlType.Qac:
                    branch_idx = branch_idx
                    self.cx_qta.add(branch_idx)
                if control_type == ConverterControlType.Pdc:
                    branch_idx = branch_idx
                    self.cx_pfa.add(branch_idx)
                if control_type == ConverterControlType.Pac:
                    branch_idx = branch_idx
                    self.cx_pta.add(branch_idx)
                else:
                    pass

    def rem_bus_qzip_simple(self,
                            bus_idx: int):
        """
        Set the bus index as unspecified (true) for Qzip if slack or bus with controllable gen/batt/shunt
        We remove the index from the set just once if collision
        I think it is the best we can do, otherwise we would need a boolean function and store all the indices

        :param bus_idx:
        """
        self.bus_unspecified_qzip[bus_idx] = True
        if bus_idx in self.cx_qzip:
            self.del_from_cx_qzip(bus_idx)

    def set_bus_qzip_simple(self,
                            bus_idx: int):
        """
        Store the bus index in the Qzip set if no slack or controllable generator/battery/shunt (check bool array)

        :param bus_idx:
        """
        if not self.bus_unspecified_qzip[bus_idx]:
            self.add_to_cx_qzip(bus_idx)

    def set_bus_vm_simple(self,
                          bus_local: int,
                          device_name="",
                          bus_remote: int = -1,
                          remote_control: bool = False,
                          is_slack: bool = False):
        """
        Set the bus control voltage checking incompatibilities
        No point in setting the voltage magnitude, already did in the circuit_to_data

        :param bus_local: Local bus index
        :param device_name: Name to store in the logger
        :param bus_remote: Remote bus index
        :param remote_control: Remote control?
        :param is_slack: Is it a slack bus?
        """

        if is_slack:
            self.bus_vm_pointer_used[bus_local] = True

        else:

            # First check if we are setting a remote bus voltage
            if remote_control and bus_remote > -1 and bus_remote != bus_local:
                if not self.bus_vm_pointer_used[bus_remote]:
                    # initialize the remote bus voltage to the control value
                    self.bus_vm_pointer_used[bus_remote] = True
                    # self.add_to_cx_vm(bus_remote)
                else:
                    self.logger.add_error(msg='Trying to set an already fixed voltage, duplicity of controls',
                                          device=device_name,
                                          device_property='Vm')
            elif remote_control:
                self.logger.add_error(msg='Remote control without a valid remote bus',
                                      device=device_name,
                                      device_property='Vm')

            # Not a remote bus control
            elif not self.bus_vm_pointer_used[bus_local]:
                # initialize the local bus voltage to the control value
                self.bus_vm_pointer_used[bus_local] = True
                # self.add_to_cx_vm(bus_local)
            else:
                self.logger.add_error(msg='Trying to set an already fixed voltage, duplicity of controls',
                                      device=device_name,
                                      device_property='Vm')


    def fill_sets(self,
                    nc: NumericalCircuit,
                    pf_options: PowerFlowOptions) -> "GeneralizedSimulationIndices":
        # nbus = len(nc.bus_data.Vbus)

        # self.bus_vm_pointer_used = np.zeros(nbus, dtype=bool)
        # self.bus_vm_source_used = np.zeros(nbus, dtype=bool)
        # self.bus_unspecified_qzip = np.zeros(nbus, dtype=bool)
        # self.hvdc_mode = np.zeros(len(nc.hvdc_data.active), dtype=bool)

        # DONE
        # -------------- Regular branch search (also applies to trafos) ----------------
        # Ensure VSCs and HVDCs have the flag so that they are not part of this data structure
        # Branches in their most generic sense are stacked as [conventional, VSC, HVDC]
        branch_idx = 0

        for k, _ in enumerate(nc.passive_branch_data.active):
            # if (nc.active_branch_data.tap_phase_control_mode[k] != 0 or
            #         nc.active_branch_data.tap_module_control_mode[k] != 0):
            #     self.add_branch_control(
            #         branch_name=nc.passive_branch_data.names[k],
            #         phase_mode=nc.active_branch_data.tap_phase_control_mode[k],
            #         module_mode=nc.active_branch_data.tap_module_control_mode[k],
            #         branch_idx=k,
            #         bus_idx=nc.active_branch_data.tap_controlled_buses[k],
            #         m=nc.active_branch_data.tap_module[k],
            #         tap_phase=nc.active_branch_data.tap_angle[k],
            #         Pset=nc.active_branch_data.Pset[k],
            #         Vm=nc.active_branch_data.vset[k],
            #         Qset=nc.active_branch_data.Qset[k],
            #         pf_opt=pf_options
            #     )

            branch_idx += 1

        # DONE
        # -------------- VSCs search ----------------
        for ii, _ in enumerate(nc.vsc_data.active):
            self.add_converter_control(nc.vsc_data, branch_idx, ii)
            self.vsc.append(branch_idx)
            branch_idx += 1

        # -------------- HvdcLines search ----------------
        # The Pf equation looks like: Pf = Pset + bool_mode * kdroop * (angle_F - angle_T)
        # The control mode does not change the indices sets, only the equation
        # See how to store this bool_mode
        for iii, _ in enumerate(nc.hvdc_data.active):
            # self.add_to_cx_Pf(branch_idx)

            self.set_bus_vm_simple(bus_local=nc.hvdc_data.F[iii],
                                   device_name=nc.hvdc_data.names[iii])

            self.set_bus_vm_simple(bus_local=nc.hvdc_data.T[iii],
                                   device_name=nc.hvdc_data.names[iii])

            self.add_to_cg_hvdc(branch_idx)

            # 1 if free mode (P as a function of angle drop), 0 if fixed mode (Pset)
            if nc.hvdc_data.control_mode[iii] == HvdcControlType.type_0_free:
                self.hvdc_mode[iii] = 1
            elif nc.hvdc_data.control_mode[iii] == HvdcControlType.type_1_Pset:
                self.hvdc_mode[iii] = 0
            else:
                pass

            self.add_to_cx_qfa(branch_idx)
            self.add_to_cx_qta(branch_idx)
            self.add_to_cx_pfa(branch_idx)
            self.add_to_cx_pta(branch_idx)

            if nc.hvdc_data.Pset[iii] > 0.0:
                self.pf_setpoints.append(nc.hvdc_data.Pset[iii])
                self.pt_setpoints.append(-nc.hvdc_data.Pset[iii])

                self.ck_pfa.add(int(branch_idx))
                self.ck_pta.add(int(branch_idx))

            else:
                self.pf_setpoints.append(-nc.hvdc_data.Pset[iii])
                self.pt_setpoints.append(nc.hvdc_data.Pset[iii])

                self.ck_pfa.add(int(branch_idx))
                self.ck_pta.add(int(branch_idx))

            # Initialize Qs to 0, although they will take whatever value

            branch_idx += 1

        # Post-processing, much needed!
        for i, val in enumerate(self.bus_vm_pointer_used):
            if not val:
                self.add_to_cx_vm(i)

        return self




    def fill_gx_sets(self,
                     nc: NumericalCircuit,
                     pf_options: PowerFlowOptions) -> "GeneralizedSimulationIndices":
        """
        Populate going over the elements, probably harder than the g_sets
        Should we filter for only active elements?
        :param nc: NumericalCircuit
        :param pf_options: PowerFlowOptions
        """
        # nbus = len(nc.bus_data.Vbus)
        #
        # self.bus_vm_pointer_used = np.zeros(nbus, dtype=bool)
        # self.bus_vm_source_used = np.zeros(nbus, dtype=bool)
        # self.bus_unspecified_qzip = np.zeros(nbus, dtype=bool)
        # self.hvdc_mode = np.zeros(len(nc.hvdc_data.active), dtype=bool)
        #
        # # DONE
        # # -------------- Buses search ----------------
        # # Assume they are all set, but probably need some logic when compiling the numerical circuit to
        # # enforce we have one slack on each AC island, split by the VSCs
        #
        # for i, bus_type in enumerate(nc.bus_data.bus_types):
        #     if not (nc.bus_data.is_dc[i]):
        #         self.add_to_cg_pac(i)
        #         self.add_to_cg_qac(i)
        #
        #         if bus_type == BusMode.Slack_tpe.value:
        #             self.add_to_cx_pzip(i)
        #             self.add_to_cx_qzip(i)
        #             self.set_bus_vm_simple(bus_local=i,
        #                                    is_slack=True)
        #         else:
        #             self.add_to_cx_va(i)
        #     else:
        #         self.add_to_cg_pdc(i)
        #
        # # DONE
        # # -------------- Generators and Batteries search ----------------
        # for dev_tpe in (nc.generator_data, nc.battery_data):
        #     for i, is_controlled in enumerate(dev_tpe.controllable):
        #         bus_idx: int = dev_tpe.bus_idx[i]
        #         ctr_bus_idx = dev_tpe.controllable_bus_idx[i]
        #         if dev_tpe.active[i]:
        #             if is_controlled:
        #
        #                 self.set_bus_vm_simple(bus_local=bus_idx,
        #                                        device_name=dev_tpe.names[i],
        #                                        bus_remote=ctr_bus_idx,
        #                                        remote_control=pf_options.control_remote_voltage)
        #
        #                 self.add_to_cx_qzip(bus_idx)
        #                 self.ck_pzip.add(bus_idx)
        #                 self.pzip_setpoints.append(dev_tpe.p[i])
        #
        #             else:
        #                 self.ck_pzip.add(bus_idx)
        #                 self.ck_qzip.add(bus_idx)
        #                 self.pzip_setpoints.append(dev_tpe.p[i])
        #                 self.qzip_setpoints.append(dev_tpe.get_q_at(i))
        #
        # # DONE
        # # -------------- ControlledShunts search ----------------
        # # Setting the Vm has already been done before
        # for i, is_controlled in enumerate(nc.shunt_data.controllable):
        #     bus_idx = nc.shunt_data.bus_idx[i]
        #     ctr_bus_idx = nc.shunt_data.controllable_bus_idx[i]
        #
        #     if is_controlled:
        #         self.set_bus_vm_simple(bus_local=bus_idx,
        #                                device_name=nc.shunt_data.names[i],
        #                                bus_remote=ctr_bus_idx,
        #                                remote_control=pf_options.control_remote_voltage)
        #
        #         self.add_to_cx_qzip(bus_idx)
        #         self.ck_pzip.add(bus_idx)
        #         self.pzip_setpoints.append(dev_tpe.p[i])
        #
        # # DONE
        # # -------------- Regular branch search (also applies to trafos) ----------------
        # # Ensure VSCs and HVDCs have the flag so that they are not part of this data structure
        # # Branches in their most generic sense are stacked as [conventional, VSC, HVDC]
        # # branch_idx = 0
        #
        # for k, _ in enumerate(nc.passive_branch_data.active):
        #     if (nc.active_branch_data.tap_phase_control_mode[k] != 0 or
        #             nc.active_branch_data.tap_module_control_mode[k] != 0):
        #         self.add_branch_control(
        #             branch_name=nc.passive_branch_data.names[k],
        #             phase_mode=nc.active_branch_data.tap_phase_control_mode[k],
        #             module_mode=nc.active_branch_data.tap_module_control_mode[k],
        #             branch_idx=k,
        #             bus_idx=nc.active_branch_data.tap_controlled_buses[k],
        #             m=nc.active_branch_data.tap_module[k],
        #             tap_phase=nc.active_branch_data.tap_angle[k],
        #             Pset=nc.active_branch_data.Pset[k],
        #             Vm=nc.active_branch_data.vset[k],
        #             Qset=nc.active_branch_data.Qset[k],
        #             pf_opt=pf_options
        #         )
        #
        #     # branch_idx += 1
        #
        # # DONE
        # # -------------- VSCs search ----------------
        # branch_idx = len(nc.passive_branch_data.active)
        # for ii, _ in enumerate(nc.vsc_data.active):
        #     self.add_converter_control(nc.vsc_data, branch_idx, ii)
        #     self.add_to_cg_acdc(branch_idx)
        #     branch_idx += 1
        #
        # # -------------- HvdcLines search ----------------
        # # The Pf equation looks like: Pf = Pset + bool_mode * kdroop * (angle_F - angle_T)
        # # The control mode does not change the indices sets, only the equation
        # # See how to store this bool_mode
        # for iii, _ in enumerate(nc.hvdc_data.active):
        #     # self.add_to_cx_Pf(branch_idx)
        #
        #     self.set_bus_vm_simple(bus_local=nc.hvdc_data.F[iii],
        #                            device_name=nc.hvdc_data.names[iii])
        #
        #     self.set_bus_vm_simple(bus_local=nc.hvdc_data.T[iii],
        #                            device_name=nc.hvdc_data.names[iii])
        #
        #     self.add_to_cg_hvdc(branch_idx)
        #
        #     # 1 if free mode (P as a function of angle drop), 0 if fixed mode (Pset)
        #     if nc.hvdc_data.control_mode[iii] == HvdcControlType.type_0_free:
        #         self.hvdc_mode[iii] = 1
        #     elif nc.hvdc_data.control_mode[iii] == HvdcControlType.type_1_Pset:
        #         self.hvdc_mode[iii] = 0
        #     else:
        #         pass
        #
        #     self.add_to_cx_qfa(branch_idx)
        #     self.add_to_cx_qta(branch_idx)
        #     self.add_to_cx_pfa(branch_idx)
        #     self.add_to_cx_pta(branch_idx)
        #
        #     if nc.hvdc_data.Pset[iii] > 0.0:
        #         self.pf_setpoints.append(nc.hvdc_data.Pset[iii])
        #         self.pt_setpoints.append(-nc.hvdc_data.Pset[iii])
        #
        #         self.ck_pfa.add(int(branch_idx))
        #         self.ck_pta.add(int(branch_idx))
        #
        #     else:
        #         self.pf_setpoints.append(-nc.hvdc_data.Pset[iii])
        #         self.pt_setpoints.append(nc.hvdc_data.Pset[iii])
        #
        #         self.ck_pfa.add(int(branch_idx))
        #         self.ck_pta.add(int(branch_idx))
        #
        #     # Initialize Qs to 0, although they will take whatever value
        #
        #     branch_idx += 1
        #
        # # Post-processing, much needed!
        # for i, val in enumerate(self.bus_vm_pointer_used):
        #     if not val:
        #         self.add_to_cx_vm(i)
        #
        # return self

    def sets_to_lists(self) -> None:
        """
        Finalize the sets, converting from sets to lists
        """
        self.cg_pac = list(self.cg_pac)
        self.cg_qac = list(self.cg_qac)
        self.cg_pdc = list(self.cg_pdc)
        self.cg_acdc = list(self.cg_acdc)
        self.cg_hvdc = list(self.cg_hvdc)
        self.cg_pftr = list(self.cg_pftr)
        self.cg_pttr = list(self.cg_pttr)
        self.cg_qftr = list(self.cg_qftr)
        self.cg_qttr = list(self.cg_qttr)

        self.cx_va = list(self.cx_va)
        self.cx_vm = list(self.cx_vm)
        self.cx_tau = list(self.cx_tau)
        self.cx_m = list(self.cx_m)
        self.cx_pzip = list(self.cx_pzip)
        self.cx_qzip = list(self.cx_qzip)
        self.cx_pfa = list(self.cx_pfa)
        self.cx_pta = list(self.cx_pta)
        self.cx_qfa = list(self.cx_qfa)
        self.cx_qta = list(self.cx_qta)

        self.ck_va = list(self.ck_va)
        self.ck_vm = list(self.ck_vm)
        self.ck_tau = list(self.ck_tau)
        self.ck_m = list(self.ck_m)
        self.ck_pzip = list(self.ck_pzip)
        self.ck_qzip = list(self.ck_qzip)
        self.ck_pfa = list(self.ck_pfa)
        self.ck_pta = list(self.ck_pta)
        self.ck_qfa = list(self.ck_qfa)
        self.ck_qta = list(self.ck_qta)
