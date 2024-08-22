# -*- coding: utf-8 -*-
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

import time
import scipy.sparse as sp
import numpy as np

from GridCalEngine.Utils.NumericalMethods.sparse_solve import get_sparse_type, get_linear_solver
from GridCalEngine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
import GridCalEngine.Simulations.PowerFlow.NumericalMethods.common_functions as cf
from GridCalEngine.basic_structures import CxVec, Vec, IntVec
linear_solver = get_linear_solver()
sparse = get_sparse_type()


def dcpf(Ybus: sp.csc_matrix, Bpqpv: sp.csc_matrix, Bref: sp.csc_matrix, Bf: sp.csc_matrix,
         S0: CxVec, I0: CxVec, Y0: CxVec, V0: CxVec, tau: Vec,
         vd: IntVec, pvpq: IntVec, pq: IntVec, pv: IntVec) -> NumericPowerFlowResults:
    """
    Solves a linear-DC power flow.
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
    :param pvpq: array of the indices of the non-slack nodes
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
        Pinj = Sbus[pvpq].real - (Bref @ Va_ref) * Vm[pvpq] + Pps[pvpq]  # TODO: add G from shunts

        # update angles for non-reference buses
        Va[pvpq] = linear_solver(Bpqpv, Pinj)
        Va[vd] = Va_ref

        # re assemble the voltage
        V = cf.polar_to_rect(Vm, Va)

        # compute the calculated power injection and the error of the voltage solution
        Scalc = cf.compute_power(Ybus, V)

        # compute the power mismatch between the specified power Sbus and the calculated power Scalc
        mismatch = cf.compute_fx(Scalc, S0, pvpq, pq)

        # check for convergence
        norm_f = np.linalg.norm(mismatch, np.Inf)
    else:
        norm_f = 0.0
        V = V0
        Scalc = cf.compute_power(Ybus, V)

    end = time.time()
    elapsed = end - start

    # return NumericPowerFlowResults(V, True, norm_f, Scalc, None, None, None, None, None, None, 1, elapsed)
    return NumericPowerFlowResults(V=V, converged=True, norm_f=norm_f,
                                   Scalc=Scalc, m=None, tau=None, Beq=None,
                                   Ybus=None, Yf=None, Yt=None,
                                   iterations=1, elapsed=elapsed)


def lacpf(Ybus, Ys, S0: CxVec, I0: CxVec, V0: CxVec, pq: IntVec, pv: IntVec) -> NumericPowerFlowResults:
    """
    Linearized AC Load Flow

    form the article:

    Linearized AC Load Flow Applied to Analysis in Electric Power Systems
        by: P. Rossoni, W. M da Rosa and E. A. Belati
    :param Ybus: Admittance matrix
    :param Ys: Admittance matrix of the series elements
    :param S0: Power Injections vector of all the nodes
    :param I0: Current Injections vector of all the nodes
    :param V0: Set voltages of all the nodes (used for the slack and PV nodes)
    :param pq: list of indices of the pq nodes
    :param pv: list of indices of the pv nodes
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
            x = linear_solver(Asys, rhs)
        except Exception as e:
            V = V0
            # Calculate the error and check the convergence
            Scalc = cf.compute_power(Ybus, V)
            mismatch = cf.compute_fx(Scalc=Scalc, Sbus=S0, idx_dP=pvpq, idx_dQ=pq)
            norm_f = cf.compute_fx_error(mismatch)

            # check for convergence
            end = time.time()
            elapsed = end - start
            # return NumericPowerFlowResults(V, False, norm_f, Scalc,
            #                                None, None, None, None, None, None, 1, elapsed)
            return NumericPowerFlowResults(V=V, converged=False, norm_f=norm_f,
                                           Scalc=Scalc, m=None, tau=None, Beq=None,
                                           Ybus=None, Yf=None, Yt=None,
                                           iterations=1, elapsed=elapsed)

        # compose the results vector
        V = V0.copy()

        #  set the pv voltages
        va_pv = x[0:npv]
        vm_pv = np.abs(V0[pv])
        V[pv] = cf.polar_to_rect(vm_pv, va_pv)

        # set the PQ voltages
        va_pq = x[npv:npv+npq]
        vm_pq = np.ones(npq) - x[npv+npq::]
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

    # return NumericPowerFlowResults(V, True, norm_f, Scalc,
    #                                None, None, None, None, None, None, 1, elapsed)
    return NumericPowerFlowResults(V=V, converged=True, norm_f=norm_f,
                                   Scalc=Scalc, m=None, tau=None, Beq=None,
                                   Ybus=None, Yf=None, Yt=None,
                                   iterations=1, elapsed=elapsed)

