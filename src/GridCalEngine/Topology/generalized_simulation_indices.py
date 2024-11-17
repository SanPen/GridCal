from typing import Set, Union
import numpy as np
from GridCalEngine.enumerations import TapPhaseControl, TapModuleControl, BusMode, HvdcControlType
from GridCalEngine.DataStructures.numerical_circuit import NumericalCircuit
from GridCalEngine.DataStructures.bus_data import BusData
from GridCalEngine.basic_structures import Logger, Vec, IntVec, BoolVec


class GeneralizedSimulationIndices:
    """
    GeneralizedSimulationIndices
    """

    def __init__(self) -> None:
        """
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
        - Pzip: store all bus indices except for the slack ones (sort of ~bus_data[:].is_slack)
        - Qzip: store the bus indices of devices acting as controllable injections (generators, batteries, controlled shunts)
                then run Pzip - bus_vm_source_used to get the Qzip set
        - Vm: store the indices of already controlled buses, raising an error if we try to set the same bus twice, stopping the program there

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
        self.cx_vm: Set[int] = set()  # All slack buses, generators, controlled shunts, batteries, HVDC lines, VSCs, transformers 
        self.cx_tau: Set[int] = set()  # All controllable transformers that do not use the tap phase control mode
        self.cx_m: Set[int] = set()  # All controllable transformers that do not use the tap module control mode
        self.cx_pzip: Set[int] = set()  # All generators, all batteries, all loads
        self.cx_qzip: Set[int] = set()  # Non-controllable generators, non-controllable batteries, all loads
        self.cx_pta: Set[int] = set()  # VSCs controlling Pt, transformers controlling Pt
        self.cx_qfa: Set[int] = set()  # VSCs controlling Qf, transformers controlling Qf
        self.cx_qta: Set[int] = set()  # VSCs controlling Qt, transformers controlling Qt

        # Source refers to the bus with the controlled device directly connected 
        # Pointer refers to the bus where we control the voltage magnitude 
        self.bus_vm_source_used: BoolVec | None = None
        self.bus_vm_pointer_used: BoolVec | None = None

        self.logger = Logger()

    def fill_g_sets(self, nc: NumericalCircuit) -> "GeneralizedSimulationIndices":
        """
        Fill the residuals sets by going over each device

        :param nc: numerical circuit
        :return:
        """
        self.bus_vm_pointer_used = np.zeros(nc.nbus, dtype=bool)
        self.bus_vm_source_used = np.zeros(nc.nbus, dtype=bool)

        # DONE
        # -------------- Buses search ----------------
        # Assume they are all set, but probably need some logic when compiling the numerical circuit to
        # enforce we have one slack on each AC island, split by the VSCs

        for i, bus in enumerate(nc.bus_data[:]):
            if not(bus.is_dc):
                self.add_to_c_pac(i)
                self.add_to_c_qac(i)

                if bus.bus_types == BusMode.Slack_tpe.value:
                    self.add_to_c_va(i)
                    self.set_bus_vm_simple(bus_local=i,
                                        is_slack=True)
            else:
                self.add_to_c_pdc(i)

        # DONE
        # -------------- Generators and Batteries search ----------------
        for dev_tpe in (nc.generator_data, nc.battery_data):
            for i, is_controlled in enumerate(dev_tpe.controllable):
                bus_idx = dev_tpe.bus_idx[i]
                ctr_bus_idx = dev_tpe.controllable_bus_idx[i]

                if is_controlled:
                    remote_control = ctr_bus_idx != -1

                    self.set_bus_vm_simple(bus_local=bus_idx,
                                           device_name=dev_tpe.names[i],
                                           bus_remote=ctr_bus_idx,
                                           remote_control=remote_control)

                    self.add_to_c_pac(bus_idx)

                else:
                    self.add_to_c_pac(bus_idx)
                    self.add_to_c_qac(bus_idx)

        # DONE
        # -------------- ControlledShunts search ----------------
        # Setting the Vm has already been done before
        for i, is_controlled in enumerate(nc.shunt_data.controllable):
            bus_idx = nc.shunt_data.bus_idx[i]
            ctr_bus_idx = nc.shunt_data.controllable_bus_idx[i]

            if is_controlled:
                remote_control = ctr_bus_idx != -1

                self.set_bus_vm_simple(bus_local=bus_idx,
                                       device_name = nc.shunt_data.names[i],
                                       bus_remote=ctr_bus_idx,
                                       remote_control=remote_control)

        # DONE
        # -------------- HvdcLines search ----------------
        # The Pf equation looks like: Pf = Pset + bool_mode * kdroop * (angle_F - angle_T)
        # The control mode does not change the indices sets, only the equation
        # See how to store this bool_mode
        for i, hvdc_dev in enumerate(nc.hvdc_data[:]):

            branch_idx = 0  # quick fix
            self.add_to_c_Pf(branch_idx)

            self.add_to_c_hvdc(branch_idx)

            self.set_bus_vm_simple(bus_local=hvdc_dev.F,
                                   device_name=hvdc_dev.name)

            self.set_bus_vm_simple(bus_local=hvdc_dev.T,
                                   device_name=hvdc_dev.name)

        # DONE
        # -------------- VSCs search ----------------
        for i, vsc_dev in enumerate(nc.vsc_data[:]):

            self.add_tau_control_branch(mode=vsc_dev.tap_phase_control_mode,
                                        branch_idx=branch_idx)

            self.add_m_control_branch(branch_name=vsc_dev.name,
                                      mode=vsc_dev.tap_module_control_mode,
                                      branch_idx=branch_idx,
                                      bus_idx=bus_idx)

            self.add_to_c_acdc(branch_idx)

        # DONE
        # -------------- Transformers search (also applies to windings) ----------------
        for i, trafo_dev in enumerate(nc.transformer_data[:]):

            self.add_tau_control_branch(mode=trafo_dev.tap_phase_control_mode,
                                        branch_idx=branch_idx)

            self.add_m_control_branch(branch_name=trafo_dev.name,
                                      mode=trafo_dev.tap_module_control_mode,
                                      branch_idx=branch_idx,
                                      bus_idx=bus_idx)

        return self

    def fill_x_sets(self, nc: NumericalCircuit) -> "GeneralizedSimulationIndices":
        """
        Populate going over the elements, probably harder than the g_sets
        Better to have a single method to fill sets, this way we avoid double searches

        :param nc:
        :return:
        """

        return self


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
                               mode: TapPhaseControl = TapPhaseControl.fixed,
                               branch_idx: int = None):
        """

        :param mode:
        :param branch_idx:
        :return:
        """
        if mode == TapPhaseControl.fixed:
            self.add_to_c_tau(branch_idx)

        elif mode == TapPhaseControl.Pf:
            self.add_to_c_Pf(branch_idx)

        elif mode == TapPhaseControl.Pt:
            self.add_to_c_Pt(branch_idx)

        else:
            pass

    def add_m_control_branch(self,
                             branch_name: str = "",
                             mode: TapModuleControl = TapModuleControl.fixed,
                             branch_idx: int = None,
                             bus_idx: int = None):

        """
        :param branch_name:
        :param mode:
        :param branch_idx:
        :param bus_idx:
        :return:
        """
        if mode == TapModuleControl.fixed:
            # May get an error eventually with VSCs
            self.add_to_c_m(branch_idx)

        elif mode == TapModuleControl.Vm:
            self.set_bus_vm_simple(bus_local=bus_idx,
                                   device_name=branch_name)

        elif mode == TapModuleControl.Qf:
            self.add_to_c_Qf(branch_idx)

        elif mode == TapModuleControl.Qt:
            self.add_to_c_Qt(branch_idx)

        else:
            pass

    def add_generator_behaviour(self, bus_idx: int, is_v_controlled: bool):
        pass

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
            self.add_to_c_vm(bus_local)
            self.bus_vm_pointer_used[bus_local] = True

        else:
            # First check if we are setting a remote bus voltage
            if remote_control and bus_remote > -1 and bus_remote != bus_local:
                if not self.bus_vm_pointer_used[bus_remote]:
                    # initialize the remote bus voltage to the control value
                    self.bus_vm_pointer_used[bus_remote] = True
                    self.add_to_c_vm(bus_remote)
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
                self.add_to_c_vm(bus_local)
            else:
                self.logger.add_error(msg='Trying to set an already fixed voltage, duplicity of controls',
                                      device=device_name,
                                      device_property='Vm')
