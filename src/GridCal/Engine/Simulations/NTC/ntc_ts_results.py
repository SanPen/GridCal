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

import numpy as np
import pandas as pd

from GridCal.Engine.Simulations.results_template import ResultsTemplate
from GridCal.Engine.Simulations.result_types import ResultTypes
from GridCal.Engine.Simulations.results_table import ResultsTable

class OptimalNetTransferCapacityTimeSeriesResults(ResultsTemplate):

    def __init__(self, bus_names, branch_names, generator_names, load_names, rates, contingency_rates, time_array, time_indices,
                 sampled_probabilities=None, loading_threshold_to_report=0.98, trm=0, ntc_load_rule=100):

        """

        :param branch_names:
        :param bus_names:
        :param gen_names:
        :param load_names:
        :param rates:
        :param contingency_rates:
        :param time_array:
        :param time_indices:
        :param sampled_probabilities:
        :param max_report_elements:
        """
        ResultsTemplate.__init__(
            self,
            name='NTC Optimal time series results',
            available_results={
                ResultTypes.FlowReports: [
                    ResultTypes.OpfNtcTsContingencyReport,
                    ResultTypes.OpfNtcTsBaseReport,
                ],
                ResultTypes.Sensibilities: [
                    ResultTypes.AvailableTransferCapacityAlpha,
                    ResultTypes.AvailableTransferCapacityAlphaN1,
                ],
                ResultTypes.DispatchResults: [
                    ResultTypes.GeneratorPower,
                    ResultTypes.GenerationDelta,
                ],
                ResultTypes.BranchMonitoring: [
                    ResultTypes.BranchMonitoring,
                ]
        },

            data_variables=[])

        self.time_array = time_array
        self.time_indices = time_indices
        self.branch_names = np.array(branch_names, dtype=object)
        self.bus_names = bus_names
        self.generator_names = generator_names
        self.load_names = load_names

        self.rates = rates
        self.contingency_rates = contingency_rates
        self.base_exchange = 0
        self.raw_report = None
        self.report = None
        self.report_headers = None
        self.report_indices = None
        self.loading_threshold_to_report = loading_threshold_to_report

        self.sampled_probabilities = sampled_probabilities

        self.results_dict = dict()
        self.optimal_idx = []
        self.feasible_idx = []
        self.infeasible_idx = []
        self.unbounded_idx = []
        self.abnormal_idx = []
        self.not_solved = []

        self.elapsed = 0

        self.trm = trm
        self.ntc_load_rule = ntc_load_rule

        if sampled_probabilities is None and len(self.time_array) > 0:
            pct = 1 / len(self.time_array)
            sampled_probabilities = np.ones(len(self.time_array)) * pct

        self.sampled_probabilities = sampled_probabilities

        self.reports = dict()

    def create_base_report(self):
        labels, columns, y = self.get_base_report()
        y_label = ''
        title = ResultTypes.OpfNtcTsBaseReport.value[0]
        self.reports['base'] = {
            'labels': labels,
            'columns': columns,
            'y': y,
            'title': title,
            'y_label': y_label,
        }

    def create_contingency_report(self):
        labels, columns, y = self.get_contingency_report()
        y_label = ''
        title = ResultTypes.OpfNtcTsContingencyReport.value[0]
        self.reports['contingency'] = {
            'labels': labels,
            'columns': columns,
            'y': y,
            'title': title,
            'y_label': y_label,
        }

    def create_alpha_report(self):
        labels, columns, y = self.get_alpha_report()
        y_label = ''
        title = ResultTypes.AvailableTransferCapacityAlpha.value[0]
        self.reports['alpha'] = {
            'labels': labels,
            'columns': columns,
            'y': y,
            'title': title,
            'y_label': y_label,
        }

    def create_alphan1_report(self):
        labels, columns, y = self.get_alpha_n1_report()
        y_label = ''
        title = ResultTypes.AvailableTransferCapacityAlphaN1.value[0]
        self.reports['alphan1'] = {
            'labels': labels,
            'columns': columns,
            'y': y,
            'title': title,
            'y_label': y_label,
        }

    def create_generation_power_report(self):
        labels, columns, y = self.get_generation_report()
        y_label = '(MW)'
        title = ResultTypes.GeneratorPower.value[0]
        self.reports['generation_power'] = {
            'labels': labels,
            'columns': columns,
            'y': y,
            'title': title,
            'y_label': y_label,
        }

    def create_generation_delta_report(self):
        labels, columns, y = self.get_generation_delta_report()
        y_label = '(MW)'
        title = ResultTypes.GenerationDelta.value[0]
        self.reports['generation_delta'] = {
            'labels': labels,
            'columns': columns,
            'y': y,
            'title': title,
            'y_label': y_label,
        }

    def create_branch_monitoring_report(self):
        labels, columns, y = self.get_branch_monitoring_report()
        y_label = '(p.u.)'
        title = ResultTypes.BranchMonitoring.value[0]
        self.reports['branch_monitoring'] = {
            'labels': labels,
            'columns': columns,
            'y': y,
            'title': title,
            'y_label': y_label,
        }

    def create_all_reports(self):
        self.create_base_report()
        self.create_contingency_report()
        self.create_generation_power_report()
        self.create_generation_delta_report()
        self.create_alpha_report()
        self.create_alphan1_report()
        self.create_branch_monitoring_report()

    def mdl(self, result_type) -> "ResultsTable":
        """
        Plot the results
        :param result_type: type of results (string)
        :return: DataFrame of the results (or None if the result was not understood)
        """

        if result_type == ResultTypes.OpfNtcTsBaseReport:
            if not 'base' in self.reports.keys():
                self.create_base_report()
            report = self.reports['base']

        elif result_type == ResultTypes.OpfNtcTsContingencyReport:
            if not 'contingency' in self.reports.keys():
                self.create_contingency_report()
            report = self.reports['contingency']

        elif result_type == ResultTypes.AvailableTransferCapacityAlpha:
            if not 'alpha' in self.reports.keys():
                self.create_alpha_report()
            report = self.reports['alpha']

        elif result_type == ResultTypes.AvailableTransferCapacityAlphaN1:
            if not 'alphan1' in self.reports.keys():
                self.create_alphan1_report()
            report = self.reports['alphan1']

        elif result_type == ResultTypes.GeneratorPower:
            if not 'generation_power' in self.reports.keys():
                self.create_generation_power_report()
            report = self.reports['generation_power']

        elif result_type == ResultTypes.GenerationDelta:
            if not 'generation_delta' in self.reports.keys():
                self.create_generation_delta_report()
            report = self.reports['generation_delta']

        elif result_type == ResultTypes.BranchMonitoring:
            if not 'branch_monitoring' in self.reports.keys():
                self.create_branch_monitoring_report()
            report = self.reports['branch_monitoring']
        else:
            raise Exception('No results available')

        mdl = ResultsTable(
            data=report['y'],
            index=report['labels'],
            columns=report['columns'],
            title=report['title'],
            ylabel=report['y_label'],
            xlabel='',
            units=report['y_label']
        )

        return mdl

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

        labels, columns, data = self.get_contingency_report()

        df = pd.DataFrame(data=data, columns=columns, index=labels)

        # print result dataframe
        print('\n\n')
        print(df)

        # Save file
        if path_out:
            df.to_csv(path_out, index=False)

    def add_probability_info(self, columns, data):

        prob_dict = dict(zip(self.time_indices, self.sampled_probabilities))

        # sort data by ntc and time index, descending to compute probability factor
        ntc_idx = list(map(str.lower, columns)).index('ntc')
        load_col_name = 'contingency load %' if 'contigency load %' in columns else 'load %'
        cload_idx = list(map(str.lower, columns)).index(load_col_name)
        time_idx = list(map(str.lower, columns)).index('time')
        data = data[np.lexsort(
            (
                data[:, time_idx],
                np.abs(data[:, cload_idx].astype(float)),
                np.abs(data[:, ntc_idx].astype(float)),
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

    def get_alpha_report(self):
        result = list(self.results_dict.values())[0]
        columns = ['Time index', 'Time'] + list(result.branch_names)
        data = np.zeros((len(self.time_indices), len(result.alpha) + 2), np.object)

        for idx, t in enumerate(self.time_indices):
            if t in self.results_dict.keys():
                data[idx, 2:] = self.results_dict[t].alpha
                data[idx, :2] = [t, self.time_array[idx].strftime("%d/%m/%Y %H:%M:%S")]

        labels = np.arange(data.shape[0])

        return labels, columns, data

    def get_alpha_n1_report(self):
        result = list(self.results_dict.values())[0]
        columns = ['Time index', 'Time'] + list(result.branch_names)
        data = np.zeros((len(self.time_indices), len(result.alpha) + 2), np.object)

        for idx, t in enumerate(self.time_indices):
            if t in self.results_dict.keys():
                data[idx, 2:] = self.results_dict[t].alpha_n1
                data[idx, :2] = [t, self.time_array[idx].strftime("%d/%m/%Y %H:%M:%S")]

        labels = np.arange(data.shape[0])

        return labels, columns, data

    def get_generation_report(self):
        labels = self.time_array
        columns = self.generator_names

        data = np.empty(shape=(len(labels), len(columns)))

        for idx, t in enumerate(self.time_indices):
            if t in self.results_dict.keys():
                data[idx] = self.results_dict[t].generator_power

        return labels, columns, data

    def get_generation_delta_report(self):
        labels = self.time_array
        columns = self.generator_names

        data = np.empty(shape=(len(labels), len(columns)))

        for idx, t in enumerate(self.time_indices):
            if t in self.results_dict.keys():
                data[idx] = self.results_dict[t].generation_delta

        return labels, columns, data

    def get_base_report(self):

        labels, columns, data = list(self.results_dict.values())[0].get_ntc_base_report()
        columns_all = ['Time index', 'Time'] + columns
        data_all = np.empty(shape=(0, len(columns_all)))

        for idx, t in enumerate(self.time_indices):
            if t in self.results_dict.keys():
                l, c, data = self.results_dict[t].get_ntc_base_report(
                    loading_threshold=self.loading_threshold_to_report,
                    reverse=True,
                )

            # complete the report data with Time info
            time_data = np.array([[t, self.time_array[idx].strftime("%d/%m/%Y %H:%M:%S")]] * data.shape[0])
            data = np.concatenate((time_data, data), axis=1)

            # add to main data set
            data_all = np.concatenate((data_all, data), axis=0)

        columns_all, data_all = self.add_probability_info(columns=columns_all, data=data_all)

        labels_all = np.arange(data_all.shape[0])

        return labels_all, columns_all, data_all

    def get_contingency_report(self):

        if len(self.results_dict.values()) == 0:
            print("Sin resultados")
            return

        labels, columns, data = list(self.results_dict.values())[0].get_full_contingency_report(
            loading_threshold=self.loading_threshold_to_report,
            reverse=True,
        )
        columns_all = ['Time index', 'Time'] + columns
        data_all = np.empty(shape=(0, len(columns_all)))

        for idx, t in enumerate(self.time_indices):

            if t in self.results_dict.keys():

                ttc = np.floor(self.results_dict[t].get_exchange_power())

                if ttc != 0:
                    l, c, data = self.results_dict[t].get_full_contingency_report(
                        loading_threshold=self.loading_threshold_to_report,
                        reverse=True,
                    )
                else:
                    data = np.zeros(shape=(1, len(columns)))

            # complete the report data with Time info
            time_data = np.array([[t, self.time_array[idx].strftime("%d/%m/%Y %H:%M:%S")]] * data.shape[0])
            data = np.concatenate((time_data, data), axis=1)

            # add to main data set
            data_all = np.concatenate((data_all, data), axis=0)

        columns_all, data_all = self.add_probability_info(
            columns=columns_all,
            data=data_all
        )

        labels_all = np.arange(data_all.shape[0])

        return labels_all, columns_all, data_all

    def get_contingency_branch_report(self):

        if len(self.results_dict.values()) == 0:
            return

        labels, columns, data = list(self.results_dict.values())[0].get_full_contingency_report(
            loading_threshold=self.loading_threshold_to_report,
            reverse=True,
        )

        columns_all = ['Time index', 'Time'] + columns
        data_all = np.empty(shape=(0, len(columns_all)))

        for idx, t in enumerate(self.time_indices):

            if t in self.results_dict.keys():

                l, c, data = self.results_dict[t].get_ntc_contingency_branch_report(
                    loading_threshold=self.loading_threshold_to_report,
                    reverse=True,
                )

            else:
                data = np.zeros(shape=(1, len(columns)))

            # complete the report data with Time info
            time_data = np.array([[t, self.time_array[idx].strftime("%d/%m/%Y %H:%M:%S")]] * data.shape[0])
            data = np.concatenate((time_data, data), axis=1)

            # add to main data set
            data_all = np.concatenate((data_all, data), axis=0)

        columns_all, data_all = self.add_probability_info(columns=columns_all, data=data_all)

        labels_all = np.arange(data_all.shape[0])

        return labels_all, columns_all, data_all

    def get_contingency_generation_report(self):

        if len(self.results_dict.values()) == 0:
            return

        labels, columns, data = list(self.results_dict.values())[0].get_full_contingency_report(
            loading_threshold=self.loading_threshold_to_report,
            reverse=True,
        )
        columns_all = ['Time index', 'Time'] + columns
        data_all = np.empty(shape=(0, len(columns_all)))

        for idx, t in enumerate(self.time_indices):

            if t in self.results_dict.keys():

                l, c, data = self.results_dict[t].get_ntc_contingency_generation_report(
                    loading_threshold=self.loading_threshold_to_report,
                    reverse=True,
                )

            else:
                data = np.zeros(shape=(1, len(columns)))

            # complete the report data with Time info
            time_data = np.array([[t, self.time_array[idx].strftime("%d/%m/%Y %H:%M:%S")]] * data.shape[0])
            data = np.concatenate((time_data, data), axis=1)

            # add to main data set
            data_all = np.concatenate((data_all, data), axis=0)

        columns_all, data_all = self.add_probability_info(
            columns=columns_all,
            data=data_all
        )

        labels_all = np.arange(data_all.shape[0])

        return labels_all, columns_all, data_all

    def get_contingency_hvdc_report(self):

        if len(self.results_dict.values()) == 0:
            return

        labels, columns, data = list(self.results_dict.values())[0].get_full_contingency_report(
            loading_threshold=self.loading_threshold_to_report,
            reverse=True,
        )
        columns_all = ['Time index', 'Time'] + columns
        data_all = np.empty(shape=(0, len(columns_all)))

        for idx, t in enumerate(self.time_indices):

            if t in self.results_dict.keys():

                l, c, data = self.results_dict[t].get_ntc_contingency_hvdc_report(
                    loading_threshold=self.loading_threshold_to_report,
                    reverse=True,
                )
            else:
                data = np.zeros(shape=(1, len(columns)))

            # complete the report data with Time info
            time_data = np.array([[t, self.time_array[idx].strftime("%d/%m/%Y %H:%M:%S")]] * data.shape[0])
            data = np.concatenate((time_data, data), axis=1)

            # add to main data set
            data_all = np.concatenate((data_all, data), axis=0)

        columns_all, data_all = self.add_probability_info(
            columns=columns_all,
            data=data_all
        )

        labels_all = np.arange(data_all.shape[0])
        return labels_all, columns_all, data_all

    def get_branch_monitoring_report(self):
        if len(self.results_dict.values()) == 0:
            return

        labels, columns, data = list(self.results_dict.values())[0].get_monitoring_logic_report()
        columns_all = ['Line', 'Time index', 'Time'] + columns
        data_all = np.empty(shape=(0, len(columns_all)))

        for idx, t in enumerate(self.time_indices):

            if t in self.results_dict.keys():
                # critical_elements = self.results_dict[t].
                l, c, data = self.results_dict[t].get_monitoring_logic_report()

                # complete the report data with Time info
                time_data = np.array([[t, self.time_array[idx].strftime("%d/%m/%Y %H:%M:%S")]] * data.shape[0])
                data = np.concatenate((np.array([l]).T, time_data, data), axis=1)

                # add to main data set
                data_all = np.concatenate((data_all, data), axis=0)

        labels_all = np.arange(data_all.shape[0])
        return labels_all, columns_all, data_all
