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


class VscData:

    def __init__(self, nvsc, nbus, ntime=1):
        """

        :param nvsc:
        :param nbus:
        """
        self.nvsc = nvsc
        self.ntime = ntime

        self.names = np.zeros(nvsc, dtype=object)
        self.R1 = np.zeros(nvsc)
        self.X1 = np.zeros(nvsc)
        self.G0 = np.zeros(nvsc)
        self.Beq = np.zeros(nvsc)
        self.m = np.zeros(nvsc)
        self.theta = np.zeros(nvsc)
        self.Inom = np.zeros(nvsc)

        self.active = np.zeros((nvsc, ntime), dtype=int)
        self.Pfset = np.zeros((nvsc, ntime))  # DC active power
        self.Qtset = np.zeros((nvsc, ntime))  # AC reactive power
        self.Vac_set = np.ones((nvsc, ntime))
        self.Vdc_set = np.ones((nvsc, ntime))

        self.control_mode = np.zeros(nvsc, dtype=object)

        self.C_vsc_bus = sp.lil_matrix((nvsc, nbus), dtype=int)  # this ons is just for splitting islands

    def slice(self, elm_idx, bus_idx, time_idx=None):
        """

        :param elm_idx:
        :param bus_idx:
        :return:
        """

        if time_idx is None:
            tidx = elm_idx
        else:
            tidx = np.ix_(elm_idx, time_idx)

        nc = VscData(nvsc=len(elm_idx), nbus=len(bus_idx))

        nc.names = self.names[elm_idx]
        nc.R1 = self.R1[elm_idx]
        nc.X1 = self.X1[elm_idx]
        nc.G0 = self.G0[elm_idx]
        nc.Beq = self.Beq[elm_idx]
        nc.m = self.m[elm_idx]
        nc.theta = self.theta[elm_idx]
        nc.Inom = self.Inom[elm_idx]

        nc.active = self.active[tidx]
        nc.Pfset = self.Pfset[tidx]
        nc.Qtset = self.Qtset[tidx]
        nc.Vac_set = self.Vac_set[tidx]
        nc.Vdc_set = self.Vdc_set[tidx]

        nc.control_mode = self.control_mode[elm_idx]

        nc.C_vsc_bus = self.C_vsc_bus[np.ix_(elm_idx, bus_idx)]

        return nc

    def get_island(self, bus_idx, t_idx=0):
        """
        Get the elements of the island given the bus indices
        :param bus_idx: list of bus indices
        :return: list of line indices of the island
        """
        if self.nvsc:
            return tp.get_elements_of_the_island(self.C_vsc_bus, bus_idx, active=self.active[:, t_idx])
        else:
            return np.zeros(0, dtype=int)

    def get_bus_indices_f(self):
        return self.C_vsc_bus.tocsc().indices

    def get_bus_indices_t(self):
        return self.C_vsc_bus.tocsc().indices

    def __len__(self):
        return self.nvsc
