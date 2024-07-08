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

import time
from typing import Dict, Union
from GridCalEngine.basic_structures import IntVec
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Simulations.LinearFactors.linear_analysis import LinearAnalysis
from GridCalEngine.Simulations.LinearFactors.linear_analysis_options import LinearAnalysisOptions
from GridCalEngine.DataStructures.numerical_circuit import compile_numerical_circuit_at
from GridCalEngine.enumerations import SimulationTypes
from GridCalEngine.Simulations.driver_template import TimeSeriesDriverTemplate
from GridCalEngine.Simulations.LinearFactors.linear_analysis_ts_results import LinearAnalysisTimeSeriesResults
from GridCalEngine.Simulations.Clustering.clustering_results import ClusteringResults


class LinearAnalysisTimeSeriesDriver(TimeSeriesDriverTemplate):
    name = 'Linear Analysis Time Series'
    tpe = SimulationTypes.LinearAnalysis_TS_run

    def __init__(self,
                 grid: MultiCircuit,
                 options: Union[LinearAnalysisOptions, None] = None,
                 time_indices: Union[IntVec, None] = None,
                 clustering_results: Union[ClusteringResults, None] = None,
                 opf_time_series_results=None):
        """
        TimeSeries Analysis constructor
        :param grid: MultiCircuit instance
        :param options: LinearAnalysisOptions instance (optional)
        :param time_indices: array of time indices to simulate (optional)
        :param clustering_results: ClusteringResults instance (optional)
        """
        TimeSeriesDriverTemplate.__init__(
            self,
            grid=grid,
            time_indices=grid.get_all_time_indices() if time_indices is None else time_indices,
            clustering_results=clustering_results,
        )

        self.options: LinearAnalysisOptions = LinearAnalysisOptions() if options is None else options

        self.opf_time_series_results = opf_time_series_results

        self.drivers: Dict[int, LinearAnalysis] = dict()

        self.results = LinearAnalysisTimeSeriesResults(
            n=self.grid.get_bus_number(),
            m=self.grid.get_branch_number_wo_hvdc(),
            time_array=self.grid.time_profile[self.time_indices],
            bus_names=self.grid.get_bus_names(),
            bus_types=self.grid.get_bus_default_types(),
            branch_names=self.grid.get_branches_wo_hvdc_names(),
            clustering_results=self.clustering_results,
        )

    def run(self):
        """
        Run the time series simulation
        :return:
        """

        self.tic()

        self.report_text('Computing TS linear analysis...')

        self.__cancel__ = False

        # Compute bus Injections
        # Pbus = self.grid.get_Pbus_prof()

        # Compute different topologies to consider
        # tpg = self.get_topologic_groups()

        for it, t in enumerate(self.time_indices):
            self.report_text('Contingency at ' + str(self.grid.time_profile[t]))
            self.report_progress2(it, len(self.time_indices))

            nc = compile_numerical_circuit_at(circuit=self.grid,
                                              t_idx=t,
                                              opf_results=self.opf_time_series_results,
                                              logger=self.logger)

            driver_ = LinearAnalysis(
                numerical_circuit=nc,
                distributed_slack=True,
                correct_values=False,
            )

            driver_.run()

            # Sf = driver_.get_flows(Sbus=Pbus[time_indices_, :])

            self.results.S[it, :] = nc.Sbus
            self.results.Sf[it, :] = driver_.get_flows(Sbus=nc.Sbus)

        rates = self.grid.get_branch_rates_wo_hvdc()
        self.results.loading = self.results.Sf / (rates + 1e-9)
        # self.results.S = Pbus[self.time_indices, :]

        self.toc()
