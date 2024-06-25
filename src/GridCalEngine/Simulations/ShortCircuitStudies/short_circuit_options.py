# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
from GridCalEngine.enumerations import FaultType
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
                 verbose: int = 0):
        """

        :param bus_index: Index of the bus failed (used if mid_line_fault is False)
        :param fault_type: fault type among 3x, LG, LL and LLG possibilities
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

        self.mid_line_fault: bool = mid_line_fault

        self.branch_index = branch_index

        self.branch_fault_locations = branch_fault_locations

        self.branch_fault_r = fault_r

        self.branch_fault_x = fault_x

        self.verbose = verbose

        self.register(key="bus_index", tpe=int)
        self.register(key="fault_type", tpe=FaultType)
        self.register(key="mid_line_fault", tpe=bool)
        self.register(key="branch_index", tpe=int)
        self.register(key="branch_fault_locations", tpe=float)
        self.register(key="branch_fault_r", tpe=int)
        self.register(key="branch_fault_x", tpe=int)
        self.register(key="verbose", tpe=int)
