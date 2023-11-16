# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
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
import GridCalEngine.Core.topology as tp
from GridCalEngine.basic_structures import CxVec, Vec, IntVec, BoolVec, StrVec


class GeneratorData:
    """
    GeneratorData
    """

    def __init__(self, nelm: int, nbus: int):
        """
        Generator data arrays
        :param nelm: number of generator
        :param nbus: number of buses
        """
        self.nelm: int = nelm
        self.nbus: int = nbus

        self.names: StrVec = np.empty(nelm, dtype=object)
        self.idtag: StrVec = np.empty(nelm, dtype=object)

        self.controllable: BoolVec = np.zeros(nelm, dtype=bool)
        self.installed_p: Vec = np.zeros(nelm, dtype=float)

        self.active: BoolVec = np.zeros(nelm, dtype=bool)
        self.p: Vec = np.zeros(nelm, dtype=float)
        self.pf: Vec = np.zeros(nelm, dtype=float)
        self.v: Vec = np.zeros(nelm, dtype=float)

        self.qmin: Vec = np.zeros(nelm, dtype=float)
        self.qmax: Vec = np.zeros(nelm, dtype=float)

        self.C_bus_elm: sp.lil_matrix = sp.lil_matrix((nbus, nelm), dtype=int)

        # r0, r1, r2, x0, x1, x2
        self.r0: Vec = np.zeros(nelm, dtype=float)
        self.r1: Vec = np.zeros(nelm, dtype=float)
        self.r2: Vec = np.zeros(nelm, dtype=float)

        self.x0: Vec = np.zeros(nelm, dtype=float)
        self.x1: Vec = np.zeros(nelm, dtype=float)
        self.x2: Vec = np.zeros(nelm, dtype=float)

        self.dispatchable: BoolVec = np.zeros(nelm, dtype=bool)
        self.pmax: Vec = np.zeros(nelm, dtype=float)
        self.pmin: Vec = np.zeros(nelm, dtype=float)

        self.cost_1: Vec = np.zeros(nelm, dtype=float)
        self.cost_0: Vec = np.zeros(nelm, dtype=float)
        self.startup_cost: Vec = np.zeros(nelm, dtype=float)
        self.availability: Vec = np.zeros(nelm, dtype=float)
        self.ramp_up: Vec = np.zeros(nelm, dtype=float)
        self.ramp_down: Vec = np.zeros(nelm, dtype=float)
        self.min_time_up: Vec = np.zeros(nelm, dtype=float)
        self.min_time_down: Vec = np.zeros(nelm, dtype=float)

        self.original_idx = np.zeros(nelm, dtype=int)

    def slice(self, elm_idx: IntVec, bus_idx: IntVec):
        """
        Slice generator data by given indices
        :param elm_idx: array of element indices
        :param bus_idx: array of bus indices
        :return: new GeneratorData instance
        """

        data = GeneratorData(nelm=len(elm_idx), nbus=len(bus_idx))

        data.names = self.names[elm_idx]
        data.idtag = self.idtag[elm_idx]

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

        data.cost_0 = self.cost_0[elm_idx]
        data.cost_1 = self.cost_1[elm_idx]
        data.startup_cost = self.startup_cost[elm_idx]
        data.availability = self.availability[elm_idx]
        data.ramp_up = self.ramp_up[elm_idx]
        data.ramp_down = self.ramp_down[elm_idx]
        data.min_time_up = self.min_time_up[elm_idx]
        data.min_time_down = self.min_time_down[elm_idx]

        data.original_idx = elm_idx

        return data

    def copy(self):
        """
        Get a deep copy of this object
        :return: new GeneratorData instance
        """

        data = GeneratorData(nelm=self.nelm, nbus=self.nbus)

        data.names = self.names.copy()
        data.idtag = self.idtag.copy()

        data.controllable = self.controllable.copy()
        data.installed_p = self.installed_p.copy()

        data.active = self.active.copy()
        data.p = self.p.copy()
        data.pf = self.pf.copy()
        data.v = self.v.copy()

        data.qmin = self.qmin.copy()
        data.qmax = self.qmax.copy()

        data.C_bus_elm = self.C_bus_elm.copy()

        data.r0 = self.r0.copy()
        data.r1 = self.r1.copy()
        data.r2 = self.r2.copy()

        data.x0 = self.x0.copy()
        data.x1 = self.x1.copy()
        data.x2 = self.x2.copy()

        data.dispatchable = self.dispatchable.copy()
        data.pmax = self.pmax.copy()
        data.pmin = self.pmin.copy()

        data.cost_0 = self.cost_0.copy()
        data.cost_1 = self.cost_1.copy()
        data.startup_cost = self.startup_cost.copy()
        data.availability = self.availability.copy()
        data.ramp_up = self.ramp_up.copy()
        data.ramp_down = self.ramp_down.copy()
        data.min_time_up = self.min_time_up.copy()
        data.min_time_down = self.min_time_down.copy()

        data.original_idx = self.original_idx

        return data

    def get_island(self, bus_idx: IntVec) -> IntVec:
        """
        Get the array of generator indices that belong to the islands given by the bus indices
        :param bus_idx: array of bus indices
        :return: array of generator indices of the island given by bus_idx
        """
        if self.nelm:
            return tp.get_elements_of_the_island(self.C_bus_elm.T, bus_idx, active=self.active)
        else:
            return np.zeros(0, dtype=int)

    def get_injections(self) -> CxVec:
        """
        Compute the active and reactive power of non-controlled generators (assuming all)
        :return:
        """
        pf2 = np.power(self.pf, 2.0)
        pf_sign = (self.pf + 1e-20) / np.abs(self.pf + 1e-20)
        Q = pf_sign * self.p * np.sqrt((1.0 - pf2) / (pf2 + 1e-20))
        return self.p + 1.0j * Q

    def get_Yshunt(self, seq: int = 1) -> CxVec:
        """
        Obtain the vector of shunt admittances of a given sequence per bus
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

    def get_effective_generation(self) -> Vec:
        """
        Get generator effective power
        :return:
        """
        return self.p * self.active

    def get_injections_per_bus(self) -> CxVec:
        """
        Get generator Injections per bus
        :return:
        """
        return self.C_bus_elm * (self.get_injections() * self.active)

    def get_bus_indices(self) -> IntVec:
        """
        Get generator bus indices
        :return:
        """
        return self.C_bus_elm.tocsc().indices

    def get_voltages_per_bus(self) -> CxVec:
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

    def get_installed_power_per_bus(self) -> Vec:
        """
        Get generator installed power per bus
        :return:
        """
        return self.C_bus_elm * self.installed_p

    def get_qmax_per_bus(self) -> Vec:
        """
        Get generator Qmax per bus
        :return:
        """
        return self.C_bus_elm * (self.qmax * self.active)

    def get_qmin_per_bus(self) -> Vec:
        """
        Get generator Qmin per bus
        :return:
        """
        return self.C_bus_elm * (self.qmin * self.active)

    def __len__(self) -> int:
        """
        Get generator count
        :return:
        """
        return self.nelm

    def get_bus_indices(self) -> IntVec:
        """
        Get the bus indices
        :return: array with the bus indices
        """
        return tp.get_csr_bus_indices(self.C_bus_elm.tocsr())
