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


import pandas as pd
from numpy import complex, zeros, ones, array
import multiprocessing
from matplotlib import pyplot as plt

from PyQt5.QtCore import QThread, QRunnable, pyqtSignal

from GridCal.Engine.IoStructures import PowerFlowResults
from GridCal.Engine.CalculationEngine import MultiCircuit, LINEWIDTH
from GridCal.Engine.PowerFlowDriver import power_flow_worker, PowerFlowOptions, PowerFlowMP


########################################################################################################################
# Time series classes
########################################################################################################################


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

        if nt > 0:
            self.voltage = zeros((nt, n), dtype=complex)

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

            self.available_results = ['Bus voltage', 'Branch power', 'Branch current', 'Branch_loading',
                                      'Branch losses']

    def set_at(self, t, results: PowerFlowResults):
        """
        Set the results at the step t
        @param t:
        @param results:
        @return:
        """

        self.voltage[t, :] = results.voltage

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

        self.Sbranch[:, br_idx] = results.Sbranch

        self.Ibranch[:, br_idx] = results.Ibranch

        self.loading[:, br_idx] = results.loading

        self.losses[:, br_idx] = results.losses

        if (results.error > self.error).any():
            self.error = results.error

        self.converged = self.converged * results.converged

        # self.voltage = self.merge_if(self.voltage, results.voltage, index, b_idx)
        #
        # self.Sbranch = self.merge_if(self.Sbranch, results.Sbranch, index, br_idx)
        #
        # self.Ibranch = self.merge_if(self.Ibranch, results.Ibranch, index, br_idx)
        #
        # self.loading = self.merge_if(self.loading, results.loading, index, br_idx)
        #
        # self.losses = self.merge_if(self.losses, results.losses, index, br_idx)
        #
        # self.error = self.merge_if(self.error, results.error, index, [grid_idx])
        #
        # self.converged = self.merge_if(self.converged, results.converged, index, [grid_idx])

        # self.Qpv = Qpv

        # self.overloads = self.merge_if(self.voltage, results.voltage, index, b_idx)
        #
        # self.overvoltage = self.merge_if(self.voltage, results.voltage, index, b_idx)
        #
        # self.undervoltage = self.merge_if(self.voltage, results.voltage, index, b_idx)
        #
        # self.overloads_idx = None
        #
        # self.overvoltage_idx = None
        #
        # self.undervoltage_idx = None
        #
        # self.buses_useful_for_storage = None

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

        return branch_overload_frequency, bus_undervoltage_frequency, bus_overvoltage_frequency, buses_selected_for_storage_frequency

    def plot(self, result_type, ax=None, indices=None, names=None):
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
            ylabel = ''
            title = ''
            if result_type == 'Bus voltage':
                data = self.voltage[:, indices]
                ylabel = '(p.u.)'
                title = 'Bus voltage '

            elif result_type == 'Branch power':
                data = self.Sbranch[:, indices]
                ylabel = '(MVA)'
                title = 'Branch power '

            elif result_type == 'Branch current':
                data = self.Ibranch[:, indices]
                ylabel = '(kA)'
                title = 'Branch current '

            elif result_type == 'Branch_loading':
                data = self.loading[:, indices] * 100
                ylabel = '(%)'
                title = 'Branch loading '

            elif result_type == 'Branch losses':
                data = self.losses[:, indices]
                ylabel = '(MVA)'
                title = 'Branch losses'

            else:
                pass

            # df.columns = labels
            if self.time is not None:
                df = pd.DataFrame(data=data, columns=labels, index=self.time)
            else:
                df = pd.DataFrame(data=data, columns=labels)

            if len(df.columns) > 10:
                df.abs().plot(ax=ax, linewidth=LINEWIDTH, legend=False)
            else:
                df.abs().plot(ax=ax, linewidth=LINEWIDTH, legend=True)

            ax.set_title(title)
            ax.set_ylabel(ylabel)
            ax.set_xlabel('Time')

            return df

        else:
            return None


class TimeSeries(QThread):
    progress_signal = pyqtSignal(float)
    progress_text = pyqtSignal(str)
    done_signal = pyqtSignal()

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

    def run_single_thread(self):
        """
        Run single thread time series
        :return:
        """
        # initialize the power flow
        power_flow = PowerFlowMP(self.grid, self.options)

        # initialize the grid time series results
        # we will append the island results with another function
        n = len(self.grid.buses)
        m = len(self.grid.branches)
        nt = len(self.grid.time_profile)
        time_series_results = TimeSeriesResults(n, m, nt, self.start_, self.end_, time=self.grid.time_profile)
        if self.end_ is None:
            self.end_ = nt

        print('Compiling...', end='')
        numerical_circuit = self.grid.compile(use_opf_vals=self.use_opf_vals,
                                              opf_time_series_results=self.opf_time_series_results)
        calculation_inputs = numerical_circuit.compute()

        # For every circuit, run the time series
        for nc, calculation_input in enumerate(calculation_inputs):

            # make a copy of the circuit to allow controls in place
            # circuit = circuit_orig.copy()

            # are we dispatching storage? if so, generate a dictionary of battery -> bus index
            # to be able to set the batteries values into the vector S
            batteries = list()
            batteries_bus_idx = list()
            if self.options.dispatch_storage:
                for k, bus in enumerate(self.grid.buses):
                    for batt in bus.batteries:
                        batt.reset()  # reset the calculation values
                        batteries.append(batt)
                        batteries_bus_idx.append(k)

            self.progress_text.emit('Time series at circuit ' + str(nc) + '...')

            # find the original indices
            bus_original_idx = numerical_circuit.islands[nc]
            branch_original_idx = numerical_circuit.island_branches[nc]

            # if there are valid profiles...
            if self.grid.time_profile is not None:

                nt = calculation_input.ntime
                n = calculation_input.nbus
                m = calculation_input.nbr
                results = TimeSeriesResults(n, m, nt, self.start_, self.end_)
                Vlast = calculation_input.Vbus

                self.progress_signal.emit(0.0)

                t = self.start_
                dt = 1.0  # default value in case of single-valued profile

                # traverse the profiles time and simulate each time step
                while t < self.end_ and not self.__cancel__:
                    # set the power values
                    # if the storage dispatch option is active, the batteries power was not included
                    # it shall be included now, after processing
                    Y = calculation_input.Ysh_prof[:, t]
                    I = calculation_input.Ibus_prof[:, t]
                    S = calculation_input.Sbus_prof[:, t]

                    # add the controlled storage power if controlling storage
                    if self.options.dispatch_storage:

                        if t < self.end_-1:
                            # compute the time delta: the time values come in nanoseconds
                            dt = (calculation_input.time_array[t+1] - calculation_input.time_array[t]).value * 1e-9 / 3600

                        for k, batt in enumerate(batteries):

                            P = batt.get_processed_at(t, dt=dt, store_values=True)
                            bus_idx = batteries_bus_idx[k]
                            S[bus_idx] += (P / calculation_input.Sbase)
                        else:
                            pass

                    # run power flow at the circuit
                    res = power_flow.run_pf(circuit=calculation_input, Vbus=Vlast, Sbus=S, Ibus=I)

                    # Recycle voltage solution
                    Vlast = res.voltage

                    # store circuit results at the time index 't'
                    results.set_at(t, res)

                    progress = ((t - self.start_ + 1) / (self.end_ - self.start_)) * 100
                    self.progress_signal.emit(progress)
                    self.progress_text.emit('Simulating island ' + str(nc) + ' at ' + str(self.grid.time_profile[t]))
                    t += 1

                # merge  the circuit's results
                time_series_results.apply_from_island(results,
                                                      bus_original_idx,
                                                      branch_original_idx,
                                                      calculation_input.time_array,
                                                      'TS')
            else:
                print('There are no profiles')
                self.progress_text.emit('There are no profiles')

        return time_series_results

    def run_multi_thread(self):
        """
        Run multi thread time series
        :return:
        """

        # initialize the grid time series results
        # we will append the island results with another function
        n = len(self.grid.buses)
        m = len(self.grid.branches)
        nt = len(self.grid.time_profile)
        time_series_results = TimeSeriesResults(n, m, nt, self.start_, self.end_, time=self.grid.time_profile)
        if self.end_ is None:
            self.end_ = nt

        n_cores = multiprocessing.cpu_count()

        print('Compiling...', end='')
        numerical_circuit = self.grid.compile()
        calculation_inputs = numerical_circuit.compute()

        # For every circuit, run the time series
        for nc, calculation_input in enumerate(calculation_inputs):

            self.progress_text.emit('Time series at circuit ' + str(nc) + ' in parallel using ' + str(n_cores) + ' cores ...')

            if nt > 0:

                nt = calculation_input.ntime
                n = calculation_input.nbus
                m = calculation_input.nbr
                results = TimeSeriesResults(n, m, nt, self.start_, self.end_)
                Vlast = calculation_input.Vbus

                self.progress_signal.emit(0.0)

                # Start jobs
                manager = multiprocessing.Manager()
                return_dict = manager.dict()

                t = self.start_
                while t < self.end_ and not self.__cancel__:

                    k = 0
                    jobs = list()

                    # launch only n_cores jobs at the time
                    while k < n_cores+2 and (t+k) < nt:
                        # set the power values
                        # Y, I, S = calculation_input.time_series_input.get_at(t)
                        Y = calculation_input.Ysh_prof[:, t]
                        I = calculation_input.Ibus_prof[:, t]
                        S = calculation_input.Sbus_prof[:, t]

                        # run power flow at the circuit
                        p = multiprocessing.Process(target=power_flow_worker, args=(t, self.options, calculation_input, Vlast, S, I, return_dict))
                        jobs.append(p)
                        p.start()
                        k += 1
                        t += 1

                    # wait for all jobs to complete
                    for proc in jobs:
                        proc.join()

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
        self.__cancel__ = True

