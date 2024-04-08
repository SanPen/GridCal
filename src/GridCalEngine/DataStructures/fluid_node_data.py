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


class FluidNodeData:
    """
    FluidNodeData
    """

    def __init__(self, nelm: int):
        """
        Fluid node data arrays
        :param nelm: number of fluid nodes
        """
        self.nelm: int = nelm

        self.names: StrVec = np.empty(nelm, dtype=object)
        self.idtag: StrVec = np.empty(nelm, dtype=object)

        self.min_level = np.zeros(nelm, dtype=float)
        self.max_level = np.zeros(nelm, dtype=float)
        self.min_soc = np.zeros(nelm, dtype=float)
        self.max_soc = np.zeros(nelm, dtype=float)
        self.initial_level = np.zeros(nelm, dtype=float)
        self.inflow = np.zeros(nelm, dtype=float)
        self.spillage_cost = np.zeros(nelm, dtype=float)

    def size(self) -> int:
        """
        Get size of the structure
        :return:
        """

        return self.nelm

    def copy(self) -> "FluidNodeData":
        """
        Get deep copy of this structure
        :return: new FluidNodeData instance
        """

        data = FluidNodeData(nelm=self.nelm)

        data.names = self.names.copy()
        data.idtag = self.idtag.copy()

        data.min_level = self.min_level.copy()
        data.max_level = self.max_level.copy()
        data.min_soc = self.min_soc.copy()
        data.max_soc = self.max_soc.copy()
        data.initial_level = self.initial_level.copy()

        data.inflow = self.inflow.copy()
        data.spillage_cost = self.spillage_cost.copy()

        return data


