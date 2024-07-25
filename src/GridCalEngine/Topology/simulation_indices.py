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
from GridCalEngine.enumerations import BusMode, TapPhaseControl, TapModuleControl
from GridCalEngine.basic_structures import Vec, IntVec, BoolVec


@nb.njit(cache=True)
def compile_types(Pbus: Vec, types: IntVec) -> Tuple[IntVec, IntVec, IntVec, IntVec, IntVec, IntVec]:
    """
    Compile the types.
    :param Pbus: array of real power Injections per node used to choose the slack as
                 the node with greater generation if no slack is provided
    :param types: array of tentative node types (it may be modified internally)
    :return: ref, pq, pv, pqpv
    """

    # check that Sbus is a 1D array
    assert (len(Pbus.shape) == 1)

    pq = np.where(types == BusMode.PQ_tpe.value)[0]
    pv = np.where(types == BusMode.PV_tpe.value)[0]
    pqv = np.where(types == BusMode.PQV_tpe.value)[0]
    p = np.where(types == BusMode.P_tpe.value)[0]
    ref = np.where(types == BusMode.Slack_tpe.value)[0]

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
            types[r] = BusMode.Slack_tpe.value
    else:
        pass  # no problem :)

    no_slack = np.concatenate((pv, pq, p, pqv))
    no_slack.sort()

    return ref, pq, pv, pqv, p, no_slack


class SimulationIndices:
    """
    Class to handle the simulation indices
    """

    def __init__(self,
                 bus_types: IntVec,
                 Pbus: Vec,
                 tap_module_control_mode: List[TapModuleControl],
                 tap_phase_control_mode: List[TapPhaseControl],
                 tap_controlled_buses: IntVec,
                 dc: IntVec):
        """

        :param bus_types: Bus type initial guess array
        :param Pbus: Active power per bus array
        :param tap_module_control_mode: TapModuleControl control mode array
        :param tap_phase_control_mode: TapPhaseControl control mode array
        :param F: Array of bus_from indices
        :param T: Array of bus_to indices
        :param dc: Arra of is DC ? per bus
        """
        # master aray of bus types (nbus)
        self.bus_types = bus_types

        # master array of branch control types (nbr)
        self.tap_module_control_mode = tap_module_control_mode
        self.tap_phase_control_mode = tap_phase_control_mode
        self.tap_controlled_buses = tap_controlled_buses

        # AC and DC indices
        self.ac: IntVec = np.where(~dc)[0]
        self.dc: IntVec = np.where(dc)[0]

        # bus type indices
        self.pq: IntVec = np.zeros(0, dtype=int)
        self.pqv: IntVec = np.zeros(0, dtype=int)
        self.pv: IntVec = np.zeros(0, dtype=int)  # PV-local
        self.p: IntVec = np.zeros(0, dtype=int)  # PV-remote
        self.vd: IntVec = np.zeros(0, dtype=int)
        self.no_slack: IntVec = np.zeros(0, dtype=int)

        # branch control indices
        self.any_control: bool = False

        # indices of the Branches controlling Pf flow with tau
        self.k_pf_tau: IntVec = np.zeros(0, dtype=int)

        # indices of the Branches when forcing the Qf flow to zero with Beq
        self.k_qf_beq: IntVec = np.zeros(0, dtype=int)

        # indices of the Branches when controlling V at some bus with m, those buses are accounted as PQV
        self.k_v_m: IntVec = np.zeros(0, dtype=int)

        # determine the bus indices
        self.vd, self.pq, self.pv, self.pqv, self.p, self.no_slack = compile_types(Pbus=Pbus, types=bus_types)

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
        self.vd, self.pq, self.pv, self.pqv, self.p, self.no_slack = compile_types(Pbus=Pbus, types=bus_types)

    def compile_control_indices(self) -> None:
        """

        :return:
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
                self.control_mode
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
        self.k_v_m = np.array(k_vt_m_lst, dtype=int)
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
