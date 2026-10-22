# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
from typing import Union
from VeraGridEngine.Simulations.PowerFlow.power_flow_ts_results import PowerFlowTimeSeriesResults
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from VeraGridEngine.Simulations.driver_template import TimeSeriesDriverTemplate
from VeraGridEngine.Simulations.Clustering.clustering_results import ClusteringResults
from VeraGridEngine.Simulations.NTC.ntc_ts_driver import NtcOperatingPoints
from VeraGridEngine.Simulations.OPF.opf_results import OptimalPowerFlowResults
from VeraGridEngine.Simulations.OPF.opf_ts_results import OptimalPowerFlowTimeSeriesResults
import VeraGridEngine.Simulations.PowerFlow.power_flow_worker as pf_worker
from VeraGridEngine.Compilers.circuit_to_pgm import pgm_pf
from VeraGridEngine.Compilers.Gslv.activation import GSLV_AVAILABLE, GSLV_UNAVAILABLE_REASON
from VeraGridEngine.Compilers.Gslv.Simulations.power_flow import gslv_pf, translate_gslv_pf_time_series_results
from VeraGridEngine.basic_structures import IntVec
from VeraGridEngine.enumerations import EngineType, SimulationTypes


class PowerFlowTimeSeriesDriver(TimeSeriesDriverTemplate):
    __slots__ = (
        "options",
        "opf_time_series_results",
        "ntc_operating_points",
    )

    tpe = SimulationTypes.PowerFlowTimeSeries_run
    name = tpe.value

    def __init__(self,
                 grid: MultiCircuit,
                 options: Union[PowerFlowOptions, None] = None,
                 time_indices: Union[IntVec, None] = None,
                 opf_time_series_results=None,
                 clustering_results: Union[ClusteringResults, None] = None,
                 engine: EngineType = EngineType.VeraGrid,
                 ntc_operating_points: NtcOperatingPoints | None = None):
        """
        PowerFlowTimeSeries constructor
        :param grid: MultiCircuit instance
        :param options: PowerFlowOptions instance
        :param time_indices: array of time indices to simulate
        :param opf_time_series_results: ClusteringResults instance (optional)
        :param clustering_results: ClusteringResults instance (optional)
        :param engine: Calculation engine to use
        :param ntc_operating_points: NTC time series operating points to reproduce
        """
        TimeSeriesDriverTemplate.__init__(
            self,
            grid=grid,
            time_indices=grid.get_all_time_indices() if time_indices is None else time_indices,
            clustering_results=clustering_results,
            engine=engine
        )

        self.options = PowerFlowOptions() if options is None else options

        self.opf_time_series_results = opf_time_series_results
        self.ntc_operating_points: NtcOperatingPoints | None = ntc_operating_points

        n = grid.get_bus_number()

        self.results = PowerFlowTimeSeriesResults(
            n=n,
            m=grid.get_branch_number(add_hvdc=False, add_vsc=False, add_switch=True),
            n_hvdc=grid.get_hvdc_number(),
            n_vsc=grid.get_vsc_number(),
            bus_names=grid.get_bus_names(),
            branch_names=grid.get_branch_names(add_hvdc=False, add_vsc=False, add_switch=True),
            hvdc_names=grid.get_hvdc_names(),
            vsc_names=grid.get_vsc_names(),
            time_array=self.grid.get_time_array()[self.time_indices],
            bus_types=np.ones(n, dtype=int),
            n_gen=grid.get_generators_number(),
            n_batt=grid.get_batteries_number(),
            n_sh=grid.get_shunt_like_device_number(),
            gen_names=grid.get_generator_names(),
            batt_names=grid.get_battery_names(),
            sh_names=grid.get_shunt_like_devices_names(),
            area_names=grid.get_area_names(),
            clustering_results=None
        )

    def run_single_thread(self, time_indices) -> PowerFlowTimeSeriesResults:
        """
        Run single thread time series
        :param time_indices: array of time indices to consider
        :return: TimeSeriesResults instance
        """

        n = self.grid.get_bus_number()
        # m = self.grid.get_branch_number(add_hvdc=False, add_vsc=False, add_switch=True)
        m = self.grid.get_branch_number(add_vsc=False,
                                        add_hvdc=False,
                                        add_switch=True)

        # initialize the grid time series results we will append the island results with another function
        time_series_results = PowerFlowTimeSeriesResults(
            n=n,
            m=m,
            n_hvdc=self.grid.get_hvdc_number(),
            n_vsc=self.grid.get_vsc_number(),
            bus_names=self.grid.get_bus_names(),
            branch_names=self.grid.get_branch_names(add_vsc=False, add_hvdc=False, add_switch=True),
            hvdc_names=self.grid.get_hvdc_names(),
            vsc_names=self.grid.get_vsc_names(),
            bus_types=np.ones(n, dtype=int),
            time_array=self.grid.time_profile[time_indices],
            n_gen=self.grid.get_generators_number(),
            n_batt=self.grid.get_batteries_number(),
            n_sh=self.grid.get_shunt_like_device_number(),
            gen_names=self.grid.get_generator_names(),
            batt_names=self.grid.get_battery_names(),
            sh_names=self.grid.get_shunt_like_devices_names(),
            area_names=self.grid.get_area_names(),
            clustering_results=self.clustering_results
        )

        # compile dictionaries once for speed
        bus_dict = {bus: i for i, bus in enumerate(self.grid.buses)}
        areas_dict = {elm: i for i, elm in enumerate(self.grid.areas)}
        self.report_progress(0.0)
        for it, t in enumerate(time_indices):

            self.report_text('Time series at ' + str(self.grid.time_profile[t]) + '...')
            self.report_progress2(it, len(time_indices))

            # the NTC operating point of this step, if any, or else the OPF results
            opf_results: OptimalPowerFlowResults | OptimalPowerFlowTimeSeriesResults | None
            if self.ntc_operating_points is not None:
                opf_results = self.ntc_operating_points.get_at(int(t))
            else:
                opf_results = self.opf_time_series_results

            # run power flow
            pf_res = pf_worker.multi_island_pf(multi_circuit=self.grid,
                                               t=t,
                                               options=self.options,
                                               opf_results=opf_results,
                                               bus_dict=bus_dict,
                                               areas_dict=areas_dict)

            # Copy the complete snapshot payload so every time-series result table stays in sync.
            time_series_results.set_at(it, pf_res)

            if self.is_cancel():
                return time_series_results

        return time_series_results

    def run_gslv(self, time_indices=None) -> PowerFlowTimeSeriesResults:
        """
        Run with GSLV
        :param time_indices: array of time indices
        :return:
        """
        res = gslv_pf(circuit=self.grid,
                      pf_opt=self.options,
                      time_series=True,
                      time_indices=time_indices,
                      opf_results=self.opf_time_series_results,
                      logger=self.logger)
        return translate_gslv_pf_time_series_results(
            grid=self.grid,
            res=res,
            options=self.options,
            time_indices=time_indices,
            clustering_results=self.clustering_results,
        )

    def run(self):
        """
        Run the time series simulation
        @return:
        """

        self.tic()
        self.report_text("Compiling and configuring...")

        if self.engine == EngineType.GSLV and not GSLV_AVAILABLE:
            self.engine = EngineType.VeraGrid
            self.logger.add_warning(f'GSLV unavailable: {GSLV_UNAVAILABLE_REASON}; falling back to VeraGrid')

        if self.engine == EngineType.VeraGrid:
            self.results = self.run_single_thread(time_indices=self.time_indices)

        elif self.engine == EngineType.GSLV:
            self.report_text('Running GSLV... ')
            self.results = self.run_gslv(time_indices=self.time_indices)

        elif self.engine == EngineType.PGM:
            self.report_text('Running Power Grid Model... ')
            self.results = pgm_pf(self.grid, self.options, logger=self.logger, time_series=True)
            self.results.area_names = np.array([a.name for a in self.grid.areas], dtype=str)

        else:
            raise Exception('Engine not implemented for Time Series:' + self.engine.value)

        # fill F, T, Areas, etc...
        self.results.fill_circuit_info(self.grid)

        self.toc()
