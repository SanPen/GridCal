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

import pandas as pd
import numpy as np
import time

from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Core.time_series_opf_data import compile_opf_time_circuit, OpfTimeCircuit
from GridCal.Engine.Simulations.OPF.ntc_opf import OpfNTC
from GridCal.Engine.Simulations.OPF.opf_ntc_driver import OptimalNetTransferCapacityOptions, OptimalNetTransferCapacityResults
from GridCal.Engine.Simulations.driver_types import SimulationTypes
from GridCal.Engine.Simulations.driver_template import TimeSeriesDriverTemplate
from GridCal.Engine.Simulations.Clustering.clustering import kmeans_approximate_sampling
from GridCal.Engine.Simulations.ATC.available_transfer_capacity_driver import compute_alpha
from GridCal.Engine.Simulations.results_template import ResultsTemplate
from GridCal.Engine.Simulations.result_types import ResultTypes
from GridCal.Engine.Simulations.results_table import ResultsTable
from GridCal.Engine.Simulations.LinearFactors import LinearAnalysis

try:
    from ortools.linear_solver import pywraplp
except ModuleNotFoundError:
    print('ORTOOLS not found :(')


class OptimalNetTransferCapacityTimeSeriesResults(ResultsTemplate):

    def __init__(self, bus_names, br_names,
                 rates, contingency_rates, time_array, time_indices,
                 sampled_probabilities=None, max_report_elements=5):
        """

        :param br_names:
        :param bus_names:
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
            available_results=[
                ResultTypes.OptimalNetTransferCapacityTimeSeriesReport
            ],

            data_variables=[])

        self.time_array = time_array
        self.time_indices = time_indices
        self.branch_names = np.array(br_names, dtype=object)
        self.bus_names = bus_names
        self.rates = rates
        self.contingency_rates = contingency_rates
        self.base_exchange = 0
        self.raw_report = None
        self.report = None
        self.report_headers = None
        self.report_indices = None
        self.max_report_elements = max_report_elements

        self.sampled_probabilities = sampled_probabilities

        self.results_dict = dict()
        self.optimal_idx = []
        self.feasible_idx = []
        self.infeasible_idx = []
        self.unbounded_idx = []
        self.abnormal_idx = []
        self.not_solved = []

        self.elapsed = 0

        if sampled_probabilities is None and len(self.time_array) > 0:
            pct = 1 / len(self.time_array)
            sampled_probabilities = np.ones(len(self.time_array)) * pct

        self.sampled_probabilities = sampled_probabilities

    def mdl(self, result_type) -> "ResultsTable":
        """
        Plot the results
        :param result_type: type of results (string)
        :return: DataFrame of the results (or None if the result was not understood)
        """

        if result_type == ResultTypes.OptimalNetTransferCapacityTimeSeriesReport:
            labels, columns, y = self.get_contingency_report()
            y_label = ''
            title = result_type.value[0]

        else:
            raise Exception('No results available')

        mdl = ResultsTable(data=y,
                           index=labels,
                           columns=columns,
                           title=title,
                           ylabel=y_label,
                           xlabel='',
                           units=y_label)
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

    def make_report(self, path_out=None):
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


    def get_contingency_report(self):

        prob_dict = dict(zip(self.time_indices, self.sampled_probabilities))

        if len(self.results_dict.values()) == 0:
            print("Sin resultados")
            return

        labels, columns, data = list(self.results_dict.values())[0].get_contingency_report()
        shifter_names, shift_idx = self.get_used_shifters()
        hvdc_names = list(list(self.results_dict.values())[0].hvdc_names)
        columns_all = ['Time index', 'Time', 'NTC (MW)'] + columns + shifter_names + hvdc_names
        data_all = np.empty(shape=(0, len(columns_all)))

        for idx, t in enumerate(self.time_indices):

            if t in self.results_dict.keys():

                # get ntc value
                ntc = np.floor(self.results_dict[t].get_exchange_power())

                if ntc != 0:

                    l, c, data = self.results_dict[t].get_contingency_report(
                        max_report_elements=self.max_report_elements)

                    # get phase shifter and hvdc data
                    shifter_data = np.array([self.results_dict[t].phase_shift[shift_idx]] * data.shape[0])
                    hvdc_data = np.array([self.results_dict[t].hvdc_Pf] * data.shape[0])

                    # add new columns to report
                    data = np.concatenate((data, shifter_data, hvdc_data), axis=1)

                else:

                    data = np.zeros(shape=(1, len(columns) + len(shifter_names) + len(hvdc_names)))

            # complete the data with time and ntc columns
            extra_data = np.array([[t, self.time_array[idx], ntc]] * data.shape[0])
            data = np.concatenate((extra_data, data), axis=1)

            # add to main data set
            data_all = np.concatenate((data_all, data), axis=0)

        # sort data by ntc and time index, descending to compute probability factor
        data_all = data_all[np.lexsort(
            (np.abs(data_all[:, 11].astype(float)), data_all[:, 0], data_all[:, 2])
        )][::-1]

        # add column into data
        prob = np.zeros((data_all.shape[0], 1))
        data_all = np.append(prob, data_all, axis=1)
        columns_all = ['Prob.'] + columns_all

        # compute cumulative probability
        time_prev = 0
        pct = 0
        for row in range(data_all.shape[0]):
            t = int(data_all[row, 1])
            if t != time_prev:
                pct += prob_dict[t]
                time_prev = t

            data_all[row, 0] = pct

        # return report data
        labels_all = np.arange(data_all.shape[0])

        # convert time to formated string
        data_all[:, 2] = [t.strftime("%d/%m/%Y %H:%M:%S") for t in data_all[:, 2]]

        print('Ejecutado en {0} scs. para {1} casos'.format(self.elapsed, len(self.time_array)))
        return labels_all, columns_all, data_all

    def get_contingency_branch_report(self):

        prob_dict = dict(zip(self.time_indices, self.sampled_probabilities))

        if len(self.results_dict.values()) == 0:
            return

        labels, columns, data = list(self.results_dict.values())[0].get_contingency_report()
        shifter_names, shift_idx = self.get_used_shifters()
        hvdc_names = list(list(self.results_dict.values())[0].hvdc_names)
        columns_all = ['Time index', 'Time', 'NTC (MW)'] + columns + shifter_names + hvdc_names
        data_all = np.empty(shape=(0, len(columns_all)))

        for idx, t in enumerate(self.time_indices):

            if t in self.results_dict.keys():

                # get ntc value
                ntc = np.floor(self.results_dict[t].get_exchange_power())

                l, c, data = self.results_dict[t].get_contingency_branch_report(
                    max_report_elements=self.max_report_elements)

                # get phase shifter and hvdc data
                shifter_data = np.array([self.results_dict[t].phase_shift[shift_idx]] * data.shape[0])
                hvdc_data = np.array([self.results_dict[t].hvdc_Pf] * data.shape[0])

                # add new columns to report
                data = np.concatenate((data, shifter_data, hvdc_data), axis=1)

            else:
                ntc = 0

                data = np.zeros(shape=(1, len(columns) + len(shifter_names) + len(hvdc_names)))

            # complete the data with time and ntc columns
            extra_data = np.array([[t, self.time_array[idx].strftime("%d/%m/%Y %H:%M:%S"), ntc]] * data.shape[0])
            data = np.concatenate((extra_data, data), axis=1)

            # add to main data set
            data_all = np.concatenate((data_all, data), axis=0)

        # sort data by ntc and time index, descending to compute probability factor

        data_all = data_all[np.lexsort(
            (np.abs(data_all[:, 11].astype(float)), data_all[:, 0], data_all[:, 2])
        )][::-1]

        # add column into data
        prob = np.zeros((data_all.shape[0], 1))
        data_all = np.append(prob, data_all, axis=1)
        columns_all = ['Prob.'] + columns_all

        # compute cumulative probability
        time_prev = 0
        pct = 0
        for row in range(data_all.shape[0]):
            t = data_all[row, 1]
            if t != time_prev:
                pct += prob_dict[t]
                time_prev = t

            data_all[row, 0] = pct

        # return report data
        labels_all = np.arange(data_all.shape[0])
        return labels_all, columns_all, data_all

    def get_contingency_generation_report(self):

        prob_dict = dict(zip(self.time_indices, self.sampled_probabilities))

        if len(self.results_dict.values()) == 0:
            return

        labels, columns, data = list(self.results_dict.values())[0].get_contingency_report()
        shifter_names, shift_idx = self.get_used_shifters()
        hvdc_names = list(list(self.results_dict.values())[0].hvdc_names)
        columns_all = ['Time index', 'Time', 'NTC (MW)'] + columns + shifter_names + hvdc_names
        data_all = np.empty(shape=(0, len(columns_all)))

        for idx, t in enumerate(self.time_indices):

            if t in self.results_dict.keys():

                # get ntc value
                ntc = np.floor(self.results_dict[t].get_exchange_power())

                l, c, data = self.results_dict[t].get_contingency_generation_report(
                    max_report_elements=self.max_report_elements)

                # get phase shifter and hvdc data
                shifter_data = np.array([self.results_dict[t].phase_shift[shift_idx]] * data.shape[0])
                hvdc_data = np.array([self.results_dict[t].hvdc_Pf] * data.shape[0])

                # add new columns to report
                data = np.concatenate((data, shifter_data, hvdc_data), axis=1)

            else:
                ntc = 0

                data = np.zeros(shape=(1, len(columns) + len(shifter_names) + len(hvdc_names)))

            # complete the data with time and ntc columns
            extra_data = np.array([[t, self.time_array[idx].strftime("%d/%m/%Y %H:%M:%S"), ntc]] * data.shape[0])
            data = np.concatenate((extra_data, data), axis=1)

            # add to main data set
            data_all = np.concatenate((data_all, data), axis=0)

        # sort data by ntc and time index, descending to compute probability factor

        data_all = data_all[np.lexsort(
            (np.abs(data_all[:, 11].astype(float)), data_all[:, 0], data_all[:, 2])
        )][::-1]

        # add column into data
        prob = np.zeros((data_all.shape[0], 1))
        data_all = np.append(prob, data_all, axis=1)
        columns_all = ['Prob.'] + columns_all

        # compute cumulative probability
        time_prev = 0
        pct = 0
        for row in range(data_all.shape[0]):
            t = data_all[row, 1]
            if t != time_prev:
                pct += prob_dict[t]
                time_prev = t

            data_all[row, 0] = pct

        # return report data
        labels_all = np.arange(data_all.shape[0])
        return labels_all, columns_all, data_all

    def get_contingency_hvdc_report(self):

        prob_dict = dict(zip(self.time_indices, self.sampled_probabilities))

        if len(self.results_dict.values()) == 0:
            return

        labels, columns, data = list(self.results_dict.values())[0].get_contingency_report()
        shifter_names, shift_idx = self.get_used_shifters()
        hvdc_names = list(list(self.results_dict.values())[0].hvdc_names)
        columns_all = ['Time index', 'Time', 'NTC (MW)'] + columns + shifter_names + hvdc_names
        data_all = np.empty(shape=(0, len(columns_all)))

        for idx, t in enumerate(self.time_indices):

            if t in self.results_dict.keys():

                # get ntc value
                ntc = np.floor(self.results_dict[t].get_exchange_power())

                l, c, data = self.results_dict[t].get_contingency_hvdc_report(
                    max_report_elements=self.max_report_elements)

                # get phase shifter and hvdc data
                shifter_data = np.array([self.results_dict[t].phase_shift[shift_idx]] * data.shape[0])
                hvdc_data = np.array([self.results_dict[t].hvdc_Pf] * data.shape[0])

                # add new columns to report
                data = np.concatenate((data, shifter_data, hvdc_data), axis=1)

            else:
                ntc = 0

                data = np.zeros(shape=(1, len(columns) + len(shifter_names) + len(hvdc_names)))

            # complete the data with time and ntc columns
            extra_data = np.array([[t, self.time_array[idx].strftime("%d/%m/%Y %H:%M:%S"), ntc]] * data.shape[0])
            data = np.concatenate((extra_data, data), axis=1)

            # add to main data set
            data_all = np.concatenate((data_all, data), axis=0)

        # sort data by ntc and time index, descending to compute probability factor

        data_all = data_all[np.lexsort(
            (np.abs(data_all[:, 11].astype(float)), data_all[:, 0], data_all[:, 2])
        )][::-1]

        # add column into data
        prob = np.zeros((data_all.shape[0], 1))
        data_all = np.append(prob, data_all, axis=1)
        columns_all = ['Prob.'] + columns_all

        # compute cumulative probability
        time_prev = 0
        pct = 0
        for row in range(data_all.shape[0]):
            t = data_all[row, 1]
            if t != time_prev:
                pct += prob_dict[t]
                time_prev = t

            data_all[row, 0] = pct

        # return report data
        labels_all = np.arange(data_all.shape[0])
        return labels_all, columns_all, data_all


class OptimalNetTransferCapacityTimeSeriesDriver(TimeSeriesDriverTemplate):

    tpe = SimulationTypes.OptimalNetTransferCapacityTimeSeries_run

    def __init__(self, grid: MultiCircuit, options: OptimalNetTransferCapacityOptions, start_=0, end_=None,
                 use_clustering=False, cluster_number=100):
        """

        :param grid: MultiCircuit Object
        :param options: Optimal net transfer capacity options
        :param start_: time index to start (optional)
        :param end_: time index to end (optional)
        """
        TimeSeriesDriverTemplate.__init__(
            self,
            grid=grid,
            start_=start_,
            end_=end_)

        # Options to use

        self.options = options
        self.unresolved_counter = 0

        self.use_clustering = use_clustering
        self.cluster_number = cluster_number

        self.results = OptimalNetTransferCapacityTimeSeriesResults(
            br_names=[],
            bus_names=[],
            rates=[],
            contingency_rates=[],
            time_array=[],
            time_indices=[])

    name = tpe.value

    def compute_exchange_sensitivity(self, linear, numerical_circuit: OpfTimeCircuit, Pload, Pgen, t):

        # compute the branch exchange sensitivity (alpha)
        alpha = compute_alpha(
            ptdf=linear.PTDF,
            P0=numerical_circuit.Sbus.real[:, t],
            Pinstalled=numerical_circuit.bus_installed_power,
            Pload=Pload[:, t].real,
            Pgen=numerical_circuit.generator_data.get_injections_per_bus()[:, t].real,
            idx1=self.options.area_from_bus_idx,
            idx2=self.options.area_to_bus_idx,
            dT=self.options.sensitivity_dT,
            mode=self.options.sensitivity_mode.value)

        return alpha

    def opf(self):
        """
        Run thread
        """

        self.progress_signal.emit(0)

        nc = compile_opf_time_circuit(self.grid)
        time_indices = self.get_time_indices()

        Pload = nc.load_data.get_injections_per_bus()
        Pgen = nc.generator_data.get_injections_per_bus()

        nt = len(time_indices)

        # declare the linear analysis
        linear = LinearAnalysis(
            grid=self.grid,
            distributed_slack=False,
            correct_values=False)

        linear.run()

        if self.use_clustering:

            if self.progress_text is not None:
                self.progress_text.emit('Clustering...')

            else:
                print('Clustering...')

            X = nc.Sbus
            X = X[:, time_indices].real.T

            # cluster and re-assign the time indices
            time_indices, sampled_probabilities = kmeans_approximate_sampling(
                X, n_points=self.cluster_number)

            self.results = OptimalNetTransferCapacityTimeSeriesResults(
                br_names=linear.numerical_circuit.branch_names,
                bus_names=linear.numerical_circuit.bus_names,
                rates=nc.Rates,
                contingency_rates=nc.ContingencyRates,
                time_array=nc.time_array[time_indices],
                sampled_probabilities=sampled_probabilities,
                time_indices=time_indices)

        else:
            self.results = OptimalNetTransferCapacityTimeSeriesResults(
                br_names=linear.numerical_circuit.branch_names,
                bus_names=linear.numerical_circuit.bus_names,
                rates=nc.Rates,
                contingency_rates=nc.ContingencyRates,
                time_array=nc.time_array[time_indices],
                time_indices=time_indices)

        for t_idx, t in enumerate(time_indices):

            # update progress bar
            progress = (t_idx + 1) / len(time_indices) * 100
            self.progress_signal.emit(progress)

            if self.progress_text is not None:
                self.progress_text.emit('Optimal net transfer capacity at ' + str(self.grid.time_profile[t]))

            else:
                print('Optimal net transfer capacity at ' + str(self.grid.time_profile[t]))

            # sensitivities
            if self.options.monitor_only_sensitive_branches:
                alpha = self.compute_exchange_sensitivity(
                    linear=linear,
                    numerical_circuit=nc,
                    Pload=Pload,
                    Pgen=Pgen,
                    t=t)
            else:
                alpha = np.ones(nc.nbr)

            # Define the problem
            self.progress_text.emit('Formulating NTC OPF...')

            problem = OpfNTC(
                numerical_circuit=nc,
                area_from_bus_idx=self.options.area_from_bus_idx,
                area_to_bus_idx=self.options.area_to_bus_idx,
                alpha=alpha,
                LODF=linear.LODF,
                PTDF=linear.PTDF,
                solver_type=self.options.mip_solver,
                generation_formulation=self.options.generation_formulation,
                monitor_only_sensitive_branches=self.options.monitor_only_sensitive_branches,
                branch_sensitivity_threshold=self.options.branch_sensitivity_threshold,
                skip_generation_limits=self.options.skip_generation_limits,
                dispatch_all_areas=self.options.dispatch_all_areas,
                tolerance=self.options.tolerance,
                weight_power_shift=self.options.weight_power_shift,
                weight_generation_cost=self.options.weight_generation_cost,
                consider_contingencies=self.options.consider_contingencies,
                consider_hvdc_contingencies=self.options.consider_hvdc_contingencies,
                consider_gen_contingencies=self.options.consider_gen_contingencies,
                generation_contingency_threshold=self.options.generation_contingency_threshold,
                logger=self.logger)

            # Solve
            time_str = str(nc.time_array[time_indices][t_idx])
            self.progress_text.emit('Solving NTC OPF...['+time_str+']')

            problem.formulate_ts(t=t)

            solved = problem.solve_ts(
                with_check=self.options.with_check,
                time_limit_ms=self.options.time_limit_ms)

            self.logger += problem.logger

            if solved:
                self.results.optimal_idx.append(t)

            else:

                if problem.status == pywraplp.Solver.FEASIBLE:
                    self.results.feasible_idx.append(t)
                    self.logger.add_error(
                        'Feasible solution, not optimal or timeout',
                        'NTC OPF')

                if problem.status == pywraplp.Solver.INFEASIBLE:
                    self.results.infeasible_idx.append(t)
                    self.logger.add_error(
                        'Unfeasible solution',
                        'NTC OPF')

                if problem.status == pywraplp.Solver.UNBOUNDED:
                    self.results.unbounded_idx.append(t)
                    self.logger.add_error(
                        'Proved unbounded',
                        'NTC OPF')

                if problem.status == pywraplp.Solver.ABNORMAL:
                    self.results.abnormal_idx.append(t)
                    self.logger.add_error(
                        'Abnormal solution, some error occurred',
                        'NTC OPF')

                if problem.status == pywraplp.Solver.NOT_SOLVED:
                    self.results.not_solved.append(t)
                    self.logger.add_error(
                        'Not solved',
                        'NTC OPF')

            # pack the results
            result = OptimalNetTransferCapacityResults(
                bus_names=nc.bus_data.bus_names,
                branch_names=nc.branch_data.branch_names,
                load_names=nc.load_data.load_names,
                generator_names=nc.generator_data.generator_names,
                battery_names=nc.battery_data.battery_names,
                hvdc_names=nc.hvdc_data.names,
                Sbus=problem.get_power_injections(),
                voltage=problem.get_voltage(),
                battery_power=np.zeros((nc.nbatt, 1)),
                controlled_generation_power=problem.get_generator_power(),
                Sf=problem.get_branch_power_from(),
                loading=problem.get_loading(),
                solved=bool(solved),
                bus_types=nc.bus_types,
                hvdc_flow=problem.get_hvdc_flow(),
                hvdc_loading=problem.get_hvdc_loading(),
                phase_shift=problem.get_phase_angles(),
                generation_delta=problem.get_generator_delta(),
                inter_area_branches=problem.inter_area_branches,
                inter_area_hvdc=problem.inter_area_hvdc,
                alpha=alpha,
                contingency_branch_flows_list=problem.get_contingency_flows_list(),
                contingency_branch_indices_list=problem.contingency_indices_list,
                contingency_generation_flows_list=problem.get_contingency_gen_flows_list(),
                contingency_generation_indices_list=problem.contingency_gen_indices_list,
                contingency_hvdc_flows_list=problem.get_contingency_hvdc_flows_list(),
                contingency_hvdc_indices_list=problem.contingency_hvdc_indices_list,
                rates=nc.branch_data.branch_rates[:, t],
                contingency_rates=nc.branch_data.branch_contingency_rates[:, t])

            self.results.results_dict[t] = result

            if self.progress_signal is not None:
                self.progress_signal.emit((t_idx + 1) / nt * 100)

            if self.__cancel__:
                break


    def run(self):
        """

        :return:
        """
        start = time.time()

        self.opf()
        self.progress_text.emit('Done!')

        end = time.time()
        self.results.elapsed = end - start


if __name__ == '__main__':

    import GridCal.Engine.basic_structures as bs
    import GridCal.Engine.Devices as dev
    from GridCal.Engine.Simulations.ATC.available_transfer_capacity_driver import AvailableTransferMode
    from GridCal.Engine import FileOpen, LinearAnalysis

    fname = r'd:\0.ntc_opf\Propuesta_2026_v22_20260729_17_fused_PMODE1.gridcal'
    path_out = r'd:\0.ntc_opf\Propuesta_2026_v22_20260729_17_fused_PMODE1.csv'
    # fname = r'd:\v19_20260105_22_zero_100hconsecutivas_active_profilesEXP_timestamp_FRfalse_PMODE1.gridcal'
    # path_out = r'd:\v19_20260105_22_zero_100hconsecutivas_active_profilesEXP_timestamp_FRfalse_PMODE1.csv'

    circuit = FileOpen(fname).open()

    areas_from_idx = [0]
    areas_to_idx = [1]

    # areas_from_idx = [7]
    # areas_to_idx = [0, 1, 2, 3, 4]

    areas_from = [circuit.areas[i] for i in areas_from_idx]
    areas_to = [circuit.areas[i] for i in areas_to_idx]

    compatible_areas = True
    for a1 in areas_from:
        if a1 in areas_to:
            compatible_areas = False
            print("The area from '{0}' is in the list of areas to. This cannot be.".format(a1.name),
                  'Incompatible areas')

    for a2 in areas_to:
        if a2 in areas_from:
            compatible_areas = False
            print("The area to '{0}' is in the list of areas from. This cannot be.".format(a2.name),
                  'Incompatible areas')

    lst_from = circuit.get_areas_buses(areas_from)
    lst_to = circuit.get_areas_buses(areas_to)
    lst_br = circuit.get_inter_areas_branches(areas_from, areas_to)
    lst_br_hvdc = circuit.get_inter_areas_hvdc_branches(areas_from, areas_to)

    idx_from = np.array([i for i, bus in lst_from])
    idx_to = np.array([i for i, bus in lst_to])
    idx_br = np.array([i for i, bus, sense in lst_br])
    sense_br = np.array([sense for i, bus, sense in lst_br])
    idx_hvdc_br = np.array([i for i, bus, sense in lst_br_hvdc])
    sense_hvdc_br = np.array([sense for i, bus, sense in lst_br_hvdc])

    if len(idx_from) == 0:
        print('The area "from" has no buses!')

    if len(idx_to) == 0:
        print('The area "to" has no buses!')

    if len(idx_br) == 0:
        print('There are no inter-area branches!')


    options = OptimalNetTransferCapacityOptions(
        area_from_bus_idx=idx_from,
        area_to_bus_idx=idx_to,
        mip_solver=bs.MIPSolvers.CBC,
        generation_formulation=dev.GenerationNtcFormulation.Proportional,
        monitor_only_sensitive_branches=True,
        branch_sensitivity_threshold=0.05,
        skip_generation_limits=True,
        consider_contingencies=True,
        consider_gen_contingencies=True,
        consider_hvdc_contingencies=True,
        generation_contingency_threshold=1000,
        dispatch_all_areas=False,
        tolerance=1e-2,
        sensitivity_dT=100.0,
        sensitivity_mode=AvailableTransferMode.InstalledPower,
        # todo: checkear si queremos el ptdf por potencia generada
        perform_previous_checks=False,
        weight_power_shift=1e5,
        weight_generation_cost=1e2,
        with_check=False,
        time_limit_ms=1e4,
        max_report_elements=5)

    print('Running optimal net transfer capacity...')

    # set optimal net transfer capacity driver instance
    start = 0
    end = 1  #circuit.get_time_number()-1

    driver = OptimalNetTransferCapacityTimeSeriesDriver(
        grid=circuit,
        options=options,
        start_=start,
        end_=end,
        use_clustering=False,
        cluster_number=1)

    driver.run()

    driver.results.make_report(path_out=path_out)
    # driver.results.make_report()
