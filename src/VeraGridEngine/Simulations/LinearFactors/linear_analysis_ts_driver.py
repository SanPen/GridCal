# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from typing import Dict, Union, TYPE_CHECKING
from VeraGridEngine.basic_structures import IntVec
from VeraGridEngine.Simulations.LinearFactors.linear_analysis import LinearAnalysis
from VeraGridEngine.Simulations.LinearFactors.linear_analysis_options import LinearAnalysisOptions
from VeraGridEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
from VeraGridEngine.enumerations import SimulationTypes
from VeraGridEngine.Simulations.driver_template import TimeSeriesDriverTemplate
from VeraGridEngine.Simulations.LinearFactors.linear_analysis_ts_results import LinearAnalysisTimeSeriesResults
from VeraGridEngine.Simulations.Clustering.clustering_results import ClusteringResults
from VeraGridEngine.DataStructures.numerical_circuit import NumericalCircuit

if TYPE_CHECKING:
    from VeraGridEngine.Devices.multi_circuit import MultiCircuit


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
            m=self.grid.get_branch_number(add_hvdc=False, add_vsc=False, add_switch=True),
            time_array=self.grid.time_profile[self.time_indices],
            bus_names=self.grid.get_bus_names(),
            bus_types=self.grid.get_bus_default_types(),
            branch_names=self.grid.get_branch_names(add_hvdc=False, add_vsc=False, add_switch=True),
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
            self.report_text('Linear analysis at ' + str(self.grid.time_profile[t]))
            self.report_progress2(it, len(self.time_indices))

            nc: NumericalCircuit = compile_numerical_circuit_at(circuit=self.grid,
                                                                t_idx=t,
                                                                opf_results=self.opf_time_series_results,
                                                                logger=self.logger)

            driver_ = LinearAnalysis(
                nc=nc,
                distributed_slack=True,
                correct_values=False,
            )

            Sbus = nc.get_power_injections_pu()
            self.results.S[it, :] = Sbus * nc.Sbase
            self.results.Sf[it, :] = driver_.get_flows(Sbus=Sbus) * nc.Sbase

        rates = self.grid.get_branch_rates()
        self.results.loading = self.results.Sf.real / (rates + 1e-9)

        self.toc()
