# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from GridCalEngine.DataStructures.fluid_turbine_data import FluidTurbineData


class FluidP2XData(FluidTurbineData):
    """
    FluidP2XData
    """

    def __init__(self, nelm: int):
        """
        Fluid P2X data arrays
        :param nelm: number of fluid p2xs
        """

        FluidTurbineData.__init__(self,
                                  nelm=nelm)

