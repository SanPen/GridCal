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

from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowResults
from GridCalEngine.Simulations.Dynamics.dynamic_modules import dynamic_simulation
from GridCalEngine.Simulations.driver_template import DriverTemplate

########################################################################################################################
# Transient stability
########################################################################################################################


class TransientStabilityOptions:

    def __init__(self, h=0.001, t_sim=15, max_err=0.0001, max_iter=25):

        # step length (s)
        self.h = h

        # simulation time (s)
        self.t_sim = t_sim

        # Maximum error in network iteration (voltage mismatches)
        self.max_err = max_err

        # Maximum number of network iterations
        self.max_iter = max_iter


class TransientStability(DriverTemplate):

    def __init__(self, grid: MultiCircuit, options: TransientStabilityOptions, pf_res: PowerFlowResults):
        """
        TimeSeries constructor
        @param grid: MultiCircuit instance
        @param options: PowerFlowOptions instance
        """
        DriverTemplate.__init__(self, grid=grid)

        self.grid = grid

        self.options = options

        self.pf_res = pf_res

        self.results = None

    def get_steps(self):
        """
        Get time steps list of strings
        """
        return list()

    def status(self, txt, progress):
        """
        Emit status
        :param txt: text to display
        :param progress: progress 0-100
        """
        self.report_progress(progress)
        self.report_text(txt)

    def run(self):
        """
        Run transient stability
        """
        self.tic()
        self.report_progress(0.0)
        self.report_text('Running transient stability...')

        # print('Compiling...', end='')
        numerical_circuit = self.grid.compile_snapshot()
        calculation_inputs = numerical_circuit.compute()

        for calculation_input in calculation_inputs:

            dynamic_devices = calculation_input.get_generators()
            bus_indices = [calculation_input.buses_dict[elm.bus] for elm in dynamic_devices]

            res = dynamic_simulation(n=len(calculation_input.buses),
                                     Vbus=self.pf_res.voltage[calculation_input.original_bus_idx],
                                     Sbus=self.pf_res.Sbus[calculation_input.original_bus_idx],
                                     Ybus=calculation_input.Ybus,
                                     Sbase=calculation_input.Sbase,
                                     fBase=calculation_input.fBase,
                                     t_sim=self.options.t_sim,
                                     h=self.options.h,
                                     dynamic_devices=dynamic_devices,
                                     bus_indices=bus_indices,
                                     callback=self.status)

        self.results = res
        self.toc()
