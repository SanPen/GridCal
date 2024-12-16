# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0


from typing import Set
import numpy as np
from GridCalEngine.enumerations import (TapPhaseControl, TapModuleControl, BusMode, HvdcControlType,
                                        ConverterControlType)
from GridCalEngine.DataStructures.numerical_circuit import NumericalCircuit
from GridCalEngine.DataStructures.vsc_data import VscData
from GridCalEngine.basic_structures import Logger, BoolVec


class GeneralizedSimulationIndices:
    """
    GeneralizedSimulationIndices
    """

    def __init__(self,
                 nc: NumericalCircuit) -> None:
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

        """

        # cg sets
        self.cg_pac: Set[int] = set()  # All AC buses (AC P balance)
        self.cg_qac: Set[int] = set()  # All AC buses (AC Q balance)
        self.cg_pdc: Set[int] = set()  # All DC buses (DC P balance)
        self.cg_acdc: Set[int] = set()  # All VSCs (loss equation)
        self.cg_hvdc: Set[int] = set()  # All HVDC lines (loss equation + control equation)
        self.cg_pftr: Set[int] = set()  # All controllable transformers
        self.cg_pttr: Set[int] = set()  # All controllable transformers
        self.cg_qftr: Set[int] = set()  # All controllable transformers
        self.cg_qttr: Set[int] = set()  # All controllable transformers

        # cx sets

        # All AC minus slack buses
        self.cx_va: Set[int] = set()

        # All minus slack buses, controlled generators/batteries/shunts, HVDC lines, VSCs, transformers
        self.cx_vm: Set[int] = set()

        self.cx_tau: Set[int] = set()  # All controllable transformers that do not use the tap phase control mode
        self.cx_m: Set[int] = set()  # All controllable transformers that do not use the tap module control mode
        self.cx_pzip: Set[int] = set()  # Slack buses
        self.cx_qzip: Set[int] = set()  # Slack buses and those AC with uncontrollable generators/batteries/shunts
        self.cx_pfa: Set[int] = set()  # VSCs controlling Pf, transformers controlling Pf
        self.cx_pta: Set[int] = set()  # VSCs controlling Pt, transformers controlling Pt
        self.cx_qfa: Set[int] = set()  # ONLY transformers controlling Qf
        self.cx_qta: Set[int] = set()  # VSCs controlling Qt, transformers controlling Qt

        # ck sets (the complements of the cx sets)
        # NOTE: implement them as lists, otherwise messed up order with setpoints lists
        self.ck_va = []
        self.ck_vm = []
        self.ck_tau = []
        self.ck_m = []
        self.ck_pzip = []
        self.ck_qzip = []
        self.ck_pfa = []
        self.ck_qfa = []
        self.ck_pta = []
        self.ck_qta = []
        # self.ck_va: Set[int] = set()
        # self.ck_vm: Set[int] = set()
        # self.ck_tau: Set[int] = set()
        # self.ck_m: Set[int] = set()
        # self.ck_pzip: Set[int] = set()
        # self.ck_qzip: Set[int] = set()
        # self.ck_pfa: Set[int] = set()
        # self.ck_pta: Set[int] = set()
        # self.ck_qfa: Set[int] = set()
        # self.ck_qta: Set[int] = set()

        # setpoints that correspond to the ck sets, P and Q in MW
        self.va_setpoints = []
        self.vm_setpoints = []
        self.tau_setpoints = []
        self.m_setpoints = []
        self.pzip_setpoints = []
        self.qzip_setpoints = []
        self.pf_setpoints = []
        self.pt_setpoints = []
        self.qf_setpoints = []
        self.qt_setpoints = []

        # Ancilliary
        # Source refers to the bus with the controlled device directly connected 
        # Pointer refers to the bus where we control the voltage magnitude 
        # Unspecified zqip is true if slack or bus with controllable gen/batt/shunt
        self.bus_vm_source_used: BoolVec | None = None
        self.bus_vm_pointer_used: BoolVec | None = None
        self.bus_va_source_used: BoolVec | None = None
        self.bus_va_pointer_used: BoolVec | None = None
        self.bus_unspecified_qzip: BoolVec | None = None

        # 1 if free mode (P as a function of angle drop), 0 if fixed mode (Pset)
        self.hvdc_mode: BoolVec | None = None

        self.logger = Logger()

        # Run the search to get the indices
        self.fill_gx_sets(nc=nc)

        # Finally convert to sets
        self.sets_to_lists()

    # Primitive additions
    # Methods for cg sets
    def add_to_cg_pac(self, value: int):
        """
        Add a value to the cg_pac set.
        
        :param value:
        :return: None
        """
        self.cg_pac.add(value)

    def add_to_cg_qac(self, value: int):
        """
        Add a value to the cg_qac set.
        
        :param value:
        :return: None
        """
        self.cg_qac.add(value)

    def add_to_cg_pdc(self, value: int):
        """
        Add a value to the cg_pdc set.
        
        :param value:
        :return: None
        """
        self.cg_pdc.add(value)

    def add_to_cg_acdc(self, value: int):
        """
        Add a value to the cg_acdc set.
        
        :param value:
        :return: None
        """
        self.cg_acdc.add(value)

    def add_to_cg_hvdc(self, value: int):
        """
        Add a value to the cg_hvdc set.
        
        :param value:
        :return: None
        """
        self.cg_hvdc.add(value)

    def add_to_cg_pftr(self, value: int):
        """
        Add a value to the cg_pftr set.
        
        :param value:
        :return: None
        """
        self.cg_pftr.add(value)

    def add_to_cg_pttr(self, value: int):
        """
        Add a value to the cg_pttr set.
        
        :param value:
        :return: None
        """
        self.cg_pttr.add(value)

    def add_to_cg_qftr(self, value: int):
        """
        Add a value to the cg_qftr set.
        
        :param value:
        :return: None
        """
        self.cg_qftr.add(value)

    def add_to_cg_qttr(self, value: int):
        """
        Add a value to the cg_qttr set.
        
        :param value:
        :return: None
        """
        self.cg_qttr.add(value)

    # Methods for cx sets
    def add_to_cx_va(self, value: int):
        """
        Add a value to the cx_va set.
        
        :param value:
        :return: None
        """
        self.cx_va.add(value)

    def add_to_cx_vm(self, value: int):
        """
        Add a value to the cx_vm set.
        
        :param value:
        :return: None
        """
        self.cx_vm.add(value)

    def add_to_cx_tau(self, value: int):
        """
        Add a value to the cx_tau set.
        
        :param value:
        :return: None
        """
        self.cx_tau.add(value)

    def add_to_cx_m(self, value: int):
        """
        Add a value to the cx_m set.
        
        :param value:
        :return: None
        """
        self.cx_m.add(value)

    def add_to_cx_pzip(self, value: int):
        """
        Add a value to the cx_pzip set.
        
        :param value:
        :return: None
        """
        self.cx_pzip.add(value)

    def add_to_cx_qzip(self, value: int):
        """
        Add a value to the cx_qzip set.
        
        :param value:
        :return: None
        """
        self.cx_qzip.add(value)

    def del_from_cx_qzip(self, value: int):
        """
        Remove a value of the cx_qzip set.
        
        :param value:
        :return: None
        """
        self.cx_qzip.remove(value)

    def add_to_cx_pfa(self, value: int):
        """
        Add a value to the cx_pfa set.
        
        :param value:
        :return: None
        """
        self.cx_pfa.add(value)

    def add_to_cx_pta(self, value: int):
        """
        Add a value to the cx_pta set.
        
        :param value:
        :return: None
        """
        self.cx_pta.add(value)

    def add_to_cx_qfa(self, value: int):
        """
        Add a value to the cx_qfa set.
        
        :param value:
        :return: None
        """
        self.cx_qfa.add(value)

    def add_to_cx_qta(self, value: int):
        """
        Add a value to the cx_qta set.
        
        :param value:
        :return: None
        """
        self.cx_qta.add(value)

    # Non-primitive additions
    def add_tau_control_branch(self,
                               branch_name: str = "",
                               mode: TapPhaseControl = TapPhaseControl.fixed,
                               tap_phase: float = 0.0,
                               Pset: float = 0.0,
                               branch_idx: int = None,
                               is_conventional: bool = True,
                               ):
        """

        :param branch_name:
        :param branch_idx:
        :param mode:
        :param tap_phase:
        :param Pset:
        :param branch_idx:
        :param is_conventional: True of transformers and all branches, False for VSCs
        :return:
        """
        # Check for non-conventional conditions first
        if not is_conventional:
            if mode == TapPhaseControl.fixed:
                # NOTE: in principle, VSCs must have two controls
                # However, if fixed mode, the system will become unsolvable 
                # FUBM adds the Beq zero equation but it is not really what we want
                # To circument this, can we assume a fixed converter sets the Qt?
                # The risk is if the other degree of freedom controls Qt also, check for that

                self.add_to_cg_qttr(branch_idx)  # NOTE: quick fix for now

                self.add_to_cx_pfa(branch_idx)
                self.add_to_cx_pta(branch_idx)

                self.logger.add_warning(msg='Fixed mode for VSCs can be problematic in a generalized power flow',
                                        device=branch_name,
                                        value=mode,
                                        device_property=TapPhaseControl,
                                        device_class=VscData)

            elif mode == TapPhaseControl.Pf:
                self.add_to_cx_pta(branch_idx)
            elif mode == TapPhaseControl.Pt:
                self.add_to_cx_pfa(branch_idx)
        else:
            # Handle conventional conditions (regular transformers)
            if mode == TapPhaseControl.fixed:
                self.ck_tau.append(branch_idx)
                self.tau_setpoints.append(tap_phase)
            elif mode == TapPhaseControl.Pf:
                self.ck_pfa.append(branch_idx)
                self.pf_setpoints.append(Pset)
            elif mode == TapPhaseControl.Pt:
                self.ck_pta.append(branch_idx)
                self.pt_setpoints.append(Pset)
            else:
                pass

    def add_m_control_branch(self,
                             branch_name: str = "",
                             mode: TapModuleControl = TapModuleControl.fixed,
                             branch_idx: int = None,
                             bus_idx: int = None,
                             is_conventional: bool = True,
                             Vm: float = 1.0,
                             Qset: float = 0.0,
                             m: float = 1.0,
                             ):

        """
        :param branch_name:
        :param mode:
        :param branch_idx:
        :param bus_idx:
        :param is_conventional: True of transformers and all branches, False for VSCs
        :param Vm:
        :param Qset:
        :param m:
        :return:
        """

        # Check the mode first
        if mode == TapModuleControl.fixed:
            if not is_conventional:
                # NOTE: in principle, VSCs must have two controls
                # However, if fixed mode, the system will become unsolvable 
                # FUBM adds the Beq zero equation but it is not really what we want
                # To circument this, we need an additional equation
                # We can assume a fixed converter sets the Qt and should remove this Qt from cx, for example

                self.add_to_cg_qttr(branch_idx)  # NOTE: quick fix for now

                self.logger.add_warning(msg='Fixed mode for VSCs can be problematic in a generalized power flow',
                                        device=branch_name,
                                        value=mode,
                                        device_property="VscData.tap_module_control_mode",
                                        device_class="VscData")
            else:
                # in this case we have to add the tap_phase to the tau set
                self.ck_m.append(branch_idx)
                self.m_setpoints.append(m)

        elif mode == TapModuleControl.Vm:
            self.set_bus_vm_simple(bus_local=bus_idx, device_name=branch_name)
            if is_conventional:
                self.ck_vm.append(bus_idx)
                self.vm_setpoints.append(Vm)

            if not is_conventional:
                self.add_to_cx_qta(branch_idx)

        elif mode in (TapModuleControl.Qf, TapModuleControl.Qt):
            if is_conventional:
                # If conventional, add
                if mode == TapModuleControl.Qf:
                    self.ck_qfa.append(branch_idx)
                    self.qf_setpoints.append(Qset)

                else:  # TapModuleControl.Qt
                    self.ck_qta.append(branch_idx)
                    self.qt_setpoints.append(Qset)
            else:
                # If not conventional, add only to cx_q*
                if mode == TapModuleControl.Qf:
                    self.add_to_cx_qta(branch_idx)
                else:  # TapModuleControl.Qt
                    pass  # no point in the DC side
                    # self.add_to_cx_qfa(branch_idx)
        else:
            pass

    def add_converter_control(self, vsc_data: VscData, branch_idx: int, ii: int):
        """
        Add controls for a VSC to the appropriate unknown sets based on control types.

        :param branch_idx: branch index
        :param vsc_data: VscData object containing VSC-related data.
        :param ii: Index of the current VSC being processed.
        :param Sbase:
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
                    self.ck_vm.append(int(bus_idx))
                    self.set_bus_vm_simple(bus_local=int(bus_idx))
                    self.vm_setpoints.append(control_magnitude)
                elif control == ConverterControlType.Vm_ac:
                    bus_idx = vsc_data.T[ii]
                    self.ck_vm.append(int(bus_idx))
                    self.set_bus_vm_simple(bus_local=int(bus_idx))
                    self.vm_setpoints.append(control_magnitude)
                elif control == ConverterControlType.Va_ac:
                    bus_idx = vsc_data.T[ii]
                    self.ck_va.append(int(bus_idx))
                    self.set_bus_va_simple(bus_local=int(bus_idx))
                    self.va_setpoints.append(control_magnitude)

                elif control == ConverterControlType.Pac:
                    self.ck_pta.append(int(branch_idx))
                    self.pt_setpoints.append(control_magnitude)

                elif control == ConverterControlType.Qac:
                    self.ck_qta.append(int(branch_idx))
                    self.qt_setpoints.append(control_magnitude)

                elif control == ConverterControlType.Pdc:
                    self.ck_pfa.append(int(branch_idx))
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
            # self.add_to_cx_vm(bus_local)
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

    def set_bus_va_simple(self,
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
            # self.add_to_cx_vm(bus_local)
            self.bus_va_pointer_used[bus_local] = True

        else:
            # First check if we are setting a remote bus voltage
            if remote_control and bus_remote > -1 and bus_remote != bus_local:
                if not self.bus_va_pointer_used[bus_remote]:
                    # initialize the remote bus voltage to the control value
                    self.bus_va_pointer_used[bus_remote] = True
                    # self.add_to_cx_vm(bus_remote)
                else:
                    self.logger.add_error(msg='Trying to set an already fixed voltage angle, duplicity of controls',
                                          device=device_name,
                                          device_property='Va')
            elif remote_control:
                self.logger.add_error(msg='Remote control without a valid remote bus',
                                      device=device_name,
                                      device_property='Va')

            # Not a remote bus control
            elif not self.bus_va_pointer_used[bus_local]:
                # initialize the local bus voltage to the control value
                self.bus_va_pointer_used[bus_local] = True
                # self.add_to_cx_vm(bus_local)
            else:
                self.logger.add_error(msg='Trying to set an already fixed voltage angle, duplicity of controls',
                                      device=device_name,
                                      device_property='Va')

    def fill_gx_sets(self,
                     nc: NumericalCircuit) -> "GeneralizedSimulationIndices":
        """
        Populate going over the elements, probably harder than the g_sets
        Should we filter for only active elements?
        :param nc: NumericalCircuit
        """
        nbus = len(nc.bus_data.Vbus)

        self.bus_vm_pointer_used = np.zeros(nbus, dtype=bool)
        self.bus_vm_source_used = np.zeros(nbus, dtype=bool)
        self.bus_va_pointer_used = np.zeros(nbus, dtype=bool)
        self.bus_va_source_used = np.zeros(nbus, dtype=bool)
        self.bus_unspecified_qzip = np.zeros(nbus, dtype=bool)
        self.hvdc_mode = np.zeros(len(nc.hvdc_data.active), dtype=bool)

        # DONE
        # -------------- Buses search ----------------
        # Assume they are all set, but probably need some logic when compiling the numerical circuit to
        # enforce we have one slack on each AC island, split by the VSCs

        for i, bus_type in enumerate(nc.bus_data.bus_types):
            if not (nc.bus_data.is_dc[i]):
                self.add_to_cg_pac(i)
                self.add_to_cg_qac(i)

                if bus_type == BusMode.Slack_tpe.value:
                    self.add_to_cx_pzip(i)
                    self.add_to_cx_qzip(i)

                    self.set_bus_vm_simple(bus_local=i,
                                           is_slack=True)
                    # It will be the generator at this bus the one to specify it
                    # self.ck_vm.append(i)
                    # self.vm_setpoints.append(abs(nc.bus_data.Vbus[i]))
                    # As it is not well done, avoid setting the setpoint here

                    self.set_bus_va_simple(bus_local=i,
                                           is_slack=True)
                    self.ck_va.append(i)
                    self.va_setpoints.append(np.angle(nc.bus_data.Vbus[i]))
                else:
                    pass
                    # self.add_to_cx_va(i)
            else:
                self.add_to_cg_pdc(i)

        # DONE
        # -------------- Generators and Batteries search ----------------
        for dev_tpe in (nc.generator_data, nc.battery_data):
            for i, is_controlled in enumerate(dev_tpe.controllable):
                bus_idx: int = dev_tpe.bus_idx[i]
                ctr_bus_idx = dev_tpe.controllable_bus_idx[i]
                if dev_tpe.active[i]:
                    if is_controlled:
                        remote_control = ctr_bus_idx != -1

                        self.set_bus_vm_simple(bus_local=bus_idx,
                                               device_name=dev_tpe.names[i],
                                               bus_remote=ctr_bus_idx,
                                               remote_control=remote_control)
                        self.ck_vm.append(bus_idx)
                        self.vm_setpoints.append(dev_tpe.v[i])

                        self.add_to_cx_qzip(bus_idx)
                        self.ck_pzip.append(bus_idx)
                        self.pzip_setpoints.append(dev_tpe.p[i])

                    else:
                        self.ck_pzip.append(bus_idx)
                        self.ck_qzip.append(bus_idx)
                        self.pzip_setpoints.append(dev_tpe.p[i] / nc.Sbase)
                        self.qzip_setpoints.append(dev_tpe.get_q_at(i))

        # DONE
        # -------------- ControlledShunts search ----------------
        # Setting the Vm has already been done before
        for i, is_controlled in enumerate(nc.shunt_data.controllable):
            bus_idx = nc.shunt_data.bus_idx[i]
            ctr_bus_idx = nc.shunt_data.controllable_bus_idx[i]

            if is_controlled:
                remote_control = ctr_bus_idx != -1

                self.set_bus_vm_simple(bus_local=bus_idx,
                                       device_name=nc.shunt_data.names[i],
                                       bus_remote=ctr_bus_idx,
                                       remote_control=remote_control)

                self.ck_vm.append(bus_idx)
                self.vm_setpoints.append(nc.shunt_data.vset[i])

                self.add_to_cx_qzip(bus_idx)

                self.ck_pzip.append(bus_idx)
                self.pzip_setpoints.append(dev_tpe.p[i])

        # DONE
        # -------------- Regular branch search (also applies to trafos) ----------------
        # Ensure VSCs and HVDCs have the flag so that they are not part of this data structure
        # Branches in their most generic sense are stacked as [conventional, VSC, HVDC]
        branch_idx = 0

        for i, _ in enumerate(nc.passive_branch_data.active):
            self.add_tau_control_branch(branch_name=nc.passive_branch_data.names[i],
                                        mode=nc.active_branch_data.tap_phase_control_mode[i],
                                        tap_phase=nc.active_branch_data.tap_angle[i],
                                        Pset=nc.active_branch_data.Pset[i],
                                        branch_idx=branch_idx,
                                        is_conventional=True,
                                        )

            bus_idx: int = nc.active_branch_data.tap_controlled_buses[i]

            self.add_m_control_branch(branch_name=nc.passive_branch_data.names[i],
                                      mode=nc.active_branch_data.tap_module_control_mode[i],
                                      branch_idx=branch_idx,
                                      bus_idx=bus_idx,
                                      is_conventional=True,
                                      Vm=nc.active_branch_data.vset[i],
                                      Qset=nc.active_branch_data.Qset[i],
                                      m=nc.active_branch_data.tap_module[i],
                                      )

            # Here we start to throw stuff into the unknown sets. previously we were simply putting known sets and setpoints
            mode1 = nc.active_branch_data.tap_module_control_mode[i]
            mode2 = nc.active_branch_data.tap_phase_control_mode[i]

            if mode1 != 0 or mode2 != 0:
                if mode2 == 0:
                    mode2 = TapPhaseControl.fixed
                # Initialize control flags
                module_control_flags = np.zeros(len(TapModuleControl), dtype=bool)
                phase_control_flags = np.zeros(len(TapPhaseControl), dtype=bool)
                # Set flags for active controls
                module_control_flags[list(TapModuleControl).index(mode1)] = True
                phase_control_flags[list(TapPhaseControl).index(mode2)] = True

                # assert that exactly one control in each flag list
                assert module_control_flags.sum() == 1, "Exactly one module control should be active"
                assert phase_control_flags.sum() == 1, "Exactly one phase control should be active"

                # Add to unknown sets based on inactive control flags
                for index, is_controlled in enumerate(module_control_flags):
                    control_type = list(TapModuleControl)[index]
                    if not is_controlled:
                        if control_type == TapModuleControl.fixed:
                            self.cx_m.add(branch_idx)
                        elif control_type == TapModuleControl.Qf:
                            self.cx_qfa.add(branch_idx)
                        elif control_type == TapModuleControl.Qt:
                            self.cx_qta.add(branch_idx)

                for index, is_controlled in enumerate(phase_control_flags):
                    control_type = list(TapPhaseControl)[index]
                    if not is_controlled:
                        if control_type == TapPhaseControl.fixed:
                            self.cx_tau.add(branch_idx)
                        elif control_type == TapPhaseControl.Pf:
                            self.cx_pfa.add(branch_idx)
                        elif control_type == TapPhaseControl.Pt:
                            self.cx_pta.add(branch_idx)

                self.cg_pftr.add(branch_idx)
                self.cg_pttr.add(branch_idx)
                self.cg_qftr.add(branch_idx)
                self.cg_qttr.add(branch_idx)

            branch_idx += 1

        # DONE
        # -------------- VSCs search ----------------
        for ii, _ in enumerate(nc.vsc_data.active):
            self.add_converter_control(nc.vsc_data, branch_idx, ii)
            self.add_to_cg_acdc(branch_idx)
            branch_idx += 1

        # DONE -- This is a bit tricky, seems to add some unwanted indices into our sets
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

                self.ck_pfa.append(int(branch_idx))
                self.ck_pta.append(int(branch_idx))

            else:
                self.pf_setpoints.append(-nc.hvdc_data.Pset[iii])
                self.pt_setpoints.append(nc.hvdc_data.Pset[iii])

                self.ck_pfa.append(int(branch_idx))
                self.ck_pta.append(int(branch_idx))

            # Initialize Qs to 0, although they will take whatever value

            branch_idx += 1

        # Post-processing, much needed!
        for i, val in enumerate(self.bus_vm_pointer_used):
            if not val:
                self.add_to_cx_vm(i)

        for i, val in enumerate(self.bus_va_pointer_used):
            if not val and not nc.bus_data.is_dc[i]:
                self.add_to_cx_va(i)

        return self

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
