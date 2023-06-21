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


import time
from typing import Dict, Union, List
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Simulations.LinearFactors.linear_analysis import LinearAnalysis
from GridCal.Engine.Simulations.LinearFactors.linear_analysis_driver import LinearAnalysisOptions
from GridCal.Engine.Core.numerical_circuit import compile_numerical_circuit_at
from GridCal.Engine.Simulations.driver_types import SimulationTypes
from GridCal.Engine.Simulations.driver_template import TimeSeriesDriverTemplate
from GridCal.Engine.Simulations.LinearFactors.linear_analysis_ts_results import LinearAnalysisTimeSeriesResults
from GridCal.Engine.Simulations.Clustering.clustering_results import ClusteringResults


class LinearAnalysisTimeSeriesDriver(TimeSeriesDriverTemplate):
    name = 'Time Series Linear Analysis '
    tpe = SimulationTypes.LinearAnalysis_TS_run

    def __init__(
            self,
            grid: MultiCircuit,
            options: LinearAnalysisOptions,
            clustering_results: Union[ClusteringResults, None] = None,
    ):
        """
        TimeSeries Analysis constructor
        :param grid: MultiCircuit instance
        :param options: LinearAnalysisOptions instance
        :param clustering_results: ClusteringResults instance
        """

        TimeSeriesDriverTemplate.__init__(
            self,
            grid=grid,
            clustering_results=clustering_results,
        )

        self.options: LinearAnalysisOptions = options

        self.drivers: Dict[int, LinearAnalysis] = dict()
        self.results: Dict[int, LinearAnalysisTimeSeriesResults] = dict()

    def get_steps(self) -> List:
        """
        Get time steps list of strings
        :return:
        """

        return [self.grid.time_profile[l].strftime('%d-%m-%Y %H:%M') for l in self.time_indices]

    def run(self):
        """
        Run the time series simulation
        :return:
        """

        tm_ = time.time()

        self.progress_text.emit('Computing TS linear analysis...')

        self.__cancel__ = False

        self.results = LinearAnalysisTimeSeriesResults(
            n=self.grid.get_bus_number(),
            m=self.grid.get_branch_number_wo_hvdc(),
            time_array=self.grid.time_profile[self.time_indices],
            bus_names=self.grid.get_bus_names(),
            bus_types=self.grid.get_bus_default_types(),
            branch_names=self.grid.get_branches_wo_hvdc_names(),
        )

        # Compute bus injections
        self.results.S = self.grid.get_Sbus()

        # Compute different topologies to consider
        tpg = self.get_topologic_groups()

        for it, t in enumerate(tpg.keys()):

            self.progress_text.emit('Processing topology group ' + str(self.grid.time_profile[t]))
            self.progress_signal.emit((it + 1) / len(tpg.keys()) * 100)

            # time indices with same topology
            time_indices_ = tpg[t]

            nc = compile_numerical_circuit_at(
                circuit=self.grid,
                t_idx=t,
            )

            driver_ = LinearAnalysis(
                numerical_circuit=nc,
                distributed_slack=True,
                correct_values=False,
            )

            driver_.run()

            Sf = driver_.get_flows(Sbus=self.results.S[time_indices_, :])

            self.results.Sf[time_indices_, :] = Sf

        rates = self.grid.get_branch_rates_wo_hvdc()
        self.results.loading = self.results.Sf / (rates + 1e-9)

        self.elapsed = time.time() - tm_

