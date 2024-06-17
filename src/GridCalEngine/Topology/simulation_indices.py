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


import numpy as np
import numba as nb
from typing import Union, Tuple, List
from GridCalEngine.enumerations import (TransformerControlType, ConverterControlType, BusMode,
                                        TapModuleControl, TapAngleControl)
from GridCalEngine.basic_structures import Vec, IntVec, BoolVec



@nb.njit(cache=True)
def compile_types(Pbus: Vec, types: IntVec) -> Tuple[IntVec, IntVec, IntVec, IntVec]:
    """
    Compile the types.
    :param Pbus: array of real power Injections per node used to choose the slack as
                 the node with greater generation if no slack is provided
    :param types: array of tentative node types (it may be modified internally)
    :return: ref, pq, pv, pqpv
    """

    # check that Sbus is a 1D array
    assert (len(Pbus.shape) == 1)

    pq = np.where(types == BusMode.PQ.value)[0]
    pv = np.where(types == BusMode.PV.value)[0]
    ref = np.where(types == BusMode.Slack.value)[0]

    if len(ref) == 0:  # there is no slack!

        if len(pv) == 0:  # there are no pv neither -> blackout grid
            pass
        else:  # select the first PV generator as the slack

            mx = max(Pbus[pv])
            if mx > 0:
                # find the generator that is injecting the most
                i = np.where(Pbus == mx)[0][0]

            else:
                # all the generators are injecting zero, pick the first pv
                i = pv[0]

            # delete the selected pv bus from the pv list and put it in the slack list
            pv = np.delete(pv, np.where(pv == i)[0])
            ref = np.array([i])

        for r in ref:
            types[r] = BusMode.Slack.value
    else:
        pass  # no problem :)

    no_slack = np.concatenate((pq, pv))
    no_slack.sort()

    return ref, pq, pv, no_slack


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
                                      k_vf_beq: np.ndarray,
                                      k_vt_m: np.ndarray,
                                      i_vf_beq: np.ndarray,
                                      i_vt_m: np.ndarray,
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
    :param k_vf_beq: indices of the Branches when controlling Vf with Beq
    :param k_vt_m: indices of the Branches when controlling Vt with ma
    :param i_vf_beq: indices of the buses where Vf is controlled by Beq
    :param i_vt_m: indices of the buses where Vt is controlled by ma
    :param branch_status: array of brach status (nbr)
    :param br_vf: array of branch voltage from set points (nbr)
    :param br_vt: array of branch voltage from set points (nbr)
    :return: Voltage set points array per bus nbus
    """
    V = np.ones(nbus, dtype=nb.complex128)
    used = np.zeros(nbus, dtype=nb.int8)
    # V = np.ones(nbus, dtype=complex)
    # used = np.zeros(nbus, dtype=int)

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
    for k, from_idx in zip(k_vf_beq, i_vf_beq):  # Branches controlling Vf
        if branch_status[k] != 0:
            if used[from_idx] == 0:
                V[from_idx] = complex(br_vf[k], 0)
                used[from_idx] = 1

    # branch - to
    for k, from_idx in zip(k_vt_m, i_vt_m):  # Branches controlling Vt
        if branch_status[k] != 0:
            if used[from_idx] == 0:
                V[from_idx] = complex(br_vt[k], 0)
                used[from_idx] = 1

    return V


class SimulationIndices:
    """
    Class to handle the simulation indices
    """

    def __init__(self,
                 bus_types: IntVec,
                 Pbus: Vec,
                 control_mode: List[Union[TransformerControlType, ConverterControlType]],
                 F: IntVec,
                 T: IntVec,
                 dc: IntVec):

        # master aray of bus types (nbus)
        self.bus_types = bus_types

        # master array of branch control types (nbr)
        self.control_mode = control_mode

        # AC and DC indices
        self.ac: IntVec = np.where(dc == 0)[0]
        self.dc: IntVec = np.where(dc != 0)[0]

        # bus type indices
        self.pq: IntVec = np.zeros(0, dtype=int)
        self.pqv: IntVec = np.zeros(0, dtype=int)
        self.pv: IntVec = np.zeros(0, dtype=int)  # PV-local
        self.pvr: IntVec = np.zeros(0, dtype=int)  # PV-remote
        self.vd: IntVec = np.zeros(0, dtype=int)
        self.no_slack: IntVec = np.zeros(0, dtype=int)

        # branch control indices
        self.any_control: bool = False

        # indices of the Branches controlling Pf flow with tau
        self.k_pf_tau: IntVec = np.zeros(0, dtype=int)

        # indices of the Branches controlling Pt flow with tau
        self.k_pt_tau: IntVec = np.zeros(0, dtype=int)

        # indices of the Branches controlling Qf flow with m
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

        # indices of the transformers with controlled tap module
        self.k_m: IntVec = np.zeros(0, dtype=int)

        # indices of the transformers with controlled tap angle
        self.k_tau: IntVec = np.zeros(0, dtype=int)

        # indices of the transformers with controlled tap angle and module
        self.k_mtau: IntVec = np.zeros(0, dtype=int)

        # indices of the buses with controlled tap module
        self.i_m: IntVec = np.zeros(0, dtype=int)

        # indices of the buses with controlled tap angle
        self.i_tau: IntVec = np.zeros(0, dtype=int)

        # indices of the buses with controlled tap angle and module
        self.i_mtau: IntVec = np.zeros(0, dtype=int)

        # (old iPfdp_va) indices of the drop-Va converters controlling the power flow with theta sh
        self.iPfdp_va: IntVec = np.zeros(0, dtype=int)

        # indices of the converters
        self.i_vsc: IntVec = np.zeros(0, dtype=int)

        # (old VfBeqbus) indices of the buses where Vf is controlled by Beq
        self.i_vf_beq: IntVec = np.zeros(0, dtype=int)

        # (old Vtmabus) indices of the buses where Vt is controlled by ma
        self.i_vt_m: IntVec = np.zeros(0, dtype=int)

        # determine the bus indices
        self.vd, self.pq, self.pv, self.no_slack = compile_types(Pbus=Pbus, types=bus_types)

        # determine the branch indices
        self.compile_control_indices(control_mode=control_mode, F=F, T=T)

    def recompile_types(self,
                        bus_types: IntVec,
                        Pbus: Vec):
        """

        :param bus_types:
        :param Pbus:
        :return:
        """
        self.bus_types = bus_types

        # determine the bus indices
        self.vd, self.pq, self.pv, self.no_slack = compile_types(Pbus=Pbus, types=bus_types)

    def compile_control_indices(self,
                                control_mode: List[Union[TransformerControlType, ConverterControlType]],
                                F: IntVec,
                                T: IntVec) -> None:
        """
        This function fills in the lists of indices to control different magnitudes

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
        k_pf_tau_lst = list()  # indices of the Branches controlling Pf flow with theta sh
        k_qf_m_lst = list()  # indices of the Branches controlling Qf with ma
        k_zero_beq_lst = list()  # indices of the Branches when forcing the Qf flow to zero (aka "the zero condition")
        k_vf_beq_lst = list()  # indices of the Branches when controlling Vf with Beq
        k_vt_m_lst = list()  # indices of the Branches when controlling Vt with ma
        k_qt_m_lst = list()  # indices of the Branches controlling the Qt flow with ma
        k_pf_dp_lst = list()  # indices of the drop converters controlling the power flow with theta sh
        k_m_modif_lst = list()  # indices of the transformers with controlled tap module
        k_tau_modif_lst = list()  # indices of the transformers with controlled tap angle
        k_mtau_modif_lst = list()  # indices of the transformers with controlled tap angle and module
        i_m_modif_lst = list()  # indices of the controlled buses with tap module
        i_tau_modif_lst = list()  # indices of the controlled buses with tap angle
        i_mtau_modif_lst = list()  # indices of the controlled buses with tap module and angle
        i_vsc_lst = list()  # indices of the converters
        iPfdp_va_lst = list()

        self.any_control = False

        for k, tpe in enumerate(control_mode):

            if tpe == TransformerControlType.fixed:
                pass

            elif tpe == TransformerControlType.Pf:  # TODO: change name .Pt by .Pf
                k_pf_tau_lst.append(k)
                k_tau_modif_lst.append(k)
                i_tau_modif_lst.append(F[k])  # TODO: identify which index is the controlled one
                self.any_control = True

            elif tpe == TransformerControlType.Qt:
                k_qt_m_lst.append(k)
                k_m_modif_lst.append(k)
                i_m_modif_lst.append(T[k])
                self.any_control = True

            elif tpe == TransformerControlType.PtQt:
                k_pf_tau_lst.append(k)
                k_qt_m_lst.append(k)
                k_m_modif_lst.append(k)
                k_tau_modif_lst.append(k)
                k_mtau_modif_lst.append(k)
                i_tau_modif_lst.append(F[k])
                i_m_modif_lst.append(T[k])
                self.any_control = True

            elif tpe == TransformerControlType.V:
                k_vt_m_lst.append(k)
                k_m_modif_lst.append(k)
                i_m_modif_lst.append(T[k])
                self.any_control = True

            elif tpe == TransformerControlType.PtV:
                k_pf_tau_lst.append(k)
                k_vt_m_lst.append(k)
                k_m_modif_lst.append(k)
                k_tau_modif_lst.append(k)
                k_mtau_modif_lst.append(k)
                i_tau_modif_lst.append(F[k])
                i_m_modif_lst.append(T[k])
                self.any_control = True

            # VSC ------------------------------------------------------------------------------------------------------
            elif tpe == ConverterControlType.type_0_free:  # 1a:Free
                k_zero_beq_lst.append(k)
                i_vsc_lst.append(k)
                self.any_control = True

            elif tpe == ConverterControlType.type_I_1:  # 1:Vac
                k_vt_m_lst.append(k)
                k_zero_beq_lst.append(k)
                i_vsc_lst.append(k)
                self.any_control = True

            elif tpe == ConverterControlType.type_I_2:  # 2:Pdc+Qac

                k_pf_tau_lst.append(k)
                k_qt_m_lst.append(k)
                k_zero_beq_lst.append(k)

                i_vsc_lst.append(k)
                self.any_control = True

            elif tpe == ConverterControlType.type_I_3:  # 3:Pdc+Vac
                k_pf_tau_lst.append(k)
                k_vt_m_lst.append(k)
                k_zero_beq_lst.append(k)

                i_vsc_lst.append(k)
                self.any_control = True

            elif tpe == ConverterControlType.type_II_4:  # 4:Vdc+Qac
                k_vf_beq_lst.append(k)
                k_qt_m_lst.append(k)

                i_vsc_lst.append(k)
                self.any_control = True

            elif tpe == ConverterControlType.type_II_5:  # 5:Vdc+Vac
                k_vf_beq_lst.append(k)
                k_vt_m_lst.append(k)

                i_vsc_lst.append(k)
                self.any_control = True

            elif tpe == ConverterControlType.type_III_6:  # 6:Droop+Qac
                k_pf_dp_lst.append(k)
                k_qt_m_lst.append(k)

                i_vsc_lst.append(k)
                self.any_control = True

            elif tpe == ConverterControlType.type_III_7:  # 4a:Droop-slack
                k_pf_dp_lst.append(k)
                k_vt_m_lst.append(k)

                i_vsc_lst.append(k)
                self.any_control = True

            elif tpe == ConverterControlType.type_IV_I:  # 8:Vdc
                k_vf_beq_lst.append(k)
                i_vsc_lst.append(k)

                self.any_control = True

            elif tpe == ConverterControlType.type_IV_II:  # 9:Pdc
                k_pf_tau_lst.append(k)
                k_zero_beq_lst.append(k)

                self.any_control = True

            elif tpe == 0:
                pass  # required for the no-control case

            else:
                raise Exception('Unknown control type:' + str(tpe))

        # FUBM- Saves the "from" bus identifier for Vf controlled by Beq
        #  (Converters type II for Vdc control)
        self.i_vf_beq = F[k_vf_beq_lst]

        # FUBM- Saves the "to"   bus identifier for Vt controlled by ma
        #  (Converters and Transformers)
        self.i_vt_m = T[k_vt_m_lst]

        self.k_pf_tau = np.array(k_pf_tau_lst, dtype=int)
        self.k_qf_m = np.array(k_qf_m_lst, dtype=int)
        self.k_zero_beq = np.array(k_zero_beq_lst, dtype=int)
        self.k_vf_beq = np.array(k_vf_beq_lst, dtype=int)
        self.k_vt_m = np.array(k_vt_m_lst, dtype=int)
        self.k_qt_m = np.array(k_qt_m_lst, dtype=int)
        self.k_pf_dp = np.array(k_pf_dp_lst, dtype=int)
        self.k_m = np.array(k_m_modif_lst, dtype=int)
        self.k_tau = np.array(k_tau_modif_lst, dtype=int)
        self.k_mtau = np.array(k_mtau_modif_lst, dtype=int)
        self.i_m = np.array(i_m_modif_lst, dtype=int)
        self.i_tau = np.array(i_tau_modif_lst, dtype=int)
        self.i_mtau = np.array(i_mtau_modif_lst, dtype=int)
        self.iPfdp_va = np.array(iPfdp_va_lst, dtype=int)
        self.i_vsc = np.array(i_vsc_lst, dtype=int)

    def get_base_voltage(self, nbus, generator_data, battery_data, hvdc_data, branch_data):
        """
        GEt the voltage profile based on the devices control voltage
        :param nbus:
        :param generator_data:
        :param battery_data:
        :param hvdc_data:
        :param branch_data:
        :return:
        """
        return compose_generator_voltage_profile(
            nbus=nbus,
            gen_bus_indices=generator_data.get_bus_indices(),
            gen_vset=generator_data.v,
            gen_status=generator_data.active,
            gen_is_controlled=generator_data.controllable,
            bat_bus_indices=battery_data.get_bus_indices(),
            bat_vset=battery_data.v,
            bat_status=battery_data.active,
            bat_is_controlled=battery_data.controllable,
            hvdc_bus_f=hvdc_data.get_bus_indices_f(),
            hvdc_bus_t=hvdc_data.get_bus_indices_t(),
            hvdc_status=hvdc_data.active,
            hvdc_vf=hvdc_data.Vset_f,
            hvdc_vt=hvdc_data.Vset_t,
            k_vf_beq=self.k_vf_beq,
            k_vt_m=self.k_vt_m,
            i_vf_beq=self.i_vf_beq,
            i_vt_m=self.i_vt_m,
            branch_status=branch_data.active,
            br_vf=branch_data.vf_set,
            br_vt=branch_data.vt_set
        )


class SimulationIndicesV2:
    """
    Class to handle the simulation indices
    """
    # TODO: Dudas: El ConverterControlType controla la toma?, TransformerControlType y ConverterControlType están en desuso¿?
    def __init__(self,
                 bus_types: IntVec,
                 Pbus: Vec,
                 branch_control_bus: IntVec,
                 branch_control_branch: IntVec,
                 branch_control_mode_m: List[Union[TapModuleControl]],#List[Union[TransformerControlType, ConverterControlType]],
                 branch_control_mode_tau: List[Union[TapAngleControl]],#List[Union[TransformerControlType, ConverterControlType]],
                 generator_control_bus: IntVec,
                 generator_iscontrolled: BoolVec,
                 generator_buses: IntVec,
                 F: IntVec,
                 T: IntVec,
                 dc: IntVec):
        """

        :param bus_types: Nbus
        :param Pbus:Nbus
        :param branch_control_bus:Nbranch
        :param branch_control_branch:Nbranch
        :param branch_control_mode_m:Nbranch
        :param branch_control_mode_tau:Nbranch
        :param generator_control_bus: Ngen
        :param generator_iscontrolled: Ngen
        :param F: Nbranch
        :param T: Nbranch
        :param dc: Nbranch
        """

        # master aray of bus types (nbus)
        self.bus_types = bus_types

        # master array of branch control types (nbr)
        #self.control_mode = control_mode

        # AC and DC indices
        self.ac: IntVec = np.where(dc == 0)[0]
        self.dc: IntVec = np.where(dc != 0)[0]

        # bus type indices
        self.pq: IntVec = np.zeros(0, dtype=int)
        self.pqv: IntVec = np.zeros(0, dtype=int)
        self.pv: IntVec = np.zeros(0, dtype=int)  # PV-local
        self.pvr: IntVec = np.zeros(0, dtype=int)  # PV-remote
        self.vd: IntVec = np.zeros(0, dtype=int)
        self.no_slack: IntVec = np.zeros(0, dtype=int)

        # branch control indices
        self.any_control: bool = False

        # (old iPfsh) indices of the Branches controlling Pf flow with theta sh
        self.k_pf_tau: IntVec = np.zeros(0, dtype=int)

        # (old iQfma) indices of the Branches controlling Qf with ma
        self.k_qf_m: IntVec = np.zeros(0, dtype=int)

        # (old iVtma) indices of the Branches when controlling Vt with ma
        self.k_vt_m: IntVec = np.zeros(0, dtype=int)

        # (old iQtma) indices of the Branches controlling the Qt flow with ma
        self.k_qt_m: IntVec = np.zeros(0, dtype=int)

        # (old iPfdp) indices of the drop-Vm converters controlling the power flow with theta sh
        self.k_pf_dp: IntVec = np.zeros(0, dtype=int)

        # indices of the transformers with controlled tap module
        self.k_m: IntVec = np.zeros(0, dtype=int)

        # indices of the transformers with controlled tap angle
        self.k_tau: IntVec = np.zeros(0, dtype=int)

        # indices of the transformers with controlled tap angle and module
        self.k_mtau: IntVec = np.zeros(0, dtype=int)

        # indices of the buses with controlled tap module
        self.i_m: IntVec = np.zeros(0, dtype=int)

        # indices of the buses with controlled tap angle
        self.i_tau: IntVec = np.zeros(0, dtype=int)

        # indices of the buses with controlled tap angle and module
        self.i_mtau: IntVec = np.zeros(0, dtype=int)

        # (old iPfdp_va) indices of the drop-Va converters controlling the power flow with theta sh
        self.iPfdp_va: IntVec = np.zeros(0, dtype=int)

        # indices of the converters
        self.i_vsc: IntVec = np.zeros(0, dtype=int)

        # (old Vtmabus) indices of the buses where Vt is controlled by ma
        self.i_vt_m: IntVec = np.zeros(0, dtype=int)

        # determine the bus indices
        self.vd, self.pq, self.pv, self.no_slack = compile_types(Pbus=Pbus, types=bus_types)

        # determine the branch indices
        #self.compile_control_indices(control_mode=control_mode, F=F, T=T)

    def compute_indices(self,
                        Pbus: Vec,
                        types: IntVec,
                        generator_control_bus: IntVec,
                        generator_buses: IntVec,
                        branch_control_bus: IntVec,
                        branch_control_branch: IntVec,
                        Snomgen: Vec,
                        branch_control_mode_m: List[Union[TapModuleControl]],
                        branch_control_mode_tau: List[Union[TapAngleControl]]) -> Tuple[IntVec, IntVec, IntVec, IntVec,
                                                                                        IntVec, IntVec, IntVec]:
        """
        Compile the types.
        :param Pbus: array of real power Injections per node used to choose the slack as
                     the node with greater generation if no slack is provided
        :param types: array of tentative node types (it may be modified internally)
        :return: ref, pq, pv, pqpv
        """

        # check that Sbus is a 1D array
        assert (len(Pbus.shape) == 1)

        pq = np.where(types == BusMode.PQ.value)[0]
        pv = np.where(types == BusMode.PV.value)[0]
        pvr = np.where(types == BusMode.PVR.value)[0]
        ref = np.where(types == BusMode.Slack.value)[0]
        k_m_vr = np.where(branch_control_mode_m == TapModuleControl.Vm)[0]
        k_m_Qf = np.where(branch_control_mode_m == TapModuleControl.Qf)[0]
        k_m_Qt = np.where(branch_control_mode_m == TapModuleControl.Qt)[0]
        k_tau_Pf = np.where(branch_control_mode_tau == TapAngleControl.Pf)[0]
        k_tau_Pt = np.where(branch_control_mode_tau == TapAngleControl.Pt)[0]
        pqv = np.zeros(0, dtype=int)
        i_m_vr = np.zeros(0, dtype=int)

        # TODO: hay que actualizar el types cada vez que se cambie un nudo
        # checking the slack information consistency
        if len(ref) == 0:  # there is no slack!
            if len(np.concatenate((pv, pvr))) == 0:  # there are no pv neither -> blackout grid
                print("Blackout grid: no slack neither pv or pvr nodes")
                pass
            else:  # select the PV with higher rate power as slack
                i = generator_buses[np.where(Snomgen == max(Snomgen))]
                if i in pv:
                    pv = np.delete(pv, np.where(pv == i)[0])
                    ref = np.array([i])
                elif i in pvr:
                    pvr = np.delete(pvr, np.where(pvr == i)[0])
                    ref = np.array([i])
            for r in ref:
                types[r] = BusMode.Slack.value

        if len(ref) > 1:    # there are more than one slacks!
            maxpos = list()
            for r in ref:
                maxpos.append(np.where(generator_buses == r)[0][0])
            mx = max(Snomgen[maxpos])
            # i = ref[np.where(max(Snomgen[maxpos]) == mx)]
            i = ref[np.where(Snomgen[maxpos] == mx)[0]]

            # delete the rest of generators from ref and put them in the pv list
            newpv = np.delete(ref, np.where(ref == i)[0])
            pv = np.concatenate([pv, newpv])
            ref = np.array([i])
        else:
            pass  # no problem :)

        no_slack = np.concatenate((pq, pv, pvr))
        no_slack.sort()

        # Let's check if slack node is controlling its own node voltage


        # Let's check if pq nodes have their voltage controlled so that they are converted to pqv
        for i in pq:
            if i in generator_control_bus:
                # add as pqv
                pqv = np.append(pqv, np.array([i]))
                # delete from pq
                pq = np.delete(pq, np.where(pq == i)[0])
            elif i in branch_control_bus:
                brctrl = np.where(branch_control_bus == i)[0]
                for j in brctrl:    # in case there are more than one
                    if branch_control_mode_m[j] == TapModuleControl.Vm:
                        #pqv = np.append(pqv, np.array([i]))
                        pq = np.delete(pq, np.where(pq == i)[0])
                        i_m_vr = np.append(i_m_vr, np.array([i]))
                    else:
                        # branch is not controlling voltage
                        pass
            else:
                # this is a pq node
                pass

        # Check feasibility of PVR nodes. PV different to PVR
        # If a bus is controlled by more than one generator or branch, let's keep just one
        idx_i, idxcounts_i = np.unique(generator_control_bus, return_counts=True)   #
        idx_k, idxcounts_k = np.unique(branch_control_bus, return_counts=True)
        idx = np.unique(np.concatenate([idx_i, idx_k]))
        idxcounts = np.zeros(idx.shape[0], dtype=float)
        for t, i in enumerate(idx):
            appears_gen = idxcounts_i[np.where(idx_i == i)] if i in idx_i else np.array([0])
            appears_br = idxcounts_k[np.where(idx_k == i)] if i in idx_k else np.array([0])
            idxcounts[t] = appears_gen + appears_br

        if np.any(idxcounts > 1):
            # let's find those nodes controlled by more than one element
            for i in np.where(idxcounts > 1)[0]:
                nodecontrolled = idx[i]
                if nodecontrolled == -1:
                    continue   # No control
                generatorsconflict = generator_buses[np.where(generator_control_bus == nodecontrolled)[0]]
                branchesconflict = np.where(branch_control_bus == nodecontrolled)[0]
                # At this point it is known which generators and/or branches are controlling the same node
                # First, let's check if there is a generator connected to this node and controlling it
                if nodecontrolled in pv:
                    # imposing its own node and disabling the rest
                    generatorsconflict = np.delete(generatorsconflict,
                                                   np.where(generatorsconflict == nodecontrolled)[0])
                    # converting the rest of pvr nodes to pv nodes
                    if pvr.shape[0] > 0:
                        for g in generatorsconflict:
                            # delete it from pvr
                            pvr = np.delete(pvr, np.where(pvr == g)[0])
                            # converting this node as a pv node
                            pv = np.append(pv, np.array([g]))
                            # changing generator control bus to itself
                            generator_control_bus[np.where(generator_buses == g)[0]] = g
                            # changing types
                            types[g] = BusMode.PV.value
                    # disabling transformer voltage control in case there are any
                    if k_m_vr.shape[0] > 0:
                        for b in branchesconflict:
                            # delete it from k_m_vr
                            k_m_vr = np.delete(k_m_vr, np.where(k_m_vr == b)[0])
                            branch_control_mode_m[b] = TapModuleControl.fixed
                            # TODO: qué hacemos con el nudo to del transformador?
                # In case node is controlled just by pvr nodes
                elif nodecontrolled in generator_control_bus:
                    # let's select the first pvr node
                    n = generator_buses[np.where(generator_control_bus == nodecontrolled)[0]]
                    # keep the first pvr node and change the rest to pv
                    if n.shape[0] > 1:
                        if ref in n:
                            pass    # it is previously checked in numerical_circuit
                        else:
                            # delete them from pvr
                            pvr = np.delete(pvr, n[1:])
                            # converting these nodes as a pv node
                            pv = np.append(pv, n)
                            for g in n:
                                # changing generator control bus to itself
                                generator_control_bus[np.where(generator_buses == g)[0]] = g
                                # changing types
                                types[g] = BusMode.PV.value
                    else:
                        # the only PVR node keeps being PVR node
                        pass
                    # disabling transformer voltage control in case there are any
                    if k_m_vr.shape[0] > 0:
                        for b in branchesconflict:
                            # delete it from k_m_vr
                            k_m_vr = np.delete(k_m_vr, np.where(k_m_vr == b)[0])
                            branch_control_mode_m[b] = TapModuleControl.fixed
                            # TODO: qué hacemos con el nudo to del transformador?
                elif nodecontrolled in branch_control_bus:
                    # any node whose voltage is controlled by a transformer tap is pqv node
                    if nodecontrolled not in pqv:
                        pqv = np.append(pqv, np.array([nodecontrolled]))
                        i_m_vr = np.append(i_m_vr, np.array([nodecontrolled]))

                # Let's check if nodecontrolled is a pq node to convert it to pqv
                if nodecontrolled in pq:
                    pqv = np.append(pqv, np.array([nodecontrolled]))
                    pq = np.delete(pq, np.where(pq == nodecontrolled)[0])


        return ref, pq, pv, pvr, no_slack, pqv, k_m_vr, k_m_Qf, k_m_Qt, k_tau_Pf, k_tau_Pt, i_m_vr
    def recompile_types(self,
                        bus_types: IntVec,
                        Pbus: Vec):
        """

        :param bus_types:
        :param Pbus:
        :return:
        """
        self.bus_types = bus_types

        # determine the bus indices
        self.vd, self.pq, self.pv, self.no_slack = compile_types(Pbus=Pbus, types=bus_types)

    def compile_control_indices(self,
                                control_mode: List[Union[TransformerControlType, ConverterControlType]],
                                F: IntVec,
                                T: IntVec) -> None:
        """
        This function fills in the lists of indices to control different magnitudes

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
        k_pf_tau_lst = list()  # indices of the Branches controlling Pf flow with theta sh
        k_qf_m_lst = list()  # indices of the Branches controlling Qf with ma
        k_zero_beq_lst = list()  # indices of the Branches when forcing the Qf flow to zero (aka "the zero condition")
        k_vf_beq_lst = list()  # indices of the Branches when controlling Vf with Beq
        k_vt_m_lst = list()  # indices of the Branches when controlling Vt with ma
        k_qt_m_lst = list()  # indices of the Branches controlling the Qt flow with ma
        k_pf_dp_lst = list()  # indices of the drop converters controlling the power flow with theta sh
        k_m_modif_lst = list()  # indices of the transformers with controlled tap module
        k_tau_modif_lst = list()  # indices of the transformers with controlled tap angle
        k_mtau_modif_lst = list()  # indices of the transformers with controlled tap angle and module
        i_m_modif_lst = list()  # indices of the controlled buses with tap module
        i_tau_modif_lst = list()  # indices of the controlled buses with tap angle
        i_mtau_modif_lst = list()  # indices of the controlled buses with tap module and angle
        i_vsc_lst = list()  # indices of the converters
        iPfdp_va_lst = list()

        self.any_control = False

        for k, tpe in enumerate(control_mode):

            if tpe == TransformerControlType.fixed:
                pass

            elif tpe == TransformerControlType.Pf:  # TODO: change name .Pt by .Pf
                k_pf_tau_lst.append(k)
                k_tau_modif_lst.append(k)
                i_tau_modif_lst.append(F[k])  # TODO: identify which index is the controlled one
                self.any_control = True

            elif tpe == TransformerControlType.Qt:
                k_qt_m_lst.append(k)
                k_m_modif_lst.append(k)
                i_m_modif_lst.append(T[k])
                self.any_control = True

            elif tpe == TransformerControlType.PtQt:
                k_pf_tau_lst.append(k)
                k_qt_m_lst.append(k)
                k_m_modif_lst.append(k)
                k_tau_modif_lst.append(k)
                k_mtau_modif_lst.append(k)
                i_tau_modif_lst.append(F[k])
                i_m_modif_lst.append(T[k])
                self.any_control = True

            elif tpe == TransformerControlType.V:
                k_vt_m_lst.append(k)
                k_m_modif_lst.append(k)
                i_m_modif_lst.append(T[k])
                self.any_control = True

            elif tpe == TransformerControlType.PtV:
                k_pf_tau_lst.append(k)
                k_vt_m_lst.append(k)
                k_m_modif_lst.append(k)
                k_tau_modif_lst.append(k)
                k_mtau_modif_lst.append(k)
                i_tau_modif_lst.append(F[k])
                i_m_modif_lst.append(T[k])
                self.any_control = True

            # VSC ------------------------------------------------------------------------------------------------------
            elif tpe == ConverterControlType.type_0_free:  # 1a:Free
                k_zero_beq_lst.append(k)
                i_vsc_lst.append(k)
                self.any_control = True

            elif tpe == ConverterControlType.type_I_1:  # 1:Vac
                k_vt_m_lst.append(k)
                k_zero_beq_lst.append(k)
                i_vsc_lst.append(k)
                self.any_control = True

            elif tpe == ConverterControlType.type_I_2:  # 2:Pdc+Qac

                k_pf_tau_lst.append(k)
                k_qt_m_lst.append(k)
                k_zero_beq_lst.append(k)

                i_vsc_lst.append(k)
                self.any_control = True

            elif tpe == ConverterControlType.type_I_3:  # 3:Pdc+Vac
                k_pf_tau_lst.append(k)
                k_vt_m_lst.append(k)
                k_zero_beq_lst.append(k)

                i_vsc_lst.append(k)
                self.any_control = True

            elif tpe == ConverterControlType.type_II_4:  # 4:Vdc+Qac
                k_vf_beq_lst.append(k)
                k_qt_m_lst.append(k)

                i_vsc_lst.append(k)
                self.any_control = True

            elif tpe == ConverterControlType.type_II_5:  # 5:Vdc+Vac
                k_vf_beq_lst.append(k)
                k_vt_m_lst.append(k)

                i_vsc_lst.append(k)
                self.any_control = True

            elif tpe == ConverterControlType.type_III_6:  # 6:Droop+Qac
                k_pf_dp_lst.append(k)
                k_qt_m_lst.append(k)

                i_vsc_lst.append(k)
                self.any_control = True

            elif tpe == ConverterControlType.type_III_7:  # 4a:Droop-slack
                k_pf_dp_lst.append(k)
                k_vt_m_lst.append(k)

                i_vsc_lst.append(k)
                self.any_control = True

            elif tpe == ConverterControlType.type_IV_I:  # 8:Vdc
                k_vf_beq_lst.append(k)
                i_vsc_lst.append(k)

                self.any_control = True

            elif tpe == ConverterControlType.type_IV_II:  # 9:Pdc
                k_pf_tau_lst.append(k)
                k_zero_beq_lst.append(k)

                self.any_control = True

            elif tpe == 0:
                pass  # required for the no-control case

            else:
                raise Exception('Unknown control type:' + str(tpe))

        # FUBM- Saves the "from" bus identifier for Vf controlled by Beq
        #  (Converters type II for Vdc control)
        self.i_vf_beq = F[k_vf_beq_lst]

        # FUBM- Saves the "to"   bus identifier for Vt controlled by ma
        #  (Converters and Transformers)
        self.i_vt_m = T[k_vt_m_lst]

        self.k_pf_tau = np.array(k_pf_tau_lst, dtype=int)
        self.k_qf_m = np.array(k_qf_m_lst, dtype=int)
        self.k_zero_beq = np.array(k_zero_beq_lst, dtype=int)
        self.k_vf_beq = np.array(k_vf_beq_lst, dtype=int)
        self.k_vt_m = np.array(k_vt_m_lst, dtype=int)
        self.k_qt_m = np.array(k_qt_m_lst, dtype=int)
        self.k_pf_dp = np.array(k_pf_dp_lst, dtype=int)
        self.k_m = np.array(k_m_modif_lst, dtype=int)
        self.k_tau = np.array(k_tau_modif_lst, dtype=int)
        self.k_mtau = np.array(k_mtau_modif_lst, dtype=int)
        self.i_m = np.array(i_m_modif_lst, dtype=int)
        self.i_tau = np.array(i_tau_modif_lst, dtype=int)
        self.i_mtau = np.array(i_mtau_modif_lst, dtype=int)
        self.iPfdp_va = np.array(iPfdp_va_lst, dtype=int)
        self.i_vsc = np.array(i_vsc_lst, dtype=int)

    def get_base_voltage(self, nbus, generator_data, battery_data, hvdc_data, branch_data):
        """
        GEt the voltage profile based on the devices control voltage
        :param nbus:
        :param generator_data:
        :param battery_data:
        :param hvdc_data:
        :param branch_data:
        :return:
        """
        return compose_generator_voltage_profile(
            nbus=nbus,
            gen_bus_indices=generator_data.get_bus_indices(),
            gen_vset=generator_data.v,
            gen_status=generator_data.active,
            gen_is_controlled=generator_data.controllable,
            bat_bus_indices=battery_data.get_bus_indices(),
            bat_vset=battery_data.v,
            bat_status=battery_data.active,
            bat_is_controlled=battery_data.controllable,
            hvdc_bus_f=hvdc_data.get_bus_indices_f(),
            hvdc_bus_t=hvdc_data.get_bus_indices_t(),
            hvdc_status=hvdc_data.active,
            hvdc_vf=hvdc_data.Vset_f,
            hvdc_vt=hvdc_data.Vset_t,
            k_vf_beq=self.k_vf_beq,
            k_vt_m=self.k_vt_m,
            i_vf_beq=self.i_vf_beq,
            i_vt_m=self.i_vt_m,
            branch_status=branch_data.active,
            br_vf=branch_data.vf_set,
            br_vt=branch_data.vt_set
        )
