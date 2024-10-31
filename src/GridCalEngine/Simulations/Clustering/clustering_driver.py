# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
from typing import Union
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.enumerations import SimulationTypes
from GridCalEngine.Simulations.driver_template import DriverTemplate
from GridCalEngine.Simulations.Clustering.clustering_results import ClusteringResults
from GridCalEngine.Simulations.Clustering.clustering_options import ClusteringAnalysisOptions
from GridCalEngine.Simulations.Clustering.clustering import kmeans_sampling


class ClusteringDriver(DriverTemplate):
    name = 'Clustering analysis'
    tpe = SimulationTypes.ClusteringAnalysis_run

    def __init__(self, grid: MultiCircuit, options: ClusteringAnalysisOptions):
        """
        Clustering analysis driver constructor
        :param grid: Multicircuit instance
        :param options: ClusteringAnalysisOptions
        """
        DriverTemplate.__init__(self, grid=grid)

        self.options: ClusteringAnalysisOptions = options

        self.results: ClusteringResults = ClusteringResults(time_indices=np.empty(0, dtype=int),
                                                            sampled_probabilities=np.empty(0),
                                                            time_array=np.empty(0),
                                                            original_sample_idx=np.empty(0, dtype=int))

    def run(self):
        """
        Run thread
        """
        self.tic()
        self.report_text("Clustering")
        self.report_progress(0.0)

        time_indices, sampled_probabilities, sample_idx = kmeans_sampling(x_input=self.grid.get_Pbus_prof(),
                                                                          n_points=self.options.n_points)
        self.results = ClusteringResults(
            time_indices=time_indices,
            sampled_probabilities=sampled_probabilities,
            time_array=self.grid.time_profile,
            original_sample_idx=sample_idx
        )

        self.toc()

    def get_steps(self):
        """
        Get variations list of strings
        """
        if self.results is not None:
            return [self.grid.time_profile[i].strftime('%d-%m-%Y %H:%M') for i in self.results.time_indices]
        else:
            return list()
