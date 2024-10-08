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
import pandas as pd
from typing import Union, Tuple, List
from GridCalEngine.enumerations import TransformerControlType, ConverterControlType, BusMode, GpfControlType
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
                 controllable_trafo_data,
                 branch_data,
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

        # Generators at AC and DC indices
        self.gen_ac: IntVec = np.where(gen_data.is_at_dc_bus == False)[0]
        self.gen_dc: IntVec = np.where(gen_data.is_at_dc_bus != False)[0]

        # Lines AC or DC
        self.branch_ac: IntVec = np.where(branch_data.dc == False)[0]
        self.branch_dc: IntVec = np.where(branch_data.dc != False)[0]
        
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



        ###### Generalised PF 2 ######

        # (Generalised PF 2)  indices of the buses where voltage is known (controlled)
        self.gpf_kn_volt_idx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the buses where angle is known (controlled)
        self.gpf_kn_angle_idx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the GENERATORS, not buses, where Pzip is known (controlled)
        self.gpf_kn_pzip_gen_idx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the GENERATORS, not buses, where Qzip is known (controlled)
        self.gpf_kn_qzip_gen_idx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the VSCs where Pfrom is known (controlled)
        self.gpf_kn_pfrom_vsc_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the VSCs where Pto is known (controlled)
        self.gpf_kn_pto_vsc_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the VSCs where Qto is known (controlled)
        self.gpf_kn_qto_vsc_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the CONTROLLABLE TRAFOS where Pfrom is known (controlled)
        self.gpf_kn_pfrom_trafo_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the CONTROLLABLE TRAFOS where Pto is known (controlled)
        self.gpf_kn_pto_trafo_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the CONTROLLABLE TRAFOS where Qfrom is known (controlled)
        self.gpf_kn_qfrom_trafo_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the CONTROLLABLE TRAFOS where Qto is known (controlled)
        self.gpf_kn_qto_trafo_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the CONTROLLABLE TRAFOS where tap module is known (controlled)
        self.gpf_kn_mod_trafo_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the CONTROLLABLE TRAFOS where tap angle is known (controlled)
        self.gpf_kn_tau_trafo_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the passive branches where Pfrom are known (controlled)
        self.gpf_kn_pfrom_passive_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the branches where Qfrom are known (controlled)
        self.gpf_kn_qfrom_passive_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the branches where Pto are known (controlled)
        self.gpf_kn_pto_passive_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the branches where Qto are known (controlled)
        self.gpf_kn_qto_passive_kdx: IntVec = np.zeros(0, dtype=int)




        # (Generalised PF 2) SETPOINTS of the buses where voltage is known (controlled)
        self.gpf_kn_volt_setpoints: Vec = np.zeros(0, dtype=float)

        # (Generalised PF 2) SETPOINTS of the buses where angle is known (controlled)
        self.gpf_kn_angle_setpoints: Vec = np.zeros(0, dtype=float)

        # (Generalised PF 2) SETPOINTS of the GENERATORS, not buses, where Pzip is known (controlled)
        self.gpf_kn_pzip_gen_setpoints: Vec = np.zeros(0, dtype=float)

        # (Generalised PF 2) SETPOINTS of the GENERATORS, not buses, where Qzip is known (controlled)
        self.gpf_kn_qzip_gen_setpoints: Vec = np.zeros(0, dtype=float)

        # (Generalised PF 2) SETPOINTS of the VSCs where Pfrom is known (controlled)
        self.gpf_kn_pfrom_vsc_setpoints: Vec = np.zeros(0, dtype=float)

        # (Generalised PF 2) SETPOINTS of the VSCs where Pto is known (controlled)
        self.gpf_kn_pto_vsc_setpoints: Vec = np.zeros(0, dtype=float)

        # (Generalised PF 2) SETPOINTS of the VSCs where Qto is known (controlled)
        self.gpf_kn_qto_vsc_setpoints: Vec = np.zeros(0, dtype=float)

        # (Generalised PF 2) SETPOINTS of the CONTROLLABLE TRAFOS where Pfrom is known (controlled)
        self.gpf_kn_pfrom_trafo_setpoints: Vec = np.zeros(0, dtype=float)

        # (Generalised PF 2) SETPOINTS of the CONTROLLABLE TRAFOS where Pto is known (controlled)
        self.gpf_kn_pto_trafo_setpoints: Vec = np.zeros(0, dtype=float)

        # (Generalised PF 2) SETPOINTS of the CONTROLLABLE TRAFOS where Qfrom is known (controlled)
        self.gpf_kn_qfrom_trafo_setpoints: Vec = np.zeros(0, dtype=float)

        # (Generalised PF 2) SETPOINTS of the CONTROLLABLE TRAFOS where Qto is known (controlled)
        self.gpf_kn_qto_trafo_setpoints: Vec = np.zeros(0, dtype=float)

        # (Generalised PF 2) SETPOINTS of the CONTROLLABLE TRAFOS where tap module is known (controlled)
        self.gpf_kn_mod_trafo_setpoints: Vec = np.zeros(0, dtype=float)

        # (Generalised PF 2) SETPOINTS of the CONTROLLABLE TRAFOS where tap angle is known (controlled)
        self.gpf_kn_tau_trafo_setpoints: Vec = np.zeros(0, dtype=float)

        # (Generalised PF 2) SETPOINTS of the passive branches where Pfrom are known (controlled)
        self.gpf_kn_pfrom_passive_setpoints: Vec = np.zeros(0, dtype=float)

        # (Generalised PF 2) SETPOINTS of the branches where Qfrom are known (controlled)
        self.gpf_kn_qfrom_passive_setpoints: Vec = np.zeros(0, dtype=float)

        # (Generalised PF 2) SETPOINTS of the branches where Pto are known (controlled)
        self.gpf_kn_pto_passive_setpoints: Vec = np.zeros(0, dtype=float)

        # (Generalised PF 2) SETPOINTS of the branches where Qto are known (controlled)
        self.gpf_kn_qto_passive_setpoints: Vec = np.zeros(0, dtype=float)




        # (Generalised PF 2) indices of the buses where voltage is UNKNOWN
        self.gpf_un_volt_idx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the buses where angle is UNKNOWN
        self.gpf_un_angle_idx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the GENERATORS, not buses, where Pzip is UNKNOWN
        self.gpf_un_pzip_gen_idx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the GENERATORS, not buses, where Qzip is UNKNOWN
        self.gpf_un_qzip_gen_idx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the VSCs where Pfrom is UNKNOWN
        self.gpf_un_pfrom_vsc_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the VSCs where Pto is UNKNOWN
        self.gpf_un_pto_vsc_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the VSCs where Qto is UNKNOWN
        self.gpf_un_qto_vsc_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the CONTROLLABLE TRAFOS where Pfrom is UNKNOWN
        self.gpf_un_pfrom_trafo_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the CONTROLLABLE TRAFOS where Pto is UNKNOWN
        self.gpf_un_pto_trafo_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the CONTROLLABLE TRAFOS where Qfrom is UNKNOWN
        self.gpf_un_qfrom_trafo_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the CONTROLLABLE TRAFOS where Qto is UNKNOWN
        self.gpf_un_qto_trafo_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the CONTROLLABLE TRAFOS where tap module is UNKNOWN
        self.gpf_un_mod_trafo_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the CONTROLLABLE TRAFOS where tap angle is UNKNOWN
        self.gpf_un_tau_trafo_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the PASSIVE BRANCHES where Pfrom are UNKNOWN
        self.gpf_un_pfrom_passive_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the PASSIVE BRANCHES where Qfrom are UNKNOWN
        self.gpf_un_qfrom_passive_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the PASSIVE BRANCHES where Pto are UNKNOWN
        self.gpf_un_pto_passive_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the PASSIVE BRANCHES where Qto are UNKNOWN
        self.gpf_un_qto_passive_kdx: IntVec = np.zeros(0, dtype=int)

        self.Sbase = Sbase
        self.adj = adj
        self.idx_islands = idx_islands

        self.gen_data = gen_data
        self.vsc_data = vsc_data
        self.bus_data = bus_data
        self.controllable_trafo_data = controllable_trafo_data
        self.branch_data = branch_data


        # determine the bus indices
        self.vd, self.pq, self.pv, self.no_slack = compile_types(Pbus=Pbus, types=bus_types)

        # determine the branch indices
        self.compile_control_indices(control_mode=control_mode, F=F, T=T)

        
        # #GENERALISED PF: quick fix, when pure AC system, run the old one.
        # if len(self.dc) == 0:
        #     # (Generalised PF) determine the indices and setpoints
        #     self.compile_control_indices_generalised_pf(Sbase, gen_data, vsc_data, bus_data, adj, idx_islands, verbose = 1)

        # else:
            # (Generalised PF 2) determine the indices and setpoints 
        self.compile_control_indices_generalised_pf2(Sbase, gen_data, vsc_data, bus_data, controllable_trafo_data, branch_data, adj, idx_islands, verbose = 1)

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

    def compile_control_indices_generalised_pf2(self, Sbase, gen_data, vsc_data, bus_data, controllable_trafo_data, branch_data, adj, idx_islands, verbose = 1):
        print("(simulation_indices.py) compile_control_indices_generalised_pf2")

        # for the buses we do this, thats fine, now we do the generators
        self.gpf_un_volt_idx = np.append(self.gpf_un_volt_idx, self.ac)
        self.gpf_un_volt_idx = np.append(self.gpf_un_volt_idx, self.dc)
        self.gpf_un_angle_idx = np.append(self.gpf_un_angle_idx, self.ac)

        #for the generators
        self.gpf_un_pzip_gen_idx = np.append(self.gpf_un_pzip_gen_idx, self.gen_ac)
        self.gpf_un_pzip_gen_idx = np.append(self.gpf_un_pzip_gen_idx, self.gen_dc)
        self.gpf_un_qzip_gen_idx = np.append(self.gpf_un_qzip_gen_idx, self.gen_ac)
  
        self.gpf_un_pfrom_vsc_kdx = np.append(self.gpf_un_pfrom_vsc_kdx, np.arange(vsc_data.nelm))
        self.gpf_un_pto_vsc_kdx = np.append(self.gpf_un_pto_vsc_kdx, np.arange(vsc_data.nelm))
        self.gpf_un_qto_vsc_kdx = np.append(self.gpf_un_qto_vsc_kdx, np.arange(vsc_data.nelm))

        #for the controllable trafos
        self.gpf_un_pfrom_trafo_kdx = np.append(self.gpf_un_pfrom_trafo_kdx, np.arange(controllable_trafo_data.nelm))
        self.gpf_un_pto_trafo_kdx = np.append(self.gpf_un_pto_trafo_kdx, np.arange(controllable_trafo_data.nelm))
        self.gpf_un_qfrom_trafo_kdx = np.append(self.gpf_un_qfrom_trafo_kdx, np.arange(controllable_trafo_data.nelm))
        self.gpf_un_qto_trafo_kdx = np.append(self.gpf_un_qto_trafo_kdx, np.arange(controllable_trafo_data.nelm))
        self.gpf_un_mod_trafo_kdx = np.append(self.gpf_un_mod_trafo_kdx, np.arange(controllable_trafo_data.nelm))
        self.gpf_un_tau_trafo_kdx = np.append(self.gpf_un_tau_trafo_kdx, np.arange(controllable_trafo_data.nelm))

        #lets iterate through all the controls now starting from the controls we get from the generators
        for k in range(gen_data.nelm):
            if k in self.gen_ac:
                #print the size of self.gen_ac
                # print("gen_ac: ", len(self.gen_ac))
                self.check_control_type(gen_data.gpf_ctrl1_mode[k], gen_data.gpf_ctrl1_elm[k], gen_data.gpf_ctrl1_val[k], gen_data.names[k])
                self.check_control_type(gen_data.gpf_ctrl2_mode[k], gen_data.gpf_ctrl2_elm[k], gen_data.gpf_ctrl2_val[k], gen_data.names[k])
            else:
                self.check_control_type(gen_data.gpf_ctrl1_mode[k], gen_data.gpf_ctrl1_elm[k], gen_data.gpf_ctrl1_val[k], gen_data.names[k])

        #lets iterate through all the controls now starting from the controls we get from the VSCs
        for k in range(vsc_data.nelm):
            self.check_control_type(vsc_data.gpf_ctrl1_mode[k], vsc_data.gpf_ctrl1_elm[k], vsc_data.gpf_ctrl1_val[k], vsc_data.names[k])
            self.check_control_type(vsc_data.gpf_ctrl2_mode[k], vsc_data.gpf_ctrl2_elm[k], vsc_data.gpf_ctrl2_val[k], vsc_data.names[k])

        #lets iterate through all the controls now starting from the controls we get from the controllable trafos
        for k in range(controllable_trafo_data.nelm):
            self.check_control_type(controllable_trafo_data.gpf_ctrl1_mode[k], controllable_trafo_data.gpf_ctrl1_elm[k], controllable_trafo_data.gpf_ctrl1_val[k], controllable_trafo_data.names[k])
            self.check_control_type(controllable_trafo_data.gpf_ctrl2_mode[k], controllable_trafo_data.gpf_ctrl2_elm[k], controllable_trafo_data.gpf_ctrl2_val[k], controllable_trafo_data.names[k])


        dict_known_idx = {"Voltage": self.gpf_kn_volt_idx, "Angle": self.gpf_kn_angle_idx}
        self.check_subsystem_slacks(idx_islands, dict_known_idx, bus_data, verbose = 1, strict = 1)
        self.check_unknowns_vs_equations(verbose = 1)
    

    def check_unknowns_vs_equations(self, verbose = 1):
        if verbose:
            # Create a dictionary with the data
            data = {
                "Type": ["AC Bus", "DC Bus", "VSC", "Controllable Trafo", "Total"],
                "Number of Instances": [len(self.ac), len(self.dc), self.vsc_data.nelm, self.controllable_trafo_data.nelm, ""],
                "Number of Equations": [len(self.ac)*2, len(self.dc), (self.vsc_data.nelm)*3, (self.controllable_trafo_data.nelm)*4, len(self.ac)*2 + len(self.dc) + (self.vsc_data.nelm) + (self.controllable_trafo_data.nelm)*4]
            }

            # Create the DataFrame
            df = pd.DataFrame(data)

            # Print the DataFrame
            print(df)


        if verbose == 1:
            # Initialize the data for the DataFrame
            data = {
                "Type": ["Voltage", "Angle", "Pzip Gen", "Qzip Gen", "Pfrom VSC", "Pto VSC", "Qto VSC", "Pfrom Trafo", "Pto Trafo", "Qfrom Trafo" , "Qto Trafo", "Modulation Trafo", "Tau Trafo", "Pfrom Passive", "Qfrom Passive", "Pto Passive", "Qto Passive", "Total"],
                "Number of Unknowns": [
                    len(self.gpf_un_volt_idx),
                    len(self.gpf_un_angle_idx),
                     len(self.gpf_un_pzip_gen_idx),
                     len(self.gpf_un_qzip_gen_idx),
                     len(self.gpf_un_pfrom_vsc_kdx),
                     len(self.gpf_un_pto_vsc_kdx),
                     len(self.gpf_un_qto_vsc_kdx),
                     len(self.gpf_un_pfrom_trafo_kdx),
                     len(self.gpf_un_pto_trafo_kdx),
                     len(self.gpf_un_qfrom_trafo_kdx),
                     len(self.gpf_un_qto_trafo_kdx),
                     len(self.gpf_un_mod_trafo_kdx),
                     len(self.gpf_un_tau_trafo_kdx),
                        len(self.gpf_un_pfrom_passive_kdx),
                        len(self.gpf_un_qfrom_passive_kdx),
                        len(self.gpf_un_pto_passive_kdx),
                        len(self.gpf_un_qto_passive_kdx),
                     len(self.gpf_un_volt_idx) + len(self.gpf_un_angle_idx) + len(self.gpf_un_pzip_gen_idx) + len(self.gpf_un_qzip_gen_idx) + len(self.gpf_un_pfrom_vsc_kdx) + len(self.gpf_un_pto_vsc_kdx) + len(self.gpf_un_qto_vsc_kdx) + len(self.gpf_un_pfrom_trafo_kdx) + len(self.gpf_un_pto_trafo_kdx) + len(self.gpf_un_qfrom_trafo_kdx) + len(self.gpf_un_qto_trafo_kdx) + len(self.gpf_un_mod_trafo_kdx) + len(self.gpf_un_tau_trafo_kdx)]
            }

            # Create the DataFrame
            df = pd.DataFrame(data)

            # Print the DataFrame
            print(df)
            
    def check_control_type(self, control_mode, elm_name, control_setpoint, master_name):
        elm_index = None
        if elm_name in self.bus_data.name_to_idx.keys():
            elm_index = self.bus_data.name_to_idx[elm_name]
            if elm_index in self.ac:
                assert control_mode == GpfControlType.type_Va or control_mode == GpfControlType.type_Vm, f"{master_name} is specifiying {control_mode} for {elm_name}. Control mode for AC bus must be either Va or Vm"
            else:
                assert control_mode == GpfControlType.type_Vm, f"{master_name} is specifiying {control_mode} for {elm_name}. Control mode for DC bus can only be Vm"

            if control_mode == GpfControlType.type_Vm:
                self.gpf_kn_volt_idx = np.append(self.gpf_kn_volt_idx, elm_index)
                self.gpf_kn_volt_setpoints = np.append(self.gpf_kn_volt_setpoints, control_setpoint)
                self.gpf_un_volt_idx = np.delete(self.gpf_un_volt_idx, np.where(self.gpf_un_volt_idx == elm_index))

            elif control_mode == GpfControlType.type_Va:
                self.gpf_kn_angle_idx = np.append(self.gpf_kn_angle_idx, elm_index)
                self.gpf_kn_angle_setpoints = np.append(self.gpf_kn_angle_setpoints, control_setpoint)
                self.gpf_un_angle_idx = np.delete(self.gpf_un_angle_idx, np.where(self.gpf_un_angle_idx == elm_index))

            else:
                raise ValueError(f"Control mode {control_mode} not supported")
            
        elif elm_name in self.gen_data.name_to_idx.keys():
            elm_index = self.gen_data.name_to_idx[elm_name]
            if elm_index in self.gen_ac:
                assert control_mode == GpfControlType.type_Pzip or control_mode == GpfControlType.type_Qzip, f"{master_name} is specifiying {control_mode} for {elm_name}. Control mode for AC generator must be either Pzip or Qzip"
            else:
                assert control_mode == GpfControlType.type_Pzip, f"{master_name} is specifiying {control_mode} for {elm_name}. Control mode for DC generator can only be Pzip"

            if control_mode == GpfControlType.type_Pzip:
                self.gpf_kn_pzip_gen_idx = np.append(self.gpf_kn_pzip_gen_idx, elm_index)
                self.gpf_kn_pzip_gen_setpoints = np.append(self.gpf_kn_pzip_gen_setpoints, control_setpoint)
                self.gpf_un_pzip_gen_idx = np.delete(self.gpf_un_pzip_gen_idx, np.where(self.gpf_un_pzip_gen_idx == elm_index))

            elif control_mode == GpfControlType.type_Qzip:
                self.gpf_kn_qzip_gen_idx = np.append(self.gpf_kn_qzip_gen_idx, elm_index)
                self.gpf_kn_qzip_gen_setpoints = np.append(self.gpf_kn_qzip_gen_setpoints, control_setpoint)
                self.gpf_un_qzip_gen_idx = np.delete(self.gpf_un_qzip_gen_idx, np.where(self.gpf_un_qzip_gen_idx == elm_index))

        elif elm_name in self.vsc_data.name_to_idx.keys():
            elm_index = self.vsc_data.name_to_idx[elm_name]
            assert control_mode == GpfControlType.type_Pf or control_mode == GpfControlType.type_Pt or control_mode == GpfControlType.type_Qt, f"VSC {master_name} is specifiying {control_mode} for {elm_name}. Control mode for VSC must be either Pf or Pt or Qt"

            if control_mode == GpfControlType.type_Pf:
                self.gpf_kn_pfrom_vsc_kdx = np.append(self.gpf_kn_pfrom_vsc_kdx, elm_index)
                self.gpf_kn_pfrom_vsc_setpoints = np.append(self.gpf_kn_pfrom_vsc_setpoints, control_setpoint)
                self.gpf_un_pfrom_vsc_kdx = np.delete(self.gpf_un_pfrom_vsc_kdx, np.where(self.gpf_un_pfrom_vsc_kdx == elm_index))

            elif control_mode == GpfControlType.type_Pt:
                self.gpf_kn_pto_vsc_kdx = np.append(self.gpf_kn_pto_vsc_kdx, elm_index)
                self.gpf_kn_pto_vsc_setpoints = np.append(self.gpf_kn_pto_vsc_setpoints, control_setpoint)
                self.gpf_un_pto_vsc_kdx = np.delete(self.gpf_un_pto_vsc_kdx, np.where(self.gpf_un_pto_vsc_kdx == elm_index))

            elif control_mode == GpfControlType.type_Qt:
                self.gpf_kn_qto_vsc_kdx = np.append(self.gpf_kn_qto_vsc_kdx, elm_index)
                self.gpf_kn_qto_vsc_setpoints = np.append(self.gpf_kn_qto_vsc_setpoints, control_setpoint)
                self.gpf_un_qto_vsc_kdx = np.delete(self.gpf_un_qto_vsc_kdx, np.where(self.gpf_un_qto_vsc_kdx == elm_index))

            else:
                raise ValueError(f"Control mode {control_mode} not supported")

        elif elm_name in self.controllable_trafo_data.name_to_idx.keys():
            elm_index = self.controllable_trafo_data.name_to_idx[elm_name]
            assert control_mode == GpfControlType.type_Pf or control_mode == GpfControlType.type_Pt or control_mode == GpfControlType.type_Qf or control_mode == GpfControlType.type_Qt or control_mode == GpfControlType.type_TapMod or control_mode == GpfControlType.type_TapAng, f"{master_name} is specifiying {control_mode} for {elm_name}. Control mode for controllable trafo must be either Pf or Pt or Qf or Qt or mod or tau"

            if control_mode == GpfControlType.type_Pf:
                self.gpf_kn_pfrom_trafo_kdx = np.append(self.gpf_kn_pfrom_trafo_kdx, elm_index)
                self.gpf_kn_pfrom_trafo_setpoints = np.append(self.gpf_kn_pfrom_trafo_setpoints, control_setpoint)
                self.gpf_un_pfrom_trafo_kdx = np.delete(self.gpf_un_pfrom_trafo_kdx, np.where(self.gpf_un_pfrom_trafo_kdx == elm_index))
            
            elif control_mode == GpfControlType.type_Pt:
                self.gpf_kn_pto_trafo_kdx = np.append(self.gpf_kn_pto_trafo_kdx, elm_index)
                self.gpf_kn_pto_trafo_setpoints = np.append(self.gpf_kn_pto_trafo_setpoints, control_setpoint)
                self.gpf_un_pto_trafo_kdx = np.delete(self.gpf_un_pto_trafo_kdx, np.where(self.gpf_un_pto_trafo_kdx == elm_index))

            elif control_mode == GpfControlType.type_Qf:
                self.gpf_kn_qfrom_trafo_kdx = np.append(self.gpf_kn_qfrom_trafo_kdx, elm_index)
                self.gpf_kn_qfrom_trafo_setpoints = np.append(self.gpf_kn_qfrom_trafo_setpoints, control_setpoint)
                self.gpf_un_qfrom_trafo_kdx = np.delete(self.gpf_un_qfrom_trafo_kdx, np.where(self.gpf_un_qfrom_trafo_kdx == elm_index))

            elif control_mode == GpfControlType.type_Qt:
                self.gpf_kn_qto_trafo_kdx = np.append(self.gpf_kn_qto_trafo_kdx, elm_index)
                self.gpf_kn_qto_trafo_setpoints = np.append(self.gpf_kn_qto_trafo_setpoints, control_setpoint)
                self.gpf_un_qto_trafo_kdx = np.delete(self.gpf_un_qto_trafo_kdx, np.where(self.gpf_un_qto_trafo_kdx == elm_index))

            elif control_mode == GpfControlType.type_TapMod:
                self.gpf_kn_mod_trafo_kdx = np.append(self.gpf_kn_mod_trafo_kdx, elm_index)
                self.gpf_kn_mod_trafo_setpoints = np.append(self.gpf_kn_mod_trafo_setpoints, control_setpoint)
                self.gpf_un_mod_trafo_kdx = np.delete(self.gpf_un_mod_trafo_kdx, np.where(self.gpf_un_mod_trafo_kdx == elm_index))

            elif control_mode == GpfControlType.type_TapAng:
                self.gpf_kn_tau_trafo_kdx = np.append(self.gpf_kn_tau_trafo_kdx, elm_index)
                self.gpf_kn_tau_trafo_setpoints = np.append(self.gpf_kn_tau_trafo_setpoints, control_setpoint)
                self.gpf_un_tau_trafo_kdx = np.delete(self.gpf_un_tau_trafo_kdx, np.where(self.gpf_un_tau_trafo_kdx == elm_index))

            else:
                raise ValueError(f"Control mode {control_mode} not supported")


        elif elm_name in self.branch_data.name_to_idx.keys():
            elm_index = self.branch_data.name_to_idx[elm_name]
            if elm_index in self.branch_ac:
                assert control_mode == GpfControlType.type_Pf or control_mode == GpfControlType.type_Qf or control_mode == GpfControlType.type_Pt or control_mode == GpfControlType.type_Qt, f"{master_name} is specifiying {control_mode} for {elm_name}. Control mode for AC passive branch must be either Pf or Qf or Pt or Qt"
            else:
                assert control_mode == GpfControlType.type_Pf or control_mode == GpfControlType.type_Pt, f"{master_name} is specifiying {control_mode} for {elm_name}. Control mode for DC branch can only be Pf or Pt"

            if control_mode == GpfControlType.type_Pf:
                self.gpf_kn_pfrom_passive_kdx = np.append(self.gpf_kn_pfrom_passive_kdx, elm_index)
                self.gpf_kn_pfrom_passive_setpoints = np.append(self.gpf_kn_pfrom_passive_setpoints, control_setpoint)

            elif control_mode == GpfControlType.type_Qf:
                self.gpf_kn_qfrom_passive_kdx = np.append(self.gpf_kn_qfrom_passive_kdx, elm_index)
                self.gpf_kn_qfrom_passive_setpoints = np.append(self.gpf_kn_qfrom_passive_setpoints, control_setpoint)

            elif control_mode == GpfControlType.type_Pt:
                self.gpf_kn_pto_passive_kdx = np.append(self.gpf_kn_pto_passive_kdx, elm_index)
                self.gpf_kn_pto_passive_setpoints = np.append(self.gpf_kn_pto_passive_setpoints, control_setpoint)

            elif control_mode == GpfControlType.type_Qt:
                self.gpf_kn_qto_passive_kdx = np.append(self.gpf_kn_qto_passive_kdx, elm_index)
                self.gpf_kn_qto_passive_setpoints = np.append(self.gpf_kn_qto_passive_setpoints, control_setpoint)

            else:
                raise ValueError(f"Control mode {control_mode} not supported")



        else:
            raise ValueError(f"Element name {elm_name} does not exist in the network")





    def compile_control_indices_generalised_pf(self, Sbase, gen_data, vsc_data, bus_data, adj, idx_islands, verbose = 0):

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
            # Create a dictionary with the data
            data = {
                "Type": ["AC Bus", "DC Bus", "VSC", "Controllable Trafo", "Total"],
                "Number of Instances": [num_ac_buses, num_dc_buses, num_vsc, num_trafo, ""],
                "Number of Equations": [num_ac_buses*2, num_dc_buses, num_vsc, num_trafo*4, total]
            }

            # Create the DataFrame
            df = pd.DataFrame(data)

            # Print the DataFrame
            print(df)


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
            # print("bus here has a generator", bus)
            # print("its voltage setpoint is", _setpoint)
            # print("its active power setpoint is", gen_data.p[gen_data.bus_idx == bus])
            # print("power factor is at", gen_data.pf[gen_data.bus_idx == bus])

            # We assume for the time being that all generators set the voltage
            _popIdx = np.where(dict_unknown_idx["Voltage"] == bus)
            if _popIdx[0].size == 0:
                continue
            if len(_setpoint) == 1:
                dict_unknown_idx["Voltage"] = np.delete(dict_unknown_idx["Voltage"], _popIdx)
                dict_known_idx["Voltage"] = np.append(dict_known_idx["Voltage"], bus)
                dict_known_setpoints["Voltage"] = np.append(dict_known_setpoints["Voltage"], _setpoint)
            elif len(_setpoint) > 1:
                dict_unknown_idx["Voltage"] = np.delete(dict_unknown_idx["Voltage"], _popIdx)
                buses = (bus * np.ones(len(_setpoint))).astype(int) #MUST cast as int because it is index later
                dict_known_idx["Voltage"] = np.append(dict_known_idx["Voltage"], buses)
                dict_known_setpoints["Voltage"] = np.append(dict_known_setpoints["Voltage"], _setpoint)
            assert len(dict_known_setpoints["Voltage"]) == len(dict_known_idx["Voltage"]), f"Voltages setpoints {dict_known_setpoints['Voltage']} and buses {dict_known_idx['Voltage']} are not the same length"

            # We are going to use the slack array to determine the control mode (which means that you must set slack yourself)
            if bus_data.bus_types[bus] == BusMode.Slack.value:  # Slack bus
                # We set the angle
                _popIdx = np.where(dict_unknown_idx["Angle"] == bus)
                if len(_setpoint) == 1:
                    dict_unknown_idx["Angle"] = np.delete(dict_unknown_idx["Angle"], _popIdx)
                    dict_known_idx["Angle"] = np.append(dict_known_idx["Angle"], bus)
                    dict_known_setpoints["Angle"] = np.append(dict_known_setpoints["Angle"], 0)
                elif len(_setpoint) > 1:
                    dict_unknown_idx["Angle"] = np.delete(dict_unknown_idx["Angle"], _popIdx)
                    buses = (bus * np.ones(len(_setpoint))).astype(int) #MUST cast as int because it is index later
                    dict_known_idx["Angle"] = np.append(dict_known_idx["Angle"], buses)
                    dict_known_setpoints["Angle"] = np.append(dict_known_setpoints["Angle"], np.zeros(len(_setpoint)))
                assert len(dict_known_setpoints["Angle"]) == len(dict_known_idx["Angle"]), f"Angles setpoints {dict_known_setpoints['Angle']} and buses {dict_known_idx['Angle']} are not the same length"

            else:
                # We set the active power
                _popIdx = np.where(dict_unknown_idx["Pzip"] == bus)
                if len(_setpoint) == 1:
                    dict_unknown_idx["Pzip"] = np.delete(dict_unknown_idx["Pzip"], _popIdx)
                    dict_known_idx["Pzip"] = np.append(dict_known_idx["Pzip"], bus)
                    rawPower = gen_data.p[gen_data.bus_idx == bus]
                    puPower = rawPower/Sbase
                    dict_known_setpoints["Pzip"] = np.append(dict_known_setpoints["Pzip"], puPower)
                elif len(_setpoint) > 1:
                    dict_unknown_idx["Pzip"] = np.delete(dict_unknown_idx["Pzip"], _popIdx)
                    buses = (bus * np.ones(len(_setpoint))).astype(int) #MUST cast as int because it is index later
                    dict_known_idx["Pzip"] = np.append(dict_known_idx["Pzip"], buses)
                    rawPower = gen_data.p[gen_data.bus_idx == bus]
                    puPower = rawPower/Sbase
                    dict_known_setpoints["Pzip"] = np.append(dict_known_setpoints["Pzip"], puPower)
                # dict_unknown_idx["Pzip"] = np.delete(dict_unknown_idx["Pzip"], _popIdx)
                # dict_known_idx["Pzip"] = np.append(dict_known_idx["Pzip"], bus)
                # rawPower = gen_data.p[gen_data.bus_idx == bus]
                # puPower = rawPower/Sbase
                # dict_known_setpoints["Pzip"] = np.append(dict_known_setpoints["Pzip"], puPower)
                assert len(dict_known_setpoints["Pzip"]) == len(dict_known_idx["Pzip"]), f"Powers setpoints {dict_known_setpoints['Pzip']} and buses {dict_known_idx['Pzip']} are not the same length"

            # print((dict_known_idx["Voltage"]), "known voltage")
            # print((dict_known_idx["Pzip"]), " known pzip")

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


        if verbose == 1:
            # Initialize the data for the DataFrame
            data = {
                "Type": ["Voltage", "Angle", "Pzip", "Qzip", "Pfrom", "Pto", "Qfrom", "Qto", "Modulation", "Tau", "Total"],
                "Number of Unknowns": [
                    len(dict_unknown_idx["Voltage"]),
                    len(dict_unknown_idx["Angle"]),
                    len(dict_unknown_idx["Pzip"]),
                    len(dict_unknown_idx["Qzip"]),
                    len(dict_unknown_idx["Pfrom"]),
                    len(dict_unknown_idx["Pto"]),
                    len(dict_unknown_idx["Qfrom"]),
                    len(dict_unknown_idx["Qto"]),
                    len(dict_unknown_idx["Modulation"]),
                    len(dict_unknown_idx["Tau"]),
                    len(dict_unknown_idx["Voltage"]) + len(dict_unknown_idx["Angle"]) + len(dict_unknown_idx["Pzip"]) + len(dict_unknown_idx["Qzip"]) + len(dict_unknown_idx["Pfrom"]) + len(dict_unknown_idx["Pto"]) + len(dict_unknown_idx["Qfrom"]) + len(dict_unknown_idx["Qto"]) + len(dict_unknown_idx["Modulation"]) + len(dict_unknown_idx["Tau"])
                ]
            }

            # Create the DataFrame
            df = pd.DataFrame(data)

            # Print the DataFrame
            print(df)

        
        self.check_subsystem_slacks(idx_islands, dict_known_idx, bus_data, verbose = 1, strict = 1)

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
        # Data list for DataFrame
        data = {"Index":[], "System": [], "No of Buses":[], "Slack Buses": [], "Remarks": []}

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

            # Append system info to data list
            _buses_in_system = [bus_data.names[busIndex] for busIndex in system]
            data["Index"].append(system)
            data["System"].append(f"Subsystem {_buses_in_system}")
            data["No of Buses"].append(len(_buses_in_system))
            data["Slack Buses"].append(isSlack)
            data["Remarks"].append("All good" if len(isSlack) == 1 else "No good")

            # true if there is exactly one slack, false otherwise
            subSystemSlacks[i] = len(isSlack) == 1

        if verbose:
            # Create the DataFrame from data list
            df = pd.DataFrame(data)
            # Print the DataFrame
            print(df)

        if strict:
            # if adding up lengthwise does not equal the length of the buses, then assert an error
            try:
                assert sum(subSystemSlacks) == len(systems), "You do not have exactly one slack bus for each subsystem"
            except AssertionError as e:
                # print (changing controls and trying again)
                print(e)
                print("Changing controls and trying again")
                #go through data["Remarks"] and look for the first No Good, then use that index to fix the controls
                for i, remark in enumerate(data["Remarks"]):
                    if remark == "No good":
                        # print(f"System {data['System'][i]} has no slack bus")
                        #self.fix_controls(subSystemSlacks, isSlack, _buses_in_system)
                        self.fix_controls(subSystemSlacks, isSlack, data["Slack Buses"][i], data["Index"][i])
                        break
                        

        return


    def fix_controls(self, subSystemSlacks, isSlack, _buses_in_system, idx):
        #get the gen_data
        #print all the inputs
        # print("subSystemSlacks", subSystemSlacks)
        # print("isSlack", isSlack)
        print("_buses_in_system", _buses_in_system)
        print("idx", idx)
        print("self.gen_data.bus_idx", self.gen_data.bus_idx)
        # use the bus dict to get the bus object
        #look for any indices in idx that is also in self.gen_data.bus_idx
        indices_incommon = np.intersect1d(idx, self.gen_data.bus_idx)
        print("indices_incommon", indices_incommon)
        #lets just take the first one
        if len(indices_incommon) > 0:
            slackBusIdx = indices_incommon[0]
            #set the corresponding generator index
            genIdx = np.where(self.gen_data.bus_idx == slackBusIdx)
            self.gen_data.gpf_ctrl1_elm[genIdx] = str(self.bus_data.names[slackBusIdx])
            self.gen_data.gpf_ctrl1_mode[genIdx] = GpfControlType.type_Vm
            self.gen_data.gpf_ctrl1_val[genIdx] = self.gen_data.v[genIdx]
            self.gen_data.gpf_ctrl2_elm[genIdx] = str(self.bus_data.names[slackBusIdx])
            self.gen_data.gpf_ctrl2_mode[genIdx] = GpfControlType.type_Va
            self.gen_data.gpf_ctrl2_val[genIdx] = 0.0 #magic number here for the angle reference
            self.resetIndices()
            self.compile_control_indices_generalised_pf2(self.Sbase, self.gen_data, self.vsc_data, self.bus_data, self.controllable_trafo_data, self.branch_data, self.adj, self.idx_islands, verbose = 1)
        else:
            print("No common indices found, I am not sure what to set as a slack bus")
            slackBusIdx = idx[0]
            self.gen_data.nelm +=1
            self.gen_ac = np.append(self.gen_ac, self.gen_data.nelm-1)
            self.gen_data.names = np.append(self.gen_data.names, f"gen{self.gen_data.nelm-1}")
            self.gen_data.gpf_ctrl1_elm = np.append(self.gen_data.gpf_ctrl1_elm, str(self.bus_data.names[slackBusIdx]))
            self.gen_data.gpf_ctrl1_mode = np.append(self.gen_data.gpf_ctrl1_mode, GpfControlType.type_Vm)
            self.gen_data.gpf_ctrl1_val = np.append(self.gen_data.gpf_ctrl1_val, 1.0)
            self.gen_data.gpf_ctrl2_elm = np.append(self.gen_data.gpf_ctrl2_elm, str(self.bus_data.names[slackBusIdx]))
            self.gen_data.gpf_ctrl2_mode = np.append(self.gen_data.gpf_ctrl2_mode, GpfControlType.type_Va)
            self.gen_data.gpf_ctrl2_val = np.append(self.gen_data.gpf_ctrl2_val, 0.0) #magic number here for the angle reference
            self.resetIndices()
            self.compile_control_indices_generalised_pf2(self.Sbase, self.gen_data, self.vsc_data, self.bus_data, self.controllable_trafo_data, self.branch_data, self.adj, self.idx_islands, verbose = 1)
            # self.gen_data.gpf_ctrl1_val.append(1.0)
            # self.gen_data.gpf_ctrl2_elm.append(str(self.bus_data.names[slackBusIdx]))
            # self.gen_data.gpf_ctrl2_mode.append(GpfControlType.type_Va)
            # self.gen_data.gpf_ctrl2_val.append(0.0) #magic number here for the angle reference
        
    def resetIndices(self):
        ###### Generalised PF 2 ######

        # (Generalised PF 2)  indices of the buses where voltage is known (controlled)
        self.gpf_kn_volt_idx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the buses where angle is known (controlled)
        self.gpf_kn_angle_idx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the GENERATORS, not buses, where Pzip is known (controlled)
        self.gpf_kn_pzip_gen_idx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the GENERATORS, not buses, where Qzip is known (controlled)
        self.gpf_kn_qzip_gen_idx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the VSCs where Pfrom is known (controlled)
        self.gpf_kn_pfrom_vsc_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the VSCs where Pto is known (controlled)
        self.gpf_kn_pto_vsc_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the VSCs where Qto is known (controlled)
        self.gpf_kn_qto_vsc_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the CONTROLLABLE TRAFOS where Pfrom is known (controlled)
        self.gpf_kn_pfrom_trafo_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the CONTROLLABLE TRAFOS where Pto is known (controlled)
        self.gpf_kn_pto_trafo_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the CONTROLLABLE TRAFOS where Qfrom is known (controlled)
        self.gpf_kn_qfrom_trafo_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the CONTROLLABLE TRAFOS where Qto is known (controlled)
        self.gpf_kn_qto_trafo_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the CONTROLLABLE TRAFOS where tap module is known (controlled)
        self.gpf_kn_mod_trafo_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the CONTROLLABLE TRAFOS where tap angle is known (controlled)
        self.gpf_kn_tau_trafo_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the passive branches where Pfrom are known (controlled)
        self.gpf_kn_pfrom_passive_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the branches where Qfrom are known (controlled)
        self.gpf_kn_qfrom_passive_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the branches where Pto are known (controlled)
        self.gpf_kn_pto_passive_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the branches where Qto are known (controlled)
        self.gpf_kn_qto_passive_kdx: IntVec = np.zeros(0, dtype=int)




        # (Generalised PF 2) SETPOINTS of the buses where voltage is known (controlled)
        self.gpf_kn_volt_setpoints: Vec = np.zeros(0, dtype=float)

        # (Generalised PF 2) SETPOINTS of the buses where angle is known (controlled)
        self.gpf_kn_angle_setpoints: Vec = np.zeros(0, dtype=float)

        # (Generalised PF 2) SETPOINTS of the GENERATORS, not buses, where Pzip is known (controlled)
        self.gpf_kn_pzip_gen_setpoints: Vec = np.zeros(0, dtype=float)

        # (Generalised PF 2) SETPOINTS of the GENERATORS, not buses, where Qzip is known (controlled)
        self.gpf_kn_qzip_gen_setpoints: Vec = np.zeros(0, dtype=float)

        # (Generalised PF 2) SETPOINTS of the VSCs where Pfrom is known (controlled)
        self.gpf_kn_pfrom_vsc_setpoints: Vec = np.zeros(0, dtype=float)

        # (Generalised PF 2) SETPOINTS of the VSCs where Pto is known (controlled)
        self.gpf_kn_pto_vsc_setpoints: Vec = np.zeros(0, dtype=float)

        # (Generalised PF 2) SETPOINTS of the VSCs where Qto is known (controlled)
        self.gpf_kn_qto_vsc_setpoints: Vec = np.zeros(0, dtype=float)

        # (Generalised PF 2) SETPOINTS of the CONTROLLABLE TRAFOS where Pfrom is known (controlled)
        self.gpf_kn_pfrom_trafo_setpoints: Vec = np.zeros(0, dtype=float)

        # (Generalised PF 2) SETPOINTS of the CONTROLLABLE TRAFOS where Pto is known (controlled)
        self.gpf_kn_pto_trafo_setpoints: Vec = np.zeros(0, dtype=float)

        # (Generalised PF 2) SETPOINTS of the CONTROLLABLE TRAFOS where Qfrom is known (controlled)
        self.gpf_kn_qfrom_trafo_setpoints: Vec = np.zeros(0, dtype=float)

        # (Generalised PF 2) SETPOINTS of the CONTROLLABLE TRAFOS where Qto is known (controlled)
        self.gpf_kn_qto_trafo_setpoints: Vec = np.zeros(0, dtype=float)

        # (Generalised PF 2) SETPOINTS of the CONTROLLABLE TRAFOS where tap module is known (controlled)
        self.gpf_kn_mod_trafo_setpoints: Vec = np.zeros(0, dtype=float)

        # (Generalised PF 2) SETPOINTS of the CONTROLLABLE TRAFOS where tap angle is known (controlled)
        self.gpf_kn_tau_trafo_setpoints: Vec = np.zeros(0, dtype=float)

        # (Generalised PF 2) SETPOINTS of the passive branches where Pfrom are known (controlled)
        self.gpf_kn_pfrom_passive_setpoints: Vec = np.zeros(0, dtype=float)

        # (Generalised PF 2) SETPOINTS of the branches where Qfrom are known (controlled)
        self.gpf_kn_qfrom_passive_setpoints: Vec = np.zeros(0, dtype=float)

        # (Generalised PF 2) SETPOINTS of the branches where Pto are known (controlled)
        self.gpf_kn_pto_passive_setpoints: Vec = np.zeros(0, dtype=float)

        # (Generalised PF 2) SETPOINTS of the branches where Qto are known (controlled)
        self.gpf_kn_qto_passive_setpoints: Vec = np.zeros(0, dtype=float)




        # (Generalised PF 2) indices of the buses where voltage is UNKNOWN
        self.gpf_un_volt_idx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the buses where angle is UNKNOWN
        self.gpf_un_angle_idx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the GENERATORS, not buses, where Pzip is UNKNOWN
        self.gpf_un_pzip_gen_idx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the GENERATORS, not buses, where Qzip is UNKNOWN
        self.gpf_un_qzip_gen_idx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the VSCs where Pfrom is UNKNOWN
        self.gpf_un_pfrom_vsc_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the VSCs where Pto is UNKNOWN
        self.gpf_un_pto_vsc_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the VSCs where Qto is UNKNOWN
        self.gpf_un_qto_vsc_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the CONTROLLABLE TRAFOS where Pfrom is UNKNOWN
        self.gpf_un_pfrom_trafo_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the CONTROLLABLE TRAFOS where Pto is UNKNOWN
        self.gpf_un_pto_trafo_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the CONTROLLABLE TRAFOS where Qfrom is UNKNOWN
        self.gpf_un_qfrom_trafo_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the CONTROLLABLE TRAFOS where Qto is UNKNOWN
        self.gpf_un_qto_trafo_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the CONTROLLABLE TRAFOS where tap module is UNKNOWN
        self.gpf_un_mod_trafo_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the CONTROLLABLE TRAFOS where tap angle is UNKNOWN
        self.gpf_un_tau_trafo_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the PASSIVE BRANCHES where Pfrom are UNKNOWN
        self.gpf_un_pfrom_passive_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the PASSIVE BRANCHES where Qfrom are UNKNOWN
        self.gpf_un_qfrom_passive_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the PASSIVE BRANCHES where Pto are UNKNOWN
        self.gpf_un_pto_passive_kdx: IntVec = np.zeros(0, dtype=int)

        # (Generalised PF 2) indices of the PASSIVE BRANCHES where Qto are UNKNOWN
        self.gpf_un_qto_passive_kdx: IntVec = np.zeros(0, dtype=int)


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
