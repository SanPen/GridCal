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
from GridCal.Engine.Simulations.OPF.simple_dispatch_ts import run_simple_dispatch_ts
from GridCal.Engine.Simulations.OPF.opf_ts_results import OptimalPowerFlowTimeSeriesResults
from GridCal.Engine.Simulations.driver_types import SimulationTypes
from GridCal.Engine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCal.Engine.Simulations.driver_template import TimeSeriesDriverTemplate
from GridCal.Engine.Core.Compilers.circuit_to_newton_pa import newton_pa_linear_opf, newton_pa_nonlinear_opf
from GridCal.Engine.Simulations.Clustering.clustering_results import ClusteringResults
import GridCal.Engine.basic_structures as bs


class OptimalPowerFlowTimeSeriesDriver(TimeSeriesDriverTemplate):
    name = 'Optimal power flow time series'
    tpe = SimulationTypes.OPFTimeSeries_run

    def __init__(self,
                 grid: MultiCircuit,
                 options: OptimalPowerFlowOptions,
                 time_indices: Union[bs.IntVec, None],
                 clustering_results: Union[ClusteringResults, None] = None,
                 engine: bs.EngineType = bs.EngineType.GridCal):
        """
        PowerFlowDriver class constructor
        :param grid: MultiCircuit Object
        :param options: OPF options
        :param time_indices: array of time indices to simulate
        :param engine: Calculation engine to use (if available)
        """
        TimeSeriesDriverTemplate.__init__(self,
                                          grid=grid,
                                          time_indices=time_indices,
                                          clustering_results=clustering_results,
                                          engine=engine)

        # Options to use
        self.options = options

        # power flow options
        self.pf_options = options.power_flow_options

        nt = len(self.time_indices) if self.time_indices is not None else 1

        # OPF results
        self.results: OptimalPowerFlowTimeSeriesResults = OptimalPowerFlowTimeSeriesResults(
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
            time=self.grid.time_profile if self.time_indices is not None else [datetime.datetime.now()],
            bus_types=np.ones(self.grid.get_bus_number(), dtype=int))

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
            Pl, Pg = run_simple_dispatch_ts(grid=self.grid,
                                            time_indices=self.time_indices,
                                            text_prog=self.progress_text.emit,
                                            prog_func=self.progress_signal.emit)

            self.results.generator_power[self.time_indices, :] = Pg

        else:
            self.logger.add_error('Solver not supported in this mode', str(self.options.solver))
            return

        if not remote:
            self.progress_signal.emit(0.0)
            self.progress_text.emit('Running all in an external solver, this may take a while...')

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

            if self.options.solver == SolverType.AC_OPF:
                self.progress_text.emit('Running Non-Linear OPF with Newton...')

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

        end = time.time()
        self.elapsed = end - start
