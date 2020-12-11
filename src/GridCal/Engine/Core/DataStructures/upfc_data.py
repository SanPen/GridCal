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


class UpfcData:

    def __init__(self, nelm, nbus, ntime=1):
        """

        :param nelm:
        :param nbus:
        :param ntime:
        """
        self.nelm = nelm
        self.ntime = ntime

        self.names = np.zeros(nelm, dtype=object)
        self.Rl = np.zeros(nelm)
        self.Xl = np.zeros(nelm)
        self.Bl = np.zeros(nelm)

        self.Rs = np.zeros(nelm)
        self.Xs = np.zeros(nelm)

        self.Rsh = np.zeros(nelm)
        self.Xsh = np.zeros(nelm)

        self.Vsh = np.zeros((nelm, ntime))
        self.Pset = np.zeros((nelm, ntime))
        self.Qset = np.zeros((nelm, ntime))

        self.C_elm_bus = sp.lil_matrix((nelm, nbus), dtype=int)  # this ons is just for splitting islands

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

        data = UpfcData(nelm=len(elm_idx), nbus=len(bus_idx))

        data.names = self.names[elm_idx]
        data.Rl = self.Rl[elm_idx]
        data.Xl = self.Xl[elm_idx]
        data.Bl = self.Bl[elm_idx]

        data.Rs = self.Rs[elm_idx]
        data.Xs = self.Xs[elm_idx]

        data.Rsh = self.Rsh[elm_idx]
        data.Xsh = self.Xsh[elm_idx]

        data.Pset = self.Pset[tidx]
        data.Qset = self.Qset[tidx]
        data.Vsh = self.Vsh[tidx]

        data.C_elm_bus = self.C_elm_bus[np.ix_(elm_idx, bus_idx)]

        return data

    def get_island(self, bus_idx):
        """
        Get the elements of the island given the bus indices
        :param bus_idx: list of bus indices
        :return: list of line indices of the island
        """
        return tp.get_elements_of_the_island(self.C_elm_bus, bus_idx)

    def __len__(self):
        return self.nelm
