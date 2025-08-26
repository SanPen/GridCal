# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from GridCalEngine.enumerations import FaultType, MethodShortCircuit, PhasesShortCircuit
from GridCalEngine.Simulations.options_template import OptionsTemplate


class ShortCircuitOptions(OptionsTemplate):
    """
    Short circuit options
    """

    def __init__(self,
                 bus_index: int = 0,
                 fault_type=FaultType.ph3,
                 mid_line_fault: bool = False,
                 branch_index: int = 0,
                 branch_fault_locations: float = 0.5,
                 fault_r: float = 1e-20,
                 fault_x: float = 1e-20,
                 verbose: int = 0,
                 method=MethodShortCircuit.sequences,
                 phases=PhasesShortCircuit.abc):
        """
        :param bus_index: Index of the bus failed (used if mid_line_fault is False)
        :param fault_type: fault type among 3x, LG, LL and LLG possibilities
        :param method: choose between the traditional sequence shortcircuit method or the new abc approach
        :param mid_line_fault: Is the fault occurring at the middle of a line?
        :param branch_index: Index of the failed branch in case of a line fault (used if mid_line_fault is True)
        :param branch_fault_locations: per unit location of the fault measured from the "from" bus
        :param fault_r: Fault resistance
        :param fault_x: Fault reactance
        :param verbose: Verbosity level
        """
        OptionsTemplate.__init__(self, name="ShortCircuitOptions")

        self.bus_index = bus_index

        self.fault_type = fault_type

        self.method = method

        self.phases = phases

        self.mid_line_fault: bool = mid_line_fault

        self.branch_index = branch_index

        self.branch_fault_locations = branch_fault_locations

        self.branch_fault_r = fault_r

        self.branch_fault_x = fault_x

        self.verbose = verbose

        self.register(key="bus_index", tpe=int)
        self.register(key="fault_type", tpe=FaultType)
        self.register(key="method", tpe=MethodShortCircuit)
        self.register(key="phases", tpe=PhasesShortCircuit)
        self.register(key="mid_line_fault", tpe=bool)
        self.register(key="branch_index", tpe=int)
        self.register(key="branch_fault_locations", tpe=float)
        self.register(key="branch_fault_r", tpe=int)
        self.register(key="branch_fault_x", tpe=int)
        self.register(key="verbose", tpe=int)
