# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0
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


