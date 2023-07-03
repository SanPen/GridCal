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
import datetime

import numpy as np
import pandas as pd
import time
from typing import Dict, Union
from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.basic_structures import TimeGrouping, get_time_groups
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.basic_structures import SolverType
from GridCal.Engine.Simulations.OPF.opf_options import OptimalPowerFlowOptions
from GridCal.Engine.Simulations.OPF.dc_opf_ts import OpfDcTimeSeries
from GridCal.Engine.Simulations.OPF.simple_dispatch_ts import run_simple_dispatch
from GridCal.Engine.Simulations.OPF.opf_results import OptimalPowerFlowResults
from GridCal.Engine.Simulations.driver_types import SimulationTypes
from GridCal.Engine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCal.Engine.Simulations.driver_template import TimeSeriesDriverTemplate
from GridCal.Engine.Core.Compilers.circuit_to_newton_pa import newton_pa_linear_opf, newton_pa_nonlinear_opf
from GridCal.Engine.Simulations.Clustering.clustering_results import ClusteringResults
import GridCal.Engine.basic_structures as bs


class OptimalPowerFlowDriver(TimeSeriesDriverTemplate):
    name = 'Optimal power flow time series'
    tpe = SimulationTypes.OPF_run

    def __init__(self,
                 grid: MultiCircuit,
                 options: OptimalPowerFlowOptions,
                 engine: bs.EngineType = bs.EngineType.GridCal):
        """
        PowerFlowDriver class constructor
        :param grid: MultiCircuit Object
        :param options: OPF options
        :param engine: Calculation engine to use (if available)
        """
        TimeSeriesDriverTemplate.__init__(self,
                                          grid=grid,
                                          time_indices=None,
                                          clustering_results=None,
                                          engine=engine)

        # Options to use
        self.options = options

        # power flow options
        self.pf_options = options.power_flow_options

        nt = len(self.time_indices) if self.time_indices is not None else 1

        # OPF results
        self.results: OptimalPowerFlowResults = OptimalPowerFlowResults(
            bus_names=self.grid.get_bus_names(),
            branch_names=self.grid.get_branch_names_wo_hvdc(),
            load_names=self.grid.get_load_names(),
            generator_names=self.grid.get_generator_names(),
            battery_names=self.grid.get_battery_names(),
            hvdc_names=self.grid.get_hvdc_names(),
            n=self.grid.get_bus_number(),
            m=self.grid.get_branch_number_wo_hvdc(),
            nt=nt,
            ngen=self.grid.get_generators_number(),
            nbat=self.grid.get_batteries_number(),
            nload=self.grid.get_loads_number(),
            nhvdc=self.grid.get_hvdc_number(),
            bus_types=np.ones(self.grid.get_bus_number(), dtype=int),
            area_names=self.grid.get_area_names())

        self.all_solved = True

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
            self.progress_signal.emit(0.0)
            self.progress_text.emit('Formulating problem...')

        if self.options.solver == SolverType.DC_OPF:

            # DC optimal power flow
            problem = OpfDcTimeSeries(circuit=self.grid,
                                      time_indices=self.time_indices,
                                      solver_type=self.options.mip_solver,
                                      zonal_grouping=self.options.zonal_grouping,
                                      skip_generation_limits=self.options.skip_generation_limits,
                                      consider_contingencies=self.options.consider_contingencies,
                                      LODF=self.options.LODF,
                                      lodf_tolerance=self.options.lodf_tolerance,
                                      maximize_inter_area_flow=self.options.maximize_flows,
                                      buses_areas_1=self.options.area_from_bus_idx,
                                      buses_areas_2=self.options.area_to_bus_idx)

        elif self.options.solver == SolverType.Simple_OPF:

            # AC optimal power flow
            Pl, Pg = run_simple_dispatch(grid=self.grid,
                                         text_prog=self.progress_text.emit,
                                         prog_func=self.progress_signal.emit)

            self.results.generator_power = Pg

        else:
            self.logger.add_error('Solver not supported in this mode', str(self.options.solver))
            return

        if not remote:
            self.progress_signal.emit(0.0)
            self.progress_text.emit('Running all in an external solver, this may take a while...')

        # solve the problem
        problem.formulate(batteries_energy_0=batteries_energy_0)
        status = problem.solve()
        print("Status:", status)

        self.results.voltage[self.time_indices, :] = problem.get_voltage()
        self.results.bus_shadow_prices[self.time_indices, :] = problem.get_shadow_prices()
        self.results.load_shedding[self.time_indices, :] = problem.get_load_shedding()
        self.results.battery_power[self.time_indices, :] = problem.get_battery_power()
        self.results.battery_energy[self.time_indices, :] = problem.get_battery_energy()
        self.results.generator_power[self.time_indices, :] = problem.get_generator_power()
        self.results.Sf[self.time_indices, :] = problem.get_branch_power_from()
        self.results.St[self.time_indices, :] = problem.get_branch_power_to()
        self.results.overloads[self.time_indices, :] = problem.get_overloads()
        self.results.loading[self.time_indices, :] = problem.get_loading()

        self.results.Sbus[self.time_indices, :] = problem.get_power_injections()
        self.results.hvdc_Pf[self.time_indices, :] = problem.get_hvdc_flows()
        self.results.hvdc_loading[self.time_indices, :] = self.results.hvdc_Pf[self.time_indices,
                                                          :] / self.numerical_circuit.hvdc_data.rate[:,
                                                               self.time_indices].transpose()
        self.results.phase_shift[self.time_indices, :] = problem.get_phase_shifts()

        self.results.contingency_flows_list += problem.get_contingency_flows_list().tolist()
        self.results.contingency_indices_list += problem.contingency_indices_list
        self.results.contingency_flows_slacks_list += problem.get_contingency_flows_slacks_list().tolist()

        return self.results

    def opf_by_groups(self):
        """
        Run the OPF by groups
        """

        self.progress_signal.emit(0.0)
        self.progress_text.emit('Making groups...')

        # get the partition points of the time series
        groups = get_time_groups(t_array=self.grid.time_profile, grouping=self.options.grouping)

        n = len(groups)
        i = 1
        energy_0 = self.numerical_circuit.battery_data.soc_0 * self.numerical_circuit.battery_data.enom
        while i < n and not self.__cancel__:

            start_ = groups[i - 1]
            end_ = groups[i]

            # show progress message
            print(start_, ':', end_, ' [', end_ - start_, ']')
            self.progress_text.emit('Running OPF for the time group {0} '
                                    'start {1} - end {2} in external solver...'.format(i, start_, end_))

            if start_ >= self.start_ and end_ <= self.end_:
                # run an opf for the group interval only if the group is within the start:end boundaries
                self.opf(start_=start_, end_=end_ + 1,
                         remote=True,
                         batteries_energy_0=energy_0)

            energy_0 = self.results.battery_energy[end_ - 1, :]

            # update progress bar
            progress = ((start_ - self.start_ + 1) / (self.end_ - self.start_)) * 100
            self.progress_signal.emit(progress)

            i += 1

    def run(self):
        """

        :return:
        """

        start = time.time()
        if self.engine == bs.EngineType.GridCal:

            if self.options.grouping == TimeGrouping.NoGrouping:
                self.opf()
            else:
                self.opf_by_groups()

        elif self.engine == bs.EngineType.NewtonPA:

            ti = self.time_indices if self.time_indices is not None else 0
            use_time_series = self.time_indices is not None

            if self.options.solver == SolverType.DC_OPF:
                self.progress_text.emit('Running Linear OPF with Newton...')

                npa_res = newton_pa_linear_opf(circuit=self.grid,
                                               opf_options=self.options,
                                               pf_opt=PowerFlowOptions(),
                                               time_series=use_time_series,
                                               time_indices=self.time_indices)

                self.results.voltage = npa_res.voltage_module[0, :] * np.exp(1j * npa_res.voltage_angle[0, :])
                self.results.bus_shadow_prices = npa_res.nodal_shadow_prices[0, :]
                self.results.load_shedding = npa_res.load_shedding[0, :]
                self.results.battery_power = npa_res.battery_power[0, :]
                # self.results.battery_energy = npa_res.battery_energy[0, :]
                self.results.generator_power = npa_res.generator_power[0, :]
                self.results.Sf = npa_res.branch_flows[0, :]
                self.results.St = -npa_res.branch_flows[0, :]
                self.results.overloads = npa_res.branch_overloads[0, :]
                self.results.loading = npa_res.branch_loading[0, :]
                self.results.phase_shift = npa_res.branch_tap_angle[0, :]

                # self.results.Sbus = npa_res.
                self.results.hvdc_Pf = npa_res.hvdc_flows[0, :]
                self.results.hvdc_loading = npa_res.hvdc_loading[0, :]
                self.results.converged = True

            if self.options.solver == SolverType.AC_OPF:
                self.progress_text.emit('Running Non-Linear OPF with Newton...')

                # pack the results
                npa_res = newton_pa_nonlinear_opf(circuit=self.grid,
                                                  pf_opt=self.pf_options,
                                                  opf_opt=self.options,
                                                  time_series=use_time_series,
                                                  time_indices=self.time_indices)

                self.results.voltage = npa_res.voltage[0, :]
                self.results.Sbus = npa_res.Scalc[0, :]
                self.results.bus_shadow_prices = npa_res.bus_shadow_prices[0, :]
                self.results.load_shedding = npa_res.load_shedding[0, :]
                self.results.battery_power = npa_res.battery_p[0, :]
                # self.results.battery_energy = npa_res.battery_energy[0, :]
                self.results.generator_power = npa_res.generator_p[0, :]
                self.results.Sf = npa_res.Sf[0, :]
                self.results.St = npa_res.St[0, :]
                self.results.overloads = npa_res.branch_overload[0, :]
                self.results.loading = npa_res.Loading[0, :]
                self.results.phase_shift = npa_res.tap_angle[0, :]

                self.results.hvdc_Pf = npa_res.hvdc_Pf[0, :]
                self.results.hvdc_loading = npa_res.hvdc_loading[0, :]
                self.results.converged = npa_res.converged

        end = time.time()
        self.elapsed = end - start
