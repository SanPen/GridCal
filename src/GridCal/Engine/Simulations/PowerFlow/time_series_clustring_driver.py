# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.

import json
import pandas as pd
import numpy as np
import time
import multiprocessing
from sklearn.cluster import KMeans
from PySide2.QtCore import QThread, QThreadPool, Signal

from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from GridCal.Engine.Simulations.result_types import ResultTypes
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCal.Engine.Simulations.PowerFlow.power_flow_worker import single_island_pf, power_flow_worker_args
from GridCal.Engine.Core.time_series_pf_data import compile_time_circuit, BranchImpedanceMode
from GridCal.Engine.Simulations.PowerFlow.time_series_driver import TimeSeries
from GridCal.Engine.Simulations.results_model import ResultsModel


def kmeans_approximate_sampling(X, n_points=10):
    """
    K-Means clustering, corrected to the closest points
    :param X: injections matrix (time, bus)
    :param n_points: number of clusters
    :return: indices of the closest to the cluster centers, deviation of the closest representatives
    """

    # declare the model
    model = KMeans(n_clusters=n_points)

    # model fitting
    model.fit(X)

    centers = model.cluster_centers_
    labels = model.labels_

    # get the closest indices to the cluster centers
    closest_idx = np.zeros(n_points, dtype=int)
    closest_prob = np.zeros(n_points, dtype=float)
    nt = X.shape[0]

    unique_labels, counts = np.unique(labels, return_counts=True)
    probabilities = counts.astype(float) / float(nt)

    prob_dict = {u: p for u, p in zip(unique_labels, probabilities)}
    for i in range(n_points):
        deviations = np.sum(np.power(X - centers[i, :], 2.0), axis=1)
        idx = deviations.argmin()
        closest_idx[i] = idx

    # sort the indices
    closest_idx = np.sort(closest_idx)

    # compute the probabilities of each index (sorted already)
    for i, idx in enumerate(closest_idx):
        lbl = model.predict(X[idx, :].reshape(1, -1))[0]
        prob = prob_dict[lbl]
        closest_prob[i] = prob

    return closest_idx, closest_prob


class TimeSeriesClustering(TimeSeries):
    name = 'Time Series Clustering'

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

        # send the finnish signal
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Done!')
        self.done_signal.emit()

