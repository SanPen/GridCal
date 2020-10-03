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


class BranchData:

    def __init__(self, nbr, nbus):
        """

        :param nbr:
        :param nbus:
        """
        self.nbr = nbr

        self.branch_names = np.empty(self.nbr, dtype=object)
        self.branch_active = np.zeros(self.nbr, dtype=int)
        self.F = np.zeros(self.nbr, dtype=int)  # indices of the "from" buses
        self.T = np.zeros(self.nbr, dtype=int)  # indices of the "to" buses
        self.branch_rates = np.zeros(self.nbr, dtype=float)
        self.C_branch_bus_f = sp.lil_matrix((self.nbr, nbus), dtype=int)  # connectivity branch with their "from" bus
        self.C_branch_bus_t = sp.lil_matrix((self.nbr, nbus), dtype=int)  # connectivity branch with their "to" bus

    def slice(self, br_idx, bus_idx):
        """

        :param br_idx:
        :param bus_idx:
        :return:
        """
        data = BranchData(nbr=len(br_idx), nbus=len(bus_idx))

        data.branch_names = self.branch_names[br_idx]
        data.branch_active = self.branch_active[br_idx]
        data.F = self.F[br_idx]
        data.T = self.T[br_idx]
        data.branch_rates = self.branch_rates[br_idx]
        data.C_branch_bus_f = self.C_branch_bus_f[np.ix_(br_idx, bus_idx)]
        data.C_branch_bus_t = self.C_branch_bus_t[np.ix_(br_idx, bus_idx)]

        return data

    def get_island(self, bus_idx):
        """

        :param bus_idx:
        :return:
        """
        return tp.get_elements_of_the_island(self.C_branch_bus_f + self.C_branch_bus_t, bus_idx)

    def __len__(self):
        return self.nbr
