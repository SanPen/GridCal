# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0


from typing import Set
import numpy as np
from GridCalEngine.enumerations import TapPhaseControl, TapModuleControl, BusMode, HvdcControlType
from GridCalEngine.DataStructures.bus_data import BusData
from GridCalEngine.DataStructures.branch_data import BranchData
from GridCalEngine.DataStructures.vsc_data import VscData
from GridCalEngine.DataStructures.hvdc_data import HvdcData
from GridCalEngine.DataStructures.generator_data import GeneratorData
from GridCalEngine.DataStructures.battery_data import BatteryData
from GridCalEngine.DataStructures.shunt_data import ShuntData
from GridCalEngine.basic_structures import Logger, BoolVec


class GeneralizedSimulationIndices:
    """
    GeneralizedSimulationIndices
    """

    def __init__(self,
                 bus_data,
                 generator_data,
                 battery_data, 
                 shunt_data,
                 branch_data,
                 vsc_data,
                 hvdc_data) -> "GeneralizedSimulationIndices":
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

        :param bus_data:
        :param generator_data:
        :param battery_data:
        :param shunt_data:
        :param branch_data:
        :param vsc_data:
        :param hvdc_data:

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
        self.cx_va: Set[int] = set()  # All slack buses
        self.cx_vm: Set[int] = set()  # All slack buses, controlled generators/batteries/shunts, HVDC lines, VSCs, transformers 
        self.cx_tau: Set[int] = set()  # All controllable transformers that do not use the tap phase control mode
        self.cx_m: Set[int] = set()  # All controllable transformers that do not use the tap module control mode
        self.cx_pzip: Set[int] = set()  # All buses unless slack
        self.cx_qzip: Set[int] = set()  # All buses minus slack and uncontrollable generators/batteries/shunts
        self.cx_pfa: Set[int] = set()  # VSCs controlling Pf, transformers controlling Pf
        self.cx_pta: Set[int] = set()  # VSCs controlling Pt, transformers controlling Pt
        self.cx_qfa: Set[int] = set()  # VSCs controlling Qf, transformers controlling Qf
        self.cx_qta: Set[int] = set()  # VSCs controlling Qt, transformers controlling Qt

        # Ancilliary
        # Source refers to the bus with the controlled device directly connected 
        # Pointer refers to the bus where we control the voltage magnitude 
        # Unspecified zqip is true if slack or bus with controllable gen/batt/shunt
        self.bus_vm_source_used: BoolVec | None = None
        self.bus_vm_pointer_used: BoolVec | None = None
        self.bus_unspecified_qzip: BoolVec | None = None

        self.logger = Logger()

        # Run the search to get the indices
        self.fill_gx_sets(bus_data=bus_data,
                          generator_data=generator_data,
                          battery_data=battery_data,
                          shunt_data=shunt_data,
                          branch_data=branch_data,
                          vsc_data=vsc_data,
                          hvdc_data=hvdc_data)

        # Negate the cx sets to show the unknowns
        self.negate_cx(nbus=len(bus_data.active),
                       nbr=len(branch_data.active) + len(vsc_data.active) + len(hvdc_data.active))

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
                               branch_idx: int = None,
                               is_conventional: bool = True):
        """
        :param branch_idx:
        :param mode:
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
                # To circument this, we assume a fixed converter sets the Qt
                self.add_to_cx_qta(branch_idx)
                self.logger.add_warning(msg='Fixed mode for VSCs can be problematic in a generalized power flow',
                                        device=branch_name,
                                        value=mode,
                                        device_property=TapPhaseControl,
                                        device_class=VscData)

            elif mode == TapPhaseControl.Pf:
                self.add_to_cx_pfa(branch_idx)
            elif mode == TapPhaseControl.Pt:
                self.add_to_cx_pta(branch_idx)
        else:
            # Handle conventional conditions (regular transformers)
            if mode == TapPhaseControl.fixed:
                self.add_to_cx_tau(branch_idx)
            elif mode == TapPhaseControl.Pf:
                self.add_to_cg_pftr(branch_idx)
                self.add_to_cx_pfa(branch_idx)
            elif mode == TapPhaseControl.Pt:
                self.add_to_cg_pttr(branch_idx)
                self.add_to_cx_pta(branch_idx)
            else:
                pass

    def add_m_control_branch(self,
                             branch_name: str = "",
                             mode: TapModuleControl = TapModuleControl.fixed,
                             branch_idx: int = None,
                             bus_idx: int = None,
                             is_conventional: bool = True):

        """
        :param branch_name:
        :param mode:
        :param branch_idx:
        :param bus_idx:
        :param is_conventional: True of transformers and all branches, False for VSCs
        :return:
        """
        # Check the mode first
        if mode == TapModuleControl.fixed:
            if not is_conventional:
                # NOTE: in principle, VSCs must have two controls
                # However, if fixed mode, the system will become unsolvable 
                # FUBM adds the Beq zero equation but it is not really what we want
                # To circument this, we assume a fixed converter sets the Qt
                self.add_to_cx_qta(branch_idx)
                self.logger.add_warning(msg='Fixed mode for VSCs can be problematic in a generalized power flow',
                                        device=branch_name,
                                        value=mode,
                                        device_property=VscData.tap_module_control_mode,
                                        device_class=VscData)
            else:
                self.add_to_cx_m(branch_idx)

        elif mode == TapModuleControl.Vm:
            self.set_bus_vm_simple(bus_local=bus_idx, device_name=branch_name)

        elif mode in (TapModuleControl.Qf, TapModuleControl.Qt):
            if is_conventional:
                # If conventional, add to both cx_q* and cg_q*
                if mode == TapModuleControl.Qf:
                    self.add_to_cx_qfa(branch_idx)
                    self.add_to_cg_qftr(branch_idx)
                else:  # TapModuleControl.Qt
                    self.add_to_cx_qta(branch_idx)
                    self.add_to_cg_qttr(branch_idx)
            else:
                # If not conventional, add only to cx_q*
                if mode == TapModuleControl.Qf:
                    self.add_to_cx_qfa(branch_idx)
                else:  # TapModuleControl.Qt
                    self.add_to_cx_qta(branch_idx)
        else:
            pass

    def add_generator_behaviour(self, bus_idx: int, is_v_controlled: bool):
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
            self.add_to_cx_vm(bus_local)
            self.bus_vm_pointer_used[bus_local] = True

        else:
            # First check if we are setting a remote bus voltage
            if remote_control and bus_remote > -1 and bus_remote != bus_local:
                if not self.bus_vm_pointer_used[bus_remote]:
                    # initialize the remote bus voltage to the control value
                    self.bus_vm_pointer_used[bus_remote] = True
                    self.add_to_cx_vm(bus_remote)
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
                self.add_to_cx_vm(bus_local)
            else:
                self.logger.add_error(msg='Trying to set an already fixed voltage, duplicity of controls',
                                      device=device_name,
                                      device_property='Vm')

    def fill_gx_sets(self, 
                     bus_data: BusData,
                     generator_data: GeneratorData,
                     battery_data: BatteryData,
                     shunt_data: ShuntData,
                     branch_data: BranchData,
                     vsc_data: VscData,
                     hvdc_data: HvdcData) -> "GeneralizedSimulationIndices":
        """
        Populate going over the elements, probably harder than the g_sets
        Should we filter for only active elements?

        :param bus_data:
        :param generator_data:
        :param battery_data:
        :param shunt_data:
        :param branch_data:
        :param vsc_data:
        :param hvdc_data:
        """
        nbus = len(bus_data.Vbus)

        self.bus_vm_pointer_used = np.zeros(nbus, dtype=bool)
        self.bus_vm_source_used = np.zeros(nbus, dtype=bool)
        self.bus_unspecified_qzip = np.zeros(nbus, dtype=bool)

        # DONE
        # -------------- Buses search ----------------
        # Assume they are all set, but probably need some logic when compiling the numerical circuit to
        # enforce we have one slack on each AC island, split by the VSCs

        for i, bus_type in enumerate(bus_data.bus_types):
            if not(bus_data.is_dc[i]):
                self.add_to_cg_pac(i)
                self.add_to_cg_qac(i)

                if bus_type == BusMode.Slack_tpe.value:
                    self.add_to_cx_va(i)
                    self.rem_bus_qzip_simple(i)
                    self.set_bus_vm_simple(bus_local=i,
                                           is_slack=True)
                else:
                    self.add_to_cx_pzip(i)
                    self.set_bus_qzip_simple(i)
            else:
                self.add_to_cg_pdc(i)
                self.add_to_cx_pzip(i)

        # DONE
        # -------------- Generators and Batteries search ----------------
        for dev_tpe in (generator_data, battery_data):
            for i, is_controlled in enumerate(dev_tpe.controllable):
                bus_idx = dev_tpe.bus_idx[i]
                ctr_bus_idx = dev_tpe.controllable_bus_idx[i]

                if is_controlled:
                    remote_control = ctr_bus_idx != -1

                    self.set_bus_vm_simple(bus_local=bus_idx,
                                           device_name=dev_tpe.names[i],
                                           bus_remote=ctr_bus_idx,
                                           remote_control=remote_control)
                    
                    self.rem_bus_qzip_simple(bus_idx)

        # DONE
        # -------------- ControlledShunts search ----------------
        # Setting the Vm has already been done before
        for i, is_controlled in enumerate(shunt_data.controllable):
            bus_idx = shunt_data.bus_idx[i]
            ctr_bus_idx = shunt_data.controllable_bus_idx[i]

            if is_controlled:
                remote_control = ctr_bus_idx != -1

                self.set_bus_vm_simple(bus_local=bus_idx,
                                       device_name = shunt_data.names[i],
                                       bus_remote=ctr_bus_idx,
                                       remote_control=remote_control)

                self.rem_bus_qzip_simple(bus_idx)

        # DONE
        # -------------- Regular branch search (also applies to trafos) ----------------
        # Ensure VSCs and HVDCs have the flag so that they are not part of this data structure
        # Branches in their most generic sense are stacked as [conventional, VSC, HVDC]
        branch_idx = 0

        for i, _ in enumerate(branch_data.active):

            self.add_tau_control_branch(branch_name=branch_data.names[i],
                                        mode=branch_data.tap_phase_control_mode[i],
                                        branch_idx=branch_idx,
                                        is_conventional=True)

            bus_idx = branch_data.tap_controlled_buses[i]

            self.add_m_control_branch(branch_name=branch_data.names[i],
                                      mode=branch_data.tap_module_control_mode[i],
                                      branch_idx=branch_idx,
                                      bus_idx=bus_idx,
                                      is_conventional=True)

            branch_idx += 1

        # DONE
        # -------------- VSCs search ----------------
        for ii, _ in enumerate(vsc_data.active):

            self.add_tau_control_branch(branch_name=vsc_data.names[ii],
                                        mode=vsc_data.tap_phase_control_mode[ii],
                                        branch_idx=branch_idx,
                                        is_conventional=False)

            bus_idx = vsc_data.tap_controlled_buses[ii]

            self.add_m_control_branch(branch_name=vsc_data.names[ii],
                                      mode=vsc_data.tap_module_control_mode[ii],
                                      branch_idx=branch_idx,
                                      bus_idx=bus_idx,
                                      is_conventional=False)

            self.add_to_cg_acdc(branch_idx)

            branch_idx += 1

        # DONE
        # -------------- HvdcLines search ----------------
        # The Pf equation looks like: Pf = Pset + bool_mode * kdroop * (angle_F - angle_T)
        # The control mode does not change the indices sets, only the equation
        # See how to store this bool_mode
        for iii, _ in enumerate(hvdc_data.active):

            self.add_to_cx_Pf(branch_idx)

            self.set_bus_vm_simple(bus_local=hvdc_data.F[iii],
                                   device_name=hvdc_data.names[iii])

            self.set_bus_vm_simple(bus_local=hvdc_data.T[iii],
                                   device_name=hvdc_data.names[iii])

            self.add_to_cg_hvdc(branch_idx)

            branch_idx += 1

        return self
    
    def negate_cx(self, nbus: int, nbr: int):
        """
        Negate the cx sets to display the unknowns, not the knowns
        :param nbus:
        :param nbr:
        """
        # Precompute the full sets of bus and branch indices
        full_bus_set = set(range(nbus))
        full_branch_set = set(range(nbr))

        # Subtract existing sets from the full sets
        self.cx_va = full_bus_set - self.cx_va
        self.cx_vm = full_bus_set - self.cx_vm
        self.cx_pzip = full_bus_set - self.cx_pzip
        self.cx_qzip = full_bus_set - self.cx_qzip

        self.cx_tau = full_branch_set - self.cx_tau
        self.cx_m = full_branch_set - self.cx_m
        self.cx_pfa = full_branch_set - self.cx_pfa
        self.cx_pta = full_branch_set - self.cx_pta
        self.cx_qfa = full_branch_set - self.cx_qfa
        self.cx_qta = full_branch_set - self.cx_qta
    
    def sets_to_lists(self):
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
        

    # def fill_x_sets(self, nc: NumericalCircuit) -> "GeneralizedSimulationIndices":
    #     """
    #     Populate going over the elements, probably harder than the g_sets
    #     Better to have a single method to fill sets, this way we avoid double searches

    #     :param nc:
    #     :return:
    #     """

    #     return self
