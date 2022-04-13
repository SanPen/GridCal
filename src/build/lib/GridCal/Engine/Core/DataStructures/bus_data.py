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


class BusData:

    def __init__(self, nbus, ntime=1):
        """

        :param nbus:
        """
        self.nbus = nbus
        self.ntime = ntime
        self.bus_names = np.empty(nbus, dtype=object)
        self.bus_active = np.ones((nbus, ntime), dtype=int)
        self.Vbus = np.ones((nbus, ntime), dtype=complex)
        self.Vmin = np.ones(nbus, dtype=float)
        self.Vmax = np.ones(nbus, dtype=float)
        self.angle_min = np.ones(nbus, dtype=float) * -3.14
        self.angle_max = np.ones(nbus, dtype=float) * 3.14
        self.bus_types = np.empty(nbus, dtype=int)
        self.bus_types_prof = np.zeros((nbus, ntime), dtype=int)
        self.bus_installed_power = np.zeros(nbus, dtype=float)
        self.bus_is_dc = np.empty(nbus, dtype=bool)
        self.areas = np.empty(nbus, dtype=int)

    def slice(self, elm_idx, time_idx=None):
        """
        Slice this data structure
        :param elm_idx: array of bus indices
        :param time_idx: array of time indices
        :return: instance of BusData
        """

        if time_idx is None:
            tidx = elm_idx
        else:
            tidx = np.ix_(elm_idx, time_idx)

        data = BusData(nbus=len(elm_idx))

        data.bus_names = self.bus_names[elm_idx]

        data.bus_active = self.bus_active[tidx]

        data.Vbus = self.Vbus[tidx]
        data.Vmin = self.Vmin[elm_idx]
        data.Vmax = self.Vmax[elm_idx]
        data.angle_min = self.angle_min[elm_idx]
        data.angle_max = self.angle_max[elm_idx]

        data.bus_types = self.bus_types[elm_idx]
        data.bus_types_prof = self.bus_types_prof[tidx]

        data.bus_installed_power = self.bus_installed_power[elm_idx]
        data.bus_is_dc = self.bus_is_dc[elm_idx]
        data.areas = self.areas[elm_idx]

        return data

    def __len__(self):
        return self.nbus

