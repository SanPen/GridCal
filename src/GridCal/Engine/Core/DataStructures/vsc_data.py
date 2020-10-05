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


class VscData:

    def __init__(self, nvsc, nbus):
        """

        :param nvsc:
        :param nbus:
        """
        self.nvsc = nvsc

        self.vsc_names = np.zeros(nvsc, dtype=object)
        self.vsc_R1 = np.zeros(nvsc)
        self.vsc_X1 = np.zeros(nvsc)
        self.vsc_G0 = np.zeros(nvsc)
        self.vsc_Beq = np.zeros(nvsc)
        self.vsc_m = np.zeros(nvsc)
        self.vsc_theta = np.zeros(nvsc)
        self.vsc_Inom = np.zeros(nvsc)
        self.vsc_Pset = np.zeros(nvsc)
        self.vsc_Qset = np.zeros(nvsc)
        self.vsc_Vac_set = np.ones(nvsc)
        self.vsc_Vdc_set = np.ones(nvsc)
        self.vsc_control_mode = np.zeros(nvsc, dtype=object)

        self.C_vsc_bus = sp.lil_matrix((nvsc, nbus), dtype=int)  # this ons is just for splitting islands

    def slice(self, vsc_idx, bus_idx):
        """

        :param vsc_idx:
        :param bus_idx:
        :return:
        """

        nc = VscData(nvsc=len(vsc_idx), nbus=len(bus_idx))

        nc.vsc_names = self.vsc_names[vsc_idx]
        nc.vsc_R1 = self.vsc_R1[vsc_idx]
        nc.vsc_X1 = self.vsc_X1[vsc_idx]
        nc.vsc_G0 = self.vsc_G0[vsc_idx]
        nc.vsc_Beq = self.vsc_Beq[vsc_idx]
        nc.vsc_m = self.vsc_m[vsc_idx]
        nc.vsc_theta = self.vsc_theta[vsc_idx]
        nc.vsc_Inom = self.vsc_Inom[vsc_idx]
        nc.vsc_Pset = self.vsc_Pset[vsc_idx]
        nc.vsc_Qset = self.vsc_Qset[vsc_idx]
        nc.vsc_Vac_set = self.vsc_Vac_set[vsc_idx]
        nc.vsc_Vdc_set = self.vsc_Vdc_set[vsc_idx]
        nc.vsc_control_mode = self.vsc_control_mode[vsc_idx]

        nc.C_vsc_bus = self.C_vsc_bus[np.ix_(vsc_idx, bus_idx)]

        return nc

    def get_island(self, bus_idx):
        """
        Get the elements of the island given the bus indices
        :param bus_idx: list of bus indices
        :return: list of line indices of the island
        """
        return tp.get_elements_of_the_island(self.C_vsc_bus, bus_idx)

    def __len__(self):
        return self.nvsc


class VscTimeData(VscData):

    def __init__(self, nvsc, nbus, ntime):
        VscData.__init__(self, nvsc, nbus)

        self.ntime = ntime
