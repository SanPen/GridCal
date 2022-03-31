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

        self.dc_line_names = np.zeros(ndcline, dtype=object)
        self.dc_line_active = np.zeros((ndcline, ntime), dtype=int)
        self.dc_line_R = np.zeros(ndcline, dtype=float)
        self.dc_line_temp_base = np.zeros(ndcline, dtype=float)
        self.dc_line_temp_oper = np.zeros(ndcline, dtype=float)
        self.dc_line_alpha = np.zeros(ndcline, dtype=float)
        self.dc_line_impedance_tolerance = np.zeros(ndcline, dtype=float)

        self.C_dc_line_bus = sp.lil_matrix((ndcline, nbus), dtype=int)  # this ons is just for splitting islands
        self.dc_F = np.zeros(ndcline, dtype=int)
        self.dc_T = np.zeros(ndcline, dtype=int)

    def slice(self, dc_line_idx, bus_idx, time_idx=None):
        """

        :param dc_line_idx:
        :param bus_idx:
        :param time_idx:
        :return:
        """

        data = DcLinesData(ndcline=len(dc_line_idx), nbus=len(bus_idx))

        data.dc_line_names = self.dc_line_names[dc_line_idx]
        data.dc_line_R = self.dc_line_R[dc_line_idx]
        data.dc_line_temp_base = self.dc_line_temp_base[dc_line_idx]
        data.dc_line_temp_oper = self.dc_line_temp_oper[dc_line_idx]
        data.dc_line_alpha = self.dc_line_alpha[dc_line_idx]
        data.dc_line_impedance_tolerance = self.dc_line_impedance_tolerance[dc_line_idx]

        data.C_dc_line_bus = self.C_dc_line_bus[np.ix_(dc_line_idx, bus_idx)]
        data.dc_F = self.dc_F[dc_line_idx]
        data.dc_T = self.dc_T[dc_line_idx]

        return data

    def get_island(self, bus_idx, t_idx=0):
        """
        Get the elements of the island given the bus indices
        :param bus_idx: list of bus indices
        :return: list of line indices of the island
        """
        if self.ndcline:
            # the active status comes in branches data
            return tp.get_elements_of_the_island(self.C_dc_line_bus, bus_idx, active=self.dc_line_active[:, t_idx])
        else:
            return np.zeros(0, dtype=int)

    def DC_R_corrected(self):
        """
        Returns temperature corrected resistances (numpy array) based on a formula
        provided by: NFPA 70-2005, National Electrical Code, Table 8, footnote #2; and
        https://en.wikipedia.org/wiki/Electrical_resistivity_and_conductivity#Linear_approximation
        (version of 2019-01-03 at 15:20 EST).
        """
        return self.dc_line_R * (1.0 + self.dc_line_alpha * (self.dc_line_temp_oper - self.dc_line_temp_base))

    def __len__(self):
        return self.ndcline
