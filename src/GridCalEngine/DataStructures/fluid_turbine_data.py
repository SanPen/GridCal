# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0
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


