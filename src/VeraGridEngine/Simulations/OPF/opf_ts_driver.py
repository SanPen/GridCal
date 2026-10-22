# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0
import datetime

import numpy as np
import pandas as pd
from typing import Union
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.enumerations import SolverType, TimeGrouping, EngineType, SimulationTypes
from VeraGridEngine.Simulations.OPF.opf_options import OptimalPowerFlowOptions
from VeraGridEngine.Simulations.OPF.Formulations.linear_opf_ts import run_linear_opf_ts, SystemVars
from VeraGridEngine.Simulations.OPF.simple_dispatch_ts import run_greedy_dispatch_ts
from VeraGridEngine.Simulations.OPF.ac_opf_worker import run_nonlinear_opf
from VeraGridEngine.Simulations.OPF.opf_ts_results import OptimalPowerFlowTimeSeriesResults
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from VeraGridEngine.Simulations.driver_template import TimeSeriesDriverTemplate
from VeraGridEngine.Simulations.Clustering.clustering_results import ClusteringResults
from VeraGridEngine.basic_structures import IntVec, Vec, get_time_groups
from VeraGridEngine.Compilers.Gslv.activation import GSLV_AVAILABLE, GSLV_UNAVAILABLE_REASON
from VeraGridEngine.Compilers.Gslv.Simulations.opf import gslv_opf


class OptimalPowerFlowTimeSeriesDriver(TimeSeriesDriverTemplate):
    __slots__ = (
        "options",
        "all_solved",
    )

    name = 'Optimal power flow time series'
    tpe = SimulationTypes.OPFTimeSeries_run

    def __init__(self,
                 grid: MultiCircuit,
                 options: Union[OptimalPowerFlowOptions, None] = None,
                 time_indices: Union[IntVec, None] = None,
                 clustering_results: Union[ClusteringResults, None] = None,
                 engine: EngineType = EngineType.VeraGrid):
        """
        Initialize the OPF time-series driver.

        :param grid: Multi-circuit model to simulate.
        :param options: OPF options.
        :param time_indices: Time indices to simulate.
        :param clustering_results: Optional clustering results.
        :param engine: Calculation engine to use.
        """
        TimeSeriesDriverTemplate.__init__(self,
                                          grid=grid,
                                          time_indices=time_indices
                                          if time_indices is not None else grid.get_all_time_indices(),
                                          clustering_results=clustering_results,
                                          engine=engine)

        # Options to use
        self.options = options if options else OptimalPowerFlowOptions()

        # find the number of time steps
        nt = len(self.time_indices) if self.time_indices is not None else 1

        # OPF results
        self.results: OptimalPowerFlowTimeSeriesResults = OptimalPowerFlowTimeSeriesResults(
            bus_names=self.grid.get_bus_names(),
            branch_names=self.grid.get_branch_names(add_hvdc=False, add_vsc=False, add_switch=True),
            load_names=self.grid.get_load_names(),
            generator_names=self.grid.get_generator_names(),
            battery_names=self.grid.get_battery_names(),
            shunt_like_names=self.grid.get_shunt_like_devices_names(),
            hvdc_names=self.grid.get_hvdc_names(),
            vsc_names=self.grid.get_vsc_names(),
            fuel_names=self.grid.get_fuel_names(),
            emission_names=self.grid.get_emission_names(),
            technology_names=self.grid.get_technology_names(),
            fluid_node_names=self.grid.get_fluid_node_names(),
            fluid_path_names=self.grid.get_fluid_path_names(),
            fluid_injection_names=self.grid.get_fluid_injection_names(),
            nt=nt,
            time_array=self.grid.time_profile[self.time_indices] if self.time_indices is not None else [
                datetime.datetime.now()],
            bus_types=np.ones(self.grid.get_bus_number(), dtype=int),
            clustering_results=clustering_results
        )

        self.all_solved = True

    @property
    def pf_options(self) -> PowerFlowOptions:
        """
        Return the embedded power-flow options.

        :return: Power flow options.
        """
        return self.options.power_flow_options

    def get_steps(self):
        """
        Return the formatted time-step labels.

        :return: List of time labels.
        """
        return [l.strftime('%d-%m-%Y %H:%M') for l in pd.to_datetime(self.grid.time_profile)]

    def run_linear_opf(self):
        """
        Run the linear OPF over the configured time range.

        :return: ``None``.
        """
        # DC optimal power flow
        opf_vars, model = run_linear_opf_ts(
            grid=self.grid,
            time_indices=self.time_indices,
            dispatch_mode=self.options.dispatch_mode,
            solver_type=self.options.mip_solver,
            zonal_grouping=self.options.zonal_grouping,
            skip_generation_limits=self.options.skip_generation_limits,
            consider_contingencies=self.options.consider_contingencies,
            contingency_groups_used=self.grid.contingency_groups,
            ramp_constraints=self.options.consider_ramps,
            consider_time_up_down=self.options.consider_time_up_down,
            area_spinning_reserve=self.options.area_spinning_reserve,
            quadratic_costs=self.options.quadratic_costs,
            lodf_threshold=self.options.lodf_tolerance,
            inter_aggregation_info=self.options.inter_aggregation_info,
            use_glsk_as_cost=self.options.use_glsk_as_cost,
            add_losses_approximation=self.options.add_losses_approximation,
            logger=self.logger,
            progress_text=self.report_text,
            progress_func=self.report_progress,
            verbose=self.options.verbose,
            robust=self.options.robust,
            mip_framework=self.options.mip_framework
        )

        self.results.voltage = opf_vars.bus_vars.Vm * np.exp(1j * opf_vars.bus_vars.Va)
        self.results.bus_shadow_prices = opf_vars.bus_vars.shadow_prices

        self.results.load_power = opf_vars.load_vars.p
        self.results.load_shedding = opf_vars.load_vars.shedding
        self.results.load_shedding_cost = opf_vars.load_vars.shedding_cost

        self.results.battery_power = opf_vars.batt_vars.p
        self.results.battery_energy = opf_vars.batt_vars.e

        self.results.generator_power = opf_vars.gen_vars.p
        self.results.generator_shedding = opf_vars.gen_vars.shedding
        self.results.generator_cost = opf_vars.gen_vars.cost
        self.results.generator_reserve = opf_vars.gen_vars.reserve
        # self.results.generator_fuel = opf_vars.gen_vars.fuel
        # self.results.generator_emissions = opf_vars.gen_vars.emissions
        self.results.generator_producing = opf_vars.gen_vars.producing
        self.results.generator_starting_up = opf_vars.gen_vars.starting_up
        self.results.generator_shutting_down = opf_vars.gen_vars.shutting_down
        self.results.generator_invested = opf_vars.gen_vars.invested

        self.results.Sf = opf_vars.branch_vars.flows
        self.results.St = -opf_vars.branch_vars.flows
        self.results.overloads = opf_vars.branch_vars.flow_slacks_pos - opf_vars.branch_vars.flow_slacks_neg
        self.results.overloads_cost = opf_vars.branch_vars.overload_cost
        self.results.losses = opf_vars.branch_vars.losses

        self.results.loading = opf_vars.branch_vars.loading
        self.results.tap_angle = opf_vars.branch_vars.tap_angles

        self.results.hvdc_Pf = opf_vars.hvdc_vars.flows
        self.results.hvdc_loading = opf_vars.hvdc_vars.loading

        self.results.vsc_Pf = opf_vars.vsc_vars.flows
        self.results.vsc_loading = opf_vars.vsc_vars.loading

        self.results.fluid_node_current_level = opf_vars.fluid_node_vars.current_level
        self.results.fluid_node_fluid_value = opf_vars.fluid_node_vars.fluid_value
        self.results.fluid_node_flow_in = opf_vars.fluid_node_vars.flow_in
        self.results.fluid_node_flow_out = opf_vars.fluid_node_vars.flow_out
        self.results.fluid_node_p2x_flow = opf_vars.fluid_node_vars.p2x_flow
        self.results.fluid_node_spillage = opf_vars.fluid_node_vars.spillage
        self.results.fluid_path_flow = opf_vars.fluid_path_vars.flow
        self.results.fluid_injection_flow = opf_vars.fluid_inject_vars.flow

        self.results.system_fuel = opf_vars.sys_vars.system_fuel
        self.results.system_emissions = opf_vars.sys_vars.system_emissions
        self.results.system_energy_cost = opf_vars.sys_vars.system_unit_energy_cost
        self.results.system_total_energy_cost = opf_vars.sys_vars.system_total_energy_cost
        self.results.power_by_technology = opf_vars.sys_vars.power_by_technology

        # set converged for all t to the value of acceptable solution
        self.results.converged = np.array([opf_vars.acceptable_solution] * opf_vars.nt)

        if self.options.report_formulation:
            self.results.report_text = model.model_as_string()

    def run_linear_opf_indices(self,
                               time_indices: IntVec,
                               result_indices: IntVec,
                               energy_0: Vec,
                               fluid_level_0: Vec):
        """
        Run the linear OPF for one time chunk.

        :param time_indices: Time indices to solve.
        :param result_indices: Result rows where each solved time index must be stored.
        :param energy_0: Initial battery energies for the chunk.
        :param fluid_level_0: Initial fluid levels for the chunk.
        :return: Linear model instance.
        """
        # DC optimal power flow
        opf_vars, model = run_linear_opf_ts(
            grid=self.grid,
            time_indices=time_indices,
            dispatch_mode=self.options.dispatch_mode,
            solver_type=self.options.mip_solver,
            zonal_grouping=self.options.zonal_grouping,
            skip_generation_limits=self.options.skip_generation_limits,
            consider_contingencies=self.options.consider_contingencies,
            contingency_groups_used=self.options.contingency_groups_used,
            ramp_constraints=self.options.consider_ramps,
            consider_time_up_down=self.options.consider_time_up_down,
            area_spinning_reserve=self.options.area_spinning_reserve,
            quadratic_costs=self.options.quadratic_costs,
            lodf_threshold=self.options.lodf_tolerance,
            inter_aggregation_info=self.options.inter_aggregation_info,
            energy_0=energy_0,
            fluid_level_0=fluid_level_0,
            use_glsk_as_cost=self.options.use_glsk_as_cost,
            add_losses_approximation=self.options.add_losses_approximation,
            logger=self.logger,
            verbose=self.options.verbose,
            robust=self.options.robust,
            mip_framework=self.options.mip_framework
        )

        self.results.voltage[result_indices, :] = opf_vars.bus_vars.Vm * np.exp(1j * opf_vars.bus_vars.Va)
        self.results.bus_shadow_prices[result_indices, :] = opf_vars.bus_vars.shadow_prices

        self.results.load_power[result_indices, :] = opf_vars.load_vars.p
        self.results.load_shedding[result_indices, :] = opf_vars.load_vars.shedding
        self.results.load_shedding_cost[result_indices, :] = opf_vars.load_vars.shedding_cost

        self.results.battery_power[result_indices, :] = opf_vars.batt_vars.p
        self.results.battery_energy[result_indices, :] = opf_vars.batt_vars.e

        self.results.generator_power[result_indices, :] = opf_vars.gen_vars.p
        self.results.generator_shedding[result_indices, :] = opf_vars.gen_vars.shedding
        self.results.generator_cost[result_indices, :] = opf_vars.gen_vars.cost
        self.results.generator_reserve[result_indices, :] = opf_vars.gen_vars.reserve
        self.results.generator_producing[result_indices, :] = opf_vars.gen_vars.producing
        self.results.generator_starting_up[result_indices, :] = opf_vars.gen_vars.starting_up
        self.results.generator_shutting_down[result_indices, :] = opf_vars.gen_vars.shutting_down
        self.results.generator_invested[result_indices, :] = opf_vars.gen_vars.invested

        self.results.Sf[result_indices, :] = opf_vars.branch_vars.flows
        self.results.St[result_indices, :] = -opf_vars.branch_vars.flows
        self.results.overloads[result_indices, :] = (opf_vars.branch_vars.flow_slacks_pos
                                                     - opf_vars.branch_vars.flow_slacks_neg)
        self.results.overloads_cost[result_indices, :] = opf_vars.branch_vars.overload_cost
        self.results.losses[result_indices, :] = opf_vars.branch_vars.losses

        self.results.loading[result_indices, :] = opf_vars.branch_vars.loading
        self.results.tap_angle[result_indices, :] = opf_vars.branch_vars.tap_angles

        self.results.hvdc_Pf[result_indices, :] = opf_vars.hvdc_vars.flows
        self.results.hvdc_loading[result_indices, :] = opf_vars.hvdc_vars.loading

        self.results.vsc_Pf[result_indices, :] = opf_vars.vsc_vars.flows
        self.results.vsc_loading[result_indices, :] = opf_vars.vsc_vars.loading

        self.results.fluid_node_current_level[result_indices, :] = opf_vars.fluid_node_vars.current_level
        self.results.fluid_node_fluid_value[result_indices, :] = opf_vars.fluid_node_vars.fluid_value
        self.results.fluid_node_flow_in[result_indices, :] = opf_vars.fluid_node_vars.flow_in
        self.results.fluid_node_flow_out[result_indices, :] = opf_vars.fluid_node_vars.flow_out
        self.results.fluid_node_p2x_flow[result_indices, :] = opf_vars.fluid_node_vars.p2x_flow
        self.results.fluid_node_spillage[result_indices, :] = opf_vars.fluid_node_vars.spillage
        self.results.fluid_path_flow[result_indices, :] = opf_vars.fluid_path_vars.flow
        self.results.fluid_injection_flow[result_indices, :] = opf_vars.fluid_inject_vars.flow

        self.results.system_fuel[result_indices, :] = opf_vars.sys_vars.system_fuel
        self.results.system_emissions[result_indices, :] = opf_vars.sys_vars.system_emissions
        self.results.system_energy_cost[result_indices] = opf_vars.sys_vars.system_unit_energy_cost
        self.results.system_total_energy_cost[result_indices] = opf_vars.sys_vars.system_total_energy_cost
        self.results.power_by_technology[result_indices] = opf_vars.sys_vars.power_by_technology

        # set converged for all t to the value of acceptable solution
        self.results.converged[result_indices] = np.array([opf_vars.acceptable_solution] * opf_vars.nt)

        return model

    def run_greedy_dispatch(self):
        """
        Run greedy dispatch over the configured time range.

        :return: ``None``.
        """
        # AC optimal power flow
        (load_profile, gen_dispatch,
         batt_dispatch, battery_energy,
         load_shedding, gen_curtailment, greedy_inpts) = run_greedy_dispatch_ts(
            grid=self.grid,
            time_indices=self.time_indices,
            text_prog=self.report_text,
            prog_func=self.report_progress,
            logger=self.logger
        )

        self.results.generator_power[self.time_indices, :] = gen_dispatch  # already in MW
        self.results.generator_shedding[self.time_indices, :] = gen_curtailment
        self.results.battery_power[self.time_indices, :] = batt_dispatch
        self.results.battery_energy[self.time_indices, :] = battery_energy

        self.results.load_shedding[self.time_indices, :] = load_shedding
        self.results.load_power[self.time_indices, :] = load_profile

        self.results.converged[self.time_indices] = True

        gen_emissions_rates_matrix = self.grid.get_gen_emission_rates_sparse_matrix()
        gen_fuel_rates_matrix = self.grid.get_gen_fuel_rates_sparse_matrix()
        gen_tech_shares_matrix = self.grid.get_gen_technology_connectivity_matrix()
        batt_tech_shares_matrix = self.grid.get_batt_technology_connectivity_matrix()

        gen_cost = gen_dispatch * greedy_inpts.gen_cost
        shedding_cost = load_shedding * greedy_inpts.load_shedding_cost

        sys_calc = SystemVars(nt=len(self.time_indices))
        sys_calc.compute(gen_emissions_rates_matrix=gen_emissions_rates_matrix,
                    gen_fuel_rates_matrix=gen_fuel_rates_matrix,
                    gen_tech_shares_matrix=gen_tech_shares_matrix,
                    batt_tech_shares_matrix=batt_tech_shares_matrix,
                    gen_p=gen_dispatch,
                    batt_p=batt_dispatch,
                    gen_cost=gen_cost,
                    shedding_cost=shedding_cost)

        self.results.system_fuel[self.time_indices, :] = sys_calc.system_fuel
        self.results.system_emissions[self.time_indices, :] = sys_calc.system_emissions
        self.results.system_energy_cost[self.time_indices] = sys_calc.system_unit_energy_cost
        self.results.system_total_energy_cost[self.time_indices] = sys_calc.system_total_energy_cost
        self.results.power_by_technology[self.time_indices, :] = sys_calc.power_by_technology


    def run_greedy_dispatch_indices(self, time_indices: IntVec, result_indices: IntVec):
        """
        Run greedy dispatch for one time chunk.

        :param time_indices: Time indices to solve.
        :param result_indices: Result rows where each solved time index must be stored.
        :return: ``None``.
        """
        # Greedy dispatch
        (load_profile, gen_dispatch,
         batt_dispatch, battery_energy,
         load_shedding, gen_curtailment, greedy_inpts) = run_greedy_dispatch_ts(
            grid=self.grid,
            time_indices=time_indices,
            text_prog=self.report_text,
            prog_func=self.report_progress,
            logger=self.logger
        )

        self.results.generator_power[result_indices, :] = gen_dispatch  # already in MW
        self.results.generator_shedding[result_indices, :] = gen_curtailment
        self.results.battery_power[result_indices, :] = batt_dispatch
        self.results.battery_energy[result_indices, :] = battery_energy

        self.results.load_shedding[result_indices, :] = load_shedding
        self.results.load_power[result_indices, :] = load_profile

        self.results.converged[result_indices] = True

        gen_emissions_rates_matrix = self.grid.get_gen_emission_rates_sparse_matrix()
        gen_fuel_rates_matrix = self.grid.get_gen_fuel_rates_sparse_matrix()
        gen_tech_shares_matrix = self.grid.get_gen_technology_connectivity_matrix()
        batt_tech_shares_matrix = self.grid.get_batt_technology_connectivity_matrix()

        gen_cost = gen_dispatch * greedy_inpts.gen_cost
        shedding_cost = load_shedding * greedy_inpts.load_shedding_cost

        sys_calc = SystemVars(nt=len(time_indices))
        sys_calc.compute(gen_emissions_rates_matrix=gen_emissions_rates_matrix,
                         gen_fuel_rates_matrix=gen_fuel_rates_matrix,
                         gen_tech_shares_matrix=gen_tech_shares_matrix,
                         batt_tech_shares_matrix=batt_tech_shares_matrix,
                         gen_p=gen_dispatch,
                         batt_p=batt_dispatch,
                         gen_cost=gen_cost,
                         shedding_cost=shedding_cost)

        self.results.system_fuel[result_indices, :] = sys_calc.system_fuel
        self.results.system_emissions[result_indices, :] = sys_calc.system_emissions
        self.results.system_energy_cost[result_indices] = sys_calc.system_unit_energy_cost
        self.results.system_total_energy_cost[result_indices] = sys_calc.system_total_energy_cost
        self.results.power_by_technology[result_indices, :] = sys_calc.power_by_technology

    def run_non_linear_opf(self):
        """
        Run the nonlinear OPF over the configured time range.

        :return: ``None``.
        """
        self.report_progress(0.0)
        for it, t in enumerate(self.time_indices):

            # report progress
            self.report_text('Nonlinear OPF at ' + str(self.grid.time_profile[t]) + '...')
            self.report_progress2(it, len(self.time_indices))

            # run opf
            res = run_nonlinear_opf(
                grid=self.grid,
                opf_options=self.options,
                t_idx=t,
                # for the first power flow, use the given strategy
                # for the successive ones, use the previous solution
                # Sbus_pf0=self.results.Sbus[it - 1, :] if it > 0 else None,
                # voltage_pf0=self.results.voltage[it - 1, :] if it > 0 else None,
                logger=self.logger
            )
            Sbase = self.grid.Sbase
            self.results.voltage[it, :] = res.V
            self.results.Sbus[it, :] = res.S * Sbase
            self.results.bus_shadow_prices[it, :] = res.lam_p
            # self.results.load_shedding = npa_res.load_shedding[0, :]
            # self.results.battery_power = npa_res.battery_p[0, :]
            # self.results.battery_energy = npa_res.battery_energy[0, :]
            self.results.generator_power[it, :] = res.Pg * Sbase
            self.results.generator_reactive_power[it, :] = res.Qg * Sbase
            self.results.generator_cost[it, :] = res.Pcost

            self.results.shunt_like_reactive_power[it, :] = res.Qsh * Sbase

            self.results.Sf[it, :] = res.Sf * Sbase
            self.results.St[it, :] = res.St * Sbase
            self.results.overloads[it, :] = (res.sl_sf - res.sl_st) * Sbase
            self.results.loading[it, :] = res.loading
            self.results.tap_angle[it, :] = res.tap_phase
            self.results.tap_module[it, :] = res.tap_module

            self.results.hvdc_Pf[it, :] = res.hvdc_Pf
            self.results.hvdc_loading[it, :] = res.hvdc_loading
            self.results.converged[it] = res.converged

            if self.is_cancel():
                return None

        # Compute the emissions, fuel costs and energy used
        (self.results.system_fuel,
         self.results.system_emissions,
         self.results.system_energy_cost) = self.get_fuel_emissions_energy_calculations(
            gen_p=self.results.generator_power,
            gen_cost=self.results.generator_cost
        )

        return None

    def run_nonlinear_opf_indices(self, time_indices: IntVec, result_indices: IntVec):
        """
        Run the nonlinear OPF for one time chunk.

        :param time_indices: Time indices to solve.
        :param result_indices: Result rows where each solved time index must be stored.
        :return: ``None``.
        """
        for it, t in enumerate(time_indices):
            result_idx: int = int(result_indices[it])

            # report progress
            self.report_text('Nonlinear OPF at ' + str(self.grid.time_profile[t]) + '...')

            # run opf
            res = run_nonlinear_opf(
                grid=self.grid,
                opf_options=self.options,
                t_idx=t,
                # for the first power flow, use the given strategy
                # for the successive ones, use the previous solution
                # Sbus_pf0=self.results.Sbus[it - 1, :] if it > 0 else None,
                # voltage_pf0=self.results.voltage[it - 1, :] if it > 0 else None,
                logger=self.logger
            )
            Sbase = self.grid.Sbase
            self.results.voltage[result_idx, :] = res.V
            self.results.Sbus[result_idx, :] = res.S * Sbase
            self.results.bus_shadow_prices[result_idx, :] = res.lam_p
            # self.results.load_shedding = npa_res.load_shedding[0, :]
            # self.results.battery_power = npa_res.battery_p[0, :]
            # self.results.battery_energy = npa_res.battery_energy[0, :]
            self.results.generator_power[result_idx, :] = res.Pg * Sbase
            self.results.generator_reactive_power[result_idx, :] = res.Qg * Sbase
            self.results.generator_cost[result_idx, :] = res.Pcost

            self.results.shunt_like_reactive_power[result_idx, :] = res.Qsh * Sbase

            self.results.Sf[result_idx, :] = res.Sf * Sbase
            self.results.St[result_idx, :] = res.St * Sbase
            self.results.overloads[result_idx, :] = (res.sl_sf - res.sl_st) * Sbase
            self.results.loading[result_idx, :] = res.loading
            self.results.tap_angle[result_idx, :] = res.tap_phase
            self.results.tap_module[result_idx, :] = res.tap_module

            self.results.hvdc_Pf[result_idx, :] = res.hvdc_Pf
            self.results.hvdc_loading[result_idx, :] = res.hvdc_loading
            self.results.converged[result_idx] = res.converged

            if self.is_cancel():
                return None

        return None

    def opf(self, remote=False, batteries_energy_0=None):
        """
        Run the configured OPF solver across the selected time range.

        :param remote: Whether the call comes from another driver.
        :param batteries_energy_0: Optional initial battery energies.
        :return: OPF time-series results.
        """

        if not remote:
            self.report_progress(0.0)
            self.report_text('Formulating problem...')

        if self.options.solver == SolverType.LINEAR_OPF:

            self.run_linear_opf()

        elif self.options.solver == SolverType.NONLINEAR_OPF:

            self.run_non_linear_opf()

        elif self.options.solver == SolverType.GREEDY_DISPATCH_OPF:

            self.run_greedy_dispatch()

        else:
            self.logger.add_error('Solver not supported in this mode', str(self.options.solver))
            return self.results

        if not remote:
            self.report_progress(0.0)
            self.report_text('Running all in an external solver, this may take a while...')

        return self.results

    def opf_by_groups(self) -> None:
        """
        Run the OPF by grouped chunks.

        :return: ``None``.
        """

        self.report_progress(0.0)
        self.report_text('Making groups...')

        # get the partition points of the time series
        groups = get_time_groups(t_array=self.grid.time_profile[self.time_indices], grouping=self.options.time_grouping)

        n = len(groups)
        i = 1
        n_groups: int = max(n - 1, 1)
        energy_0: Union[Vec, None] = None  # at the beginning
        fluid_level_0: Union[Vec, None] = None

        while i < n and not self.is_cancel():
            start_ = groups[i - 1]
            end_ = groups[i]

            # Grab the last time index in the last group
            if i == n - 1:
                result_indices = np.arange(start_, end_ + 1)
            else:
                result_indices = np.arange(start_, end_)

            time_indices = self.time_indices[result_indices]

            # show progress message
            msg = f"Group {i} -> {start_} : {end_} [{end_ - start_}]"
            if self.options.verbose > 0:
                print(msg)

            self.report_text('Running OPF for the time group {0} '
                             'start {1} - end {2} in external solver...'.format(i, start_, end_))

            if self.options.solver == SolverType.LINEAR_OPF:

                model = self.run_linear_opf_indices(time_indices=time_indices,
                                                    result_indices=result_indices,
                                                    energy_0=energy_0,
                                                    fluid_level_0=fluid_level_0)

                final_result_idx: int = int(result_indices[-1])
                energy_0 = self.results.battery_energy[final_result_idx, :]
                fluid_level_0 = self.results.fluid_node_current_level[final_result_idx, :]

                if self.options.report_formulation:
                    self.results.report_text = f"## {msg}\n\n" + model.model_as_string()

            elif self.options.solver == SolverType.NONLINEAR_OPF:

                self.run_nonlinear_opf_indices(time_indices=time_indices,
                                               result_indices=result_indices)


            elif self.options.solver == SolverType.GREEDY_DISPATCH_OPF:

                self.run_greedy_dispatch_indices(time_indices=time_indices,
                                                 result_indices=result_indices)

            else:
                self.logger.add_error('Solver not supported in this mode', str(self.options.solver))
                return None

            # update progress bar
            self.report_progress2(i - 1, n_groups)

            if self.is_cancel():
                return None

            i += 1

        return None

    def add_report(self, eps: float = 1e-6) -> None:
        """
        Append warnings to the logger from the computed results.

        :param eps: Numerical tolerance for reporting.
        :return: ``None``.
        """
        if self.progress_text:
            self.report_text("Creating report")

        nt = len(self.time_indices)
        for t, t_idx in enumerate(self.time_indices):

            self.report_progress2(t, nt)

            t_name = str(self.results.time_array[t])

            for gen_name, gen_shedding in zip(self.results.generator_names, self.results.generator_shedding[t, :]):
                if gen_shedding > eps:
                    self.logger.add_warning("Generation shedding {}".format(t_name),
                                            device=gen_name,
                                            value=gen_shedding,
                                            expected_value=0.0)

            for load_name, load_shedding in zip(self.results.load_names, self.results.load_shedding[t, :]):
                if load_shedding > eps:
                    self.logger.add_warning("Load shedding {}".format(t_name),
                                            device=load_name,
                                            value=load_shedding,
                                            expected_value=0.0)

            for fluid_node_name, fluid_node_spillage in zip(self.results.fluid_node_names,
                                                            self.results.fluid_node_spillage[t, :]):
                if fluid_node_spillage > eps:
                    self.logger.add_warning("Fluid node spillage {}".format(t_name),
                                            device=fluid_node_name,
                                            value=fluid_node_spillage,
                                            expected_value=0.0)

            for name, val in zip(self.results.branch_names, self.results.loading[t, :]):
                if val > (1.0 + eps):
                    self.logger.add_warning("Overload {}".format(t_name),
                                            device=name,
                                            value=val * 100,
                                            expected_value=100.0)

            va = np.angle(self.results.voltage[t, :])
            for i, bus in enumerate(self.grid.buses):
                if va[i] > bus.angle_max:
                    self.logger.add_warning("Overvoltage {}".format(t_name),
                                            device=bus.name,
                                            value=va[i],
                                            expected_value=bus.angle_max)
                elif va[i] < bus.angle_min:
                    self.logger.add_warning("Undervoltage {}".format(t_name),
                                            device=bus.name,
                                            value=va[i],
                                            expected_value=bus.angle_min)

    def run(self):
        """
        Execute the configured OPF time-series study.

        :return: ``None``.
        """

        self.tic()
        self.report_text("Compiling and configuring...")

        if self.engine == EngineType.GSLV:
            if not GSLV_AVAILABLE:
                self.engine = EngineType.VeraGrid
                self.logger.add_warning(f'GSLV unavailable: {GSLV_UNAVAILABLE_REASON}; falling back to VeraGrid')
            else:
                if self.options.solver != SolverType.LINEAR_OPF:
                    self.engine = EngineType.VeraGrid
                    self.logger.add_warning('GSLV OPF time series only supports LINEAR_OPF, falling back to VeraGrid')
                else:
                    pass
        else:
            pass

        if self.engine == EngineType.VeraGrid:

            if self.options.time_grouping == TimeGrouping.NoGrouping:
                self.opf()
            else:
                if self.time_indices is None:
                    self.opf()
                else:
                    if len(self.time_indices) == 0:
                        self.opf()
                    else:
                        self.opf_by_groups()

        elif self.engine == EngineType.GSLV:

            if self.time_indices is None:
                use_time_series = False
                source_time_indices: IntVec = np.array([0], dtype=int)
                result_time_indices: IntVec = np.array([0], dtype=int)
            else:
                use_time_series = True
                result_time_indices = np.arange(0, len(self.time_indices), dtype=int)
                # GSLV returns compact result matrices for the requested time window.
                source_time_indices = result_time_indices

            if self.options.solver == SolverType.LINEAR_OPF:
                self.report_text('Running Linear OPF with GSLV...')

                gslv_res = gslv_opf(circuit=self.grid,
                                    opf_options=self.options,
                                    time_series=use_time_series,
                                    time_indices=self.time_indices,
                                    logger=self.logger)

                self.results.voltage[result_time_indices, :] = gslv_res.voltage[source_time_indices, :]
                self.results.Sbus[result_time_indices, :] = gslv_res.Sbus[source_time_indices, :].real
                self.results.bus_shadow_prices[result_time_indices, :] = gslv_res.bus_shadow_prices[
                    source_time_indices, :
                ]

                self.results.load_power[result_time_indices, :] = gslv_res.load_power[source_time_indices, :]
                self.results.load_shedding[result_time_indices, :] = gslv_res.load_shedding[source_time_indices, :]
                self.results.load_shedding_cost[result_time_indices, :] = gslv_res.load_shedding_cost[
                    source_time_indices, :
                ]

                self.results.battery_power[result_time_indices, :] = gslv_res.battery_power[source_time_indices, :]
                self.results.battery_energy[result_time_indices, :] = gslv_res.battery_energy[source_time_indices, :]
                self.results.battery_invested[result_time_indices, :] = gslv_res.battery_invested[
                    source_time_indices, :
                ]

                self.results.generator_power[result_time_indices, :] = gslv_res.generator_power[
                    source_time_indices, :
                ]
                self.results.generator_reactive_power[result_time_indices, :] = gslv_res.generator_reactive_power[
                    source_time_indices, :
                ]
                self.results.generator_shedding[result_time_indices, :] = gslv_res.generator_shedding[
                    source_time_indices, :
                ]
                self.results.generator_cost[result_time_indices, :] = gslv_res.generator_cost[
                    source_time_indices, :
                ]
                self.results.generator_producing[result_time_indices, :] = gslv_res.generator_producing[
                    source_time_indices, :
                ]
                self.results.generator_starting_up[result_time_indices, :] = gslv_res.generator_starting_up[
                    source_time_indices, :
                ]
                self.results.generator_shutting_down[result_time_indices, :] = gslv_res.generator_shutting_down[
                    source_time_indices, :
                ]
                self.results.generator_invested[result_time_indices, :] = gslv_res.generator_invested[
                    source_time_indices, :
                ]

                self.results.shunt_like_reactive_power[result_time_indices, :] = gslv_res.shunt_like_reactive_power[
                    source_time_indices, :
                ]

                self.results.Sf[result_time_indices, :] = gslv_res.Sf[source_time_indices, :].real
                self.results.St[result_time_indices, :] = gslv_res.St[source_time_indices, :].real
                self.results.loading[result_time_indices, :] = gslv_res.loading[source_time_indices, :].real
                self.results.losses[result_time_indices, :] = gslv_res.losses[source_time_indices, :]
                self.results.tap_angle[result_time_indices, :] = gslv_res.tap_angle[source_time_indices, :]
                self.results.tap_module[result_time_indices, :] = gslv_res.tap_module[source_time_indices, :]
                self.results.overloads[result_time_indices, :] = gslv_res.overloads[source_time_indices, :].real
                self.results.overloads_cost[result_time_indices, :] = gslv_res.overloads_cost[
                    source_time_indices, :
                ]

                self.results.hvdc_Pf[result_time_indices, :] = gslv_res.hvdc_Pf[source_time_indices, :]
                self.results.hvdc_loading[result_time_indices, :] = gslv_res.hvdc_loading[
                    source_time_indices, :
                ]

                self.results.vsc_Pf[result_time_indices, :] = gslv_res.vsc_Pf[source_time_indices, :]
                self.results.vsc_loading[result_time_indices, :] = gslv_res.vsc_loading[
                    source_time_indices, :
                ]

                self.results.fluid_node_current_level[result_time_indices, :] = gslv_res.fluid_node_current_level[
                    source_time_indices, :
                ]
                self.results.fluid_node_flow_in[result_time_indices, :] = gslv_res.fluid_node_flow_in[
                    source_time_indices, :
                ]
                self.results.fluid_node_flow_out[result_time_indices, :] = gslv_res.fluid_node_flow_out[
                    source_time_indices, :
                ]
                self.results.fluid_node_p2x_flow[result_time_indices, :] = gslv_res.fluid_node_p2x_flow[
                    source_time_indices, :
                ]
                self.results.fluid_node_spillage[result_time_indices, :] = gslv_res.fluid_node_spillage[
                    source_time_indices, :
                ]
                self.results.fluid_path_flow[result_time_indices, :] = gslv_res.fluid_path_flow[
                    source_time_indices, :
                ]
                self.results.fluid_injection_flow[result_time_indices, :] = gslv_res.fluid_injection_flow[
                    source_time_indices, :
                ]

                self.results.system_fuel[result_time_indices, :] = gslv_res.system_fuel[source_time_indices, :]
                self.results.system_emissions[result_time_indices, :] = gslv_res.system_emissions[
                    source_time_indices, :
                ]
                self.results.system_energy_cost[result_time_indices] = gslv_res.system_energy_cost[
                    source_time_indices
                ]
                self.results.system_total_energy_cost[result_time_indices] = gslv_res.system_total_energy_cost[
                    source_time_indices
                ]
                if self.results.power_by_technology.shape[1] == gslv_res.power_by_technology.shape[1]:
                    self.results.power_by_technology[result_time_indices, :] = gslv_res.power_by_technology[
                        source_time_indices, :
                    ]
                else:
                    self.results.power_by_technology[result_time_indices, :] = 0.0

                self.results.converged[result_time_indices] = gslv_res.converged[source_time_indices]

        else:
            if self.options.time_grouping == TimeGrouping.NoGrouping:
                self.opf()
            else:
                if self.time_indices is None:
                    self.opf()
                else:
                    if len(self.time_indices) == 0:
                        self.opf()
                    else:
                        self.opf_by_groups()

        if self.options.generate_report:
            self.add_report()

        self.toc()
