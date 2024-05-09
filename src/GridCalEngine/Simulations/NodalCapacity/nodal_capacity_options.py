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
from GridCalEngine.Simulations import OptimalPowerFlowOptions
from GridCalEngine.enumerations import NodalCapacityMethod
from GridCalEngine.basic_structures import IntVec


class NodalCapacityOptions:
    """
    NodalCapacityOptions
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
        self.opf_options = opf_options if opf_options else OptimalPowerFlowOptions()
        self.capacity_nodes_idx = capacity_nodes_idx if capacity_nodes_idx else np.zeros(0, dtype=int)
        self.method = method
        self.nodal_capacity_sign = nodal_capacity_sign
