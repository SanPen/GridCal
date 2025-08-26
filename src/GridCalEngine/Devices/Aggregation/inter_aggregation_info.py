# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from typing import List, Tuple, TYPE_CHECKING
import numpy as np
from GridCalEngine.Devices.Parents.editable_device import EditableDevice, DeviceType
from GridCalEngine.basic_structures import IntVec, Vec
from GridCalEngine.basic_structures import Logger

if TYPE_CHECKING:
    from GridCalEngine.Devices.Substation.bus import Bus
    from GridCalEngine.Devices.Aggregation.area import Area
    from GridCalEngine.Devices.Aggregation.zone import Zone
    from GridCalEngine.Devices.Aggregation.country import Country
    from GridCalEngine.Devices.Branches.hvdc_line import HvdcLine
    from GridCalEngine.Devices.types import BRANCH_TYPES


class InterAggregationInfo(EditableDevice):
    """
    Class to store information of inter area, inter country, etc
    """
    __slots__ = (
        'valid',
        'lst_from',
        'lst_to',
        'lst_br',
        'lst_br_hvdc',
        'objects_from',
        'objects_to',
        'logger',
    )

    def __init__(self,
                 valid: bool,
                 lst_from: List[Tuple[int, Bus]],
                 lst_to: List[Tuple[int, Bus]],
                 lst_br: List[Tuple[int, BRANCH_TYPES, float]],
                 lst_br_hvdc: List[Tuple[int, HvdcLine, float]],
                 objects_from: List[Area | Zone | Country],
                 objects_to: List[Area | Zone | Country],
                 logger: Logger = Logger()):
        """

        :param valid:
        :param lst_from: list of tuples bus idx, Bus in the areas from
        :param lst_to: list of tuples bus idx, Bus in the areas to
        :param lst_br: List of inter area Branches (branch index, branch object, flow sense w.r.t the area exchange),
        :param lst_br_hvdc: List of inter area HVDC (branch index, branch object, flow sense w.r.t the area exchange),
        :param objects_from:  List of areas from
        :param objects_to: List of areas to
        :param logger: Logger object
        """
        EditableDevice.__init__(self,
                                name="",
                                code="",
                                idtag=None,
                                device_type=DeviceType.InterAggregationInfo)

        self.valid: float = valid

        # store the bus index and the bus object ptr
        self.lst_from: List[Tuple[int, Bus]] = lst_from
        self.lst_to: List[Tuple[int, Bus]] = lst_to

        # store the branch index, the branch ptr and the sense
        self.lst_br: List[Tuple[int, BRANCH_TYPES, float]] = lst_br
        self.lst_br_hvdc = lst_br_hvdc

        self.objects_from: List[Area | Zone | Country] = objects_from
        self.objects_to: List[Area | Zone | Country] = objects_to

        self.logger = logger

    @property
    def idx_bus_from(self) -> IntVec:
        """
        Get bus of the aggregation "from" indices
        :return: IntVec
        """
        return np.array([i for i, bus in self.lst_from])

    @property
    def idx_bus_to(self) -> IntVec:
        """
        Get bus of the aggregation "to" indices
        :return: IntVec
        """
        return np.array([i for i, bus in self.lst_to])

    @property
    def idx_branches(self) -> IntVec:
        """
        Get array of tie-branches indices
        :return: IntVec
        """
        return np.array([i for i, bus, sense in self.lst_br])

    @property
    def sense_branches(self) -> Vec:
        """
        Get array of tie-branch sense values (1 for from->to, -1 for to->from)
        :return: IntVec
        """
        return np.array([sense for i, bus, sense in self.lst_br])

    @property
    def idx_hvdc(self) -> IntVec:
        """

        :return:
        """
        return np.array([i for i, bus, sense in self.lst_br_hvdc])

    @property
    def sense_hvdc(self) -> Vec:
        """

        :return:
        """
        return np.array([sense for i, bus, sense in self.lst_br_hvdc])
