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
import datetime

import numpy as np
import pandas as pd
from typing import Union, List
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.enumerations import EngineType, SimulationTypes
from GridCalEngine.Simulations.OPF.opf_options import OptimalPowerFlowOptions
from GridCalEngine.Simulations.OPF.linear_opf_ts import run_linear_opf_ts
from GridCalEngine.Simulations.OPF.NumericalMethods.ac_opf import run_nonlinear_opf
from GridCalEngine.Simulations.NodalCapacity.nodal_capacity_options import NodalCapacityOptions
from GridCalEngine.Simulations.NodalCapacity.nodal_capacity_ts_results import NodalCapacityTimeSeriesResults
from GridCalEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCalEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver
from GridCalEngine.Simulations.ContinuationPowerFlow.continuation_power_flow_driver import ContinuationPowerFlowDriver
from GridCalEngine.Simulations.ContinuationPowerFlow.continuation_power_flow_options import ContinuationPowerFlowOptions
from GridCalEngine.Simulations.ContinuationPowerFlow.continuation_power_flow_input import ContinuationPowerFlowInput
from GridCalEngine.Simulations.driver_template import TimeSeriesDriverTemplate
from GridCalEngine.Simulations.Clustering.clustering_results import ClusteringResults
from GridCalEngine.basic_structures import IntVec
from GridCalEngine.enumerations import NodalCapacityMethod, CpfStopAt, CpfParametrization


class NodalCapacityTimeSeriesDriver(TimeSeriesDriverTemplate):
    name = 'Nodal capacity time series'
    tpe = SimulationTypes.NodalCapacityTimeSeries_run

    def __init__(self,
                 grid: MultiCircuit,
                 options: Union[NodalCapacityOptions, None] = None,
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
                                          time_indices=time_indices,
                                          clustering_results=clustering_results,
                                          engine=engine)

        # Options to use
        self.options = options if options else NodalCapacityOptions()

        # find the number of time steps
        nt = len(self.time_indices) if self.time_indices is not None else 1

        # compose the time array
        time_array = (self.grid.time_profile[self.time_indices] if self.time_indices is not None
                      else [datetime.datetime.now()])

        # OPF results
        self.results: NodalCapacityTimeSeriesResults = NodalCapacityTimeSeriesResults(
            bus_names=self.grid.get_bus_names(),
            branch_names=self.grid.get_branch_names_wo_hvdc(),
            load_names=self.grid.get_load_names(),
            generator_names=self.grid.get_generator_names(),
            battery_names=self.grid.get_battery_names(),
            hvdc_names=self.grid.get_hvdc_names(),
            fuel_names=self.grid.get_fuel_names(),
            emission_names=self.grid.get_emission_names(),
            fluid_node_names=self.grid.get_fluid_node_names(),
            fluid_path_names=self.grid.get_fluid_path_names(),
            fluid_injection_names=self.grid.get_fluid_injection_names(),
            n=self.grid.get_bus_number(),
            m=self.grid.get_branch_number_wo_hvdc(),
            nt=nt,
            ngen=self.grid.get_generators_number(),
            nbat=self.grid.get_batteries_number(),
            nload=self.grid.get_loads_number(),
            nhvdc=self.grid.get_hvdc_number(),
            n_fluid_node=self.grid.get_fluid_nodes_number(),
            n_fluid_path=self.grid.get_fluid_paths_number(),
            n_fluid_injection=self.grid.get_fluid_injection_number(),
            time_array=time_array,
            bus_types=np.ones(self.grid.get_bus_number(), dtype=int),
            clustering_results=clustering_results,
            capacity_nodes_idx=self.options.capacity_nodes_idx
        )

        self.all_solved = True

    @property
    def opf_options(self) -> OptimalPowerFlowOptions:
        """
        Get the OptimalPowerFlowOptions options provides with the OpfOptions
        :return: PowerFlowOptions
        """
        return self.options.opf_options

    @property
    def pf_options(self) -> PowerFlowOptions:
        """
        Get the PowerFlow options provides with the OpfOptions
        :return: PowerFlowOptions
        """
        return self.options.opf_options.power_flow_options

    def get_steps(self):
        """
        Get time steps list of strings
        """
        return [l.strftime('%d-%m-%Y %H:%M') for l in pd.to_datetime(self.grid.time_profile)]

    def get_time_indices(self):

        if self.time_indices is not None:
            has_ts = True
            t_indices: Union[List[None], IntVec] = self.time_indices
        else:
            has_ts = False
            t_indices: Union[List[None], IntVec] = [None]

        return has_ts, t_indices

    def linear_opf(self, remote=False, batteries_energy_0=None):
        """
        Run a power flow for every circuit
        :param remote: is this function being called from the time series?
        :param batteries_energy_0: initial state of the batteries, if None the default values are taken
        :return: OptimalPowerFlowResults object
        """

        if not remote:
            self.report_progress(0.0)
            self.report_text('Formulating problem...')

        # DC optimal power flow
        opf_vars = run_linear_opf_ts(grid=self.grid,
                                     time_indices=self.time_indices,
                                     solver_type=self.opf_options.mip_solver,
                                     zonal_grouping=self.opf_options.zonal_grouping,
                                     skip_generation_limits=self.opf_options.skip_generation_limits,
                                     consider_contingencies=self.opf_options.consider_contingencies,
                                     contingency_groups_used=self.opf_options.contingency_groups_used,
                                     unit_Commitment=self.opf_options.unit_commitment,
                                     ramp_constraints=self.opf_options.unit_commitment,
                                     all_generators_fixed=False,
                                     lodf_threshold=self.opf_options.lodf_tolerance,
                                     maximize_inter_area_flow=self.opf_options.maximize_flows,
                                     areas_from=self.opf_options.areas_from,
                                     areas_to=self.opf_options.areas_to,
                                     energy_0=batteries_energy_0,
                                     optimize_nodal_capacity=True,
                                     nodal_capacity_sign=self.options.nodal_capacity_sign,
                                     capacity_nodes_idx=self.options.capacity_nodes_idx,
                                     logger=self.logger,
                                     progress_text=self.report_text,
                                     progress_func=self.report_progress,
                                     export_model_fname=self.opf_options.export_model_fname)

        self.results.Sbus = opf_vars.bus_vars.Pcalc + 1j * np.zeros_like(opf_vars.bus_vars.Pcalc)
        self.results.voltage = np.ones((opf_vars.nt, opf_vars.nbus)) * np.exp(1j * opf_vars.bus_vars.theta)
        self.results.bus_shadow_prices = opf_vars.bus_vars.shadow_prices
        self.results.nodal_capacity = opf_vars.nodal_capacity_vars.P

        self.results.load_shedding = opf_vars.load_vars.shedding

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

        self.results.Sf = opf_vars.branch_vars.flows
        self.results.St = -opf_vars.branch_vars.flows
        self.results.overloads = opf_vars.branch_vars.flow_slacks_pos - opf_vars.branch_vars.flow_slacks_neg
        self.results.loading = opf_vars.branch_vars.loading
        self.results.phase_shift = opf_vars.branch_vars.tap_angles

        self.results.hvdc_Pf = opf_vars.hvdc_vars.flows
        self.results.hvdc_loading = opf_vars.hvdc_vars.loading

        self.results.fluid_node_current_level = opf_vars.fluid_node_vars.current_level
        self.results.fluid_node_flow_in = opf_vars.fluid_node_vars.flow_in
        self.results.fluid_node_flow_out = opf_vars.fluid_node_vars.flow_out
        self.results.fluid_node_p2x_flow = opf_vars.fluid_node_vars.p2x_flow
        self.results.fluid_node_spillage = opf_vars.fluid_node_vars.spillage
        self.results.fluid_path_flow = opf_vars.fluid_path_vars.flow
        self.results.fluid_injection_flow = opf_vars.fluid_inject_vars.flow

        self.results.system_fuel = opf_vars.sys_vars.system_fuel
        self.results.system_emissions = opf_vars.sys_vars.system_emissions
        self.results.system_energy_cost = opf_vars.sys_vars.system_energy_cost

        # set converged for all t to the value of acceptable solution
        self.results.converged = np.array([opf_vars.acceptable_solution] * opf_vars.nt)

        if not remote:
            self.report_progress(0.0)
            self.report_text('Running all in an external solver, this may take a while...')

        return self.results

    def non_linear_opf(self, remote=False, batteries_energy_0=None):
        """
        Run a power flow for every circuit
        :param remote: is this function being called from the time series?
        :param batteries_energy_0: initial state of the batteries, if None the default values are taken
        :return: OptimalPowerFlowResults object
        """

        if not remote:
            self.report_progress(0.0)
            self.report_text('Formulating problem...')

        has_ts, t_indices = self.get_time_indices()

        self.report_progress(0.0)
        for it, t in enumerate(t_indices):

            # report progress
            if has_ts:
                self.report_text('Nonlinear OPF at ' + str(self.grid.time_profile[t]) + '...')
                self.report_progress2(it, len(self.time_indices))
            else:
                self.report_text('Nonlinear OPF at the snapshot...')
                self.report_progress2(it, 1)

            # run opf
            res = run_nonlinear_opf(grid=self.grid,
                                    opf_options=self.opf_options,
                                    pf_options=self.pf_options,
                                    t_idx=t,
                                    # for the first power flow, use the given strategy
                                    # for the successive ones, use the previous solution
                                    pf_init=self.opf_options.ips_init_with_pf if it == 0 else True,
                                    Sbus_pf0=self.results.Sbus[it - 1, :] if it > 0 else None,
                                    voltage_pf0=self.results.voltage[it - 1, :] if it > 0 else None,
                                    optimize_nodal_capacity=True,
                                    nodal_capacity_sign=self.options.nodal_capacity_sign,
                                    capacity_nodes_idx=self.options.capacity_nodes_idx,
                                    logger=self.logger)

            # set the results
            Sbase = self.grid.Sbase
            self.results.voltage[it, :] = res.V
            self.results.Sbus[it, :] = res.S * Sbase
            self.results.bus_shadow_prices[it, :] = res.lam_p
            self.results.nodal_capacity[it, :] = res.nodal_capacity
            # self.results.load_shedding = npa_res.load_shedding[0, :]
            # self.results.battery_power = npa_res.battery_p[0, :]
            # self.results.battery_energy = npa_res.battery_energy[0, :]
            self.results.generator_power[it, :] = res.Pg * Sbase
            self.results.generator_cost[it, :] = res.Pcost

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

        if not remote:
            self.report_progress(0.0)
            self.report_text('Running all in an external solver, this may take a while...')

        return self.results

    def cpf(self, remote=False, batteries_energy_0=None):
        """
        Run a power flow for every circuit
        :param remote: is this function being called from the time series?
        :param batteries_energy_0: initial state of the batteries, if None the default values are taken
        :return: OptimalPowerFlowResults object
        """

        if not remote:
            self.report_progress(0.0)
            self.report_text('Formulating problem...')

        has_ts, t_indices = self.get_time_indices()

        # we need to initialize with a power flow solution
        pf_options = PowerFlowOptions()
        power_flow = PowerFlowDriver(grid=self.grid, options=pf_options)
        power_flow.run()

        # declare the CPF options
        vc_options = ContinuationPowerFlowOptions(step=0.001,
                                                  approximation_order=CpfParametrization.ArcLength,
                                                  adapt_step=True,
                                                  step_min=0.00001,
                                                  step_max=0.2,
                                                  error_tol=1e-3,
                                                  tol=1e-6,
                                                  max_it=20,
                                                  stop_at=CpfStopAt.Full,
                                                  verbose=0)

        # define the direcion of loading
        base_power = power_flow.results.Sbus / self.grid.Sbase
        target_power = base_power.copy()
        target_power[self.options.capacity_nodes_idx] *= 2.0 * self.options.nodal_capacity_sign

        # We compose the target direction
        vc_inputs = ContinuationPowerFlowInput(Sbase=base_power,
                                               Vbase=power_flow.results.voltage,
                                               Starget=target_power)

        # declare the CPF driver and run
        vc = ContinuationPowerFlowDriver(grid=self.grid,
                                         options=vc_options,
                                         inputs=vc_inputs,
                                         pf_options=pf_options)
        vc.run()

        self.report_progress(0.0)
        for it, t in enumerate(t_indices):

            # report progress
            if has_ts:
                self.report_text('Nonlinear OPF at ' + str(self.grid.time_profile[t]) + '...')
                self.report_progress2(it, len(self.time_indices))
            else:
                self.report_text('Nonlinear OPF at the snapshot...')
                self.report_progress2(it, 1)

            # run opf
            res = vc.run_at(t_idx=t)

            # set the results
            Sbase = self.grid.Sbase
            self.results.voltage[it, :] = res.voltages[-1, :]
            self.results.Sbus[it, :] = res.Sbus[-1, :] * Sbase
            # self.results.bus_shadow_prices[it, :] = res.lam_p
            # self.results.load_shedding = npa_res.load_shedding[0, :]
            # self.results.battery_power = npa_res.battery_p[0, :]
            # self.results.battery_energy = npa_res.battery_energy[0, :]
            # self.results.generator_power[it, :] = res.Pg * Sbase
            # self.results.generator_cost[it, :] = res.Pcost

            self.results.Sf[it, :] = res.Sf[-1, :] * Sbase
            self.results.St[it, :] = res.St[-1, :] * Sbase
            # self.results.overloads[it, :] = (res.sl_sf - res.sl_st) * Sbase
            self.results.loading[it, :] = res.loading[-1, :]
            # self.results.phase_shift[it, :] = res.tap_phase

            # self.results.hvdc_Pf[it, :] = res.hvdc_Pf
            # self.results.hvdc_loading[it, :] = res.hvdc_loading
            self.results.converged[it] = res.converged[-1]

            if self.__cancel__:
                return self.results

        if not remote:
            self.report_progress(0.0)
            self.report_text('Running all in an external solver, this may take a while...')

        return self.results

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

            if self.options.method == NodalCapacityMethod.LinearOptimization:
                self.linear_opf()

            elif self.options.method == NodalCapacityMethod.NonlinearOptimization:
                self.non_linear_opf()

            elif self.options.method == NodalCapacityMethod.CPF:
                self.cpf()

        elif self.engine == EngineType.NewtonPA:

            self.logger.add_warning("Engine not implemented", value=str(self.engine.value))

        if self.opf_options.generate_report:
            self.add_report()

        self.toc()
