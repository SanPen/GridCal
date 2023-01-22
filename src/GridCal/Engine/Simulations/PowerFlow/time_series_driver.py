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

import json
import pandas as pd
import numpy as np
import time

from GridCal.Engine.Simulations.PowerFlow.time_series_results import TimeSeriesResults
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCal.Engine.Simulations.PowerFlow.power_flow_worker import single_island_pf, get_hvdc_power
from GridCal.Engine.Core.time_series_pf_data import compile_time_circuit, BranchImpedanceMode
from GridCal.Engine.Core.snapshot_pf_data import compile_snapshot_circuit_at
from GridCal.Engine.Simulations.driver_types import SimulationTypes
from GridCal.Engine.Simulations.driver_template import DriverTemplate
import GridCal.Engine.Simulations.PowerFlow.power_flow_worker as pf_worker
from GridCal.Engine.Core.Compilers.circuit_to_newton import NEWTON_AVAILBALE, to_newton_native, newton_power_flow
from GridCal.Engine.Core.Compilers.circuit_to_bentayga import BENTAYGA_AVAILABLE, bentayga_pf
from GridCal.Engine.Core.Compilers.circuit_to_newton_pa import NEWTON_PA_AVAILABLE, newton_pa_pf
import GridCal.Engine.basic_structures as bs


class TimeSeries(DriverTemplate):
    tpe = SimulationTypes.TimeSeries_run
    name = tpe.value

    def __init__(self, grid: MultiCircuit, options: PowerFlowOptions, opf_time_series_results=None,
                 start_=0, end_=None, engine: bs.EngineType = bs.EngineType.GridCal):
        """
        TimeSeries constructor
        @param grid: MultiCircuit instance
        @param options: PowerFlowOptions instance
        """
        DriverTemplate.__init__(self, grid, engine=engine)

        # reference the grid directly
        # self.grid = grid

        self.options = options

        self.opf_time_series_results = opf_time_series_results

        self.start_ = start_

        self.end_ = end_

    def get_steps(self):
        """
        Get time steps list of strings
        """
        return [l.strftime('%d-%m-%Y %H:%M') for l in pd.to_datetime(self.grid.time_profile[self.start_: self.end_])]

    def run_single_thread_old(self, time_indices) -> TimeSeriesResults:
        """
        Run single thread time series
        :param time_indices: array of time indices to consider
        :return: TimeSeriesResults instance
        """

        # compile the multi-circuit
        time_circuit = compile_time_circuit(circuit=self.grid,
                                            apply_temperature=False,
                                            branch_tolerance_mode=BranchImpedanceMode.Specified,
                                            opf_results=self.opf_time_series_results,
                                            use_stored_guess=self.options.use_stored_guess)

        # do the topological computation
        time_islands = time_circuit.split_into_islands(ignore_single_node_islands=self.options.ignore_single_node_islands)

        # initialize the grid time series results we will append the island results with another function
        time_series_results = TimeSeriesResults(n=time_circuit.nbus,
                                                m=time_circuit.nbr,
                                                n_tr=time_circuit.ntr,
                                                n_hvdc=time_circuit.nhvdc,
                                                bus_names=time_circuit.bus_names,
                                                branch_names=time_circuit.branch_names,
                                                transformer_names=time_circuit.tr_names,
                                                hvdc_names=time_circuit.hvdc_names,
                                                bus_types=time_circuit.bus_types,
                                                time_array=self.grid.time_profile[time_indices])

        time_series_results.bus_types = time_circuit.bus_types

        # compose total buses-> bus index dict
        bus_dict = self.grid.get_bus_index_dict()

        time_indices_set = set(time_indices)

        # For every island, run the time series
        for island_index, calculation_input in enumerate(time_islands):

            # compose the HVDC power injections
            Shvdc, Losses_hvdc, Pf_hvdc, Pt_hvdc, loading_hvdc, n_free = get_hvdc_power(self.grid,
                                                                                        bus_dict,
                                                                                        theta=np.zeros(time_circuit.nbus))

            # Are we dispatching storage? if so, generate a dictionary of battery -> bus index
            # to be able to set the batteries values into the vector S
            batteries = list()
            batteries_bus_idx = list()
            if self.options.dispatch_storage:
                for k, bus in enumerate(self.grid.buses):
                    for battery in bus.batteries:
                        battery.reset()  # reset the calculation values
                        batteries.append(battery)
                        batteries_bus_idx.append(k)

            self.progress_text.emit('Time series at circuit ' + str(island_index) + '...')

            # find the original indices
            bus_original_idx = calculation_input.original_bus_idx
            branch_original_idx = calculation_input.original_branch_idx

            # declare a results object for the partition
            results = TimeSeriesResults(n=calculation_input.nbus,
                                        m=calculation_input.nbr,
                                        n_tr=calculation_input.ntr,
                                        n_hvdc=calculation_input.nhvdc,
                                        bus_names=calculation_input.bus_data.names,
                                        branch_names=calculation_input.branch_data.names,
                                        transformer_names=calculation_input.transformer_data.names,
                                        hvdc_names=calculation_input.hvdc_data.names,
                                        bus_types=time_circuit.bus_data.bus_types,
                                        time_array=self.grid.time_profile[calculation_input.original_time_idx])

            self.progress_signal.emit(0.0)

            # default value in case of single-valued profile
            dt = 1.0

            # traverse the time profiles of the partition and simulate each time step
            nt = len(calculation_input.original_time_idx)
            for it, t in enumerate(calculation_input.original_time_idx):

                if t in time_indices_set:

                    # set the power values
                    # if the storage dispatch option is active, the batteries power is not included
                    # therefore, it shall be included after processing
                    V = calculation_input.Vbus[:, it]
                    I = calculation_input.Ibus[:, it]
                    S = calculation_input.Sbus[:, it]
                    Yload = calculation_input.YLoadBus[:, it]
                    branch_rates = calculation_input.Rates[:, it]

                    # add the controlled storage power if we are controlling the storage devices
                    if self.options.dispatch_storage:

                        if (it+1) < len(calculation_input.original_time_idx):
                            # compute the time delta: the time values come in nanoseconds
                            dt = (calculation_input.time_array[it + 1]
                                  - calculation_input.time_array[it]).value * 1e-9 / 3600.0

                        for k, battery in enumerate(batteries):

                            power = battery.get_processed_at(it, dt=dt, store_values=True)

                            bus_idx = batteries_bus_idx[k]

                            S[bus_idx] += power / calculation_input.Sbase

                    # run power flow at the circuit
                    res = single_island_pf(circuit=calculation_input,
                                           Vbus=V,
                                           Sbus=S,
                                           Ibus=I,
                                           Yloadbus=Yload,
                                           ma=calculation_input.branch_data.m[:, it],
                                           theta=calculation_input.branch_data.theta[:, it],
                                           Beq=calculation_input.branch_data.Beq[:, it],
                                           pq=calculation_input.pq_prof[it],
                                           pv=calculation_input.pv_prof[it],
                                           vd=calculation_input.vd_prof[it],
                                           pqpv=calculation_input.pqpv_prof[it],
                                           Qmin=calculation_input.Qmin_bus[:, it],
                                           Qmax=calculation_input.Qmax_bus[:, it],
                                           branch_rates=branch_rates,
                                           options=self.options,
                                           logger=self.logger)

                    # Recycle voltage solution
                    # last_voltage = res.voltage

                    # store circuit results at the time index 'it'
                    results.set_at(it, res)

                    progress = ((it + 1) / nt) * 100
                    self.progress_signal.emit(progress)
                    self.progress_text.emit('Simulating island ' + str(island_index)
                                            + ' at ' + str(self.grid.time_profile[t]))

                    if self.__cancel__:
                        # merge the circuit's results
                        time_series_results.apply_from_island(results,
                                                              bus_original_idx,
                                                              branch_original_idx,
                                                              calculation_input.original_time_idx,
                                                              'TS')
                        # abort by returning at this point
                        return time_series_results

            # merge the circuit's results
            time_series_results.apply_from_island(results,
                                                  bus_original_idx,
                                                  branch_original_idx,
                                                  calculation_input.original_time_idx,
                                                  'TS')

        # set the HVDC results here since the HVDC is not a branch in this modality
        time_series_results.hvdc_Pf = -time_circuit.hvdc_Pf.T
        time_series_results.hvdc_Pt = -time_circuit.hvdc_Pt.T
        # TODO: Fix HVDC for time series
        # time_series_results.hvdc_loading = time_circuit.hvdc_loading.T
        # time_series_results.hvdc_losses = time_circuit.hvdc_losses.T

        # set the inter-area variables
        time_series_results.F = time_circuit.F
        time_series_results.T = time_circuit.T
        time_series_results.hvdc_F = time_circuit.hvdc_data.get_bus_indices_f()
        time_series_results.hvdc_T = time_circuit.hvdc_data.get_bus_indices_t()
        time_series_results.bus_area_indices = time_circuit.bus_data.areas
        time_series_results.area_names = [a.name for a in self.grid.areas]

        return time_series_results

    def run_single_thread(self, time_indices) -> TimeSeriesResults:
        """
        Run single thread time series
        :param time_indices: array of time indices to consider
        :return: TimeSeriesResults instance
        """

        n = self.grid.get_bus_number(),
        m = self.grid.get_branch_number_wo_hvdc()

        # initialize the grid time series results we will append the island results with another function
        time_series_results = TimeSeriesResults(n=self.grid.get_bus_number(),
                                                m=self.grid.get_branch_number_wo_hvdc(),
                                                n_tr=self.grid.get_transformers2w_number(),
                                                n_hvdc=self.grid.get_hvdc_number(),
                                                bus_names=self.grid.get_bus_names(),
                                                branch_names=self.grid.get_branch_names_wo_hvdc(),
                                                transformer_names=self.grid.get_transformers2w_names(),
                                                hvdc_names=self.grid.get_hvdc_names(),
                                                bus_types=np.zeros(m),
                                                time_array=self.grid.time_profile[time_indices])

        # compile dictionaries once for speed
        bus_dict = {bus: i for i, bus in enumerate(self.grid.buses)}
        areas_dict = {elm: i for i, elm in enumerate(self.grid.areas)}
        self.progress_signal.emit(0.0)
        for it, t in enumerate(time_indices):

            self.progress_text.emit('Time series at ' + str(self.grid.time_profile[t]) + '...')

            progress = ((it + 1) / len(time_indices)) * 100
            self.progress_signal.emit(progress)

            pf_res = pf_worker.multi_island_pf(multi_circuit=self.grid,
                                               t=t,
                                               options=self.options,
                                               opf_results=self.opf_time_series_results,
                                               bus_dict=bus_dict,
                                               areas_dict=areas_dict)

            # gather results
            time_series_results.voltage[t, :] = pf_res.voltage
            time_series_results.S[t, :] = pf_res.Sbus
            time_series_results.Sf[t, :] = pf_res.Sf
            time_series_results.St[t, :] = pf_res.St
            time_series_results.Vbranch[t, :] = pf_res.Vbranch
            time_series_results.loading[t, :] = pf_res.loading
            time_series_results.losses[t, :] = pf_res.losses
            time_series_results.hvdc_losses[t, :] = pf_res.hvdc_losses
            time_series_results.hvdc_Pf[t, :] = pf_res.hvdc_Pf
            time_series_results.hvdc_Pt[t, :] = pf_res.hvdc_Pt
            time_series_results.hvdc_loading[t, :] = pf_res.hvdc_loading
            time_series_results.error_values[t] = pf_res.error
            time_series_results.converged_values[t] = pf_res.converged

            if self.__cancel__:
                return time_series_results

        return time_series_results

    def run_bentayga(self):

        res = bentayga_pf(self.grid, self.options, time_series=True)

        results = TimeSeriesResults(n=self.grid.get_bus_number(),
                                    m=self.grid.get_branch_number_wo_hvdc(),
                                    n_tr=self.grid.get_transformers2w_number(),
                                    n_hvdc=self.grid.get_hvdc_number(),
                                    bus_names=res.names,
                                    branch_names=res.names,
                                    transformer_names=[],
                                    hvdc_names=res.hvdc_names,
                                    bus_types=res.bus_types,
                                    time_array=self.grid.time_profile)

        results.voltage = res.V
        results.S = res.S
        results.Sf = res.Sf
        results.St = res.St
        results.loading = res.loading
        results.losses = res.losses
        results.Vbranch = res.Vbranch
        results.If = res.If
        results.It = res.It
        results.Beq = res.Beq
        results.m = res.tap_modules
        results.theta = res.tap_angles

        return results

    def run_newton_pa(self, time_indices=None):

        res = newton_pa_pf(self.grid, self.options, time_series=True, tidx=time_indices)

        results = TimeSeriesResults(n=self.grid.get_bus_number(),
                                    m=self.grid.get_branch_number_wo_hvdc(),
                                    n_tr=self.grid.get_transformers2w_number(),
                                    n_hvdc=self.grid.get_hvdc_number(),
                                    bus_names=res.bus_names,
                                    branch_names=res.branch_names,
                                    transformer_names=[],
                                    hvdc_names=res.hvdc_names,
                                    bus_types=res.bus_types,
                                    time_array=self.grid.time_profile[time_indices])

        results.voltage = res.voltage
        results.S = res.Scalc
        results.Sf = res.Sf
        results.St = res.St
        results.loading = res.Loading
        results.losses = res.Losses
        # results.Vbranch = res.Vbranch
        # results.If = res.If
        # results.It = res.It
        results.Beq = res.Beq
        results.ma = res.tap_module
        results.theta = res.tap_angle
        results.F = res.F
        results.T = res.T
        results.hvdc_F = res.hvdc_F
        results.hvdc_T = res.hvdc_T
        results.hvdc_Pf = res.hvdc_Pf
        results.hvdc_Pt = res.hvdc_Pt
        results.hvdc_loading = res.hvdc_loading
        results.hvdc_losses = res.hvdc_losses
        results.error_values = res.error

        return results

    def run(self):
        """
        Run the time series simulation
        @return:
        """

        a = time.time()

        if self.end_ is None:
            self.end_ = len(self.grid.time_profile)
        time_indices = np.arange(self.start_, self.end_)

        if self.engine == bs.EngineType.GridCal:
            self.results = self.run_single_thread(time_indices=time_indices)

        elif self.engine == bs.EngineType.Newton:
            pass

        elif self.engine == bs.EngineType.Bentayga:
            self.progress_text.emit('Running Bentayga... ')
            self.results = self.run_bentayga()

        elif self.engine == bs.EngineType.NewtonPA:
            self.progress_text.emit('Running Newton power analytics... ')
            self.results = self.run_newton_pa(time_indices=time_indices)

        else:
            raise Exception('Unknown engine :/')

        # fill F, T, Areas, etc...
        self.results.fill_circuit_info(self.grid)

        self.elapsed = time.time() - a
