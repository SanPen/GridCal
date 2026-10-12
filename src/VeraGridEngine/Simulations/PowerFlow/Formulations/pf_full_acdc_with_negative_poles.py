# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import time
from typing import Tuple, List, Dict, Callable, Union
import numpy as np
from numba import njit
from scipy.sparse import csc_matrix, isspmatrix_csc
from VeraGridEngine.Topology.admittance_matrices import compute_admittances_fast
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from VeraGridEngine.DataStructures.numerical_circuit import NumericalCircuit
import VeraGridEngine.Simulations.Derivatives.csc_derivatives as deriv
from VeraGridEngine.Simulations.Derivatives.csc_derivatives import dSbus_dV_with_I0_numba_sparse_csc
from VeraGridEngine.Utils.NumericalMethods.common import find_closest_number, make_complex
from VeraGridEngine.Utils.Sparse.csc2 import (CSC, CxCSC, mat_to_scipy, scipy_to_mat, sp_slice, csc_stack_2d_ff)
from VeraGridEngine.Simulations.PowerFlow.NumericalMethods.discrete_controls import (control_q_for_generalized_method,
                                                                                     DiscreteShuntControlState,
                                                                                     QvDroopControlState,
                                                                                     compute_slack_distribution)
from VeraGridEngine.Simulations.PowerFlow.NumericalMethods.common_functions import expand
from VeraGridEngine.Simulations.PowerFlow.NumericalMethods.static_generator_droop import StaticGeneratorDroop
from VeraGridEngine.Simulations.PowerFlow.NumericalMethods.common_functions import compute_fx_error
from VeraGridEngine.Simulations.PowerFlow.Formulations.pf_formulation_template import PfFormulationTemplate
from VeraGridEngine.Simulations.PowerFlow.NumericalMethods.common_functions import (compute_zip_power, compute_power,
                                                                                    compute_current,
                                                                                    polar_to_rect, voltage_q_droop,
                                                                                    voltage_pdc_droop,
                                                                                    asynchronous_gen_q,
                                                                                    voltage_pdc_droop_neg,
                                                                                    compute_asynchronous_generator_q_per_bus)
from VeraGridEngine.enumerations import (TapPhaseControl, TapModuleControl, HvdcControlType, ConverterControlType,
                                         ShuntControlMode, GeneratorType)
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
                 I0: CxVec,
                 u_cbr_m: IntVec,
                 u_cbr_tau: IntVec,
                 k_cbr_pf: IntVec,
                 k_cbr_pt: IntVec,
                 k_cbr_qf: IntVec,
                 k_cbr_qt: IntVec,
                 u_vsc_ifp: IntVec,
                 u_vsc_pt: IntVec,
                 u_vsc_qt: IntVec,
                 k_vsc_imax: IntVec,
                 alpha2: Vec,
                 alpha3: Vec,
                 hvdc_r: Vec,
                 hvdc_droop: Vec,
                 i_u_vm: IntVec,
                 i_u_va: IntVec,
                 i_k_p: IntVec,
                 i_k_q: IntVec,
                 Ifp_vsc: Vec,
                 Udc_vsc: Vec,
                 k_vsc_pfp_droop: IntVec,
                 droop_factor: Vec,
                 k_vsc_pdc: IntVec,
                 pdc_factor: Vec,
                 k_vsc_vmdc_diff: IntVec,
                 dc_rows: IntVec,
                 Vdc_bus: Vec,
                 S0r: Vec,
                 Y0r: Vec,
                 Pt_vsc: Vec,
                 Qt_vsc: Vec,
                 Pf_hvdc: Vec,
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
    Analytic Jacobian of the AC/DC formulation
    Rows as in compute_f:
        P (AC buses), Q, loss_vsc, Imax_vsc, droop_vsc, pdc_vsc, vmdc_diff,
        dI_dc, loss_hvdc, inj_hvdc, Pf_cbr, Pt_cbr, Qf_cbr, Qt_cbr
    Columns as in x2var:
        Va, Vm, Ifp_vsc, Pt_vsc, Qt_vsc, Pf_hvdc, Pt_hvdc, Qf_hvdc, Qt_hvdc, m, tau
    :param nbus: number of buses
    :param nbr: number of passive branches
    :param nvsc: number of VSCs
    :param nhvdc: number of HVDC lines
    :param F: passive branch from-bus indices
    :param T: passive branch to-bus indices
    :param Fdcp_vsc: VSC positive pole bus indices
    :param Fdcn_vsc: VSC negative pole bus indices (-1 if not there)
    :param T_vsc: VSC AC bus indices
    :param F_hvdc: HVDC from-bus indices
    :param T_hvdc: HVDC to-bus indices
    :param tap_angles: branch tap angles (expanded)
    :param tap_modules: branch tap modules (expanded)
    :param V: complex bus voltages
    :param Vm: voltage magnitudes
    :param Va: voltage angles
    :param I0: current injections vector
    :param u_cbr_m: branches with unknown tap module
    :param u_cbr_tau: branches with unknown tap angle
    :param k_cbr_pf: branches with Pf controlled
    :param k_cbr_pt: branches with Pt controlled
    :param k_cbr_qf: branches with Qf controlled
    :param k_cbr_qt: branches with Qt controlled
    :param u_vsc_ifp: VSCs whose positive pole current is unknown
    :param u_vsc_pt: VSCs whose Pt is unknown
    :param u_vsc_qt: VSCs whose Qt is unknown
    :param k_vsc_imax: VSCs working at maximum current
    :param alpha2: VSC linear loss coefficients
    :param alpha3: VSC quadratic loss coefficients
    :param hvdc_r: HVDC resistances [pu]
    :param hvdc_droop: HVDC droop gains
    :param i_u_vm: buses with unknown Vm
    :param i_u_va: buses with unknown Va
    :param i_k_p: buses with P balance (AC only)
    :param i_k_q: buses with Q balance (of course AC only)
    :param Ifp_vsc: VSC positive pole currents
    :param Udc_vsc: signed pole-to-return DC voltage per VSC
    :param k_vsc_pfp_droop: droop-controlled VSC indices
    :param droop_factor: voltage sensitivity factor per droop equation
    :param k_vsc_pdc: fixed-Pdc VSC indices
    :param pdc_factor: voltage sensitivity factor per Pdc equation (Ifp)
    :param k_vsc_vmdc_diff: bipolar Vm_dc pole-to-pole VSC indices
    :param dc_rows: non-grounded DC bus indices
    :param Vdc_bus: signed DC voltage per bus (Vm * cos(Va))
    :param S0r: real part of the base power injections per bus [pu]
    :param Y0r: real part of the base admittance injections per bus [pu]
    :param Pt_vsc: VSC AC active powers
    :param Qt_vsc: VSC AC reactive powers
    :param Pf_hvdc: HVDC from-side active powers
    :param Ys: branch series admittances
    :param Bc: branch parallel susceptances
    :param yff_cbr: branch yff primitives
    :param yft_cbr: branch yft primitives
    :param ytf_cbr: branch ytf primitives
    :param ytt_cbr: branch ytt primitives
    :param Yi: Ybus CSC row indices
    :param Yp: Ybus CSC column pointers
    :param Yx: Ybus CSC values
    :return: Jacobian in CSC format
    """
    tap = polar_to_rect(tap_modules, tap_angles)

    nvm = len(i_u_vm)
    nva = len(i_u_va)
    nifp = len(u_vsc_ifp)
    npt = len(u_vsc_pt)
    nqt = len(u_vsc_qt)
    nm = len(u_cbr_m)
    ntau = len(u_cbr_tau)
    n_droop = len(k_vsc_pfp_droop)
    n_pdc = len(k_vsc_pdc)
    n_vmdc = len(k_vsc_vmdc_diff)
    n_idc = len(dc_rows)
    nimax = len(k_vsc_imax)
    hvdc_range = np.arange(nhvdc)

    # -------- ROW 1 + ROW 2 (Sbus): bus-bus derivatives (including I0 Norton current) --------
    dSy_dVm_x, dSy_dVa_x = dSbus_dV_with_I0_numba_sparse_csc(Yx, Yp, Yi, V, Vm, I0)

    dS_dVm = CxCSC(nbus, nbus, len(dSy_dVm_x), False).set(Yi, Yp, dSy_dVm_x)
    dS_dVa = CxCSC(nbus, nbus, len(dSy_dVa_x), False).set(Yi, Yp, dSy_dVa_x)

    nkp = len(i_k_p)
    nkq = len(i_k_q)
    npq_f = len(k_cbr_pf)
    npq_t = len(k_cbr_pt)
    nqq_f = len(k_cbr_qf)
    nqq_t = len(k_cbr_qt)

    # -------- ROW 1 (P, AC buses only) --------
    dP_dVa = sp_slice(dS_dVa.real, i_k_p, i_u_va)
    dP_dVm = sp_slice(dS_dVm.real, i_k_p, i_u_vm)
    dP_dIfpvsc = CSC(nkp, nifp, 0, False)  # fully empty
    dP_dPtvsc = deriv.dPQ_dPQft_csc(nbus, nvsc, i_k_p, u_vsc_pt, T_vsc)
    dP_dQtvsc = CSC(nkp, nqt, 0, False)  # fully empty
    dP_dPfhvdc = deriv.dPQ_dPQft_csc(nbus, nhvdc, i_k_p, hvdc_range, F_hvdc)
    dP_dPthvdc = deriv.dPQ_dPQft_csc(nbus, nhvdc, i_k_p, hvdc_range, T_hvdc)
    dP_dQfhvdc = CSC(nkp, nhvdc, 0, False)  # fully empty
    dP_dQthvdc = CSC(nkp, nhvdc, 0, False)  # fully empty
    dP_dm = deriv.dSbus_dm_csc(nbus, i_k_p, u_cbr_m, F, T, Ys, Bc, tap, tap_modules, V).real
    dP_dtau = deriv.dSbus_dtau_csc(nbus, i_k_p, u_cbr_tau, F, T, Ys, tap, V).real

    # -------- ROW 2 (Q) --------
    dQ_dVa = sp_slice(dS_dVa.imag, i_k_q, i_u_va)
    dQ_dVm = sp_slice(dS_dVm.imag, i_k_q, i_u_vm)
    dQ_dIfpvsc = CSC(nkq, nifp, 0, False)  # fully empty
    dQ_dPtvsc = CSC(nkq, npt, 0, False)  # fully empty
    dQ_dQtvsc = deriv.dPQ_dPQft_csc(nbus, nvsc, i_k_q, u_vsc_qt, T_vsc)
    dQ_dPfhvdc = CSC(nkq, nhvdc, 0, False)  # fully empty
    dQ_dPthvdc = CSC(nkq, nhvdc, 0, False)  # fully empty
    dQ_dQfhvdc = deriv.dPQ_dPQft_csc(nbus, nhvdc, i_k_q, hvdc_range, F_hvdc)
    dQ_dQthvdc = deriv.dPQ_dPQft_csc(nbus, nhvdc, i_k_q, hvdc_range, T_hvdc)
    dQ_dm = deriv.dSbus_dm_csc(nbus, i_k_q, u_cbr_m, F, T, Ys, Bc, tap, tap_modules, V).imag
    dQ_dtau = deriv.dSbus_dtau_csc(nbus, i_k_q, u_cbr_tau, F, T, Ys, tap, V).imag

    # -------- ROW 3 (Losses VSCs) --------
    dLvsc_dVa = CSC(nvsc, nva, 0, False)  # fully empty
    dLvsc_dVm = deriv.dLossvsc_dVm_curr_csc(nvsc, nbus, i_u_vm, alpha2, alpha3, Vm, Pt_vsc, Qt_vsc,
                                            T_vsc, Ifp_vsc, Va, Fdcp_vsc, Fdcn_vsc)
    dLvsc_dIfpvsc = deriv.dLossvsc_dIfp_csc(nvsc, u_vsc_ifp, Udc_vsc)
    dLvsc_dPtvsc = deriv.dLossvsc_dPtvsc_csc(nvsc, u_vsc_pt, alpha2, alpha3, Vm, Pt_vsc, Qt_vsc, T_vsc)
    dLvsc_dQtvsc = deriv.dLossvsc_dQtvsc_csc(nvsc, u_vsc_qt, alpha2, alpha3, Vm, Pt_vsc, Qt_vsc, T_vsc)
    dLvsc_dPfhvdc = CSC(nvsc, nhvdc, 0, False)  # fully empty
    dLvsc_dPthvdc = CSC(nvsc, nhvdc, 0, False)  # fully empty
    dLvsc_dQfhvdc = CSC(nvsc, nhvdc, 0, False)  # fully empty
    dLvsc_dQthvdc = CSC(nvsc, nhvdc, 0, False)  # fully empty
    dLvsc_dm = CSC(nvsc, nm, 0, False)  # fully empty
    dLvsc_dtau = CSC(nvsc, ntau, 0, False)  # fully empty

    # -------- ROW 4 (max current VSCs) --------
    dImax_dVa = CSC(nimax, nva, 0, False)  # fully empty
    dImax_dVm = deriv.dImaxvsc_dVm_csc(nbus, k_vsc_imax, i_u_vm, Pt_vsc, Qt_vsc, Vm, T_vsc)
    dImax_dIfpvsc = CSC(nimax, nifp, 0, False)  # fully empty
    dImax_dPtvsc = deriv.dImaxvsc_dPQ_csc(nvsc, k_vsc_imax, u_vsc_pt, Pt_vsc, Vm, T_vsc)
    dImax_dQtvsc = deriv.dImaxvsc_dPQ_csc(nvsc, k_vsc_imax, u_vsc_qt, Qt_vsc, Vm, T_vsc)
    dImax_dPfhvdc = CSC(nimax, nhvdc, 0, False)  # fully empty
    dImax_dPthvdc = CSC(nimax, nhvdc, 0, False)  # fully empty
    dImax_dQfhvdc = CSC(nimax, nhvdc, 0, False)  # fully empty
    dImax_dQthvdc = CSC(nimax, nhvdc, 0, False)  # fully empty
    dImax_dm = CSC(nimax, nm, 0, False)  # fully empty
    dImax_dtau = CSC(nimax, ntau, 0, False)  # fully empty

    # -------- ROW 5 (Pdc voltage-droop equations: Udc * Ifp - droop(u) = 0) --------
    dDroop_dVa = CSC(n_droop, nva, 0, False)  # fully empty
    dDroop_dVm = deriv.dUdcIfp_dVm_csc(n_droop, nbus, i_u_vm, k_vsc_pfp_droop, droop_factor,
                                       Va, Fdcp_vsc, Fdcn_vsc)
    dDroop_dIfpvsc = deriv.dUdcIfp_dIfp_csc(n_droop, nvsc, k_vsc_pfp_droop, u_vsc_ifp, Udc_vsc)
    dDroop_dPtvsc = CSC(n_droop, npt, 0, False)  # fully empty
    dDroop_dQtvsc = CSC(n_droop, nqt, 0, False)  # fully empty
    dDroop_dPfhvdc = CSC(n_droop, nhvdc, 0, False)  # fully empty
    dDroop_dPthvdc = CSC(n_droop, nhvdc, 0, False)  # fully empty
    dDroop_dQfhvdc = CSC(n_droop, nhvdc, 0, False)  # fully empty
    dDroop_dQthvdc = CSC(n_droop, nhvdc, 0, False)  # fully empty
    dDroop_dm = CSC(n_droop, nm, 0, False)  # fully empty
    dDroop_dtau = CSC(n_droop, ntau, 0, False)  # fully empty

    # -------- ROW 6 (fixed Pdc equations: Udc * Ifp - Pdc_set = 0) --------
    dPdc_dVa = CSC(n_pdc, nva, 0, False)  # fully empty (DC bus angles are not unknowns)
    dPdc_dVm = deriv.dUdcIfp_dVm_csc(n_pdc, nbus, i_u_vm, k_vsc_pdc, pdc_factor,
                                     Va, Fdcp_vsc, Fdcn_vsc)
    dPdc_dIfpvsc = deriv.dUdcIfp_dIfp_csc(n_pdc, nvsc, k_vsc_pdc, u_vsc_ifp, Udc_vsc)
    dPdc_dPtvsc = CSC(n_pdc, npt, 0, False)  # fully empty
    dPdc_dQtvsc = CSC(n_pdc, nqt, 0, False)  # fully empty
    dPdc_dPfhvdc = CSC(n_pdc, nhvdc, 0, False)  # fully empty
    dPdc_dPthvdc = CSC(n_pdc, nhvdc, 0, False)  # fully empty
    dPdc_dQfhvdc = CSC(n_pdc, nhvdc, 0, False)  # fully empty
    dPdc_dQthvdc = CSC(n_pdc, nhvdc, 0, False)  # fully empty
    dPdc_dm = CSC(n_pdc, nm, 0, False)  # fully empty
    dPdc_dtau = CSC(n_pdc, ntau, 0, False)  # fully empty

    # -------- ROW 7 (bipolar Vm_dc pole-to-pole: (V[F].real - V[F_dcn].real) - Udc_set = 0) --------
    dVmdcDiff_dVa = CSC(n_vmdc, nva, 0, False)  # fully empty (DC bus angles are not unknowns)
    dVmdcDiff_dVm = deriv.dVmdcDiff_dVm_csc(n_vmdc, nbus, i_u_vm, k_vsc_vmdc_diff, Fdcp_vsc, Fdcn_vsc, Va)
    dVmdcDiff_dIfpvsc = CSC(n_vmdc, nifp, 0, False)  # fully empty
    dVmdcDiff_dPtvsc = CSC(n_vmdc, npt, 0, False)  # fully empty
    dVmdcDiff_dQtvsc = CSC(n_vmdc, nqt, 0, False)  # fully empty
    dVmdcDiff_dPfhvdc = CSC(n_vmdc, nhvdc, 0, False)  # fully empty
    dVmdcDiff_dPthvdc = CSC(n_vmdc, nhvdc, 0, False)  # fully empty
    dVmdcDiff_dQfhvdc = CSC(n_vmdc, nhvdc, 0, False)  # fully empty
    dVmdcDiff_dQthvdc = CSC(n_vmdc, nhvdc, 0, False)  # fully empty
    dVmdcDiff_dm = CSC(n_vmdc, nm, 0, False)  # fully empty
    dVmdcDiff_dtau = CSC(n_vmdc, ntau, 0, False)  # fully empty

    # -------- ROW 8 (DC bus current balance, replaces the DC power balance) --------
    dIdc_dVa = CSC(n_idc, nva, 0, False)  # fully empty (DC bus angles are not unknowns)
    dIdc_dVm = deriv.dIdc_dVm_csc(nbus, i_u_vm, dc_rows, Yp, Yi, Yx, Va, Vdc_bus, S0r, Y0r)
    dIdc_dIfpvsc = deriv.dIdc_dIfp_csc(nbus, dc_rows, u_vsc_ifp, Fdcp_vsc, Fdcn_vsc)
    dIdc_dPtvsc = CSC(n_idc, npt, 0, False)  # fully empty
    dIdc_dQtvsc = CSC(n_idc, nqt, 0, False)  # fully empty
    dIdc_dPfhvdc = CSC(n_idc, nhvdc, 0, False)  # fully empty
    dIdc_dPthvdc = CSC(n_idc, nhvdc, 0, False)  # fully empty
    dIdc_dQfhvdc = CSC(n_idc, nhvdc, 0, False)  # fully empty
    dIdc_dQthvdc = CSC(n_idc, nhvdc, 0, False)  # fully empty
    dIdc_dm = CSC(n_idc, nm, 0, False)  # fully empty
    dIdc_dtau = CSC(n_idc, ntau, 0, False)  # fully empty

    # -------- ROW 9 (loss HVDCs) --------
    dLhvdc_dVa = CSC(nhvdc, nva, 0, False)  # fully empty
    dLhvdc_dVm = deriv.dLosshvdc_dVm_csc(nhvdc, nbus, i_u_vm, Vm, Pf_hvdc, hvdc_r, F_hvdc)
    dLhvdc_dIfpvsc = CSC(nhvdc, nifp, 0, False)  # fully empty
    dLhvdc_dPtvsc = CSC(nhvdc, npt, 0, False)  # fully empty
    dLhvdc_dQtvsc = CSC(nhvdc, nqt, 0, False)  # fully empty
    dLhvdc_dPfhvdc = deriv.dLosshvdc_dPfhvdc_csc(nhvdc, Vm, hvdc_r, F_hvdc)
    dLhvdc_dPthvdc = deriv.dLosshvdc_dPthvdc_csc(nhvdc)
    dLhvdc_dQfhvdc = CSC(nhvdc, nhvdc, 0, False)  # fully empty
    dLhvdc_dQthvdc = CSC(nhvdc, nhvdc, 0, False)  # fully empty
    dLhvdc_dm = CSC(nhvdc, nm, 0, False)  # fully empty
    dLhvdc_dtau = CSC(nhvdc, ntau, 0, False)  # fully empty

    # -------- ROW 10 (inj HVDCs) --------
    dInjhvdc_dVa = CSC(nhvdc, nva, 0, False)  # fully empty
    # the residual droop term uses Vm (see compute_f), so the block lives in the Vm columns
    dInjhvdc_dVm = deriv.dInjhvdc_dVa_csc(nhvdc, nbus, i_u_vm, hvdc_droop, F_hvdc, T_hvdc)
    dInjhvdc_dIfpvsc = CSC(nhvdc, nifp, 0, False)  # fully empty
    dInjhvdc_dPtvsc = CSC(nhvdc, npt, 0, False)  # fully empty
    dInjhvdc_dQtvsc = CSC(nhvdc, nqt, 0, False)  # fully empty
    dInjhvdc_dPfhvdc = deriv.dInjhvdc_dPfhvdc_csc(nhvdc)
    dInjhvdc_dPthvdc = CSC(nhvdc, nhvdc, 0, False)  # fully empty
    dInjhvdc_dQfhvdc = CSC(nhvdc, nhvdc, 0, False)  # fully empty
    dInjhvdc_dQthvdc = CSC(nhvdc, nhvdc, 0, False)  # fully empty
    dInjhvdc_dm = CSC(nhvdc, nm, 0, False)  # fully empty
    dInjhvdc_dtau = CSC(nhvdc, ntau, 0, False)  # fully empty

    # -------- ROW 11 (Pf) --------
    dPf_dVa = deriv.dSf_dVa_csc(nbus, k_cbr_pf, i_u_va, yft_cbr, V, F, T).real
    dPf_dVm = deriv.dSf_dVm_csc(nbus, k_cbr_pf, i_u_vm, yff_cbr, yft_cbr, Vm, Va, F, T).real
    dPf_dIfpvsc = CSC(npq_f, nifp, 0, False)  # fully empty
    dPf_dPtvsc = CSC(npq_f, npt, 0, False)  # fully empty
    dPf_dQtvsc = CSC(npq_f, nqt, 0, False)  # fully empty
    dPf_dPfhvdc = CSC(npq_f, nhvdc, 0, False)  # fully empty
    dPf_dPthvdc = CSC(npq_f, nhvdc, 0, False)  # fully empty
    dPf_dQfhvdc = CSC(npq_f, nhvdc, 0, False)  # fully empty
    dPf_dQthvdc = CSC(npq_f, nhvdc, 0, False)  # fully empty
    dPf_dm = deriv.dSf_dm_csc(nbr, k_cbr_pf, u_cbr_m, F, T, Ys, Bc, tap, tap_modules, V).real
    dPf_dtau = deriv.dSf_dtau_csc(nbr, k_cbr_pf, u_cbr_tau, F, T, Ys, tap, V).real

    # -------- ROW 12 (Pt) --------
    dPt_dVa = deriv.dSt_dVa_csc(nbus, k_cbr_pt, i_u_va, ytf_cbr, V, F, T).real
    dPt_dVm = deriv.dSt_dVm_csc(nbus, k_cbr_pt, i_u_vm, ytt_cbr, ytf_cbr, Vm, Va, F, T).real
    dPt_dIfpvsc = CSC(npq_t, nifp, 0, False)  # fully empty
    dPt_dPtvsc = CSC(npq_t, npt, 0, False)  # fully empty
    dPt_dQtvsc = CSC(npq_t, nqt, 0, False)  # fully empty
    dPt_dPfhvdc = CSC(npq_t, nhvdc, 0, False)  # fully empty
    dPt_dPthvdc = CSC(npq_t, nhvdc, 0, False)  # fully empty
    dPt_dQfhvdc = CSC(npq_t, nhvdc, 0, False)  # fully empty
    dPt_dQthvdc = CSC(npq_t, nhvdc, 0, False)  # fully empty
    dPt_dm = deriv.dSt_dm_csc(nbr, k_cbr_pt, u_cbr_m, F, T, Ys, tap, tap_modules, V).real
    dPt_dtau = deriv.dSt_dtau_csc(nbr, k_cbr_pt, u_cbr_tau, F, T, Ys, tap, V).real

    # -------- ROW 13 (Qf) --------
    dQf_dVa = deriv.dSf_dVa_csc(nbus, k_cbr_qf, i_u_va, yft_cbr, V, F, T).imag
    dQf_dVm = deriv.dSf_dVm_csc(nbus, k_cbr_qf, i_u_vm, yff_cbr, yft_cbr, Vm, Va, F, T).imag
    dQf_dIfpvsc = CSC(nqq_f, nifp, 0, False)  # fully empty
    dQf_dPtvsc = CSC(nqq_f, npt, 0, False)  # fully empty
    dQf_dQtvsc = CSC(nqq_f, nqt, 0, False)  # fully empty
    dQf_dPfhvdc = CSC(nqq_f, nhvdc, 0, False)  # fully empty
    dQf_dPthvdc = CSC(nqq_f, nhvdc, 0, False)  # fully empty
    dQf_dQfhvdc = CSC(nqq_f, nhvdc, 0, False)  # fully empty
    dQf_dQthvdc = CSC(nqq_f, nhvdc, 0, False)  # fully empty
    dQf_dm = deriv.dSf_dm_csc(nbr, k_cbr_qf, u_cbr_m, F, T, Ys, Bc, tap, tap_modules, V).imag
    dQf_dtau = deriv.dSf_dtau_csc(nbr, k_cbr_qf, u_cbr_tau, F, T, Ys, tap, V).imag

    # -------- ROW 14 (Qt) --------
    dQt_dVa = deriv.dSt_dVa_csc(nbus, k_cbr_qt, i_u_va, ytf_cbr, V, F, T).imag
    dQt_dVm = deriv.dSt_dVm_csc(nbus, k_cbr_qt, i_u_vm, ytt_cbr, ytf_cbr, Vm, Va, F, T).imag
    dQt_dIfpvsc = CSC(nqq_t, nifp, 0, False)  # fully empty
    dQt_dPtvsc = CSC(nqq_t, npt, 0, False)  # fully empty
    dQt_dQtvsc = CSC(nqq_t, nqt, 0, False)  # fully empty
    dQt_dPfhvdc = CSC(nqq_t, nhvdc, 0, False)  # fully empty
    dQt_dPthvdc = CSC(nqq_t, nhvdc, 0, False)  # fully empty
    dQt_dQfhvdc = CSC(nqq_t, nhvdc, 0, False)  # fully empty
    dQt_dQthvdc = CSC(nqq_t, nhvdc, 0, False)  # fully empty
    dQt_dm = deriv.dSt_dm_csc(nbr, k_cbr_qt, u_cbr_m, F, T, Ys, tap, tap_modules, V).imag
    dQt_dtau = deriv.dSt_dtau_csc(nbr, k_cbr_qt, u_cbr_tau, F, T, Ys, tap, V).imag

    # compose the Jacobian: 14 block-rows x 11 block-columns
    J = csc_stack_2d_ff(mats=[
        dP_dVa, dP_dVm, dP_dIfpvsc, dP_dPtvsc, dP_dQtvsc,
        dP_dPfhvdc, dP_dPthvdc, dP_dQfhvdc, dP_dQthvdc, dP_dm, dP_dtau,

        dQ_dVa, dQ_dVm, dQ_dIfpvsc, dQ_dPtvsc, dQ_dQtvsc,
        dQ_dPfhvdc, dQ_dPthvdc, dQ_dQfhvdc, dQ_dQthvdc, dQ_dm, dQ_dtau,

        dLvsc_dVa, dLvsc_dVm, dLvsc_dIfpvsc, dLvsc_dPtvsc, dLvsc_dQtvsc,
        dLvsc_dPfhvdc, dLvsc_dPthvdc, dLvsc_dQfhvdc, dLvsc_dQthvdc, dLvsc_dm, dLvsc_dtau,

        dImax_dVa, dImax_dVm, dImax_dIfpvsc, dImax_dPtvsc, dImax_dQtvsc,
        dImax_dPfhvdc, dImax_dPthvdc, dImax_dQfhvdc, dImax_dQthvdc, dImax_dm, dImax_dtau,

        dDroop_dVa, dDroop_dVm, dDroop_dIfpvsc, dDroop_dPtvsc, dDroop_dQtvsc,
        dDroop_dPfhvdc, dDroop_dPthvdc, dDroop_dQfhvdc, dDroop_dQthvdc, dDroop_dm, dDroop_dtau,

        dPdc_dVa, dPdc_dVm, dPdc_dIfpvsc, dPdc_dPtvsc, dPdc_dQtvsc,
        dPdc_dPfhvdc, dPdc_dPthvdc, dPdc_dQfhvdc, dPdc_dQthvdc, dPdc_dm, dPdc_dtau,

        dVmdcDiff_dVa, dVmdcDiff_dVm, dVmdcDiff_dIfpvsc, dVmdcDiff_dPtvsc, dVmdcDiff_dQtvsc,
        dVmdcDiff_dPfhvdc, dVmdcDiff_dPthvdc, dVmdcDiff_dQfhvdc, dVmdcDiff_dQthvdc, dVmdcDiff_dm, dVmdcDiff_dtau,

        dIdc_dVa, dIdc_dVm, dIdc_dIfpvsc, dIdc_dPtvsc, dIdc_dQtvsc,
        dIdc_dPfhvdc, dIdc_dPthvdc, dIdc_dQfhvdc, dIdc_dQthvdc, dIdc_dm, dIdc_dtau,

        dLhvdc_dVa, dLhvdc_dVm, dLhvdc_dIfpvsc, dLhvdc_dPtvsc, dLhvdc_dQtvsc,
        dLhvdc_dPfhvdc, dLhvdc_dPthvdc, dLhvdc_dQfhvdc, dLhvdc_dQthvdc, dLhvdc_dm, dLhvdc_dtau,

        dInjhvdc_dVa, dInjhvdc_dVm, dInjhvdc_dIfpvsc, dInjhvdc_dPtvsc, dInjhvdc_dQtvsc,
        dInjhvdc_dPfhvdc, dInjhvdc_dPthvdc, dInjhvdc_dQfhvdc, dInjhvdc_dQthvdc, dInjhvdc_dm, dInjhvdc_dtau,

        dPf_dVa, dPf_dVm, dPf_dIfpvsc, dPf_dPtvsc, dPf_dQtvsc,
        dPf_dPfhvdc, dPf_dPthvdc, dPf_dQfhvdc, dPf_dQthvdc, dPf_dm, dPf_dtau,

        dPt_dVa, dPt_dVm, dPt_dIfpvsc, dPt_dPtvsc, dPt_dQtvsc,
        dPt_dPfhvdc, dPt_dPthvdc, dPt_dQfhvdc, dPt_dQthvdc, dPt_dm, dPt_dtau,

        dQf_dVa, dQf_dVm, dQf_dIfpvsc, dQf_dPtvsc, dQf_dQtvsc,
        dQf_dPfhvdc, dQf_dPthvdc, dQf_dQfhvdc, dQf_dQthvdc, dQf_dm, dQf_dtau,

        dQt_dVa, dQt_dVm, dQt_dIfpvsc, dQt_dPtvsc, dQt_dQtvsc,
        dQt_dPfhvdc, dQt_dPthvdc, dQt_dQfhvdc, dQt_dQthvdc, dQt_dm, dQt_dtau,

    ], n_rows=14, n_cols=11)

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

        if Fdcn_vsc[i] > -1:
            res[Fdcn_vsc[i]] += Pfn_vsc[i]

        res[T_vsc[i]] += St_vsc[i]

    return res


@njit(cache=True)
def calc_flows_active_branch_per_bus(nbus: int,
                                     F_hvdc: IntVec, T_hvdc: IntVec, Sf_hvdc: CxVec, St_hvdc: CxVec,
                                     Fdcp_vsc: IntVec, Fdcn_vsc: IntVec, T_vsc: IntVec,
                                     Vm: Vec, Va: Vec, Ifp_vsc: Vec, St_vsc: CxVec) -> CxVec:
    """
    Summation of magnitudes per bus (complex)
    Used to add effects of VSCs and HVDCs to the traditional branches
    The VSC DC pole powers are rebuilt from the currents and voltages
    The return current is always -Ifp, so no need for it as a variable
    :param nbus:
    :param F_hvdc:
    :param T_hvdc:
    :param Sf_hvdc:
    :param St_hvdc:
    :param Fdcp_vsc:
    :param Fdcn_vsc:
    :param T_vsc:
    :param Vm:
    :param Va:
    :param Ifp_vsc:
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
        Pfp_vsc = Ifp_vsc[i] * Vm[Fdcp_vsc[i]] * np.cos(Va[Fdcp_vsc[i]])
        res[Fdcp_vsc[i]] += Pfp_vsc

        if Fdcn_vsc[i] > -1:
            Pfn_vsc = -Ifp_vsc[i] * Vm[Fdcn_vsc[i]] * np.cos(Va[Fdcn_vsc[i]])
            res[Fdcn_vsc[i]] += Pfn_vsc

        res[T_vsc[i]] += St_vsc[i]

    return res


@njit(cache=True)
def calculate_vsc_currents(nbus: int,
                           Fdcp_vsc: IntVec,
                           Fdcn_vsc: IntVec,
                           Ifp_vsc: Vec) -> CxVec:
    """
    Aggregate the VSC pole current injections per bus, used by
    the DC bus current-balance residuals
    :param nbus: Total number of nodes (buses)
    :param Fdcp_vsc: Node index vector for the positive pole of each VSC
    :param Fdcn_vsc: Node index vector for the neutral/negative pole of each VSC
    :param Ifp_vsc: Positive pole current injections (p.u.)
    :return: vector of current injections per node
    """
    Iconv = np.zeros(nbus, dtype=np.complex128)

    for i in range(len(Fdcp_vsc)):
        # Positive pole
        Iconv[Fdcp_vsc[i]] += Ifp_vsc[i]

        # Neutral pole (if exists, i.e., index > -1) returns the negative current
        if Fdcn_vsc[i] > -1:
            Iconv[Fdcn_vsc[i]] -= Ifp_vsc[i]

    return Iconv


def calc_autodiff_jacobian(func: Callable[[Vec], Vec],
                           x: Vec,
                           sparsity: CSC,
                           h: float = 1e-8) -> CSC:
    """
    Compute a sparse finite-difference Jacobian using column coloring.

    Columns with disjoint residual support are perturbed together. The values
    remain finite differences of ``func``; the supplied analytic matrix is
    used only as the structural sparsity contract.

    :param func: function accepting a vector x and args, and returning either a vector or a
                 tuple where the first argument is a vector and the second.
    :param x: Point at which to evaluate the Jacobian (numpy array).
    :param sparsity: Structural Jacobian pattern at the current formulation state.
    :param h: Small step for finite difference.
    :return: Jacobian matrix as a CSC matrix.
    """
    nx: int = len(x)
    f0: Vec = func(x)
    n_rows: int = len(f0)
    structural_matrix: csc_matrix = mat_to_scipy(sparsity).copy()
    structural_matrix.data = np.ones(structural_matrix.nnz, dtype=float)
    conflict_matrix: csc_matrix = (structural_matrix.T @ structural_matrix).tocsc()
    column_colors: IntVec = np.full(nx, -1, dtype=int)
    used_color_stamp: IntVec = np.full(nx, -1, dtype=int)
    color_count: int = 0

    # Alex review required: accelerate the static PF finite-difference Jacobian without changing its equations.
    column_index: int
    for column_index in range(nx):
        data_index: int
        for data_index in range(
                conflict_matrix.indptr[column_index],
                conflict_matrix.indptr[column_index + 1]):
            conflicting_column: int = conflict_matrix.indices[data_index]
            conflicting_color: int = column_colors[conflicting_column]
            if conflicting_color >= 0:
                used_color_stamp[conflicting_color] = column_index
            else:
                pass

        selected_color: int = 0
        while selected_color < color_count and used_color_stamp[selected_color] == column_index:
            selected_color += 1
        if selected_color == color_count:
            color_count += 1
        else:
            pass
        column_colors[column_index] = selected_color

    jacobian_data: Vec = np.zeros(structural_matrix.nnz, dtype=float)
    color_index: int
    for color_index in range(color_count):
        color_columns: IntVec = np.where(column_colors == color_index)[0]
        x_plus_h: Vec = np.copy(x)
        x_plus_h[color_columns] += h
        f_plus_h: Vec = func(x_plus_h)
        finite_difference: Vec = (f_plus_h - f0) / h

        for column_index in color_columns:
            column_start: int = structural_matrix.indptr[column_index]
            column_end: int = structural_matrix.indptr[column_index + 1]
            structural_rows: IntVec = structural_matrix.indices[column_start:column_end]
            jacobian_data[column_start:column_end] = finite_difference[structural_rows]

    jacobian: csc_matrix = csc_matrix(
        (
            jacobian_data,
            structural_matrix.indices.copy(),
            structural_matrix.indptr.copy(),
        ),
        shape=(n_rows, nx),
    )
    return scipy_to_mat(jacobian)


class PfAcDcWithNegativePoles(PfFormulationTemplate):

    __slots__ = (
        "nc",
        "logger",
        "use_autodiff_jacobian",
        "V0",
        "S0",
        "I0",
        "Y0",
        "Qmin",
        "Qmax",
        "bus_types",
        "bus_grounded",
        "is_p_controlled",
        "is_q_controlled",
        "is_vm_controlled",
        "is_va_controlled",
        "u_cbr_m",
        "u_cbr_tau",
        "u_cbr_m_tau",
        "k_cbr_pf",
        "k_cbr_pt",
        "k_cbr_qf",
        "k_cbr_qt",
        "cbr_pf_set",
        "cbr_pt_set",
        "cbr_qf_set",
        "cbr_qt_set",
        "u_vsc_pfp",
        "u_vsc_pfn",
        "u_vsc_ifp",
        "u_vsc_pt",
        "u_vsc_qt",
        "k_vsc_pfp",
        "k_vsc_pfp_droop",
        "k_vsc_pfn",
        "k_vsc_i",
        "k_vsc_pdc",
        "k_vsc_pt",
        "k_vsc_qt",
        "k_vsc_vmdc_diff",
        "k_vsc_has_dc_n",
        "vsc_pfp_set",
        "vsc_pfn_set",
        "vsc_i_set",
        "vsc_pdc_set",
        "vsc_pt_set",
        "vsc_qt_set",
        "vsc_pfp_droop_side",
        "vsc_vmdc_diff_side",
        "hvdc_droop_idx",
        "i_u_vm",
        "i_u_va",
        "i_k_p",
        "i_k_p_dc",
        "i_k_q",
        "Ifp_vsc",
        "Pf_hvdc",
        "Qf_hvdc",
        "Pt_hvdc",
        "Qt_hvdc",
        "Pt_vsc",
        "Qt_vsc",
        "m",
        "tau",
        "adm",
        "discrete_shunt_control",
        "qv_droop_control",
        "static_droop",
    )

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

        # set to True to use the finite-difference Jacobian
        self.use_autodiff_jacobian: bool = self.options.use_autodiff_jacobian

        self.V0: CxVec = V0
        self.S0: CxVec = S0
        self.I0: CxVec = I0
        # We move Y0 to Ybus diagonal to improve convergence, so self.Y0 set to zeros
        self.Y0: CxVec = np.zeros_like(Y0)

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
        self.u_vsc_ifp = np.zeros(0, dtype=int)  # instead of the power
        self.u_vsc_pt = np.zeros(0, dtype=int)
        self.u_vsc_qt = np.zeros(0, dtype=int)
        self.k_vsc_pt = np.zeros(0, dtype=int)
        self.k_vsc_qt = np.zeros(0, dtype=int)
        self.k_vsc_i = np.zeros(0, dtype=int)
        self.vsc_pt_set = np.zeros(0, dtype=float)
        self.vsc_qt_set = np.zeros(0, dtype=float)
        self.vsc_i_set = np.zeros(0, dtype=float)
        self.k_vsc_has_dc_n = np.zeros(0, dtype=int)
        self.k_vsc_pfp_droop = np.zeros(0, dtype=int)  # VSCs whose Pfp follows a Pdc voltage-droop
        self.vsc_pfp_droop_side = np.zeros(0, dtype=int)  # 1 if control1 carries the droop, else 2
        self.k_vsc_vmdc_diff = np.zeros(0, dtype=int)  # bipolar VSCs whose Vm_dc regulates pole-to-pole Udc
        self.vsc_vmdc_diff_side = np.zeros(0, dtype=int)  # 1 if control1 carries the Vm_dc, else 2
        self.k_vsc_pdc = np.zeros(0, dtype=int)  # VSCs whose Pdc fixes (Vfp - Vfn) * Ifp = Pdc_set
        self.vsc_pdc_set = np.zeros(0, dtype=float)  # Pdc setpoints in MW aligned with k_vsc_pdc
        self._set_vsc_control_indices()

        # Fill HVDC Indices
        self.hvdc_droop_idx = np.zeros(0, dtype=int)
        self._set_hvdc_control_indices()

        # Alter bus indices after all other index initializations
        self.i_u_vm = np.zeros(0, dtype=int)
        self.i_u_va = np.zeros(0, dtype=int)
        self.i_k_p = np.zeros(0, dtype=int)
        self.i_k_q = np.zeros(0, dtype=int)
        self.i_k_p_dc = np.zeros(0, dtype=int)
        self._set_bus_control_indices()

        # Unknowns -----------------------------------------------------------------------------------------------------
        # Va and Vm are set at the parent. The return pole current is not an unknown:
        # it is structurally -Ifp for converters with a modelled negative pole
        self.Ifp_vsc = np.zeros(nc.vsc_data.nelm)
        self.Pt_vsc = np.zeros(nc.vsc_data.nelm)
        self.Qt_vsc = np.zeros(nc.vsc_data.nelm)
        self.Pf_hvdc = np.zeros(nc.hvdc_data.nelm)
        self.Qf_hvdc = np.zeros(nc.hvdc_data.nelm)
        self.Pt_hvdc = np.zeros(nc.hvdc_data.nelm)
        self.Qt_hvdc = np.zeros(nc.hvdc_data.nelm)
        self.m = self.nc.active_branch_data.tap_module[self.u_cbr_m]
        self.tau = self.nc.active_branch_data.tap_angle[self.u_cbr_tau]

        # set the VSC AC-side set-points
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
            Yshunt_bus=self.nc.get_Yshunt_bus_pu() + Y0,
        )
        self.adm.initialize_update()  # allows mega fast matrix updates

        if self.options.verbose > 1:
            print("Ybus\n", self.adm.Ybus.toarray())

        # Store the control states in lightweight wrappers that forward the
        # numerical work to the existing Numba kernels.
        self.discrete_shunt_control = DiscreteShuntControlState(nc=self.nc)
        self.qv_droop_control = QvDroopControlState(S0=self.S0, nc=self.nc)
        self.static_droop: StaticGeneratorDroop = StaticGeneratorDroop(self.nc)

        # On a flat start the negative DC poles sit at +1 instead
        # of -1 and the grounded buses at 1 instead of 0. Init them correctly
        if not self.options.use_stored_guess:
            self._apply_bipolar_flat_start()

        # warm-start the DC pole currents once the pole voltages carry the right signs
        self._seed_pdc_pole_currents()

    def _apply_bipolar_flat_start(self, v_ground: float = 1e-8) -> None:
        """
        Init Vm/Va so a bipolar AC/DC grid flat starts in the right basin:
            positive DC pole -> +1
            negative DC pole -> -1
            Return/ground -> ~0

        AC buses are left untouched

        Polarity is inferred from the grid structure:
          1. split the DC network into islands
          2. the grounding area is any island holding a grounded bus or a VSC
             negative terminal (F_dcn) -> seeded to roughly 0
          3. every other island is an active or "live" pole, where its sign
          comes from a Vm_dc voltage reference

        A pole island with no Vm_dc reference is under-defined (its sign would be
        fixed only by the initial guess). We default it to +1 and warn, because a
        well conditioned bipolar grid must anchor each pole with a V reference.

        :param v_ground: small non-zero magnitude for grounded buses
        :return: nothing
        """
        vsc = self.nc.vsc_data
        is_dc = self.nc.bus_data.is_dc
        F_pb = self.nc.passive_branch_data.F
        T_pb = self.nc.passive_branch_data.T
        dc_pb = self.nc.passive_branch_data.dc

        # We label each DC bus with its island id (running a BFS over DC lines)
        adj: Dict[int, List[int]] = dict()
        for k in np.where(dc_pb != 0)[0]:
            f, t = int(F_pb[k]), int(T_pb[k])
            adj.setdefault(f, list()).append(t)
            adj.setdefault(t, list()).append(f)

        comp: Dict[int, int] = dict()  # bus -> island id
        comp_buses: List[List[int]] = list()  # island id -> buses
        for b0 in np.where(is_dc != 0)[0]:
            b0 = int(b0)
            if b0 not in comp:
                cid = len(comp_buses)
                members: List[int] = list()
                stack = [b0]
                comp[b0] = cid
                while stack:
                    u = stack.pop()
                    members.append(u)
                    for w in adj.get(u, ()):
                        if w not in comp:
                            comp[w] = cid
                            stack.append(w)
                comp_buses.append(members)

        # The positive DC pole fp is never meant to be grounded
        for k in range(vsc.nelm):
            if vsc.active[k] and self.bus_grounded[int(vsc.F[k])]:
                self.logger.add_warning(
                    msg="VSC positive DC terminal is grounded, while the positive "
                        "pole is never meant to be grounded",
                    device=str(self.nc.bus_data.names[int(vsc.F[k])]))

        # Set the grounding area for islands with a grounded bus or a VSC negative
        is_return = [bool(np.any(self.bus_grounded[m] != 0)) for m in comp_buses]
        for fn in vsc.F_dcn:
            if fn > -1 and int(fn) in comp:
                is_return[comp[int(fn)]] = True

        # Each pole island gets the sign from a Vm_dc reference on its fp side
        vmdc = ConverterControlType.Vm_dc.idx()
        sign: Dict[int, int] = dict()  # pole island, so apply +-1
        for k in range(vsc.nelm):
            if vsc.active[k]:
                pole = comp.get(int(vsc.F[k]))
                if pole is not None and not is_return[pole]:
                    if vsc.control1_int[k] == vmdc:
                        sign[pole] = 1 if vsc.control1_val[k] >= 0.0 else -1
                    elif vsc.control2_int[k] == vmdc:
                        sign[pole] = 1 if vsc.control2_val[k] >= 0.0 else -1

        # under-defined pole islands (no Vm_dc reference) default to +1 and warn
        for cid, members in enumerate(comp_buses):
            if not is_return[cid] and cid not in sign:
                sign[cid] = 1
                self.logger.add_warning(
                    msg="DC pole has no Vm_dc voltage reference; sign defaults to +1 "
                        "and depends on the initial guess. Anchor the pole to make it well posed.",
                    device=str(self.nc.bus_data.names[members[0]]))

        # Populate the DC bus voltage with the guess
        for b in np.where(is_dc != 0)[0]:
            b = int(b)
            cid = comp[b]
            if is_return[cid]:
                self._Vm[b] = v_ground
                self._Va[b] = 0.0
            elif sign.get(cid, 1) > 0:
                self._Va[b] = 0.0
            else:
                self._Va[b] = np.pi  # Like a minus sign
        self.V = polar_to_rect(self._Vm, self._Va)

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
        # We exclude DC buses as it is the current for which the balance is imposed
        self.i_k_p = np.where((self.is_p_controlled == 1) & (self.nc.bus_data.is_dc == 0))[0]
        self.i_k_q = np.where(self.is_q_controlled == 1)[0]
        # DC buses carrying a current-balance equation when P-controlled, not DC slacks and not grounded
        self.i_k_p_dc = np.where((self.is_p_controlled == 1)
                                 & (self.nc.bus_data.is_dc != 0)
                                 & (self.nc.bus_data.is_grounded == 0))[0]

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
            if ctrl_m == TapModuleControl.Vm.idx():

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
                                          device=self.nc.passive_branch_data.idtag[k])

            elif ctrl_m == TapModuleControl.Qf.idx():
                u_cbr_m.append(k)
                k_cbr_qf.append(k)
                cbr_qf_set.append(self.nc.active_branch_data.Qset[k])

            elif ctrl_m == TapModuleControl.Qt.idx():
                u_cbr_m.append(k)
                k_cbr_qt.append(k)
                cbr_qt_set.append(self.nc.active_branch_data.Qset[k])

            elif ctrl_m == TapModuleControl.fixed.idx():
                # bus_idx = self.nc.active_branch_data.tap_controlled_buses[k]
                # self.is_vm_controlled[bus_idx] = False
                # self.m[k] = self.nc.active_branch_data.tap_module[k]
                pass

            else:
                raise Exception(f"Unknown tap phase module mode {ctrl_m}")

            # analyze tap-phase controls
            if ctrl_tau == TapPhaseControl.Pf.idx():
                u_cbr_tau.append(k)
                k_cbr_pf.append(k)
                cbr_pf_set.append(self.nc.active_branch_data.Pset[k])

            elif ctrl_tau == TapPhaseControl.Pt.idx():
                u_cbr_tau.append(k)
                k_cbr_pt.append(k)
                cbr_pt_set.append(self.nc.active_branch_data.Pset[k])

            elif ctrl_tau == TapPhaseControl.fixed.idx():
                # self.tau[k] = self.nc.active_branch_data.tap_angle[k]
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
        k_vsc_has_dc_n = list()

        # VSC LOOP
        for k in range(self.nc.vsc_data.nelm):

            if self.nc.vsc_data.active[k]:

                if self.nc.vsc_data.F_dcn[k] > -1:
                    k_vsc_has_dc_n.append(k)

                control1 = self.nc.vsc_data.control1_int[k]
                control2 = self.nc.vsc_data.control2_int[k]
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
                if control1 == ConverterControlType.Fault1.idx() and control2 == ConverterControlType.Fault2.idx():
                    u_vsc_pfp.append(k)
                    u_vsc_pt.append(k)
                    u_vsc_qt.append(k)

                elif control1 == ConverterControlType.Vm_dc.idx() and control2 == ConverterControlType.Vm_dc.idx():
                    self.logger.add_error(
                        f"VSC control1 and control2 are the same for VSC indexed at {k},"
                        f" control1: {control1}, control2: {control2}")

                elif (control1 == ConverterControlType.Vm_dc.idx()
                      and control2 == ConverterControlType.Vm_ac.idx()):

                    if control1_bus_device > -1:
                        self.is_vm_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        self.is_vm_controlled[control2_bus_device] = True
                    u_vsc_pfp.append(k)

                    if self.nc.vsc_data.F_dcn[k] > -1:
                        u_vsc_pfn.append(k)
                    u_vsc_pt.append(k)
                    u_vsc_qt.append(k)

                elif (control1 == ConverterControlType.Vm_dc.idx()
                      and control2 == ConverterControlType.Va_ac.idx()):

                    if control1_bus_device > -1:
                        self.is_vm_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        self.is_va_controlled[control2_bus_device] = True
                    u_vsc_pfp.append(k)

                    if self.nc.vsc_data.F_dcn[k] > -1:
                        u_vsc_pfn.append(k)
                    u_vsc_pt.append(k)
                    u_vsc_qt.append(k)

                elif (control1 == ConverterControlType.Vm_dc.idx()
                      and (control2 == ConverterControlType.Qac.idx()
                           or control2 == ConverterControlType.Q_droop.idx())):

                    if control1_bus_device > -1:
                        self.is_vm_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        pass
                    if control1_branch_device > -1:
                        pass
                    if control2_branch_device > -1:
                        u_vsc_pfp.append(control2_branch_device)

                        if self.nc.vsc_data.F_dcn[k] > -1:
                            u_vsc_pfn.append(control2_branch_device)
                        u_vsc_pt.append(control2_branch_device)

                        k_vsc_qt.append(control2_branch_device)

                        vsc_qt_set.append(control2_magnitude)

                elif (control1 == ConverterControlType.Vm_dc.idx()
                      and (control2 == ConverterControlType.Pdc.idx()
                           or control2 == ConverterControlType.Pdc_droop.idx())):

                    if control1_bus_device > -1:
                        self.is_vm_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        pass
                    if control1_branch_device > -1:
                        pass
                    if control2_branch_device > -1:
                        u_vsc_pt.append(control2_branch_device)
                        u_vsc_qt.append(control2_branch_device)

                        if self.nc.vsc_data.F_dcn[k] > -1:
                            u_vsc_pfn.append(control2_branch_device)

                        k_vsc_pfp.append(control2_branch_device)

                        vsc_pfp_set.append(control2_magnitude)

                elif (control1 == ConverterControlType.Vm_dc.idx()
                      and control2 == ConverterControlType.Pac.idx()):

                    if control1_bus_device > -1:
                        self.is_vm_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        pass
                    if control1_branch_device > -1:
                        pass
                    if control2_branch_device > -1:
                        u_vsc_pfp.append(control2_branch_device)

                        if self.nc.vsc_data.F_dcn[k] > -1:
                            u_vsc_pfn.append(control2_branch_device)

                        u_vsc_qt.append(control2_branch_device)

                        k_vsc_pt.append(control2_branch_device)

                        vsc_pt_set.append(control2_magnitude)

                elif (control1 == ConverterControlType.Vm_dc.idx()
                      and control2 == ConverterControlType.Imax.idx()):

                    if control1_bus_device > -1:
                        self.is_vm_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        pass
                    if control1_branch_device > -1:
                        pass
                    if control2_branch_device > -1:
                        u_vsc_pfp.append(control2_branch_device)

                        if self.nc.vsc_data.F_dcn[k] > -1:
                            u_vsc_pfn.append(control2_branch_device)

                        u_vsc_pt.append(control2_branch_device)
                        u_vsc_qt.append(control2_branch_device)

                        k_vsc_i.append(control2_branch_device)

                        vsc_i_set.append(control2_magnitude)

                elif (control1 == ConverterControlType.Vm_ac.idx()
                      and control2 == ConverterControlType.Vm_dc.idx()):

                    if control1_bus_device > -1:
                        self.is_vm_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        self.is_vm_controlled[control2_bus_device] = True
                    u_vsc_pfp.append(k)

                    if self.nc.vsc_data.F_dcn[k] > -1:
                        u_vsc_pfn.append(k)
                    u_vsc_pt.append(k)
                    u_vsc_qt.append(k)

                elif (control1 == ConverterControlType.Vm_ac.idx()
                      and control2 == ConverterControlType.Vm_ac.idx()):

                    self.logger.add_error(
                        f"VSC control1 and control2 are the same for VSC indexed at {k},"
                        f" control1: {control1}, control2: {control2}")

                elif (control1 == ConverterControlType.Vm_ac.idx()
                      and control2 == ConverterControlType.Va_ac.idx()):

                    if control1_bus_device > -1:
                        self.is_vm_controlled[control1_bus_device] = True
                        # Grid-forming voltage control fixes Vm, while the
                        # converter's unknown Qt still needs the nodal Q row.
                        self.is_q_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        self.is_va_controlled[control2_bus_device] = True
                        # Grid-forming angle control fixes Va, while the
                        # converter's unknown Pt still needs the nodal P row.
                        self.is_p_controlled[control2_bus_device] = True
                    u_vsc_pfp.append(k)

                    if self.nc.vsc_data.F_dcn[k] > -1:
                        u_vsc_pfn.append(k)
                    u_vsc_pt.append(k)
                    u_vsc_qt.append(k)

                elif (control1 == ConverterControlType.Vm_ac.idx()
                      and control2 == ConverterControlType.Qac.idx()):

                    if control1_bus_device > -1:
                        self.is_vm_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        pass
                    if control1_branch_device > -1:
                        pass
                    if control2_branch_device > -1:
                        u_vsc_pfp.append(control2_branch_device)

                        if self.nc.vsc_data.F_dcn[k] > -1:
                            u_vsc_pfn.append(control2_branch_device)
                        u_vsc_pt.append(control2_branch_device)

                        k_vsc_qt.append(control2_branch_device)
                        vsc_qt_set.append(control2_magnitude)

                elif (control1 == ConverterControlType.Vm_ac.idx()
                      and (control2 == ConverterControlType.Pdc.idx()
                           or control2 == ConverterControlType.Pdc_droop.idx())):

                    if control1_bus_device > -1:
                        self.is_vm_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        pass
                    if control1_branch_device > -1:
                        pass
                    if control2_branch_device > -1:
                        u_vsc_pt.append(control2_branch_device)
                        u_vsc_qt.append(control2_branch_device)

                        if self.nc.vsc_data.F_dcn[k] > -1:
                            u_vsc_pfn.append(control2_branch_device)

                        k_vsc_pfp.append(control2_branch_device)
                        vsc_pfp_set.append(control2_magnitude)

                elif (control1 == ConverterControlType.Vm_ac.idx()
                      and control2 == ConverterControlType.Pac.idx()):

                    if control1_bus_device > -1:
                        self.is_vm_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        pass
                    if control1_branch_device > -1:
                        pass
                    if control2_branch_device > -1:
                        u_vsc_pfp.append(control2_branch_device)

                        if self.nc.vsc_data.F_dcn[k] > -1:
                            u_vsc_pfn.append(control2_branch_device)
                        u_vsc_qt.append(control2_branch_device)

                        k_vsc_pt.append(control2_branch_device)
                        vsc_pt_set.append(control2_magnitude)

                elif (control1 == ConverterControlType.Vm_ac.idx()
                      and control2 == ConverterControlType.Imax.idx()):

                    if control1_bus_device > -1:
                        self.is_vm_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        pass
                    if control1_branch_device > -1:
                        pass
                    if control2_branch_device > -1:
                        u_vsc_pfp.append(control2_branch_device)

                        if self.nc.vsc_data.F_dcn[k] > -1:
                            u_vsc_pfn.append(control2_branch_device)
                        u_vsc_pt.append(control2_branch_device)
                        u_vsc_qt.append(control2_branch_device)

                        k_vsc_i.append(control2_branch_device)

                        vsc_i_set.append(control2_magnitude)

                elif (control1 == ConverterControlType.Va_ac.idx()
                      and control2 == ConverterControlType.Vm_dc.idx()):

                    if control1_bus_device > -1:
                        self.is_va_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        self.is_vm_controlled[control2_bus_device] = True
                    u_vsc_pfp.append(k)

                    if self.nc.vsc_data.F_dcn[k] > -1:
                        u_vsc_pfn.append(k)
                    u_vsc_pt.append(k)
                    u_vsc_qt.append(k)

                elif (control1 == ConverterControlType.Va_ac.idx()
                      and control2 == ConverterControlType.Vm_ac.idx()):

                    if control1_bus_device > -1:
                        self.is_va_controlled[control1_bus_device] = True
                        # Grid-forming angle control fixes Va, while the
                        # converter's unknown Pt still needs the nodal P row.
                        self.is_p_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        self.is_vm_controlled[control2_bus_device] = True
                        # Grid-forming voltage control fixes Vm, while the
                        # converter's unknown Qt still needs the nodal Q row.
                        self.is_q_controlled[control2_bus_device] = True
                    u_vsc_pfp.append(k)

                    if self.nc.vsc_data.F_dcn[k] > -1:
                        u_vsc_pfn.append(k)
                    u_vsc_pt.append(k)
                    u_vsc_qt.append(k)

                elif (control1 == ConverterControlType.Va_ac.idx()
                      and control2 == ConverterControlType.Va_ac.idx()):

                    self.logger.add_error(
                        f"VSC control1 and control2 are the same for VSC indexed at {k},"
                        f" control1: {control1}, control2: {control2}")

                elif (control1 == ConverterControlType.Va_ac.idx()
                      and (control2 == ConverterControlType.Qac.idx()
                           or control2 == ConverterControlType.Q_droop.idx())):

                    if control1_bus_device > -1:
                        self.is_va_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        pass
                    if control1_branch_device > -1:
                        pass
                    if control2_branch_device > -1:
                        u_vsc_pfp.append(control2_branch_device)

                        if self.nc.vsc_data.F_dcn[k] > -1:
                            u_vsc_pfn.append(control2_branch_device)
                        u_vsc_pt.append(control2_branch_device)

                        k_vsc_qt.append(control2_branch_device)
                        vsc_qt_set.append(control2_magnitude)

                elif (control1 == ConverterControlType.Va_ac.idx()
                      and (control2 == ConverterControlType.Pdc.idx()
                           or control2 == ConverterControlType.Pdc_droop.idx())):

                    if control1_bus_device > -1:
                        self.is_va_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        pass
                    if control1_branch_device > -1:
                        pass
                    if control2_branch_device > -1:
                        u_vsc_pt.append(control2_branch_device)
                        u_vsc_qt.append(control2_branch_device)

                        if self.nc.vsc_data.F_dcn[k] > -1:
                            u_vsc_pfn.append(control2_branch_device)

                        k_vsc_pfp.append(control2_branch_device)
                        vsc_pfp_set.append(control2_magnitude)

                elif (control1 == ConverterControlType.Va_ac.idx()
                      and control2 == ConverterControlType.Pac.idx()):

                    if control1_bus_device > -1:
                        self.is_va_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        pass
                    if control1_branch_device > -1:
                        pass
                    if control2_branch_device > -1:
                        u_vsc_pfp.append(control2_branch_device)

                        if self.nc.vsc_data.F_dcn[k] > -1:
                            u_vsc_pfn.append(control2_branch_device)
                        u_vsc_qt.append(control2_branch_device)

                        k_vsc_pt.append(control2_branch_device)
                        vsc_pt_set.append(control2_magnitude)

                elif (control1 == ConverterControlType.Va_ac.idx()
                      and control2 == ConverterControlType.Imax.idx()):

                    if control1_bus_device > -1:
                        self.is_va_controlled[control1_bus_device] = True
                    if control2_bus_device > -1:
                        pass
                    if control1_branch_device > -1:
                        pass
                    if control2_branch_device > -1:
                        u_vsc_pfp.append(control2_branch_device)

                        if self.nc.vsc_data.F_dcn[k] > -1:
                            u_vsc_pfn.append(control2_branch_device)
                        u_vsc_pt.append(control2_branch_device)
                        u_vsc_qt.append(control2_branch_device)

                        k_vsc_i.append(control2_branch_device)

                        vsc_i_set.append(control2_magnitude)

                elif ((control1 == ConverterControlType.Qac.idx()
                       or control1 == ConverterControlType.Q_droop.idx())
                      and control2 == ConverterControlType.Vm_dc.idx()):

                    if control2_bus_device > -1:
                        self.is_vm_controlled[control2_bus_device] = True
                    if control1_branch_device > -1:
                        u_vsc_pfp.append(control1_branch_device)

                        if self.nc.vsc_data.F_dcn[k] > -1:
                            u_vsc_pfn.append(control1_branch_device)
                        u_vsc_pt.append(control1_branch_device)

                        k_vsc_qt.append(control1_branch_device)
                        vsc_qt_set.append(control1_magnitude)

                elif ((control1 == ConverterControlType.Qac.idx()
                       or control1 == ConverterControlType.Q_droop.idx())
                      and control2 == ConverterControlType.Vm_ac.idx()):

                    if control2_bus_device > -1:
                        self.is_vm_controlled[control2_bus_device] = True
                    if control1_branch_device > -1:
                        u_vsc_pfp.append(control1_branch_device)

                        if self.nc.vsc_data.F_dcn[k] > -1:
                            u_vsc_pfn.append(control1_branch_device)
                        u_vsc_pt.append(control1_branch_device)

                        k_vsc_qt.append(control1_branch_device)
                        vsc_qt_set.append(control1_magnitude)

                elif ((control1 == ConverterControlType.Qac.idx()
                       or control1 == ConverterControlType.Q_droop.idx())
                      and control2 == ConverterControlType.Va_ac.idx()):

                    if control2_bus_device > -1:
                        self.is_va_controlled[control2_bus_device] = True
                    if control1_branch_device > -1:
                        u_vsc_pfp.append(control1_branch_device)

                        if self.nc.vsc_data.F_dcn[k] > -1:
                            u_vsc_pfn.append(control1_branch_device)

                        u_vsc_pt.append(control1_branch_device)

                        k_vsc_qt.append(control1_branch_device)
                        vsc_qt_set.append(control1_magnitude)

                elif ((control1 == ConverterControlType.Qac.idx()
                       or control1 == ConverterControlType.Q_droop.idx())
                      and (control2 == ConverterControlType.Qac.idx()
                           or control2 == ConverterControlType.Q_droop.idx())):

                    self.logger.add_error(
                        f"VSC control1 and control2 are the same for VSC indexed at {k},"
                        f" control1: {control1}, control2: {control2}")

                elif ((control1 == ConverterControlType.Qac.idx()
                       or control1 == ConverterControlType.Q_droop.idx())
                      and (control2 == ConverterControlType.Pdc.idx()
                           or control2 == ConverterControlType.Pdc_droop.idx())):

                    if control1_branch_device > -1:

                        if self.nc.vsc_data.F_dcn[k] > -1:
                            u_vsc_pfn.append(control1_branch_device)
                        u_vsc_pt.append(control1_branch_device)
                        k_vsc_qt.append(control1_branch_device)
                        vsc_qt_set.append(control1_magnitude)

                    if control2_branch_device > -1:
                        k_vsc_pfp.append(control2_branch_device)
                        vsc_pfp_set.append(control2_magnitude)

                elif ((control1 == ConverterControlType.Qac.idx()
                       or control1 == ConverterControlType.Q_droop.idx())
                      and control2 == ConverterControlType.Pac.idx()):

                    if control1_branch_device > -1:
                        u_vsc_pfp.append(control1_branch_device)

                        if self.nc.vsc_data.F_dcn[k] > -1:
                            u_vsc_pfn.append(control1_branch_device)
                        k_vsc_qt.append(control1_branch_device)
                        vsc_qt_set.append(control1_magnitude)

                    if control2_branch_device > -1:
                        k_vsc_pt.append(control2_branch_device)
                        vsc_pt_set.append(control2_magnitude)

                elif ((control1 == ConverterControlType.Qac.idx()
                       or control1 == ConverterControlType.Q_droop.idx())
                      and control2 == ConverterControlType.Imax.idx()):

                    if control1_branch_device > -1:
                        u_vsc_pfp.append(control1_branch_device)

                        if self.nc.vsc_data.F_dcn[k] > -1:
                            u_vsc_pfn.append(control1_branch_device)
                        u_vsc_pt.append(control1_branch_device)
                        k_vsc_qt.append(control1_branch_device)
                        vsc_qt_set.append(control1_magnitude)

                    if control2_branch_device > -1:
                        k_vsc_i.append(control2_branch_device)
                        vsc_i_set.append(control2_magnitude)

                elif ((control1 == ConverterControlType.Pdc.idx()
                       or control1 == ConverterControlType.Pdc_droop.idx())
                      and control2 == ConverterControlType.Vm_dc.idx()):

                    if control2_bus_device > -1:
                        self.is_vm_controlled[control2_bus_device] = True
                    if control1_branch_device > -1:
                        u_vsc_pt.append(control1_branch_device)
                        u_vsc_qt.append(control1_branch_device)

                        if self.nc.vsc_data.F_dcn[k] > -1:
                            u_vsc_pfn.append(control1_branch_device)

                        k_vsc_pfp.append(control1_branch_device)
                        vsc_pfp_set.append(control1_magnitude)

                elif ((control1 == ConverterControlType.Pdc.idx()
                       or control1 == ConverterControlType.Pdc_droop.idx())
                      and control2 == ConverterControlType.Vm_ac.idx()):

                    if control2_bus_device > -1:
                        self.is_vm_controlled[control2_bus_device] = True
                    if control1_branch_device > -1:
                        u_vsc_pt.append(control1_branch_device)
                        u_vsc_qt.append(control1_branch_device)

                        if self.nc.vsc_data.F_dcn[k] > -1:
                            u_vsc_pfn.append(control1_branch_device)

                        k_vsc_pfp.append(control1_branch_device)
                        vsc_pfp_set.append(control1_magnitude)

                elif ((control1 == ConverterControlType.Pdc.idx()
                       or control1 == ConverterControlType.Pdc_droop.idx())
                      and control2 == ConverterControlType.Va_ac.idx()):

                    if control2_bus_device > -1:
                        self.is_va_controlled[control2_bus_device] = True
                    if control1_branch_device > -1:
                        u_vsc_pt.append(control1_branch_device)
                        u_vsc_qt.append(control1_branch_device)

                        if self.nc.vsc_data.F_dcn[k] > -1:
                            u_vsc_pfn.append(control1_branch_device)

                        k_vsc_pfp.append(control1_branch_device)
                        vsc_pfp_set.append(control1_magnitude)

                elif ((control1 == ConverterControlType.Pdc.idx()
                       or control1 == ConverterControlType.Pdc_droop.idx())
                      and (control2 == ConverterControlType.Qac.idx()
                           or control2 == ConverterControlType.Q_droop.idx())):

                    if control1_branch_device > -1:
                        u_vsc_pt.append(control1_branch_device)

                        if self.nc.vsc_data.F_dcn[k] > -1:
                            u_vsc_pfn.append(control1_branch_device)

                        k_vsc_pfp.append(control1_branch_device)
                        vsc_pfp_set.append(control1_magnitude)

                    if control2_branch_device > -1:
                        k_vsc_qt.append(control2_branch_device)
                        vsc_qt_set.append(control2_magnitude)

                elif ((control1 == ConverterControlType.Pdc.idx()
                       or control1 == ConverterControlType.Pdc_droop.idx())
                      and (control2 == ConverterControlType.Pdc.idx()
                           or control2 == ConverterControlType.Pdc_droop.idx())):

                    self.logger.add_error(
                        f"VSC control1 and control2 are the same for VSC indexed at {k},"
                        f" control1: {control1}, control2: {control2}")

                elif ((control1 == ConverterControlType.Pdc.idx()
                       or control1 == ConverterControlType.Pdc_droop.idx())
                      and control2 == ConverterControlType.Pac.idx()):

                    if control1_branch_device > -1:
                        u_vsc_pt.append(control1_branch_device)
                        u_vsc_qt.append(control1_branch_device)

                        if self.nc.vsc_data.F_dcn[k] > -1:
                            u_vsc_pfn.append(control1_branch_device)

                        k_vsc_pfp.append(control1_branch_device)
                        vsc_pfp_set.append(control1_magnitude)

                        k_vsc_pt.append(control1_branch_device)
                        vsc_pt_set.append(control1_magnitude)

                elif ((control1 == ConverterControlType.Pdc.idx()
                       or control1 == ConverterControlType.Pdc_droop.idx())
                          and control2 == ConverterControlType.Imax.idx()):

                    if control1_branch_device > -1:
                        u_vsc_pt.append(control1_branch_device)
                        u_vsc_qt.append(control1_branch_device)

                        if self.nc.vsc_data.F_dcn[k] > -1:
                            u_vsc_pfn.append(control1_branch_device)

                        k_vsc_pfp.append(control1_branch_device)
                        vsc_pfp_set.append(control1_magnitude)

                    if control2_branch_device > -1:
                        k_vsc_i.append(control2_branch_device)
                        vsc_i_set.append(control2_magnitude)

                elif (control1 == ConverterControlType.Pac.idx()
                      and control2 == ConverterControlType.Vm_dc.idx()):

                    if control2_bus_device > -1:
                        self.is_vm_controlled[control2_bus_device] = True
                    if control1_branch_device > -1:
                        u_vsc_pfp.append(control1_branch_device)

                        if self.nc.vsc_data.F_dcn[k] > -1:
                            u_vsc_pfn.append(control1_branch_device)
                        u_vsc_qt.append(control1_branch_device)

                        k_vsc_pt.append(control1_branch_device)
                        vsc_pt_set.append(control1_magnitude)

                elif (control1 == ConverterControlType.Pac.idx()
                      and control2 == ConverterControlType.Vm_ac.idx()):

                    if control2_bus_device > -1:
                        self.is_vm_controlled[control2_bus_device] = True
                        self.is_q_controlled[control2_bus_device] = True
                    if control1_branch_device > -1:
                        u_vsc_pfp.append(control1_branch_device)
                        if self.nc.vsc_data.F_dcn[k] > -1:
                            u_vsc_pfn.append(control1_branch_device)
                        u_vsc_qt.append(control1_branch_device)

                        k_vsc_pt.append(control1_branch_device)
                        vsc_pt_set.append(control1_magnitude)

                elif (control1 == ConverterControlType.Pac.idx()
                      and control2 == ConverterControlType.Va_ac.idx()):

                    if control2_bus_device > -1:
                        self.is_va_controlled[control2_bus_device] = True
                    if control1_branch_device > -1:
                        u_vsc_pfp.append(control1_branch_device)

                        if self.nc.vsc_data.F_dcn[k] > -1:
                            u_vsc_pfn.append(control1_branch_device)
                        u_vsc_qt.append(control1_branch_device)

                        k_vsc_pt.append(control1_branch_device)
                        vsc_pt_set.append(control1_magnitude)

                elif (control1 == ConverterControlType.Pac.idx()
                      and (control2 == ConverterControlType.Qac.idx()
                           or control2 == ConverterControlType.Q_droop.idx())):

                    if control1_branch_device > -1:
                        u_vsc_pfp.append(control1_branch_device)

                        if self.nc.vsc_data.F_dcn[k] > -1:
                            u_vsc_pfn.append(control1_branch_device)

                        k_vsc_pt.append(control1_branch_device)
                        k_vsc_qt.append(control1_branch_device)
                        vsc_qt_set.append(control2_magnitude)
                        vsc_pt_set.append(control1_magnitude)

                elif (control1 == ConverterControlType.Pac.idx()
                      and (control2 == ConverterControlType.Pdc.idx()
                           or control2 == ConverterControlType.Pdc_droop.idx())):

                    if control1_branch_device > -1:

                        if self.nc.vsc_data.F_dcn[k] > -1:
                            u_vsc_pfn.append(control1_branch_device)

                        u_vsc_qt.append(control1_branch_device)

                        k_vsc_pfp.append(control1_branch_device)
                        vsc_pfp_set.append(control1_magnitude)

                        k_vsc_pt.append(control1_branch_device)
                        vsc_pt_set.append(control1_magnitude)

                elif (control1 == ConverterControlType.Pac.idx()
                      and control2 == ConverterControlType.Pac.idx()):

                    self.logger.add_error(
                        f"VSC control1 and control2 are the same for VSC indexed at {k},"
                        f" control1: {control1}, control2: {control2}")

                elif (control1 == ConverterControlType.Pac.idx()
                      and control2 == ConverterControlType.Imax.idx()):

                    if control1_branch_device > -1:
                        u_vsc_pfp.append(control1_branch_device)

                        if self.nc.vsc_data.F_dcn[k] > -1:
                            u_vsc_pfn.append(control1_branch_device)
                        u_vsc_qt.append(control1_branch_device)

                        k_vsc_pt.append(control1_branch_device)
                        vsc_pt_set.append(control1_magnitude)

                    if control2_branch_device > -1:
                        k_vsc_i.append(control2_branch_device)
                        vsc_i_set.append(control2_magnitude)

                elif (control1 == ConverterControlType.Imax.idx()
                      and control2 == ConverterControlType.Vm_dc.idx()):

                    if control1_branch_device > -1:
                        u_vsc_pfp.append(control1_branch_device)

                        if self.nc.vsc_data.F_dcn[k] > -1:
                            u_vsc_pfn.append(control1_branch_device)

                        u_vsc_pt.append(control1_branch_device)
                        u_vsc_qt.append(control1_branch_device)

                        k_vsc_i.append(control1_branch_device)
                        vsc_i_set.append(control1_magnitude)

                    if control2_bus_device > -1:
                        self.is_vm_controlled[control2_bus_device] = True

                elif (control1 == ConverterControlType.Imax.idx()
                      and control2 == ConverterControlType.Vm_ac.idx()):

                    if control1_branch_device > -1:
                        u_vsc_pfp.append(control1_branch_device)

                        if self.nc.vsc_data.F_dcn[k] > -1:
                            u_vsc_pfn.append(control1_branch_device)
                        u_vsc_pt.append(control1_branch_device)
                        u_vsc_qt.append(control1_branch_device)

                        k_vsc_i.append(control1_branch_device)
                        vsc_i_set.append(control1_magnitude)

                    if control2_bus_device > -1:
                        self.is_vm_controlled[control2_bus_device] = True

                elif (control1 == ConverterControlType.Imax.idx()
                      and control2 == ConverterControlType.Va_ac.idx()):

                    if control1_branch_device > -1:
                        u_vsc_pfp.append(control1_branch_device)

                        if self.nc.vsc_data.F_dcn[k] > -1:
                            u_vsc_pfn.append(control1_branch_device)

                        u_vsc_pt.append(control1_branch_device)
                        u_vsc_qt.append(control1_branch_device)

                        k_vsc_i.append(control1_branch_device)
                        vsc_i_set.append(control1_magnitude)

                    if control2_bus_device > -1:
                        self.is_va_controlled[control2_bus_device] = True

                elif (control1 == ConverterControlType.Imax.idx()
                      and (control2 == ConverterControlType.Qac.idx()
                           or control2 == ConverterControlType.Q_droop.idx())):

                    if control1_branch_device > -1:
                        u_vsc_pfp.append(control1_branch_device)

                        if self.nc.vsc_data.F_dcn[k] > -1:
                            u_vsc_pfn.append(control1_branch_device)

                        u_vsc_pt.append(control1_branch_device)

                        k_vsc_i.append(control1_branch_device)
                        vsc_i_set.append(control1_magnitude)

                    if control2_branch_device > -1:
                        k_vsc_qt.append(control1_branch_device)
                        vsc_qt_set.append(control1_magnitude)

                elif (control1 == ConverterControlType.Imax.idx()
                      and (control2 == ConverterControlType.Pdc.idx()
                           or control2 == ConverterControlType.Pdc_droop.idx())):

                    if control1_branch_device > -1:

                        if self.nc.vsc_data.F_dcn[k] > -1:
                            u_vsc_pfn.append(control1_branch_device)

                        u_vsc_pt.append(control1_branch_device)
                        u_vsc_qt.append(control1_branch_device)

                        k_vsc_i.append(control1_branch_device)
                        vsc_i_set.append(control1_magnitude)

                    if control2_branch_device > -1:
                        k_vsc_pfp.append(control2_branch_device)
                        vsc_pfp_set.append(control2_magnitude)

                elif (control1 == ConverterControlType.Imax.idx()
                      and control2 == ConverterControlType.Pac.idx()):

                    if control1_branch_device > -1:
                        u_vsc_pfp.append(control1_branch_device)

                        if self.nc.vsc_data.F_dcn[k] > -1:
                            u_vsc_pfn.append(control1_branch_device)

                        u_vsc_qt.append(control1_branch_device)

                        k_vsc_i.append(control1_branch_device)
                        vsc_i_set.append(control1_magnitude)

                    if control2_branch_device > -1:
                        k_vsc_pt.append(control2_branch_device)
                        vsc_pt_set.append(control2_magnitude)

                elif (control1 == ConverterControlType.Imax.idx()
                      and control2 == ConverterControlType.Imax.idx()):
                    self.logger.add_error(
                        f"VSC control1 and control2 are the same for VSC indexed at {k},"
                        f" control1: {control1}, control2: {control2}")

        # Fill arrays
        self.u_vsc_pfp = np.array(u_vsc_pfp, dtype=int)
        self.u_vsc_pfn = np.array(u_vsc_pfn, dtype=int)
        self.u_vsc_pt = np.array(u_vsc_pt, dtype=int)
        self.u_vsc_qt = np.array(u_vsc_qt, dtype=int)
        self.k_vsc_pfp = np.array(k_vsc_pfp, dtype=int)
        self.k_vsc_pfn = np.array(k_vsc_pfn, dtype=int)
        self.k_vsc_pt = np.array(k_vsc_pt, dtype=int)
        self.k_vsc_qt = np.array(k_vsc_qt, dtype=int)
        self.k_vsc_i = np.array(k_vsc_i, dtype=int)
        self.k_vsc_has_dc_n = np.array(k_vsc_has_dc_n, dtype=int)
        self.vsc_pfp_set = np.array(vsc_pfp_set, dtype=float)
        self.vsc_pfn_set = np.array(vsc_pfn_set, dtype=float)
        self.vsc_pt_set = np.array(vsc_pt_set, dtype=float)
        self.vsc_qt_set = np.array(vsc_qt_set, dtype=float)
        self.vsc_i_set = np.array(vsc_i_set, dtype=float)

        # --- Pdc voltage-droop reformulation -------------------------------------------------------------------------
        droop_k = list()
        droop_side = list()
        keep_k = list()
        keep_set = list()
        for idx in range(len(self.k_vsc_pfp)):
            kk = int(self.k_vsc_pfp[idx])
            if self.nc.vsc_data.control1_int[kk] == ConverterControlType.Pdc_droop.idx():
                droop_k.append(kk)
                droop_side.append(1)
            elif self.nc.vsc_data.control2_int[kk] == ConverterControlType.Pdc_droop.idx():
                droop_k.append(kk)
                droop_side.append(2)
            else:
                keep_k.append(kk)
                keep_set.append(self.vsc_pfp_set[idx])

        self.k_vsc_pfp = np.array(keep_k, dtype=int)
        self.vsc_pfp_set = np.array(keep_set, dtype=float)
        self.k_vsc_pfp_droop = np.array(droop_k, dtype=int)
        self.vsc_pfp_droop_side = np.array(droop_side, dtype=int)
        if len(self.k_vsc_pfp_droop):
            self.u_vsc_pfp = np.unique(np.r_[self.u_vsc_pfp, self.k_vsc_pfp_droop]).astype(int)

        # With pole currents as the DC unknowns, a fixed power follows
        # (Vfp - Vfn) * Ifp - Pdc_set = 0
        self.k_vsc_pdc = self.k_vsc_pfp.copy()
        self.vsc_pdc_set = self.vsc_pfp_set.copy()
        self.k_vsc_pfp = np.zeros(0, dtype=int)
        self.vsc_pfp_set = np.zeros(0, dtype=float)
        if len(self.k_vsc_pdc):
            self.u_vsc_pfp = np.unique(np.r_[self.u_vsc_pfp, self.k_vsc_pdc]).astype(int)

        # the DC side unknowns are the positive pole currents at the same converters
        self.u_vsc_ifp = self.u_vsc_pfp.copy()

        # A bipolar VSC sets the voltage as the difference Vfp - Vfn, if not bipolar, only Vfp
        vd = self.nc.vsc_data
        vmdc = ConverterControlType.Vm_dc.idx()
        eligible = vd.active.astype(bool) & (vd.F_dcn > -1)
        on_side1 = eligible & (vd.control1_int == vmdc)
        on_side2 = eligible & (vd.control2_int == vmdc) & ~on_side1
        selected = on_side1 | on_side2

        self.k_vsc_vmdc_diff = np.where(selected)[0].astype(int)
        self.vsc_vmdc_diff_side = np.where(on_side1[selected], 1, 2).astype(int)

        # The regulated pole bus stops being pinned, so Vm[F] becomes an unknown again
        bus_dev = np.where(on_side1, vd.control1_bus_idx, vd.control2_bus_idx)[selected]
        self.is_vm_controlled[bus_dev[bus_dev > -1]] = False

    def _seed_pdc_pole_currents(self) -> None:
        """
        Warm-start the pole currents of the fixed-Pdc converters at
        Ifp = Pdc_set / (Vfp - Vfn) evaluated at the current voltage guess
        (Vfn = 0 for monopolar converters). Converters whose pole-to-pole
        voltage guess is ~0 are left at zero current.
        :return: None
        """
        if len(self.k_vsc_pdc) == 0:
            return
        else:
            kp: IntVec = self.k_vsc_pdc
            f_dcp: IntVec = self.nc.vsc_data.F[kp]
            f_dcn: IntVec = self.nc.vsc_data.F_dcn[kp]

            # signed DC voltages of each pole (angle is 0 or pi on DC buses)
            vdc_p: Vec = self.Vm[f_dcp] * np.cos(self.Va[f_dcp])
            vdc_n: Vec = np.zeros(len(kp))
            has_return = f_dcn > -1
            vdc_n[has_return] = self.Vm[f_dcn[has_return]] * np.cos(self.Va[f_dcn[has_return]])
            vdc_vsc: Vec = vdc_p - vdc_n

            # only seed where the voltage guess gives a usable divisor, i.e. not 0.000x
            valid = np.abs(vdc_vsc) > 1e-12
            if np.any(valid):
                i0: Vec = np.zeros(len(kp))
                i0[valid] = (self.vsc_pdc_set[valid] / self.nc.Sbase) / vdc_vsc[valid]
                self.Ifp_vsc[kp] = i0
            else:
                pass

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

            if self.nc.hvdc_data.control_mode_int[k] == HvdcControlType.type_0_free.idx():
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
        c = b + len(self.u_vsc_ifp)
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
        self.Ifp_vsc[self.u_vsc_ifp] = x[b:c]
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
            self.Ifp_vsc[self.u_vsc_ifp],
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
                + len(self.u_vsc_ifp)
                + len(self.u_vsc_pt)
                + len(self.u_vsc_qt)
                + self.nc.hvdc_data.nelm
                + self.nc.hvdc_data.nelm
                + self.nc.hvdc_data.nelm
                + self.nc.hvdc_data.nelm
                + len(self.u_cbr_m)
                + len(self.u_cbr_tau))

    def _pfp_droop_values(self, V: CxVec) -> Vec:
        """
        Pfp as given by the Pdc voltage-droop law
        :param V: complex bus voltages
        :return: array aligned with self.k_vsc_pfp_droop
        """
        vd = self.nc.vsc_data
        out = np.zeros(len(self.k_vsc_pfp_droop))
        for i in range(len(self.k_vsc_pfp_droop)):
            k = int(self.k_vsc_pfp_droop[i])

            # gather the droop parameters from the side (control1 or control2) that carries them
            if self.vsc_pfp_droop_side[i] == 1:
                u_min: float = vd.control1_droop_val_min[k]
                u_max: float = vd.control1_droop_val_max[k]
                u_set: float = vd.control1_droop_val[k]
                p_set: float = vd.control1_val[k]
                droop: float = vd.control1_val_droop[k]
                p_min: float = vd.control1_val_min[k]
                p_max: float = vd.control1_val_max[k]
            else:
                u_min = vd.control2_droop_val_min[k]
                u_max = vd.control2_droop_val_max[k]
                u_set = vd.control2_droop_val[k]
                p_set = vd.control2_val[k]
                droop = vd.control2_val_droop[k]
                p_min = vd.control2_val_min[k]
                p_max = vd.control2_val_max[k]

            # signed pole voltages: the negative/return pole only exists for bipolar converters
            ut: complex = V[vd.F[k]]
            if vd.F_dcn[k] > -1:
                un: complex = V[vd.F_dcn[k]]
            else:
                un = 0.0 + 0.0j

            # pick the droop law matching the pole polarity
            if ut.real > 0.0:
                out[i] = voltage_pdc_droop(
                    ut=ut, un=un, u_setpoint_min=u_min, u_setpoint_max=u_max, u_setpoint=u_set,
                    Pdc_setpoint=p_set, S_r=vd.rates[k], droop=droop,
                    P_min=p_min, P_max=p_max, S_base=self.nc.Sbase)
            else:
                out[i] = voltage_pdc_droop_neg(
                    ut=ut, un=un, u_setpoint_min=u_min, u_setpoint_max=u_max, u_setpoint=u_set,
                    Pdc_setpoint=p_set, S_r=vd.rates[k], droop=droop,
                    P_min=p_min, P_max=p_max, S_base=self.nc.Sbase)
        return out

    def _vmdc_diff_setpoints(self) -> Vec:
        """
        Pole-to-pole DC voltage setpoints Udc_set for the bipolar Vm_dc converters, aligned with
        self.k_vsc_vmdc_diff. These are signed voltages in pu (no Sbase scaling).
        :return: array aligned with self.k_vsc_vmdc_diff
        """
        vd = self.nc.vsc_data
        out = np.zeros(len(self.k_vsc_vmdc_diff))
        for i in range(len(self.k_vsc_vmdc_diff)):
            k = int(self.k_vsc_vmdc_diff[i])
            out[i] = vd.control1_val[k] if self.vsc_vmdc_diff_side[i] == 1 else vd.control2_val[k]
        return out

    def _pfp_droop_slopes(self) -> Vec:
        """
        Signed slope s * d(Pdc_droop)/du of the Pdc voltage-droop law [pu]
        u = s * (Vfp - Vfn) is the voltage diff and
        s = +1 on a positive pole, -1 on a negative pole
        """
        vd = self.nc.vsc_data
        out = np.zeros(len(self.k_vsc_pfp_droop))
        for i in range(len(self.k_vsc_pfp_droop)):
            k = int(self.k_vsc_pfp_droop[i])
            if self.vsc_pfp_droop_side[i] == 1:
                droop, uset = vd.control1_val_droop[k], vd.control1_droop_val[k]
                umin, umax = vd.control1_droop_val_min[k], vd.control1_droop_val_max[k]
                Pset, Pmin, Pmax = vd.control1_val[k], vd.control1_val_min[k], vd.control1_val_max[k]
            else:
                droop, uset = vd.control2_val_droop[k], vd.control2_droop_val[k]
                umin, umax = vd.control2_droop_val_min[k], vd.control2_droop_val_max[k]
                Pset, Pmin, Pmax = vd.control2_val[k], vd.control2_val_min[k], vd.control2_val_max[k]

            # signed pole voltages, matching _pfp_droop_values
            vdc_p = self.Vm[vd.F[k]] * np.cos(self.Va[vd.F[k]])
            if vd.F_dcn[k] > -1:
                vdc_n = self.Vm[vd.F_dcn[k]] * np.cos(self.Va[vd.F_dcn[k]])
            else:
                vdc_n = 0.0
            if vdc_p > 0.0:
                s = 1.0
            else:
                s = -1.0
            u = s * (vdc_p - vdc_n)

            if umin <= u <= umax:
                P_droop = vd.rates[k] * 100.0 / droop
                Pdc = Pset * self.nc.Sbase - P_droop * (uset - u)
                if Pmin <= Pdc <= Pmax:
                    out[i] = s * P_droop / self.nc.Sbase
        return out

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
        c = b + len(self.u_vsc_ifp)
        d = c + len(self.u_vsc_pt)
        e = d + len(self.u_vsc_qt)
        f = e + nhvdc
        g = f + nhvdc
        h = g + nhvdc
        i = h + nhvdc
        j = i + len(self.u_cbr_m)
        k = j + len(self.u_cbr_tau)

        # copy the sliceable vectors
        Vm_ = self.Vm.copy()
        Va_ = self.Va.copy()
        Ifp_vsc_ = self.Ifp_vsc.copy()
        Pt_vsc_ = self.Pt_vsc.copy()
        Qt_vsc_ = self.Qt_vsc.copy()

        # update the vectors
        Va_[self.i_u_va] = x[0:a]
        Vm_[self.i_u_vm] = x[a:b]
        Ifp_vsc_[self.u_vsc_ifp] = x[b:c]
        Pt_vsc_[self.u_vsc_pt] = x[c:d]
        Qt_vsc_[self.u_vsc_qt] = x[d:e]
        Pf_hvdc_ = x[e:f]
        Pt_hvdc_ = x[f:g]
        Qf_hvdc_ = x[g:h]
        Qt_hvdc_ = x[h:i]
        m_ = x[i:j]
        tau_ = x[j:k]

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

        # Asynchronous Generators --------------------------------------------------------------------------------------
        Qag = compute_asynchronous_generator_q_per_bus(nbus=self.nc.bus_data.nbus,
                                                       V=V,
                                                       gen_bus_idx=self.nc.generator_data.bus_idx,
                                                       gen_active=self.nc.generator_data.active,
                                                       gen_types=self.nc.generator_data.tpe_int,
                                                       Rs=self.nc.generator_data.Rs,
                                                       Xs=self.nc.generator_data.Xs,
                                                       Xm=self.nc.generator_data.Xm,
                                                       Rr=self.nc.generator_data.Rr,
                                                       Xr=self.nc.generator_data.Xr,
                                                       P=self.nc.generator_data.p,
                                                       Snom=self.nc.generator_data.snom)

        # Use V instead of Vm (not a device-centered axis). Thus avoid compute_zip_power()
        # We add self.Y0 despite it being zero
        Sbus = self.S0 + 1j * Qag / self.nc.Sbase + V * np.conj(self.I0) + V * np.conj(V) * np.conj(self.Y0)
        Sbus += 1j * self.static_droop.delta_q_bus(V)
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

        for k in self.k_vsc_qt:

            if self.nc.vsc_data.ysvs[k] != 0.0:

                if self.nc.vsc_data.control1_int[k] == ConverterControlType.Qac.idx():
                    Qt_vsc_[k] = np.abs(V[self.nc.vsc_data.T[k]] ** 2) * self.nc.vsc_data.ysvs[k] / self.nc.Sbase

                elif self.nc.vsc_data.control2_int[k] == ConverterControlType.Qac.idx():
                    Qt_vsc_[k] = np.abs(V[self.nc.vsc_data.T[k]] ** 2) * self.nc.vsc_data.ysvs[k] / self.nc.Sbase

            if self.nc.vsc_data.control1_int[k] == ConverterControlType.Q_droop.idx():
                Qt_vsc_[k] = voltage_q_droop(
                    ut=V[self.nc.vsc_data.T[k]],
                    u_setpoint_min=self.nc.vsc_data.control1_droop_val_min[k],
                    u_setpoint_max=self.nc.vsc_data.control1_droop_val_max[k],
                    u_setpoint=self.nc.vsc_data.control1_droop_val[k],
                    Q_setpoint=self.nc.vsc_data.control1_val[k],
                    S_r=self.nc.vsc_data.rates[k],
                    droop=self.nc.vsc_data.control1_val_droop[k],
                    Q_min=self.nc.vsc_data.control1_val_min[k],
                    Q_max=self.nc.vsc_data.control1_val_max[k],
                    S_base=self.nc.Sbase
                )
            elif self.nc.vsc_data.control2_int[k] == ConverterControlType.Q_droop.idx():
                Qt_vsc_[k] = voltage_q_droop(
                    ut=V[self.nc.vsc_data.T[k]],
                    u_setpoint_min=self.nc.vsc_data.control2_droop_val_min[k],
                    u_setpoint_max=self.nc.vsc_data.control2_droop_val_max[k],
                    u_setpoint=self.nc.vsc_data.control2_droop_val[k],
                    Q_setpoint=self.nc.vsc_data.control2_val[k],
                    S_r=self.nc.vsc_data.rates[k],
                    droop=self.nc.vsc_data.control2_val_droop[k],
                    Q_min=self.nc.vsc_data.control2_val_min[k],
                    Q_max=self.nc.vsc_data.control2_val_max[k],
                    S_base=self.nc.Sbase
                )

        T_vsc = self.nc.vsc_data.T
        Fdcp_vsc = self.nc.vsc_data.F
        Fdcn_vsc = self.nc.vsc_data.F_dcn
        It = np.sqrt(Pt_vsc_ * Pt_vsc_ + Qt_vsc_ * Qt_vsc_) / Vm_[T_vsc]
        It2 = It * It
        PLoss_IEC = (self.nc.vsc_data.alpha3 * It2
                     + self.nc.vsc_data.alpha2 * It
                     + self.nc.vsc_data.alpha1)

        Vdc_p_vsc_ = Vm_[Fdcp_vsc] * np.cos(Va_[Fdcp_vsc])
        Vdc_n_vsc_ = np.zeros(self.nc.vsc_data.nelm)
        has_return = Fdcn_vsc > -1
        Vdc_n_vsc_[has_return] = Vm_[Fdcn_vsc[has_return]] * np.cos(Va_[Fdcn_vsc[has_return]])
        Udc_vsc_ = Vdc_p_vsc_ - Vdc_n_vsc_
        # the return pole carries -Ifp always, just change signs
        Pfp_vsc_ = Vdc_p_vsc_ * Ifp_vsc_
        Pfn_vsc_ = -Vdc_n_vsc_ * Ifp_vsc_

        loss_vsc = PLoss_IEC - Pt_vsc_ - Pfp_vsc_ - Pfn_vsc_
        St_vsc = make_complex(Pt_vsc_, Qt_vsc_)

        # Pdc voltage-droop equation per droop converter: Udc * Ifp - droop(Vdc) = 0
        droop_vsc = Udc_vsc_[self.k_vsc_pfp_droop] * Ifp_vsc_[self.k_vsc_pfp_droop] - self._pfp_droop_values(V)

        # Bipolar Pdc equation: pole-to-return voltage times pole current
        kp = self.k_vsc_pdc
        pdc_vsc = Udc_vsc_[kp] * Ifp_vsc_[kp] - self.vsc_pdc_set / self.nc.Sbase

        # Bipolar Vm_dc pole-to-pole voltage equation: (V[F].real - V[F_dcn].real) - Udc_set = 0
        kk = self.k_vsc_vmdc_diff
        vmdc_diff = ((V[self.nc.vsc_data.F[kk]].real - V[self.nc.vsc_data.F_dcn[kk]].real)
                     - self._vmdc_diff_setpoints())

        # Add the 3rd equation per VSC
        current_vsc = It ** 2 - Imax_vsc ** 2

        # DC Bus Current balance ---------------------------------------------------------------------------------------
        # DC buses use a current eq. instead of a power mismatch to avoid div by 0
        tm[4] = time.time()
        is_dc_indices = self.i_k_p_dc

        I_passive_all = compute_current(adm_.Ybus, V)

        I_conv = calculate_vsc_currents(
            nbus=self.nc.bus_data.nbus,
            Fdcp_vsc=self.nc.vsc_data.F,
            Fdcn_vsc=self.nc.vsc_data.F_dcn,
            Ifp_vsc=Ifp_vsc_
        )

        # The injections of loads and generators at DC buses enter as currents too
        I_injections = np.conj(Sbus[is_dc_indices] / (V[is_dc_indices] + 1e-20))

        dI_dc = (I_conv[is_dc_indices] + I_passive_all[is_dc_indices] - I_injections).real

        # HVDC ---------------------------------------------------------------------------------------------------------
        tm[5] = time.time()

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
        tm[6] = time.time()

        Scalc_active = calc_flows_active_branch_per_bus(
            nbus=self.nc.bus_data.nbus,
            F_hvdc=self.nc.hvdc_data.F,
            T_hvdc=self.nc.hvdc_data.T,
            Sf_hvdc=Sf_hvdc,
            St_hvdc=St_hvdc,
            Fdcp_vsc=self.nc.vsc_data.F,
            Fdcn_vsc=self.nc.vsc_data.F_dcn,
            T_vsc=self.nc.vsc_data.T,
            Vm=Vm_,
            Va=Va_,
            Ifp_vsc=Ifp_vsc_,
            St_vsc=St_vsc)

        Scalc_ = Scalc_active + Scalc_passive

        dS = Scalc_ - Sbus

        # compose the residuals vector ---------------------------------------------------------------------------------
        tm[7] = time.time()

        f_ = np.r_[
            dS[self.i_k_p].real,
            dS[self.i_k_q].imag,
            loss_vsc,
            current_vsc[self.k_vsc_i],
            droop_vsc,
            pdc_vsc,
            vmdc_diff,
            dI_dc,
            loss_hvdc,
            inj_hvdc,
            Pf_cbr - self.cbr_pf_set,
            Pt_cbr - self.cbr_pt_set,
            Qf_cbr - self.cbr_qf_set,
            Qt_cbr - self.cbr_qt_set
        ]

        tm[8] = time.time()

        if update_class_vars:
            self._Va = Va_
            self._Vm = Vm_
            self.Ifp_vsc = Ifp_vsc_
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

        if self.options.verbose > 1:
            print('residual = \n', f_)

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
        # print('error = ', self._error)

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

            # discrete shunt logic
            if self.discrete_shunt_control.apply(Vm=self.Vm, adm=self.adm):
                any_change = True

            if self.qv_droop_control.apply(S0=self.S0, Vm=self.Vm):
                any_change = True

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
                        self.nc.active_branch_data.tap_module_control_mode[k] = TapModuleControl.fixed.idx()
                        self.nc.active_branch_data.tap_module[k] = self.m[i]

                        branch_ctrl_change = True
                        self.logger.add_info("Min tap module reached",
                                             device=self.nc.passive_branch_data.names[k],
                                             value=self.m[i])

                    elif self.m[i] > self.nc.active_branch_data.tap_module_max[k]:
                        self.m[i] = self.nc.active_branch_data.tap_module_max[k]
                        m_fixed_idx.append(i)

                        # self.tap_module_control_mode[k] = TapModuleControl.fixed
                        self.nc.active_branch_data.tap_module_control_mode[k] = TapModuleControl.fixed.idx()
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

                        self.nc.active_branch_data.tap_phase_control_mode[k] = TapPhaseControl.fixed.idx()
                        self.nc.active_branch_data.tap_angle[k] = self.tau[i]

                        branch_ctrl_change = True
                        self.logger.add_info("Min tap phase reached",
                                             device=self.nc.passive_branch_data.names[k],
                                             value=self.tau[i])

                    elif self.tau[i] > self.nc.active_branch_data.tap_angle_max[k]:
                        self.tau[i] = self.nc.active_branch_data.tap_angle_max[k]
                        tau_fixed_idx.append(i)

                        self.nc.active_branch_data.tap_phase_control_mode[k] = TapPhaseControl.fixed.idx()
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

                    It_i = np.sqrt(self.Pt_vsc[i] ** 2 + self.Qt_vsc[i] ** 2) / self.Vm[self.nc.vsc_data.T[i]]
                    Imax = self.nc.vsc_data.rates[i] / self.nc.Sbase  # Assume 1.0 p.u. base voltage

                    # print(f"Josep current: {It_i}, Imax: {Imax}")

                    if (It_i > Imax
                            and self.nc.vsc_data.control1_int[i] != ConverterControlType.Imax.idx()
                            and self.nc.vsc_data.control2_int[i] != ConverterControlType.Imax.idx()):

                        self.logger.add_info("VSC current limit reached",
                                             device=self.nc.vsc_data.names[i],
                                             value=It_i)

                        if self.nc.vsc_data.control1_int[i] == ConverterControlType.Vm_ac.idx():
                            self.nc.bus_data.is_vm_controlled[self.nc.vsc_data.T[i]] = False
                            self.nc.vsc_data.control1_int[i] = ConverterControlType.Imax.idx()
                            self.nc.vsc_data.control1_val[i] = Imax
                            self.nc.vsc_data.control1_branch_idx[i] = i
                            branch_ctrl_change = True
                        elif self.nc.vsc_data.control2_int[i] == ConverterControlType.Vm_ac.idx():
                            self.nc.bus_data.is_vm_controlled[self.nc.vsc_data.T[i]] = False
                            self.nc.vsc_data.control2_int[i] = ConverterControlType.Imax.idx()
                            self.nc.vsc_data.control2_val[i] = Imax
                            self.nc.vsc_data.control2_branch_idx[i] = i
                            branch_ctrl_change = True
                        elif self.nc.vsc_data.control1_int[i] in (ConverterControlType.Pdc.idx(),
                                                                  ConverterControlType.Pdc_droop.idx()):
                            self.nc.vsc_data.control1_int[i] = ConverterControlType.Imax.idx()
                            self.nc.vsc_data.control1_val[i] = Imax
                            self.nc.vsc_data.control1_branch_idx[i] = i
                            branch_ctrl_change = True
                        elif self.nc.vsc_data.control2_int[i] in (ConverterControlType.Pdc.idx(),
                                                                  ConverterControlType.Pdc_droop.idx()):
                            self.nc.vsc_data.control2_int[i] = ConverterControlType.Imax.idx()
                            self.nc.vsc_data.control2_val[i] = Imax
                            self.nc.vsc_data.control2_branch_idx[i] = i
                            branch_ctrl_change = True
                        elif self.nc.vsc_data.control1_int[i] == ConverterControlType.Pac.idx():
                            self.nc.vsc_data.control1_int[i] = ConverterControlType.Imax.idx()
                            self.nc.vsc_data.control1_val[i] = Imax
                            self.nc.vsc_data.control1_branch_idx[i] = i
                            branch_ctrl_change = True
                        elif self.nc.vsc_data.control2_int[i] == ConverterControlType.Pac.idx():
                            self.nc.vsc_data.control2_int[i] = ConverterControlType.Imax.idx()
                            self.nc.vsc_data.control2_val[i] = Imax
                            self.nc.vsc_data.control2_branch_idx[i] = i
                            branch_ctrl_change = True
                        elif self.nc.vsc_data.control1_int[i] == ConverterControlType.Qac.idx():
                            self.nc.vsc_data.control1_int[i] = ConverterControlType.Imax.idx()
                            self.nc.vsc_data.control1_val[i] = Imax
                            self.nc.vsc_data.control1_branch_idx[i] = i
                            branch_ctrl_change = True
                        elif self.nc.vsc_data.control2_int[i] == ConverterControlType.Qac.idx():
                            self.nc.vsc_data.control2_int[i] = ConverterControlType.Imax.idx()
                            self.nc.vsc_data.control2_val[i] = Imax
                            self.nc.vsc_data.control2_branch_idx[i] = i
                            branch_ctrl_change = True
                        elif self.nc.vsc_data.control1_int[i] == ConverterControlType.Vm_dc.idx():
                            self.nc.bus_data.is_vm_controlled[self.nc.vsc_data.F[i]] = False
                            self.nc.vsc_data.control1_int[i] = ConverterControlType.Imax.idx()
                            self.nc.vsc_data.control1_val[i] = Imax
                            self.nc.vsc_data.control1_branch_idx[i] = i
                            branch_ctrl_change = True
                        elif self.nc.vsc_data.control2_int[i] == ConverterControlType.Vm_dc.idx():
                            self.nc.bus_data.is_vm_controlled[self.nc.vsc_data.F[i]] = False
                            self.nc.vsc_data.control2_int[i] = ConverterControlType.Imax.idx()
                            self.nc.vsc_data.control2_val[i] = Imax
                            self.nc.vsc_data.control2_branch_idx[i] = i
                            branch_ctrl_change = True
                        elif self.nc.vsc_data.control1_int[i] == ConverterControlType.Va_ac.idx():
                            self.nc.bus_data.is_va_controlled[self.nc.vsc_data.T[i]] = False
                            self.nc.vsc_data.control1_int[i] = ConverterControlType.Imax.idx()
                            self.nc.vsc_data.control1_val[i] = Imax
                            self.nc.vsc_data.control1_branch_idx[i] = i
                            branch_ctrl_change = True
                        elif self.nc.vsc_data.control2_int[i] == ConverterControlType.Va_ac.idx():
                            self.nc.bus_data.is_va_controlled[self.nc.vsc_data.T[i]] = False
                            self.nc.vsc_data.control2_int[i] = ConverterControlType.Imax.idx()
                            self.nc.vsc_data.control2_val[i] = Imax
                            self.nc.vsc_data.control2_branch_idx[i] = i
                            branch_ctrl_change = True
                        else:
                            raise ValueError(f"Unfound control type when switching to current limiting: "
                                             f"{self.nc.vsc_data.control1_int[i]}")

                        # print(It_i, Imax)

                        # Potentially add new conditionals, mainly for the 2nd iteration once saturated
                        # If letting the P naturally go to zero is not enough, no longer control Vm
                        # Control Q and then it will naturally get to a point that does not surpass Imax

                    elif (It_i > Imax * 1.1
                          and self.nc.vsc_data.control1_int[i] == ConverterControlType.Imax.idx()
                          and self.nc.vsc_data.control2_int[i] == ConverterControlType.Imax.idx()):
                        """
                        We give some margin to the current because it may not exactly converge to Imax
                        in just one iteration. 10% buffer seems enough.
                        
                        We establish reactive power priority over active power
                        So if we are already controlling Imax, set the P to zero
                        As a last resort, set Q to zero
                        """

                        if self.nc.vsc_data.control1_int[i] in (ConverterControlType.Pdc.idx(),
                                                                ConverterControlType.Pdc_droop.idx()):
                            self.nc.vsc_data.control1_val[i] = 0.0
                        elif self.nc.vsc_data.control2_int[i] in (ConverterControlType.Pdc.idx(),
                                                                  ConverterControlType.Pdc_droop.idx()):
                            self.nc.vsc_data.control2_val[i] = 0.0
                        elif self.nc.vsc_data.control1_int[i] == ConverterControlType.Pac.idx():
                            self.nc.vsc_data.control1_val[i] = 0.0
                        elif self.nc.vsc_data.control2_int[i] == ConverterControlType.Pac.idx():
                            self.nc.vsc_data.control2_val[i] = 0.0
                        elif self.nc.vsc_data.control1_int[i] == ConverterControlType.Qac.idx():
                            self.nc.vsc_data.control1_val[i] = 0.0
                        elif self.nc.vsc_data.control2_int[i] == ConverterControlType.Qac.idx():
                            self.nc.vsc_data.control2_val[i] = 0.0
                        else:
                            raise ValueError(f"Unfound control type when switching to current limiting: "
                                             f"{self.nc.vsc_data.control1_int[i]}")

                    # print(f"VSC {i} control 1: {self.nc.vsc_data.control1[i]}")
                    print(f"VSC {i} control 2: {self.nc.vsc_data.control2_int[i]}")

            # Check minimum AC voltage threshold for VSC disconnection
            n_disconnected_vscs = 0
            for i in range(self.nc.nvsc):

                if self.nc.vsc_data.active[i]:

                    ac_bus_idx = self.nc.vsc_data.T[i]
                    ac_voltage = self.Vm[ac_bus_idx]
                    min_v = self.nc.vsc_data.min_ac_voltage[i]

                    if ac_voltage < min_v:
                        # Switch controls to Pac=0, Qac=0 to effectively disconnect the VSC
                        # while keeping it active in the system (avoids size mismatch issues)
                        control1 = self.nc.vsc_data.control1_int[i]
                        control2 = self.nc.vsc_data.control2_int[i]
                        ctrl1_bus = self.nc.vsc_data.control1_bus_idx[i]
                        ctrl2_bus = self.nc.vsc_data.control2_bus_idx[i]

                        # Release bus voltage/angle control flags for current controls
                        if control1 in (ConverterControlType.Vm_dc.idx(), ConverterControlType.Vm_ac.idx()):
                            if ctrl1_bus > -1:
                                self.nc.bus_data.is_vm_controlled[ctrl1_bus] = False
                        elif control1 == ConverterControlType.Va_ac.idx():
                            if ctrl1_bus > -1:
                                self.nc.bus_data.is_va_controlled[ctrl1_bus] = False

                        if control2 in (ConverterControlType.Vm_dc.idx(), ConverterControlType.Vm_ac.idx()):
                            if ctrl2_bus > -1:
                                self.nc.bus_data.is_vm_controlled[ctrl2_bus] = False
                        elif control2 == ConverterControlType.Va_ac.idx():
                            if ctrl2_bus > -1:
                                self.nc.bus_data.is_va_controlled[ctrl2_bus] = False

                        branch_ctrl_change = True

                        # Switch to Pac=0, Qac=0
                        self.nc.vsc_data.control1_int[i] = ConverterControlType.Pac.idx()
                        self.nc.vsc_data.control1_val[i] = 0.0
                        self.nc.vsc_data.control1_branch_idx[i] = i
                        self.nc.vsc_data.control1_bus_idx[i] = -1

                        self.nc.vsc_data.control2_int[i] = ConverterControlType.Qac.idx()
                        self.nc.vsc_data.control2_val[i] = 0.0
                        self.nc.vsc_data.control2_branch_idx[i] = i
                        self.nc.vsc_data.control2_bus_idx[i] = -1

                        n_disconnected_vscs += 1

                        self.logger.add_info("VSC disconnected due to low AC voltage (Pac=0, Qac=0)",
                                             device=self.nc.vsc_data.names[i],
                                             value=ac_voltage)

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

                # re-apply the VSC setpoints after the control indices have been rebuilt
                if n_disconnected_vscs > 0:
                    self._seed_pdc_pole_currents()
                    self.Pt_vsc[self.k_vsc_pt] = self.vsc_pt_set / self.nc.Sbase
                    self.Qt_vsc[self.k_vsc_qt] = self.vsc_qt_set / self.nc.Sbase

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
        Sbus += 1j * self.static_droop.delta_q_bus(V)
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
        Fdcp_vsc = self.nc.vsc_data.F
        Fdcn_vsc = self.nc.vsc_data.F_dcn
        It = np.sqrt(self.Pt_vsc * self.Pt_vsc + self.Qt_vsc * self.Qt_vsc) / self.Vm[T_vsc]
        It2 = It * It
        PLoss_IEC = (self.nc.vsc_data.alpha3 * It2
                     + self.nc.vsc_data.alpha2 * It
                     + self.nc.vsc_data.alpha1)

        Vdc_p_vsc = self.Vm[Fdcp_vsc] * np.cos(self.Va[Fdcp_vsc])
        Vdc_n_vsc = np.zeros(self.nc.vsc_data.nelm)
        has_return = Fdcn_vsc > -1
        Vdc_n_vsc[has_return] = self.Vm[Fdcn_vsc[has_return]] * np.cos(self.Va[Fdcn_vsc[has_return]])
        Udc_vsc = Vdc_p_vsc - Vdc_n_vsc
        # the return pole carries -Ifp structurally, hence Pfn = -Vfn * Ifp
        Pfp_vsc = Vdc_p_vsc * self.Ifp_vsc
        Pfn_vsc = -Vdc_n_vsc * self.Ifp_vsc

        loss_vsc = PLoss_IEC - self.Pt_vsc - Pfp_vsc - Pfn_vsc

        # Pdc voltage-droop equation per droop converter: Udc * Ifp - droop(Vdc) = 0
        droop_vsc = Udc_vsc[self.k_vsc_pfp_droop] * self.Ifp_vsc[self.k_vsc_pfp_droop] - self._pfp_droop_values(V)

        # Bipolar Pdc equation: pole-to-return voltage times pole current
        kp = self.k_vsc_pdc
        pdc_vsc = Udc_vsc[kp] * self.Ifp_vsc[kp] - self.vsc_pdc_set / self.nc.Sbase

        # Bipolar Vm_dc pole-to-pole voltage equation: (V[F].real - V[F_dcn].real) - Udc_set = 0
        kk = self.k_vsc_vmdc_diff
        vmdc_diff = (V[Fdcp_vsc[kk]].real - V[Fdcn_vsc[kk]].real) - self._vmdc_diff_setpoints()

        current_vsc = It ** 2 - Imax_vsc ** 2

        St_vsc = make_complex(self.Pt_vsc, self.Qt_vsc)

        # DC Bus Current balance ---------------------------------------------------------------------------------------
        # DC buses use a current mismatch instead of a power mismatch (see compute_f)
        is_dc_indices = self.i_k_p_dc

        I_passive_all = compute_current(self.adm.Ybus, V)

        I_conv = calculate_vsc_currents(
            nbus=self.nc.bus_data.nbus,
            Fdcp_vsc=Fdcp_vsc,
            Fdcn_vsc=Fdcn_vsc,
            Ifp_vsc=self.Ifp_vsc
        )

        I_injections = np.conj(Sbus[is_dc_indices] / (V[is_dc_indices] + 1e-20))

        dI_dc = (I_conv[is_dc_indices] + I_passive_all[is_dc_indices] - I_injections).real

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
            Fdcp_vsc=Fdcp_vsc,
            Fdcn_vsc=Fdcn_vsc,
            T_vsc=T_vsc,
            Vm=self.Vm,
            Va=self.Va,
            Ifp_vsc=self.Ifp_vsc,
            St_vsc=St_vsc)

        self.Scalc = Scalc_active + Scalc_passive

        dS = self.Scalc - Sbus

        # compose the residuals vector ---------------------------------------------------------------------------------
        self._f = np.r_[
            dS[self.i_k_p].real,
            dS[self.i_k_q].imag,
            loss_vsc,
            current_vsc[self.k_vsc_i],
            droop_vsc,
            pdc_vsc,
            vmdc_diff,
            dI_dc,
            dloss_hvdc,
            dinj_hvdc,
            Pf_cbr - self.cbr_pf_set,
            Pt_cbr - self.cbr_pt_set,
            Qf_cbr - self.cbr_qf_set,
            Qt_cbr - self.cbr_qt_set
        ]

        return self._f

    def Jacobian(self, autodiff: Union[bool, None] = None) -> CSC:
        """
        Get the Jacobian of the current-based AC/DC formulation.
        :param autodiff: use the finite-difference Jacobian
        :return: Jacobian matrix in CSC format
        """
        if autodiff is None:
            autodiff = self.use_autodiff_jacobian

        if autodiff:
            # TODO: SANPEN: And what if the Jacobian is not complete because we haven't computed the derivatives and we want the autodiff for debugging? Again, AI Slop
            sparsity: CSC = self.Jacobian(autodiff=False)
            J: CSC = calc_autodiff_jacobian(func=self.compute_f,
                                            x=self.var2x(),
                                            sparsity=sparsity,
                                            h=1e-7)
            return J
        else:
            # expanded tap arrays
            tap_modules = expand(self.nc.nbr, self.m, self.u_cbr_m, 1.0)
            tap_angles = expand(self.nc.nbr, self.tau, self.u_cbr_tau, 0.0)

            # HVDC parameters
            nhvdc = self.nc.hvdc_data.nelm
            hvdc_r_pu = self.nc.hvdc_data.r / (self.nc.hvdc_data.Vnf * self.nc.hvdc_data.Vnf / self.nc.Sbase)
            hvdc_droop_redone = np.zeros(nhvdc, dtype=float)
            if len(self.hvdc_droop_idx) > 0:
                hvdc_droop_redone[self.hvdc_droop_idx] = self.nc.hvdc_data.angle_droop[self.hvdc_droop_idx]

            # rebuild the phasor from the current Vm/Va
            V: CxVec = polar_to_rect(self.Vm, self.Va)

            # signed DC voltages per bus and pole-to-return per converter
            vd = self.nc.vsc_data
            Vdc_bus: Vec = self.Vm * np.cos(self.Va)
            Udc_vsc: Vec = Vdc_bus[vd.F].copy()
            has_return = vd.F_dcn > -1
            Udc_vsc[has_return] -= Vdc_bus[vd.F_dcn[has_return]]

            # voltage sensitivity factors of the Udc * Ifp equations
            pdc_factor: Vec = self.Ifp_vsc[self.k_vsc_pdc].copy()
            droop_factor: Vec = self.Ifp_vsc[self.k_vsc_pfp_droop] - self._pfp_droop_slopes()

            # DC current-balance rows and the injection sensitivities
            dc_rows: IntVec = self.i_k_p_dc

            assert isspmatrix_csc(self.adm.Ybus)

            J_sym: CSC = adv_jacobian(
                nbus=self.nc.nbus,
                nbr=self.nc.nbr,
                nvsc=vd.nelm,
                nhvdc=nhvdc,
                F=self.nc.passive_branch_data.F,
                T=self.nc.passive_branch_data.T,
                Fdcp_vsc=vd.F,
                Fdcn_vsc=vd.F_dcn,
                T_vsc=vd.T,
                F_hvdc=self.nc.hvdc_data.F,
                T_hvdc=self.nc.hvdc_data.T,
                tap_angles=tap_angles,
                tap_modules=tap_modules,
                V=V,
                Vm=self.Vm,
                Va=self.Va,
                I0=self.I0,
                u_cbr_m=self.u_cbr_m,
                u_cbr_tau=self.u_cbr_tau,
                k_cbr_pf=self.k_cbr_pf,
                k_cbr_pt=self.k_cbr_pt,
                k_cbr_qf=self.k_cbr_qf,
                k_cbr_qt=self.k_cbr_qt,
                u_vsc_ifp=self.u_vsc_ifp,
                u_vsc_pt=self.u_vsc_pt,
                u_vsc_qt=self.u_vsc_qt,
                k_vsc_imax=self.k_vsc_i,
                alpha2=vd.alpha2,
                alpha3=vd.alpha3,
                hvdc_r=hvdc_r_pu,
                hvdc_droop=hvdc_droop_redone,
                i_u_vm=self.i_u_vm,
                i_u_va=self.i_u_va,
                i_k_p=self.i_k_p,
                i_k_q=self.i_k_q,
                Ifp_vsc=self.Ifp_vsc,
                Udc_vsc=Udc_vsc,
                k_vsc_pfp_droop=self.k_vsc_pfp_droop,
                droop_factor=droop_factor,
                k_vsc_pdc=self.k_vsc_pdc,
                pdc_factor=pdc_factor,
                k_vsc_vmdc_diff=self.k_vsc_vmdc_diff,
                dc_rows=dc_rows,
                Vdc_bus=Vdc_bus,
                S0r=self.S0.real,
                Y0r=self.Y0.real,
                Pt_vsc=self.Pt_vsc,
                Qt_vsc=self.Qt_vsc,
                Pf_hvdc=self.Pf_hvdc,
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

        cols += [f'dIfp_vsc_{i}' for i in self.u_vsc_ifp]
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
        bus_dc = self.i_k_p_dc

        rows = [f'dP_{i}' for i in self.i_k_p]
        rows += [f'dQ_{i}' for i in self.i_k_q]
        rows += [f'dloss_vsc_{i}' for i in range(self.nc.vsc_data.nelm)]
        rows += [f'dImax_vsc_{i}' for i in self.k_vsc_i]
        rows += [f'ddroop_vsc_{i}' for i in self.k_vsc_pfp_droop]
        rows += [f'dpdc_vsc_{i}' for i in self.k_vsc_pdc]
        rows += [f'dvmdc_diff_{i}' for i in self.k_vsc_vmdc_diff]
        rows += [f'dI_{i}' for i in bus_dc]
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

        Fdcp = self.nc.vsc_data.F
        Fdcn = self.nc.vsc_data.F_dcn
        Vdc_p_vsc = self.Vm[Fdcp] * np.cos(self.Va[Fdcp])
        Vdc_n_vsc = np.zeros(self.nc.vsc_data.nelm)
        has_return = Fdcn > -1
        Vdc_n_vsc[has_return] = self.Vm[Fdcn[has_return]] * np.cos(self.Va[Fdcn[has_return]])
        Pfp_vsc_pu = self.Ifp_vsc * Vdc_p_vsc
        Pfn_vsc_pu = -self.Ifp_vsc * Vdc_n_vsc

        Pfp_vsc = Pfp_vsc_pu * self.nc.Sbase
        Pfn_vsc = Pfn_vsc_pu * self.nc.Sbase
        Vfn = np.where(Fdcn > -1, self.V[Fdcn].real, 0.0)
        Vdc_vsc = self.V[Fdcp].real - Vfn
        St_vsc = make_complex(self.Pt_vsc, self.Qt_vsc) * self.nc.Sbase
        If_vsc = self.Ifp_vsc  # the positive pole current is a solver unknown now
        It_vsc = make_complex(self.Pt_vsc, self.Qt_vsc) / self.Vm[self.nc.vsc_data.T]
        Uac_vsc = self.V[self.nc.vsc_data.T]
        loading_vsc = np.abs(make_complex(self.Pt_vsc, self.Qt_vsc) / Uac_vsc + 1e-20) / (
                self.nc.vsc_data.rates / self.nc.Sbase + 1e-20)
        losses_vsc = (self.Pt_vsc + self.Ifp_vsc * (Vdc_p_vsc - Vdc_n_vsc)) * self.nc.Sbase

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
            Pfp_vsc=Pfp_vsc,
            Pfn_vsc=Pfn_vsc,
            St_vsc=St_vsc)

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
            Pfp_vsc=Pfp_vsc,
            Pfn_vsc=Pfn_vsc,
            Vdc_vsc=Vdc_vsc,
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
