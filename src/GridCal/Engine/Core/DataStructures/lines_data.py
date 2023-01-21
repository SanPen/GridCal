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


class LinesData:

    def __init__(self, nline, nbus, ntime=1):
        """

        :param nline:
        :param nbus:
        """
        self.nline = nline
        self.ntime = ntime

        self.names = np.zeros(nline, dtype=object)
        self.active = np.zeros((nline, ntime), dtype=int)
        self.R = np.zeros(nline, dtype=float)
        self.X = np.zeros(nline, dtype=float)
        self.B = np.zeros(nline, dtype=float)

        self.C_line_bus = sp.lil_matrix((nline, nbus), dtype=int)  # this ons is just for splitting islands

    def slice(self, elm_idx, bus_idx, time_idx=None):
        """

        :param elm_idx:
        :param bus_idx:
        :return:
        """

        if time_idx is None:
            idx = elm_idx
        else:
            idx = np.ix_(elm_idx, time_idx)

        data = LinesData(nline=len(elm_idx), nbus=len(bus_idx))

        data.active = self.active[idx]

        data.names = self.names[elm_idx]

        data.R = self.R[elm_idx]
        data.X = self.X[elm_idx]
        data.B = self.B[elm_idx]
        data.C_line_bus = self.C_line_bus[np.ix_(elm_idx, bus_idx)]

        return data

    def get_island(self, bus_idx, t_idx=0):
        """
        Get the elements of the island given the bus indices
        :param bus_idx: list of bus indices
        :return: list of line indices of the island
        """
        if self.nline:
            return tp.get_elements_of_the_island(self.C_line_bus, bus_idx,
                                                 active=self.active[:, t_idx])
        else:
            return np.zeros(0, dtype=int)

    def __len__(self):
        return self.nline

