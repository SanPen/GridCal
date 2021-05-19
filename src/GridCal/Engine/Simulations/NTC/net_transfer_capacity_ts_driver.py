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
import time
import json
import numpy as np
import pandas as pd

from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Core.time_series_pf_data import compile_time_circuit
import GridCal.Engine.Simulations.LinearFactors.linear_analysis as la
from GridCal.Engine.Simulations.NTC.net_transfer_capacity_driver import NetTransferCapacityOptions, compute_atc, compute_alpha
from GridCal.Engine.Simulations.driver_types import SimulationTypes
from GridCal.Engine.Simulations.result_types import ResultTypes
from GridCal.Engine.Simulations.results_model import ResultsModel
from GridCal.Engine.Simulations.results_template import ResultsTemplate
from GridCal.Engine.Simulations.driver_template import TSDriverTemplate


class NetTransferCapacityTimeSeriesResults(ResultsTemplate):

    def __init__(self, n_br, n_bus, time_array, br_names, bus_names, bus_types):
        """

        :param n_br:
        :param n_bus:
        :param time_array:
        :param br_names:
        :param bus_names:
        :param bus_types:
        """
        ResultsTemplate.__init__(self,
                                 name='ATC Time Series Results',
                                 available_results=[
                                                    ResultTypes.NetTransferCapacityAlpha,
                                                    ResultTypes.NetTransferCapacityReport,
                                                    ResultTypes.NetTransferCapacityPS
                                                    ],
                                 data_variables=['alpha',
                                                 'atc_max',
                                                 'atc_min',
                                                 'worst_max',
                                                 'worst_min',
                                                 'worst_contingency_max',
                                                 'worst_contingency_min',
                                                 'PS_down',
                                                 'PS_up',
                                                 'time_array',
                                                 'branch_names',
                                                 'bus_names',
                                                 'bus_types',
                                                 'report',
                                                 'report_headers',
                                                 'report_indices'])
        self.n_br = n_br
        self.n_bus = n_bus
        self.nt = len(time_array)
        self.time_array = time_array
        self.branch_names = br_names
        self.bus_names = bus_names
        self.bus_types = bus_types

        # available transfer capacity matrix (branch, contingency branch)

        self.atc = np.zeros((self.nt, self.n_br))
        self.alpha = np.zeros((self.nt, self.n_br))
        self.worst_contingency = np.zeros((self.nt, self.n_br), dtype=int)

        self.alpha = np.zeros((self.nt, self.n_br))
        self.worst_max = np.zeros(self.nt, dtype=int)
        self.worst_min = np.zeros(self.nt, dtype=int)
        self.worst_contingency_max = np.zeros(self.nt, dtype=int)
        self.worst_contingency_min = np.zeros(self.nt, dtype=int)
        self.atc_max = np.zeros((self.nt, self.n_br))
        self.atc_min = np.zeros((self.nt, self.n_br))
        self.PS_down = np.zeros(self.nt)
        self.PS_up = np.zeros(self.nt)

        self.report = np.empty((self.nt, 8), dtype=object)
        self.report_headers = ['Branch min',
                               'Branch max',
                               'Worst Contingency min',
                               'Worst Contingency max',
                               'ATC max',
                               'ATC min',
                               'PS down',
                               'PS up']
        self.report_indices = self.time_array

    def get_steps(self):
        return

    def make_report(self):
        """

        :return:
        """
        self.report = np.empty((self.nt, 8), dtype=object)
        self.report_headers = ['Branch min',
                               'Branch max',
                               'Worst Contingency min',
                               'Worst Contingency max',
                               'ATC max',
                               'ATC min',
                               'PS down',
                               'PS up']
        self.report_indices = self.time_array
        for t in range(self.atc.shape[0]):
            self.report[t, 0] = self.branch_names[self.worst_max[t]]
            self.report[t, 1] = self.branch_names[self.worst_min[t]]
            self.report[t, 2] = self.branch_names[self.worst_contingency_max[t]]
            self.report[t, 3] = self.branch_names[self.worst_contingency_min[t]]
            self.report[t, 4] = self.atc_max[t, self.worst_max[t]]
            self.report[t, 5] = self.atc_min[t, self.worst_min[t]]
            self.report[t, 6] = self.PS_down[t]
            self.report[t, 7] = self.PS_up[t]

    def get_results_dict(self):
        """
        Returns a dictionary with the results sorted in a dictionary
        :return: dictionary of 2D numpy arrays (probably of complex numbers)
        """
        data = {'PS_down': self.PS_down.tolist(),
                'PS_up': self.PS_up.tolist(),
                'atc_max': self.atc_max.tolist(),
                'atc_min': self.atc_min.tolist()}
        return data

    def mdl(self, result_type: ResultTypes):
        """
        Plot the results
        :param result_type:
        :return:
        """

        index = pd.to_datetime(self.time_array)

        if result_type == ResultTypes.NetTransferCapacityAlpha:
            data = self.alpha
            y_label = '(p.u.)'
            title, _ = result_type.value
            labels = self.branch_names

        elif result_type == ResultTypes.NetTransferCapacity:
            data = self.atc
            y_label = '(MW)'
            title, _ = result_type.value
            labels = self.branch_names

        elif result_type == ResultTypes.NetTransferCapacityPS:
            data = np.c_[self.PS_up, self.PS_down]
            y_label = '(MW)'
            title, _ = result_type.value
            labels = ['PS up', 'PS down']

        elif result_type == ResultTypes.NetTransferCapacityReport:
            data = np.array(self.report)
            y_label = ''
            title, _ = result_type.value
            index = pd.to_datetime(self.report_indices)
            labels = self.report_headers

        else:
            raise Exception('Result type not understood:' + str(result_type))

        # assemble model
        mdl = ResultsModel(data=data,
                           index=index,
                           columns=labels,
                           title=title,
                           ylabel=y_label)
        return mdl


class NetTransferCapacityTimeSeriesDriver(TSDriverTemplate):
    tpe = SimulationTypes.NetTransferCapacityTS_run
    name = tpe.value

    def __init__(self, grid: MultiCircuit, options: NetTransferCapacityOptions, start_=0, end_=None):
        """
        Power Transfer Distribution Factors class constructor
        @param grid: MultiCircuit Object
        @param options: OPF options
        @:param pf_results: PowerFlowResults, this is to get the Sf
        """
        TSDriverTemplate.__init__(self,
                                  grid=grid,
                                  start_=start_,
                                  end_=end_)

        # Options to use
        self.options = options

        # OPF results
        self.results = NetTransferCapacityTimeSeriesResults(n_br=0,
                                                            n_bus=0,
                                                            time_array=[],
                                                            br_names=[],
                                                            bus_names=[],
                                                            bus_types=[])

    def run(self):
        """
        Run thread
        """
        start = time.time()

        self.progress_signal.emit(0)

        time_indices = self.get_time_indices()

        # declare the linear analysis
        self.progress_text.emit('Analyzing...')
        linear_analysis = la.LinearAnalysis(grid=self.grid,
                                            distributed_slack=self.options.distributed_slack,
                                            correct_values=self.options.correct_values)
        linear_analysis.run()

        ts_numeric_circuit = compile_time_circuit(self.grid)
        ne = ts_numeric_circuit.nbr
        nc = ts_numeric_circuit.nbr
        nt = len(ts_numeric_circuit.time_array)

        # declare the results
        self.results = NetTransferCapacityTimeSeriesResults(n_br=ts_numeric_circuit.nbr,
                                                            n_bus=ts_numeric_circuit.nbus,
                                                            time_array=ts_numeric_circuit.time_array,
                                                            br_names=ts_numeric_circuit.branch_names,
                                                            bus_names=ts_numeric_circuit.bus_names,
                                                            bus_types=ts_numeric_circuit.bus_types)

        # compute the base Sf
        P = ts_numeric_circuit.Sbus.real  # these are in p.u.
        flows = linear_analysis.get_flows_time_series(P)  # will be converted to MW internally
        rates = ts_numeric_circuit.Rates.T
        contingency_rates = ts_numeric_circuit.ContingencyRates.T
        for t in time_indices:

            if self.progress_text is not None:
                self.progress_text.emit('Available transfer capacity at ' + str(self.grid.time_profile[t]))

            # compute the branch exchange sensitivity (alpha)
            alpha = compute_alpha(ptdf=linear_analysis.PTDF,
                                  P0=P[:, t],  # no problem that these are in p.u., only used for the sensitivity
                                  idx1=self.options.bus_idx_from,
                                  idx2=self.options.bus_idx_to)

            # compute the ATC
            atc_max, atc_min, worst_max, worst_min, \
            worst_contingency_max, worst_contingency_min, PS_down, PS_up = compute_atc(ptdf=linear_analysis.PTDF,
                                                                                       lodf=linear_analysis.LODF,
                                                                                       alpha=alpha,
                                                                                       flows=flows[t, :],
                                                                                       rates=rates[t, :],
                                                                                       contingency_rates=contingency_rates[t, :],
                                                                                       threshold=self.options.threshold)

            # assign the results
            self.results.alpha[t, :] = alpha
            self.results.atc_max[t, :] = atc_max
            self.results.atc_min[t, :] = atc_min
            self.results.worst_max[t] = worst_max
            self.results.worst_max[t] = worst_max
            self.results.worst_contingency_max[t] = worst_contingency_max
            self.results.worst_contingency_min[t] = worst_contingency_min
            self.results.PS_down[t] = PS_down
            self.results.PS_up[t] = PS_up

            if self.progress_signal is not None:
                self.progress_signal.emit((t + 1) / nt * 100)

            if self.__cancel__:
                break

        self.results.make_report()

        end = time.time()
        self.elapsed = end - start
        self.progress_text.emit('Done!')
        self.done_signal.emit()

    def get_steps(self):
        """
        Get variations list of strings
        """
        if self.results is not None:
            return [v for v in self.results.branch_names]
        else:
            return list()

    def cancel(self):
        self.__cancel__ = True


if __name__ == '__main__':

    from GridCal.Engine import PowerFlowOptions, FileOpen, LinearAnalysis, PowerFlowDriver, SolverType
    fname = r'C:\Users\penversa\Git\GridCal\Grids_and_profiles\grids\IEEE 118 Bus - ntc_areas.gridcal'

    main_circuit = FileOpen(fname).open()

    simulation_ = LinearAnalysis(grid=main_circuit)
    simulation_.run()

    pf_options = PowerFlowOptions(solver_type=SolverType.NR,
                                  retry_with_other_methods=True)
    power_flow = PowerFlowDriver(main_circuit, pf_options)
    power_flow.run()

    options = NetTransferCapacityOptions()
    driver = NetTransferCapacityTimeSeriesDriver(main_circuit, options, power_flow.results)
    driver.run()

    print()

