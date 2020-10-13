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


class ShuntData:

    def __init__(self, nshunt, nbus):
        """

        :param nshunt:
        :param nbus:
        """
        self.nshunt = nshunt

        self.shunt_names = np.empty(nshunt, dtype=object)
        self.shunt_active = np.zeros(nshunt, dtype=bool)
        self.shunt_admittance = np.zeros(nshunt, dtype=complex)

        self.C_bus_shunt = sp.lil_matrix((nbus, nshunt), dtype=int)

    def slice(self, shunt_idx, bus_idx):
        """

        :param shunt_idx:
        :param bus_idx:
        :return:
        """
        data = ShuntData(nshunt=len(shunt_idx), nbus=len(bus_idx))

        data.shunt_names = self.shunt_names[shunt_idx]
        data.shunt_active = self.shunt_active[shunt_idx]
        data.shunt_admittance = self.shunt_admittance[shunt_idx]

        data.C_bus_shunt = self.C_bus_shunt[np.ix_(bus_idx, shunt_idx)]

        return data

    def get_island(self, bus_idx):
        return tp.get_elements_of_the_island(self.C_bus_shunt.T, bus_idx)

    def get_injections_per_bus(self):
        return self.C_bus_shunt * (self.shunt_admittance * self.shunt_active)

    def __len__(self):
        return self.nshunt
