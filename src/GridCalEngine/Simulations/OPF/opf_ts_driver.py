# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0
import datetime

import numpy as np
import pandas as pd
from typing import Union
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.enumerations import SolverType, TimeGrouping, EngineType, SimulationTypes
from GridCalEngine.Simulations.OPF.opf_options import OptimalPowerFlowOptions
from GridCalEngine.Simulations.OPF.linear_opf_ts import run_linear_opf_ts
from GridCalEngine.Simulations.OPF.simple_dispatch_ts import run_greedy_dispatch_ts
from GridCalEngine.Simulations.OPF.NumericalMethods.ac_opf import run_nonlinear_opf
from GridCalEngine.Simulations.OPF.opf_ts_results import OptimalPowerFlowTimeSeriesResults
from GridCalEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCalEngine.Simulations.driver_template import TimeSeriesDriverTemplate
from GridCalEngine.Compilers.circuit_to_newton_pa import newton_pa_linear_opf, newton_pa_nonlinear_opf
from GridCalEngine.Simulations.Clustering.clustering_results import ClusteringResults
from GridCalEngine.basic_structures import IntVec, Vec, get_time_groups


class OptimalPowerFlowTimeSeriesDriver(TimeSeriesDriverTemplate):
    name = 'Optimal power flow time series'
    tpe = SimulationTypes.OPFTimeSeries_run

    def __init__(self,
                 grid: MultiCircuit,
                 options: Union[OptimalPowerFlowOptions, None] = None,
                 time_indices: Union[IntVec, None] = None,
                 clustering_results: Union[ClusteringResults, None] = None,
                 engine: EngineType = EngineType.GridCal):
        """
        OptimalPowerFlowTimeSeriesDriver class constructor
        :param grid: MultiCircuit Object
        :param options: OPF options (optional)
        :param time_indices: array of time indices to simulate (optional)
        :param engine: Calculation engine to use (if available) (optional)
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
        Get the PowerFlow options provides with the OpfOptions
        :return: PowerFlowOptions
        """
        return self.options.power_flow_options

    def get_steps(self):
        """
        Get time steps list of strings
        """
        return [l.strftime('%d-%m-%Y %H:%M') for l in pd.to_datetime(self.grid.time_profile)]

    def opf(self, remote=False, batteries_energy_0=None):
        """
        Run a power flow for every circuit
        :param remote: is this function being called from the time series?
        :param batteries_energy_0: initial state of the batteries, if None the default values are taken
        :return: OptimalPowerFlowResults object
        """

        if not remote:
            self.report_progress(0.0)
            self.report_text('Formulating problem...')

        if self.options.solver == SolverType.LINEAR_OPF:

            # DC optimal power flow
            opf_vars = run_linear_opf_ts(grid=self.grid,
                                         time_indices=self.time_indices,
                                         solver_type=self.options.mip_solver,
                                         zonal_grouping=self.options.zonal_grouping,
                                         skip_generation_limits=self.options.skip_generation_limits,
                                         consider_contingencies=self.options.consider_contingencies,
                                         contingency_groups_used=self.grid.contingency_groups,
                                         unit_commitment=self.options.unit_commitment,
                                         ramp_constraints=self.options.unit_commitment,
                                         generation_expansion_planning=self.options.generation_expansion_planning,
                                         all_generators_fixed=False,
                                         lodf_threshold=self.options.lodf_tolerance,
                                         maximize_inter_area_flow=self.options.maximize_flows,
                                         inter_aggregation_info=self.options.inter_aggregation_info,
                                         logger=self.logger,
                                         progress_text=self.report_text,
                                         progress_func=self.report_progress,
                                         export_model_fname=self.options.export_model_fname,
                                         verbose=self.options.verbose,
                                         robust=self.options.robust)

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
            # self.results.generator_fuel = opf_vars.gen_vars.fuel
            # self.results.generator_emissions = opf_vars.gen_vars.emissions
            self.results.generator_producing = opf_vars.gen_vars.producing
            self.results.generator_starting_up = opf_vars.gen_vars.starting_up
            self.results.generator_shutting_down = opf_vars.gen_vars.shedding
            self.results.generator_invested = opf_vars.gen_vars.invested

            self.results.Sf = opf_vars.branch_vars.flows
            self.results.St = -opf_vars.branch_vars.flows
            self.results.overloads = opf_vars.branch_vars.flow_slacks_pos - opf_vars.branch_vars.flow_slacks_neg
            self.results.overloads_cost = opf_vars.branch_vars.overload_cost

            self.results.loading = opf_vars.branch_vars.loading
            self.results.phase_shift = opf_vars.branch_vars.tap_angles

            self.results.hvdc_Pf = opf_vars.hvdc_vars.flows
            self.results.hvdc_loading = opf_vars.hvdc_vars.loading

            self.results.vsc_Pf = opf_vars.vsc_vars.flows
            self.results.vsc_loading = opf_vars.vsc_vars.loading

            self.results.fluid_node_current_level = opf_vars.fluid_node_vars.current_level
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

        elif self.options.solver == SolverType.NONLINEAR_OPF:

            self.report_progress(0.0)
            for it, t in enumerate(self.time_indices):

                # report progress
                self.report_text('Nonlinear OPF at ' + str(self.grid.time_profile[t]) + '...')
                self.report_progress2(it, len(self.time_indices))

                # run opf
                res = run_nonlinear_opf(
                    grid=self.grid,
                    opf_options=self.options,
                    pf_options=self.pf_options,
                    t_idx=t,
                    # for the first power flow, use the given strategy
                    # for the successive ones, use the previous solution
                    pf_init=self.options.ips_init_with_pf if it == 0 else True,
                    Sbus_pf0=self.results.Sbus[it - 1, :] if it > 0 else None,
                    voltage_pf0=self.results.voltage[it - 1, :] if it > 0 else None,
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
                self.results.phase_shift[it, :] = res.tap_phase

                self.results.hvdc_Pf[it, :] = res.hvdc_Pf
                self.results.hvdc_loading[it, :] = res.hvdc_loading
                self.results.converged[it] = res.converged

                if self.__cancel__:
                    return self.results

            # Compute the emissions, fuel costs and energy used
            (self.results.system_fuel,
             self.results.system_emissions,
             self.results.system_energy_cost) = self.get_fuel_emissions_energy_calculations(
                gen_p=self.results.generator_power,
                gen_cost=self.results.generator_cost
            )

        elif self.options.solver == SolverType.SIMPLE_OPF:

            # AC optimal power flow
            load_profile, gen_dispatch, batt_dispatch, battery_energy, load_shedding = run_greedy_dispatch_ts(
                grid=self.grid,
                time_indices=self.time_indices,
                text_prog=self.report_text,
                prog_func=self.report_progress,
                logger=self.logger
            )

            self.results.generator_power[self.time_indices, :] = gen_dispatch  # already in MW
            self.results.battery_power[self.time_indices, :] = batt_dispatch
            self.results.battery_energy[self.time_indices, :] = battery_energy

            self.results.load_shedding[self.time_indices, :] = load_shedding
            self.results.load_power[self.time_indices, :] = load_profile

        else:
            self.logger.add_error('Solver not supported in this mode', str(self.options.solver))
            return

        if not remote:
            self.report_progress(0.0)
            self.report_text('Running all in an external solver, this may take a while...')

        return self.results

    def opf_by_groups(self) -> None:
        """
        Run the OPF by groups
        """

        self.report_progress(0.0)
        self.report_text('Making groups...')

        # get the partition points of the time series
        groups = get_time_groups(t_array=self.grid.time_profile[self.time_indices], grouping=self.options.time_grouping)

        n = len(groups)
        i = 1
        energy_0: Union[Vec, None] = None  # at the beginning
        fluid_level_0: Union[Vec, None] = None

        while i < n and not self.__cancel__:
            start_ = groups[i - 1]
            end_ = groups[i]

            # Grab the last time index in the last group
            if i == n - 1:
                time_indices = np.arange(start_, end_ + 1)
            else:
                time_indices = np.arange(start_, end_)

            # show progress message
            print(start_, ':', end_, ' [', end_ - start_, ']')
            self.report_text('Running OPF for the time group {0} '
                             'start {1} - end {2} in external solver...'.format(i, start_, end_))

            # run an opf for the group interval only if the group is within the start:end boundaries
            # DC optimal power flow
            opf_vars = run_linear_opf_ts(grid=self.grid,
                                         time_indices=time_indices,
                                         solver_type=self.options.mip_solver,
                                         zonal_grouping=self.options.zonal_grouping,
                                         skip_generation_limits=self.options.skip_generation_limits,
                                         consider_contingencies=self.options.consider_contingencies,
                                         contingency_groups_used=self.options.contingency_groups_used,
                                         unit_commitment=self.options.unit_commitment,
                                         ramp_constraints=self.options.unit_commitment,
                                         generation_expansion_planning=self.options.generation_expansion_planning,
                                         all_generators_fixed=False,
                                         lodf_threshold=self.options.lodf_tolerance,
                                         maximize_inter_area_flow=self.options.maximize_flows,
                                         inter_aggregation_info=self.options.inter_aggregation_info,
                                         energy_0=energy_0,
                                         fluid_level_0=fluid_level_0,
                                         logger=self.logger,
                                         export_model_fname=self.options.export_model_fname,
                                         verbose=self.options.verbose,
                                         robust=self.options.robust)

            self.results.voltage[time_indices, :] = opf_vars.bus_vars.Vm * np.exp(1j * opf_vars.bus_vars.Va)
            self.results.bus_shadow_prices[time_indices, :] = opf_vars.bus_vars.shadow_prices

            self.results.load_power[time_indices, :] = opf_vars.load_vars.p
            self.results.load_shedding[time_indices, :] = opf_vars.load_vars.shedding
            self.results.load_shedding_cost[time_indices, :] = opf_vars.load_vars.shedding_cost

            self.results.battery_power[time_indices, :] = opf_vars.batt_vars.p
            self.results.battery_energy[time_indices, :] = opf_vars.batt_vars.e

            self.results.generator_power[time_indices, :] = opf_vars.gen_vars.p
            self.results.generator_shedding[time_indices, :] = opf_vars.gen_vars.shedding
            self.results.generator_cost[time_indices, :] = opf_vars.gen_vars.cost
            self.results.generator_producing[time_indices, :] = opf_vars.gen_vars.producing
            self.results.generator_starting_up[time_indices, :] = opf_vars.gen_vars.starting_up
            self.results.generator_shutting_down[time_indices, :] = opf_vars.gen_vars.shedding
            self.results.generator_invested[time_indices, :] = opf_vars.gen_vars.invested

            self.results.Sf[time_indices, :] = opf_vars.branch_vars.flows
            self.results.St[time_indices, :] = -opf_vars.branch_vars.flows
            self.results.overloads[time_indices, :] = (opf_vars.branch_vars.flow_slacks_pos
                                                       - opf_vars.branch_vars.flow_slacks_neg)
            self.results.overloads_cost[time_indices, :] = opf_vars.branch_vars.overload_cost

            self.results.loading[time_indices, :] = opf_vars.branch_vars.loading
            self.results.phase_shift[time_indices, :] = opf_vars.branch_vars.tap_angles

            self.results.hvdc_Pf[time_indices, :] = opf_vars.hvdc_vars.flows
            self.results.hvdc_loading[time_indices, :] = opf_vars.hvdc_vars.loading

            self.results.vsc_Pf[time_indices, :] = opf_vars.vsc_vars.flows
            self.results.vsc_loading[time_indices, :] = opf_vars.vsc_vars.loading

            self.results.fluid_node_current_level[time_indices, :] = opf_vars.fluid_node_vars.current_level
            self.results.fluid_node_flow_in[time_indices, :] = opf_vars.fluid_node_vars.flow_in
            self.results.fluid_node_flow_out[time_indices, :] = opf_vars.fluid_node_vars.flow_out
            self.results.fluid_node_p2x_flow[time_indices, :] = opf_vars.fluid_node_vars.p2x_flow
            self.results.fluid_node_spillage[time_indices, :] = opf_vars.fluid_node_vars.spillage
            self.results.fluid_path_flow[time_indices, :] = opf_vars.fluid_path_vars.flow
            self.results.fluid_injection_flow[time_indices, :] = opf_vars.fluid_inject_vars.flow

            self.results.system_fuel[time_indices, :] = opf_vars.sys_vars.system_fuel
            self.results.system_emissions[time_indices, :] = opf_vars.sys_vars.system_emissions
            self.results.system_energy_cost[time_indices] = opf_vars.sys_vars.system_unit_energy_cost
            self.results.system_total_energy_cost[time_indices] = opf_vars.sys_vars.system_total_energy_cost
            self.results.power_by_technology[time_indices] = opf_vars.sys_vars.power_by_technology

            # set converged for all t to the value of acceptable solution
            self.results.converged[time_indices] = np.array([opf_vars.acceptable_solution] * opf_vars.nt)

            energy_0 = self.results.battery_energy[end_ - 1, :]
            fluid_level_0 = self.results.fluid_node_current_level[end_ - 1, :]

            # update progress bar
            self.report_progress2(i, len(groups))

            i += 1

    def add_report(self, eps: float = 1e-6) -> None:
        """
        Add a report of the results (in-place)
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

        :return:
        """

        self.tic()

        if self.engine == EngineType.GridCal:

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

        elif self.engine == EngineType.NewtonPA:

            if self.time_indices is None:
                ti = 0
                use_time_series = False
            else:
                use_time_series = True
                if self.using_clusters:
                    ti = np.arange(0, len(self.time_indices))
                else:
                    ti = self.time_indices

            if self.options.solver == SolverType.LINEAR_OPF:
                self.report_text('Running Linear OPF with Newton...')

                npa_res = newton_pa_linear_opf(circuit=self.grid,
                                               opf_options=self.options,
                                               pf_opt=PowerFlowOptions(),
                                               time_series=use_time_series,
                                               time_indices=self.time_indices)

                self.results.voltage[ti, :] = npa_res.voltage_module * np.exp(1j * npa_res.voltage_angle)
                self.results.bus_shadow_prices[ti, :] = npa_res.nodal_shadow_prices
                self.results.load_shedding[ti, :] = npa_res.load_shedding
                self.results.battery_power[ti, :] = npa_res.battery_power
                self.results.battery_energy[ti, :] = npa_res.battery_energy
                self.results.generator_power[ti, :] = npa_res.generator_power
                self.results.Sf[ti, :] = npa_res.branch_flows
                self.results.St[ti, :] = -npa_res.branch_flows
                self.results.overloads[ti, :] = npa_res.branch_overloads
                self.results.loading[ti, :] = npa_res.branch_loading
                self.results.phase_shift[ti, :] = npa_res.branch_tap_angle

                # self.results.Sbus[ti, :] = problem.get_power_injections()
                self.results.hvdc_Pf[ti, :] = npa_res.hvdc_flows
                self.results.hvdc_loading[ti, :] = npa_res.hvdc_loading

                self.results.fluid_node_current_level[ti, :] = npa_res.fluid_node_vars.current_level
                self.results.fluid_node_flow_in[ti, :] = npa_res.fluid_node_vars.flow_in
                self.results.fluid_node_flow_out[ti, :] = npa_res.fluid_node_vars.flow_out
                self.results.fluid_node_p2x_flow[ti, :] = npa_res.fluid_node_vars.p2x_flow
                self.results.fluid_node_spillage[ti, :] = npa_res.fluid_node_vars.spillage
                self.results.fluid_path_flow[ti, :] = npa_res.fluid_path_vars.flow
                self.results.fluid_injection_flow[ti, :] = npa_res.fluid_inject_vars.flow

            if self.options.solver == SolverType.NONLINEAR_OPF:
                self.report_text('Running Non-Linear OPF with Newton...')

                # pack the results
                npa_res = newton_pa_nonlinear_opf(circuit=self.grid,
                                                  pf_opt=self.pf_options,
                                                  opf_opt=self.options,
                                                  time_series=use_time_series,
                                                  time_indices=self.time_indices)

                self.results.voltage[ti, :] = npa_res.voltage
                self.results.Sbus[ti, :] = npa_res.Scalc
                self.results.bus_shadow_prices[ti, :] = npa_res.bus_shadow_prices
                self.results.load_shedding[ti, :] = npa_res.load_shedding
                self.results.battery_power[ti, :] = npa_res.battery_p
                # self.results.battery_energy[ti, :] = npa_res.battery_energy
                self.results.generator_power[ti, :] = npa_res.generator_p
                self.results.Sf[ti, :] = npa_res.Sf
                self.results.St[ti, :] = npa_res.St
                self.results.overloads[ti, :] = npa_res.branch_overload
                self.results.loading[ti, :] = npa_res.Loading
                # self.results.phase_shift[ti, :] = npa_res.branch_tap_angle

                # self.results.Sbus[ti, :] = problem.get_power_injections()
                self.results.hvdc_Pf[ti, :] = npa_res.hvdc_Pf
                self.results.hvdc_loading[ti, :] = npa_res.hvdc_loading

                self.results.fluid_node_current_level[ti, :] = npa_res.fluid_node_vars.current_level
                self.results.fluid_node_flow_in[ti, :] = npa_res.fluid_node_vars.flow_in
                self.results.fluid_node_flow_out[ti, :] = npa_res.fluid_node_vars.flow_out
                self.results.fluid_node_p2x_flow[ti, :] = npa_res.fluid_node_vars.p2x_flow
                self.results.fluid_node_spillage[ti, :] = npa_res.fluid_node_vars.spillage
                self.results.fluid_path_flow[ti, :] = npa_res.fluid_path_vars.flow
                self.results.fluid_injection_flow[ti, :] = npa_res.fluid_inject_vars.flow

        if self.options.generate_report:
            self.add_report()

        self.toc()
