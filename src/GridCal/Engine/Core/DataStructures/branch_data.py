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

        # composite losses curve (a * x^2 + b * x + c)
        self.a = np.zeros(self.nbr, dtype=float)
        self.b = np.zeros(self.nbr, dtype=float)
        self.c = np.zeros(self.nbr, dtype=float)

        self.R = np.zeros(self.nbr, dtype=float)
        self.X = np.zeros(self.nbr, dtype=float)
        self.G = np.zeros(self.nbr, dtype=float)
        self.B = np.zeros(self.nbr, dtype=float)
        self.m = np.ones(self.nbr, dtype=float)
        self.k = np.ones(self.nbr, dtype=float)
        self.theta = np.zeros(self.nbr, dtype=float)
        self.Beq = np.zeros(self.nbr, dtype=float)
        self.G0 = np.zeros(self.nbr, dtype=float)

        self.tap_t = np.ones(self.nbr, dtype=float)
        self.tap_f = np.ones(self.nbr, dtype=float)

        self.Pset = np.zeros(self.nbr)
        self.Qset = np.zeros(self.nbr)
        self.vf_set = np.ones(self.nbr)
        self.vt_set = np.ones(self.nbr)
        self.Kdp = np.ones(self.nbr)
        self.control_mode = np.zeros(self.nbr, dtype=object)

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

        data.R = self.R[br_idx]
        data.X = self.X[br_idx]
        data.G = self.G[br_idx]
        data.B = self.B[br_idx]
        data.m = self.m[br_idx]
        data.k = self.k[br_idx]
        data.theta = self.theta[br_idx]
        data.Beq = self.Beq[br_idx]
        data.G0 = self.G0[br_idx]

        data.tap_t = self.tap_f[br_idx]
        data.tap_f = self.tap_t[br_idx]

        data.Pset = self.Pset[br_idx]
        data.Qset = self.Qset[br_idx]
        data.vf_set = self.vf_set[br_idx]
        data.vt_set = self.vt_set[br_idx]
        data.Kdp = self.Kdp[br_idx]
        data.control_mode = self.control_mode[br_idx]

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
