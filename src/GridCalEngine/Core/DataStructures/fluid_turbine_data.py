# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
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
from GridCalEngine.basic_structures import Vec, CxVec, IntVec, StrVec


class FluidTurbineData:
    """
    FluidTurbineData
    """

    def __init__(self, nelm: int):
        """
        Fluid turbine data arrays
        :param nelm: number of fluid turbines
        """
        self.nelm: int = nelm

        self.names: StrVec = np.empty(nelm, dtype=object)
        self.idtag: StrVec = np.empty(nelm, dtype=object)

        self.efficiency = np.zeros(nelm, dtype=float)
        self.max_flow_rate = np.zeros(nelm, dtype=float)

        self.plant_idx = np.empty(nelm, dtype=int)
        self.generator_idx = np.empty(nelm, dtype=int)

    def size(self) -> int:
        """
        Get size of the structure
        :return:
        """

        return self.nelm

    def copy(self) -> "FluidTurbineData":
        """
        Get deep copy of this structure
        :return: new FluidTurbineData instance
        """

        data = FluidTurbineData(nelm=self.nelm)

        data.names = self.names.copy()
        data.idtag = self.idtag.copy()

        data.efficiency = self.efficiency.copy()
        data.max_flow_rate = self.max_flow_rate.copy()
        data.plant_idx = self.plant_idx.copy()
        data.generator_idx = self.generator_idx.copy()

        return data


