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


from GridCal.Engine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from GridCal.Engine.Simulations.Stochastic.monte_carlo_results import MonteCarloResults
from GridCal.Engine.Simulations.Stochastic.monte_carlo_driver import make_monte_carlo_input
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Simulations.PowerFlow.power_flow_driver import PowerFlowMP, PowerFlowOptions, power_flow_worker
from GridCal.Engine.Simulations.PowerFlow.time_series_driver import TimeSeriesResults


class LatinHypercubeSampling(QThread):
    progress_signal = Signal(float)
    progress_text = Signal(str)
    done_signal = Signal()

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

        self.__cancel__ = False

    def get_steps(self):
        """
        Get time steps list of strings
        """
        p = self.results.points_number
        return ['point:' + str(l) for l in range(p)]

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

        lhs_results = MonteCarloResults(n, m, batch_size)
        avg_res = PowerFlowResults()
        avg_res.initialize(n, m)

        # compile
        # print('Compiling...', end='')
        numerical_circuit = self.circuit.compile()
        numerical_islands = numerical_circuit.compute(branch_tolerance_mode=self.options.branch_impedance_tolerance_mode)

        lhs_results.bus_types = numerical_circuit.bus_types

        max_iter = batch_size * len(numerical_islands)
        Sbase = self.circuit.Sbase
        it = 0

        # For every circuit, run the time series
        for numerical_island in numerical_islands:

            # try:
            # set the time series as sampled in the circuit

            monte_carlo_input = make_monte_carlo_input(numerical_island)
            mc_time_series = monte_carlo_input(batch_size, use_latin_hypercube=True)
            Vbus = numerical_island.Vbus

            # short cut the indices
            b_idx = numerical_island.original_bus_idx
            br_idx = numerical_island.original_branch_idx

            manager = multiprocessing.Manager()
            return_dict = manager.dict()

            t = 0
            while t < batch_size and not self.__cancel__:

                k = 0
                jobs = list()

                # launch only n_cores jobs at the time
                while k < n_cores + 2 and (t + k) < batch_size:
                    # set the power values
                    Y, I, S = mc_time_series.get_at(t)

                    # run power flow at the circuit
                    p = multiprocessing.Process(target=power_flow_worker,
                                                args=(t, self.options, numerical_island,
                                                      Vbus, S/Sbase, I/Sbase, return_dict))
                    jobs.append(p)
                    p.start()
                    k += 1
                    t += 1

                # wait for all jobs to complete
                for proc in jobs:
                    proc.join()

                progress = ((t + 1) / batch_size) * 100
                self.progress_signal.emit(progress)

            # collect results
            self.progress_text.emit('Collecting results...')
            for t in return_dict.keys():
                # store circuit results at the time index 't'
                res = return_dict[t]

                lhs_results.S_points[t, numerical_island.original_bus_idx] = res.Sbus
                lhs_results.V_points[t, numerical_island.original_bus_idx] = res.voltage
                lhs_results.I_points[t, numerical_island.original_branch_idx] = res.Ibranch
                lhs_results.loading_points[t, numerical_island.original_branch_idx] = res.loading
                lhs_results.losses_points[t, numerical_island.original_branch_idx] = res.losses

            # except Exception as ex:
            #     print(c.name, ex)

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

        # initialize the power flow
        power_flow = PowerFlowMP(self.circuit, self.options)

        # initialize the grid time series results
        # we will append the island results with another function
        self.circuit.time_series_results = TimeSeriesResults(0, 0, 0, 0, 0)

        batch_size = self.sampling_points
        n = len(self.circuit.buses)
        m = len(self.circuit.branches)

        self.progress_signal.emit(0.0)
        self.progress_text.emit('Running Latin Hypercube Sampling...')

        lhs_results = MonteCarloResults(n, m, batch_size)
        avg_res = PowerFlowResults()
        avg_res.initialize(n, m)

        # compile the numerical circuit
        numerical_circuit = self.circuit.compile()
        numerical_input_islands = numerical_circuit.compute(branch_tolerance_mode=self.options.branch_impedance_tolerance_mode)

        max_iter = batch_size * len(numerical_input_islands)
        Sbase = numerical_circuit.Sbase
        it = 0

        # For every circuit, run the time series
        for numerical_island in numerical_input_islands:

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
                res = power_flow.run_pf(circuit=numerical_island, Vbus=Vbus, Sbus=S / Sbase, Ibus=I / Sbase)

                # Gather the results
                lhs_results.S_points[t, numerical_island.original_bus_idx] = res.Sbus
                lhs_results.V_points[t, numerical_island.original_bus_idx] = res.voltage
                lhs_results.I_points[t, numerical_island.original_branch_idx] = res.Ibranch
                lhs_results.loading_points[t, numerical_island.original_branch_idx] = res.loading
                lhs_results.losses_points[t, numerical_island.original_branch_idx] = res.losses

                it += 1
                self.progress_signal.emit(it / max_iter * 100)

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
        # Ibranch = avg_res.Ibranch
        # loading = avg_res.loading
        # lhs_results.losses = avg_res.losses
        # flow_direction = avg_res.flow_direction
        # Sbus = avg_res.Sbus

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
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Cancelled')
        self.done_signal.emit()
