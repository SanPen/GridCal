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

    def __init__(self, nbus):
        """
        Bus data arrays
        :param nbus: number of buses
        """
        self.nbus: int = nbus
        self.names: np.array = np.empty(nbus, dtype=object)
        self.active: np.array = np.ones(nbus, dtype=int)
        self.Vbus: np.array = np.ones(nbus, dtype=complex)
        self.Vmin: np.array = np.ones(nbus, dtype=float)
        self.Vmax: np.array = np.ones(nbus, dtype=float)
        self.angle_min: np.array = np.full(nbus, fill_value=-3.14, dtype=float)
        self.angle_max: np.array = np.full(nbus, fill_value=3.14, dtype=float)
        self.bus_types: np.array = np.empty(nbus, dtype=int)
        self.installed_power: np.array = np.zeros(nbus, dtype=float)
        self.is_dc: np.array = np.empty(nbus, dtype=bool)
        self.areas: np.array = np.empty(nbus, dtype=int)

        self.original_idx = np.zeros(nbus, dtype=int)

    def slice(self, elm_idx):
        """
        Slice this data structure
        :param elm_idx: array of bus indices
        :return: instance of BusData
        """

        data = BusData(nbus=len(elm_idx))

        data.names = self.names[elm_idx]

        data.active = self.active[elm_idx]

        data.Vbus = self.Vbus[elm_idx]
        data.Vmin = self.Vmin[elm_idx]
        data.Vmax = self.Vmax[elm_idx]
        data.angle_min = self.angle_min[elm_idx]
        data.angle_max = self.angle_max[elm_idx]

        data.bus_types = self.bus_types[elm_idx]
        data.installed_power = self.installed_power[elm_idx]
        data.is_dc = self.is_dc[elm_idx]
        data.areas = self.areas[elm_idx]

        data.original_idx = elm_idx

        return data

    def __len__(self):
        return self.nbus

