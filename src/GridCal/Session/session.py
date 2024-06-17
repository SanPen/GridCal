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
from typing import Dict, Union, List, Tuple, Any
from collections.abc import Callable
from warnings import warn

# Module imports
from GridCalEngine.Simulations.ATC.available_transfer_capacity_driver import (AvailableTransferCapacityDriver,
                                                                              AvailableTransferCapacityResults)
from GridCalEngine.Simulations.ATC.available_transfer_capacity_ts_driver import (
    AvailableTransferCapacityTimeSeriesDriver, AvailableTransferCapacityTimeSeriesResults)
from GridCalEngine.Simulations.ContingencyAnalysis.contingency_analysis_driver import (ContingencyAnalysisDriver,
                                                                                       ContingencyAnalysisResults)
from GridCalEngine.Simulations.ContingencyAnalysis.contingency_analysis_ts_driver import (
    ContingencyAnalysisTimeSeriesDriver, ContingencyAnalysisTimeSeriesResults)
from GridCalEngine.Simulations.ContinuationPowerFlow.continuation_power_flow_driver import (ContinuationPowerFlowDriver,
                                                                                            ContinuationPowerFlowResults)
from GridCalEngine.Simulations.LinearFactors.linear_analysis_driver import LinearAnalysisDriver, LinearAnalysisResults
from GridCalEngine.Simulations.LinearFactors.linear_analysis_ts_driver import (LinearAnalysisTimeSeriesDriver,
                                                                               LinearAnalysisTimeSeriesResults)
from GridCalEngine.Simulations.OPF.opf_driver import OptimalPowerFlowDriver, OptimalPowerFlowResults
from GridCalEngine.Simulations.OPF.opf_ts_driver import (OptimalPowerFlowTimeSeriesDriver,
                                                         OptimalPowerFlowTimeSeriesResults)
from GridCalEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver, PowerFlowResults
from GridCalEngine.Simulations.PowerFlow.power_flow_ts_driver import (PowerFlowTimeSeriesDriver,
                                                                      PowerFlowTimeSeriesResults)
from GridCalEngine.Simulations.ShortCircuitStudies.short_circuit_driver import ShortCircuitDriver, ShortCircuitResults
from GridCalEngine.Simulations.Stochastic.stochastic_power_flow_driver import (StochasticPowerFlowDriver,
                                                                               StochasticPowerFlowResults)
from GridCalEngine.Simulations.Clustering.clustering_driver import ClusteringDriver, ClusteringResults
from GridCalEngine.Simulations.Stochastic.blackout_driver import CascadingResults
from GridCalEngine.Simulations.InputsAnalysis.inputs_analysis_driver import InputsAnalysisResults
from GridCalEngine.Simulations.InvestmentsEvaluation.investments_evaluation_driver import (InvestmentsEvaluationDriver,
                                                                                           InvestmentsEvaluationResults)
from GridCalEngine.Simulations.SigmaAnalysis.sigma_analysis_driver import SigmaAnalysisResults
from GridCalEngine.Simulations.NTC.ntc_driver import OptimalNetTransferCapacityResults
from GridCalEngine.Simulations.NodalCapacity.nodal_capacity_ts_driver import (NodalCapacityTimeSeriesDriver,
                                                                              NodalCapacityTimeSeriesResults)
from GridCalEngine.Simulations.Topology.node_groups_driver import NodeGroupsDriver
from GridCalEngine.Simulations.driver_template import DriverTemplate
from GridCalEngine.Simulations.results_template import DriverToSave
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.enumerations import ResultTypes, SimulationTypes
from GridCalEngine.Simulations.types import DRIVER_OBJECTS, RESULTS_OBJECTS
from GridCalEngine.basic_structures import Logger
from GridCal.Session.results_model import ResultsModel


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

    def get_steps(self) -> List[Any]:
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

    def cancel(self) -> None:
        """
        Cancel the simulation
        """
        self.__cancel__ = True
        self.driver.__cancel__ = True


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
        self.drivers: Dict[SimulationTypes, DRIVER_OBJECTS] = dict()
        self.threads: Dict[SimulationTypes, GcThread] = dict()

    def __str__(self):
        return self.name

    def clear(self) -> None:
        """
        Delete all the drivers
        """
        self.drivers = dict()

    def register(self, driver: DRIVER_OBJECTS):
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
            driver: DRIVER_OBJECTS,
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

    def get_driver_results(self, driver_type: SimulationTypes) -> Tuple[
        Union[None, DRIVER_OBJECTS], Union[None, RESULTS_OBJECTS]]:
        """
        Get the results of the driver
        :param driver_type: driver type
        :return: driver, results (None, None if not found)
        """

        drv: DRIVER_OBJECTS = self.drivers.get(driver_type, None)

        if drv is not None:
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

    def delete_driver(self, driver_type: SimulationTypes) -> None:
        """
        Get the results of the driver
        :param driver_type: driver type to delete
        """
        if driver_type in self.drivers.keys():
            del self.drivers[driver_type]

    def delete_driver_by_name(self, study_name: str) -> None:
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

    def get_driver_by_name(self,
                           study_name: str) -> Union[DRIVER_OBJECTS, None]:
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

    def get_results_model_by_name(self,
                                  study_name: str,
                                  study_type: ResultTypes) -> Union[ResultsModel, None]:
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
                                       data_dict: Dict[str, pd.DataFrame]) -> None:
        """
        Create driver with the results
        :param grid: MultiCircuit instance
        :param study_name: name of the study (i.e. Power Flow)
        :param data_dict: dictionary of data coming from the file
        """

        time_indices = data_dict.get('time_indices', grid.get_all_time_indices())

        # get the results' object dictionary
        if study_name == AvailableTransferCapacityDriver.tpe.value:
            drv = AvailableTransferCapacityDriver(grid=grid, options=None)

        elif study_name == AvailableTransferCapacityTimeSeriesDriver.tpe.value:
            drv = AvailableTransferCapacityTimeSeriesDriver(grid=grid,
                                                            options=None,
                                                            time_indices=time_indices,
                                                            clustering_results=None)

        elif study_name == ContingencyAnalysisDriver.tpe.value:
            drv = ContingencyAnalysisDriver(grid=grid, options=None)

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
            drv = LinearAnalysisDriver(grid=grid, options=None)

        elif study_name == ContinuationPowerFlowDriver.tpe.value:
            drv = LinearAnalysisTimeSeriesDriver(grid=grid,
                                                 options=None,
                                                 time_indices=time_indices,
                                                 clustering_results=None)

        elif study_name == OptimalPowerFlowDriver.tpe.value:
            drv = OptimalPowerFlowDriver(grid=grid, options=None)

        elif study_name == OptimalPowerFlowTimeSeriesDriver.tpe.value:
            drv = OptimalPowerFlowTimeSeriesDriver(grid=grid,
                                                   options=None,
                                                   time_indices=time_indices,
                                                   clustering_results=None)

        elif study_name == NodalCapacityTimeSeriesDriver.tpe.value:
            drv = NodalCapacityTimeSeriesDriver(grid=grid,
                                                options=None,
                                                time_indices=time_indices,
                                                clustering_results=None)

        elif study_name == PowerFlowDriver.tpe.value:
            drv = PowerFlowDriver(grid=grid, options=None)

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
            drv = StochasticPowerFlowDriver(grid=grid, options=None)

        elif study_name == ClusteringDriver.tpe.value:
            drv = ClusteringDriver(grid=grid, options=None)

        elif study_name == InvestmentsEvaluationDriver.tpe.value:
            drv = InvestmentsEvaluationDriver(grid=grid, options=None)

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

    def is_this_running(self, sim_tpe: SimulationTypes) -> bool:
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
    def clustering(self) -> ClusteringResults:
        """

        :return:
        """
        drv, results = self.get_driver_results(SimulationTypes.ClusteringAnalysis_run)
        return results

    @property
    def power_flow(self) -> PowerFlowResults:
        """

        :return:
        """
        drv, results = self.get_driver_results(SimulationTypes.PowerFlow_run)
        return results

    @property
    def power_flow_driver_and_results(self) -> Tuple[PowerFlowDriver, PowerFlowResults]:
        """

        :return:
        """
        drv, results = self.get_driver_results(SimulationTypes.PowerFlow_run)
        return drv, results

    @property
    def power_flow_ts(self) -> PowerFlowTimeSeriesResults:
        """

        :return:
        """
        drv, results = self.get_driver_results(SimulationTypes.PowerFlowTimeSeries_run)
        return results

    @property
    def optimal_power_flow(self) -> OptimalPowerFlowResults:
        """

        :return:
        """
        drv, results = self.get_driver_results(SimulationTypes.OPF_run)
        return results

    @property
    def optimal_power_flow_ts(self) -> OptimalPowerFlowTimeSeriesResults:
        """

        :return:
        """
        drv, results = self.get_driver_results(SimulationTypes.OPFTimeSeries_run)
        return results

    @property
    def short_circuit(self) -> ShortCircuitResults:
        """

        :return:
        """
        drv, results = self.get_driver_results(SimulationTypes.ShortCircuit_run)
        return results

    @property
    def linear_power_flow(self) -> LinearAnalysisResults:
        """

        :return:
        """
        drv, results = self.get_driver_results(SimulationTypes.LinearAnalysis_run)
        return results

    @property
    def linear_power_flow_ts(self) -> LinearAnalysisTimeSeriesResults:
        """

        :return:
        """
        drv, results = self.get_driver_results(SimulationTypes.LinearAnalysis_TS_run)
        return results

    @property
    def contingency(self) -> ContingencyAnalysisResults:
        """

        :return:
        """
        drv, results = self.get_driver_results(SimulationTypes.ContingencyAnalysis_run)
        return results

    @property
    def contingency_ts(self) -> ContingencyAnalysisTimeSeriesResults:
        """

        :return:
        """
        drv, results = self.get_driver_results(SimulationTypes.ContingencyAnalysisTS_run)
        return results

    @property
    def continuation_power_flow(self) -> ContinuationPowerFlowResults:
        """

        :return:
        """
        drv, results = self.get_driver_results(SimulationTypes.ContinuationPowerFlow_run)
        return results

    @property
    def net_transfer_capacity(self) -> AvailableTransferCapacityResults:
        """

        :return:
        """
        drv, results = self.get_driver_results(SimulationTypes.NetTransferCapacity_run)
        return results

    @property
    def net_transfer_capacity_ts(self) -> AvailableTransferCapacityTimeSeriesResults:
        """

        :return:
        """
        drv, results = self.get_driver_results(SimulationTypes.NetTransferCapacityTS_run)
        return results

    @property
    def optimal_net_transfer_capacity(self) -> OptimalNetTransferCapacityResults:
        """

        :return:
        """
        drv, results = self.get_driver_results(SimulationTypes.OPF_NTC_run)
        return results

    @property
    def optimal_net_transfer_capacity_ts(self) -> OptimalNetTransferCapacityResults:
        """

        :return:
        """
        drv, results = self.get_driver_results(SimulationTypes.OPF_NTC_TS_run)
        return results

    @property
    def nodal_capacity_optimization_ts(self) -> NodalCapacityTimeSeriesResults:
        """

        :return:
        """
        drv, results = self.get_driver_results(SimulationTypes.NodalCapacityTimeSeries_run)
        return results

    @property
    def stochastic_power_flow(self) -> StochasticPowerFlowResults:
        """

        :return:
        """
        drv, results = self.get_driver_results(SimulationTypes.StochasticPowerFlow)
        return results

    @property
    def sigma_analysis(self) -> SigmaAnalysisResults:
        """

        :return:
        """
        drv, results = self.get_driver_results(SimulationTypes.SigmaAnalysis_run)
        return results

    @property
    def cascade(self) -> CascadingResults:
        """

        :return:
        """
        drv, results = self.get_driver_results(SimulationTypes.Cascade_run)
        return results

    @property
    def inputs_analysis(self) -> InputsAnalysisResults:
        """

        :return:
        """
        drv, results = self.get_driver_results(SimulationTypes.InputsAnalysis_run)
        return results

    @property
    def investments_evaluation(self) -> InvestmentsEvaluationResults:
        """

        :return:
        """
        drv, results = self.get_driver_results(SimulationTypes.InvestmentsEvaluation_run)
        return results

    @property
    def node_groups_driver(self) -> NodeGroupsDriver:
        """

        :return:
        """
        drv, results = self.get_driver_results(SimulationTypes.NodeGrouping_run)
        return drv
