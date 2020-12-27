# -*- coding: utf-8 -*-
# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.

import time
import scipy.sparse as sp
import numpy as np

from GridCal.Engine.Simulations.sparse_solve import get_sparse_type, get_linear_solver
from GridCal.Engine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults

linear_solver = get_linear_solver()
sparse = get_sparse_type()


def dcpf(Ybus, Bpqpv, Bref, Sbus, Ibus, V0, ref, pvpq, pq, pv) -> NumericPowerFlowResults:
    """
    Solves a DC power flow.
    :param Ybus: Normal circuit admittance matrix
    :param Sbus: Complex power injections at all the nodes
    :param Ibus: Complex current injections at all the nodes
    :param V0: Array of complex seed voltage (it contains the ref voltages)
    :param ref: array of the indices of the slack nodes
    :param pvpq: array of the indices of the non-slack nodes
    :param pq: array of the indices of the pq nodes
    :param pv: array of the indices of the pv nodes
    :return:
        Complex voltage solution
        Converged: Always true
        Solution error
        Computed power injections given the found solution
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
        Pinj = Sbus[pvpq].real + (- Bref * Va_ref + Ibus[pvpq].real) * Vm[pvpq]

        # update angles for non-reference buses
        Va[pvpq] = linear_solver(Bpqpv, Pinj)
        Va[ref] = Va_ref

        # re assemble the voltage
        V = Vm * np.exp(1j * Va)

        # compute the calculated power injection and the error of the voltage solution
        Scalc = V * np.conj(Ybus * V - Ibus)

        # compute the power mismatch between the specified power Sbus and the calculated power Scalc
        mis = Scalc - Sbus  # complex power mismatch
        mismatch = np.r_[mis[pv].real, mis[pq].real, mis[pq].imag]  # concatenate again

        # check for convergence
        norm_f = np.linalg.norm(mismatch, np.Inf)
    else:
        norm_f = 0.0
        V = V0
        Scalc = V * np.conj(Ybus * V - Ibus)

    end = time.time()
    elapsed = end - start

    return NumericPowerFlowResults(V, True, norm_f, Scalc, None, None, None, 1, elapsed)


def lacpf(Y, Ys, S, I, Vset, pq, pv) -> NumericPowerFlowResults:
    """
    Linearized AC Load Flow

    form the article:

    Linearized AC Load Flow Applied to Analysis in Electric Power Systems
        by: P. Rossoni, W. M da Rosa and E. A. Belati
    Args:
        Y: Admittance matrix
        Ys: Admittance matrix of the series elements
        S: Power injections vector of all the nodes
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
        A12 = Y.real[np.ix_(pvpq, pq)]
        A21 = -Ys.real[np.ix_(pq, pvpq)]
        A22 = -Y.imag[np.ix_(pq, pq)]

        Asys = sp.vstack([sp.hstack([A11, A12]),
                          sp.hstack([A21, A22])], format="csc")

        # compose the right hand side (power vectors)
        rhs = np.r_[S.real[pvpq], S.imag[pq]]

        # solve the linear system
        try:
            x = linear_solver(Asys, rhs)
        except Exception as e:
            voltages_vector = Vset
            # Calculate the error and check the convergence
            s_calc = voltages_vector * np.conj(Y * voltages_vector)
            # complex power mismatch
            power_mismatch = s_calc - S
            # concatenate error by type
            mismatch = np.r_[power_mismatch[pv].real, power_mismatch[pq].real, power_mismatch[pq].imag]
            # check for convergence
            norm_f = np.linalg.norm(mismatch, np.Inf)
            end = time.time()
            elapsed = end - start
            return voltages_vector, False, norm_f, s_calc, 1, elapsed

        # compose the results vector
        voltages_vector = Vset.copy()

        #  set the pv voltages
        va_pv = x[0:npv]
        vm_pv = np.abs(Vset[pv])
        voltages_vector[pv] = vm_pv * np.exp(1.0j * va_pv)

        # set the PQ voltages
        va_pq = x[npv:npv+npq]
        vm_pq = np.ones(npq) - x[npv+npq::]
        voltages_vector[pq] = vm_pq * np.exp(1.0j * va_pq)

        # Calculate the error and check the convergence
        s_calc = voltages_vector * np.conj(Y * voltages_vector)
        # complex power mismatch
        power_mismatch = s_calc - S
        # concatenate error by type
        mismatch = np.r_[power_mismatch[pv].real, power_mismatch[pq].real, power_mismatch[pq].imag]

        # check for convergence
        norm_f = np.linalg.norm(mismatch, np.Inf)
    else:
        norm_f = 0.0
        voltages_vector = Vset
        s_calc = voltages_vector * np.conj(Y * voltages_vector)

    end = time.time()
    elapsed = end - start

    return NumericPowerFlowResults(voltages_vector, True, norm_f, s_calc, None, None, None, 1, elapsed)

