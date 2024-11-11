from typing import List
from GridCalEngine.basic_structures import IntVec


class GeneralizedSimulationIndices:

    def __init__(self):
        # CVa -> Indices of the buses where the voltage angles are specified.
        self.c_va: List[int] = list()

        # CVm -> Indices of the buses where the voltage modules are specified.
        self.c_vm: List[int] = list()

        # Cτ -> Indices of the controllable branches where the phase shift angles are specified.
        self.c_tau: List[int] = list()

        # Cm -> Indices of the controllable branches where the tap ratios are specified.
        self.c_m: List[int] = list()

        # CPzip -> Indices of the buses where the ZIP active power injection are specified.
        self.c_p_zip: List[int] = list()

        # CQzip -> Indices of the buses where the ZIP reactive power injection are specified.
        self.c_p_zip: List[int] = list()

        # CPf -> Indices of the controllable branches where Pf is specified.
        self.c_Pf: List[int] = list()

        # CPt -> Indices of the controllable branches where Pt is specified.
        self.c_Pf: List[int] = list()

        # CQf -> Indices of the controllable branches where Qf is specified.
        self.c_Qf: List[int] = list()

        # CQt -> Indices of the controllable branches where Qt is specified.
        self.c_Qt: List[int] = list()

        # CInjP -> Indices of the injection devices where the P is specified.
        self.c_inj_P: List[int] = list()

        # CInjQ -> Indices of the injection devices where the Q is specified.
        self.c_inj_Q: List[int] = list()
