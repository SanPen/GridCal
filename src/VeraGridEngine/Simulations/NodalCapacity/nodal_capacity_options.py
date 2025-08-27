# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Union
import numpy as np
from VeraGridEngine.Simulations.options_template import OptionsTemplate
from VeraGridEngine.Simulations import OptimalPowerFlowOptions
from VeraGridEngine.enumerations import NodalCapacityMethod, SubObjectType, DeviceType
from VeraGridEngine.basic_structures import IntVec


class NodalCapacityOptions(OptionsTemplate):
    """
    Nodal Capacity Options
    """

    def __init__(self,
                 opf_options: Union[None, OptimalPowerFlowOptions] = None,
                 capacity_nodes_idx: Union[None, IntVec] = None,
                 nodal_capacity_sign: float = 1.0,
                 method: NodalCapacityMethod = NodalCapacityMethod.LinearOptimization):
        """

        :param opf_options: OPF options
        :param capacity_nodes_idx: array of bus indices to optimize
        :param nodal_capacity_sign: if > 0 the generation is maximized, if < 0 the load is maximized
        :param method: NodalCapacityMethod
        """
        OptionsTemplate.__init__(self, name="NodalCapacityOptions")

        self.opf_options = opf_options if opf_options is not None else OptimalPowerFlowOptions()
        self.capacity_nodes_idx = capacity_nodes_idx if capacity_nodes_idx is not None else np.zeros(0, dtype=int)
        self.method: NodalCapacityMethod = method
        self.nodal_capacity_sign = nodal_capacity_sign

        self.register(key="opf_options", tpe=DeviceType.SimulationOptionsDevice)
        self.register(key="capacity_nodes_idx", tpe=SubObjectType.Array)
        self.register(key="method", tpe=NodalCapacityMethod)
        self.register(key="nodal_capacity_sign", tpe=float)
