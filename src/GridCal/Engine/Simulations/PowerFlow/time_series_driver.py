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

import json
import pandas as pd
import numpy as np
import time
import multiprocessing
from sklearn.cluster import KMeans
from PySide2.QtCore import QThread, QThreadPool, Signal

from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from GridCal.Engine.Simulations.result_types import ResultTypes
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCal.Engine.Simulations.PowerFlow.power_flow_worker import single_island_pf, power_flow_worker_args
from GridCal.Engine.Simulations.Stochastic.latin_hypercube_sampling import lhs
from GridCal.Gui.GuiFunctions import ResultsModel


class TimeSeriesResults(PowerFlowResults):

    def __init__(self, n, m, time_array):
        """
        TimeSeriesResults constructor
        @param n: number of buses
        @param m: number of branches
        @param nt: number of time steps
        """
        PowerFlowResults.__init__(self)
        self.name = 'Time series'
        self.nt = len(time_array)
        self.m = m
        self.n = n

        self.time = time_array

        self.bus_types = np.zeros(n, dtype=int)

        if self.nt > 0:
            self.voltage = np.zeros((self.nt, n), dtype=complex)

            self.S = np.zeros((self.nt, n), dtype=complex)

            self.Sbranch = np.zeros((self.nt, m), dtype=complex)

            self.Ibranch = np.zeros((self.nt, m), dtype=complex)

            self.Vbranch = np.zeros((self.nt, m), dtype=complex)

            self.loading = np.zeros((self.nt, m), dtype=complex)

            self.losses = np.zeros((self.nt, m), dtype=complex)

            self.flow_direction = np.zeros((self.nt, m), dtype=float)

            self.error = np.zeros(self.nt)

            self.converged = np.ones(self.nt, dtype=bool)  # guilty assumption

            self.overloads = [None] * self.nt

            self.overvoltage = [None] * self.nt

            self.undervoltage = [None] * self.nt

            self.overloads_idx = [None] * self.nt

            self.overvoltage_idx = [None] * self.nt

            self.undervoltage_idx = [None] * self.nt

            self.buses_useful_for_storage = [None] * self.nt

        else:
            self.voltage = None

            self.S = None

            self.Sbranch = None

            self.Ibranch = None

            self.Vbranch = None

            self.loading = None

            self.losses = None

            self.flow_direction = None

            self.error = None

            self.converged = None

            self.overloads = None

            self.overvoltage = None

            self.undervoltage = None

            self.overloads_idx = None

            self.overvoltage_idx = None

            self.undervoltage_idx = None

            self.buses_useful_for_storage = None

        self.available_results = [ResultTypes.BusVoltageModule,
                                  ResultTypes.BusVoltageAngle,
                                  ResultTypes.BusActivePower,
                                  ResultTypes.BusReactivePower,
                                  ResultTypes.BranchActivePower,
                                  ResultTypes.BranchReactivePower,
                                  ResultTypes.BranchActiveCurrent,
                                  ResultTypes.BranchReactiveCurrent,
                                  ResultTypes.BranchLoading,
                                  ResultTypes.BranchActiveLosses,
                                  ResultTypes.BranchReactiveLosses,
                                  ResultTypes.BranchVoltage,
                                  ResultTypes.BranchAngles,
                                  ResultTypes.SimulationError]

    def set_at(self, t, results: PowerFlowResults):
        """
        Set the results at the step t
        @param t: time index
        @param results: PowerFlowResults instance
        """

        self.voltage[t, :] = results.voltage

        self.S[t, :] = results.Sbus

        self.Sbranch[t, :] = results.Sbranch

        self.Ibranch[t, :] = results.Ibranch

        self.Vbranch[t, :] = results.Vbranch

        self.loading[t, :] = results.loading

        self.losses[t, :] = results.losses

        self.flow_direction[t, :] = results.flow_direction

        self.error[t] = max(results.error)

        self.converged[t] = min(results.converged)

        self.overloads[t] = results.overloads

        self.overvoltage[t] = results.overvoltage

        self.undervoltage[t] = results.undervoltage

        self.overloads_idx[t] = results.overloads_idx

        self.overvoltage_idx[t] = results.overvoltage_idx

        self.undervoltage_idx[t] = results.undervoltage_idx

        self.buses_useful_for_storage[t] = results.buses_useful_for_storage

    @staticmethod
    def merge_if(df, arr, ind, cols):
        """

        @param df:
        @param arr:
        @param ind:
        @param cols:
        @return:
        """
        obj = pd.DataFrame(data=arr, index=ind, columns=cols)
        if df is None:
            df = obj
        else:
            df = pd.concat([df, obj], axis=1)

        return df

    def apply_from_island(self, results, b_idx, br_idx, t_index, grid_idx):
        """
        Apply results from another island circuit to the circuit results represented here
        :param results: PowerFlowResults
        :param b_idx: bus original indices
        :param br_idx: branch original indices
        :param t_index:
        :param grid_idx:
        :return:
        """

        # bus results
        if self.voltage.shape == results.voltage.shape:
            self.voltage = results.voltage
            self.S = results.S
        else:
            self.voltage[np.ix_(t_index, b_idx)] = results.voltage
            self.S[np.ix_(t_index, b_idx)] = results.S

        # branch results
        if self.Sbranch.shape == results.Sbranch.shape:
            self.Sbranch = results.Sbranch

            self.Ibranch = results.Ibranch

            self.Vbranch = results.Vbranch

            self.loading = results.loading

            self.losses = results.losses

            self.flow_direction = results.flow_direction

            if (results.error > self.error).any():
                self.error += results.error

            self.converged = self.converged * results.converged

        else:
            self.Sbranch[np.ix_(t_index, br_idx)] = results.Sbranch

            self.Ibranch[np.ix_(t_index, br_idx)] = results.Ibranch

            self.Vbranch[np.ix_(t_index, br_idx)] = results.Vbranch

            self.loading[np.ix_(t_index, br_idx)] = results.loading

            self.losses[np.ix_(t_index, br_idx)] = results.losses

            self.flow_direction[np.ix_(t_index, br_idx)] = results.flow_direction

            if (results.error > self.error[t_index]).any():
                self.error[t_index] += results.error

            self.converged[t_index] = self.converged[t_index] * results.converged

    def get_results_dict(self):
        """
        Returns a dictionary with the results sorted in a dictionary
        :return: dictionary of 2D numpy arrays (probably of complex numbers)
        """
        data = {'Vm': np.abs(self.voltage).tolist(),
                'Va': np.angle(self.voltage).tolist(),
                'P': self.S.real.tolist(),
                'Q': self.S.imag.tolist(),
                'Sbr_real': self.Sbranch.real.tolist(),
                'Sbr_imag': self.Sbranch.imag.tolist(),
                'Ibr_real': self.Ibranch.real.tolist(),
                'Ibr_imag': self.Ibranch.imag.tolist(),
                'loading': np.abs(self.loading).tolist(),
                'losses': np.abs(self.losses).tolist()}
        return data

    def save(self, fname):
        """
        Export as json
        """

        with open(fname, "wb") as output_file:
            json_str = json.dumps(self.get_results_dict())
            output_file.write(json_str)

    def analyze(self):
        """
        Analyze the results
        @return:
        """
        branch_overload_frequency = np.zeros(self.m)
        bus_undervoltage_frequency = np.zeros(self.n)
        bus_overvoltage_frequency = np.zeros(self.n)
        buses_selected_for_storage_frequency = np.zeros(self.n)
        for i in range(self.nt):
            branch_overload_frequency[self.overloads_idx[i]] += 1
            bus_undervoltage_frequency[self.undervoltage_idx[i]] += 1
            bus_overvoltage_frequency[self.overvoltage_idx[i]] += 1
            buses_selected_for_storage_frequency[self.buses_useful_for_storage[i]] += 1

        return branch_overload_frequency, bus_undervoltage_frequency, bus_overvoltage_frequency, \
                buses_selected_for_storage_frequency

    def mdl(self, result_type: ResultTypes, indices=None, names=None) -> "ResultsModel":
        """

        :param result_type:
        :param indices:
        :param names:
        :return:
        """

        if indices is None:
            indices = np.array(range(len(names)))

        if len(indices) > 0:

            labels = names[indices]

            if result_type == ResultTypes.BusVoltageModule:
                data = np.abs(self.voltage[:, indices])
                y_label = '(p.u.)'
                title = 'Bus voltage '

            elif result_type == ResultTypes.BusVoltageAngle:
                data = np.angle(self.voltage[:, indices], deg=True)
                y_label = '(Deg)'
                title = 'Bus voltage '

            elif result_type == ResultTypes.BusActivePower:
                data = self.S[:, indices].real
                y_label = '(MW)'
                title = 'Bus active power '

            elif result_type == ResultTypes.BusReactivePower:
                data = self.S[:, indices].imag
                y_label = '(MVAr)'
                title = 'Bus reactive power '

            elif result_type == ResultTypes.BranchPower:
                data = self.Sbranch[:, indices]
                y_label = '(MVA)'
                title = 'Branch power '

            elif result_type == ResultTypes.BranchActivePower:
                data = self.Sbranch[:, indices].real
                y_label = '(MW)'
                title = 'Branch power '

            elif result_type == ResultTypes.BranchReactivePower:
                data = self.Sbranch[:, indices].imag
                y_label = '(MVAr)'
                title = 'Branch power '

            elif result_type == ResultTypes.BranchCurrent:
                data = self.Ibranch[:, indices]
                y_label = '(kA)'
                title = 'Branch current '

            elif result_type == ResultTypes.BranchActiveCurrent:
                data = self.Ibranch[:, indices].real
                y_label = '(p.u.)'
                title = 'Branch current '

            elif result_type == ResultTypes.BranchReactiveCurrent:
                data = self.Ibranch[:, indices].imag
                y_label = '(p.u.)'
                title = 'Branch current '

            elif result_type == ResultTypes.BranchLoading:
                data = np.abs(self.loading[:, indices]) * 100
                y_label = '(%)'
                title = 'Branch loading '

            elif result_type == ResultTypes.BranchLosses:
                data = self.losses[:, indices]
                y_label = '(MVA)'
                title = 'Branch losses'

            elif result_type == ResultTypes.BranchActiveLosses:
                data = self.losses[:, indices].real
                y_label = '(MW)'
                title = 'Branch losses'

            elif result_type == ResultTypes.BranchReactiveLosses:
                data = self.losses[:, indices].imag
                y_label = '(MVAr)'
                title = 'Branch losses'

            elif result_type == ResultTypes.BranchVoltage:
                data = np.abs(self.Vbranch[:, indices])
                y_label = '(p.u.)'
                title = result_type.value[0]

            elif result_type == ResultTypes.BranchAngles:
                data = np.angle(self.Vbranch[:, indices], deg=True)
                y_label = '(deg)'
                title = result_type.value[0]

            elif result_type == ResultTypes.BatteryPower:
                data = np.zeros_like(self.losses[:, indices])
                y_label = '$\Delta$ (MVA)'
                title = 'Battery power'

            elif result_type == ResultTypes.SimulationError:
                data = self.error.reshape(-1, 1)
                y_label = 'p.u.'
                labels = ['Error']
                title = 'Error'

            else:
                raise Exception('Result type not understood:' + str(result_type))

            if self.time is not None:
                index = self.time
            else:
                index = list(range(data.shape[0]))

            # assemble model
            mdl = ResultsModel(data=data, index=index, columns=labels, title=title, ylabel=y_label, units=y_label)
            return mdl

        else:
            return None


def kmeans_case_sampling(X, n_points=10):
    """
    K-Means clustering
    :param X: injections matrix (time, bus)
    :param n_points: number of clusters
    :return: indices of the closest to the cluster centers, deviation of the closest representatives
    """

    # declare the model
    model = KMeans(n_clusters=n_points)

    # model fitting
    model.fit(X)

    centers = model.cluster_centers_
    labels = model.labels_

    # get the closest indices to the cluster centers
    closest_idx = np.zeros(n_points, dtype=int)
    closest_prob = np.zeros(n_points, dtype=float)
    nt = X.shape[0]

    unique_labels, counts = np.unique(labels, return_counts=True)
    probabilities = counts.astype(float) / float(nt)

    prob_dict = {u: p for u, p in zip(unique_labels, probabilities)}
    for i in range(n_points):
        deviations = np.sum(np.power(X - centers[i, :], 2.0), axis=1)
        idx = deviations.argmin()
        closest_idx[i] = idx

    # sort the indices
    closest_idx = np.sort(closest_idx)

    # compute the probabilities of each index (sorted already)
    for i, idx in enumerate(closest_idx):
        lbl = model.predict(X[idx, :].reshape(1, -1))[0]
        prob = prob_dict[lbl]
        closest_prob[i] = prob

    return closest_idx, closest_prob


def time_series_worker(n, m, time_profile, namespace, options: PowerFlowOptions,
                       time_indices, logger: Logger) -> (TimeSeriesResults, np.array):
    """

    :param n:
    :param m:
    :param time_profile:
    :param buses:
    :param numerical_circuit:
    :param options:
    :param time_indices:  array of time indices to consider
    :param logger:
    :return: TimeSeriesResults instance
    """

    # initialize the grid time series results we will append the island results with another function
    time_series_results = TimeSeriesResults(n, m, time_array=time_profile[time_indices])

    calc_inputs_dict = namespace.calc_inputs_dict
    time_series_results.bus_types = namespace.bus_types

    # for each partition of the profiles...
    for t_key, calc_inputs in calc_inputs_dict.items():

        # For every island, run the time series
        for island_index, calculation_input in enumerate(calc_inputs):

            # find the original indices
            bus_original_idx = calculation_input.original_bus_idx
            branch_original_idx = calculation_input.original_branch_idx

            # if there are valid profiles...
            if time_profile is not None:

                # declare a results object for the partition
                results = TimeSeriesResults(n=calculation_input.nbus,
                                            m=calculation_input.nbr,
                                            time_array=time_profile[time_indices])
                last_voltage = calculation_input.Vbus

                # default value in case of single-valued profile
                dt = 1.0

                # traverse the time profiles of the partition and simulate each time step
                for it, t in enumerate(time_indices):

                    # set the power values
                    # if the storage dispatch option is active, the batteries power is not included
                    # therefore, it shall be included after processing
                    Ysh = calculation_input.Ysh_prof[:, it]
                    I = calculation_input.Ibus_prof[:, it]
                    S = calculation_input.Sbus_prof[:, it]
                    branch_rates = calculation_input.branch_rates_prof[it, :]

                    # add the controlled storage power if we are controlling the storage devices
                    if options.dispatch_storage:

                        if (it+1) < len(calculation_input.original_time_idx):
                            # compute the time delta: the time values come in nanoseconds
                            dt = (calculation_input.time_array[it + 1]
                                  - calculation_input.time_array[it]).value * 1e-9 / 3600.0

                    # run power flow at the circuit
                    res = single_island_pf(circuit=calculation_input,
                                           Vbus=last_voltage,
                                           Sbus=S,
                                           Ibus=I,
                                           branch_rates=branch_rates,
                                           options=options,
                                           logger=logger)

                    # store circuit results at the time index 'it'
                    results.set_at(it, res)

                # merge the circuit's results
                time_series_results.apply_from_island(results,
                                                      bus_original_idx,
                                                      branch_original_idx,
                                                      time_indices,
                                                      'TS')
    return time_series_results, time_indices


class TimeSeries(QThread):
    progress_signal = Signal(float)
    progress_text = Signal(str)
    done_signal = Signal()
    name = 'Time Series'

    def __init__(self, grid: MultiCircuit, options: PowerFlowOptions, opf_time_series_results=None,
                 start_=0, end_=None, use_clustering=False, cluster_number=10):
        """
        TimeSeries constructor
        @param grid: MultiCircuit instance
        @param options: PowerFlowOptions instance
        """
        QThread.__init__(self)

        # reference the grid directly
        self.grid = grid

        self.options = options

        self.opf_time_series_results = opf_time_series_results

        self.results = None

        self.start_ = start_

        self.end_ = end_

        self.use_clustering = use_clustering

        self.cluster_number = cluster_number

        self.elapsed = 0

        self.logger = Logger()

        self.returned_results = list()

        self.pool = None

        self._mt_i = 0
        self._mt_n = 1

        self.__cancel__ = False

    def get_steps(self):
        """
        Get time steps list of strings
        """
        return [l.strftime('%d-%m-%Y %H:%M') for l in pd.to_datetime(self.grid.time_profile[self.start_: self.end_])]

    def run_single_thread(self, time_indices) -> TimeSeriesResults:
        """
        Run single thread time series
        :param time_indices: array of time indices to consider
        :return: TimeSeriesResults instance
        """

        # initialize the grid time series results we will append the island results with another function

        n = len(self.grid.buses)
        m = len(self.grid.branches)
        time_series_results = TimeSeriesResults(n, m, time_array=self.grid.time_profile[time_indices])

        # compile the multi-circuit
        numerical_circuit = self.grid.compile_time_series(opf_time_series_results=self.opf_time_series_results)

        # do the topological computation
        calc_inputs_dict = numerical_circuit.compute(branch_tolerance_mode=self.options.branch_impedance_tolerance_mode,
                                                     ignore_single_node_islands=self.options.ignore_single_node_islands)

        time_series_results.bus_types = numerical_circuit.bus_types

        # for each partition of the profiles...
        for t_key, calc_inputs in calc_inputs_dict.items():

            # For every island, run the time series
            for island_index, calculation_input in enumerate(calc_inputs):

                # Are we dispatching storage? if so, generate a dictionary of battery -> bus index
                # to be able to set the batteries values into the vector S
                batteries = list()
                batteries_bus_idx = list()
                if self.options.dispatch_storage:
                    for k, bus in enumerate(self.grid.buses):
                        for battery in bus.batteries:
                            battery.reset()  # reset the calculation values
                            batteries.append(battery)
                            batteries_bus_idx.append(k)

                self.progress_text.emit('Time series at circuit ' + str(island_index) + '...')

                # find the original indices
                bus_original_idx = calculation_input.original_bus_idx
                branch_original_idx = calculation_input.original_branch_idx

                # if there are valid profiles...
                if self.grid.time_profile is not None:

                    # declare a results object for the partition
                    results = TimeSeriesResults(n=calculation_input.nbus,
                                                m=calculation_input.nbr,
                                                time_array=self.grid.time_profile[time_indices])
                    last_voltage = calculation_input.Vbus

                    self.progress_signal.emit(0.0)

                    # default value in case of single-valued profile
                    dt = 1.0

                    # traverse the time profiles of the partition and simulate each time step
                    for it, t in enumerate(time_indices):

                        # set the power values
                        # if the storage dispatch option is active, the batteries power is not included
                        # therefore, it shall be included after processing
                        Ysh = calculation_input.Ysh_prof[:, it]
                        I = calculation_input.Ibus_prof[:, it]
                        S = calculation_input.Sbus_prof[:, it]
                        branch_rates = calculation_input.branch_rates_prof[it, :]

                        # add the controlled storage power if we are controlling the storage devices
                        if self.options.dispatch_storage:

                            if (it+1) < len(calculation_input.original_time_idx):
                                # compute the time delta: the time values come in nanoseconds
                                dt = (calculation_input.time_array[it + 1]
                                      - calculation_input.time_array[it]).value * 1e-9 / 3600.0

                            for k, battery in enumerate(batteries):

                                power = battery.get_processed_at(it, dt=dt, store_values=True)

                                bus_idx = batteries_bus_idx[k]

                                S[bus_idx] += power / calculation_input.Sbase

                        # run power flow at the circuit
                        res = single_island_pf(circuit=calculation_input, Vbus=last_voltage, Sbus=S, Ibus=I,
                                               branch_rates=branch_rates,
                                               options=self.options, logger=self.logger)

                        # Recycle voltage solution
                        # last_voltage = res.voltage

                        # store circuit results at the time index 'it'
                        results.set_at(it, res)

                        progress = ((t - self.start_ + 1) / (self.end_ - self.start_)) * 100
                        self.progress_signal.emit(progress)
                        self.progress_text.emit('Simulating island ' + str(island_index)
                                                + ' at ' + str(self.grid.time_profile[t]))

                        if self.__cancel__:
                            # merge the circuit's results
                            time_series_results.apply_from_island(results,
                                                                  bus_original_idx,
                                                                  branch_original_idx,
                                                                  time_indices,
                                                                  'TS')
                            # abort by returning at this point
                            return time_series_results

                    # merge the circuit's results
                    time_series_results.apply_from_island(results,
                                                          bus_original_idx,
                                                          branch_original_idx,
                                                          time_indices,
                                                          'TS')

                else:
                    print('There are no profiles')
                    self.progress_text.emit('There are no profiles')

        return time_series_results

    def run_single_thread_clustering(self, time_indices) -> TimeSeriesResults:
        """
        Run single thread time series using the time series clustering
        :param time_indices: array of time indices to consider
        :return: TimeSeriesResults instance
        """
        # compile the multi-circuit
        numerical_circuit = self.grid.compile_time_series(opf_time_series_results=self.opf_time_series_results)

        self.progress_text.emit('Clustering...')
        X = numerical_circuit.get_power_injections()
        X = X[:, time_indices].real.T
        time_idx, closest_prob = kmeans_case_sampling(X, n_points=self.cluster_number)

        time_series_results = self.run_single_thread(time_indices=time_idx)

        return time_series_results

    def update_prog(self):
        self._mt_i += 1
        progress = (self._mt_i + 1) / self._mt_n * 100
        self.progress_signal.emit(progress)

    def collect_mt_result(self, res):
        """

        :param res:
        :return:
        """
        self.returned_results.append(res)

    def run_multi_thread_old(self, time_indices) -> TimeSeriesResults:
        """
        Run multi thread time series
        :param time_indices: array of time indices to consider
        :return: TimeSeriesResults instance
        """

        # initialize the grid time series results, we will append the island results with another function
        n = len(self.grid.buses)
        m = len(self.grid.branches)
        time_series_results = TimeSeriesResults(n, m, time_array=self.grid.time_profile[time_indices])

        n_cores = multiprocessing.cpu_count()
        self.pool = multiprocessing.Pool()

        # compile the multi-circuit
        numerical_circuit = self.grid.compile_time_series(opf_time_series_results=self.opf_time_series_results)

        # perform the topological computation
        calc_inputs_dict = numerical_circuit.compute(branch_tolerance_mode=self.options.branch_impedance_tolerance_mode,
                                                     ignore_single_node_islands=self.options.ignore_single_node_islands)

        # for each partition of the profiles...
        for t_key, calc_inputs in calc_inputs_dict.items():

            # For every island, run the time series
            for island_index, calculation_input in enumerate(calc_inputs):

                self.progress_text.emit('Time series at circuit ' + str(island_index) + '...')

                # Start jobs
                self.returned_results = list()

                # if there are valid profiles...
                if self.grid.time_profile is not None:

                    # declare a results object for the partition
                    results = TimeSeriesResults(n=calculation_input.nbus,
                                                m=calculation_input.nbr,
                                                time_array=self.grid.time_profile[time_indices])
                    Vbus = calculation_input.Vbus

                    self.progress_signal.emit(0.0)

                    # traverse the time profiles of the partition and simulate each time step
                    for it, t in enumerate(time_indices):

                        # set the power values
                        # if the storage dispatch option is active, the batteries power is not included
                        # therefore, it shall be included after processing
                        Ysh = calculation_input.Ysh_prof[:, it]
                        Ibus = calculation_input.Ibus_prof[:, it]
                        Sbus = calculation_input.Sbus_prof[:, it]
                        branch_rates = calculation_input.branch_rates_prof[t, :]

                        args = (it, self.options, calculation_input, Vbus, Sbus, Ibus, branch_rates)
                        self.pool.apply_async(power_flow_worker_args, (args,), callback=self.collect_mt_result)

                    # wait for all jobs to complete
                    self.pool.close()
                    self.pool.join()

                    # collect results
                    self.progress_text.emit('Collecting results...')
                    for it, res in self.returned_results:
                        # store circuit results at the time index 't'
                        results.set_at(it, res)

                    # merge  the circuit's results
                    time_series_results.apply_from_island(results,
                                                          calculation_input.original_bus_idx,
                                                          calculation_input.original_branch_idx,
                                                          time_indices,
                                                          'TS multi-thread')

                else:
                    print('There are no profiles')
                    self.progress_text.emit('There are no profiles')

        return time_series_results

    def run_multi_thread(self, time_indices) -> TimeSeriesResults:

        # initialize the grid time series results, we will append the island results with another function
        n = len(self.grid.buses)
        m = len(self.grid.branches)
        nt = len(time_indices)
        time_series_results = TimeSeriesResults(n, m, time_array=self.grid.time_profile[time_indices])

        # compile the multi-circuit
        self.progress_text.emit('Compiling time series...')
        numerical_circuit = self.grid.compile_time_series(opf_time_series_results=self.opf_time_series_results)

        # compute the time indices per process
        n_cores = multiprocessing.cpu_count()
        nchunk = int(nt / n_cores)
        time_chunks = list()
        k = 0
        while k < (nt - nchunk * 2):
            k2 = k+nchunk
            if k2 > nt:
                k2 = nt
            time_chunk = time_indices[k:k2]
            k += nchunk
            time_chunks.append(time_chunk)
        time_chunks.append(time_indices[k::])  # add the last chunk

        # schedule jobs
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Running in parallel...')
        self.pool = multiprocessing.Pool()
        manager = multiprocessing.Manager()
        namespace = manager.Namespace()

        stuff = list()

        calc_inputs_dict = numerical_circuit.compute(branch_tolerance_mode=self.options.branch_impedance_tolerance_mode,
                                                     ignore_single_node_islands=self.options.ignore_single_node_islands)

        namespace.calc_inputs_dict = calc_inputs_dict
        namespace.bus_types = numerical_circuit.bus_types

        for time_chunk in time_chunks:
            # n, m, time_profile, buses, numerical_circuit, options, time_indices, logger
            args = (n, m, self.grid.time_profile, namespace, self.options, time_chunk, self.logger)
            p = self.pool.apply_async(func=time_series_worker, args=args, callback=self.collect_mt_result)
            stuff.append(p)

        # wait for all jobs to complete
        self.pool.close()
        self.pool.join()

        # collect results
        self.progress_text.emit('Collecting results...')
        for result, time_chunk in self.returned_results:
            # merge  the circuit's results
            time_series_results.apply_from_island(result,
                                                  np.arange(n),
                                                  np.arange(m),
                                                  time_chunk,
                                                  'TS multi-thread')
        self.progress_signal.emit(100.0)
        return time_series_results

    def run(self):
        """
        Run the time series simulation
        @return:
        """

        a = time.time()

        if self.end_ is None:
            self.end_ = len(self.grid.time_profile)
        time_indices = np.arange(self.start_, self.end_)

        if self.options.multi_thread:
            self.results = self.run_multi_thread(time_indices)
        else:
            if self.use_clustering:
                self.results = self.run_single_thread_clustering(time_indices)
            else:
                self.results = self.run_single_thread(time_indices)

        self.elapsed = time.time() - a

        # send the finnish signal
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Done!')
        self.done_signal.emit()

    def cancel(self):
        """
        Cancel the simulation
        """
        self.__cancel__ = True
        if self.pool is not None:
            self.pool.terminate()
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Cancelled!')
        self.done_signal.emit()


class SampledTimeSeries(QThread):
    progress_signal = Signal(float)
    progress_text = Signal(str)
    done_signal = Signal()
    name = 'Time Series'

    def __init__(self, grid: MultiCircuit, options: PowerFlowOptions, opf_time_series_results=None,
                 number_of_steps=10):
        """
        TimeSeries constructor
        @param grid: MultiCircuit instance
        @param options: PowerFlowOptions instance
        """
        QThread.__init__(self)

        # reference the grid directly
        self.grid = grid

        self.options = options

        self.opf_time_series_results = opf_time_series_results

        self.results = None

        self.number_of_steps = number_of_steps

        self.elapsed = 0

        self.logger = Logger()

        self.returned_results = list()

        self.pool = None

        self.steps = self.sample_steps()

        self.__cancel__ = False

    def get_steps(self):
        """
        Get time steps list of strings
        """
        return [l.strftime('%d-%m-%Y %H:%M') for l in pd.to_datetime(self.grid.time_profile[self.steps])]

    def sample_steps(self):

        n = len(self.grid.time_profile)
        points = (np.sort(lhs(self.number_of_steps, 1)[0]) * n).astype(int)

        return points

    def run_single_thread(self) -> TimeSeriesResults:
        """
        Run single thread time series
        :return: TimeSeriesResults instance
        """

        # initialize the grid time series results we will append the island results with another function
        n = len(self.grid.buses)
        m = len(self.grid.branches)
        nt = self.number_of_steps
        time_series_results = TimeSeriesResults(n, m, nt, start=0, end=self.number_of_steps,
                                                time_array=self.grid.time_profile[self.steps])

        # compile the multi-circuit
        numerical_circuit = self.grid.compile_time_series(opf_time_series_results=self.opf_time_series_results)

        # do the topological computation
        calc_inputs_dict = numerical_circuit.compute(branch_tolerance_mode=self.options.branch_impedance_tolerance_mode,
                                                     ignore_single_node_islands=self.options.ignore_single_node_islands)

        time_series_results.bus_types = numerical_circuit.bus_types

        # for each partition of the profiles...
        for t_key, calc_inputs in calc_inputs_dict.items():

            # For every island, run the time series
            for island_index, calculation_input in enumerate(calc_inputs):

                # Are we dispatching storage? if so, generate a dictionary of battery -> bus index
                # to be able to set the batteries values into the vector S
                batteries = list()
                batteries_bus_idx = list()
                if self.options.dispatch_storage:
                    for k, bus in enumerate(self.grid.buses):
                        for battery in bus.batteries:
                            battery.reset()  # reset the calculation values
                            batteries.append(battery)
                            batteries_bus_idx.append(k)

                self.progress_text.emit('Time series at circuit ' + str(island_index) + '...')

                # find the original indices
                bus_original_idx = calculation_input.original_bus_idx
                branch_original_idx = calculation_input.original_branch_idx

                # if there are valid profiles...
                if self.grid.time_profile is not None:

                    # declare a results object for the partition
                    # nt = calculation_input.ntime
                    n = calculation_input.nbus
                    m = calculation_input.nbr
                    results = TimeSeriesResults(n, m, nt, 0, nt)
                    last_voltage = calculation_input.Vbus

                    self.progress_signal.emit(0.0)

                    # default value in case of single-valued profile
                    dt = 1.0

                    # traverse the time profiles of the partition and simulate each time step
                    for it, t in enumerate(self.steps):

                        # set the power values
                        # if the storage dispatch option is active, the batteries power is not included
                        # therefore, it shall be included after processing
                        Ysh = calculation_input.Ysh_prof[:, t]
                        I = calculation_input.Ibus_prof[:, t]
                        S = calculation_input.Sbus_prof[:, t]
                        branch_rates = calculation_input.branch_rates_prof[t, :]

                        # add the controlled storage power if we are controlling the storage devices
                        if self.options.dispatch_storage:

                            if (it+1) < len(calculation_input.original_time_idx):
                                # compute the time delta: the time values come in nanoseconds
                                dt = (calculation_input.time_array[it + 1]
                                      - calculation_input.time_array[it]).value * 1e-9 / 3600.0

                            for k, battery in enumerate(batteries):

                                power = battery.get_processed_at(it, dt=dt, store_values=True)

                                bus_idx = batteries_bus_idx[k]

                                S[bus_idx] += power / calculation_input.Sbase
                        else:
                            pass

                        # run power flow at the circuit
                        res = single_island_pf(circuit=calculation_input, Vbus=last_voltage, Sbus=S, Ibus=I,
                                               branch_rates=branch_rates,
                                               options=self.options, logger=self.logger)

                        # Recycle voltage solution
                        # last_voltage = res.voltage

                        # store circuit results at the time index 't'
                        results.set_at(it, res)

                        progress = ((it + 1) / self.number_of_steps) * 100
                        self.progress_signal.emit(progress)
                        self.progress_text.emit('Simulating island ' + str(island_index)
                                                + ' at ' + str(self.grid.time_profile[t]))

                    if self.__cancel__:
                        # merge the circuit's results
                        time_series_results.apply_from_island(results,
                                                              bus_original_idx,
                                                              branch_original_idx,
                                                              np.array(range(self.number_of_steps)), #np.array(calculation_input.original_time_idx)[self.steps],
                                                              'TS')
                        # abort by returning at this point
                        return time_series_results

                    # merge the circuit's results
                    time_series_results.apply_from_island(results,
                                                          bus_original_idx,
                                                          branch_original_idx,
                                                          np.array(range(self.number_of_steps)),
                                                          'TS')

                else:
                    print('There are no profiles')
                    self.progress_text.emit('There are no profiles')

        return time_series_results

    def update_progress_mt(self, res):
        """

        :param res:
        :return:
        """
        t, _ = res
        progress = ((t - self.start_ + 1) / (self.end_ - self.start_)) * 100
        self.progress_signal.emit(progress)
        self.returned_results.append(res)

    def run_multi_thread(self) -> TimeSeriesResults:
        """
        Run multi thread time series
        :return: TimeSeriesResults instance
        """

        # initialize the grid time series results, we will append the island results with another function
        n = len(self.grid.buses)
        m = len(self.grid.branches)
        nt = len(self.grid.time_profile)
        time_series_results = TimeSeriesResults(n, m, nt, self.start_, self.end_, time_array=self.grid.time_profile)

        if self.end_ is None:
            self.end_ = nt

        n_cores = multiprocessing.cpu_count()
        self.pool = multiprocessing.Pool()

        # compile the multi-circuit
        numerical_circuit = self.grid.compile_time_series(opf_time_series_results=self.opf_time_series_results)

        # perform the topological computation
        calc_inputs_dict = numerical_circuit.compute(branch_tolerance_mode=self.options.branch_impedance_tolerance_mode,
                                                     ignore_single_node_islands=self.options.ignore_single_node_islands)

        # for each partition of the profiles...
        for t_key, calc_inputs in calc_inputs_dict.items():

            # For every island, run the time series
            for island_index, calculation_input in enumerate(calc_inputs):

                self.progress_text.emit('Time series at circuit ' + str(island_index) + '...')

                # Start jobs
                self.returned_results = list()

                # if there are valid profiles...
                if self.grid.time_profile is not None:

                    # declare a results object for the partition
                    nt = calculation_input.ntime
                    n = calculation_input.nbus
                    m = calculation_input.nbr
                    results = TimeSeriesResults(n, m, nt, self.start_, self.end_)
                    Vbus = calculation_input.Vbus

                    self.progress_signal.emit(0.0)

                    # traverse the time profiles of the partition and simulate each time step
                    for it, t in enumerate(calculation_input.original_time_idx):

                        if (t >= self.start_) and (t < self.end_):

                            # set the power values
                            # if the storage dispatch option is active, the batteries power is not included
                            # therefore, it shall be included after processing
                            Ysh = calculation_input.Ysh_prof[:, it]
                            Ibus = calculation_input.Ibus_prof[:, it]
                            Sbus = calculation_input.Sbus_prof[:, it]
                            branch_rates = calculation_input.branch_rates_prof[t, :]

                            args = (t, self.options, calculation_input, Vbus, Sbus, Ibus, branch_rates)
                            self.pool.apply_async(power_flow_worker_args, (args,), callback=self.update_progress_mt)

                    # wait for all jobs to complete
                    self.pool.close()
                    self.pool.join()

                    # collect results
                    self.progress_text.emit('Collecting results...')
                    for t, res in self.returned_results:
                        # store circuit results at the time index 't'
                        results.set_at(t, res)

                    # merge  the circuit's results
                    time_series_results.apply_from_island(results,
                                                          calculation_input.original_bus_idx,
                                                          calculation_input.original_branch_idx,
                                                          calculation_input.original_time_idx,
                                                          'TS multi-thread')

                else:
                    print('There are no profiles')
                    self.progress_text.emit('There are no profiles')

        return time_series_results

    def run(self):
        """
        Run the time series simulation
        @return:
        """

        a = time.time()
        if self.options.multi_thread:
            self.results = self.run_multi_thread()
        else:
            self.results = self.run_single_thread()

        self.elapsed = time.time() - a

        # send the finnish signal
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Done!')
        self.done_signal.emit()

    def cancel(self):
        """
        Cancel the simulation
        """
        self.__cancel__ = True
        if self.pool is not None:
            self.pool.terminate()
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Cancelled!')
        self.done_signal.emit()
