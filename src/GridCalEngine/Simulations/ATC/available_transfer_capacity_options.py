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
from GridCalEngine.enumerations import AvailableTransferMode, SubObjectType
from GridCalEngine.basic_structures import Vec, IntVec
from GridCalEngine.Simulations.options_template import OptionsTemplate


class AvailableTransferCapacityOptions(OptionsTemplate):
    """
    Available Transfer Capacity Options
    """

    def __init__(self,
                 distributed_slack: bool = True,
                 correct_values: bool = True,
                 use_provided_flows: bool = False,
                 bus_idx_from: Union[None, IntVec] = None,
                 bus_idx_to: Union[None, IntVec] = None,
                 idx_br: Union[None, IntVec] = None,
                 sense_br: Union[None, IntVec] = None,
                 Pf: Union[None, Vec] = None,
                 idx_hvdc_br: Union[None, IntVec] = None,
                 sense_hvdc_br: Union[None, IntVec] = None,
                 Pf_hvdc: Union[None, Vec] = None,
                 dT: float = 100.0,
                 threshold: float = 0.02,
                 mode: AvailableTransferMode = AvailableTransferMode.Generation,
                 max_report_elements: int = -1,
                 use_clustering: bool = False,
                 cluster_number: int = 200):
        """
        Available Transfer Capacity Options
        :param distributed_slack: Distribute the slack effect?
        :param correct_values: Correct the theoretical glitch values to [-1, 1] ?
        :param use_provided_flows: Use the provided flows?
        :param bus_idx_from: array of bus from idx for every branch
        :param bus_idx_to: array of bus to idx for every branch
        :param idx_br: array of selected branches idx
        :param sense_br: array of sense sign of the branches.
                        1 if the branch connection goes in the same sense as the transfer, -1 otherwise
        :param Pf: Array of base real power flow values for all the branches
        :param idx_hvdc_br: Array of HVDC slected indices
        :param sense_hvdc_br: array of sense sign of the HVDC branches.
                             1 if the branch connection goes in the same sense as the transfer, -1 otherwise
        :param Pf_hvdc: Array of base real power flow values for all the HVDC
        :param dT: increment o transfer in MW
        :param threshold: Sentitivity threeshold to the transfer
        :param mode: AvailableTransferMode
        :param max_report_elements: maximum number of elements to show in the report (-1 for all)
        :param use_clustering: Use clustering?
        """
        OptionsTemplate.__init__(self, name="AvailableTransferCapacityOptions")

        self.distributed_slack = distributed_slack
        self.correct_values = correct_values
        self.use_provided_flows = use_provided_flows

        empty_idx = np.zeros(0, dtype=int)

        self.bus_idx_from: IntVec = bus_idx_from if bus_idx_from is not None else empty_idx
        self.bus_idx_to: IntVec = bus_idx_to if bus_idx_to is not None else empty_idx
        self.inter_area_branch_idx: IntVec = idx_br if idx_br is not None else empty_idx
        self.inter_area_branch_sense: IntVec = sense_br if sense_br is not None else empty_idx

        self.Pf: Union[None, Vec] = Pf

        self.idx_hvdc_br: IntVec = idx_hvdc_br if idx_hvdc_br is not None else empty_idx
        self.inter_area_hvdc_branch_sense: IntVec = sense_hvdc_br if sense_hvdc_br is not None else empty_idx

        self.Pf_hvdc: Union[None, Vec] = Pf_hvdc

        self.dT = dT
        self.threshold = threshold
        self.mode = mode
        self.max_report_elements = max_report_elements
        self.use_clustering = use_clustering
        self.cluster_number = cluster_number

        self.register(key="distributed_slack", tpe=bool)
        self.register(key="correct_values", tpe=bool)
        self.register(key="use_provided_flows", tpe=bool)

        self.register(key="bus_idx_from", tpe=SubObjectType.Array)
        self.register(key="bus_idx_to", tpe=SubObjectType.Array)
        self.register(key="inter_area_branch_idx", tpe=SubObjectType.Array)
        self.register(key="inter_area_branch_sense", tpe=SubObjectType.Array)
        self.register(key="Pf", tpe=SubObjectType.Array)
        self.register(key="idx_hvdc_br", tpe=SubObjectType.Array)
        self.register(key="use_provided_flows", tpe=SubObjectType.Array)
        self.register(key="inter_area_hvdc_branch_sense", tpe=SubObjectType.Array)
        self.register(key="Pf_hvdc", tpe=SubObjectType.Array)

        self.register(key="dT", tpe=float)
        self.register(key="threshold", tpe=float)
        self.register(key="mode", tpe=AvailableTransferMode)
        self.register(key="max_report_elements", tpe=int)
        self.register(key="use_clustering", tpe=bool)
        self.register(key="cluster_number", tpe=int)
