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
from uuid import uuid4
import pandas as pd
from PySide6.QtCore import QThread, Signal
from typing import Dict, Union, List
from collections.abc import Callable
from warnings import warn

# Module imports
from GridCalEngine.Simulations.ATC.available_transfer_capacity_driver import AvailableTransferCapacityDriver
from GridCalEngine.Simulations.ATC.available_transfer_capacity_ts_driver import \
    AvailableTransferCapacityTimeSeriesDriver
from GridCalEngine.Simulations.ContingencyAnalysis.contingency_analysis_driver import ContingencyAnalysisDriver
from GridCalEngine.Simulations.ContingencyAnalysis.contingency_analysis_ts_driver import \
    ContingencyAnalysisTimeSeriesDriver
from GridCalEngine.Simulations.ContinuationPowerFlow.continuation_power_flow_driver import ContinuationPowerFlowDriver
from GridCalEngine.Simulations.LinearFactors.linear_analysis_driver import LinearAnalysisDriver
from GridCalEngine.Simulations.LinearFactors.linear_analysis_ts_driver import LinearAnalysisTimeSeriesDriver
from GridCalEngine.Simulations.OPF.opf_driver import OptimalPowerFlowDriver
from GridCalEngine.Simulations.OPF.opf_ts_driver import OptimalPowerFlowTimeSeriesDriver
from GridCalEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver
from GridCalEngine.Simulations.PowerFlow.power_flow_ts_driver import PowerFlowTimeSeriesDriver
from GridCalEngine.Simulations.ShortCircuitStudies.short_circuit_driver import ShortCircuitDriver
from GridCalEngine.Simulations.Stochastic.stochastic_power_flow_driver import StochasticPowerFlowDriver
from GridCalEngine.Simulations.Clustering.clustering_driver import ClusteringDriver
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Simulations.driver_template import DriverTemplate
from GridCalEngine.Simulations.driver_types import SimulationTypes
from GridCalEngine.enumerations import ResultTypes
from GridCalEngine.basic_structures import Logger
from GridCal.Session.results_model import ResultsModel
from GridCalEngine.Simulations.results_template import DriverToSave


class GcThread(QThread):
    """
    Generic GridCal Thread
    this is used as a template for a Qt Thread
    """
    progress_signal = Signal(float)
    progress_text = Signal(str)
    done_signal = Signal()

    def __init__(self, driver: DriverTemplate):
        QThread.__init__(self)

        # assign the driver and set the driver's reporting functions
        self.driver = driver
        self.driver.progress_signal = self.progress_signal
        self.driver.progress_text = self.progress_text
        self.driver.done_signal = self.done_signal
        self.tpe = driver.tpe

        self.results = None

        self.elapsed = 0

        self.logger = Logger()

        self.__cancel__ = False

    def get_steps(self):
        """

        :return:
        """
        return list()

    def run(self) -> None:
        """
        Run driver
        """
        self.progress_signal.emit(0.0)

        self.driver.run()

        self.progress_signal.emit(0.0)
        if self.__cancel__:
            self.progress_text.emit('Cancelled!')
        else:
            self.progress_text.emit('Done!')
        self.done_signal.emit()

    def cancel(self):
        """
        Cancel the simulation
        """
        self.__cancel__ = True
        # self.terminate()
        # self.quit()
        self.driver.__cancel__ = True
        # self.progress_signal.emit(0.0)
        # self.progress_text.emit('Cancelled!')
        # self.done_signal.emit()


class SimulationSession:
    """
    The simulation session is the simulation manager
    it serves to orchestrate the threads and to store the drivers and their results
    """

    def __init__(self, name: str = 'Session', idtag: str = None):
        """
        Constructor
        :param name: Session name
        :param idtag: Unique identifier
        """
        self.idtag: str = uuid4().hex if idtag is None else idtag

        # name of the session
        self.name: str = name

        # dictionary of drivers
        self.drivers: Dict[SimulationTypes, DriverTemplate] = dict()
        self.threads: Dict[SimulationTypes, GcThread] = dict()

    def __str__(self):
        return self.name

    def clear(self) -> None:
        """
        Delete all the drivers
        """
        self.drivers = dict()

    def register(self, driver: DriverTemplate):
        """
        Register driver
        :param driver: driver to register (must have a tpe variable in it)
        """
        # register
        self.drivers[driver.tpe] = driver

    def get_save_data(self) -> List[DriverToSave]:
        """
        Get data to be saved
        :return: List[DriverToSave]
        """
        data = list()
        for tpe, drv in self.drivers.items():
            data.append(DriverToSave(name=self.name,
                                     tpe=tpe,
                                     results=drv.results,
                                     logger=drv.logger))
        return data

    def run(self,
            driver: DriverTemplate,
            post_func: Union[None, Callable] = None,
            prog_func: Union[None, Callable] = None,
            text_func: Union[None, Callable] = None):
        """
        Register driver
        :param driver: driver to register (must have a tpe variable in it)
        :param post_func: Function to run after it is done
        :param prog_func: Function to display the progress
        :param text_func: Function to display text
        """

        # create process
        thr = GcThread(driver)
        thr.progress_signal.connect(prog_func)
        thr.progress_text.connect(text_func)
        thr.done_signal.connect(post_func)

        # check and kill
        if driver.tpe in self.drivers.keys():
            del self.drivers[driver.tpe]
            if self.threads[driver.tpe].isRunning():
                self.threads[driver.tpe].terminate()
            del self.threads[driver.tpe]

        # register
        self.drivers[driver.tpe] = driver
        self.threads[driver.tpe] = thr

        # run!
        thr.start()

    def get_available_drivers(self):
        """
        Get a list of the available driver objects
        :return: List[Driver]
        """
        return [drv for driver_type, drv in self.drivers.items() if drv is not None]

    def exists(self, driver_type: SimulationTypes):
        """
        Get the results of the driver
        :param driver_type: driver type to look for
        :return: True / False
        """
        return driver_type in self.drivers.keys()

    def get_driver_results(self, driver_type: SimulationTypes):
        """
        Get the results of the driver
        :param driver_type: driver type
        :return: driver, results (None, None if not found)
        """
        if driver_type in self.drivers.keys():
            drv = self.drivers[driver_type]
            if hasattr(drv, 'results'):
                return drv, drv.results
            else:
                return drv, None
        else:
            return None, None

    def get_results(self, driver_type: SimulationTypes):
        """
        Get the results of the driver
        :param driver_type: driver type
        :return: driver, results (None, None if not found)
        """
        if driver_type in self.drivers.keys():
            drv = self.drivers[driver_type]
            if hasattr(drv, 'results'):
                return drv.results
            else:
                return None
        else:
            return None

    def delete_driver(self, driver_type: SimulationTypes):
        """
        Get the results of the driver
        :param driver_type: driver type to delete
        """
        if driver_type in self.drivers.keys():
            del self.drivers[driver_type]

    def delete_driver_by_name(self, study_name: str):
        """
        Delete the driver by it's name
        :param study_name: driver name
        """
        for driver_type, drv in self.drivers.items():
            if study_name == drv.tpe.value:
                del self.drivers[driver_type]
                return
            if study_name == drv.name:
                del self.drivers[driver_type]
                return

    def get_driver_by_name(self, study_name: str) -> Union[DriverTemplate, None]:
        """
        Get the driver by it's name
        :param study_name: driver name
        """
        for driver_type, drv in self.drivers.items():
            if study_name == drv.name:
                return self.drivers[driver_type]
            if study_name == drv.tpe.value:
                return self.drivers[driver_type]
        return None

    def get_results_model_by_name(self, study_name: str, study_type: ResultTypes) -> Union[ResultsModel, None]:
        """
        Get the results model given the study name and study type
        :param study_name: name of the study
        :param study_type: name of the study type
        :return: ResultsModel instance or None if not found
        """
        for driver_type, drv in self.drivers.items():
            if study_name == drv.tpe.value or study_name == drv.name:
                if drv.results is not None:
                    return ResultsModel(drv.results.mdl(result_type=study_type))
                else:
                    print('There seem to be no results :(')
                    return None

        return None

    def register_driver_from_disk_data(self,
                                       grid: MultiCircuit,
                                       study_name: str,
                                       data_dict: Dict[str, pd.DataFrame]):
        """
        Create driver with the results
        :param grid: MultiCircuit instance
        :param study_name: name of the study (i.e. Power Flow)
        :param data_dict: dictionary of data coming from the file
        :return:
        """

        time_indices = data_dict.get('time_indices', grid.get_all_time_indices())

        # get the results' object dictionary
        if study_name == AvailableTransferCapacityDriver.tpe.value:
            drv = AvailableTransferCapacityDriver(grid=grid,
                                                  options=None)

        elif study_name == AvailableTransferCapacityTimeSeriesDriver.tpe.value:
            drv = AvailableTransferCapacityTimeSeriesDriver(grid=grid,
                                                            options=None,
                                                            time_indices=time_indices,
                                                            clustering_results=None)

        elif study_name == ContingencyAnalysisDriver.tpe.value:
            drv = ContingencyAnalysisDriver(grid=grid,
                                            options=None)

        elif study_name == ContingencyAnalysisTimeSeriesDriver.tpe.value:
            drv = ContingencyAnalysisTimeSeriesDriver(grid=grid,
                                                      options=None,
                                                      time_indices=time_indices,
                                                      clustering_results=None)

        elif study_name == ContinuationPowerFlowDriver.tpe.value:
            drv = ContinuationPowerFlowDriver(grid=grid,
                                              options=None,
                                              inputs=None,
                                              pf_options=None,
                                              opf_results=None)

        elif study_name == LinearAnalysisDriver.tpe.value:
            drv = LinearAnalysisDriver(grid=grid,
                                       options=None)

        elif study_name == ContinuationPowerFlowDriver.tpe.value:
            drv = LinearAnalysisTimeSeriesDriver(grid=grid,
                                                 options=None,
                                                 time_indices=time_indices,
                                                 clustering_results=None)

        elif study_name == OptimalPowerFlowDriver.tpe.value:
            drv = OptimalPowerFlowDriver(grid=grid,
                                         options=None)

        elif study_name == OptimalPowerFlowTimeSeriesDriver.tpe.value:
            drv = OptimalPowerFlowTimeSeriesDriver(grid=grid,
                                                   options=None,
                                                   time_indices=time_indices,
                                                   clustering_results=None)

        elif study_name == PowerFlowDriver.tpe.value:
            drv = PowerFlowDriver(grid=grid,
                                  options=None)

        elif study_name == PowerFlowTimeSeriesDriver.tpe.value:
            drv = PowerFlowTimeSeriesDriver(grid=grid,
                                            options=None,
                                            time_indices=time_indices,
                                            clustering_results=None)

        elif study_name == ShortCircuitDriver.tpe.value:
            drv = ShortCircuitDriver(grid=grid,
                                     options=None,
                                     pf_options=None,
                                     pf_results=None,
                                     opf_results=None)

        elif study_name == StochasticPowerFlowDriver.tpe.value:
            drv = StochasticPowerFlowDriver(grid=grid,
                                            options=None)

        elif study_name == ClusteringDriver.tpe.value:
            drv = ClusteringDriver(grid=grid,
                                   options=None)

        else:
            warn(f"Session {study_name} not implemented for disk retrieval :/")
            return

        # fill in the saved results
        drv.results.parse_saved_data(grid=grid, data_dict=data_dict)

        # perform whatever operations are needed after loading
        drv.results.consolidate_after_loading()

        # parse the logger if available
        logger_data = data_dict.get('logger', None)
        if logger_data is not None:
            drv.logger.parse_df(df=logger_data)

        # register the driver
        self.register(drv)

    def is_this_running(self, sim_tpe: SimulationTypes):
        """
        Check if a simulation type is running
        :param sim_tpe: SimulationTypes
        :return: True / False
        """
        for driver_type, drv in self.threads.items():
            if drv is not None:
                if drv.isRunning():
                    if driver_type == sim_tpe:
                        return True
        return False

    def is_anything_running(self) -> bool:
        """
        Check if anything is running
        :return: True / False
        """

        for driver_type, drv in self.threads.items():
            if drv is not None:
                if drv.isRunning():
                    return True
        return False

    @property
    def power_flow(self):
        """

        :return:
        """
        return self.get_driver_results(SimulationTypes.PowerFlow_run)[1]

    @property
    def power_flow_ts(self):
        """

        :return:
        """
        return self.get_driver_results(SimulationTypes.TimeSeries_run)[1]

    @property
    def power_flow_cluster_ts(self):
        """

        :return:
        """
        return self.get_driver_results(SimulationTypes.ClusteringTimeSeries_run)[1]

    @property
    def optimal_power_flow(self):
        """

        :return:
        """
        return self.get_driver_results(SimulationTypes.OPF_run)[1]

    @property
    def optimal_power_flow_ts(self):
        """

        :return:
        """
        return self.get_driver_results(SimulationTypes.OPFTimeSeries_run)[1]

    @property
    def short_circuit(self):
        """

        :return:
        """
        return self.get_driver_results(SimulationTypes.ShortCircuit_run)[1]

    @property
    def linear_power_flow(self):
        """

        :return:
        """
        return self.get_driver_results(SimulationTypes.LinearAnalysis_run)[1]

    @property
    def linear_power_flow_ts(self):
        """

        :return:
        """
        return self.get_driver_results(SimulationTypes.LinearAnalysis_TS_run)[1]

    @property
    def contingency(self):
        """

        :return:
        """
        return self.get_driver_results(SimulationTypes.ContingencyAnalysis_run)[1]

    @property
    def contingency_ts(self):
        """

        :return:
        """
        return self.get_driver_results(SimulationTypes.ContingencyAnalysisTS_run)[1]

    @property
    def continuation_power_flow(self):
        """

        :return:
        """
        return self.get_driver_results(SimulationTypes.ContinuationPowerFlow_run)[1]

    @property
    def net_transfer_capacity(self):
        """

        :return:
        """
        return self.get_driver_results(SimulationTypes.NetTransferCapacity_run)[1]

    @property
    def net_transfer_capacity_ts(self):
        """

        :return:
        """
        return self.get_driver_results(SimulationTypes.NetTransferCapacityTS_run)[1]

    @property
    def optimal_net_transfer_capacity(self):
        """

        :return:
        """
        return self.get_driver_results(SimulationTypes.OPF_NTC_run)[1]

    @property
    def stochastic_power_flow(self):
        """

        :return:
        """
        return self.get_driver_results(SimulationTypes.StochasticPowerFlow)[1]

    @property
    def sigma_analysis(self):
        """

        :return:
        """
        return self.get_driver_results(SimulationTypes.SigmaAnalysis_run)[1]

    @property
    def cascade(self):
        """

        :return:
        """
        return self.get_driver_results(SimulationTypes.Cascade_run)[1]
