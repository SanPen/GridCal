# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Simulations.driver_template import DriverTemplate
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Simulations.Rms.rms_results import RmsResults
from VeraGridEngine.Simulations.Rms.problems.rms_problem import RmsProblem
from VeraGridEngine.Simulations.Rms.numerical.integration_methods import Trapezoid, BackEuler
from VeraGridEngine.enumerations import EngineType, SimulationTypes, DynamicIntegrationMethod


class RmsSimulationDriver(DriverTemplate):
    name = 'Power Flow'
    tpe = SimulationTypes.RmsDynamic_run

    """
    Dynamic wrapper to use with Qt
    """

    def __init__(self, grid: MultiCircuit,
                 options: RmsOptions,
                 engine: EngineType = EngineType.VeraGrid):

        """
        DynamicDriver class constructor
        :param grid: MultiCircuit instance
        :param options: RmsOptions instance (optional)
        :param engine: EngineType (i.e., EngineType.VeraGrid) (optional)
        """

        DriverTemplate.__init__(self, grid=grid, engine=engine)

        self.options = options

        self.results = RmsResults()

    def run(self):
        """
        Main function to initialize and run the system simulation.

        This function sets up logging, starts the dynamic simulation, and
        logs the outcome. It handles and logs any exceptions raised during execution.
        :return:
        """
        # Run the dynamic simulation
        self.run_time_simulation()

    def run_time_simulation(self):
        """
        Performs the numerical integration using the chosen method.
        :return:
        """

        # Get integration method
        if self.options.integration_method == DynamicIntegrationMethod.Trapezoid:
            integrator = Trapezoid()
        elif self.options.integration_method == DynamicIntegrationMethod.BackEuler:
            integrator = BackEuler()
        else:
            raise ValueError(f"integrator not implemented :( {self.options.integration_method}")
