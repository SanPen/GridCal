# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from typing import List, Tuple, Dict, Union
from enum import Enum
import numba as nb
import numpy as np
import scipy.sparse as sp

from VeraGridEngine.Devices import RemedialAction
from VeraGridEngine.Topology.simulation_indices import SimulationIndices
from VeraGridEngine.Topology.topology import find_islands
from VeraGridEngine.basic_structures import Vec, IntVec, CxVec, BoolVec, Mat, CxMat, StrVec, Logger
from VeraGridEngine.enumerations import BusMode, ContingencyOperationTypes, GeneratorControlMode, ShuntControlMode
import VeraGridEngine.Topology.topology as tp
import VeraGridEngine.Topology.simulation_indices as si
import VeraGridEngine.Topology.admittance_matrices as ycalc
from VeraGridEngine.DataStructures.battery_data import BatteryData
from VeraGridEngine.DataStructures.passive_branch_data import PassiveBranchData
from VeraGridEngine.DataStructures.active_branch_data import ActiveBranchData
from VeraGridEngine.DataStructures.bus_data import BusData
from VeraGridEngine.DataStructures.generator_data import GeneratorData
from VeraGridEngine.DataStructures.hvdc_data import HvdcData
from VeraGridEngine.DataStructures.vsc_data import VscData
from VeraGridEngine.DataStructures.load_data import LoadData
from VeraGridEngine.DataStructures.shunt_data import ShuntData
from VeraGridEngine.DataStructures.fluid_node_data import FluidNodeData
from VeraGridEngine.DataStructures.fluid_turbine_data import FluidTurbineData
from VeraGridEngine.DataStructures.fluid_pump_data import FluidPumpData
from VeraGridEngine.DataStructures.fluid_p2x_data import FluidP2XData
from VeraGridEngine.DataStructures.fluid_path_data import FluidPathData
from VeraGridEngine.Devices.Aggregation.investment import Investment
from VeraGridEngine.Devices.Events.contingency import Contingency
from VeraGridEngine.Utils.compare import compare_arr

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


@nb.jit(cache=True)
def build_q_limits(nbus: int, Sbase: float,
                   gen_idx, q_min_gen, q_max_gen, active_gen, control_mode_int_gen,
                   batt_idx, q_min_batt, q_max_batt, active_batt, control_mode_int_batt,
                   sh_idx, q_min_sh, q_max_sh, active_sh, control_mode_int_sh,
                   hvdc_f, hvdc_t, q_min_hvdc_f, q_max_hvdc_f, q_min_hvdc_t, q_max_hvdc_t, active_hvdc,
                   v_ctrl_val_gen: int, v_ctrl_val_sh: int):
    """

    :param nbus:
    :param Sbase:
    :param gen_idx:
    :param q_min_gen:
    :param q_max_gen:
    :param active_gen:
    :param control_mode_int_gen:
    :param batt_idx:
    :param q_min_batt:
    :param q_max_batt:
    :param active_batt:
    :param control_mode_int_batt:
    :param sh_idx:
    :param q_min_sh:
    :param q_max_sh:
    :param active_sh:
    :param control_mode_int_sh:
    :param hvdc_f:
    :param hvdc_t:
    :param q_min_hvdc_f:
    :param q_max_hvdc_f:
    :param q_min_hvdc_t:
    :param q_max_hvdc_t:
    :param active_hvdc:
    :param v_ctrl_val_gen:
    :param v_ctrl_val_sh
    :return:
    """
    max_mask = np.zeros(nbus, dtype=nb.int32)
    Qmax_bus = np.full(nbus, 1e-20)

    min_mask = np.zeros(nbus, dtype=nb.int32)
    Qmin_bus = np.full(nbus, 1e20)

    for i, qmin, qmax, active, ctrl_mode in zip(gen_idx, q_min_gen, q_max_gen, active_gen, control_mode_int_gen):

        if active and ctrl_mode == v_ctrl_val_gen:
            if max_mask[i] == 0:
                Qmax_bus[i] = qmax / Sbase
            else:
                Qmax_bus[i] += qmax / Sbase

            if min_mask[i] == 0:
                Qmin_bus[i] = qmin / Sbase
            else:
                Qmin_bus[i] += qmin / Sbase

            max_mask[i] += 1
            min_mask[i] += 1

    for i, qmin, qmax, active, ctrl_mode in zip(batt_idx, q_min_batt, q_max_batt, active_batt,
                                                   control_mode_int_batt):

        if active and ctrl_mode == v_ctrl_val_gen:
            if max_mask[i] == 0:
                Qmax_bus[i] = qmax / Sbase
            else:
                Qmax_bus[i] += qmax / Sbase

            if min_mask[i] == 0:
                Qmin_bus[i] = qmin / Sbase
            else:
                Qmin_bus[i] += qmin / Sbase

            max_mask[i] += 1
            min_mask[i] += 1

    for i, qmin, qmax, active, ctrl_mode in zip(sh_idx, q_min_sh, q_max_sh, active_sh, control_mode_int_sh):

        if active and ctrl_mode == v_ctrl_val_sh:
            if max_mask[i] == 0:
                Qmax_bus[i] = qmax / Sbase
            else:
                Qmax_bus[i] += qmax / Sbase

            if min_mask[i] == 0:
                Qmin_bus[i] = qmin / Sbase
            else:
                Qmin_bus[i] += qmin / Sbase

            max_mask[i] += 1
            min_mask[i] += 1

    for f, t, qmin_f, qmax_f, qmin_t, qmax_t, active in zip(hvdc_f, hvdc_t, q_min_hvdc_f, q_max_hvdc_f,
                                                            q_min_hvdc_t, q_max_hvdc_t, active_hvdc):

        if active:
            if max_mask[f] == 0:
                Qmax_bus[f] = qmax_f / Sbase
            else:
                Qmax_bus[f] += qmax_f / Sbase

            if min_mask[f] == 0:
                Qmin_bus[f] = qmin_f / Sbase
            else:
                Qmin_bus[f] += qmin_f / Sbase

            max_mask[f] += 1
            min_mask[f] += 1

            if max_mask[t] == 0:
                Qmax_bus[t] = qmax_t / Sbase
            else:
                Qmax_bus[t] += qmax_t / Sbase

            if min_mask[t] == 0:
                Qmin_bus[t] = qmin_t / Sbase
            else:
                Qmin_bus[t] += qmin_t / Sbase

            max_mask[t] += 1
            min_mask[t] += 1

    return Qmax_bus, Qmin_bus


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


@nb.jit(cache=True)
def correct_bus_types(gen_idx: IntVec,
                      control_mode_int: IntVec,
                      gen_controllable_bus_idx: IntVec,
                      bus_types: IntVec,
                      v_ctrl_val: int) -> None:
    """
    Correct remote voltage-controlled bus types after topology processing.

    :param gen_idx:
    :param control_mode_int:
    :param gen_controllable_bus_idx:
    :param bus_types:
    :param v_ctrl_val: value for GeneratorControlMode.V
    :return: None.
    """
    for i in range(len(gen_idx)):
        # A negative index means that the device controls its local bus, whose
        # type was already assigned during compilation and must not be remapped.
        controlled_bus_idx: int = gen_controllable_bus_idx[i]
        if control_mode_int[i] == v_ctrl_val:
            if controlled_bus_idx >= 0:
                if bus_types[controlled_bus_idx] != 2:
                    bus_types[controlled_bus_idx] = 2
                else:
                    pass
            else:
                pass
        else:
            pass


def select_ac_phase_reference_buses(
        bus_types: IntVec,
        active_power: Vec,
        bus_active: BoolVec,
        is_dc_bus: BoolVec,
        branch_from: IntVec,
        branch_to: IntVec,
        branch_active: BoolVec,
) -> IntVec:
    """Select missing angular references in independent AC phase regions.

    Passive AC branches couple voltage angles. VSC and DC connections transfer
    power without coupling the absolute AC phase, so they must not merge the
    regions used to select one reference bus.

    :param bus_types: Compiled bus modes before automatic promotion.
    :param active_power: Active-power injections used to rank PV candidates.
    :param bus_active: Active state of every bus.
    :param is_dc_bus: DC classification of every bus.
    :param branch_from: From-bus indices of passive branches.
    :param branch_to: To-bus indices of passive branches.
    :param branch_active: Active state of passive branches.
    :return: PV bus indices that must become angular references.
    """
    bus_count: int = len(bus_types)
    branch_count: int = len(branch_from)
    maximum_entry_count: int = bus_count + 2 * branch_count
    row_indices: IntVec = np.empty(maximum_entry_count, dtype=np.int64)
    column_indices: IntVec = np.empty(maximum_entry_count, dtype=np.int64)
    adjacency_data: IntVec = np.ones(maximum_entry_count, dtype=np.int64)
    entry_count: int = 0
    bus_index: int

    # Diagonal entries retain isolated active AC buses as one-bus phase regions.
    for bus_index in range(bus_count):
        if bool(bus_active[bus_index]) and not bool(is_dc_bus[bus_index]):
            row_indices[entry_count] = bus_index
            column_indices[entry_count] = bus_index
            entry_count += 1
        else:
            pass

    branch_index: int
    for branch_index in range(branch_count):
        from_index: int = int(branch_from[branch_index])
        to_index: int = int(branch_to[branch_index])
        connects_active_ac_buses: bool = (
            bool(branch_active[branch_index])
            and from_index >= 0
            and to_index >= 0
            and bool(bus_active[from_index])
            and bool(bus_active[to_index])
            and not bool(is_dc_bus[from_index])
            and not bool(is_dc_bus[to_index])
        )
        if connects_active_ac_buses:
            row_indices[entry_count] = from_index
            column_indices[entry_count] = to_index
            entry_count += 1
            row_indices[entry_count] = to_index
            column_indices[entry_count] = from_index
            entry_count += 1
        else:
            pass

    adjacency: sp.csc_matrix = sp.csc_matrix(
        (
            adjacency_data[:entry_count],
            (row_indices[:entry_count], column_indices[:entry_count]),
        ),
        shape=(bus_count, bus_count),
    )
    ac_active: BoolVec = np.logical_and(bus_active, np.logical_not(is_dc_bus))
    phase_regions: List[IntVec] = find_islands(
        adj=adjacency,
        active=ac_active,
    )
    selected_indices: IntVec = np.empty(len(phase_regions), dtype=np.int64)
    selected_count: int = 0
    phase_region: IntVec

    for phase_region in phase_regions:
        region_modes: IntVec = bus_types[phase_region]
        has_reference: bool = bool(
            np.any(region_modes == BusMode.Slack_tpe.value)
        )
        if has_reference:
            pass
        else:
            pv_candidates: IntVec = phase_region[
                region_modes == BusMode.PV_tpe.value
            ]
            if len(pv_candidates) == 0:
                pass
            else:
                ranked_candidate_index: int = int(
                    np.argmax(active_power[pv_candidates])
                )
                selected_indices[selected_count] = int(
                    pv_candidates[ranked_candidate_index]
                )
                selected_count += 1

    return selected_indices[:selected_count]


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

    __slots__ = (
        "nbus",
        "nbr",
        "t_idx",
        "nload",
        "ngen",
        "nbatt",
        "nshunt",
        "nhvdc",
        "nvsc",
        "nfluidnode",
        "nfluidturbine",
        "nfluidpump",
        "nfluidp2x",
        "nfluidpath",
        "Sbase",
        "bus_data",
        "passive_branch_data",
        "active_branch_data",
        "hvdc_data",
        "vsc_data",
        "load_data",
        "battery_data",
        "generator_data",
        "shunt_data",
        "fluid_node_data",
        "fluid_turbine_data",
        "fluid_pump_data",
        "fluid_p2x_data",
        "fluid_path_data",
        "__bus_map_arr",
        "__topology_performed",
        "structs_idtag_dict",
        "bus_dict",
    )

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
                 t_idx: int | None = None):
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
        :param t_idx:  Time index (None for the snapshot or the time series index [0..N-1])
        """

        self.nbus: int = nbus
        self.nbr: int = nbr
        self.t_idx: int | None = t_idx

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
        self.bus_dict: Dict[Any, int] | None = None

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

    def get_linear_power_injections(self) -> CxVec:
        """
        Compute the bus power injections seen by the linear studies (DC PF, PTDF).

        Those models assume a flat voltage of 1 p.u.

        :return: array of power injections in MW
        """
        return (self.get_power_injections()
                + np.conj(self.load_data.get_current_injections_per_bus()
                          + self.load_data.get_admittance_injections_per_bus()))

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
        nc.active_branch_data = self.active_branch_data.copy()
        nc.hvdc_data = self.hvdc_data.copy()
        nc.vsc_data = self.vsc_data.copy()
        nc.load_data = self.load_data.copy()
        nc.shunt_data = self.shunt_data.copy()
        nc.generator_data = self.generator_data.copy()
        nc.battery_data = self.battery_data.copy()
        nc.fluid_node_data = self.fluid_node_data.copy()
        nc.fluid_turbine_data = self.fluid_turbine_data.copy()
        nc.fluid_pump_data = self.fluid_pump_data.copy()
        nc.fluid_p2x_data = self.fluid_p2x_data.copy()
        nc.fluid_path_data = self.fluid_path_data.copy()
        nc.__bus_map_arr = self.__bus_map_arr.copy()
        nc.__topology_performed = self.__topology_performed
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

        uses_internal_bus_types: bool = bus_types is None
        if bus_types is None:
            bus_types = self.bus_data.bus_types
        else:
            bus_types = np.array(bus_types, dtype=int, copy=True)

        # TODO: SANPEN: What is this and why is it here? probably colliding with problem-specific logic later
        # Promote one PV source in every AC phase region before the generic
        # classifier runs. Imported PV/SL semantics remain unchanged in
        # MultiCircuit while VSC/DC links stay outside the phase graph.
        promoted_reference_indices: IntVec = select_ac_phase_reference_buses(
            bus_types=bus_types,
            active_power=Sbus.real,
            bus_active=self.bus_data.active,
            is_dc_bus=self.bus_data.is_dc,
            branch_from=self.passive_branch_data.F,
            branch_to=self.passive_branch_data.T,
            branch_active=self.passive_branch_data.active,
        )
        promoted_reference_index: np.int64
        for promoted_reference_index in promoted_reference_indices:
            if uses_internal_bus_types:
                self.bus_data.set_bus_mode(
                    idx=int(promoted_reference_index),
                    val=BusMode.Slack_tpe,
                )
            else:
                bus_types[int(promoted_reference_index)] = (
                    BusMode.Slack_tpe.value
                )

        simulation_indices: si.SimulationIndices = si.SimulationIndices(
            bus_types=bus_types,
            Pbus=Sbus.real,
            tap_module_control_mode=self.active_branch_data.tap_module_control_mode,
            tap_phase_control_mode=self.active_branch_data.tap_phase_control_mode,
            tap_controlled_buses=self.active_branch_data.tap_controlled_buses,
            F=self.passive_branch_data.F,
            T=self.passive_branch_data.T,
            is_dc_bus=self.bus_data.is_dc,
            force_only_pq_pv_vd_types=force_only_pq_pv_vd_types,
        )

        if uses_internal_bus_types:
            # Keep the physical P/Q/Vm/Va masks synchronized with every
            # explicit or automatically selected numerical reference.
            reference_index: np.int64
            for reference_index in simulation_indices.vd:
                self.bus_data.set_bus_mode(
                    idx=int(reference_index),
                    val=BusMode.Slack_tpe,
                )
        else:
            # Caller-owned bus-type arrays are temporary alternatives and must
            # not mutate the canonical control masks stored by this circuit.
            pass

        return simulation_indices

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

    def get_linear_admittance_matrices(self,
                                       indices: SimulationIndices | None = None) -> ycalc.LinearAdmittanceMatrices:
        """
        Get the linear admittances
        :return:LinearAdmittanceMatrices
        """
        if indices is None:
            indices = self.get_simulation_indices()

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
        # # generators
        # Qmax_bus = self.generator_data.get_qmax_per_bus()
        # Qmin_bus = self.generator_data.get_qmin_per_bus()
        #
        # if self.nbatt > 0:
        #     # batteries
        #     Qmax_bus += self.battery_data.get_qmax_per_bus()
        #     Qmin_bus += self.battery_data.get_qmin_per_bus()
        #
        # if self.nhvdc > 0:
        #     # hvdc from
        #     Qmax_bus += self.hvdc_data.get_qmax_from_per_bus()
        #     Qmin_bus += self.hvdc_data.get_qmin_from_per_bus()
        #
        #     # hvdc to
        #     Qmax_bus += self.hvdc_data.get_qmax_to_per_bus()
        #     Qmin_bus += self.hvdc_data.get_qmin_to_per_bus()
        #
        # if self.nshunt > 0:
        #     Qmax_bus += self.shunt_data.get_qmax_per_bus()
        #     Qmin_bus += self.shunt_data.get_qmin_per_bus()
        #
        # # fix zero values
        # Qmax_bus[Qmax_bus == 0] = 1e20
        # Qmin_bus[Qmin_bus == 0] = -1e20
        #
        # return Qmax_bus / self.Sbase, Qmin_bus / self.Sbase

        Qmax_bus, Qmin_bus = build_q_limits(
            nbus=self.bus_data.nbus,
            Sbase=self.Sbase,
            gen_idx=self.generator_data.bus_idx,
            q_min_gen=self.generator_data.qmin,
            q_max_gen=self.generator_data.qmax,
            active_gen=self.generator_data.active,
            control_mode_int_gen=self.generator_data.control_mode_int,

            batt_idx=self.battery_data.bus_idx,
            q_min_batt=self.battery_data.qmin,
            q_max_batt=self.battery_data.qmax,
            active_batt=self.battery_data.active,
            control_mode_int_batt=self.battery_data.control_mode_int,

            sh_idx=self.shunt_data.bus_idx,
            q_min_sh=self.shunt_data.qmin,
            q_max_sh=self.shunt_data.qmax,
            active_sh=self.shunt_data.active,
            control_mode_int_sh=self.shunt_data.control_mode_int,

            hvdc_f=self.hvdc_data.F,
            hvdc_t=self.hvdc_data.T,
            q_min_hvdc_f=self.hvdc_data.Qmin_f,
            q_max_hvdc_f=self.hvdc_data.Qmax_f,
            q_min_hvdc_t=self.hvdc_data.Qmin_t,
            q_max_hvdc_t=self.hvdc_data.Qmax_t,
            active_hvdc=self.hvdc_data.active,

            v_ctrl_val_gen=GeneratorControlMode.V.idx(),
            v_ctrl_val_sh = ShuntControlMode.Continuous.idx()
        )
        return Qmax_bus, Qmin_bus

    def compute_adjacency_matrix(self, consider_hvdc_as_island_links: bool = False) -> sp.csc_matrix:
        """
        Compute the adjacency matrix
        :param consider_hvdc_as_island_links: Does the HVDCLine works for the topology as a normal line?
        :return: csc_matrix
        """

        if consider_hvdc_as_island_links:

            # We want to consider HVDC lines as part of the graph for ACOPF simulations
            i, j, data, n_elm = tp.build_branches_C_coo_3(
                bus_active=self.bus_data.active,
                F1=self.passive_branch_data.F, T1=self.passive_branch_data.T, active1=self.passive_branch_data.active,
                F2=self.vsc_data.F, T2=self.vsc_data.T, FN2=self.vsc_data.F_dcn, active2=self.vsc_data.active,
                F3=self.hvdc_data.F, T3=self.hvdc_data.T, active3=self.hvdc_data.active,
            )
        else:

            # Case for most other simulations, where HvdcLine splits the islands
            i, j, data, n_elm = tp.build_branches_C_coo_2(
                bus_active=self.bus_data.active,
                F1=self.passive_branch_data.F, T1=self.passive_branch_data.T, active1=self.passive_branch_data.active,
                F2=self.vsc_data.F, T2=self.vsc_data.T, FN2=self.vsc_data.F_dcn, active2=self.vsc_data.active,
            )

        C = sp.coo_matrix((data, (i, j)), shape=(n_elm, self.bus_data.nbus), dtype=int)

        adjacency: sp.csc_matrix = (C.T @ C).tocsc()
        mutual: sp.coo_matrix = self.passive_branch_data.Ycoupling3.tocoo()
        if mutual.nnz > 0:
            # Coupled circuits must be solved together even without a galvanic path.
            nbranch: int = self.passive_branch_data.nelm
            rows: IntVec = (mutual.row % (4 * nbranch)) // 4
            columns: IntVec = (mutual.col % (4 * nbranch)) // 4
            active: BoolVec = self.passive_branch_data.active[rows] & self.passive_branch_data.active[columns]
            links: sp.csc_matrix = sp.csc_matrix(
                (np.ones(np.count_nonzero(active), dtype=int),
                 (self.passive_branch_data.F[rows[active]], self.passive_branch_data.F[columns[active]])),
                shape=adjacency.shape)
            adjacency += links + links.T
        else:
            pass
        return adjacency.tocsc()

    def process_reducible_branches(self) -> int:
        """
        Process the reducible branches (i.e. reduce branches like the switches) in-place
        :return: Number of reduced branches
        """
        i, j, data, n_red = tp.build_reducible_branches_C_coo(
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

                    if len(island) > 1:
                        sub_island = island[1:]
                        # set the mapping to the first index of the island to the reduced buses
                        self.__bus_map_arr[sub_island] = i0

                        # deactivate the reduced buses
                        self.bus_data.active[sub_island] = False

                        # preserve the control status and controlled set-points on the surviving bus
                        self.bus_data.propagate_controls(chosen_idx=i0, other_idx=sub_island)

            # remap
            self.passive_branch_data.remap(self.__bus_map_arr)
            self.active_branch_data.remap(self.__bus_map_arr)
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
                   logger: Logger | None = None) -> "NumericalCircuit":
        """
        Get the island corresponding to the given buses
        :param bus_idx: array of bus indices
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
        nc.vsc_data = self.vsc_data.slice(elm_idx=vsc_idx, bus_idx=bus_idx, bus_map=bus_map, logger=logger)
        nc.hvdc_data = self.hvdc_data.slice(elm_idx=hvdc_idx, bus_idx=bus_idx, bus_map=bus_map, logger=logger)

        # Correct bus types because of generators moving around due to the topology processing
        if self.topology_performed:
            correct_bus_types(gen_idx=gen_idx,
                              control_mode_int=nc.generator_data.control_mode_int,
                              gen_controllable_bus_idx=nc.generator_data.controllable_bus_idx,
                              bus_types=nc.bus_data.bus_types,
                              v_ctrl_val=GeneratorControlMode.V.idx())
            correct_bus_types(gen_idx=batt_idx,
                              control_mode_int=nc.battery_data.control_mode_int,
                              gen_controllable_bus_idx=nc.battery_data.controllable_bus_idx,
                              bus_types=nc.bus_data.bus_types,
                              v_ctrl_val=GeneratorControlMode.V.idx())

        return nc

    @staticmethod
    def _get_common_indices_by_idtag(idtags_a: StrVec, idtags_b: StrVec) -> Tuple[IntVec, IntVec]:
        """
        Get matching indices for the common idtags of two arrays, preserving the
        order from the first array.
        """
        idx_by_idtag_b = {str(idtag): i for i, idtag in enumerate(idtags_b)}
        idx_a = list()
        idx_b = list()

        for i, idtag in enumerate(idtags_a):
            j = idx_by_idtag_b.get(str(idtag), None)
            if j is not None:
                idx_a.append(i)
                idx_b.append(j)

        return np.array(idx_a, dtype=int), np.array(idx_b, dtype=int)

    def _slice_explicit(self,
                        bus_idx: IntVec,
                        br_idx: IntVec,
                        hvdc_idx: IntVec,
                        vsc_idx: IntVec,
                        load_idx: IntVec,
                        gen_idx: IntVec,
                        batt_idx: IntVec,
                        shunt_idx: IntVec,
                        logger: Logger | None = None) -> "NumericalCircuit":
        """
        Slice the numerical circuit using explicit index vectors for each data structure.
        """
        if logger is None:
            logger = Logger()

        bus_map = np.full(self.bus_data.nbus, -1, dtype=int)
        bus_map[bus_idx] = np.arange(len(bus_idx))

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

        nc.bus_data = self.bus_data.slice(elm_idx=bus_idx)
        nc.passive_branch_data = self.passive_branch_data.slice(elm_idx=br_idx, bus_idx=bus_idx,
                                                                bus_map=bus_map, logger=logger)
        nc.active_branch_data = self.active_branch_data.slice(elm_idx=br_idx, bus_idx=bus_idx,
                                                              bus_map=bus_map, logger=logger)
        nc.load_data = self.load_data.slice(elm_idx=load_idx, bus_idx=bus_idx, bus_map=bus_map)
        nc.battery_data = self.battery_data.slice(elm_idx=batt_idx, bus_idx=bus_idx, bus_map=bus_map)
        nc.generator_data = self.generator_data.slice(elm_idx=gen_idx, bus_idx=bus_idx, bus_map=bus_map)
        nc.shunt_data = self.shunt_data.slice(elm_idx=shunt_idx, bus_idx=bus_idx, bus_map=bus_map)
        nc.vsc_data = self.vsc_data.slice(elm_idx=vsc_idx, bus_idx=bus_idx, bus_map=bus_map, logger=logger)
        nc.hvdc_data = self.hvdc_data.slice(elm_idx=hvdc_idx, bus_idx=bus_idx, bus_map=bus_map, logger=logger)

        if self.topology_performed:
            correct_bus_types(gen_idx=gen_idx,
                              control_mode_int=nc.generator_data.control_mode_int,
                              gen_controllable_bus_idx=nc.generator_data.controllable_bus_idx,
                              bus_types=nc.bus_data.bus_types,
                              v_ctrl_val=GeneratorControlMode.V.idx())
            correct_bus_types(gen_idx=batt_idx,
                              control_mode_int=nc.battery_data.control_mode_int,
                              gen_controllable_bus_idx=nc.battery_data.controllable_bus_idx,
                              bus_types=nc.bus_data.bus_types,
                              v_ctrl_val=GeneratorControlMode.V.idx())

        nc.consolidate_information()
        return nc

    def _align_to_common_idtags(self, nc_2: "NumericalCircuit") -> Tuple["NumericalCircuit", "NumericalCircuit"]:
        """
        Align two numerical circuits to their common element idtags.
        """
        bus_idx_1, bus_idx_2 = self._get_common_indices_by_idtag(self.bus_data.idtag, nc_2.bus_data.idtag)
        bus_set_1 = set(int(i) for i in bus_idx_1.tolist())
        bus_set_2 = set(int(i) for i in bus_idx_2.tolist())

        def _filter_branch_like(idx_1: IntVec, idx_2: IntVec, f_1: IntVec, t_1: IntVec, f_2: IntVec, t_2: IntVec):
            keep_1 = list()
            keep_2 = list()
            for i_1, i_2 in zip(idx_1.tolist(), idx_2.tolist()):
                if (int(f_1[i_1]) in bus_set_1 and int(t_1[i_1]) in bus_set_1
                        and int(f_2[i_2]) in bus_set_2 and int(t_2[i_2]) in bus_set_2):
                    keep_1.append(i_1)
                    keep_2.append(i_2)
            return np.array(keep_1, dtype=int), np.array(keep_2, dtype=int)

        def _filter_monopole_like(idx_1: IntVec, idx_2: IntVec, bus_1: IntVec, bus_2: IntVec,
                                  ctrl_1: IntVec | None = None, ctrl_2: IntVec | None = None):
            keep_1 = list()
            keep_2 = list()
            for i_1, i_2 in zip(idx_1.tolist(), idx_2.tolist()):
                if int(bus_1[i_1]) not in bus_set_1 or int(bus_2[i_2]) not in bus_set_2:
                    continue
                if ctrl_1 is not None and int(ctrl_1[i_1]) > -1 and int(ctrl_1[i_1]) not in bus_set_1:
                    continue
                if ctrl_2 is not None and int(ctrl_2[i_2]) > -1 and int(ctrl_2[i_2]) not in bus_set_2:
                    continue
                keep_1.append(i_1)
                keep_2.append(i_2)
            return np.array(keep_1, dtype=int), np.array(keep_2, dtype=int)

        br_idx_1, br_idx_2 = self._get_common_indices_by_idtag(self.passive_branch_data.idtag,
                                                               nc_2.passive_branch_data.idtag)
        br_idx_1, br_idx_2 = _filter_branch_like(br_idx_1, br_idx_2,
                                                 self.passive_branch_data.F, self.passive_branch_data.T,
                                                 nc_2.passive_branch_data.F, nc_2.passive_branch_data.T)

        hvdc_idx_1, hvdc_idx_2 = self._get_common_indices_by_idtag(self.hvdc_data.idtag, nc_2.hvdc_data.idtag)
        hvdc_idx_1, hvdc_idx_2 = _filter_branch_like(hvdc_idx_1, hvdc_idx_2,
                                                     self.hvdc_data.F, self.hvdc_data.T,
                                                     nc_2.hvdc_data.F, nc_2.hvdc_data.T)

        vsc_idx_1, vsc_idx_2 = self._get_common_indices_by_idtag(self.vsc_data.idtag, nc_2.vsc_data.idtag)
        vsc_idx_1, vsc_idx_2 = _filter_branch_like(vsc_idx_1, vsc_idx_2,
                                                   self.vsc_data.F, self.vsc_data.T,
                                                   nc_2.vsc_data.F, nc_2.vsc_data.T)

        load_idx_1, load_idx_2 = self._get_common_indices_by_idtag(self.load_data.idtag, nc_2.load_data.idtag)
        load_idx_1, load_idx_2 = _filter_monopole_like(load_idx_1, load_idx_2,
                                                       self.load_data.bus_idx, nc_2.load_data.bus_idx)

        gen_idx_1, gen_idx_2 = self._get_common_indices_by_idtag(self.generator_data.idtag, nc_2.generator_data.idtag)
        gen_idx_1, gen_idx_2 = _filter_monopole_like(gen_idx_1, gen_idx_2,
                                                     self.generator_data.bus_idx, nc_2.generator_data.bus_idx,
                                                     self.generator_data.controllable_bus_idx,
                                                     nc_2.generator_data.controllable_bus_idx)

        batt_idx_1, batt_idx_2 = self._get_common_indices_by_idtag(self.battery_data.idtag, nc_2.battery_data.idtag)
        batt_idx_1, batt_idx_2 = _filter_monopole_like(batt_idx_1, batt_idx_2,
                                                       self.battery_data.bus_idx, nc_2.battery_data.bus_idx,
                                                       self.battery_data.controllable_bus_idx,
                                                       nc_2.battery_data.controllable_bus_idx)

        shunt_idx_1, shunt_idx_2 = self._get_common_indices_by_idtag(self.shunt_data.idtag, nc_2.shunt_data.idtag)
        shunt_idx_1, shunt_idx_2 = _filter_monopole_like(shunt_idx_1, shunt_idx_2,
                                                         self.shunt_data.bus_idx, nc_2.shunt_data.bus_idx,
                                                         self.shunt_data.controllable_bus_idx,
                                                         nc_2.shunt_data.controllable_bus_idx)

        logger = Logger()
        return (
            self._slice_explicit(bus_idx=bus_idx_1, br_idx=br_idx_1, hvdc_idx=hvdc_idx_1, vsc_idx=vsc_idx_1,
                                 load_idx=load_idx_1, gen_idx=gen_idx_1, batt_idx=batt_idx_1,
                                 shunt_idx=shunt_idx_1, logger=logger),
            nc_2._slice_explicit(bus_idx=bus_idx_2, br_idx=br_idx_2, hvdc_idx=hvdc_idx_2, vsc_idx=vsc_idx_2,
                                 load_idx=load_idx_2, gen_idx=gen_idx_2, batt_idx=batt_idx_2,
                                 shunt_idx=shunt_idx_2, logger=logger),
        )

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
        n_red = self.process_reducible_branches()

        # find the matching islands
        adj = self.compute_adjacency_matrix(consider_hvdc_as_island_links=consider_hvdc_as_island_links)

        idx_islands = tp.find_islands(adj=adj, active=self.bus_data.active)

        circuit_islands = list()  # type: List[NumericalCircuit]

        for island_bus_indices in idx_islands:
            if ignore_single_node_islands:
                if len(island_bus_indices) > 1:
                    island = self.get_island(bus_idx=island_bus_indices, logger=logger)
                    circuit_islands.append(island)
            else:
                island = self.get_island(bus_idx=island_bus_indices, logger=logger)
                circuit_islands.append(island)

        return circuit_islands

    def _compare_strict(self, nc_2: "NumericalCircuit", tol=1e-6) -> Tuple[bool, Logger]:
        """
        Strict position-based numerical circuit comparison.
        :param nc_2: other NumericalCircuit
        :param tol: tolerance for numerical values
        :return: all ok?, Logger with the errors and warning events
        """

        logger = Logger()

        # --------------------------------------------------------------------------------------------------------------
        #  Compare data
        # --------------------------------------------------------------------------------------------------------------

        self.passive_branch_data.compare(other=nc_2.passive_branch_data, tol=tol, logger=logger)
        self.active_branch_data.compare(other=nc_2.active_branch_data, tol=tol, logger=logger)
        self.bus_data.compare(other=nc_2.bus_data, tol=tol, logger=logger)
        self.generator_data.compare(other=nc_2.generator_data, tol=tol, logger=logger)
        self.load_data.compare(other=nc_2.load_data, tol=tol, logger=logger)
        self.shunt_data.compare(other=nc_2.shunt_data, tol=tol, logger=logger)

        # --------------------------------------------------------------------------------------------------------------
        #  Compare arrays and data
        # --------------------------------------------------------------------------------------------------------------

        Sbus = self.get_power_injections_pu()
        Sbus2 = nc_2.get_power_injections_pu()

        # the .copy() is so that bus_types is not affected after using this
        sim_idx = self.get_simulation_indices(Sbus=Sbus.copy(), bus_types=self.bus_data.bus_types.copy())
        sim_idx2 = nc_2.get_simulation_indices(Sbus=Sbus2.copy(), bus_types=nc_2.bus_data.bus_types.copy())

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

        return logger.error_count() == 0, logger

    def compare(self, nc_2: "NumericalCircuit", tol=1e-6, by_idtag: bool = False) -> Tuple[bool, Logger]:
        """
        Compare this numerical circuit with another numerical circuit.
        :param nc_2: other NumericalCircuit
        :param tol: tolerance for numerical values
        :param by_idtag: comparison mode (if true the comparison is made by idtag instead of by raw shape)
        :return: all ok?, Logger with the errors and warning events
        """
        if by_idtag:
            nc_1_cmp, nc_2_cmp = self._align_to_common_idtags(nc_2=nc_2)
            return nc_1_cmp._compare_strict(nc_2=nc_2_cmp, tol=tol)
        else:
            return self._compare_strict(nc_2=nc_2, tol=tol)

    def _compare_injection_sums_against(self,
                                        other: "NumericalCircuit",
                                        tol: float,
                                        logger: Logger,
                                        label: str) -> None:
        """
        Compare electrically relevant total injection sums against another circuit.
        """
        compare_arr(np.atleast_1d(self.get_power_injections_pu().sum()),
                    np.atleast_1d(other.get_power_injections_pu().sum()),
                    tol, label, 'sum(Sbus)', logger)
        compare_arr(np.atleast_1d(self.get_current_injections_pu().sum()),
                    np.atleast_1d(other.get_current_injections_pu().sum()),
                    tol, label, 'sum(Ibus)', logger)
        compare_arr(np.atleast_1d(self.get_admittance_injections_pu().sum()),
                    np.atleast_1d(other.get_admittance_injections_pu().sum()),
                    tol, label, 'sum(Ybus_load)', logger)
        compare_arr(np.atleast_1d(self.get_Yshunt_bus_pu().sum()),
                    np.atleast_1d(other.get_Yshunt_bus_pu().sum()),
                    tol, label, 'sum(Ybus_shunt)', logger)

    def compare_sums(self, nc_2: "NumericalCircuit", tol=1e-6) -> Tuple[bool, Logger]:
        """
        Compare raw injection sums.
        """
        logger = Logger()
        self._compare_injection_sums_against(other=nc_2, tol=tol, logger=logger, label='Injection sums')
        return logger.error_count() == 0, logger

    def get_structural_ntc(self, bus_a1_idx: IntVec, bus_a2_idx: IntVec) -> float:
        """
        Get the structural NTC
        :param bus_a1_idx: array of bus indices of the area from
        :param bus_a2_idx: array of bus indices of the area to
        :return: structural NTC in MVA
        """
        sum_ratings = 0.0

        for struct in [self.passive_branch_data, self.hvdc_data, self.vsc_data]:

            inter_area_branches = struct.get_inter_areas(bus_idx_from=bus_a1_idx, bus_idx_to=bus_a2_idx)
            for k, sense in inter_area_branches:
                sum_ratings += struct.rates[k]

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
