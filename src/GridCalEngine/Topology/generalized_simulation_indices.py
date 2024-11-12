from typing import Set, Dict
from GridCalEngine.basic_structures import IntVec
from GridCalEngine.enumerations import TapPhaseControl, TapModuleControl


class GeneralizedSimulationIndices:
    """
    GeneralizedSimulationIndices
    """

    def __init__(self):
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

    def slice(self, bus_idx: IntVec, br_idx: IntVec) -> "GeneralizedSimulationIndices":
        """

        :param bus_idx:
        :param br_idx:
        :return:
        """
        # TODO: Test this stuff
        indices = GeneralizedSimulationIndices()

        # build the mappings
        bus_map: Dict[int, int] = {o: i for i, o in enumerate(bus_idx)}
        br_map: Dict[int, int] = {o: i for i, o in enumerate(br_idx)}

        # bus index slicing
        indices.c_va = {bus_map[val] for val in self.c_va}
        indices.c_vm = {bus_map[val] for val in self.c_vm}

        indices.c_p_zip = {bus_map[val] for val in self.c_p_zip}
        indices.c_q_zip = {bus_map[val] for val in self.c_q_zip}

        indices.c_inj_P = {bus_map[val] for val in self.c_inj_P}
        indices.c_inj_Q = {bus_map[val] for val in self.c_inj_Q}

        # branch index slicing
        indices.c_tau = {br_map[val] for val in self.c_tau}
        indices.c_m = {br_map[val] for val in self.c_m}

        indices.c_Pf = {br_map[val] for val in self.c_Pf}
        indices.c_Pt = {br_map[val] for val in self.c_Pt}
        indices.c_Qf = {br_map[val] for val in self.c_Qf}
        indices.c_Qt = {br_map[val] for val in self.c_Qt}

        return indices

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