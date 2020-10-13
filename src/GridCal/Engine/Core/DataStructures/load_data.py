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


class LoadData:

    def __init__(self, nload, nbus):
        """

        :param nload:
        :param nbus:
        """
        self.nload = nload

        self.load_names = np.empty(nload, dtype=object)
        self.load_active = np.zeros(nload, dtype=bool)
        self.load_s = np.zeros(nload, dtype=complex)

        self.C_bus_load = sp.lil_matrix((nbus, nload), dtype=int)

    def slice(self, load_idx, bus_idx):
        """

        :param load_idx:
        :param bus_idx:
        :return:
        """
        data = LoadData(nload=len(load_idx), nbus=len(bus_idx))

        data.load_names = self.load_names[load_idx]
        data.load_active = self.load_active[load_idx]
        data.load_s = self.load_s[load_idx]

        data.C_bus_load = self.C_bus_load[np.ix_(bus_idx, load_idx)]

        return data

    def get_island(self, bus_idx):
        return tp.get_elements_of_the_island(self.C_bus_load.T, bus_idx)

    def get_injections_per_bus(self):
        return - self.C_bus_load * (self.load_s * self.load_active)

    def __len__(self):
        return self.nload
