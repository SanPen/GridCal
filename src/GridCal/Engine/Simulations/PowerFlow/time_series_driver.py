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

import pickle as pkl
import pandas as pd
from numpy import complex, zeros, ones, array, zeros_like
import multiprocessing
from matplotlib import pyplot as plt

from PySide2.QtCore import QThread, Signal

from GridCal.Engine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from GridCal.Engine.Simulations.result_types import ResultTypes
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.plot_config import LINEWIDTH
from GridCal.Engine.Simulations.PowerFlow.power_flow_driver import power_flow_worker, PowerFlowOptions, PowerFlowMP


class TimeSeriesResults(PowerFlowResults):

    def __init__(self, n, m, nt, start, end, time=None):
        """
        TimeSeriesResults constructor
        @param n: number of buses
        @param m: number of branches
        @param nt: number of time steps
        """
        PowerFlowResults.__init__(self)

        self.nt = nt
        self.m = m
        self.n = n
        self.start = start
        self.end = end

        self.time = time

        self.bus_types = zeros(n, dtype=int)

        if nt > 0:
            self.voltage = zeros((nt, n), dtype=complex)

            self.S = zeros((nt, n), dtype=complex)

            self.Sbranch = zeros((nt, m), dtype=complex)

            self.Ibranch = zeros((nt, m), dtype=complex)

            self.loading = zeros((nt, m), dtype=complex)

            self.losses = zeros((nt, m), dtype=complex)

            self.flow_direction = zeros((nt, m), dtype=float)

            self.error = zeros(nt)

            self.converged = ones(nt, dtype=bool)  # guilty assumption

            # self.Qpv = Qpv

            self.overloads = [None] * nt

            self.overvoltage = [None] * nt

            self.undervoltage = [None] * nt

            self.overloads_idx = [None] * nt

            self.overvoltage_idx = [None] * nt

            self.undervoltage_idx = [None] * nt

            self.buses_useful_for_storage = [None] * nt

        else:
            self.voltage = None

            self.S = None

            self.Sbranch = None

            self.Ibranch = None

            self.loading = None

            self.losses = None

            self.flow_direction = None

            self.error = None

            self.converged = None

            # self.Qpv = Qpv

            self.overloads = None

            self.overvoltage = None

            self.undervoltage = None

            self.overloads_idx = None

            self.overvoltage_idx = None

            self.undervoltage_idx = None

            self.buses_useful_for_storage = None

        self.available_results = [ResultTypes.BusVoltage,
                                  ResultTypes.BusActivePower,
                                  ResultTypes.BusReactivePower,
                                  ResultTypes.BranchPower,
                                  ResultTypes.BranchCurrent,
                                  ResultTypes.BranchLoading,
                                  ResultTypes.BranchLosses,
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

        self.loading[t, :] = results.loading

        self.losses[t, :] = results.losses

        self.flow_direction[t, :] = results.flow_direction

        self.error[t] = max(results.error)

        self.converged[t] = min(results.converged)

        # self.Qpv = Qpv

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

    def apply_from_island(self, results, b_idx, br_idx, index, grid_idx):
        """
        Apply results from another island circuit to the circuit results represented here
        @param results: PowerFlowResults
        @param b_idx: bus original indices
        @param br_idx: branch original indices
        @return:
        """

        self.voltage[:, b_idx] = results.voltage

        self.S[:, b_idx] = results.S

        self.Sbranch[:, br_idx] = results.Sbranch

        self.Ibranch[:, br_idx] = results.Ibranch

        self.loading[:, br_idx] = results.loading

        self.losses[:, br_idx] = results.losses

        self.flow_direction[:, br_idx] = results.flow_direction

        if (results.error > self.error).any():
            self.error += results.error

        self.converged = self.converged * results.converged

    def get_results_dict(self):
        """
        Returns a dictionary with the results sorted in a dictionary
        :return: dictionary of 2D numpy arrays (probably of complex numbers)
        """
        data = {'V': self.voltage,
                'S': self.S,
                'Sbr': self.Sbranch,
                'Ibr': self.Ibranch,
                'loading': self.loading,
                'losses': self.losses}
        return data

    def save(self, fname):
        """
        Export as pickle
        """

        with open(fname, "wb") as output_file:
            pkl.dump(self.get_results_dict(), output_file)

    def analyze(self):
        """
        Analyze the results
        @return:
        """
        branch_overload_frequency = zeros(self.m)
        bus_undervoltage_frequency = zeros(self.n)
        bus_overvoltage_frequency = zeros(self.n)
        buses_selected_for_storage_frequency = zeros(self.n)
        for i in range(self.nt):
            branch_overload_frequency[self.overloads_idx[i]] += 1
            bus_undervoltage_frequency[self.undervoltage_idx[i]] += 1
            bus_overvoltage_frequency[self.overvoltage_idx[i]] += 1
            buses_selected_for_storage_frequency[self.buses_useful_for_storage[i]] += 1

        return branch_overload_frequency, bus_undervoltage_frequency, bus_overvoltage_frequency, \
                buses_selected_for_storage_frequency

    def plot(self, result_type: ResultTypes, ax=None, indices=None, names=None):
        """
        Plot the results
        :param result_type:
        :param ax:
        :param indices:
        :param names:
        :return:
        """

        if ax is None:
            fig = plt.figure()
            ax = fig.add_subplot(111)

        if indices is None:
            indices = array(range(len(names)))

        if len(indices) > 0:

            labels = names[indices]

            if result_type == ResultTypes.BusVoltage:
                data = self.voltage[:, indices]
                y_label = '(p.u.)'
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

            elif result_type == ResultTypes.BranchCurrent:
                data = self.Ibranch[:, indices]
                y_label = '(kA)'
                title = 'Branch current '

            elif result_type == ResultTypes.BranchLoading:
                data = self.loading[:, indices] * 100
                y_label = '(%)'
                title = 'Branch loading '

            elif result_type == ResultTypes.BranchLosses:
                data = self.losses[:, indices]
                y_label = '(MVA)'
                title = 'Branch losses'

            elif result_type == ResultTypes.BatteryPower:
                data = zeros_like(self.losses[:, indices])
                y_label = '$\Delta$ (MVA)'
                title = 'Battery power'

            elif result_type == ResultTypes.SimulationError:
                data = self.error
                y_label = 'Per unit power'
                labels = [y_label]
                title = 'Error'

            else:
                raise Exception('Result type not understood:' + str(result_type))

            if self.time is not None:
                df = pd.DataFrame(data=data, columns=labels, index=self.time)
            else:
                df = pd.DataFrame(data=data, columns=labels)

            if len(df.columns) > 10:
                df.abs().plot(ax=ax, linewidth=LINEWIDTH, legend=False)
            else:
                df.abs().plot(ax=ax, linewidth=LINEWIDTH, legend=True)

            ax.set_title(title)
            ax.set_ylabel(y_label)
            ax.set_xlabel('Time')

            return df

        else:
            return None


class TimeSeries(QThread):
    progress_signal = Signal(float)
    progress_text = Signal(str)
    done_signal = Signal()

    def __init__(self, grid: MultiCircuit, options: PowerFlowOptions, use_opf_vals=False, opf_time_series_results=None,
                 start_=0, end_=None):
        """
        TimeSeries constructor
        @param grid: MultiCircuit instance
        @param options: PowerFlowOptions instance
        """
        QThread.__init__(self)

        # reference the grid directly
        self.grid = grid

        self.options = options

        self.use_opf_vals = use_opf_vals

        self.opf_time_series_results = opf_time_series_results

        self.results = None

        self.start_ = start_

        self.end_ = end_

        self.__cancel__ = False

    def get_steps(self):
        """
        Get time steps list of strings
        """
        return [l.strftime('%d-%m-%Y %H:%M') for l in pd.to_datetime(self.grid.time_profile)]

    def run_single_thread(self) -> TimeSeriesResults:
        """
        Run single thread time series
        :return: TimeSeriesResults instance
        """
        # initialize the power flow
        power_flow = PowerFlowMP(self.grid, self.options)

        # initialize the grid time series results we will append the island results with another function
        n = len(self.grid.buses)
        m = len(self.grid.branches)
        nt = len(self.grid.time_profile)
        time_series_results = TimeSeriesResults(n, m, nt, self.start_, self.end_, time=self.grid.time_profile)
        if self.end_ is None:
            self.end_ = nt

        # compile the multi-circuit
        numerical_circuit = self.grid.compile(use_opf_vals=self.use_opf_vals,
                                              opf_time_series_results=self.opf_time_series_results)

        # do the topological computation
        calc_inputs_dict = numerical_circuit.compute_ts(branch_tolerance_mode=
                                                        self.options.branch_impedance_tolerance_mode)

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
                    nt = calculation_input.ntime
                    n = calculation_input.nbus
                    m = calculation_input.nbr
                    results = TimeSeriesResults(n, m, nt, self.start_, self.end_)
                    last_voltage = calculation_input.Vbus

                    self.progress_signal.emit(0.0)

                    # default value in case of single-valued profile
                    dt = 1.0

                    # traverse the time profiles of the partition and simulate each time step
                    for it, t in enumerate(calculation_input.original_time_idx):

                        if (t >= self.start_) and (t < self.end_):

                            # set the power values
                            # if the storage dispatch option is active, the batteries power is not included
                            # therefore, it shall be included after processing
                            Ysh = calculation_input.Ysh_prof[:, it]
                            I = calculation_input.Ibus_prof[:, it]
                            S = calculation_input.Sbus_prof[:, it]

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
                            res = power_flow.run_pf(circuit=calculation_input, Vbus=last_voltage, Sbus=S, Ibus=I)

                            # Recycle voltage solution
                            last_voltage = res.voltage

                            # store circuit results at the time index 't'
                            results.set_at(t, res)

                            progress = ((t - self.start_ + 1) / (self.end_ - self.start_)) * 100
                            self.progress_signal.emit(progress)
                            self.progress_text.emit('Simulating island ' + str(island_index)
                                                    + ' at ' + str(self.grid.time_profile[t]))

                        else:
                            pass

                        if self.__cancel__:
                            # merge the circuit's results
                            time_series_results.apply_from_island(results,
                                                                  bus_original_idx,
                                                                  branch_original_idx,
                                                                  calculation_input.time_array,
                                                                  'TS')
                            # abort by returning at this point
                            return time_series_results

                    # merge the circuit's results
                    time_series_results.apply_from_island(results,
                                                          bus_original_idx,
                                                          branch_original_idx,
                                                          calculation_input.time_array,
                                                          'TS')

                else:
                    print('There are no profiles')
                    self.progress_text.emit('There are no profiles')

        return time_series_results

    def run_multi_thread(self) -> TimeSeriesResults:
        """
        Run multi thread time series
        :return: TimeSeriesResults instance
        """

        # initialize the grid time series results, we will append the island results with another function
        n = len(self.grid.buses)
        m = len(self.grid.branches)
        nt = len(self.grid.time_profile)
        time_series_results = TimeSeriesResults(n, m, nt, self.start_, self.end_, time=self.grid.time_profile)

        if self.end_ is None:
            self.end_ = nt

        n_cores = multiprocessing.cpu_count()

        # compile the multi-circuit
        numerical_circuit = self.grid.compile(use_opf_vals=self.use_opf_vals,
                                              opf_time_series_results=self.opf_time_series_results)

        # perform the topological computation
        calc_inputs_dict = numerical_circuit.compute_ts(branch_tolerance_mode=
                                                        self.options.branch_impedance_tolerance_mode)

        jobs = list()

        if len(calc_inputs_dict) == 1:

            # there is only one partition
            calc_inputs = calc_inputs_dict[0]

            # For every circuit, run the time series
            for island_index, calculation_input in enumerate(calc_inputs):

                self.progress_text.emit('Time series at circuit ' + str(island_index)
                                        + ' in parallel using ' + str(n_cores) + ' cores ...')

                if nt > 0:

                    nt = calculation_input.ntime
                    n = calculation_input.nbus
                    m = calculation_input.nbr
                    results = TimeSeriesResults(n, m, nt, self.start_, self.end_)
                    last_voltage = calculation_input.Vbus

                    self.progress_signal.emit(0.0)

                    # Start jobs
                    manager = multiprocessing.Manager()
                    return_dict = manager.dict()

                    t = self.start_
                    while t < self.end_ and not self.__cancel__:

                        k = 0

                        # launch only n_cores jobs at the time
                        while k < n_cores + 2 and (t + k) < nt:

                            # set the power values
                            Ysh = calculation_input.Ysh_prof[:, t]
                            I = calculation_input.Ibus_prof[:, t]
                            S = calculation_input.Sbus_prof[:, t]

                            # run power flow at the circuit
                            p = multiprocessing.Process(target=power_flow_worker, args=(t, self.options,
                                                                                        calculation_input,
                                                                                        last_voltage, S,
                                                                                        I, return_dict))
                            jobs.append(p)
                            p.start()
                            k += 1
                            t += 1

                        # wait for all jobs to complete
                        for process_ in jobs:
                            process_.join()

                        progress = ((t - self.start_ + 1) / (self.end_ - self.start_)) * 100
                        self.progress_signal.emit(progress)

                    # collect results
                    self.progress_text.emit('Collecting results...')
                    for t in return_dict.keys():
                        # store circuit results at the time index 't'
                        results.set_at(t, return_dict[t])

                    # merge  the circuit's results
                    time_series_results.apply_from_island(results,
                                                          calculation_input.original_bus_idx,
                                                          calculation_input.original_branch_idx,
                                                          calculation_input.time_array,
                                                          'TS multi-thread')
                else:
                    print('There are no profiles')
                    self.progress_text.emit('There are no profiles')

        else:
            # there are more than one partition

            # for each partition of the profiles...
            for t_key, calc_inputs in calc_inputs_dict.items():

                # For every island, run the time series
                for island_index, calculation_input in enumerate(calc_inputs):

                    self.progress_text.emit('Time series at circuit ' + str(island_index) + '...')

                    # find the original indices
                    bus_original_idx = calculation_input.original_bus_idx
                    branch_original_idx = calculation_input.original_branch_idx

                    # Start jobs
                    manager = multiprocessing.Manager()
                    return_dict = manager.dict()

                    # if there are valid profiles...
                    if self.grid.time_profile is not None:

                        # declare a results object for the partition
                        nt = calculation_input.ntime
                        n = calculation_input.nbus
                        m = calculation_input.nbr
                        results = TimeSeriesResults(n, m, nt, self.start_, self.end_)
                        last_voltage = calculation_input.Vbus

                        self.progress_signal.emit(0.0)

                        # traverse the time profiles of the partition and simulate each time step
                        for it, t in enumerate(calculation_input.original_time_idx):

                            if (t >= self.start_) and (t < self.end_):

                                # set the power values
                                # if the storage dispatch option is active, the batteries power is not included
                                # therefore, it shall be included after processing
                                Ysh = calculation_input.Ysh_prof[:, it]
                                I = calculation_input.Ibus_prof[:, it]
                                S = calculation_input.Sbus_prof[:, it]

                                # run power flow at the circuit
                                p = multiprocessing.Process(target=power_flow_worker, args=(t, self.options,
                                                                                            calculation_input,
                                                                                            last_voltage, S,
                                                                                            I, return_dict))
                                jobs.append(p)
                                p.start()

                                # wait for all jobs to complete
                                if len(jobs) >= n_cores:
                                    for process_ in jobs:
                                        process_.join()

                                    # clear the jobs
                                    jobs = list()

                                progress = ((t - self.start_ + 1) / (self.end_ - self.start_)) * 100
                                self.progress_signal.emit(progress)
                                self.progress_text.emit('Simulating island ' + str(island_index)
                                                        + ' at ' + str(self.grid.time_profile[t]))

                            else:
                                pass

                            if self.__cancel__:

                                # collect results
                                self.progress_text.emit('Collecting results...')
                                for t in return_dict.keys():
                                    # store circuit results at the time index 't'
                                    results.set_at(t, return_dict[t])

                                # merge the circuit's results
                                time_series_results.apply_from_island(results,
                                                                      bus_original_idx,
                                                                      branch_original_idx,
                                                                      calculation_input.time_array,
                                                                      'TS')
                                # abort by returning at this point
                                return time_series_results

                        # wait for the possibly open jobs to finish
                        for process_ in jobs:
                            process_.join()

                        # collect results
                        self.progress_text.emit('Collecting results...')
                        for t in return_dict.keys():
                            # store circuit results at the time index 't'
                            results.set_at(t, return_dict[t])

                        # merge the circuit's results
                        time_series_results.apply_from_island(results,
                                                              bus_original_idx,
                                                              branch_original_idx,
                                                              calculation_input.time_array,
                                                              'TS')

                    else:
                        print('There are no profiles')
                        self.progress_text.emit('There are no profiles')

        return time_series_results

    def run(self):
        """
        Run the time series simulation
        @return:
        """

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
        self.progress_text.emit('Cancelled!')
        self.done_signal.emit()


