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
            grid: MultiCircuit,
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
            time_indices: np.ndarray,
            clustering_results: Union["ClusteringResults", None] = None,
            engine: bs.EngineType = bs.EngineType.GridCal):
        """
        Time Series driver constructor
        :param grid: MultiCircuit instance
        :param time_indices: array of time indices to simulate
        :param clustering_results: ClusteringResults object (optional)
        """

        DriverTemplate.__init__(self, grid=grid, engine=engine)

        if clustering_results:
            self.time_indices = clustering_results.time_indices
            self.sampled_probabilities = clustering_results.sampled_probabilities

        else:
            self.time_indices = time_indices
            self.sampled_probabilities = np.ones(shape=len(self.time_indices)) / len(self.time_indices)

        self.topologic_groups: Dict[int, List[int]] = self.get_topologic_groups()

    def get_steps(self):
        """
        Get time steps list of strings
        """

        return [self.grid.time_profile[i].strftime('%d-%m-%Y %H:%M') for i in self.time_indices]

    def get_topologic_groups(self) -> Dict[int, List[int]]:
        return self.grid.get_topologic_group_dict()

    def set_topologic_groups(self):
        self.topologic_groups = self.get_topologic_groups()
