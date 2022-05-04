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


class HvdcData:

    def __init__(self, nhvdc, nbus, ntime=1):
        """

        :param nhvdc:
        :param nbus:
        """
        self.nhvdc = nhvdc
        self.ntime = ntime

        self.names = np.zeros(nhvdc, dtype=object)

        self.angle_droop = np.zeros((nhvdc, ntime))

        self.control_mode = np.zeros(nhvdc, dtype=object)

        self.dispatchable = np.zeros(nhvdc, dtype=int)

        self.active = np.zeros((nhvdc, ntime), dtype=bool)
        self.rate = np.zeros((nhvdc, ntime))
        self.contingency_rate = np.zeros((nhvdc, ntime))

        self.r = np.zeros(nhvdc)

        self.Pset = np.zeros((nhvdc, ntime))
        self.Pt = np.zeros((nhvdc, ntime))

        self.Vset_f = np.zeros((nhvdc, ntime))
        self.Vset_t = np.zeros((nhvdc, ntime))

        self.Qmin_f = np.zeros(nhvdc)
        self.Qmax_f = np.zeros(nhvdc)
        self.Qmin_t = np.zeros(nhvdc)
        self.Qmax_t = np.zeros(nhvdc)

        self.C_hvdc_bus_f = sp.lil_matrix((nhvdc, nbus), dtype=int)  # this ons is just for splitting islands
        self.C_hvdc_bus_t = sp.lil_matrix((nhvdc, nbus), dtype=int)  # this ons is just for splitting islands

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

        data = HvdcData(nhvdc=len(elm_idx), nbus=len(bus_idx))

        data.names = self.names[elm_idx]
        data.active = self.active[elm_idx]
        data.dispatchable = self.dispatchable[elm_idx]

        data.rate = self.rate[tidx]
        data.contingency_rate = self.contingency_rate[tidx]
        data.Pset = self.Pset[tidx]

        data.r = self.r[elm_idx]

        data.Vset_f = self.Vset_f[tidx]
        data.Vset_t = self.Vset_t[tidx]

        data.angle_droop = self.angle_droop[elm_idx]

        data.control_mode = self.control_mode[elm_idx]

        data.Qmin_f = self.Qmin_f[elm_idx]
        data.Qmax_f = self.Qmax_f[elm_idx]
        data.Qmin_t = self.Qmin_t[elm_idx]
        data.Qmax_t = self.Qmax_t[elm_idx]

        data.C_hvdc_bus_f = self.C_hvdc_bus_f[np.ix_(elm_idx, bus_idx)]
        data.C_hvdc_bus_t = self.C_hvdc_bus_t[np.ix_(elm_idx, bus_idx)]

        return data

    def get_bus_indices_f(self):
        return self.C_hvdc_bus_f * np.arange(self.C_hvdc_bus_f.shape[1])

    def get_bus_indices_t(self):
        return self.C_hvdc_bus_t * np.arange(self.C_hvdc_bus_t.shape[1])

    def get_island(self, bus_idx, t_idx=0):
        """
        Get HVDC indices of the island given by the bus indices
        :param bus_idx: list of bus indices
        :return: list of HVDC lines indices
        """
        if self.nhvdc:
            return tp.get_elements_of_the_island(self.C_hvdc_bus_f + self.C_hvdc_bus_t, bus_idx,
                                                 active=self.active[:, t_idx])
        else:
            return np.zeros(0, dtype=int)

    def get_qmax_from_per_bus(self):
        """
        Max reactive power in the From Bus
        :return: (nbus, nt) Qmax From
        """
        return self.C_hvdc_bus_f.T * (self.Qmax_f * self.active.T).T

    def get_qmin_from_per_bus(self):
        """
        Min reactive power in the From Bus
        :return: (nbus, nt) Qmin From
        """
        return self.C_hvdc_bus_f.T * (self.Qmin_f * self.active.T).T

    def get_qmax_to_per_bus(self):
        """
        Max reactive power in the To Bus
        :return: (nbus, nt) Qmax To
        """
        return self.C_hvdc_bus_t.T * (self.Qmax_t * self.active.T).T

    def get_qmin_to_per_bus(self):
        """
        Min reactive power in the To Bus
        :return: (nbus, nt) Qmin To
        """
        return self.C_hvdc_bus_t.T * (self.Qmin_t * self.active.T).T

    def get_angle_droop_in_pu_rad(self, Sbase):
        """
        Get the angle droop in pu/rad
        :param Sbase:
        :return:
        """
        return self.angle_droop * 57.295779513 / Sbase

    def __len__(self):
        return self.nhvdc
