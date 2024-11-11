from typing import Set
from GridCalEngine.basic_structures import IntVec
from GridCalEngine.enumerations import TapPhaseControl, TapModuleControl


class GeneralizedSimulationIndices:
    """

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

    # Add functions for each set
    def add_to_c_va(self, value: int):
        self.c_va.add(value)

    def add_to_c_vm(self, value: int):
        self.c_vm.add(value)

    def add_to_c_tau(self, value: int):
        self.c_tau.add(value)

    def add_to_c_m(self, value: int):
        self.c_m.add(value)

    def add_to_c_p_zip(self, value: int):
        self.c_p_zip.add(value)

    def add_to_c_q_zip(self, value: int):
        self.c_q_zip.add(value)

    def add_to_c_Pf(self, value: int):
        self.c_Pf.add(value)

    def add_to_c_Pt(self, value: int):
        self.c_Pt.add(value)

    def add_to_c_Qf(self, value: int):
        self.c_Qf.add(value)

    def add_to_c_Qt(self, value: int):
        self.c_Qt.add(value)

    def add_to_c_inj_P(self, value: int):
        self.c_inj_P.add(value)

    def add_to_c_inj_Q(self, value: int):
        self.c_inj_Q.add(value)

    def add_tap_phase_control(self, mode: TapPhaseControl, branch_idx: int):
        """

        :param mode:
        :param branch_idx:
        :return:
        """
        if mode == TapPhaseControl.fixed:
            self.add_to_c_tau(branch_idx)

        else:
            pass  # it is controllable

    def add_tap_module_control(self, mode: TapModuleControl, branch_idx):
        """

        :param mode:
        :param branch_idx:
        :return:
        """
        if mode == TapModuleControl.fixed:
            self.add_to_c_m(branch_idx)

        else:
            pass  # it is controllable

    def add_generator_behaviour(self, bus_idx: int, is_v_controlled: bool):
        pass