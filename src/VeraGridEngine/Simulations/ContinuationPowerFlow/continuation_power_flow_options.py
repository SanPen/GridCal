# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from VeraGridEngine.Simulations.ContinuationPowerFlow.continuation_power_flow import (CpfStopAt,
                                                                                      CpfParametrization)
from VeraGridEngine.Simulations.options_template import OptionsTemplate


class ContinuationPowerFlowOptions(OptionsTemplate):
    """
    ContinuationPowerFlowOptions
    """

    def __init__(self,
                 step=0.01,
                 approximation_order=CpfParametrization.Natural,
                 adapt_step=True,
                 step_min=0.0001,
                 step_max=0.2,
                 error_tol=1e-3,
                 tol=1e-6,
                 max_it=20,
                 stop_at=CpfStopAt.Nose,
                 verbose: int = 0):
        """
        Voltage collapse options
        @param step: Step length
        @param approximation_order: Order of the approximation: 1, 2, 3, etc...
        @param adapt_step: Use adaptive step length?
        @param step_min: Minimum step length
        @param step_max: Maximum step length
        @param error_tol: Error tolerance
        @param tol: tolerance
        @param max_it: Maximum number of iterations
        @param stop_at: Value of lambda to stop at, it can be specified by a concept namely NOSE to sto at the edge or
        FULL tp draw the full curve
        """
        OptionsTemplate.__init__(self, name='ContinuationPowerFlowOptions')

        self.step = step

        self.approximation_order = approximation_order

        self.adapt_step = adapt_step

        self.step_min = step_min

        self.step_max = step_max

        self.step_tol = error_tol

        self.solution_tol = tol

        self.max_it = max_it

        self.stop_at = stop_at

        self.verbose = verbose

        self.register(key="step", tpe=float)
        self.register(key="approximation_order", tpe=CpfParametrization)
        self.register(key="adapt_step", tpe=bool)
        self.register(key="step_min", tpe=float)
        self.register(key="step_max", tpe=float)
        self.register(key="step_tol", tpe=float)
        self.register(key="solution_tol", tpe=float)
        self.register(key="max_it", tpe=int)
        self.register(key="stop_at", tpe=CpfStopAt)
        self.register(key="verbose", tpe=int)
