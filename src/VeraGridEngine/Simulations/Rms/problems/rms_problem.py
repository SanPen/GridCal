# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from VeraGridEngine.Devices.multi_circuit import MultiCircuit



class RmsProblem:
    """
    DAE (Differential-Algebraic Equation) class to store and manage.

    Responsibilities:
        - Store state and algebraic variables (x, y)
        - Store Jacobian matrices
        - Store residual equations
        - Store sparsity patterns
    """

    def __init__(self, grid: MultiCircuit):
        """
        DAE class constructor
        Initialize DAE object with required containers and defaults.
        :param system: The simulation system object to which this DAE is tied
        """

