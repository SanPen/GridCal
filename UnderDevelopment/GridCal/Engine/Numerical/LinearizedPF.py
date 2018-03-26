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
from scipy.sparse.linalg import spsolve
from scipy.sparse.linalg import factorized
from scipy.sparse import hstack as hstack_s, vstack as vstack_s
from numpy import linalg, Inf, exp, r_, conj, angle, matrix, empty, ones, abs as npabs


def dcpf(Ybus, Sbus, Ibus, V0, ref, pvpq, pq, pv):
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

    # Decompose the voltage in angle and magnitude
    Va_ref = angle(V0[ref])  # we only need the angles at the slack nodes
    Vm = npabs(V0)

    # initialize result vector
    Va = empty(len(V0))

    # reconvert the pqpv vector to a matrix so that we can call numpy directly with it
    pvpq_ = matrix(pvpq)

    # Compile the reduced imaginary impedance matrix
    Bpqpv = Ybus.imag[pvpq_.T, pvpq_]
    Bref = Ybus.imag[pvpq_.T, ref]

    # compose the reduced power injections
    # Since we have removed the slack nodes, we must account their influence as injections Bref * Va_ref
    Pinj = Sbus[pvpq].real + (- Bref * Va_ref + Ibus[pvpq].real) * Vm[pvpq]

    # update angles for non-reference buses
    Va[pvpq] = spsolve(Bpqpv, Pinj)
    Va[ref] = Va_ref

    # re assemble the voltage
    V = Vm * exp(1j * Va)

    # compute the calculated power injection and the error of the voltage solution
    Scalc = V * conj(Ybus * V - Ibus)

    # compute the power mismatch between the specified power Sbus and the calculated power Scalc
    mis = Scalc - Sbus  # complex power mismatch
    F = r_[mis[pv].real, mis[pq].real, mis[pq].imag]  # concatenate again

    # check for convergence
    normF = linalg.norm(F, Inf)

    end = time.time()
    elapsed = end - start

    return V, True, normF, Scalc, 1, elapsed


def lacpf(Y, Ys, S, I, Vset, pq, pv):
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

    pvpq = r_[pv, pq]
    npq = len(pq)
    npv = len(pv)

    # compose the system matrix
    # G = Y.real
    # B = Y.imag
    # Gp = Ys.real
    # Bp = Ys.imag

    A11 = -Ys.imag[pvpq, :][:, pvpq]
    A12 = Y.real[pvpq, :][:, pq]
    A21 = -Ys.real[pq, :][:, pvpq]
    A22 = -Y.imag[pq, :][:, pq]

    Asys = vstack_s([hstack_s([A11, A12]),
                     hstack_s([A21, A22])], format="csc")

    # compose the right hand side (power vectors)
    rhs = r_[S.real[pvpq], S.imag[pq]]

    # solve the linear system
    x = factorized(Asys)(rhs)

    # compose the results vector
    voltages_vector = Vset.copy()

    #  set the pv voltages
    va_pv = x[0:npv]
    vm_pv = npabs(Vset[pv])
    voltages_vector[pv] = vm_pv * exp(1j * va_pv)

    # set the PQ voltages
    va_pq = x[npv:npv+npq]
    vm_pq = ones(npq) + x[npv+npq::]
    voltages_vector[pq] = vm_pq * exp(1j * va_pq)

    # Calculate the error and check the convergence
    s_calc = voltages_vector * conj(Y * voltages_vector)
    # complex power mismatch
    power_mismatch = s_calc - S
    # concatenate error by type
    mismatch = r_[power_mismatch[pv].real, power_mismatch[pq].real, power_mismatch[pq].imag]

    # check for convergence
    norm_f = linalg.norm(mismatch, Inf)

    end = time.time()
    elapsed = end - start

    return voltages_vector, True, norm_f, s_calc, 1, elapsed

