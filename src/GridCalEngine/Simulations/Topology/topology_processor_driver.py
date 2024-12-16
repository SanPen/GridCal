# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.enumerations import SimulationTypes
from GridCalEngine.Simulations.driver_template import DriverTemplate


class TopologyProcessorDriver(DriverTemplate):
    """
    TopologyProcessorDriver
    """

    name = 'Topology processor'
    tpe = SimulationTypes.TopologyProcessor_run

    def __init__(self, grid: MultiCircuit):
        """
        Electric distance clustering
        :param grid: MultiCircuit instance
        """
        DriverTemplate.__init__(self, grid=grid)

    def run(self):
        """
        Run the topology processing in-place
        @return:
        """
        self.tic()
        self.report_progress(0.0)
        nt = self.grid.get_time_number()

        # process snapshot
        self.grid.process_topology_at(t_idx=None, logger=self.logger)

        for t in range(nt):
            # process time step "t"
            self.grid.process_topology_at(t_idx=t, logger=self.logger)

            self.report_progress2(t, nt)

        # display progress
        self.report_done()
        self.toc()

    def cancel(self):
        """
        Cancel the simulation
        :return:
        """
        self.__cancel__ = True
        self.report_done("Cancelled!")
