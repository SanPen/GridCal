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
import scipy.sparse as sp
import GridCal.Engine.Core.topology as tp


class StaticGeneratorData:

    def __init__(self, nstagen, nbus):
        """

        :param nstagen:
        :param nbus:
        """
        self.nstagen = nstagen

        self.static_generator_names = np.empty(nstagen, dtype=object)
        self.static_generator_active = np.zeros(nstagen, dtype=bool)
        self.static_generator_s = np.zeros(nstagen, dtype=complex)

        self.C_bus_static_generator = sp.lil_matrix((nbus, nstagen), dtype=int)

    def slice(self, stagen_idx, bus_idx):
        """

        :param stagen_idx:
        :param bus_idx:
        :return:
        """
        data = StaticGeneratorData(nstagen=len(stagen_idx), nbus=len(bus_idx))
        data.static_generator_names = self.static_generator_names[stagen_idx]
        data.static_generator_active = self.static_generator_active[stagen_idx]
        data.static_generator_s = self.static_generator_s[stagen_idx]

        data.C_bus_static_generator = self.C_bus_static_generator[np.ix_(bus_idx, stagen_idx)]

        return data

    def get_island(self, bus_idx):
        return tp.get_elements_of_the_island(self.C_bus_static_generator.T, bus_idx)

    def get_injections_per_bus(self):
        return self.C_bus_static_generator * (self.static_generator_s * self.static_generator_active)

    def __len__(self):
        return self.nstagen


class StaticGeneratorTimeData(StaticGeneratorData):

    def __init__(self, nstagen, nbus, ntime):
        StaticGeneratorData.__init__(self, nstagen, nbus)
        self.ntime = ntime

        self.static_generator_active = np.zeros((ntime, nstagen), dtype=bool)
        self.static_generator_s = np.zeros((ntime, nstagen), dtype=complex)

    def slice_time(self, nstagen_idx, bus_idx, time_idx):
        """

        :param nstagen_idx:
        :param bus_idx:
        :param time_idx:
        :return:
        """
        data = StaticGeneratorTimeData(nstagen=len(nstagen_idx), nbus=len(bus_idx), ntime=len(time_idx))

        data.load_names = self.static_generator_names[nstagen_idx]

        data.static_generator_active = self.static_generator_active[np.ix_(time_idx, nstagen_idx)]
        data.static_generator_s = self.static_generator_s[np.ix_(time_idx, nstagen_idx)]

        data.C_bus_static_generator = self.C_bus_static_generator[np.ix_(bus_idx, nstagen_idx)]

        return data

    def get_injections_per_bus(self):
        return self.C_bus_static_generator * (self.static_generator_s * self.static_generator_active).T

