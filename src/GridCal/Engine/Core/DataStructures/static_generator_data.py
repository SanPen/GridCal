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

    def __init__(self, nstagen, nbus, ntime=1):
        """

        :param nstagen:
        :param nbus:
        """
        self.nstagen = nstagen
        self.ntime = ntime

        self.static_generator_names = np.empty(nstagen, dtype=object)

        self.static_generator_active = np.zeros((nstagen, ntime), dtype=bool)
        self.static_generator_s = np.zeros((nstagen, ntime), dtype=complex)

        self.C_bus_static_generator = sp.lil_matrix((nbus, nstagen), dtype=int)

    def slice(self, elm_idx, bus_idx, time_idx=None):
        """

        :param elm_idx:
        :param bus_idx:
        :param time_idx: 
        :return:
        """
        if time_idx is None:
            tidx = elm_idx
        else:
            tidx = np.ix_(elm_idx, time_idx)

        data = StaticGeneratorData(nstagen=len(elm_idx), nbus=len(bus_idx))
        data.static_generator_names = self.static_generator_names[elm_idx]

        data.static_generator_active = self.static_generator_active[tidx]
        data.static_generator_s = self.static_generator_s[tidx]

        data.C_bus_static_generator = self.C_bus_static_generator[np.ix_(bus_idx, elm_idx)]

        return data

    def get_island(self, bus_idx):
        return tp.get_elements_of_the_island(self.C_bus_static_generator.T, bus_idx)

    def get_injections_per_bus(self):
        return self.C_bus_static_generator * (self.static_generator_s * self.static_generator_active)

    def __len__(self):
        return self.nstagen
