# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0
from GridCalEngine.DataStructures.fluid_turbine_data import FluidTurbineData


class FluidPumpData(FluidTurbineData):
    """
    FluidPumpData
    """

    def __init__(self, nelm: int):
        """
        Fluid pump data arrays
        :param nelm: number of fluid pumps
        """

        FluidTurbineData.__init__(self,
                                  nelm=nelm)

