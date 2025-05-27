# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

import time
import scipy.sparse as sp
import numpy as np

from GridCalEngine.Utils.NumericalMethods.sparse_solve import get_sparse_type, get_linear_solver
from GridCalEngine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
from GridCalEngine.DataStructures.numerical_circuit import NumericalCircuit
import GridCalEngine.Simulations.PowerFlow.NumericalMethods.common_functions as cf
from GridCalEngine.basic_structures import CxVec, Vec, IntVec, CscMat
from GridCalEngine.enumerations import ConverterControlType

linear_solver = get_linear_solver()
sparse = get_sparse_type()


def dcpf(nc: NumericalCircuit,
         Ybus: sp.csc_matrix, Bpqpv: sp.csc_matrix, Bref: sp.csc_matrix, Bf: sp.csc_matrix,
         S0: CxVec, I0: CxVec, Y0: CxVec, V0: CxVec, tau: Vec,
         vd: IntVec, no_slack: IntVec, pq: IntVec, pv: IntVec) -> NumericPowerFlowResults:
    """
    Solves a linear-DC power flow.
    :param nc: NumericalCircuit instance
    :param Ybus: Normal circuit admittance matrix
    :param Bpqpv: Susceptance matrix reduced
    :param Bref: Susceptane matrix sliced for the slack node
    :param Bf: Susceptance matrix of the Branches to nodes (used to include the phase shifters)
    :param S0: Complex power Injections at all the nodes
    :param I0: Complex current Injections at all the nodes
    :param Y0: Complex admittance Injections at all the nodes
    :param V0: Array of complex seed voltage (it contains the ref voltages)
    :param tau: Array of branch angles
    :param vd: array of the indices of the slack nodes
    :param no_slack: array of the indices of the non-slack nodes
    :param pq: array of the indices of the pq nodes
    :param pv: array of the indices of the pv nodes
    :return: NumericPowerFlowResults instance
    """

    start = time.time()
    npq = len(pq)
    npv = len(pv)
    if (npq + npv) > 0:
        # Decompose the voltage in angle and magnitude
        Va_ref = np.angle(V0[vd])  # we only need the angles at the slack nodes
        Vm = np.abs(V0)

        # initialize result vector
        Va = np.empty(len(V0))

        # compute the power injection
        Sbus = cf.compute_zip_power(S0, I0, Y0, Vm)

        # compose the reduced power injections (Pinj)
        # Since we have removed the slack nodes, we must account their influence as Injections Bref * Va_ref
        # We also need to account for the effect of the phase shifters (Pps)
        Pps = Bf.T @ tau
        Pinj = Sbus[no_slack].real - (Bref @ Va_ref) * Vm[no_slack] + Pps[no_slack]  # TODO: add G from shunts

        # update angles for non-reference buses
        Va[no_slack] = linear_solver(Bpqpv, Pinj)
        Va[vd] = Va_ref

        # re assemble the voltage
        V = cf.polar_to_rect(Vm, Va)

        # compute the calculated power injection and the error of the voltage solution
        Scalc = cf.compute_power(Ybus, V)

        # compute the power mismatch between the specified power Sbus and the calculated power Scalc
        mismatch = cf.compute_fx(Scalc, S0, no_slack, pq)

        # check for convergence
        norm_f = np.linalg.norm(mismatch, np.inf)
    else:
        norm_f = 0.0
        V = V0
        Scalc = cf.compute_power(Ybus, V)

    end = time.time()
    elapsed = end - start

    Sf, St, If, It, Vbranch, loading, losses, Sbus = cf.power_flow_post_process_linear(
        Sbus=Scalc,
        V=V,
        active=nc.passive_branch_data.active,
        X=nc.passive_branch_data.X,
        tap_module=nc.active_branch_data.tap_module,
        tap_angle=nc.active_branch_data.tap_angle,
        F=nc.passive_branch_data.F,
        T=nc.passive_branch_data.T,
        branch_rates=nc.passive_branch_data.rates,
        Sbase=nc.Sbase
    )

    return NumericPowerFlowResults(V=V,
                                   Scalc=Scalc * nc.Sbase,
                                   m=np.ones(nc.nbr, dtype=float),
                                   tau=np.zeros(nc.nbr, dtype=float),
                                   Sf=Sf,
                                   St=St,
                                   If=If,
                                   It=It,
                                   loading=loading,
                                   losses=losses,
                                   Pf_vsc=np.zeros(nc.nvsc, dtype=float),
                                   St_vsc=np.zeros(nc.nvsc, dtype=complex),
                                   If_vsc=np.zeros(nc.nvsc, dtype=float),
                                   It_vsc=np.zeros(nc.nvsc, dtype=complex),
                                   losses_vsc=np.zeros(nc.nvsc, dtype=float),
                                   loading_vsc=np.zeros(nc.nvsc, dtype=float),
                                   Sf_hvdc=np.zeros(nc.nhvdc, dtype=complex),
                                   St_hvdc=np.zeros(nc.nhvdc, dtype=complex),
                                   losses_hvdc=np.zeros(nc.nhvdc, dtype=complex),
                                   loading_hvdc=np.zeros(nc.nhvdc, dtype=complex),
                                   norm_f=norm_f,
                                   converged=True,
                                   iterations=1,
                                   elapsed=elapsed)


def acdc_lin_pf(nc: NumericalCircuit,
                Bbus: sp.csc_matrix, Bf: sp.csc_matrix,
                Gbus: sp.csc_matrix, Gf: sp.csc_matrix,
                ac: IntVec, dc: IntVec, vd: IntVec, pv: IntVec,
                S0: CxVec, I0: CxVec, Y0: CxVec, V0: CxVec, tau: Vec) -> NumericPowerFlowResults:
    """
    Solves a linear-ACDC power flow.
    :param nc:
    :param Bbus:
    :param Bf:
    :param Gbus:
    :param Gf:
    :param ac:
    :param dc:
    :param vd:
    :param pv:
    :param S0:
    :param I0:
    :param Y0:
    :param V0:
    :param tau:
    :return:
    """


    """
    
    :param nc: NumericalCircuit instance
    :param Ybus: Normal circuit admittance matrix
    :param Bpqpv: Susceptance matrix reduced
    :param Bref: Susceptane matrix sliced for the slack node
    :param Bf: Susceptance matrix of the Branches to nodes (used to include the phase shifters)
    :param S0: Complex power Injections at all the nodes
    :param I0: Complex current Injections at all the nodes
    :param Y0: Complex admittance Injections at all the nodes
    :param V0: Array of complex seed voltage (it contains the ref voltages)
    :param tau: Array of branch angles
    :param vd: array of the indices of the slack nodes
    :param no_slack: array of the indices of the non-slack nodes
    :param pq: array of the indices of the pq nodes
    :param pv: array of the indices of the pv nodes
    :return: NumericPowerFlowResults instance
    """

    start = time.time()

    ac_noslack = np.setdiff1d(ac, vd)  # elements from ac that are not in vd
    dc_noslack = np.setdiff1d(dc, pv)  # elements from dc that are not in pv
    dc_pv = np.intersect1d(dc, pv)  # elements that are pv and dc

    A11 = Bbus[np.ix_(ac_noslack, ac_noslack)]
    A12 = sp.csc_matrix((len(ac_noslack), len(dc_noslack)), dtype=float)
    A21 = sp.csc_matrix((len(dc_noslack), len(ac_noslack)), dtype=float)
    A22 = Gbus[np.ix_(dc_noslack, dc_noslack)]

    Asys = sp.vstack([sp.hstack([A11, A12]),
                      sp.hstack([A21, A22])], format="csc")

    npq = len(ac_noslack)
    zm = np.zeros(nc.passive_branch_data.nelm)

    if npq > 0:
        # Decompose the voltage in angle and magnitude
        Va = np.angle(V0)
        Vm = np.abs(V0)

        # initialize result vector

        # compute the power injection
        Sbus = cf.compute_zip_power(S0, I0, Y0, Vm)

        # compose the reduced power injections (Pinj)
        # Since we have removed the slack nodes, we must account their influence as Injections Bref * Va_ref
        # We also need to account for the effect of the phase shifters (Pps)
        Pps = Bf.T @ tau

        Bref = Bbus[:, vd]
        Gref = Gbus[:, dc_pv]
        Pref = (Bref @ Va[vd]) * Vm + (Gref @ Vm[dc_pv])

        P = Sbus.real - Pref + Pps

        # add the converters effect
        for i in range(nc.vsc_data.nelm):
            if nc.vsc_data.control1[i] == ConverterControlType.Pdc:
                P[nc.vsc_data.F[i]] -= nc.vsc_data.control1_val[i] / nc.Sbase

            elif nc.vsc_data.control2[i] == ConverterControlType.Pac:
                P[nc.vsc_data.T[i]] -= nc.vsc_data.control1_val[i] / nc.Sbase

            if nc.vsc_data.control2[i] == ConverterControlType.Pdc:
                P[nc.vsc_data.F[i]] -= nc.vsc_data.control2_val[i] / nc.Sbase

            elif nc.vsc_data.control2[i] == ConverterControlType.Pac:
                P[nc.vsc_data.T[i]] -= nc.vsc_data.control2_val[i] / nc.Sbase

        f = np.r_[P[ac_noslack], P[dc_noslack]]

        # update angles for non-reference buses
        dx = linear_solver(Asys, f)
        Va[ac_noslack] = dx[0:len(ac_noslack)]
        Vm[dc_noslack] = dx[len(ac_noslack):len(ac_noslack) + len(dc_noslack)]

        # re assemble the voltage
        V = cf.polar_to_rect(Vm, Va)

        # compute flows
        Pf = (Bf @ Va + Gf @ Vm) * nc.Sbase

        # check for convergence
        norm_f = 0.0
    else:
        norm_f = 0.0
        Pf = zm
        V = V0

    end = time.time()
    elapsed = end - start

    # Sf, St, If, It, Vbranch, loading, losses, Sbus = cf.power_flow_post_process_linear(
    #     Sbus=S0,
    #     V=V,
    #     active=nc.passive_branch_data.active,
    #     X=nc.passive_branch_data.X,
    #     tap_module=nc.active_branch_data.tap_module,
    #     tap_angle=nc.active_branch_data.tap_angle,
    #     F=nc.passive_branch_data.F,
    #     T=nc.passive_branch_data.T,
    #     branch_rates=nc.passive_branch_data.rates,
    #     Sbase=nc.Sbase
    # )

    loading = Pf / (nc.passive_branch_data.rates + 1e-20)

    return NumericPowerFlowResults(V=V,
                                   Scalc=S0 * nc.Sbase,
                                   m=np.ones(nc.nbr, dtype=float),
                                   tau=np.zeros(nc.nbr, dtype=float),
                                   Sf=Pf,
                                   St=-Pf,
                                   If=zm,
                                   It=zm,
                                   loading=loading,
                                   losses=zm,
                                   Pf_vsc=np.zeros(nc.nvsc, dtype=float),
                                   St_vsc=np.zeros(nc.nvsc, dtype=complex),
                                   If_vsc=np.zeros(nc.nvsc, dtype=float),
                                   It_vsc=np.zeros(nc.nvsc, dtype=complex),
                                   losses_vsc=np.zeros(nc.nvsc, dtype=float),
                                   loading_vsc=np.zeros(nc.nvsc, dtype=float),
                                   Sf_hvdc=np.zeros(nc.nhvdc, dtype=complex),
                                   St_hvdc=np.zeros(nc.nhvdc, dtype=complex),
                                   losses_hvdc=np.zeros(nc.nhvdc, dtype=complex),
                                   loading_hvdc=np.zeros(nc.nhvdc, dtype=complex),
                                   norm_f=norm_f,
                                   converged=True,
                                   iterations=1,
                                   elapsed=elapsed)


def lacpf(nc: NumericalCircuit,
          Ybus: CscMat, Yf: CscMat, Yt: CscMat, Ys: CscMat, Yshunt_bus: CxVec,
          S0: CxVec, V0: CxVec, pq: IntVec, pv: IntVec, vd: IntVec) -> NumericPowerFlowResults:
    """
    Linearized AC Load Flow

    form the article:

    Linearized AC Load Flow Applied to Analysis in Electric Power Systems
        by: P. Rossoni, W. M da Rosa and E. A. Belati
    :param nc: NumericalCircuit instance
    :param Ybus: Admittance matrix
    :param Yf: Admittance from matrix
    :param Yt: Admittance to matrix
    :param Ys: Admittance matrix of the series elements
    :param Yshunt_bus: Admittance vector of the series elements per bus
    :param S0: Power Injections vector of all the nodes
    :param V0: Set voltages of all the nodes (used for the slack and PV nodes)
    :param pq: list of indices of the pq nodes
    :param pv: list of indices of the pv nodes
    :param vd: Array with the indices of the slack buses
    :return: NumericPowerFlowResults
    """

    start = time.time()

    pvpq = np.r_[pv, pq]
    npq = len(pq)
    npv = len(pv)

    if (npq + npv) > 0:
        # compose the system matrix
        # G = Y.real
        # B = Y.imag
        # Gp = Ys.real
        # Bp = Ys.imag

        A11 = -Ys.imag[np.ix_(pvpq, pvpq)]
        A12 = Ybus.real[np.ix_(pvpq, pq)]
        A21 = -Ys.real[np.ix_(pq, pvpq)]
        A22 = -Ybus.imag[np.ix_(pq, pq)]

        Asys = sp.vstack([sp.hstack([A11, A12]),
                          sp.hstack([A21, A22])], format="csc")

        # compose the right hand side (power vectors)
        rhs = np.r_[S0.real[pvpq], S0.imag[pq]]

        # solve the linear system
        try:
            x = linear_solver(Asys, -rhs)
        except RuntimeError as e:
            V = V0
            # Calculate the error and check the convergence
            Scalc = cf.compute_power(Ybus, V)
            mismatch = cf.compute_fx(Scalc=Scalc, Sbus=S0, idx_dP=pvpq, idx_dQ=pq)
            norm_f = cf.compute_fx_error(mismatch)

            # check for convergence
            end = time.time()
            elapsed = end - start

            return NumericPowerFlowResults(V=V,
                                           Scalc=Scalc * nc.Sbase,
                                           m=np.ones(nc.nbr, dtype=float),
                                           tau=np.zeros(nc.nbr, dtype=float),
                                           Sf=np.zeros(nc.nbr, dtype=complex),
                                           St=np.zeros(nc.nbr, dtype=complex),
                                           If=np.zeros(nc.nbr, dtype=complex),
                                           It=np.zeros(nc.nbr, dtype=complex),
                                           loading=np.zeros(nc.nbr, dtype=complex),
                                           losses=np.zeros(nc.nbr, dtype=complex),
                                           Pf_vsc=np.zeros(nc.nvsc, dtype=float),
                                           St_vsc=np.zeros(nc.nvsc, dtype=complex),
                                           If_vsc=np.zeros(nc.nvsc, dtype=float),
                                           It_vsc=np.zeros(nc.nvsc, dtype=complex),
                                           losses_vsc=np.zeros(nc.nvsc, dtype=float),
                                           loading_vsc=np.zeros(nc.nvsc, dtype=float),
                                           Sf_hvdc=np.zeros(nc.nhvdc, dtype=complex),
                                           St_hvdc=np.zeros(nc.nhvdc, dtype=complex),
                                           losses_hvdc=np.zeros(nc.nhvdc, dtype=complex),
                                           loading_hvdc=np.zeros(nc.nhvdc, dtype=complex),
                                           norm_f=norm_f,
                                           converged=False,
                                           iterations=1,
                                           elapsed=elapsed)

        # compose the results vector
        V = V0.copy()

        #  set the pv voltages
        va_pv = x[0:npv]
        vm_pv = np.abs(V0[pv])
        V[pv] = cf.polar_to_rect(vm_pv, va_pv)

        # set the PQ voltages
        va_pq = x[npv:npv + npq]
        vm_pq = np.ones(npq) - x[npv + npq::]
        V[pq] = cf.polar_to_rect(vm_pq, va_pq)

        # Calculate the error and check the convergence
        Scalc = cf.compute_power(Ybus, V)
        mismatch = cf.compute_fx(Scalc, S0, pvpq, pq)
        norm_f = cf.compute_fx_error(mismatch)
    else:
        norm_f = 0.0
        V = V0
        Scalc = cf.compute_power(Ybus, V)

    end = time.time()
    elapsed = end - start

    # Compute the Branches power and the slack buses power
    Sf, St, If, It, Vbranch, loading, losses, Sbus = cf.power_flow_post_process_nonlinear(
        Sbus=Scalc,
        V=V,
        F=nc.passive_branch_data.F,
        T=nc.passive_branch_data.T,
        pv=pv,
        vd=vd,
        Ybus=Ybus,
        Yf=Yf,
        Yt=Yt,
        Yshunt_bus=Yshunt_bus,
        branch_rates=nc.passive_branch_data.rates,
        Sbase=nc.Sbase
    )

    return NumericPowerFlowResults(V=V,
                                   Scalc=Scalc * nc.Sbase,
                                   m=np.ones(nc.nbr, dtype=float),
                                   tau=np.zeros(nc.nbr, dtype=float),
                                   Sf=Sf,
                                   St=St,
                                   If=If,
                                   It=It,
                                   loading=loading,
                                   losses=losses,
                                   Pf_vsc=np.zeros(nc.nvsc, dtype=float),
                                   St_vsc=np.zeros(nc.nvsc, dtype=complex),
                                   If_vsc=np.zeros(nc.nvsc, dtype=float),
                                   It_vsc=np.zeros(nc.nvsc, dtype=complex),
                                   losses_vsc=np.zeros(nc.nvsc, dtype=float),
                                   loading_vsc=np.zeros(nc.nvsc, dtype=float),
                                   Sf_hvdc=np.zeros(nc.nhvdc, dtype=complex),
                                   St_hvdc=np.zeros(nc.nhvdc, dtype=complex),
                                   losses_hvdc=np.zeros(nc.nhvdc, dtype=complex),
                                   loading_hvdc=np.zeros(nc.nhvdc, dtype=complex),
                                   norm_f=norm_f,
                                   converged=True,
                                   iterations=1,
                                   elapsed=elapsed)
