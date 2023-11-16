# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
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
import time
from typing import Union

from GridCalEngine.Core.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Core.DataStructures.numerical_circuit import compile_numerical_circuit_at, NumericalCircuit
from GridCalEngine.Simulations.NTC.ntc_opf import run_linear_ntc_opf_ts
from GridCalEngine.Simulations.NTC.ntc_driver import OptimalNetTransferCapacityOptions, OptimalNetTransferCapacityResults
from GridCalEngine.Simulations.NTC.ntc_ts_results import OptimalNetTransferCapacityTimeSeriesResults
from GridCalEngine.Simulations.driver_types import SimulationTypes
from GridCalEngine.Simulations.driver_template import TimeSeriesDriverTemplate
from GridCalEngine.Simulations.Clustering.clustering import kmeans_sampling
from GridCalEngine.Simulations.ATC.available_transfer_capacity_driver import compute_alpha
from GridCalEngine.Simulations.LinearFactors.linear_analysis import LinearAnalysis
from GridCalEngine.Simulations.Clustering.clustering_results import ClusteringResults
from GridCalEngine.basic_structures import Logger
from GridCalEngine.enumerations import AvailableTransferMode

try:
    from ortools.linear_solver import pywraplp
except ModuleNotFoundError:
    print('ORTOOLS not found :(')


class OptimalNetTransferCapacityTimeSeriesDriver(TimeSeriesDriverTemplate):

    tpe = SimulationTypes.OptimalNetTransferCapacityTimeSeries_run

    def __init__(self, grid: MultiCircuit,
                 options: OptimalNetTransferCapacityOptions,
                 time_indices: np.ndarray,
                 clustering_results: Union[ClusteringResults, None] = None):
        """

        :param grid: MultiCircuit Object
        :param options: Optimal net transfer capacity options
        :param time_indices: time index to start (optional)
        :param clustering_results: ClusteringResults (optional)
        """
        TimeSeriesDriverTemplate.__init__(
            self,
            grid=grid,
            time_indices=time_indices,
            clustering_results=clustering_results)

        # Options to use

        self.options = options
        self.unresolved_counter = 0

        self.logger = Logger()

        self.results = OptimalNetTransferCapacityTimeSeriesResults(
            branch_names=[],
            bus_names=[],
            generator_names=[],
            load_names=[],
            rates=[],
            contingency_rates=[],
            time_array=[],
            time_indices=[],
            sampled_probabilities=[],
            trm=self.options.trm,
            ntc_load_rule=self.options.ntc_load_rule,
            loading_threshold_to_report=self.options.loading_threshold_to_report,
            reversed_sort_loading=self.options.reversed_sort_loading,
        )

        self.installed_alpha = None
        self.installed_alpha_n1 = None

    name = tpe.value

    def compute_exchange_sensitivity(self, linear, numerical_circuit: NumericalCircuit, t, with_n1=True):

        # compute the branch exchange sensitivity (alpha)
        tm0 = time.time()
        alpha, alpha_n1 = compute_alpha(
            ptdf=linear.PTDF,
            lodf=linear.LODF if with_n1 else None,
            P0=numerical_circuit.Sbus.real[:, t],
            Pinstalled=numerical_circuit.bus_installed_power,
            Pgen=numerical_circuit.generator_data.get_injections_per_bus()[:, t].real,
            Pload=numerical_circuit.load_data.get_injections_per_bus()[:, t].real,
            idx1=self.options.area_from_bus_idx,
            idx2=self.options.area_to_bus_idx,
            mode=self.options.transfer_method.value)

        # self.logger.add_info('Exchange sensibility computed in {0:.2f} scs.'.format(time.time()-tm0))
        return alpha, alpha_n1

    def opf(self):
        """
        Run thread
        """

        self.progress_signal.emit(0)

        if self.progress_text is not None:
            self.progress_text.emit('Compiling circuit...')
        else:
            print('Compiling cicuit...')

        tm0 = time.time()
        nc = compile_numerical_circuit_at(self.grid, t_idx=None)
        self.logger.add_info(f'Time circuit compiled in {time.time()-tm0:.2f} scs')
        print(f'Time circuit compiled in {time.time()-tm0:.2f} scs')

        # declare the linear analysis
        if self.progress_text is not None:
            self.progress_text.emit('Computing linear analysis...')
        else:
            print('Computing linear analysis...')

        linear = LinearAnalysis(
            nc=nc,
            distributed_slack=False,
            correct_values=False,
            with_nx=self.options.consider_nx_contingencies,
        )

        tm0 = time.time()
        linear.run()

        self.logger.add_info(f'Linear analysis computed in {time.time()-tm0:.2f} scs.')
        print(f'Linear analysis computed in {time.time()-tm0:.2f} scs.')

        time_indices = self.get_time_indices()

        if self.use_clustering:

            if self.progress_text is not None:
                self.progress_text.emit('Clustering...')

            else:
                print('Clustering...')

            X = nc.Sbus
            X = X[:, time_indices].real.T

            # cluster and re-assign the time indices
            tm1 = time.time()
            time_indices, sampled_probabilities = kmeans_sampling(
                x_input=X,
                n_points=self.cluster_number,
            )

            self.logger.add_info(f'Kmeans sampling computed in {time.time()-tm1:.2f} scs. [{len(time_indices)} points]')
            print(f'Kmeans sampling computed in {time.time()-tm1:.2f} scs. [{len(time_indices)} points]')

        else:
            sampled_probabilities = np.full(len(time_indices), 1.0 / len(time_indices))

        nt = len(time_indices)

        # Initialize results object
        self.results = OptimalNetTransferCapacityTimeSeriesResults(
            branch_names=linear.numerical_circuit.branch_names,
            bus_names=linear.numerical_circuit.bus_names,
            generator_names=linear.numerical_circuit.generator_names,
            load_names=linear.numerical_circuit.load_names,
            rates=nc.Rates,
            contingency_rates=nc.ContingencyRates,
            time_array=nc.time_array[time_indices],
            time_indices=time_indices,
            sampled_probabilities=sampled_probabilities,
            trm=self.options.trm,
            loading_threshold_to_report=self.options.loading_threshold_to_report,
            ntc_load_rule=self.options.ntc_load_rule)

        if self.options.transfer_method == AvailableTransferMode.InstalledPower:
            alpha, alpha_n1 = self.compute_exchange_sensitivity(
                linear=linear,
                numerical_circuit=nc,
                t=0,
                with_n1=self.options.n1_consideration
            )
        else:
            alpha = np.ones(nc.nelm),
            alpha_n1 = np.ones((nc.nelm, nc.nelm)),

        for t_idx, t in enumerate(time_indices):

            # Initialize problem object (needed to reset solver variable names)
            # problem = OpfNTC(
            #     numerical_circuit=nc,
            #     area_from_bus_idx=self.options.area_from_bus_idx,
            #     area_to_bus_idx=self.options.area_to_bus_idx,
            #     LODF=linear.LODF,
            #     LODF_NX=linear.LODF_NX,
            #     PTDF=linear.PTDF,
            #     alpha=alpha,
            #     alpha_n1=alpha_n1,
            #     solver_type=self.options.mip_solver,
            #     generation_formulation=self.options.generation_formulation,
            #     monitor_only_sensitive_branches=self.options.monitor_only_sensitive_branches,
            #     monitor_only_ntc_load_rule_branches=self.options.monitor_only_ntc_load_rule_branches,
            #     branch_sensitivity_threshold=self.options.branch_sensitivity_threshold,
            #     skip_generation_limits=self.options.skip_generation_limits,
            #     dispatch_all_areas=self.options.dispatch_all_areas,
            #     tolerance=self.options.tolerance,
            #     weight_power_shift=self.options.weight_power_shift,
            #     weight_generation_cost=self.options.weight_generation_cost,
            #     consider_contingencies=self.options.consider_contingencies,
            #     consider_hvdc_contingencies=self.options.consider_hvdc_contingencies,
            #     consider_gen_contingencies=self.options.consider_gen_contingencies,
            #     generation_contingency_threshold=self.options.generation_contingency_threshold,
            #     match_gen_load=self.options.match_gen_load,
            #     ntc_load_rule=self.options.ntc_load_rule,
            #     transfer_method=self.options.transfer_method,
            #     logger=self.logger
            # )

            opf_vars = run_linear_ntc_opf_ts(grid=self.grid,
                                             time_indices=self.time_indices,
                                             solver_type=self.options.mip_solver,
                                             zonal_grouping=self.options.zonal_grouping,
                                             skip_generation_limits=self.options.skip_generation_limits,
                                             consider_contingencies=self.options.consider_contingencies,
                                             lodf_threshold=self.options.lodf_tolerance,
                                             maximize_inter_area_flow=self.options.maximize_flows,
                                             buses_areas_1=self.options.area_from_bus_idx,
                                             buses_areas_2=self.options.area_to_bus_idx,
                                             logger=self.logger,
                                             progress_text=self.progress_text.emit,
                                             progress_func=self.progress_signal.emit,
                                             export_model_fname=self.options.export_model_fname)

            self.results.voltage = np.ones((opf_vars.nt, opf_vars.nbus)) * np.exp(1j * opf_vars.bus_vars.theta)
            self.results.bus_shadow_prices = opf_vars.bus_vars.shadow_prices
            self.results.load_shedding = opf_vars.load_vars.shedding
            self.results.battery_power = opf_vars.batt_vars.p
            self.results.battery_energy = opf_vars.batt_vars.e
            self.results.generator_power = opf_vars.gen_vars.p
            self.results.Sf = opf_vars.branch_vars.flows
            self.results.St = -opf_vars.branch_vars.flows
            self.results.overloads = opf_vars.branch_vars.flow_slacks_pos - opf_vars.branch_vars.flow_slacks_neg
            self.results.loading = opf_vars.branch_vars.loading
            self.results.phase_shift = opf_vars.branch_vars.tap_angles
            # self.results.Sbus = problem.get_power_injections()
            self.results.hvdc_Pf = opf_vars.hvdc_vars.flows
            self.results.hvdc_loading = opf_vars.hvdc_vars.loading

            # update progress bar
            progress = (t_idx + 1) / len(time_indices) * 100
            self.progress_signal.emit(progress)

            if self.progress_text is not None:
                self.progress_text.emit('Optimal net transfer capacity at ' + str(self.grid.time_profile[t]))

            else:
                print('Optimal net transfer capacity at ' + str(self.grid.time_profile[t]))

            # # sensitivities
            # if self.options.monitor_only_sensitive_branches or self.options.monitor_only_ntc_load_rule_branches:
            #
            #     if self.options.transfer_method != AvailableTransferMode.InstalledPower:
            #         problem.alpha, problem.alpha_n1 = self.compute_exchange_sensitivity(
            #             linear=linear,
            #             numerical_circuit=nc,
            #             t=t,
            #             with_n1=self.options.n1_consideration)
            #
            # time_str = str(nc.time_array[time_indices][t_idx])
            #
            # # Define the problem
            # self.progress_text.emit('Formulating NTC OPF...['+time_str+']')
            # problem.formulate_ts(t=t)
            #
            # # Solve
            # self.progress_text.emit('Solving NTC OPF...['+time_str+']')
            # solved = problem.solve_ts(
            #     t=t,
            #     time_limit_ms=self.options.time_limit_ms
            # )
            # # print('Problem solved in {0:.2f} scs.'.format(time.time() - tm0))
            #
            # self.logger += problem.logger
            #
            # if solved:
            #     self.results.optimal_idx.append(t)
            #
            # else:
            #
            #     if problem.status == pywraplp.Solver.FEASIBLE:
            #         self.results.feasible_idx.append(t)
            #         self.logger.add_error(
            #             'Feasible solution, not optimal or timeout',
            #             'NTC OPF')
            #
            #     if problem.status == pywraplp.Solver.INFEASIBLE:
            #         self.results.infeasible_idx.append(t)
            #         self.logger.add_error(
            #             'Unfeasible solution',
            #             'NTC OPF')
            #
            #     if problem.status == pywraplp.Solver.UNBOUNDED:
            #         self.results.unbounded_idx.append(t)
            #         self.logger.add_error(
            #             'Proved unbounded',
            #             'NTC OPF')
            #
            #     if problem.status == pywraplp.Solver.ABNORMAL:
            #         self.results.abnormal_idx.append(t)
            #         self.logger.add_error(
            #             'Abnormal solution, some error occurred',
            #             'NTC OPF')
            #
            #     if problem.status == pywraplp.Solver.NOT_SOLVED:
            #         self.results.not_solved.append(t)
            #         self.logger.add_error(
            #             'Not solved',
            #             'NTC OPF')
            #
            # # pack the results
            # idx_w = np.argmax(np.abs(problem.alpha_n1), axis=1)
            # alpha_w = np.take_along_axis(problem.alpha_n1, np.expand_dims(idx_w, axis=1), axis=1)

            result = OptimalNetTransferCapacityResults(
                bus_names=nc.bus_data.names,
                branch_names=nc.branch_data.names,
                load_names=nc.load_data.names,
                generator_names=nc.generator_data.names,
                battery_names=nc.battery_data.names,
                hvdc_names=nc.hvdc_data.names,
                trm=self.options.trm,
                ntc_load_rule=self.options.ntc_load_rule,
                branch_control_modes=nc.branch_data.control_mode,
                hvdc_control_modes=nc.hvdc_data.control_mode,
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
                hvdc_angle_slack=problem.get_hvdc_angle_slacks(),
                inter_area_branches=problem.inter_area_branches,
                inter_area_hvdc=problem.inter_area_hvdc,
                alpha=problem.alpha,
                alpha_n1=problem.alpha_n1,
                alpha_w=alpha_w,
                contingency_branch_flows_list=problem.get_contingency_flows_list(),
                contingency_branch_indices_list=problem.contingency_indices_list,
                contingency_generation_flows_list=problem.get_contingency_gen_flows_list(),
                contingency_generation_indices_list=problem.contingency_gen_indices_list,
                contingency_hvdc_flows_list=problem.get_contingency_hvdc_flows_list(),
                contingency_hvdc_indices_list=problem.contingency_hvdc_indices_list,
                contingency_branch_alpha_list=problem.contingency_branch_alpha_list,
                contingency_generation_alpha_list=problem.contingency_generation_alpha_list,
                contingency_hvdc_alpha_list=problem.contingency_hvdc_alpha_list,
                branch_ntc_load_rule=problem.get_branch_ntc_load_rule(),
                rates=nc.branch_data.rates[:, t],
                contingency_rates=nc.branch_data.contingency_rates[:, t],
                area_from_bus_idx=self.options.area_from_bus_idx,
                area_to_bus_idx=self.options.area_to_bus_idx,
                structural_ntc=problem.structural_ntc,
                sbase=nc.Sbase,
                monitor=problem.monitor,
                monitor_loading=problem.monitor_loading,
                monitor_by_sensitivity=problem.monitor_by_sensitivity,
                monitor_by_unrealistic_ntc=problem.monitor_by_unrealistic_ntc,
                monitor_by_zero_exchange=problem.monitor_by_zero_exchange,
                loading_threshold=self.options.loading_threshold_to_report,
                reversed_sort_loading=self.options.reversed_sort_loading,
            )

            self.progress_text.emit('Creating report...['+time_str+']')

            result.create_all_reports(
                loading_threshold=self.options.loading_threshold_to_report,
                reverse=self.options.reversed_sort_loading,
                save_memory=True,  # todo: check if needed
            )
            self.results.results_dict[t] = result

            if self.progress_signal is not None:
                self.progress_signal.emit((t_idx + 1) / nt * 100)

            if self.__cancel__:
                break

        self.progress_text.emit('Creating final reports...')

        self.results.create_all_reports(
            loading_threshold=self.options.loading_threshold_to_report,
            reverse=self.options.reversed_sort_loading,

        )

        self.progress_text.emit('Done!')

        self.logger.add_info('Ejecutado en {0:.2f} scs. para {1} casos'.format(
            time.time()-tm0, len(self.results.time_array)))

    def run(self):
        """

        :return:
        """
        self.tic()

        self.opf()
        self.progress_text.emit('Done!')

        self.toc()

