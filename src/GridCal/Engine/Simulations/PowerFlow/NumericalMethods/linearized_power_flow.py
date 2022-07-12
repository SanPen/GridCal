# -*- coding: utf-8 -*-
# GridCal
# Copyright (C) 2022 Santiago Peñate Vera
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

from GridCal.Engine.Simulations.sparse_solve import get_sparse_type, get_linear_solver
from GridCal.Engine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
from GridCal.Engine.Simulations.PowerFlow.NumericalMethods.common_functions import *

linear_solver = get_linear_solver()
sparse = get_sparse_type()


def dcpf(Ybus, Bpqpv, Bref, Btheta, S0, I0, V0, theta, ref, pvpq, pq, pv) -> NumericPowerFlowResults:
    """
    Solves a linear-DC power flow.
    :param Ybus: Normal circuit admittance matrix
    :param Bpqpv: Susceptance matrix reduced
    :param Bref: Susceptane matrix sliced for the slack node
    :param Btheta: Susceptance matrix of the branches to nodes (used to include the phase shifters)
    :param S0: Complex power injections at all the nodes
    :param I0: Complex current injections at all the nodes
    :param V0: Array of complex seed voltage (it contains the ref voltages)
    :param theta: Array of branch angles
    :param ref: array of the indices of the slack nodes
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
        Va_ref = np.angle(V0[ref])  # we only need the angles at the slack nodes
        Vm = np.abs(V0)

        # initialize result vector
        Va = np.empty(len(V0))

        # compose the reduced power injections
        # Since we have removed the slack nodes, we must account their influence as injections Bref * Va_ref
        # We also need to account for the effect of the phase shifters
        Pps = Btheta * theta
        Pinj = S0[pvpq].real + (- Bref * Va_ref + I0[pvpq].real) * Vm[pvpq] - Pps[pvpq]

        # update angles for non-reference buses
        Va[pvpq] = linear_solver(Bpqpv, Pinj)
        Va[ref] = Va_ref

        # re assemble the voltage
        V = polar_to_rect(Vm, Va)

        # compute the calculated power injection and the error of the voltage solution
        Scalc = V * np.conj(Ybus * V - I0)

        # compute the power mismatch between the specified power Sbus and the calculated power Scalc
        mismatch = compute_fx(Scalc, S0, pvpq, pq)

        # check for convergence
        norm_f = np.linalg.norm(mismatch, np.Inf)
    else:
        norm_f = 0.0
        V = V0
        Scalc = V * np.conj(Ybus * V - I0)

    end = time.time()
    elapsed = end - start

    return NumericPowerFlowResults(V, True, norm_f, Scalc, None, None, None, None, None, None, 1, elapsed)


def lacpf(Ybus, Ys, S0, I0, Vset, pq, pv) -> NumericPowerFlowResults:
    """
    Linearized AC Load Flow

    form the article:

    Linearized AC Load Flow Applied to Analysis in Electric Power Systems
        by: P. Rossoni, W. M da Rosa and E. A. Belati
    Args:
        Ybus: Admittance matrix
        Ys: Admittance matrix of the series elements
        S0: Power injections vector of all the nodes
        Vset: Set voltages of all the nodes (used for the slack and PV nodes)
        pq: list of indices of the pq nodes
        pv: list of indices of the pv nodes

    Returns: Voltage vector, converged?, error, calculated power and elapsed time
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
            V = Vset
            # Calculate the error and check the convergence
            Scalc = compute_power(Ybus, V)
            mismatch = compute_fx(Scalc, S0)
            norm_f = compute_fx_error(mismatch)

            # check for convergence
            end = time.time()
            elapsed = end - start
            return NumericPowerFlowResults(V, False, norm_f, Scalc,
                                           None, None, None, None, None, None, 1, elapsed)

        # compose the results vector
        V = Vset.copy()

        #  set the pv voltages
        va_pv = x[0:npv]
        vm_pv = np.abs(Vset[pv])
        V[pv] = polar_to_rect(vm_pv, va_pv)

        # set the PQ voltages
        va_pq = x[npv:npv+npq]
        vm_pq = np.ones(npq) - x[npv+npq::]
        V[pq] = polar_to_rect(vm_pq, va_pq)

        # Calculate the error and check the convergence
        Scalc = compute_power(Ybus, V)
        mismatch = compute_fx(Scalc, S0, pvpq, pq)
        norm_f = compute_fx_error(mismatch)
    else:
        norm_f = 0.0
        V = Vset
        Scalc = compute_power(Ybus, V)

    end = time.time()
    elapsed = end - start

    return NumericPowerFlowResults(V, True, norm_f, Scalc,
                                   None, None, None, None, None, None, 1, elapsed)

