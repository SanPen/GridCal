# GridCal
# Copyright (C) 2022 Santiago Peñate Vera
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

        self.names = np.empty(nshunt, dtype=object)

        self.active = np.zeros((nshunt, ntime), dtype=bool)
        self.admittance = np.zeros((nshunt, ntime), dtype=complex)

        self.controlled = np.zeros(nshunt, dtype=bool)
        self.b_min = np.zeros(nshunt, dtype=float)
        self.b_max = np.zeros(nshunt, dtype=float)

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

        data.names = self.names[elm_idx]

        data.controlled = self.controlled[elm_idx]
        data.b_min = self.b_min[elm_idx]
        data.b_max = self.b_max[elm_idx]

        data.active = self.active[tidx]
        data.admittance = self.admittance[tidx]

        data.C_bus_shunt = self.C_bus_shunt[np.ix_(bus_idx, elm_idx)]

        return data

    def get_island(self, bus_idx, t_idx=0):
        if self.nshunt:
            return tp.get_elements_of_the_island(self.C_bus_shunt.T, bus_idx, active=self.active[t_idx])
        else:
            return np.zeros(0, dtype=int)

    def get_controlled_per_bus(self):
        return self.C_bus_shunt * (self.controlled * self.active)

    def get_injections_per_bus(self):
        return self.C_bus_shunt * (self.admittance * self.active)

    def get_b_max_per_bus(self):
        return self.C_bus_shunt * (self.b_max.reshape(-1, 1) * self.active)

    def get_b_min_per_bus(self):
        return self.C_bus_shunt * (self.b_min.reshape(-1, 1) * self.active)

    def __len__(self):
        return self.nshunt

