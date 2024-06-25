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
from GridCalEngine.enumerations import TransformerControlType, ConverterControlType, BusMode
from GridCalEngine.basic_structures import Vec, IntVec, BoolVec
from GridCalEngine.exceptions import ControlLengthError, ControlNotImplementedError


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
        """

        :param bus_types: Bus type initial guess array
        :param Pbus: Active power per bus array
        :param control_mode: Branch control mode array
        :param F: Array of bus_from indices
        :param T: Array of bus_to indices
        :param dc: Arra of is DC ? per bus
        """
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


class SimulationIndices2:
    """
    Class to handle the simulation indices
    """

    def __init__(self,
                 bus_types: IntVec,
                 Pbus: Vec,
                 control_mode: List[Union[TransformerControlType, ConverterControlType]],
                 F: IntVec,
                 T: IntVec,
                 dc: IntVec,
                 dc_bus: BoolVec,
                 gen_data,
                 vsc_data,
                 bus_data,
                 adj,
                 idx_islands,
                 Sbase):
        """

        :param bus_types: Bus type initial guess array
        :param Pbus: Active power per bus array
        :param control_mode: Branch control mode array
        :param F: Array of bus_from indices
        :param T: Array of bus_to indices
        :param dc: Arra of is DC ? per bus
        """
        # master aray of bus types (nbus)
        self.bus_types = bus_types

        # master array of branch control types (nbr)
        self.control_mode = control_mode

        # AC and DC indices
        self.ac: IntVec = np.where(dc_bus == False)[0]
        self.dc: IntVec = np.where(dc_bus != False)[0]

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

        # (Generalised PF) indices of the buses where voltage is known (controlled)
        self.kn_volt_idx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF) indices of the buses where angle is known (controlled)
        self.kn_angle_idx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF) indices of the buses where Pzip is known (controlled)
        self.kn_pzip_idx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF) indices of the buses where Qzip is known (controlled)
        self.kn_qzip_idx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF) indices of the branches where Pfrom is known (controlled)
        self.kn_pfrom_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF) indices of the branches where Qfrom is known (controlled)
        self.kn_qfrom_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF) indices of the branches where Pto is known (controlled)
        self.kn_pto_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF) indices of the branches where Qto is known (controlled)
        self.kn_qto_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF) indices of the branches where tau is known (controlled)
        self.kn_tau_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF) indices of the branches where modulation is known (controlled)
        self.kn_mod_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF) indices of the passive branches where Pfrom are known (controlled)
        self.kn_passive_pfrom_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF) indices of the branches where Qfrom are known (controlled)
        self.kn_passive_qfrom_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF) indices of the branches where Pto are known (controlled)
        self.kn_passive_pto_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF) indices of the branches where Qto are known (controlled)
        self.kn_passive_qto_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF) setpoints of the buses where voltage is known (controlled)
        self.kn_volt_setpoints: Vec = np.zeros(0, dtype=float)

        # (Generalised PF) setpoints of the buses where angle is known (controlled)
        self.kn_angle_setpoints: Vec = np.zeros(0, dtype=float)

        # (Generalised PF) setpoints of the buses where Pzip is known (controlled)
        self.kn_pzip_setpoints: Vec = np.zeros(0, dtype=float)

        # (Generalised PF) setpoints of the buses where Qzip is known (controlled)
        self.kn_qzip_setpoints: Vec = np.zeros(0, dtype=float)

        # (Generalised PF) setpoints of the branches where Pfrom is known (controlled)
        self.kn_pfrom_setpoints: Vec = np.zeros(0, dtype=float)

        # (Generalised PF) setpoints of the branches where Qfrom is known (controlled)
        self.kn_qfrom_setpoints: Vec = np.zeros(0, dtype=float)

        # (Generalised PF) setpoints of the branches where Pto is known (controlled)
        self.kn_pto_setpoints: Vec = np.zeros(0, dtype=float)

        # (Generalised PF) setpoints of the branches where Qto is known (controlled)
        self.kn_qto_setpoints: Vec = np.zeros(0, dtype=float)

        # (Generalised PF) setpoints of the branches where tau is known (controlled)
        self.kn_tau_setpoints: Vec = np.zeros(0, dtype=float)

        # (Generalised PF) setpoints of the branches where modulation is known (controlled)
        self.kn_mod_setpoints: Vec = np.zeros(0, dtype=float)

        # (Generalised PF) setpoints of the passive branches where Pfrom are known (controlled)
        self.kn_passive_pfrom_setpoints: Vec = np.zeros(0, dtype=float)

        # (Generalised PF) setpoints of the branches where Qfrom are known (controlled)
        self.kn_passive_qfrom_setpoints: Vec = np.zeros(0, dtype=float)

        # (Generalised PF) setpoints of the branches where Pto are known (controlled)
        self.kn_passive_pto_setpoints: Vec = np.zeros(0, dtype=float)

        # (Generalised PF) setpoints of the branches where Qto are known (controlled)
        self.kn_passive_qto_setpoints: Vec = np.zeros(0, dtype=float)

        # (Generalised PF) indices of the buses where voltage is unknown
        self.un_volt_idx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF) indices of the buses where angle is unknown
        self.un_angle_idx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF) indices of the buses where Pzip is unknown
        self.un_pzip_idx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF) indices of the buses where Qzip is unknown
        self.un_qzip_idx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF) indices of the branches where Pfrom is unknown
        self.un_pfrom_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF) indices of the branches where Qfrom is unknown
        self.un_qfrom_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF) indices of the branches where Pto is unknown
        self.un_pto_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF) indices of the branches where Qto is unknown
        self.un_qto_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF) indices of the branches where tau is unknown
        self.un_tau_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF) indices of the branches where modulation is unknown
        self.un_mod_kdx: IntVec = np.zeros(0, dtype=int)

        # determine the bus indices
        self.vd, self.pq, self.pv, self.no_slack = compile_types(Pbus=Pbus, types=bus_types)

        # determine the branch indices
        self.compile_control_indices(control_mode=control_mode, F=F, T=T)

        # (Generalised PF) determine the indices and setpoints
        self.compile_control_indices_generalised_pf(Sbase, gen_data, vsc_data, bus_data, adj, idx_islands, verbose=1)

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

    def compile_control_indices_generalised_pf(self, Sbase, gen_data, vsc_data, bus_data, adj, idx_islands, verbose=0):
        # print("we have gen_data")
        # print("nelm")
        # print(gen_data.nelm)
        # print("nbus")
        # print(gen_data.nbus)
        # print("names")
        # print(gen_data.names)
        # print("idtag")
        # print(gen_data.idtag)
        # print("controllable")
        # print(gen_data.controllable)
        # print("installed_p")
        # print(gen_data.installed_p)

        # print("isActive")
        # print(gen_data.active)
        # print("p")
        # print(gen_data.p)
        # print("pf")
        # print(gen_data.pf)
        # print("v")
        # print(gen_data.v)

        # print("mttf")
        # print(gen_data.mttf)
        # print("mttr")
        # print(gen_data.mttr)

        # print("C_bus_elm")
        # print(gen_data.C_bus_elm)

        # print("r0")
        # print(gen_data.r0)
        # print("r1")
        # print(gen_data.r1)
        # print("r2")
        # print(gen_data.r2)

        # print("x0")
        # print(gen_data.x0)
        # print("x1")
        # print(gen_data.x1)
        # print("x2")
        # print(gen_data.x2)

        # print("dispatchable")
        # print(gen_data.dispatchable)
        # print("pmax")
        # print(gen_data.pmax)
        # print("pmin")
        # print(gen_data.pmin)

        # print("cost_1")
        # print(gen_data.cost_1)
        # print("cost_0")
        # print(gen_data.cost_0)
        # print("cost_2")
        # print(gen_data.cost_2)
        # print("startup_cost")
        # print(gen_data.startup_cost)
        # print("availability")
        # print(gen_data.availability)
        # print("ramp_up")
        # print(gen_data.ramp_up)
        # print("ramp_down")
        # print(gen_data.ramp_down)
        # print("min_time_up")
        # print(gen_data.min_time_up)
        # print("min_time_down")
        # print(gen_data.min_time_down)

        # print("original_idx")
        # print(gen_data.original_idx)

        # print("we have vsc_data")
        # print("vsc_data.nbus",vsc_data.nbus)
        # print("vsc_data.nelm",vsc_data.nelm)

        # get the number of ac buses
        ac_buses = self.ac
        num_ac_buses = len(ac_buses)

        # get the number of dc buses
        dc_buses = self.dc
        num_dc_buses = len(dc_buses)

        # get the number of vscs
        num_vsc = vsc_data.nelm

        # get the number of transformers
        num_trafo = 0

        total = num_ac_buses * 2 + num_dc_buses + num_vsc + num_trafo * 4

        if verbose:
            import prettytable as pt
            table = pt.PrettyTable()
            table.field_names = ["Type", "Number of Instances", "Number of Equations"]
            table.add_row(["AC Bus", num_ac_buses, num_ac_buses * 2])
            table.add_row(["DC Bus", num_dc_buses, num_dc_buses])
            table.add_row(["VSC", num_vsc, num_vsc])
            table.add_row(["Controllable Trafo", num_trafo, num_trafo * 4])
            table.add_row(["Total", "", total])
            print(table)

        dict_known_idx = {
            "Voltage": self.kn_volt_idx,
            "Angle": self.kn_angle_idx,
            "Pzip": self.kn_pzip_idx,
            "Qzip": self.kn_qzip_idx,
            "Pfrom": self.kn_pfrom_kdx,
            "Pto": self.kn_pto_kdx,
            "Qfrom": self.kn_qfrom_kdx,
            "Qto": self.kn_qto_kdx,
            "Modulation": self.kn_mod_kdx,
            "Tau": self.kn_tau_kdx
        }

        dict_known_setpoints = {
            "Voltage": self.kn_volt_setpoints,
            "Angle": self.kn_angle_setpoints,
            "Pzip": self.kn_pzip_setpoints,
            "Qzip": self.kn_qzip_setpoints,
            "Pfrom": self.kn_pfrom_setpoints,
            "Pto": self.kn_pto_setpoints,
            "Qfrom": self.kn_qfrom_setpoints,
            "Qto": self.kn_qto_setpoints,
            "Modulation": self.kn_mod_setpoints,
            "Tau": self.kn_tau_setpoints
        }

        dict_unknown_idx = {
            "Voltage": self.un_volt_idx,
            "Angle": self.un_angle_idx,
            "Pzip": self.un_pzip_idx,
            "Qzip": self.un_qzip_idx,
            "Pfrom": self.un_pfrom_kdx,
            "Pto": self.un_pto_kdx,
            "Qfrom": self.un_qfrom_kdx,
            "Qto": self.un_qto_kdx,
            "Modulation": self.un_mod_kdx,
            "Tau": self.un_tau_kdx
        }

        for bus in self.ac:
            dict_unknown_idx["Voltage"] = np.append(dict_unknown_idx["Voltage"], bus)
            dict_unknown_idx["Angle"] = np.append(dict_unknown_idx["Angle"], bus)
            dict_known_idx["Pzip"] = np.append(dict_known_idx["Pzip"], bus)
            dict_known_idx["Qzip"] = np.append(dict_known_idx["Qzip"], bus)
            dict_known_setpoints["Pzip"] = np.append(dict_known_setpoints["Pzip"], 0)
            dict_known_setpoints["Qzip"] = np.append(dict_known_setpoints["Qzip"], 0)

        for bus in self.dc:
            dict_unknown_idx["Voltage"] = np.append(dict_unknown_idx["Voltage"], bus)
            dict_known_idx["Pzip"] = np.append(dict_known_idx["Pzip"], bus)
            dict_known_setpoints["Pzip"] = np.append(dict_known_setpoints["Pzip"], 0)

        for bus in gen_data.bus_idx:
            if bus in self.ac:
                dict_unknown_idx["Pzip"] = np.append(dict_unknown_idx["Pzip"], bus)
                dict_unknown_idx["Qzip"] = np.append(dict_unknown_idx["Qzip"], bus)
                _popIdx = np.where(dict_known_idx["Pzip"] == bus)
                dict_known_setpoints["Pzip"] = np.delete(dict_known_setpoints["Pzip"], _popIdx)
                dict_known_setpoints["Qzip"] = np.delete(dict_known_setpoints["Qzip"], _popIdx)
                dict_known_idx["Pzip"] = np.delete(dict_known_idx["Pzip"], _popIdx)
                dict_known_idx["Qzip"] = np.delete(dict_known_idx["Qzip"], _popIdx)

            else:
                dict_unknown_idx["Pzip"] = np.append(dict_unknown_idx["Pzip"], bus)
                _popIdx = np.where(dict_known_idx["Pzip"] == bus)
                dict_known_setpoints["Pzip"] = np.delete(dict_known_setpoints["Pzip"], _popIdx)
                dict_known_idx["Pzip"] = np.delete(dict_known_idx["Pzip"], _popIdx)

        for vsc_idx in range(num_vsc):
            assert vsc_data.F[vsc_idx] in self.dc
            assert vsc_data.T[vsc_idx] in self.ac
            dict_unknown_idx["Pfrom"] = np.append(dict_unknown_idx["Pfrom"], vsc_data.branch_index[vsc_idx])
            dict_unknown_idx["Pto"] = np.append(dict_unknown_idx["Pto"], vsc_data.branch_index[vsc_idx])
            dict_unknown_idx["Qto"] = np.append(dict_unknown_idx["Qto"], vsc_data.branch_index[vsc_idx])

        for trafo_idx in range(num_trafo):
            # controllable Trafo not supported yet
            pass

        # Set the "control modes" for generators
        for bus in gen_data.bus_idx:
            # grab the voltage setpoint
            _setpoint = gen_data.v[gen_data.bus_idx == bus]
            print("bus here has a generator", bus)
            print("its voltage setpoint is", _setpoint)
            print("its active power setpoint is", gen_data.p[gen_data.bus_idx == bus])
            print("power factor is at", gen_data.pf[gen_data.bus_idx == bus])

            # We assume for the time being that all generators set the voltage
            _popIdx = np.where(dict_unknown_idx["Voltage"] == bus)
            dict_unknown_idx["Voltage"] = np.delete(dict_unknown_idx["Voltage"], _popIdx)
            dict_known_idx["Voltage"] = np.append(dict_known_idx["Voltage"], bus)
            dict_known_setpoints["Voltage"] = np.append(dict_known_setpoints["Voltage"], _setpoint)

            # We are going to use the slack array to determine the control mode (which means that you must set slack yourself)
            if bus_data.bus_types[bus] == BusMode.Slack.value:  # Slack bus
                # We set the angle
                _popIdx = np.where(dict_unknown_idx["Angle"] == bus)
                dict_unknown_idx["Angle"] = np.delete(dict_unknown_idx["Angle"], _popIdx)
                dict_known_idx["Angle"] = np.append(dict_known_idx["Angle"], bus)
                dict_known_setpoints["Angle"] = np.append(dict_known_setpoints["Angle"], 0)

            else:
                # We set the active power
                _popIdx = np.where(dict_unknown_idx["Pzip"] == bus)
                dict_unknown_idx["Pzip"] = np.delete(dict_unknown_idx["Pzip"], _popIdx)
                dict_known_idx["Pzip"] = np.append(dict_known_idx["Pzip"], bus)
                rawPower = gen_data.p[gen_data.bus_idx == bus]
                puPower = rawPower / Sbase
                dict_known_setpoints["Pzip"] = np.append(dict_known_setpoints["Pzip"], puPower)

        # Set the "control modes" for VSCs (we do it one by one because I dont know the order of the control_modes array)
        for vsc_idx in range(num_vsc):
            # print("vsc number", vsc_idx)
            # print("from bus", vsc_data.F[vsc_idx])
            # print("to bus", vsc_data.T[vsc_idx])
            # print("branch number", vsc_data.branch_index[vsc_idx])
            # print("control mode", vsc_data.control_mode[vsc_idx])

            # Check if the control mode is valid
            control_mode = vsc_data.control_mode[vsc_idx]
            self.check_control_modes(control_mode)

            # We set the controls for the acceptable control modes
            if control_mode == ConverterControlType.type_I_2:  # 2:Pdc+Qac
                self.any_control = True

                _popIdx = np.where(dict_unknown_idx["Pfrom"] == vsc_data.branch_index[vsc_idx])
                dict_unknown_idx["Pfrom"] = np.delete(dict_unknown_idx["Pfrom"], _popIdx)
                dict_known_idx["Pfrom"] = np.append(dict_known_idx["Pfrom"], vsc_data.branch_index[vsc_idx])
                dict_known_setpoints["Pfrom"] = np.append(dict_known_setpoints["Pfrom"], vsc_data.Pdc_set[vsc_idx])

                _popIdx = np.where(dict_unknown_idx["Qto"] == vsc_data.branch_index[vsc_idx])
                dict_unknown_idx["Qto"] = np.delete(dict_unknown_idx["Qto"], _popIdx)
                dict_known_idx["Qto"] = np.append(dict_known_idx["Qto"], vsc_data.branch_index[vsc_idx])
                dict_known_setpoints["Qto"] = np.append(dict_known_setpoints["Qto"], vsc_data.Qac_set[vsc_idx])

            elif control_mode == ConverterControlType.type_I_3:  # 3:Pdc+Vac
                self.any_control = True

                _popIdx = np.where(dict_unknown_idx["Pfrom"] == vsc_data.branch_index[vsc_idx])
                dict_unknown_idx["Pfrom"] = np.delete(dict_unknown_idx["Pfrom"], _popIdx)
                dict_known_idx["Pfrom"] = np.append(dict_known_idx["Pfrom"], vsc_data.branch_index[vsc_idx])
                dict_known_setpoints["Pfrom"] = np.append(dict_known_setpoints["Pfrom"], vsc_data.Pdc_set[vsc_idx])

                _popIdx = np.where(dict_unknown_idx["Voltage"] == vsc_data.T[vsc_idx])
                dict_unknown_idx["Voltage"] = np.delete(dict_unknown_idx["Voltage"], _popIdx)
                dict_known_idx["Voltage"] = np.append(dict_known_idx["Voltage"], vsc_data.T[vsc_idx])
                dict_known_setpoints["Voltage"] = np.append(dict_known_setpoints["Voltage"], vsc_data.Vac_set[vsc_idx])

            elif control_mode == ConverterControlType.type_II_4:  # 4:Vdc+Qac
                self.any_control = True

                _popIdx = np.where(dict_unknown_idx["Voltage"] == vsc_data.F[vsc_idx])
                dict_unknown_idx["Voltage"] = np.delete(dict_unknown_idx["Voltage"], _popIdx)
                dict_known_idx["Voltage"] = np.append(dict_known_idx["Voltage"], vsc_data.F[vsc_idx])
                dict_known_setpoints["Voltage"] = np.append(dict_known_setpoints["Voltage"], vsc_data.Vdc_set[vsc_idx])

                _popIdx = np.where(dict_unknown_idx["Qto"] == vsc_data.branch_index[vsc_idx])
                dict_unknown_idx["Qto"] = np.delete(dict_unknown_idx["Qto"], _popIdx)
                dict_known_idx["Qto"] = np.append(dict_known_idx["Qto"], vsc_data.branch_index[vsc_idx])
                dict_known_setpoints["Qto"] = np.append(dict_known_setpoints["Qto"], vsc_data.Qac_set[vsc_idx])

            elif control_mode == ConverterControlType.type_II_5:  # 5:Vdc+Vac
                self.any_control = True

                _popIdx = np.where(dict_unknown_idx["Voltage"] == vsc_data.F[vsc_idx])
                dict_unknown_idx["Voltage"] = np.delete(dict_unknown_idx["Voltage"], _popIdx)
                dict_known_idx["Voltage"] = np.append(dict_known_idx["Voltage"], vsc_data.F[vsc_idx])
                dict_known_setpoints["Voltage"] = np.append(dict_known_setpoints["Voltage"], vsc_data.Vdc_set[vsc_idx])

                _popIdx = np.where(dict_unknown_idx["Voltage"] == vsc_data.T[vsc_idx])
                dict_unknown_idx["Voltage"] = np.delete(dict_unknown_idx["Voltage"], _popIdx)
                dict_known_idx["Voltage"] = np.append(dict_known_idx["Voltage"], vsc_data.T[vsc_idx])
                dict_known_setpoints["Voltage"] = np.append(dict_known_setpoints["Voltage"], vsc_data.Vac_set[vsc_idx])

        # use pretty table to print the above information
        if verbose == 1:
            table = pt.PrettyTable()
            table.field_names = ["Type", "Number of Unknowns"]
            table.add_row(["Voltage", len(dict_unknown_idx["Voltage"])])
            table.add_row(["Angle", len(dict_unknown_idx["Angle"])])
            table.add_row(["Pzip", len(dict_unknown_idx["Pzip"])])
            table.add_row(["Qzip", len(dict_unknown_idx["Qzip"])])
            table.add_row(["Pfrom", len(dict_unknown_idx["Pfrom"])])
            table.add_row(["Pto", len(dict_unknown_idx["Pto"])])
            table.add_row(["Qfrom", len(dict_unknown_idx["Qfrom"])])
            table.add_row(["Qto", len(dict_unknown_idx["Qto"])])
            table.add_row(["Modulation", len(dict_unknown_idx["Modulation"])])
            table.add_row(["Tau", len(dict_unknown_idx["Tau"])])
            table.add_row(["Total", len(dict_unknown_idx["Voltage"]) + len(dict_unknown_idx["Angle"]) + len(
                dict_unknown_idx["Pzip"]) + len(dict_unknown_idx["Qzip"]) + len(dict_unknown_idx["Pfrom"]) + len(
                dict_unknown_idx["Pto"]) + len(dict_unknown_idx["Qfrom"]) + len(dict_unknown_idx["Qto"]) + len(
                dict_unknown_idx["Modulation"]) + len(dict_unknown_idx["Tau"])])
            print(table)

        self.check_subsystem_slacks(idx_islands, dict_known_idx, bus_data, verbose=1, strict=1)

        self.kn_volt_idx = dict_known_idx["Voltage"]
        self.kn_angle_idx = dict_known_idx["Angle"]
        self.kn_pzip_idx = dict_known_idx["Pzip"]
        self.kn_qzip_idx = dict_known_idx["Qzip"]
        self.kn_pfrom_kdx = dict_known_idx["Pfrom"]
        self.kn_pto_kdx = dict_known_idx["Pto"]
        self.kn_qfrom_kdx = dict_known_idx["Qfrom"]
        self.kn_qto_kdx = dict_known_idx["Qto"]
        self.kn_mod_kdx = dict_known_idx["Modulation"]
        self.kn_tau_kdx = dict_known_idx["Tau"]

        self.kn_volt_setpoints = dict_known_setpoints["Voltage"]
        self.kn_angle_setpoints = dict_known_setpoints["Angle"]
        self.kn_pzip_setpoints = dict_known_setpoints["Pzip"]
        self.kn_qzip_setpoints = dict_known_setpoints["Qzip"]
        self.kn_pfrom_setpoints = dict_known_setpoints["Pfrom"]
        self.kn_pto_setpoints = dict_known_setpoints["Pto"]
        self.kn_qfrom_setpoints = dict_known_setpoints["Qfrom"]
        self.kn_qto_setpoints = dict_known_setpoints["Qto"]
        self.kn_mod_setpoints = dict_known_setpoints["Modulation"]
        self.kn_tau_setpoints = dict_known_setpoints["Tau"]

        self.un_volt_idx = dict_unknown_idx["Voltage"]
        self.un_angle_idx = dict_unknown_idx["Angle"]
        self.un_pzip_idx = dict_unknown_idx["Pzip"]
        self.un_qzip_idx = dict_unknown_idx["Qzip"]
        self.un_pfrom_kdx = dict_unknown_idx["Pfrom"]
        self.un_pto_kdx = dict_unknown_idx["Pto"]
        self.un_qfrom_kdx = dict_unknown_idx["Qfrom"]
        self.un_qto_kdx = dict_unknown_idx["Qto"]
        self.un_mod_kdx = dict_unknown_idx["Modulation"]
        self.un_tau_kdx = dict_unknown_idx["Tau"]

        return

    def check_subsystem_slacks(self, systems, dict_known_idx, bus_data, verbose=0, strict=0):
        subSystemSlacks = np.zeros(len(systems), dtype=bool)
        # initialise pretty table
        import prettytable as pt  # TODO: use pandas
        table = pt.PrettyTable()
        # add some headers
        table.field_names = ["System", "Slack Buses", "Remarks"]

        for i, system in enumerate(systems):
            isSlack = []
            isDC = False
            for busIndex in system:
                # get bus object from index using grid object
                if bus_data.is_dc[busIndex] == True:
                    if busIndex in dict_known_idx["Voltage"]:
                        isSlack.append(busIndex)
                else:
                    if busIndex in dict_known_idx["Voltage"] and busIndex in dict_known_idx["Angle"]:
                        isSlack.append(busIndex)

            # add the system to the table
            table.add_row([f"Subsystem {i + 1}", isSlack, "All good" if len(isSlack) == 1 else "No good"])
            # true is there is exactly one slack, false otherwise
            subSystemSlacks[i] = len(isSlack) == 1

        if verbose:
            print(table)

        if strict:
            # if adding up lengthwise does not equal the length of the buses, then assert an error
            assert sum(subSystemSlacks) == len(systems), "You do not have exactly one slack bus for each subsystem"

        return

    def check_control_modes(self, control_mode: List[Union[TransformerControlType, ConverterControlType]]):
        """
        Check if the control modes are valid
        :param control_mode:
        :return:
        """
        if control_mode is not None:
            if control_mode == ConverterControlType.type_0_free:
                raise ControlLengthError(controlmode=control_mode, length=0)

            if control_mode in [ConverterControlType.type_I_1, ConverterControlType.type_IV_I,
                                ConverterControlType.type_IV_II]:
                raise ControlLengthError(controlmode=control_mode, length=1)

            if control_mode in [ConverterControlType.type_III_6, ConverterControlType.type_III_7]:
                raise ControlNotImplementedError(controlmode=control_mode)

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
