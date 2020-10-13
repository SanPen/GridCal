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


class LinesData:

    def __init__(self, nline, nbus, ntime=1):
        """

        :param nline:
        :param nbus:
        """
        self.nline = nline
        self.ntime = ntime

        self.line_names = np.zeros(nline, dtype=object)
        self.line_R = np.zeros(nline, dtype=float)
        self.line_X = np.zeros(nline, dtype=float)
        self.line_B = np.zeros(nline, dtype=float)

        self.C_line_bus = sp.lil_matrix((nline, nbus), dtype=int)  # this ons is just for splitting islands

    def slice(self, elm_idx, bus_idx, time_idx=None):
        """

        :param elm_idx:
        :param bus_idx:
        :return:
        """

        data = LinesData(nline=len(elm_idx), nbus=len(bus_idx))

        data.line_names = self.line_names[elm_idx]
        data.line_R = self.line_R[elm_idx]
        data.line_X = self.line_X[elm_idx]
        data.line_B = self.line_B[elm_idx]
        data.C_line_bus = self.C_line_bus[np.ix_(elm_idx, bus_idx)]

        return data

    def get_island(self, bus_idx):
        """
        Get the elements of the island given the bus indices
        :param bus_idx: list of bus indices
        :return: list of line indices of the island
        """
        return tp.get_elements_of_the_island(self.C_line_bus, bus_idx)

    def __len__(self):
        return self.nline

