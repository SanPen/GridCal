# GridCal
# Copyright (C) 2022 Santiago Peñate Vera
# 
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
import time
import json
import numpy as np
import pandas as pd

from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Core.time_series_pf_data import compile_time_circuit
import GridCal.Engine.Simulations.LinearFactors.linear_analysis as la
from GridCal.Engine.Simulations.ATC.available_transfer_capacity_driver import AvailableTransferCapacityOptions, compute_atc_list, compute_alpha
from GridCal.Engine.Simulations.driver_types import SimulationTypes
from GridCal.Engine.Simulations.result_types import ResultTypes
from GridCal.Engine.Simulations.results_table import ResultsTable
from GridCal.Engine.Simulations.results_template import ResultsTemplate
from GridCal.Engine.Simulations.driver_template import TimeSeriesDriverTemplate
from GridCal.Engine.Simulations.Clustering.clustering import kmeans_approximate_sampling


class AvailableTransferCapacityTimeSeriesResults(ResultsTemplate):

    def __init__(self, br_names, bus_names, rates, contingency_rates, time_array):
        """

        :param br_names:
        :param bus_names:
        :param rates:
        :param contingency_rates:
        :param nt:
        """
        ResultsTemplate.__init__(self,
                                 name='ATC Results',
                                 available_results=[
                                     ResultTypes.AvailableTransferCapacityReport
                                 ],
                                 data_variables=['reports',
                                                 'branch_names',
                                                 'bus_names',
                                                 'time_array'])

        self.time_array = time_array
        self.branch_names = np.array(br_names, dtype=object)
        self.bus_names = bus_names
        self.rates = rates
        self.contingency_rates = contingency_rates
        self.base_exchange = 0
        self.raw_report = None
        self.report = None
        self.report_headers = None
        self.report_indices = None

    def get_steps(self):
        return

    def make_report(self, threshold: float = 0.0):
        """

        :return:
        """
        self.report_headers = ['Time',
                               'Branch',
                               'Base flow',
                               'Rate',
                               'Alpha',
                               'ATC normal',
                               'Limiting contingency branch',
                               'Limiting contingency flow',
                               'Contingency rate',
                               'Beta',
                               'Contingency ATC',
                               'ATC',
                               'Base exchange flow',
                               'NTC']
        self.report = np.empty((len(self.raw_report), len(self.report_headers)), dtype=object)

        rep = np.array(self.raw_report)

        # sort by ATC
        if len(self.raw_report):
            self.report_indices = np.arange(0, len(rep))

            t = rep[:, 0].astype(int)
            m = rep[:, 1].astype(int)
            c = rep[:, 2].astype(int)

            # time
            self.report[:, 0] = self.time_array[t].strftime('%d/%m/%Y %H:%M').values

            # Branch name
            self.report[:, 1] = self.branch_names[m]

            # Base flow'
            self.report[:, 2] = rep[:, 10]

            # rate
            self.report[:, 3] = self.rates[t, m]  # 'Rate', (time, branch)

            # alpha
            self.report[:, 4] = rep[:, 3]

            # 'ATC normal'
            self.report[:, 5] = rep[:, 6]

            # contingency info -----

            # 'Limiting contingency branch'
            self.report[:, 6] = self.branch_names[c]

            # 'Limiting contingency flow'
            self.report[:, 7] = rep[:, 11]

            # 'Contingency rate' (time, branch)
            self.report[:, 8] = self.contingency_rates[t, m]

            # 'Beta'
            self.report[:, 9] = rep[:, 4]

            # 'Contingency ATC'
            self.report[:, 10] = rep[:, 7]

            # ATC
            self.report[:, 11] = rep[:, 8]

            # Base exchange flow
            self.report[:, 12] = rep[:, 14]

            # NTC
            self.report[:, 13] = rep[:, 9]

            # trim by abs alpha > threshold and loading <= 1
            loading = np.abs(self.report[:, 2] / (self.report[:, 3] + 1e-20))
            idx = np.where((np.abs(self.report[:, 4]) > threshold) & (loading <= 1.0))[0]

            self.report = self.report[idx, :]
        else:
            print('Empty raw report :/')

    def get_results_dict(self):
        """
        Returns a dictionary with the results sorted in a dictionary
        :return: dictionary of 2D numpy arrays (probably of complex numbers)
        """
        data = {'report': self.report.tolist()}
        return data

    def mdl(self, result_type: ResultTypes) -> ResultsTable:
        """
        Plot the results
        :param result_type:
        :return:
        """

        if result_type == ResultTypes.AvailableTransferCapacityReport:
            data = np.array(self.report)
            y_label = ''
            title, _ = result_type.value
            index = self.report_indices
            labels = self.report_headers
        else:
            raise Exception('Result type not understood:' + str(result_type))

        # assemble model
        mdl = ResultsTable(data=data,
                           index=index,
                           columns=labels,
                           title=title,
                           ylabel=y_label)
        return mdl


class AvailableTransferCapacityClusteringResults(AvailableTransferCapacityTimeSeriesResults):

    def __init__(self, br_names, bus_names, rates, contingency_rates, time_array, sampled_time_idx,
                 sampled_probabilities):
        """

        :param br_names:
        :param bus_names:
        :param rates:
        :param contingency_rates:
        :param time_array:
        :param sampled_time_idx:
        :param sampled_probabilities:
        """
        AvailableTransferCapacityTimeSeriesResults.__init__(self, br_names=br_names,
                                                            bus_names=bus_names,
                                                            rates=rates,
                                                            contingency_rates=contingency_rates,
                                                            time_array=time_array)

        # self.available_results.append(ResultTypes.P)

        self.sampled_time_idx = sampled_time_idx
        self.sampled_probabilities = sampled_probabilities


class AvailableTransferCapacityTimeSeriesDriver(TimeSeriesDriverTemplate):
    tpe = SimulationTypes.NetTransferCapacityTS_run
    name = tpe.value

    def __init__(self, grid: MultiCircuit, options: AvailableTransferCapacityOptions, start_=0, end_=None):
        """
        Power Transfer Distribution Factors class constructor
        @param grid: MultiCircuit Object
        @param options: OPF options
        @:param pf_results: PowerFlowResults, this is to get the Sf
        """
        TimeSeriesDriverTemplate.__init__(self,
                                          grid=grid,
                                          start_=start_,
                                          end_=end_)

        # Options to use
        self.options = options

        # OPF results
        self.results: AvailableTransferCapacityTimeSeriesResults = None

    def run(self):
        """
        Run thread
        """
        start = time.time()

        self.progress_signal.emit(0)
        nc = compile_time_circuit(self.grid)
        nt = len(nc.time_array)
        time_indices = self.get_time_indices()

        # declare the linear analysis
        self.progress_text.emit('Analyzing...')
        linear_analysis = la.LinearAnalysis(grid=self.grid,
                                            distributed_slack=self.options.distributed_slack,
                                            correct_values=self.options.correct_values)
        linear_analysis.run()

        # get the branch indices to analyze
        br_idx = nc.branch_data.get_monitor_enabled_indices()
        con_br_idx = nc.branch_data.get_contingency_enabled_indices()

        # declare the results
        self.results = AvailableTransferCapacityTimeSeriesResults(br_names=linear_analysis.numerical_circuit.branch_names,
                                                                  bus_names=linear_analysis.numerical_circuit.bus_names,
                                                                  rates=nc.Rates,
                                                                  contingency_rates=nc.ContingencyRates,
                                                                  time_array=nc.time_array[time_indices])

        if self.options.use_clustering:
            self.progress_text.emit('Clustering...')
            X = nc.Sbus
            X = X[:, time_indices].real.T

            # cluster and re-assign the time indices
            time_indices, \
                sampled_probabilities = kmeans_approximate_sampling(X, n_points=self.options.cluster_number)

        # get the power injections
        P = nc.Sbus.real  # these are in p.u.

        # get flow
        if self.options.use_provided_flows:
            flows = self.options.Pf

            if self.options.Pf is None:
                msg = 'The option to use the provided flows is enabled, but no flows are available'
                self.logger.add_error(msg)
                raise Exception(msg)
        else:
            # compute the base Sf
            flows = linear_analysis.get_flows_time_series(P)  # will be converted to MW internally

        # transform the contingency rates and the normal rates
        contingency_rates = nc.ContingencyRates.T
        rates = nc.Rates.T

        # these results can be copied directly
        self.results.base_flow = flows
        self.results.rates = rates
        self.results.contingency_rates = contingency_rates

        for it, t in enumerate(time_indices):

            if self.progress_text is not None:
                self.progress_text.emit('Available transfer capacity at ' + str(self.grid.time_profile[t]))

            # compute the branch exchange sensitivity (alpha)
            alpha = compute_alpha(ptdf=linear_analysis.PTDF,
                                  P0=P[:, t],  # no problem that there are in p.u., are only used for the sensitivity
                                  Pinstalled=nc.bus_installed_power,
                                  Pgen=nc.generator_data.get_injections_per_bus(),
                                  Pload=nc.load_data.get_injections_per_bus(),
                                  idx1=self.options.bus_idx_from,
                                  idx2=self.options.bus_idx_to,
                                  dT=self.options.dT,
                                  mode=self.options.mode.value)

            # base exchange
            base_exchange = (self.options.inter_area_branch_sense * flows[t, self.options.inter_area_branch_idx]).sum()

            # consider the HVDC transfer
            if self.options.Pf_hvdc is not None:
                if len(self.options.idx_hvdc_br):
                    base_exchange += (self.options.inter_area_hvdc_branch_sense * self.options.Pf_hvdc[t, self.options.idx_hvdc_br]).sum()

            # compute ATC
            report = compute_atc_list(br_idx=br_idx,
                                      contingency_br_idx=con_br_idx,
                                      lodf=linear_analysis.LODF,
                                      alpha=alpha,
                                      flows=flows[t, :],
                                      rates=rates[t, :],
                                      contingency_rates=contingency_rates[t, :],
                                      base_exchange=base_exchange,
                                      time_idx=t,
                                      threshold=self.options.threshold)
            report = np.array(report, dtype=object)

            # sort by NTC
            report = report[report[:, 9].argsort()]

            # curtail report
            if self.options.max_report_elements > 0:
                report = report[:self.options.max_report_elements, :]

            # post-process and store the results
            if self.results.raw_report is None:
                self.results.raw_report = report
            else:
                self.results.raw_report = np.r_[self.results.raw_report, report]

            if self.progress_signal is not None:
                self.progress_signal.emit((t + 1) / nt * 100)

            if self.__cancel__:
                break

        self.progress_text.emit('Building the report...')
        self.results.make_report()

        end = time.time()
        self.elapsed = end - start

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

    options = AvailableTransferCapacityOptions()
    driver = AvailableTransferCapacityTimeSeriesDriver(main_circuit, options, power_flow.results)
    driver.run()

    print()

