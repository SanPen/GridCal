# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import numpy as np
from GridCalEngine.basic_structures import Vec, CxVec, IntVec, StrVec


class FluidPathData:
    """
    FluidPathData
    """

    def __init__(self, nelm: int):
        """
        Fluid path data arrays
        :param nelm: number of fluid rivers
        """
        self.nelm: int = nelm

        self.names: StrVec = np.empty(nelm, dtype=object)
        self.idtag: StrVec = np.empty(nelm, dtype=object)

        self.source_idx = np.empty(nelm, dtype=int)
        self.target_idx = np.empty(nelm, dtype=int)
        self.min_flow = np.zeros(nelm, dtype=float)
        self.max_flow = np.zeros(nelm, dtype=float)

    def size(self) -> int:
        """
        Get size of the structure
        :return:
        """

        return self.nelm

    def copy(self) -> "FluidPathData":
        """
        Get deep copy of this structure
        :return: new FluidPathData instance
        """

        data = FluidPathData(nelm=self.nelm)

        data.names = self.names.copy()
        data.idtag = self.idtag.copy()

        data.source_idx = self.source_idx.copy()
        data.target_idx = self.target_idx.copy()
        data.min_flow = self.min_flow.copy()
        data.max_flow = self.max_flow.copy()

        return data
