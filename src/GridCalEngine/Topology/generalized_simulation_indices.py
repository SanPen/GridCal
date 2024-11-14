from typing import Set
from GridCalEngine.enumerations import TapPhaseControl, TapModuleControl, BusMode
from GridCalEngine.DataStructures.numerical_circuit import NumericalCircuit


class GeneralizedSimulationIndices:
    """
    GeneralizedSimulationIndices
    """

    def __init__(self) -> None:
        """
        Constructor
        """
        # CVa -> Indices of the buses where the voltage angles are specified.
        # (slack bus)
        self.c_va: Set[int] = set()

        # CVm -> Indices of the buses where the voltage modules are specified.
        # Slack buses, Gerators, ControlledShunts, Batteries, HvdcLine, VSC, Transformers.
        self.c_vm: Set[int] = set()

        # Cτ -> Indices of the controllable branches where the phase shift angles are specified.
        self.c_tau: Set[int] = set()

        # Cm -> Indices of the controllable branches where the tap ratios are specified.
        self.c_m: Set[int] = set()

        # CPzip -> Indices of the buses where the ZIP active power injection are specified.
        # (Generators, Batteries)
        self.c_p_zip: Set[int] = set()

        # CQzip -> Indices of the buses where the ZIP reactive power injection are specified.
        # (Generators, Batteries) that are not controlling voltage
        self.c_q_zip: Set[int] = set()

        # CPf -> Indices of the controllable branches where Pf is specified.
        self.c_Pf: Set[int] = set()

        # CPt -> Indices of the controllable branches where Pt is specified.
        self.c_Pt: Set[int] = set()

        # CQf -> Indices of the controllable branches where Qf is specified.
        self.c_Qf: Set[int] = set()

        # CQt -> Indices of the controllable branches where Qt is specified.
        self.c_Qt: Set[int] = set()

        # CInjP -> Indices of the injection devices where the P is specified.
        self.c_inj_P: Set[int] = set()

        # CInjQ -> Indices of the injection devices where the Q is specified.
        self.c_inj_Q: Set[int] = set()

    def fill_specified(self, nc: NumericalCircuit) -> "GeneralizedSimulationIndices":
        """

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