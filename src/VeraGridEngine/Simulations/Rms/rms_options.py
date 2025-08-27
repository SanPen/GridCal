# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from VeraGridEngine.enumerations import DynamicIntegrationMethod


class RmsOptions:

    def __init__(self,
                 time_step: float = 0.01,
                 simulation_time: float = 5,
                 max_integrator_iterations: int = 20,
                 tolerance: float = 1e-6,
                 integration_method: DynamicIntegrationMethod = DynamicIntegrationMethod.Trapezoid):
        """
        RmsOptions
        :param time_step: time step of the simulations (s)
        :param simulation_time: simulation time (s)
        :param max_integrator_iterations: max number of iterations
        :param tolerance: Integration tolerance
        :param integration_method: Integration method (default Trapezoid)
        """
        self.time_step: float = time_step
        self.simulation_time: float = simulation_time
        self.max_integrator_iterations: int = max_integrator_iterations
        self.tolerance: float = tolerance
        self.integration_method: DynamicIntegrationMethod = integration_method
