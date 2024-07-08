# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
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
import numpy as np
from typing import Union, List

from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.DataStructures.numerical_circuit import compile_numerical_circuit_at
from GridCalEngine.Simulations.LinearFactors.linear_analysis_options import LinearAnalysisOptions
from GridCalEngine.Simulations.LinearFactors.linear_analysis_ts_driver import LinearAnalysisTimeSeriesDriver
from GridCalEngine.Simulations.LinearFactors.linear_analysis import LinearAnalysis
from GridCalEngine.Simulations.ATC.available_transfer_capacity_driver import compute_atc_list, compute_alpha
from GridCalEngine.Simulations.ATC.available_transfer_capacity_options import AvailableTransferCapacityOptions
from GridCalEngine.Simulations.results_table import ResultsTable
from GridCalEngine.Simulations.results_template import ResultsTemplate
from GridCalEngine.Simulations.driver_template import TimeSeriesDriverTemplate
from GridCalEngine.Simulations.Clustering.clustering_results import ClusteringResults
from GridCalEngine.basic_structures import Vec, Mat, IntVec, StrVec, DateVec
from GridCalEngine.enumerations import StudyResultsType, AvailableTransferMode, ResultTypes, DeviceType, SimulationTypes


class AvailableTransferCapacityTimeSeriesResults(ResultsTemplate):
    """
    AvailableTransferCapacityTimeSeriesResults
    """

    def __init__(self, br_names: StrVec, bus_names: StrVec, rates: Mat, contingency_rates: Mat, time_array: DateVec,
                 clustering_results):
        """

        :param br_names:
        :param bus_names:
        :param rates:
        :param contingency_rates:
        :param time_array:
        """
        ResultsTemplate.__init__(
            self,
            name='ATC Results',
            available_results=[
                ResultTypes.AvailableTransferCapacityReport
            ],
            time_array=time_array,
            clustering_results=clustering_results,
            study_results_type=StudyResultsType.AvailableTransferCapacity
        )

        # self.time_array = time_array
        self.branch_names = np.array(br_names, dtype=object)
        self.bus_names = bus_names
        self.rates = rates
        self.contingency_rates = contingency_rates
        self.base_exchange = 0
        self.raw_report = None
        self.report = None
        self.report_headers: StrVec = None
        self.report_indices: IntVec = None

    def clear(self):
        """
        Crear the results
        :return:
        """
        self.base_exchange = 0
        self.raw_report = None
        self.report = None
        self.report_headers: StrVec = None
        self.report_indices: IntVec = None

    def make_report(self, threshold: float = 0.0):
        """

        :return:
        """
        self.report_headers = [
            'Time',
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
            'NTC'
        ]

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
            return ResultsTable(
                data=np.array(self.report),
                index=self.report_indices,
                columns=self.report_headers,
                title=result_type.value,
                ylabel="",
                cols_device_type=DeviceType.NoDevice,
                idx_device_type=DeviceType.NoDevice
            )
        else:
            raise Exception('Result type not understood:' + str(result_type))


class AvailableTransferCapacityTimeSeriesDriver(TimeSeriesDriverTemplate):
    tpe = SimulationTypes.NetTransferCapacityTS_run
    name = tpe.value

    def __init__(self,
                 grid: MultiCircuit,
                 options: AvailableTransferCapacityOptions,
                 time_indices: np.ndarray,
                 clustering_results: Union[ClusteringResults, None] = None):

        """
        Power Transfer Distribution Factors class constructor
        :param grid: MultiCircuit Object
        :param options: OPF options
        :param time_indices: array of time indices to simulate
        :param clustering_results: ClusteringResults (optional)
        """

        TimeSeriesDriverTemplate.__init__(
            self,
            grid=grid,
            time_indices=time_indices,
            clustering_results=clustering_results
        )

        # Options to use
        self.options = options

        # OPF results
        self.results = AvailableTransferCapacityTimeSeriesResults(
            br_names=self.grid.get_branches_wo_hvdc_names(),
            bus_names=self.grid.get_bus_names(),
            rates=self.grid.get_branch_rates_prof_wo_hvdc(),
            contingency_rates=self.grid.get_branch_contingency_rates_prof_wo_hvdc(),
            time_array=self.grid.time_profile[self.time_indices],
            clustering_results=clustering_results
        )

    def get_steps(self) -> List[str]:
        """
        Get time steps list of strings
        """

        return []

    def run(self) -> None:
        """
        Run thread
        """
        self.tic()

        mode_2_int = {AvailableTransferMode.Generation: 0,
                      AvailableTransferMode.InstalledPower: 1,
                      AvailableTransferMode.Load: 2,
                      AvailableTransferMode.GenerationAndLoad: 3}

        # declare the linear analysis
        self.report_text("Analyzing...")
        self.report_progress(0.0)

        la_options = LinearAnalysisOptions(
            distribute_slack=self.options.distributed_slack,
            correct_values=self.options.correct_values,
        )

        la_driver = LinearAnalysisTimeSeriesDriver(
            grid=self.grid,
            options=la_options,
            time_indices=self.time_indices
        )

        la_driver.run()

        # get the branch indices to analyze
        nc = compile_numerical_circuit_at(self.grid, logger=self.logger)
        br_idx = nc.branch_data.get_monitor_enabled_indices()
        con_br_idx = nc.branch_data.get_contingency_enabled_indices()

        # declare the results
        self.results.clear()

        for it, t in enumerate(self.time_indices):

            self.report_text('Available transfer capacity at ' + str(self.grid.time_profile[t]))

            nc = compile_numerical_circuit_at(circuit=self.grid, t_idx=t)

            linear_analysis = LinearAnalysis(
                numerical_circuit=nc,
                distributed_slack=True,
                correct_values=False,
            )
            linear_analysis.run()

            P: Vec = nc.Sbus.real

            # get flow
            if self.options.use_provided_flows:
                flows_t = self.options.Pf[t, :]

                if self.options.Pf is None:
                    msg = 'The option to use the provided flows is enabled, but no flows are available'
                    self.logger.add_error(msg)
                    raise Exception(msg)
            else:
                flows_t: Vec = linear_analysis.get_flows(P)

            # compute the branch exchange sensitivity (alpha)
            alpha = compute_alpha(ptdf=linear_analysis.PTDF,
                                  P0=P,  # no problem that there are in p.u., are only used for the sensitivity
                                  Pinstalled=nc.bus_installed_power,
                                  Pgen=nc.generator_data.get_injections_per_bus().real,
                                  Pload=nc.load_data.get_injections_per_bus().real,
                                  idx1=self.options.bus_idx_from,
                                  idx2=self.options.bus_idx_to,
                                  mode=mode_2_int[self.options.mode])

            # base exchange
            base_exchange = (self.options.inter_area_branch_sense * flows_t[self.options.inter_area_branch_idx]).sum()

            # consider the HVDC transfer
            if self.options.Pf_hvdc is not None:
                if len(self.options.idx_hvdc_br):
                    base_exchange += (self.options.inter_area_hvdc_branch_sense * self.options.Pf_hvdc[
                        t, self.options.idx_hvdc_br]).sum()

            # compute ATC
            report = compute_atc_list(br_idx=br_idx,
                                      contingency_br_idx=con_br_idx,
                                      lodf=linear_analysis.LODF,
                                      alpha=alpha,
                                      flows=flows_t,
                                      rates=self.results.rates[t, :],
                                      contingency_rates=self.results.contingency_rates[t, :],
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

            self.report_progress2(t, len(self.time_indices))

            if self.__cancel__:
                break

        self.report_text('Building the report...')
        self.results.make_report()

        self.toc()

    def cancel(self):
        self.__cancel__ = True
