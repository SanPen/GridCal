# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.
from numpy import complex, zeros, power

import multiprocessing
from PySide2.QtCore import QThread, Signal

from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from GridCal.Engine.Simulations.Stochastic.monte_carlo_results import MonteCarloResults
from GridCal.Engine.Simulations.Stochastic.monte_carlo_driver import make_monte_carlo_input
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Simulations.PowerFlow.power_flow_worker import PowerFlowOptions, single_island_pf, \
                                                                   power_flow_worker_args
from GridCal.Engine.Simulations.PowerFlow.time_series_driver import TimeSeriesResults


class LatinHypercubeSampling(QThread):
    progress_signal = Signal(float)
    progress_text = Signal(str)
    done_signal = Signal()
    name = 'Latin Hypercube'

    def __init__(self, grid: MultiCircuit, options: PowerFlowOptions, sampling_points=1000):
        """
        Latin Hypercube constructor
        Args:
            grid: MultiCircuit instance
            options: Power flow options
            sampling_points: number of sampling points
        """
        QThread.__init__(self)

        self.circuit = grid

        self.options = options

        self.sampling_points = sampling_points

        self.results = None

        self.logger = Logger()

        self.pool = multiprocessing.Pool()

        self.returned_results = list()

        self.__cancel__ = False

    def get_steps(self):
        """
        Get time steps list of strings
        """
        p = self.results.points_number
        return ['point:' + str(l) for l in range(p)]

    def update_progress_mt(self, res):
        """

        :param res:
        :return:
        """
        t, _ = res
        progress = (t + 1) / self.sampling_points * 100
        self.progress_signal.emit(progress)
        self.returned_results.append(res)

    def run_multi_thread(self):
        """
        Run the monte carlo simulation
        @return:
        """
        # print('LHS run')
        self.__cancel__ = False

        # initialize vars
        batch_size = self.sampling_points
        n = len(self.circuit.buses)
        m = len(self.circuit.branches)
        n_cores = multiprocessing.cpu_count()

        self.progress_signal.emit(0.0)
        self.progress_text.emit('Running Latin Hypercube Sampling in parallel using ' + str(n_cores) + ' cores ...')

        lhs_results = MonteCarloResults(n, m, batch_size, name='Latin Hypercube')
        avg_res = PowerFlowResults()
        avg_res.initialize(n, m)

        # compile the multi-circuit
        numerical_circuit = self.circuit.compile()

        # perform the topological computation
        calc_inputs_dict = numerical_circuit.compute_ts(
            branch_tolerance_mode=self.options.branch_impedance_tolerance_mode,
            ignore_single_node_islands=self.options.ignore_single_node_islands)

        # for each partition of the profiles...
        for t_key, calc_inputs in calc_inputs_dict.items():

            # For every island, run the time series
            for island_index, numerical_island in enumerate(calc_inputs):

                lhs_results.bus_types = numerical_circuit.bus_types

                monte_carlo_input = make_monte_carlo_input(numerical_island)
                mc_time_series = monte_carlo_input(batch_size, use_latin_hypercube=True)
                Vbus = numerical_island.Vbus
                branch_rates = numerical_island.branch_rates

                # short cut the indices
                b_idx = numerical_island.original_bus_idx
                br_idx = numerical_island.original_branch_idx

                # Start jobs
                self.returned_results = list()

                t = 0
                while t < batch_size and not self.__cancel__:

                    Ysh, Ibus, Sbus = mc_time_series.get_at(t)

                    args = (t, self.options, numerical_island, Vbus, Sbus, Ibus, branch_rates)

                    self.pool.apply_async(power_flow_worker_args, (args,), callback=self.update_progress_mt)

                # wait for all jobs to complete
                self.pool.close()
                self.pool.join()

                # collect results
                self.progress_text.emit('Collecting results...')
                for t, res in self.returned_results:
                    # store circuit results at the time index 't'
                    lhs_results.S_points[t, numerical_island.original_bus_idx] = res.Sbus
                    lhs_results.V_points[t, numerical_island.original_bus_idx] = res.voltage
                    lhs_results.I_points[t, numerical_island.original_branch_idx] = res.Ibranch
                    lhs_results.loading_points[t, numerical_island.original_branch_idx] = res.loading
                    lhs_results.losses_points[t, numerical_island.original_branch_idx] = res.losses

                # compile MC results
                self.progress_text.emit('Compiling results...')
                lhs_results.compile()

                # compute the island branch results
                island_avg_res = numerical_island.compute_branch_results(lhs_results.voltage[b_idx])

                # apply the island averaged results
                avg_res.apply_from_island(island_avg_res, b_idx=b_idx, br_idx=br_idx)

        # lhs_results the averaged branch magnitudes
        lhs_results.sbranch = avg_res.Sbranch
        lhs_results.losses = avg_res.losses
        self.results = lhs_results

        # send the finnish signal
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Done!')
        self.done_signal.emit()

        return lhs_results

    def run_single_thread(self):
        """
        Run the monte carlo simulation
        @return:
        """
        # print('LHS run')
        self.__cancel__ = False

        # initialize the grid time series results
        # we will append the island results with another function
        self.circuit.time_series_results = TimeSeriesResults(0, 0, 0, 0, 0)

        batch_size = self.sampling_points
        n = len(self.circuit.buses)
        m = len(self.circuit.branches)

        self.progress_signal.emit(0.0)
        self.progress_text.emit('Running Latin Hypercube Sampling...')

        lhs_results = MonteCarloResults(n, m, batch_size, name='Latin Hypercube')
        avg_res = PowerFlowResults()
        avg_res.initialize(n, m)

        # compile the multi-circuit
        numerical_circuit = self.circuit.compile()

        # perform the topological computation
        calc_inputs_dict = numerical_circuit.compute_ts(
            branch_tolerance_mode=self.options.branch_impedance_tolerance_mode,
            ignore_single_node_islands=self.options.ignore_single_node_islands)

        Sbase = numerical_circuit.Sbase
        it = 0
        # for each partition of the profiles...
        for t_key, calc_inputs in calc_inputs_dict.items():

            # For every island, run the time series
            for island_index, numerical_island in enumerate(calc_inputs):

                # try:
                # set the time series as sampled in the circuit
                # build the inputs
                monte_carlo_input = make_monte_carlo_input(numerical_island)
                mc_time_series = monte_carlo_input(batch_size, use_latin_hypercube=True)
                Vbus = numerical_island.Vbus

                # short cut the indices
                b_idx = numerical_island.original_bus_idx
                br_idx = numerical_island.original_branch_idx

                # run the time series
                for t in range(batch_size):

                    # set the power values from a Monte carlo point at 't'
                    Y, I, S = mc_time_series.get_at(t)

                    # Run the set monte carlo point at 't'
                    res = single_island_pf(circuit=numerical_island, Vbus=Vbus, Sbus=S / Sbase, Ibus=I / Sbase,
                                           branch_rates=numerical_island.branch_rates,
                                           options=self.options, logger=self.logger)

                    # Gather the results
                    lhs_results.S_points[t, numerical_island.original_bus_idx] = res.Sbus
                    lhs_results.V_points[t, numerical_island.original_bus_idx] = res.voltage
                    lhs_results.I_points[t, numerical_island.original_branch_idx] = res.Ibranch
                    lhs_results.loading_points[t, numerical_island.original_branch_idx] = res.loading
                    lhs_results.losses_points[t, numerical_island.original_branch_idx] = res.losses

                    it += 1
                    self.progress_signal.emit(it / batch_size * 100)

                    if self.__cancel__:
                        break

                if self.__cancel__:
                    break

                # compile MC results
                self.progress_text.emit('Compiling results...')
                lhs_results.compile()

                # compute the island branch results
                island_avg_res = numerical_island.compute_branch_results(lhs_results.voltage[b_idx])

                # apply the island averaged results
                avg_res.apply_from_island(island_avg_res, b_idx=b_idx, br_idx=br_idx)

        # lhs_results the averaged branch magnitudes
        lhs_results.sbranch = avg_res.Sbranch

        lhs_results.bus_types = numerical_circuit.bus_types

        self.results = lhs_results

        # send the finnish signal
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Done!')
        self.done_signal.emit()

        return lhs_results

    def run(self):
        """
        Run the monte carlo simulation
        @return:
        """
        # print('LHS run')
        self.__cancel__ = False

        if self.options.multi_thread:
            self.results = self.run_multi_thread()
        else:
            self.results = self.run_single_thread()

        # send the finnish signal
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Done!')
        self.done_signal.emit()

    def cancel(self):
        """
        Cancel the simulation
        """
        self.__cancel__ = True
        self.pool.terminate()
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Cancelled')
        self.done_signal.emit()
