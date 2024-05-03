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

class GeneratorError(Exception):
    """Base class for exceptions in this generator control module."""
    pass

class ControlLengthError(GeneratorError):
    """Exception raised if not exactly two controls are chosen for the generator."""
    def __init__(self, controlmode, message="Exactly two controls must be chosen for generator operation"):
        self.controlmode = controlmode
        self.message = message
        super().__init__(self.message)

class UnderFrequencyError(GeneratorError):
    """Exception raised for an underfrequency condition in generator operation."""
    def __init__(self, frequency, message="Frequency is below the minimum threshold for safe operation"):
        self.frequency = frequency
        self.message = message
        super().__init__(self.message)


class PowerFlowError(Exception):
    """Base class for exceptions in this module."""
    pass

class SlackError(PowerFlowError):
    """Exception raised when there is a problem with the slack bus in a power flow study."""
    def __init__(self, message="Invalid or undefined slack bus configuration"):
        self.message = message
        super().__init__(self.message)

class RectangularJacobianError(PowerFlowError):
    """Exception raised when the Jacobian matrix used in power flow calculation is not square."""
    def __init__(self, rows, columns, message="Jacobian matrix must be square"):
        self.rows = rows
        self.columns = columns
        self.message = f"{message}: found {rows}x{columns}"
        super().__init__(self.message)

class VSCError(Exception):
    """Base class for exceptions in this module."""
    pass

class ControlLengthError(VSCError):
    """Exception raised if not exactly two controls chosen"""
    def __init__(self, controlmode, length, message="Exactly two controls must be chosen"):
        self.controlmode = controlmode
        self.length = length
        self.message = message + f" but found {self.length}" + f", {self.controlmode}"
        super().__init__(self.message)

class ControlNotImplementedError(VSCError):
    """Exception raised if a control mode is not implemented."""
    def __init__(self, controlmode, message="Control mode is not implemented"):
        self.controlmode = controlmode
        self.message = message + f": {controlmode}"
        super().__init__(self.message)

class UnderVoltageError(VSCError):
    """Exception raised for an undervoltage condition in VSC."""
    def __init__(self, voltage, message="Voltage is below the minimum threshold"):
        self.voltage = voltage
        self.message = message
        super().__init__(self.message)
