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
from GridCalEngine.basic_structures import CxVec, Vec, IntVec, BoolVec, StrVec


class BusData:
    """
    BusData
    """

    def __init__(self, nbus: int):
        """
        Bus data arrays
        :param nbus: number of buses
        """
        self.nbus: int = nbus
        self.idtag: StrVec = np.empty(nbus, dtype=object)
        self.names: StrVec = np.empty(nbus, dtype=object)
        self.active: IntVec = np.ones(nbus, dtype=int)
        self.Vbus: CxVec = np.ones(nbus, dtype=complex)
        self.Vmin: Vec = np.ones(nbus, dtype=float)
        self.Vmax: Vec = np.ones(nbus, dtype=float)
        self.Vnom: Vec = np.ones(nbus, dtype=float)
        self.angle_min: Vec = np.full(nbus, fill_value=-3.14, dtype=float)
        self.angle_max: Vec = np.full(nbus, fill_value=3.14, dtype=float)
        self.bus_types: IntVec = np.empty(nbus, dtype=int)
        self.installed_power: Vec = np.zeros(nbus, dtype=float)
        self.is_dc: BoolVec = np.empty(nbus, dtype=bool)
        self.areas: IntVec = np.empty(nbus, dtype=int)
        self.substations: IntVec = np.empty(nbus, dtype=int)

        self.original_idx: IntVec = np.zeros(nbus, dtype=int)

    def slice(self, elm_idx: IntVec) -> "BusData":
        """
        Slice this data structure
        :param elm_idx: array of bus indices
        :return: instance of BusData
        """

        data = BusData(nbus=len(elm_idx))

        data.names = self.names[elm_idx]
        data.idtag = self.idtag[elm_idx]
        data.active = self.active[elm_idx]

        data.Vbus = self.Vbus[elm_idx]
        data.Vmin = self.Vmin[elm_idx]
        data.Vmax = self.Vmax[elm_idx]
        data.Vnom = self.Vnom[elm_idx]
        data.angle_min = self.angle_min[elm_idx]
        data.angle_max = self.angle_max[elm_idx]

        data.bus_types = self.bus_types[elm_idx]
        data.installed_power = self.installed_power[elm_idx]
        data.is_dc = self.is_dc[elm_idx]
        data.areas = self.areas[elm_idx]
        data.substations = self.substations[elm_idx]

        data.original_idx = elm_idx

        return data

    def copy(self) -> "BusData":
        """
        Deep copy of this structure
        :return: instance of BusData
        """

        data = BusData(nbus=self.nbus)

        data.names = self.names.copy()
        data.idtag = self.idtag.copy()
        data.active = self.active.copy()

        data.Vbus = self.Vbus.copy()
        data.Vmin = self.Vmin.copy()
        data.Vmax = self.Vmax.copy()
        data.Vnom = self.Vnom.copy()
        data.angle_min = self.angle_min.copy()
        data.angle_max = self.angle_max.copy()

        data.bus_types = self.bus_types.copy()
        data.installed_power = self.installed_power.copy()
        data.is_dc = self.is_dc.copy()
        data.areas = self.areas.copy()
        data.substations = self.substations.copy()

        data.original_idx = self.original_idx.copy()

        return data

    def __len__(self) -> int:
        return self.nbus
