# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import time
from typing import Tuple, List, Callable, Union
import numpy as np
import pandas as pd
import scipy as sp
from numba import njit
from scipy.sparse import diags, csc_matrix
from scipy.sparse import lil_matrix
from GridCalEngine.Topology.admittance_matrices import compute_admittances
from GridCalEngine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
from GridCalEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCalEngine.DataStructures.numerical_circuit import NumericalCircuit
import GridCalEngine.Simulations.Derivatives.csc_derivatives as deriv
from GridCalEngine.Utils.Sparse.csc2 import CSC, CxCSC, scipy_to_mat, mat_to_scipy, sp_slice, csc_stack_2d_ff, \
    scipy_to_cxmat 
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.common_functions import expand
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.common_functions import compute_fx_error
from GridCalEngine.Simulations.PowerFlow.Formulations.pf_formulation_template import PfFormulationTemplate
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.common_functions import (compute_zip_power, compute_power,
                                                                                   compute_fx, polar_to_rect)
from GridCalEngine.enumerations import (TapPhaseControl, TapModuleControl, BusMode, HvdcControlType,
                                        ConverterControlType)
from GridCalEngine.basic_structures import Vec, IntVec, CxVec, BoolVec, Logger
from GridCalEngine.Simulations.Derivatives.matpower_derivatives import dSbus_dV_matpower


# @njit()
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
                 R: Vec,
                 X: Vec,
                 G: Vec,
                 B: Vec,
                 k: Vec,
                 Ys: CxVec,
                 tap_angles: Vec,
                 tap_modules: Vec,
                 vtap_f: Vec,
                 vtap_t: Vec,
                 Bc: Vec,
                 V: CxVec,
                 Vm: Vec,
                adm,

                 # Controllable Branch Indices
                 u_cbr_m: IntVec,
                 u_cbr_tau: IntVec,
                 cbr: IntVec,
                 k_cbr_pf: IntVec,
                 k_cbr_pt: IntVec,
                 k_cbr_qf: IntVec,
                 k_cbr_qt: IntVec,
                 cbr_pf_set: Vec,
                 cbr_pt_set: Vec,
                 cbr_qf_set: Vec,
                 cbr_qt_set: Vec,

                 # VSC Indices
                 u_vsc_pf: IntVec,
                 u_vsc_pt: IntVec,
                 u_vsc_qt: IntVec,
                 k_vsc_pf: IntVec,
                 k_vsc_pt: IntVec,
                 k_vsc_qt: IntVec,
                 vsc_pf_set: Vec,
                 vsc_pt_set: Vec,
                 vsc_qt_set: Vec,

                 #VSC Params
                 alpha1: Vec,
                 alpha2: Vec,
                 alpha3: Vec,

                 # HVDC Indices
                 hvdc_droop_idx: IntVec,

                 # HVDC Params
                 hvdc_r,
                 hvdc_pset,
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
                 Qf_hvdc: Vec,
                 Pt_hvdc: Vec,
                 Qt_hvdc: Vec,

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
                 conn_vsc_F: CSC,
                 conn_vsc_T: CSC,
                 conn_hvdc_F: CSC,
                 conn_hvdc_T: CSC,
                 Ybus: CSC) -> CSC:
    """
    Compute the advanced jacobian
    :param nbus:
    :param nbr:
    :param F:
    :param T:
    :param kconv:
    :param complex_tap:
    :param tap_modules:
    :param Bc:
    :param V:
    :param Vm:

    :param u_cbr_m:
    :param u_cbr_tau:
    :param cbr:
    :param k_cbr_pf:
    :param k_cbr_pt:
    :param k_cbr_qf:
    :param k_cbr_qt:
    :param cbr_pf_set:
    :param cbr_pt_set:
    :param cbr_qf_set:
    :param cbr_qt_set:

    :param u_vsc_pf:
    :param u_vsc_pt:
    :param u_vsc_qt:
    :param k_vsc_pf:
    :param k_vsc_pt:
    :param k_vsc_qt:
    :param vsc_pf_set:
    :param vsc_pt_set:
    :param vsc_qt_set:

    :param hvdc_droop_idx:

    :param i_u_vm:
    :param i_u_va:
    :param i_k_p:
    :param i_k_q:

    :param Pf_vsc:
    :param Pt_vsc:
    :param Qt_vsc:
    :param Pf_hvdc:
    :param Qf_hvdc:
    :param Pt_hvdc:
    :param Qt_hvdc:

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
    :param Ybus:
    :return:
    """
    tap = polar_to_rect(tap_modules, tap_angles)

    # bus-bus derivatives (always needed)
    
    # passive admittance contribution
    dSy_dVm_x, dSy_dVa_x = deriv.dSbus_dV_numba_sparse_csc(Yx=Ybus.data, Yp=Ybus.indptr, Yi=Ybus.indices, V=V, Vm=Vm)
    dSy_dVm = CxCSC(nbus, nbus, len(dSy_dVm_x), False).set(Ybus.indices, Ybus.indptr, dSy_dVm_x)
    dSy_dVa = CxCSC(nbus, nbus, len(dSy_dVa_x), False).set(Ybus.indices, Ybus.indptr, dSy_dVa_x)

    # active transformers contribution
    # being tap = m exp(j*tau) and tap_modules = m
    dScbr_dVm = deriv.dSbr_dVm_csc(nbus, cbr, F_cbr, T_cbr, yff_cbr, yft_cbr, ytf_cbr, ytt_cbr, yff0, yft0, ytf0, ytt0, V, tap, tap_modules)
    dScbr_dVa = deriv.dSbr_dVa_csc(nbus, cbr, F_cbr, T_cbr, yff_cbr, yft_cbr, ytf_cbr, ytt_cbr, yff0, yft0, ytf0, ytt0, V, tap, tap_modules)

    # -------------
    # # try addition with coo to check
    # dSy_dVm_coo = CSC((dSy_dVm.real.data, dSy_dVm.indices, dSy_dVm.indptr), shape=(nbus, nbus))
    # dSy_dVa_coo = dSy_dVa.to_coo()
    # dScbr_dVm_coo = dScbr_dVm.to_coo()
    # dScbr_dVa_coo = dScbr_dVa.to_coo()

    # dS_dVm = dSy_dVm_coo + dScbr_dVm_coo
    # dS_dVa = dSy_dVa_coo + dScbr_dVa_coo  # check if implemented for complex

    # -------------

    # Sum not working well!! Try adding real + real and imag + imag
    # dS_dVm = deriv.csc_add_wrapper(dSy_dVm, dScbr_dVm)
    # dS_dVa = deriv.csc_add_wrapper(dSy_dVa, dScbr_dVa)

    # convert to regular csc_matrix to handle the sum
    dSy_dVm_r = csc_matrix((dSy_dVm.real.data, dSy_dVm.indices, dSy_dVm.indptr), shape=(dSy_dVm.n_rows, dSy_dVm.n_cols))
    dSy_dVa_r = csc_matrix((dSy_dVa.real.data, dSy_dVa.indices, dSy_dVa.indptr), shape=(dSy_dVa.n_rows, dSy_dVa.n_cols))
    dScbr_dVm_r = csc_matrix((dScbr_dVm.real.data, dScbr_dVm.indices, dScbr_dVm.indptr), shape=(dScbr_dVm.n_rows, dScbr_dVm.n_cols))
    dScbr_dVa_r = csc_matrix((dScbr_dVa.real.data, dScbr_dVa.indices, dScbr_dVa.indptr), shape=(dScbr_dVa.n_rows, dScbr_dVa.n_cols))

    dSy_dVm_i = csc_matrix((dSy_dVm.imag.data, dSy_dVm.indices, dSy_dVm.indptr), shape=(dSy_dVm.n_rows, dSy_dVm.n_cols))
    dSy_dVa_i = csc_matrix((dSy_dVa.imag.data, dSy_dVa.indices, dSy_dVa.indptr), shape=(dSy_dVa.n_rows, dSy_dVa.n_cols))
    dScbr_dVm_i = csc_matrix((dScbr_dVm.imag.data, dScbr_dVm.indices, dScbr_dVm.indptr), shape=(dScbr_dVm.n_rows, dScbr_dVm.n_cols))
    dScbr_dVa_i = csc_matrix((dScbr_dVa.imag.data, dScbr_dVa.indices, dScbr_dVa.indptr), shape=(dScbr_dVa.n_rows, dScbr_dVa.n_cols))

    # dSy_dVm_r = dSy_dVm.real
    # dSy_dVa_r = dSy_dVa.real
    # dScbr_dVm_r = dScbr_dVm.real
    # dScbr_dVa_r = dScbr_dVa.real

    # dSy_dVm_i = dSy_dVm.imag
    # dSy_dVa_i = dSy_dVa.imag
    # dScbr_dVm_i = dScbr_dVm.imag
    # dScbr_dVa_i = dScbr_dVa.imag

    # dS_dVm_r = csc_add_ff2_wrapper(dSy_dVm_r, dScbr_dVm_r)
    # dS_dVa_r = csc_add_ff2_wrapper(dSy_dVa_r, dScbr_dVa_r)
    # dS_dVm_i = csc_add_ff2_wrapper(dSy_dVm_i, dScbr_dVm_i)
    # dS_dVa_i = csc_add_ff2_wrapper(dSy_dVa_i, dScbr_dVa_i)

    dS_dVm_r0 = dSy_dVm_r + dScbr_dVm_r
    dS_dVa_r0 = dSy_dVa_r + dScbr_dVa_r
    dS_dVm_i0 = dSy_dVm_i + dScbr_dVm_i
    dS_dVa_i0 = dSy_dVa_i + dScbr_dVa_i

    dS_dVm_r = CSC(n_rows=dS_dVm_r0.shape[0], n_cols=dS_dVm_r0.shape[1], nnz=len(dS_dVm_r0.data), force_zeros=False)
    dS_dVm_r.set(dS_dVm_r0.indices, dS_dVm_r0.indptr, dS_dVm_r0.data)

    dS_dVa_r = CSC(n_rows=dS_dVa_r0.shape[0], n_cols=dS_dVa_r0.shape[1], nnz=len(dS_dVa_r0.data), force_zeros=False)
    dS_dVa_r.set(dS_dVa_r0.indices, dS_dVa_r0.indptr, dS_dVa_r0.data)

    dS_dVm_i = CSC(n_rows=dS_dVm_i0.shape[0], n_cols=dS_dVm_i0.shape[1], nnz=len(dS_dVm_i0.data), force_zeros=False)
    dS_dVm_i.set(dS_dVm_i0.indices, dS_dVm_i0.indptr, dS_dVm_i0.data)

    dS_dVa_i = CSC(n_rows=dS_dVa_i0.shape[0], n_cols=dS_dVa_i0.shape[1], nnz=len(dS_dVa_i0.data), force_zeros=False)
    dS_dVa_i.set(dS_dVa_i0.indices, dS_dVa_i0.indptr, dS_dVa_i0.data)

    # dP_dVm__ = sp_slice(dS_dVm.real, i_k_p, i_u_vm)
    # dQ_dVm__ = sp_slice(dS_dVm.imag, i_k_q, i_u_vm)

    # dP_dVa__ = sp_slice(dS_dVa.real, i_k_p, i_u_va)
    # dQ_dVa__ = sp_slice(dS_dVa.imag, i_k_q, i_u_va)

    dP_dVm__ = sp_slice(dS_dVm_r, i_k_p, i_u_vm)
    dQ_dVm__ = sp_slice(dS_dVm_i, i_k_q, i_u_vm)

    dP_dVa__ = sp_slice(dS_dVa_r, i_k_p, i_u_va)
    dQ_dVa__ = sp_slice(dS_dVa_i, i_k_q, i_u_va)


    # -------------------

    # dScbr_dm = deriv.dSbr_dm_csc(nbus, u_cbr_m, F_cbr, T_cbr, yff_cbr, yft_cbr, ytf_cbr, ytt_cbr, V, tap, tap_modules)
    # dScbr_dtau = deriv.dSbr_dtau_csc(nbus, u_cbr_tau, F_cbr, T_cbr, yff_cbr, yft_cbr, ytf_cbr, ytt_cbr, V, tap, tap_modules)

    # -------------------
    
    dLossvsc_dVa_ = CxCSC(nvsc, len(i_u_va), 0, False)
    dLosshvdc_dVa_ = CxCSC(nhvdc, len(i_u_va), 0, False)
    dInj_dVa_ = deriv.dInj_dVa_csc(nhvdc, i_u_va, hvdc_pset, hvdc_r, hvdc_droop, V, F_hvdc, T_hvdc)
    dPf_dVa_ = deriv.dSf_dVa_csc(nbus, k_cbr_pf, i_u_va, adm.yff, adm.yft, V, F, T).real
    dQf_dVa_ = deriv.dSf_dVa_csc(nbus, k_cbr_qf, i_u_va, adm.yff, adm.yft, V, F, T).imag
    dPt_dVa_ = deriv.dSt_dVa_csc(nbus, k_cbr_pt, i_u_va, adm.ytf, V, F, T).real
    dQt_dVa_ = deriv.dSt_dVa_csc(nbus, k_cbr_qt, i_u_va, adm.ytf, V, F, T).imag


    dLossvsc_dVm_ = deriv.dLossvsc_dVm_csc(nvsc, i_u_vm, alpha1, alpha2, alpha3, V, Pf_vsc, Pt_vsc, Qt_vsc, F_vsc, T_vsc)
    dLosshvdc_dVm_ = deriv.dLosshvdc_dVm_csc(nhvdc, i_u_vm, Vm, Pf_hvdc, Pt_hvdc, hvdc_r, F_hvdc, T_hvdc)
    dInj_dVm_ = CxCSC(nhvdc, len(i_u_vm), 0, False)
    dPf_dVm_ = deriv.dSf_dVm_csc(nbus, k_cbr_pf, i_u_vm, adm.yff, adm.yft, V, F, T).real
    dQf_dVm_ = deriv.dSf_dVm_csc(nbus, k_cbr_qf, i_u_vm, adm.yff, adm.yft, V, F, T).imag
    dPt_dVm_ = deriv.dSt_dVm_csc(nbus, k_cbr_pt, i_u_vm, adm.ytt, adm.ytf, V, F, T).real
    dQt_dVm_ = deriv.dSt_dVm_csc(nbus, k_cbr_qt, i_u_vm, adm.ytt, adm.ytf, V, F, T).imag

    dP_dm__ = deriv.dSbus_dm_csc(nbus, i_k_p, u_cbr_m, F, T, yff_cbr, yft_cbr, ytf_cbr, ytt_cbr, tap, tap_modules, V).real
    dQ_dm__ = deriv.dSbus_dm_csc(nbus, i_k_q, u_cbr_m, F, T, yff_cbr, yft_cbr, ytf_cbr, ytt_cbr, tap, tap_modules, V).imag
    dLossvsc_dm_ = CxCSC(nvsc, len(u_cbr_m), 0, False)
    dLosshvdc_dm_ = CxCSC(nhvdc, len(u_cbr_m), 0, False)
    dInj_dm_ = CxCSC(nbus, len(u_cbr_m), 0, False)
    dPf_dm_ = deriv.dSf_dm_csc(nbr, k_cbr_pf, u_cbr_m, F, T, Ys, Bc, k, tap, tap_modules, V).real
    dQf_dm_ = deriv.dSf_dm_csc(nbr, k_cbr_qf, u_cbr_m, F, T, Ys, Bc, k, tap, tap_modules, V).imag
    dPt_dm_ = deriv.dSt_dm_csc(nbr, k_cbr_pt, u_cbr_m, F, T, Ys, k, tap, tap_modules, V).real
    dQt_dm_ = deriv.dSt_dm_csc(nbr, k_cbr_qt, u_cbr_m, F, T, Ys, k, tap, tap_modules, V).imag

    dP_dtau__ = deriv.dSbus_dtau_csc(nbus, i_k_p, u_cbr_tau, F, T, yff_cbr, yft_cbr, ytf_cbr, ytt_cbr, tap, tap_modules, V).real
    dQ_dtau__ = deriv.dSbus_dtau_csc(nbus, i_k_q, u_cbr_tau, F, T, yff_cbr, yft_cbr, ytf_cbr, ytt_cbr, tap, tap_modules, V).imag
    dLossvsc_dtau_ = CxCSC(nvsc, len(u_cbr_tau), 0, False)
    dLosshvdc_dtau_ = CxCSC(nhvdc, len(u_cbr_tau), 0, False)
    dInj_dtau_ = CxCSC(nbus, len(u_cbr_tau), 0, False)
    dPf_dtau_ = deriv.dSf_dtau_csc(nbr, k_cbr_pf, u_cbr_tau, F, T, Ys, k, tap, V).real
    dQf_dtau_ = deriv.dSf_dtau_csc(nbr, k_cbr_qf, u_cbr_tau, F, T, Ys, k, tap, V).imag
    dPt_dtau_ = deriv.dSt_dtau_csc(nbr, k_cbr_pt, u_cbr_tau, F, T, Ys, k, tap, V).real
    dQt_dtau_ = deriv.dSt_dtau_csc(nbr, k_cbr_qt, u_cbr_tau, F, T, Ys, k, tap, V).imag

    # # dP_dPfvsc__ = sp_slice(scipy_to_mat(conn_vsc_F.transpose()), i_k_p, u_vsc_pf)
    # dP_dPfvsc__ = deriv.dP_dPfvsc_csc(nbus, i_k_p, u_vsc_pf, F_vsc)
    # dQ_dPfvsc__ = CxCSC(len(i_k_q), len(u_vsc_pf), 0, False)
    # dLossvsc_dPfvsc_ = deriv.dLossvsc_dPfvsc_csc(nvsc, u_vsc_pf)
    # dLosshvdc_dPfvsc_ = CxCSC(nhvdc, len(u_vsc_pf), 0, False)
    # dInj_dPfvsc_ = CxCSC(nbus, len(u_vsc_pf), 0, False)
    # dPf_dPfvsc_ = CxCSC(len(k_cbr_pf), len(u_vsc_pf), 0, False)
    # dQf_dPfvsc_ = CxCSC(len(k_cbr_qf), len(u_vsc_pf), 0, False)
    # dPt_dPfvsc_ = CxCSC(len(k_cbr_pt), len(u_vsc_pf), 0, False)
    # dQt_dPfvsc_ = CxCSC(len(k_cbr_qt), len(u_vsc_pf), 0, False)

    # dP_dPtvsc__ = sp_slice(scipy_to_mat(conn_vsc_T.transpose()), i_k_p, u_vsc_pt)
    # # dP_dPtvsc__ = deriv.dP_dPtvsc_csc(nbus, i_k_p, u_vsc_pt, T_vsc)
    # dQ_dPtvsc__ = CxCSC(len(i_k_q), len(u_vsc_pt), 0, False)
    # dLossvsc_dPtvsc_ = deriv.dLossvsc_dPtvsc_csc(nvsc, u_vsc_pt, alpha2, alpha3, Vm, Pt_vsc, T_vsc)
    # dLosshvdc_dPtvsc_ = CxCSC(nhvdc, len(u_vsc_pt), 0, False)
    # dInj_dPtvsc_ = CxCSC(nbus, len(u_vsc_pt), 0, False)
    # dPf_dPtvsc_ = CxCSC(len(k_cbr_pf), len(u_vsc_pt), 0, False)
    # dQf_dPtvsc_ = CxCSC(len(k_cbr_qf), len(u_vsc_pt), 0, False)
    # dPt_dPtvsc_ = CxCSC(len(k_cbr_pt), len(u_vsc_pt), 0, False)
    # dQt_dPtvsc_ = CxCSC(len(k_cbr_qt), len(u_vsc_pt), 0, False)

    # dP_dQtvsc__ = CxCSC(len(i_k_p), len(u_vsc_qt), 0, False)
    # dQ_dQtvsc__ = sp_slice(scipy_to_mat(conn_vsc_F.transpose()), i_k_q, u_vsc_qt)
    # dLossvsc_dQtvsc_ = deriv.dLossvsc_dQtvsc_csc(nvsc, u_vsc_qt, alpha2, alpha3, Vm, Qt_vsc, T_vsc)
    # dLosshvdc_dQtvsc_ = CxCSC(nhvdc, len(u_vsc_qt), 0, False)
    # dInj_dQtvsc_ = CxCSC(nbus, len(u_vsc_qt), 0, False)
    # dPf_dQtvsc_ = CxCSC(len(k_cbr_pf), len(u_vsc_qt), 0, False)
    # dQf_dQtvsc_ = CxCSC(len(k_cbr_qf), len(u_vsc_qt), 0, False)
    # dPt_dQtvsc_ = CxCSC(len(k_cbr_pt), len(u_vsc_qt), 0, False)
    # dQt_dQtvsc_ = CxCSC(len(k_cbr_qt), len(u_vsc_qt), 0, False)

    # dP_dPfhvdc__ = sp_slice(scipy_to_mat(conn_hvdc_F.transpose()), i_k_p, hvdc_droop_idx)
    # dQ_dPfhvdc__ = CxCSC(len(i_k_q), len(hvdc_droop_idx), 0, False)
    # dLossvsc_dPfhvdc_ = CxCSC(nvsc, len(hvdc_droop_idx), 0, False)
    # dLosshvdc_dPfhvdc_ = deriv.dLosshvdc_dPfhvdc_csc(nhvdc, hvdc_droop_idx, Vm, Pf_hvdc, Pt_hvdc, hvdc_r, F_hvdc, T_hvdc)
    # dInj_dPfhvdc_ = deriv.dInj_dPfhvdc_csc(nhvdc, hvdc_droop_idx, hvdc_pset, hvdc_r, hvdc_droop, V, F_hvdc, T_hvdc)
    # dPf_dPfhvdc_ = CxCSC(len(k_cbr_pf), len(hvdc_droop_idx), 0, False)
    # dQf_dPfhvdc_ = CxCSC(len(k_cbr_qf), len(hvdc_droop_idx), 0, False)
    # dPt_dPfhvdc_ = CxCSC(len(k_cbr_pt), len(hvdc_droop_idx), 0, False)
    # dQt_dPfhvdc_ = CxCSC(len(k_cbr_qt), len(hvdc_droop_idx), 0, False)

    # dP_dPthvdc__ = sp_slice(scipy_to_mat(conn_hvdc_T.transpose()), i_k_p, hvdc_droop_idx)
    # dQ_dPthvdc__ = CxCSC(len(i_k_q), len(hvdc_droop_idx), 0, False)
    # dLossvsc_dPthvdc_ = CxCSC(nvsc, len(hvdc_droop_idx), 0, False)
    # dLosshvdc_dPthvdc_ = deriv.dLosshvdc_dPthvdc_csc(nhvdc, hvdc_droop_idx, Vm, Pf_hvdc, Pt_hvdc, hvdc_r, F_hvdc, T_hvdc)
    # dInj_dPthvdc_ = CxCSC(nhvdc, nhvdc, 0, False)
    # dPf_dPthvdc_ = CxCSC(len(k_cbr_pf), len(hvdc_droop_idx), 0, False)
    # dQf_dPthvdc_ = CxCSC(len(k_cbr_qf), len(hvdc_droop_idx), 0, False)
    # dPt_dPthvdc_ = CxCSC(len(k_cbr_pt), len(hvdc_droop_idx), 0, False)
    # dQt_dPthvdc_ = CxCSC(len(k_cbr_qt), len(hvdc_droop_idx), 0, False)

    # dP_dQfhvdc__ = CxCSC(len(i_k_q), len(hvdc_droop_idx), 0, False)
    # dQ_dQfhvdc__ = sp_slice(scipy_to_mat(conn_hvdc_F.transpose()), i_k_q, hvdc_droop_idx)
    # dLossvsc_dQfhvdc_ = CxCSC(nvsc, len(hvdc_droop_idx), 0, False)
    # dLosshvdc_dQfhvdc_ = CxCSC(nhvdc, len(hvdc_droop_idx), 0, False)
    # dInj_dQfhvdc_ = CxCSC(nhvdc, len(hvdc_droop_idx), 0, False)
    # dPf_dQfhvdc_ = CxCSC(len(k_cbr_pf), len(hvdc_droop_idx), 0, False)
    # dQf_dQfhvdc_ = CxCSC(len(k_cbr_qf), len(hvdc_droop_idx), 0, False)
    # dPt_dQfhvdc_ = CxCSC(len(k_cbr_pt), len(hvdc_droop_idx), 0, False)
    # dQt_dQfhvdc_ = CxCSC(len(k_cbr_qt), len(hvdc_droop_idx), 0, False)

    # dP_dQthvdc__ = CxCSC(len(i_k_q), len(hvdc_droop_idx), 0, False)
    # dQ_dQthvdc__ = sp_slice(scipy_to_mat(conn_hvdc_T.transpose()), i_k_q, hvdc_droop_idx)
    # dLossvsc_dQthvdc_ = CxCSC(nvsc, len(hvdc_droop_idx), 0, False)
    # dLosshvdc_dQthvdc_ = CxCSC(nhvdc, len(hvdc_droop_idx), 0, False)
    # dInj_dQthvdc_ = CxCSC(nhvdc, len(hvdc_droop_idx), 0, False)
    # dPf_dQthvdc_ = CxCSC(len(k_cbr_pf), len(hvdc_droop_idx), 0, False)
    # dQf_dQthvdc_ = CxCSC(len(k_cbr_qf), len(hvdc_droop_idx), 0, False)
    # dPt_dQthvdc_ = CxCSC(len(k_cbr_pt), len(hvdc_droop_idx), 0, False)
    # dQt_dQthvdc_ = CxCSC(len(k_cbr_qt), len(hvdc_droop_idx), 0, False)

    # compose the Jacobian
    J = csc_stack_2d_ff(mats=
                        [dP_dVa__, dP_dVm__, dP_dm__, dP_dtau__,
                         dQ_dVa__, dQ_dVm__, dQ_dm__, dQ_dtau__,
                         dPf_dVa_, dPf_dVm_, dPf_dm_, dPf_dtau_,
                         dPt_dVa_, dPt_dVm_, dPt_dm_, dPt_dtau_,
                         dQf_dVa_, dQf_dVm_, dQf_dm_, dQf_dtau_,
                         dQt_dVa_, dQt_dVm_, dQt_dm_, dQt_dtau_],
                        n_rows=6, n_cols=4)



    # J = csc_stack_2d_ff(
    #     mats=[
    #         dP_dVa__, dP_dVm__, dP_dPfvsc__, dP_dPtvsc__, dP_dQtvsc__, dP_dPfhvdc__, dP_dPthvdc__, dP_dQfhvdc__, dP_dQthvdc__, dP_dm__, dP_dtau__,
    #         dQ_dVa__, dQ_dVm__, dQ_dPfvsc__, dQ_dPtvsc__, dQ_dQtvsc__, dQ_dPfhvdc__, dQ_dPthvdc__, dQ_dQfhvdc__, dQ_dQthvdc__, dQ_dm__, dQ_dtau__,
    #         dLossvsc_dVa_, dLossvsc_dVm_, dLossvsc_dPfvsc_, dLossvsc_dPtvsc_, dLossvsc_dQtvsc_, dLossvsc_dPfhvdc_, dLossvsc_dPthvdc_, dLossvsc_dQfhvdc_, dLossvsc_dQthvdc_, dLossvsc_dm_, dLossvsc_dtau_,
    #         dLosshvdc_dVa_, dLosshvdc_dVm_, dLosshvdc_dPfvsc_, dLosshvdc_dPtvsc_, dLosshvdc_dQtvsc_, dLosshvdc_dPfhvdc_, dLosshvdc_dPthvdc_, dLosshvdc_dQfhvdc_, dLosshvdc_dQthvdc_, dLosshvdc_dm_, dLosshvdc_dtau_,
    #         dInj_dVa_,    dInj_dVm_, dInj_dPfvsc_, dInj_dPtvsc_, dInj_dQtvsc_, dInj_dPfhvdc_, dInj_dPthvdc_, dInj_dQfhvdc_, dInj_dQthvdc_, dInj_dm_, dInj_dtau_,
    #         dPf_dVa_,     dPf_dVm_, dPf_dPfvsc_, dPf_dPtvsc_, dPf_dQtvsc_, dPf_dPfhvdc_, dPf_dPthvdc_, dPf_dQfhvdc_, dPf_dQthvdc_, dPf_dm_, dPf_dtau_,
    #         dQf_dVa_,     dQf_dVm_, dQf_dPfvsc_, dQf_dPtvsc_, dQf_dQtvsc_, dQf_dPfhvdc_, dQf_dPthvdc_, dQf_dQfhvdc_, dQf_dQthvdc_, dQf_dm_, dQf_dtau_,
    #         dPt_dVa_,     dPt_dVm_, dPt_dPfvsc_, dPt_dPtvsc_, dPt_dQtvsc_, dPt_dPfhvdc_, dPt_dPthvdc_, dPt_dQfhvdc_, dPt_dQthvdc_, dPt_dm_, dPt_dtau_,
    #         dQt_dVa_,     dQt_dVm_, dQt_dPfvsc_, dQt_dPtvsc_, dQt_dQtvsc_, dQt_dPfhvdc_, dQt_dPthvdc_, dQt_dQfhvdc_, dQt_dQthvdc_, dQt_dm_, dQt_dtau_
    #     ],
    #     n_rows=9,
    #     n_cols=11
    # )

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
    ys = 1.0 / (R + 1.0j * X + 1e-20)  # series admittance
    bc2 = (G + 1j * B) / 2.0  # shunt admittance
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

        # Controllable Branch Indices
        self.u_cbr_m = np.zeros(0, dtype=int)
        self.u_cbr_tau = np.zeros(0, dtype=int)
        self.cbr = np.zeros(0, dtype=int)
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
        # self._Vm = np.zeros(nc.bus_data.nbus)
        # self._Va = np.zeros(nc.bus_data.nbus)
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
        ys = 1.0 / (nc.passive_branch_data.R[self.cbr]
                    + 1.0j * nc.passive_branch_data.X[self.cbr] + 1e-20)  # series admittance
        bc2 = (nc.passive_branch_data.G[self.cbr] + 1j * nc.passive_branch_data.B[self.cbr]) / 2.0  # shunt admittance
        vtap_f = nc.passive_branch_data.virtual_tap_f[self.cbr]
        vtap_t = nc.passive_branch_data.virtual_tap_t[self.cbr]
        self.yff_cbr = (ys + bc2) / (vtap_f * vtap_f)
        self.yft_cbr = -ys / (vtap_f * vtap_t)
        self.ytf_cbr = -ys / (vtap_t * vtap_f)
        self.ytt_cbr = (ys + bc2) / (vtap_t * vtap_t)
        self.F_cbr = self.nc.passive_branch_data.F[self.cbr]
        self.T_cbr = self.nc.passive_branch_data.T[self.cbr]

        # This is fully constant and hence we could precompute it
        m0 = self.nc.active_branch_data.tap_module.copy()
        tau0 = self.nc.active_branch_data.tap_angle.copy()

        self.yff0 = self.yff_cbr / (m0[self.cbr] * m0[self.cbr])
        self.yft0 = self.yft_cbr / (m0[self.cbr] * np.exp(-1.0j * tau0[self.cbr]))
        self.ytf0 = self.ytf_cbr / (m0[self.cbr] * np.exp(1.0j * tau0[self.cbr]))
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

    def _analyze_branch_controls(self) -> None:
        """
        Analyze the control branches and compute the indices
        :return: None
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

        # CONTROLLABLE BRANCH LOOP
        for k in range(self.nc.passive_branch_data.nelm):

            ctrl_m = self.nc.active_branch_data.tap_module_control_mode[k]
            ctrl_tau = self.nc.active_branch_data.tap_phase_control_mode[k]

            # analyze tap-module controls
            if ctrl_m == TapModuleControl.Vm:

                # Every bus controlled by m has to become a PQV bus
                bus_idx = self.nc.active_branch_data.tap_controlled_buses[k]
                # self.is_p_controlled[bus_idx] = True
                # self.is_q_controlled[bus_idx] = True
                self.is_vm_controlled[bus_idx] = True
                # self.is_va_controlled[bus_idx] = True
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
                pass

            elif ctrl_tau == 0:
                pass

            else:
                raise Exception(f"Unknown tap phase control mode {ctrl_tau}")

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
                    # self.is_p_controlled[control1_bus_device] = True
                    # self.is_q_controlled[control1_bus_device] = True
                    self.is_vm_controlled[control1_bus_device] = True
                    # self.is_va_controlled[control1_bus_device] = True
                if control2_bus_device > -1:
                    # self.is_p_controlled[control2_bus_device] = True
                    # self.is_q_controlled[control2_bus_device] = True
                    self.is_vm_controlled[control2_bus_device] = True
                    # self.is_va_controlled[control2_bus_device] = True

            elif control1 == ConverterControlType.Vm_dc and control2 == ConverterControlType.Va_ac:
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

            elif control1 == ConverterControlType.Vm_dc and control2 == ConverterControlType.Qac:
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

            elif control1 == ConverterControlType.Vm_dc and control2 == ConverterControlType.Pdc:
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

            elif control1 == ConverterControlType.Vm_dc and control2 == ConverterControlType.Pac:
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

            elif control1 == ConverterControlType.Vm_ac and control2 == ConverterControlType.Vm_dc:
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

            elif control1 == ConverterControlType.Vm_ac and control2 == ConverterControlType.Vm_ac:
                self.logger.add_error(
                    f"VSC control1 and control2 are the same for VSC indexed at {k},"
                    f" control1: {control1}, control2: {control2}")

            elif control1 == ConverterControlType.Vm_ac and control2 == ConverterControlType.Va_ac:
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

            elif control1 == ConverterControlType.Va_ac and control2 == ConverterControlType.Vm_ac:
                if control1_bus_device > -1:
                    self.is_va_controlled[control1_bus_device] = True
                if control2_bus_device > -1:
                    self.is_vm_controlled[control2_bus_device] = True

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
                    u_vsc_pf.append(control1_branch_device)
                    u_vsc_pt.append(control1_branch_device)
                    k_vsc_qt.append(control1_branch_device)
                    vsc_qt_set.append(control1_magnitude)

            elif control1 == ConverterControlType.Qac and control2 == ConverterControlType.Pac:
                if control1_branch_device > -1:
                    u_vsc_pf.append(control1_branch_device)
                    u_vsc_pt.append(control1_branch_device)
                    k_vsc_qt.append(control1_branch_device)
                    vsc_qt_set.append(control1_magnitude)


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
                    u_vsc_qt.append(control1_branch_device)
                    k_vsc_qt.append(control1_branch_device)
                    vsc_qt_set.append(control1_magnitude)

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
        # hvdc = list()
        hvdc_droop_idx = list()

        # HVDC LOOP
        for k in range(self.nc.hvdc_data.nelm):
            # hvdc.append(k)
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

        yff = (self.yff_cbr / (m2[self.cbr] * m2[self.cbr]))
        yft = self.yft_cbr / (m2[self.cbr] * np.exp(-1.0j * tau2[self.cbr]))
        ytf = self.ytf_cbr / (m2[self.cbr] * np.exp(1.0j * tau2[self.cbr]))
        ytt = self.ytt_cbr

        Vf_cbr = V[self.F_cbr]
        Vt_cbr = V[self.T_cbr]
        Sf_cbr = (Vf_cbr * np.conj(Vf_cbr) * np.conj(yff - self.yff0) + Vf_cbr * np.conj(Vt_cbr) * np.conj(yft - self.yft0))
        St_cbr = (Vt_cbr * np.conj(Vt_cbr) * np.conj(ytt - self.ytt0) + Vt_cbr * np.conj(Vf_cbr) * np.conj(ytf - self.ytf0))

        # difference between the actual power and the power calculated with the passive term (initial admittance)
        AScalc_cbr = np.zeros(self.nc.bus_data.nbus, dtype=complex)
        AScalc_cbr[self.F_cbr] += Sf_cbr
        AScalc_cbr[self.T_cbr] += St_cbr

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
        St_vsc = Pt_vsc + 1j * Qt_vsc

        Scalc_vsc = Pf_vsc @ self.nc.vsc_data.Cf + St_vsc @ self.nc.vsc_data.Ct

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

        Sf_hvdc = Pf_hvdc + 1j * Qf_hvdc
        St_hvdc = Pt_hvdc + 1j * Qt_hvdc
        Scalc_hvdc = Sf_hvdc @ self.nc.hvdc_data.Cf + St_hvdc @ self.nc.hvdc_data.Ct

        # total nodal power --------------------------------------------------------------------------------------------
        Scalc = Scalc_passive + AScalc_cbr + Scalc_vsc + Scalc_hvdc
        dS = Scalc - Sbus

        # compose the residuals vector ---------------------------------------------------------------------------------
        _f = np.r_[
            dS[self.i_k_p].real,
            dS[self.i_k_q].imag,
            loss_vsc,
            loss_hvdc,
            inj_hvdc,
            self.cbr_pf_set - Pf_cbr,
            self.cbr_pt_set - Pt_cbr,
            self.cbr_qf_set - Qf_cbr,
            self.cbr_qt_set - Qt_cbr
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

        # converged?
        self._converged = self._error < self.options.tolerance

        if self.options.verbose > 1:
            print("Error:", self._error)

        return self._error, self._converged, x, self.f

    def fx(self) -> Vec:
        """
        Used? No
        :return:
        """

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

            # Jdense = np.array(J.todense())
            # dff = pd.DataFrame(Jdense)
            # dff.to_excel("Jacobian_autodiff.xlsx")
            return J

        else:
            # build the symbolic Jacobian
            tap_modules = expand(self.nc.nbr, self.m, self.u_cbr_m, 1.0)
            tap_angles = expand(self.nc.nbr, self.tau, self.u_cbr_tau, 0.0)
            tap = polar_to_rect(tap_modules, tap_angles)

            adm = compute_admittances(
                R=self.nc.passive_branch_data.R,
                X=self.nc.passive_branch_data.X,
                G=self.nc.passive_branch_data.G,
                B=self.nc.passive_branch_data.B,
                k=self.nc.passive_branch_data.k,
                tap_module=tap_modules,
                vtap_f=self.nc.passive_branch_data.virtual_tap_f,
                vtap_t=self.nc.passive_branch_data.virtual_tap_t,
                tap_angle=tap_angles,
                Cf=self.nc.passive_branch_data.Cf.tocsc(),
                Ct=self.nc.passive_branch_data.Ct.tocsc(),
                Yshunt_bus=self.nc.get_Yshunt_bus(),
                conn=self.nc.passive_branch_data.conn,
                seq=1,
                add_windings_phase=False
            )

            J_sym = adv_jacobian(nbus=self.nc.nbus,
                                 nbr=self.nc.nbr,
                                 nvsc=self.nc.vsc_data.nelm,
                                 nhvdc=self.nc.hvdc_data.nelm,
                                 F=self.nc.passive_branch_data.F,
                                 T=self.nc.passive_branch_data.T,
                                 F_vsc=self.nc.vsc_data.F,
                                 T_vsc=self.nc.vsc_data.T,
                                 F_hvdc=self.nc.hvdc_data.F,
                                 T_hvdc=self.nc.hvdc_data.T,
                                 R=self.nc.passive_branch_data.R,
                                 X=self.nc.passive_branch_data.X,
                                 G=self.nc.passive_branch_data.G,
                                 B=self.nc.passive_branch_data.B,
                                 k=self.nc.passive_branch_data.k,
                                 Ys=self.nc.passive_branch_data.get_series_admittance(),
                                 vtap_f=self.nc.passive_branch_data.virtual_tap_f,
                                 vtap_t=self.nc.passive_branch_data.virtual_tap_t,
                                 tap_angles=tap_angles,
                                 tap_modules=tap_modules,
                                 Bc=self.nc.passive_branch_data.B,
                                 V=self.V,
                                 Vm=self.Vm,
                                 adm=adm,

                                 # Controllable Branch Indices
                                 u_cbr_m=self.u_cbr_m,
                                 u_cbr_tau=self.u_cbr_tau,
                                 cbr=self.cbr,
                                 k_cbr_pf=self.k_cbr_pf,
                                 k_cbr_pt=self.k_cbr_pt,
                                 k_cbr_qf=self.k_cbr_qf,
                                 k_cbr_qt=self.k_cbr_qt,
                                 cbr_pf_set=self.cbr_pf_set,
                                 cbr_pt_set=self.cbr_pt_set,
                                 cbr_qf_set=self.cbr_qf_set,
                                 cbr_qt_set=self.cbr_qt_set,

                                 # VSC Indices
                                 u_vsc_pf=self.u_vsc_pf,
                                 u_vsc_pt=self.u_vsc_pt,
                                 u_vsc_qt=self.u_vsc_qt,
                                 k_vsc_pf=self.k_vsc_pf,
                                 k_vsc_pt=self.k_vsc_pt,
                                 k_vsc_qt=self.k_vsc_qt,
                                 vsc_pf_set=self.vsc_pf_set,
                                 vsc_pt_set=self.vsc_pt_set,
                                 vsc_qt_set=self.vsc_qt_set,

                                 # VSC Params
                                 alpha1=self.nc.vsc_data.alpha1,
                                 alpha2=self.nc.vsc_data.alpha2,
                                 alpha3=self.nc.vsc_data.alpha3,

                                 # HVDC Indices
                                 hvdc_droop_idx=self.hvdc_droop_idx,

                                 # HVDC Params
                                 hvdc_r=self.nc.hvdc_data.r,
                                 hvdc_pset=self.nc.hvdc_data.Pset,
                                 hvdc_droop=self.nc.hvdc_data.angle_droop,
                                 
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
                                 Qf_hvdc=self.Qf_hvdc,
                                 Pt_hvdc=self.Pt_hvdc,
                                 Qt_hvdc=self.Qt_hvdc,

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
                                 conn_vsc_F=self.nc.vsc_data.Cf,
                                 conn_vsc_T=self.nc.vsc_data.Ct,
                                 conn_hvdc_F=self.nc.hvdc_data.Cf,
                                 conn_hvdc_T=self.nc.hvdc_data.Ct,
                                 Ybus=self.Ybus)

            # Jdense = np.array(J.todense())
            # dff = pd.DataFrame(Jdense)
            # dff.to_excel("Jacobian_symbolic.xlsx")

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

        ys = 1.0 / (R + 1.0j * X + 1e-20)  # series admittance
        bc2 = (G + 1j * B) / 2.0  # shunt admittance
        yff = (ys + bc2) / (m * m * vtap_f * vtap_f)
        yft = -ys / (m * np.exp(-1.0j * tau) * vtap_f * vtap_t)
        ytf = -ys / (m * np.exp(1.0j * tau) * vtap_t * vtap_f)
        ytt = (ys + bc2) / (vtap_t * vtap_t)

        If = Vf * yff + Vt * yft
        It = Vt * ytt + Vf * ytf
        Sf = Vf * np.conj(If)
        St = Vt * np.conj(It)

        Pf_cbr = calcSf(k=self.k_cbr_pf,
                        V=V,
                        F=self.nc.passive_branch_data.F,
                        T=self.nc.passive_branch_data.T,
                        R=self.nc.passive_branch_data.R,
                        X=self.nc.passive_branch_data.X,
                        G=self.nc.passive_branch_data.G,
                        B=self.nc.passive_branch_data.B,
                        m=m,
                        tau=tau,
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
                        m=m,
                        tau=tau,
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
                        m=m,
                        tau=tau,
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
                        m=m,
                        tau=tau,
                        vtap_f=self.nc.passive_branch_data.virtual_tap_f,
                        vtap_t=self.nc.passive_branch_data.virtual_tap_t).imag

        # Branch losses in MVA
        losses = (Sf + St) * self.nc.Sbase

        # branch voltage increment
        Vbranch = Vf - Vt

        # Branch loading in p.u.
        loading = Sf * self.nc.Sbase / (self.nc.passive_branch_data.rates + 1e-9)

        # VSC ----------------------------------------------------------------------------------------------------------
        Pf_vsc = self.Pf_vsc
        St_vsc = (self.Pt_vsc + 1j * self.Qt_vsc)
        If_vsc = Pf_vsc / np.abs(V[self.nc.vsc_data.F])
        It_vsc = St_vsc / np.conj(V[self.nc.vsc_data.T])
        loading_vsc = abs(St_vsc) / (self.nc.vsc_data.rates + 1e-20) * self.nc.Sbase

        # HVDC ---------------------------------------------------------------------------------------------------------
        Sf_hvdc = (self.Pf_hvdc + 1j * self.Qf_hvdc) * self.nc.Sbase
        St_hvdc = (self.Pt_hvdc + 1j * self.Qt_hvdc) * self.nc.Sbase
        loading_hvdc = Sf_hvdc.real / (self.nc.hvdc_data.rates + 1e-20)

        return NumericPowerFlowResults(
            V=self.V,
            Scalc=self.Scalc * self.nc.Sbase,
            m=expand(self.nc.nbr, self.m, self.u_cbr_m, 1.0),
            tau=expand(self.nc.nbr, self.tau, self.u_cbr_tau, 0.0),
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
