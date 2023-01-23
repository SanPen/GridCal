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


class LoadData:

    def __init__(self, nload, nbus, ntime=1):
        """

        :param nload:
        :param nbus:
        :param ntime:
        """
        self.nload = nload
        self.ntime = ntime

        self.names = np.empty(nload, dtype=object)

        self.active = np.zeros((nload, ntime), dtype=bool)
        self.S = np.zeros((nload, ntime), dtype=complex)
        self.I = np.zeros((nload, ntime), dtype=complex)
        self.Y = np.zeros((nload, ntime), dtype=complex)

        self.C_bus_load = sp.lil_matrix((nbus, nload), dtype=int)

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

        data = LoadData(nload=len(elm_idx), nbus=len(bus_idx))

        data.names = self.names[elm_idx]

        data.active = self.active[tidx]
        data.S = self.S[tidx]
        data.I = self.I[tidx]
        data.Y = self.Y[tidx]

        data.C_bus_load = self.C_bus_load[np.ix_(bus_idx, elm_idx)]

        return data

    def get_island(self, bus_idx, t_idx=0):
        if self.nload:
            return tp.get_elements_of_the_island(self.C_bus_load.T, bus_idx,
                                                 active=self.active[t_idx])
        else:
            return np.zeros(0, dtype=int)

    def get_effective_load(self):
        return self.S * self.active

    def get_injections_per_bus(self):
        return - self.C_bus_load * self.get_effective_load()

    def get_current_injections_per_bus(self):
        return - self.C_bus_load * (self.I * self.active)

    def get_admittance_injections_per_bus(self):
        return - self.C_bus_load * (self.Y * self.active)

    def __len__(self):
        return self.nload


class LoadOpfData(LoadData):

    def __init__(self, nload, nbus, ntime=1):
        """

        :param nload:
        :param nbus:
        :param ntime:
        """
        LoadData.__init__(self, nload, nbus, ntime)

        self.load_cost = np.zeros((nload, ntime))

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

        data = LoadData(nload=len(elm_idx), nbus=len(bus_idx))

        data.names = self.names[elm_idx]

        data.active = self.active[tidx]
        data.S = self.S[tidx]
        data.load_cost = self.load_cost[tidx]

        data.C_bus_load = self.C_bus_load[np.ix_(bus_idx, elm_idx)]

        return data
