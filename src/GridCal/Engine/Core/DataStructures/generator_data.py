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

    def __init__(self, ngen, nbus):
        """

        :param ngen:
        :param nbus:
        """
        self.ngen = ngen

        self.generator_names = np.empty(ngen, dtype=object)
        self.generator_active = np.zeros(ngen, dtype=bool)
        self.generator_controllable = np.zeros(ngen, dtype=bool)
        self.generator_installed_p = np.zeros(ngen)
        self.generator_p = np.zeros(ngen)
        self.generator_pf = np.zeros(ngen)
        self.generator_v = np.zeros(ngen)
        self.generator_qmin = np.zeros(ngen)
        self.generator_qmax = np.zeros(ngen)

        self.C_bus_gen = sp.lil_matrix((nbus, ngen), dtype=int)

    def slice(self, gen_idx, bus_idx):
        """

        :param gen_idx:
        :param bus_idx:
        :return:
        """
        data = GeneratorData(ngen=len(gen_idx), nbus=len(bus_idx))

        data.generator_names = self.generator_names[gen_idx]
        data.generator_active = self.generator_active[gen_idx]
        data.generator_controllable = self.generator_controllable[gen_idx]
        data.generator_p = self.generator_p[gen_idx]
        data.generator_pf = self.generator_pf[gen_idx]
        data.generator_v = self.generator_v[gen_idx]
        data.generator_qmin = self.generator_qmin[gen_idx]
        data.generator_qmax = self.generator_qmax[gen_idx]

        data.C_bus_gen = self.C_bus_gen[np.ix_(bus_idx, gen_idx)]

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
        return self.C_bus_gen * (self.generator_qmax * self.generator_active)

    def get_qmin_per_bus(self):
        return self.C_bus_gen * (self.generator_qmin * self.generator_active)

    def __len__(self):
        return self.ngen


class GeneratorTimeData(GeneratorData):

    def __init__(self, ngen, nbus, ntime):
        GeneratorData.__init__(self, ngen, nbus)

        self.ntime = ntime

        self.generator_active = np.zeros((ntime, ngen), dtype=bool)
        self.generator_p = np.zeros((ntime, ngen))
        self.generator_pf = np.zeros((ntime, ngen))
        self.generator_v = np.zeros((ntime, ngen))

    def slice_time(self, gen_idx, bus_idx, time_idx):
        """

        :param gen_idx:
        :param bus_idx:
        :param time_idx:
        :return:
        """
        data = GeneratorTimeData(ngen=len(gen_idx), nbus=len(bus_idx), ntime=len(time_idx))

        data.generator_names = self.generator_names[gen_idx]
        data.generator_controllable = self.generator_controllable[gen_idx]
        data.generator_qmin = self.generator_qmin[gen_idx]
        data.generator_qmax = self.generator_qmax[gen_idx]

        data.generator_active = self.generator_active[np.ix_(time_idx, gen_idx)]
        data.generator_p = self.generator_p[np.ix_(time_idx, gen_idx)]
        data.generator_pf = self.generator_pf[np.ix_(time_idx, gen_idx)]
        data.generator_v = self.generator_v[np.ix_(time_idx, gen_idx)]

        data.C_bus_gen = self.C_bus_gen[np.ix_(bus_idx, gen_idx)]

        return data

    def get_injections_per_bus(self):
        return self.C_bus_gen * (self.get_injections() * self.generator_active).T
