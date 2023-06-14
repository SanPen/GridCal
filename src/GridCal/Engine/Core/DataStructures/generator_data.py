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

    def __init__(
            self,
            nelm: int,
            nbus: int,
    ):
        """
        Generator data arrays
        :param nelm: number of generator
        :param nbus: number of buses
        :param ntime: time index
        """
        self.nelm: int = nelm

        self.names: np.ndarray = np.empty(nelm, dtype=object)

        self.controllable: np.ndarray = np.zeros(nelm, dtype=bool)
        self.installed_p: np.ndarray = np.zeros(nelm, dtype=float)

        self.active: np.ndarray = np.zeros(nelm, dtype=bool)
        self.p: np.ndarray = np.zeros(nelm, dtype=float)
        self.pf: np.ndarray = np.zeros(nelm, dtype=float)
        self.v: np.ndarray = np.zeros(nelm, dtype=float)

        self.qmin: np.ndarray = np.zeros(nelm, dtype=float)
        self.qmax: np.ndarray = np.zeros(nelm, dtype=float)

        self.C_bus_elm: sp.lil_matrix = sp.lil_matrix((nbus, nelm), dtype=int)

        # r0, r1, r2, x0, x1, x2
        self.r0: np.ndarray = np.zeros(nelm, dtype=float)
        self.r1: np.ndarray = np.zeros(nelm, dtype=float)
        self.r2: np.ndarray = np.zeros(nelm, dtype=float)

        self.x0: np.ndarray = np.zeros(nelm, dtype=float)
        self.x1: np.ndarray = np.zeros(nelm, dtype=float)
        self.x2: np.ndarray = np.zeros(nelm, dtype=float)

        self.dispatchable: np.ndarray = np.zeros(nelm, dtype=bool)
        self.pmax: np.ndarray = np.zeros(nelm, dtype=float)
        self.pmin: np.ndarray = np.zeros(nelm, dtype=float)
        self.cost: np.ndarray = np.zeros(nelm, dtype=float)

        self.original_idx = np.zeros(nelm, dtype=int)

    def slice(
            self,
            elm_idx: np.ndarray,
            bus_idx: np.ndarray
    ):
        """
        Slice generator data by given indices
        :param elm_idx: array of element indices
        :param bus_idx: array of bus indices
        :return: new GeneratorData instance
        """

        data = GeneratorData(nelm=len(elm_idx), nbus=len(bus_idx))

        data.names = self.names[elm_idx]

        data.controllable = self.controllable[elm_idx]
        data.installed_p = self.installed_p[elm_idx]

        data.active = self.active[elm_idx]
        data.p = self.p[elm_idx]
        data.pf = self.pf[elm_idx]
        data.v = self.v[elm_idx]

        data.qmin = self.qmin[elm_idx]
        data.qmax = self.qmax[elm_idx]

        data.C_bus_elm = self.C_bus_elm[np.ix_(bus_idx, elm_idx)]

        data.r0 = self.r0[elm_idx]
        data.r1 = self.r1[elm_idx]
        data.r2 = self.r2[elm_idx]

        data.x0 = self.x0[elm_idx]
        data.x1 = self.x1[elm_idx]
        data.x2 = self.x2[elm_idx]

        data.dispatchable = self.dispatchable[elm_idx]
        data.pmax = self.pmax[elm_idx]
        data.pmin = self.pmin[elm_idx]
        data.cost = self.cost[elm_idx]

        data.original_idx = elm_idx

        return data

    def get_island(
            self,
            bus_idx: np.ndarray,
    ):
        """
        Get the array of generator indices that belong to the islands given by the bus indices
        :param bus_idx: array of bus indices
        :return:
        """
        if self.nelm:
            return tp.get_elements_of_the_island(
                self.C_bus_elm.T, bus_idx, active=self.active)
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

    def get_Yshunt(
            self,
            seq: int=1
    ):
        """
        Obtain the vector of shunt admittances of a given sequence
        :param seq: sequence (0, 1 or 2)
        """
        if seq == 0:
            return self.C_bus_elm @ (1.0 / (self.r0 + 1j * self.x0))
        elif seq == 1:
            return self.C_bus_elm @ (1.0 / (self.r1 + 1j * self.x1))
        elif seq == 2:
            return self.C_bus_elm @ (1.0 / (self.r2 + 1j * self.x2))
        else:
            raise Exception('Sequence must be 0, 1, 2')

    def get_effective_generation(self):
        """
        Get generator effective power
        :return:
        """
        return self.p * self.active

    def get_injections_per_bus(self):
        """
        Get generator injections per bus
        :return:
        """
        return self.C_bus_elm * (self.get_injections() * self.active)

    def get_bus_indices(self):
        """
        Get generator bus indices
        :return:
        """
        return self.C_bus_elm.tocsc().indices

    def get_voltages_per_bus(self):
        """
        Get generator voltages per bus
        :return:
        """
        n_per_bus = self.C_bus_elm.sum(axis=1)
        n_per_bus[n_per_bus == 0] = 1  # replace the zeros by 1 to be able to divide
        # the division by n_per_bus achieves the averaging of the voltage control
        # value if more than 1 battery is present per bus
        # return self.C_bus_gen * (self.generator_v * self.generator_active) / n_per_bus
        return np.ndarray((self.C_bus_elm * self.v) / n_per_bus)

    def get_installed_power_per_bus(self):
        """
        Get generator installed power per bus
        :return:
        """
        return self.C_bus_elm * self.installed_p

    def get_qmax_per_bus(self):
        """
        Get generator Qmax per bus
        :return:
        """
        return self.C_bus_elm * (self.qmax * self.active)

    def get_qmin_per_bus(self):
        """
        Get generator Qmin per bus
        :return:
        """
        return self.C_bus_elm * (self.qmin * self.active)

    def __len__(self):
        """
        Get generator count
        :return:
        """
        return self.nelm


