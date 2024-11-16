from typing import Set, Union
import numpy as np
from GridCalEngine.enumerations import TapPhaseControl, TapModuleControl, BusMode
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

    def fill_specified(self, nc: NumericalCircuit,
                       use_stored_guess: bool = False,
                       control_remote_voltage: bool = True) -> "GeneralizedSimulationIndices":
        """
        Fill the specified sets by going over each device
        Possible duplicity of controls in setting Vm; we check for this and raise an error if so

        :param nc: numerical circuit
        :param use_stored_guess:
        :param control_remote_voltage: true if controlling a remote bus
        :return:
        """
        self.bus_voltage_used = np.zeros(nc.nbus, dtype=bool)

        # -------------- Slack Buses search ----------------
        # Assume they are all set, but probably need some logic when compiling the numerical circuit to
        # enforce we have one slack on each AC island, split by the VSCs

        for i, bus in enumerate(nc.bus_data[:]):
            if bus.bus_types == BusMode.Slack_tpe.value:
                self.add_to_c_va(i)
                self.set_bus_vm_simple(bus_local=i,
                                       bus_data=nc.bus_data)

        # -------------- Generators and Batteries search ----------------
        for dev_tpe in (nc.generator_data, nc.battery_data):
            for i, is_controlled in enumerate(dev_tpe.controllable):
                bus_idx = dev_tpe.bus_idx[i]
                ctr_bus_idx = dev_tpe.controllable_bus_idx[i]

                if is_controlled:
                    remote_control = ctr_bus_idx != -1

                    self.set_bus_vm_simple(bus_local=bus_idx,
                                           bus_data=nc.bus_data,
                                           bus_remote=ctr_bus_idx,
                                           remote_control=remote_control,
                                           candidate_vm=dev_tpe.v[i])

                    self.add_to_c_p_zip(bus_idx)

                else:
                    self.add_to_c_p_zip(bus_idx)
                    self.add_to_c_q_zip(bus_idx)

        # -------------- ControlledShunts search ----------------
        for i, is_controlled in enumerate(nc.shunt_data.controllable):
            bus_idx = nc.shunt_data.bus_idx[i]
            ctr_bus_idx = nc.shunt_data.controllable_bus_idx[i]

            if is_controlled:
                remote_control = ctr_bus_idx != -1

                self.set_bus_vm_simple(bus_local=bus_idx,
                                       bus_data=nc.bus_data,
                                       bus_remote=ctr_bus_idx,
                                       remote_control=remote_control,
                                       candidate_vm=nc.shunt_data.vset[i])

        # -------------- HvdcLines search ----------------

        for i, tpe in enumerate(nc.bus_data.bus_types):
            if tpe == BusMode.Slack_tpe.value:
                self.c_va.add(i)
                self.c_vm.add(i)
            # elif tpe == BusMode.PQ_tpe.value:
            #     pass
            # elif tpe == BusMode.PV_tpe.value:
            #     self.c_vm.add(i)
            # elif tpe == BusMode.PQV_tpe.value:
            #     self.c_vm.add(i)
            # elif tpe == BusMode.P_tpe.value:
            #     pass

        for struct in (nc.generator_data, nc.battery_data):
            for e, is_controlled in enumerate(struct.controllable):
                bus_idx = struct.bus_idx[e]
                ctr_bus_idx = struct.controllable_bus_idx[e]

                if is_controlled:
                    remote_control = ctr_bus_idx != -1

                    self.set_bus_control_voltage(i=bus_idx,
                                                 j=ctr_bus_idx,
                                                 remote_control=remote_control and control_remote_voltage,
                                                 bus_name=nc.bus_data.names[bus_idx],
                                                 bus_data=nc.bus_data,
                                                 candidate_Vm=struct.v[e],
                                                 use_stored_guess=use_stored_guess)

                    # Set voltage magnitude through set_bus_control_voltage

                else:
                    self.c_p_zip.add(bus_idx)
                    self.c_q_zip.add(bus_idx)

        for struct in (nc.branch_data, nc.vsc_data):
            for k, tpe in enumerate(struct.tap_module_control_mode):
                if tpe == TapModuleControl.fixed:
                    pass
                elif tpe == TapModuleControl.Vm:
                    ii = struct.tap_controlled_buses[k]
                    if ii > -1:
                        # if the controlled branch was specified, use that
                        self.c_vm.add(ii)
                    else:
                        # else, we pick the from bus
                        iii = struct.F[k]
                        self.c_vm.add(iii)

                elif tpe == TapModuleControl.Qf:
                    self.c_Qf.add(k)

                elif tpe == TapModuleControl.Qt:
                    self.c_Qt.add(k)

            for k, tpe in enumerate(struct.tap_phase_control_mode):
                if tpe == TapPhaseControl.fixed:
                    pass
                elif tpe == TapPhaseControl.Pf:
                    self.c_Pf.add(k)

                elif tpe == TapPhaseControl.Pt:
                    self.c_Pt.add(k)

        return self

    def fill_unspecified(self, nc: NumericalCircuit) -> "GeneralizedSimulationIndices":
        """
        Redo, just negate the specified I guess
        :param nc:
        :return:
        """

        for i, tpe in enumerate(nc.bus_data.bus_types):
            if tpe == BusMode.Slack_tpe.value:
                self.c_va.add(i)
                self.c_vm.add(i)
            elif tpe == BusMode.PQ_tpe.value:
                pass
            elif tpe == BusMode.PV_tpe.value:
                self.c_vm.add(i)
            elif tpe == BusMode.PQV_tpe.value:
                self.c_vm.add(i)
            elif tpe == BusMode.P_tpe.value:
                pass

        return self

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

    def add_tap_phase_control(self, mode: TapPhaseControl, branch_idx: int):
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
            pass  # it is controllable

    def add_tap_module_control(self, mode: TapModuleControl, branch_idx, bus_idx: int):
        """

        :param mode:
        :param branch_idx:
        :param bus_idx:
        :return:
        """
        if mode == TapModuleControl.fixed:
            self.add_to_c_m(branch_idx)

        elif mode == TapModuleControl.Vm:
            self.add_to_c_vm(bus_idx)

        elif mode == TapModuleControl.Qf:
            self.add_to_c_Qf(branch_idx)

        elif mode == TapModuleControl.Qt:
            self.add_to_c_Qt(branch_idx)

        else:
            pass  # it is controllable

    def add_generator_behaviour(self, bus_idx: int, is_v_controlled: bool):
        pass

    def set_bus_vm_simple(self,
                          bus_local: int,
                          bus_data: BusData,
                          bus_remote: int = -1,
                          remote_control: bool = False,
                          candidate_vm: float = 1.0) -> None:
        """
        Set the bus control voltage checking incompatibilities
        Simple setting for now, just throwing errors if the bus is already set

        :param bus_local: Local bus index
        :param bus_remote: Remote bus index
        :param remote_control: Remote control?
        :param candidate_vm: Candidate voltage
        :param bus_data: BusData
        """

        if bus_data.bus_types[bus_local] == BusMode.Slack_tpe.value:
            self.add_to_c_vm(bus_local)
            self.bus_voltage_used[bus_local] = True

        else:
            # First check if we are setting a remote bus voltage
            if remote_control and bus_remote > -1 and bus_remote != bus_local:
                if not self.bus_voltage_used[bus_remote]:
                    # initialize the remote bus voltage to the control value
                    bus_data.Vbus[bus_remote] = complex(candidate_vm, 0)
                    self.bus_voltage_used[bus_remote] = True
                    self.add_to_c_vm(bus_remote)
                else:
                    self.logger.add_error(msg='Trying to set an already fixed voltage, duplicity of controls',
                                          device=bus_data.names[bus_remote],
                                          device_property='Vm')
            elif remote_control:
                self.logger.add_error(msg='Remote control without a valid remote bus',
                                      device=bus_data.names[bus_remote],
                                      device_property='Vm')

            # Not a remote bus control
            elif not self.bus_voltage_used[bus_local]:
                # initialize the local bus voltage to the control value
                bus_data.Vbus[bus_local] = complex(candidate_vm, 0)
                self.bus_voltage_used[bus_local] = True
                self.add_to_c_vm(bus_local)
            else:
                self.logger.add_error(msg='Trying to set an already fixed voltage, duplicity of controls',
                                      device=bus_data.names[bus_local],
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
