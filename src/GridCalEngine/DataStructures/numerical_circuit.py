# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from typing import List, Tuple, Dict, Union
from enum import Enum
import numba as nb
import numpy as np
import pandas as pd
import scipy.sparse as sp

from GridCalEngine.Devices import RemedialAction
from GridCalEngine.Topology.simulation_indices import SimulationIndices
from GridCalEngine.Topology.topology import find_islands
from GridCalEngine.basic_structures import Logger
from GridCalEngine.basic_structures import Vec, IntVec, CxVec, BoolVec, Mat, CxMat
from GridCalEngine.enumerations import BusMode, ContingencyOperationTypes
import GridCalEngine.Topology.topology as tp
import GridCalEngine.Topology.simulation_indices as si
import GridCalEngine.Topology.admittance_matrices as ycalc
from GridCalEngine.DataStructures.battery_data import BatteryData
from GridCalEngine.DataStructures.passive_branch_data import PassiveBranchData
from GridCalEngine.DataStructures.active_branch_data import ActiveBranchData
from GridCalEngine.DataStructures.bus_data import BusData
from GridCalEngine.DataStructures.generator_data import GeneratorData
from GridCalEngine.DataStructures.hvdc_data import HvdcData
from GridCalEngine.DataStructures.vsc_data import VscData
from GridCalEngine.DataStructures.load_data import LoadData
from GridCalEngine.DataStructures.shunt_data import ShuntData
from GridCalEngine.DataStructures.fluid_node_data import FluidNodeData
from GridCalEngine.DataStructures.fluid_turbine_data import FluidTurbineData
from GridCalEngine.DataStructures.fluid_pump_data import FluidPumpData
from GridCalEngine.DataStructures.fluid_p2x_data import FluidP2XData
from GridCalEngine.DataStructures.fluid_path_data import FluidPathData
from GridCalEngine.Devices.Aggregation.investment import Investment
from GridCalEngine.Devices.Aggregation.contingency import Contingency

ALL_STRUCTS = Union[
    BusData,
    GeneratorData,
    BatteryData,
    LoadData,
    ShuntData,
    PassiveBranchData,
    HvdcData,
    FluidNodeData,
    FluidTurbineData,
    FluidPumpData,
    FluidP2XData,
    FluidPathData
]


@nb.njit(cache=True)
def build_reducible_branches_C_coo(F: IntVec, T: IntVec, reducible: IntVec, active: IntVec):
    """
    Build the COO coordinates of the C matrix
    :param F: branches From indices
    :param T: branches To indices
    :param reducible: branches reducible array
    :param active: branches active array
    :return: i, j, data, n_red
    """

    """
    
    C = sp.lil_matrix((self.passive_branch_data.nelm, self.bus_data.nbus))
        n_red = 0
        for k in range(self.passive_branch_data.nelm):
            if self.passive_branch_data.reducible[k] and self.passive_branch_data.active[k]:
                f = self.passive_branch_data.F[k]
                t = self.passive_branch_data.T[k]
                C[k, f] = 1
                C[k, t] = 1
                n_red += 1 
    """
    nelm = len(F)
    i = np.empty(nelm * 2, dtype=np.int64)
    j = np.empty(nelm * 2, dtype=np.int64)
    data = np.empty(nelm * 2, dtype=np.int64)
    ii = 0
    n_red = 0
    for k in range(nelm):
        if reducible[k] and active[k]:
            # C[k, f] = 1
            i[ii] = k
            j[ii] = F[k]
            data[ii] = 1
            ii += 1

            # C[k, t] = 1
            i[ii] = k
            j[ii] = T[k]
            data[ii] = 1
            ii += 1

            n_red += 1

    return i[:ii], j[:ii], data[:ii], n_red


@nb.njit(cache=True)
def build_branches_C_coo_2(bus_active: IntVec,
                           F1: IntVec, T1: IntVec, active1: IntVec,
                           F2: IntVec, T2: IntVec, active2: IntVec):
    """
    Build the COO coordinates of the C matrix
    :param bus_active: array of bus active values
    :param F1: Passive branches from bus indices array
    :param T1: Passive branches to bus indices array
    :param active1: Passive branches active array
    :param F2: VSC from buses indices array
    :param T2: VSC to buses indices array
    :param active2: VSC active array
    :return:
    """

    """

    C = sp.lil_matrix((n_elm, self.bus_data.nbus), dtype=int)
        for struct in structs:
            for k in range(struct.nelm):
                f = struct.F[k]
                t = struct.T[k]
                if struct.active[k] and self.bus_data.active[f] and self.bus_data.active[t]:
                    C[k, f] = 1
                    C[k, t] = 1
    """
    nelm = len(F1) + len(F2)
    i = np.empty(nelm * 2, dtype=np.int64)
    j = np.empty(nelm * 2, dtype=np.int64)
    data = np.empty(nelm * 2, dtype=np.int64)

    ii = 0

    for k in range(len(F1)):
        if active1[k]:
            f = F1[k]
            t = T1[k]
            if bus_active[f] and bus_active[t]:
                # C[k, f] = 1
                i[ii] = k
                j[ii] = f
                data[ii] = 1
                ii += 1

                # C[k, t] = 1
                i[ii] = k
                j[ii] = t
                data[ii] = 1
                ii += 1

    for k in range(len(F2)):
        if active2[k]:
            f = F2[k]
            t = T2[k]
            if bus_active[f] and bus_active[t]:
                # C[k, f] = 1
                i[ii] = k
                j[ii] = f
                data[ii] = 1
                ii += 1

                # C[k, t] = 1
                i[ii] = k
                j[ii] = t
                data[ii] = 1
                ii += 1

    return i[:ii], j[:ii], data[:ii], nelm


@nb.njit(cache=True)
def build_branches_C_coo_3(bus_active: IntVec,
                           F1: IntVec, T1: IntVec, active1: IntVec,
                           F2: IntVec, T2: IntVec, active2: IntVec,
                           F3: IntVec, T3: IntVec, active3: IntVec):
    """
    Build the COO coordinates of the C matrix
    :param bus_active: array of bus active values
    :param F1: Passive branches from bus indices array
    :param T1: Passive branches to bus indices array
    :param active1: Passive branches active array
    :param F2: VSC from buses indices array
    :param T2: VSC to buses indices array
    :param active2: VSC active array
    :param F3: HVDC from bus indices array
    :param T3: HVDC to bus indices array
    :param active3: HVDC active array
    :return: i, j, data, nelm to build C(nelm, nbus)
    """

    """

    C = sp.lil_matrix((n_elm, self.bus_data.nbus), dtype=int)
        for struct in structs:
            for k in range(struct.nelm):
                f = struct.F[k]
                t = struct.T[k]
                if struct.active[k] and self.bus_data.active[f] and self.bus_data.active[t]:
                    C[k, f] = 1
                    C[k, t] = 1
    """
    nelm = len(F1) + len(F2) + len(F3)
    i = np.empty(nelm * 2, dtype=np.int64)
    j = np.empty(nelm * 2, dtype=np.int64)
    data = np.empty(nelm * 2, dtype=np.int64)

    ii = 0

    for k in range(len(F1)):
        if active1[k]:
            f = F1[k]
            t = T1[k]
            if bus_active[f] and bus_active[t]:
                # C[k, f] = 1
                i[ii] = k
                j[ii] = f
                data[ii] = 1
                ii += 1

                # C[k, t] = 1
                i[ii] = k
                j[ii] = t
                data[ii] = 1
                ii += 1

    for k in range(len(F2)):
        if active2[k]:
            f = F2[k]
            t = T2[k]
            if bus_active[f] and bus_active[t]:
                # C[k, f] = 1
                i[ii] = k
                j[ii] = f
                data[ii] = 1
                ii += 1

                # C[k, t] = 1
                i[ii] = k
                j[ii] = t
                data[ii] = 1
                ii += 1

    for k in range(len(F3)):
        if active3[k]:
            f = F3[k]
            t = T3[k]
            if bus_active[f] and bus_active[t]:
                # C[k, f] = 1
                i[ii] = k
                j[ii] = f
                data[ii] = 1
                ii += 1

                # C[k, t] = 1
                i[ii] = k
                j[ii] = t
                data[ii] = 1
                ii += 1

    return i[:ii], j[:ii], data[:ii], nelm


def check_arr(arr: Vec | IntVec | BoolVec | CxVec,
              arr_expected: Vec | IntVec | BoolVec | CxVec,
              tol: float, name: str, test: str, logger: Logger) -> int:
    """

    :param arr:
    :param arr_expected:
    :param tol:
    :param name:
    :param test:
    :param logger:
    :return:
    """
    if arr.shape != arr_expected.shape:
        logger.add_error(msg="Different shape",
                         device=name,
                         device_property=test,
                         value=str(arr.shape),
                         expected_value=str(arr_expected.shape))
        return 1

    if np.allclose(arr, arr_expected, atol=tol):
        return 0
    else:
        if arr.dtype in (np.bool_, bool):
            diff = arr.astype(int) - arr_expected.astype(int)
            logger.add_error(msg="Numeric differences",
                             device=name,
                             device_property=test,
                             value=f"min diff: {diff.min()}, max diff: {diff.max()}",
                             expected_value=tol)
        else:
            diff = arr - arr_expected
            logger.add_error(msg="Numeric differences",
                             device=name,
                             device_property=test,
                             value=f"min diff: {diff.min()}, max diff: {diff.max()}",
                             expected_value=tol)
        return 1


class DataStructType(Enum):
    BUSDATA = 1
    BRANCHDATA = 2
    HVDCDATA = 3
    GENERATORDATA = 4
    BATTERYDATA = 5
    LOADDATA = 6
    SHUNTDATA = 7
    VSCDATA = 8
    NOSTRUCT = 0


class NumericalCircuit:
    """
    Class storing the calculation information of the devices
    """
    available_structures = {
        "Bus arrays": [
            'V', 'Va', 'Vm',
            'S', 'P', 'Q',
            'I',
            'Y',
            'Qmin',
            'Qmax',
        ],
        "Bus indices": [
            'Types',
            'bus_ctrl',
            'pq',
            'pqv',
            'p',
            'pv',
            'vd'
        ],
        "Branch arrays": [
            'tap_f',
            'tap_t',
            'Pf_set',
            'Qf_set',
            'Pt_set',
            'Qt_set',
        ],
        "Branch indices": [
            'branch_ctrl',
            'k_pf_tau',
            'k_pt_tau',
            'k_qf_m',
            'k_qt_m',
            'k_qf_beq',
            'k_v_m',
            'k_v_beq',
        ],
        "System matrices": [
            'Ybus',
            'G',
            'B',
            'Yf',
            'Yt',
            'Bbus',
            'Bf',
            'Cf',
            'Ct',
            "B'",
            "B''",
            'Yshunt',
            'Yseries',
        ],
        "Power flow arrays": [
            'idx_dPf',
            'idx_dQf',
            'idx_dPt',
            'idx_dQt',
            'idx_dVa',
            'idx_dVm',
            'idx_dm',
            'idx_dtau',
            'x',
            'f(x)',
            'Jacobian',
        ]
    }

    def __init__(self,
                 nbus: int,
                 nbr: int,
                 nhvdc: int,
                 nvsc: int,
                 nload: int,
                 ngen: int,
                 nbatt: int,
                 nshunt: int,
                 nfluidnode: int,
                 nfluidturbine: int,
                 nfluidpump: int,
                 nfluidp2x: int,
                 nfluidpath: int,
                 sbase: float,
                 t_idx: int = 0):
        """
        Numerical circuit
        :param nbus: Number of calculation buses
        :param nbr: Number of calculation Branches
        :param nhvdc: Number of calculation hvdc devices
        :param nvsc: Number of calculation vsc devices
        :param nload:  Number of calculation load devices
        :param ngen:  Number of calculation generator devices
        :param nbatt:  Number of calculation battery devices
        :param nshunt:  Number of calculation shunt devices
        :param sbase:  Base power (MVA)
        :param t_idx:  Time index
        """

        self.nbus: int = nbus
        self.nbr: int = nbr
        self.t_idx: int = t_idx

        self.nload: int = nload
        self.ngen: int = ngen
        self.nbatt: int = nbatt
        self.nshunt: int = nshunt
        self.nhvdc: int = nhvdc
        self.nvsc: int = nvsc

        self.nfluidnode: int = nfluidnode
        self.nfluidturbine: int = nfluidturbine
        self.nfluidpump: int = nfluidpump
        self.nfluidp2x: int = nfluidp2x
        self.nfluidpath: int = nfluidpath

        self.Sbase: float = sbase

        # --------------------------------------------------------------------------------------------------------------
        # Data structures
        # --------------------------------------------------------------------------------------------------------------
        self.bus_data: BusData = BusData(nbus=nbus)
        self.passive_branch_data: PassiveBranchData = PassiveBranchData(nelm=nbr, nbus=nbus)
        self.active_branch_data: ActiveBranchData = ActiveBranchData(nelm=nbr, nbus=nbus)
        self.hvdc_data: HvdcData = HvdcData(nelm=nhvdc, nbus=nbus)
        self.vsc_data: VscData = VscData(nelm=nvsc, nbus=nbus)

        self.load_data: LoadData = LoadData(nelm=nload, nbus=nbus)
        self.battery_data: BatteryData = BatteryData(nelm=nbatt, nbus=nbus)
        self.generator_data: GeneratorData = GeneratorData(nelm=ngen, nbus=nbus)
        self.shunt_data: ShuntData = ShuntData(nelm=nshunt, nbus=nbus)

        self.fluid_node_data: FluidNodeData = FluidNodeData(nelm=nfluidnode)
        self.fluid_turbine_data: FluidTurbineData = FluidTurbineData(nelm=nfluidturbine)
        self.fluid_pump_data: FluidPumpData = FluidPumpData(nelm=nfluidpump)
        self.fluid_p2x_data: FluidP2XData = FluidP2XData(nelm=nfluidp2x)
        self.fluid_path_data: FluidPathData = FluidPathData(nelm=nfluidpath)

        # this array is used to keep track of the bus topological reduction
        self.__bus_map_arr = np.arange(self.bus_data.nbus, dtype=int)

        self.__topology_performed = False

        # map to relate the elements idtag to their structures
        # used during contingency analysis to modify the structures active, etc...
        # based on the device idtag
        self.structs_idtag_dict: Dict[str, Tuple[DataStructType, int]] = dict()

    def propagate_bus_result(self, bus_magnitude: Vec | CxVec):
        """
        This function applies the __bus_map_arr to a calculated magnitude to
        propagate the calculated nodal result
        :param bus_magnitude: some array of the size of buses (all)
        :return: propagated results
        """
        return bus_magnitude[self.__bus_map_arr]

    def propagate_bus_result_mat(self, bus_magnitude: Mat | CxMat):
        """
        This function applies the __bus_map_arr to a calculated magnitude to
        propagate the calculated nodal result
        :param bus_magnitude: some array of the size of buses (all)
        :return: propagated results
        """
        return bus_magnitude[:, self.__bus_map_arr]

    @property
    def topology_performed(self) -> bool:
        """
        Flag indicating if topology processing happened here
        :return:
        """
        return self.__topology_performed

    def get_reduction_bus_mapping(self) -> IntVec:
        """
        Get array is used to keep track of the bus topological reduction
        :return: IntVec
        """
        return self.__bus_map_arr

    def get_power_injections(self) -> CxVec:
        """
        Compute the power
        :return: return the array of power Injections in MW if normalized is false, in p.u. otherwise
        """

        # load
        Sbus = self.load_data.get_injections_per_bus()  # MW (negative already)

        # generators
        Sbus += self.generator_data.get_injections_per_bus()

        # battery
        Sbus += self.battery_data.get_injections_per_bus()

        return Sbus

    def get_power_injections_pu(self) -> CxVec:
        """
        Compute the power
        :return: return the array of power Injections in MW if normalized is false, in p.u. otherwise
        """
        return self.get_power_injections() / self.Sbase

    def get_current_injections_pu(self) -> CxVec:
        """

        :return:
        """
        return self.load_data.get_current_injections_per_bus() / self.Sbase

    def get_admittance_injections_pu(self) -> CxVec:
        """

        :return:
        """
        return self.load_data.get_admittance_injections_per_bus() / self.Sbase

    def get_Yshunt_bus_pu(self) -> CxVec:
        """

        :return:
        """
        return self.shunt_data.get_injections_per_bus() / self.Sbase

    def consolidate_information(self) -> None:
        """
        Consolidates the information of this object
        """

        self.nbus = len(self.bus_data)
        self.nbr = len(self.passive_branch_data)
        self.nhvdc = len(self.hvdc_data)
        self.nvsc = len(self.vsc_data)
        self.nload = len(self.load_data)
        self.ngen = len(self.generator_data)
        self.nbatt = len(self.battery_data)
        self.nshunt = len(self.shunt_data)

        # self.bus_data.installed_power = self.generator_data.get_installed_power_per_bus()
        # self.bus_data.installed_power += self.battery_data.get_installed_power_per_bus()

        if self.active_branch_data.any_pf_control is False:
            if self.vsc_data.nelm > 0:
                self.active_branch_data.any_pf_control = True

    def copy(self) -> "NumericalCircuit":
        """
        Deep copy of ths object
        :return: NumericalCircuit instance
        """
        nc = NumericalCircuit(nbus=self.nbus,
                              nbr=self.nbr,
                              nhvdc=self.nhvdc,
                              nvsc=self.nvsc,
                              nload=self.nload,
                              ngen=self.ngen,
                              nbatt=self.nbatt,
                              nshunt=self.nshunt,
                              nfluidnode=self.nfluidnode,
                              nfluidturbine=self.nfluidturbine,
                              nfluidpump=self.nfluidpump,
                              nfluidp2x=self.nfluidp2x,
                              nfluidpath=self.nfluidpath,
                              sbase=self.Sbase,
                              t_idx=self.t_idx)

        nc.bus_data = self.bus_data.copy()
        nc.passive_branch_data = self.passive_branch_data.copy()
        nc.hvdc_data = self.hvdc_data.copy()
        nc.load_data = self.load_data.copy()
        nc.shunt_data = self.shunt_data.copy()
        nc.generator_data = self.generator_data.copy()
        nc.battery_data = self.battery_data.copy()
        nc.fluid_node_data = self.fluid_node_data.copy()
        nc.fluid_turbine_data = self.fluid_turbine_data.copy()
        nc.fluid_pump_data = self.fluid_pump_data.copy()
        nc.fluid_p2x_data = self.fluid_p2x_data.copy()
        nc.fluid_path_data = self.fluid_path_data.copy()
        nc.structs_idtag_dict = self.structs_idtag_dict.copy()
        nc.consolidate_information()

        return nc

    def init_idtags_dict(self):
        """
        Initialize the internal structure for idtags querying
        :return:
        """
        self.structs_idtag_dict.clear()

        for i, idtag in enumerate(self.passive_branch_data.idtag):
            self.structs_idtag_dict[str(idtag)] = (DataStructType.BRANCHDATA, i)

        for i, idtag in enumerate(self.generator_data.idtag):
            self.structs_idtag_dict[str(idtag)] = (DataStructType.GENERATORDATA, i)

        for i, idtag in enumerate(self.hvdc_data.idtag):
            self.structs_idtag_dict[str(idtag)] = (DataStructType.HVDCDATA, i)

        for i, idtag in enumerate(self.battery_data.idtag):
            self.structs_idtag_dict[str(idtag)] = (DataStructType.BATTERYDATA, i)

        for i, idtag in enumerate(self.shunt_data.idtag):
            self.structs_idtag_dict[str(idtag)] = (DataStructType.SHUNTDATA, i)

        for i, idtag in enumerate(self.load_data.idtag):
            self.structs_idtag_dict[str(idtag)] = (DataStructType.LOADDATA, i)

        for i, idtag in enumerate(self.vsc_data.idtag):
            self.structs_idtag_dict[str(idtag)] = (DataStructType.VSCDATA, i)

        for i, idtag in enumerate(self.bus_data.idtag):
            self.structs_idtag_dict[str(idtag)] = (DataStructType.BUSDATA, i)

    def query_idtag(self, idtag: str) -> Tuple[DataStructType, int]:
        """
        Query the structure and index where an idtag exists
        :param idtag: idtag
        :return: DataStructType, integer position
        """
        # lazy initialization in case we forgot...
        if len(self.structs_idtag_dict) == 0:
            if self.bus_data.nbus > 0 or self.passive_branch_data.nelm > 0:
                self.init_idtags_dict()

        return self.structs_idtag_dict.get(idtag, (DataStructType.NOSTRUCT, 0))

    def set_investments_status(self, investments_list: List[Investment], status: int) -> None:
        """
        Set the status of a list of investments
        :param investments_list: list of investments
        :param status: status to set in the internal structures
        """

        for inv in investments_list:

            structure, idx = self.query_idtag(inv.device_idtag)

            if structure == DataStructType.NOSTRUCT:
                raise Exception('Could not find the idtag, is this a programming bug?')

            elif structure == DataStructType.BRANCHDATA:
                self.passive_branch_data.active[idx] = status

            elif structure == DataStructType.GENERATORDATA:
                self.generator_data.active[idx] = status

            elif structure == DataStructType.HVDCDATA:
                self.hvdc_data.active[idx] = status

            elif structure == DataStructType.BUSDATA:
                self.bus_data.active[idx] = status

            elif structure == DataStructType.BATTERYDATA:
                self.battery_data.active[idx] = status

            elif structure == DataStructType.LOADDATA:
                self.load_data.active[idx] = status

            elif structure == DataStructType.SHUNTDATA:
                self.shunt_data.active[idx] = status

            elif structure == DataStructType.VSCDATA:
                self.vsc_data.active[idx] = status

    def set_con_or_ra_status(self,
                             event_list: List[Contingency | RemedialAction],
                             revert: bool = False) -> Vec:
        """
        Set the status of a list of contingencies or remedial actions
        :param event_list: list of contingencies and or remedial actions
        :param revert: if false, the contingencies are applied, else they are reversed
        :return: vector of power injection increments
        """

        # vector of power injection increments
        inj_increment = np.zeros(self.nbus)

        # apply the contingencies
        for cnt in event_list:

            structure, idx = self.query_idtag(cnt.device_idtag)

            if structure == DataStructType.NOSTRUCT:
                raise Exception('Could not find the idtag, is this a programming bug?')

            elif structure == DataStructType.BRANCHDATA:

                if cnt.prop == ContingencyOperationTypes.Active:
                    if revert:
                        self.passive_branch_data.active[idx] = int(not bool(cnt.value))
                    else:
                        self.passive_branch_data.active[idx] = int(cnt.value)
                else:
                    print(f'Unknown contingency property {cnt.prop} at {cnt.name} {cnt.idtag}')

            elif structure == DataStructType.GENERATORDATA:

                if cnt.prop == ContingencyOperationTypes.Active:
                    if revert:
                        self.generator_data.active[idx] = int(not bool(cnt.value))
                    else:
                        self.generator_data.active[idx] = int(cnt.value)

                elif cnt.prop == ContingencyOperationTypes.PowerPercentage:

                    inj_increment[self.generator_data.bus_idx[idx]] -= self.generator_data.p[idx]

                    if revert:
                        self.generator_data.p[idx] /= float(cnt.value / 100.0)
                    else:
                        self.generator_data.p[idx] *= float(cnt.value / 100.0)

                    inj_increment[self.generator_data.bus_idx[idx]] += self.generator_data.p[idx]
                else:
                    print(f'Unknown contingency property {cnt.prop} at {cnt.name} {cnt.idtag}')

            elif structure == DataStructType.HVDCDATA:
                if cnt.prop == ContingencyOperationTypes.Active:
                    if revert:
                        self.hvdc_data.active[idx] = int(not bool(cnt.value))
                    else:
                        self.hvdc_data.active[idx] = int(cnt.value)

                elif cnt.prop == ContingencyOperationTypes.PowerPercentage:

                    inj_increment[self.hvdc_data.F[idx]] += self.hvdc_data.Pset[idx]
                    inj_increment[self.hvdc_data.T[idx]] -= self.hvdc_data.Pset[idx]

                    if revert:
                        self.hvdc_data.Pset[idx] /= float(cnt.value / 100.0)
                    else:
                        self.hvdc_data.Pset[idx] *= float(cnt.value / 100.0)

                    inj_increment[self.hvdc_data.F[idx]] -= self.hvdc_data.Pset[idx]
                    inj_increment[self.hvdc_data.T[idx]] += self.hvdc_data.Pset[idx]
                else:
                    print(f'Unknown contingency property {cnt.prop} at {cnt.name} {cnt.idtag}')

            elif structure == DataStructType.BUSDATA:
                if cnt.prop == ContingencyOperationTypes.Active:
                    if revert:
                        self.bus_data.active[idx] = int(not bool(cnt.value))
                    else:
                        self.bus_data.active[idx] = int(cnt.value)
                else:
                    print(f'Unknown contingency property {cnt.prop} at {cnt.name} {cnt.idtag}')

            elif structure == DataStructType.BATTERYDATA:
                if cnt.prop == ContingencyOperationTypes.Active:
                    if revert:
                        self.battery_data.active[idx] = int(not bool(cnt.value))
                    else:
                        self.battery_data.active[idx] = int(cnt.value)

                elif cnt.prop == ContingencyOperationTypes.PowerPercentage:

                    inj_increment[self.battery_data.bus_idx[idx]] -= self.battery_data.p[idx]

                    if revert:
                        self.battery_data.p[idx] /= float(cnt.value / 100.0)
                    else:
                        self.battery_data.p[idx] *= float(cnt.value / 100.0)

                    inj_increment[self.battery_data.bus_idx[idx]] += self.battery_data.p[idx]
                else:
                    print(f'Unknown contingency property {cnt.prop} at {cnt.name} {cnt.idtag}')

            elif structure == DataStructType.LOADDATA:
                if cnt.prop == ContingencyOperationTypes.Active:
                    if revert:
                        self.load_data.active[idx] = int(not bool(cnt.value))
                    else:
                        self.load_data.active[idx] = int(cnt.value)

                elif cnt.prop == ContingencyOperationTypes.PowerPercentage:

                    inj_increment[self.load_data.bus_idx[idx]] -= self.load_data.S[idx].real

                    if revert:
                        self.load_data.S[idx] /= float(cnt.value / 100.0)
                    else:
                        self.load_data.S[idx] *= float(cnt.value / 100.0)

                    inj_increment[self.load_data.bus_idx[idx]] += self.load_data.S[idx].real
                else:
                    print(f'Unknown contingency property {cnt.prop} at {cnt.name} {cnt.idtag}')

            elif structure == DataStructType.SHUNTDATA:
                if cnt.prop == ContingencyOperationTypes.Active:
                    if revert:
                        self.shunt_data.active[idx] = int(not bool(cnt.value))
                    else:
                        self.shunt_data.active[idx] = int(cnt.value)

                elif cnt.prop == ContingencyOperationTypes.PowerPercentage:

                    inj_increment[self.shunt_data.bus_idx[idx]] -= self.shunt_data.Y[idx].real

                    if revert:
                        self.shunt_data.Y[idx] /= float(cnt.value / 100.0)
                    else:
                        self.shunt_data.Y[idx] *= float(cnt.value / 100.0)

                    inj_increment[self.shunt_data.bus_idx[idx]] += self.shunt_data.Y[idx].real
                else:
                    print(f'Unknown contingency property {cnt.prop} at {cnt.name} {cnt.idtag}')

            elif structure == DataStructType.VSCDATA:
                if cnt.prop == ContingencyOperationTypes.Active:
                    if revert:
                        self.vsc_data.active[idx] = int(not bool(cnt.value))
                    else:
                        self.vsc_data.active[idx] = int(cnt.value)
                else:
                    print(f'Unknown contingency property {cnt.prop} at {cnt.name} {cnt.idtag}')

        return inj_increment

    def get_simulation_indices(self, Sbus: CxVec | None = None,
                               bus_types: IntVec | None = None,
                               force_only_pq_pv_vd_types=False) -> si.SimulationIndices:
        """
        Get the simulation indices
        :param Sbus: Array of bus powers (optional)
        :param bus_types: different array of bus_types (optional)
        :param force_only_pq_pv_vd_types: if true, all bus types are forced into PQ PV or VD,
                                          for certain types of simulations that cannot handle other bus types
        :return: SimulationIndices
        """
        if Sbus is None:
            Sbus = self.get_power_injections_pu()

        if bus_types is None:
            bus_types = self.bus_data.bus_types

        return si.SimulationIndices(bus_types=bus_types,
                                    Pbus=Sbus.real,
                                    tap_module_control_mode=self.active_branch_data.tap_module_control_mode,
                                    tap_phase_control_mode=self.active_branch_data.tap_phase_control_mode,
                                    tap_controlled_buses=self.active_branch_data.tap_controlled_buses,
                                    is_converter=np.zeros(self.nbr, dtype=bool),
                                    F=self.passive_branch_data.F,
                                    T=self.passive_branch_data.T,
                                    is_dc_bus=self.bus_data.is_dc,
                                    force_only_pq_pv_vd_types=force_only_pq_pv_vd_types)

    def get_connectivity_matrices(self) -> tp.ConnectivityMatrices:
        """
        Get connectivity matrices
        :return:
        """
        return tp.compute_connectivity(
            branch_active=self.passive_branch_data.active.astype(int),
            Cf_=self.passive_branch_data.Cf.tocsc(),
            Ct_=self.passive_branch_data.Ct.tocsc()
        )

    def get_admittance_matrices(self) -> ycalc.AdmittanceMatrices:
        """
        Get Admittance structures
        :return: Admittance object
        """

        # compute admittances on demand
        return ycalc.compute_admittances(
            R=self.passive_branch_data.R,
            X=self.passive_branch_data.X,
            G=self.passive_branch_data.G,
            B=self.passive_branch_data.B,
            tap_module=self.active_branch_data.tap_module,
            vtap_f=self.passive_branch_data.virtual_tap_f,
            vtap_t=self.passive_branch_data.virtual_tap_t,
            tap_angle=self.active_branch_data.tap_angle,
            Cf=self.passive_branch_data.Cf.tocsc(),
            Ct=self.passive_branch_data.Ct.tocsc(),
            Yshunt_bus=self.get_Yshunt_bus_pu(),
            conn=self.passive_branch_data.conn,
            seq=1
        )

    def get_series_admittance_matrices(self) -> ycalc.SeriesAdmittanceMatrices:
        """

        :return:
        """
        return ycalc.compute_split_admittances(
            R=self.passive_branch_data.R,
            X=self.passive_branch_data.X,
            G=self.passive_branch_data.G,
            B=self.passive_branch_data.B,
            active=self.passive_branch_data.active.astype(int),
            tap_module=self.active_branch_data.tap_module,
            vtap_f=self.passive_branch_data.virtual_tap_f,
            vtap_t=self.passive_branch_data.virtual_tap_t,
            tap_angle=self.active_branch_data.tap_angle,
            Cf=self.passive_branch_data.Cf.tocsc(),
            Ct=self.passive_branch_data.Ct.tocsc(),
            Yshunt_bus=self.get_Yshunt_bus_pu(),
        )

    def get_fast_decoupled_amittances(self) -> ycalc.FastDecoupledAdmittanceMatrices:
        """

        :return:
        """
        return ycalc.compute_fast_decoupled_admittances(
            X=self.passive_branch_data.X,
            B=self.passive_branch_data.B,
            tap_module=self.active_branch_data.tap_module,
            active=self.passive_branch_data.active.astype(int),
            vtap_f=self.passive_branch_data.virtual_tap_f,
            vtap_t=self.passive_branch_data.virtual_tap_t,
            Cf=self.passive_branch_data.Cf.tocsc(),
            Ct=self.passive_branch_data.Ct.tocsc(),
        )

    def get_linear_admittance_matrices(self, indices: SimulationIndices) -> ycalc.LinearAdmittanceMatrices:
        """

        :return:
        """
        return ycalc.compute_linear_admittances(
            nbr=self.nbr,
            X=self.passive_branch_data.X,
            R=self.passive_branch_data.R,
            m=self.active_branch_data.tap_module,
            active=self.passive_branch_data.active.astype(int),
            Cf=self.passive_branch_data.Cf.tocsc(),
            Ct=self.passive_branch_data.Ct.tocsc(),
            ac=indices.ac,
            dc=indices.dc
        )

    def get_reactive_power_limits(self) -> Tuple[Vec, Vec]:
        """
        compute the reactive power limits in place
        :return: Qmax_bus, Qmin_bus in per unit
        """
        # generators
        Qmax_bus = self.generator_data.get_qmax_per_bus()
        Qmin_bus = self.generator_data.get_qmin_per_bus()

        if self.nbatt > 0:
            # batteries
            Qmax_bus += self.battery_data.get_qmax_per_bus()
            Qmin_bus += self.battery_data.get_qmin_per_bus()

        if self.nhvdc > 0:
            # hvdc from
            Qmax_bus += self.hvdc_data.get_qmax_from_per_bus()
            Qmin_bus += self.hvdc_data.get_qmin_from_per_bus()

            # hvdc to
            Qmax_bus += self.hvdc_data.get_qmax_to_per_bus()
            Qmin_bus += self.hvdc_data.get_qmin_to_per_bus()

        if self.nshunt > 0:
            Qmax_bus += self.shunt_data.get_qmax_per_bus()
            Qmin_bus += self.shunt_data.get_qmin_per_bus()

        # fix zero values
        Qmax_bus[Qmax_bus == 0] = 1e20
        Qmin_bus[Qmin_bus == 0] = -1e20

        return Qmax_bus / self.Sbase, Qmin_bus / self.Sbase

    def get_structure(self, structure_type: str) -> pd.DataFrame:
        """
        Get a DataFrame with the input.
        :param: structure_type: String representing structure type
        :return: pandas DataFrame
        """
        Sbus = self.get_power_injections_pu()
        idx = self.get_simulation_indices(Sbus=Sbus)

        Qmax_bus, Qmin_bus = self.get_reactive_power_limits()

        from GridCalEngine.Simulations.PowerFlow.Formulations.pf_advanced_formulation import (
            PfAdvancedFormulation)
        from GridCalEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions

        formulation = PfAdvancedFormulation(V0=self.bus_data.Vbus,
                                            S0=Sbus,
                                            I0=self.get_current_injections_pu(),
                                            Y0=self.get_admittance_injections_pu(),
                                            Qmin=Qmin_bus,
                                            Qmax=Qmax_bus,
                                            nc=self,
                                            options=PowerFlowOptions(),
                                            logger=Logger())

        if structure_type == 'V':
            df = pd.DataFrame(
                data=self.bus_data.Vbus,
                columns=['Voltage (p.u.)'],
                index=self.bus_data.names,
            )

        elif structure_type == 'Va':
            df = pd.DataFrame(
                data=np.angle(self.bus_data.Vbus),
                columns=['Voltage angles (rad)'],
                index=self.bus_data.names,
            )
        elif structure_type == 'Vm':
            df = pd.DataFrame(
                data=np.abs(self.bus_data.Vbus),
                columns=['Voltage modules (p.u.)'],
                index=self.bus_data.names,
            )
        elif structure_type == 'S':
            df = pd.DataFrame(
                data=Sbus,
                columns=['Power (p.u.)'],
                index=self.bus_data.names,
            )

        elif structure_type == 'P':
            df = pd.DataFrame(
                data=Sbus.real,
                columns=['Power (p.u.)'],
                index=self.bus_data.names,
            )

        elif structure_type == 'Q':
            df = pd.DataFrame(
                data=Sbus.imag,
                columns=['Power (p.u.)'],
                index=self.bus_data.names,
            )

        elif structure_type == 'I':
            df = pd.DataFrame(
                data=self.get_current_injections_pu(),
                columns=['Current (p.u.)'],
                index=self.bus_data.names,
            )

        elif structure_type == 'Y':
            df = pd.DataFrame(
                data=self.get_admittance_injections_pu(),
                columns=['Admittance (p.u.)'],
                index=self.bus_data.names,
            )

        elif structure_type == 'Ybus':
            adm = self.get_admittance_matrices()
            df = pd.DataFrame(
                data=adm.Ybus.toarray(),
                columns=self.bus_data.names,
                index=self.bus_data.names,
            )

        elif structure_type == 'G':
            adm = self.get_admittance_matrices()
            df = pd.DataFrame(
                data=adm.Ybus.real.toarray(),
                columns=self.bus_data.names,
                index=self.bus_data.names,
            )

        elif structure_type == 'B':
            adm = self.get_admittance_matrices()
            df = pd.DataFrame(
                data=adm.Ybus.imag.toarray(),
                columns=self.bus_data.names,
                index=self.bus_data.names,
            )

        elif structure_type == 'Yf':
            adm = self.get_admittance_matrices()
            df = pd.DataFrame(
                data=adm.Yf.toarray(),
                columns=self.bus_data.names,
                index=self.passive_branch_data.names,
            )

        elif structure_type == 'Yt':
            adm = self.get_admittance_matrices()
            df = pd.DataFrame(
                data=adm.Yt.toarray(),
                columns=self.bus_data.names,
                index=self.passive_branch_data.names,
            )

        elif structure_type == 'Bbus':
            adm = self.get_linear_admittance_matrices(idx)
            df = pd.DataFrame(
                data=adm.Bbus.toarray(),
                columns=self.bus_data.names,
                index=self.bus_data.names,
            )

        elif structure_type == 'Bf':
            adm = self.get_linear_admittance_matrices(idx)
            df = pd.DataFrame(
                data=adm.Bf.toarray(),
                columns=self.bus_data.names,
                index=self.passive_branch_data.names,
            )

        elif structure_type == 'Cf':
            df = pd.DataFrame(
                data=self.passive_branch_data.Cf.toarray(),
                columns=self.bus_data.names,
                index=self.passive_branch_data.names,
            )

        elif structure_type == 'Ct':
            df = pd.DataFrame(
                data=self.passive_branch_data.Ct.toarray(),
                columns=self.bus_data.names,
                index=self.passive_branch_data.names,
            )

        elif structure_type == 'Yshunt':
            df = pd.DataFrame(
                data=self.get_Yshunt_bus_pu(),
                columns=['Shunt admittance (p.u.)'],
                index=self.bus_data.names,
            )

        elif structure_type == 'Yseries':
            adm = self.get_admittance_matrices()
            df = pd.DataFrame(
                data=adm.Yseries.toarray(),
                columns=self.bus_data.names,
                index=self.bus_data.names,
            )

        elif structure_type == "B'":
            adm = self.get_fast_decoupled_amittances()
            if adm.B1.shape[0] == len(idx.pqpv):
                data = adm.B1.toarray()
                names = self.bus_data.names[idx.pqpv]
            else:
                data = adm.B1[np.ix_(idx.pqpv, idx.pqpv)].toarray()
                names = self.bus_data.names[idx.pqpv]

            df = pd.DataFrame(
                data=data,
                columns=names,
                index=names,
            )

        elif structure_type == "B''":
            adm = self.get_fast_decoupled_amittances()
            if adm.B2.shape[0] == len(idx.pq):
                data = adm.B2.toarray()
                names = self.bus_data.names[idx.pq]
            else:
                data = adm.B2[np.ix_(idx.pq, idx.pq)].toarray()
                names = self.bus_data.names[idx.pq]

            df = pd.DataFrame(
                data=data,
                columns=names,
                index=names,
            )

        elif structure_type == 'Types':
            data = self.bus_data.bus_types
            df = pd.DataFrame(
                data=data,
                columns=['Bus types'],
                index=self.bus_data.names,
            )

        elif structure_type == 'x':
            df = pd.DataFrame(
                data=formulation.var2x(),
                columns=['x'],
                index=formulation.get_x_names(),
            )

        elif structure_type == 'f(x)':
            df = pd.DataFrame(
                data=formulation.fx(),
                columns=['f(x)'],
                index=formulation.get_fx_names(),
            )

        elif structure_type == 'Jacobian':
            df = formulation.get_jacobian_df(autodiff=False)

        elif structure_type == 'Qmin':
            df = pd.DataFrame(
                data=Qmin_bus,
                columns=['Qmin'],
                index=self.bus_data.names,
            )

        elif structure_type == 'Qmax':
            df = pd.DataFrame(
                data=Qmax_bus,
                columns=['Qmax'],
                index=self.bus_data.names,
            )

        elif structure_type == 'bus_ctrl':
            data1 = [BusMode.as_str(val) for val in self.bus_data.bus_types]

            df = pd.DataFrame(
                data=data1,
                columns=['bus_ctrl'],
                index=self.bus_data.names,
            )

        elif structure_type == 'branch_ctrl':

            data1 = [val.value if val != 0 else "-" for val in self.active_branch_data.tap_module_control_mode]
            data2 = [val.value if val != 0 else "-" for val in self.active_branch_data.tap_phase_control_mode]

            df = pd.DataFrame(
                data=np.c_[
                    self.passive_branch_data.F,
                    self.passive_branch_data.T,
                    self.active_branch_data.tap_controlled_buses,
                    data1,
                    data2
                ],
                columns=['bus F', 'bus T', 'V ctrl bus', 'm control', 'tau control'],
                index=[f"{k}) {name}" for k, name in enumerate(self.passive_branch_data.names)],
            )

        elif structure_type == 'pq':
            df = pd.DataFrame(
                data=idx.pq.astype(int).astype(str),
                columns=['pq'],
                index=self.bus_data.names[idx.pq],
            )

        elif structure_type == 'pv':
            df = pd.DataFrame(
                data=idx.pv.astype(int).astype(str),
                columns=['pv'],
                index=self.bus_data.names[idx.pv],
            )

        elif structure_type == 'pqv':
            df = pd.DataFrame(
                data=idx.pqv.astype(int).astype(str),
                columns=['pqv'],
                index=self.bus_data.names[idx.pqv],
            )

        elif structure_type == 'p':
            df = pd.DataFrame(
                data=idx.p.astype(int).astype(str),
                columns=['p'],
                index=self.bus_data.names[idx.p],
            )

        elif structure_type == 'vd':
            df = pd.DataFrame(
                data=idx.vd.astype(int).astype(str),
                columns=['vd'],
                index=self.bus_data.names[idx.vd],
            )

        elif structure_type == 'pqpv':
            df = pd.DataFrame(
                data=idx.pqpv.astype(int).astype(str),
                columns=['pqpv'],
                index=self.bus_data.names[idx.pqpv],
            )

        elif structure_type == 'tap_f':
            df = pd.DataFrame(
                data=self.passive_branch_data.virtual_tap_f,
                columns=['Virtual tap from (p.u.)'],
                index=self.passive_branch_data.names,
            )

        elif structure_type == 'tap_t':
            df = pd.DataFrame(
                data=self.passive_branch_data.virtual_tap_t,
                columns=['Virtual tap to (p.u.)'],
                index=self.passive_branch_data.names,
            )

        elif structure_type == 'k_pf_tau':
            df = pd.DataFrame(
                data=idx.k_pf_tau.astype(int).astype(str),
                columns=['k_pf_tau'],
                index=self.passive_branch_data.names[idx.k_pf_tau],
            )

        elif structure_type == 'k_pt_tau':
            df = pd.DataFrame(
                data=idx.k_pt_tau.astype(int).astype(str),
                columns=['k_pt_tau'],
                index=self.passive_branch_data.names[idx.k_pt_tau],
            )

        elif structure_type == 'k_qf_m':
            df = pd.DataFrame(
                data=idx.k_qf_m.astype(int).astype(str),
                columns=['k_qf_m'],
                index=self.passive_branch_data.names[idx.k_qf_m],
            )

        elif structure_type == 'k_qt_m':
            df = pd.DataFrame(
                data=idx.k_qt_m.astype(int).astype(str),
                columns=['k_qt_m'],
                index=self.passive_branch_data.names[idx.k_qt_m],
            )

        elif structure_type == 'k_qf_beq':
            df = pd.DataFrame(
                data=idx.k_qf_beq.astype(int).astype(str),
                columns=['k_qf_beq'],
                index=self.passive_branch_data.names[idx.k_qf_beq],
            )

        elif structure_type == 'k_v_m':
            df = pd.DataFrame(
                data=idx.k_v_m.astype(int).astype(str),
                columns=['k_v_m'],
                index=self.passive_branch_data.names[idx.k_v_m],
            )
        elif structure_type == 'k_v_beq':
            df = pd.DataFrame(
                data=idx.k_v_beq.astype(int).astype(str),
                columns=['k_v_beq'],
                index=self.passive_branch_data.names[idx.k_v_beq],
            )
        elif structure_type == 'idx_dPf':
            df = pd.DataFrame(
                data=formulation.idx_dPf.astype(int).astype(str),
                columns=['idx_dPf'],
                index=self.passive_branch_data.names[formulation.idx_dPf],
            )

        elif structure_type == 'idx_dQf':
            df = pd.DataFrame(
                data=formulation.idx_dQf.astype(int).astype(str),
                columns=['idx_dQf'],
                index=self.passive_branch_data.names[formulation.idx_dQf],
            )

        elif structure_type == 'idx_dPt':
            df = pd.DataFrame(
                data=formulation.idx_dPt.astype(int).astype(str),
                columns=['idx_dPt'],
                index=self.passive_branch_data.names[formulation.idx_dPt],
            )

        elif structure_type == 'idx_dQt':
            df = pd.DataFrame(
                data=formulation.idx_dQt.astype(int).astype(str),
                columns=['idx_dQt'],
                index=self.passive_branch_data.names[formulation.idx_dQt],
            )

        elif structure_type == 'idx_dVa':
            df = pd.DataFrame(
                data=formulation.idx_dVa.astype(int).astype(str),
                columns=['idx_dVa'],
                index=self.bus_data.names[formulation.idx_dVa],
            )

        elif structure_type == 'idx_dVm':
            df = pd.DataFrame(
                data=formulation.idx_dVm.astype(int).astype(str),
                columns=['idx_dVm'],
                index=self.bus_data.names[formulation.idx_dVm],
            )

        elif structure_type == 'idx_dm':
            df = pd.DataFrame(
                data=formulation.idx_dm.astype(int).astype(str),
                columns=['idx_dm'],
                index=self.passive_branch_data.names[formulation.idx_dm],
            )

        elif structure_type == 'idx_dtau':
            df = pd.DataFrame(
                data=formulation.idx_dtau.astype(int).astype(str),
                columns=['idx_dtau'],
                index=self.passive_branch_data.names[formulation.idx_dtau],
            )

        elif structure_type == 'Pf_set':
            df = pd.DataFrame(
                data=self.active_branch_data.Pset[formulation.idx_dPf],
                columns=['Pf_set'],
                index=self.passive_branch_data.names[formulation.idx_dPf],
            )

        elif structure_type == 'Pt_set':
            df = pd.DataFrame(
                data=self.active_branch_data.Pset[formulation.idx_dPt],
                columns=['Pt_set'],
                index=self.passive_branch_data.names[formulation.idx_dPt],
            )

        elif structure_type == 'Qf_set':
            df = pd.DataFrame(
                data=self.active_branch_data.Qset[formulation.idx_dQf],
                columns=['Qf_set'],
                index=self.passive_branch_data.names[formulation.idx_dQf],
            )

        elif structure_type == 'Qt_set':
            df = pd.DataFrame(
                data=self.active_branch_data.Qset[formulation.idx_dQt],
                columns=['Qt_set'],
                index=self.passive_branch_data.names[formulation.idx_dQt],
            )

        else:
            raise Exception('PF input: structure type not found' + str(structure_type))

        return df

    def compute_adjacency_matrix(self, consider_hvdc_as_island_links: bool = False) -> sp.csc_matrix:
        """
        Compute the adjacency matrix
        :param consider_hvdc_as_island_links: Does the HVDCLine works for the topology as a normal line?
        :return: csc_matrix
        """

        if consider_hvdc_as_island_links:
            i, j, data, n_elm = build_branches_C_coo_3(
                bus_active=self.bus_data.active,
                F1=self.passive_branch_data.F, T1=self.passive_branch_data.T, active1=self.passive_branch_data.active,
                F2=self.vsc_data.F, T2=self.vsc_data.T, active2=self.vsc_data.active,
                F3=self.hvdc_data.F, T3=self.hvdc_data.T, active3=self.hvdc_data.active,
            )
        else:
            i, j, data, n_elm = build_branches_C_coo_2(
                bus_active=self.bus_data.active,
                F1=self.passive_branch_data.F, T1=self.passive_branch_data.T, active1=self.passive_branch_data.active,
                F2=self.vsc_data.F, T2=self.vsc_data.T, active2=self.vsc_data.active,
            )

        C = sp.coo_matrix((data, (i, j)), shape=(n_elm, self.bus_data.nbus), dtype=int)

        return (C.T @ C).tocsc()

    def process_reducible_branches(self) -> int:
        """
        Process the reducible branches (i.e. reduce branches like the switches) in-place
        :return: Number of reduced branches
        """
        i, j, data, n_red = build_reducible_branches_C_coo(
            F=self.passive_branch_data.F,
            T=self.passive_branch_data.T,
            reducible=self.passive_branch_data.reducible,
            active=self.passive_branch_data.active.astype(int),
        )
        C = sp.coo_matrix((data, (i, j)),
                          shape=(self.passive_branch_data.nelm, self.bus_data.nbus),
                          dtype=int)

        if n_red > 0:

            # compute the adjacency matrix
            A = C.T @ C

            # get the islands formed by the reducible branches
            islands = find_islands(adj=A.tocsc(), active=self.bus_data.active)

            # compose the bus mapping array where each entry point to the final island bus
            self.__bus_map_arr = np.arange(self.bus_data.nbus, dtype=int)

            for island in islands:
                if len(island):
                    i0 = island[0]
                    for ii in range(1, len(island)):
                        i = island[ii]
                        self.__bus_map_arr[i] = i0

                        # deactivate the reduced buses
                        self.bus_data.active[i] = False

            # remap
            self.passive_branch_data.remap(self.__bus_map_arr)
            self.vsc_data.remap(self.__bus_map_arr)
            self.hvdc_data.remap(self.__bus_map_arr)
            self.load_data.remap(self.__bus_map_arr)
            self.generator_data.remap(self.__bus_map_arr)
            self.battery_data.remap(self.__bus_map_arr)
            self.shunt_data.remap(self.__bus_map_arr)
            self.__topology_performed = True
        else:
            pass

        return n_red

    def get_island(self,
                   bus_idx: IntVec,
                   consider_hvdc_as_island_links: bool = False,
                   consider_vsc_as_island_links: bool = True,
                   logger: Logger | None = None) -> "NumericalCircuit":
        """
        Get the island corresponding to the given buses
        :param bus_idx: array of bus indices
        :param consider_hvdc_as_island_links: Does the HVDCLine works for the topology as a normal line?
        :param consider_vsc_as_island_links: Consider the VSC devices as a regular branch?
        :param logger: Logger
        :return: NumericalCircuit
        """
        if logger is None:
            logger = Logger()

        # this is an array to map the old indices to the new indices
        # it is used by the structures to re-map the bus indices
        bus_map = np.full(self.bus_data.nbus, -1, dtype=int)
        bus_map[bus_idx] = np.arange(len(bus_idx))

        br_idx = tp.get_island_branch_indices(bus_map=bus_map,
                                              elm_active=self.passive_branch_data.active,
                                              F=self.passive_branch_data.F,
                                              T=self.passive_branch_data.T)

        hvdc_idx = tp.get_island_branch_indices(bus_map=bus_map,
                                                elm_active=self.hvdc_data.active,
                                                F=self.hvdc_data.F,
                                                T=self.hvdc_data.T)

        vsc_idx = tp.get_island_branch_indices(bus_map=bus_map,
                                               elm_active=self.vsc_data.active,
                                               F=self.vsc_data.F,
                                               T=self.vsc_data.T)

        load_idx = tp.get_island_monopole_indices(bus_map=bus_map,
                                                  elm_active=self.load_data.active,
                                                  elm_bus=self.load_data.bus_idx)

        gen_idx = tp.get_island_monopole_indices(bus_map=bus_map,
                                                 elm_active=self.generator_data.active,
                                                 elm_bus=self.generator_data.bus_idx)

        batt_idx = tp.get_island_monopole_indices(bus_map=bus_map,
                                                  elm_active=self.battery_data.active,
                                                  elm_bus=self.battery_data.bus_idx)

        shunt_idx = tp.get_island_monopole_indices(bus_map=bus_map,
                                                   elm_active=self.shunt_data.active,
                                                   elm_bus=self.shunt_data.bus_idx)

        nc = NumericalCircuit(
            nbus=len(bus_idx),
            nbr=len(br_idx),
            nhvdc=len(hvdc_idx),
            nvsc=len(vsc_idx),
            nload=len(load_idx),
            ngen=len(gen_idx),
            nbatt=len(batt_idx),
            nshunt=len(shunt_idx),
            nfluidnode=0,
            nfluidturbine=0,
            nfluidpump=0,
            nfluidp2x=0,
            nfluidpath=0,
            sbase=self.Sbase,
            t_idx=self.t_idx,
        )

        # slice data
        nc.bus_data = self.bus_data.slice(elm_idx=bus_idx)

        nc.passive_branch_data = self.passive_branch_data.slice(elm_idx=br_idx, bus_idx=bus_idx,
                                                                bus_map=bus_map, logger=logger)

        nc.active_branch_data = self.active_branch_data.slice(elm_idx=br_idx, bus_idx=bus_idx,
                                                              bus_map=bus_map, logger=logger)

        nc.load_data = self.load_data.slice(elm_idx=load_idx, bus_idx=bus_idx, bus_map=bus_map)
        nc.battery_data = self.battery_data.slice(elm_idx=batt_idx, bus_idx=bus_idx, bus_map=bus_map)
        nc.generator_data = self.generator_data.slice(elm_idx=gen_idx, bus_idx=bus_idx, bus_map=bus_map)
        nc.shunt_data = self.shunt_data.slice(elm_idx=shunt_idx, bus_idx=bus_idx, bus_map=bus_map)

        if consider_hvdc_as_island_links:
            nc.hvdc_data = self.hvdc_data.slice(elm_idx=hvdc_idx, bus_idx=bus_idx, bus_map=bus_map, logger=logger)

        if consider_vsc_as_island_links:
            nc.vsc_data = self.vsc_data.slice(elm_idx=vsc_idx, bus_idx=bus_idx, bus_map=bus_map, logger=logger)

        return nc

    def split_into_islands(self,
                           ignore_single_node_islands: bool = False,
                           consider_hvdc_as_island_links: bool = False,
                           logger: Logger | None = None) -> List["NumericalCircuit"]:
        """
        Split circuit into islands
        :param ignore_single_node_islands: ignore islands composed of only one bus
        :param consider_hvdc_as_island_links: Does the HVDCLine works for the topology as a normal line?
        :param logger: Logger
        :return: List[NumericCircuit]
        """
        if logger is None:
            logger = Logger()

        # detect the topology reductions
        self.process_reducible_branches()

        # find the matching islands
        adj = self.compute_adjacency_matrix(consider_hvdc_as_island_links=consider_hvdc_as_island_links)

        idx_islands = tp.find_islands(adj=adj, active=self.bus_data.active)

        circuit_islands = list()  # type: List[NumericalCircuit]

        for island_bus_indices in idx_islands:
            if ignore_single_node_islands:
                if len(island_bus_indices) > 1:
                    island = self.get_island(island_bus_indices,
                                             consider_hvdc_as_island_links=consider_hvdc_as_island_links,
                                             logger=logger)
                    circuit_islands.append(island)
            else:
                island = self.get_island(island_bus_indices,
                                         consider_hvdc_as_island_links=consider_hvdc_as_island_links,
                                         logger=logger)
                circuit_islands.append(island)

        return circuit_islands

    def compare(self, nc_2: "NumericalCircuit", tol=1e-6) -> Tuple[bool, Logger]:
        """
        Compare this numerical circuit with another numerical circuit
        :param nc_2: NumericalCircuit
        :param tol: NumericalCircuit
        :return: Logger with the errors and warning events
        """

        logger = Logger()

        # --------------------------------------------------------------------------------------------------------------
        #  Compare data
        # --------------------------------------------------------------------------------------------------------------

        check_arr(self.passive_branch_data.F, nc_2.passive_branch_data.F, tol, 'BranchData', 'F', logger)
        check_arr(self.passive_branch_data.T, nc_2.passive_branch_data.T, tol, 'BranchData', 'T', logger)
        check_arr(self.passive_branch_data.active, nc_2.passive_branch_data.active, tol,
                  'BranchData', 'active', logger)
        check_arr(self.passive_branch_data.R, nc_2.passive_branch_data.R, tol, 'BranchData', 'r', logger)
        check_arr(self.passive_branch_data.X, nc_2.passive_branch_data.X, tol, 'BranchData', 'x', logger)
        check_arr(self.passive_branch_data.G, nc_2.passive_branch_data.G, tol, 'BranchData', 'g', logger)
        check_arr(self.passive_branch_data.B, nc_2.passive_branch_data.B, tol, 'BranchData', 'b', logger)
        check_arr(self.passive_branch_data.rates, nc_2.passive_branch_data.rates, tol, 'BranchData',
                  'rates', logger)
        check_arr(self.active_branch_data.tap_module, nc_2.active_branch_data.tap_module, tol,
                  'BranchData', 'tap_module', logger)
        check_arr(self.active_branch_data.tap_angle, nc_2.active_branch_data.tap_angle, tol,
                  'BranchData', 'tap_angle', logger)

        check_arr(self.passive_branch_data.G0, nc_2.passive_branch_data.G0, tol, 'BranchData', 'g0', logger)

        check_arr(self.passive_branch_data.virtual_tap_f, nc_2.passive_branch_data.virtual_tap_f,
                  tol, 'BranchData', 'vtap_f', logger)
        check_arr(self.passive_branch_data.virtual_tap_t, nc_2.passive_branch_data.virtual_tap_t,
                  tol, 'BranchData', 'vtap_t', logger)

        # bus data
        check_arr(self.bus_data.active, nc_2.bus_data.active, tol, 'BusData', 'active', logger)
        check_arr(self.bus_data.Vbus.real, nc_2.bus_data.Vbus.real, tol, 'BusData', 'V0', logger)
        check_arr(self.bus_data.installed_power, nc_2.bus_data.installed_power, tol, 'BusData', 'installed power',
                  logger)
        check_arr(self.bus_data.bus_types, nc_2.bus_data.bus_types, tol, 'BusData', 'types', logger)

        # generator data
        check_arr(self.generator_data.active, nc_2.generator_data.active, tol, 'GenData', 'active', logger)
        check_arr(self.generator_data.p, nc_2.generator_data.p, tol, 'GenData', 'P', logger)
        check_arr(self.generator_data.v, nc_2.generator_data.v, tol, 'GenData', 'Vset', logger)
        check_arr(self.generator_data.qmin, nc_2.generator_data.qmin, tol, 'GenData', 'Qmin', logger)
        check_arr(self.generator_data.qmax, nc_2.generator_data.qmax, tol, 'GenData', 'Qmax', logger)

        # load data
        check_arr(self.load_data.active, nc_2.load_data.active, tol, 'LoadData',
                  'active', logger)
        check_arr(self.load_data.S, nc_2.load_data.S, tol, 'LoadData', 'S', logger)
        check_arr(self.load_data.I, nc_2.load_data.I, tol, 'LoadData', 'I', logger)
        check_arr(self.load_data.Y, nc_2.load_data.Y, tol, 'LoadData', 'Y', logger)

        # shunt
        check_arr(self.shunt_data.active, nc_2.shunt_data.active, tol, 'ShuntData', 'active', logger)
        check_arr(self.shunt_data.Y, nc_2.shunt_data.Y, tol, 'ShuntData', 'S', logger)
        check_arr(self.shunt_data.get_injections_per_bus(),
                  nc_2.shunt_data.get_injections_per_bus(), tol, 'ShuntData', 'Injections per bus', logger)

        # --------------------------------------------------------------------------------------------------------------
        #  Compare arrays and data
        # --------------------------------------------------------------------------------------------------------------
        sim_idx = self.get_simulation_indices()
        sim_idx2 = nc_2.get_simulation_indices()

        Sbus = self.get_power_injections_pu()
        Sbus2 = nc_2.get_power_injections_pu()

        check_arr(Sbus.real, Sbus2.real, tol, 'Pbus', 'P', logger)
        check_arr(Sbus.imag, Sbus2.imag, tol, 'Qbus', 'Q', logger)

        check_arr(sim_idx.pq, sim_idx2.pq, tol, 'Types', 'pq', logger)
        check_arr(sim_idx.pv, sim_idx2.pv, tol, 'Types', 'pv', logger)
        check_arr(sim_idx.vd, sim_idx2.vd, tol, 'Types', 'vd', logger)

        conn = self.get_connectivity_matrices()
        conn2 = nc_2.get_connectivity_matrices()

        check_arr(conn.Cf.toarray(), conn2.Cf.toarray(), tol, 'Connectivity', 'Cf (dense)', logger)
        check_arr(conn.Ct.toarray(), conn2.Ct.toarray(), tol, 'Connectivity', 'Ct (dense)', logger)
        check_arr(conn.Cf.tocsc().data, conn2.Cf.tocsc().data, tol, 'Connectivity', 'Cf', logger)
        check_arr(conn.Ct.tocsc().data, conn2.Ct.tocsc().data, tol, 'Connectivity', 'Ct', logger)

        adm = self.get_admittance_matrices()
        adm2 = nc_2.get_admittance_matrices()

        check_arr(adm.Ybus.toarray(), adm2.Ybus.toarray(), tol, 'Adm.', 'Ybus (dense)', logger)
        check_arr(adm.Ybus.tocsc().data.real, adm2.Ybus.tocsc().data.real, tol, 'Adm.', 'Ybus (real)', logger)
        check_arr(adm.Ybus.tocsc().data.imag, adm2.Ybus.tocsc().data.imag, tol, 'Adm.', 'Ybus (imag)', logger)
        check_arr(adm.Yf.tocsc().data.real, adm2.Yf.tocsc().data.real, tol, 'Adm.', 'Yf (real)', logger)
        check_arr(adm.Yf.tocsc().data.imag, adm2.Yf.tocsc().data.imag, tol, 'Adm.', 'Yf (imag)', logger)
        check_arr(adm.Yt.tocsc().data.real, adm2.Yt.tocsc().data.real, tol, 'Adm.', 'Yt (real)', logger)
        check_arr(adm.Yt.tocsc().data.imag, adm2.Yt.tocsc().data.imag, tol, 'Adm.', 'Yt (imag)', logger)

        # if any error in the logger, bad
        return logger.error_count() == 0, logger

    def get_structural_ntc(self, bus_a1_idx: IntVec, bus_a2_idx: IntVec) -> float:
        """
        Get the structural NTC
        :param bus_a1_idx: list of buses of the area from
        :param bus_a2_idx: list of buses of the area to
        :return: structural NTC in MVA
        """

        inter_area_branches = self.passive_branch_data.get_inter_areas(bus_idx_from=bus_a1_idx, bus_idx_to=bus_a2_idx)
        sum_ratings = 0.0
        for k, sense in inter_area_branches:
            sum_ratings += self.passive_branch_data.rates[k]

        inter_area_hvdcs = self.hvdc_data.get_inter_areas(bus_idx_from=bus_a1_idx, bus_idx_to=bus_a2_idx)
        for k, sense in inter_area_hvdcs:
            sum_ratings += self.hvdc_data.rates[k]

        return sum_ratings

    def is_dc(self) -> Tuple[int, str]:
        """
        Check if this island is DC
        :return: int, str -> 1: all DC, 0: all AC, 2: AC and DC
        """
        n = len(self.bus_data.is_dc)
        ndc = np.sum(self.bus_data.is_dc)
        if n == ndc:
            return 1, "DC"
        elif ndc == 0:
            return 0, "AC"
        else:
            return 2, "AC/DC"
