# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from GridCalEngine.DataStructures.branch_data import BranchData
from GridCalEngine.basic_structures import Vec, IntVec, BoolVec, StrVec, ObjVec, Logger


class VscData(BranchData):
    """
    VscData class provides a structured model for managing data related to
    Voltage Source Converters (VSC) in power grid simulations.
    """

    def __init__(self, nelm: int, nbus: int):
        """
        Initializes the VscData with arrays for managing converter data.
        :param nelm: number of VSC elements
        :param nbus: number of buses
        """
        BranchData.__init__(self, nelm=nelm, nbus=nbus)

    def copy(self) -> "VscData":
        """
        Get a deep copy of this VscData object
        :return: new VscData instance
        """
        data = super().copy()

        return data

    def slice(self, elm_idx: IntVec, bus_idx: IntVec, logger: Logger | None) -> "VscData":
        """
        Slice VSC data by given indices
        :param elm_idx: array of VSC element indices
        :param bus_idx: array of bus indices
        :param logger: Logger
        :return: new VscData instance
        """
        data = super().slice(elm_idx, bus_idx, logger)
        data.__class__ = VscData
        return data
