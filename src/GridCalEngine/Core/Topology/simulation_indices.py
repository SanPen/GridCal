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
from GridCalEngine.basic_structures import Vec, IntVec


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
        self.pv: IntVec = np.zeros(0, dtype=int)
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

            elif tpe == TransformerControlType.Vt:
                k_vt_m_lst.append(k)
                k_m_modif_lst.append(k)
                i_m_modif_lst.append(T[k])
                self.any_control = True

            elif tpe == TransformerControlType.PtVt:
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
