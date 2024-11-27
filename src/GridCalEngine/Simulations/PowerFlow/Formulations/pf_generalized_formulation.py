# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from typing import Tuple, List, Callable, Union
import numpy as np
import pandas as pd
import scipy as sp
from scipy.sparse import lil_matrix, csc_matrix, hstack, vstack, csr_matrix
from GridCalEngine.Topology.admittance_matrices import compute_admittances
from GridCalEngine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
from GridCalEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCalEngine.DataStructures.numerical_circuit import NumericalCircuit
import GridCalEngine.Simulations.Derivatives.csc_derivatives as deriv
from GridCalEngine.Topology.simulation_indices import compile_types
from GridCalEngine.Utils.Sparse.csc2 import CSC, CxCSC, sp_slice, csc_stack_2d_ff, scipy_to_mat, sp_slice_cols, \
    sp_slice_rows, pack_4_by_4, mat_to_scipy
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.common_functions import expand
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.common_functions import compute_fx_error
from GridCalEngine.Simulations.PowerFlow.Formulations.pf_formulation_template import PfFormulationTemplate
from GridCalEngine.enumerations import BusMode, TapPhaseControl, TapModuleControl, ConverterControlType
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.common_functions import (compute_zip_power, compute_power,
                                                                                   polar_to_rect, get_Sf, get_St,
                                                                                   get_It)
from GridCalEngine.basic_structures import Vec, IntVec, CxVec, Logger, ObjVec
import GridCalEngine.Topology.generalized_simulation_indices as gsi


def recompute_controllable_power(V_f: CxVec,
                                 V_t: CxVec,
                                 R: Vec,
                                 X: Vec,
                                 G: Vec,
                                 B: Vec,
                                 tap_module: Vec,
                                 vtap_f: Vec,
                                 vtap_t: Vec,
                                 tap_angle: Vec) -> Tuple[Vec, Vec, Vec, Vec]:
    """
    Compute the complete admittance matrices for the general power flow methods (Newton-Raphson based)
    
    :param V_f: From voltages array
    :param V_t: To voltages array
    :param R: array of branch resistance (p.u.)
    :param X: array of branch reactance (p.u.)
    :param G: array of branch conductance (p.u.)
    :param B: array of branch susceptance (p.u.)
    :param k: array of converter values: 1 for regular Branches, sqrt(3) / 2 for VSC
    :param tap_module: array of tap modules (for all Branches, regardless of their type)
    :param vtap_f: array of virtual taps at the "from" side
    :param vtap_t: array of virtual taps at the "to" side
    :param tap_angle: array of tap angles (for all Branches, regardless of their type)
    :return: Pf, Qf, Pt, Qt
    """

    # form the admittance matrices
    ys = 1.0 / (R + 1.0j * X + 1e-20)  # series admittance
    bc2 = (G + 1j * B) / 2.0  # shunt admittance
    mp = tap_module

    Yff = (ys + bc2) / (mp * mp * vtap_f * vtap_f)
    Yft = -ys / (mp * np.exp(-1.0j * tap_angle) * vtap_f * vtap_t)
    Ytf = -ys / (mp * np.exp(1.0j * tap_angle) * vtap_t * vtap_f)
    Ytt = (ys + bc2) / (vtap_t * vtap_t)

    Sf = V_f * np.conj(V_f) * Yff - V_f * np.conj(V_t) * Yft
    St = V_t * np.conj(V_t) * Ytt - V_t * np.conj(V_f) * Ytf

    return Sf.real, Sf.imag, St.real, St.imag


# @njit()
def adv_jacobian(nbus: int,
                 nbr: int,
                 ix_vm: IntVec,
                 ix_va: IntVec,
                 ix_pzip: IntVec,
                 ix_qzip: IntVec,
                 ix_pf: IntVec,
                 ix_qf: IntVec,
                 ix_pt: IntVec,
                 ix_qt: IntVec,
                 ix_m: IntVec,
                 ix_tau: IntVec,
                 ig_pbus: IntVec,
                 ig_qbus: IntVec,
                 ig_plossacdc: IntVec,
                 ig_plosshvdc: IntVec,
                 ig_pinjhvdc: IntVec,
                 ig_pftr: IntVec,
                 ig_qftr: IntVec,
                 ig_pttr: IntVec,
                 ig_qttr: IntVec,
                 ig_contrbr: IntVec,
                 Cf_acdc: sp.sparse,
                 Ct_acdc: sp.sparse,
                 Cf_hvdc: sp.sparse,
                 Ct_hvdc: sp.sparse,
                 Cf_contbr: sp.sparse,
                 Ct_contbr: sp.sparse,
                 Cf_branch: sp.sparse,
                 Ct_branch: sp.sparse,
                 alpha1: Vec,
                 alpha2: Vec,
                 alpha3: Vec,
                 F_acdc: IntVec,
                 T_acdc: IntVec,
                 F_hvdc: IntVec,
                 T_hvdc: IntVec,
                 hvdc_mode: IntVec,
                 hvdc_angle_droop: Vec,
                 hvdc_pset: Vec,
                 hvdc_r: Vec,
                 hvdc_Vnf: Vec,
                 hvdc_Vnt: Vec,
                 Pf: Vec,
                 Qf: Vec,
                 Pt: Vec,
                 Qt: Vec,
                 F: IntVec,
                 T: IntVec,
                 Ys: CxVec,
                 kconv: Vec,
                 complex_tap: CxVec,
                 tap_modules: Vec,
                 Bc: Vec,
                 V: CxVec,
                 Vm: Vec,
                 Va: Vec,
                 Sbase: float,
                 Ybus_x: CxVec,
                 Ybus_p: IntVec,
                 Ybus_i: IntVec,
                 yff: CxVec,
                 yft: CxVec,
                 ytf: CxVec,
                 ytt: CxVec) -> CSC:
    """
    Compute the generalized jacobian
    :param nbus:
    :param nbr:
    :param ix_vm:
    :param ix_va:
    :param ix_pzip:
    :param ix_qzip:
    :param ix_pf:
    :param ix_qf:
    :param ix_pt:
    :param ix_qt:
    :param ix_m:
    :param ix_tau:
    :param ig_pbus:
    :param ig_qbus:
    :param ig_plossacdc:
    :param ig_plosshvdc:
    :param ig_pinjhvdc:
    :param ig_pftr:
    :param ig_qftr:
    :param ig_pttr:
    :param ig_qttr:
    :param ig_contrbr: controllable branch indices (controllable transformers)
    :param Cf_acdc:
    :param Ct_acdc:
    :param Cf_hvdc:
    :param Ct_hvdc:
    :param Cf_contbr:
    :param Ct_contbr:
    :param alpha1: a
    :param alpha2: b
    :param alpha3: c
    :param F_acdc: from buses for AC/DC VSCs
    :param T_acdc: to buses for AC/DC VSCs
    :param F_hvdc: from buses for HVDC
    :param T_hvdc: to buses for HVDC
    :param F: for regular branches
    :param T: for regular branches
    :param Pf:
    :param Qf:
    :param Pt:
    :param Qt:
    :param Ys: Series admittance 1 / (R + jX)
    :param kconv:
    :param complex_tap:
    :param tap_modules:
    :param Bc: Total changing susceptance
    :param Beq:
    :param V:
    :param Vm:
    :param Ybus_x:
    :param Ybus_p:
    :param Ybus_i:
    :param yff:
    :param yft:
    :param ytf:
    :param ytt:
    :return:

    x = [Vm, Va, Pzip, Qzip, Pf, Qf, Pt, Qt, m, tau]
    g = [Pbus, Qbus, Ploss_acdc, Ploss_hvdc, Pinj_hvdc, Pftr, Qftr, Pttr, Qttr]

    """
    print()
    # print("ix_qt", ix_qt)
    # DO SOME IMPORTANT CASTING
    ix_vm = np.asarray(ix_vm).astype(np.int32)
    ix_va = np.asarray(ix_va).astype(np.int32)
    ix_pzip = np.asarray(ix_pzip).astype(np.int32)
    ix_qzip = np.asarray(ix_qzip).astype(np.int32)
    ix_pf = np.asarray(ix_pf).astype(np.int32)
    ix_qf = np.asarray(ix_qf).astype(np.int32)
    ix_pt = np.asarray(ix_pt).astype(np.int32)
    ix_qt = np.asarray(ix_qt).astype(np.int32)
    ix_m = np.asarray(ix_m).astype(np.int32)
    ix_tau = np.asarray(ix_tau).astype(np.int32)

    ig_sbus = ig_pbus + ig_qbus
    ig_pbus = np.asarray(ig_pbus).astype(np.int32)
    ig_qbus = np.asarray(ig_qbus).astype(np.int32)
    ig_sbus = np.asarray(ig_sbus).astype(np.int32)

    ig_plossacdc = np.asarray(ig_plossacdc).astype(np.int32)
    ig_plosshvdc = np.asarray(ig_plosshvdc).astype(np.int32)
    ig_pinjhvdc = np.asarray(ig_pinjhvdc).astype(np.int32)
    ig_pftr = np.asarray(ig_pftr).astype(np.int32)
    ig_qftr = np.asarray(ig_qftr).astype(np.int32)
    ig_pttr = np.asarray(ig_pttr).astype(np.int32)
    ig_qttr = np.asarray(ig_qttr).astype(np.int32)
    ig_contrbr = np.asarray(ig_contrbr).astype(np.int32)

    # COMPUTE DERIVATIVES

    # dS_dVma bus-bus derivatives (always needed)
    dS_dVm_x, dS_dVa_x = deriv.dSbus_dV_numba_sparse_csc(Ybus_x, Ybus_p, Ybus_i, V, Vm)
    dS_dVm = CxCSC(nbus, nbus, len(dS_dVm_x), False).set(Ybus_i, Ybus_p, dS_dVm_x)
    dS_dVa = CxCSC(nbus, nbus, len(dS_dVa_x), False).set(Ybus_i, Ybus_p, dS_dVa_x)
    dP_dVm = dS_dVm.real
    dQ_dVm = dS_dVm.imag
    dP_dVa = dS_dVa.real
    dQ_dVa = dS_dVa.imag

    dP_dVm_lil = mat_to_scipy(dP_dVm).tocsr().tolil()
    dQ_dVm_lil = mat_to_scipy(dQ_dVm).tocsr().tolil()
    dP_dVa_lil = mat_to_scipy(dP_dVa).tocsr().tolil()
    dQ_dVa_lil = mat_to_scipy(dQ_dVa).tocsr().tolil()
    dP_dVm_lil = dP_dVm_lil[ig_pbus, :][:, ix_vm]
    dQ_dVm_lil = dQ_dVm_lil[ig_qbus, :][:, ix_vm]
    dP_dVa_lil = dP_dVa_lil[ig_pbus, :][:, ix_va]
    dQ_dVa_lil = dQ_dVa_lil[ig_qbus, :][:, ix_va]

    dS_dVm_lil = vstack([dP_dVm_lil, dQ_dVm_lil])
    dS_dVa_lil = vstack([dP_dVa_lil, dQ_dVa_lil])
    dS_dV_lil = hstack([dS_dVm_lil, dS_dVa_lil])
    assert dS_dV_lil.shape == (len(ig_sbus), len(ix_vm) + len(
        ix_va)), f"Shape is {dS_dV_lil.shape}, it should be {len(ig_sbus), len(ix_vm) + len(ix_va)}"

    # dS_dV = csc_stack_2d_ff(mats=[dP_dVm, dQ_dVm, dP_dVa, dQ_dVa], n_rows=2, n_cols=2)

    '''
    dS_dSzip: remade it as 4 different chunks below: dP_dPzip, dQ_dQzip, dP_dQzip, dQ_dPzip
    # dS_dSzip
    # ix_szip = ix_pzip + ix_qzip
    # ig_sbus = ig_pbus + ig_qbus
    # nnz_dS_dSzip = np.intersect1d(ix_szip,
                                  # ig_sbus)  # indices where both have entries, eg: cross([1, 2, 3], [2, 4]) = [2]
    # dS_dSzip = CxCSC(nbus, nbus, nnz_dS_dSzip, False).set(ig_sbus, ix_szip, (-1 + 0j) * np.ones(nnz_dS_dSzip))
    # dS_dSzip = -1  # Size nbus x nbus, or slice directly
    # then do the full crossing ig_pbus, ig_qbus, ix_pzip, ix_qzip
    '''

    pzipData = -1 * np.ones(len(ix_pzip), dtype=np.float64)
    qzipData = -1 * np.ones(len(ix_qzip), dtype=np.float64)
    # csc_matrix((data, indices, indptr), shape=(3, 3)).toarray()

    dP_dPzip = csc_matrix((pzipData, ix_pzip, np.arange(len(ix_pzip) + 1)), shape=(nbus, len(ix_pzip)))
    dQ_dQzip = csc_matrix((qzipData, ix_qzip, np.arange(len(ix_qzip) + 1)), shape=(nbus, len(ix_qzip)))
    dQ_dPzip = csc_matrix((len(ig_qbus), len(ix_pzip)), dtype=np.float64)
    dP_dQzip = csc_matrix((len(ig_pbus), len(ix_qzip)), dtype=np.float64)

    # turn everything into lil
    dP_dPzip_lil = dP_dPzip.tocsr()[ig_pbus, :].tolil()
    dQ_dPzip_lil = dQ_dPzip.tocsr().tolil()
    dQ_dQzip_lil = dQ_dQzip.tocsr()[ig_qbus, :].tolil()
    dP_dQzip_lil = dP_dQzip.tocsr().tolil()

    dS_dPzip_lil = vstack([dP_dPzip_lil, dQ_dPzip_lil])
    dS_dQzip_lil = vstack([dP_dQzip_lil, dQ_dQzip_lil])
    ds_dSzip_lil = hstack([dS_dPzip_lil, dS_dQzip_lil])
    assert ds_dSzip_lil.shape == (len(ig_sbus), len(ix_pzip) + len(
        ix_qzip)), f"Shape is {ds_dSzip_lil.shape}, it should be {len(ig_sbus), len(ix_pzip) + len(ix_qzip)}"

    '''
    # dS_dSft
    # I think we need C matrices even if not present in Raiyan's thesis
    # How are Cs structured? ndev x nbus
    # ig_conttr = ig_pftr + ig_pttr + ig_qftr + ig_qttr, as if one branch controls something, immediately goes there
    # when slicing, if we have set some entry we should not have, it will be sorted out as it will not be grabbed
    dS_dSf = CxCSC(nbus, nbr, 0, False)  # keep it all empty with no set zeros


    dS_dSf[range(nbus), ig_plossacdc] = Cf_acdc.transpose()  # indexing not allowed for sparse matrices
    dS_dSf[range(nbus), ig_plosshvdc] = Cf_hvdc.transpose()  # fill intersection bus x hvdc
    dS_dSf[range(nbus), ig_contrbr] = Cf_contbr[ig_contrbr,
                                      :].transpose()  # fill intersection bus x controllable trafos
                                      
    dS_dSt = CxCSC(nbus, nbr, 0, False)  # keep it all empty with no set zeros
    dS_dSt[range(nbus), ig_plossacdc] = Ct_acdc.transpose()  # fill intersection bus x acdc
    dS_dSt[range(nbus), ig_plosshvdc] = Ct_hvdc.transpose()  # fill intersection bus x hvdc
    dS_dSt[range(nbus), ig_contrbr] = Ct_contbr[ig_contrbr,
                                      :].transpose()  # fill intersection bus x controllable trafos (or in reality, all classic branches)

    '''
    # FROM POWERS
    dP_dPf_branch = 0.0 * Cf_branch.transpose()
    dQ_dQf_branch = 0.0 * Cf_branch.transpose()
    dP_dPf_branch_lil = dP_dPf_branch.tocsr().tolil()
    dQ_dQf_branch_lil = dQ_dQf_branch.tocsr().tolil()

    dP_dPf_acdc = 1.0 * Cf_acdc.transpose()
    dQ_dQf_acdc = 0.0 * Cf_acdc.transpose()
    dP_dPf_acdc_lil = dP_dPf_acdc.tocsr().tolil()
    dQ_dQf_acdc_lil = dQ_dQf_acdc.tocsr().tolil()

    dP_dPf_hvdc_lil = 1.0 * Cf_hvdc.transpose()
    dQ_dQf_hvdc_lil = 1.0 * Cf_hvdc.transpose()

    dP_dPf_contbr = 1.0 * Cf_contbr[ig_contrbr, :].transpose()
    dQ_dQf_contbr = 1.0 * Cf_contbr[ig_contrbr, :].transpose()
    dP_dPf_contbr_lil = dP_dPf_contbr.tocsr().tolil()
    dQ_dQf_contbr_lil = dQ_dQf_contbr.tocsr().tolil()

    dP_dPf_lil = hstack([dP_dPf_branch_lil, dP_dPf_acdc_lil, dP_dPf_hvdc_lil, dP_dPf_contbr_lil]).tolil()
    dP_dPf_lil = dP_dPf_lil[ig_pbus, :][:, ix_pf]
    dQ_dQf_lil = hstack([dQ_dQf_branch_lil, dQ_dQf_acdc_lil, dQ_dQf_hvdc_lil, dQ_dQf_contbr_lil]).tolil()
    dQ_dQf_lil = dQ_dQf_lil[ig_qbus, :][:, ix_qf]
    dP_dQf_lil = csc_matrix((len(ig_pbus), len(ix_qf)), dtype=np.float64).tocsr().tolil()
    dQ_dPf_lil = csc_matrix((len(ig_qbus), len(ix_pf)), dtype=np.float64).tocsr().tolil()

    dS_dPf_lil = vstack([dP_dPf_lil, dQ_dPf_lil])
    dS_dQf_lil = vstack([dP_dQf_lil, dQ_dQf_lil])
    dS_dSf_lil = hstack([dS_dPf_lil, dS_dQf_lil])
    assert dS_dSf_lil.shape == (len(ig_sbus), len(ix_pf) + len(
        ix_qf)), f"Shape is {dS_dSf_lil.shape}, it should be {len(ig_sbus), len(ix_pf) + len(ix_qf)}"

    # TO POWERS

    dP_dPt_branch = 0.0 * Ct_branch.transpose()
    dQ_dQt_branch = 0.0 * Ct_branch.transpose()
    dP_dPt_branch_lil = dP_dPt_branch.tocsr().tolil()
    dQ_dQt_branch_lil = dQ_dQt_branch.tocsr().tolil()

    dP_dPt_acdc = 1.0 * Ct_acdc.transpose()
    dQ_dQt_acdc = 1.0 * Ct_acdc.transpose()
    dP_dPt_acdc_lil = dP_dPt_acdc.tocsr().tolil()
    dQ_dQt_acdc_lil = dQ_dQt_acdc.tocsr().tolil()

    dP_dPt_hvdc = 1.0 * Ct_hvdc.transpose()
    dQ_dQt_hvdc = 1.0 * Ct_hvdc.transpose()

    dP_dPt_contbr = 1.0 * Ct_contbr[ig_contrbr, :].transpose()
    dQ_dQt_contbr = 1.0 * Ct_contbr[ig_contrbr, :].transpose()
    dP_dPt_contbr_lil = dP_dPt_contbr.tocsr().tolil()
    dQ_dQt_contbr_lil = dQ_dQt_contbr.tocsr().tolil()

    dP_dPt_lil = hstack([dP_dPt_branch_lil, dP_dPt_acdc_lil, dP_dPt_hvdc, dP_dPt_contbr_lil]).tolil()
    dP_dPt_lil = dP_dPt_lil[ig_pbus, :][:, ix_pt]
    dQ_dQt_lil = hstack([dQ_dQt_branch_lil, dQ_dQt_acdc_lil, dQ_dQt_hvdc, dQ_dQt_contbr_lil]).tolil()
    dQ_dQt_lil = dQ_dQt_lil[ig_qbus, :][:, ix_qt]

    dP_dQt_lil = csc_matrix((len(ig_pbus), len(ix_qt)), dtype=np.float64).tocsr().tolil()
    dQ_dPt_lil = csc_matrix((len(ig_qbus), len(ix_pt)), dtype=np.float64).tocsr().tolil()

    dS_dPt_lil = vstack([dP_dPt_lil, dQ_dPt_lil])
    dS_dQt_lil = vstack([dP_dQt_lil, dQ_dQt_lil])
    dS_dSt_lil = hstack([dS_dPt_lil, dS_dQt_lil])
    assert dS_dSt_lil.shape == (len(ig_sbus), len(ix_pt) + len(
        ix_qt)), f"Shape is {dS_dSt_lil.shape}, it should be {len(ig_sbus), len(ix_pt) + len(ix_qt)}"
    print()

    '''
    dS_dtau and dS_dm from csc_derivatives.py, already there
    where complex_tap = m * e ^ (1j * tau) and tap_modules = m 
    '''
    dS_dtau = deriv.dSbus_dtau_csc(nbus, ig_sbus, ix_tau, F, T, Ys, kconv, complex_tap, V)
    dP_dtau = dS_dtau.real
    dQ_dtau = dS_dtau.imag
    dS_dm = deriv.dSbus_dm_csc(nbus, ig_sbus, ix_m, F, T, Ys, Bc, kconv, complex_tap, tap_modules, V)
    dP_dm = dS_dm.real
    dQ_dm = dS_dm.imag
    # ds_dbr = csc_stack_2d_ff(mats=[dP_dtau, dQ_dtau, dP_dm, dQ_dm], n_rows=2, n_cols=2)

    dP_dtau_lil = mat_to_scipy(dP_dtau).tocsr().tolil()
    dQ_dtau_lil = mat_to_scipy(dQ_dtau).tocsr().tolil()
    dP_dtau_lil = dP_dtau_lil[ig_pbus, :][:, ix_tau]
    dQ_dtau_lil = dQ_dtau_lil[ig_qbus, :][:, ix_tau]
    dP_dm_lil = mat_to_scipy(dP_dm).tocsr().tolil()
    dQ_dm_lil = mat_to_scipy(dQ_dm).tocsr().tolil()
    dP_dm_lil = dP_dm_lil[ig_pbus, :][:, ix_m]
    dQ_dm_lil = dQ_dm_lil[ig_qbus, :][:, ix_m]

    dS_dtau_lil = vstack([dP_dtau_lil, dQ_dtau_lil])
    dS_dm_lil = vstack([dP_dm_lil, dQ_dm_lil])
    assert dS_dtau_lil.shape == (
    len(ig_sbus), len(ix_tau)), f"Shape is {dS_dtau_lil.shape}, it should be {len(ig_sbus), len(ix_tau)}"
    assert dS_dm_lil.shape == (
    len(ig_sbus), len(ix_m)), f"Shape is {dS_dm_lil.shape}, it should be {len(ig_sbus), len(ix_m)}"

    print()

    # First 2 rows completed up to here
    J2rows = hstack([dS_dV_lil, ds_dSzip_lil, dS_dSf_lil, dS_dSt_lil, dS_dtau_lil, dS_dm_lil])

    '''
    # VSC loss eq.
    # Derivatives from Raiyan's thesis, 4 nnz terms, no big deal
    # Do we want to run njit? And will numba handle it well?
    nvsc = len(ig_plossacdc)
    pq_sqrt = np.sqrt(Pt[ig_plossacdc] * Pt[ig_plossacdc] + Qt[ig_plossacdc] * Qt[ig_plossacdc])
    pq_sqrt += 1e-20 #add a tiny tiny number to avoid division by zero
    # dLacdc_dVm applies only to the T side
    dLacdc_dVm = ((alpha2 * pq_sqrt * Qt[ig_plossacdc]) / (Vm[T_acdc] * Vm[T_acdc])
                  + 2 * alpha3 * (Pt[ig_plossacdc] * Pt[ig_plossacdc] + Qt[ig_plossacdc] * Qt[ig_plossacdc]) / (
                              Vm[T_acdc] * Vm[T_acdc] * Vm[T_acdc]))

    dLacdc_dPt = np.ones(nvsc) - alpha2 * Pt[ig_plossacdc] / (Vm[T_acdc] * pq_sqrt) - 2 * alpha3 * Pt[ig_plossacdc] / (
                Vm[T_acdc] * Vm[T_acdc])
    dLacdc_dQt = - alpha2 * Qt[ig_plossacdc] / (Vm[T_acdc] * pq_sqrt) - 2 * alpha3 * Qt[ig_plossacdc] / (
                Vm[T_acdc] * Vm[T_acdc])
    dLacdc_dPf = np.ones(nvsc)
    
    '''
    nvsc = len(ig_plossacdc)
    pq = Pt[ig_plossacdc] * Pt[ig_plossacdc] + Qt[ig_plossacdc] * Qt[ig_plossacdc]
    pq_sqrt = np.sqrt(pq)
    pq_sqrt += 1e-20
    dLacdc_dVm = alpha2 * pq_sqrt / (Vm[T_acdc] * Vm[T_acdc]) + 2 * alpha3 * (pq) / (
                Vm[T_acdc] * Vm[T_acdc] * Vm[T_acdc])
    dLacdc_dVm *= -1

    dLacdc_dPt = np.ones(nvsc) - alpha2 * Pt[ig_plossacdc] / (Vm[T_acdc] * pq_sqrt) - 2 * alpha3 * Pt[ig_plossacdc] / (
                Vm[T_acdc] * Vm[T_acdc])
    dLacdc_dPt *= -1

    _a = alpha2 * Qt[ig_plossacdc] / (Vm[T_acdc] * pq_sqrt)
    _b = 2 * alpha3 * Qt[ig_plossacdc] / (Vm[T_acdc] * Vm[T_acdc])
    dLacdc_dQt = - _a - _b
    dLacdc_dQt *= -1

    dLacdc_dPf = np.ones(nvsc)
    dLacdc_dPf *= -1

    I = np.eye(nvsc)
    j_L_Vt = np.multiply(Ct_acdc.transpose().toarray(), dLacdc_dVm)
    j_L_Pt = np.multiply(I, dLacdc_dPt)
    j_L_Qt = np.multiply(I, dLacdc_dQt)
    j_L_Pf = np.multiply(I, dLacdc_dPf)
    j_L_Vt_trimmed = csr_matrix(j_L_Vt)[ix_vm, :].transpose()
    vsc_ix_pf = np.intersect1d(ig_plossacdc, ix_pf)
    vsc_ix_qf = np.intersect1d(ig_plossacdc, ix_qf)
    vsc_ix_pt = np.intersect1d(ig_plossacdc, ix_pt)
    vsc_ix_qt = np.intersect1d(ig_plossacdc, ix_qt)
    remapped_ix_pf = vsc_ix_pf - nbr
    remapped_ix_qf = vsc_ix_qf - nbr
    remapped_ix_pt = vsc_ix_pt - nbr
    remapped_ix_qt = vsc_ix_qt - nbr
    j_L_Pf_trimmed = csr_matrix(j_L_Pf)[:, remapped_ix_pf]
    j_L_Pt_trimmed = csr_matrix(j_L_Pt)[:, remapped_ix_pt]
    j_L_Qt_trimmed = csr_matrix(j_L_Qt)[:, remapped_ix_qt]

    # now we make the chunks of zeros
    ncontBr_hvdc_ix_pf = len(ix_pf) - len(remapped_ix_pf)
    ncontBr_hvdc_ix_qf = len(ix_qf) - len(remapped_ix_qf)
    ncontBr_hvdc_ix_pt = len(ix_pt) - len(remapped_ix_pt)
    ncontBr_hvdc_ix_qt = len(ix_qt) - len(remapped_ix_qt)
    dL_dVa = csc_matrix((nvsc, len(ix_va)))
    dL_dPzip = csc_matrix((nvsc, len(ix_pzip)))
    dL_dQzip = csc_matrix((nvsc, len(ix_qzip)))
    dL_dPfrom_Trafo = csc_matrix((nvsc, ncontBr_hvdc_ix_pf))
    dL_dQfrom_Trafo = csc_matrix((nvsc, ncontBr_hvdc_ix_qf))
    dL_dPto_Trafo = csc_matrix((nvsc, ncontBr_hvdc_ix_pt))
    dL_dQto_Trafo = csc_matrix((nvsc, ncontBr_hvdc_ix_qt))
    dL_dMod_Trafo = csc_matrix((nvsc, len(ix_m)))
    dL_dTau_Trafo = csc_matrix((nvsc, len(ix_tau)))

    '''
    |j_L_Vt_trimmed|dL_dVa|dL_dPzip|dL_dQzip|j_L_Pf_trimmed|j_L_Pt_trimmed|j_L_Qt_trimmed|dL_dPfrom_Trafo|dL_dQfrom_Trafo|dL_dPto_Trafo|dL_dQto_Trafo|dL_dMod_Trafo|dL_dTau_Trafo|
    '''
    hChunk0 = hstack(
        [j_L_Vt_trimmed.tocsc(), dL_dVa, dL_dPzip, dL_dQzip, j_L_Pf_trimmed.tocsc(), j_L_Pt_trimmed.tocsc(),
         j_L_Qt_trimmed.tocsc(), dL_dPfrom_Trafo, dL_dQfrom_Trafo, dL_dPto_Trafo, dL_dQto_Trafo, dL_dMod_Trafo,
         dL_dTau_Trafo])

    # # BUILD J (without hvdc)
    # J = scipy_to_mat(vstack([J2rows, hChunk0]).tocsc())
    # return J

    """
    # HVDC loss eq. (work in progress)
    # compute them going through a loop better
    Pc = (Pset + (Va[F] - Va[T]) * mode * droop) / Sbase
    We simplify mode * droop = md
    Pc = (Pset + (Va[F] - Va[T]) * md) / Sbase
    Derivatives are dependent on the sign, hence we have two regions to consider
    Go over a loop to compute them
    
    If Pc > 0:
    ------------
    dPlosshvdc_dVa[F] = md / Sbase - rpu * (md * md * (2 * Va[F] - 2 * Va[T]) / (Sbase * Sbase * Vm[F] * Vm[F])
                                            + (2 * Pset * md) / (Sbase * Sbase * Vm[F] * Vm[F]))
                                            
    dPlosshvdc_dVa[T] = -md / Sbase - rpu * (md * md * (2 * Va[F] - 2 * Va[T]) / (Sbase * Sbase * Vm[F] * Vm[F])
                                        - (2 * Pset * md) / (Sbase * Sbase * Vm[F] * Vm[F]))
                                        
    dPlosshvdc_dVm[F] = -rpu * (-2 * Pset * Pset / (Sbase * Sbase * Vm[F] * Vm[F] * Vm[F])
                                -2 * md * md * (Va[F] * Va[F] + Va[T] * Va[T] - 2 * Va[F] * Va[T]) / (Sbase * Sbase * Vm[F] * Vm[F] * Vm[F]) 
                                -4 * Pset * (Va[F] - Va[T]) * md / (Sbase * Sbase * Vm[F] * Vm[F] * Vm[F]))
                         
    dPlosshvdc_dPt[br_hvdc] = 1
    
    Elif Pc < 0:
    ------------
     dPlosshvdc_dVa[F] = md / Sbase - rpu * (md * md * (2 * Va[F] - 2 * Va[T]) / (Sbase * Sbase * Vm[T] * Vm[T])
                                            + (2 * Pset * md) / (Sbase * Sbase * Vm[T] * Vm[T]))
                                            
     dPlosshvdc_dVa[T] = -md / Sbase - rpu * (md * md * (2 * Va[F] - 2 * Va[T]) / (Sbase * Sbase * Vm[T] * Vm[T])
                                        - (2 * Pset * md) / (Sbase * Sbase * Vm[T] * Vm[T]))
                                        
     dPlosshvdc_dVm[F] = -rpu * (-2 * Pset * Pset / (Sbase * Sbase * Vm[T] * Vm[T] * Vm[T])
                                -2 * md * md * (Va[F] * Va[F] + Va[T] * Va[T] - 2 * Va[F] * Va[T]) / (Sbase * Sbase * Vm[T] * Vm[T] * Vm[T]) 
                                -4 * Pset * (Va[F] - Va[T]) * md / (Sbase * Sbase * Vm[T] * Vm[T] * Vm[T]))
                           
    dPlosshvdc_dPf[br_hvdc] = 1
    
    Else:
        edge case, simply set derivatives to 0 (very unlikely to take place and could ill-condition J if row of 0s)
    """

    # HVDC injection equation
    """
    Pc = (Pset + (Va[F] - Va[T]) * mode * droop) / Sbase
    We simplify mode * droop = md
    Pc = (Pset + (Va[F] - Va[T]) * md) / Sbase
    Derivatives are dependent on the sign, hence we have two regions to consider
    Go over a loop to compute them
    
    If Pc > 0: Pf - (Pset + (Va[F] - Va[T]) * md) / Sbase = 0
    ------------
    dPinjhvdc_dVa[F] = - md / Sbase
    dPinjhvdc_dVa[T] = md / Sbase
    dPinjhvdc_dPf[br_hvdc] = 1
    
    Elif Pc < 0: Pt - (Pset + (Va[F] - Va[T]) * md) / Sbase = 0 
    ------------
    dPinjhvdc_dVa[F] = - md / Sbase
    dPinjhvdc_dVa[T] = md / Sbase
    dPinjhvdc_dPt[br_hvdc] = 1
    """
    # jac = lil_matrix((n_rows, nx))
    nhvdc = len(ig_plosshvdc)
    dPlosshvdc_dVa = np.zeros(nbus)
    dPlosshvdc_dVm = np.zeros(nbus)
    dPlosshvdc_dPf = np.zeros(nhvdc)
    dPlosshvdc_dPt = np.zeros(nhvdc)
    dPinjhvdc_dVa = np.zeros(nbus)
    dPinjhvdc_dPf = np.zeros(nhvdc)
    dPinjhvdc_dPt = np.zeros(nhvdc)

    for i in range(nhvdc):
        dtheta = np.rad2deg(Va[T_hvdc[i]] - Va[F_hvdc[i]])
        droop_contr = hvdc_mode[i] * hvdc_angle_droop[i] * dtheta
        pCalc = hvdc_pset[i] + droop_contr
        md = hvdc_mode[i] * hvdc_angle_droop[i]
        F = F_hvdc[i]
        T = T_hvdc[i]

        if pCalc > 0:
            rpu = hvdc_r[i] * Sbase / (hvdc_Vnf[i] * hvdc_Vnt[i])
            dPlosshvdc_dVa[F] = (md / Sbase)
            dPlosshvdc_dVa[F] -= rpu * (md * md * (2 * Va[F_hvdc[i]] - 2 * Va[T_hvdc[i]]) / (
                        Sbase * Sbase * Vm[F_hvdc[i]] * Vm[F_hvdc[i]]))
            dPlosshvdc_dVa[F] += (2 * hvdc_pset[i] * md) / (Sbase * Sbase * Vm[F_hvdc[i]] * Vm[F_hvdc[i]])

            dPlosshvdc_dVa[T] = (-md / Sbase)
            dPlosshvdc_dVa[T] -= rpu * (md * md * (2 * Va[F_hvdc[i]] - 2 * Va[T_hvdc[i]]) / (
                        Sbase * Sbase * Vm[F_hvdc[i]] * Vm[F_hvdc[i]]))
            dPlosshvdc_dVa[T] -= (2 * hvdc_pset[i] * md) / (Sbase * Sbase * Vm[F_hvdc[i]] * Vm[F_hvdc[i]])

            dPlosshvdc_dVm[F] = -rpu * (-2 * hvdc_pset[i] * hvdc_pset[i] / (
                        Sbase * Sbase * Vm[F_hvdc[i]] * Vm[F_hvdc[i]] * Vm[F_hvdc[i]]))
            dPlosshvdc_dVm[F] -= 2 * md * md * (
                        Va[F_hvdc[i]] * Va[F_hvdc[i]] + Va[T_hvdc[i]] * Va[T_hvdc[i]] - 2 * Va[F_hvdc[i]] * Va[
                    T_hvdc[i]]) / (Sbase * Sbase * Vm[F_hvdc[i]] * Vm[F_hvdc[i]] * Vm[F_hvdc[i]])
            dPlosshvdc_dVm[F] -= 4 * hvdc_pset[i] * (Va[F_hvdc[i]] - Va[T_hvdc[i]]) * md / (
                        Sbase * Sbase * Vm[F_hvdc[i]] * Vm[F_hvdc[i]] * Vm[F_hvdc[i]])

            dPlosshvdc_dPt[i] = 1

            dPinjhvdc_dVa[F] = -md / Sbase
            dPinjhvdc_dVa[T] = md / Sbase
            dPinjhvdc_dPf[i] = 1


        elif pCalc < 0:
            dPlosshvdc_dVa[F] = (md / Sbase)
            dPlosshvdc_dVa[F] -= rpu * (md * md * (2 * Va[F_hvdc[i]] - 2 * Va[T_hvdc[i]]) / (
                        Sbase * Sbase * Vm[T_hvdc[i]] * Vm[T_hvdc[i]]))
            dPlosshvdc_dVa[F] += (2 * hvdc_pset[i] * md) / (Sbase * Sbase * Vm[T_hvdc[i]] * Vm[T_hvdc[i]])

            dPlosshvdc_dVa[T] = (-md / Sbase)
            dPlosshvdc_dVa[T] -= rpu * (md * md * (2 * Va[F_hvdc[i]] - 2 * Va[T_hvdc[i]]) / (
                        Sbase * Sbase * Vm[T_hvdc[i]] * Vm[T_hvdc[i]]))
            dPlosshvdc_dVa[T] -= (2 * hvdc_pset[i] * md) / (Sbase * Sbase * Vm[T_hvdc[i]] * Vm[T_hvdc[i]])

            dPlosshvdc_dVm[F] = -rpu * (-2 * hvdc_pset[i] * hvdc_pset[i] / (
                        Sbase * Sbase * Vm[T_hvdc[i]] * Vm[T_hvdc[i]] * Vm[T_hvdc[i]]))
            dPlosshvdc_dVm[F] -= 2 * md * md * (
                        Va[F_hvdc[i]] * Va[F_hvdc[i]] + Va[T_hvdc[i]] * Va[T_hvdc[i]] - 2 * Va[F_hvdc[i]] * Va[
                    T_hvdc[i]]) / (Sbase * Sbase * Vm[T_hvdc[i]] * Vm[T_hvdc[i]] * Vm[T_hvdc[i]])
            dPlosshvdc_dVm[F] -= 4 * hvdc_pset[i] * (Va[F_hvdc[i]] - Va[T_hvdc[i]]) * md / (
                        Sbase * Sbase * Vm[T_hvdc[i]] * Vm[T_hvdc[i]] * Vm[T_hvdc[i]])

            dPlosshvdc_dPf[i] = 1

            dPinjhvdc_dVa[F] = -md / Sbase
            dPinjhvdc_dVa[T] = md / Sbase
            dPinjhvdc_dPt[i] = 1

        else:
            pass

    # slice Ct_hvdc using ig_plosshvdc
    conn_hvdc = Ct_hvdc[:, ig_plosshvdc]

    j_Ploss_Vm = np.multiply(conn_hvdc.transpose().toarray(), dPlosshvdc_dVm)
    j_Ploss_Va = np.multiply(conn_hvdc.transpose().toarray(), dPlosshvdc_dVa)
    j_Ploss_Pt = np.multiply(np.eye(nhvdc), dPlosshvdc_dPt)
    j_Ploss_Pf = np.multiply(np.eye(nhvdc), dPlosshvdc_dPf)
    j_Pinj_Va = np.multiply(conn_hvdc.transpose().toarray(), dPinjhvdc_dVa)
    j_Pinj_Pf = np.multiply(np.eye(nhvdc), dPinjhvdc_dPf)
    j_Pinj_Pt = np.multiply(np.eye(nhvdc), dPinjhvdc_dPt)

    j_Ploss_Vm_trimmed = csr_matrix(j_Ploss_Vm)[:, ix_vm].transpose()
    j_Ploss_Va_trimmed = csr_matrix(j_Ploss_Va)[:, ix_va]
    j_Pinj_Va_trimmed = csr_matrix(j_Pinj_Va)[:, ix_va]

    hvdc_ix_pf = np.intersect1d(ig_plosshvdc, ix_pf)
    hvdc_ix_qf = np.intersect1d(ig_plosshvdc, ix_qf)
    hvdc_ix_pt = np.intersect1d(ig_plosshvdc, ix_pt)
    hvdc_ix_qt = np.intersect1d(ig_plosshvdc, ix_qt)

    remapped_hvdc_ix_pf = hvdc_ix_pf - nbr - nvsc
    remapped_hvdc_ix_qf = hvdc_ix_qf - nbr - nvsc
    remapped_hvdc_ix_pt = hvdc_ix_pt - nbr - nvsc
    remapped_hvdc_ix_qt = hvdc_ix_qt - nbr - nvsc

    # TODO: When slicing by column, CSC is best
    j_Ploss_Pf_trimmed = csr_matrix(j_Ploss_Pf)[:, remapped_hvdc_ix_pf]
    j_Ploss_Pt_trimmed = csr_matrix(j_Ploss_Pt)[:, remapped_hvdc_ix_pt]
    j_Pinj_Pf_trimmed = csr_matrix(j_Pinj_Pf)[:, remapped_hvdc_ix_pf]
    j_Pinj_Pt_trimmed = csr_matrix(j_Pinj_Pt)[:, remapped_hvdc_ix_pt]

    # now we pad zeros
    ncontBr_hvdc_ix_pf = len(ix_pf) - len(remapped_hvdc_ix_pf)
    ncontBr_hvdc_ix_qf = len(ix_qf) - len(remapped_hvdc_ix_qf)
    ncontBr_hvdc_ix_pt = len(ix_pt) - len(remapped_hvdc_ix_pt)
    ncontBr_hvdc_ix_qt = len(ix_qt) - len(remapped_hvdc_ix_qt)
    dBuffer_dVm = csc_matrix((nhvdc, len(ix_vm)))
    dBuffer_dVa = csc_matrix((nhvdc, len(ix_va)))
    dBuffer_dPzip = csc_matrix((nhvdc, len(ix_pzip)))
    dBuffer_dQzip = csc_matrix((nhvdc, len(ix_qzip)))
    dBuffer_dPfrom_vsc = csc_matrix((nhvdc, len(remapped_ix_pf)))
    dBuffer_dQfrom_vsc = csc_matrix((nhvdc, len(remapped_ix_qf)))
    dBuffer_dPto_vsc = csc_matrix((nhvdc, len(remapped_ix_pt)))
    dBuffer_dQto_vsc = csc_matrix((nhvdc, len(remapped_ix_qt)))
    dBuffer_dQfrom_hvdc = csc_matrix((nhvdc, len(remapped_hvdc_ix_qf)))
    dBuffer_dQto_hvdc = csc_matrix((nhvdc, len(remapped_hvdc_ix_pt)))
    dBuffer_dPfrom_Trafo = csc_matrix((nhvdc, ncontBr_hvdc_ix_pf))
    dBuffer_dQfrom_Trafo = csc_matrix((nhvdc, ncontBr_hvdc_ix_qf))
    dBuffer_dPto_Trafo = csc_matrix((nhvdc, ncontBr_hvdc_ix_pt))
    dBuffer_dQto_Trafo = csc_matrix((nhvdc, ncontBr_hvdc_ix_qt))
    dBuffer_dMod_Trafo = csc_matrix((nhvdc, len(ix_m)))
    dBuffer_dTau_Trafo = csc_matrix((nhvdc, len(ix_tau)))

    pLoss = hstack([j_Ploss_Vm_trimmed.tocsc(), j_Ploss_Va_trimmed.tocsc(), dBuffer_dPzip, dBuffer_dQzip,
                    j_Ploss_Pf_trimmed.tocsc(), dBuffer_dPfrom_Trafo,
                    dBuffer_dQfrom_vsc, dBuffer_dQfrom_hvdc, dBuffer_dQfrom_Trafo, dBuffer_dPto_vsc,
                    j_Ploss_Pt_trimmed.tocsc(), dBuffer_dPto_Trafo, dBuffer_dQto_vsc, dBuffer_dQto_hvdc,
                    dBuffer_dQto_Trafo,
                    dBuffer_dMod_Trafo, dBuffer_dTau_Trafo])

    pInj = hstack([dBuffer_dVm, j_Pinj_Va_trimmed.tocsc(), dBuffer_dPzip, dBuffer_dQzip, dBuffer_dPfrom_vsc,
                   j_Pinj_Pf_trimmed.tocsc(), dBuffer_dPfrom_Trafo,
                   dBuffer_dQfrom_vsc, dBuffer_dQfrom_hvdc, dBuffer_dQfrom_Trafo, dBuffer_dPto_vsc,
                   j_Pinj_Pt_trimmed.tocsc(), dBuffer_dPto_Trafo, dBuffer_dQto_vsc, dBuffer_dQto_hvdc,
                   dBuffer_dQto_Trafo,
                   dBuffer_dMod_Trafo, dBuffer_dTau_Trafo])

    print()
    # BUILD J (with hvdc without trafo)
    J = scipy_to_mat(vstack([J2rows, hChunk0, pLoss, pInj]).tocsc())
    print("J")
    print(J.toarray())
    return J

    """
    Controllable branches dSft_dmtau already computed in csc_derivatives.py (Not finished yet)
    """
    dPf_dVa = deriv.dSf_dVa_csc(nbus, ig_pftr, ix_va, yff, yft, V, F, T).real
    dQf_dVa = deriv.dSf_dVa_csc(nbus, ig_qftr, ix_va, yff, yft, V, F, T).imag
    dPt_dVa = deriv.dSt_dVa_csc(nbus, ig_pttr, ix_va, ytf, V, F, T).real
    dQt_dVa = deriv.dSt_dVa_csc(nbus, ig_qttr, ix_va, ytf, V, F, T).imag

    # SLICE
    dP_dVm = sp_slice(dS_dVm.real, ig_pbus, ix_vm)
    dQ_dVm = sp_slice(dS_dVm.imag, ig_qbus, ix_vm)
    dP_dVa = sp_slice(dS_dVa.real, ig_pbus, ix_va)
    dQ_dVa = sp_slice(dS_dVa.imag, ig_qbus, ix_va)

    return J


def calc_autodiff_jacobian(func: Callable[[Vec], Vec], x: Vec, h=1e-8) -> csc_matrix:
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

    return jac.tocsc()


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

        print("(pf_generalized_formulation.py) self.nc.passive_branch_data.nelm: ", self.nc.passive_branch_data.nelm)
        print("(pf_generalized_formulation.py) self.nc.active_branch_data.nelm: ", self.nc.active_branch_data.nelm)
        print("(pf_generalized_formulation.py) self.nc.vsc_data.nelm: ", self.nc.vsc_data.nelm)

        # TODO: need to take into account every device eventually
        self.I0: CxVec = self.nc.load_data.get_current_injections_per_bus() / self.nc.Sbase
        self.Y0: CxVec = self.nc.load_data.get_admittance_injections_per_bus() / self.nc.Sbase
        self.S0: CxVec = self.nc.load_data.get_injections_per_bus() / self.nc.Sbase
        self.V0: CxVec = V0

        print(f"self.S0: {self.S0}")
        print(f"self.I0: {self.I0}")
        print(f"self.Y0: {self.Y0}")
        print(f"self.V0: {self.V0}")

        # QUESTION: is there a reason not to do this? I use this in var2x
        self.Sbus = compute_zip_power(self.S0, self.I0, self.Y0, self.Vm)
        self.Sf: CxVec = np.zeros(nc.active_branch_data.nelm + nc.nvsc + nc.nhvdc, dtype=np.complex128)
        self.St: CxVec = np.zeros(nc.active_branch_data.nelm + nc.nvsc + nc.nhvdc, dtype=np.complex128)
        # self.Sf: CxVec = np.zeros(nc.nbr, dtype=np.complex128)
        # self.St: CxVec = np.zeros(nc.nbr, dtype=np.complex128)

        self.Pzip = np.zeros(nc.nbus)
        self.Qzip = np.zeros(nc.nbus)
        self.Pf = np.real(self.Sf)
        self.Qf = np.imag(self.Sf)
        self.Pt = np.real(self.St)
        self.Qt = np.imag(self.St)

        print(f"self.Pbus: {self.Pzip}")
        print(f"self.Qbus: {self.Qzip}")
        print(f"self.Sf: {self.Sf}")
        print(f"self.Pf: {self.Pf}")
        print(f"self.Qf: {self.Qf}")
        print(f"self.St: {self.St}")
        print(f"self.Pt: {self.Pt}")
        print(f"self.Qt: {self.Qt}")

        self.bus_types = self.nc.bus_data.bus_types.copy()
        self.tap_module_control_mode = self.nc.active_branch_data.tap_module_control_mode.copy()
        self.tap_phase_control_mode = self.nc.active_branch_data.tap_phase_control_mode.copy()

        self.pq = np.array(0, dtype=int)
        self.pv = np.array(0, dtype=int)
        self.pqv = np.array(0, dtype=int)
        self.p = np.array(0, dtype=int)
        self.idx_conv = np.array(0, dtype=int)

        self.idx_dVa = np.array(0, dtype=int)
        self.idx_dVm = np.array(0, dtype=int)
        self.idx_dP = np.array(0, dtype=int)
        self.idx_dQ = np.array(0, dtype=int)

        self.idx_dm = np.array(0, dtype=int)
        self.idx_dtau = np.array(0, dtype=int)
        self.idx_dbeq = np.array(0, dtype=int)

        self.idx_dPf = np.array(0, dtype=int)
        self.idx_dQf = np.array(0, dtype=int)

        self.idx_dPt = np.array(0, dtype=int)
        self.idx_dQt = np.array(0, dtype=int)

        # Generalized indices
        self.indices = gsi.GeneralizedSimulationIndices(self.nc)
        self.controlled_idx = self.nc.active_branch_data.get_controlled_idx()
        self.fixed_idx = self.nc.active_branch_data.get_fixed_idx()
        self.hvdc_mode = self.indices.hvdc_mode
        print()
        # cg sets
        self.cg_pac = self.indices.cg_pac
        self.cg_qac = self.indices.cg_qac
        self.cg_pdc = self.indices.cg_pdc
        self.cg_acdc = self.indices.cg_acdc
        self.cg_hvdc = self.indices.cg_hvdc
        self.cg_pftr = self.indices.cg_pftr
        self.cg_pttr = self.indices.cg_pttr
        self.cg_qftr = self.indices.cg_qftr
        self.cg_qttr = self.indices.cg_qttr

        # cx sets [UNKNOWNS] The order of this list is important
        self.cx_vm = self.indices.cx_vm
        self.cx_va = self.indices.cx_va
        self.cx_pzip = self.indices.cx_pzip
        self.cx_qzip = self.indices.cx_qzip
        self.cx_pfa = self.indices.cx_pfa
        self.cx_qfa = self.indices.cx_qfa
        self.cx_pta = self.indices.cx_pta
        self.cx_qta = self.indices.cx_qta
        self.cx_m = self.indices.cx_m
        self.cx_tau = self.indices.cx_tau

        # ck sets [KNOWNS]
        self.ck_vm = self.indices.ck_vm
        self.ck_va = self.indices.ck_va
        self.ck_pzip = self.indices.ck_pzip
        self.ck_qzip = self.indices.ck_qzip
        self.ck_pfa = self.indices.ck_pfa
        self.ck_qfa = self.indices.ck_qfa
        self.ck_pta = self.indices.ck_pta
        self.ck_qta = self.indices.ck_qta
        self.ck_m = self.indices.ck_m
        self.ck_tau = self.indices.ck_tau

        # setpoints corresponding to the knowns
        self.va_setpoints = self.indices.va_setpoints
        self.vm_setpoints = self.indices.vm_setpoints
        self.tau_setpoints = self.indices.tau_setpoints
        self.m_setpoints = self.indices.m_setpoints
        self.pzip_setpoints = self.indices.pzip_setpoints
        self.qzip_setpoints = self.indices.qzip_setpoints
        self.pf_setpoints = self.indices.pf_setpoints
        self.pt_setpoints = self.indices.pt_setpoints
        self.qf_setpoints = self.indices.qf_setpoints
        self.qt_setpoints = self.indices.qt_setpoints

        # Update setpoints
        self.Vm[self.indices.ck_vm] = self.indices.vm_setpoints
        self.Va[self.indices.ck_va] = self.indices.va_setpoints
        self.Pzip[self.indices.ck_pzip] = np.array(self.indices.pzip_setpoints) / nc.Sbase
        idx = np.where(nc.bus_data.bus_types == BusMode.Slack_tpe.value)[0]
        self.Pzip[idx] = self.Sbus[idx].real  # before we were grabbing the idx, seemed wrong to me
        self.Qzip[self.indices.ck_qzip] = np.array(self.indices.qzip_setpoints) / nc.Sbase
        self.Pf[self.indices.ck_pfa] = np.array(self.indices.pf_setpoints) / nc.Sbase
        self.Pt[self.indices.ck_pta] = np.array(self.indices.pt_setpoints) / nc.Sbase
        self.Qt[self.indices.ck_qta] = np.array(self.indices.qt_setpoints) / nc.Sbase

        self.cx_m_indexing = np.arange(len(self.cx_m))
        self.cx_tau_indexing = np.arange(len(self.cx_tau))
        self.m: Vec = np.ones(len(self.cx_m))
        self.tau: Vec = np.zeros(len(self.cx_tau))

        self.Ys: CxVec = self.nc.passive_branch_data.get_series_admittance()

        R = np.full(nc.nbr, 1e+20)
        X = np.full(nc.nbr, 1e+20)
        G = np.zeros(nc.nbr, dtype=float)
        B = np.zeros(nc.nbr, dtype=float)
        k = np.ones(nc.nbr, dtype=float)
        tap_module = np.ones(nc.nbr, dtype=float)
        tap_angle = np.zeros(nc.nbr, dtype=float)

        # fill the fixed indices with a small value
        R[self.fixed_idx] = nc.passive_branch_data.R[self.fixed_idx]
        X[self.fixed_idx] = nc.passive_branch_data.X[self.fixed_idx]
        G[self.fixed_idx] = nc.passive_branch_data.G[self.fixed_idx]
        B[self.fixed_idx] = nc.passive_branch_data.B[self.fixed_idx]
        tap_module[self.fixed_idx] = nc.active_branch_data.tap_module[self.fixed_idx]
        tap_angle[self.fixed_idx] = nc.active_branch_data.tap_angle[self.fixed_idx]

        self.adm = compute_admittances(
            R=R,
            X=X,
            G=G,
            B=B,
            k=k,
            tap_module=tap_module,
            vtap_f=self.nc.passive_branch_data.virtual_tap_f,
            vtap_t=self.nc.passive_branch_data.virtual_tap_t,
            tap_angle=tap_angle,
            Cf=self.nc.Cf,
            Ct=self.nc.Ct,
            Yshunt_bus=self.nc.Yshunt_from_devices,
            conn=self.nc.passive_branch_data.conn,
            seq=1,
            add_windings_phase=False
        )

    def x2var(self, x: Vec) -> None:
        """
        Convert X to decission variables
        :param x: solution vector
        """
        a = len(self.cx_vm)
        b = a + len(self.cx_va)
        c = b + len(self.cx_pzip)
        d = c + len(self.cx_qzip)
        e = d + len(self.cx_pfa)
        f = e + len(self.cx_qfa)
        g = f + len(self.cx_pta)
        h = g + len(self.cx_qta)
        i = h + len(self.cx_m)
        j = i + len(self.cx_tau)

        # update the vectors
        self.Vm[self.cx_vm] = x[0:a]
        self.Va[self.cx_va] = x[a:b]
        self.Pzip[self.cx_pzip] = x[b:c]
        self.Qzip[self.cx_qzip] = x[c:d]
        self.Pf[self.cx_pfa] = x[d:e]
        self.Qf[self.cx_qfa] = x[e:f]
        self.Pt[self.cx_pta] = x[f:g]
        self.Qt[self.cx_qta] = x[g:h]
        self.m = x[h:i]
        self.tau = x[i:j]

    # DONE
    def var2x(self) -> Vec:
        """
        Convert the internal decision variables into the vector
        :return: Vector
        """
        return np.r_[
            self.Vm[self.cx_vm],
            self.Va[self.cx_va],
            self.Pzip[self.cx_pzip],
            self.Qzip[self.cx_qzip],
            self.Pf[self.cx_pfa],
            self.Qf[self.cx_qfa],
            self.Pt[self.cx_pta],
            self.Qt[self.cx_qta],
            self.m,
            self.tau
        ]

    # DONE
    def size(self) -> int:
        """
        Size of the jacobian matrix
        :return:
        """
        return (len(self.cx_vm)
                + len(self.cx_va)
                + len(self.cx_pzip)
                + len(self.cx_qzip)
                + len(self.cx_pfa)
                + len(self.cx_qfa)
                + len(self.cx_pta)
                + len(self.cx_qta)
                + len(self.cx_m)
                + len(self.cx_tau))

    def compute_f(self, x: Vec) -> Vec:
        """
        Compute the residual vector
        :param x: Solution vector
        :return: Residual vector
        """

        a = len(self.cx_vm)
        b = a + len(self.cx_va)
        c = b + len(self.cx_pzip)
        d = c + len(self.cx_qzip)
        e = d + len(self.cx_pfa)
        f = e + len(self.cx_qfa)
        g = f + len(self.cx_pta)
        h = g + len(self.cx_qta)
        i = h + len(self.cx_m)
        j = i + len(self.cx_tau)

        # update the vectors
        Va = self.Va.copy()
        Vm = self.Vm.copy()
        Pbus = self.Pzip.copy()
        Qbus = self.Qzip.copy()
        Pf = self.Pf.copy()
        Qf = self.Qf.copy()
        Pt = self.Pt.copy()
        Qt = self.Qt.copy()
        # m = self.m.copy()
        # tau = self.tau.copy()

        Vm[self.cx_vm] = x[0:a]
        Va[self.cx_va] = x[a:b]
        Pbus[self.cx_pzip] = x[b:c]
        Qbus[self.cx_qzip] = x[c:d]
        Pf[self.cx_pfa] = x[d:e]
        Qf[self.cx_qfa] = x[e:f]
        Pt[self.cx_pta] = x[f:g]
        Qt[self.cx_qta] = x[g:h]
        m = x[h:i]
        tau = x[i:j]

        # compute the complex voltage
        V = polar_to_rect(Vm, Va)

        # VSC Loss equation
        toBus = self.nc.vsc_data.T
        It = np.sqrt(Pt * Pt + Qt * Qt)[self.cg_acdc] / Vm[toBus]
        It2 = It * It
        PLoss_IEC = (self.nc.vsc_data.alpha3 * It2
                     + self.nc.vsc_data.alpha2 * It
                     + self.nc.vsc_data.alpha1)

        Ploss_acdc = PLoss_IEC - Pt[self.cg_acdc] - Pf[self.cg_acdc]

        # Legacy HVDC power injection (Pinj_hvdc) equation + loss (Ploss_hvdc) equation
        Ploss_hvdc = np.zeros(self.nc.nhvdc)
        Pinj_hvdc = np.zeros(self.nc.nhvdc)
        for i in range(self.nc.nhvdc):
            dtheta = np.rad2deg(Va[self.nc.hvdc_data.F[i]] - Va[self.nc.hvdc_data.T[i]])
            droop_contr = self.indices.hvdc_mode[i] * self.nc.hvdc_data.angle_droop[i] * dtheta
            Pcalc_hvdc = self.nc.hvdc_data.Pset[i] + droop_contr

            if Pcalc_hvdc > 0.0:
                ihvdcpu = Pcalc_hvdc / self.nc.Sbase / (Vm[self.nc.hvdc_data.F[i]])
                rpu = self.nc.hvdc_data.r[i] * self.nc.Sbase / (self.nc.hvdc_data.Vnf[i] * self.nc.hvdc_data.Vnf[i])
                losshvdcpu = rpu * ihvdcpu * ihvdcpu
                Ploss_hvdc[i] = Pt[self.cg_hvdc[i]] + Pcalc_hvdc / self.nc.Sbase - losshvdcpu
                Pinj_hvdc[i] = Pf[self.cg_hvdc[i]] - Pcalc_hvdc / self.nc.Sbase

            elif Pcalc_hvdc < 0.0:
                ihvdcpu = Pcalc_hvdc / self.nc.Sbase / (Vm[self.nc.hvdc_data.T[i]])
                rpu = self.nc.hvdc_data.r[i] * self.nc.Sbase / (self.nc.hvdc_data.Vnt[i] * self.nc.hvdc_data.Vnt[i])
                losshvdcpu = rpu * ihvdcpu * ihvdcpu
                Ploss_hvdc[i] = Pcalc_hvdc / self.nc.Sbase + Pf[self.cg_hvdc[i]] - losshvdcpu
                Pinj_hvdc[i] = Pt[self.cg_hvdc[i]] - Pcalc_hvdc / self.nc.Sbase

            else:
                Ploss_hvdc[i] = 0.0
                Pinj_hvdc[i] = 0.0

        # compute the function residual
        Sbus = compute_zip_power(self.S0, self.I0, self.Y0, Vm)
        Sbus += Pbus + 1j * Qbus
        Scalc = compute_power(self.adm.Ybus, V)

        dS = (
                Scalc - Sbus

                # add contribution of acdc link
                + ((Pf + 1j * Qf)[self.cg_acdc] @ self.nc.vsc_data.C_branch_bus_f
                   + (Pt + 1j * Qt)[self.cg_acdc] @ self.nc.vsc_data.C_branch_bus_t)

                # add contribution of HVDC link
                + ((Pf + 1j * Qf)[self.cg_hvdc] @ self.nc.hvdc_data.C_hvdc_bus_f
                   + (Pt + 1j * Qt)[self.cg_hvdc] @ self.nc.hvdc_data.C_hvdc_bus_t)

                # add contribution of transformer
                + ((Pf + 1j * Qf)[self.cg_pttr] @ self.nc.passive_branch_data.C_branch_bus_f[self.cg_pttr, :]
                   + (Pt + 1j * Qt)[self.cg_pttr] @ self.nc.passive_branch_data.C_branch_bus_t[self.cg_pttr, :])

        )

        V = Vm * np.exp(1j * Va)

        # remapping of indices
        m2 = np.ones(self.nc.nbr)
        m2[self.cx_m] = m.copy()
        tau2 = np.zeros(self.nc.nbr)
        tau2[self.cx_tau] = tau.copy()

        Pftr, Qftr, Pttr, Qttr = recompute_controllable_power(
            V_f=V[self.nc.passive_branch_data.F[self.controlled_idx]],
            V_t=V[self.nc.passive_branch_data.T[self.controlled_idx]],
            R=self.nc.passive_branch_data.R[self.controlled_idx],
            X=self.nc.passive_branch_data.X[self.controlled_idx],
            G=self.nc.passive_branch_data.G[self.controlled_idx],
            B=self.nc.passive_branch_data.B[self.controlled_idx],
            tap_module=m2[self.controlled_idx],
            vtap_f=self.nc.passive_branch_data.virtual_tap_f[self.controlled_idx],
            vtap_t=self.nc.passive_branch_data.virtual_tap_t[self.controlled_idx],
            tap_angle=tau2[self.controlled_idx]
        )

        _f = np.r_[
            dS[self.cg_pac + self.cg_pdc].real,
            dS[self.cg_qac].imag,
            Ploss_acdc,
            Ploss_hvdc,
            Pinj_hvdc,
            Pftr - self.nc.active_branch_data.Pset[self.cg_pftr],
            Qftr - self.nc.active_branch_data.Qset[self.cg_qftr],
            Pttr - self.nc.active_branch_data.Pset[self.cg_pttr],
            Qttr - self.nc.active_branch_data.Qset[self.cg_qttr]
        ]

        errf = compute_fx_error(_f)
        if errf < 1e-7:
            print()

        assert len(_f) == j, f"len(_f)={len(_f)} != j={j}"

        return _f

    def check_error(self, x: Vec) -> Tuple[float, Vec]:
        """
        Check error of the solution without affecting the problem
        :param x: Solution vector
        :return: error
        """
        _res = self.compute_f(x)
        err = compute_fx_error(_res)
        print("Error:", err)

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

        # Update converter losses
        toBus = self.nc.vsc_data.T
        It = np.sqrt(self.Pt * self.Pt + self.Qt * self.Qt)[self.cg_acdc] / self.Vm[toBus]
        It2 = It * It
        PLoss_IEC = (self.nc.vsc_data.alpha3 * It2
                     + self.nc.vsc_data.alpha2 * It
                     + self.nc.vsc_data.alpha1)

        # ACDC Power Loss Residual
        Ploss_acdc = PLoss_IEC - self.Pt[self.cg_acdc] - self.Pf[self.cg_acdc]

        # Legacy HVDC power injection (Pinj_hvdc) equation + loss (Ploss_hvdc) equation
        Ploss_hvdc = np.zeros(self.nc.nhvdc)
        Pinj_hvdc = np.zeros(self.nc.nhvdc)
        for i in range(self.nc.nhvdc):
            dtheta = np.rad2deg(self.Va[self.nc.hvdc_data.F[i]] - self.Va[self.nc.hvdc_data.T[i]])
            droop_contr = self.indices.hvdc_mode[i] * self.nc.hvdc_data.angle_droop[i] * dtheta
            Pcalc_hvdc = self.nc.hvdc_data.Pset[i] + droop_contr

            if Pcalc_hvdc > 0.0:
                ihvdcpu = Pcalc_hvdc / self.nc.Sbase / (self.Vm[self.nc.hvdc_data.F[i]])
                rpu = self.nc.hvdc_data.r[i] * self.nc.Sbase / (self.nc.hvdc_data.Vnf[i] * self.nc.hvdc_data.Vnf[i])
                losshvdcpu = rpu * ihvdcpu * ihvdcpu
                Ploss_hvdc[i] = self.Pt[self.cg_hvdc[i]] + Pcalc_hvdc / self.nc.Sbase - losshvdcpu
                Pinj_hvdc[i] = self.Pf[self.cg_hvdc[i]] - Pcalc_hvdc / self.nc.Sbase

            elif Pcalc_hvdc < 0.0:
                ihvdcpu = Pcalc_hvdc / self.nc.Sbase / (self.Vm[self.nc.hvdc_data.T[i]])
                rpu = self.nc.hvdc_data.r[i] * self.nc.Sbase / (self.nc.hvdc_data.Vnt[i] * self.nc.hvdc_data.Vnt[i])
                losshvdcpu = rpu * ihvdcpu * ihvdcpu
                Ploss_hvdc[i] = Pcalc_hvdc / self.nc.Sbase + self.Pf[self.cg_hvdc[i]] - losshvdcpu
                Pinj_hvdc[i] = self.Pt[self.cg_hvdc[i]] - Pcalc_hvdc / self.nc.Sbase

            else:
                Ploss_hvdc[i] = 0.0
                Pinj_hvdc[i] = 0.0

        # compute the function residual
        Sbus = compute_zip_power(self.S0, self.I0, self.Y0, self.Vm) + self.Pzip + 1j * self.Qzip
        Scalc = compute_power(self.adm.Ybus, self.V)

        dS = (
                Scalc - Sbus

                # add contribution of acdc link
                + ((self.Pf + 1j * self.Qf)[self.cg_acdc] @ self.nc.vsc_data.C_branch_bus_f
                   + (self.Pt + 1j * self.Qt)[self.cg_acdc] @ self.nc.vsc_data.C_branch_bus_t)

                # add contribution of HVDC link
                + ((self.Pf + 1j * self.Qf)[self.cg_hvdc] @ self.nc.hvdc_data.C_hvdc_bus_f
                   + (self.Pt + 1j * self.Qt)[self.cg_hvdc] @ self.nc.hvdc_data.C_hvdc_bus_t)

                # add contribution of transformer
                + ((self.Pf + 1j * self.Qf)[self.cg_pttr] @ self.nc.passive_branch_data.C_branch_bus_f[self.cg_pttr, :]
                   + (self.Pt + 1j * self.Qt)[self.cg_pttr] @ self.nc.passive_branch_data.C_branch_bus_t[self.cg_pttr,
                                                              :])
        )

        # remapping of indices
        m2 = np.ones(self.nc.nbr)
        m2[self.cx_m] = self.m.copy()
        tau2 = np.zeros(self.nc.nbr)
        tau2[self.cx_tau] = self.tau.copy()

        # Use self.Pf...
        Pftr, Qftr, Pttr, Qttr = recompute_controllable_power(
            V_f=self.V[self.nc.passive_branch_data.F[self.controlled_idx]],
            V_t=self.V[self.nc.passive_branch_data.T[self.controlled_idx]],
            R=self.nc.passive_branch_data.R[self.controlled_idx],
            X=self.nc.passive_branch_data.X[self.controlled_idx],
            G=self.nc.passive_branch_data.G[self.controlled_idx],
            B=self.nc.passive_branch_data.B[self.controlled_idx],
            tap_module=m2[self.controlled_idx],
            vtap_f=self.nc.passive_branch_data.virtual_tap_f[self.controlled_idx],
            vtap_t=self.nc.passive_branch_data.virtual_tap_t[self.controlled_idx],
            tap_angle=tau2[self.controlled_idx]
        )
        self._f = np.r_[
            dS[self.cg_pac + self.cg_pdc].real,
            dS[self.cg_qac].imag,
            Ploss_acdc,
            Ploss_hvdc,
            Pinj_hvdc,
            Pftr - self.nc.active_branch_data.Pset[self.cg_pftr],
            Qftr - self.nc.active_branch_data.Qset[self.cg_qftr],
            Pttr - self.nc.active_branch_data.Pset[self.cg_pttr],
            Qttr - self.nc.active_branch_data.Qset[self.cg_qttr]
        ]

        # compute the error
        self._error = compute_fx_error(self._f)

        if self.options.verbose > 1:
            print("Vm:", self.Vm)
            print("Va:", self.Va)
            print("Pbus:", self.Pzip)
            print("Qbus:", self.Qzip)
            print("Pf:", self.Pf)
            print("Qf:", self.Qf)
            print("Pt:", self.Pt)
            print("Qt:", self.Qt)
            print("m:", self.m)
            print("tau:", self.tau)
            print("error:", self._error)

        # Update controls only below a certain error
        """
        if update_controls and self._error < self._controls_tol:
            any_change = False
            branch_ctrl_change = False

            # review reactive power limits
            # it is only worth checking Q limits with a low error
            # since with higher errors, the Q values may be far from realistic
            # finally, the Q control only makes sense if there are pv nodes
            if self.options.control_Q and (len(self.pv) + len(self.p)) > 0:

                # check and adjust the reactive power
                # this function passes pv buses to pq when the limits are violated,
                # but not pq to pv because that is unstable
                changed, pv, pq, pqv, p = control_q_inside_method(self.Scalc, self.S0,
                                                                  self.pv, self.pq,
                                                                  self.pqv, self.p,
                                                                  self.Qmin, self.Qmax)

                if len(changed) > 0:
                    any_change = True

                    # update the bus type lists
                    self.update_bus_types(pq=pq, pv=pv, pqv=pqv, p=p)

                    # the composition of x may have changed, so recompute
                    x = self.var2x()

            # update Slack control
            if self.options.distributed_slack:
                ok, delta = compute_slack_distribution(Scalc=self.Scalc,
                                                       vd=self.vd,
                                                       bus_installed_power=self.nc.bus_installed_power)
                if ok:
                    any_change = True
                    # Update the objective power to reflect the slack distribution
                    self.S0 += delta

            # update the tap module control
            if self.options.control_taps_modules:
                for i, k in enumerate(self.idx_dm):

                    m_taps = self.nc.branch_data.m_taps[i]

                    if self.options.orthogonalize_controls and m_taps is not None:
                        _, self.m[i] = find_closest_number(arr=m_taps, target=self.m[i])

                    if self.m[i] < self.nc.branch_data.tap_module_min[k]:
                        self.m[i] = self.nc.branch_data.tap_module_min[k]
                        self.tap_module_control_mode[k] = TapModuleControl.fixed
                        branch_ctrl_change = True
                        self.logger.add_info("Min tap module reached",
                                             device=self.nc.branch_data.names[k],
                                             value=self.m[i])

                    if self.m[i] > self.nc.branch_data.tap_module_max[k]:
                        self.m[i] = self.nc.branch_data.tap_module_max[k]
                        self.tap_module_control_mode[k] = TapModuleControl.fixed
                        branch_ctrl_change = True
                        self.logger.add_info("Max tap module reached",
                                             device=self.nc.branch_data.names[k],
                                             value=self.m[i])

            # update the tap phase control
            if self.options.control_taps_phase:

                for i, k in enumerate(self.idx_dtau):

                    tau_taps = self.nc.branch_data.tau_taps[i]

                    if self.options.orthogonalize_controls and tau_taps is not None:
                        _, self.tau[i] = find_closest_number(arr=tau_taps, target=self.tau[i])

                    if self.tau[i] < self.nc.branch_data.tap_angle_min[k]:
                        self.tau[i] = self.nc.branch_data.tap_angle_min[k]
                        self.tap_phase_control_mode[k] = TapPhaseControl.fixed
                        branch_ctrl_change = True
                        self.logger.add_info("Min tap phase reached",
                                             device=self.nc.branch_data.names[k],
                                             value=self.tau[i])

                    if self.tau[i] > self.nc.branch_data.tap_angle_max[k]:
                        self.tau[i] = self.nc.branch_data.tap_angle_max[k]
                        self.tap_phase_control_mode[k] = TapPhaseControl.fixed
                        branch_ctrl_change = True
                        self.logger.add_info("Max tap phase reached",
                                             device=self.nc.branch_data.names[k],
                                             value=self.tau[i])

            if branch_ctrl_change:
                k_v_m = self.analyze_branch_controls()
                vd, pq, pv, pqv, p, self.no_slack = compile_types(Pbus=self.nc.Sbus.real, types=self.bus_types)
                self.update_bus_types(pq=pq, pv=pv, pqv=pqv, p=p)

            if any_change or branch_ctrl_change:
                # recompute the error based on the new Scalc and S0
                self._f = self.fx()

                # compute the error
                self._error = compute_fx_error(self._f)
        """

        # converged?
        self._converged = self._error < self.options.tolerance
        print("Error:", self._error)

        return self._error, self._converged, x, self.f

    def fx(self) -> Vec:
        """
        Used?
        :return:
        """

        # Assumes the internal vars were updated already with self.x2var()
        Sbus = compute_zip_power(self.S0, self.I0, self.Y0, self.Vm)
        self.Scalc = compute_power(self.adm.Ybus, self.V)

        dS = self.Scalc - Sbus  # compute the mismatch

        Pf = get_Sf(k=self.idx_dPf, Vm=self.Vm, V=self.V,
                    yff=self.adm.yff, yft=self.adm.yft, F=self.nc.F, T=self.nc.T).real

        Qf = get_Sf(k=self.idx_dQf, Vm=self.Vm, V=self.V,
                    yff=self.adm.yff, yft=self.adm.yft, F=self.nc.F, T=self.nc.T).imag

        Pt = get_St(k=self.idx_dPt, Vm=self.Vm, V=self.V,
                    ytf=self.adm.ytf, ytt=self.adm.ytt, F=self.nc.F, T=self.nc.T).real

        Qt = get_St(k=self.idx_dQt, Vm=self.Vm, V=self.V,
                    ytf=self.adm.ytf, ytt=self.adm.ytt, F=self.nc.F, T=self.nc.T).imag

        self._f = np.r_[
            dS[self.idx_dP].real,
            dS[self.idx_dQ].imag,
            Pf - self.nc.passive_branch_data.Pset[self.idx_dPf],
            Qf - self.nc.passive_branch_data.Qset[self.idx_dQf],
            Pt - self.nc.passive_branch_data.Pset[self.idx_dPt],
            Qt - self.nc.passive_branch_data.Qset[self.idx_dQt]
        ]
        return self._f

    def fx_diff(self, x: Vec) -> Vec:
        """
        Fx for autodiff
        :param x: solutions vector
        :return: f(x)
        """
        ff = self.compute_f(x)
        return ff

    def Jacobian(self, autodiff: bool = False) -> CSC:
        """
        Get the Jacobian
        :return:
        """
        if autodiff:
            J = calc_autodiff_jacobian(func=self.fx_diff, x=self.var2x(), h=1e-6)
            print("(pf_generalized_formulation.py) J: ")
            print(J)
            # print shape of J
            print("J shape: ", J.shape)
            return scipy_to_mat(J)
        else:
            n_rows = (len(self.cg_pac)
                      + len(self.cg_qac)
                      + len(self.cg_pdc)
                      + len(self.cg_acdc)
                      + (2 * len(self.cg_hvdc))  # hvdc has 2 equations: Pinj and Ploss
                      + len(self.cg_pftr)
                      + len(self.cg_qftr)
                      + len(self.cg_pttr)
                      + len(self.cg_qttr))

            n_cols = (len(self.cx_vm)
                      + len(self.cx_va)
                      + len(self.cx_tau)
                      + len(self.cx_pzip)
                      + len(self.cx_qzip)
                      + len(self.cx_pfa)
                      + len(self.cx_qfa)
                      + len(self.cx_pta)
                      + len(self.cx_qta)
                      + len(self.cx_m)
                      + len(self.cx_tau))

            print()
            if n_cols != n_rows:
                raise ValueError("Incorrect J indices!")

            tap_modules = expand(self.nc.nbr, self.m, self.idx_dm, 1.0)
            tap_angles = expand(self.nc.nbr, self.tau, self.idx_dtau, 0.0)
            tap = polar_to_rect(tap_modules, tap_angles)

            # print("self.indices.cx_qta", self.indices.cx_qta)
            J = adv_jacobian(
                nbus=self.nc.nbus,
                nbr=self.nc.nbr,
                ix_vm=self.indices.cx_vm,
                ix_va=self.indices.cx_va,
                ix_pzip=self.indices.cx_pzip,
                ix_qzip=self.indices.cx_qzip,
                ix_pf=self.indices.cx_pfa,
                ix_qf=self.indices.cx_qfa,
                ix_pt=self.indices.cx_pta,
                ix_qt=self.indices.cx_qta,
                ix_m=self.indices.ck_m,
                ix_tau=self.indices.ck_tau,
                ig_pbus=self.indices.cg_pac + self.indices.cg_pdc,
                ig_qbus=self.indices.cg_qac,
                ig_plossacdc=self.indices.cg_acdc,
                ig_plosshvdc=self.indices.cg_hvdc,
                ig_pinjhvdc=self.indices.cg_hvdc,
                # TODO: clarify this set? I think it should be the same as ig_plosshvdc
                ig_pftr=self.indices.cg_pftr,
                ig_qftr=self.indices.cg_qftr,
                ig_pttr=self.indices.cg_pttr,
                ig_qttr=self.indices.cg_qttr,
                ig_contrbr=self.indices.cg_qttr,
                Cf_acdc=self.nc.vsc_data.C_branch_bus_f,
                Ct_acdc=self.nc.vsc_data.C_branch_bus_t,
                Cf_hvdc=self.nc.hvdc_data.C_hvdc_bus_f,
                Ct_hvdc=self.nc.hvdc_data.C_hvdc_bus_t,
                Cf_contbr=self.nc.passive_branch_data.C_branch_bus_f,
                Ct_contbr=self.nc.passive_branch_data.C_branch_bus_t,
                Cf_branch=self.nc.passive_branch_data.C_branch_bus_f,
                Ct_branch=self.nc.passive_branch_data.C_branch_bus_t,
                alpha1=self.nc.vsc_data.alpha1,
                alpha2=self.nc.vsc_data.alpha2,
                alpha3=self.nc.vsc_data.alpha3,
                F_acdc=self.nc.vsc_data.F,
                T_acdc=self.nc.vsc_data.T,
                F_hvdc=self.nc.hvdc_data.F,
                T_hvdc=self.nc.hvdc_data.T,
                hvdc_mode=self.indices.hvdc_mode,
                hvdc_angle_droop=self.nc.hvdc_data.angle_droop,
                hvdc_pset=self.nc.hvdc_data.Pset,
                hvdc_r=self.nc.hvdc_data.r,
                hvdc_Vnf=self.nc.hvdc_data.Vnf,
                hvdc_Vnt=self.nc.hvdc_data.Vnt,
                Pf=self.Pf,
                Qf=self.Qf,
                Pt=self.Pt,
                Qt=self.Qt,
                F=self.nc.F,
                T=self.nc.T,
                Ys=self.Ys,
                kconv=self.nc.passive_branch_data.k,
                complex_tap=tap,
                tap_modules=tap_modules,
                Bc=self.nc.passive_branch_data.B,
                V=self.V,
                Vm=np.abs(self.V),
                Va=np.angle(self.V),
                Sbase=self.nc.Sbase,
                Ybus_x=self.adm.Ybus.data,
                Ybus_p=self.adm.Ybus.indptr,
                Ybus_i=self.adm.Ybus.indices,
                yff=self.adm.yff,
                yft=self.adm.yft,
                ytf=self.adm.ytf,
                ytt=self.adm.ytt)

            # J = adv_jacobian(nbus=self.nc.nbus,
            #                  nbr=self.nc.nbr,
            #                  idx_dva=self.idx_dVa,
            #                  idx_dvm=self.idx_dVm,
            #                  idx_dm=self.idx_dm,
            #                  idx_dtau=self.idx_dtau,
            #                  idx_dbeq=self.idx_dbeq,
            #                  idx_dP=self.idx_dP,
            #                  idx_dQ=self.idx_dQ,
            #                  idx_dPf=self.idx_dPf,
            #                  idx_dQf=self.idx_dQf,
            #                  idx_dPt=self.idx_dPt,
            #                  idx_dQt=self.idx_dQt,
            #
            #                  F=self.nc.F,
            #                  T=self.nc.T,
            #                  Ys=self.Ys,
            #                  kconv=self.nc.passive_branch_data.k,
            #                  complex_tap=tap,
            #                  tap_modules=tap_modules,
            #                  Bc=self.nc.passive_branch_data.B,
            #                  Beq=expand(self.nc.nbr, self.beq, self.idx_dbeq, 0.0),
            #                  V=self.V,
            #                  Vm=self.Vm,
            #                  Ybus_x=self.adm.Ybus.data,
            #                  Ybus_p=self.adm.Ybus.indptr,
            #                  Ybus_i=self.adm.Ybus.indices,
            #                  yff=self.adm.yff,
            #                  yft=self.adm.yft,
            #                  ytf=self.adm.ytf,
            #                  ytt=self.adm.ytt)

            return J

    def get_x_names(self) -> List[str]:
        """
        Names matching x
        :return:
        """
        cols = [f'dVa {i}' for i in self.idx_dVa]
        cols += [f'dVm {i}' for i in self.idx_dVm]
        cols += [f'dm {i}' for i in self.idx_dm]
        cols += [f'dtau {i}' for i in self.idx_dtau]
        cols += [f'dBeq {i}' for i in self.idx_dbeq]

        return cols

    def get_fx_names(self) -> List[str]:
        """
        Names matching fx
        :return:
        """
        '''
        self.cg_pac = generalisedSimulationIndices.cg_pac
        self.cg_qac = generalisedSimulationIndices.cg_qac
        self.cg_pdc = generalisedSimulationIndices.cg_pdc
        self.cg_acdc = generalisedSimulationIndices.cg_acdc
        self.cg_hvdc = generalisedSimulationIndices.cg_hvdc
        self.cg_pftr = generalisedSimulationIndices.cg_pftr
        self.cg_pttr = generalisedSimulationIndices.cg_pttr
        self.cg_qftr = generalisedSimulationIndices.cg_qftr
        self.cg_qttr = generalisedSimulationIndices.cg_qttr
                    dS[self.cg_pac + self.cg_pdc].real,
            dS[self.cg_qac].imag,
            Ploss_acdc,
            Pf[self.cg_pftr] - self.nc.active_branch_data.Pset[self.cg_pftr],
            Qf[self.cg_qftr] - self.nc.active_branch_data.Qset[self.cg_qftr],
            Pt[self.cg_pttr] - self.nc.active_branch_data.Pset[self.cg_pttr],
            Qt[self.cg_qttr] - self.nc.active_branch_data.Qset[self.cg_qttr]
        '''

        rows = [f'active power balance node {i}' for i in (self.cg_pac.union(self.cg_pdc))]
        rows += [f'reactive power balance node {i}' for i in self.cg_qac]
        rows += [f'Ploss_acdc {i}' for i in self.cg_acdc]
        rows += [f'Ploss_hvdc {i}' for i in self.cg_hvdc]
        rows += [f'Pinj_hvdc {i}' for i in self.cg_hvdc]
        rows += [f'cg_pftr {i}' for i in self.cg_pttr]
        rows += [f'cg_pttr {i}' for i in self.cg_pttr]
        rows += [f'cg_qftr {i}' for i in self.cg_qftr]
        rows += [f'cg_qttr {i}' for i in self.cg_qttr]

        return rows

    def get_jacobian_df(self, autodiff=False) -> pd.DataFrame:
        """
        Get the Jacobian DataFrame
        :return: DataFrame
        """
        J = self.Jacobian(autodiff=autodiff)
        return pd.DataFrame(
            data=J.toarray(),
            columns=self.get_x_names(),
            index=self.get_fx_names(),
        )

    def get_solution(self, elapsed: float, iterations: int) -> NumericPowerFlowResults:
        """
        Get the problem solution
        :param elapsed: Elapsed seconds
        :param iterations: Iteration number
        :return: NumericPowerFlowResults
        """
        return NumericPowerFlowResults(V=self.V,
                                       converged=self.converged,
                                       norm_f=self.error,
                                       Scalc=self.Scalc,
                                       m=expand(self.nc.nbr, self.m, self.idx_dm, 1.0),
                                       tau=expand(self.nc.nbr, self.tau, self.idx_dtau, 0.0),
                                       Ybus=self.adm.Ybus,
                                       Yf=self.adm.Yf,
                                       Yt=self.adm.Yt,
                                       iterations=iterations,
                                       elapsed=elapsed)
