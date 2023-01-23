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


class DcLinesData:

    def __init__(self, ndcline, nbus, ntime=1):
        """

        :param ndcline:
        :param nbus:
        """
        self.ndcline = ndcline
        self.ntime = ntime

        self.names = np.zeros(ndcline, dtype=object)
        self.active = np.zeros((ndcline, ntime), dtype=int)
        self.R = np.zeros(ndcline, dtype=float)
        self.temp_base = np.zeros(ndcline, dtype=float)
        self.temp_oper = np.zeros(ndcline, dtype=float)
        self.alpha = np.zeros(ndcline, dtype=float)
        self.impedance_tolerance = np.zeros(ndcline, dtype=float)

        self.C_dc_line_bus = sp.lil_matrix((ndcline, nbus), dtype=int)  # this ons is just for splitting islands
        self.F = np.zeros(ndcline, dtype=int)
        self.T = np.zeros(ndcline, dtype=int)

    def slice(self, dc_line_idx, bus_idx, time_idx=None):
        """

        :param dc_line_idx:
        :param bus_idx:
        :param time_idx:
        :return:
        """

        data = DcLinesData(ndcline=len(dc_line_idx), nbus=len(bus_idx))

        data.names = self.names[dc_line_idx]
        data.R = self.R[dc_line_idx]
        data.temp_base = self.temp_base[dc_line_idx]
        data.temp_oper = self.temp_oper[dc_line_idx]
        data.alpha = self.alpha[dc_line_idx]
        data.impedance_tolerance = self.impedance_tolerance[dc_line_idx]

        data.C_dc_line_bus = self.C_dc_line_bus[np.ix_(dc_line_idx, bus_idx)]
        data.F = self.F[dc_line_idx]
        data.T = self.T[dc_line_idx]

        return data

    def get_island(self, bus_idx, t_idx=0):
        """
        Get the elements of the island given the bus indices
        :param bus_idx: list of bus indices
        :return: list of line indices of the island
        """
        if self.ndcline:
            # the active status comes in branches data
            return tp.get_elements_of_the_island(self.C_dc_line_bus, bus_idx, active=self.active[:, t_idx])
        else:
            return np.zeros(0, dtype=int)

    def DC_R_corrected(self):
        """
        Returns temperature corrected resistances (numpy array) based on a formula
        provided by: NFPA 70-2005, National Electrical Code, Table 8, footnote #2; and
        https://en.wikipedia.org/wiki/Electrical_resistivity_and_conductivity#Linear_approximation
        (version of 2019-01-03 at 15:20 EST).
        """
        return self.R * (1.0 + self.alpha * (self.temp_oper - self.temp_base))

    def __len__(self):
        return self.ndcline
