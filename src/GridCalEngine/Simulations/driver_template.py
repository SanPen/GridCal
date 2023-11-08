# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
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
import numpy as np
from typing import List, Dict, Union
from GridCalEngine.basic_structures import IntVec, Vec
from GridCalEngine.Simulations.driver_types import SimulationTypes
from GridCalEngine.basic_structures import Logger
from GridCalEngine.Core.Devices.multi_circuit import MultiCircuit
import GridCalEngine.basic_structures as bs
import GridCalEngine.Core.topology as tp


class DummySignal:
    """
    Qt signal placeholder to not to import QT in the engine
    """

    def __init__(self, tpe: type = str) -> None:
        self.tpe = tpe

    def emit(self, val: str = '') -> None:
        pass

    def connect(self, val):
        """

        :param val:
        """
        pass


class DriverTemplate:
    """
    Base driver template
    """
    tpe = SimulationTypes.TemplateDriver
    name = 'Template'

    def __init__(self,
                 grid: MultiCircuit,
                 engine: bs.EngineType = bs.EngineType.GridCal):
        """
        Constructor
        :param grid: MultiCircuit instance
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

        self.__start = time.time()

    def tic(self, skip_logger=False):
        """
        Register start of time
        """
        self.__start = time.time()

        if not skip_logger:
            self.logger.add_info(msg="Elapsed total (s)",
                                 device="Started")

    def toc(self, skip_logger=False):
        """
        Register end of time
        :param skip_logger: skip logging this?
        """
        self.elapsed = time.time() - self.__start

        if not skip_logger:
            self.logger.add_info(msg="Elapsed total (s)",
                                 device="Ended",
                                 value=self.elapsed)

    def get_steps(self):
        """
        Get the number of steps in the simulation
        :return:
        """
        return list()

    def run(self):
        """

        """
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
    """
    Time series driver template
    """

    def __init__(
            self,
            grid: MultiCircuit,
            time_indices: IntVec,
            clustering_results: Union["ClusteringResults", None] = None,
            engine: bs.EngineType = bs.EngineType.GridCal,
            check_time_series: bool = True):
        """
        Time Series driver constructor
        :param grid: MultiCircuit instance
        :param time_indices: array of time indices to simulate
        :param clustering_results: ClusteringResults object (optional)
        """
        if not grid.has_time_series and check_time_series:
            raise Exception(self.name + " can only run in grids with time series data :(")

        DriverTemplate.__init__(self, grid=grid, engine=engine)

        self.clustering_results = clustering_results

        if clustering_results:
            self.using_clusters = True
            self.time_indices: IntVec = clustering_results.time_indices
            self.sampled_probabilities: Vec = clustering_results.sampled_probabilities
            self.original_sample_idx: IntVec = clustering_results.original_sample_idx

            self.topologic_groups: Dict[int, List[int]] = self.get_topologic_groups()

        else:
            self.using_clusters = False
            self.original_sample_idx = None
            if time_indices is None:
                self.time_indices = None
                self.sampled_probabilities = None
            else:
                if len(time_indices) == 0:
                    self.time_indices = None
                    self.sampled_probabilities = None
                else:
                    self.time_indices: IntVec = time_indices
                    self.sampled_probabilities: Vec = np.ones(shape=len(self.time_indices)) / len(self.time_indices)

                    self.topologic_groups: Dict[int, List[int]] = self.get_topologic_groups()

    def get_steps(self):
        """
        Get time steps list of strings
        """

        return [self.grid.time_profile[i].strftime('%d-%m-%Y %H:%M') for i in self.time_indices]

    def get_topologic_groups(self) -> Dict[int, List[int]]:
        """
        Get numerical circuit time groups
        :return: Dictionary with the time: [array of times] represented by the index, for instance
                 {0: [0, 1, 2, 3, 4], 5: [5, 6, 7, 8]}
                 This means that [0, 1, 2, 3, 4] are represented by the topology of 0
                 and that [5, 6, 7, 8] are represented by the topology of 5
        """

        return tp.find_different_states(
            states_array=self.grid.get_branch_active_time_array()[self.time_indices]
        )
