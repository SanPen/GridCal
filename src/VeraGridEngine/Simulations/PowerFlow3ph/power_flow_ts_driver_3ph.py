# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Union

import numpy as np

from VeraGridEngine.Compilers.Gslv.activation import GSLV_AVAILABLE, GSLV_UNAVAILABLE_REASON
from VeraGridEngine.Compilers.Gslv.Simulations.power_flow_3ph import (
    gslv_pf_3ph,
    translate_gslv_pf_3ph_results,
)
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Simulations.Clustering.clustering_results import ClusteringResults
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow3ph.power_flow_ts_results_3ph import PowerFlowTimeSeriesResults3Ph
from VeraGridEngine.Simulations.PowerFlow3ph.power_flow_worker_3ph import multi_island_pf_3ph
from VeraGridEngine.Simulations.driver_template import TimeSeriesDriverTemplate
from VeraGridEngine.basic_structures import IntVec
from VeraGridEngine.enumerations import EngineType, SimulationTypes

if TYPE_CHECKING:
    from VeraGridEngine.Simulations.OPF.opf_ts_results import OptimalPowerFlowTimeSeriesResults


class PowerFlowTimeSeriesDriver3Ph(TimeSeriesDriverTemplate):
    """
    Three-phase power-flow time-series driver.
    """

    __slots__ = (
        "options",
        "opf_time_series_results",
    )

    tpe = SimulationTypes.PowerFlowTimeSeries3ph_run
    name = tpe.value

    def __init__(
        self,
        grid: MultiCircuit,
        options: Union[PowerFlowOptions, None] = None,
        time_indices: Union[IntVec, None] = None,
        opf_time_series_results: Union[OptimalPowerFlowTimeSeriesResults, None] = None,
        clustering_results: Union[ClusteringResults, None] = None,
        engine: EngineType = EngineType.VeraGrid,
    ) -> None:
        """
        Build one three-phase power-flow time-series driver.

        :param grid: Circuit under study.
        :param options: Power-flow options.
        :param time_indices: Selected time steps.
        :param opf_time_series_results: Optional OPF guidance results.
        :param clustering_results: Optional clustering metadata.
        :param engine: Requested engine.
        :return: None.
        """
        TimeSeriesDriverTemplate.__init__(
            self,
            grid=grid,
            time_indices=grid.get_all_time_indices() if time_indices is None else time_indices,
            clustering_results=clustering_results,
            engine=engine,
        )

        self.options: PowerFlowOptions = PowerFlowOptions() if options is None else options
        self.opf_time_series_results: OptimalPowerFlowTimeSeriesResults | None = opf_time_series_results

        bus_names: np.ndarray = self.grid.get_bus_names()
        branch_names: np.ndarray = self.grid.get_branch_names(add_hvdc=False, add_vsc=False, add_switch=True)

        self.results: PowerFlowTimeSeriesResults3Ph = PowerFlowTimeSeriesResults3Ph(
            n=3 * len(bus_names),
            m=3 * len(branch_names),
            n_hvdc=self.grid.get_hvdc_number(),
            n_vsc=self.grid.get_vsc_number(),
            n_gen=self.grid.get_generation_like_number(),
            n_batt=self.grid.get_batteries_number(),
            n_sh=self.grid.get_shunt_like_device_number(),
            n_load=self.grid.get_load_like_device_number(),
            bus_names=bus_names,
            branch_names=branch_names,
            hvdc_names=self.grid.get_hvdc_names(),
            vsc_names=self.grid.get_vsc_names(),
            gen_names=self.grid.get_generation_like_names(),
            batt_names=self.grid.get_battery_names(),
            sh_names=self.grid.get_shunt_like_devices_names(),
            load_names=self.grid.get_load_like_devices_names(),
            bus_types=np.ones(len(bus_names), dtype=int),
            time_array=self.grid.get_time_array()[self.time_indices],
            clustering_results=self.clustering_results,
        )

    def run_single_thread(self, time_indices: IntVec) -> PowerFlowTimeSeriesResults3Ph:
        """
        Run the three-phase time series with the internal engine.

        :param time_indices: Selected time indices.
        :return: Time-series results.
        """
        bus_names: np.ndarray = self.grid.get_bus_names()
        branch_names: np.ndarray = self.grid.get_branch_names(add_hvdc=False, add_vsc=False, add_switch=True)

        results: PowerFlowTimeSeriesResults3Ph = PowerFlowTimeSeriesResults3Ph(
            n=3 * len(bus_names),
            m=3 * len(branch_names),
            n_hvdc=self.grid.get_hvdc_number(),
            n_vsc=self.grid.get_vsc_number(),
            n_gen=self.grid.get_generation_like_number(),
            n_batt=self.grid.get_batteries_number(),
            n_sh=self.grid.get_shunt_like_device_number(),
            n_load=self.grid.get_load_like_device_number(),
            bus_names=bus_names,
            branch_names=branch_names,
            hvdc_names=self.grid.get_hvdc_names(),
            vsc_names=self.grid.get_vsc_names(),
            gen_names=self.grid.get_generation_like_names(),
            batt_names=self.grid.get_battery_names(),
            sh_names=self.grid.get_shunt_like_devices_names(),
            load_names=self.grid.get_load_like_devices_names(),
            bus_types=np.ones(len(bus_names), dtype=int),
            time_array=self.grid.time_profile[time_indices],
            clustering_results=self.clustering_results,
        )

        # The internal solver already accepts reusable index lookups, so they are
        # built once here to avoid repeating the same mapping work on every step.
        bus_dict: Dict = {bus: i for i, bus in enumerate(self.grid.buses)}
        areas_dict: Dict = {area: i for i, area in enumerate(self.grid.areas)}
        self.report_progress(0.0)

        it: int
        t_idx: int
        for it, t_idx in enumerate(time_indices):
            # Each step must rebuild the network state at the selected profile index.
            self.report_text("Time series 3ph at " + str(self.grid.time_profile[t_idx]) + "...")
            self.report_progress2(it, len(time_indices))

            snapshot_results = multi_island_pf_3ph(
                multi_circuit=self.grid,
                t=t_idx,
                options=self.options,
                opf_results=self.opf_time_series_results,
                logger=self.logger,
                bus_dict=bus_dict,
                areas_dict=areas_dict,
            )

            results.set_at(it, snapshot_results)

            if self.is_cancel():
                return results
            else:
                pass

        return results

    def run_gslv(self, time_indices: IntVec) -> PowerFlowTimeSeriesResults3Ph:
        """
        Run the three-phase time series with one native GSLV snapshot per time step.

        :param time_indices: Selected time indices.
        :return: Time-series results.
        """
        bus_names: np.ndarray = self.grid.get_bus_names()
        branch_names: np.ndarray = self.grid.get_branch_names(add_hvdc=False, add_vsc=False, add_switch=True)
        results: PowerFlowTimeSeriesResults3Ph = PowerFlowTimeSeriesResults3Ph(
            n=3 * len(bus_names),
            m=3 * len(branch_names),
            n_hvdc=self.grid.get_hvdc_number(),
            n_vsc=self.grid.get_vsc_number(),
            n_gen=self.grid.get_generation_like_number(),
            n_batt=self.grid.get_batteries_number(),
            n_sh=self.grid.get_shunt_like_device_number(),
            n_load=self.grid.get_load_like_device_number(),
            bus_names=bus_names,
            branch_names=branch_names,
            hvdc_names=self.grid.get_hvdc_names(),
            vsc_names=self.grid.get_vsc_names(),
            gen_names=self.grid.get_generation_like_names(),
            batt_names=self.grid.get_battery_names(),
            sh_names=self.grid.get_shunt_like_devices_names(),
            load_names=self.grid.get_load_like_devices_names(),
            bus_types=np.ones(len(bus_names), dtype=int),
            time_array=self.grid.time_profile[time_indices],
            clustering_results=self.clustering_results,
        )

        it: int
        t_idx: int
        for it, t_idx in enumerate(time_indices):
            # The GSLV wrapper exposes a snapshot three-phase API, so the time-series
            # driver dispatches one explicit snapshot per requested time index.
            self.report_text("Time series 3ph at " + str(self.grid.time_profile[t_idx]) + "...")
            self.report_progress2(it, len(time_indices))

            gslv_snapshot = gslv_pf_3ph(
                circuit=self.grid,
                pf_opt=self.options,
                t_idx=int(t_idx),
                logger=self.logger,
            )
            snapshot_results = translate_gslv_pf_3ph_results(self.grid, gslv_snapshot)
            results.set_at(it, snapshot_results)

            if self.is_cancel():
                return results
            else:
                pass

        return results

    def run(self) -> None:
        """
        Run the selected three-phase time-series simulation.

        :return: None.
        """
        self.tic()
        self.report_text("Compiling and configuring...")

        # The driver can only keep the GSLV engine when the wrapper is available.
        if self.engine == EngineType.GSLV and not GSLV_AVAILABLE:
            self.engine = EngineType.VeraGrid
            self.logger.add_warning(f'GSLV unavailable: {GSLV_UNAVAILABLE_REASON}; falling back to VeraGrid')
        else:
            pass

        if self.engine == EngineType.VeraGrid:
            self.results = self.run_single_thread(time_indices=self.time_indices)
        elif self.engine == EngineType.GSLV:
            self.results = self.run_gslv(time_indices=self.time_indices)
        else:
            raise Exception("Engine " + self.engine.value + " not implemented for " + self.name)

        self.results.fill_circuit_info(self.grid)
        self.toc()
