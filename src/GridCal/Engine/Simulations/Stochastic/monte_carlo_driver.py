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
from GridCal.Engine.Simulations.Stochastic.monte_carlo_input import MonteCarloInput
from GridCal.Engine.Core.time_series_pf_data import TimeCircuit
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.basic_structures import CDF
from GridCal.Engine.Simulations.PowerFlow.power_flow_worker import PowerFlowOptions, single_island_pf, \
                                                                    power_flow_worker_args, power_flow_post_process

from GridCal.Engine.Core.time_series_pf_data import compile_time_circuit, BranchImpedanceMode

########################################################################################################################
# Monte Carlo classes
########################################################################################################################


def make_monte_carlo_input(numerical_input_island: TimeCircuit):
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
        Scdf[i] = CDF(numerical_input_island.Sbus[i, :])
        Icdf[i] = CDF(numerical_input_island.Ibus[i, :])
        Ycdf[i] = CDF(numerical_input_island.Yshunt_from_devices[i, :])

    return MonteCarloInput(n, Scdf, Icdf, Ycdf)


class MonteCarlo(QThread):
    progress_signal = Signal(float)
    progress_text = Signal(str)
    done_signal = Signal()
    name = 'Monte Carlo'

    def __init__(self, grid: MultiCircuit, options: PowerFlowOptions, mc_tol=1e-3, batch_size=100, max_mc_iter=10000,
                 opf_time_series_results=None):
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

        self.opf_time_series_results = opf_time_series_results

        self.mc_tol = mc_tol

        self.batch_size = batch_size
        self.max_mc_iter = max_mc_iter

        self.results = None

        self.logger = Logger()

        self.pool = None

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
        """
        t, _ = res
        progress = (t + 1) / self.max_mc_iter * 100
        self.progress_signal.emit(progress)
        self.returned_results.append(res)

    def run_multi_thread(self):
        """
        Run the monte carlo simulation
        @return: MonteCarloResults instance
        """

        self.__cancel__ = False

        # initialize the grid time series results
        # we will append the island results with another function
        # self.circuit.time_series_results = TimeSeriesResults(0, 0, [])
        self.pool = multiprocessing.Pool()
        it = 0
        variance_sum = 0.0
        std_dev_progress = 0
        v_variance = 0

        n = len(self.circuit.buses)
        m = self.circuit.get_branch_number()

        mc_results = MonteCarloResults(n, m, name='Monte Carlo')
        avg_res = PowerFlowResults()
        avg_res.initialize(n, m)

        # compile circuits
        numerical_circuit = self.circuit.compile_time_series()

        # perform the topological computation
        calc_inputs_dict = numerical_circuit.compute(branch_tolerance_mode=self.options.branch_impedance_tolerance_mode,
                                                     ignore_single_node_islands=self.options.ignore_single_node_islands)

        mc_results.bus_types = numerical_circuit.bus_types

        v_sum = zeros(n, dtype=complex)

        self.progress_signal.emit(0.0)

        while (std_dev_progress < 100.0) and (it < self.max_mc_iter) and not self.__cancel__:

            self.progress_text.emit('Running Monte Carlo: Variance: ' + str(v_variance))

            mc_results = MonteCarloResults(n, m, self.batch_size, name='Monte Carlo')

            # for each partition of the profiles...
            for t_key, calc_inputs in calc_inputs_dict.items():

                # For every island, run the time series
                for island_index, numerical_island in enumerate(calc_inputs):

                    # set the time series as sampled
                    monte_carlo_input = make_monte_carlo_input(numerical_island)
                    mc_time_series = monte_carlo_input(self.batch_size, use_latin_hypercube=False)
                    Vbus = numerical_island.Vbus
                    branch_rates = numerical_island.branch_rates

                    # short cut the indices
                    b_idx = numerical_island.original_bus_idx
                    br_idx = numerical_island.original_branch_idx

                    self.returned_results = list()

                    t = 0
                    while t < self.batch_size and not self.__cancel__:

                        Ysh, Ibus, Sbus = mc_time_series.get_at(t)

                        args = (t, self.options, numerical_island, Vbus, Sbus, Ibus, branch_rates)

                        self.pool.apply_async(power_flow_worker_args, (args,), callback=self.update_progress_mt)

                    # wait for all jobs to complete
                    self.pool.close()
                    self.pool.join()

                    # collect results
                    self.progress_text.emit('Collecting batch results...')
                    for t, res in self.returned_results:
                        # store circuit results at the time index 't'
                        mc_results.S_points[t, numerical_island.original_bus_idx] = res.Sbus
                        mc_results.V_points[t, numerical_island.original_bus_idx] = res.voltage
                        mc_results.Sbr_points[t, numerical_island.original_branch_idx] = res.Sf
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

        # compute the averaged branch magnitudes
        mc_results.sbranch = avg_res.Sf
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

        # initialize the grid time series results
        # we will append the island results with another function
        # self.circuit.time_series_results = TimeSeriesResults(0, 0, [])
        # Sbase = self.circuit.Sbase

        it = 0
        variance_sum = 0.0
        std_dev_progress = 0
        v_variance = 0

        # n = len(self.circuit.buses)
        # m = self.circuit.get_branch_number()
        #
        # # compile circuits
        # numerical_circuit = self.circuit.compile_time_series()
        #
        # # perform the topological computation
        # calc_inputs_dict = numerical_circuit.compute(branch_tolerance_mode=self.options.branch_impedance_tolerance_mode,
        #                                              ignore_single_node_islands=self.options.ignore_single_node_islands)
        #
        # mc_results = MonteCarloResults(n, m, name='Monte Carlo')
        # avg_res = PowerFlowResults()
        # avg_res.initialize(n, m)

        # compile the multi-circuit
        numerical_circuit = compile_time_circuit(circuit=self.circuit,
                                                 apply_temperature=False,
                                                 branch_tolerance_mode=BranchImpedanceMode.Specified,
                                                 opf_results=self.opf_time_series_results)

        # do the topological computation
        calculation_inputs = numerical_circuit.split_into_islands(ignore_single_node_islands=self.options.ignore_single_node_islands)

        mc_results_master = MonteCarloResults(n=numerical_circuit.nbus,
                                              m=numerical_circuit.nbr,
                                              p=self.max_mc_iter,
                                              bus_names=numerical_circuit.bus_names,
                                              branch_names=numerical_circuit.branch_names,
                                              bus_types=numerical_circuit.bus_types,
                                              name='Monte Carlo')

        avg_res = PowerFlowResults(n=numerical_circuit.nbus,
                                   m=numerical_circuit.nbr,
                                   n_tr=numerical_circuit.ntr,
                                   n_hvdc=numerical_circuit.nhvdc,
                                   bus_names=numerical_circuit.bus_names,
                                   branch_names=numerical_circuit.branch_names,
                                   transformer_names=numerical_circuit.tr_names,
                                   hvdc_names=numerical_circuit.hvdc_names,
                                   bus_types=numerical_circuit.bus_types)

        n = numerical_circuit.nbus
        m = numerical_circuit.nbr
        v_sum = zeros(n, dtype=complex)

        self.progress_signal.emit(0.0)

        while (std_dev_progress < 100.0) and (it < self.max_mc_iter) and not self.__cancel__:

            self.progress_text.emit('Running Monte Carlo: Variance: ' + str(v_variance))

            batch_results = MonteCarloResults(n=numerical_circuit.nbus,
                                              m=numerical_circuit.nbr,
                                              p=self.max_mc_iter,
                                              bus_names=numerical_circuit.bus_names,
                                              branch_names=numerical_circuit.branch_names,
                                              bus_types=numerical_circuit.bus_types,
                                              name='Monte Carlo')

            # For every island, run the time series
            for island_index, numerical_island in enumerate(calculation_inputs):

                # short cut the indices
                bus_idx = numerical_island.original_bus_idx
                br_idx = numerical_island.original_branch_idx

                # set the time series as sampled
                monte_carlo_input = make_monte_carlo_input(numerical_island)
                mc_time_series = monte_carlo_input(self.batch_size, use_latin_hypercube=False)
                Vbus = numerical_island.Vbus[:, 0]

                # run the time series
                for t in range(self.batch_size):
                    # set the power values
                    Y, I, S = mc_time_series.get_at(t)

                    res = single_island_pf(circuit=numerical_island,
                                           Vbus=Vbus,
                                           Sbus=S,
                                           Ibus=I,
                                           branch_rates=numerical_island.branch_rates,
                                           options=self.options,
                                           logger=self.logger)

                    batch_results.S_points[t, bus_idx] = res.Sbus
                    batch_results.V_points[t, bus_idx] = res.voltage
                    batch_results.Sbr_points[t, br_idx] = res.Sf
                    batch_results.loading_points[t, br_idx] = res.loading
                    batch_results.losses_points[t, br_idx] = res.losses

                self.progress_text.emit('Compiling results...')
                batch_results.compile()

                # compute the island branch results
                Sfb, Stb, If, It, Vbranch, loading, \
                losses, flow_direction, Sbus = power_flow_post_process(numerical_island,
                                                                       Sbus=batch_results.S_points.mean(axis=0)[bus_idx],
                                                                       V=batch_results.V_points.mean(axis=0)[bus_idx],
                                                                       branch_rates=numerical_island.branch_rates)

                # apply the island averaged results
                avg_res.Sbus[bus_idx] = Sbus
                avg_res.voltage[bus_idx] = batch_results.voltage[bus_idx]
                avg_res.Sf[br_idx] = Sfb
                avg_res.St[br_idx] = Stb
                avg_res.If[br_idx] = If
                avg_res.It[br_idx] = It
                avg_res.Vbranch[br_idx] = Vbranch
                avg_res.loading[br_idx] = loading
                avg_res.losses[br_idx] = losses
                avg_res.flow_direction[br_idx] = flow_direction

            # Compute the Monte Carlo values
            it += self.batch_size
            mc_results_master.append_batch(batch_results)
            v_sum += mc_results_master.get_voltage_sum()
            v_avg = v_sum / it
            v_variance = abs((power(mc_results_master.V_points - v_avg, 2.0) / (it - 1)).min())

            # progress
            variance_sum += v_variance
            err = variance_sum / it
            if err == 0:
                err = 1e-200  # to avoid division by zeros
            mc_results_master.error_series.append(err)

            # emmit the progress signal
            std_dev_progress = 100 * self.mc_tol / err
            if std_dev_progress > 100:
                std_dev_progress = 100
            self.progress_signal.emit(max((std_dev_progress, it / self.max_mc_iter * 100)))

        # compile results
        mc_results_master.bus_types = numerical_circuit.bus_types

        # send the finnish signal
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Done!')
        self.done_signal.emit()

        return mc_results_master

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

