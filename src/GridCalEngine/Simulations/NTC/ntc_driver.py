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

from GridCalEngine.Core.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Simulations.NTC.ntc_opf import OpfNTC, get_inter_areas_branches
from GridCalEngine.Core.DataStructures.numerical_circuit import compile_numerical_circuit_at, NumericalCircuit
from GridCalEngine.Simulations.driver_types import SimulationTypes
from GridCalEngine.Simulations.driver_template import DriverTemplate
from GridCalEngine.Simulations.ATC.available_transfer_capacity_driver import compute_alpha
from GridCalEngine.Simulations.NTC.ntc_options import OptimalNetTransferCapacityOptions
from GridCalEngine.Simulations.NTC.ntc_results import OptimalNetTransferCapacityResults
from GridCalEngine.Simulations.ContingencyAnalysis.contingency_analysis_driver import ContingencyAnalysisDriver, \
    ContingencyAnalysisOptions
from GridCalEngine.Simulations.LinearFactors.linear_analysis import LinearAnalysis, LinearMultiContingencies
from GridCalEngine.basic_structures import SolverType
from GridCalEngine.basic_structures import Logger

try:
    from ortools.linear_solver import pywraplp
except ModuleNotFoundError:
    print('ORTOOLS not found :(')


class OptimalNetTransferCapacityDriver(DriverTemplate):
    name = 'Optimal net transfer capacity'
    tpe = SimulationTypes.OPF_NTC_run

    def __init__(self, grid: MultiCircuit, options: OptimalNetTransferCapacityOptions, pf_options: "PowerFlowOptions"):
        """
        PowerFlowDriver class constructor
        @param grid: MultiCircuit Object
        @param options: OPF options
        """
        DriverTemplate.__init__(self, grid=grid)

        # Options to use
        self.options = options
        self.pf_options = pf_options

        self.all_solved = True

        self.logger = Logger()

    def get_steps(self):
        """
        Get time steps list of strings
        """
        return list()

    def compute_exchange_sensitivity(self, linear, numerical_circuit: NumericalCircuit, with_n1=True):

        # compute the branch exchange sensitivity (alpha)
        return compute_alpha(
            ptdf=linear.PTDF,
            lodf=linear.LODF if with_n1 else None,
            P0=numerical_circuit.Sbus.real,
            Pinstalled=numerical_circuit.bus_installed_power,
            Pgen=numerical_circuit.generator_data.get_injections_per_bus()[:, 0].real,
            Pload=numerical_circuit.load_data.get_injections_per_bus()[:, 0].real,
            idx1=self.options.area_from_bus_idx,
            idx2=self.options.area_to_bus_idx,
            dT=self.options.sensitivity_dT,
            mode=self.options.transfer_method.value,
        )

    def opf(self):
        """
        Run a power flow for every circuit
        @return: OptimalPowerFlowResults object
        """

        self.progress_text.emit('Compiling...')

        contingency_flows_list = list()
        contingency_indices_list = list()
        contingency_gen_flows_list = list()
        contingency_gen_indices_list = list()
        contingency_hvdc_flows_list = list()
        contingency_hvdc_indices_list = list()

        contingency_branch_alpha_list = list()
        contingency_generation_alpha_list = list()
        contingency_hvdc_alpha_list = list()

        numerical_circuit = compile_numerical_circuit_at(
            circuit=self.grid,
            t_idx=None,
            apply_temperature=self.pf_options.apply_temperature_correction,
            branch_tolerance_mode=self.pf_options.branch_impedance_tolerance_mode)

        self.progress_text.emit('Running linear analysis...')

        # declare the linear analysis
        linear = LinearAnalysis(
            numerical_circuit=numerical_circuit,
            distributed_slack=False,
            correct_values=False,
            with_nx=self.options.consider_nx_contingencies,
            branch_dict=self.grid.get_branches_wo_hvdc_dict(),
            contingency_group_dict=self.grid.get_contingency_group_dict(),
        )

        linear.run()

        # sensitivities
        if self.options.monitor_only_sensitive_branches or self.options.monitor_only_ntc_load_rule_branches:
            alpha, alpha_n1 = self.compute_exchange_sensitivity(
                linear=linear,
                numerical_circuit=numerical_circuit,
                with_n1=self.options.n1_consideration
            )
        else:
            alpha = np.ones(numerical_circuit.nbr)
            alpha_n1 = np.ones((numerical_circuit.nbr, numerical_circuit.nbr))

        base_problems = False
        if self.options.perform_previous_checks:

            # run dc power flow ----------------------------------------------------------------------------------------
            self.progress_text.emit('Pre-solving base state (DC power flow)...')
            from GridCalEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver, PowerFlowOptions
            pf_options = PowerFlowOptions(solver_type=SolverType.DC)
            pf_drv = PowerFlowDriver(grid=self.grid, options=pf_options)
            pf_drv.run()
            indices = np.where(np.abs(pf_drv.results.loading.real) >= 1.0)
            for m in zip(indices[0]):
                if numerical_circuit.branch_data.monitor_loading[m] and \
                        alpha[m] >= self.options.branch_sensitivity_threshold:
                    elm_name = '{0}'.format(numerical_circuit.branch_names[m])

                    self.logger.add_error('Base overload', elm_name, pf_drv.results.loading[m].real * 100, 100)
                    base_problems = True

            # run contingency analysis ---------------------------------------------------------------------------------
            if self.options.consider_contingencies:
                self.progress_text.emit('Pre-solving base state (Contingency analysis)...')
                options = ContingencyAnalysisOptions(
                    distributed_slack=False,
                    use_provided_flows=True,
                    Pf=pf_drv.results.Sf.real)
                linear_multiple_contingencies = LinearMultiContingencies(grid=self.grid)
                cnt_drv = ContingencyAnalysisDriver(grid=self.grid, options=options,
                                                    linear_multiple_contingencies=linear_multiple_contingencies)
                cnt_drv.run()
                indices = np.where(np.abs(cnt_drv.results.loading.real) >= 1.0)

                for m, c in zip(indices[0], indices[1]):
                    if numerical_circuit.branch_data.monitor_loading[m] and \
                            numerical_circuit.branch_data.contingency_enabled[c] and \
                            alpha[m] >= self.options.branch_sensitivity_threshold:
                        elm_name = '{0} @ {1}'.format(
                            numerical_circuit.branch_names[m],
                            numerical_circuit.branch_names[c])

                        self.logger.add_error(
                            'Base contingency overload',
                            elm_name, cnt_drv.results.loading[m, c].real * 100,
                            100)

                        contingency_flows_list.append(cnt_drv.results.Sf[m, c].real)
                        contingency_indices_list.append((m, c))
                        contingency_branch_alpha_list.append(alpha_n1[m, c])
                        base_problems = True

            if base_problems:
                # get the inter-area Branches and their sign
                inter_area_branches = get_inter_areas_branches(
                    nbr=numerical_circuit.nbr,
                    F=numerical_circuit.branch_data.F,
                    T=numerical_circuit.branch_data.T,
                    buses_areas_1=self.options.area_from_bus_idx,
                    buses_areas_2=self.options.area_to_bus_idx)

                inter_area_hvdc = get_inter_areas_branches(
                    nbr=numerical_circuit.nhvdc,
                    F=numerical_circuit.hvdc_data.get_bus_indices_f(),
                    T=numerical_circuit.hvdc_data.get_bus_indices_t(),
                    buses_areas_1=self.options.area_from_bus_idx,
                    buses_areas_2=self.options.area_to_bus_idx)

                idx_w = np.argmax(np.abs(alpha_n1), axis=1)
                alpha_w = np.take_along_axis(alpha_n1, np.expand_dims(idx_w, axis=1), axis=1)

                # pack the results
                self.results = OptimalNetTransferCapacityResults(
                    bus_names=numerical_circuit.bus_data.names,
                    branch_names=numerical_circuit.branch_data.names,
                    load_names=numerical_circuit.load_data.names,
                    generator_names=numerical_circuit.generator_data.names,
                    battery_names=numerical_circuit.battery_data.names,
                    hvdc_names=numerical_circuit.hvdc_data.names,
                    trm=self.options.trm,
                    ntc_load_rule=self.options.ntc_load_rule,
                    branch_control_modes=numerical_circuit.branch_data.control_mode,
                    hvdc_control_modes=numerical_circuit.hvdc_data.control_mode,
                    Sbus=numerical_circuit.Sbus.real,
                    voltage=pf_drv.results.voltage,
                    battery_power=np.zeros((numerical_circuit.nbatt, 1)),
                    controlled_generation_power=numerical_circuit.generator_data.p,
                    Sf=pf_drv.results.Sf.real,
                    loading=pf_drv.results.loading.real,
                    solved=False,
                    bus_types=numerical_circuit.bus_types,
                    hvdc_flow=pf_drv.results.hvdc_Pt,
                    hvdc_loading=pf_drv.results.hvdc_loading,
                    phase_shift=pf_drv.results.tap_angle,
                    generation_delta=np.zeros(numerical_circuit.ngen),
                    inter_area_branches=inter_area_branches,
                    inter_area_hvdc=inter_area_hvdc,
                    alpha=alpha,
                    alpha_n1=alpha_n1,
                    alpha_w=alpha_w,
                    contingency_branch_flows_list=contingency_flows_list,
                    contingency_branch_indices_list=contingency_indices_list,
                    contingency_branch_alpha_list=contingency_branch_alpha_list,
                    contingency_generation_flows_list=contingency_gen_flows_list,
                    contingency_generation_indices_list=contingency_gen_indices_list,
                    contingency_generation_alpha_list=list(),
                    contingency_hvdc_flows_list=contingency_hvdc_flows_list,
                    contingency_hvdc_indices_list=contingency_hvdc_indices_list,
                    contingency_hvdc_alpha_list=list(),
                    rates=numerical_circuit.branch_data.rates[:, 0],
                    contingency_rates=numerical_circuit.branch_data.contingency_rates[:, 0],
                    area_from_bus_idx=self.options.area_from_bus_idx,
                    area_to_bus_idx=self.options.area_to_bus_idx,
                    loading_threshold=self.options.loading_threshold_to_report,
                    reversed_sort_loading=self.options.reversed_sort_loading,
                )
        else:
            pass

        if not base_problems:

            self.progress_text.emit('Formulating NTC OPF...')

            # Define the problem
            problem = OpfNTC(
                numerical_circuit=numerical_circuit,
                area_from_bus_idx=self.options.area_from_bus_idx,
                area_to_bus_idx=self.options.area_to_bus_idx,
                alpha=alpha,
                alpha_n1=alpha_n1,
                LODF=linear.LODF,
                LODF_NX=linear.LODF_NX,
                PTDF=linear.PTDF,
                solver_type=self.options.mip_solver,
                generation_formulation=self.options.generation_formulation,
                monitor_only_sensitive_branches=self.options.monitor_only_sensitive_branches,
                monitor_only_ntc_load_rule_branches=self.options.monitor_only_ntc_load_rule_branches,
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
                match_gen_load=self.options.match_gen_load,
                ntc_load_rule=self.options.ntc_load_rule,
                transfer_method=self.options.transfer_method,
                logger=self.logger)

            # Solve
            self.progress_text.emit('Solving NTC OPF...')
            problem.formulate()
            solved = problem.solve(
                time_limit_ms=self.options.time_limit_ms)

            err = problem.error()

            if not solved:

                if problem.status == pywraplp.Solver.FEASIBLE:
                    self.logger.add_error(
                        'Feasible solution, not optimal',
                        'NTC OPF',
                        str(err),
                        self.options.tolerance)

                if problem.status == pywraplp.Solver.INFEASIBLE:
                    self.logger.add_error(
                        'Unfeasible solution',
                        'NTC OPF',
                        str(err),
                        self.options.tolerance)

                if problem.status == pywraplp.Solver.UNBOUNDED:
                    self.logger.add_error(
                        'Proved unbounded',
                        'NTC OPF',
                        str(err),
                        self.options.tolerance)

                if problem.status == pywraplp.Solver.ABNORMAL:
                    self.logger.add_error(
                        'Abnormal solution, some error happens',
                        'NTC OPF',
                        str(err),
                        self.options.tolerance)

                if problem.status == pywraplp.Solver.NOT_SOLVED:
                    self.logger.add_error(
                        'Not solved, maybe timeout occurs',
                        'NTC OPF',
                        str(err),
                        self.options.tolerance)

            self.logger += problem.logger

            idx_w = np.argmax(np.abs(alpha_n1), axis=1)
            alpha_w = np.take_along_axis(alpha_n1, np.expand_dims(idx_w, axis=1), axis=1)

            # pack the results
            self.results = OptimalNetTransferCapacityResults(
                bus_names=numerical_circuit.bus_data.names,
                branch_names=numerical_circuit.branch_data.names,
                load_names=numerical_circuit.load_data.names,
                generator_names=numerical_circuit.generator_data.names,
                battery_names=numerical_circuit.battery_data.names,
                hvdc_names=numerical_circuit.hvdc_data.names,
                trm=self.options.trm,
                ntc_load_rule=self.options.ntc_load_rule,
                branch_control_modes=numerical_circuit.branch_data.control_mode,
                hvdc_control_modes=numerical_circuit.hvdc_data.control_mode,
                Sbus=problem.get_power_injections(),
                voltage=problem.get_voltage(),
                battery_power=np.zeros((numerical_circuit.nbatt, 1)),
                controlled_generation_power=problem.get_generator_power(),
                Sf=problem.get_branch_power_from(),
                loading=problem.get_loading(),
                solved=bool(solved),
                bus_types=numerical_circuit.bus_types,
                hvdc_flow=problem.get_hvdc_flow(),
                hvdc_loading=problem.get_hvdc_loading(),
                phase_shift=problem.get_phase_angles(),
                generation_delta=problem.get_generator_delta(),
                hvdc_angle_slack=problem.get_hvdc_angle_slacks(),
                inter_area_branches=problem.inter_area_branches,
                inter_area_hvdc=problem.inter_area_hvdc,
                alpha=alpha,
                alpha_n1=alpha_n1,
                alpha_w=alpha_w,
                monitor=problem.monitor,
                monitor_loading=problem.monitor_loading,
                monitor_by_sensitivity=problem.monitor_by_sensitivity,
                monitor_by_unrealistic_ntc=problem.monitor_by_unrealistic_ntc,
                monitor_by_zero_exchange=problem.monitor_by_zero_exchange,
                contingency_branch_flows_list=problem.get_contingency_flows_list(),
                contingency_branch_indices_list=problem.contingency_indices_list,
                contingency_branch_alpha_list=problem.contingency_branch_alpha_list,
                contingency_generation_flows_list=problem.get_contingency_gen_flows_list(),
                contingency_generation_indices_list=problem.contingency_gen_indices_list,
                contingency_generation_alpha_list=problem.contingency_generation_alpha_list,
                contingency_hvdc_flows_list=problem.get_contingency_hvdc_flows_list(),
                contingency_hvdc_indices_list=problem.contingency_hvdc_indices_list,
                contingency_hvdc_alpha_list=problem.contingency_hvdc_alpha_list,
                branch_ntc_load_rule=problem.get_branch_ntc_load_rule(),
                rates=numerical_circuit.branch_data.rates[:, 0],
                contingency_rates=numerical_circuit.branch_data.contingency_rates[:, 0],
                area_from_bus_idx=self.options.area_from_bus_idx,
                area_to_bus_idx=self.options.area_to_bus_idx,
                structural_ntc=problem.structural_ntc,
                sbase=numerical_circuit.Sbase,
                loading_threshold=self.options.loading_threshold_to_report,
                reversed_sort_loading=self.options.reversed_sort_loading,
            )

        self.progress_text.emit('Creating reports...')
        self.results.create_all_reports(
            loading_threshold=self.options.loading_threshold_to_report,
            reverse=self.options.reversed_sort_loading,
        )

        self.progress_text.emit('Done!')

        return self.results

    def run(self):
        """

        :return:
        """
        start = time.time()
        self.opf()
        end = time.time()
        self.elapsed = end - start
