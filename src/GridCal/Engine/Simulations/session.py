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
from uuid import uuid4

# Module imports
from GridCal.Engine.Simulations.driver_types import SimulationTypes
from GridCal.Engine.Simulations.NTC.net_transfer_capacity_driver import NetTransferCapacityResults
from GridCal.Engine.Simulations.NTC.net_transfer_capacity_ts_driver import NetTransferCapacityTimeSeriesResults
from GridCal.Engine.Simulations.ContingencyAnalysis.contingency_analysis_results import ContingencyAnalysisResults
from GridCal.Engine.Simulations.ContingencyAnalysis.contingency_analysis_ts_results import ContingencyAnalysisTimeSeriesResults
from GridCal.Engine.Simulations.ContinuationPowerFlow.continuation_power_flow_driver import ContinuationPowerFlowResults
from GridCal.Engine.Simulations.LinearFactors.linear_analysis_driver import LinearAnalysisResults
from GridCal.Engine.Simulations.LinearFactors.linear_analysis_ts_driver import LinearAnalysisTimeSeriesResults
from GridCal.Engine.Simulations.OPF.opf_results import OptimalPowerFlowResults
from GridCal.Engine.Simulations.OPF.opf_ts_results import OptimalPowerFlowTimeSeriesResults
from GridCal.Engine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from GridCal.Engine.Simulations.PowerFlow.time_series_driver import TimeSeriesResults
from GridCal.Engine.Simulations.ShortCircuitStudies.short_circuit_driver import ShortCircuitResults
from GridCal.Engine.Simulations.Stochastic.stochastic_power_flow_results import StochasticPowerFlowResults
from GridCal.Engine.Simulations.driver_template import DriverTemplate


def get_results_object_dictionary():
    """
    Get dictionary of recognizable result types in order to be able to load a driver from disk
    :return: dictionary[driver name: empty results object]
    """
    lst = [(NetTransferCapacityResults(0, 0, [], [], [], (), ()), SimulationTypes.NetTransferCapacity_run),
           (NetTransferCapacityTimeSeriesResults(0, 0, [], [], [], []), SimulationTypes.NetTransferCapacityTS_run),
           (ContingencyAnalysisResults(0, 0, [], [], []), SimulationTypes.ContingencyAnalysis_run),
           (ContingencyAnalysisTimeSeriesResults(0, 0, 0, [], [], [], []), SimulationTypes.ContingencyAnalysisTS_run),
           (ContinuationPowerFlowResults(0, 0, 0, [], [], []), SimulationTypes.ContinuationPowerFlow_run),
           (LinearAnalysisResults(0, 0, (), (), ()), SimulationTypes.LinearAnalysis_run),
           (LinearAnalysisTimeSeriesResults(0, 0, (), (), (), ()), SimulationTypes.LinearAnalysis_TS_run),
           (OptimalPowerFlowResults((), (), (), (), ()), SimulationTypes.OPF_run),
           (OptimalPowerFlowTimeSeriesResults((), (), (), (), (), 0, 0, 0), SimulationTypes.OPFTimeSeries_run),
           (PowerFlowResults(0, 0, 0, 0, (), (), (), (), ()), SimulationTypes.PowerFlow_run),
           (TimeSeriesResults(0, 0, 0, 0, (), (), (), (), (), ()), SimulationTypes.TimeSeries_run),
           (ShortCircuitResults(0, 0, 0, (), (), (), ()), SimulationTypes.ShortCircuit_run),
           (StochasticPowerFlowResults(0, 0, 0, (), (), ()), SimulationTypes.StochasticPowerFlow)
           ]

    return {tpe.value: (elm, tpe) for elm, tpe in lst}


class SimulationSession:

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
        self.drivers = dict()

    def __str__(self):
        return self.name

    def clear(self):
        """
        Delete all the drivers
        """
        self.drivers = dict()

    def register(self, driver):
        """
        Register driver
        :param driver: driver to register (must have a tpe variable in it)
        """
        self.drivers[driver.tpe] = driver

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
            if study_name == drv.name:
                del self.drivers[driver_type]
                return

    def get_driver_by_name(self, study_name: str):
        """
        Get the driver by it's name
        :param study_name: driver name
        """
        for driver_type, drv in self.drivers.items():
            if study_name == drv.name:
                return self.drivers[driver_type]
        return None

    def get_results_model_by_name(self, study_name, study_type):
        """
        Get the results model given the study name and study type
        :param study_name: name of the study
        :param study_type: name of the study type
        :return: ResultsModel instance or None if not found
        """
        for driver_type, drv in self.drivers.items():
            if study_name == drv.name:
                if drv.results is not None:
                    return drv.results.mdl(result_type=study_type)
                else:
                    print('There seem to be no results :(')
                    return None

        return None

    def register_driver_from_disk_data(self, grid, study_name: str, data_dict: dict):
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


