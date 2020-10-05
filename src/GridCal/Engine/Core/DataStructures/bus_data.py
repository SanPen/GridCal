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
import numpy as np


class BusData:

    def __init__(self, nbus):
        """

        :param nbus:
        """
        self.nbus = nbus
        self.bus_names = np.empty(nbus, dtype=object)
        self.bus_active = np.ones(nbus, dtype=int)
        self.Vbus = np.ones(nbus, dtype=complex)
        self.bus_types = np.empty(nbus, dtype=int)
        self.bus_installed_power = np.zeros(nbus, dtype=float)
        self.bus_is_dc = np.empty(nbus, dtype=bool)

    def slice(self, bus_idx):
        """

        :param bus_idx:
        :return:
        """
        data = BusData(nbus=len(bus_idx))

        data.bus_names = self.bus_names[bus_idx]
        data.bus_active = self.bus_active[bus_idx]
        data.Vbus = self.Vbus[bus_idx]
        data.bus_types = self.bus_types[bus_idx]
        data.bus_installed_power = self.bus_installed_power[bus_idx]
        data.bus_is_dc = self.bus_is_dc[bus_idx]

        return data

    def __len__(self):
        return self.nbus


class BusTimeData(BusData):

    def __init__(self, nbus, ntime):
        """

        :param nbus:
        :param ntime:
        """
        BusData.__init__(self, nbus)

        self.ntime = ntime

        self.bus_active = np.ones((ntime, nbus), dtype=int)
        self.Vbus = np.ones((ntime, nbus), dtype=complex)

    def slice_time(self, bus_idx, time_idx):
        """

        :param bus_idx:
        :param time_idx:
        :return:
        """
        data = BusData(nbus=len(bus_idx))

        data.bus_names = self.bus_names[bus_idx]

        data.bus_active = self.bus_active[np.ix_(time_idx, bus_idx)]
        data.Vbus = self.Vbus[np.ix_(time_idx, bus_idx)]

        data.bus_types = self.bus_types[bus_idx]
        data.bus_installed_power = self.bus_installed_power[bus_idx]
        data.bus_is_dc = self.bus_is_dc[bus_idx]

        return data
