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

import time
import numpy as np
from typing import Dict, Union

from GridCalEngine.Simulations.results_template import ResultsTemplate
from GridCalEngine.enumerations import ResultTypes, StudyResultsType
from GridCalEngine.Simulations.results_table import ResultsTable, DeviceType


class OptimalNetTransferCapacityTimeSeriesResults(ResultsTemplate):

    def __init__(
            self,
            bus_names: np.ndarray,
            branch_names: np.ndarray,
            hvdc_names: np.ndarray,
            time_array: np.ndarray,
            time_indices: np.ndarray,
            sampled_probabilities: Union[np.ndarray, None] = None,
            loading_threshold_to_report: float = 0.98,
            reversed_sort_loading: bool = True,
            trm: float = 0,
            ntc_load_rule: float = 100):

        """

        :param bus_names:
        :param branch_names:
        :param time_array:
        :param time_indices:
        :param sampled_probabilities:
        :param loading_threshold_to_report:
        :param reversed_sort_loading:
        :param trm:
        :param ntc_load_rule:
        """
        ResultsTemplate.__init__(
            self,
            name='NTC Optimal time series results',
            available_results={
                ResultTypes.FlowReports: [
                    ResultTypes.TsContingencyFlowReport,
                    ResultTypes.TsBaseFlowReport,
                ],
                ResultTypes.Sensibilities: [
                    ResultTypes.AvailableTransferCapacityAlpha,
                    ResultTypes.AvailableTransferCapacityAlphaN1,
                ],
                ResultTypes.DispatchResults: [
                    ResultTypes.GeneratorPower,
                    ResultTypes.GenerationDelta,
                ],
                ResultTypes.BranchResults: [
                    ResultTypes.BranchMonitoring,
                    ResultTypes.TsCriticalBranches,
                    ResultTypes.TsContingencyBranches,
                ],
            },
            time_array=time_array,
            clustering_results=None,
            study_results_type=StudyResultsType.NetTransferCapacityTimeSeries)

        nt = len(time_indices)
        m = len(branch_names)
        n = len(bus_names)
        nhvdc = len(hvdc_names)

        # self.time_array = time_array
        self.time_indices = time_indices
        self.branch_names = np.array(branch_names, dtype=object)
        self.bus_names = bus_names

        self.voltage = np.zeros((nt, n), dtype=complex)
        self.Sbus = np.zeros((nt, n), dtype=complex)
        self.bus_shadow_prices = np.zeros((nt, n), dtype=float)

        self.Sf = np.zeros((nt, m), dtype=complex)
        self.St = np.zeros((nt, m), dtype=complex)
        self.loading = np.zeros((nt, m), dtype=float)
        self.losses = np.zeros((nt, m), dtype=float)
        self.phase_shift = np.zeros((nt, m), dtype=float)
        self.overloads = np.zeros((nt, m), dtype=float)
        self.rates = np.zeros(m)
        self.contingency_rates = np.zeros(m)
        self.contingency_flows_list = list()
        self.contingency_indices_list = list()  # [(t, m, c), ...]
        self.contingency_flows_slacks_list = list()

        self.hvdc_Pf = np.zeros((nt, nhvdc), dtype=float)
        self.hvdc_loading = np.zeros((nt, nhvdc), dtype=float)

        self.monitor = np.zeros((nt, m), dtype=bool)
        self.monitor_type = np.zeros((nt, m), dtype=object)

        self.base_exchange = 0
        self.raw_report = None
        self.report = None
        self.report_headers = None
        self.report_indices = None

        self.optimal_idx = []
        self.feasible_idx = []
        self.infeasible_idx = []
        self.unbounded_idx = []
        self.abnormal_idx = []
        self.not_solved = []

        self.elapsed = 0

        self.trm = trm
        self.ntc_load_rule = ntc_load_rule

        if sampled_probabilities is None and len(self.time_indices) > 0:
            sampled_probabilities = np.full(len(self.time_indices), fill_value=1 / len(self.time_indices))

        self.sampled_probabilities = sampled_probabilities

        self.loading_threshold_to_report = loading_threshold_to_report
        self.reversed_sort_loading = reversed_sort_loading

        self.results_dict: Dict[int, "OptimalNetTransferCapacityResults"] = dict()
        self.reports: Dict[str, ResultsTable] = dict()

    def get_alpha_report(self):

        title = ResultTypes.TsAlphaReport.value

        if title not in self.reports.keys():
            self.create_alpha_report()

        return self.reports[title]

    def get_alphan1_report(self):

        title = ResultTypes.TsWorstAlphaN1Report.value

        if title not in self.reports.keys():
            self.create_worst_alpha_n1_report()

        return self.reports[title]

    def get_generation_power_report(self):

        title = ResultTypes.TsGenerationPowerReport.value

        if title not in self.reports.keys():
            self.create_generation_power_report()

        return self.reports[title]

    def get_generation_delta_report(self):

        title = ResultTypes.TsGenerationDeltaReport.value

        if title not in self.reports.keys():
            self.create_generation_delta_report()

        return self.reports[title]

    def get_base_report(self, loading_threshold=0.0, reverse=True):

        title = f'{ResultTypes.TsBaseFlowReport.value}. ' \
                f'Loading threshold: {str(loading_threshold)}. ' \
                f'Reverse: {str(reverse)}'

        if title not in self.reports.keys():
            self.create_base_report(
                loading_threshold=loading_threshold,
                reverse=reverse,
            )

        return self.reports[title]

    def get_contingency_full_report(self, loading_threshold, reverse=True):

        title = f'{ResultTypes.TsContingencyFlowReport.value}. ' \
                f'Loading threshold: {str(loading_threshold)}. ' \
                f'Reverse: {str(reverse)}'

        if title not in self.reports.keys():
            self.create_contingency_full_report(
                loading_threshold=loading_threshold,
                reverse=reverse,
            )
        return self.reports[title]

    def get_branch_monitoring_report(self):

        title = ResultTypes.TsBranchMonitoring.value

        if title not in self.reports.keys():
            self.create_branch_monitoring_report()

        return self.reports[title]

    def get_critical_branches_report(self, loading_threshold=100, reverse=True):

        title = f'{ResultTypes.TsCriticalBranches.value}. ' \
                f'Loading threshold: {str(loading_threshold)}. ' \
                f'Reverse: {str(reverse)}'

        if title not in self.reports.keys():
            self.create_critical_branches_report(
                loading_threshold=loading_threshold,
                reverse=reverse
            )

        return self.reports[title]

    def get_contingency_branches_report(self, loading_threshold=100, reverse=True):

        title = f'{ResultTypes.TsContingencyBranches.value}. ' \
                f'Loading threshold: {str(loading_threshold)}. ' \
                f'Reverse: {str(reverse)}'

        if title not in self.reports.keys():
            self.create_contingency_branches_report(
                loading_threshold=loading_threshold,
                reverse=reverse
            )

        return self.reports[title]

    def create_all_reports(self, loading_threshold, reverse):

        tm0 = time.time()

        tm1 = time.time()
        self.create_generation_power_report()
        print(f'Generation power report created in {time.time() - tm1:.2f} scs.')

        tm1 = time.time()
        self.create_generation_delta_report()
        print(f'Generation delta report created in {time.time() - tm1:.2f} scs.')

        tm1 = time.time()
        self.create_alpha_report()
        print(f'Alpha report created in {time.time() - tm1:.2f} scs.')

        tm1 = time.time()
        self.create_worst_alpha_n1_report()
        print(f'Worst alpha n1 report created in {time.time() - tm1:.2f} scs.')

        tm1 = time.time()
        self.create_branch_monitoring_report()
        print(f'Branch monitoring report created in {time.time() - tm1:.2f} scs.')

        tm1 = time.time()
        self.create_base_report(
            loading_threshold=loading_threshold,
            reverse=reverse
        )
        print(f'Base report created in {time.time() - tm1:.2f} scs.')

        tm1 = time.time()
        self.create_contingency_full_report(
            loading_threshold=loading_threshold,
            reverse=reverse
        )
        print(f'Contingency power report created in {time.time() - tm1:.2f} scs.')

        tm1 = time.time()
        self.create_critical_branches_report(
            loading_threshold=100,
            reverse=reverse
        )
        print(f'Critical branches report created in {time.time() - tm1:.2f} scs.')
        print(f'All final reports created in {time.time() - tm0:.2f} scs.')

    def mdl(self, result_type) -> "ResultsTable":
        """
        Plot the results
        :param result_type: type of results (string)
        :return: DataFrame of the results (or None if the result was not understood)
        """

        if result_type == ResultTypes.TsBaseFlowReport:
            return self.get_base_report(
                loading_threshold=self.loading_threshold_to_report,
                reverse=self.reversed_sort_loading,
            )

        elif result_type == ResultTypes.TsContingencyFlowReport:
            return self.get_contingency_full_report(
                loading_threshold=self.loading_threshold_to_report,
                reverse=self.reversed_sort_loading,
            )

        elif result_type == ResultTypes.AvailableTransferCapacityAlpha:
            return self.get_alpha_report()

        elif result_type == ResultTypes.AvailableTransferCapacityAlphaN1:
            return self.get_alphan1_report()

        elif result_type == ResultTypes.GeneratorPower:
            return self.get_generation_power_report()

        elif result_type == ResultTypes.GenerationDelta:
            return self.get_generation_delta_report()

        elif result_type == ResultTypes.BranchMonitoring:
            # Todo: revisar la monitorización de unrealistic ntc logic
            # todo: añadir una columna con Load at Zero Exchange
            return self.get_branch_monitoring_report()

        elif result_type == ResultTypes.TsCriticalBranches:
            return self.get_critical_branches_report()

        elif result_type == ResultTypes.TsContingencyBranches:
            return self.get_contingency_branches_report()
        else:
            raise Exception('No results available')

    def get_steps(self):
        return

    def get_used_shifters(self):
        all_names = list()
        all_idx = list()

        # Get all shifters name
        for idx, t in enumerate(self.time_indices):
            if t in self.results_dict.keys():
                shift_idx = np.where(self.results_dict[t].phase_shift != 0)[0]
                if len(shift_idx) > 0:
                    names = self.results_dict[t].branch_names[shift_idx]
                    all_names = all_names + [n for n in names if n not in all_names]
                    all_idx = all_idx + [ix for ix in shift_idx if ix not in all_idx]

        return all_names, all_idx

    def get_hvdc_angle_slacks(self):
        all_names = list()
        all_idx = list()

        # Get all shifters name
        for idx, t in enumerate(self.time_indices):
            if t in self.results_dict.keys():
                angle_idx = np.where(self.results_dict[t].hvdc_angle_slack != 0)[0]
                if len(angle_idx) > 0:
                    names = self.results_dict[t].branch_names[angle_idx]
                    all_names = all_names + [n for n in names if n not in all_names]
                    all_idx = all_idx + [ix for ix in angle_idx if ix not in all_idx]

        return all_names, all_idx

    def save_report(self, path_out=None):
        """

         :param path_out:
         :return:
         """

        print('\n\n')
        print('Ejecutado en {0} scs. para {1} casos'.format(self.elapsed, len(self.time_array)))

        print('\n\n')
        print('Total resueltos:', len(self.optimal_idx))
        print('Total factibles o interrumpidos:', len(self.feasible_idx))
        print('Total sin resultado:', len(self.infeasible_idx))
        print('Total sin limites:', len(self.unbounded_idx))
        print('Total con error:', len(self.abnormal_idx))
        print('Total sin analizar:', len(self.not_solved))

        report_table = self.get_contingency_full_report(loading_threshold=self.loading_threshold_to_report)

        report_table.save_to_csv(path_out)

    def add_probability_info(self, columns, data):

        prob_dict = dict(zip(self.time_indices, self.sampled_probabilities))

        # get columns indices to sort
        ttc_idx = list(map(str.lower, columns)).index('ttc')
        load_col_name = [c for c in columns if any(x in c.lower().split(' ') for x in ['flow', 'load']) and '%' in c][0]
        cload_idx = columns.index(load_col_name)
        time_idx = list(map(str.lower, columns)).index('time')

        # sort data by ntc, time index, load (descending) to compute probability factor
        data = data[np.lexsort(
            (
                np.abs(data[:, cload_idx].astype(float)),
                data[:, time_idx],
                data[:, ttc_idx].astype(float),  # not abs value
            )
        )][::-1]

        # add probability info into data
        prob = np.zeros((data.shape[0], 1))
        data = np.append(prob, data, axis=1)
        columns = ['Prob.'] + columns

        # compute cumulative probability
        time_prev = 0
        pct = 0
        for row in range(data.shape[0]):
            t = int(data[row, 1])
            if t != time_prev:
                pct += prob_dict[t]
                time_prev = t

            data[row, 0] = pct

        return columns, data

    def create_alpha_report(self):

        title = ResultTypes.TsAlphaReport.value

        result = list(self.results_dict.values())[0]
        columns = ['Time index', 'Time'] + list(result.branch_names)
        data = np.zeros((len(self.time_indices), len(result.alpha) + 2), object)

        for idx, t in enumerate(self.time_indices):
            if t in self.results_dict.keys():
                data[idx, 2:] = self.results_dict[t].alpha
                data[idx, :2] = [t, self.time_array[idx].strftime("%d/%m/%Y %H:%M:%S")]

        labels = np.arange(data.shape[0])

        self.reports[title] = ResultsTable(
            index=labels,
            columns=columns,
            data=data,
            title=title,
        )

    def create_worst_alpha_n1_report(self):

        title = ResultTypes.TsWorstAlphaN1Report.value

        result = list(self.results_dict.values())[0]
        columns = ['Time index', 'Time'] + list(result.branch_names)
        data = np.zeros((len(self.time_indices), len(result.alpha) + 2), object)

        for idx, t in enumerate(self.time_indices):
            if t in self.results_dict.keys():
                data[idx, 2:] = self.results_dict[t].alpha_w[:, 0]
                data[idx, :2] = [t, self.time_array[idx].strftime("%d/%m/%Y %H:%M:%S")]

        labels = np.arange(data.shape[0])

        self.reports[title] = ResultsTable(
            index=labels,
            columns=columns,
            data=data,
            title=title,
        )

    def create_generation_power_report(self):

        title = ResultTypes.TsGenerationPowerReport.value

        labels = self.time_array
        columns = self.generator_names

        data = np.empty(shape=(len(labels), len(columns)))

        for idx, t in enumerate(self.time_indices):
            if t in self.results_dict.keys():
                data[idx] = self.results_dict[t].generator_power

        self.reports[title] = ResultsTable(
            index=labels,
            columns=columns,
            data=data,
            title=title,
        )

    def create_generation_delta_report(self):

        title = ResultTypes.TsGenerationDeltaReport.value

        labels = self.time_array
        columns = self.generator_names

        data = np.empty(shape=(len(labels), len(columns)))

        for idx, t in enumerate(self.time_indices):
            if t in self.results_dict.keys():
                data[idx] = self.results_dict[t].generation_delta

        self.reports[title] = ResultsTable(
            index=labels,
            columns=columns,
            data=data,
            title=title
        )

    def create_base_report(self, loading_threshold, reverse):

        title = f'{ResultTypes.TsBaseFlowReport.value}. ' \
                f'Loading threshold: {str(loading_threshold)}. ' \
                f'Reverse: {str(reverse)}'

        mdl = list(self.results_dict.values())[0].get_base_report(
            loading_threshold=loading_threshold,
            reverse=reverse,
        )

        columns_all = ['Time index', 'Time'] + mdl.get_data()[1]
        data_all = np.empty(shape=(0, len(columns_all)))

        for idx, t in enumerate(self.time_indices):
            if t in self.results_dict.keys():
                mdl = self.results_dict[t].get_base_report(
                    loading_threshold=loading_threshold,
                    reverse=reverse,
                )
                data = mdl.get_data()[2]

                if data.shape[0] == 0:
                    data = np.zeros(shape=(1, len(mdl.get_data()[1])))

            else:
                data = np.zeros(shape=(1, len(mdl.get_data()[1])))

            # complete the report data with Time info
            time_data = np.array([[t, self.time_array[idx].strftime("%d/%m/%Y %H:%M:%S")]] * data.shape[0])
            data = np.concatenate((time_data, data), axis=1)

            # add to main data set
            data_all = np.concatenate((data_all, data), axis=0)

        columns_all, data_all = self.add_probability_info(columns=columns_all, data=data_all)

        self.reports[title] = ResultsTable(
            data=data_all,
            index=np.arange(data_all.shape[0]),
            columns=columns_all,
            title=title,
            ylabel='(p.u.)',
            xlabel='',
            units='',
        )

    def create_contingency_full_report(self, loading_threshold=0.0, reverse=True):

        title = f'{ResultTypes.TsContingencyFlowReport.value}. ' \
                f'Loading threshold: {str(loading_threshold)}. ' \
                f'Reverse: {str(reverse)}'

        if len(self.results_dict.values()) == 0:
            print("Sin resultados")
            return

        mdl = list(self.results_dict.values())[0].get_contingency_report(
            loading_threshold=loading_threshold,
            reverse=reverse,
        )

        columns_all = ['Time index', 'Time'] + mdl.get_data()[1]
        data_all = np.empty(shape=(0, len(columns_all)))

        for idx, t in enumerate(self.time_indices):

            if t in self.results_dict.keys():

                ttc = np.floor(self.results_dict[t].get_exchange_power())

                if ttc != 0:
                    mdl = self.results_dict[t].get_contingency_report(
                        loading_threshold=loading_threshold,
                        reverse=reverse,
                    )
                    data = mdl.get_data()[2]

                    if data.shape[0] == 0:
                        data = np.zeros(shape=(1, len(mdl.get_data()[1])))

                else:
                    data = np.zeros(shape=(1, len(mdl.get_data()[1])))

            # complete the report data with Time info
            time_data = np.array([[t, self.time_array[idx].strftime("%d/%m/%Y %H:%M:%S")]] * data.shape[0])
            data = np.concatenate((time_data, data), axis=1)

            # add to main data set
            data_all = np.concatenate((data_all, data), axis=0)

        columns_all, data_all = self.add_probability_info(
            columns=columns_all,
            data=data_all
        )

        self.reports[title] = ResultsTable(
            data=data_all,
            index=np.arange(data_all.shape[0]),
            columns=columns_all,
            title=title,
            ylabel='(p.u.)',
            xlabel='',
            units='',
        )

    def create_contingency_branch_report(self, loading_threshold=0.0, reverse=True):

        title = f'{ResultTypes.TsContingencyFlowBranchReport.value}. ' \
                f'Loading threshold: {str(self.loading_threshold_to_report)}. ' \
                f'Reverse: {str(reverse)}'

        if len(self.results_dict.values()) == 0:
            return ResultsTable(data=np.zeros(0), columns=[], index=[])

        mdl = list(self.results_dict.values())[0].get_contingency_branch_report(
            loading_threshold=loading_threshold,
            reverse=reverse,
        )

        columns_all = ['Time index', 'Time'] + mdl.get_data()[1]
        data_all = np.empty(shape=(0, len(columns_all)))

        for idx, t in enumerate(self.time_indices):

            if t in self.results_dict.keys():

                mdl = self.results_dict[t].get_contingency_branch_report(
                    loading_threshold=loading_threshold,
                    reverse=reverse,
                )
                data = mdl.get_data()[2]

                if data.shape[0] == 0:
                    data = np.zeros(shape=(1, len(mdl.get_data()[1])))

            else:
                data = np.zeros(shape=(1, len(mdl.get_data()[1])))

            # complete the report data with Time info
            time_data = np.array([[t, self.time_array[idx].strftime("%d/%m/%Y %H:%M:%S")]] * data.shape[0])
            data = np.concatenate((time_data, data), axis=1)

            # add to main data set
            data_all = np.concatenate((data_all, data), axis=0)

        columns_all, data_all = self.add_probability_info(
            columns=columns_all,
            data=data_all
        )

        self.reports[title] = ResultsTable(
            data=data_all,
            index=np.arange(data_all.shape[0]),
            columns=columns_all,
            title=title,
            ylabel='(p.u.)',
            xlabel='',
            units='',
        )

    def create_contingency_generation_report(self, loading_threshold=0.0, reverse=True):

        title = f'{ResultTypes.TsContingencyFlowGenerationReport.value}. ' \
                f'Loading threshold: {str(loading_threshold)}. ' \
                f'Reverse: {str(reverse)}'

        if len(self.results_dict.values()) == 0:
            return

        mdl = list(self.results_dict.values())[0].get_contingency_generation_report(
            loading_threshold=loading_threshold,
            reverse=reverse,
        )

        columns_all = ['Time index', 'Time'] + mdl.get_data()[1]
        data_all = np.empty(shape=(0, len(columns_all)))

        for idx, t in enumerate(self.time_indices):

            if t in self.results_dict.keys():

                mdl = self.results_dict[t].get_contingency_generation_report(
                    loading_threshold=loading_threshold,
                    reverse=reverse,
                )

                data = mdl.get_data()[2]

                if data.shape[0] == 0:
                    data = np.zeros(shape=(1, len(mdl.get_data()[1])))

            else:
                data = np.zeros(shape=(1, len(mdl.get_data()[1])))

            # complete the report data with Time info
            time_data = np.array([[t, self.time_array[idx].strftime("%d/%m/%Y %H:%M:%S")]] * data.shape[0])
            data = np.concatenate((time_data, data), axis=1)

            # add to main data set
            data_all = np.concatenate((data_all, data), axis=0)

        columns_all, data_all = self.add_probability_info(
            columns=columns_all,
            data=data_all
        )

        self.reports[title] = ResultsTable(
            data=data_all,
            index=np.arange(data_all.shape[0]),
            columns=columns_all,
            title=title,
            ylabel='(p.u.)',
            xlabel='',
            units='',
        )

    def create_contingency_hvdc_report(self, loading_threshold=0.0, reverse=True):

        title = f'{ResultTypes.TsContingencyFlowHvdcReport.value}. ' \
                f'Loading threshold: {str(loading_threshold)}. ' \
                f'Reverse: {str(reverse)}'

        if len(self.results_dict.values()) == 0:
            return

        mdl = list(self.results_dict.values())[0].get_contingency_hvdc_report(
            loading_threshold=loading_threshold,
            reverse=reverse,
        )

        columns_all = ['Time index', 'Time'] + mdl.get_data()[1]
        data_all = np.empty(shape=(0, len(columns_all)))

        for idx, t in enumerate(self.time_indices):

            if t in self.results_dict.keys():

                mdl = self.results_dict[t].get_contingency_hvdc_report(
                    loading_threshold=loading_threshold,
                    reverse=reverse,
                )
                data = mdl.get_data()[2]

                if data.shape[0] == 0:
                    data = np.zeros(shape=(1, len(mdl.get_data()[1])))

            else:
                data = np.zeros(shape=(1, len(mdl.get_data()[1])))

            # complete the report data with Time info
            time_data = np.array([[t, self.time_array[idx].strftime("%d/%m/%Y %H:%M:%S")]] * data.shape[0])
            data = np.concatenate((time_data, data), axis=1)

            # add to main data set
            data_all = np.concatenate((data_all, data), axis=0)

        columns_all, data_all = self.add_probability_info(
            columns=columns_all,
            data=data_all
        )

        self.reports[title] = ResultsTable(
            data=data_all,
            index=np.arange(data_all.shape[0]),
            columns=columns_all,
            title=title,
            ylabel='(p.u.)',
            xlabel='',
            units='',
        )

    def create_branch_monitoring_report(self):

        title = ResultTypes.TsBranchMonitoring.value

        if len(self.results_dict.values()) == 0:
            return

        mdl = list(self.results_dict.values())[0].get_monitoring_logic_report()
        columns_all = ['Line', 'Time index', 'Time'] + mdl.get_data()[1]
        data_all = np.empty(shape=(0, len(columns_all)))

        for idx, t in enumerate(self.time_indices):

            if t in self.results_dict.keys():
                # critical_elements = self.results_dict[t].
                mdl = self.results_dict[t].get_monitoring_logic_report()

                # complete the report data with Time info
                time_data = np.array(
                    [[t, self.time_array[idx].strftime("%d/%m/%Y %H:%M:%S")]] * mdl.get_data()[2].shape[0])
                data = np.concatenate((np.array([mdl.get_data()[0]]).T, time_data, mdl.get_data()[2]), axis=1)

                # add to main data set
                data_all = np.concatenate((data_all, data), axis=0)

        self.reports[title] = ResultsTable(
            data=data_all,
            index=np.arange(data_all.shape[0]),
            columns=columns_all,
            title=title,
            ylabel='(p.u.)',
            xlabel='',
            units='',
        )

    def create_contingency_branches_report(self, loading_threshold=100.0, reverse=True):

        title = f'{ResultTypes.TsContingencyBranches.value}. ' \
                f'Loading threshold: {str(loading_threshold)}. ' \
                f'Reverse: {str(reverse)}'

        if len(self.results_dict.values()) == 0:
            return

        mdl = self.get_contingency_full_report(
            loading_threshold=loading_threshold,
            reverse=reverse
        )

        df = mdl.to_df()

        # Filter dataframe values
        df_ = df[['Time index', 'Monitored', 'Contingency']].drop_duplicates()

        # Set the hourly probability
        prod_dict = dict(zip(self.time_indices, self.sampled_probabilities))
        df_['Prob.'] = df_['Time index'].astype(int).map(prod_dict)

        # Get the monitored/contingency probability
        mc_prob = df_[['Monitored', 'Contingency', 'Prob.']].groupby(
            ['Monitored',
             'Contingency'
             ]
        ).agg({
            'Prob.': sum
        }).reset_index()

        self.reports[title] = ResultsTable(
            data=mc_prob.values,
            index=mc_prob.index,
            columns=mc_prob.columns,
            title=title,
            ylabel='',
            xlabel='',
            units='',
        )

    def create_critical_branches_report(self, loading_threshold=100.0, reverse=True):

        title = f'{ResultTypes.TsCriticalBranches.value}. ' \
                f'Loading threshold: {str(loading_threshold)}. ' \
                f'Reverse: {str(reverse)}'

        if len(self.results_dict.values()) == 0:
            return

        mdl = self.get_contingency_full_report(
            loading_threshold=loading_threshold,
            reverse=reverse
        )

        df = mdl.to_df()

        # Filter dataframe values
        df_ = df[['Time index', 'Monitored', 'Contingency']].drop_duplicates()

        # Set the hourly probability
        prod_dict = dict(zip(self.time_indices, self.sampled_probabilities))
        df_['Prob.'] = df_['Time index'].astype(int).map(prod_dict)

        # Get the monitored/contingency probability
        mc_prob = df_[['Monitored', 'Contingency', 'Prob.']].groupby(
            ['Monitored',
             'Contingency'
             ]
        ).agg({
            'Prob.': sum
        }).reset_index()

        # Add probability to contingency names
        mc_prob['Contingency'] = mc_prob['Contingency'] + ' [' + mc_prob['Prob.'].round(decimals=2).astype(str) + ']'

        # Group by monitor aggregating contingency names as list
        mc_df = mc_prob[['Monitored', 'Contingency']].groupby(
            'Monitored'
        ).agg({
            'Contingency': list
        })

        # Get monitor/contingency dict
        mc_dict = mc_df.T.to_dict(orient='records')[0]

        # Get probability by monitored
        m_prob = df_[['Time index', 'Monitored', 'Prob.']].drop_duplicates(
            keep='first',
        ).groupby(
            ['Monitored']
        ).agg({
            'Prob.': sum
        })

        # Complete info with contingency probability
        contingecies = ['; '.join(v) for v in m_prob.index.map(mc_dict).values]
        m_prob['Contingencies'] = contingecies

        self.reports[title] = ResultsTable(
            data=m_prob.values,
            index=m_prob.index,
            columns=m_prob.columns,
            title=title,
            ylabel='',
            xlabel='',
            units='',
        )
