# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
import numpy as np
from GridCalEngine.DataStructures.branch_parent_data import BranchParentData
from GridCalEngine.enumerations import ConverterControlType
from GridCalEngine.basic_structures import Vec, IntVec, ObjVec, Logger


class VscData(BranchParentData):
    """
    VscData class provides a structured model for managing data related to
    Voltage Source Converters (VSC) in power grid simulations.
    """

    def __init__(self, nelm: int, nbus: int):
        """
        Branch data arrays
        :param nelm: number of elements
        :param nbus: number of buses
        """
        BranchParentData.__init__(self, nelm=nelm, nbus=nbus)

        self.Kdp: Vec = np.ones(self.nelm, dtype=float)
        self.alpha1: Vec = np.zeros(self.nelm, dtype=float)  # converter losses parameter (alpha1)
        self.alpha2: Vec = np.zeros(self.nelm, dtype=float)  # converter losses parameter (alpha2)
        self.alpha3: Vec = np.zeros(self.nelm, dtype=float)  # converter losses parameter (alpha3)

        self.control1: ObjVec = np.full(self.nelm, fill_value=ConverterControlType.Vm_dc, dtype=object)
        self.control2: ObjVec = np.full(self.nelm, fill_value=ConverterControlType.Pac, dtype=object)

        self.control1_val: Vec = np.ones(self.nelm, dtype=float)
        self.control2_val: Vec = np.ones(self.nelm, dtype=float)

        self.control1_bus_idx: IntVec = np.zeros(nelm, dtype=int)
        self.control2_bus_idx: IntVec = np.zeros(nelm, dtype=int)
        self.control1_branch_idx: IntVec = np.zeros(nelm, dtype=int)
        self.control2_branch_idx: IntVec = np.zeros(nelm, dtype=int)

    def slice(self, elm_idx: IntVec, bus_idx: IntVec, logger: Logger | None) -> "VscData":
        """
        Slice branch data by given indices
        :param elm_idx: array of branch indices
        :param bus_idx: array of bus indices
        :param logger: Logger
        :return: new BranchData instance
        """

        data, bus_map = super().slice(elm_idx, bus_idx, logger)
        data: VscData = data
        data.__class__ = VscData

        data.Kdp = self.Kdp[elm_idx]
        data.alpha1 = self.alpha1[elm_idx]
        data.alpha2 = self.alpha2[elm_idx]
        data.alpha3 = self.alpha3[elm_idx]

        data.control1 = self.control1[elm_idx]
        data.control2 = self.control2[elm_idx]

        data.control1_val = self.control1_val[elm_idx]
        data.control2_val = self.control2_val[elm_idx]

        data.control1_bus_idx = self.control1_bus_idx[elm_idx]
        data.control2_bus_idx = self.control2_bus_idx[elm_idx]

        # TODO: think about how to re-map this stuff
        data.control1_branch_idx = self.control1_branch_idx[elm_idx]
        data.control2_branch_idx = self.control2_branch_idx[elm_idx]

        # br_map: Dict[int, int] = {o: i for i, o in enumerate(bus_idx)}
        for k in range(data.nelm):
            data.control1_bus_idx[k] = bus_map.get(data.control1_bus_idx[k], -1)

            if data.control1_bus_idx[k] == -1:
                if logger is not None:
                    logger.add_error(f"Branch {k}, {self.names[k]} is connected to a disconnected node",
                                     value=data.control1_bus_idx[k])

            data.control1_bus_idx[k] = bus_map.get(data.control1_bus_idx[k], -1)

            if data.control1_bus_idx[k] == -1:
                if logger is not None:
                    logger.add_error(f"Branch {k}, {self.names[k]} is connected to a disconnected node",
                                     value=data.control1_bus_idx[k])

        return data

    def copy(self) -> "VscData":
        """
        Get a deep copy of this object
        :return: new BranchData instance
        """
        data: VscData = super().copy()
        data.__class__ = VscData

        data.Kdp = self.Kdp.copy()
        data.dc = self.dc.copy()
        data.alpha1 = self.alpha1.copy()
        data.alpha2 = self.alpha2.copy()
        data.alpha3 = self.alpha3.copy()

        data.control1 = self.control1.copy()
        data.control2 = self.control2.copy()

        data.control1_val = self.control1_val.copy()
        data.control2_val = self.control2_val.copy()

        data.control1_bus_idx = self.control1_bus_idx.copy()
        data.control2_bus_idx = self.control2_bus_idx.copy()
        data.control1_branch_idx = self.control1_branch_idx.copy()
        data.control2_branch_idx = self.control2_branch_idx.copy()

        return data
