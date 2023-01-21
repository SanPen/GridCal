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


class GeneratorData:

    def __init__(self, ngen, nbus, ntime=1):
        """

        :param ngen:
        :param nbus:
        """
        self.ngen = ngen
        self.ntime = ntime

        self.names = np.empty(ngen, dtype=object)

        self.controllable = np.zeros(ngen, dtype=bool)
        self.installed_p = np.zeros(ngen)

        self.active = np.zeros((ngen, ntime), dtype=bool)
        self.p = np.zeros((ngen, ntime))
        self.pf = np.zeros((ngen, ntime))
        self.v = np.zeros((ngen, ntime))

        self.qmin = np.zeros(ngen)
        self.qmax = np.zeros(ngen)

        self.C_bus_gen = sp.lil_matrix((nbus, ngen), dtype=int)

        # r0, r1, r2, x0, x1, x2
        self.r0 = np.zeros(ngen)
        self.r1 = np.zeros(ngen)
        self.r2 = np.zeros(ngen)

        self.x0 = np.zeros(ngen)
        self.x1 = np.zeros(ngen)
        self.x2 = np.zeros(ngen)

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

        data.names = self.names[elm_idx]
        data.controllable = self.controllable[elm_idx]

        data.active = self.active[tidx]
        data.p = self.p[tidx]
        data.pf = self.pf[tidx]
        data.v = self.v[tidx]

        data.qmin = self.qmin[elm_idx]
        data.qmax = self.qmax[elm_idx]

        data.C_bus_gen = self.C_bus_gen[np.ix_(bus_idx, elm_idx)]

        data.r0 = self.r0[elm_idx]
        data.r1 = self.r1[elm_idx]
        data.r2 = self.r2[elm_idx]

        data.x0 = self.x0[elm_idx]
        data.x1 = self.x1[elm_idx]
        data.x2 = self.x2[elm_idx]

        return data

    def get_island(self, bus_idx, t_idx=0):
        if self.ngen:
            return tp.get_elements_of_the_island(self.C_bus_gen.T, bus_idx,
                                                 active=self.active[t_idx])
        else:
            return np.zeros(0, dtype=int)

    def get_injections(self):
        """
        Compute the active and reactive power of non-controlled generators (assuming all)
        :return:
        """
        pf2 = np.power(self.pf, 2.0)
        pf_sign = (self.pf + 1e-20) / np.abs(self.pf + 1e-20)
        Q = pf_sign * self.p * np.sqrt((1.0 - pf2) / (pf2 + 1e-20))
        return self.p + 1.0j * Q

    def get_Yshunt(self, seq=1):
        """
        Obtain the vector of shunt admittances of a given sequence
        :param seq: sequence (0, 1 or 2)
        """
        if seq == 0:
            return self.C_bus_gen @ (1.0 / (self.r0 + 1j * self.x0))
        elif seq == 1:
            return self.C_bus_gen @ (1.0 / (self.r1 + 1j * self.x1))
        elif seq == 2:
            return self.C_bus_gen @ (1.0 / (self.r2 + 1j * self.x2))
        else:
            raise Exception('Sequence must be 0, 1, 2')

    def get_effective_generation(self):
        return self.p * self.active

    def get_injections_per_bus(self):
        return self.C_bus_gen * (self.get_injections() * self.active)

    def get_bus_indices(self):
        return self.C_bus_gen.tocsc().indices

    def get_voltages_per_bus(self):
        n_per_bus = self.C_bus_gen.sum(axis=1)
        n_per_bus[n_per_bus == 0] = 1  # replace the zeros by 1 to be able to divide
        # the division by n_per_bus achieves the averaging of the voltage control
        # value if more than 1 battery is present per bus
        # return self.C_bus_gen * (self.generator_v * self.generator_active) / n_per_bus
        return np.array((self.C_bus_gen * self.v) / n_per_bus)

    def get_installed_power_per_bus(self):
        return self.C_bus_gen * self.installed_p

    def get_qmax_per_bus(self):
        return self.C_bus_gen * (self.qmax.reshape(-1, 1) * self.active)

    def get_qmin_per_bus(self):
        return self.C_bus_gen * (self.qmin.reshape(-1, 1) * self.active)

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

        data.names = self.names[elm_idx]
        data.controllable = self.controllable[elm_idx]
        data.generator_dispatchable = self.generator_dispatchable[elm_idx]

        data.generator_pmax = self.generator_pmax[elm_idx]
        data.generator_pmin = self.generator_pmin[elm_idx]

        data.active = self.active[tidx]
        data.p = self.p[tidx]
        data.pf = self.pf[tidx]
        data.v = self.v[tidx]
        data.generator_cost = self.generator_cost[tidx]

        data.qmin = self.qmin[elm_idx]
        data.qmax = self.qmax[elm_idx]

        data.C_bus_gen = self.C_bus_gen[np.ix_(bus_idx, elm_idx)]

        return data
