import numpy as np
from typing import List, Tuple
import scipy.sparse as sp
from GridCalEngine.enumerations import GpfControlType
from GridCalEngine.basic_structures import Vec, IntVec


class ControlData:

    def __init__(self):
        # VSC Control settings
        self.vsc_control_modes: List[GpfControlType] = []
        self.vsc_control_idx: List[IntVec] = []
        self.vsc_control_values: List[Vec] = []

        # Gen control settings
        self.gen_control_modes: List[GpfControlType] = []
        self.gen_control_idx: List[IntVec] = []
        self.gen_control_values: List[Vec] = []

        # Controllable Branch (Trafo) control settings
        self.controllable_branch_control_modes: List[GpfControlType] = []
        self.controllable_branch_control_modes: List[IntVec] = []
        self.controllable_branch_control_modes: List[Vec] = []

        # Bus control settings
        self.bus_control_modes: List[GpfControlType] = []
        self.bus_control_idx: List[IntVec] = []
        self.bus_control_values: List[Vec] = []

        # Passive branch control settings
        self.passive_branch_control_modes: List[GpfControlType] = []
        self.passive_branch_control_idx: List[IntVec] = []
        self.passive_branch_control_values: List[Vec] = []
