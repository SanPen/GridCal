# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import time
from typing import Tuple, List, Dict, Callable
import numpy as np
from numba import njit
from scipy.sparse import lil_matrix, isspmatrix_csc
from VeraGridEngine.Topology.admittance_matrices import compute_admittances_fast
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from VeraGridEngine.DataStructures.numerical_circuit import NumericalCircuit
import VeraGridEngine.Simulations.Derivatives.csc_derivatives as deriv
from VeraGridEngine.Utils.NumericalMethods.common import find_closest_number, make_complex
from VeraGridEngine.Utils.Sparse.csc2 import (CSC, CxCSC, scipy_to_mat, sp_slice, csc_stack_2d_ff)
from VeraGridEngine.Simulations.PowerFlow.NumericalMethods.discrete_controls import (control_q_for_generalized_method,
                                                                                     compute_slack_distribution)
from VeraGridEngine.Simulations.PowerFlow.NumericalMethods.common_functions import expand
from VeraGridEngine.Simulations.PowerFlow.NumericalMethods.common_functions import compute_fx_error
from VeraGridEngine.Simulations.PowerFlow.Formulations.pf_formulation_template import PfFormulationTemplate
from VeraGridEngine.Simulations.PowerFlow.NumericalMethods.common_functions import (compute_zip_power, compute_power,
                                                                                    polar_to_rect)
from VeraGridEngine.enumerations import (TapPhaseControl, TapModuleControl, HvdcControlType, ConverterControlType)
from VeraGridEngine.basic_structures import Vec, IntVec, CxVec, Logger


@njit()
def adv_jacobian(nbus: int,
                 nbr: int,
                 nvsc: int,
                 nhvdc: int,
                 F: IntVec,
                 T: IntVec,
                 Fdcp_vsc: IntVec,
                 Fdcn_vsc: IntVec,
                 T_vsc: IntVec,
                 F_hvdc: IntVec,
                 T_hvdc: IntVec,

                 tap_angles: Vec,
                 tap_modules: Vec,

                 V: CxVec,
                 Vm: Vec,
                 Va: Vec,

                 # Controllable Branch Indices
                 u_cbr_m: IntVec,
                 u_cbr_tau: IntVec,

                 k_cbr_pf: IntVec,
                 k_cbr_pt: IntVec,
                 k_cbr_qf: IntVec,
                 k_cbr_qt: IntVec,

                 # VSC Indices
                 u_vsc_pfp: IntVec,
                 u_vsc_pfn: IntVec,
                 u_vsc_pt: IntVec,
                 u_vsc_qt: IntVec,

                 k_vsc_imax: IntVec,

                 # VSC Params
                 alpha1: Vec,
                 alpha2: Vec,
                 alpha3: Vec,

                 # HVDC Params
                 hvdc_r: Vec,
                 hvdc_droop: Vec,

                 # Bus Indices
                 i_u_vm: IntVec,
                 i_u_va: IntVec,
                 i_k_p: IntVec,
                 i_k_q: IntVec,

                 # Unknowns
                 Pfp_vsc: Vec,
                 Pfn_vsc: Vec,
                 Pt_vsc: Vec,
                 Qt_vsc: Vec,
                 Pf_hvdc: Vec,

                 # Admittances and Connections
                 Ys: CxVec,
                 Bc: Vec,

                 yff_cbr: CxVec,
                 yft_cbr: CxVec,
                 ytf_cbr: CxVec,
                 ytt_cbr: CxVec,

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
    :param Fdcp_vsc:
    :param Fdcn_vsc:
    :param T_vsc:
    :param F_hvdc:
    :param T_hvdc:
    :param tap_angles:
    :param tap_modules:
    :param V:
    :param Vm:
    :param Va:
    :param u_cbr_m:
    :param u_cbr_tau:
    :param k_cbr_pf:
    :param k_cbr_pt:
    :param k_cbr_qf:
    :param k_cbr_qt:
    :param u_vsc_pfp:
    :param u_vsc_pfn:
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
    :param Pfp_vsc:
    :param Pfn_vsc:
    :param Pt_vsc:
    :param Qt_vsc:
    :param Pf_hvdc:
    :param Ys:
    :param Bc:
    :param yff_cbr:
    :param yft_cbr:
    :param ytf_cbr:
    :param ytt_cbr:
    :param Yi:
    :param Yp:
    :param Yx:
    :return:
    """

    tap = polar_to_rect(tap_modules, tap_angles)

    # -------- ROW 1 + ROW 2 (Sbus) ---------
    # bus-bus derivatives (always needed)
    dSy_dVm_x, dSy_dVa_x = deriv.dSbus_dV_numba_sparse_csc(Yx, Yp, Yi, V, Vm)
    dS_dVm = CxCSC(nbus, nbus, len(dSy_dVm_x), False).set(Yi, Yp, dSy_dVm_x)
    dS_dVa = CxCSC(nbus, nbus, len(dSy_dVa_x), False).set(Yi, Yp, dSy_dVa_x)

    nvsc_imax = len(k_vsc_imax)
    hvdc_range = np.arange(nhvdc)

    # -------- ROW 1 (P) ---------
    dP_dVa = sp_slice(dS_dVa.real, i_k_p, i_u_va)
    dP_dVm = sp_slice(dS_dVm.real, i_k_p, i_u_vm)
    dP_dPfpvsc = deriv.dPQ_dPQft_csc(nbus, nvsc, i_k_p, u_vsc_pfp, Fdcp_vsc)
    dP_dPfnvsc = deriv.dPQ_dPQft_csc(nbus, nvsc, i_k_p, u_vsc_pfn, Fdcn_vsc)
    dP_dPtvsc = deriv.dPQ_dPQft_csc(nbus, nvsc, i_k_p, u_vsc_pt, T_vsc)
    dP_dQtvsc = CSC(len(i_k_p), len(u_vsc_qt), 0, False)  # fully empty
    dP_dPfhvdc = deriv.dPQ_dPQft_csc(nbus, nhvdc, i_k_p, hvdc_range, F_hvdc)
    dP_dPthvdc = deriv.dPQ_dPQft_csc(nbus, nhvdc, i_k_p, hvdc_range, T_hvdc)
    dP_dQfhvdc = CSC(len(i_k_p), nhvdc, 0, False)  # fully empty
    dP_dQthvdc = CSC(len(i_k_p), nhvdc, 0, False)  # fully empty
    dP_dm = deriv.dSbus_dm_csc(nbus, i_k_p, u_cbr_m, F, T, Ys, Bc, tap, tap_modules, V).real
    dP_dtau = deriv.dSbus_dtau_csc(nbus, i_k_p, u_cbr_tau, F, T, Ys, tap, V).real

    # -------- ROW 2 (Q) ---------
    dQ_dVa = sp_slice(dS_dVa.imag, i_k_q, i_u_va)
    dQ_dVm = sp_slice(dS_dVm.imag, i_k_q, i_u_vm)
    dQ_dPfpvsc = CSC(len(i_k_q), len(u_vsc_pfp), 0, False)  # fully empty
    dQ_dPfnvsc = CSC(len(i_k_q), len(u_vsc_pfn), 0, False)  # fully empty
    dQ_dPtvsc = CSC(len(i_k_q), len(u_vsc_pt), 0, False)  # fully empty
    dQ_dQtvsc = deriv.dPQ_dPQft_csc(nbus, nvsc, i_k_q, u_vsc_qt, T_vsc)
    dQ_dPfhvdc = CSC(len(i_k_q), nhvdc, 0, False)  # fully empty
    dQ_dPthvdc = CSC(len(i_k_q), nhvdc, 0, False)  # fully empty
    dQ_dQfhvdc = deriv.dPQ_dPQft_csc(nbus, nhvdc, i_k_q, hvdc_range, F_hvdc)
    dQ_dQthvdc = deriv.dPQ_dPQft_csc(nbus, nhvdc, i_k_q, hvdc_range, T_hvdc)
    dQ_dm = deriv.dSbus_dm_csc(nbus, i_k_q, u_cbr_m, F, T, Ys, Bc, tap, tap_modules, V).imag
    dQ_dtau = deriv.dSbus_dtau_csc(nbus, i_k_q, u_cbr_tau, F, T, Ys, tap, V).imag

    # -------- ROW 3 (Losses VSCs) ---------
    dLvsc_dVa = CSC(nvsc, len(i_u_va), 0, False)  # fully empty
    dLvsc_dVm = deriv.dLossvsc_dVm_csc(nvsc, nbus, i_u_vm, alpha2, alpha3, Vm, Pt_vsc, Qt_vsc, T_vsc)
    dLvsc_dPfpvsc = deriv.dLossvsc_dPfvsc_csc(nvsc, u_vsc_pfp)
    dLvsc_dPfnvsc = deriv.dLossvsc_dPfvsc_csc(nvsc, u_vsc_pfn)
    dLvsc_dPtvsc = deriv.dLossvsc_dPtvsc_csc(nvsc, u_vsc_pt, alpha2, alpha3, Vm, Pt_vsc, Qt_vsc, T_vsc)
    dLvsc_dQtvsc = deriv.dLossvsc_dQtvsc_csc(nvsc, u_vsc_qt, alpha2, alpha3, Vm, Pt_vsc, Qt_vsc, T_vsc)
    dLvsc_dPfhvdc = CSC(nvsc, nhvdc, 0, False)  # fully empty
    dLvsc_dPthvdc = CSC(nvsc, nhvdc, 0, False)  # fully empty
    dLvsc_dQfhvdc = CSC(nvsc, nhvdc, 0, False)  # fully empty
    dLvsc_dQthvdc = CSC(nvsc, nhvdc, 0, False)  # fully empty
    dLvsc_dm = CSC(nvsc, len(u_cbr_m), 0, False)  # fully empty
    dLvsc_dtau = CSC(nvsc, len(u_cbr_tau), 0, False)  # fully empty

    # -------- ROW 4 (current balance VSCs) ---------
    dIvsc_dVa = CSC(nvsc, len(i_u_va), 0, False)  # fully empty
    dIvsc_dVm = deriv.dIvsc_dVm_csc(nvsc, nbus, i_u_vm, Pfp_vsc, Pfn_vsc, Fdcp_vsc, Fdcn_vsc)
    dIvsc_dPfpvsc = deriv.dIvsc_dPfpvsc_csc(nvsc, u_vsc_pfp, Vm, Fdcn_vsc)
    dIvsc_dPfnvsc = deriv.dIvsc_dPfnvsc_csc(nvsc, u_vsc_pfn, Vm, Fdcp_vsc)
    dIvsc_dPtvsc = CSC(nvsc, len(u_vsc_pt), 0, False)  # fully empty
    dIvsc_dQtvsc = CSC(nvsc, len(u_vsc_qt), 0, False)  # fully empty
    dIvsc_dPfhvdc = CSC(nvsc, nhvdc, 0, False)  # fully empty
    dIvsc_dPthvdc = CSC(nvsc, nhvdc, 0, False)  # fully empty
    dIvsc_dQfhvdc = CSC(nvsc, nhvdc, 0, False)  # fully empty
    dIvsc_dQthvdc = CSC(nvsc, nhvdc, 0, False)  # fully empty
    dIvsc_dm = CSC(nvsc, len(u_cbr_m), 0, False)  # fully empty
    dIvsc_dtau = CSC(nvsc, len(u_cbr_tau), 0, False)  # fully empty

    # -------- ROW 5 (max current VSCs) ---------
    dImax_dVa = CSC(nvsc_imax, len(i_u_va), 0, False)  # fully empty
    dImax_dVm = deriv.dImaxvsc_dVm_csc(nbus, k_vsc_imax, i_u_vm, Pt_vsc, Qt_vsc, Vm, T_vsc)
    dImax_dPfpvsc = CSC(nvsc_imax, len(u_vsc_pfp), 0, False)  # fully empty
    dImax_dPfnvsc = CSC(nvsc_imax, len(u_vsc_pfn), 0, False)  # fully empty
    dImax_dPtvsc = deriv.dImaxvsc_dPQ_csc(nvsc, k_vsc_imax, u_vsc_pt, Pt_vsc, Vm, T_vsc)
    dImax_dQtvsc = deriv.dImaxvsc_dPQ_csc(nvsc, k_vsc_imax, u_vsc_qt, Qt_vsc, Vm, T_vsc)
    dImax_dPfhvdc = CSC(nvsc_imax, nhvdc, 0, False)  # fully empty
    dImax_dPthvdc = CSC(nvsc_imax, nhvdc, 0, False)  # fully empty
    dImax_dQfhvdc = CSC(nvsc_imax, nhvdc, 0, False)  # fully empty
    dImax_dQthvdc = CSC(nvsc_imax, nhvdc, 0, False)  # fully empty
    dImax_dm = CSC(nvsc_imax, len(u_cbr_m), 0, False)  # fully empty
    dImax_dtau = CSC(nvsc_imax, len(u_cbr_tau), 0, False)  # fully empty

    # -------- ROW 6 (loss HVDCs) ---------
    dLhvdc_dVa = CSC(nhvdc, len(i_u_va), 0, False)  # fully empty
    dLhvdc_dVm = deriv.dLosshvdc_dVm_csc(nhvdc, nbus, i_u_vm, Vm, Pf_hvdc, hvdc_r, F_hvdc)
    dLhvdc_dPfpvsc = CSC(nhvdc, nvsc, 0, False)  # fully empty
    dLhvdc_dPfnvsc = CSC(nhvdc, nvsc, 0, False)  # fully empty
    dLhvdc_dPtvsc = CSC(nhvdc, nvsc, 0, False)  # fully empty
    dLhvdc_dQtvsc = CSC(nhvdc, nvsc, 0, False)  # fully empty
    dLhvdc_dPfhvdc = deriv.dLosshvdc_dPfhvdc_csc(nhvdc, Vm, hvdc_r, F_hvdc)
    dLhvdc_dPthvdc = deriv.dLosshvdc_dPthvdc_csc(nhvdc)
    dLhvdc_dQfhvdc = CSC(nhvdc, nhvdc, 0, False)  # fully empty
    dLhvdc_dQthvdc = CSC(nhvdc, nhvdc, 0, False)  # fully empty
    dLhvdc_dm = CSC(nhvdc, len(u_cbr_m), 0, False)  # fully empty
    dLhvdc_dtau = CSC(nhvdc, len(u_cbr_tau), 0, False)  # fully empty

    # -------- ROW 7 (inj HVDCs) ---------
    dInjhvdc_dVa = deriv.dInjhvdc_dVa_csc(nhvdc, nbus, i_u_va, hvdc_droop, F_hvdc, T_hvdc)
    dInjhvdc_dVm = CSC(nhvdc, len(i_u_vm), 0, False)  # fully empty
    dInjhvdc_dPfpvsc = CSC(nhvdc, len(u_vsc_pfp), 0, False)  # fully empty
    dInjhvdc_dPfnvsc = CSC(nhvdc, len(u_vsc_pfn), 0, False)  # fully empty
    dInjhvdc_dPtvsc = CSC(nhvdc, len(u_vsc_pt), 0, False)  # fully empty
    dInjhvdc_dQtvsc = CSC(nhvdc, len(u_vsc_qt), 0, False)  # fully empty
    dInjhvdc_dPfhvdc = deriv.dInjhvdc_dPfhvdc_csc(nhvdc)
    dInjhvdc_dPthvdc = CSC(nhvdc, nhvdc, 0, False)  # fully empty
    dInjhvdc_dQfhvdc = CSC(nhvdc, nhvdc, 0, False)  # fully empty
    dInjhvdc_dQthvdc = CSC(nhvdc, nhvdc, 0, False)  # fully empty
    dInjhvdc_dm = CSC(nhvdc, len(u_cbr_m), 0, False)  # fully empty
    dInjhvdc_dtau = CSC(nhvdc, len(u_cbr_tau), 0, False)  # fully empty

    # -------- ROW 8 (Pf) ---------
    dPf_dVa = deriv.dSf_dVa_csc(nbus, k_cbr_pf, i_u_va, yft_cbr, V, F, T).real
    dPf_dVm = deriv.dSf_dVm_csc(nbus, k_cbr_pf, i_u_vm, yff_cbr, yft_cbr, Vm, Va, F, T).real
    dPf_dPfpvsc = CSC(len(k_cbr_pf), len(u_vsc_pfp), 0, False)  # fully empty
    dPf_dPfnvsc = CSC(len(k_cbr_pf), len(u_vsc_pfn), 0, False)  # fully empty
    dPf_dPtvsc = CSC(len(k_cbr_pf), len(u_vsc_pt), 0, False)  # fully empty
    dPf_dQtvsc = CSC(len(k_cbr_pf), len(u_vsc_qt), 0, False)  # fully empty
    dPf_dPfhvdc = CSC(len(k_cbr_pf), nhvdc, 0, False)  # fully empty
    dPf_dPthvdc = CSC(len(k_cbr_pf), nhvdc, 0, False)  # fully empty
    dPf_dQfhvdc = CSC(len(k_cbr_pf), nhvdc, 0, False)  # fully empty
    dPf_dQthvdc = CSC(len(k_cbr_pf), nhvdc, 0, False)  # fully empty
    dPf_dm = deriv.dSf_dm_csc(nbr, k_cbr_pf, u_cbr_m, F, T, Ys, Bc, tap, tap_modules, V).real
    dPf_dtau = deriv.dSf_dtau_csc(nbr, k_cbr_pf, u_cbr_tau, F, T, Ys, tap, V).real

    # -------- ROW 9 (Pt) ---------
    dPt_dVa = deriv.dSt_dVa_csc(nbus, k_cbr_pt, i_u_va, ytf_cbr, V, F, T).real
    dPt_dVm = deriv.dSt_dVm_csc(nbus, k_cbr_pt, i_u_vm, ytt_cbr, ytf_cbr, Vm, Va, F, T).real
    dPt_dPfpvsc = CSC(len(k_cbr_pt), len(u_vsc_pfp), 0, False)  # fully empty
    dPt_dPfnvsc = CSC(len(k_cbr_pt), len(u_vsc_pfn), 0, False)  # fully empty
    dPt_dPtvsc = CSC(len(k_cbr_pt), len(u_vsc_pt), 0, False)  # fully empty
    dPt_dQtvsc = CSC(len(k_cbr_pt), len(u_vsc_qt), 0, False)  # fully empty
    dPt_dPfhvdc = CSC(len(k_cbr_pt), nhvdc, 0, False)  # fully empty
    dPt_dPthvdc = CSC(len(k_cbr_pt), nhvdc, 0, False)  # fully empty
    dPt_dQfhvdc = CSC(len(k_cbr_pt), nhvdc, 0, False)  # fully empty
    dPt_dQthvdc = CSC(len(k_cbr_pt), nhvdc, 0, False)  # fully empty
    dPt_dm = deriv.dSt_dm_csc(nbr, k_cbr_pt, u_cbr_m, F, T, Ys, tap, tap_modules, V).real
    dPt_dtau = deriv.dSt_dtau_csc(nbr, k_cbr_pt, u_cbr_tau, F, T, Ys, tap, V).real

    # -------- ROW 10 (Qf) ---------
    dQf_dVa = deriv.dSf_dVa_csc(nbus, k_cbr_qf, i_u_va, yft_cbr, V, F, T).imag
    dQf_dVm = deriv.dSf_dVm_csc(nbus, k_cbr_qf, i_u_vm, yff_cbr, yft_cbr, Vm, Va, F, T).imag
    dQf_dPfpvsc = CSC(len(k_cbr_qf), len(u_vsc_pfp), 0, False)  # fully empty
    dQf_dPfnvsc = CSC(len(k_cbr_qf), len(u_vsc_pfn), 0, False)  # fully empty
    dQf_dPtvsc = CSC(len(k_cbr_qf), len(u_vsc_pt), 0, False)  # fully empty
    dQf_dQtvsc = CSC(len(k_cbr_qf), len(u_vsc_qt), 0, False)  # fully empty
    dQf_dPfhvdc = CSC(len(k_cbr_qf), nhvdc, 0, False)  # fully empty
    dQf_dPthvdc = CSC(len(k_cbr_qf), nhvdc, 0, False)  # fully empty
    dQf_dQfhvdc = CSC(len(k_cbr_qf), nhvdc, 0, False)  # fully empty
    dQf_dQthvdc = CSC(len(k_cbr_qf), nhvdc, 0, False)  # fully empty
    dQf_dm = deriv.dSf_dm_csc(nbr, k_cbr_qf, u_cbr_m, F, T, Ys, Bc, tap, tap_modules, V).imag
    dQf_dtau = deriv.dSf_dtau_csc(nbr, k_cbr_qf, u_cbr_tau, F, T, Ys, tap, V).imag

    # -------- ROW 11 (Qt) ---------
    dQt_dVa = deriv.dSt_dVa_csc(nbus, k_cbr_qt, i_u_va, ytf_cbr, V, F, T).imag
    dQt_dVm = deriv.dSt_dVm_csc(nbus, k_cbr_qt, i_u_vm, ytt_cbr, ytf_cbr, Vm, Va, F, T).imag
    dQt_dPfpvsc = CSC(len(k_cbr_qt), len(u_vsc_pfp), 0, False)  # fully empty
    dQt_dPfnvsc = CSC(len(k_cbr_qt), len(u_vsc_pfn), 0, False)  # fully empty
    dQt_dPtvsc = CSC(len(k_cbr_qt), len(u_vsc_pt), 0, False)  # fully empty
    dQt_dQtvsc = CSC(len(k_cbr_qt), len(u_vsc_qt), 0, False)  # fully empty
    dQt_dPfhvdc = CSC(len(k_cbr_qt), nhvdc, 0, False)  # fully empty
    dQt_dPthvdc = CSC(len(k_cbr_qt), nhvdc, 0, False)  # fully empty
    dQt_dQfhvdc = CSC(len(k_cbr_qt), nhvdc, 0, False)  # fully empty
    dQt_dQthvdc = CSC(len(k_cbr_qt), nhvdc, 0, False)  # fully empty
    dQt_dm = deriv.dSt_dm_csc(nbr, k_cbr_qt, u_cbr_m, F, T, Ys, tap, tap_modules, V).imag
    dQt_dtau = deriv.dSt_dtau_csc(nbr, k_cbr_qt, u_cbr_tau, F, T, Ys, tap, V).imag

    J_jo = csc_stack_2d_ff(mats=[

        dP_dVa, dP_dVm, dP_dPfpvsc, dP_dPfnvsc, dP_dPtvsc, dP_dQtvsc, dP_dPfhvdc, dP_dPthvdc, dP_dQfhvdc, dP_dQthvdc, dP_dm, dP_dtau,

        # dQ_dVa, dQ_dVm, dQ_dPfpvsc, dQ_dPfnvsc, dQ_dPtvsc, dQ_dQtvsc, dQ_dPfhvdc, dQ_dPthvdc, dQ_dQfhvdc, dQ_dQthvdc, dQ_dm, dQ_dtau,

        # dLvsc_dVa, dLvsc_dVm, dLvsc_dPfpvsc, dLvsc_dPfnvsc, dLvsc_dPtvsc, dLvsc_dQtvsc, dLvsc_dPfhvdc, dLvsc_dPthvdc,
        # dLvsc_dQfhvdc, dLvsc_dQthvdc, dLvsc_dm, dLvsc_dtau,

        # dIvsc_dVa, dIvsc_dVm, dIvsc_dPfpvsc, dIvsc_dPfnvsc, dIvsc_dPtvsc, dIvsc_dQtvsc, dIvsc_dPfhvdc, dIvsc_dPthvdc,
        # dIvsc_dQfhvdc, dIvsc_dQthvdc, dIvsc_dm, dIvsc_dtau,
    ], n_rows=1, n_cols=12)

    # compose the Jacobian
    J = csc_stack_2d_ff(mats=[
        dP_dVa, dP_dVm, dP_dPfpvsc, dP_dPfnvsc, dP_dPtvsc, dP_dQtvsc, dP_dPfhvdc, dP_dPthvdc, dP_dQfhvdc, dP_dQthvdc, dP_dm, dP_dtau,

        dQ_dVa, dQ_dVm, dQ_dPfpvsc, dQ_dPfnvsc, dQ_dPtvsc, dQ_dQtvsc, dQ_dPfhvdc, dQ_dPthvdc, dQ_dQfhvdc, dQ_dQthvdc, dQ_dm, dQ_dtau,

        dLvsc_dVa, dLvsc_dVm, dLvsc_dPfpvsc, dLvsc_dPfnvsc, dLvsc_dPtvsc, dLvsc_dQtvsc, dLvsc_dPfhvdc, dLvsc_dPthvdc,
        dLvsc_dQfhvdc, dLvsc_dQthvdc, dLvsc_dm, dLvsc_dtau,

        dIvsc_dVa, dIvsc_dVm, dIvsc_dPfpvsc, dIvsc_dPfnvsc, dIvsc_dPtvsc, dIvsc_dQtvsc, dIvsc_dPfhvdc, dIvsc_dPthvdc,
        dIvsc_dQfhvdc, dIvsc_dQthvdc, dIvsc_dm, dIvsc_dtau,

        dImax_dVa, dImax_dVm, dImax_dPfpvsc, dImax_dPfnvsc, dImax_dPtvsc, dImax_dQtvsc, dImax_dPfhvdc, dImax_dPthvdc,
        dImax_dQfhvdc, dImax_dQthvdc, dImax_dm, dImax_dtau,

        dLhvdc_dVa, dLhvdc_dVm, dLhvdc_dPfpvsc, dLhvdc_dPfnvsc, dLhvdc_dPtvsc, dLhvdc_dQtvsc, dLhvdc_dPfhvdc, dLhvdc_dPthvdc,
        dLhvdc_dQfhvdc, dLhvdc_dQthvdc, dLhvdc_dm, dLhvdc_dtau,

        dInjhvdc_dVa, dInjhvdc_dVm, dInjhvdc_dPfpvsc, dInjhvdc_dPfnvsc, dInjhvdc_dPtvsc, dInjhvdc_dQtvsc, dInjhvdc_dPfhvdc,
        dInjhvdc_dPthvdc, dInjhvdc_dQfhvdc, dInjhvdc_dQthvdc, dInjhvdc_dm, dInjhvdc_dtau,

        dPf_dVa, dPf_dVm, dPf_dPfpvsc, dPf_dPfnvsc, dPf_dPtvsc, dPf_dQtvsc, dPf_dPfhvdc, dPf_dPthvdc, dPf_dQfhvdc,
        dPf_dQthvdc, dPf_dm, dPf_dtau,

        dPt_dVa, dPt_dVm, dPt_dPfpvsc, dPt_dPfnvsc, dPt_dPtvsc, dPt_dQtvsc, dPt_dPfhvdc, dPt_dPthvdc, dPt_dQfhvdc,
        dPt_dQthvdc, dPt_dm, dPt_dtau,

        dQf_dVa, dQf_dVm, dQf_dPfpvsc, dQf_dPfnvsc, dQf_dPtvsc, dQf_dQtvsc, dQf_dPfhvdc, dQf_dPthvdc, dQf_dQfhvdc,
        dQf_dQthvdc, dQf_dm, dQf_dtau,

        dQt_dVa, dQt_dVm, dQt_dPfpvsc, dQt_dPfnvsc, dQt_dPtvsc, dQt_dQtvsc, dQt_dPfhvdc, dQt_dPthvdc, dQt_dQfhvdc,
        dQt_dQthvdc, dQt_dm, dQt_dtau

    ], n_rows=11, n_cols=12)

    return J


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
                                 Fdcp_vsc: IntVec, Fdcn_vsc: IntVec, T_vsc: IntVec,
                                 Pfp_vsc: Vec, Pfn_vsc: Vec, St_vsc: CxVec) -> CxVec:
    """
    Summation of magnitudes per bus (complex)
    Includes everything: VSCs, HVDCs, and all 
    traditional branches (lines and controllable transformers)
    :param nbus:
    :param F_br:
    :param T_br:
    :param Sf_br:
    :param St_br:
    :param F_hvdc:
    :param T_hvdc:
    :param Sf_hvdc:
    :param St_hvdc:
    :param Fdcp_vsc:
    :param Fdcn_vsc:
    :param T_vsc:
    :param Pfp_vsc:
    :param Pfn_vsc:
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

    # Add VSC with its 3 terminals
    for i in range(len(Fdcp_vsc)):
        res[Fdcp_vsc[i]] += Pfp_vsc[i]
        res[Fdcn_vsc[i]] += Pfn_vsc[i]
        res[T_vsc[i]] += St_vsc[i]

    return res


@njit(cache=True)
def calc_flows_active_branch_per_bus(nbus: int,
                                     F_hvdc: IntVec, T_hvdc: IntVec, Sf_hvdc: CxVec, St_hvdc: CxVec,
                                     Fdcp_vsc: IntVec, Fdcn_vsc: IntVec, T_vsc: IntVec,
                                     Pfp_vsc: Vec, Pfn_vsc: Vec, St_vsc: CxVec) -> CxVec:
    """
    Summation of magnitudes per bus (complex)
    Used to add effects of VSCs and HVDCs to 
    the traditional branches (lines and controllable transformers)
    :param nbus:
    :param F_hvdc:
    :param T_hvdc:
    :param Sf_hvdc:
    :param St_hvdc:
    :param Fdcp_vsc:
    :param Fdcn_vsc:
    :param T_vsc:
    :param Pfp_vsc:
    :param Pfn_vsc:
    :param St_vsc:
    :return:
    """

    res = np.zeros(nbus, dtype=np.complex128)

    # Add HVDC
    for i in range(len(F_hvdc)):
        res[F_hvdc[i]] += Sf_hvdc[i]
        res[T_hvdc[i]] += St_hvdc[i]

    # Add VSC
    for i in range(len(Fdcp_vsc)):
        res[Fdcp_vsc[i]] += Pfp_vsc[i]
        res[Fdcn_vsc[i]] += Pfn_vsc[i]
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


class PfAcDcWithNegativePoles(PfFormulationTemplate):

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

        # Indices ------------------------------------------------------------------------------------------------------

        # Bus indices (initial values)
        self.bus_types = nc.bus_data.bus_types.copy()
        self.bus_grounded = nc.bus_data.is_grounded.copy()
        self.is_p_controlled = nc.bus_data.is_p_controlled.copy()
        self.is_q_controlled = nc.bus_data.is_q_controlled.copy()
        self.is_vm_controlled = nc.bus_data.is_vm_controlled.copy()
        self.is_va_controlled = nc.bus_data.is_va_controlled.copy()

        # Fill controllable Branch Indices
        self.u_cbr_m = np.zeros(0, dtype=int)
        self.u_cbr_tau = np.zeros(0, dtype=int)
        self.u_cbr_m_tau = np.zeros(0, dtype=int)

        self.k_cbr_pf = np.zeros(0, dtype=int)
        self.k_cbr_pt = np.zeros(0, dtype=int)
        self.k_cbr_qf = np.zeros(0, dtype=int)
        self.k_cbr_qt = np.zeros(0, dtype=int)
        self.cbr_pf_set = np.zeros(0, dtype=float)
        self.cbr_pt_set = np.zeros(0, dtype=float)
        self.cbr_qf_set = np.zeros(0, dtype=float)
        self.cbr_qt_set = np.zeros(0, dtype=float)

        self._set_branch_control_indices()

        # Fill VSC Indices
        self.u_vsc_pfp = np.zeros(0, dtype=int)
        self.u_vsc_pfn = np.zeros(0, dtype=int)
        self.u_vsc_pt = np.zeros(0, dtype=int)
        self.u_vsc_qt = np.zeros(0, dtype=int)
        self.k_vsc_pfp = np.zeros(0, dtype=int)
        self.k_vsc_pfn = np.zeros(0, dtype=int)
        self.k_vsc_pt = np.zeros(0, dtype=int)
        self.k_vsc_qt = np.zeros(0, dtype=int)
        self.k_vsc_i = np.zeros(0, dtype=int)
        self.vsc_pfp_set = np.zeros(0, dtype=float)
        self.vsc_pfn_set = np.zeros(0, dtype=float)
        self.vsc_pt_set = np.zeros(0, dtype=float)
        self.vsc_qt_set = np.zeros(0, dtype=float)
        self.vsc_i_set = np.zeros(0, dtype=float)
        self._set_vsc_control_indices()

        # Fill HVDC Indices
        self.hvdc_droop_idx = np.zeros(0, dtype=int)
        self._set_hvdc_control_indices()

        # Alter bus indices after all other index initializations
        self.i_u_vm = np.zeros(0, dtype=int)
        self.i_u_va = np.zeros(0, dtype=int)
        self.i_k_p = np.zeros(0, dtype=int)
        self.i_k_q = np.zeros(0, dtype=int)
        self._set_bus_control_indices()

        # Unknowns -----------------------------------------------------------------------------------------------------
        # Va and Vm are set at the parent
        self.Pfp_vsc = np.zeros(nc.vsc_data.nelm)
        self.Pfn_vsc = np.zeros(nc.vsc_data.nelm)
        self.Pt_vsc = np.zeros(nc.vsc_data.nelm)
        self.Qt_vsc = np.zeros(nc.vsc_data.nelm)
        self.Pf_hvdc = np.zeros(nc.hvdc_data.nelm)
        self.Qf_hvdc = np.zeros(nc.hvdc_data.nelm)
        self.Pt_hvdc = np.zeros(nc.hvdc_data.nelm)
        self.Qt_hvdc = np.zeros(nc.hvdc_data.nelm)
        self.m = self.nc.active_branch_data.tap_module[self.u_cbr_m]
        self.tau = self.nc.active_branch_data.tap_angle[self.u_cbr_tau]

        # set the VSC set-points
        self.Pfp_vsc[self.k_vsc_pfp] = self.vsc_pfp_set / self.nc.Sbase
        self.Pfn_vsc[self.k_vsc_pfn] = self.vsc_pfn_set / self.nc.Sbase
        self.Pt_vsc[self.k_vsc_pt] = self.vsc_pt_set / self.nc.Sbase
        self.Qt_vsc[self.k_vsc_qt] = self.vsc_qt_set / self.nc.Sbase

        # Admittance ---------------------------------------------------------------------------------------------------
        self.adm = compute_admittances_fast(
            nbus=self.nc.bus_data.nbus,
            R=self.nc.passive_branch_data.R,
            X=self.nc.passive_branch_data.X,
            G=self.nc.passive_branch_data.G,
            B=self.nc.passive_branch_data.B,
            tap_module=expand(self.nc.nbr, self.m, self.u_cbr_m, 1.0),
            vtap_f=self.nc.passive_branch_data.virtual_tap_f,
            vtap_t=self.nc.passive_branch_data.virtual_tap_t,
            tap_angle=expand(self.nc.nbr, self.tau, self.u_cbr_tau, 0.0),
            F=self.nc.passive_branch_data.F,
            T=self.nc.passive_branch_data.T,
            Yshunt_bus=self.nc.get_Yshunt_bus_pu(),
        )
        self.adm.initialize_update()  # allows mega fast matrix updates

        if self.options.verbose > 1:
            print("Ybus\n", self.adm.Ybus.toarray())

    def _update_Qlim_indices(self, i_u_vm: IntVec, i_k_q: IntVec) -> None:
        """
        Update the indices due to applying Q limits
        :param i_u_vm: Indices of unknown voltage magnitudes
        :param i_k_q: Indices of Q controlled buses
        """
        self.i_u_vm = i_u_vm
        self.i_k_q = i_k_q

    def _set_bus_control_indices(self) -> None:
        """
        Analyze the bus indices from the boolean marked arrays
        """
        self.i_u_vm = np.where(self.is_vm_controlled == 0)[0]
        self.i_u_va = np.where(self.is_va_controlled == 0)[0]
        self.i_k_p = np.where(self.is_p_controlled == 1)[0]
        self.i_k_q = np.where(self.is_q_controlled == 1)[0]

    def _set_branch_control_indices(self) -> None:
        """
        Analyze the control branches and compute the indices
        """
        # Controllable Branch Indices
        u_cbr_m = list()
        u_cbr_tau = list()
        k_cbr_pf = list()
        k_cbr_pt = list()
        k_cbr_qf = list()
        k_cbr_qt = list()
        cbr_pf_set = list()
        cbr_pt_set = list()
        cbr_qf_set = list()
        cbr_qt_set = list()

        original_to_island_bus_dict: Dict[int, int] = self.nc.bus_data.get_original_to_island_bus_dict()

        # CONTROLLABLE BRANCH LOOP
        for k in range(self.nc.passive_branch_data.nelm):

            ctrl_m = self.nc.active_branch_data.tap_module_control_mode[k]
            ctrl_tau = self.nc.active_branch_data.tap_phase_control_mode[k]

            # analyze tap-module controls
            if ctrl_m == TapModuleControl.Vm:

                # Every bus controlled by m has to become a PQV bus
                bus_idx: int = int(self.nc.active_branch_data.tap_controlled_buses[k])
                island_bus_idx = original_to_island_bus_dict.get(bus_idx, None)
                # self.is_p_controlled[bus_idx] = True
                # self.is_q_controlled[bus_idx] = True
                if island_bus_idx is not None:
                    if not self.is_vm_controlled[island_bus_idx]:
                        self.is_vm_controlled[island_bus_idx] = True
                        u_cbr_m.append(k)
                else:
                    self.logger.add_error("Controlled bus index outside of the island, skipping control",
                                          device=self.nc.passive_branch_data.idtag[k],)

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

        self.u_cbr_m = np.array(u_cbr_m, dtype=int)
        self.u_cbr_tau = np.array(u_cbr_tau, dtype=int)
        self.u_cbr_m_tau = np.unique(np.r_[u_cbr_m, u_cbr_tau]).astype(int)

        self.k_cbr_pf = np.array(k_cbr_pf, dtype=int)
        self.k_cbr_pt = np.array(k_cbr_pt, dtype=int)
        self.k_cbr_qf = np.array(k_cbr_qf, dtype=int)
        self.k_cbr_qt = np.array(k_cbr_qt, dtype=int)

        self.cbr_pf_set = np.array(cbr_pf_set, dtype=float)
        self.cbr_pt_set = np.array(cbr_pt_set, dtype=float)
        self.cbr_qf_set = np.array(cbr_qf_set, dtype=float)
        self.cbr_qt_set = np.array(cbr_qt_set, dtype=float)

    def _set_vsc_control_indices(self) -> None:
        """
        Analyze the control branches and compute the indices
        :return: None
        """

        # VSC Indices
        u_vsc_pfp = list()
        u_vsc_pfn = list()
        u_vsc_pt = list()
        u_vsc_qt = list()
        k_vsc_pfp = list()
        k_vsc_pfn = list()
        k_vsc_pt = list()
        k_vsc_qt = list()
        k_vsc_i = list()
        vsc_pfp_set = list()
        vsc_pfn_set = list()
        vsc_pt_set = list()
        vsc_qt_set = list()
        vsc_i_set = list()

        # VSC LOOP
        for k in range(self.nc.vsc_data.nelm):

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
            Imax = 'Imax'
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
                u_vsc_pfp.append(k)
                u_vsc_pfn.append(k)
                u_vsc_pt.append(k)
                u_vsc_qt.append(k)

            elif control1 == ConverterControlType.Vm_dc and control2 == ConverterControlType.Va_ac:
                if control1_bus_device > -1:
                    self.is_vm_controlled[control1_bus_device] = True
                if control2_bus_device > -1:
                    self.is_va_controlled[control2_bus_device] = True
                u_vsc_pfp.append(k)
                u_vsc_pfn.append(k)
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
                    u_vsc_pfp.append(control2_branch_device)
                    u_vsc_pfn.append(control2_branch_device)
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

                    u_vsc_pfn.append(control2_branch_device)

                    k_vsc_pfp.append(control2_branch_device)

                    vsc_pfp_set.append(control2_magnitude)

            elif control1 == ConverterControlType.Vm_dc and control2 == ConverterControlType.Pac:
                if control1_bus_device > -1:
                    self.is_vm_controlled[control1_bus_device] = True
                if control2_bus_device > -1:
                    pass
                if control1_branch_device > -1:
                    pass
                if control2_branch_device > -1:
                    u_vsc_pfp.append(control2_branch_device)
                    u_vsc_pfn.append(control2_branch_device)
                    u_vsc_qt.append(control2_branch_device)

                    k_vsc_pt.append(control2_branch_device)

                    vsc_pt_set.append(control2_magnitude)

            elif control1 == ConverterControlType.Vm_dc and control2 == ConverterControlType.Imax:
                if control1_bus_device > -1:
                    self.is_vm_controlled[control1_bus_device] = True
                if control2_bus_device > -1:
                    pass
                if control1_branch_device > -1:
                    pass
                if control2_branch_device > -1:
                    u_vsc_pfp.append(control2_branch_device)
                    u_vsc_pfn.append(control2_branch_device)
                    u_vsc_pt.append(control2_branch_device)
                    u_vsc_qt.append(control2_branch_device)

                    k_vsc_i.append(control2_branch_device)

                    vsc_i_set.append(control2_magnitude)

            elif control1 == ConverterControlType.Vm_ac and control2 == ConverterControlType.Vm_dc:
                if control1_bus_device > -1:
                    self.is_vm_controlled[control1_bus_device] = True
                if control2_bus_device > -1:
                    self.is_vm_controlled[control2_bus_device] = True
                u_vsc_pfp.append(k)
                u_vsc_pfn.append(k)
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
                u_vsc_pfp.append(k)
                u_vsc_pfn.append(k)
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
                    u_vsc_pfp.append(control2_branch_device)
                    u_vsc_pfn.append(control2_branch_device)
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
                    u_vsc_pfn.append(control2_branch_device)

                    k_vsc_pfp.append(control2_branch_device)
                    vsc_pfp_set.append(control2_magnitude)

            elif control1 == ConverterControlType.Vm_ac and control2 == ConverterControlType.Pac:
                if control1_bus_device > -1:
                    self.is_vm_controlled[control1_bus_device] = True
                if control2_bus_device > -1:
                    pass
                if control1_branch_device > -1:
                    pass
                if control2_branch_device > -1:
                    u_vsc_pfp.append(control2_branch_device)
                    u_vsc_pfn.append(control2_branch_device)
                    u_vsc_qt.append(control2_branch_device)

                    k_vsc_pt.append(control2_branch_device)
                    vsc_pt_set.append(control2_magnitude)

            elif control1 == ConverterControlType.Vm_ac and control2 == ConverterControlType.Imax:
                if control1_bus_device > -1:
                    self.is_vm_controlled[control1_bus_device] = True
                if control2_bus_device > -1:
                    pass
                if control1_branch_device > -1:
                    pass
                if control2_branch_device > -1:
                    u_vsc_pfp.append(control2_branch_device)
                    u_vsc_pfn.append(control2_branch_device)
                    u_vsc_pt.append(control2_branch_device)
                    u_vsc_qt.append(control2_branch_device)

                    k_vsc_i.append(control2_branch_device)

                    vsc_i_set.append(control2_magnitude)

            elif control1 == ConverterControlType.Va_ac and control2 == ConverterControlType.Vm_dc:
                if control1_bus_device > -1:
                    self.is_va_controlled[control1_bus_device] = True
                if control2_bus_device > -1:
                    self.is_vm_controlled[control2_bus_device] = True
                u_vsc_pfp.append(k)
                u_vsc_pfn.append(k)
                u_vsc_pt.append(k)
                u_vsc_qt.append(k)

            elif control1 == ConverterControlType.Va_ac and control2 == ConverterControlType.Vm_ac:
                if control1_bus_device > -1:
                    self.is_va_controlled[control1_bus_device] = True
                if control2_bus_device > -1:
                    self.is_vm_controlled[control2_bus_device] = True
                u_vsc_pfp.append(k)
                u_vsc_pfn.append(k)
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
                    u_vsc_pfp.append(control2_branch_device)
                    u_vsc_pfn.append(control2_branch_device)
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
                    u_vsc_pfn.append(control2_branch_device)

                    k_vsc_pfp.append(control2_branch_device)
                    vsc_pfp_set.append(control2_magnitude)

            elif control1 == ConverterControlType.Va_ac and control2 == ConverterControlType.Pac:
                if control1_bus_device > -1:
                    self.is_va_controlled[control1_bus_device] = True
                if control2_bus_device > -1:
                    pass
                if control1_branch_device > -1:
                    pass
                if control2_branch_device > -1:
                    u_vsc_pfp.append(control2_branch_device)
                    u_vsc_pfn.append(control2_branch_device)
                    u_vsc_qt.append(control2_branch_device)

                    k_vsc_pt.append(control2_branch_device)
                    vsc_pt_set.append(control2_magnitude)

            elif control1 == ConverterControlType.Va_ac and control2 == ConverterControlType.Imax:
                if control1_bus_device > -1:
                    self.is_va_controlled[control1_bus_device] = True
                if control2_bus_device > -1:
                    pass
                if control1_branch_device > -1:
                    pass
                if control2_branch_device > -1:
                    u_vsc_pfp.append(control2_branch_device)
                    u_vsc_pfn.append(control2_branch_device)
                    u_vsc_pt.append(control2_branch_device)
                    u_vsc_qt.append(control2_branch_device)

                    k_vsc_i.append(control2_branch_device)

                    vsc_i_set.append(control2_magnitude)


            elif control1 == ConverterControlType.Qac and control2 == ConverterControlType.Vm_dc:
                if control2_bus_device > -1:
                    self.is_vm_controlled[control2_bus_device] = True
                if control1_branch_device > -1:
                    u_vsc_pfp.append(control1_branch_device)
                    u_vsc_pfn.append(control1_branch_device)
                    u_vsc_pt.append(control1_branch_device)

                    k_vsc_qt.append(control1_branch_device)
                    vsc_qt_set.append(control1_magnitude)

            elif control1 == ConverterControlType.Qac and control2 == ConverterControlType.Vm_ac:
                if control2_bus_device > -1:
                    self.is_vm_controlled[control2_bus_device] = True
                if control1_branch_device > -1:
                    u_vsc_pfp.append(control1_branch_device)
                    u_vsc_pfn.append(control1_branch_device)
                    u_vsc_pt.append(control1_branch_device)

                    k_vsc_qt.append(control1_branch_device)
                    vsc_qt_set.append(control1_magnitude)

            elif control1 == ConverterControlType.Qac and control2 == ConverterControlType.Va_ac:
                if control2_bus_device > -1:
                    self.is_va_controlled[control2_bus_device] = True
                if control1_branch_device > -1:
                    u_vsc_pfp.append(control1_branch_device)
                    u_vsc_pfn.append(control1_branch_device)
                    u_vsc_pt.append(control1_branch_device)

                    k_vsc_qt.append(control1_branch_device)
                    vsc_qt_set.append(control1_magnitude)

            elif control1 == ConverterControlType.Qac and control2 == ConverterControlType.Qac:
                self.logger.add_error(
                    f"VSC control1 and control2 are the same for VSC indexed at {k},"
                    f" control1: {control1}, control2: {control2}")

            elif control1 == ConverterControlType.Qac and control2 == ConverterControlType.Pdc:
                if control1_branch_device > -1:
                    u_vsc_pfn.append(control1_branch_device)
                    u_vsc_pt.append(control1_branch_device)
                    k_vsc_qt.append(control1_branch_device)
                    vsc_qt_set.append(control1_magnitude)

                if control2_branch_device > -1:
                    k_vsc_pfp.append(control2_branch_device)
                    vsc_pfp_set.append(control2_magnitude)

            elif control1 == ConverterControlType.Qac and control2 == ConverterControlType.Pac:
                if control1_branch_device > -1:
                    u_vsc_pfp.append(control1_branch_device)
                    u_vsc_pfn.append(control1_branch_device)
                    k_vsc_qt.append(control1_branch_device)
                    vsc_qt_set.append(control1_magnitude)

                if control2_branch_device > -1:
                    k_vsc_pt.append(control2_branch_device)
                    vsc_pt_set.append(control2_magnitude)

            elif control1 == ConverterControlType.Qac and control2 == ConverterControlType.Imax:
                if control1_branch_device > -1:
                    u_vsc_pfp.append(control1_branch_device)
                    u_vsc_pfn.append(control1_branch_device)
                    u_vsc_pt.append(control1_branch_device)
                    k_vsc_qt.append(control1_branch_device)
                    vsc_qt_set.append(control1_magnitude)

                if control2_branch_device > -1:
                    k_vsc_i.append(control2_branch_device)
                    vsc_i_set.append(control2_magnitude)

            elif control1 == ConverterControlType.Pdc and control2 == ConverterControlType.Vm_dc:
                if control2_bus_device > -1:
                    self.is_vm_controlled[control2_bus_device] = True
                if control1_branch_device > -1:
                    u_vsc_pt.append(control1_branch_device)
                    u_vsc_qt.append(control1_branch_device)
                    u_vsc_pfn.append(control1_branch_device)

                    k_vsc_pfp.append(control1_branch_device)
                    vsc_pfp_set.append(control1_magnitude)

            elif control1 == ConverterControlType.Pdc and control2 == ConverterControlType.Vm_ac:
                if control2_bus_device > -1:
                    self.is_vm_controlled[control2_bus_device] = True
                if control1_branch_device > -1:
                    u_vsc_pt.append(control1_branch_device)
                    u_vsc_qt.append(control1_branch_device)
                    u_vsc_pfn.append(control1_branch_device)

                    k_vsc_pfp.append(control1_branch_device)
                    vsc_pfp_set.append(control1_magnitude)

            elif control1 == ConverterControlType.Pdc and control2 == ConverterControlType.Va_ac:
                if control2_bus_device > -1:
                    self.is_va_controlled[control2_bus_device] = True
                if control1_branch_device > -1:
                    u_vsc_pt.append(control1_branch_device)
                    u_vsc_qt.append(control1_branch_device)
                    u_vsc_pfn.append(control1_branch_device)

                    k_vsc_pfp.append(control1_branch_device)
                    vsc_pfp_set.append(control1_magnitude)

            elif control1 == ConverterControlType.Pdc and control2 == ConverterControlType.Qac:
                if control1_branch_device > -1:
                    u_vsc_pt.append(control1_branch_device)
                    u_vsc_pfn.append(control1_branch_device)

                    k_vsc_pfp.append(control1_branch_device)
                    vsc_pfp_set.append(control1_magnitude)

                if control2_branch_device > -1:
                    k_vsc_qt.append(control2_branch_device)
                    vsc_qt_set.append(control2_magnitude)

            elif control1 == ConverterControlType.Pdc and control2 == ConverterControlType.Pdc:
                self.logger.add_error(
                    f"VSC control1 and control2 are the same for VSC indexed at {k},"
                    f" control1: {control1}, control2: {control2}")

            elif control1 == ConverterControlType.Pdc and control2 == ConverterControlType.Pac:
                if control1_branch_device > -1:
                    u_vsc_pt.append(control1_branch_device)
                    u_vsc_qt.append(control1_branch_device)
                    u_vsc_pfn.append(control1_branch_device)

                    k_vsc_pfp.append(control1_branch_device)
                    vsc_pfp_set.append(control1_magnitude)

                    k_vsc_pt.append(control1_branch_device)
                    vsc_pt_set.append(control1_magnitude)

            elif control1 == ConverterControlType.Pdc and control2 == ConverterControlType.Imax:
                if control1_branch_device > -1:
                    u_vsc_pt.append(control1_branch_device)
                    u_vsc_qt.append(control1_branch_device)
                    u_vsc_pfn.append(control1_branch_device)

                    k_vsc_pfp.append(control1_branch_device)
                    vsc_pfp_set.append(control1_magnitude)

                if control2_branch_device > -1:
                    k_vsc_i.append(control2_branch_device)
                    vsc_i_set.append(control2_magnitude)

            elif control1 == ConverterControlType.Pac and control2 == ConverterControlType.Vm_dc:
                if control2_bus_device > -1:
                    self.is_vm_controlled[control2_bus_device] = True
                if control1_branch_device > -1:
                    u_vsc_pfp.append(control1_branch_device)
                    u_vsc_pfn.append(control1_branch_device)
                    u_vsc_qt.append(control1_branch_device)

                    k_vsc_pt.append(control1_branch_device)
                    vsc_pt_set.append(control1_magnitude)

            elif control1 == ConverterControlType.Pac and control2 == ConverterControlType.Vm_ac:
                if control2_bus_device > -1:
                    self.is_vm_controlled[control2_bus_device] = True
                if control1_branch_device > -1:
                    u_vsc_pfp.append(control1_branch_device)
                    u_vsc_pfn.append(control1_branch_device)
                    u_vsc_qt.append(control1_branch_device)

                    k_vsc_pt.append(control1_branch_device)
                    vsc_pt_set.append(control1_magnitude)


            elif control1 == ConverterControlType.Pac and control2 == ConverterControlType.Va_ac:
                if control2_bus_device > -1:
                    self.is_va_controlled[control2_bus_device] = True
                if control1_branch_device > -1:
                    u_vsc_pfp.append(control1_branch_device)
                    u_vsc_pfn.append(control1_branch_device)
                    u_vsc_qt.append(control1_branch_device)

                    k_vsc_pt.append(control1_branch_device)
                    vsc_pt_set.append(control1_magnitude)

            elif control1 == ConverterControlType.Pac and control2 == ConverterControlType.Qac:
                if control1_branch_device > -1:
                    u_vsc_pfp.append(control1_branch_device)
                    u_vsc_pfn.append(control1_branch_device)

                    k_vsc_pt.append(control1_branch_device)
                    k_vsc_qt.append(control1_branch_device)
                    vsc_qt_set.append(control2_magnitude)
                    vsc_pt_set.append(control1_magnitude)

            elif control1 == ConverterControlType.Pac and control2 == ConverterControlType.Pdc:
                if control1_branch_device > -1:
                    u_vsc_pfn.append(control1_branch_device)
                    u_vsc_qt.append(control1_branch_device)

                    k_vsc_pfp.append(control1_branch_device)
                    vsc_pfp_set.append(control1_magnitude)

                    k_vsc_pt.append(control1_branch_device)
                    vsc_pt_set.append(control1_magnitude)

            elif control1 == ConverterControlType.Pac and control2 == ConverterControlType.Pac:
                self.logger.add_error(
                    f"VSC control1 and control2 are the same for VSC indexed at {k},"
                    f" control1: {control1}, control2: {control2}")

            elif control1 == ConverterControlType.Pac and control2 == ConverterControlType.Imax:
                if control1_branch_device > -1:
                    u_vsc_pfp.append(control1_branch_device)
                    u_vsc_pfn.append(control1_branch_device)
                    u_vsc_qt.append(control1_branch_device)

                    k_vsc_pt.append(control1_branch_device)
                    vsc_pt_set.append(control1_magnitude)

                if control2_branch_device > -1:
                    k_vsc_i.append(control2_branch_device)
                    vsc_i_set.append(control2_magnitude)

            elif control1 == ConverterControlType.Imax and control2 == ConverterControlType.Vm_dc:
                if control1_branch_device > -1:
                    u_vsc_pfp.append(control1_branch_device)
                    u_vsc_pfn.append(control1_branch_device)
                    u_vsc_pt.append(control1_branch_device)
                    u_vsc_qt.append(control1_branch_device)

                    k_vsc_i.append(control1_branch_device)
                    vsc_i_set.append(control1_magnitude)

                if control2_bus_device > -1:
                    self.is_vm_controlled[control2_bus_device] = True

            elif control1 == ConverterControlType.Imax and control2 == ConverterControlType.Vm_ac:
                if control1_branch_device > -1:
                    u_vsc_pfp.append(control1_branch_device)
                    u_vsc_pfn.append(control1_branch_device)
                    u_vsc_pt.append(control1_branch_device)
                    u_vsc_qt.append(control1_branch_device)

                    k_vsc_i.append(control1_branch_device)
                    vsc_i_set.append(control1_magnitude)

                if control2_bus_device > -1:
                    self.is_vm_controlled[control2_bus_device] = True

            elif control1 == ConverterControlType.Imax and control2 == ConverterControlType.Va_ac:
                if control1_branch_device > -1:
                    u_vsc_pfp.append(control1_branch_device)
                    u_vsc_pfn.append(control1_branch_device)
                    u_vsc_pt.append(control1_branch_device)
                    u_vsc_qt.append(control1_branch_device)

                    k_vsc_i.append(control1_branch_device)
                    vsc_i_set.append(control1_magnitude)

                if control2_bus_device > -1:
                    self.is_va_controlled[control2_bus_device] = True

            elif control1 == ConverterControlType.Imax and control2 == ConverterControlType.Qac:
                if control1_branch_device > -1:
                    u_vsc_pfp.append(control1_branch_device)
                    u_vsc_pfn.append(control1_branch_device)
                    u_vsc_pt.append(control1_branch_device)

                    k_vsc_i.append(control1_branch_device)
                    vsc_i_set.append(control1_magnitude)

                if control2_branch_device > -1:
                    k_vsc_qt.append(control1_branch_device)
                    vsc_qt_set.append(control1_magnitude)

            elif control1 == ConverterControlType.Imax and control2 == ConverterControlType.Pdc:
                if control1_branch_device > -1:
                    u_vsc_pfn.append(control1_branch_device)
                    u_vsc_pt.append(control1_branch_device)
                    u_vsc_qt.append(control1_branch_device)

                    k_vsc_i.append(control1_branch_device)
                    vsc_i_set.append(control1_magnitude)

                if control2_branch_device > -1:
                    k_vsc_pfp.append(control2_branch_device)
                    vsc_pfp_set.append(control2_magnitude)

            elif control1 == ConverterControlType.Imax and control2 == ConverterControlType.Pac:
                if control1_branch_device > -1:
                    u_vsc_pfp.append(control1_branch_device)
                    u_vsc_pfn.append(control1_branch_device)
                    u_vsc_qt.append(control1_branch_device)

                    k_vsc_i.append(control1_branch_device)
                    vsc_i_set.append(control1_magnitude)

                if control2_branch_device > -1:
                    k_vsc_pt.append(control2_branch_device)
                    vsc_pt_set.append(control2_magnitude)

            elif control1 == ConverterControlType.Imax and control2 == ConverterControlType.Imax:
                self.logger.add_error(
                    f"VSC control1 and control2 are the same for VSC indexed at {k},"
                    f" control1: {control1}, control2: {control2}")


        # self.vsc = np.array(vsc, dtype=int)
        self.u_vsc_pfp = np.array(u_vsc_pfp, dtype=int)
        self.u_vsc_pfn = np.array(u_vsc_pfn, dtype=int)
        self.u_vsc_pt = np.array(u_vsc_pt, dtype=int)
        self.u_vsc_qt = np.array(u_vsc_qt, dtype=int)
        self.k_vsc_pfp = np.array(k_vsc_pfp, dtype=int)
        self.k_vsc_pfn = np.array(k_vsc_pfn, dtype=int)
        self.k_vsc_pt = np.array(k_vsc_pt, dtype=int)
        self.k_vsc_qt = np.array(k_vsc_qt, dtype=int)
        self.k_vsc_i = np.array(k_vsc_i, dtype=int)
        self.vsc_pfp_set = np.array(vsc_pfp_set, dtype=float)
        self.vsc_pfn_set = np.array(vsc_pfn_set, dtype=float)
        self.vsc_pt_set = np.array(vsc_pt_set, dtype=float)
        self.vsc_qt_set = np.array(vsc_qt_set, dtype=float)
        self.vsc_i_set = np.array(vsc_i_set, dtype=float)

    def _set_hvdc_control_indices(self) -> None:
        """
        Analyze the control hvdc and compute the indices
        :return: None
        """

        # HVDC Indices
        hvdc_droop_idx = list()

        # HVDC LOOP
        for k in range(self.nc.hvdc_data.nelm):

            self.is_q_controlled[self.nc.hvdc_data.F[k]] = True
            self.is_q_controlled[self.nc.hvdc_data.T[k]] = True

            if self.nc.hvdc_data.control_mode[k] == HvdcControlType.type_0_free:
                hvdc_droop_idx.append(k)

        # self.hvdc = np.array(hvdc, dtype=int)
        self.hvdc_droop_idx = np.array(hvdc_droop_idx)

    def x2var(self, x: Vec) -> None:
        """
        Convert X to decision variables
        :param x: solution vector
        """
        a = len(self.i_u_va)
        b = a + len(self.i_u_vm)
        c = b + len(self.u_vsc_pfp)
        d = c + len(self.u_vsc_pfn)
        e = d + len(self.u_vsc_pt)
        f = e + len(self.u_vsc_qt)
        g = f + self.nc.hvdc_data.nelm
        h = g + self.nc.hvdc_data.nelm
        i = h + self.nc.hvdc_data.nelm
        j = i + self.nc.hvdc_data.nelm
        k = j + len(self.u_cbr_m)
        l = k + len(self.u_cbr_tau)

        # update the vectors
        self.Va[self.i_u_va] = x[0:a]
        self.Vm[self.i_u_vm] = x[a:b]
        self.Pfp_vsc[self.u_vsc_pfp] = x[b:c]
        self.Pfn_vsc[self.u_vsc_pfn] = x[c:d]
        self.Pt_vsc[self.u_vsc_pt] = x[d:e]
        self.Qt_vsc[self.u_vsc_qt] = x[e:f]
        self.Pf_hvdc = x[f:g]
        self.Pt_hvdc = x[g:h]
        self.Qf_hvdc = x[h:i]
        self.Qt_hvdc = x[i:j]
        self.m = x[j:k]
        self.tau = x[k:l]

    def var2x(self) -> Vec:
        """
        Convert the internal decision variables into the vector
        :return: Vector
        """
        return np.r_[
            self.Va[self.i_u_va],
            self.Vm[self.i_u_vm],
            self.Pfp_vsc[self.u_vsc_pfp],
            self.Pfn_vsc[self.u_vsc_pfn],
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
                + len(self.u_vsc_pfp)
                + len(self.u_vsc_pfn)
                + len(self.u_vsc_pt)
                + len(self.u_vsc_qt)
                + self.nc.hvdc_data.nelm
                + self.nc.hvdc_data.nelm
                + self.nc.hvdc_data.nelm
                + self.nc.hvdc_data.nelm
                + len(self.u_cbr_m)
                + len(self.u_cbr_tau))

    def compute_f(self, x: Vec, update_class_vars: bool = False) -> Vec:
        """
        Compute the residual vector
        :param x: Solution vector
        :param update_class_vars: Update the class vars related to the calculation step
        :return: Residual vector
        """
        tm = [None] * 9

        tm[0] = time.time()
        nhvdc = self.nc.hvdc_data.nelm

        a = len(self.i_u_va)
        b = a + len(self.i_u_vm)
        c = b + len(self.u_vsc_pfp)
        d = c + len(self.u_vsc_pfn)
        e = d + len(self.u_vsc_pt)
        f = e + len(self.u_vsc_qt)
        g = f + nhvdc
        h = g + nhvdc
        i = h + nhvdc
        j = i + nhvdc
        k = j + len(self.u_cbr_m)
        l = k + len(self.u_cbr_tau)

        # copy the sliceable vectors
        Vm_ = self.Vm.copy()
        Va_ = self.Va.copy()
        Pfp_vsc_ = self.Pfp_vsc.copy()
        Pfn_vsc_ = self.Pfn_vsc.copy()
        Pt_vsc_ = self.Pt_vsc.copy()
        Qt_vsc_ = self.Qt_vsc.copy()

        # update the vectors
        Va_[self.i_u_va] = x[0:a]
        Vm_[self.i_u_vm] = x[a:b]
        Pfp_vsc_[self.u_vsc_pfp] = x[b:c]
        Pfn_vsc_[self.u_vsc_pfn] = x[c:d]
        Pt_vsc_[self.u_vsc_pt] = x[d:e]
        Qt_vsc_[self.u_vsc_qt] = x[e:f]
        Pf_hvdc_ = x[f:g]
        Pt_hvdc_ = x[g:h]
        Qf_hvdc_ = x[h:i]
        Qt_hvdc_ = x[i:j]
        m_ = x[j:k]
        tau_ = x[k:l]

        # Controllable branches ----------------------------------------------------------------------------------------
        tm[1] = time.time()

        m2 = self.nc.active_branch_data.tap_module.copy()
        if len(self.u_cbr_m) > 0:
            m2[self.u_cbr_m] = m_

        tau2 = self.nc.active_branch_data.tap_angle.copy()
        if len(self.u_cbr_tau) > 0:
            tau2[self.u_cbr_tau] = tau_

            # adm_ = compute_admittances_fast(
        #     nbus=self.nc.bus_data.nbus,
        #     R=self.nc.passive_branch_data.R,
        #     X=self.nc.passive_branch_data.X,
        #     G=self.nc.passive_branch_data.G,
        #     B=self.nc.passive_branch_data.B,
        #     tap_module=m2,
        #     vtap_f=self.nc.passive_branch_data.virtual_tap_f,
        #     vtap_t=self.nc.passive_branch_data.virtual_tap_t,
        #     tap_angle=tau2,
        #     F=self.nc.passive_branch_data.F,
        #     T=self.nc.passive_branch_data.T,
        #     Yshunt_bus=self.Yshunt_bus
        # )

        if len(self.u_cbr_m_tau) > 0:
            adm_ = self.adm.copy()
            adm_.modify_taps_fast(idx=self.u_cbr_m_tau,
                                  tap_module=m2[self.u_cbr_m_tau],
                                  tap_angle=tau2[self.u_cbr_m_tau])
        else:
            adm_ = self.adm  # there is no admittance change, hence we can just pick the existing adm

        Imax_vsc = self.nc.vsc_data.rates / self.nc.Sbase

        # Passive branches ---------------------------------------------------------------------------------------------
        tm[2] = time.time()

        V = polar_to_rect(Vm_, Va_)
        Sbus = compute_zip_power(self.S0, self.I0, self.Y0, Vm_)
        Scalc_passive = compute_power(adm_.Ybus, V)

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
        tm[3] = time.time()

        T_vsc = self.nc.vsc_data.T
        It = np.sqrt(Pt_vsc_ * Pt_vsc_ + Qt_vsc_ * Qt_vsc_) / Vm_[T_vsc]
        It2 = It * It
        PLoss_IEC = (self.nc.vsc_data.alpha3 * It2
                     + self.nc.vsc_data.alpha2 * It
                     + self.nc.vsc_data.alpha1)

        loss_vsc = PLoss_IEC - Pt_vsc_ - Pfp_vsc_ - Pfn_vsc_
        St_vsc = make_complex(Pt_vsc_, Qt_vsc_)

        # Add the 2nd equation per VSC
        balance_vsc = Pfp_vsc_ * Vm_[self.nc.vsc_data.F_dcn] + Pfn_vsc_ * Vm_[self.nc.vsc_data.F]

        # Add the 3rd equation per VSC
        current_vsc = It**2 - Imax_vsc**2

        # HVDC ---------------------------------------------------------------------------------------------------------
        tm[4] = time.time()

        Vmf_hvdc = Vm_[self.nc.hvdc_data.F]
        zbase = self.nc.hvdc_data.Vnf * self.nc.hvdc_data.Vnf / self.nc.Sbase
        Ploss_hvdc = self.nc.hvdc_data.r / zbase * np.power(Pf_hvdc_ / Vmf_hvdc, 2.0)
        loss_hvdc = Ploss_hvdc - Pf_hvdc_ - Pt_hvdc_

        Pinj_hvdc = self.nc.hvdc_data.Pset / self.nc.Sbase
        if len(self.hvdc_droop_idx):
            Vaf_hvdc = Vm_[self.nc.hvdc_data.F[self.hvdc_droop_idx]]
            Vat_hvdc = Vm_[self.nc.hvdc_data.T[self.hvdc_droop_idx]]
            Pinj_hvdc[self.hvdc_droop_idx] += self.nc.hvdc_data.angle_droop[self.hvdc_droop_idx] * (Vaf_hvdc - Vat_hvdc)
        inj_hvdc = Pf_hvdc_ - Pinj_hvdc

        Sf_hvdc = make_complex(Pf_hvdc_, Qf_hvdc_)
        St_hvdc = make_complex(Pt_hvdc_, Qt_hvdc_)

        # total nodal power --------------------------------------------------------------------------------------------
        tm[5] = time.time()

        Scalc_active = calc_flows_active_branch_per_bus(
            nbus=self.nc.bus_data.nbus,
            F_hvdc=self.nc.hvdc_data.F,
            T_hvdc=self.nc.hvdc_data.T,
            Sf_hvdc=Sf_hvdc,
            St_hvdc=St_hvdc,
            Fdcp_vsc=self.nc.vsc_data.F,
            Fdcn_vsc=self.nc.vsc_data.F_dcn,
            T_vsc=self.nc.vsc_data.T,
            Pfp_vsc=Pfp_vsc_,
            Pfn_vsc=Pfn_vsc_,
            St_vsc=St_vsc)
        Scalc_ = Scalc_active + Scalc_passive

        dS = Scalc_ - Sbus

        # compose the residuals vector ---------------------------------------------------------------------------------
        tm[6] = time.time()

        f_ = np.r_[
            dS[self.i_k_p].real,
            dS[self.i_k_q].imag,
            loss_vsc,
            balance_vsc,
            current_vsc[self.k_vsc_i],
            loss_hvdc,
            inj_hvdc,
            Pf_cbr - self.cbr_pf_set,
            Pt_cbr - self.cbr_pt_set,
            Qf_cbr - self.cbr_qf_set,
            Qt_cbr - self.cbr_qt_set
        ]

        tm[7] = time.time()
        for i in range(self.nc.nvsc):

            It_i = np.sqrt(self.Pt_vsc[i]**2 + self.Qt_vsc[i]**2) / self.Vm[self.nc.vsc_data.T[i]]
            Imax = self.nc.vsc_data.rates[i] / self.nc.Sbase  # Assume 1.0 p.u. base voltage

            # print(f"Compute f current: {It_i}, Imax: {Imax}")
            # print(f"Control 1: {self.nc.vsc_data.control1[i]}, Control 2: {self.nc.vsc_data.control2[i]}")
            # print('-------')

        if update_class_vars:
            self._Va = Va_
            self._Vm = Vm_
            self.Pfp_vsc = Pfp_vsc_
            self.Pfn_vsc = Pfn_vsc_
            self.Pt_vsc = Pt_vsc_
            self.Qt_vsc = Qt_vsc_
            self.Pf_hvdc = Pf_hvdc_
            self.Pt_hvdc = Pt_hvdc_
            self.Qf_hvdc = Qf_hvdc_
            self.Qt_hvdc = Qt_hvdc_
            self.m = m_
            self.tau = tau_
            self.Scalc = Scalc_
            self.adm = adm_
            self._f = f_

        return f_

    def check_error(self, x: Vec) -> Tuple[float, Vec]:
        """
        Check error of the solution without affecting the problem
        :param x: Solution vector
        :return: error
        """
        _res = self.compute_f(x, update_class_vars=False)
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
        self._f = self.compute_f(x, update_class_vars=True)

        self._error = compute_fx_error(self._f)

        # Update controls only below a certain error
        if update_controls and self._error < self._controls_tol:
            any_change = False
            branch_ctrl_change = False
            m_fixed_idx = list()
            tau_fixed_idx = list()

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
                changed, i_u_vm, i_k_q = control_q_for_generalized_method(self.Scalc, self.S0,
                                                                          pv, self.i_u_vm, self.i_k_q,
                                                                          self.Qmin, self.Qmax)

                if len(changed) > 0:
                    any_change = True

                    # update the bus type lists
                    self._update_Qlim_indices(i_u_vm=i_u_vm, i_k_q=i_k_q)

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

                for i, k in enumerate(self.u_cbr_m):

                    # m_taps = self.nc.passive_branch_data.m_taps[i]
                    m_taps = self.nc.passive_branch_data.m_taps[k]

                    if self.options.orthogonalize_controls and m_taps is not None:
                        _, self.m[i] = find_closest_number(arr=m_taps, target=float(self.m[i]))

                    if self.m[i] < self.nc.active_branch_data.tap_module_min[k]:
                        self.m[i] = self.nc.active_branch_data.tap_module_min[k]
                        m_fixed_idx.append(i)

                        # self.tap_module_control_mode[k] = TapModuleControl.fixed
                        self.nc.active_branch_data.tap_module_control_mode[k] = TapModuleControl.fixed
                        self.nc.active_branch_data.tap_module[k] = self.m[i]

                        branch_ctrl_change = True
                        self.logger.add_info("Min tap module reached",
                                             device=self.nc.passive_branch_data.names[k],
                                             value=self.m[i])

                    elif self.m[i] > self.nc.active_branch_data.tap_module_max[k]:
                        self.m[i] = self.nc.active_branch_data.tap_module_max[k]
                        m_fixed_idx.append(i)

                        # self.tap_module_control_mode[k] = TapModuleControl.fixed
                        self.nc.active_branch_data.tap_module_control_mode[k] = TapModuleControl.fixed
                        self.nc.active_branch_data.tap_module[k] = self.m[i]

                        branch_ctrl_change = True
                        self.logger.add_info("Max tap module reached",
                                             device=self.nc.passive_branch_data.names[k],
                                             value=self.m[i])

            # update the tap phase control
            if self.options.control_taps_phase:

                for i, k in enumerate(self.u_cbr_tau):

                    tau_taps = self.nc.passive_branch_data.tau_taps[k]

                    if self.options.orthogonalize_controls and tau_taps is not None:
                        _, self.tau[i] = find_closest_number(arr=tau_taps, target=self.tau[i])

                    if self.tau[i] < self.nc.active_branch_data.tap_angle_min[k]:
                        self.tau[i] = self.nc.active_branch_data.tap_angle_min[k]
                        tau_fixed_idx.append(i)

                        self.nc.active_branch_data.tap_phase_control_mode[k] = TapPhaseControl.fixed
                        self.nc.active_branch_data.tap_angle[k] = self.tau[i]

                        branch_ctrl_change = True
                        self.logger.add_info("Min tap phase reached",
                                             device=self.nc.passive_branch_data.names[k],
                                             value=self.tau[i])

                    elif self.tau[i] > self.nc.active_branch_data.tap_angle_max[k]:
                        self.tau[i] = self.nc.active_branch_data.tap_angle_max[k]
                        tau_fixed_idx.append(i)

                        self.nc.active_branch_data.tap_phase_control_mode[k] = TapPhaseControl.fixed
                        self.nc.active_branch_data.tap_angle[k] = self.tau[i]

                        branch_ctrl_change = True
                        self.logger.add_info("Max tap phase reached",
                                             device=self.nc.passive_branch_data.names[k],
                                             value=self.tau[i])

            if self.options.limit_i_vsc:
                """
                Limit the current through the VSCs
                Priority of magnitudes to remove from controlling: V, P, Q, theta
                When switching to current limiting, do not allow going back
                """

                for i in range(self.nc.nvsc):

                    It_i = np.sqrt(self.Pt_vsc[i]**2 + self.Qt_vsc[i]**2) / self.Vm[self.nc.vsc_data.T[i]]
                    Imax = self.nc.vsc_data.rates[i] / self.nc.Sbase  # Assume 1.0 p.u. base voltage

                    print(f"Josep current: {It_i}, Imax: {Imax}")

                    if (It_i > Imax
                        and self.nc.vsc_data.control1[i] != ConverterControlType.Imax
                        and self.nc.vsc_data.control2[i] != ConverterControlType.Imax):

                        self.logger.add_info("VSC current limit reached",
                                             device=self.nc.vsc_data.names[i],
                                             value=It_i)

                        if self.nc.vsc_data.control1[i] == ConverterControlType.Vm_ac:
                            self.nc.bus_data.is_vm_controlled[self.nc.vsc_data.T[i]] = False
                            self.nc.vsc_data.control1[i] = ConverterControlType.Imax
                            self.nc.vsc_data.control1_val[i] = Imax
                            self.nc.vsc_data.control1_branch_idx[i] = i
                            branch_ctrl_change = True
                        elif self.nc.vsc_data.control2[i] == ConverterControlType.Vm_ac:
                            self.nc.bus_data.is_vm_controlled[self.nc.vsc_data.T[i]] = False
                            self.nc.vsc_data.control2[i] = ConverterControlType.Imax
                            self.nc.vsc_data.control2_val[i] = Imax
                            self.nc.vsc_data.control2_branch_idx[i] = i
                            branch_ctrl_change = True
                        elif self.nc.vsc_data.control1[i] == ConverterControlType.Pdc:
                            self.nc.vsc_data.control1[i] = ConverterControlType.Imax
                            self.nc.vsc_data.control1_val[i] = Imax
                            self.nc.vsc_data.control1_branch_idx[i] = i
                            branch_ctrl_change = True
                        elif self.nc.vsc_data.control2[i] == ConverterControlType.Pdc:
                            self.nc.vsc_data.control2[i] = ConverterControlType.Imax
                            self.nc.vsc_data.control2_val[i] = Imax
                            self.nc.vsc_data.control2_branch_idx[i] = i
                            branch_ctrl_change = True
                        elif self.nc.vsc_data.control1[i] == ConverterControlType.Pac:
                            self.nc.vsc_data.control1[i] = ConverterControlType.Imax
                            self.nc.vsc_data.control1_val[i] = Imax
                            self.nc.vsc_data.control1_branch_idx[i] = i
                            branch_ctrl_change = True
                        elif self.nc.vsc_data.control2[i] == ConverterControlType.Pac:
                            self.nc.vsc_data.control2[i] = ConverterControlType.Imax
                            self.nc.vsc_data.control2_val[i] = Imax
                            self.nc.vsc_data.control2_branch_idx[i] = i
                            branch_ctrl_change = True
                        elif self.nc.vsc_data.control1[i] == ConverterControlType.Qac:
                            self.nc.vsc_data.control1[i] = ConverterControlType.Imax
                            self.nc.vsc_data.control1_val[i] = Imax
                            self.nc.vsc_data.control1_branch_idx[i] = i
                            branch_ctrl_change = True
                        elif self.nc.vsc_data.control2[i] == ConverterControlType.Qac:
                            self.nc.vsc_data.control2[i] = ConverterControlType.Imax
                            self.nc.vsc_data.control2_val[i] = Imax
                            self.nc.vsc_data.control2_branch_idx[i] = i
                            branch_ctrl_change = True
                        elif self.nc.vsc_data.control1[i] == ConverterControlType.Vm_dc:
                            self.nc.bus_data.is_vm_controlled[self.nc.vsc_data.F[i]] = False
                            self.nc.vsc_data.control1[i] = ConverterControlType.Imax
                            self.nc.vsc_data.control1_val[i] = Imax
                            self.nc.vsc_data.control1_branch_idx[i] = i
                            branch_ctrl_change = True
                        elif self.nc.vsc_data.control2[i] == ConverterControlType.Vm_dc:
                            self.nc.bus_data.is_vm_controlled[self.nc.vsc_data.F[i]] = False
                            self.nc.vsc_data.control2[i] = ConverterControlType.Imax
                            self.nc.vsc_data.control2_val[i] = Imax
                            self.nc.vsc_data.control2_branch_idx[i] = i
                            branch_ctrl_change = True
                        elif self.nc.vsc_data.control1[i] == ConverterControlType.Va_ac:
                            self.nc.bus_data.is_va_controlled[self.nc.vsc_data.T[i]] = False
                            self.nc.vsc_data.control1[i] = ConverterControlType.Imax
                            self.nc.vsc_data.control1_val[i] = Imax
                            self.nc.vsc_data.control1_branch_idx[i] = i
                            branch_ctrl_change = True
                        elif self.nc.vsc_data.control2[i] == ConverterControlType.Va_ac:
                            self.nc.bus_data.is_va_controlled[self.nc.vsc_data.T[i]] = False
                            self.nc.vsc_data.control2[i] = ConverterControlType.Imax
                            self.nc.vsc_data.control2_val[i] = Imax
                            self.nc.vsc_data.control2_branch_idx[i] = i
                            branch_ctrl_change = True
                        else:
                            raise ValueError(f"Unfound control type when switching to current limiting: "
                                             f"{self.nc.vsc_data.control1[i]}")

                        print(It_i, Imax)


                        # Potentially add new conditionals, mainly for the 2nd iteration once saturated
                        # If letting the P naturally go to zero is not enough, no longer control Vm
                        # Control Q and then it will naturally get to a point that does not surpass Imax

                    elif (It_i > Imax * 1.1
                        and self.nc.vsc_data.control1[i] == ConverterControlType.Imax
                        and self.nc.vsc_data.control2[i] == ConverterControlType.Imax):
                        """
                        We give some margin to the current because it may not exactly converge to Imax
                        in just one iteration. 10% buffer seems enough.
                        
                        We establish reactive power priority over active power
                        So if we are already controlling Imax, set the P to zero
                        As a last resort, set Q to zero
                        """

                        if self.nc.vsc_data.control1[i] == ConverterControlType.Pdc:
                            self.nc.vsc_data.control1_val[i] = 0.0
                        elif self.nc.vsc_data.control2[i] == ConverterControlType.Pdc:
                            self.nc.vsc_data.control2_val[i] = 0.0
                        elif self.nc.vsc_data.control1[i] == ConverterControlType.Pac:
                            self.nc.vsc_data.control1_val[i] = 0.0
                        elif self.nc.vsc_data.control2[i] == ConverterControlType.Pac:
                            self.nc.vsc_data.control2_val[i] = 0.0
                        elif self.nc.vsc_data.control1[i] == ConverterControlType.Qac:
                            self.nc.vsc_data.control1_val[i] = 0.0
                        elif self.nc.vsc_data.control2[i] == ConverterControlType.Qac:
                            self.nc.vsc_data.control2_val[i] = 0.0
                        else:
                            raise ValueError(f"Unfound control type when switching to current limiting: "
                                             f"{self.nc.vsc_data.control1[i]}")

                    print(f"VSC {i} control 1: {self.nc.vsc_data.control1[i]}")
                    print(f"VSC {i} control 2: {self.nc.vsc_data.control2[i]}")

            if branch_ctrl_change:

                if len(m_fixed_idx) > 0:
                    self.m = np.delete(self.m, m_fixed_idx)

                if len(tau_fixed_idx) > 0:
                    self.tau = np.delete(self.tau, tau_fixed_idx)

                self.bus_types = self.nc.bus_data.bus_types.copy()
                self.is_p_controlled = self.nc.bus_data.is_p_controlled.copy()
                self.is_q_controlled = self.nc.bus_data.is_q_controlled.copy()
                self.is_vm_controlled = self.nc.bus_data.is_vm_controlled.copy()
                self.is_va_controlled = self.nc.bus_data.is_va_controlled.copy()
                self._set_vsc_control_indices()
                self._set_branch_control_indices()
                self._set_bus_control_indices()

                # the composition of x may have changed, so recompute
                x = self.var2x()

            if any_change or branch_ctrl_change:
                # recompute the error based on the new Scalc and S0
                self._f = self.fx()

                # compute the error
                self._error = compute_fx_error(self._f)

        # converged?
        self._converged = self._error < self.options.tolerance

        if self.options.verbose > 1:
            print("Error:", self._error)

        return self._error, self._converged, x, self.f

    def fx(self) -> Vec:
        """
        Used when updating the controls
        :return:
        """

        V = polar_to_rect(self.Vm, self.Va)
        Sbus = compute_zip_power(self.S0, self.I0, self.Y0, self.Vm)
        Imax_vsc = self.nc.vsc_data.rates / self.nc.Sbase

        # Update Ybus with the new taps
        m2 = self.nc.active_branch_data.tap_module.copy()
        if len(self.u_cbr_m) > 0:
            m2[self.u_cbr_m] = self.m

        tau2 = self.nc.active_branch_data.tap_angle.copy()
        if len(self.u_cbr_tau) > 0:
            tau2[self.u_cbr_tau] = self.tau

        # self.adm = compute_admittances_fast(
        #     nbus=self.nc.bus_data.nbus,
        #     R=self.nc.passive_branch_data.R,
        #     X=self.nc.passive_branch_data.X,
        #     G=self.nc.passive_branch_data.G,
        #     B=self.nc.passive_branch_data.B,
        #     tap_module=m2,
        #     vtap_f=self.nc.passive_branch_data.virtual_tap_f,
        #     vtap_t=self.nc.passive_branch_data.virtual_tap_t,
        #     tap_angle=tau2,
        #     F=self.nc.passive_branch_data.F,
        #     T=self.nc.passive_branch_data.T,
        #     Yshunt_bus=self.Yshunt_bus,
        # )
        if len(self.u_cbr_m_tau) > 0:
            self.adm.modify_taps_fast(idx=self.u_cbr_m_tau,
                                      tap_module=m2[self.u_cbr_m_tau],
                                      tap_angle=tau2[self.u_cbr_m_tau])

        Scalc_passive = compute_power(self.adm.Ybus, V)

        # Controllable branches ----------------------------------------------------------------------------------------
        # Power at the controlled branches
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
        F = self.nc.vsc_data.F
        F_dcn = self.nc.vsc_data.F_dcn
        It = np.sqrt(self.Pt_vsc * self.Pt_vsc + self.Qt_vsc * self.Qt_vsc) / self.Vm[T_vsc]
        It2 = It * It
        PLoss_IEC = (self.nc.vsc_data.alpha3 * It2
                     + self.nc.vsc_data.alpha2 * It
                     + self.nc.vsc_data.alpha1)

        loss_vsc = PLoss_IEC - self.Pt_vsc - self.Pfp_vsc - self.Pfn_vsc
        balance_vsc = self.Pfp_vsc * self.Vm[F_dcn] + self.Pfn_vsc * self.Vm[F]

        current_vsc = It**2 - Imax_vsc**2

        St_vsc = make_complex(self.Pt_vsc, self.Qt_vsc)

        # HVDC ---------------------------------------------------------------------------------------------------------
        Vmf_hvdc = self.Vm[self.nc.hvdc_data.F]
        zbase = self.nc.hvdc_data.Vnf * self.nc.hvdc_data.Vnf / self.nc.Sbase
        Ploss_hvdc = self.nc.hvdc_data.r / zbase * np.power(self.Pf_hvdc / Vmf_hvdc, 2.0)
        dloss_hvdc = Ploss_hvdc - self.Pf_hvdc - self.Pt_hvdc

        Pinj_hvdc = self.nc.hvdc_data.Pset / self.nc.Sbase
        if len(self.hvdc_droop_idx):
            Vaf_hvdc = self.Vm[self.nc.hvdc_data.F[self.hvdc_droop_idx]]
            Vat_hvdc = self.Vm[self.nc.hvdc_data.T[self.hvdc_droop_idx]]
            Pinj_hvdc[self.hvdc_droop_idx] += self.nc.hvdc_data.angle_droop[self.hvdc_droop_idx] * (Vaf_hvdc - Vat_hvdc)
        dinj_hvdc = self.Pf_hvdc - Pinj_hvdc

        Sf_hvdc = make_complex(self.Pf_hvdc, self.Qf_hvdc)
        St_hvdc = make_complex(self.Pt_hvdc, self.Qt_hvdc)

        # total nodal power --------------------------------------------------------------------------------------------
        Scalc_active = calc_flows_active_branch_per_bus(
            nbus=self.nc.bus_data.nbus,
            F_hvdc=self.nc.hvdc_data.F,
            T_hvdc=self.nc.hvdc_data.T,
            Sf_hvdc=Sf_hvdc,
            St_hvdc=St_hvdc,
            Fdcp_vsc=F,
            Fdcn_vsc=F_dcn,
            T_vsc=T_vsc,
            Pfp_vsc=self.Pfp_vsc,
            Pfn_vsc=self.Pfn_vsc,
            St_vsc=St_vsc)

        self.Scalc = Scalc_active + Scalc_passive

        dS = self.Scalc - Sbus

        # compose the residuals vector ---------------------------------------------------------------------------------
        self._f = np.r_[
            dS[self.i_k_p].real,
            dS[self.i_k_q].imag,
            loss_vsc,
            balance_vsc,
            current_vsc[self.k_vsc_i],
            dloss_hvdc,
            dinj_hvdc,
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
                                       h=1e-7)

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

            assert isspmatrix_csc(self.adm.Ybus)

            J_sym = adv_jacobian(
                nbus=self.nc.nbus,
                nbr=self.nc.nbr,
                nvsc=self.nc.vsc_data.nelm,
                nhvdc=nhvdc,
                F=self.nc.passive_branch_data.F,
                T=self.nc.passive_branch_data.T,
                Fdcp_vsc=self.nc.vsc_data.F,
                Fdcn_vsc=self.nc.vsc_data.F_dcn,
                T_vsc=self.nc.vsc_data.T,
                F_hvdc=self.nc.hvdc_data.F,
                T_hvdc=self.nc.hvdc_data.T,

                tap_angles=tap_angles,
                tap_modules=tap_modules,

                V=self.V,
                Vm=self.Vm,
                Va=self.Va,

                # Controllable Branch Indices
                u_cbr_m=self.u_cbr_m,
                u_cbr_tau=self.u_cbr_tau,

                k_cbr_pf=self.k_cbr_pf,
                k_cbr_pt=self.k_cbr_pt,
                k_cbr_qf=self.k_cbr_qf,
                k_cbr_qt=self.k_cbr_qt,

                # VSC Indices
                u_vsc_pfp=self.u_vsc_pfp,
                u_vsc_pfn=self.u_vsc_pfn,
                u_vsc_pt=self.u_vsc_pt,
                u_vsc_qt=self.u_vsc_qt,

                k_vsc_imax=self.k_vsc_i,

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
                Pfp_vsc=self.Pfp_vsc,
                Pfn_vsc=self.Pfn_vsc,
                Pt_vsc=self.Pt_vsc,
                Qt_vsc=self.Qt_vsc,
                Pf_hvdc=self.Pf_hvdc,

                # Admittances and Connections
                Ys=self.adm.ys,
                Bc=self.nc.passive_branch_data.B,

                yff_cbr=self.adm.yff,
                yft_cbr=self.adm.yft,
                ytf_cbr=self.adm.ytf,
                ytt_cbr=self.adm.ytt,

                Yi=self.adm.Ybus.indices,
                Yp=self.adm.Ybus.indptr,
                Yx=self.adm.Ybus.data
            )

            return J_sym

    def get_x_names(self) -> List[str]:
        """
        Names matching x
        :return:
        """
        cols = [f'dVa_{i}' for i in self.i_u_va]
        cols += [f'dVm_{i}' for i in self.i_u_vm]

        cols += [f'dPfp_vsc_{i}' for i in self.u_vsc_pfp]
        cols += [f'dPfn_vsc_{i}' for i in self.u_vsc_pfn]
        cols += [f'dPt_vsc_{i}' for i in self.u_vsc_pt]
        cols += [f'dQt_vsc_{i}' for i in self.u_vsc_qt]

        cols += [f'dPf_hvdc_{i}' for i in range(self.nc.hvdc_data.nelm)]
        cols += [f'dPt_hvdc_{i}' for i in range(self.nc.hvdc_data.nelm)]
        cols += [f'dQf_hvdc_{i}' for i in range(self.nc.hvdc_data.nelm)]
        cols += [f'dQt_hvdc_{i}' for i in range(self.nc.hvdc_data.nelm)]

        cols += [f'dm_{i}' for i in self.u_cbr_m]
        cols += [f'dtau_{i}' for i in self.u_cbr_tau]

        return cols

    def get_fx_names(self) -> List[str]:
        """
        Names matching fx
        :return:
        """

        rows = [f'dP_{i}' for i in self.i_k_p]
        rows += [f'dQ_{i}' for i in self.i_k_q]
        rows += [f'dloss_vsc_{i}' for i in range(self.nc.vsc_data.nelm)]
        rows += [f'dloss_hvdc_{i}' for i in range(self.nc.hvdc_data.nelm)]
        rows += [f'dinj_hvdc_{i}' for i in range(self.nc.hvdc_data.nelm)]

        rows += [f'dPf_{i}' for i in self.k_cbr_pf]
        rows += [f'dPt_{i}' for i in self.k_cbr_pt]
        rows += [f'dQf_{i}' for i in self.k_cbr_qf]
        rows += [f'dQt_{i}' for i in self.k_cbr_qt]

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

        Vf = self.V[self.nc.passive_branch_data.F]
        Vt = self.V[self.nc.passive_branch_data.T]

        If = Vf * self.adm.yff + Vt * self.adm.yft
        It = Vt * self.adm.ytt + Vf * self.adm.ytf
        Sf = Vf * np.conj(If) * self.nc.Sbase
        St = Vt * np.conj(It) * self.nc.Sbase

        # Branch losses in MVA
        losses = (Sf + St)

        # Branch loading in p.u.
        loading = Sf / (self.nc.passive_branch_data.rates + 1e-9)

        # VSC ----------------------------------------------------------------------------------------------------------
        Pf_vsc = self.Pfp_vsc * self.nc.Sbase
        St_vsc = make_complex(self.Pt_vsc, self.Qt_vsc) * self.nc.Sbase
        If_vsc = self.Pfp_vsc / self.Vm[self.nc.vsc_data.F]
        It_vsc = St_vsc / self.Vm[self.nc.vsc_data.T]
        loading_vsc = np.abs(St_vsc) / (self.nc.vsc_data.rates + 1e-20)
        losses_vsc = (self.Pt_vsc + self.Pfp_vsc + self.Pfn_vsc) * self.nc.Sbase
        # losses_vsc = Pf_vsc + St_vsc.real

        # HVDC ---------------------------------------------------------------------------------------------------------
        Sf_hvdc = make_complex(self.Pf_hvdc, self.Qf_hvdc) * self.nc.Sbase
        St_hvdc = make_complex(self.Pt_hvdc, self.Qt_hvdc) * self.nc.Sbase
        loading_hvdc = Sf_hvdc.real / (self.nc.hvdc_data.rates + 1e-20)
        losses_hvdc = Sf_hvdc + Sf_hvdc

        # Basic bus powers
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
            Fdcp_vsc=self.nc.vsc_data.F,
            Fdcn_vsc=self.nc.vsc_data.F_dcn,
            T_vsc=self.nc.vsc_data.T,
            Pfp_vsc=self.Pfp_vsc,
            Pfn_vsc=self.Pfn_vsc,
            St_vsc=St_vsc
        )

        m2 = self.nc.active_branch_data.tap_module.copy()
        tau2 = self.nc.active_branch_data.tap_angle.copy()
        m2[self.u_cbr_m] = self.m
        tau2[self.u_cbr_tau] = self.tau

        return NumericPowerFlowResults(
            V=self.V,
            Scalc=Sbus,
            m=m2,
            tau=tau2,
            Sf=Sf,
            St=St,
            If=If,
            It=It,
            loading=loading,
            losses=losses,
            Pf_vsc=Pf_vsc,
            St_vsc=St_vsc,
            If_vsc=If_vsc,
            It_vsc=It_vsc,
            losses_vsc=losses_vsc,
            loading_vsc=loading_vsc,
            Sf_hvdc=Sf_hvdc,
            St_hvdc=St_hvdc,
            losses_hvdc=losses_hvdc,
            loading_hvdc=loading_hvdc,
            norm_f=self.error,
            converged=self.converged,
            iterations=iterations,
            elapsed=elapsed
        )
