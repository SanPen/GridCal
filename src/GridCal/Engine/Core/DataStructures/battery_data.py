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


class BatteryData:

    def __init__(self, nbatt, nbus, ntime=1):
        """

        :param nbatt:
        :param nbus:
        """
        self.nbatt = nbatt
        self.ntime = ntime

        self.battery_names = np.empty(nbatt, dtype=object)

        self.battery_controllable = np.zeros(nbatt, dtype=bool)
        self.battery_installed_p = np.zeros(nbatt)

        self.battery_active = np.zeros((nbatt, ntime), dtype=bool)
        self.battery_p = np.zeros((nbatt, ntime))
        self.battery_pf = np.zeros((nbatt, ntime))
        self.battery_v = np.zeros((nbatt, ntime))

        self.battery_qmin = np.zeros(nbatt)
        self.battery_qmax = np.zeros(nbatt)

        self.C_bus_batt = sp.lil_matrix((nbus, nbatt), dtype=int)

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

        data.battery_names = self.battery_names[elm_idx]
        data.battery_controllable = self.battery_controllable[elm_idx]

        data.battery_active = self.battery_active[tidx]
        data.battery_p = self.battery_p[tidx]
        data.battery_pf = self.battery_pf[tidx]
        data.battery_v = self.battery_v[tidx]

        data.battery_qmin = self.battery_qmin[elm_idx]
        data.battery_qmax = self.battery_qmax[elm_idx]

        data.C_bus_batt = self.C_bus_batt[np.ix_(bus_idx, elm_idx)]

        return data

    def get_island(self, bus_idx):
        return tp.get_elements_of_the_island(self.C_bus_batt.T, bus_idx)

    def get_injections(self):
        """
        Compute the active and reactive power of non-controlled batteries (assuming all)
        :return:
        """
        pf2 = np.power(self.battery_pf, 2.0)
        pf_sign = (self.battery_pf + 1e-20) / np.abs(self.battery_pf + 1e-20)
        Q = pf_sign * self.battery_p * np.sqrt((1.0 - pf2) / (pf2 + 1e-20))
        return self.battery_p + 1.0j * Q

    def get_injections_per_bus(self):
        return self.C_bus_batt * (self.get_injections() * self.battery_active)

    def get_installed_power_per_bus(self):
        return self.C_bus_batt * self.battery_installed_p

    def get_qmax_per_bus(self):
        return self.C_bus_batt * (self.battery_qmax.reshape(-1, 1) * self.battery_active)

    def get_qmin_per_bus(self):
        return self.C_bus_batt * (self.battery_qmin.reshape(-1, 1) * self.battery_active)

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

        data.battery_names = self.battery_names[elm_idx]
        data.battery_controllable = self.battery_controllable[elm_idx]
        data.battery_dispatchable = self.battery_dispatchable[elm_idx]

        data.battery_pmax = self.battery_pmax[elm_idx]
        data.battery_pmin = self.battery_pmin[elm_idx]
        data.battery_enom = self.battery_enom[elm_idx]
        data.battery_min_soc = self.battery_min_soc[elm_idx]
        data.battery_max_soc = self.battery_max_soc[elm_idx]
        data.battery_soc_0 = self.battery_soc_0[elm_idx]
        data.battery_discharge_efficiency = self.battery_discharge_efficiency[elm_idx]
        data.battery_charge_efficiency = self.battery_charge_efficiency[elm_idx]

        data.battery_active = self.battery_active[tidx]
        data.battery_p = self.battery_p[tidx]
        data.battery_pf = self.battery_pf[tidx]
        data.battery_v = self.battery_v[tidx]
        data.battery_cost = self.battery_cost[tidx]

        data.battery_qmin = self.battery_qmin[elm_idx]
        data.battery_qmax = self.battery_qmax[elm_idx]

        data.C_bus_batt = self.C_bus_batt[np.ix_(bus_idx, elm_idx)]

        return data
