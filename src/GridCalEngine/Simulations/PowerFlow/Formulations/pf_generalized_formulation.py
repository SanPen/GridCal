# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Tuple, List, Callable
import numpy as np
from numba import njit
from scipy.sparse import diags
from scipy.sparse import lil_matrix, isspmatrix_csc
from GridCalEngine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
from GridCalEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCalEngine.DataStructures.numerical_circuit import NumericalCircuit
import GridCalEngine.Simulations.Derivatives.csc_derivatives as deriv
from GridCalEngine.Utils.NumericalMethods.common import find_closest_number, make_complex
from GridCalEngine.Utils.Sparse.csc2 import (CSC, CxCSC, scipy_to_mat, sp_slice, csc_stack_2d_ff, csc_add_cx)
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.discrete_controls import control_q_josep_method, \
    compute_slack_distribution
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.common_functions import expand
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.common_functions import compute_fx_error
from GridCalEngine.Simulations.PowerFlow.Formulations.pf_formulation_template import PfFormulationTemplate
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.common_functions import (compute_zip_power, compute_power,
                                                                                   polar_to_rect)
from GridCalEngine.enumerations import (TapPhaseControl, TapModuleControl, HvdcControlType, ConverterControlType)
from GridCalEngine.basic_structures import Vec, IntVec, CxVec, Logger


@njit()
def adv_jacobian(nbus: int,
                 nbr: int,
                 nvsc: int,
                 nhvdc: int,
                 F: IntVec,
                 T: IntVec,
                 F_vsc: IntVec,
                 T_vsc: IntVec,
                 F_hvdc: IntVec,
                 T_hvdc: IntVec,

                 tap_angles: Vec,
                 tap_modules: Vec,

                 V: CxVec,
                 Vm: Vec,

                 # Controllable Branch Indices
                 u_cbr_m: IntVec,
                 u_cbr_tau: IntVec,
                 cbr: IntVec,

                 k_cbr_pf: IntVec,
                 k_cbr_pt: IntVec,
                 k_cbr_qf: IntVec,
                 k_cbr_qt: IntVec,

                 # VSC Indices
                 u_vsc_pf: IntVec,
                 u_vsc_pt: IntVec,
                 u_vsc_qt: IntVec,

                 # VSC Params
                 alpha1: Vec,
                 alpha2: Vec,
                 alpha3: Vec,

                 # HVDC Params
                 hvdc_r,
                 hvdc_droop,

                 # Bus Indices
                 i_u_vm: IntVec,
                 i_u_va: IntVec,
                 i_k_p: IntVec,
                 i_k_q: IntVec,

                 # Unknowns
                 Pf_vsc: Vec,
                 Pt_vsc: Vec,
                 Qt_vsc: Vec,
                 Pf_hvdc: Vec,

                 # Admittances and Connections
                 yff_cbr: CxVec,
                 yft_cbr: CxVec,
                 ytf_cbr: CxVec,
                 ytt_cbr: CxVec,

                 yff0: CxVec,
                 yft0: CxVec,
                 ytf0: CxVec,
                 ytt0: CxVec,

                 F_cbr: IntVec,
                 T_cbr: IntVec,

                 Yi: IntVec,
                 Yp: IntVec,
                 Yx: CxVec) -> CSC:
    """

    :param nbus:
    :param nbr:
    :param nvsc:
    :param nhvdc:
    :param F:
    :param T:
    :param F_vsc:
    :param T_vsc:
    :param F_hvdc:
    :param T_hvdc:
    :param tap_angles:
    :param tap_modules:
    :param V:
    :param Vm:
    :param u_cbr_m:
    :param u_cbr_tau:
    :param cbr:
    :param k_cbr_pf:
    :param k_cbr_pt:
    :param k_cbr_qf:
    :param k_cbr_qt:
    :param u_vsc_pf:
    :param u_vsc_pt:
    :param u_vsc_qt:
    :param alpha1:
    :param alpha2:
    :param alpha3:
    :param hvdc_r:
    :param hvdc_droop:
    :param i_u_vm:
    :param i_u_va:
    :param i_k_p:
    :param i_k_q:
    :param Pf_vsc:
    :param Pt_vsc:
    :param Qt_vsc:
    :param Pf_hvdc:
    :param yff_cbr:
    :param yft_cbr:
    :param ytf_cbr:
    :param ytt_cbr:
    :param yff0:
    :param yft0:
    :param ytf0:
    :param ytt0:
    :param F_cbr:
    :param T_cbr:
    :param Yi:
    :param Yp:
    :param Yx:
    :return:
    """

    tap = polar_to_rect(tap_modules, tap_angles)

    # -------- ROW 1 + ROW 2 (Sbus) ---------
    # bus-bus derivatives (always needed)

    # passive admittance contribution
    dSy_dVm_x, dSy_dVa_x = deriv.dSbus_dV_numba_sparse_csc(Yx, Yp, Yi, V, Vm)
    dSy_dVm = CxCSC(nbus, nbus, len(dSy_dVm_x), False).set(Yi, Yp, dSy_dVm_x)
    dSy_dVa = CxCSC(nbus, nbus, len(dSy_dVa_x), False).set(Yi, Yp, dSy_dVa_x)

    # active transformers contribution
    dScbr_dVm = deriv.dSbr_bus_dVm_josep_csc(nbus, cbr, F_cbr, T_cbr, yff_cbr, yft_cbr, ytf_cbr, ytt_cbr, yff0, yft0,
                                             ytf0, ytt0, V, tap, tap_modules)
    dScbr_dVa = deriv.dSbr_bus_dVa_josep_csc(nbus, cbr, F_cbr, T_cbr, yff_cbr, yft_cbr, ytf_cbr, ytt_cbr, yff0, yft0,
                                             ytf0, ytt0, V, tap, tap_modules)

    dS_dVm = csc_add_cx(dSy_dVm, dScbr_dVm)
    dS_dVa = csc_add_cx(dSy_dVa, dScbr_dVa)

    dP_dVm__ = sp_slice(dS_dVm.real, i_k_p, i_u_vm)
    dQ_dVm__ = sp_slice(dS_dVm.imag, i_k_q, i_u_vm)

    dP_dVa__ = sp_slice(dS_dVa.real, i_k_p, i_u_va)
    dQ_dVa__ = sp_slice(dS_dVa.imag, i_k_q, i_u_va)

    dP_dtau__ = deriv.dSbus_dtau_josep_csc(nbus, i_k_p, u_cbr_tau, F, T, yff_cbr, yft_cbr, ytf_cbr, ytt_cbr,
                                           tap, tap_modules, V).real
    dQ_dtau__ = deriv.dSbus_dtau_josep_csc(nbus, i_k_q, u_cbr_tau, F, T, yff_cbr, yft_cbr, ytf_cbr, ytt_cbr,
                                           tap, tap_modules, V).imag

    dP_dm__ = deriv.dSbus_dm_josep_csc(nbus, i_k_p, u_cbr_m, F, T, yff_cbr, yft_cbr, ytf_cbr, ytt_cbr,
                                       tap, tap_modules, V).real
    dQ_dm__ = deriv.dSbus_dm_josep_csc(nbus, i_k_q, u_cbr_m, F, T, yff_cbr, yft_cbr, ytf_cbr, ytt_cbr,
                                       tap, tap_modules, V).imag

    dP_dPfvsc__ = deriv.dPQ_dPQft_csc(nbus, nvsc, i_k_p, u_vsc_pf, F_vsc)
    dP_dPtvsc__ = deriv.dPQ_dPQft_csc(nbus, nvsc, i_k_p, u_vsc_pt, T_vsc)
    dP_dQtvsc__ = CSC(len(i_k_p), len(u_vsc_qt), 0, False)  # fully empty 

    dQ_dPfvsc__ = CSC(len(i_k_q), len(u_vsc_pf), 0, False)  # fully empty 
    dQ_dPtvsc__ = CSC(len(i_k_q), len(u_vsc_pt), 0, False)  # fully empty 
    dQ_dQtvsc__ = deriv.dPQ_dPQft_csc(nbus, nvsc, i_k_q, u_vsc_qt, T_vsc)

    # hvdc_range = np.array(range(nhvdc))
    hvdc_range = np.arange(nhvdc)
    dP_dPfhvdc__ = deriv.dPQ_dPQft_csc(nbus, nhvdc, i_k_p, hvdc_range, F_hvdc)
    dP_dPthvdc__ = deriv.dPQ_dPQft_csc(nbus, nhvdc, i_k_p, hvdc_range, T_hvdc)
    dP_dQfhvdc__ = CSC(len(i_k_p), nhvdc, 0, False)  # fully empty
    dP_dQthvdc__ = CSC(len(i_k_p), nhvdc, 0, False)  # fully empty

    dQ_dPfhvdc__ = CSC(len(i_k_q), nhvdc, 0, False)  # fully empty
    dQ_dPthvdc__ = CSC(len(i_k_q), nhvdc, 0, False)  # fully empty
    dQ_dQfhvdc__ = deriv.dPQ_dPQft_csc(nbus, nhvdc, i_k_q, hvdc_range, F_hvdc)
    dQ_dQthvdc__ = deriv.dPQ_dPQft_csc(nbus, nhvdc, i_k_q, hvdc_range, T_hvdc)

    # -------- ROW 3 (VSCs) ---------
    dLossvsc_dVa_ = CSC(nvsc, len(i_u_va), 0, False)
    dLossvsc_dVm_ = deriv.dLossvsc_dVm_csc(nvsc, nbus, i_u_vm, alpha1, alpha2, alpha3, V, Pf_vsc, Pt_vsc, Qt_vsc, F_vsc,
                                           T_vsc)
    dLossvsc_dPfvsc_ = deriv.dLossvsc_dPfvsc_josep_csc(nvsc, u_vsc_pf)
    dLossvsc_dPtvsc_ = deriv.dLossvsc_dPtvsc_josep_csc(nvsc, u_vsc_pt, alpha2, alpha3, V, Pt_vsc, Qt_vsc, T_vsc)
    dLossvsc_dQtvsc_ = deriv.dLossvsc_dQtvsc_josep_csc(nvsc, u_vsc_qt, alpha2, alpha3, V, Pt_vsc, Qt_vsc, T_vsc)
    dLossvsc_dPfhvdc_ = CSC(nvsc, nhvdc, 0, False)
    dLossvsc_dPthvdc_ = CSC(nvsc, nhvdc, 0, False)
    dLossvsc_dQfhvdc_ = CSC(nvsc, nhvdc, 0, False)
    dLossvsc_dQthvdc_ = CSC(nvsc, nhvdc, 0, False)
    dLossvsc_dm_ = CSC(nvsc, len(u_cbr_m), 0, False)
    dLossvsc_dtau_ = CSC(nvsc, len(u_cbr_tau), 0, False)

    # -------- ROW 4 (loss HVDCs) ---------
    dLosshvdc_dVa_ = CSC(nhvdc, len(i_u_va), 0, False)

    dLosshvdc_dVm_ = deriv.dLosshvdc_dVm_josep_csc(nhvdc, nbus, i_u_vm, V, Pf_hvdc, hvdc_r, F_hvdc)
    dLosshvdc_dPfhvdc_ = deriv.dLosshvdc_dPfhvdc_josep_csc(nhvdc, V, hvdc_r, F_hvdc)
    dLosshvdc_dPthvdc_ = deriv.dLosshvdc_dPthvdc_josep_csc(nhvdc)

    dLosshvdc_dPfvsc_ = CSC(nhvdc, nvsc, 0, False)
    dLosshvdc_dPtvsc_ = CSC(nhvdc, nvsc, 0, False)
    dLosshvdc_dQtvsc_ = CSC(nhvdc, nvsc, 0, False)
    dLosshvdc_dQfhvdc_ = CSC(nhvdc, nhvdc, 0, False)
    dLosshvdc_dQthvdc_ = CSC(nhvdc, nhvdc, 0, False)

    dLosshvdc_dm_ = CSC(nhvdc, len(u_cbr_m), 0, False)
    dLosshvdc_dtau_ = CSC(nhvdc, len(u_cbr_tau), 0, False)

    # -------- ROW 5 (inj HVDCs) ---------
    dInjhvdc_dVa_ = deriv.dInjhvdc_dVa_josep_csc(nhvdc, nbus, i_u_va, hvdc_droop, F_hvdc, T_hvdc)

    dInjhvdc_dVm_ = CSC(nhvdc, len(i_u_vm), 0, False)
    dInjhvdc_dPfvsc_ = CSC(nhvdc, len(u_vsc_pf), 0, False)
    dInjhvdc_dPtvsc_ = CSC(nhvdc, len(u_vsc_pt), 0, False)
    dInjhvdc_dQtvsc_ = CSC(nhvdc, len(u_vsc_qt), 0, False)

    dInjhvdc_dPfhvdc_ = deriv.dInjhvdc_dPfhvdc_josep_csc(nhvdc)

    dInjhvdc_dPthvdc_ = CSC(nhvdc, nhvdc, 0, False)
    dInjhvdc_dQfhvdc_ = CSC(nhvdc, nhvdc, 0, False)
    dInjhvdc_dQthvdc_ = CSC(nhvdc, nhvdc, 0, False)

    dInjhvdc_dm_ = CSC(nhvdc, len(u_cbr_m), 0, False)
    dInjhvdc_dtau_ = CSC(nhvdc, len(u_cbr_tau), 0, False)

    # -------- ROW 6 + ROW 7 + ROW 8 + ROW 9 (contr. branch powers) ---------
    dPf_dVa_ = deriv.dSf_dVa_josep_csc(nbus, k_cbr_pf, i_u_va, yff_cbr, yft_cbr, ytf_cbr, ytt_cbr, yff0, yft0, ytf0,
                                       ytt0, V, F, T, tap, tap_modules).real
    dQf_dVa_ = deriv.dSf_dVa_josep_csc(nbus, k_cbr_qf, i_u_va, yff_cbr, yft_cbr, ytf_cbr, ytt_cbr, yff0, yft0, ytf0,
                                       ytt0, V, F, T, tap, tap_modules).imag
    dPt_dVa_ = deriv.dSt_dVa_josep_csc(nbus, k_cbr_pt, i_u_va, yff_cbr, yft_cbr, ytf_cbr, ytt_cbr, yff0, yft0, ytf0,
                                       ytt0, V, F, T, tap, tap_modules).real
    dQt_dVa_ = deriv.dSt_dVa_josep_csc(nbus, k_cbr_qt, i_u_va, yff_cbr, yft_cbr, ytf_cbr, ytt_cbr, yff0, yft0, ytf0,
                                       ytt0, V, F, T, tap, tap_modules).imag

    dPf_dVm_ = deriv.dSf_dVm_josep_csc(nbus, k_cbr_pf, i_u_vm, yff_cbr, yft_cbr, ytf_cbr, ytt_cbr, yff0, yft0, ytf0,
                                       ytt0, V, F, T, tap, tap_modules).real
    dQf_dVm_ = deriv.dSf_dVm_josep_csc(nbus, k_cbr_qf, i_u_vm, yff_cbr, yft_cbr, ytf_cbr, ytt_cbr, yff0, yft0, ytf0,
                                       ytt0, V, F, T, tap, tap_modules).imag
    dPt_dVm_ = deriv.dSt_dVm_josep_csc(nbus, k_cbr_pt, i_u_vm, yff_cbr, yft_cbr, ytf_cbr, ytt_cbr, yff0, yft0, ytf0,
                                       ytt0, V, F, T, tap, tap_modules).real
    dQt_dVm_ = deriv.dSt_dVm_josep_csc(nbus, k_cbr_qt, i_u_vm, yff_cbr, yft_cbr, ytf_cbr, ytt_cbr, yff0, yft0, ytf0,
                                       ytt0, V, F, T, tap, tap_modules).imag

    dPf_dm_ = deriv.dSf_dm_josep_csc(nbr, k_cbr_pf, u_cbr_m, F, T, yff_cbr, yft_cbr, ytf_cbr, ytt_cbr,
                                     tap, tap_modules, V).real
    dQf_dm_ = deriv.dSf_dm_josep_csc(nbr, k_cbr_qf, u_cbr_m, F, T, yff_cbr, yft_cbr, ytf_cbr, ytt_cbr,
                                     tap, tap_modules, V).imag
    dPt_dm_ = deriv.dSt_dm_josep_csc(nbr, k_cbr_pt, u_cbr_m, F, T, yff_cbr, yft_cbr, ytf_cbr, ytt_cbr,
                                     tap, tap_modules, V).real
    dQt_dm_ = deriv.dSt_dm_josep_csc(nbr, k_cbr_qt, u_cbr_m, F, T, yff_cbr, yft_cbr, ytf_cbr, ytt_cbr,
                                     tap, tap_modules, V).imag

    dPf_dtau_ = deriv.dSf_dtau_josep_csc(nbr, k_cbr_pf, u_cbr_tau, F, T, yff_cbr, yft_cbr, ytf_cbr, ytt_cbr,
                                         tap, tap_modules, V).real
    dQf_dtau_ = deriv.dSf_dtau_josep_csc(nbr, k_cbr_qf, u_cbr_tau, F, T, yff_cbr, yft_cbr, ytf_cbr, ytt_cbr,
                                         tap, tap_modules, V).imag
    dPt_dtau_ = deriv.dSt_dtau_josep_csc(nbr, k_cbr_pt, u_cbr_tau, F, T, yff_cbr, yft_cbr, ytf_cbr, ytt_cbr,
                                         tap, tap_modules, V).real
    dQt_dtau_ = deriv.dSt_dtau_josep_csc(nbr, k_cbr_qt, u_cbr_tau, F, T, yff_cbr, yft_cbr, ytf_cbr, ytt_cbr,
                                         tap, tap_modules, V).imag

    dPf_dPfvsc_ = CSC(len(k_cbr_pf), len(u_vsc_pf), 0, False)
    dPf_dPtvsc_ = CSC(len(k_cbr_pf), len(u_vsc_pt), 0, False)
    dPf_dQtvsc_ = CSC(len(k_cbr_pf), len(u_vsc_qt), 0, False)
    dPf_dPfhvdc_ = CSC(len(k_cbr_pf), nhvdc, 0, False)
    dPf_dPthvdc_ = CSC(len(k_cbr_pf), nhvdc, 0, False)
    dPf_dQfhvdc_ = CSC(len(k_cbr_pf), nhvdc, 0, False)
    dPf_dQthvdc_ = CSC(len(k_cbr_pf), nhvdc, 0, False)

    dPt_dPfvsc_ = CSC(len(k_cbr_pt), len(u_vsc_pf), 0, False)
    dPt_dPtvsc_ = CSC(len(k_cbr_pt), len(u_vsc_pt), 0, False)
    dPt_dQtvsc_ = CSC(len(k_cbr_pt), len(u_vsc_qt), 0, False)
    dPt_dPfhvdc_ = CSC(len(k_cbr_pt), nhvdc, 0, False)
    dPt_dPthvdc_ = CSC(len(k_cbr_pt), nhvdc, 0, False)
    dPt_dQfhvdc_ = CSC(len(k_cbr_pt), nhvdc, 0, False)
    dPt_dQthvdc_ = CSC(len(k_cbr_pt), nhvdc, 0, False)

    dQf_dPfvsc_ = CSC(len(k_cbr_qf), len(u_vsc_pf), 0, False)
    dQf_dPtvsc_ = CSC(len(k_cbr_qf), len(u_vsc_pt), 0, False)
    dQf_dQtvsc_ = CSC(len(k_cbr_qf), len(u_vsc_qt), 0, False)
    dQf_dPfhvdc_ = CSC(len(k_cbr_qf), nhvdc, 0, False)
    dQf_dPthvdc_ = CSC(len(k_cbr_qf), nhvdc, 0, False)
    dQf_dQfhvdc_ = CSC(len(k_cbr_qf), nhvdc, 0, False)
    dQf_dQthvdc_ = CSC(len(k_cbr_qf), nhvdc, 0, False)

    dQt_dPfvsc_ = CSC(len(k_cbr_qt), len(u_vsc_pf), 0, False)
    dQt_dPtvsc_ = CSC(len(k_cbr_qt), len(u_vsc_pt), 0, False)
    dQt_dQtvsc_ = CSC(len(k_cbr_qt), len(u_vsc_qt), 0, False)
    dQt_dPfhvdc_ = CSC(len(k_cbr_qt), nhvdc, 0, False)
    dQt_dPthvdc_ = CSC(len(k_cbr_qt), nhvdc, 0, False)
    dQt_dQfhvdc_ = CSC(len(k_cbr_qt), nhvdc, 0, False)
    dQt_dQthvdc_ = CSC(len(k_cbr_qt), nhvdc, 0, False)

    # compose the Jacobian
    J = csc_stack_2d_ff(
        mats=
        [dP_dVa__, dP_dVm__, dP_dPfvsc__, dP_dPtvsc__, dP_dQtvsc__, dP_dPfhvdc__, dP_dPthvdc__,
         dP_dQfhvdc__, dP_dQthvdc__, dP_dm__, dP_dtau__,
         dQ_dVa__, dQ_dVm__, dQ_dPfvsc__, dQ_dPtvsc__, dQ_dQtvsc__, dQ_dPfhvdc__, dQ_dPthvdc__,
         dQ_dQfhvdc__, dQ_dQthvdc__, dQ_dm__, dQ_dtau__,
         dLossvsc_dVa_, dLossvsc_dVm_, dLossvsc_dPfvsc_, dLossvsc_dPtvsc_, dLossvsc_dQtvsc_,
         dLossvsc_dPfhvdc_, dLossvsc_dPthvdc_, dLossvsc_dQfhvdc_, dLossvsc_dQthvdc_, dLossvsc_dm_,
         dLossvsc_dtau_,
         dLosshvdc_dVa_, dLosshvdc_dVm_, dLosshvdc_dPfvsc_, dLosshvdc_dPtvsc_, dLosshvdc_dQtvsc_,
         dLosshvdc_dPfhvdc_, dLosshvdc_dPthvdc_, dLosshvdc_dQfhvdc_, dLosshvdc_dQthvdc_, dLosshvdc_dm_,
         dLosshvdc_dtau_,
         dInjhvdc_dVa_, dInjhvdc_dVm_, dInjhvdc_dPfvsc_, dInjhvdc_dPtvsc_, dInjhvdc_dQtvsc_,
         dInjhvdc_dPfhvdc_, dInjhvdc_dPthvdc_, dInjhvdc_dQfhvdc_, dInjhvdc_dQthvdc_, dInjhvdc_dm_,
         dInjhvdc_dtau_,
         dPf_dVa_, dPf_dVm_, dPf_dPfvsc_, dPf_dPtvsc_, dPf_dQtvsc_, dPf_dPfhvdc_, dPf_dPthvdc_,
         dPf_dQfhvdc_, dPf_dQthvdc_, dPf_dm_, dPf_dtau_,
         dPt_dVa_, dPt_dVm_, dPt_dPfvsc_, dPt_dPtvsc_, dPt_dQtvsc_, dPt_dPfhvdc_, dPt_dPthvdc_,
         dPt_dQfhvdc_, dPt_dQthvdc_, dPt_dm_, dPt_dtau_,
         dQf_dVa_, dQf_dVm_, dQf_dPfvsc_, dQf_dPtvsc_, dQf_dQtvsc_, dQf_dPfhvdc_, dQf_dPthvdc_,
         dQf_dQfhvdc_, dQf_dQthvdc_, dQf_dm_, dQf_dtau_,
         dQt_dVa_, dQt_dVm_, dQt_dPfvsc_, dQt_dPtvsc_, dQt_dQtvsc_, dQt_dPfhvdc_, dQt_dPthvdc_,
         dQt_dQfhvdc_, dQt_dQthvdc_, dQt_dm_, dQt_dtau_],
        n_rows=9, n_cols=11
    )

    return J


def calcYbus(Cf, Ct, Yshunt_bus: CxVec,
             R: Vec, X: Vec, G: Vec, B: Vec, m: Vec, tau: Vec, vtap_f: Vec, vtap_t: Vec) -> CSC:
    """
    Compute passive Ybus
    :param Cf:
    :param Ct:
    :param Yshunt_bus:
    :param R:
    :param X:
    :param G:
    :param B:
    :param m:
    :param tau:
    :param vtap_f:
    :param vtap_t:
    :return:
    """
    ys = 1.0 / make_complex(R, X + 1e-20)  # series admittance
    bc2 = make_complex(G, B) / 2.0  # shunt admittance
    yff = (ys + bc2) / (m * m * vtap_f * vtap_f)
    yft = -ys / (m * np.exp(-1.0j * tau) * vtap_f * vtap_t)
    ytf = -ys / (m * np.exp(1.0j * tau) * vtap_t * vtap_f)
    ytt = (ys + bc2) / (vtap_t * vtap_t)

    Yf = diags(yff) * Cf + diags(yft) * Ct
    Yt = diags(ytf) * Cf + diags(ytt) * Ct
    Ybus = Cf.T * Yf + Ct.T * Yt + diags(Yshunt_bus)

    return Ybus.tocsc()


@njit(cache=True)
def calcSf(k: IntVec, V: CxVec, F: IntVec, T: IntVec,
           R: Vec, X: Vec, G: Vec, B: Vec, m: Vec, tau: Vec, vtap_f: Vec, vtap_t: Vec):
    """
    Compute Sf for pi branches
    :param k:
    :param V:
    :param F:
    :param T:
    :param R:
    :param X:
    :param G:
    :param B:
    :param m:
    :param tau:
    :param vtap_f:
    :param vtap_t:
    :return:
    """
    ys = 1.0 / (R[k] + 1.0j * X[k] + 1e-20)  # series admittance
    bc2 = (G[k] + 1j * B[k]) / 2.0  # shunt admittance
    yff = (ys + bc2) / (m[k] * m[k] * vtap_f[k] * vtap_f[k])
    yft = -ys / (m[k] * np.exp(-1.0j * tau[k]) * vtap_f[k] * vtap_t[k])

    Vf = V[F[k]]
    Vt = V[T[k]]

    # Sf_cbr = (np.power(Vf, 2.0) * np.conj(yff) + Vf * Vt * np.conj(yft))
    If_cbr = Vf * yff + Vt * yft
    Sf_cbr = Vf * np.conj(If_cbr)

    return Sf_cbr


@njit(cache=True)
def calcSt(k: IntVec, V: CxVec, F: IntVec, T: IntVec,
           R: Vec, X: Vec, G: Vec, B: Vec, m: Vec, tau: Vec, vtap_f: Vec, vtap_t: Vec):
    """
    Compute St for pi branches
    :param k:
    :param V:
    :param F:
    :param T:
    :param R:
    :param X:
    :param G:
    :param B:
    :param m:
    :param tau:
    :param vtap_f:
    :param vtap_t:
    :return:
    """
    ys = 1.0 / (R[k] + 1.0j * X[k] + 1e-20)  # series admittance
    bc2 = (G[k] + 1j * B[k]) / 2.0  # shunt admittance

    ytf = -ys / (m[k] * np.exp(1.0j * tau[k]) * vtap_t[k] * vtap_f[k])
    ytt = (ys + bc2) / (vtap_t[k] * vtap_t[k])

    Vf = V[F[k]]
    Vt = V[T[k]]

    It_cbr = Vt * ytt + Vf * ytf
    St_cbr = Vt * np.conj(It_cbr)

    # St_cbr = (np.power(Vt, 2.0) * np.conj(ytt) + Vt * Vf * np.conj(ytf))

    return St_cbr


@njit(cache=True)
def calc_flows_summation_per_bus(nbus: int,
                                 F_br: IntVec, T_br: IntVec, Sf_br: CxVec, St_br: CxVec,
                                 F_hvdc: IntVec, T_hvdc: IntVec, Sf_hvdc: CxVec, St_hvdc: CxVec,
                                 F_vsc: IntVec, T_vsc: IntVec, Pf_vsc: Vec, St_vsc: CxVec) -> CxVec:
    """
    Summation of magnitudes per bus (complex)
    :param nbus:
    :param F_br:
    :param T_br:
    :param Sf_br:
    :param St_br:
    :param F_hvdc:
    :param T_hvdc:
    :param Sf_hvdc:
    :param St_hvdc:
    :param F_vsc:
    :param T_vsc:
    :param Pf_vsc:
    :param St_vsc:
    :return:
    """

    res = np.zeros(nbus, dtype=np.complex128)

    # Add branches
    for i in range(len(F_br)):
        res[F_br[i]] += Sf_br[i]
        res[T_br[i]] += St_br[i]

    # Add HVDC
    for i in range(len(F_hvdc)):
        res[F_hvdc[i]] += Sf_hvdc[i]
        res[T_hvdc[i]] += St_hvdc[i]

    # Add VSC
    for i in range(len(F_vsc)):
        res[F_vsc[i]] += Pf_vsc[i]
        res[T_vsc[i]] += St_vsc[i]

    return res


def calc_autodiff_jacobian(func: Callable[[Vec], Vec], x: Vec, h=1e-8) -> CSC:
    """
    Compute the Jacobian matrix of `func` at `x` using finite differences.

    :param func: function accepting a vector x and args, and returning either a vector or a
                 tuple where the first argument is a vector and the second.
    :param x: Point at which to evaluate the Jacobian (numpy array).
    :param h: Small step for finite difference.
    :return: Jacobian matrix as a CSC matrix.
    """
    nx = len(x)
    f0 = func(x)

    n_rows = len(f0)

    jac = lil_matrix((n_rows, nx))

    for j in range(nx):
        x_plus_h = np.copy(x)
        x_plus_h[j] += h
        f_plus_h = func(x_plus_h)
        row = (f_plus_h - f0) / h
        for i in range(n_rows):
            if row[i] != 0.0:
                jac[i, j] = row[i]

    return scipy_to_mat(jac.tocsc())


class PfGeneralizedFormulation(PfFormulationTemplate):

    def __init__(self, V0: CxVec, S0: CxVec, I0: CxVec, Y0: CxVec,
                 Qmin: Vec, Qmax: Vec,
                 nc: NumericalCircuit,
                 options: PowerFlowOptions,
                 logger: Logger):
        """
        Constructor
        :param V0: Initial voltage solution
        :param S0: Set power injections
        :param I0: Set current injections
        :param Y0: Set admittance injections
        :param nc: NumericalCircuit
        :param options: PowerFlowOptions
        :param logger: Logger (modified in-place)
        """
        PfFormulationTemplate.__init__(self, V0=V0, options=options)

        self.nc: NumericalCircuit = nc

        self.logger: Logger = logger

        self.S0: CxVec = S0
        self.I0: CxVec = I0
        self.Y0: CxVec = Y0

        self.Qmin = Qmin
        self.Qmax = Qmax

        # arrays for branch control types (nbr)
        # self.tap_module_control_mode = nc.active_branch_data.tap_module_control_mode
        # self.tap_controlled_buses = nc.active_branch_data.tap_phase_control_mode
        # self.tap_phase_control_mode = nc.active_branch_data.tap_controlled_buses
        self.F = nc.passive_branch_data.F
        self.T = nc.passive_branch_data.T

        # Indices ------------------------------------------------------------------------------------------------------

        # Bus indices
        self.bus_types = nc.bus_data.bus_types.copy()
        self.is_p_controlled = nc.bus_data.is_p_controlled.copy()
        self.is_q_controlled = nc.bus_data.is_q_controlled.copy()
        self.is_vm_controlled = nc.bus_data.is_vm_controlled.copy()
        self.is_va_controlled = nc.bus_data.is_va_controlled.copy()

        # HVDC LOOP
        for k in range(self.nc.hvdc_data.nelm):
            self.nc.bus_data.is_q_controlled[self.nc.hvdc_data.F[k]] = True
            self.nc.bus_data.is_q_controlled[self.nc.hvdc_data.T[k]] = True

        # Controllable Branch Indices
        self.u_cbr_m = np.zeros(0, dtype=int)
        self.u_cbr_tau = np.zeros(0, dtype=int)
        self.cbr = np.zeros(0, dtype=int)
        self.u_rel_cbr_m = np.zeros(0, dtype=int)
        self.u_rel_cbr_tau = np.zeros(0, dtype=int)
        self.k_cbr_pf = np.zeros(0, dtype=int)
        self.k_cbr_pt = np.zeros(0, dtype=int)
        self.k_cbr_qf = np.zeros(0, dtype=int)
        self.k_cbr_qt = np.zeros(0, dtype=int)
        self.cbr_pf_set = np.zeros(0, dtype=float)
        self.cbr_pt_set = np.zeros(0, dtype=float)
        self.cbr_qf_set = np.zeros(0, dtype=float)
        self.cbr_qt_set = np.zeros(0, dtype=float)
        self._analyze_branch_controls()
        self.cbr = np.union1d(self.u_cbr_m, self.u_cbr_tau)
        cbr_dic = {val: idx for idx, val in enumerate(self.cbr)}
        self.u_rel_cbr_m = np.array([cbr_dic[val] for val in self.u_cbr_m], dtype=np.int32)
        self.u_rel_cbr_t = np.array([cbr_dic[val] for val in self.u_cbr_tau], dtype=np.int32)

        # VSC Indices
        self.u_vsc_pf = np.zeros(0, dtype=int)
        self.u_vsc_pt = np.zeros(0, dtype=int)
        self.u_vsc_qt = np.zeros(0, dtype=int)
        self.k_vsc_pf = np.zeros(0, dtype=int)
        self.k_vsc_pt = np.zeros(0, dtype=int)
        self.k_vsc_qt = np.zeros(0, dtype=int)
        self.vsc_pf_set = np.zeros(0, dtype=float)
        self.vsc_pt_set = np.zeros(0, dtype=float)
        self.vsc_qt_set = np.zeros(0, dtype=float)
        self._analyze_vsc_controls()

        # HVDC Indices
        self.hvdc_droop_idx = np.zeros(0, dtype=int)
        self._analyze_hvdc_controls()

        # Bus indices
        self.i_u_vm = np.where(self.is_vm_controlled == 0)[0]
        self.i_u_va = np.where(self.is_va_controlled == 0)[0]
        self.i_k_p = np.where(self.is_p_controlled == 1)[0]
        self.i_k_q = np.where(self.is_q_controlled == 1)[0]

        # Unknowns -----------------------------------------------------------------------------------------------------
        # Va and Vm are set internally
        self.Pf_vsc = np.zeros(nc.vsc_data.nelm)
        self.Pt_vsc = np.zeros(nc.vsc_data.nelm)
        self.Qt_vsc = np.zeros(nc.vsc_data.nelm)
        self.Pf_hvdc = np.zeros(nc.hvdc_data.nelm)
        self.Qf_hvdc = np.zeros(nc.hvdc_data.nelm)
        self.Pt_hvdc = np.zeros(nc.hvdc_data.nelm)
        self.Qt_hvdc = np.zeros(nc.hvdc_data.nelm)
        self.m = np.ones(len(self.u_cbr_m))
        self.tau = np.zeros(len(self.u_cbr_tau))

        # set the VSC set-points
        self.Pf_vsc[self.k_vsc_pf] = self.vsc_pf_set / self.nc.Sbase
        self.Pt_vsc[self.k_vsc_pt] = self.vsc_pt_set / self.nc.Sbase
        self.Qt_vsc[self.k_vsc_qt] = self.vsc_qt_set / self.nc.Sbase

        # Controllable branches ----------------------------------------------------------------------------------------
        ys = 1.0 / (nc.passive_branch_data.R
                    + 1.0j * nc.passive_branch_data.X + 1e-20)  # series admittance
        bc2 = make_complex(nc.passive_branch_data.G, nc.passive_branch_data.B) / 2.0  # shunt admittance
        vtap_f = nc.passive_branch_data.virtual_tap_f
        vtap_t = nc.passive_branch_data.virtual_tap_t
        self.yff_cbr = (ys + bc2) / (vtap_f * vtap_f)
        self.yft_cbr = -ys / (vtap_f * vtap_t)
        self.ytf_cbr = -ys / (vtap_t * vtap_f)
        self.ytt_cbr = (ys + bc2) / (vtap_t * vtap_t)
        self.F_cbr = self.nc.passive_branch_data.F
        self.T_cbr = self.nc.passive_branch_data.T

        # This is fully constant and hence we could precompute it
        m0 = self.nc.active_branch_data.tap_module.copy()
        tau0 = self.nc.active_branch_data.tap_angle.copy()

        self.yff0 = self.yff_cbr / (m0 * m0)
        self.yft0 = self.yft_cbr / (m0 * np.exp(-1.0j * tau0))
        self.ytf0 = self.ytf_cbr / (m0 * np.exp(1.0j * tau0))
        self.ytt0 = self.ytt_cbr

        self.Ybus = calcYbus(Cf=self.nc.passive_branch_data.Cf,
                             Ct=self.nc.passive_branch_data.Ct,
                             Yshunt_bus=self.nc.shunt_data.get_injections_per_bus() / self.nc.Sbase,
                             R=self.nc.passive_branch_data.R,
                             X=self.nc.passive_branch_data.X,
                             G=self.nc.passive_branch_data.G,
                             B=self.nc.passive_branch_data.B,
                             m=self.nc.active_branch_data.tap_module,
                             tau=self.nc.active_branch_data.tap_angle,
                             vtap_f=self.nc.passive_branch_data.virtual_tap_f,
                             vtap_t=self.nc.passive_branch_data.virtual_tap_t)

        if self.options.verbose > 1:
            print("Ybus\n", self.Ybus.toarray())

    def update_Qlim_indices(self, i_u_vm: IntVec, i_k_q: IntVec) -> None:
        """
        Update the indices due to applying Q limits
        :param i_u_vm: Indices of unknown voltage magnitudes
        :param i_k_q: Indices of Q controlled buses
        """
        self.i_u_vm = i_u_vm
        self.i_k_q = i_k_q

    def analyze_bus_controls(self) -> None:
        """
        Analyze the bus indices from the boolean marked arrays
        """
        self.i_u_vm = np.where(self.is_vm_controlled == 0)[0]
        self.i_u_va = np.where(self.is_va_controlled == 0)[0]
        self.i_k_p = np.where(self.is_p_controlled == 1)[0]
        self.i_k_q = np.where(self.is_q_controlled == 1)[0]

    def _analyze_branch_controls(self) -> None:
        """
        Analyze the control branches and compute the indices
        """
        # Controllable Branch Indices
        u_cbr_m = list()
        u_cbr_tau = list()
        cbr = list()
        k_cbr_pf = list()
        k_cbr_pt = list()
        k_cbr_qf = list()
        k_cbr_qt = list()
        cbr_pf_set = list()
        cbr_pt_set = list()
        cbr_qf_set = list()
        cbr_qt_set = list()

        dic_old_to_new_bus = {val: idx for idx, val in enumerate(self.nc.bus_data.original_idx)}

        # CONTROLLABLE BRANCH LOOP
        count_overl = 0
        for k in range(self.nc.passive_branch_data.nelm):

            ctrl_m = self.nc.active_branch_data.tap_module_control_mode[k]
            ctrl_tau = self.nc.active_branch_data.tap_phase_control_mode[k]

            # analyze tap-module controls
            if ctrl_m == TapModuleControl.Vm:

                # Every bus controlled by m has to become a PQV bus
                bus_idx = self.nc.active_branch_data.tap_controlled_buses[k]
                new_bus_idx = dic_old_to_new_bus[bus_idx]
                # self.is_p_controlled[bus_idx] = True
                # self.is_q_controlled[bus_idx] = True
                if not self.is_vm_controlled[new_bus_idx]:
                    self.is_vm_controlled[new_bus_idx] = True
                    u_cbr_m.append(k)

            elif ctrl_m == TapModuleControl.Qf:
                u_cbr_m.append(k)
                k_cbr_qf.append(k)
                cbr_qf_set.append(self.nc.active_branch_data.Qset[k])

            elif ctrl_m == TapModuleControl.Qt:
                u_cbr_m.append(k)
                k_cbr_qt.append(k)
                cbr_qt_set.append(self.nc.active_branch_data.Qset[k])

            elif ctrl_m == TapModuleControl.fixed:
                # bus_idx = self.nc.active_branch_data.tap_controlled_buses[k]
                # self.is_vm_controlled[bus_idx] = False
                # self.m[k] = self.nc.active_branch_data.tap_module[k]
                pass

            elif ctrl_m == 0:
                pass

            else:
                raise Exception(f"Unknown tap phase module mode {ctrl_m}")

            # analyze tap-phase controls
            if ctrl_tau == TapPhaseControl.Pf:
                u_cbr_tau.append(k)
                k_cbr_pf.append(k)
                cbr_pf_set.append(self.nc.active_branch_data.Pset[k])

            elif ctrl_tau == TapPhaseControl.Pt:
                u_cbr_tau.append(k)
                k_cbr_pt.append(k)
                cbr_pt_set.append(self.nc.active_branch_data.Pset[k])

            elif ctrl_tau == TapPhaseControl.fixed:
                # self.tau[k] = self.nc.active_branch_data.tap_angle[k]
                pass

            elif ctrl_tau == 0:
                pass

            else:
                raise Exception(f"Unknown tap phase control mode {ctrl_tau}")

        print('count_overl', count_overl)
        self.u_cbr_m = np.array(u_cbr_m, dtype=int)
        self.u_cbr_tau = np.array(u_cbr_tau, dtype=int)
        self.cbr = np.array(cbr, dtype=int)
        self.k_cbr_pf = np.array(k_cbr_pf, dtype=int)
        self.k_cbr_pt = np.array(k_cbr_pt, dtype=int)
        self.k_cbr_qf = np.array(k_cbr_qf, dtype=int)
        self.k_cbr_qt = np.array(k_cbr_qt, dtype=int)
        self.cbr_pf_set = np.array(cbr_pf_set, dtype=float)
        self.cbr_pt_set = np.array(cbr_pt_set, dtype=float)
        self.cbr_qf_set = np.array(cbr_qf_set, dtype=float)
        self.cbr_qt_set = np.array(cbr_qt_set, dtype=float)

    def _analyze_vsc_controls(self) -> None:
        """
        Analyze the control branches and compute the indices
        :return: None
        """

        # VSC Indices
        # vsc = list()
        u_vsc_pf = list()
        u_vsc_pt = list()
        u_vsc_qt = list()
        k_vsc_pf = list()
        k_vsc_pt = list()
        k_vsc_qt = list()
        vsc_pf_set = list()
        vsc_pt_set = list()
        vsc_qt_set = list()

        # VSC LOOP
        for k in range(self.nc.vsc_data.nelm):
            # vsc.append(i)
            control1 = self.nc.vsc_data.control1[k]
            control2 = self.nc.vsc_data.control2[k]
            assert control1 != control2, f"VSC control types must be different for VSC indexed at {k}"
            control1_magnitude = self.nc.vsc_data.control1_val[k]
            control2_magnitude = self.nc.vsc_data.control2_val[k]
            control1_bus_device = self.nc.vsc_data.control1_bus_idx[k]
            control2_bus_device = self.nc.vsc_data.control2_bus_idx[k]
            control1_branch_device = self.nc.vsc_data.control1_branch_idx[k]
            control2_branch_device = self.nc.vsc_data.control2_branch_idx[k]

            """    

            Vm_dc = 'Vm_dc'
            Vm_ac = 'Vm_ac'
            Va_ac = 'Va_ac'
            Qac = 'Q_ac'
            Pdc = 'P_dc'
            Pac = 'P_ac'

            """

            if control1 == ConverterControlType.Vm_dc and control2 == ConverterControlType.Vm_dc:
                self.logger.add_error(
                    f"VSC control1 and control2 are the same for VSC indexed at {k},"
                    f" control1: {control1}, control2: {control2}")

            elif control1 == ConverterControlType.Vm_dc and control2 == ConverterControlType.Vm_ac:
                if control1_bus_device > -1:
                    self.is_vm_controlled[control1_bus_device] = True
                if control2_bus_device > -1:
                    self.is_vm_controlled[control2_bus_device] = True
                u_vsc_pf.append(k)
                u_vsc_pt.append(k)
                u_vsc_qt.append(k)

            elif control1 == ConverterControlType.Vm_dc and control2 == ConverterControlType.Va_ac:
                if control1_bus_device > -1:
                    self.is_vm_controlled[control1_bus_device] = True
                if control2_bus_device > -1:
                    self.is_va_controlled[control2_bus_device] = True
                u_vsc_pf.append(k)
                u_vsc_pt.append(k)
                u_vsc_qt.append(k)


            elif control1 == ConverterControlType.Vm_dc and control2 == ConverterControlType.Qac:
                if control1_bus_device > -1:
                    self.is_vm_controlled[control1_bus_device] = True
                if control2_bus_device > -1:
                    pass
                if control1_branch_device > -1:
                    pass
                if control2_branch_device > -1:
                    u_vsc_pf.append(control2_branch_device)
                    u_vsc_pt.append(control2_branch_device)

                    k_vsc_qt.append(control2_branch_device)

                    vsc_qt_set.append(control2_magnitude)

            elif control1 == ConverterControlType.Vm_dc and control2 == ConverterControlType.Pdc:
                if control1_bus_device > -1:
                    self.is_vm_controlled[control1_bus_device] = True
                if control2_bus_device > -1:
                    pass
                if control1_branch_device > -1:
                    pass
                if control2_branch_device > -1:
                    u_vsc_pt.append(control2_branch_device)
                    u_vsc_qt.append(control2_branch_device)

                    k_vsc_pf.append(control2_branch_device)

                    vsc_pf_set.append(control2_magnitude)

            elif control1 == ConverterControlType.Vm_dc and control2 == ConverterControlType.Pac:
                if control1_bus_device > -1:
                    self.is_vm_controlled[control1_bus_device] = True
                if control2_bus_device > -1:
                    pass
                if control1_branch_device > -1:
                    pass
                if control2_branch_device > -1:
                    u_vsc_pf.append(control2_branch_device)
                    u_vsc_qt.append(control2_branch_device)

                    k_vsc_pt.append(control2_branch_device)

                    vsc_pt_set.append(control2_magnitude)

            elif control1 == ConverterControlType.Vm_ac and control2 == ConverterControlType.Vm_dc:
                if control1_bus_device > -1:
                    self.is_vm_controlled[control1_bus_device] = True
                if control2_bus_device > -1:
                    self.is_vm_controlled[control2_bus_device] = True
                u_vsc_pf.append(k)
                u_vsc_pt.append(k)
                u_vsc_qt.append(k)

            elif control1 == ConverterControlType.Vm_ac and control2 == ConverterControlType.Vm_ac:
                self.logger.add_error(
                    f"VSC control1 and control2 are the same for VSC indexed at {k},"
                    f" control1: {control1}, control2: {control2}")

            elif control1 == ConverterControlType.Vm_ac and control2 == ConverterControlType.Va_ac:
                if control1_bus_device > -1:
                    self.is_vm_controlled[control1_bus_device] = True
                if control2_bus_device > -1:
                    self.is_va_controlled[control2_bus_device] = True
                u_vsc_pf.append(k)
                u_vsc_pt.append(k)
                u_vsc_qt.append(k)


            elif control1 == ConverterControlType.Vm_ac and control2 == ConverterControlType.Qac:
                if control1_bus_device > -1:
                    self.is_vm_controlled[control1_bus_device] = True
                if control2_bus_device > -1:
                    pass
                if control1_branch_device > -1:
                    pass
                if control2_branch_device > -1:
                    u_vsc_pf.append(control2_branch_device)
                    u_vsc_pt.append(control2_branch_device)
                    k_vsc_qt.append(control2_branch_device)
                    vsc_qt_set.append(control2_magnitude)

            elif control1 == ConverterControlType.Vm_ac and control2 == ConverterControlType.Pdc:
                if control1_bus_device > -1:
                    self.is_vm_controlled[control1_bus_device] = True
                if control2_bus_device > -1:
                    pass
                if control1_branch_device > -1:
                    pass
                if control2_branch_device > -1:
                    u_vsc_pt.append(control2_branch_device)
                    u_vsc_qt.append(control2_branch_device)
                    k_vsc_pf.append(control2_branch_device)
                    vsc_pf_set.append(control2_magnitude)

            elif control1 == ConverterControlType.Vm_ac and control2 == ConverterControlType.Pac:
                if control1_bus_device > -1:
                    self.is_vm_controlled[control1_bus_device] = True
                if control2_bus_device > -1:
                    pass
                if control1_branch_device > -1:
                    pass
                if control2_branch_device > -1:
                    u_vsc_pf.append(control2_branch_device)
                    u_vsc_qt.append(control2_branch_device)
                    k_vsc_pt.append(control2_branch_device)
                    vsc_pt_set.append(control2_magnitude)

            elif control1 == ConverterControlType.Va_ac and control2 == ConverterControlType.Vm_dc:
                if control1_bus_device > -1:
                    self.is_va_controlled[control1_bus_device] = True
                if control2_bus_device > -1:
                    self.is_vm_controlled[control2_bus_device] = True
                u_vsc_pf.append(k)
                u_vsc_pt.append(k)
                u_vsc_qt.append(k)

            elif control1 == ConverterControlType.Va_ac and control2 == ConverterControlType.Vm_ac:
                if control1_bus_device > -1:
                    self.is_va_controlled[control1_bus_device] = True
                if control2_bus_device > -1:
                    self.is_vm_controlled[control2_bus_device] = True
                u_vsc_pf.append(k)
                u_vsc_pt.append(k)
                u_vsc_qt.append(k)


            elif control1 == ConverterControlType.Va_ac and control2 == ConverterControlType.Va_ac:
                self.logger.add_error(
                    f"VSC control1 and control2 are the same for VSC indexed at {k},"
                    f" control1: {control1}, control2: {control2}")

            elif control1 == ConverterControlType.Va_ac and control2 == ConverterControlType.Qac:
                if control1_bus_device > -1:
                    self.is_va_controlled[control1_bus_device] = True
                if control2_bus_device > -1:
                    pass
                if control1_branch_device > -1:
                    pass
                if control2_branch_device > -1:
                    u_vsc_pf.append(control2_branch_device)
                    u_vsc_pt.append(control2_branch_device)
                    k_vsc_qt.append(control2_branch_device)
                    vsc_qt_set.append(control2_magnitude)

            elif control1 == ConverterControlType.Va_ac and control2 == ConverterControlType.Pdc:
                if control1_bus_device > -1:
                    self.is_va_controlled[control1_bus_device] = True
                if control2_bus_device > -1:
                    pass
                if control1_branch_device > -1:
                    pass
                if control2_branch_device > -1:
                    u_vsc_pt.append(control2_branch_device)
                    u_vsc_qt.append(control2_branch_device)
                    k_vsc_pf.append(control2_branch_device)
                    vsc_pf_set.append(control2_magnitude)

            elif control1 == ConverterControlType.Va_ac and control2 == ConverterControlType.Pac:
                if control1_bus_device > -1:
                    self.is_va_controlled[control1_bus_device] = True
                if control2_bus_device > -1:
                    pass
                if control1_branch_device > -1:
                    pass
                if control2_branch_device > -1:
                    u_vsc_pf.append(control2_branch_device)
                    u_vsc_qt.append(control2_branch_device)
                    k_vsc_pt.append(control2_branch_device)
                    vsc_pt_set.append(control2_magnitude)

            elif control1 == ConverterControlType.Qac and control2 == ConverterControlType.Vm_dc:
                if control2_bus_device > -1:
                    self.is_vm_controlled[control2_bus_device] = True
                if control1_branch_device > -1:
                    u_vsc_pf.append(control1_branch_device)
                    u_vsc_pt.append(control1_branch_device)
                    k_vsc_qt.append(control1_branch_device)
                    vsc_qt_set.append(control1_magnitude)

            elif control1 == ConverterControlType.Qac and control2 == ConverterControlType.Vm_ac:
                if control2_bus_device > -1:
                    self.is_vm_controlled[control2_bus_device] = True
                if control1_branch_device > -1:
                    u_vsc_pf.append(control1_branch_device)
                    u_vsc_pt.append(control1_branch_device)
                    k_vsc_qt.append(control1_branch_device)
                    vsc_qt_set.append(control1_magnitude)

            elif control1 == ConverterControlType.Qac and control2 == ConverterControlType.Va_ac:
                if control2_bus_device > -1:
                    self.is_va_controlled[control2_bus_device] = True
                if control1_branch_device > -1:
                    u_vsc_pf.append(control1_branch_device)
                    u_vsc_pt.append(control1_branch_device)
                    k_vsc_qt.append(control1_branch_device)
                    vsc_qt_set.append(control1_magnitude)

            elif control1 == ConverterControlType.Qac and control2 == ConverterControlType.Qac:
                self.logger.add_error(
                    f"VSC control1 and control2 are the same for VSC indexed at {k},"
                    f" control1: {control1}, control2: {control2}")

            elif control1 == ConverterControlType.Qac and control2 == ConverterControlType.Pdc:
                if control1_branch_device > -1:
                    u_vsc_pt.append(control1_branch_device)
                    k_vsc_qt.append(control1_branch_device)
                    vsc_qt_set.append(control1_magnitude)
                    k_vsc_pf.append(control2_branch_device)
                    vsc_pf_set.append(control2_magnitude)

            elif control1 == ConverterControlType.Qac and control2 == ConverterControlType.Pac:
                if control1_branch_device > -1:
                    u_vsc_pf.append(control1_branch_device)
                    k_vsc_pt.append(control2_branch_device)
                    k_vsc_qt.append(control1_branch_device)
                    vsc_qt_set.append(control1_magnitude)
                    vsc_pt_set.append(control2_magnitude)


            elif control1 == ConverterControlType.Pdc and control2 == ConverterControlType.Vm_dc:
                if control2_bus_device > -1:
                    self.is_vm_controlled[control2_bus_device] = True
                if control1_branch_device > -1:
                    u_vsc_pt.append(control1_branch_device)
                    u_vsc_qt.append(control1_branch_device)
                    k_vsc_pf.append(control1_branch_device)
                    vsc_pf_set.append(control1_magnitude)

            elif control1 == ConverterControlType.Pdc and control2 == ConverterControlType.Vm_ac:
                if control2_bus_device > -1:
                    self.is_vm_controlled[control2_bus_device] = True
                if control1_branch_device > -1:
                    u_vsc_pt.append(control1_branch_device)
                    u_vsc_qt.append(control1_branch_device)
                    k_vsc_pf.append(control1_branch_device)
                    vsc_pf_set.append(control1_magnitude)

            elif control1 == ConverterControlType.Pdc and control2 == ConverterControlType.Va_ac:
                if control2_bus_device > -1:
                    self.is_va_controlled[control2_bus_device] = True
                if control1_branch_device > -1:
                    u_vsc_pt.append(control1_branch_device)
                    u_vsc_qt.append(control1_branch_device)
                    k_vsc_pf.append(control1_branch_device)
                    vsc_pf_set.append(control1_magnitude)

            elif control1 == ConverterControlType.Pdc and control2 == ConverterControlType.Qac:
                if control1_branch_device > -1:
                    k_vsc_pf.append(control1_branch_device)
                    vsc_pf_set.append(control1_magnitude)
                    k_vsc_qt.append(control2_branch_device)
                    vsc_qt_set.append(control2_magnitude)
                    u_vsc_pt.append(control1_branch_device)

            elif control1 == ConverterControlType.Pdc and control2 == ConverterControlType.Pdc:
                self.logger.add_error(
                    f"VSC control1 and control2 are the same for VSC indexed at {k},"
                    f" control1: {control1}, control2: {control2}")

            elif control1 == ConverterControlType.Pdc and control2 == ConverterControlType.Pac:
                if control1_branch_device > -1:
                    u_vsc_pt.append(control1_branch_device)
                    u_vsc_qt.append(control1_branch_device)
                    k_vsc_pt.append(control1_branch_device)
                    vsc_pt_set.append(control1_magnitude)

            elif control1 == ConverterControlType.Pac and control2 == ConverterControlType.Vm_dc:
                if control2_bus_device > -1:
                    self.is_vm_controlled[control2_bus_device] = True
                if control1_branch_device > -1:
                    u_vsc_pf.append(control1_branch_device)
                    u_vsc_qt.append(control1_branch_device)
                    k_vsc_pf.append(control1_branch_device)
                    vsc_pf_set.append(control1_magnitude)

            elif control1 == ConverterControlType.Pac and control2 == ConverterControlType.Vm_ac:
                if control2_bus_device > -1:
                    self.is_vm_controlled[control2_bus_device] = True
                if control1_branch_device > -1:
                    u_vsc_pf.append(control1_branch_device)
                    u_vsc_qt.append(control1_branch_device)
                    k_vsc_pt.append(control1_branch_device)
                    vsc_pt_set.append(control1_magnitude)

            elif control1 == ConverterControlType.Pac and control2 == ConverterControlType.Va_ac:
                if control2_bus_device > -1:
                    self.is_va_controlled[control2_bus_device] = True
                if control1_branch_device > -1:
                    u_vsc_pf.append(control1_branch_device)
                    u_vsc_qt.append(control1_branch_device)
                    k_vsc_pt.append(control1_branch_device)
                    vsc_pt_set.append(control1_magnitude)

            elif control1 == ConverterControlType.Pac and control2 == ConverterControlType.Qac:
                if control1_branch_device > -1:
                    u_vsc_pf.append(control1_branch_device)
                    k_vsc_pt.append(control1_branch_device)
                    k_vsc_qt.append(control1_branch_device)
                    vsc_qt_set.append(control1_magnitude)
                    vsc_pt_set.append(control1_magnitude)

            elif control1 == ConverterControlType.Pac and control2 == ConverterControlType.Pdc:
                if control1_branch_device > -1:
                    u_vsc_pf.append(control1_branch_device)
                    u_vsc_qt.append(control1_branch_device)
                    k_vsc_pt.append(control1_branch_device)
                    vsc_pt_set.append(control1_magnitude)

            elif control1 == ConverterControlType.Pac and control2 == ConverterControlType.Pac:
                self.logger.add_error(
                    f"VSC control1 and control2 are the same for VSC indexed at {k},"
                    f" control1: {control1}, control2: {control2}")

        # self.vsc = np.array(vsc, dtype=int)
        self.u_vsc_pf = np.array(u_vsc_pf, dtype=int)
        self.u_vsc_pt = np.array(u_vsc_pt, dtype=int)
        self.u_vsc_qt = np.array(u_vsc_qt, dtype=int)
        self.k_vsc_pf = np.array(k_vsc_pf, dtype=int)
        self.k_vsc_pt = np.array(k_vsc_pt, dtype=int)
        self.k_vsc_qt = np.array(k_vsc_qt, dtype=int)
        self.vsc_pf_set = np.array(vsc_pf_set, dtype=float)
        self.vsc_pt_set = np.array(vsc_pt_set, dtype=float)
        self.vsc_qt_set = np.array(vsc_qt_set, dtype=float)


    def _analyze_vsc_controls_old(self) -> None:
        """
        Analyze the control branches and compute the indices
        :return: None
        """

        # VSC Indices
        # vsc = list()
        u_vsc_pf = list()
        u_vsc_pt = list()
        u_vsc_qt = list()
        k_vsc_pf = list()
        k_vsc_pt = list()
        k_vsc_qt = list()
        vsc_pf_set = list()
        vsc_pt_set = list()
        vsc_qt_set = list()

        # VSC LOOP
        for k in range(self.nc.vsc_data.nelm):
            # vsc.append(i)
            control1 = self.nc.vsc_data.control1[k]
            control2 = self.nc.vsc_data.control2[k]
            assert control1 != control2, f"VSC control types must be different for VSC indexed at {k}"
            control1_magnitude = self.nc.vsc_data.control1_val[k]
            control2_magnitude = self.nc.vsc_data.control2_val[k]
            control1_bus_device = self.nc.vsc_data.control1_bus_idx[k]
            control2_bus_device = self.nc.vsc_data.control2_bus_idx[k]
            control1_branch_device = self.nc.vsc_data.control1_branch_idx[k]
            control2_branch_device = self.nc.vsc_data.control2_branch_idx[k]

            """"    

            Vm_dc = 'Vm_dc'
            Vm_ac = 'Vm_ac'
            Va_ac = 'Va_ac'
            Qac = 'Q_ac'
            Pdc = 'P_dc'
            Pac = 'P_ac'


            """
            if control1 == ConverterControlType.Vm_dc:
                if control2 == ConverterControlType.Vm_dc:
                    self.logger.add_error(
                        f"VSC control1 and control2 are the same for VSC indexed at {k},"
                        f" control1: {control1}, control2: {control2}")
                elif control2 == ConverterControlType.Vm_ac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                elif control2 == ConverterControlType.Va_ac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        self.is_va_controlled[control2_bus_device] = True
                elif control2 == ConverterControlType.Qac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                        pass

                    if control1_branch_device > -1:
                        # self.u_vsc_pf.append(control1_branch_device)
                        # self.u_vsc_pt.append(control1_branch_device)
                        # self.u_vsc_qt.append(control1_branch_device)

                        # self.k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)

                        # self.vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                        pass

                    if control2_branch_device > -1:
                        u_vsc_pf.append(control2_branch_device)
                        u_vsc_pt.append(control2_branch_device)
                        # self.u_vsc_qt.append(control2_branch_device)

                        # self.k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        k_vsc_qt.append(control2_branch_device)

                        # self.vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        vsc_qt_set.append(control2_magnitude)

                elif control2 == ConverterControlType.Pdc:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                        pass

                    if control1_branch_device > -1:
                        # self.u_vsc_pf.append(control1_branch_device)
                        # self.u_vsc_pt.append(control1_branch_device)
                        # self.u_vsc_qt.append(control1_branch_device)

                        # self.k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)

                        # self.vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                        pass

                    if control2_branch_device > -1:
                        # self.u_vsc_pf.append(control2_branch_device)
                        u_vsc_pt.append(control2_branch_device)
                        u_vsc_qt.append(control2_branch_device)

                        k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)

                        vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)

                elif control2 == ConverterControlType.Pac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                        pass
                    if control1_branch_device > -1:
                        # self.u_vsc_pf.append(control1_branch_device)
                        # self.u_vsc_pt.append(control1_branch_device)
                        # self.u_vsc_qt.append(control1_branch_device)
                        # self.k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)
                        # self.vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                        pass
                    if control2_branch_device > -1:
                        u_vsc_pf.append(control2_branch_device)
                        # self.u_vsc_pt.append(control2_branch_device)
                        u_vsc_qt.append(control2_branch_device)

                        # self.k_vsc_pf.append(control2_branch_device)
                        k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)

                        # self.vsc_pf_set.append(control2_magnitude)
                        vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)

                else:
                    raise Exception(f"Unknown control type {control2}")

            elif control1 == ConverterControlType.Vm_ac:
                if control2 == ConverterControlType.Vm_dc:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                elif control2 == ConverterControlType.Vm_ac:
                    self.logger.add_error(
                        f"VSC control1 and control2 are the same for VSC indexed at {k},"
                        f" control1: {control1}, control2: {control2}")

                elif control2 == ConverterControlType.Va_ac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        self.is_va_controlled[control2_bus_device] = True

                elif control2 == ConverterControlType.Qac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                        pass
                    if control1_branch_device > -1:
                        # self.u_vsc_pf.append(control1_branch_device)
                        # self.u_vsc_pt.append(control1_branch_device)
                        # self.u_vsc_qt.append(control1_branch_device)
                        # self.k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)
                        # self.vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                        pass
                    if control2_branch_device > -1:
                        u_vsc_pf.append(control2_branch_device)
                        u_vsc_pt.append(control2_branch_device)
                        # self.u_vsc_qt.append(control2_branch_device)

                        # self.k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        k_vsc_qt.append(control2_branch_device)

                        # self.vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        vsc_qt_set.append(control2_magnitude)

                elif control2 == ConverterControlType.Pdc:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                        pass
                    if control1_branch_device > -1:
                        # self.u_vsc_pf.append(control1_branch_device)
                        # self.u_vsc_pt.append(control1_branch_device)
                        # self.u_vsc_qt.append(control1_branch_device)
                        # self.k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)
                        # self.vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                        pass
                    if control2_branch_device > -1:
                        # self.u_vsc_pf.append(control2_branch_device)
                        u_vsc_pt.append(control2_branch_device)
                        u_vsc_qt.append(control2_branch_device)

                        k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)

                        vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)

                elif control2 == ConverterControlType.Pac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                        pass
                    if control1_branch_device > -1:
                        # self.u_vsc_pf.append(control1_branch_device)
                        # self.u_vsc_pt.append(control1_branch_device)
                        # self.u_vsc_qt.append(control1_branch_device)
                        # self.k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)
                        # self.vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                        pass
                    if control2_branch_device > -1:
                        u_vsc_pf.append(control2_branch_device)
                        # self.u_vsc_pt.append(control2_branch_device)
                        u_vsc_qt.append(control2_branch_device)

                        # self.k_vsc_pf.append(control2_branch_device)
                        k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)

                        # self.vsc_pf_set.append(control2_magnitude)
                        vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)

                else:
                    raise Exception(f"Unknown control type {control2}")

            elif control1 == ConverterControlType.Va_ac:
                if control2 == ConverterControlType.Vm_dc:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        self.is_va_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True

                elif control2 == ConverterControlType.Vm_ac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        self.is_va_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True

                elif control2 == ConverterControlType.Va_ac:
                    self.logger.add_error(
                        f"VSC control1 and control2 are the same for VSC indexed at {k},"
                        f" control1: {control1}, control2: {control2}")

                elif control2 == ConverterControlType.Qac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        self.is_va_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                        pass
                    if control1_branch_device > -1:
                        # self.u_vsc_pf.append(control1_branch_device)
                        # self.u_vsc_pt.append(control1_branch_device)
                        # self.u_vsc_qt.append(control1_branch_device)
                        # self.k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)
                        # self.vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                        pass
                    if control2_branch_device > -1:
                        u_vsc_pf.append(control2_branch_device)
                        u_vsc_pt.append(control2_branch_device)
                        # self.u_vsc_qt.append(control2_branch_device)

                        # self.k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        k_vsc_qt.append(control2_branch_device)

                        # self.vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        vsc_qt_set.append(control2_magnitude)

                elif control2 == ConverterControlType.Pdc:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        self.is_va_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                        pass
                    if control1_branch_device > -1:
                        # self.u_vsc_pf.append(control1_branch_device)
                        # self.u_vsc_pt.append(control1_branch_device)
                        # self.u_vsc_qt.append(control1_branch_device)
                        # self.k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)
                        # self.vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                        pass
                    if control2_branch_device > -1:
                        # self.u_vsc_pf.append(control2_branch_device)
                        u_vsc_pt.append(control2_branch_device)
                        u_vsc_qt.append(control2_branch_device)

                        k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)

                        vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)

                elif control2 == ConverterControlType.Pac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        self.is_va_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                        pass
                    if control1_branch_device > -1:
                        # self.u_vsc_pf.append(control1_branch_device)
                        # self.u_vsc_pt.append(control1_branch_device)
                        # self.u_vsc_qt.append(control1_branch_device)
                        # self.k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)
                        # self.vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                        pass
                    if control2_branch_device > -1:
                        u_vsc_pf.append(control2_branch_device)
                        # self.u_vsc_pt.append(control2_branch_device)
                        u_vsc_qt.append(control2_branch_device)

                        # self.k_vsc_pf.append(control2_branch_device)
                        k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)

                        # self.vsc_pf_set.append(control2_magnitude)
                        vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)

                else:
                    raise Exception(f"Unknown control type {control2}")

            elif control1 == ConverterControlType.Qac:
                if control2 == ConverterControlType.Vm_dc:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                        pass
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                    if control1_branch_device > -1:
                        u_vsc_pf.append(control1_branch_device)
                        u_vsc_pt.append(control1_branch_device)
                        # self.u_vsc_qt.append(control1_branch_device)

                        # self.k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        k_vsc_qt.append(control1_branch_device)

                        # self.vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        vsc_qt_set.append(control1_magnitude)
                    if control2_branch_device > -1:
                        # self.u_vsc_pf.append(control2_branch_device)
                        # self.u_vsc_pt.append(control2_branch_device)
                        # self.u_vsc_qt.append(control2_branch_device)
                        # self.k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)
                        # self.vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)
                        pass


                elif control2 == ConverterControlType.Vm_ac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                        pass
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                    if control1_branch_device > -1:
                        u_vsc_pf.append(control1_branch_device)
                        u_vsc_pt.append(control1_branch_device)
                        # self.u_vsc_qt.append(control1_branch_device)

                        # self.k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        k_vsc_qt.append(control1_branch_device)

                        # self.vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        vsc_qt_set.append(control1_magnitude)
                    if control2_branch_device > -1:
                        # self.u_vsc_pf.append(control2_branch_device)
                        # self.u_vsc_pt.append(control2_branch_device)
                        # self.u_vsc_qt.append(control2_branch_device)
                        # self.k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)
                        # self.vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)
                        pass

                elif control2 == ConverterControlType.Va_ac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                        pass
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        self.is_va_controlled[control2_bus_device] = True
                    if control1_branch_device > -1:
                        u_vsc_pf.append(control1_branch_device)
                        u_vsc_pt.append(control1_branch_device)
                        # self.u_vsc_qt.append(control1_branch_device)

                        # self.k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        k_vsc_qt.append(control1_branch_device)

                        # self.vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        vsc_qt_set.append(control1_magnitude)
                    if control2_branch_device > -1:
                        # self.u_vsc_pf.append(control2_branch_device)
                        # self.u_vsc_pt.append(control2_branch_device)
                        # self.u_vsc_qt.append(control2_branch_device)
                        # self.k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)
                        # self.vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)
                        pass
                elif control2 == ConverterControlType.Qac:
                    self.logger.add_error(
                        f"VSC control1 and control2 are the same for VSC indexed at {k},"
                        f" control1: {control1}, control2: {control2}")
                elif control2 == ConverterControlType.Pdc:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                        pass
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                        pass
                    if control1_branch_device > -1:
                        u_vsc_pf.append(control1_branch_device)
                        u_vsc_pt.append(control1_branch_device)
                        # self.u_vsc_qt.append(control1_branch_device)

                        # self.k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        k_vsc_qt.append(control1_branch_device)

                        # self.vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        vsc_qt_set.append(control1_magnitude)
                    if control2_branch_device > -1:
                        # self.u_vsc_pf.append(control2_branch_device)
                        u_vsc_pt.append(control2_branch_device)
                        u_vsc_qt.append(control2_branch_device)

                        k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)

                        vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)
                        pass
                elif control2 == ConverterControlType.Pac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                        pass
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                        pass
                    if control1_branch_device > -1:
                        u_vsc_pf.append(control1_branch_device)
                        u_vsc_pt.append(control1_branch_device)
                        # self.u_vsc_qt.append(control1_branch_device)

                        # self.k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        k_vsc_qt.append(control1_branch_device)

                        # self.vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        vsc_qt_set.append(control1_magnitude)
                    if control2_branch_device > -1:
                        u_vsc_pf.append(control2_branch_device)
                        # self.u_vsc_pt.append(control2_branch_device)
                        u_vsc_qt.append(control2_branch_device)

                        # self.k_vsc_pf.append(control2_branch_device)
                        k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)

                        # self.vsc_pf_set.append(control2_magnitude)
                        vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)
                else:
                    raise Exception(f"Unknown control type {control2}")

            elif control1 == ConverterControlType.Pdc:

                if control2 == ConverterControlType.Vm_dc:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                        pass
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                    if control1_branch_device > -1:
                        # self.u_vsc_pf.append(control1_branch_device)
                        u_vsc_pt.append(control1_branch_device)
                        u_vsc_qt.append(control1_branch_device)

                        k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)

                        vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                    if control2_branch_device > -1:
                        # self.u_vsc_pf.append(control2_branch_device)
                        # self.u_vsc_pt.append(control2_branch_device)
                        # self.u_vsc_qt.append(control2_branch_device)
                        # self.k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)
                        # self.vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)
                        pass
                elif control2 == ConverterControlType.Vm_ac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                        pass
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                    if control1_branch_device > -1:
                        # self.u_vsc_pf.append(control1_branch_device)
                        u_vsc_pt.append(control1_branch_device)
                        u_vsc_qt.append(control1_branch_device)

                        k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)

                        vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                    if control2_branch_device > -1:
                        # self.u_vsc_pf.append(control2_branch_device)
                        # self.u_vsc_pt.append(control2_branch_device)
                        # self.u_vsc_qt.append(control2_branch_device)
                        # self.k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)
                        # self.vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)
                        pass
                elif control2 == ConverterControlType.Va_ac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                        pass
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        self.is_va_controlled[control2_bus_device] = True
                    if control1_branch_device > -1:
                        # self.u_vsc_pf.append(control1_branch_device)
                        u_vsc_pt.append(control1_branch_device)
                        u_vsc_qt.append(control1_branch_device)

                        k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)

                        vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                    if control2_branch_device > -1:
                        # self.u_vsc_pf.append(control2_branch_device)
                        # self.u_vsc_pt.append(control2_branch_device)
                        # self.u_vsc_qt.append(control2_branch_device)
                        # self.k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)
                        # self.vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)
                        pass
                elif control2 == ConverterControlType.Qac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                        pass
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                        pass
                    if control1_branch_device > -1:
                        # self.u_vsc_pf.append(control1_branch_device)
                        u_vsc_pt.append(control1_branch_device)
                        u_vsc_qt.append(control1_branch_device)

                        k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)

                        vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                    if control2_branch_device > -1:
                        u_vsc_pf.append(control2_branch_device)
                        u_vsc_pt.append(control2_branch_device)
                        # self.u_vsc_qt.append(control2_branch_device)

                        # self.k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        k_vsc_qt.append(control2_branch_device)

                        # self.vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        vsc_qt_set.append(control2_magnitude)

                elif control2 == ConverterControlType.Pdc:
                    self.logger.add_error(
                        f"VSC control1 and control2 are the same for VSC indexed at {k},"
                        f" control1: {control1}, control2: {control2}")
                elif control2 == ConverterControlType.Pac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                        pass
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                        pass
                    if control1_branch_device > -1:
                        # self.u_vsc_pf.append(control1_branch_device)
                        u_vsc_pt.append(control1_branch_device)
                        u_vsc_qt.append(control1_branch_device)

                        k_vsc_pf.append(control1_branch_device)
                        # self.k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)

                        vsc_pf_set.append(control1_magnitude)
                        # self.vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                    if control2_branch_device > -1:
                        u_vsc_pf.append(control2_branch_device)
                        # self.u_vsc_pt.append(control2_branch_device)
                        u_vsc_qt.append(control2_branch_device)

                        # self.k_vsc_pf.append(control2_branch_device)
                        k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)

                        # self.vsc_pf_set.append(control2_magnitude)
                        vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)

                else:
                    raise Exception(f"Unknown control type {control2}")

            elif control1 == ConverterControlType.Pac:
                if control2 == ConverterControlType.Vm_dc:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                        pass
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                    if control1_branch_device > -1:
                        u_vsc_pf.append(control1_branch_device)
                        # self.u_vsc_pt.append(control1_branch_device)
                        u_vsc_qt.append(control1_branch_device)

                        # self.k_vsc_pf.append(control1_branch_device)
                        k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)

                        # self.vsc_pf_set.append(control1_magnitude)
                        vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                    if control2_branch_device > -1:
                        # self.u_vsc_pf.append(control2_branch_device)
                        # self.u_vsc_pt.append(control2_branch_device)
                        # self.u_vsc_qt.append(control2_branch_device)
                        # self.k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)
                        # self.vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)
                        pass
                elif control2 == ConverterControlType.Vm_ac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                        pass
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                    if control1_branch_device > -1:
                        u_vsc_pf.append(control1_branch_device)
                        # self.u_vsc_pt.append(control1_branch_device)
                        u_vsc_qt.append(control1_branch_device)

                        # self.k_vsc_pf.append(control1_branch_device)
                        k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)

                        # self.vsc_pf_set.append(control1_magnitude)
                        vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                    if control2_branch_device > -1:
                        # self.u_vsc_pf.append(control2_branch_device)
                        # self.u_vsc_pt.append(control2_branch_device)
                        # self.u_vsc_qt.append(control2_branch_device)
                        # self.k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)
                        # self.vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)
                        pass
                elif control2 == ConverterControlType.Va_ac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                        pass
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        self.is_va_controlled[control2_bus_device] = True
                    if control1_branch_device > -1:
                        u_vsc_pf.append(control1_branch_device)
                        # self.u_vsc_pt.append(control1_branch_device)
                        u_vsc_qt.append(control1_branch_device)

                        # self.k_vsc_pf.append(control1_branch_device)
                        k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)

                        # self.vsc_pf_set.append(control1_magnitude)
                        vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                    if control2_branch_device > -1:
                        # self.u_vsc_pf.append(control2_branch_device)
                        # self.u_vsc_pt.append(control2_branch_device)
                        # self.u_vsc_qt.append(control2_branch_device)
                        # self.k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)
                        # self.vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)
                        pass
                elif control2 == ConverterControlType.Qac:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                        pass
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                        pass
                    if control1_branch_device > -1:
                        u_vsc_pf.append(control1_branch_device)
                        # self.u_vsc_pt.append(control1_branch_device)
                        u_vsc_qt.append(control1_branch_device)

                        # self.k_vsc_pf.append(control1_branch_device)
                        k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)

                        # self.vsc_pf_set.append(control1_magnitude)
                        vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                    if control2_branch_device > -1:
                        u_vsc_pf.append(control2_branch_device)
                        u_vsc_pt.append(control2_branch_device)
                        # self.u_vsc_qt.append(control2_branch_device)

                        # self.k_vsc_pf.append(control2_branch_device)
                        # self.k_vsc_pt.append(control2_branch_device)
                        k_vsc_qt.append(control2_branch_device)

                        # self.vsc_pf_set.append(control2_magnitude)
                        # self.vsc_pt_set.append(control2_magnitude)
                        vsc_qt_set.append(control2_magnitude)
                elif control2 == ConverterControlType.Pdc:
                    if control1_bus_device > -1:
                        # self.is_p_controlled[control1_bus_device] = True
                        # self.is_q_controlled[control1_bus_device] = True
                        # self.is_vm_controlled[control1_bus_device] = True
                        # self.is_va_controlled[control1_bus_device] = True
                        pass
                    if control2_bus_device > -1:
                        # self.is_p_controlled[control2_bus_device] = True
                        # self.is_q_controlled[control2_bus_device] = True
                        # self.is_vm_controlled[control2_bus_device] = True
                        # self.is_va_controlled[control2_bus_device] = True
                        pass
                    if control1_branch_device > -1:
                        u_vsc_pf.append(control1_branch_device)
                        # self.u_vsc_pt.append(control1_branch_device)
                        u_vsc_qt.append(control1_branch_device)

                        # self.k_vsc_pf.append(control1_branch_device)
                        k_vsc_pt.append(control1_branch_device)
                        # self.k_vsc_qt.append(control1_branch_device)

                        # self.vsc_pf_set.append(control1_magnitude)
                        vsc_pt_set.append(control1_magnitude)
                        # self.vsc_qt_set.append(control1_magnitude)
                    if control2_branch_device > -1:
                        u_vsc_pf.append(control2_branch_device)
                        # self.u_vsc_pt.append(control2_branch_device)
                        u_vsc_qt.append(control2_branch_device)

                        # self.k_vsc_pf.append(control2_branch_device)
                        k_vsc_pt.append(control2_branch_device)
                        # self.k_vsc_qt.append(control2_branch_device)

                        # self.vsc_pf_set.append(control2_magnitude)
                        vsc_pt_set.append(control2_magnitude)
                        # self.vsc_qt_set.append(control2_magnitude)

                elif control2 == ConverterControlType.Pac:
                    self.logger.add_error(
                        f"VSC control1 and control2 are the same for VSC indexed at {k},"
                        f" control1: {control1}, control2: {control2}")
                else:
                    raise Exception(f"Unknown control type {control2}")

            else:
                raise Exception(f"Unknown control type {control1}")

        # self.vsc = np.array(vsc, dtype=int)
        self.u_vsc_pf = np.array(u_vsc_pf, dtype=int)
        self.u_vsc_pt = np.array(u_vsc_pt, dtype=int)
        self.u_vsc_qt = np.array(u_vsc_qt, dtype=int)
        self.k_vsc_pf = np.array(k_vsc_pf, dtype=int)
        self.k_vsc_pt = np.array(k_vsc_pt, dtype=int)
        self.k_vsc_qt = np.array(k_vsc_qt, dtype=int)
        self.vsc_pf_set = np.array(vsc_pf_set, dtype=float)
        self.vsc_pt_set = np.array(vsc_pt_set, dtype=float)
        self.vsc_qt_set = np.array(vsc_qt_set, dtype=float)

    def _analyze_hvdc_controls(self) -> None:
        """
        Analyze the control branches and compute the indices
        :return: None
        """

        # HVDC Indices
        hvdc_droop_idx = list()

        # HVDC LOOP
        for k in range(self.nc.hvdc_data.nelm):
            # hvdc.append(k)
            # self.nc.bus_data.is_q_controlled[self.nc.hvdc_data.bus_f[k]] = True
            # self.nc.bus_data.is_q_controlled[self.nc.hvdc_data.bus_t[k]] = True
            # self.nc.bus_data.bus_types[self.nc.hvdc_data.bus_f[k]] = BusMode.PQV
            if self.nc.hvdc_data.control_mode[k] == HvdcControlType.type_0_free:
                hvdc_droop_idx.append(k)

        # self.hvdc = np.array(hvdc, dtype=int)
        self.hvdc_droop_idx = np.array(hvdc_droop_idx)

    def x2var(self, x: Vec) -> None:
        """
        Convert X to decission variables
        :param x: solution vector
        """
        a = len(self.i_u_va)
        b = a + len(self.i_u_vm)
        c = b + len(self.u_vsc_pf)
        d = c + len(self.u_vsc_pt)
        e = d + len(self.u_vsc_qt)
        f = e + self.nc.hvdc_data.nelm
        g = f + self.nc.hvdc_data.nelm
        h = g + self.nc.hvdc_data.nelm
        i = h + self.nc.hvdc_data.nelm
        j = i + len(self.u_cbr_m)
        k = j + len(self.u_cbr_tau)

        # update the vectors
        self.Va[self.i_u_va] = x[0:a]
        self.Vm[self.i_u_vm] = x[a:b]
        self.Pf_vsc[self.u_vsc_pf] = x[b:c]
        self.Pt_vsc[self.u_vsc_pt] = x[c:d]
        self.Qt_vsc[self.u_vsc_qt] = x[d:e]
        self.Pf_hvdc = x[e:f]
        self.Pt_hvdc = x[f:g]
        self.Qf_hvdc = x[g:h]
        self.Qt_hvdc = x[h:i]
        self.m = x[i:j]
        self.tau = x[j:k]

    def var2x(self) -> Vec:
        """
        Convert the internal decision variables into the vector
        :return: Vector
        """
        return np.r_[
            self.Va[self.i_u_va],
            self.Vm[self.i_u_vm],
            self.Pf_vsc[self.u_vsc_pf],
            self.Pt_vsc[self.u_vsc_pt],
            self.Qt_vsc[self.u_vsc_qt],
            self.Pf_hvdc,
            self.Pt_hvdc,
            self.Qf_hvdc,
            self.Qt_hvdc,
            self.m,
            self.tau
        ]

    def size(self) -> int:
        """
        Size of the jacobian matrix
        :return:
        """
        return (len(self.i_u_vm)
                + len(self.i_u_va)
                + len(self.u_vsc_pf)
                + len(self.u_vsc_pt)
                + len(self.u_vsc_qt)
                + self.nc.hvdc_data.nelm
                + self.nc.hvdc_data.nelm
                + self.nc.hvdc_data.nelm
                + self.nc.hvdc_data.nelm
                + len(self.u_cbr_m)
                + len(self.u_cbr_tau))

    def compute_f(self, x: Vec) -> Vec:
        """
        Compute the residual vector
        :param x: Solution vector
        :return: Residual vector
        """

        nhvdc = self.nc.hvdc_data.nelm

        a = len(self.i_u_va)
        b = a + len(self.i_u_vm)
        c = b + len(self.u_vsc_pf)
        d = c + len(self.u_vsc_pt)
        e = d + len(self.u_vsc_qt)
        f = e + nhvdc
        g = f + nhvdc
        h = g + nhvdc
        i = h + nhvdc
        j = i + len(self.u_cbr_m)
        k = j + len(self.u_cbr_tau)

        # copy the sliceable vectors
        Vm = self.Vm.copy()
        Va = self.Va.copy()
        Pf_vsc = self.Pf_vsc.copy()
        Pt_vsc = self.Pt_vsc.copy()
        Qt_vsc = self.Qt_vsc.copy()

        # update the vectors
        Va[self.i_u_va] = x[0:a]
        Vm[self.i_u_vm] = x[a:b]
        Pf_vsc[self.u_vsc_pf] = x[b:c]
        Pt_vsc[self.u_vsc_pt] = x[c:d]
        Qt_vsc[self.u_vsc_qt] = x[d:e]
        Pf_hvdc = x[e:f]
        Pt_hvdc = x[f:g]
        Qf_hvdc = x[g:h]
        Qt_hvdc = x[h:i]
        m = x[i:j]
        tau = x[j:k]

        # Passive branches ---------------------------------------------------------------------------------------------

        # remember that Ybus here is computed with the fixed taps
        V = polar_to_rect(Vm, Va)
        Sbus = compute_zip_power(self.S0, self.I0, self.Y0, Vm)
        Scalc_passive = compute_power(self.Ybus, V)

        # Controllable branches ----------------------------------------------------------------------------------------
        # Power at the controlled branches
        m2 = self.nc.active_branch_data.tap_module.copy()
        tau2 = self.nc.active_branch_data.tap_angle.copy()
        m2[self.u_cbr_m] = m
        tau2[self.u_cbr_tau] = tau

        yff = (self.yff_cbr / (m2 * m2))
        yft = self.yft_cbr / (m2 * np.exp(-1.0j * tau2))
        ytf = self.ytf_cbr / (m2 * np.exp(1.0j * tau2))
        ytt = self.ytt_cbr

        Vf_cbr = V[self.F_cbr[self.cbr]]
        Vt_cbr = V[self.T_cbr[self.cbr]]
        yff_ = yff[self.cbr]
        yft_ = yft[self.cbr]
        ytf_ = ytf[self.cbr]
        ytt_ = ytt[self.cbr]
        yff0_ = self.yff0[self.cbr]
        yft0_ = self.yft0[self.cbr]
        ytf0_ = self.ytf0[self.cbr]
        ytt0_ = self.ytt0[self.cbr]

        Sf_cbr = (Vf_cbr * np.conj(Vf_cbr) * np.conj(yff_ - yff0_) + Vf_cbr * np.conj(Vt_cbr) * np.conj(yft_ - yft0_))
        St_cbr = (Vt_cbr * np.conj(Vt_cbr) * np.conj(ytt_ - ytt0_) + Vt_cbr * np.conj(Vf_cbr) * np.conj(ytf_ - ytf0_))

        # difference between the actual power and the power calculated with the passive term (initial admittance)
        # AScalc_cbr = np.zeros(self.nc.bus_data.nbus, dtype=complex)
        # AScalc_cbr[self.F_cbr[self.cbr]] += Sf_cbr
        # AScalc_cbr[self.T_cbr[self.cbr]] += St_cbr

        Pf_cbr = calcSf(k=self.k_cbr_pf,
                        V=V,
                        F=self.nc.passive_branch_data.F,
                        T=self.nc.passive_branch_data.T,
                        R=self.nc.passive_branch_data.R,
                        X=self.nc.passive_branch_data.X,
                        G=self.nc.passive_branch_data.G,
                        B=self.nc.passive_branch_data.B,
                        m=m2,
                        tau=tau2,
                        vtap_f=self.nc.passive_branch_data.virtual_tap_f,
                        vtap_t=self.nc.passive_branch_data.virtual_tap_t).real

        Pt_cbr = calcSt(k=self.k_cbr_pt,
                        V=V,
                        F=self.nc.passive_branch_data.F,
                        T=self.nc.passive_branch_data.T,
                        R=self.nc.passive_branch_data.R,
                        X=self.nc.passive_branch_data.X,
                        G=self.nc.passive_branch_data.G,
                        B=self.nc.passive_branch_data.B,
                        m=m2,
                        tau=tau2,
                        vtap_f=self.nc.passive_branch_data.virtual_tap_f,
                        vtap_t=self.nc.passive_branch_data.virtual_tap_t).real

        Qf_cbr = calcSf(k=self.k_cbr_qf,
                        V=V,
                        F=self.nc.passive_branch_data.F,
                        T=self.nc.passive_branch_data.T,
                        R=self.nc.passive_branch_data.R,
                        X=self.nc.passive_branch_data.X,
                        G=self.nc.passive_branch_data.G,
                        B=self.nc.passive_branch_data.B,
                        m=m2,
                        tau=tau2,
                        vtap_f=self.nc.passive_branch_data.virtual_tap_f,
                        vtap_t=self.nc.passive_branch_data.virtual_tap_t).imag

        Qt_cbr = calcSt(k=self.k_cbr_qt,
                        V=V,
                        F=self.nc.passive_branch_data.F,
                        T=self.nc.passive_branch_data.T,
                        R=self.nc.passive_branch_data.R,
                        X=self.nc.passive_branch_data.X,
                        G=self.nc.passive_branch_data.G,
                        B=self.nc.passive_branch_data.B,
                        m=m2,
                        tau=tau2,
                        vtap_f=self.nc.passive_branch_data.virtual_tap_f,
                        vtap_t=self.nc.passive_branch_data.virtual_tap_t).imag

        # VSC ----------------------------------------------------------------------------------------------------------
        T_vsc = self.nc.vsc_data.T
        It = np.sqrt(Pt_vsc * Pt_vsc + Qt_vsc * Qt_vsc) / Vm[T_vsc]
        It2 = It * It
        PLoss_IEC = (self.nc.vsc_data.alpha3 * It2
                     + self.nc.vsc_data.alpha2 * It
                     + self.nc.vsc_data.alpha1)

        loss_vsc = PLoss_IEC - Pt_vsc - Pf_vsc
        St_vsc = make_complex(Pt_vsc, Qt_vsc)
        # Scalc_vsc = Pf_vsc @ self.nc.vsc_data.Cf + St_vsc @ self.nc.vsc_data.Ct

        # HVDC ---------------------------------------------------------------------------------------------------------
        Vmf_hvdc = Vm[self.nc.hvdc_data.F]
        zbase = self.nc.hvdc_data.Vnf * self.nc.hvdc_data.Vnf / self.nc.Sbase
        Ploss_hvdc = self.nc.hvdc_data.r / zbase * np.power(Pf_hvdc / Vmf_hvdc, 2.0)
        loss_hvdc = Ploss_hvdc - Pf_hvdc - Pt_hvdc

        Pinj_hvdc = self.nc.hvdc_data.Pset / self.nc.Sbase
        if len(self.hvdc_droop_idx):
            Vaf_hvdc = Vm[self.nc.hvdc_data.F[self.hvdc_droop_idx]]
            Vat_hvdc = Vm[self.nc.hvdc_data.T[self.hvdc_droop_idx]]
            Pinj_hvdc[self.hvdc_droop_idx] += self.nc.hvdc_data.angle_droop[self.hvdc_droop_idx] * (Vaf_hvdc - Vat_hvdc)
        inj_hvdc = Pf_hvdc - Pinj_hvdc

        Sf_hvdc = make_complex(Pf_hvdc, Qf_hvdc)
        St_hvdc = make_complex(Pt_hvdc, Qt_hvdc)
        # Scalc_hvdc = Sf_hvdc @ self.nc.hvdc_data.Cf + St_hvdc @ self.nc.hvdc_data.Ct

        # total nodal power --------------------------------------------------------------------------------------------
        # Scalc = Scalc_passive + AScalc_cbr + Scalc_vsc + Scalc_hvdc
        self.Scalc = Scalc_passive + calc_flows_summation_per_bus(
            nbus=self.nc.bus_data.nbus,
            F_br=self.F_cbr[self.cbr],
            T_br=self.T_cbr[self.cbr],
            Sf_br=Sf_cbr,
            St_br=St_cbr,
            F_hvdc=self.nc.hvdc_data.F,
            T_hvdc=self.nc.hvdc_data.T,
            Sf_hvdc=Sf_hvdc,
            St_hvdc=St_hvdc,
            F_vsc=self.nc.vsc_data.F,
            T_vsc=self.nc.vsc_data.T,
            Pf_vsc=Pf_vsc,
            St_vsc=St_vsc
        )

        dS = self.Scalc - Sbus

        # compose the residuals vector ---------------------------------------------------------------------------------
        _f = np.r_[
            dS[self.i_k_p].real,
            dS[self.i_k_q].imag,
            loss_vsc,
            loss_hvdc,
            inj_hvdc,
            Pf_cbr - self.cbr_pf_set,
            Pt_cbr - self.cbr_pt_set,
            Qf_cbr - self.cbr_qf_set,
            Qt_cbr - self.cbr_qt_set
        ]

        return _f

    def check_error(self, x: Vec) -> Tuple[float, Vec]:
        """
        Check error of the solution without affecting the problem
        :param x: Solution vector
        :return: error
        """
        _res = self.compute_f(x)
        err = compute_fx_error(_res)

        # compute the error
        return err, x

    def update(self, x: Vec, update_controls: bool = False) -> Tuple[float, bool, Vec, Vec]:
        """
        Update step
        :param x: Solution vector
        :param update_controls:
        :return: error, converged?, x, fx
        """
        # set the problem state
        self.x2var(x)

        # compute the complex voltage
        self.V = polar_to_rect(self.Vm, self.Va)

        # compute f(x)
        self._f = self.compute_f(x)

        self._error = compute_fx_error(self._f)

        # Update controls only below a certain error
        if update_controls and self._error < self._controls_tol:
            any_change = False
            branch_ctrl_change = False

            # generator reactive power limits
            # condition to enter:
            # 1. At least two voltage controlled buses (1 slack and one with a shiftable generator)
            # 2. At least two buses with a free Q (1 slack and one with a shiftable generator)
            if self.options.control_Q and (self.nc.nbus - len(self.i_u_vm) >= 2) and (
                    self.nc.nbus - len(self.i_k_q)) >= 2:

                # check and adjust the reactive power
                # only update once, from voltage regulated to PQ injection
                i_k_vm = np.setdiff1d(np.arange(self.nc.nbus), self.i_u_vm)
                pv = np.intersect1d(i_k_vm, self.i_k_p)
                changed, i_u_vm, i_k_q = control_q_josep_method(self.Scalc, self.S0,
                                                                pv, self.i_u_vm, self.i_k_q,
                                                                self.Qmin, self.Qmax)

                if len(changed) > 0:
                    any_change = True

                    # update the bus type lists
                    self.update_Qlim_indices(i_u_vm=i_u_vm, i_k_q=i_k_q)

                    # the composition of x may have changed, so recompute
                    x = self.var2x()

            # update Slack control
            # as before but noticed it can cause slow convergence
            if self.options.distributed_slack:
                nbus_ar = np.arange(self.nc.nbus)
                i_k_vm = np.setdiff1d(nbus_ar, self.i_u_vm)
                i_k_va = np.setdiff1d(nbus_ar, self.i_u_va)
                vd = np.intersect1d(i_k_va, i_k_vm)
                ok, delta = compute_slack_distribution(
                    Scalc=self.Scalc,
                    vd=vd,
                    bus_installed_power=self.nc.bus_data.installed_power
                )
                if ok:
                    any_change = True
                    # Update the objective power to reflect the slack distribution
                    self.S0 += delta

            # update the tap module control
            if self.options.control_taps_modules:
                m_changed_ind = list()
                for i, k in enumerate(self.u_cbr_m):

                    # m_taps = self.nc.passive_branch_data.m_taps[i]
                    m_taps = self.nc.passive_branch_data.m_taps[k]

                    if self.options.orthogonalize_controls and m_taps is not None:
                        _, self.m[i] = find_closest_number(arr=m_taps, target=self.m[i])

                    if self.m[i] < self.nc.active_branch_data.tap_module_min[k]:
                        self.m[i] = self.nc.active_branch_data.tap_module_min[k]
                        m_changed_ind.append(i)

                        # self.tap_module_control_mode[k] = TapModuleControl.fixed
                        self.nc.active_branch_data.tap_module_control_mode[k] = TapModuleControl.fixed
                        self.nc.active_branch_data.tap_module[k] = self.m[i]

                        branch_ctrl_change = True
                        self.logger.add_info("Min tap module reached",
                                             device=self.nc.passive_branch_data.names[k],
                                             value=self.m[i])

                    if self.m[i] > self.nc.active_branch_data.tap_module_max[k]:
                        self.m[i] = self.nc.active_branch_data.tap_module_max[k]
                        m_changed_ind.append(i)

                        # self.tap_module_control_mode[k] = TapModuleControl.fixed
                        self.nc.active_branch_data.tap_module_control_mode[k] = TapModuleControl.fixed
                        self.nc.active_branch_data.tap_module[k] = self.m[i]

                        branch_ctrl_change = True
                        self.logger.add_info("Max tap module reached",
                                             device=self.nc.passive_branch_data.names[k],
                                             value=self.m[i])

                    if len(m_changed_ind) > 0:
                        self.m = np.delete(self.m, m_changed_ind)

            # update the tap phase control
            if self.options.control_taps_phase:
                t_changed_ind = list()

                for i, k in enumerate(self.u_cbr_tau):

                    tau_taps = self.nc.passive_branch_data.tau_taps[k]

                    if self.options.orthogonalize_controls and tau_taps is not None:
                        _, self.tau[i] = find_closest_number(arr=tau_taps, target=self.tau[i])

                    if self.tau[i] < self.nc.active_branch_data.tap_angle_min[k]:
                        self.tau[i] = self.nc.active_branch_data.tap_angle_min[k]
                        t_changed_ind.append(i)

                        self.nc.active_branch_data.tap_phase_control_mode[k] = TapPhaseControl.fixed
                        self.nc.active_branch_data.tap_angle[k] = self.tau[i]

                        branch_ctrl_change = True
                        self.logger.add_info("Min tap phase reached",
                                             device=self.nc.passive_branch_data.names[k],
                                             value=self.tau[i])

                    if self.tau[i] > self.nc.active_branch_data.tap_angle_max[k]:
                        self.tau[i] = self.nc.active_branch_data.tap_angle_max[k]
                        t_changed_ind.append(i)

                        self.nc.active_branch_data.tap_phase_control_mode[k] = TapPhaseControl.fixed
                        self.nc.active_branch_data.tap_angle[k] = self.tau[i]

                        branch_ctrl_change = True
                        self.logger.add_info("Max tap phase reached",
                                             device=self.nc.passive_branch_data.names[k],
                                             value=self.tau[i])

                    if len(t_changed_ind) > 0:
                        self.tau = np.delete(self.tau, t_changed_ind)

            if branch_ctrl_change:
                self.bus_types = self.nc.bus_data.bus_types.copy()
                self.is_p_controlled = self.nc.bus_data.is_p_controlled.copy()
                self.is_q_controlled = self.nc.bus_data.is_q_controlled.copy()
                self.is_vm_controlled = self.nc.bus_data.is_vm_controlled.copy()
                self.is_va_controlled = self.nc.bus_data.is_va_controlled.copy()
                self._analyze_branch_controls()
                self.analyze_bus_controls()
                # the composition of x may have changed, so recompute
                x = self.var2x()

                # vd, pq, pv, pqv, p, self.no_slack = compile_types(Pbus=self.S0.real, types=self.bus_types)
                # self.update_bus_types(pq=pq, pv=pv, pqv=pqv, p=p)
            #
            if any_change or branch_ctrl_change:
                # recompute the error based on the new Scalc and S0
                self._f = self.fx()

                # compute the rror
                self._error = compute_fx_error(self._f)

        # converged?
        self._converged = self._error < self.options.tolerance

        if self.options.verbose > 1:
            print("Error:", self._error)

        return self._error, self._converged, x, self.f

    def fx(self) -> Vec:
        """
        Used? Yes! Needed when updating the controls
        :return:
        """

        # remember that Ybus here is computed with the fixed taps
        V = polar_to_rect(self.Vm, self.Va)
        Sbus = compute_zip_power(self.S0, self.I0, self.Y0, self.Vm)
        Scalc_passive = compute_power(self.Ybus, V)

        # Controllable branches ----------------------------------------------------------------------------------------
        # Power at the controlled branches
        m2 = self.nc.active_branch_data.tap_module.copy()
        tau2 = self.nc.active_branch_data.tap_angle.copy()
        m2[self.u_cbr_m] = self.m
        tau2[self.u_cbr_tau] = self.tau

        yff = (self.yff_cbr / (m2 * m2))
        yft = self.yft_cbr / (m2 * np.exp(-1.0j * tau2))
        ytf = self.ytf_cbr / (m2 * np.exp(1.0j * tau2))
        ytt = self.ytt_cbr

        Vf_cbr = V[self.F_cbr[self.cbr]]
        Vt_cbr = V[self.T_cbr[self.cbr]]
        yff_ = yff[self.cbr]
        yft_ = yft[self.cbr]
        ytf_ = ytf[self.cbr]
        ytt_ = ytt[self.cbr]
        yff0_ = self.yff0[self.cbr]
        yft0_ = self.yft0[self.cbr]
        ytf0_ = self.ytf0[self.cbr]
        ytt0_ = self.ytt0[self.cbr]

        Sf_cbr = (Vf_cbr * np.conj(Vf_cbr) * np.conj(yff_ - yff0_) + Vf_cbr * np.conj(Vt_cbr) * np.conj(yft_ - yft0_))
        St_cbr = (Vt_cbr * np.conj(Vt_cbr) * np.conj(ytt_ - ytt0_) + Vt_cbr * np.conj(Vf_cbr) * np.conj(ytf_ - ytf0_))

        # difference between the actual power and the power calculated with the passive term (initial admittance)
        # AScalc_cbr = np.zeros(self.nc.bus_data.nbus, dtype=complex)
        # AScalc_cbr[self.F_cbr[self.cbr]] += Sf_cbr
        # AScalc_cbr[self.T_cbr[self.cbr]] += St_cbr

        Pf_cbr = calcSf(k=self.k_cbr_pf,
                        V=V,
                        F=self.nc.passive_branch_data.F,
                        T=self.nc.passive_branch_data.T,
                        R=self.nc.passive_branch_data.R,
                        X=self.nc.passive_branch_data.X,
                        G=self.nc.passive_branch_data.G,
                        B=self.nc.passive_branch_data.B,
                        m=m2,
                        tau=tau2,
                        vtap_f=self.nc.passive_branch_data.virtual_tap_f,
                        vtap_t=self.nc.passive_branch_data.virtual_tap_t).real

        Pt_cbr = calcSt(k=self.k_cbr_pt,
                        V=V,
                        F=self.nc.passive_branch_data.F,
                        T=self.nc.passive_branch_data.T,
                        R=self.nc.passive_branch_data.R,
                        X=self.nc.passive_branch_data.X,
                        G=self.nc.passive_branch_data.G,
                        B=self.nc.passive_branch_data.B,
                        m=m2,
                        tau=tau2,
                        vtap_f=self.nc.passive_branch_data.virtual_tap_f,
                        vtap_t=self.nc.passive_branch_data.virtual_tap_t).real

        Qf_cbr = calcSf(k=self.k_cbr_qf,
                        V=V,
                        F=self.nc.passive_branch_data.F,
                        T=self.nc.passive_branch_data.T,
                        R=self.nc.passive_branch_data.R,
                        X=self.nc.passive_branch_data.X,
                        G=self.nc.passive_branch_data.G,
                        B=self.nc.passive_branch_data.B,
                        m=m2,
                        tau=tau2,
                        vtap_f=self.nc.passive_branch_data.virtual_tap_f,
                        vtap_t=self.nc.passive_branch_data.virtual_tap_t).imag

        Qt_cbr = calcSt(k=self.k_cbr_qt,
                        V=V,
                        F=self.nc.passive_branch_data.F,
                        T=self.nc.passive_branch_data.T,
                        R=self.nc.passive_branch_data.R,
                        X=self.nc.passive_branch_data.X,
                        G=self.nc.passive_branch_data.G,
                        B=self.nc.passive_branch_data.B,
                        m=m2,
                        tau=tau2,
                        vtap_f=self.nc.passive_branch_data.virtual_tap_f,
                        vtap_t=self.nc.passive_branch_data.virtual_tap_t).imag

        # VSC ----------------------------------------------------------------------------------------------------------
        T_vsc = self.nc.vsc_data.T
        It = np.sqrt(self.Pt_vsc * self.Pt_vsc + self.Qt_vsc * self.Qt_vsc) / self.Vm[T_vsc]
        It2 = It * It
        PLoss_IEC = (self.nc.vsc_data.alpha3 * It2
                     + self.nc.vsc_data.alpha2 * It
                     + self.nc.vsc_data.alpha1)

        loss_vsc = PLoss_IEC - self.Pt_vsc - self.Pf_vsc
        St_vsc = make_complex(self.Pt_vsc, self.Qt_vsc)

        # Scalc_vsc = self.Pf_vsc @ self.nc.vsc_data.Cf + St_vsc @ self.nc.vsc_data.Ct

        # HVDC ---------------------------------------------------------------------------------------------------------
        Vmf_hvdc = self.Vm[self.nc.hvdc_data.F]
        zbase = self.nc.hvdc_data.Vnf * self.nc.hvdc_data.Vnf / self.nc.Sbase
        Ploss_hvdc = self.nc.hvdc_data.r / zbase * np.power(self.Pf_hvdc / Vmf_hvdc, 2.0)
        loss_hvdc = Ploss_hvdc - self.Pf_hvdc - self.Pt_hvdc

        Pinj_hvdc = self.nc.hvdc_data.Pset / self.nc.Sbase
        if len(self.hvdc_droop_idx):
            Vaf_hvdc = self.Vm[self.nc.hvdc_data.F[self.hvdc_droop_idx]]
            Vat_hvdc = self.Vm[self.nc.hvdc_data.T[self.hvdc_droop_idx]]
            Pinj_hvdc[self.hvdc_droop_idx] += self.nc.hvdc_data.angle_droop[self.hvdc_droop_idx] * (Vaf_hvdc - Vat_hvdc)
        inj_hvdc = self.Pf_hvdc - Pinj_hvdc

        Sf_hvdc = make_complex(self.Pf_hvdc, self.Qf_hvdc)
        St_hvdc = make_complex(self.Pt_hvdc, self.Qt_hvdc)
        # Scalc_hvdc = Sf_hvdc @ self.nc.hvdc_data.Cf + St_hvdc @ self.nc.hvdc_data.Ct

        # total nodal power --------------------------------------------------------------------------------------------
        # Scalc = Scalc_passive + AScalc_cbr + Scalc_vsc + Scalc_hvdc
        # self.Scalc = Scalc  # needed for the Q control check to use

        self.Scalc = Scalc_passive + calc_flows_summation_per_bus(
            nbus=self.nc.bus_data.nbus,
            F_br=self.F_cbr[self.cbr],
            T_br=self.T_cbr[self.cbr],
            Sf_br=Sf_cbr,
            St_br=St_cbr,
            F_hvdc=self.nc.hvdc_data.F,
            T_hvdc=self.nc.hvdc_data.T,
            Sf_hvdc=Sf_hvdc,
            St_hvdc=St_hvdc,
            F_vsc=self.nc.vsc_data.F,
            T_vsc=self.nc.vsc_data.T,
            Pf_vsc=self.Pf_vsc,
            St_vsc=St_vsc
        )

        dS = self.Scalc - Sbus

        # compose the residuals vector ---------------------------------------------------------------------------------
        self._f = np.r_[
            dS[self.i_k_p].real,
            dS[self.i_k_q].imag,
            loss_vsc,
            loss_hvdc,
            inj_hvdc,
            Pf_cbr - self.cbr_pf_set,
            Pt_cbr - self.cbr_pt_set,
            Qf_cbr - self.cbr_qf_set,
            Qt_cbr - self.cbr_qt_set
        ]

        return self._f

    def Jacobian(self, autodiff: bool = False) -> CSC:
        """
        Get the Jacobian
        :return:
        """
        if autodiff:
            J = calc_autodiff_jacobian(func=self.compute_f,
                                       x=self.var2x(),
                                       h=1e-8)

            if self.options.verbose > 1:
                print("(pf_generalized_formulation.py) J: ")
                print(J.toarray())
                print("J shape: ", J.shape)
            return J

        else:
            # build the symbolic Jacobian
            tap_modules = expand(self.nc.nbr, self.m, self.u_cbr_m, 1.0)
            tap_angles = expand(self.nc.nbr, self.tau, self.u_cbr_tau, 0.0)

            # HVDC
            nhvdc = self.nc.hvdc_data.nelm

            hvdc_r_pu = self.nc.hvdc_data.r / (self.nc.hvdc_data.Vnf * self.nc.hvdc_data.Vnf / self.nc.Sbase)

            hvdc_droop_redone = np.zeros(self.nc.hvdc_data.nelm, dtype=float)
            if len(self.hvdc_droop_idx) > 0:
                hvdc_droop_redone[self.hvdc_droop_idx] = self.nc.hvdc_data.angle_droop[self.hvdc_droop_idx]

            assert isspmatrix_csc(self.Ybus)

            J_sym = adv_jacobian(
                nbus=self.nc.nbus,
                nbr=self.nc.nbr,
                nvsc=self.nc.vsc_data.nelm,
                nhvdc=nhvdc,
                F=self.nc.passive_branch_data.F,
                T=self.nc.passive_branch_data.T,
                F_vsc=self.nc.vsc_data.F,
                T_vsc=self.nc.vsc_data.T,
                F_hvdc=self.nc.hvdc_data.F,
                T_hvdc=self.nc.hvdc_data.T,
                tap_angles=tap_angles,
                tap_modules=tap_modules,

                V=self.V,
                Vm=self.Vm,

                # Controllable Branch Indices
                u_cbr_m=self.u_cbr_m,
                u_cbr_tau=self.u_cbr_tau,
                cbr=self.cbr,

                k_cbr_pf=self.k_cbr_pf,
                k_cbr_pt=self.k_cbr_pt,
                k_cbr_qf=self.k_cbr_qf,
                k_cbr_qt=self.k_cbr_qt,

                # VSC Indices
                u_vsc_pf=self.u_vsc_pf,
                u_vsc_pt=self.u_vsc_pt,
                u_vsc_qt=self.u_vsc_qt,

                # VSC Params
                alpha1=self.nc.vsc_data.alpha1,
                alpha2=self.nc.vsc_data.alpha2,
                alpha3=self.nc.vsc_data.alpha3,

                # HVDC Params
                hvdc_r=hvdc_r_pu,
                hvdc_droop=hvdc_droop_redone,

                # Bus Indices
                i_u_vm=self.i_u_vm,
                i_u_va=self.i_u_va,
                i_k_p=self.i_k_p,
                i_k_q=self.i_k_q,

                # Unknowns
                Pf_vsc=self.Pf_vsc,
                Pt_vsc=self.Pt_vsc,
                Qt_vsc=self.Qt_vsc,
                Pf_hvdc=self.Pf_hvdc,

                # Admittances and Connections
                yff_cbr=self.yff_cbr,
                yft_cbr=self.yft_cbr,
                ytf_cbr=self.ytf_cbr,
                ytt_cbr=self.ytt_cbr,

                yff0=self.yff0,
                yft0=self.yft0,
                ytf0=self.ytf0,
                ytt0=self.ytt0,

                F_cbr=self.F_cbr,
                T_cbr=self.T_cbr,

                Yi=self.Ybus.indices,
                Yp=self.Ybus.indptr,
                Yx=self.Ybus.data
            )

            if self.options.verbose > 1:
                print("(pf_generalized_formulation.py) J: ")
                print(J_sym.toarray())
                print("J shape: ", J_sym.shape)

            return J_sym

    def get_x_names(self) -> List[str]:
        """
        Names matching x
        :return:
        """
        cols = [f'dVa {i}' for i in self.i_u_va]
        cols += [f'dVm {i}' for i in self.i_u_vm]

        cols += [f'dPf_var_vsc {i}' for i in self.u_vsc_pf]
        cols += [f'dPt_var_vsc {i}' for i in self.u_vsc_pt]
        cols += [f'dQt_var_vsc {i}' for i in self.u_vsc_qt]

        cols += [f'dPf_hvdc {i}' for i in range(self.nc.hvdc_data.nelm)]
        cols += [f'dPt_hvdc {i}' for i in range(self.nc.hvdc_data.nelm)]
        cols += [f'dQf_hvdc {i}' for i in range(self.nc.hvdc_data.nelm)]
        cols += [f'dQt_hvdc {i}' for i in range(self.nc.hvdc_data.nelm)]

        cols += [f'dm {i}' for i in self.u_cbr_m]
        cols += [f'dtau {i}' for i in self.u_cbr_tau]

        return cols

    def get_fx_names(self) -> List[str]:
        """
        Names matching fx
        :return:
        """

        rows = [f'dP {i}' for i in self.i_k_p]
        rows += [f'dQ {i}' for i in self.i_k_q]
        rows += [f'dloss_vsc {i}' for i in range(self.nc.vsc_data.nelm)]
        rows += [f'dloss_hvdc {i}' for i in range(self.nc.hvdc_data.nelm)]
        rows += [f'dinj_hvdc {i}' for i in range(self.nc.hvdc_data.nelm)]

        rows += [f'dPf {i}' for i in self.k_cbr_pf]
        rows += [f'dPt {i}' for i in self.k_cbr_pt]
        rows += [f'dQf {i}' for i in self.k_cbr_qf]
        rows += [f'dQt {i}' for i in self.k_cbr_qt]

        return rows

    def get_solution(self, elapsed: float, iterations: int) -> NumericPowerFlowResults:
        """
        Get the problem solution
        :param elapsed: Elapsed seconds
        :param iterations: Iteration number
        :return: NumericPowerFlowResults
        """

        # Branches -----------------------------------------------------------------------------------------------------
        # compute the flows, currents, losses for all branches

        V = self.Vm * np.exp(1j * self.Va)
        Vf = V[self.nc.passive_branch_data.F]
        Vt = V[self.nc.passive_branch_data.T]

        # compose all taps (m and tau)
        m = self.nc.active_branch_data.tap_module.copy()
        m[self.u_cbr_m] = self.m
        tau = self.nc.active_branch_data.tap_angle.copy()
        tau[self.u_cbr_tau] = self.tau

        R = self.nc.passive_branch_data.R
        X = self.nc.passive_branch_data.X
        G = self.nc.passive_branch_data.G
        B = self.nc.passive_branch_data.B
        vtap_f = self.nc.passive_branch_data.virtual_tap_f
        vtap_t = self.nc.passive_branch_data.virtual_tap_t

        ys = 1.0 / make_complex(R, X + 1e-20)  # series admittance
        bc2 = make_complex(G, B) / 2.0  # shunt admittance
        yff = (ys + bc2) / (m * m * vtap_f * vtap_f)
        yft = -ys / (m * np.exp(-1.0j * tau) * vtap_f * vtap_t)
        ytf = -ys / (m * np.exp(1.0j * tau) * vtap_t * vtap_f)
        ytt = (ys + bc2) / (vtap_t * vtap_t)

        If = Vf * yff + Vt * yft
        It = Vt * ytt + Vf * ytf
        Sf = Vf * np.conj(If)
        St = Vt * np.conj(It)

        # Branch losses in MVA
        losses = (Sf + St) * self.nc.Sbase

        # Branch loading in p.u.
        loading = Sf * self.nc.Sbase / (self.nc.passive_branch_data.rates + 1e-9)

        # VSC ----------------------------------------------------------------------------------------------------------
        Pf_vsc = self.Pf_vsc
        St_vsc = make_complex(self.Pt_vsc, self.Qt_vsc)
        If_vsc = Pf_vsc / np.abs(V[self.nc.vsc_data.F])
        It_vsc = St_vsc / np.conj(V[self.nc.vsc_data.T])
        loading_vsc = np.abs(St_vsc) / (self.nc.vsc_data.rates + 1e-20) * self.nc.Sbase

        # HVDC ---------------------------------------------------------------------------------------------------------
        Sf_hvdc = make_complex(self.Pf_hvdc, self.Qf_hvdc) * self.nc.Sbase
        St_hvdc = make_complex(self.Pt_hvdc, self.Qt_hvdc) * self.nc.Sbase
        loading_hvdc = Sf_hvdc.real / (self.nc.hvdc_data.rates + 1e-20)

        # Basic bus powers
        # Sbus_const = compute_zip_power(self.S0, self.I0, self.Y0, self.Vm)
        # Sbus_vsc = Pf_vsc @ self.nc.vsc_data.Cf + St_vsc @ self.nc.vsc_data.Ct
        # Sbus_hvdc = Sf_hvdc @ self.nc.hvdc_data.Cf + St_hvdc @ self.nc.hvdc_data.Ct
        # Sbus_br = Sf @ self.nc.passive_branch_data.Cf + St @ self.nc.passive_branch_data.Ct
        #
        # # Sbus_act = Sbus_vsc + Sbus_hvdc + Sbus_br - Sbus_const
        # Sbus = Sbus_vsc + Sbus_hvdc + Sbus_br

        # the trick here is that the mismatch of the branch flow summations is what we actually want;
        # that'd be the injections per bus in the end, including the voltage dependent values
        Sbus = calc_flows_summation_per_bus(
            nbus=self.nc.bus_data.nbus,
            F_br=self.nc.passive_branch_data.F,
            T_br=self.nc.passive_branch_data.T,
            Sf_br=Sf,
            St_br=St,
            F_hvdc=self.nc.hvdc_data.F,
            T_hvdc=self.nc.hvdc_data.T,
            Sf_hvdc=Sf_hvdc,
            St_hvdc=St_hvdc,
            F_vsc=self.nc.vsc_data.F,
            T_vsc=self.nc.vsc_data.T,
            Pf_vsc=Pf_vsc,
            St_vsc=St_vsc
        )

        return NumericPowerFlowResults(
            V=self.V,
            Scalc=Sbus * self.nc.Sbase,
            m=m,
            tau=tau,
            Sf=Sf * self.nc.Sbase,
            St=St * self.nc.Sbase,
            If=If,
            It=It,
            loading=loading,
            losses=losses,
            Pf_vsc=Pf_vsc * self.nc.Sbase,
            St_vsc=St_vsc * self.nc.Sbase,
            If_vsc=If_vsc,
            It_vsc=It_vsc,
            losses_vsc=Pf_vsc + St_vsc.real,
            loading_vsc=loading_vsc,
            Sf_hvdc=Sf_hvdc,
            St_hvdc=St_hvdc,
            losses_hvdc=Sf_hvdc + Sf_hvdc,
            loading_hvdc=loading_hvdc,
            norm_f=self.error,
            converged=self.converged,
            iterations=iterations,
            elapsed=elapsed
        )
