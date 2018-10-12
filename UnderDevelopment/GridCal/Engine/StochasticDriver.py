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
import os
import pickle as pkl
from warnings import warn
import pandas as pd
import pulp
import numpy as np
from numpy import complex, zeros, exp, r_, array, angle, c_, power, vstack, floor, arange

from matplotlib import pyplot as plt
import multiprocessing
from PyQt5.QtCore import QThread, QRunnable, pyqtSignal

from GridCal.Engine.IoStructures import MonteCarloResults, MonteCarloInput, CalculationInputs, PowerFlowResults
from GridCal.Engine.CalculationEngine import CDF, MultiCircuit
from GridCal.Engine.PowerFlowDriver import PowerFlowMP, PowerFlowOptions, power_flow_worker
from GridCal.Engine.TimeSeriesDriver import TimeSeriesResults

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
    progress_signal = pyqtSignal(float)
    progress_text = pyqtSignal(str)
    done_signal = pyqtSignal()

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
        numerical_input_islands = numerical_circuit.compute()

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
        numerical_input_islands = numerical_circuit.compute()

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
        mc_results.losses = avg_res.losses

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


class LatinHypercubeSampling(QThread):
    progress_signal = pyqtSignal(float)
    progress_text = pyqtSignal(str)
    done_signal = pyqtSignal()

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
        print('Compiling...', end='')
        numerical_circuit = self.circuit.compile()
        numerical_islands = numerical_circuit.compute()

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
                                                args=(t, self.options, numerical_island, Vbus, S/Sbase, I/Sbase, return_dict))
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
        numerical_input_islands = numerical_circuit.compute()

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
        # Ibranch = avg_res.Ibranch
        # loading = avg_res.loading
        lhs_results.losses = avg_res.losses
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
