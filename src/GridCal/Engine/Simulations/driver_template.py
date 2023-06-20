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

import numpy as np
from typing import List, Dict, Union
from GridCal.Engine.Simulations.driver_types import SimulationTypes
from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.Core.multi_circuit import MultiCircuit
import GridCal.Engine.basic_structures as bs
from GridCal.Engine.Simulations.Clustering.clustering import kmeans_sampling

class DummySignal:

    def __init__(self, tpe=str):
        self.tpe = tpe

    def emit(self, val=''):
        pass

    def connect(self, val):
        pass


class DriverTemplate:

    tpe = SimulationTypes.TemplateDriver
    name = 'Template'

    def __init__(
            self,
            grid: MultiCircuit,  #todo: ver si podemos quitarlo para que heredemos en los drivers de numerical circuit
            engine: bs.EngineType = bs.EngineType.GridCal
    ):
        """

        :param grid: Multicircuit instance
        :param engine: EngineType
        """
        self.progress_signal = DummySignal()
        self.progress_text = DummySignal(str)
        self.done_signal = DummySignal()

        self.grid = grid

        self.results = None

        self.engine = engine

        self.elapsed = 0

        self.logger = Logger()

        self.__cancel__ = False

    def get_steps(self):
        return list()

    def run(self):
        pass

    def cancel(self):
        """
        Cancel the simulation
        """
        self.__cancel__ = True
        self.progress_signal.emit(0)
        self.progress_text.emit('Cancelled!')
        self.done_signal.emit()


class TimeSeriesDriverTemplate(DriverTemplate):

    def __init__(
            self,
            grid: MultiCircuit,
            start_: int = 0,
            end_: Union[int, None] = None,
            use_clustering: bool = False,
    ):
        """

        :param grid: Multicircuit instance
        :param start_: Integer. First time index to consider
        :param end_: Integer. Last time index to consider. None for the last one.
        :param use_clustering: Boolean. True to cluster time indices
        """

        DriverTemplate.__init__(self, grid=grid)

        self.start_ = start_

        self.indices = self.grid.time_profile

        self.use_clustering: bool = use_clustering

        if end_ is not None:
            self.end_ = end_
        else:
            self.end_ = len(self.grid.time_profile)

        self.time_indices = self.get_time_indices()
        self.sampled_probabilities = np.ones(shape=len(self.time_indices)) / len(self.time_indices)

        self.topologic_groups: Dict[int, List[int]] = self.get_topologic_groups()

    def get_time_indices(self) -> np.ndarray:
        """
        Get an array of indices of the time steps selected within the start-end interval
        :return: np.array[int]
        """
        if self.end_ is None:
            self.end_ = len(self.grid.time_profile)

        return np.arange(self.start_, self.end_ + 1)

    def get_topologic_groups(self) -> Dict[int, List[int]]:
        return self.grid.get_topologic_group_dict()

    def set_topologic_groups(self):
        self.topologic_groups = self.get_topologic_groups()

    def apply_cluster_indices(self, X, n_points=10):
        """
        Function to set indices and probabilities with k-means clustering method
        :param X: matrix to evaluate (time, params)
        :param n_points: number of clusters
        :return: nothing, just reassign time_indices and sampled probabilities params
        """
        if self.use_clustering:

            self.progress_text.emit('Clustering...')

            # cluster and re-assign the time indices
            self.time_indices, self.sampled_probabilities = kmeans_sampling(
                X=X[:, self.time_indices].real.T,
                n_points=n_points
            )
