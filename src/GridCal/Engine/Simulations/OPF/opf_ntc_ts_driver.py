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
from GridCal.Engine.Core.time_series_opf_data import compile_opf_time_circuit
from GridCal.Engine.Simulations.OPF.ntc_opf import OpfNTC
from GridCal.Engine.Simulations.OPF.opf_ntc_driver import OptimalNetTransferCapacityOptions, OptimalNetTransferCapacityResults
from GridCal.Engine.Simulations.driver_types import SimulationTypes
from GridCal.Engine.Simulations.driver_template import TimeSeriesDriverTemplate
from GridCal.Engine.Simulations.Clustering.clustering import kmeans_approximate_sampling
from GridCal.Engine.Simulations.ATC.available_transfer_capacity_driver import compute_alpha


class OptimalNetTransferCapacityTimeSeriesDriver(TimeSeriesDriverTemplate):
    tpe = SimulationTypes.OptimalNetTransferCapacityTimeSeries_run
    def __init__(self, grid: MultiCircuit,
                 options: OptimalNetTransferCapacityOptions,
                 start_=0,
                 end_=None,
                 use_clustering=False,
                 cluster_number=100):
        """

        :param grid: MultiCircuit Object
        :param options: Optimal net transfer capacity options
        :param start_: time index to start (optional)
        :param end_: time index to end (optional)
        """
        TimeSeriesDriverTemplate.__init__(self,
                                          grid=grid,
                                          start_=start_,
                                          end_=end_)

        # Options to use

        self.options = options
        self.unresolved_counter = 0
        # OPF results
        # self.results = OptimalNetTransferCapacityTimeSeriesResults(
        #     br_names=[],
        #     bus_names=[],
        #     rates=[],
        #     contingency_rates=[],
        #     time_array=[])

        self.results = dict()

        self.use_clustering = use_clustering
        self.cluster_number = cluster_number

    name = tpe.value

    def run(self):
        """
        Run thread
        """
        start = time.time()

        self.progress_signal.emit(0)

        nc = compile_opf_time_circuit(self.grid)
        time_indices = self.get_time_indices()

        nt = len(time_indices)

        # declare the linear analysis
        linear = LinearAnalysis(
            grid=self.grid,
            distributed_slack=False,
            correct_values=False)

        linear.run()

        # declare the results
        # self.results = OptimalNetTransferCapacityTimeSeriesResults(
        #     br_names=linear.numerical_circuit.branch_names,
        #     bus_names=linear.numerical_circuit.bus_names,
        #     rates=nc.Rates,
        #     contingency_rates=nc.ContingencyRates,
        #     time_array=nc.time_array[time_indices])

        if self.use_clustering:
            self.progress_text.emit('Clustering...')
            X = nc.Sbus
            X = X[:, time_indices].real.T

            # cluster and re-assign the time indices
            time_indices, sampled_probabilities = kmeans_approximate_sampling(
                    X, n_points=self.cluster_number)

        # get the power injections
        P = nc.Sbus.real  # these are in p.u.

        for it, t in enumerate(time_indices):

            if self.progress_text is not None:
                self.progress_text.emit('Optimal net transfer capacity at ' + str(self.grid.time_profile[t]))

            # compute the branch exchange sensitivity (alpha)
            alpha = compute_alpha(
                ptdf=linear.PTDF,
                P0=P[:, t],
                # no problem that there are in p.u., are only used for the sensitivity
                Pinstalled=nc.bus_installed_power,
                idx1=self.options.area_from_bus_idx,
                idx2=self.options.area_to_bus_idx,
                bus_types=nc.bus_types_prof(t),
                dT=self.options.sensitivity_dT,
                mode=self.options.sensitivity_mode.value)

            # Define the problem
            self.progress_text.emit('Formulating NTC OPF...')

            problem = OpfNTC(
                numerical_circuit=nc,
                area_from_bus_idx=self.options.area_from_bus_idx,
                area_to_bus_idx=self.options.area_to_bus_idx,
                alpha=alpha,
                LODF=linear.LODF,
                solver_type=self.options.mip_solver,
                generation_formulation=self.options.generation_formulation,
                monitor_only_sensitive_branches=self.options.monitor_only_sensitive_branches,
                branch_sensitivity_threshold=self.options.branch_sensitivity_threshold,
                skip_generation_limits=self.options.skip_generation_limits,
                consider_contingencies=self.options.consider_contingencies,
                maximize_exchange_flows=self.options.maximize_exchange_flows,
                dispatch_all_areas=self.options.dispatch_all_areas,
                tolerance=self.options.tolerance,
                weight_power_shift=self.options.weight_power_shift,
                weight_generation_cost=self.options.weight_generation_cost,
                weight_generation_delta=self.options.weight_generation_delta,
                weight_kirchoff=self.options.weight_kirchoff,
                weight_overloads=self.options.weight_overloads,
                weight_hvdc_control=self.options.weight_hvdc_control,
                logger=self.logger)

            # Solve
            self.progress_text.emit('Solving NTC OPF...['+str(t)+']')

            problem.formulate_ts(add_slacks=True, t=t)

            solved = problem.solve_ts(with_check=self.options.with_check,
                                      time_limit_ms=self.options.time_limit_ms)
            err = problem.error()

            self.logger += problem.logger

            if not solved:
                self.unresolved_counter += 1
                self.logger.add_error(
                    'Did not solve',
                    'NTC OPF',
                    str(err),
                    self.options.tolerance)

            else:
                # pack the results
                self.results[t] = OptimalNetTransferCapacityResults(
                    bus_names=nc.bus_data.bus_names,
                    branch_names=nc.branch_data.branch_names,
                    load_names=nc.load_data.load_names,
                    generator_names=nc.generator_data.generator_names,
                    battery_names=nc.battery_data.battery_names,
                    hvdc_names=nc.hvdc_data.names,
                    Sbus=problem.get_power_injections(),
                    voltage=problem.get_voltage(),
                    load_shedding=problem.get_load_shedding(),
                    generator_shedding=np.zeros((nc.ngen, 1)),
                    battery_power=np.zeros((nc.nbatt, 1)),
                    controlled_generation_power=problem.get_generator_power(),
                    Sf=problem.get_branch_power_from(),
                    overloads=problem.get_overloads(),
                    loading=problem.get_loading(),
                    converged=bool(solved),
                    bus_types=nc.bus_types,
                    hvdc_flow=problem.get_hvdc_flow(),
                    hvdc_loading=problem.get_hvdc_loading(),
                    hvdc_slacks=problem.get_hvdc_slacks(),
                    phase_shift=problem.get_phase_angles(),
                    generation_delta=problem.get_generator_delta(),
                    generation_delta_slacks=problem.get_generator_delta_slacks(),
                    inter_area_branches=problem.inter_area_branches,
                    inter_area_hvdc=problem.inter_area_hvdc,
                    alpha=alpha,
                    contingency_flows_list=problem.get_contingency_flows_list(),
                    contingency_indices_list=problem.contingency_indices_list,
                    contingency_flows_slacks_list=problem.get_contingency_flows_slacks_list(),
                    rates=nc.branch_data.branch_rates[:, t],
                    contingency_rates=nc.branch_data.branch_contingency_rates[:, t])

        end = time.time()
        self.elapsed = end-start


if __name__ == '__main__':

    import GridCal.Engine.basic_structures as bs
    import GridCal.Engine.Devices as dev
    from GridCal.Engine.Simulations.ATC.available_transfer_capacity_driver import AvailableTransferMode
    from GridCal.Engine import PowerFlowOptions, FileOpen, LinearAnalysis, PowerFlowDriver, SolverType

    fname = r'd:\v19_20260105_22_zero_100hconsecutivas_active_profilesEXP_timestamp_FRfalse.gridcal'

    main_circuit = FileOpen(fname).open()

    areas_from_idx = [0, 1, 2, 3, 4]
    areas_to_idx = [7]

    areas_from = [main_circuit.areas[i] for i in areas_from_idx]
    areas_to = [main_circuit.areas[i] for i in areas_to_idx]

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

    lst_from = main_circuit.get_areas_buses(areas_from)
    lst_to = main_circuit.get_areas_buses(areas_to)
    lst_br = main_circuit.get_inter_areas_branches(areas_from, areas_to)
    lst_br_hvdc = main_circuit.get_inter_areas_hvdc_branches(areas_from, areas_to)

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

    mip_solver = bs.MIPSolvers.CBC

    generation_formulation = dev.GenerationNtcFormulation.Proportional

    monitor_only_sensitive_branches = True
    skip_generation_limits = True
    branch_sensitivity_threshold = 0.05
    dT = 100
    consider_contingencies = True
    maximize_exchange_flows = True
    perform_previous_checks = False
    dispatch_all_areas = False
    tolerance = 1e-2
    sensitivity_dT = 100.0
    sensitivity_mode = AvailableTransferMode.InstalledPower
    weight_power_shift = 1e0
    weight_generation_cost = 1e-2
    weight_generation_delta = 1e0
    weight_kirchoff = 1e5
    weight_overloads = 1e5
    weight_hvdc_control = 1e0

    options = OptimalNetTransferCapacityOptions(
        area_from_bus_idx=idx_from,
        area_to_bus_idx=idx_to,
        mip_solver=mip_solver,
        generation_formulation=generation_formulation,
        monitor_only_sensitive_branches=monitor_only_sensitive_branches,
        branch_sensitivity_threshold=branch_sensitivity_threshold,
        skip_generation_limits=skip_generation_limits,
        consider_contingencies=consider_contingencies,
        maximize_exchange_flows=maximize_exchange_flows,
        dispatch_all_areas=dispatch_all_areas,
        tolerance=tolerance,
        sensitivity_dT=dT,
        sensitivity_mode=sensitivity_mode,
        perform_previous_checks=perform_previous_checks,
        weight_power_shift=weight_power_shift,
        weight_generation_cost=weight_generation_cost,
        weight_generation_delta=weight_generation_delta,
        weight_kirchoff=0,
        weight_overloads=weight_overloads,
        weight_hvdc_control=weight_hvdc_control,
        with_check=False,
        time_limit_ms=1e4)

    print('Running optimal power flow...')

    # set optimal net transfer capacity driver instance
    start = 0
    end = main_circuit.get_time_number()-1
    driver = OptimalNetTransferCapacityTimeSeriesDriver(
        grid=main_circuit,
        options=options,
        start_=start,
        end_=end)

    driver.run()

    for t in range(end):
        if t not in driver.results.keys():
            print('\n\nHora', t, ': Sin solución',)
        else:
            print('\n\nHora', t, ': Capacidad', driver.results[t].get_exchange_power(), "MW")
            labels, columns, data = driver.results[t].get_contingency_report()
            df = pd.DataFrame(index=labels, columns=columns, data=data)
            print(df[['Monitored','Contingency', 'ContingencyFlow (%)', 'ContingencyFlow (MW)']][:5])

    print('\n\nTotal sin resultados:', driver.unresolved_counter)
    print('\n\nTotal scs.:', driver.elapsed/1e3)