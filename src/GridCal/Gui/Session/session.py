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
from uuid import uuid4
from PySide6.QtCore import QThread, Signal
from typing import Dict, Union
from collections.abc import Callable

# Module imports
from GridCalEngine.Simulations.ATC.available_transfer_capacity_driver import AvailableTransferCapacityResults
from GridCalEngine.Simulations.ATC.available_transfer_capacity_ts_driver import \
    AvailableTransferCapacityTimeSeriesResults
from GridCalEngine.Simulations.ContingencyAnalysis.contingency_analysis_results import ContingencyAnalysisResults
from GridCalEngine.Simulations.ContingencyAnalysis.contingency_analysis_ts_results import \
    ContingencyAnalysisTimeSeriesResults
from GridCalEngine.Simulations.ContinuationPowerFlow.continuation_power_flow_driver import ContinuationPowerFlowResults
from GridCalEngine.Simulations.LinearFactors.linear_analysis_driver import LinearAnalysisResults
from GridCalEngine.Simulations.LinearFactors.linear_analysis_ts_driver import LinearAnalysisTimeSeriesResults
from GridCalEngine.Simulations.OPF.opf_results import OptimalPowerFlowResults
from GridCalEngine.Simulations.OPF.opf_ts_results import OptimalPowerFlowTimeSeriesResults
from GridCalEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from GridCalEngine.Simulations.PowerFlow.power_flow_ts_driver import PowerFlowTimeSeriesResults
from GridCalEngine.Simulations.ShortCircuitStudies.short_circuit_driver import ShortCircuitResults
from GridCalEngine.Simulations.Stochastic.stochastic_power_flow_results import StochasticPowerFlowResults
from GridCalEngine.Core.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Simulations.driver_template import DriverTemplate
from GridCalEngine.Simulations.driver_types import SimulationTypes
from GridCalEngine.Simulations.result_types import ResultTypes
from GridCalEngine.basic_structures import Logger
from GridCal.Gui.Session.results_model import ResultsModel


def get_results_object_dictionary():
    """
    Get dictionary of recognizable result types in order to be able to load a driver from disk
    :return: dictionary[driver name: empty results object]
    """
    lst = [(AvailableTransferCapacityResults([], [], [], [], clustering_results=None), SimulationTypes.NetTransferCapacity_run),
           (AvailableTransferCapacityTimeSeriesResults([], [], [], [], [], clustering_results=None), SimulationTypes.NetTransferCapacityTS_run),
           (ContingencyAnalysisResults(0, 0, 0, [], [], [], []), SimulationTypes.ContingencyAnalysis_run),
           (ContingencyAnalysisTimeSeriesResults(0, 0, 0, [], [], [], [], [], clustering_results=None),
            SimulationTypes.ContingencyAnalysisTS_run),
           (ContinuationPowerFlowResults(0, 0, 0, [], [], []), SimulationTypes.ContinuationPowerFlow_run),
           (LinearAnalysisResults(0, 0, (), (), ()), SimulationTypes.LinearAnalysis_run),
           (LinearAnalysisTimeSeriesResults(0, 0, (), (), (), (), clustering_results=None), SimulationTypes.LinearAnalysis_TS_run),
           (OptimalPowerFlowResults(bus_names=(), branch_names=(), load_names=(), generator_names=(), battery_names=(),
                                    hvdc_names=(), bus_types=(), area_names=(), F=(), T=(), F_hvdc=(), T_hvdc=(), bus_area_indices=()),
                                    SimulationTypes.OPF_run),
           (OptimalPowerFlowTimeSeriesResults((), (), (), (), (), (), 0, 0, 0, clustering_results=None), SimulationTypes.OPFTimeSeries_run),
           (PowerFlowResults(0, 0, 0, 0, (), (), (), (), ()), SimulationTypes.PowerFlow_run),
           (PowerFlowTimeSeriesResults(0, 0, 0, 0, (), (), (), (), (), ()), SimulationTypes.TimeSeries_run),
           (ShortCircuitResults(0, 0, 0, 0, (), (), (), (), ()), SimulationTypes.ShortCircuit_run),
           (StochasticPowerFlowResults(0, 0, 0, (), (), ()), SimulationTypes.StochasticPowerFlow)
           ]

    return {tpe.value: (elm, tpe) for elm, tpe in lst}


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
        self.threads: Dict[GcThread] = dict()

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

    def register_driver_from_disk_data(self, grid: MultiCircuit, study_name: str, data_dict: dict):
        """
        Create driver with the results
        :param grid: MultiCircuit instance
        :param study_name: name of the study (i.e. Power Flow)
        :param data_dict: dictionary of data coming from the file
        :return:
        """

        # get the results' object dictionary
        drivers_dict = get_results_object_dictionary()

        if study_name in drivers_dict.keys():

            # declare a dummy driver
            drv = DriverTemplate(grid=grid)

            # set the empty results driver
            drv.results, drv.tpe = drivers_dict[study_name]
            drv.name = drv.tpe.value

            # fill in the variables
            for arr_name, arr in data_dict.items():
                setattr(drv.results, arr_name, arr)

            # perform whatever operations are needed after loading
            drv.results.consolidate_after_loading()

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
