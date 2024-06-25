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

from typing import Union
import numpy as np
from GridCalEngine.Simulations.options_template import OptionsTemplate
from GridCalEngine.Simulations import OptimalPowerFlowOptions
from GridCalEngine.enumerations import NodalCapacityMethod, SubObjectType, DeviceType
from GridCalEngine.basic_structures import IntVec


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
