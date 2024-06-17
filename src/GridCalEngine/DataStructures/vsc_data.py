import numpy as np
from typing import List, Tuple
import scipy.sparse as sp
from GridCalEngine.enumerations import ConverterControlType
from GridCalEngine.basic_structures import Vec, IntVec, BoolVec, StrVec

class VscData:
    """
    VscData class provides a structured model for managing data related to Voltage Source Converters (VSC) in power grid simulations.
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
        self.control_mode: List[ConverterControlType] = [ConverterControlType.type_0_free] * nelm
        self.kdp: Vec = np.zeros(nelm, dtype=float)
        self.Pdc_set: Vec = np.zeros(nelm, dtype=float)
        self.Qac_set: Vec = np.zeros(nelm, dtype=float)
        self.Vac_set: Vec = np.zeros(nelm, dtype=float)
        self.Vdc_set: Vec = np.zeros(nelm, dtype=float)


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
