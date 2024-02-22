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
from __future__ import annotations
import numpy as np
import pandas as pd
import scipy.sparse as sp
from typing import List, Tuple, Dict, Union, TYPE_CHECKING

from GridCalEngine.basic_structures import Logger
from GridCalEngine.Core.Devices.multi_circuit import MultiCircuit
from GridCalEngine.basic_structures import Vec, IntVec, CxVec
from GridCalEngine.enumerations import BranchImpedanceMode
import GridCalEngine.Core.Topology.topology as tp
import GridCalEngine.Core.Topology.simulation_indices as si

from GridCalEngine.Utils.NumericalMethods.sparse_solve import get_sparse_type
import GridCalEngine.Core.Compilers.circuit_to_data as gc_compiler2
import GridCalEngine.Core.Topology.admittance_matrices as ycalc
import GridCalEngine.Core.DataStructures as ds
from GridCalEngine.Core.Devices.Substation.bus import Bus
from GridCalEngine.Core.Devices.Aggregation.area import Area
from GridCalEngine.Core.Devices.Aggregation.investment import Investment
from GridCalEngine.Core.Devices.Aggregation.contingency import Contingency

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from GridCalEngine.Simulations.OPF.opf_results import OptimalPowerFlowResults

sparse_type = get_sparse_type()

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
    available_structures = [
        'Vbus',
        'Sbus',
        'Ibus',
        'Ybus',
        'G',
        'B',
        'Yf',
        'Yt',
        'Bbus',
        'Bf',
        'Cf',
        'Ct',
        'Yshunt',
        'Yseries',
        "B'",
        "B''",
        'Types',
        'Jacobian',
        'Qmin',
        'Qmax',
        'pq',
        'pv',
        'vd',
        'pqpv',
        'tap_f',
        'tap_t',
        'k_pf_tau',
        'k_qf_m',
        'k_zero_beq',
        'k_vf_beq',
        'k_vt_m',
        'k_qt_m',
        'k_pf_dp',
        'i_vsc',
        'i_vf_beq',
        'i_vt_m'
    ]

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

        self.Vbus_: CxVec = None
        self.Sbus_: CxVec = None
        self.Ibus_: CxVec = None
        self.YloadBus_: CxVec = None
        self.Yshunt_from_devices_: CxVec = None

        self.Qmax_bus_: Vec = None
        self.Qmin_bus_: Vec = None
        self.Bmax_bus_: Vec = None
        self.Bmin_bus_: Vec = None

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

    def reset_calculations(self):
        """
        This resets the lazy evaluation of the calculations like Ybus, Sbus, etc...
        If you want to use the NumericalCircuit as structure to modify stuff,
        this should be called after all modifications prior to the usage in any
        calculation
        """
        self.Vbus_: CxVec = None
        self.Sbus_: CxVec = None
        self.Ibus_: CxVec = None
        self.YloadBus_: CxVec = None
        self.Yshunt_from_devices_: CxVec = None

        self.Qmax_bus_: Vec = None
        self.Qmin_bus_: Vec = None
        self.Bmax_bus_: Vec = None
        self.Bmin_bus_: Vec = None

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

    def consolidate_information(self, use_stored_guess: bool = False) -> None:
        """
        Consolidates the information of this object
        :return:
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

        if not use_stored_guess:
            self.bus_data.Vbus = si.compose_generator_voltage_profile(
                nbus=self.nbus,
                gen_bus_indices=self.generator_data.get_bus_indices(),
                gen_vset=self.generator_data.v,
                gen_status=self.generator_data.active,
                gen_is_controlled=self.generator_data.controllable,
                bat_bus_indices=self.battery_data.get_bus_indices(),
                bat_vset=self.battery_data.v,
                bat_status=self.battery_data.active,
                bat_is_controlled=self.battery_data.controllable,
                hvdc_bus_f=self.hvdc_data.get_bus_indices_f(),
                hvdc_bus_t=self.hvdc_data.get_bus_indices_t(),
                hvdc_status=self.hvdc_data.active,
                hvdc_vf=self.hvdc_data.Vset_f,
                hvdc_vt=self.hvdc_data.Vset_t,
                k_vf_beq=self.k_vf_beq,
                i_vf_beq=self.i_vf_beq,
                k_vt_m=self.k_vt_m,
                i_vt_m=self.i_vt_m,
                branch_status=self.branch_data.active,
                br_vf=self.branch_data.vf_set,
                br_vt=self.branch_data.vt_set
            )

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

    def get_structures_list(self) -> List[Union[ds.BusData, ds.LoadData, ds.ShuntData,
    ds.GeneratorData, ds.BatteryData,
    ds.BranchData, ds.HvdcData,
    ds.FluidNodeData, ds.FluidTurbineData, ds.FluidPumpData,
    ds.FluidP2XData, ds.FluidPathData]]:
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
        structs_dict = dict()

        for struct_elm in self.get_structures_list():

            for i, idtag in enumerate(struct_elm.idtag):
                structs_dict[idtag] = (struct_elm, i)

        return structs_dict

    def set_investments_status(self, investments_list: List[Investment], status: int) -> None:
        """
        Set the status of a list of investmensts
        :param investments_list: list of investments
        :param status: status to set in the internal strctures
        """

        for inv in investments_list:

            # search the investment device
            structure, idx = self.structs_dict.get(inv.device_idtag, (None, 0))

            if structure is not None:
                structure.active[idx] = status
            else:
                raise Exception('Could not find the idtag, is this a programming bug?')

    def set_contingency_status(self, contingencies_list: List[Contingency], revert: bool = False):
        """
        Set the status of a list of contingencies
        :param contingencies_list: list of contingencies
        :param revert: if false, the contingencies are applied, else they are reversed
        """
        # apply the contingencies
        for cnt in contingencies_list:

            # search the investment device
            structure, idx = self.structs_dict.get(cnt.device_idtag, (None, 0))

            if structure is not None:
                if cnt.prop == 'active':
                    if revert:
                        structure.active[idx] = int(not bool(cnt.value))
                    else:
                        structure.active[idx] = int(cnt.value)
                elif cnt.prop == '%':
                    if revert:
                        structure.p[idx] /= float(cnt.value / 100.0)
                    else:
                        structure.p[idx] *= float(cnt.value / 100.0)
                else:
                    print(f'Unknown contingency property {cnt.prop} at {cnt.name} {cnt.idtag}')
            else:
                print(f'contingency device not found {cnt.name} {cnt.idtag}')

    def set_linear_contingency_status(self, contingencies_list: List[Contingency], revert: bool = False):
        """
        Set the status of a list of contingencies
        :param contingencies_list: list of contingencies
        :param revert: if false, the contingencies are applied, else they are reversed
        """
        injections = np.zeros(self.nbus)
        # apply the contingencies
        for cnt in contingencies_list:

            # search the investment device
            structure, idx = self.structs_dict.get(cnt.device_idtag, (None, 0))

            if structure is not None:
                if cnt.prop == 'active':
                    if revert:
                        structure.active[idx] = int(not bool(cnt.value))
                    else:
                        structure.active[idx] = int(cnt.value)
                elif cnt.prop == '%':
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
    def Bmax_bus(self):
        """

        :return:
        """
        if self.Bmax_bus_ is None:
            self.Bmax_bus_, self.Bmin_bus_ = self.compute_susceptance_limits()

        return self.Bmax_bus_

    @property
    def Bmin_bus(self):
        """

        :return:
        """
        if self.Bmin_bus_ is None:
            self.Bmax_bus_, self.Bmin_bus_ = self.compute_susceptance_limits()

        return self.Bmin_bus_

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
        Array of indices of the AC Branches
        :return: array of indices
        """
        if self.simulation_indices_ is None:
            self.simulation_indices_ = self.get_simulation_indices()

        return self.simulation_indices_.ac

    @property
    def dc_indices(self):
        """
        Array of indices of the DC Branches
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
        :return:
        """
        return si.SimulationIndices(bus_types=self.bus_data.bus_types,
                                    Pbus=self.Sbus.real,
                                    control_mode=self.branch_data.control_mode,
                                    F=self.branch_data.F,
                                    T=self.branch_data.T,
                                    dc=self.branch_data.dc
                                    )

    def get_connectivity_matrices(self) -> tp.ConnectivityMatrices:
        """
        Get connectivity matrices
        :return:
        """
        return tp.compute_connectivity(
            branch_active=self.branch_data.active,
            Cf_=self.branch_data.C_branch_bus_f,
            Ct_=self.branch_data.C_branch_bus_t
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
            G0sw=self.branch_data.G0sw,
            If=np.zeros(len(self.branch_data)),
            a=self.branch_data.a,
            b=self.branch_data.b,
            c=self.branch_data.c,
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
            a=self.branch_data.a,
            b=self.branch_data.b,
            c=self.branch_data.c,
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
            vtap_f=self.branch_data.vf_set,
            vtap_t=self.branch_data.vt_set,
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

        return self.admittances_.Ybus

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
        if self.simulation_indices_ is None:
            self.simulation_indices_ = self.get_simulation_indices()

        return self.simulation_indices_.any_control

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
    def k_qf_m(self):
        """
        Get k_qf_m
        :return:
        """
        if self.simulation_indices_ is None:
            self.simulation_indices_ = self.get_simulation_indices()

        return self.simulation_indices_.k_qf_m

    @property
    def k_zero_beq(self):
        """
        Get k_zero_beq
        :return:
        """
        if self.simulation_indices_ is None:
            self.simulation_indices_ = self.get_simulation_indices()

        return self.simulation_indices_.k_zero_beq

    @property
    def k_vf_beq(self):
        """
        Get k_vf_beq
        :return:
        """
        if self.simulation_indices_ is None:
            self.simulation_indices_ = self.get_simulation_indices()

        return self.simulation_indices_.k_vf_beq

    @property
    def k_vt_m(self):
        """
        Get k_vt_m
        :return:
        """
        if self.simulation_indices_ is None:
            self.simulation_indices_ = self.get_simulation_indices()

        return self.simulation_indices_.k_vt_m

    @property
    def k_qt_m(self):
        """
        Get k_qt_m
        :return:
        """
        if self.simulation_indices_ is None:
            self.simulation_indices_ = self.get_simulation_indices()

        return self.simulation_indices_.k_qt_m

    @property
    def k_pf_dp(self):
        """
        Get k_pf_dp
        :return:
        """
        if self.simulation_indices_ is None:
            self.simulation_indices_ = self.get_simulation_indices()

        return self.simulation_indices_.k_pf_dp

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
    def i_m(self):
        """
        Get i_m
        :return:
        """
        if self.simulation_indices_ is None:
            self.simulation_indices_ = self.get_simulation_indices()

        return self.simulation_indices_.i_m

    @property
    def i_tau(self):
        """
        Get i_tau
        :return:
        """
        if self.simulation_indices_ is None:
            self.simulation_indices_ = self.get_simulation_indices()

        return self.simulation_indices_.i_tau

    @property
    def i_mtau(self):
        """
        Get i_mtau
        :return:
        """
        if self.simulation_indices_ is None:
            self.simulation_indices_ = self.get_simulation_indices()

        return self.simulation_indices_.i_mtau

    @property
    def iPfdp_va(self):
        """
        Get iPfdp_va
        :return:
        """
        if self.simulation_indices_ is None:
            self.simulation_indices_ = self.get_simulation_indices()

        return self.simulation_indices_.iPfdp_va

    @property
    def i_vsc(self):
        """
        Get i_vsc
        :return:
        """
        if self.simulation_indices_ is None:
            self.simulation_indices_ = self.get_simulation_indices()

        return self.simulation_indices_.i_vsc

    @property
    def i_vf_beq(self):
        """
        Get i_vf_beq
        :return:
        """
        if self.simulation_indices_ is None:
            self.simulation_indices_ = self.get_simulation_indices()

        return self.simulation_indices_.i_vf_beq

    @property
    def i_vt_m(self):
        """
        Get i_vt_m
        :return:
        """
        if self.simulation_indices_ is None:
            self.simulation_indices_ = self.get_simulation_indices()

        return self.simulation_indices_.i_vt_m

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

        if self.nshunt > 0:
            # shunts
            Qmax_bus += self.shunt_data.get_b_max_per_bus()
            Qmin_bus += self.shunt_data.get_b_min_per_bus()

        if self.nhvdc > 0:
            # hvdc from
            Qmax_bus += self.hvdc_data.get_qmax_from_per_bus()
            Qmin_bus += self.hvdc_data.get_qmin_from_per_bus()

            # hvdc to
            Qmax_bus += self.hvdc_data.get_qmax_to_per_bus()
            Qmin_bus += self.hvdc_data.get_qmin_to_per_bus()

        # fix zero values
        Qmax_bus[Qmax_bus == 0] = 1e20
        Qmin_bus[Qmin_bus == 0] = -1e20

        return Qmax_bus / self.Sbase, Qmin_bus / self.Sbase

    def compute_susceptance_limits(self):
        """
        Compute susceptance limits
        :return:
        """
        Bmin = self.shunt_data.get_b_min_per_bus() / self.Sbase
        Bmax = self.shunt_data.get_b_max_per_bus() / self.Sbase

        return Bmax, Bmin

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

    def compute_adjacency_matrix(self) -> sp.csc_matrix:
        """
        Compute the adjacency matrix
        :return: csc_matrix
        """
        # compute the adjacency matrix
        return tp.get_adjacency_matrix(
            C_branch_bus_f=self.Cf,
            C_branch_bus_t=self.Ct,
            branch_active=self.branch_data.active,
            bus_active=self.bus_data.active
        )

    def get_structure(self, structure_type) -> pd.DataFrame:
        """
        Get a DataFrame with the input.
        :param: structure_type: String representig structure type
        :return: pandas DataFrame
        """

        if structure_type == 'Vbus':
            df = pd.DataFrame(
                data=self.Vbus,
                columns=['Voltage (p.u.)'],
                index=self.bus_data.names,
            )

        elif structure_type == 'Sbus':
            df = pd.DataFrame(
                data=self.Sbus,
                columns=['Power (p.u.)'],
                index=self.bus_data.names,
            )

        elif structure_type == 'Ibus':
            df = pd.DataFrame(
                data=self.Ibus,
                columns=['Current (p.u.)'],
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

        elif structure_type == 'Jacobian':

            from GridCalEngine.Simulations.PowerFlow.NumericalMethods.acdc_jacobian import fubm_jacobian

            pvpq = np.r_[self.pv, self.pq]

            cols = ['1) dVa {0}'.format(i) for i in pvpq]
            cols += ['2) dVm {0}'.format(i) for i in self.pq]
            cols += ['3) dPfsh {0}'.format(i) for i in self.k_pf_tau]
            cols += ['4) dQfma {0}'.format(i) for i in self.k_qf_m]
            cols += ['5) dBeqz {0}'.format(i) for i in self.k_zero_beq]
            cols += ['6) dBeqv {0}'.format(i) for i in self.k_vf_beq]
            cols += ['7) dVtma {0}'.format(i) for i in self.k_vt_m]
            cols += ['8) dQtma {0}'.format(i) for i in self.k_qt_m]
            cols += ['9) dPfdp {0}'.format(i) for i in self.k_pf_dp]

            rows = ['1) dP {0}'.format(i) for i in pvpq]
            rows += ['2) dQ {0}'.format(i) for i in self.pq]
            rows += ['3) dQ {0}'.format(i) for i in self.k_vf_beq]
            rows += ['4) dQ {0}'.format(i) for i in self.k_vt_m]
            rows += ['5) dPf {0}'.format(i) for i in self.k_pf_tau]
            rows += ['6) dQf {0}'.format(i) for i in self.k_qf_m]
            rows += ['7) dQf {0}'.format(i) for i in self.k_zero_beq]
            rows += ['8) dQt {0}'.format(i) for i in self.k_qt_m]
            rows += ['9) dPfdp {0}'.format(i) for i in self.k_pf_dp]

            # compute admittances
            Ys = 1.0 / (self.branch_data.R + 1j * self.branch_data.X)
            Ybus, Yf, Yt, tap = ycalc.compile_y_acdc(
                Cf=self.Cf,
                Ct=self.Ct,
                C_bus_shunt=self.shunt_data.C_bus_elm.tocsc(),
                shunt_admittance=self.shunt_data.admittance,
                shunt_active=self.shunt_data.active,
                ys=Ys,
                B=self.branch_data.B,
                Sbase=self.Sbase,
                tap_module=self.branch_data.tap_module,
                tap_angle=self.branch_data.tap_angle,
                Beq=self.branch_data.Beq,
                Gsw=self.branch_data.G0sw,
                virtual_tap_from=self.branch_data.virtual_tap_f,
                virtual_tap_to=self.branch_data.virtual_tap_t,
            )

            J = fubm_jacobian(
                nb=self.nbus,
                nl=self.nbr,
                k_pf_tau=self.k_pf_tau,
                k_pf_dp=self.k_pf_dp,
                k_qf_m=self.k_qf_m,
                k_qt_m=self.k_qt_m,
                k_vt_m=self.k_vt_m,
                k_zero_beq=self.k_zero_beq,
                k_vf_beq=self.k_vf_beq,
                i_vf_beq=self.i_vf_beq,
                i_vt_m=self.i_vt_m,
                F=self.F,
                T=self.T,
                Ys=Ys,
                k2=self.branch_data.k,
                complex_tap=tap,
                tap_modules=self.branch_data.tap_module,
                Bc=self.branch_data.B,
                Beq=self.branch_data.Beq,
                Kdp=self.branch_data.Kdp,
                V=self.Vbus,
                Ybus=Ybus.tocsc(),
                Yf=Yf.tocsc(),
                Yt=Yt.tocsc(),
                Cf=self.Cf.tocsc(),
                Ct=self.Ct.tocsc(),
                pvpq=pvpq,
                pq=self.pq,
            )

            df = pd.DataFrame(
                data=J.toarray(),
                columns=cols,
                index=rows,
            )

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

        elif structure_type == 'pq':
            df = pd.DataFrame(
                data=self.pq,
                columns=['pq'],
                index=self.bus_data.names[self.pq],
            )

        elif structure_type == 'pv':
            df = pd.DataFrame(
                data=self.pv,
                columns=['pv'],
                index=self.bus_data.names[self.pv],
            )

        elif structure_type == 'vd':
            df = pd.DataFrame(
                data=self.vd,
                columns=['vd'],
                index=self.bus_data.names[self.vd],
            )

        elif structure_type == 'pqpv':
            df = pd.DataFrame(
                data=self.pqpv,
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
                data=self.k_pf_tau,
                columns=['k_pf_tau'],
                index=self.branch_data.names[self.k_pf_tau],
            )

        elif structure_type == 'k_qf_m':
            df = pd.DataFrame(
                data=self.k_qf_m,
                columns=['k_qf_m'],
                index=self.branch_data.names[self.k_qf_m],
            )

        elif structure_type == 'k_zero_beq':
            df = pd.DataFrame(
                data=self.k_zero_beq,
                columns=['k_zero_beq'],
                index=self.branch_data.names[self.k_zero_beq],
            )

        elif structure_type == 'k_vf_beq':
            df = pd.DataFrame(
                data=self.k_vf_beq,
                columns=['k_vf_beq'],
                index=self.branch_data.names[self.k_vf_beq],
            )

        elif structure_type == 'k_vt_m':
            df = pd.DataFrame(
                data=self.k_vt_m,
                columns=['k_vt_m'],
                index=self.branch_data.names[self.k_vt_m],
            )

        elif structure_type == 'k_qt_m':
            df = pd.DataFrame(
                data=self.k_qt_m,
                columns=['k_qt_m'],
                index=self.branch_data.names[self.k_qt_m],
            )

        elif structure_type == 'k_pf_dp':
            df = pd.DataFrame(
                data=self.k_pf_dp,
                columns=['k_pf_dp'],
                index=self.branch_data.names[self.k_pf_dp],
            )

        elif structure_type == 'i_vsc':
            df = pd.DataFrame(
                data=self.i_vsc,
                columns=['i_vsc'],
                index=self.branch_data.names[self.i_vsc],
            )

        elif structure_type == 'i_vf_beq':
            df = pd.DataFrame(
                data=self.i_vf_beq,
                columns=['i_vf_beq'],
                index=self.bus_data.names[self.i_vf_beq],
            )

        elif structure_type == 'i_vt_m':
            df = pd.DataFrame(
                data=self.i_vt_m,
                columns=['i_vt_m'],
                index=self.bus_data.names[self.i_vt_m],
            )

        else:
            raise Exception('PF input: structure type not found' + str(structure_type))

        return df

    def get_island(self, bus_idx) -> "NumericalCircuit":
        """
        Get the island corresponding to the given buses
        :param bus_idx: array of bus indices
        :return: SnapshotData
        """

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
        nc.branch_data = self.branch_data.slice(elm_idx=br_idx, bus_idx=bus_idx)

        # HVDC data does not propagate into islands
        # nc.hvdc_data = self.hvdc_data.slice(elm_idx=hvdc_idx, bus_idx=bus_idx)

        nc.load_data = self.load_data.slice(elm_idx=load_idx, bus_idx=bus_idx)
        nc.battery_data = self.battery_data.slice(elm_idx=batt_idx, bus_idx=bus_idx)
        nc.generator_data = self.generator_data.slice(elm_idx=gen_idx, bus_idx=bus_idx)
        nc.shunt_data = self.shunt_data.slice(elm_idx=shunt_idx, bus_idx=bus_idx)

        return nc

    def split_into_islands(self, ignore_single_node_islands=False) -> List["NumericalCircuit"]:
        """
        Split circuit into islands
        :param ignore_single_node_islands: ignore islands composed of only one bus
        :return: List[NumericCircuit]
        """

        # find the matching islands
        idx_islands = tp.find_islands(adj=self.compute_adjacency_matrix(),
                                      active=self.bus_data.active)

        circuit_islands = list()  # type: List[NumericalCircuit]

        for bus_idx in idx_islands:
            if ignore_single_node_islands:
                if len(bus_idx) > 1:
                    island = self.get_island(bus_idx)
                    circuit_islands.append(island)
            else:
                island = self.get_island(bus_idx)
                circuit_islands.append(island)

        return circuit_islands


def compile_numerical_circuit_at(circuit: MultiCircuit,
                                 t_idx: Union[int, None] = None,
                                 apply_temperature=False,
                                 branch_tolerance_mode=BranchImpedanceMode.Specified,
                                 opf_results: Union[OptimalPowerFlowResults, None] = None,
                                 use_stored_guess=False,
                                 bus_dict: Union[Dict[Bus, int], None] = None,
                                 areas_dict: Union[Dict[Area, int], None] = None) -> NumericalCircuit:
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
    :return: NumericalCircuit instance
    """

    logger = Logger()

    # if any valis time index is specified, then the data is compiled from the time series
    time_series = t_idx is not None

    # declare the numerical circuit
    nc = NumericalCircuit(nbus=0,
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
                          t_idx=t_idx)

    if bus_dict is None:
        bus_dict = {bus: i for i, bus in enumerate(circuit.buses)}

    if areas_dict is None:
        areas_dict = {elm: i for i, elm in enumerate(circuit.areas)}

    nc.bus_data = gc_compiler2.get_bus_data(circuit=circuit,
                                            t_idx=t_idx,
                                            time_series=time_series,
                                            areas_dict=areas_dict,
                                            use_stored_guess=use_stored_guess)

    nc.generator_data, gen_dict = gc_compiler2.get_generator_data(circuit=circuit,
                                                                  bus_dict=bus_dict,
                                                                  bus_data=nc.bus_data,
                                                                  t_idx=t_idx,
                                                                  time_series=time_series,
                                                                  Vbus=nc.bus_data.Vbus,
                                                                  logger=logger,
                                                                  opf_results=opf_results,
                                                                  use_stored_guess=use_stored_guess)

    nc.battery_data = gc_compiler2.get_battery_data(circuit=circuit,
                                                    bus_dict=bus_dict,
                                                    bus_data=nc.bus_data,
                                                    t_idx=t_idx,
                                                    time_series=time_series,
                                                    Vbus=nc.bus_data.Vbus,
                                                    logger=logger,
                                                    opf_results=opf_results,
                                                    use_stored_guess=use_stored_guess)

    nc.shunt_data = gc_compiler2.get_shunt_data(circuit=circuit,
                                                bus_dict=bus_dict,
                                                t_idx=t_idx,
                                                time_series=time_series,
                                                Vbus=nc.bus_data.Vbus,
                                                logger=logger,
                                                use_stored_guess=use_stored_guess)

    nc.load_data = gc_compiler2.get_load_data(circuit=circuit,
                                              bus_dict=bus_dict,
                                              Vbus=nc.bus_data.Vbus,
                                              bus_data=nc.bus_data,
                                              logger=logger,
                                              t_idx=t_idx,
                                              time_series=time_series,
                                              opf_results=opf_results,
                                              use_stored_guess=use_stored_guess)

    nc.branch_data = gc_compiler2.get_branch_data(circuit=circuit,
                                                  t_idx=t_idx,
                                                  time_series=time_series,
                                                  bus_dict=bus_dict,
                                                  Vbus=nc.bus_data.Vbus,
                                                  apply_temperature=apply_temperature,
                                                  branch_tolerance_mode=branch_tolerance_mode,
                                                  opf_results=opf_results,
                                                  use_stored_guess=use_stored_guess)

    nc.hvdc_data = gc_compiler2.get_hvdc_data(circuit=circuit,
                                              t_idx=t_idx,
                                              time_series=time_series,
                                              bus_dict=bus_dict,
                                              bus_types=nc.bus_data.bus_types,
                                              opf_results=opf_results)

    if len(circuit.fluid_nodes) > 0:
        nc.fluid_node_data, plant_dict = gc_compiler2.get_fluid_node_data(circuit=circuit,
                                                                          t_idx=t_idx,
                                                                          time_series=time_series)

        nc.fluid_turbine_data = gc_compiler2.get_fluid_turbine_data(circuit=circuit,
                                                                    plant_dict=plant_dict,
                                                                    gen_dict=gen_dict,
                                                                    t_idx=t_idx)

        nc.fluid_pump_data = gc_compiler2.get_fluid_pump_data(circuit=circuit,
                                                              plant_dict=plant_dict,
                                                              gen_dict=gen_dict,
                                                              t_idx=t_idx)

        nc.fluid_p2x_data = gc_compiler2.get_fluid_p2x_data(circuit=circuit,
                                                            plant_dict=plant_dict,
                                                            gen_dict=gen_dict,
                                                            t_idx=t_idx)

        nc.fluid_path_data = gc_compiler2.get_fluid_path_data(circuit=circuit,
                                                              plant_dict=plant_dict,
                                                              t_idx=t_idx)

    nc.consolidate_information(use_stored_guess=use_stored_guess)

    return nc
