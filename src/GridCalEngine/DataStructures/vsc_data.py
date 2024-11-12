# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
from typing import List, Tuple
import scipy.sparse as sp
import GridCalEngine.Topology.topology as tp
from GridCalEngine.enumerations import ConverterControlType, GpfControlType
from GridCalEngine.basic_structures import Vec, IntVec, BoolVec, StrVec, ObjVec, Logger


class VscData:
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
        self.nbus: int = nbus
        self.nelm: int = nelm

        # Basic data
        self.names: StrVec = np.zeros(nelm, dtype=object)
        self.idtag: StrVec = np.zeros(nelm, dtype=object)
        self.branch_index: IntVec = np.zeros(nelm, dtype=int)
        self.F: IntVec = np.zeros(nelm, dtype=int)  # 'from' bus indices
        self.T: IntVec = np.zeros(nelm, dtype=int)  # 'to' bus indices
        self.active: BoolVec = np.zeros(nelm, dtype=bool)
        self.rate: Vec = np.zeros(nelm, dtype=float)
        self.contingency_factor: Vec = np.zeros(nelm, dtype=float)
        self.protection_rating_factor: Vec = np.zeros(nelm, dtype=float)
        self.monitor_loading: BoolVec = np.zeros(nelm, dtype=bool)
        self.mttf: Vec = np.zeros(nelm, dtype=float)
        self.mttr: Vec = np.zeros(nelm, dtype=float)
        self.cost: Vec = np.zeros(nelm, dtype=float)
        self.capex: Vec = np.zeros(nelm, dtype=float)
        self.opex: Vec = np.zeros(nelm, dtype=float)

        # Electrical properties
        self.R: Vec = np.zeros(nelm, dtype=float)
        self.X: Vec = np.zeros(nelm, dtype=float)
        self.R0: Vec = np.zeros(nelm, dtype=float)
        self.X0: Vec = np.zeros(nelm, dtype=float)
        self.R2: Vec = np.zeros(nelm, dtype=float)
        self.X2: Vec = np.zeros(nelm, dtype=float)
        self.G0sw: Vec = np.zeros(nelm, dtype=float)
        self.Beq: Vec = np.zeros(nelm, dtype=float)
        self.Beq_max: Vec = np.zeros(nelm, dtype=float)
        self.Beq_min: Vec = np.zeros(nelm, dtype=float)
        self.tap_module: Vec = np.zeros(nelm, dtype=float)
        self.tap_module_max: Vec = np.zeros(nelm, dtype=float)
        self.tap_module_min: Vec = np.zeros(nelm, dtype=float)

        # Loss Params
        self.alpha1: Vec = np.zeros(nelm, dtype=float)
        self.alpha2: Vec = np.zeros(nelm, dtype=float)
        self.alpha3: Vec = np.zeros(nelm, dtype=float)

        # Connection Matrix
        self.C_vsc_bus_f: sp.lil_matrix = sp.lil_matrix((nelm, nbus),
                                                        dtype=int)  # this ons is just for splitting islands
        self.C_vsc_bus_t: sp.lil_matrix = sp.lil_matrix((nelm, nbus),
                                                        dtype=int)  # this ons is just for splitting islands

        # Control settings
        # Get rid of ConverterControlType? Visible in vsc_data but not imported. Why?
        self.control_mode: List[ConverterControlType] = [ConverterControlType.type_0_free] * nelm

        self.kdp: Vec = np.zeros(nelm, dtype=float)
        self.Pdc_set: Vec = np.zeros(nelm, dtype=float)
        self.Qac_set: Vec = np.zeros(nelm, dtype=float)
        self.Vac_set: Vec = np.zeros(nelm, dtype=float)
        self.Vdc_set: Vec = np.zeros(nelm, dtype=float)

        # GENERALISED PF
        self.gpf_ctrl1_elm: ObjVec = np.empty(nelm, dtype=object)
        self.gpf_ctrl1_mode: List[GpfControlType] = [GpfControlType.type_None] * nelm
        self.gpf_ctrl1_val: Vec = np.zeros(nelm, dtype=float)
        self.gpf_ctrl2_elm: ObjVec = np.empty(nelm, dtype=object)
        self.gpf_ctrl2_mode: List[GpfControlType] = [GpfControlType.type_None] * nelm
        self.gpf_ctrl2_val: Vec = np.zeros(nelm, dtype=float)

        self.name_to_idx: dict = dict()

    def size(self) -> int:
        """
        Get size of the VSC data structure
        :return: number of VSC elements
        """
        return self.nelm

    def copy(self) -> "VscData":
        """
        Get a deep copy of this VscData object
        :return: new VscData instance
        """
        data = VscData(nelm=self.nelm, nbus=self.nbus)

        data.names = self.names.copy()
        data.idtag = self.idtag.copy()
        data.branch_index = self.branch_index.copy()
        data.F = self.F.copy()
        data.T = self.T.copy()
        data.active = self.active.copy()
        data.rate = self.rate.copy()
        data.contingency_factor = self.contingency_factor.copy()
        data.protection_rating_factor = self.protection_rating_factor.copy()
        data.monitor_loading = self.monitor_loading.copy()
        data.mttf = self.mttf.copy()
        data.mttr = self.mttr.copy()
        data.cost = self.cost.copy()
        data.capex = self.capex.copy()
        data.opex = self.opex.copy()

        # Electrical properties
        data.R = self.R.copy()
        data.X = self.X.copy()
        data.R0 = self.R0.copy()
        data.X0 = self.X0.copy()
        data.R2 = self.R2.copy()
        data.X2 = self.X2.copy()
        data.G0sw = self.G0sw.copy()
        data.Beq = self.Beq.copy()
        data.Beq_max = self.Beq_max.copy()
        data.Beq_min = self.Beq_min.copy()
        data.tap_module = self.tap_module.copy()
        data.tap_module_max = self.tap_module_max.copy()
        data.tap_module_min = self.tap_module_min.copy()

        # Loss Params
        data.alpha1 = self.alpha1.copy()
        data.alpha2 = self.alpha2.copy()
        data.alpha3 = self.alpha3.copy()

        # Connection Matrix
        data.C_vsc_bus_f = self.C_vsc_bus_f.copy()
        data.C_vsc_bus_t = self.C_vsc_bus_t.copy()

        # Control settings
        data.control_mode = self.control_mode.copy()
        data.kdp = self.kdp.copy()
        data.Pdc_set = self.Pdc_set.copy()
        data.Qac_set = self.Qac_set.copy()
        data.Vac_set = self.Vac_set.copy()
        data.Vdc_set = self.Vdc_set.copy()

        # Generalized PF
        data.gpf_ctrl1_elm = self.gpf_ctrl1_elm.copy()
        data.gpf_ctrl1_mode = self.gpf_ctrl1_mode.copy()
        data.gpf_ctrl1_val = self.gpf_ctrl1_val.copy()
        data.gpf_ctrl2_elm = self.gpf_ctrl2_elm.copy()
        data.gpf_ctrl2_mode = self.gpf_ctrl2_mode.copy()
        data.gpf_ctrl2_val = self.gpf_ctrl2_val.copy()

        data.name_to_idx = self.name_to_idx.copy()

        return data

    def slice(self, elm_idx: IntVec, bus_idx: IntVec, logger: Logger | None) -> "VscData":
        """
        Slice VSC data by given indices
        :param elm_idx: array of VSC element indices
        :param bus_idx: array of bus indices
        :param logger: Logger
        :return: new VscData instance
        """
        data = VscData(nelm=len(elm_idx), nbus=len(bus_idx))

        # Basic data
        data.names = self.names[elm_idx]
        data.idtag = self.idtag[elm_idx]
        data.branch_index = self.branch_index[elm_idx]
        data.F = self.F[elm_idx]
        data.T = self.T[elm_idx]
        data.active = self.active[elm_idx]
        data.rate = self.rate[elm_idx]
        data.contingency_factor = self.contingency_factor[elm_idx]
        data.protection_rating_factor = self.protection_rating_factor[elm_idx]
        data.monitor_loading = self.monitor_loading[elm_idx]
        data.mttf = self.mttf[elm_idx]
        data.mttr = self.mttr[elm_idx]
        data.cost = self.cost[elm_idx]
        data.capex = self.capex[elm_idx]
        data.opex = self.opex[elm_idx]

        # Electrical properties
        data.R = self.R[elm_idx]
        data.X = self.X[elm_idx]
        data.R0 = self.R0[elm_idx]
        data.X0 = self.X0[elm_idx]
        data.R2 = self.R2[elm_idx]
        data.X2 = self.X2[elm_idx]
        data.G0sw = self.G0sw[elm_idx]
        data.Beq = self.Beq[elm_idx]
        data.Beq_max = self.Beq_max[elm_idx]
        data.Beq_min = self.Beq_min[elm_idx]
        data.tap_module = self.tap_module[elm_idx]
        data.tap_module_max = self.tap_module_max[elm_idx]
        data.tap_module_min = self.tap_module_min[elm_idx]

        # Loss Params
        data.alpha1 = self.alpha1[elm_idx]
        data.alpha2 = self.alpha2[elm_idx]
        data.alpha3 = self.alpha3[elm_idx]

        # Connection Matrices
        data.C_vsc_bus_f = self.C_vsc_bus_f[np.ix_(elm_idx, bus_idx)]
        data.C_vsc_bus_t = self.C_vsc_bus_t[np.ix_(elm_idx, bus_idx)]

        # Control settings
        data.control_mode = [self.control_mode[i] for i in elm_idx]
        data.kdp = self.kdp[elm_idx]
        data.Pdc_set = self.Pdc_set[elm_idx]
        data.Qac_set = self.Qac_set[elm_idx]
        data.Vac_set = self.Vac_set[elm_idx]
        data.Vdc_set = self.Vdc_set[elm_idx]

        # Generalized PF controls
        data.gpf_ctrl1_elm = self.gpf_ctrl1_elm[elm_idx]
        data.gpf_ctrl1_mode = [self.gpf_ctrl1_mode[i] for i in elm_idx]
        data.gpf_ctrl1_val = self.gpf_ctrl1_val[elm_idx]
        data.gpf_ctrl2_elm = self.gpf_ctrl2_elm[elm_idx]
        data.gpf_ctrl2_mode = [self.gpf_ctrl2_mode[i] for i in elm_idx]
        data.gpf_ctrl2_val = self.gpf_ctrl2_val[elm_idx]

        # Copy the name-to-index dictionary
        data.name_to_idx = {name: idx for name, idx in self.name_to_idx.items() if idx in elm_idx}

        # Remap F and T bus indices and check for disconnections
        bus_map = {o: i for i, o in enumerate(bus_idx)}
        for k in range(data.nelm):
            data.F[k] = bus_map.get(data.F[k], -1)
            if data.F[k] == -1:
                if logger is not None:
                    logger.add_error(f"VSC element {k}, {self.names[k]} is connected to a disconnected node", value=data.F[k])
                data.active[k] = 0

            data.T[k] = bus_map.get(data.T[k], -1)
            if data.T[k] == -1:
                if logger is not None:
                    logger.add_error(f"VSC element {k}, {self.names[k]} is connected to a disconnected node", value=data.T[k])
                data.active[k] = 0

        return data

    def get_island(self, bus_idx: IntVec) -> IntVec:
        """
        Get the array of VSC indices that belong to the island given by the bus indices
        :param bus_idx: array of bus indices
        :return: array of island VSC indices
        """
        if self.nelm:
            return tp.get_elements_of_the_island(
                C_element_bus=self.C_vsc_bus_f + self.C_vsc_bus_t,
                island=bus_idx,
                active=self.active
            )
        else:
            return np.zeros(0, dtype=int)


    def update_loading(self, Pbus: Vec, Vbus: Vec, Sbase: float):
        """
        Calculate loading and losses for each VSC based on current power and voltage levels.
        :param Pbus: Array of active power at each bus
        :param Vbus: Array of voltage magnitude at each bus
        :param Sbase: System base power
        :return: Updated power and loss values
        """
        loading = np.zeros(self.nelm, dtype=float)
        losses = np.zeros(self.nelm, dtype=float)
        for i in range(self.nelm):
            if self.active[i]:
                # Calculate power flow and losses based on control mode and settings
                # Placeholder logic; real implementation needed based on specific control modes and VSC characteristics
                loading[i] = Pbus[self.F[i]] / self.Pmax[i]
                # Assume some loss model, for example, proportional to the square of the current flow
                losses[i] = 0.01 * Pbus[self.F[i]] ** 2 / Sbase  # Simple loss model: 1% of power squared

        return loading, losses

    def __len__(self):
        """
        Returns the number of VSCs managed by this data structure.
        :return: number of VSC elements
        """
        return self.nelm

    def get_bus_indices_f(self) -> IntVec:
        """
        Get the 'from' bus indices for all VSC elements.
        :return: Array of 'from' bus indices.
        """
        return self.F

    def get_bus_indices_t(self) -> IntVec:
        """
        Get the 'to' bus indices for all VSC elements.
        :return: Array of 'to' bus indices.
        """
        return self.T

    def get_qmax_to_per_bus(self) -> Vec:
        """
        Get the maximum reactive power at the 'to' buses for all VSC elements.
        :return: Array of maximum reactive power values at 'to' buses.
        """
        # Assuming a method to calculate or retrieve Qmax for the 'to' side
        # Placeholder implementation
        return np.zeros(self.nelm, dtype=float)  # Replace with actual implementation

    def get_qmin_to_per_bus(self) -> Vec:
        """
        Get the minimum reactive power at the 'to' buses for all VSC elements.
        :return: Array of minimum reactive power values at 'to' buses.
        """
        # Assuming a method to calculate or retrieve Qmin for the 'to' side
        # Placeholder implementation
        return np.zeros(self.nelm, dtype=float)  # Replace with actual implementation

    def get_angle_droop_in_pu_rad(self) -> Vec:
        """
        Get the angle droop control settings in per-unit radians for all VSC elements.
        :return: Array of angle droop settings in per-unit radians.
        """
        # Placeholder implementation
        return np.zeros(self.nelm, dtype=float)  # Replace with actual implementation based on VSC control settings

    def get_inter_areas(self, buses_areas_1, buses_areas_2) -> List[Tuple[int, float]]:
        """
        Get the VSCs that join two areas.
        :param buses_areas_1: Area from
        :param buses_areas_2: Area to
        :return: List of (VSC index, flow sense w.r.t the area exchange)
        """
        # Placeholder implementation
        lst = []
        for k in range(self.nelm):
            if self.F[k] in buses_areas_1 and self.T[k] in buses_areas_2:
                lst.append((k, 1.0))
            elif self.F[k] in buses_areas_2 and self.T[k] in buses_areas_1:
                lst.append((k, -1.0))
        return lst
