# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0


from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowResults
from GridCalEngine.Simulations.Dynamics.dynamic_modules import dynamic_simulation
from GridCalEngine.Simulations.driver_template import DriverTemplate
from GridCalEngine.Compilers.circuit_to_data import compile_numerical_circuit_at

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
        numerical_circuit =  compile_numerical_circuit_at(self.grid, t_idx=None)
        calculation_inputs = numerical_circuit.split_into_islands()

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
