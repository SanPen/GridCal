# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations
import time
import numpy as np
from typing import List, Dict, Union, TYPE_CHECKING
from VeraGridEngine.basic_structures import IntVec, Vec
from VeraGridEngine.basic_structures import Logger, Mat
from VeraGridEngine.enumerations import EngineType, SimulationTypes
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
import VeraGridEngine.Topology.topology as tp

if TYPE_CHECKING:
    from VeraGridEngine.Simulations.Clustering.clustering_results import ClusteringResults


class DummySignal:
    """
    Qt signal placeholder to not to import QT in the engine
    """

    def __init__(self, tpe: type = str) -> None:
        self.tpe = tpe

    def emit(self, val: Union[str, float] = '') -> None:
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
                 engine: EngineType = EngineType.VeraGrid):
        """
        Constructor
        :param grid: MultiCircuit instance
        :param engine: EngineType
        """
        self.progress_signal = DummySignal()
        self.progress_text = DummySignal(str)
        self.done_signal = DummySignal()

        self.grid: MultiCircuit = grid

        self.results = None

        self.engine = engine

        self.elapsed = 0

        self.logger = Logger()

        self.__cancel__ = False

        self._is_running = False

        self.__start = time.time()

    def tic(self, skip_logger=False):
        """
        Register start of time
        """
        self.__start = time.time()

        if not skip_logger:
            self.logger.add_info(msg="Elapsed total (s)",
                                 device_property="Started")

    def toc(self, skip_logger=False):
        """
        Register end of time
        :param skip_logger: skip logging this?
        """
        self.elapsed = time.time() - self.__start

        if not skip_logger:
            self.logger.add_info(msg="Elapsed total (s)",
                                 device_property="Ended (s)",
                                 value='{:.4f}'.format(self.elapsed))

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

    def report_progress(self, val: float):
        """
        Report progress
        :param val: float value
        """
        self.progress_signal.emit(val)

    def report_progress2(self, current: int, total: int):
        """
        Report progress
        :param current: current value (zero based)
        :param total: total value
        """
        val = ((current + 1) / total) * 100
        self.progress_signal.emit(val)

    def report_done(self, txt="done!", val=0.0):
        """
        Report done
        """
        self.report_progress(val)
        self.report_text(txt)
        self.done_signal.emit()

    def report_text(self, val: str):
        """
        Report text
        :param val: text value
        """
        self.progress_text.emit(val)

    def cancel(self):
        """
        Cancel the simulation
        """
        self.__cancel__ = True
        self.report_done("Cancelled!")

    def is_cancel(self) -> bool:
        """
        Check if cancel was activated
        :return:
        """
        return self.__cancel__

    def isRunning(self):
        return self._is_running


class TimeSeriesDriverTemplate(DriverTemplate):
    """
    Time series driver template
    """

    def __init__(
            self,
            grid: MultiCircuit,
            time_indices: IntVec,
            clustering_results: Union[ClusteringResults, None] = None,
            engine: EngineType = EngineType.VeraGrid,
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

        self.clustering_results: Union[ClusteringResults, None] = clustering_results

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
        if self.time_indices is None:
            return []
        else:
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

    def get_fuel_emissions_energy_calculations(self, gen_p: Mat, gen_cost: Mat):
        """
        Calculate fuel emissions and energy cost
        :param gen_p:
        :param gen_cost:
        :return:
        """
        # gather the fuels and emission rates matrices
        gen_emissions_rates_matrix = self.grid.get_gen_emission_rates_sparse_matrix()
        gen_fuel_rates_matrix = self.grid.get_gen_fuel_rates_sparse_matrix()

        system_fuel = (gen_fuel_rates_matrix * gen_p.T).T
        system_emissions = (gen_emissions_rates_matrix * gen_p.T).T

        with np.errstate(divide='ignore', invalid='ignore'):  # numpy magic to ignore the zero divisions
            system_energy_cost = np.nan_to_num(gen_cost / gen_p).sum(axis=1)

        return system_fuel, system_emissions, system_energy_cost
