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
        self.drivers = dict()

    def register(self, driver):
        """
        Register driver
        :param driver:
        :return:
        """
        self.drivers[driver.tpe] = driver

    def get_available_drivers(self):
        return [drv for driver_type, drv in self.drivers.items() if drv is not None]

    def exists(self, driver_type: SimulationTypes):
        """
        Get the results of the driver
        :param driver_type:
        :return:
        """
        return driver_type in self.drivers.keys()

    def get_driver_results(self, driver_type: SimulationTypes):
        """
        Get the results of the driver
        :param driver_type:
        :return:
        """
        if driver_type in self.drivers.keys():
            drv = self.drivers[driver_type]
            if hasattr(drv, 'results'):
                return drv, drv.results
            else:
                return drv, None
        else:
            return None, None

    def get_results_model_by_name(self, study_name, study_type):
        """
        Get the results model given the study name and study type
        :param study_name:
        :param study_type:
        :return:
        """
        for driver_type, drv in self.drivers.items():
            if study_name == drv.name:
                if drv.results is not None:
                    return drv.results.mdl(result_type=study_type)
                else:
                    print('There seem to be no results :(')
                    return None

        return None

