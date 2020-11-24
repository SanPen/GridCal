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


class GeneratorData:

    def __init__(self, ngen, nbus, ntime=1):
        """

        :param ngen:
        :param nbus:
        """
        self.ngen = ngen
        self.ntime = ntime

        self.generator_names = np.empty(ngen, dtype=object)

        self.generator_controllable = np.zeros(ngen, dtype=bool)
        self.generator_installed_p = np.zeros(ngen)

        self.generator_active = np.zeros((ngen, ntime), dtype=bool)
        self.generator_p = np.zeros((ngen, ntime))
        self.generator_pf = np.zeros((ngen, ntime))
        self.generator_v = np.zeros((ngen, ntime))

        self.generator_qmin = np.zeros(ngen)
        self.generator_qmax = np.zeros(ngen)

        self.C_bus_gen = sp.lil_matrix((nbus, ngen), dtype=int)

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

        data = GeneratorData(ngen=len(elm_idx), nbus=len(bus_idx))

        data.generator_names = self.generator_names[elm_idx]
        data.generator_controllable = self.generator_controllable[elm_idx]

        data.generator_active = self.generator_active[tidx]
        data.generator_p = self.generator_p[tidx]
        data.generator_pf = self.generator_pf[tidx]
        data.generator_v = self.generator_v[tidx]

        data.generator_qmin = self.generator_qmin[elm_idx]
        data.generator_qmax = self.generator_qmax[elm_idx]

        data.C_bus_gen = self.C_bus_gen[np.ix_(bus_idx, elm_idx)]

        return data

    def get_island(self, bus_idx):
        return tp.get_elements_of_the_island(self.C_bus_gen.T, bus_idx)

    def get_injections(self):
        """
        Compute the active and reactive power of non-controlled generators (assuming all)
        :return:
        """
        pf2 = np.power(self.generator_pf, 2.0)
        pf_sign = (self.generator_pf + 1e-20) / np.abs(self.generator_pf + 1e-20)
        Q = pf_sign * self.generator_p * np.sqrt((1.0 - pf2) / (pf2 + 1e-20))
        return self.generator_p + 1.0j * Q

    def get_injections_per_bus(self):
        return self.C_bus_gen * (self.get_injections() * self.generator_active)

    def get_installed_power_per_bus(self):
        return self.C_bus_gen * self.generator_installed_p

    def get_qmax_per_bus(self):
        return self.C_bus_gen * (self.generator_qmax.reshape(-1, 1) * self.generator_active)

    def get_qmin_per_bus(self):
        return self.C_bus_gen * (self.generator_qmin.reshape(-1, 1) * self.generator_active)

    def __len__(self):
        return self.ngen


class GeneratorOpfData(GeneratorData):

    def __init__(self, ngen, nbus, ntime=1):
        """

        :param ngen:
        :param nbus:
        :param ntime:
        """
        GeneratorData.__init__(self, ngen, nbus, ntime)

        self.generator_dispatchable = np.zeros(ngen, dtype=bool)
        self.generator_pmax = np.zeros(ngen)
        self.generator_pmin = np.zeros(ngen)
        self.generator_cost = np.zeros((ngen, ntime))

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

        data = GeneratorOpfData(ngen=len(elm_idx), nbus=len(bus_idx))

        data.generator_names = self.generator_names[elm_idx]
        data.generator_controllable = self.generator_controllable[elm_idx]
        data.generator_dispatchable = self.generator_dispatchable[elm_idx]

        data.generator_pmax = self.generator_pmax[elm_idx]
        data.generator_pmin = self.generator_pmin[elm_idx]

        data.generator_active = self.generator_active[tidx]
        data.generator_p = self.generator_p[tidx]
        data.generator_pf = self.generator_pf[tidx]
        data.generator_v = self.generator_v[tidx]
        data.generator_cost = self.generator_cost[tidx]

        data.generator_qmin = self.generator_qmin[elm_idx]
        data.generator_qmax = self.generator_qmax[elm_idx]

        data.C_bus_gen = self.C_bus_gen[np.ix_(bus_idx, elm_idx)]

        return data
