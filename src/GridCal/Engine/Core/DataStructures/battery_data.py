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


class BatteryData:

    def __init__(self, nbatt, nbus, ntime=1):
        """

        :param nbatt:
        :param nbus:
        """
        self.nbatt = nbatt
        self.ntime = ntime

        self.names = np.empty(nbatt, dtype=object)

        self.controllable = np.zeros(nbatt, dtype=bool)
        self.installed_p = np.zeros(nbatt)

        self.active = np.zeros((nbatt, ntime), dtype=bool)
        self.p = np.zeros((nbatt, ntime))
        self.pf = np.zeros((nbatt, ntime))
        self.v = np.zeros((nbatt, ntime))

        self.qmin = np.zeros(nbatt)
        self.qmax = np.zeros(nbatt)

        self.C_bus_batt = sp.lil_matrix((nbus, nbatt), dtype=int)

        # r0, r1, r2, x0, x1, x2
        self.r0 = np.zeros(nbatt)
        self.r1 = np.zeros(nbatt)
        self.r2 = np.zeros(nbatt)

        self.x0 = np.zeros(nbatt)
        self.x1 = np.zeros(nbatt)
        self.x2 = np.zeros(nbatt)

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

        data = BatteryData(nbatt=len(elm_idx), nbus=len(bus_idx))

        data.names = self.names[elm_idx]
        data.controllable = self.controllable[elm_idx]

        data.active = self.active[tidx]
        data.p = self.p[tidx]
        data.pf = self.pf[tidx]
        data.v = self.v[tidx]

        data.qmin = self.qmin[elm_idx]
        data.qmax = self.qmax[elm_idx]

        data.C_bus_batt = self.C_bus_batt[np.ix_(bus_idx, elm_idx)]

        data.r0 = self.r0[elm_idx]
        data.r1 = self.r1[elm_idx]
        data.r2 = self.r2[elm_idx]

        data.x0 = self.x0[elm_idx]
        data.x1 = self.x1[elm_idx]
        data.x2 = self.x2[elm_idx]

        return data

    def get_island(self, bus_idx, t_idx=0):
        if self.nbatt:
            return tp.get_elements_of_the_island(self.C_bus_batt.T, bus_idx, active=self.active[t_idx])
        else:
            return np.zeros(0, dtype=int)

    def get_injections(self):
        """
        Compute the active and reactive power of non-controlled batteries (assuming all)
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
            return self.C_bus_batt @ (1.0 / (self.r0 + 1j * self.x0))
        elif seq == 1:
            return self.C_bus_batt @ (1.0 / (self.r1 + 1j * self.x1))
        elif seq == 2:
            return self.C_bus_batt @ (1.0 / (self.r2 + 1j * self.x2))
        else:
            raise Exception('Sequence must be 0, 1, 2')

    def get_injections_per_bus(self):
        return self.C_bus_batt * (self.get_injections() * self.active)

    def get_bus_indices(self):
        return self.C_bus_batt.tocsc().indices

    def get_voltages_per_bus(self):
        n_per_bus = self.C_bus_batt.sum(axis=1)
        n_per_bus[n_per_bus == 0] = 1
        # the division by n_per_bus achieves the averaging of the voltage control
        # value if more than 1 battery is present per bus
        # return self.C_bus_batt * (self.battery_v * self.battery_active) / n_per_bus
        return np.array((self.C_bus_batt * self.v) / n_per_bus)

    def get_installed_power_per_bus(self):
        return self.C_bus_batt * self.installed_p

    def get_qmax_per_bus(self):
        return self.C_bus_batt * (self.qmax.reshape(-1, 1) * self.active)

    def get_qmin_per_bus(self):
        return self.C_bus_batt * (self.qmin.reshape(-1, 1) * self.active)

    def __len__(self):
        return self.nbatt


class BatteryOpfData(BatteryData):

    def __init__(self, nbatt, nbus, ntime=1):
        """

        :param nbatt: 
        :param nbus: 
        :param ntime: 
        """
        BatteryData.__init__(self, nbatt, nbus, ntime)

        self.battery_dispatchable = np.zeros(nbatt, dtype=bool)
        self.battery_pmax = np.zeros(nbatt)
        self.battery_pmin = np.zeros(nbatt)
        self.battery_enom = np.zeros(nbatt)
        self.battery_min_soc = np.zeros(nbatt)
        self.battery_max_soc = np.zeros(nbatt)
        self.battery_soc_0 = np.zeros(nbatt)
        self.battery_discharge_efficiency = np.zeros(nbatt)
        self.battery_charge_efficiency = np.zeros(nbatt)
        self.battery_cost = np.zeros((nbatt, ntime))

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

        data = BatteryOpfData(nbatt=len(elm_idx), nbus=len(bus_idx))

        data.names = self.names[elm_idx]
        data.controllable = self.controllable[elm_idx]
        data.battery_dispatchable = self.battery_dispatchable[elm_idx]

        data.battery_pmax = self.battery_pmax[elm_idx]
        data.battery_pmin = self.battery_pmin[elm_idx]
        data.battery_enom = self.battery_enom[elm_idx]
        data.battery_min_soc = self.battery_min_soc[elm_idx]
        data.battery_max_soc = self.battery_max_soc[elm_idx]
        data.battery_soc_0 = self.battery_soc_0[elm_idx]
        data.battery_discharge_efficiency = self.battery_discharge_efficiency[elm_idx]
        data.battery_charge_efficiency = self.battery_charge_efficiency[elm_idx]

        data.active = self.active[tidx]
        data.p = self.p[tidx]
        data.pf = self.pf[tidx]
        data.v = self.v[tidx]
        data.battery_cost = self.battery_cost[tidx]

        data.qmin = self.qmin[elm_idx]
        data.qmax = self.qmax[elm_idx]

        data.C_bus_batt = self.C_bus_batt[np.ix_(bus_idx, elm_idx)]

        return data
