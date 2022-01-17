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
import multiprocessing
from sklearn.cluster import KMeans
from sklearn.cluster import SpectralClustering

from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCal.Engine.Core.time_series_pf_data import compile_time_circuit, BranchImpedanceMode
from GridCal.Engine.Simulations.PowerFlow.time_series_driver import TimeSeries
from GridCal.Engine.Simulations.driver_types import SimulationTypes
from GridCal.Engine.Simulations.Clustering.clustering import kmeans_approximate_sampling


class TimeSeriesClustering(TimeSeries):
    name = 'Time Series Clustering'
    tpe = SimulationTypes.ClusteringTimeSeries_run

    def __init__(self, grid: MultiCircuit, options: PowerFlowOptions, opf_time_series_results=None,
                 start_=0, end_=None, cluster_number=10):
        """
        TimeSeriesClustering constructor
        @param grid: MultiCircuit instance
        @param options: PowerFlowOptions instance
        """
        TimeSeries.__init__(self,  grid=grid, options=options, opf_time_series_results=opf_time_series_results,
                            start_=start_, end_=end_)

        self.cluster_number = cluster_number

        self.sampled_time_idx = list()
        self.sampled_probabilities = list()

    def get_steps(self):
        """
        Get time steps list of strings
        """
        return [l.strftime('%d-%m-%Y %H:%M') for l in pd.to_datetime(self.grid.time_profile[self.sampled_time_idx])]

    def run(self):
        """
        Run the time series simulation
        @return:
        """

        a = time.time()

        if self.end_ is None:
            self.end_ = len(self.grid.time_profile)
        time_indices = np.arange(self.start_, self.end_)

        # compile the multi-circuit
        time_circuit = compile_time_circuit(circuit=self.grid,
                                            apply_temperature=False,
                                            branch_tolerance_mode=BranchImpedanceMode.Specified,
                                            opf_results=self.opf_time_series_results)

        self.progress_text.emit('Clustering...')
        X = time_circuit.Sbus
        X = X[:, time_indices].real.T
        self.sampled_time_idx, self.sampled_probabilities = kmeans_approximate_sampling(X, n_points=self.cluster_number)

        self.results = self.run_single_thread(time_indices=self.sampled_time_idx)

        self.elapsed = time.time() - a
