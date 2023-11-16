# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
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

import numpy as np
import numba as nb
import pandas as pd
import scipy.sparse as sp
from typing import List, Tuple, Dict, Union

from GridCalEngine.basic_structures import Logger
from GridCalEngine.Core.Devices.multi_circuit import MultiCircuit
from GridCalEngine.basic_structures import BranchImpedanceMode, Vec, IntVec, CxVec
import GridCalEngine.Core.topology as tp

from GridCalEngine.Core.topology import compile_types
from GridCalEngine.Simulations.sparse_solve import get_sparse_type
import GridCalEngine.Core.Compilers.circuit_to_data as gc_compiler2
import GridCalEngine.Core.admittance_matrices as ycalc
from GridCalEngine.enumerations import TransformerControlType, ConverterControlType
import GridCalEngine.Core.DataStructures as ds
from GridCalEngine.Core.Devices.Substation.bus import Bus
from GridCalEngine.Core.Devices.Aggregation.area import Area
from GridCalEngine.Core.Devices.Aggregation.investment import Investment

sparse_type = get_sparse_type()

ALL_STRUCTS = Union[ds.BusData, ds.GeneratorData, ds.BatteryData, ds.LoadData, ds.ShuntData, ds.BranchData, ds.HvdcData]


@nb.njit(cache=True)
def compose_generator_voltage_profile(nbus: int,
                                      gen_bus_indices: np.ndarray,
                                      gen_vset: np.ndarray,
                                      gen_status: np.ndarray,
                                      gen_is_controlled: np.ndarray,
                                      bat_bus_indices: np.ndarray,
                                      bat_vset: np.ndarray,
                                      bat_status: np.ndarray,
                                      bat_is_controlled: np.ndarray,
                                      hvdc_bus_f: np.ndarray,
                                      hvdc_bus_t: np.ndarray,
                                      hvdc_status: np.ndarray,
                                      hvdc_vf: np.ndarray,
                                      hvdc_vt: np.ndarray,
                                      iBeqv: np.ndarray,
                                      iVtma: np.ndarray,
                                      VfBeqbus: np.ndarray,
                                      Vtmabus: np.ndarray,
                                      branch_status: np.ndarray,
                                      br_vf: np.ndarray,
                                      br_vt: np.ndarray):
    """
    Get the array of voltage set points per bus
    :param nbus: number of buses
    :param gen_bus_indices: array of bus indices per generator (ngen)
    :param gen_vset: array of voltage set points (ngen)
    :param gen_status: array of generator status (ngen)
    :param gen_is_controlled: array of values indicating if a generator controls the voltage or not (ngen)
    :param bat_bus_indices:  array of bus indices per battery (nbatt)
    :param bat_vset: array of voltage set points (nbatt)
    :param bat_status: array of battery status (nbatt)
    :param bat_is_controlled: array of values indicating if a battery controls the voltage or not (nbatt)
    :param hvdc_bus_f: array of hvdc bus from indices (nhvdc)
    :param hvdc_bus_t: array of hvdc bus to indices (nhvdc)
    :param hvdc_status: array of hvdc status (nhvdc)
    :param hvdc_vf: array of hvdc voltage from set points (nhvdc)
    :param hvdc_vt: array of hvdc voltage to set points (nhvdc)
    :param iBeqv: indices of the Branches when controlling Vf with Beq
    :param iVtma: indices of the Branches when controlling Vt with ma
    :param VfBeqbus: indices of the buses where Vf is controlled by Beq
    :param Vtmabus: indices of the buses where Vt is controlled by ma
    :param branch_status: array of brach status (nbr)
    :param br_vf: array of branch voltage from set points (nbr)
    :param br_vt: array of branch voltage from set points (nbr)
    :return: Voltage set points array per bus nbus
    """
    V = np.ones(nbus, dtype=nb.complex128)
    used = np.zeros(nbus, dtype=nb.int8)

    # generators
    for i, bus_idx in enumerate(gen_bus_indices):
        if gen_is_controlled[i]:
            if used[bus_idx] == 0:
                if gen_status[i]:
                    V[bus_idx] = complex(gen_vset[i], 0)
                    used[bus_idx] = 1

    # batteries
    for i, bus_idx in enumerate(bat_bus_indices):
        if bat_is_controlled[i]:
            if used[bus_idx] == 0:
                if bat_status[i]:
                    V[bus_idx] = complex(bat_vset[i], 0)
                    used[bus_idx] = 1

    # HVDC
    for i in range(hvdc_status.shape[0]):
        from_idx = hvdc_bus_f[i]
        to_idx = hvdc_bus_t[i]
        if hvdc_status[i] != 0:
            if used[from_idx] == 0:
                V[from_idx] = complex(hvdc_vf[i], 0)
                used[from_idx] = 1
            if used[to_idx] == 0:
                V[to_idx] = complex(hvdc_vt[i], 0)
                used[to_idx] = 1

    # branch - from
    for i in iBeqv:  # Branches controlling Vf
        from_idx = VfBeqbus[i]
        if branch_status[i] != 0:
            if used[from_idx] == 0:
                V[from_idx] = complex(br_vf[i], 0)
                used[from_idx] = 1

    # branch - to
    for i in iVtma:  # Branches controlling Vt
        from_idx = Vtmabus[i]
        if branch_status[i] != 0:
            if used[from_idx] == 0:
                V[from_idx] = complex(br_vt[i], 0)
                used[from_idx] = 1

    return V


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
        'iPfsh',
        'iQfma',
        'iBeqz',
        'iBeqv',
        'iVtma',
        'iQtma',
        'iPfdp',
        'iVscL',
        'VfBeqbus',
        'Vtmabus'
    ]

    def __init__(self,
                 nbus: int,
                 nbr: int,
                 nhvdc: int,
                 nload: int,
                 ngen: int,
                 nbatt: int,
                 nshunt: int,
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

        self.Sbase: float = sbase

        self.any_control: bool = False

        # (old iPfsh) indices of the Branches controlling Pf flow with theta sh
        self.k_pf_tau: IntVec = np.zeros(0, dtype=int)

        # (old iQfma) indices of the Branches controlling Qf with ma
        self.k_qf_m: IntVec = np.zeros(0, dtype=int)

        # (old iBeqz) indices of the Branches when forcing the Qf flow to zero (aka "the zero condition")
        self.k_zero_beq: IntVec = np.zeros(0, dtype=int)

        # (old iBeqv) indices of the Branches when controlling Vf with Beq
        self.k_vf_beq: IntVec = np.zeros(0, dtype=int)

        # (old iVtma) indices of the Branches when controlling Vt with ma
        self.k_vt_m: IntVec = np.zeros(0, dtype=int)

        # (old iQtma) indices of the Branches controlling the Qt flow with ma
        self.k_qt_m: IntVec = np.zeros(0, dtype=int)

        # (old iPfdp) indices of the drop-Vm converters controlling the power flow with theta sh
        self.k_pf_dp: IntVec = np.zeros(0, dtype=int)

        # (old iPfdp_va) indices of the drop-Va converters controlling the power flow with theta sh
        self.iPfdp_va: IntVec = np.zeros(0, dtype=int)

        # indices of the converters
        self.i_vsc: IntVec = np.zeros(0, dtype=int)

        # (old VfBeqbus) indices of the buses where Vf is controlled by Beq
        self.i_vf_beq: IntVec = np.zeros(0, dtype=int)

        # (old Vtmabus) indices of the buses where Vt is controlled by ma
        self.i_vt_m: IntVec = np.zeros(0, dtype=int)  

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

        # --------------------------------------------------------------------------------------------------------------
        # Internal variables filled on demand, to be ready to consume once computed
        # --------------------------------------------------------------------------------------------------------------

        self.Cf_: Union[sp.csc_matrix, None] = None
        self.Ct_: Union[sp.csc_matrix, None] = None
        self.A_: Union[sp.csc_matrix, None] = None

        self.Vbus_: CxVec = None
        self.Sbus_: CxVec = None
        self.Ibus_: CxVec = None
        self.YloadBus_: CxVec = None
        self.Yshunt_from_devices_: CxVec = None

        self.Qmax_bus_: Vec = None
        self.Qmin_bus_: Vec = None
        self.Bmax_bus_: Vec = None
        self.Bmin_bus_: Vec = None

        self.admittances_: Union[ycalc.Admittance, None] = None

        # Admittance for HELM / AC linear
        self.Yseries_: Union[sp.csc_matrix, None] = None
        self.Yshunt_: Union[sp.csc_matrix, None] = None

        # Admittances for Fast-Decoupled
        self.B1_: Union[sp.csc_matrix, None] = None
        self.B2_: Union[sp.csc_matrix, None] = None

        # Admittances for Linear
        self.Bbus_: Union[sp.csc_matrix, None] = None
        self.Bf_: Union[sp.csc_matrix, None] = None
        self.Btheta_: Union[sp.csc_matrix, None] = None
        self.Bpqpv_: Union[sp.csc_matrix, None] = None
        self.Bref_: Union[sp.csc_matrix, None] = None

        self.pq_: IntVec = None
        self.pv_: IntVec = None
        self.vd_: IntVec = None
        self.pqpv_: IntVec = None
        self.ac_: IntVec = None
        self.dc_: IntVec = None

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
        self.Cf_: Union[sp.csc_matrix, None] = None
        self.Ct_: Union[sp.csc_matrix, None] = None
        self.A_: Union[sp.csc_matrix, None] = None

        self.Vbus_: CxVec = None
        self.Sbus_: CxVec = None
        self.Ibus_: CxVec = None
        self.YloadBus_: CxVec = None
        self.Yshunt_from_devices_: CxVec = None

        self.Qmax_bus_: Vec = None
        self.Qmin_bus_: Vec = None
        self.Bmax_bus_: Vec = None
        self.Bmin_bus_: Vec = None

        self.admittances_: Union[ycalc.Admittance, None] = None

        # Admittance for HELM / AC linear
        self.Yseries_: Union[sp.csc_matrix, None] = None
        self.Yshunt_: Union[sp.csc_matrix, None] = None

        # Admittances for Fast-Decoupled
        self.B1_: Union[sp.csc_matrix, None] = None
        self.B2_: Union[sp.csc_matrix, None] = None

        # Admittances for Linear
        self.Bbus_: Union[sp.csc_matrix, None] = None
        self.Bf_: Union[sp.csc_matrix, None] = None
        self.Btheta_: Union[sp.csc_matrix, None] = None
        self.Bpqpv_: Union[sp.csc_matrix, None] = None
        self.Bref_: Union[sp.csc_matrix, None] = None

        self.pq_: IntVec = None
        self.pv_: IntVec = None
        self.vd_: IntVec = None
        self.pqpv_: IntVec = None
        self.ac_: IntVec = None
        self.dc_: IntVec = None

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
            self.bus_data.Vbus = compose_generator_voltage_profile(
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
                iBeqv=np.array(self.k_vf_beq, dtype=int),
                iVtma=np.array(self.k_vt_m, dtype=int),
                VfBeqbus=np.array(self.i_vf_beq, dtype=int),
                Vtmabus=np.array(self.i_vt_m, dtype=int),
                branch_status=self.branch_data.active,
                br_vf=self.branch_data.vf_set,
                br_vt=self.branch_data.vt_set
            )

        self.determine_control_indices()

    def re_calc_admittance_matrices(self, tap_module, idx=None):
        """
        Fast admittance recombination
        :param tap_module: transformer taps (if idx is provided, must have the same length as idx,
                           otherwise the length must be the number of Branches)
        :param idx: Indices of the Branches where the tap belongs,
                    if None assumes that the tap sizes is equal to the number of Branches
        :return:
        """
        if idx is None:
            Ybus_, Yf_, Yt_ = self.admittances_.modify_taps(self.branch_data.tap_module, tap_module)
        else:
            Ybus_, Yf_, Yt_ = self.admittances_.modify_taps(self.branch_data.tap_module[idx], tap_module)

        self.admittances_.Ybus = Ybus_
        self.admittances_.Yf = Yf_
        self.admittances_.Yt = Yt_

    def determine_control_indices(self):
        """
        This function fills in the lists of indices to control different magnitudes

        :returns idx_sh, idx_qz, idx_vf, idx_vt, idx_qt, VfBeqbus, Vtmabus

        VSC Control modes:

        in the paper's scheme:
        from -> DC
        to   -> AC

        |   Mode    |   const.1 |   const.2 |   type    |
        -------------------------------------------------
        |   1       |   theta   |   Vac     |   I       |
        |   2       |   Pf      |   Qac     |   I       |
        |   3       |   Pf      |   Vac     |   I       |
        -------------------------------------------------
        |   4       |   Vdc     |   Qac     |   II      |
        |   5       |   Vdc     |   Vac     |   II      |
        -------------------------------------------------
        |   6       | Vdc droop |   Qac     |   III     |
        |   7       | Vdc droop |   Vac     |   III     |
        -------------------------------------------------

        Indices where each control goes:
        mismatch  →  |  ∆Pf	Qf	Qf  Qt	∆Qt
        variable  →  |  Ɵsh	Beq	m	m	Beq
        Indices   →  |  Ish	Iqz	Ivf	Ivt	Iqt
        ------------------------------------
        VSC 1	     |  -	1	-	1	-   |   AC voltage control (voltage “to”)
        VSC 2	     |  1	1	-	-	1   |   Active and reactive power control
        VSC 3	     |  1	1	-	1	-   |   Active power and AC voltage control
        VSC 4	     |  -	-	1	-	1   |   Dc voltage and Reactive power flow control
        VSC 5	     |  -	-	-	1	1   |   Ac and Dc voltage control
        ------------------------------------
        Transformer 0|	-	-	-	-	-   |   Fixed transformer
        Transformer 1|	1	-	-	-	-   |   Phase shifter → controls power
        Transformer 2|	-	-	1	-	-   |   Control the voltage at the “from” side
        Transformer 3|	-	-	-	1	-   |   Control the voltage at the “to” side
        Transformer 4|	1	-	1	-	-   |   Control the power flow and the voltage at the “from” side
        Transformer 5|	1	-	-	1	-   |   Control the power flow and the voltage at the “to” side
        ------------------------------------

        """

        # indices in the global branch scheme
        iPfsh = list()  # indices of the Branches controlling Pf flow with theta sh
        iQfma = list()  # indices of the Branches controlling Qf with ma
        iBeqz = list()  # indices of the Branches when forcing the Qf flow to zero (aka "the zero condition")
        iBeqv = list()  # indices of the Branches when controlling Vf with Beq
        iVtma = list()  # indices of the Branches when controlling Vt with ma
        iQtma = list()  # indices of the Branches controlling the Qt flow with ma
        iPfdp = list()  # indices of the drop converters controlling the power flow with theta sh
        iVscL = list()  # indices of the converters
        iPfdp_va = list()

        self.any_control = False

        for k, tpe in enumerate(self.branch_data.control_mode):

            if tpe == TransformerControlType.fixed:
                pass

            elif tpe == TransformerControlType.Pt:
                iPfsh.append(k)
                self.any_control = True

            elif tpe == TransformerControlType.Qt:
                iQtma.append(k)
                self.any_control = True

            elif tpe == TransformerControlType.PtQt:
                iPfsh.append(k)
                iQtma.append(k)
                self.any_control = True

            elif tpe == TransformerControlType.Vt:
                iVtma.append(k)
                self.any_control = True

            elif tpe == TransformerControlType.PtVt:
                iPfsh.append(k)
                iVtma.append(k)
                self.any_control = True

            # VSC ------------------------------------------------------------------------------------------------------
            elif tpe == ConverterControlType.type_0_free:  # 1a:Free
                iBeqz.append(k)
                iVscL.append(k)
                self.any_control = True

            elif tpe == ConverterControlType.type_I_1:  # 1:Vac
                iVtma.append(k)
                iBeqz.append(k)
                iVscL.append(k)
                self.any_control = True

            elif tpe == ConverterControlType.type_I_2:  # 2:Pdc+Qac

                iPfsh.append(k)
                iQtma.append(k)
                iBeqz.append(k)

                iVscL.append(k)
                self.any_control = True

            elif tpe == ConverterControlType.type_I_3:  # 3:Pdc+Vac
                iPfsh.append(k)
                iVtma.append(k)
                iBeqz.append(k)

                iVscL.append(k)
                self.any_control = True

            elif tpe == ConverterControlType.type_II_4:  # 4:Vdc+Qac
                iBeqv.append(k)
                iQtma.append(k)

                iVscL.append(k)
                self.any_control = True

            elif tpe == ConverterControlType.type_II_5:  # 5:Vdc+Vac
                iBeqv.append(k)
                iVtma.append(k)

                iVscL.append(k)
                self.any_control = True

            elif tpe == ConverterControlType.type_III_6:  # 6:Droop+Qac
                iPfdp.append(k)
                iQtma.append(k)

                iVscL.append(k)
                self.any_control = True

            elif tpe == ConverterControlType.type_III_7:  # 4a:Droop-slack
                iPfdp.append(k)
                iVtma.append(k)

                iVscL.append(k)
                self.any_control = True

            elif tpe == ConverterControlType.type_IV_I:  # 8:Vdc
                iBeqv.append(k)
                iVscL.append(k)

                self.any_control = True

            elif tpe == ConverterControlType.type_IV_II:  # 9:Pdc
                iPfsh.append(k)
                iBeqz.append(k)

                self.any_control = True

            elif tpe == 0:
                pass  # required for the no-control case

            else:
                raise Exception('Unknown control type:' + str(tpe))

        # VfBeqbus_sh = list()
        # for k, is_controlled in enumerate(self.shunt_data.get_controlled_per_bus()):
        #     if is_controlled:
        #         VfBeqbus_sh.append(k)
        #         self.any_control = True

        # FUBM- Saves the "from" bus identifier for Vf controlled by Beq
        #  (Converters type II for Vdc control)
        self.i_vf_beq = self.F[iBeqv]

        # FUBM- Saves the "to"   bus identifier for Vt controlled by ma
        #  (Converters and Transformers)
        self.i_vt_m = self.T[iVtma]

        self.k_pf_tau = np.array(iPfsh, dtype=int)
        self.k_qf_m = np.array(iQfma, dtype=int)
        self.k_zero_beq = np.array(iBeqz, dtype=int)
        self.k_vf_beq = np.array(iBeqv, dtype=int)
        self.k_vt_m = np.array(iVtma, dtype=int)
        self.k_qt_m = np.array(iQtma, dtype=int)
        self.k_pf_dp = np.array(iPfdp, dtype=int)
        self.iPfdp_va = np.array(iPfdp_va, dtype=int)
        self.i_vsc = np.array(iVscL, dtype=int)

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
                              sbase=self.Sbase,
                              t_idx=self.t_idx)

        nc.bus_data = self.bus_data.copy()
        nc.branch_data = self.branch_data.copy()
        nc.hvdc_data = self.hvdc_data.copy()
        nc.load_data = self.load_data.copy()
        nc.shunt_data = self.shunt_data.copy()
        nc.generator_data = self.generator_data.copy()
        nc.battery_data = self.battery_data.copy()
        nc.consolidate_information()

        return nc

    def get_structures_list(self) -> List[Union[ds.BusData, ds.LoadData, ds.ShuntData,
    ds.GeneratorData, ds.BatteryData,
    ds.BranchData, ds.HvdcData]]:
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
                self.hvdc_data]

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
        if self.ac_ is None:
            self.ac_ = self.branch_data.get_ac_indices()

        return self.ac_

    @property
    def dc_indices(self):
        """
        Array of indices of the DC Branches
        :return: array of indices
        """
        if self.dc_ is None:
            self.dc_ = self.branch_data.get_dc_indices()

        return self.dc_

    @property
    def Cf(self):
        """
        Connectivity matrix of the "from" nodes
        :return: CSC matrix
        """
        # compute on demand and store
        if self.Cf_ is None:
            self.Cf_, self.Ct_ = ycalc.compute_connectivity(
                branch_active=self.branch_data.active,
                Cf_=self.branch_data.C_branch_bus_f,
                Ct_=self.branch_data.C_branch_bus_t)

        if not isinstance(self.Cf_, sp.csc_matrix):
            self.Cf_ = self.Cf_.tocsc()

        return self.Cf_

    @property
    def Ct(self):
        """
        Connectivity matrix of the "to" nodes
        :return: CSC matrix
        """
        # compute on demand and store
        if self.Ct_ is None:
            self.Cf_, self.Ct_ = ycalc.compute_connectivity(
                branch_active=self.branch_data.active,
                Cf_=self.branch_data.C_branch_bus_f,
                Ct_=self.branch_data.C_branch_bus_t)

        if not isinstance(self.Ct_, sp.csc_matrix):
            self.Ct_ = self.Ct_.tocsc()

        return self.Ct_

    @property
    def A(self):
        """
        Connectivity matrix
        :return: CSC matrix
        """

        if self.A_ is None:
            self.A_ = (self.Cf - self.Ct).tocsc()

        return self.A_

    @property
    def Ybus(self):
        """
        Admittance matrix
        :return: CSC matrix
        """

        # compute admittances on demand
        if self.admittances_ is None:
            self.admittances_ = ycalc.compute_admittances(
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
        return self.admittances_.Ybus

    @property
    def Yf(self):
        """
        Admittance matrix of the "from" nodes with the Branches
        :return: CSC matrix
        """
        if self.admittances_ is None:
            _ = self.Ybus  # call the constructor of Yf

        return self.admittances_.Yf

    @property
    def Yt(self):
        """
        Admittance matrix of the "to" nodes with the Branches
        :return: CSC matrix
        """
        if self.admittances_ is None:
            _ = self.Ybus  # call the constructor of Yt

        return self.admittances_.Yt

    @property
    def Yseries(self):
        """
        Admittance matrix of the series elements of the pi model of the Branches
        :return: CSC matrix
        """
        # compute admittances on demand
        if self.Yseries_ is None:
            self.Yseries_, self.Yshunt_ = ycalc.compute_split_admittances(
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

        return self.Yseries_

    @property
    def Yshunt(self):
        """
        Array of shunt admittances of the pi model of the Branches (used in HELM mostly)
        :return: Array of complex values
        """
        if self.Yshunt_ is None:
            _ = self.Yseries  # call the constructor of Yshunt

        return self.Yshunt_

    # @property
    # def YshuntHelm(self):
    #     return self.Yshunt_from_devices

    @property
    def B1(self):
        """
        B' matrix of the fast decoupled method
        :return:
        """
        if self.B1_ is None:
            self.B1_, self.B2_ = ycalc.compute_fast_decoupled_admittances(
                X=self.branch_data.X,
                B=self.branch_data.B,
                tap_module=self.branch_data.tap_module,
                vtap_f=self.branch_data.vf_set,
                vtap_t=self.branch_data.vt_set,
                Cf=self.Cf,
                Ct=self.Ct,
            )

        return self.B1_

    @property
    def B2(self):
        """
        B'' matrix of the fast decoupled method
        :return:
        """
        if self.B2_ is None:
            _ = self.B1  # call the constructor of B2

        return self.B2_

    @property
    def Bbus(self):
        """
        Susceptance matrix for the linear methods
        :return:
        """
        if self.Bbus_ is None:
            self.Bbus_, self.Bf_, self.Btheta_ = ycalc.compute_linear_admittances(
                nbr=self.nbr,
                X=self.branch_data.X,
                R=self.branch_data.R,
                tap_modules=self.branch_data.tap_module,
                active=self.branch_data.active,
                Cf=self.Cf,
                Ct=self.Ct,
                ac=self.ac_indices,
                dc=self.dc_indices
            )

            self.Bpqpv_ = self.Bbus_[np.ix_(self.pqpv, self.pqpv)].tocsc()
            self.Bref_ = self.Bbus_[np.ix_(self.pqpv, self.vd)].tocsc()

        return self.Bbus_

    @property
    def Bf(self):
        """
        Susceptance matrix of the "from" nodes to the Branches
        :return:
        """
        if self.Bf_ is None:
            _ = self.Bbus  # call the constructor of Bf

        return self.Bf_

    @property
    def Btheta(self):
        """

        :return:
        """
        if self.Bf_ is None:
            _ = self.Bbus  # call the constructor of Bf

        return self.Btheta_

    @property
    def Bpqpv(self):
        """

        :return:
        """
        if self.Bpqpv_ is None:
            _ = self.Bbus  # call the constructor of Bpqpv

        return self.Bpqpv_

    @property
    def Bref(self):
        """

        :return:
        """
        if self.Bref_ is None:
            _ = self.Bbus  # call the constructor of Bref

        return self.Bref_

    @property
    def vd(self):
        """

        :return:
        """
        if self.vd_ is None:
            self.vd_, self.pq_, self.pv_, self.pqpv_ = compile_types(Pbus=self.Sbus.real, types=self.bus_data.bus_types)

        return self.vd_

    @property
    def pq(self):
        """

        :return:
        """
        if self.pq_ is None:
            _ = self.vd  # call the constructor

        return self.pq_

    @property
    def pv(self):
        """

        :return:
        """
        if self.pv_ is None:
            _ = self.vd  # call the constructor

        return self.pv_

    @property
    def pqpv(self):
        """

        :return:
        """
        if self.pqpv_ is None:
            _ = self.vd  # call the constructor

        return self.pqpv_

    @property
    def structs_dict(self):
        """

        :return:
        """
        if self.structs_dict_ is None:
            self.structs_dict_ = self.get_structs_idtag_dict()

        return self.structs_dict_

    def compute_reactive_power_limits(self):
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

        elif structure_type == 'iPfsh':
            df = pd.DataFrame(
                data=self.k_pf_tau,
                columns=['iPfsh'],
                index=self.branch_data.names[self.k_pf_tau],
            )

        elif structure_type == 'iQfma':
            df = pd.DataFrame(
                data=self.k_qf_m,
                columns=['iQfma'],
                index=self.branch_data.names[self.k_qf_m],
            )

        elif structure_type == 'iBeqz':
            df = pd.DataFrame(
                data=self.k_zero_beq,
                columns=['iBeqz'],
                index=self.branch_data.names[self.k_zero_beq],
            )

        elif structure_type == 'iBeqv':
            df = pd.DataFrame(
                data=self.k_vf_beq,
                columns=['iBeqv'],
                index=self.branch_data.names[self.k_vf_beq],
            )

        elif structure_type == 'iVtma':
            df = pd.DataFrame(
                data=self.k_vt_m,
                columns=['iVtma'],
                index=self.branch_data.names[self.k_vt_m],
            )

        elif structure_type == 'iQtma':
            df = pd.DataFrame(
                data=self.k_qt_m,
                columns=['iQtma'],
                index=self.branch_data.names[self.k_qt_m],
            )

        elif structure_type == 'iPfdp':
            df = pd.DataFrame(
                data=self.k_pf_dp,
                columns=['iPfdp'],
                index=self.branch_data.names[self.k_pf_dp],
            )

        elif structure_type == 'iVscL':
            df = pd.DataFrame(
                data=self.i_vsc,
                columns=['iVscL'],
                index=self.branch_data.names[self.i_vsc],
            )

        elif structure_type == 'VfBeqbus':
            df = pd.DataFrame(
                data=self.i_vf_beq,
                columns=['VfBeqbus'],
                index=self.bus_data.names[self.i_vf_beq],
            )

        elif structure_type == 'Vtmabus':
            df = pd.DataFrame(
                data=self.i_vt_m,
                columns=['Vtmabus'],
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

        nc.determine_control_indices()

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
                                 opf_results: Union["OptimalPowerFlowResults", None] = None,
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

    nc.generator_data = gc_compiler2.get_generator_data(circuit=circuit,
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

    nc.consolidate_information(use_stored_guess=use_stored_guess)

    return nc
