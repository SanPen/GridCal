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
                then run Pzip - controllable_bus_injections
        - Vm: store the indices of already controlled buses, raising an error if we try to set the same bus twice, stopping the program there

        Idea: should we use sets instead of lists? Much more efficient for the intersection and difference operations maybe?
        """
        # CVa -> Indices of the buses where the voltage angles are specified.
        # Bus index type
        # (Slack buses)
        self.c_va: Set[int] = set()

        # CVm -> Indices of the buses where the voltage modules are specified.
        # Bus index type
        # (Slack buses, Generators, ControlledShunts, Batteries, HvdcLines, VSCs, Transformers)
        self.c_vm: Set[int] = set()

        # Cτ -> Indices of the controllable branches where the phase shift angles are specified.
        # Branch index type
        # (Transformers)
        self.c_tau: Set[int] = set()

        # Cm -> Indices of the controllable branches where the tap ratios are specified.
        # Branch index type
        # (Transformers)
        self.c_m: Set[int] = set()

        # CPac -> Indices of the buses where the ZIP active power injection are specified.
        # Bus index type
        # (AC buses)
        self.c_pac: Set[int] = set()

        # CQac -> Indices of the buses where the ZIP reactive power injection are specified.
        # Bus index type
        # (AC buses)
        self.c_qac: Set[int] = set()

        # CPdc -> Indices of the buses where the P active power injection is specified.
        # Bus index type
        # (DC buses)
        self.c_pdc: Set[int] = set()

        # CPf -> Indices of branches where Pf is specified.
        # Branch index type
        # (VSCs, HvdcLines)
        self.c_Pf: Set[int] = set()

        # CPt -> Indices of branches where Pt is specified.
        # Branch index type
        # (VSCs)
        self.c_Pt: Set[int] = set()

        # CQf -> Indices of branches where Qf is specified.
        # Branch index type
        # (VSCs)
        self.c_Qf: Set[int] = set()

        # CQt -> Indices of branches where Qt is specified.
        # Branch index type
        # (VSCs)
        self.c_Qt: Set[int] = set()

        # Cacdc -> Indices of branches with loss equations for AC/DC VSCs.
        # Branch index type
        # (VSCs)
        self.c_acdc: Set[int] = set()

        # Chvdc -> Indices of branches with loss equations for HVDC lines.
        # Branch index type
        # (HvdcLines)
        self.c_hvdc: Set[int] = set()

        # -----------------------
        # Check if this is really needed
        # CInjP -> Indices of the injection devices where the P is specified.
        self.c_inj_P: Set[int] = set()

        # CInjQ -> Indices of the injection devices where the Q is specified.
        self.c_inj_Q: Set[int] = set()

        self.logger = Logger()

        self.bus_voltage_used: BoolVec | None = None

    def fill_specified(self, nc: NumericalCircuit):
        """
        Fill the specified sets by going over each device
        Possible duplicity of controls in setting Vm; we check for this and raise an error if so
        This function will eventually be removed, we have to move it inside the circuit_to_data

        :param nc: numerical circuit
        :return:
        """
        self.bus_voltage_used = np.zeros(nc.nbus, dtype=bool)

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

    def fill_unspecified(self, nc: NumericalCircuit) -> "GeneralizedSimulationIndices":
        """
        Redo, just negate the specified I guess
        For this counting the total of buses and branches would come in handy
        :param nc:
        :return:
        """

        return self

    # Primitive additions
    def add_to_c_va(self, value: int):
        """

        :param value:
        :return:
        """
        self.c_va.add(value)

    def add_to_c_vm(self, value: int):
        """

        :param value:
        :return:
        """
        self.c_vm.add(value)

    def add_to_c_tau(self, value: int):
        """

        :param value:
        :return:
        """
        self.c_tau.add(value)

    def add_to_c_m(self, value: int):
        """

        :param value:
        :return:
        """
        self.c_m.add(value)

    def add_to_c_pac(self, value: int):
        """

        :param value:
        :return:
        """
        self.c_pac.add(value)

    def add_to_c_qac(self, value: int):
        """

        :param value:
        :return:
        """
        self.c_qac.add(value)

    def add_to_c_pdc(self, value: int):
        """

        :param value:
        :return:
        """
        self.c_pdc.add(value)

    def add_to_c_Pf(self, value: int):
        """

        :param value:
        :return:
        """
        self.c_Pf.add(value)

    def add_to_c_Pt(self, value: int):
        """

        :param value:
        :return:
        """
        self.c_Pt.add(value)

    def add_to_c_Qf(self, value: int):
        """

        :param value:
        :return:
        """
        self.c_Qf.add(value)

    def add_to_c_Qt(self, value: int):
        """

        :param value:
        :return:
        """
        self.c_Qt.add(value)

    def add_to_c_inj_P(self, value: int):
        """

        :param value:
        """
        self.c_inj_P.add(value)

    def add_to_c_inj_Q(self, value: int):
        """

        :param value:
        """
        self.c_inj_Q.add(value)

    def add_to_c_acdc(self, value: int):
        """

        :param value:
        """
        self.c_acdc.add(value)

    def add_to_c_hvdc(self, value: int):
        """

        :param value:
        """
        self.c_hvdc.add(value)

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
            self.bus_voltage_used[bus_local] = True

        else:
            # First check if we are setting a remote bus voltage
            if remote_control and bus_remote > -1 and bus_remote != bus_local:
                if not self.bus_voltage_used[bus_remote]:
                    # initialize the remote bus voltage to the control value
                    self.bus_voltage_used[bus_remote] = True
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
            elif not self.bus_voltage_used[bus_local]:
                # initialize the local bus voltage to the control value
                self.bus_voltage_used[bus_local] = True
                self.add_to_c_vm(bus_local)
            else:
                self.logger.add_error(msg='Trying to set an already fixed voltage, duplicity of controls',
                                      device=device_name,
                                      device_property='Vm')
