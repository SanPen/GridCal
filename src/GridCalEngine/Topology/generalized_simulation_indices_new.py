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
        # self.tap_controlled_buses = nc.active_branch_data.tap_phase_control_mode
        self.tap_phase_control_mode = nc.active_branch_data.tap_phase_control_mode
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
        self.u_cbr_m = np.array(0, dtype=int)
        self.u_cbr_tau = np.array(0, dtype=int)
        self.cbr = np.array(0, dtype=int)
        self.k_cbr_pf = np.array(0, dtype=int)
        self.k_cbr_pt = np.array(0, dtype=int)
        self.k_cbr_qf = np.array(0, dtype=int)
        self.k_cbr_qt = np.array(0, dtype=int)
        self.cbr_pf_set = np.array(0, dtype=float)
        self.cbr_pt_set = np.array(0, dtype=float)
        self.cbr_qf_set = np.array(0, dtype=float)
        self.cbr_qt_set = np.array(0, dtype=float)

        # VSC Indices
        self.vsc = np.array(0, dtype=int)
        self.u_vsc_pf = np.array(0, dtype=int)
        self.u_vsc_pt = np.array(0, dtype=int)
        self.u_vsc_qt = np.array(0, dtype=int)
        self.k_vsc_pf = np.array(0, dtype=int)
        self.k_vsc_pt = np.array(0, dtype=int)
        self.k_vsc_qt = np.array(0, dtype=int)
        self.vsc_pf_set = np.array(0, dtype=float)
        self.vsc_pt_set = np.array(0, dtype=float)
        self.vsc_qt_set = np.array(0, dtype=float)

        # HVDC Indices
        self.hvdc = np.array(0, dtype=int)

        # Analyze Branch controls
        # Controllable Branch Indices
        self.analyze_branch_controls()

        # Check that controlled magnitudes are 2 on average across all buses
        total_controlled_magnitudes = np.sum(
            self.is_p_controlled.astype(int)
            + self.is_q_controlled.astype(int)
            + self.is_vm_controlled.astype(int)
            + self.is_va_controlled.astype(int)
        )
        print("total_controlled_magnitudes", total_controlled_magnitudes)
        print("self.is_p_controlled", self.is_p_controlled)
        print("self.is_q_controlled", self.is_q_controlled)
        print("self.is_vm_controlled", self.is_vm_controlled)
        print("self.is_va_controlled", self.is_va_controlled)
        print("element wise sum",
              self.is_p_controlled.astype(int)
              + self.is_q_controlled.astype(int)
              + self.is_vm_controlled.astype(int)
              + self.is_va_controlled.astype(int)
              )
        assert total_controlled_magnitudes == self.nc.bus_data.nbus * 2, f"Sum of all control flags must be equal to 2 times the number of buses, which is {self.nc.bus_data.nbus * 2}, got {total_controlled_magnitudes}"

        # Ancilliary
        # Source refers to the bus with the controlled device directly connected
        # Pointer refers to the bus where we control the voltage magnitude
        # Unspecified zqip is true if slack or bus with controllable gen/batt/shunt
        # self.bus_vm_source_used: BoolVec | None = None
        self.bus_vm_pointer_used: BoolVec | None = None
        # self.bus_unspecified_qzip: BoolVec | None = None

        # 1 if free mode (P as a function of angle drop), 0 if fixed mode (Pset)
        # self.hvdc_mode: BoolVec | None = None

        # Run the search to get the indices
        # self.fill_gx_sets(nc=nc, pf_options=pf_options)

    def analyze_branch_controls(self) -> None:
        """
        Analyze the control branches and compute the indices
        :return: None
        """
        # Controllable Branch Indices
        u_cbr_m = list()
        u_cbr_tau = list()
        cbr = list()
        k_cbr_pf = list()
        k_cbr_pt = list()
        k_cbr_qf = list()
        k_cbr_qt = list()
        cbr_pf_set = list()
        cbr_pt_set = list()
        cbr_qf_set = list()
        cbr_qt_set = list()

        # VSC Indices
        vsc = list()
        u_vsc_pf = list()
        u_vsc_pt = list()
        u_vsc_qt = list()
        k_vsc_pf = list()
        k_vsc_pt = list()
        k_vsc_qt = list()
        vsc_pf_set = list()
        vsc_pt_set = list()
        vsc_qt_set = list()

        # HVDC Indices
        hvdc = list()

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
                # self.is_p_controlled[bus_idx] = True
                # self.is_q_controlled[bus_idx] = True
                self.is_vm_controlled[bus_idx] = True
                # self.is_va_controlled[bus_idx] = True
                u_cbr_m.append(k)

            elif ctrl_m == TapModuleControl.Qf:
                u_cbr_m.append(k)
                k_cbr_qf.append(k)
                cbr_qf_set.append(self.nc.active_branch_data.Qset[k])


            elif ctrl_m == TapModuleControl.Qt:
                u_cbr_m.append(k)
                k_cbr_qt.append(k)
                cbr_qt_set.append(self.nc.active_branch_data.Qset[k])

            elif ctrl_m == TapModuleControl.fixed:
                pass

            elif ctrl_m == 0:
                pass

            else:
                raise Exception(f"Unknown tap phase module mode {ctrl_m}")

            # analyze tap-phase controls
            if ctrl_tau == TapPhaseControl.Pf:
                u_cbr_tau.append(k)
                k_cbr_pf.append(k)
                cbr_pf_set.append(self.nc.active_branch_data.Pset[k])

            elif ctrl_tau == TapPhaseControl.Pt:
                u_cbr_tau.append(k)
                k_cbr_pt.append(k)
                cbr_pt_set.append(self.nc.active_branch_data.Pset[k])

            elif ctrl_tau == TapPhaseControl.fixed:
                pass

            elif ctrl_tau == 0:
                pass

            else:
                raise Exception(f"Unknown tap phase control mode {ctrl_tau}")
            i += 1

        # VSC LOOP
        for k in range(self.nc.vsc_data.nelm):
            vsc.append(i)
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
                        u_vsc_pf.append(control2_branch_device)
                        u_vsc_pt.append(control2_branch_device)
                        # self.u_vsc_qt.append(control2_branch_device)

                        # self.k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        k_vsc_qt.append(control2_branch_device)

                        # self.vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        vsc_qt_set.append(control2_magnitude)

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
                        u_vsc_pt.append(control2_branch_device)
                        u_vsc_qt.append(control2_branch_device)

                        k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)

                        vsc_pf_set.append(control2_magnitude)
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
                        u_vsc_pf.append(control2_branch_device)
                        # self.u_vsc_pt.append(control2_branch_device)
                        u_vsc_qt.append(control2_branch_device)

                        # self.k_vsc_pf.append(control2_branch_device)
                        k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)

                        # self.vsc_pf_set.append(control2_magnitude)
                        vsc_pt_set.append(control2_magnitude)
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
                        u_vsc_pf.append(control2_branch_device)
                        u_vsc_pt.append(control2_branch_device)
                        # self.u_vsc_qt.append(control2_branch_device)

                        # self.k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        k_vsc_qt.append(control2_branch_device)

                        # self.vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        vsc_qt_set.append(control2_magnitude)

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
                        u_vsc_pt.append(control2_branch_device)
                        u_vsc_qt.append(control2_branch_device)

                        k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)

                        vsc_pf_set.append(control2_magnitude)
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
                        u_vsc_pf.append(control2_branch_device)
                        # self.u_vsc_pt.append(control2_branch_device)
                        u_vsc_qt.append(control2_branch_device)

                        # self.k_vsc_pf.append(control2_branch_device)
                        k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)

                        # self.vsc_pf_set.append(control2_magnitude)
                        vsc_pt_set.append(control2_magnitude)
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
                        u_vsc_pf.append(control2_branch_device)
                        u_vsc_pt.append(control2_branch_device)
                        # self.u_vsc_qt.append(control2_branch_device)

                        # self.k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        k_vsc_qt.append(control2_branch_device)

                        # self.vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        vsc_qt_set.append(control2_magnitude)

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
                        u_vsc_pt.append(control2_branch_device)
                        u_vsc_qt.append(control2_branch_device)

                        k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)

                        vsc_pf_set.append(control2_magnitude)
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
                        u_vsc_pf.append(control2_branch_device)
                        # self.u_vsc_pt.append(control2_branch_device)
                        u_vsc_qt.append(control2_branch_device)

                        # self.k_vsc_pf.append(control2_branch_device)
                        k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)

                        # self.vsc_pf_set.append(control2_magnitude)
                        vsc_pt_set.append(control2_magnitude)
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
                        u_vsc_pf.append(control1_branch_device)
                        u_vsc_pt.append(control1_branch_device)
                        # self.u_vsc_qt.append(control1_branch_device)

                        # self.k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        k_vsc_qt.append(control1_branch_device)

                        # self.vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        vsc_qt_set.append(control1_magnitude)
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
                        u_vsc_pf.append(control1_branch_device)
                        u_vsc_pt.append(control1_branch_device)
                        # self.u_vsc_qt.append(control1_branch_device)

                        # self.k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        k_vsc_qt.append(control1_branch_device)

                        # self.vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        vsc_qt_set.append(control1_magnitude)
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
                        u_vsc_pf.append(control1_branch_device)
                        u_vsc_pt.append(control1_branch_device)
                        # self.u_vsc_qt.append(control1_branch_device)

                        # self.k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        k_vsc_qt.append(control1_branch_device)

                        # self.vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        vsc_qt_set.append(control1_magnitude)
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
                        u_vsc_pf.append(control1_branch_device)
                        u_vsc_pt.append(control1_branch_device)
                        # self.u_vsc_qt.append(control1_branch_device)

                        # self.k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        k_vsc_qt.append(control1_branch_device)

                        # self.vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        vsc_qt_set.append(control1_magnitude)
                    if control2_branch_device > -1:
                        # self.u_vsc_pf.append(control2_branch_device)
                        u_vsc_pt.append(control2_branch_device)
                        u_vsc_qt.append(control2_branch_device)

                        k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)

                        vsc_pf_set.append(control2_magnitude)
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
                        u_vsc_pf.append(control1_branch_device)
                        u_vsc_pt.append(control1_branch_device)
                        # self.u_vsc_qt.append(control1_branch_device)

                        # self.k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        k_vsc_qt.append(control1_branch_device)

                        # self.vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        vsc_qt_set.append(control1_magnitude)
                    if control2_branch_device > -1:
                        u_vsc_pf.append(control2_branch_device)
                        # self.u_vsc_pt.append(control2_branch_device)
                        u_vsc_qt.append(control2_branch_device)

                        # self.k_vsc_pf.append(control2_branch_device)
                        k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)

                        # self.vsc_pf_set.append(control2_magnitude)
                        vsc_pt_set.append(control2_magnitude)
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
                        u_vsc_pt.append(control1_branch_device)
                        u_vsc_qt.append(control1_branch_device)

                        k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)

                        vsc_pf_set.append(control1_magnitude)
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
                        u_vsc_pt.append(control1_branch_device)
                        u_vsc_qt.append(control1_branch_device)

                        k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)

                        vsc_pf_set.append(control1_magnitude)
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
                        u_vsc_pt.append(control1_branch_device)
                        u_vsc_qt.append(control1_branch_device)

                        k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)

                        vsc_pf_set.append(control1_magnitude)
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
                        u_vsc_pt.append(control1_branch_device)
                        u_vsc_qt.append(control1_branch_device)

                        k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)

                        vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                    if control2_branch_device > -1:
                        u_vsc_pf.append(control2_branch_device)
                        u_vsc_pt.append(control2_branch_device)
                        # self.u_vsc_qt.append(control2_branch_device)

                        # self.k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        k_vsc_qt.append(control2_branch_device)

                        # self.vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        vsc_qt_set.append(control2_magnitude)

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
                        u_vsc_pt.append(control1_branch_device)
                        u_vsc_qt.append(control1_branch_device)

                        k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)

                        vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                    if control2_branch_device > -1:
                        u_vsc_pf.append(control2_branch_device)
                        # self.u_vsc_pt.append(control2_branch_device)
                        u_vsc_qt.append(control2_branch_device)

                        # self.k_vsc_pf.append(control2_branch_device)
                        k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)

                        # self.vsc_pf_set.append(control2_magnitude)
                        vsc_pt_set.append(control2_magnitude)
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
                        u_vsc_pf.append(control1_branch_device)
                        # self.u_vsc_pt.append(control1_branch_device)
                        u_vsc_qt.append(control1_branch_device)

                        # self.k_vsc_pf.append(control1_branch_device)
                        k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)

                        # self.vsc_pf_set.append(control1_magnitude)
                        vsc_pt_set.append(control1_magnitude)
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
                        u_vsc_pf.append(control1_branch_device)
                        # self.u_vsc_pt.append(control1_branch_device)
                        u_vsc_qt.append(control1_branch_device)

                        # self.k_vsc_pf.append(control1_branch_device)
                        k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)

                        # self.vsc_pf_set.append(control1_magnitude)
                        vsc_pt_set.append(control1_magnitude)
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
                        u_vsc_pf.append(control1_branch_device)
                        # self.u_vsc_pt.append(control1_branch_device)
                        u_vsc_qt.append(control1_branch_device)

                        # self.k_vsc_pf.append(control1_branch_device)
                        k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)

                        # self.vsc_pf_set.append(control1_magnitude)
                        vsc_pt_set.append(control1_magnitude)
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
                        u_vsc_pf.append(control1_branch_device)
                        # self.u_vsc_pt.append(control1_branch_device)
                        u_vsc_qt.append(control1_branch_device)

                        # self.k_vsc_pf.append(control1_branch_device)
                        k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)

                        # self.vsc_pf_set.append(control1_magnitude)
                        vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                    if control2_branch_device > -1:
                        u_vsc_pf.append(control2_branch_device)
                        u_vsc_pt.append(control2_branch_device)
                        # self.u_vsc_qt.append(control2_branch_device)

                        # self.k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        k_vsc_qt.append(control2_branch_device)

                        # self.vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        vsc_qt_set.append(control2_magnitude)
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
                        u_vsc_pf.append(control1_branch_device)
                        # self.u_vsc_pt.append(control1_branch_device)
                        u_vsc_qt.append(control1_branch_device)

                        # self.k_vsc_pf.append(control1_branch_device)
                        k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)

                        # self.vsc_pf_set.append(control1_magnitude)
                        vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                    if control2_branch_device > -1:
                        u_vsc_pf.append(control2_branch_device)
                        # self.u_vsc_pt.append(control2_branch_device)
                        u_vsc_qt.append(control2_branch_device)

                        # self.k_vsc_pf.append(control2_branch_device)
                        k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)

                        # self.vsc_pf_set.append(control2_magnitude)
                        vsc_pt_set.append(control2_magnitude)
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

        # HVDC LOOP
        for k in range(self.nc.hvdc_data.nelm):
            hvdc.append(k)
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

        self.u_cbr_m = np.array(u_cbr_m, dtype=int)
        self.u_cbr_tau = np.array(u_cbr_tau, dtype=int)
        self.cbr = np.array(cbr, dtype=int)
        self.k_cbr_pf = np.array(k_cbr_pf, dtype=int)
        self.k_cbr_pt = np.array(k_cbr_pt, dtype=int)
        self.k_cbr_qf = np.array(k_cbr_qf, dtype=int)
        self.k_cbr_qt = np.array(k_cbr_qt, dtype=int)
        self.cbr_pf_set = np.array(cbr_pf_set, dtype=float)
        self.cbr_pt_set = np.array(cbr_pt_set, dtype=float)
        self.cbr_qf_set = np.array(cbr_qf_set, dtype=float)
        self.cbr_qt_set = np.array(cbr_qt_set, dtype=float)

        self.vsc = np.array(vsc, dtype=int)
        self.u_vsc_pf = np.array(u_vsc_pf, dtype=int)
        self.u_vsc_pt = np.array(u_vsc_pt, dtype=int)
        self.u_vsc_qt = np.array(u_vsc_qt, dtype=int)
        self.k_vsc_pf = np.array(k_vsc_pf, dtype=int)
        self.k_vsc_pt = np.array(k_vsc_pt, dtype=int)
        self.k_vsc_qt = np.array(k_vsc_qt, dtype=int)
        self.vsc_pf_set = np.array(vsc_pf_set, dtype=float)
        self.vsc_pt_set = np.array(vsc_pt_set, dtype=float)
        self.vsc_qt_set = np.array(vsc_qt_set, dtype=float)

        self.hvdc = np.array(hvdc, dtype=int)

