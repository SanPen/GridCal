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


class ShuntData:

    def __init__(self, nshunt, nbus, ntime=1):
        """

        :param nshunt:
        :param nbus:
        """
        self.nshunt = nshunt
        self.ntime = ntime

        self.shunt_names = np.empty(nshunt, dtype=object)

        self.shunt_active = np.zeros((nshunt, ntime), dtype=bool)
        self.shunt_admittance = np.zeros((nshunt, ntime), dtype=complex)

        self.shunt_controlled = np.zeros(nshunt, dtype=bool)
        self.shunt_b_min = np.zeros(nshunt, dtype=float)
        self.shunt_b_max = np.zeros(nshunt, dtype=float)

        self.C_bus_shunt = sp.lil_matrix((nbus, nshunt), dtype=int)

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

        data = ShuntData(nshunt=len(elm_idx), nbus=len(bus_idx))

        data.shunt_names = self.shunt_names[elm_idx]

        data.shunt_controlled = self.shunt_controlled[elm_idx]
        data.shunt_b_min = self.shunt_b_min[elm_idx]
        data.shunt_b_max = self.shunt_b_max[elm_idx]

        data.shunt_active = self.shunt_active[tidx]
        data.shunt_admittance = self.shunt_admittance[tidx]

        data.C_bus_shunt = self.C_bus_shunt[np.ix_(bus_idx, elm_idx)]

        return data

    def get_island(self, bus_idx):
        return tp.get_elements_of_the_island(self.C_bus_shunt.T, bus_idx)

    def get_controlled_per_bus(self):
        return self.C_bus_shunt * (self.shunt_controlled * self.shunt_active)

    def get_injections_per_bus(self):
        return self.C_bus_shunt * (self.shunt_admittance * self.shunt_active)

    def get_b_max_per_bus(self):
        return self.C_bus_shunt * (self.shunt_b_max.reshape(-1, 1) * self.shunt_active)

    def get_b_min_per_bus(self):
        return self.C_bus_shunt * (self.shunt_b_min.reshape(-1, 1) * self.shunt_active)

    def __len__(self):
        return self.nshunt

