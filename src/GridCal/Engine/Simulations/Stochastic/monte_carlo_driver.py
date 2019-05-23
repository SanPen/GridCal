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
from GridCal.Engine.Simulations.Stochastic.monte_carlo_input import MonteCarloInput
from GridCal.Engine.Core.calculation_inputs import CalculationInputs
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.basic_structures import CDF
from GridCal.Engine.Simulations.PowerFlow.power_flow_driver import PowerFlowMP, PowerFlowOptions, power_flow_worker
from GridCal.Engine.Simulations.PowerFlow.time_series_driver import TimeSeriesResults

########################################################################################################################
# Monte Carlo classes
########################################################################################################################


def make_monte_carlo_input(numerical_input_island: CalculationInputs):
    """
    Generate a monte carlo input instance
    :param numerical_input_island:
    :return:
    """
    n = numerical_input_island.nbus
    Scdf = [None] * n
    Icdf = [None] * n
    Ycdf = [None] * n

    for i in range(n):
        Scdf[i] = CDF(numerical_input_island.Sbus_prof[i, :])
        Icdf[i] = CDF(numerical_input_island.Ibus_prof[i, :])
        Ycdf[i] = CDF(numerical_input_island.Ysh_prof[i, :])

    return MonteCarloInput(n, Scdf, Icdf, Ycdf)


class MonteCarlo(QThread):
    progress_signal = Signal(float)
    progress_text = Signal(str)
    done_signal = Signal()

    def __init__(self, grid: MultiCircuit, options: PowerFlowOptions, mc_tol=1e-3, batch_size=100, max_mc_iter=10000):
        """
        Monte Carlo simulation constructor
        :param grid: MultiGrid instance
        :param options: Power flow options
        :param mc_tol: monte carlo std.dev tolerance
        :param batch_size: size of the batch
        :param max_mc_iter: maximum monte carlo iterations in case of not reach the precission
        """
        QThread.__init__(self)

        self.circuit = grid

        self.options = options

        self.mc_tol = mc_tol

        self.batch_size = batch_size
        self.max_mc_iter = max_mc_iter

        n = len(self.circuit.buses)
        m = len(self.circuit.branches)

        self.results = MonteCarloResults(n, m)

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

        self.__cancel__ = False

        # initialize the grid time series results
        # we will append the island results with another function
        self.circuit.time_series_results = TimeSeriesResults(0, 0, 0, 0, 0)
        Sbase = self.circuit.Sbase
        n_cores = multiprocessing.cpu_count()

        it = 0
        variance_sum = 0.0
        std_dev_progress = 0
        v_variance = 0

        n = len(self.circuit.buses)
        m = len(self.circuit.branches)

        mc_results = MonteCarloResults(n, m)
        avg_res = PowerFlowResults()
        avg_res.initialize(n, m)

        # compile circuits
        numerical_circuit = self.circuit.compile()
        numerical_input_islands = numerical_circuit.compute(branch_tolerance_mode=self.options.branch_impedance_tolerance_mode)

        mc_results.bus_types = numerical_circuit.bus_types

        v_sum = zeros(n, dtype=complex)

        self.progress_signal.emit(0.0)

        while (std_dev_progress < 100.0) and (it < self.max_mc_iter) and not self.__cancel__:

            self.progress_text.emit('Running Monte Carlo: Variance: ' + str(v_variance))

            mc_results = MonteCarloResults(n, m, self.batch_size)

            # For every circuit, run the time series
            for numerical_island in numerical_input_islands:

                # set the time series as sampled
                monte_carlo_input = make_monte_carlo_input(numerical_island)
                mc_time_series = monte_carlo_input(self.batch_size, use_latin_hypercube=False)
                Vbus = numerical_island.Vbus

                manager = multiprocessing.Manager()
                return_dict = manager.dict()

                # short cut the indices
                b_idx = numerical_island.original_bus_idx
                br_idx = numerical_island.original_branch_idx

                t = 0
                while t < self.batch_size and not self.__cancel__:

                    k = 0
                    jobs = list()

                    # launch only n_cores jobs at the time
                    while k < n_cores + 2 and (t + k) < self.batch_size:
                        # set the power values
                        Y, I, S = mc_time_series.get_at(t)

                        # run power flow at the circuit
                        p = multiprocessing.Process(target=power_flow_worker,
                                                    args=(t, self.options, numerical_island, Vbus, S / Sbase, I / Sbase, return_dict))
                        jobs.append(p)
                        p.start()
                        k += 1
                        t += 1

                    # wait for all jobs to complete
                    for proc in jobs:
                        proc.join()

                    # progress = ((t + 1) / self.batch_size) * 100
                    # self.progress_signal.emit(progress)

                # collect results
                self.progress_text.emit('Collecting batch results...')
                for t in return_dict.keys():
                    # store circuit results at the time index 't'
                    res = return_dict[t]

                    mc_results.S_points[t, numerical_island.original_bus_idx] = res.Sbus
                    mc_results.V_points[t, numerical_island.original_bus_idx] = res.voltage
                    mc_results.I_points[t, numerical_island.original_branch_idx] = res.Ibranch
                    mc_results.loading_points[t, numerical_island.original_branch_idx] = res.loading
                    mc_results.losses_points[t, numerical_island.original_branch_idx] = res.losses

                # compile MC results
                self.progress_text.emit('Compiling results...')
                mc_results.compile()

                # compute the island branch results
                island_avg_res = numerical_island.compute_branch_results(mc_results.voltage[b_idx])

                # apply the island averaged results
                avg_res.apply_from_island(island_avg_res, b_idx=b_idx, br_idx=br_idx)

            # Compute the Monte Carlo values
            it += self.batch_size
            mc_results.append_batch(mc_results)
            v_sum += mc_results.get_voltage_sum()
            v_avg = v_sum / it
            v_variance = abs((power(mc_results.V_points - v_avg, 2.0) / (it - 1)).min())

            # progress
            variance_sum += v_variance
            err = variance_sum / it
            if err == 0:
                err = 1e-200  # to avoid division by zeros
            mc_results.error_series.append(err)

            # emmit the progress signal
            std_dev_progress = 100 * self.mc_tol / err
            if std_dev_progress > 100:
                std_dev_progress = 100
            self.progress_signal.emit(max((std_dev_progress, it / self.max_mc_iter * 100)))

            # print(iter, '/', max_mc_iter)
            # print('Vmc:', Vavg)
            # print('Vstd:', Vvariance, ' -> ', std_dev_progress, ' %')

        # compute the averaged branch magnitudes
        mc_results.sbranch = avg_res.Sbranch
        mc_results.losses = avg_res.losses

        # print('V mc: ', mc_results.voltage)

        # send the finnish signal
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Done!')
        self.done_signal.emit()

        return mc_results

    def run_single_thread(self):
        """
        Run the monte carlo simulation
        @return:
        """

        self.__cancel__ = False

        # initialize the power flow
        power_flow = PowerFlowMP(self.circuit, self.options)

        # initialize the grid time series results
        # we will append the island results with another function
        self.circuit.time_series_results = TimeSeriesResults(0, 0, 0, 0, 0)
        Sbase = self.circuit.Sbase

        it = 0
        variance_sum = 0.0
        std_dev_progress = 0
        v_variance = 0

        n = len(self.circuit.buses)
        m = len(self.circuit.branches)

        # compile circuits
        numerical_circuit = self.circuit.compile()
        numerical_input_islands = numerical_circuit.compute(branch_tolerance_mode=self.options.branch_impedance_tolerance_mode)



        mc_results = MonteCarloResults(n, m)
        avg_res = PowerFlowResults()
        avg_res.initialize(n, m)

        v_sum = zeros(n, dtype=complex)

        self.progress_signal.emit(0.0)

        while (std_dev_progress < 100.0) and (it < self.max_mc_iter) and not self.__cancel__:

            self.progress_text.emit('Running Monte Carlo: Variance: ' + str(v_variance))

            mc_results = MonteCarloResults(n, m, self.batch_size)

            # For every circuit, run the time series
            for numerical_island in numerical_input_islands:

                # set the time series as sampled
                monte_carlo_input = make_monte_carlo_input(numerical_island)
                mc_time_series = monte_carlo_input(self.batch_size, use_latin_hypercube=False)
                Vbus = numerical_island.Vbus

                # run the time series
                for t in range(self.batch_size):
                    # set the power values
                    Y, I, S = mc_time_series.get_at(t)

                    # res = powerflow.run_at(t, mc=True)
                    res = power_flow.run_pf(circuit=numerical_island, Vbus=Vbus, Sbus=S / Sbase, Ibus=I / Sbase)

                    mc_results.S_points[t, numerical_island.original_bus_idx] = res.Sbus
                    mc_results.V_points[t, numerical_island.original_bus_idx] = res.voltage
                    mc_results.I_points[t, numerical_island.original_branch_idx] = res.Ibranch
                    mc_results.loading_points[t, numerical_island.original_branch_idx] = res.loading
                    mc_results.losses_points[t, numerical_island.original_branch_idx] = res.losses

                # short cut the indices
                b_idx = numerical_island.original_bus_idx
                br_idx = numerical_island.original_branch_idx

                self.progress_text.emit('Compiling results...')
                mc_results.compile()

                # compute the island branch results
                island_avg_res = numerical_island.compute_branch_results(mc_results.voltage[b_idx])

                # apply the island averaged results
                avg_res.apply_from_island(island_avg_res, b_idx=b_idx, br_idx=br_idx)

            # Compute the Monte Carlo values
            it += self.batch_size
            mc_results.append_batch(mc_results)
            v_sum += mc_results.get_voltage_sum()
            v_avg = v_sum / it
            v_variance = abs((power(mc_results.V_points - v_avg, 2.0) / (it - 1)).min())

            # progress
            variance_sum += v_variance
            err = variance_sum / it
            if err == 0:
                err = 1e-200  # to avoid division by zeros
            mc_results.error_series.append(err)

            # emmit the progress signal
            std_dev_progress = 100 * self.mc_tol / err
            if std_dev_progress > 100:
                std_dev_progress = 100
            self.progress_signal.emit(max((std_dev_progress, it / self.max_mc_iter * 100)))

            # print(iter, '/', max_mc_iter)
            # print('Vmc:', Vavg)
            # print('Vstd:', Vvariance, ' -> ', std_dev_progress, ' %')

        # compile results
        mc_results.sbranch = avg_res.Sbranch
        # mc_results.losses = avg_res.losses
        mc_results.bus_types = numerical_circuit.bus_types

        # send the finnish signal
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Done!')
        self.done_signal.emit()

        return mc_results

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
        :return:
        """
        self.__cancel__ = True
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Cancelled')
        self.done_signal.emit()

