# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
import numpy as np
import pandas as pd
import scipy.sparse as sp
from typing import List, Tuple, Dict, Union, TYPE_CHECKING

from GridCalEngine.Devices import RemedialAction
from GridCalEngine.basic_structures import Logger
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.basic_structures import Vec, IntVec, CxVec, BoolVec
from GridCalEngine.enumerations import BranchImpedanceMode, BusMode, ContingencyOperationTypes
import GridCalEngine.Topology.topology as tp
import GridCalEngine.Topology.simulation_indices as si

import GridCalEngine.Compilers.circuit_to_data as gc_compiler2
import GridCalEngine.Topology.admittance_matrices as ycalc
import GridCalEngine.DataStructures as ds
from GridCalEngine.Devices.Substation.bus import Bus
from GridCalEngine.Devices.Aggregation.area import Area
from GridCalEngine.Devices.Aggregation.investment import Investment
from GridCalEngine.Devices.Aggregation.contingency import Contingency

if TYPE_CHECKING:  # Only imports the below statements during type checking
    pass

ALL_STRUCTS = Union[
    ds.BusData,
    ds.GeneratorData,
    ds.BatteryData,
    ds.LoadData,
    ds.ShuntData,
    ds.BranchData,
    ds.HvdcData,
    ds.FluidNodeData,
    ds.FluidTurbineData,
    ds.FluidPumpData,
    ds.FluidP2XData,
    ds.FluidPathData
]


def CheckArr(arr: Vec | IntVec | BoolVec | CxVec, arr_expected: Vec | IntVec | BoolVec | CxVec,
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
        if arr.dtype == np.bool_:
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


def get_inter_areas_branch(F: np.ndarray,
                           T: np.ndarray,
                           buses_in_a1: np.ndarray,
                           buses_in_a2: np.ndarray):
    """
    Get the Branches that join two areas
    :param F: Array indices of branch bus from indices
    :param T: Array of branch bus to indices
    :param buses_in_a1: Array of bus indices belonging area from
    :param buses_in_a2: Array of bus indices belonging area to
    :return: List of (branch index, branch object, flow sense w.r.t the area exchange)
    """
    nbr = len(F)
    lst: List[Tuple[int, float]] = list()
    for k in range(nbr):
        if F[k] in buses_in_a1 and T[k] in buses_in_a2:
            lst.append((k, 1.0))
        elif F[k] in buses_in_a2 and T[k] in buses_in_a1:
            lst.append((k, -1.0))
    return lst


def get_devices_per_areas(Cdev: sp.csc_matrix,
                          buses_in_a1: IntVec,
                          buses_in_a2: IntVec):
    """
    Get the devices that belong to the Area 1, Area 2 and the rest of areas
    :param Cdev: CSC connectivity matrix (bus, elm)
    :param buses_in_a1: Array of bus indices belonging area from
    :param buses_in_a2: Array of bus indices belonging area to
    :return: Tree lists: (devs_in_a1, devs_in_a2, devs_out) each of the lists contains (bus index, device index) tuples
    """
    assert isinstance(Cdev, sp.csc_matrix)
    devs_in_a1 = list()
    devs_in_a2 = list()
    devs_out = list()
    for j in range(Cdev.shape[1]):  # for each bus
        for ii in range(Cdev.indptr[j], Cdev.indptr[j + 1]):
            i = Cdev.indices[ii]
            if i in buses_in_a1:
                devs_in_a1.append((i, j))  # i: bus idx, j: dev idx
            elif i in buses_in_a2:
                devs_in_a2.append((i, j))  # i: bus idx, j: dev idx
            else:
                devs_out.append((i, j))  # i: bus idx, j: dev idx

    return devs_in_a1, devs_in_a2, devs_out


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
            'idx_dbeq',
            'x',
            'f(x)',
            'Jacobian',
        ]
    }

    def __init__(self,
                 nbus: int,
                 nbr: int,
                 nhvdc: int,
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

        self.nfluidnode: int = nfluidnode
        self.nfluidturbine: int = nfluidturbine
        self.nfluidpump: int = nfluidpump
        self.nfluidp2x: int = nfluidp2x
        self.nfluidpath: int = nfluidpath

        self.Sbase: float = sbase

        # --------------------------------------------------------------------------------------------------------------
        # Data structures
        # --------------------------------------------------------------------------------------------------------------
        self.bus_data: ds.BusData = ds.BusData(nbus=nbus)
        self.branch_data: ds.BranchData = ds.BranchData(nelm=nbr, nbus=nbus)
        self.hvdc_data: ds.HvdcData = ds.HvdcData(nelm=nhvdc, nbus=nbus)

        self.load_data: ds.LoadData = ds.LoadData(nelm=nload, nbus=nbus)

        self.battery_data: ds.BatteryData = ds.BatteryData(nelm=nbatt, nbus=nbus)

        self.generator_data: ds.GeneratorData = ds.GeneratorData(nelm=ngen, nbus=nbus)

        self.shunt_data: ds.ShuntData = ds.ShuntData(nelm=nshunt, nbus=nbus)

        self.fluid_node_data: ds.FluidNodeData = ds.FluidNodeData(nelm=nfluidnode)
        self.fluid_turbine_data: ds.FluidTurbineData = ds.FluidTurbineData(nelm=nfluidturbine)
        self.fluid_pump_data: ds.FluidPumpData = ds.FluidPumpData(nelm=nfluidpump)
        self.fluid_p2x_data: ds.FluidP2XData = ds.FluidP2XData(nelm=nfluidp2x)
        self.fluid_path_data: ds.FluidPathData = ds.FluidPathData(nelm=nfluidpath)

        # --------------------------------------------------------------------------------------------------------------
        # Internal variables filled on demand, to be ready to consume once computed
        # --------------------------------------------------------------------------------------------------------------

        self.Vbus_: Union[None, CxVec] = None
        self.Sbus_: Union[None, CxVec] = None
        self.Ibus_: Union[None, CxVec] = None
        self.YloadBus_: Union[None, CxVec] = None
        self.Yshunt_from_devices_: Union[None, CxVec] = None
        self.Bmax_bus_: Union[None, Vec] = None
        self.Bmin_bus_: Union[None, Vec] = None
        self.Qmax_bus_: Union[None, Vec] = None
        self.Qmin_bus_: Union[None, Vec] = None

        # class that holds all the simulation indices
        self.simulation_indices_: Union[None, si.SimulationIndices] = None

        # Connectivity matrices
        self.conn_matrices_: Union[tp.ConnectivityMatrices, None] = None

        # general admittances
        self.admittances_: Union[ycalc.AdmittanceMatrices, None] = None

        # Admittance for HELM / AC linear
        self.series_admittances_: Union[ycalc.SeriesAdmittanceMatrices, None] = None

        # Admittances for Fast-Decoupled
        self.fast_decoupled_admittances_: Union[ycalc.FastDecoupledAdmittanceMatrices, None] = None

        # Admittances for Linear
        self.linear_admittances_: Union[ycalc.LinearAdmittanceMatrices, None] = None

        # dictionary relating idtags to structures and indices
        # Dict[idtag] -> (structure, index)
        self.structs_dict_: Union[Dict[str, Tuple[ALL_STRUCTS, int]], None] = None

    def reset_calculations(self) -> None:
        """
        This resets the lazy evaluation of the calculations like Ybus, Sbus, etc...
        If you want to use the NumericalCircuit as structure to modify stuff,
        this should be called after all modifications prior to the usage in any
        calculation
        """
        self.Vbus_: Union[None, CxVec] = None
        self.Sbus_: Union[None, CxVec] = None
        self.Ibus_: Union[None, CxVec] = None
        self.YloadBus_: Union[None, CxVec] = None
        self.Yshunt_from_devices_: Union[None, CxVec] = None
        self.Qmax_bus_: Union[None, Vec] = None
        self.Qmin_bus_: Union[None, Vec] = None
        self.Bmax_bus_: Union[None, Vec] = None
        self.Bmin_bus_: Union[None, Vec] = None

        # Connectivity matrices
        self.conn_matrices_: Union[tp.ConnectivityMatrices, None] = None

        # general admittances
        self.admittances_: Union[ycalc.AdmittanceMatrices, None] = None

        # Admittance for HELM / AC linear
        self.series_admittances_: Union[ycalc.SeriesAdmittanceMatrices, None] = None

        # Admittances for Fast-Decoupled
        self.fast_decoupled_admittances_: Union[ycalc.FastDecoupledAdmittanceMatrices, None] = None

        # Admittances for Linear
        self.linear_admittances_: Union[ycalc.LinearAdmittanceMatrices, None] = None

        # dictionary relating idtags to structures and indices
        # Dict[idtag] -> (structure, index)
        self.structs_dict_: Union[Dict[str, Tuple[ALL_STRUCTS, int]], None] = None

    def get_injections(self, normalize=True) -> CxVec:
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

        # HVDC forced power is not handled here because of the possible islands

        if normalize:
            Sbus /= self.Sbase

        return Sbus

    def consolidate_information(self) -> None:
        """
        Consolidates the information of this object
        """

        self.nbus = len(self.bus_data)
        self.nbr = len(self.branch_data)
        self.nhvdc = len(self.hvdc_data)
        self.nload = len(self.load_data)
        self.ngen = len(self.generator_data)
        self.nbatt = len(self.battery_data)
        self.nshunt = len(self.shunt_data)

        self.branch_data.C_branch_bus_f = self.branch_data.C_branch_bus_f.tocsc()
        self.branch_data.C_branch_bus_t = self.branch_data.C_branch_bus_t.tocsc()

        self.hvdc_data.C_hvdc_bus_f = self.hvdc_data.C_hvdc_bus_f.tocsc()
        self.hvdc_data.C_hvdc_bus_t = self.hvdc_data.C_hvdc_bus_t.tocsc()
        self.load_data.C_bus_elm = self.load_data.C_bus_elm.tocsr()
        self.battery_data.C_bus_elm = self.battery_data.C_bus_elm.tocsr()
        self.generator_data.C_bus_elm = self.generator_data.C_bus_elm.tocsr()
        self.shunt_data.C_bus_elm = self.shunt_data.C_bus_elm.tocsr()

        self.bus_data.installed_power = self.generator_data.get_installed_power_per_bus()
        self.bus_data.installed_power += self.battery_data.get_installed_power_per_bus()

    def copy(self) -> "NumericalCircuit":
        """
        Deep copy of ths object
        :return: NumericalCircuit instance
        """
        nc = NumericalCircuit(nbus=self.nbus,
                              nbr=self.nbr,
                              nhvdc=self.nhvdc,
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
        nc.branch_data = self.branch_data.copy()
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
        nc.consolidate_information()

        return nc

    def get_structures_list(self) -> List[ALL_STRUCTS]:
        """
        Get a list of the structures inside the NumericalCircuit
        :return:
        """
        return [self.bus_data,
                self.generator_data,
                self.battery_data,
                self.load_data,
                self.shunt_data,
                self.branch_data,
                self.hvdc_data,
                self.fluid_node_data,
                self.fluid_turbine_data,
                self.fluid_pump_data,
                self.fluid_p2x_data,
                self.fluid_path_data]

    def get_structs_idtag_dict(self) -> Dict[str, Tuple[ALL_STRUCTS, int]]:
        """
        Get a dictionary to map idtags to the structure they belong and the index
        :return: Dictionary relating an idtag to the structure and the index in it (Dict[idtag] -> (structure, index))
        """
        structs_dict: Dict[str, Tuple[ALL_STRUCTS, int]] = dict()

        for struct_elm in self.get_structures_list():

            for i, idtag in enumerate(struct_elm.idtag):
                structs_dict[idtag] = (struct_elm, i)

        return structs_dict

    def set_investments_status(self, investments_list: List[Investment], status: int) -> None:
        """
        Set the status of a list of investments
        :param investments_list: list of investments
        :param status: status to set in the internal structures
        """

        for inv in investments_list:

            # search the investment device
            structure, idx = self.structs_dict.get(inv.device_idtag, (None, 0))

            if structure is not None:
                structure.active[idx] = status
            else:
                raise Exception('Could not find the idtag, is this a programming bug?')

    def set_con_or_ra_status(self, event_list: List[Contingency | RemedialAction],
                             revert: bool = False):
        """
        Set the status of a list of contingencies
        :param event_list: list of contingencies and or remedial actions
        :param revert: if false, the contingencies are applied, else they are reversed
        """
        # apply the contingencies
        for cnt in event_list:

            if isinstance(cnt, (Contingency, RemedialAction)):

                # search the investment device
                structure, idx = self.structs_dict.get(cnt.device_idtag, (None, 0))

                if structure is not None:
                    if cnt.prop == ContingencyOperationTypes.Active:
                        if revert:
                            structure.active[idx] = int(not bool(cnt.value))
                        else:
                            structure.active[idx] = int(cnt.value)
                    elif cnt.prop == ContingencyOperationTypes.PowerPercentage:
                        if revert:
                            structure.p[idx] /= float(cnt.value / 100.0)
                        else:
                            structure.p[idx] *= float(cnt.value / 100.0)
                    else:
                        print(f'Unknown contingency property {cnt.prop} at {cnt.name} {cnt.idtag}')
                else:
                    print(f'contingency device not found {cnt.name} {cnt.idtag}')
            else:
                raise Exception(f"The object {cnt} is not a Contingency or a remedial action")

    def set_linear_con_or_ra_status(self, event_list: List[Contingency | RemedialAction],
                                    revert: bool = False):
        """
        Set the status of a list of contingencies
        :param event_list: list of contingencies and or remedial actions
        :param revert: if false, the contingencies are applied, else they are reversed
        """
        injections = np.zeros(self.nbus)
        # apply the contingencies
        for cnt in event_list:

            if isinstance(cnt, (Contingency, RemedialAction)):

                # search the investment device
                structure, idx = self.structs_dict.get(cnt.device_idtag, (None, 0))

                if structure is not None:
                    if cnt.prop == ContingencyOperationTypes.Active:
                        if revert:
                            structure.active[idx] = int(not bool(cnt.value))
                        else:
                            structure.active[idx] = int(cnt.value)
                    elif cnt.prop == ContingencyOperationTypes.PowerPercentage:
                        # TODO Cambiar el acceso a P por una función (o función que incremente- decremente porcentaje)
                        assert not isinstance(structure, ds.HvdcData)  # TODO Arreglar esto
                        dev_injections = np.zeros(structure.size())
                        dev_injections[idx] -= structure.p[idx]
                        if revert:
                            structure.p[idx] /= float(cnt.value / 100.0)
                        else:
                            structure.p[idx] *= float(cnt.value / 100.0)
                        dev_injections[idx] += structure.p[idx]
                        injections += structure.get_array_per_bus(dev_injections)
                    else:
                        print(f'Unknown contingency property {cnt.prop} at {cnt.name} {cnt.idtag}')
                else:
                    print(f'contingency device not found {cnt.name} {cnt.idtag}')
            else:
                raise Exception(f"The object {cnt} is not a Contingency or a remedial action")

        return injections

    @property
    def original_bus_idx(self):
        """

        :return:
        """
        return self.bus_data.original_idx

    @property
    def original_branch_idx(self):
        """

        :return:
        """
        return self.branch_data.original_idx

    @property
    def original_load_idx(self):
        """

        :return:
        """
        return self.load_data.original_idx

    @property
    def original_generator_idx(self):
        """

        :return:
        """
        return self.generator_data.original_idx

    @property
    def original_battery_idx(self):
        """

        :return:
        """
        return self.battery_data.original_idx

    @property
    def original_shunt_idx(self):
        """

        :return:
        """
        return self.shunt_data.original_idx

    @property
    def Vbus(self):
        """

        :return:
        """
        if self.Vbus_ is None:
            self.Vbus_ = self.bus_data.Vbus

        return self.Vbus_

    @property
    def Sbus(self) -> CxVec:
        """
        Returns the power Injections in per-unit
        :return: array of power Injections (p.u.)
        """

        if self.Sbus_ is None:
            self.Sbus_ = self.get_injections(normalize=True)

        return self.Sbus_

    @property
    def Pbus(self) -> Vec:
        """
        Return real power injections in per-unit
        :return: array of real power (p.u.)
        """
        return self.Sbus.real

    @property
    def Ibus(self):
        """

        :return:
        """
        if self.Ibus_ is None:
            self.Ibus_ = self.load_data.get_current_injections_per_bus() / self.Sbase

        return self.Ibus_

    @property
    def YLoadBus(self):
        """

        :return:
        """
        if self.YloadBus_ is None:
            self.YloadBus_ = self.load_data.get_admittance_injections_per_bus() / self.Sbase

        return self.YloadBus_

    @property
    def Rates(self):
        """

        :return:
        """
        return self.branch_data.rates

    @property
    def ContingencyRates(self):
        """

        :return:
        """
        return self.branch_data.contingency_rates

    @property
    def Qmax_bus(self):
        """

        :return:
        """
        if self.Qmax_bus_ is None:
            self.Qmax_bus_, self.Qmin_bus_ = self.compute_reactive_power_limits()

        return self.Qmax_bus_

    @property
    def Qmin_bus(self):
        """

        :return:
        """
        if self.Qmin_bus_ is None:
            self.Qmax_bus_, self.Qmin_bus_ = self.compute_reactive_power_limits()

        return self.Qmin_bus_

    @property
    def Yshunt_from_devices(self):
        """

        :return:
        """
        # compute on demand and store
        if self.Yshunt_from_devices_ is None:
            self.Yshunt_from_devices_ = self.shunt_data.get_injections_per_bus() / self.Sbase

        return self.Yshunt_from_devices_

    @property
    def bus_types(self):
        """

        :return:
        """
        return self.bus_data.bus_types

    @property
    def bus_installed_power(self):
        """

        :return:
        """
        return self.bus_data.installed_power

    @property
    def bus_names(self):
        """

        :return:
        """
        return self.bus_data.names

    @property
    def branch_names(self):
        """

        :return:
        """
        return self.branch_data.names

    @property
    def rates(self):
        """

        :return:
        """
        return self.branch_data.rates

    @property
    def contingency_rates(self):
        """

        :return:
        """
        return self.branch_data.contingency_rates

    @property
    def load_names(self):
        """

        :return:
        """
        return self.load_data.names

    @property
    def generator_names(self):
        """

        :return:
        """
        return self.generator_data.names

    @property
    def battery_names(self):
        """

        :return:
        """
        return self.battery_data.names

    @property
    def shunt_names(self):
        """

        :return:
        """
        return self.shunt_data.names

    @property
    def hvdc_names(self):
        """

        :return:
        """
        return self.hvdc_data.names

    @property
    def F(self):
        """

        :return:
        """
        return self.branch_data.F

    @property
    def T(self):
        """

        :return:
        """
        return self.branch_data.T

    @property
    def branch_rates(self):
        """

        :return:
        """
        return self.branch_data.rates

    @property
    def ac_indices(self):
        """
        Array of indices of the AC buses
        :return: array of indices
        """
        if self.simulation_indices_ is None:
            self.simulation_indices_ = self.get_simulation_indices()

        return self.simulation_indices_.ac

    @property
    def dc_indices(self):
        """
        Array of indices of the DC buses
        :return: array of indices
        """
        if self.simulation_indices_ is None:
            self.simulation_indices_ = self.get_simulation_indices()

        return self.simulation_indices_.dc

    @property
    def Cf(self):
        """
        Connectivity matrix of the "from" nodes
        :return: CSC matrix
        """
        # compute on demand and store
        if self.conn_matrices_ is None:
            self.conn_matrices_ = self.get_connectivity_matrices()

        return self.conn_matrices_.Cf

    @property
    def Ct(self):
        """
        Connectivity matrix of the "to" nodes
        :return: CSC matrix
        """
        # compute on demand and store
        if self.conn_matrices_ is None:
            self.conn_matrices_ = self.get_connectivity_matrices()

        return self.conn_matrices_.Ct

    @property
    def A(self):
        """
        Connectivity matrix
        :return: CSC matrix
        """
        if self.conn_matrices_ is None:
            self.conn_matrices_ = self.get_connectivity_matrices()

        return self.conn_matrices_.A

    def get_simulation_indices(self) -> si.SimulationIndices:
        """
        Get the simulation indices
        :return: SimulationIndices
        """
        return si.SimulationIndices(bus_types=self.bus_data.bus_types,
                                    Pbus=self.Sbus.real,
                                    tap_module_control_mode=self.branch_data.tap_module_control_mode,
                                    tap_phase_control_mode=self.branch_data.tap_phase_control_mode,
                                    tap_controlled_buses=self.branch_data.tap_controlled_buses,
                                    is_converter=self.branch_data.is_converter,
                                    F=self.branch_data.F,
                                    T=self.branch_data.T,
                                    is_dc_bus=self.bus_data.is_dc)

    def get_connectivity_matrices(self) -> tp.ConnectivityMatrices:
        """
        Get connectivity matrices
        :return:
        """
        return tp.compute_connectivity(
            branch_active=self.branch_data.active,
            Cf_=self.branch_data.C_branch_bus_f.tocsc(),
            Ct_=self.branch_data.C_branch_bus_t.tocsc()
        )

    def get_admittance_matrices(self) -> ycalc.AdmittanceMatrices:
        """
        Get Admittance structures
        :return: Admittance object
        """

        # compute admittances on demand
        return ycalc.compute_admittances(
            R=self.branch_data.R,
            X=self.branch_data.X,
            G=self.branch_data.G,
            B=self.branch_data.B,
            k=self.branch_data.k,
            tap_module=self.branch_data.tap_module,
            vtap_f=self.branch_data.virtual_tap_f,
            vtap_t=self.branch_data.virtual_tap_t,
            tap_angle=self.branch_data.tap_angle,
            Beq=self.branch_data.Beq,
            Cf=self.Cf,
            Ct=self.Ct,
            Gsw=self.branch_data.G0sw,
            Yshunt_bus=self.Yshunt_from_devices,
            conn=self.branch_data.conn,
            seq=1,
            add_windings_phase=False
        )

    def get_series_admittance_matrices(self) -> ycalc.SeriesAdmittanceMatrices:
        """

        :return:
        """
        return ycalc.compute_split_admittances(
            R=self.branch_data.R,
            X=self.branch_data.X,
            G=self.branch_data.G,
            B=self.branch_data.B,
            k=self.branch_data.k,
            tap_module=self.branch_data.tap_module,
            vtap_f=self.branch_data.virtual_tap_f,
            vtap_t=self.branch_data.virtual_tap_t,
            tap_angle=self.branch_data.tap_angle,
            Beq=self.branch_data.Beq,
            Cf=self.Cf,
            Ct=self.Ct,
            G0sw=self.branch_data.G0sw,
            If=np.zeros(len(self.branch_data)),
            a=self.branch_data.alpha1,
            b=self.branch_data.alpha2,
            c=self.branch_data.alpha3,
            Yshunt_bus=self.Yshunt_from_devices,
        )

    def get_fast_decoupled_amittances(self) -> ycalc.FastDecoupledAdmittanceMatrices:
        """

        :return:
        """
        return ycalc.compute_fast_decoupled_admittances(
            X=self.branch_data.X,
            B=self.branch_data.B,
            tap_module=self.branch_data.tap_module,
            vtap_f=self.branch_data.virtual_tap_f,
            vtap_t=self.branch_data.virtual_tap_t,
            Cf=self.Cf,
            Ct=self.Ct,
        )

    def get_linear_admittance_matrices(self) -> ycalc.LinearAdmittanceMatrices:
        """

        :return:
        """
        return ycalc.compute_linear_admittances(
            nbr=self.nbr,
            X=self.branch_data.X,
            R=self.branch_data.R,
            m=self.branch_data.tap_module,
            active=self.branch_data.active,
            Cf=self.Cf,
            Ct=self.Ct,
            ac=self.ac_indices,
            dc=self.dc_indices
        )

    @property
    def Ybus(self):
        """
        Admittance matrix
        :return: CSC matrix
        """

        # compute admittances on demand
        if self.admittances_ is None:
            self.admittances_ = self.get_admittance_matrices()

        return self.admittances_.Ybus.tocsc()

    @property
    def Yf(self):
        """
        Admittance matrix of the "from" nodes with the Branches
        :return: CSC matrix
        """
        if self.admittances_ is None:
            self.admittances_ = self.get_admittance_matrices()

        return self.admittances_.Yf

    @property
    def Yt(self):
        """
        Admittance matrix of the "to" nodes with the Branches
        :return: CSC matrix
        """
        if self.admittances_ is None:
            self.admittances_ = self.get_admittance_matrices()

        return self.admittances_.Yt

    @property
    def Yseries(self):
        """
        Admittance matrix of the series elements of the pi model of the Branches
        :return: CSC matrix
        """
        # compute admittances on demand
        if self.series_admittances_ is None:
            self.series_admittances_ = self.get_series_admittance_matrices()

        return self.series_admittances_.Yseries

    @property
    def Yshunt(self):
        """
        Array of shunt admittances of the pi model of the Branches (used in HELM mostly)
        :return: Array of complex values
        """
        if self.series_admittances_ is None:
            self.series_admittances_ = self.get_series_admittance_matrices()

        return self.series_admittances_.Yshunt

    @property
    def B1(self):
        """
        B' matrix of the fast decoupled method
        :return:
        """
        if self.fast_decoupled_admittances_ is None:
            self.fast_decoupled_admittances_ = self.get_fast_decoupled_amittances()

        return self.fast_decoupled_admittances_.B1

    @property
    def B2(self):
        """
        B'' matrix of the fast decoupled method
        :return:
        """
        if self.fast_decoupled_admittances_ is None:
            self.fast_decoupled_admittances_ = self.get_fast_decoupled_amittances()

        return self.fast_decoupled_admittances_.B2

    @property
    def Bbus(self):
        """
        Susceptance matrix for the linear methods
        :return:
        """
        if self.linear_admittances_ is None:
            self.linear_admittances_ = self.get_linear_admittance_matrices()

        return self.linear_admittances_.Bbus

    @property
    def Bf(self):
        """
        Susceptance matrix of the "from" nodes to the Branches
        :return:
        """
        if self.linear_admittances_ is None:
            self.linear_admittances_ = self.get_linear_admittance_matrices()

        return self.linear_admittances_.Bf

    @property
    def Bpqpv(self):
        """

        :return:
        """
        if self.linear_admittances_ is None:
            self.linear_admittances_ = self.get_linear_admittance_matrices()

        return self.linear_admittances_.get_Bred(pqpv=self.pqpv)

    @property
    def Bref(self):
        """

        :return:
        """
        if self.linear_admittances_ is None:
            self.linear_admittances_ = self.get_linear_admittance_matrices()

        return self.linear_admittances_.get_Bslack(pqpv=self.pqpv, vd=self.vd)

    @property
    def vd(self):
        """

        :return:
        """
        if self.simulation_indices_ is None:
            self.simulation_indices_ = self.get_simulation_indices()

        return self.simulation_indices_.vd

    @property
    def pq(self):
        """

        :return:
        """
        if self.simulation_indices_ is None:
            self.simulation_indices_ = self.get_simulation_indices()

        return self.simulation_indices_.pq

    @property
    def pv(self):
        """

        :return:
        """
        if self.simulation_indices_ is None:
            self.simulation_indices_ = self.get_simulation_indices()

        return self.simulation_indices_.pv

    @property
    def pqv(self):
        """

        :return:
        """
        if self.simulation_indices_ is None:
            self.simulation_indices_ = self.get_simulation_indices()

        return self.simulation_indices_.pqv

    @property
    def p(self):
        """

        :return:
        """
        if self.simulation_indices_ is None:
            self.simulation_indices_ = self.get_simulation_indices()

        return self.simulation_indices_.p

    @property
    def pqpv(self):
        """

        :return:
        """
        # TODO: rename to "no_slack"
        if self.simulation_indices_ is None:
            self.simulation_indices_ = self.get_simulation_indices()

        return self.simulation_indices_.no_slack

    @property
    def any_control(self):
        """

        :return:
        """
        return self.branch_data._any_pf_control

    @property
    def k_pf_tau(self):
        """
        Get k_pf_tau
        :return:
        """
        if self.simulation_indices_ is None:
            self.simulation_indices_ = self.get_simulation_indices()

        return self.simulation_indices_.k_pf_tau

    @property
    def k_qf_beq(self):
        """
        Get k_qf_beq
        :return:
        """
        if self.simulation_indices_ is None:
            self.simulation_indices_ = self.get_simulation_indices()

        return self.simulation_indices_.k_qf_beq

    @property
    def k_v_m(self):
        """
        Get k_v_m
        :return:
        """
        if self.simulation_indices_ is None:
            self.simulation_indices_ = self.get_simulation_indices()

        return self.simulation_indices_.k_v_m

    @property
    def k_m(self):
        """
        Get k_m
        :return:
        """
        if self.simulation_indices_ is None:
            self.simulation_indices_ = self.get_simulation_indices()

        return self.simulation_indices_.k_m

    @property
    def k_tau(self):
        """
        Get k_tau
        :return:
        """
        if self.simulation_indices_ is None:
            self.simulation_indices_ = self.get_simulation_indices()

        return self.simulation_indices_.k_tau

    @property
    def k_mtau(self):
        """
        Get k_mtau
        :return:
        """
        if self.simulation_indices_ is None:
            self.simulation_indices_ = self.get_simulation_indices()

        return self.simulation_indices_.k_mtau

    @property
    def structs_dict(self):
        """

        :return:
        """
        if self.structs_dict_ is None:
            self.structs_dict_ = self.get_structs_idtag_dict()

        return self.structs_dict_

    def compute_reactive_power_limits(self) -> Tuple[Vec, Vec]:
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

    def get_inter_areas_branches(self, buses_areas_1, buses_areas_2):
        """
        Get the Branches that join two areas
        :param buses_areas_1: Area from
        :param buses_areas_2: Area to
        :return: List of (branch index, branch object, flow sense w.r.t the area exchange)
        """
        return get_inter_areas_branch(self.branch_data.F, self.branch_data.T, buses_areas_1, buses_areas_2)

    def get_inter_areas_hvdc(self, buses_areas_1, buses_areas_2):
        """
        Get the Branches that join two areas
        :param buses_areas_1: Area from
        :param buses_areas_2: Area to
        :return: List of (branch index, branch object, flow sense w.r.t the area exchange)
        """
        F = self.hvdc_data.get_bus_indices_f()
        T = self.hvdc_data.get_bus_indices_t()
        return get_inter_areas_branch(F, T, buses_areas_1, buses_areas_2)

    def get_generators_per_areas(self, buses_in_a1, buses_in_a2):
        """
        Get the generators that belong to the Area 1, Area 2 and the rest of areas
        :param buses_in_a1: List of bus indices of the area 1
        :param buses_in_a2: List of bus indices of the area 2
        :return: Tree lists: (gens_in_a1, gens_in_a2, gens_out)
                 each of the lists contains (bus index, generator index) tuples
        """
        if isinstance(self.generator_data.C_bus_elm, sp.csc_matrix):
            Cgen = self.generator_data.C_bus_elm
        else:
            Cgen = self.generator_data.C_bus_elm.tocsc()

        return get_devices_per_areas(Cgen, buses_in_a1, buses_in_a2)

    def get_batteries_per_areas(self, buses_in_a1, buses_in_a2):
        """
        Get the batteries that belong to the Area 1, Area 2 and the rest of areas
        :param buses_in_a1: List of bus indices of the area 1
        :param buses_in_a2: List of bus indices of the area 2
        :return: Tree lists: (batteries_in_a1, batteries_in_a2, batteries_out)
                 each of the lists contains (bus index, generator index) tuples
        """
        if isinstance(self.battery_data.C_bus_elm, sp.csc_matrix):
            Cgen = self.battery_data.C_bus_elm
        else:
            Cgen = self.battery_data.C_bus_elm.tocsc()

        return get_devices_per_areas(Cgen, buses_in_a1, buses_in_a2)

    def compute_adjacency_matrix(self, consider_hvdc_as_island_links: bool = False) -> sp.csc_matrix:
        """
        Compute the adjacency matrix
        :param consider_hvdc_as_island_links: Does the HVDCLine works for the topology as a normal line?
        :return: csc_matrix
        """

        if consider_hvdc_as_island_links:
            conn_matrices = tp.compute_connectivity_with_hvdc(
                branch_active=self.branch_data.active,
                Cf_=self.branch_data.C_branch_bus_f.tocsc(),
                Ct_=self.branch_data.C_branch_bus_t.tocsc(),
                hvdc_active=self.hvdc_data.active,
                Cf_hvdc=self.hvdc_data.C_hvdc_bus_f.tocsc(),
                Ct_hvdc=self.hvdc_data.C_hvdc_bus_t.tocsc()
            )

            # compute the adjacency matrix
            return tp.get_adjacency_matrix(
                C_branch_bus_f=conn_matrices.Cf,
                C_branch_bus_t=conn_matrices.Ct,
                branch_active=np.r_[self.branch_data.active, self.hvdc_data.active],
                bus_active=self.bus_data.active
            )
        else:

            # compute the adjacency matrix
            return tp.get_adjacency_matrix(
                C_branch_bus_f=self.Cf,
                C_branch_bus_t=self.Ct,
                branch_active=self.branch_data.active,
                bus_active=self.bus_data.active
            )

    def get_structure(self, structure_type: str) -> pd.DataFrame:
        """
        Get a DataFrame with the input.
        :param: structure_type: String representing structure type
        :return: pandas DataFrame
        """

        if self.simulation_indices_ is None:
            self.simulation_indices_ = self.get_simulation_indices()

        # idx_dm = np.r_[self.simulation_indices_.k_v_m, self.simulation_indices_.k_qf_m, self.simulation_indices_.k_qt_m]
        # idx_dtau = np.r_[self.simulation_indices_.k_pf_tau, self.simulation_indices_.k_pt_tau]
        # idx_dbeq = self.simulation_indices_.k_qf_beq
        # idx_dPf = self.simulation_indices_.k_pf_tau
        # idx_dQf = np.r_[self.simulation_indices_.k_qf_m, self.simulation_indices_.k_qf_beq]
        # idx_dPt = self.simulation_indices_.k_pt_tau
        # idx_dQt = self.simulation_indices_.k_qt_m

        from GridCalEngine.Simulations.PowerFlow.Formulations.pf_advanced_formulation import (
            PfAdvancedFormulation)
        from GridCalEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions

        formulation = PfAdvancedFormulation(V0=self.Vbus,
                                            S0=self.Sbus,
                                            I0=self.Ibus,
                                            Y0=self.YLoadBus,
                                            Qmin=self.Qmin_bus,
                                            Qmax=self.Qmax_bus,
                                            nc=self,
                                            options=PowerFlowOptions(),
                                            logger=Logger())

        if structure_type == 'V':
            df = pd.DataFrame(
                data=self.Vbus,
                columns=['Voltage (p.u.)'],
                index=self.bus_data.names,
            )

        elif structure_type == 'Va':
            df = pd.DataFrame(
                data=np.angle(self.Vbus),
                columns=['Voltage angles (rad)'],
                index=self.bus_data.names,
            )
        elif structure_type == 'Vm':
            df = pd.DataFrame(
                data=np.abs(self.Vbus),
                columns=['Voltage modules (p.u.)'],
                index=self.bus_data.names,
            )
        elif structure_type == 'S':
            df = pd.DataFrame(
                data=self.Sbus,
                columns=['Power (p.u.)'],
                index=self.bus_data.names,
            )

        elif structure_type == 'P':
            df = pd.DataFrame(
                data=self.Sbus.real,
                columns=['Power (p.u.)'],
                index=self.bus_data.names,
            )

        elif structure_type == 'Q':
            df = pd.DataFrame(
                data=self.Sbus.imag,
                columns=['Power (p.u.)'],
                index=self.bus_data.names,
            )

        elif structure_type == 'I':
            df = pd.DataFrame(
                data=self.Ibus,
                columns=['Current (p.u.)'],
                index=self.bus_data.names,
            )

        elif structure_type == 'Y':
            df = pd.DataFrame(
                data=self.YLoadBus,
                columns=['Admittance (p.u.)'],
                index=self.bus_data.names,
            )

        elif structure_type == 'Ybus':
            df = pd.DataFrame(
                data=self.Ybus.toarray(),
                columns=self.bus_data.names,
                index=self.bus_data.names,
            )

        elif structure_type == 'G':
            df = pd.DataFrame(
                data=self.Ybus.real.toarray(),
                columns=self.bus_data.names,
                index=self.bus_data.names,
            )

        elif structure_type == 'B':
            df = pd.DataFrame(
                data=self.Ybus.imag.toarray(),
                columns=self.bus_data.names,
                index=self.bus_data.names,
            )

        elif structure_type == 'Yf':
            df = pd.DataFrame(
                data=self.Yf.toarray(),
                columns=self.bus_data.names,
                index=self.branch_data.names,
            )

        elif structure_type == 'Yt':
            df = pd.DataFrame(
                data=self.Yt.toarray(),
                columns=self.bus_data.names,
                index=self.branch_data.names,
            )

        elif structure_type == 'Bbus':
            df = pd.DataFrame(
                data=self.Bbus.toarray(),
                columns=self.bus_data.names,
                index=self.bus_data.names,
            )

        elif structure_type == 'Bf':
            df = pd.DataFrame(
                data=self.Bf.toarray(),
                columns=self.bus_data.names,
                index=self.branch_data.names,
            )

        elif structure_type == 'Cf':
            df = pd.DataFrame(
                data=self.Cf.toarray(),
                columns=self.bus_data.names,
                index=self.branch_data.names,
            )

        elif structure_type == 'Ct':
            df = pd.DataFrame(
                data=self.Ct.toarray(),
                columns=self.bus_data.names,
                index=self.branch_data.names,
            )

        elif structure_type == 'Yshunt':
            df = pd.DataFrame(
                data=self.Yshunt,
                columns=['Shunt admittance (p.u.)'],
                index=self.bus_data.names,
            )

        elif structure_type == 'Yseries':
            df = pd.DataFrame(
                data=self.Yseries.toarray(),
                columns=self.bus_data.names,
                index=self.bus_data.names,
            )

        elif structure_type == "B'":

            if self.B1.shape[0] == len(self.pqpv):
                data = self.B1.toarray()
                names = self.bus_names[self.pqpv]
            else:
                data = self.B1[np.ix_(self.pqpv, self.pqpv)].toarray()
                names = self.bus_names[self.pqpv]

            df = pd.DataFrame(
                data=data,
                columns=names,
                index=names,
            )

        elif structure_type == "B''":
            if self.B2.shape[0] == len(self.pq):
                data = self.B2.toarray()
                names = self.bus_names[self.pq]
            else:
                data = self.B2[np.ix_(self.pq, self.pq)].toarray()
                names = self.bus_names[self.pq]

            df = pd.DataFrame(
                data=data,
                columns=names,
                index=names,
            )

        elif structure_type == 'Types':
            data = self.bus_types
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
                data=self.Qmin_bus,
                columns=['Qmin'],
                index=self.bus_data.names,
            )

        elif structure_type == 'Qmax':
            df = pd.DataFrame(
                data=self.Qmax_bus,
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

            data1 = [val.value if val != 0 else "-" for val in self.branch_data.tap_module_control_mode]
            data2 = [val.value if val != 0 else "-" for val in self.branch_data.tap_phase_control_mode]

            df = pd.DataFrame(
                data=np.c_[
                    self.branch_data.F,
                    self.branch_data.T,
                    self.branch_data.tap_controlled_buses,
                    data1,
                    data2
                ],
                columns=['bus F', 'bus T', 'V ctrl bus', 'm control', 'tau control'],
                index=[f"{k}) {name}" for k, name in enumerate(self.branch_data.names)],
            )

        elif structure_type == 'pq':
            df = pd.DataFrame(
                data=self.pq.astype(int).astype(str),
                columns=['pq'],
                index=self.bus_data.names[self.pq],
            )

        elif structure_type == 'pv':
            df = pd.DataFrame(
                data=self.pv.astype(int).astype(str),
                columns=['pv'],
                index=self.bus_data.names[self.pv],
            )

        elif structure_type == 'pqv':
            df = pd.DataFrame(
                data=self.pqv.astype(int).astype(str),
                columns=['pqv'],
                index=self.bus_data.names[self.pqv],
            )

        elif structure_type == 'p':
            df = pd.DataFrame(
                data=self.p.astype(int).astype(str),
                columns=['p'],
                index=self.bus_data.names[self.p],
            )

        elif structure_type == 'vd':
            df = pd.DataFrame(
                data=self.vd.astype(int).astype(str),
                columns=['vd'],
                index=self.bus_data.names[self.vd],
            )

        elif structure_type == 'pqpv':
            df = pd.DataFrame(
                data=self.pqpv.astype(int).astype(str),
                columns=['pqpv'],
                index=self.bus_data.names[self.pqpv],
            )

        elif structure_type == 'tap_f':
            df = pd.DataFrame(
                data=self.branch_data.virtual_tap_f,
                columns=['Virtual tap from (p.u.)'],
                index=self.branch_data.names,
            )

        elif structure_type == 'tap_t':
            df = pd.DataFrame(
                data=self.branch_data.virtual_tap_t,
                columns=['Virtual tap to (p.u.)'],
                index=self.branch_data.names,
            )

        elif structure_type == 'k_pf_tau':
            df = pd.DataFrame(
                data=self.simulation_indices_.k_pf_tau.astype(int).astype(str),
                columns=['k_pf_tau'],
                index=self.branch_data.names[self.simulation_indices_.k_pf_tau],
            )

        elif structure_type == 'k_pt_tau':
            df = pd.DataFrame(
                data=self.simulation_indices_.k_pt_tau.astype(int).astype(str),
                columns=['k_pt_tau'],
                index=self.branch_data.names[self.simulation_indices_.k_pt_tau],
            )

        elif structure_type == 'k_qf_m':
            df = pd.DataFrame(
                data=self.simulation_indices_.k_qf_m.astype(int).astype(str),
                columns=['k_qf_m'],
                index=self.branch_data.names[self.simulation_indices_.k_qf_m],
            )

        elif structure_type == 'k_qt_m':
            df = pd.DataFrame(
                data=self.simulation_indices_.k_qt_m.astype(int).astype(str),
                columns=['k_qt_m'],
                index=self.branch_data.names[self.simulation_indices_.k_qt_m],
            )

        elif structure_type == 'k_qf_beq':
            df = pd.DataFrame(
                data=self.simulation_indices_.k_qf_beq.astype(int).astype(str),
                columns=['k_qf_beq'],
                index=self.branch_data.names[self.simulation_indices_.k_qf_beq],
            )

        elif structure_type == 'k_v_m':
            df = pd.DataFrame(
                data=self.simulation_indices_.k_v_m.astype(int).astype(str),
                columns=['k_v_m'],
                index=self.branch_data.names[self.simulation_indices_.k_v_m],
            )
        elif structure_type == 'k_v_beq':
            df = pd.DataFrame(
                data=self.simulation_indices_.k_v_beq.astype(int).astype(str),
                columns=['k_v_beq'],
                index=self.branch_data.names[self.simulation_indices_.k_v_beq],
            )
        elif structure_type == 'idx_dPf':
            df = pd.DataFrame(
                data=formulation.idx_dPf.astype(int).astype(str),
                columns=['idx_dPf'],
                index=self.branch_data.names[formulation.idx_dPf],
            )

        elif structure_type == 'idx_dQf':
            df = pd.DataFrame(
                data=formulation.idx_dQf.astype(int).astype(str),
                columns=['idx_dQf'],
                index=self.branch_data.names[formulation.idx_dQf],
            )

        elif structure_type == 'idx_dPt':
            df = pd.DataFrame(
                data=formulation.idx_dPt.astype(int).astype(str),
                columns=['idx_dPt'],
                index=self.branch_data.names[formulation.idx_dPt],
            )

        elif structure_type == 'idx_dQt':
            df = pd.DataFrame(
                data=formulation.idx_dQt.astype(int).astype(str),
                columns=['idx_dQt'],
                index=self.branch_data.names[formulation.idx_dQt],
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
                index=self.branch_data.names[formulation.idx_dm],
            )

        elif structure_type == 'idx_dtau':
            df = pd.DataFrame(
                data=formulation.idx_dtau.astype(int).astype(str),
                columns=['idx_dtau'],
                index=self.branch_data.names[formulation.idx_dtau],
            )

        elif structure_type == 'idx_dbeq':
            df = pd.DataFrame(
                data=formulation.idx_dbeq.astype(int).astype(str),
                columns=['idx_dbeq'],
                index=self.branch_data.names[formulation.idx_dbeq],
            )

        elif structure_type == 'Pf_set':
            df = pd.DataFrame(
                data=self.branch_data.Pset[formulation.idx_dPf],
                columns=['Pf_set'],
                index=self.branch_data.names[formulation.idx_dPf],
            )

        elif structure_type == 'Pt_set':
            df = pd.DataFrame(
                data=self.branch_data.Pset[formulation.idx_dPt],
                columns=['Pt_set'],
                index=self.branch_data.names[formulation.idx_dPt],
            )

        elif structure_type == 'Qf_set':
            df = pd.DataFrame(
                data=self.branch_data.Qset[formulation.idx_dQf],
                columns=['Qf_set'],
                index=self.branch_data.names[formulation.idx_dQf],
            )

        elif structure_type == 'Qt_set':
            df = pd.DataFrame(
                data=self.branch_data.Qset[formulation.idx_dQt],
                columns=['Qt_set'],
                index=self.branch_data.names[formulation.idx_dQt],
            )

        else:
            raise Exception('PF input: structure type not found' + str(structure_type))

        return df

    def get_island(self, bus_idx: IntVec,
                   consider_hvdc_as_island_links: bool = False,
                   logger: Logger | None = None) -> "NumericalCircuit":
        """
        Get the island corresponding to the given buses
        :param bus_idx: array of bus indices
        :param consider_hvdc_as_island_links: Does the HVDCLine works for the topology as a normal line?
        :param logger: Logger
        :return: SnapshotData
        """
        if logger is None:
            logger = Logger()

        # if the island is the same as the original bus indices, no slicing is needed
        if len(bus_idx) == len(self.bus_data.original_idx):
            if np.all(bus_idx == self.bus_data.original_idx):
                return self

        # find the indices of the devices of the island
        br_idx = self.branch_data.get_island(bus_idx)
        hvdc_idx = self.hvdc_data.get_island(bus_idx)

        load_idx = self.load_data.get_island(bus_idx)
        gen_idx = self.generator_data.get_island(bus_idx)
        batt_idx = self.battery_data.get_island(bus_idx)
        shunt_idx = self.shunt_data.get_island(bus_idx)

        nc = NumericalCircuit(
            nbus=len(bus_idx),
            nbr=len(br_idx),
            nhvdc=len(hvdc_idx),
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
        nc.branch_data = self.branch_data.slice(elm_idx=br_idx, bus_idx=bus_idx, logger=logger)

        nc.load_data = self.load_data.slice(elm_idx=load_idx, bus_idx=bus_idx)
        nc.battery_data = self.battery_data.slice(elm_idx=batt_idx, bus_idx=bus_idx)
        nc.generator_data = self.generator_data.slice(elm_idx=gen_idx, bus_idx=bus_idx)
        nc.shunt_data = self.shunt_data.slice(elm_idx=shunt_idx, bus_idx=bus_idx)

        # HVDC data does not propagate into islands
        if consider_hvdc_as_island_links:
            nc.hvdc_data = self.hvdc_data.slice(elm_idx=hvdc_idx, bus_idx=bus_idx)

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

        # find the matching islands
        adj = self.compute_adjacency_matrix(consider_hvdc_as_island_links=consider_hvdc_as_island_links)
        idx_islands = tp.find_islands(adj=adj, active=self.bus_data.active)

        circuit_islands = list()  # type: List[NumericalCircuit]

        for bus_idx in idx_islands:
            if ignore_single_node_islands:
                if len(bus_idx) > 1:
                    island = self.get_island(bus_idx,
                                             consider_hvdc_as_island_links=consider_hvdc_as_island_links,
                                             logger=logger)
                    circuit_islands.append(island)
            else:
                island = self.get_island(bus_idx,
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

        CheckArr(self.branch_data.F, nc_2.branch_data.F, tol, 'BranchData', 'F', logger)
        CheckArr(self.branch_data.T, nc_2.branch_data.T, tol, 'BranchData', 'T', logger)
        CheckArr(self.branch_data.active, nc_2.branch_data.active, tol,
                 'BranchData', 'active', logger)
        CheckArr(self.branch_data.R, nc_2.branch_data.R, tol, 'BranchData', 'r', logger)
        CheckArr(self.branch_data.X, nc_2.branch_data.X, tol, 'BranchData', 'x', logger)
        CheckArr(self.branch_data.G, nc_2.branch_data.G, tol, 'BranchData', 'g', logger)
        CheckArr(self.branch_data.B, nc_2.branch_data.B, tol, 'BranchData', 'b', logger)
        CheckArr(self.branch_data.rates, nc_2.branch_data.rates, tol, 'BranchData',
                 'rates', logger)
        CheckArr(self.branch_data.tap_module, nc_2.branch_data.tap_module, tol,
                 'BranchData', 'tap_module', logger)
        CheckArr(self.branch_data.tap_angle, nc_2.branch_data.tap_angle, tol,
                 'BranchData', 'tap_angle', logger)

        CheckArr(self.branch_data.G0, nc_2.branch_data.G0, tol, 'BranchData', 'g0', logger)

        CheckArr(self.branch_data.virtual_tap_f, nc_2.branch_data.virtual_tap_f,
                 tol, 'BranchData', 'vtap_f', logger)
        CheckArr(self.branch_data.virtual_tap_t, nc_2.branch_data.virtual_tap_t,
                 tol, 'BranchData', 'vtap_t', logger)

        # bus data
        CheckArr(self.bus_data.active, nc_2.bus_data.active, tol, 'BusData',
                 'active', logger)
        CheckArr(self.bus_data.Vbus.real, nc_2.bus_data.Vbus.real, tol, 'BusData',
                 'V0', logger)
        CheckArr(self.bus_data.installed_power, nc_2.bus_data.installed_power, tol,
                 'BusData', 'installed power', logger)
        CheckArr(self.bus_data.bus_types, nc_2.bus_data.bus_types, tol, 'BusData',
                 'types', logger)

        # generator data
        CheckArr(self.generator_data.active, nc_2.generator_data.active, tol,
                 'GenData', 'active', logger)
        CheckArr(self.generator_data.p, nc_2.generator_data.p, tol, 'GenData', 'P', logger)
        # CheckArr(nc_newton.generator_data.generator_pf, nc_gc.generator_data.generator_pf, tol, 'GenData', 'Pf')
        CheckArr(self.generator_data.v, nc_2.generator_data.v, tol, 'GenData',
                 'Vset', logger)
        CheckArr(self.generator_data.qmin, nc_2.generator_data.qmin, tol,
                 'GenData', 'Qmin', logger)
        CheckArr(self.generator_data.qmax, nc_2.generator_data.qmax, tol,
                 'GenData', 'Qmax', logger)

        # load data
        CheckArr(self.load_data.active, nc_2.load_data.active, tol, 'LoadData',
                 'active', logger)
        CheckArr(self.load_data.S, nc_2.load_data.S, tol, 'LoadData', 'S', logger)
        CheckArr(self.load_data.I, nc_2.load_data.I, tol, 'LoadData', 'I', logger)
        CheckArr(self.load_data.Y, nc_2.load_data.Y, tol, 'LoadData', 'Y', logger)

        # shunt
        CheckArr(self.shunt_data.active, nc_2.shunt_data.active, tol, 'ShuntData',
                 'active', logger)
        CheckArr(self.shunt_data.Y, nc_2.shunt_data.Y, tol,
                 'ShuntData', 'S', logger)
        CheckArr(self.shunt_data.get_injections_per_bus(),
                 nc_2.shunt_data.get_injections_per_bus(), tol, 'ShuntData',
                 'Injections per bus', logger)

        # --------------------------------------------------------------------------------------------------------------
        #  Compare arrays and data
        # --------------------------------------------------------------------------------------------------------------

        CheckArr(self.Sbus.real, nc_2.Sbus.real, tol, 'Pbus', 'P', logger)
        CheckArr(self.Sbus.imag, nc_2.Sbus.imag, tol, 'Qbus', 'Q', logger)

        CheckArr(self.pq, nc_2.pq, tol, 'Types', 'pq', logger)
        CheckArr(self.pv, nc_2.pv, tol, 'Types', 'pv', logger)
        CheckArr(self.vd, nc_2.vd, tol, 'Types', 'vd', logger)

        CheckArr(self.Cf.toarray(), nc_2.Cf.toarray(), tol, 'Connectivity',
                 'Cf (dense)', logger)
        CheckArr(self.Ct.toarray(), nc_2.Ct.toarray(), tol, 'Connectivity',
                 'Ct (dense)', logger)
        CheckArr(self.Cf.tocsc().data, nc_2.Cf.tocsc().data, tol, 'Connectivity',
                 'Cf', logger)
        CheckArr(self.Ct.tocsc().data, nc_2.Ct.tocsc().data, tol, 'Connectivity',
                 'Ct', logger)

        CheckArr(self.Ybus.toarray(), nc_2.Ybus.toarray(), tol, 'Admittances',
                 'Ybus (dense)', logger)
        CheckArr(self.Ybus.tocsc().data.real, nc_2.Ybus.tocsc().data.real, tol,
                 'Admittances', 'Ybus (real)', logger)
        CheckArr(self.Ybus.tocsc().data.imag, nc_2.Ybus.tocsc().data.imag, tol,
                 'Admittances', 'Ybus (imag)', logger)
        CheckArr(self.Yf.tocsc().data.real, nc_2.Yf.tocsc().data.real,
                 tol, 'Admittances', 'Yf (real)', logger)
        CheckArr(self.Yf.tocsc().data.imag, nc_2.Yf.tocsc().data.imag, tol,
                 'Admittances', 'Yf (imag)', logger)
        CheckArr(self.Yt.tocsc().data.real, nc_2.Yt.tocsc().data.real, tol,
                 'Admittances', 'Yt (real)', logger)
        CheckArr(self.Yt.tocsc().data.imag, nc_2.Yt.tocsc().data.imag, tol,
                 'Admittances', 'Yt (imag)', logger)

        CheckArr(self.Vbus, nc_2.Vbus, tol, 'NumericCircuit', 'V0', logger)

        # if any error in the logger, bad
        return logger.error_count() == 0, logger

    def get_structural_ntc(self, bus_a1_idx: IntVec, bus_a2_idx: IntVec) -> float:
        """
        Get the structural NTC
        :param bus_a1_idx: list of buses of the area from
        :param bus_a2_idx: list of buses of the area to
        :return: structural NTC in MVA
        """

        inter_area_branches = self.branch_data.get_inter_areas(bus_idx_from=bus_a1_idx, bus_idx_to=bus_a2_idx)
        sum_ratings = 0.0
        for k, sense in inter_area_branches:
            sum_ratings += self.branch_data.rates[k]

        inter_area_hvdcs = self.hvdc_data.get_inter_areas(bus_idx_from=bus_a1_idx, bus_idx_to=bus_a2_idx)
        for k, sense in inter_area_hvdcs:
            sum_ratings += self.hvdc_data.rate[k]

        return sum_ratings


def compile_numerical_circuit_at(circuit: MultiCircuit,
                                 t_idx: Union[int, None] = None,
                                 apply_temperature=False,
                                 branch_tolerance_mode=BranchImpedanceMode.Specified,
                                 opf_results: gc_compiler2.VALID_OPF_RESULTS | None = None,
                                 use_stored_guess=False,
                                 bus_dict: Union[Dict[Bus, int], None] = None,
                                 areas_dict: Union[Dict[Area, int], None] = None,
                                 control_taps_modules: bool = True,
                                 control_taps_phase: bool = True,
                                 control_remote_voltage: bool = True,
                                 logger=Logger()) -> NumericalCircuit:
    """
    Compile a NumericalCircuit from a MultiCircuit
    :param circuit: MultiCircuit instance
    :param t_idx: time step from the time series to gather data from, if None the snapshot is used
    :param apply_temperature: apply the branch temperature correction
    :param branch_tolerance_mode: Branch tolerance mode
    :param opf_results:(optional) OptimalPowerFlowResults instance
    :param use_stored_guess: use the storage voltage guess?
    :param bus_dict (optional) Dict[Bus, int] dictionary
    :param areas_dict (optional) Dict[Area, int] dictionary
    :param control_taps_modules: control taps modules?
    :param control_taps_phase: control taps phase?
    :param control_remote_voltage: control remote voltage?
    :param logger: Logger instance
    :return: NumericalCircuit instance
    """

    if circuit.get_connectivity_nodes_number() + circuit.get_switches_number():
        # process topology, this
        circuit.process_topology_at(t_idx=t_idx, logger=logger)

    # if any valid time index is specified, then the data is compiled from the time series
    time_series = t_idx is not None

    bus_voltage_used = np.zeros(circuit.get_bus_number(), dtype=bool)

    # declare the numerical circuit
    nc = NumericalCircuit(
        nbus=0,
        nbr=0,
        nhvdc=0,
        nload=0,
        ngen=0,
        nbatt=0,
        nshunt=0,
        nfluidnode=0,
        nfluidturbine=0,
        nfluidpump=0,
        nfluidp2x=0,
        nfluidpath=0,
        sbase=circuit.Sbase,
        t_idx=t_idx
    )

    if bus_dict is None:
        bus_dict = {bus: i for i, bus in enumerate(circuit.buses)}

    if areas_dict is None:
        areas_dict = {elm: i for i, elm in enumerate(circuit.areas)}

    nc.bus_data = gc_compiler2.get_bus_data(
        circuit=circuit,
        t_idx=t_idx,
        time_series=time_series,
        areas_dict=areas_dict,
        use_stored_guess=use_stored_guess
    )

    nc.generator_data, gen_dict = gc_compiler2.get_generator_data(
        circuit=circuit,
        bus_dict=bus_dict,
        bus_data=nc.bus_data,
        t_idx=t_idx,
        time_series=time_series,
        bus_voltage_used=bus_voltage_used,
        logger=logger,
        opf_results=opf_results,
        use_stored_guess=use_stored_guess,
        control_remote_voltage=control_remote_voltage
    )

    nc.battery_data = gc_compiler2.get_battery_data(
        circuit=circuit,
        bus_dict=bus_dict,
        bus_data=nc.bus_data,
        t_idx=t_idx,
        time_series=time_series,
        bus_voltage_used=bus_voltage_used,
        logger=logger,
        opf_results=opf_results,
        use_stored_guess=use_stored_guess,
        control_remote_voltage=control_remote_voltage
    )

    nc.shunt_data = gc_compiler2.get_shunt_data(
        circuit=circuit,
        bus_dict=bus_dict,
        bus_voltage_used=bus_voltage_used,
        bus_data=nc.bus_data,
        t_idx=t_idx,
        time_series=time_series,
        logger=logger,
        use_stored_guess=use_stored_guess,
        control_remote_voltage=control_remote_voltage
    )

    nc.load_data = gc_compiler2.get_load_data(
        circuit=circuit,
        bus_dict=bus_dict,
        bus_voltage_used=bus_voltage_used,
        bus_data=nc.bus_data,
        logger=logger,
        t_idx=t_idx,
        time_series=time_series,
        opf_results=opf_results,
        use_stored_guess=use_stored_guess
    )

    nc.branch_data = gc_compiler2.get_branch_data(
        circuit=circuit,
        t_idx=t_idx,
        time_series=time_series,
        bus_dict=bus_dict,
        bus_data=nc.bus_data,
        bus_voltage_used=bus_voltage_used,
        apply_temperature=apply_temperature,
        branch_tolerance_mode=branch_tolerance_mode,
        opf_results=opf_results,
        use_stored_guess=use_stored_guess,
        control_taps_modules=control_taps_modules,
        control_taps_phase=control_taps_phase,
        control_remote_voltage=control_remote_voltage,
    )

    nc.hvdc_data = gc_compiler2.get_hvdc_data(
        circuit=circuit,
        t_idx=t_idx,
        time_series=time_series,
        bus_dict=bus_dict,
        bus_types=nc.bus_data.bus_types,
        bus_data=nc.bus_data,
        bus_voltage_used=bus_voltage_used,
        opf_results=opf_results,
        use_stored_guess=use_stored_guess,
        logger=logger
    )

    if len(circuit.fluid_nodes) > 0:
        nc.fluid_node_data, plant_dict = gc_compiler2.get_fluid_node_data(
            circuit=circuit,
            t_idx=t_idx,
            time_series=time_series
        )

        nc.fluid_turbine_data = gc_compiler2.get_fluid_turbine_data(
            circuit=circuit,
            plant_dict=plant_dict,
            gen_dict=gen_dict,
            t_idx=t_idx
        )

        nc.fluid_pump_data = gc_compiler2.get_fluid_pump_data(
            circuit=circuit,
            plant_dict=plant_dict,
            gen_dict=gen_dict,
            t_idx=t_idx
        )

        nc.fluid_p2x_data = gc_compiler2.get_fluid_p2x_data(
            circuit=circuit,
            plant_dict=plant_dict,
            gen_dict=gen_dict,
            t_idx=t_idx
        )

        nc.fluid_path_data = gc_compiler2.get_fluid_path_data(
            circuit=circuit,
            plant_dict=plant_dict,
            t_idx=t_idx
        )

    nc.consolidate_information()

    return nc
