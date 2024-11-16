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
        Constructor
        Specified sets of indices represent those indices where we know the value of the variable.
        Unspecified sets can be obtained by subtracting the specified sets from the total set of indices.
        Sets can only be of two types: bus indices or branch indices.

        | Device Type     | Specified Sets Involved                         |
        |-----------------|-------------------------------------------------|
        | Slack Buses     | `c_va`, `c_vm`                                  |
        | Generators      | `c_vm`, `c_p_zip`, `c_q_zip`                    |
        | ControlledShunts| `c_vm`                                          |
        | Batteries       | `c_vm`, `c_p_zip`, `c_q_zip`                    |
        | HvdcLines       | `c_vm`, `c_Pf`, `c_hvdc`                        |
        | VSCs            | `c_vm`, `c_Pf`, `c_Pt`, `c_Qf`, `c_Qt`, `c_acdc`|
        | Transformers    | `c_vm`, `c_tau`, `c_m`                          |

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

        # CPzip -> Indices of the buses where the ZIP active power injection are specified.
        # Bus index type
        # (Generators, Batteries)
        self.c_p_zip: Set[int] = set()

        # CQzip -> Indices of the buses where the ZIP reactive power injection are specified.
        # Bus index type
        # (Generators, Batteries) that are not controlling voltage
        self.c_q_zip: Set[int] = set()

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
        # -------------- Slack Buses search ----------------
        # Assume they are all set, but probably need some logic when compiling the numerical circuit to
        # enforce we have one slack on each AC island, split by the VSCs

        for i, bus in enumerate(nc.bus_data[:]):
            if bus.bus_types == BusMode.Slack_tpe.value:
                self.add_to_c_va(i)
                self.set_bus_vm_simple(bus_local=i,
                                       is_slack=True)

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

                    self.add_to_c_p_zip(bus_idx)

                else:
                    self.add_to_c_p_zip(bus_idx)
                    self.add_to_c_q_zip(bus_idx)

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

        # for i, tpe in enumerate(nc.bus_data.bus_types):
        #     if tpe == BusMode.Slack_tpe.value:
        #         self.c_va.add(i)
        #         self.c_vm.add(i)
        #     elif tpe == BusMode.PQ_tpe.value:
        #         pass
        #     elif tpe == BusMode.PV_tpe.value:
        #         self.c_vm.add(i)
        #     elif tpe == BusMode.PQV_tpe.value:
        #         self.c_vm.add(i)
        #     elif tpe == BusMode.P_tpe.value:
        #         pass

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

    def add_to_c_p_zip(self, value: int):
        """

        :param value:
        :return:
        """
        self.c_p_zip.add(value)

    def add_to_c_q_zip(self, value: int):
        """

        :param value:
        :return:
        """
        self.c_q_zip.add(value)

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

    def set_bus_control_voltage(self,
                                i: int,
                                j: int,
                                remote_control: bool,
                                bus_name: str,
                                bus_data: BusData,
                                candidate_Vm: float,
                                use_stored_guess: bool,
                                ) -> None:
        """
        Set the bus control voltage
        :param i: Bus index
        :param j: Remote Bus index
        :param remote_control: Using remote control?
        :param bus_name: Bus name
        :param bus_data: BusData
        :param candidate_Vm: Voltage set point that you want to set
        :param use_stored_guess: Use the stored seed values?
        """

        if bus_data.bus_types[i] != BusMode.Slack_tpe.value:  # if it is not Slack
            if remote_control and j > -1 and j != i:

                # P bus
                self.c_p_zip.add(i)

                # PQV bus
                self.c_vm.add(j)
                self.c_p_zip.add(j)
                self.c_q_zip.add(j)

            else:
                # PV bus
                self.c_vm.add(i)
                self.c_p_zip.add(i)

        if not use_stored_guess:
            if not self.bus_voltage_used[i]:
                if remote_control and j > -1 and j != i:
                    # initialize the remote bus voltage to the control value
                    bus_data.Vbus[j] = complex(candidate_Vm, 0)
                    self.bus_voltage_used[j] = True
                else:
                    # initialize the local bus voltage to the control value
                    bus_data.Vbus[i] = complex(candidate_Vm, 0)
                    self.bus_voltage_used[i] = True

            elif candidate_Vm != bus_data.Vbus[i]:
                self.logger.add_error(msg='Different control voltage set points',
                                      device=bus_name,
                                      value=candidate_Vm,
                                      expected_value=bus_data.Vbus[i])
