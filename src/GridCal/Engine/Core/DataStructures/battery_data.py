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

    def __init__(self, nbatt, nbus):
        """

        :param nbatt:
        :param nbus:
        """
        self.nbatt = nbatt

        self.battery_names = np.empty(nbatt, dtype=object)
        self.battery_active = np.zeros(nbatt, dtype=bool)
        self.battery_controllable = np.zeros(nbatt, dtype=bool)
        self.battery_installed_p = np.zeros(nbatt)
        self.battery_p = np.zeros(nbatt)
        self.battery_pf = np.zeros(nbatt)
        self.battery_v = np.zeros(nbatt)
        self.battery_qmin = np.zeros(nbatt)
        self.battery_qmax = np.zeros(nbatt)

        self.C_bus_batt = sp.lil_matrix((nbus, nbatt), dtype=int)

    def slice(self, batt_idx, bus_idx):
        """

        :param batt_idx:
        :param bus_idx:
        :return:
        """
        nc = BatteryData(nbatt=len(batt_idx), nbus=len(bus_idx))

        nc.battery_names = self.battery_names[batt_idx]
        nc.battery_active = self.battery_active[batt_idx]
        nc.battery_controllable = self.battery_controllable[batt_idx]
        nc.battery_p = self.battery_p[batt_idx]
        nc.battery_pf = self.battery_pf[batt_idx]
        nc.battery_v = self.battery_v[batt_idx]
        nc.battery_qmin = self.battery_qmin[batt_idx]
        nc.battery_qmax = self.battery_qmax[batt_idx]

        nc.C_bus_batt = self.C_bus_batt[np.ix_(bus_idx, batt_idx)]

        return nc

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
        return self.C_bus_batt * (self.battery_qmax * self.battery_active)

    def get_qmin_per_bus(self):
        return self.C_bus_batt * (self.battery_qmin * self.battery_active)

    def __len__(self):
        return self.nbatt
