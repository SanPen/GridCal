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


def dcpf(bus_admittances, complex_bus_powers, current_injections_and_extractions, bus_voltages, slack_bus_indices, pq_and_pv_bus_indices, pq_bus_indices, pv_bus_indices):
    """
    Solves a DC power flow.
    :param bus_admittances: Normal circuit admittance matrix
    :param complex_bus_powers: Complex power injections at all the nodes
    :param current_injections_and_extractions: Complex current injections at all the nodes
    :param bus_voltages: Array of complex seed voltage (it contains the ref voltages)
    :param slack_bus_indices: array of the indices of the slack nodes
    :param pq_and_pv_bus_indices: array of the indices of the non-slack nodes
    :param pq_bus_indices: array of the indices of the pq nodes
    :param pv_bus_indices: array of the indices of the pv nodes
    :return:
        Complex voltage solution
        Converged: Always true
        Solution error
        Computed power injections given the found solution
    """

    start = time.time()

    # Decompose the voltage in angle and magnitude
    Va_ref = angle(bus_voltages[slack_bus_indices])  # we only need the angles at the slack nodes
    Vm = npabs(bus_voltages)

    # initialize result vector
    Va = empty(len(bus_voltages))

    # reconvert the pqpv vector to a matrix so that we can call numpy directly with it
    pvpq_ = matrix(pq_and_pv_bus_indices)

    # Compile the reduced imaginary impedance matrix
    Bpqpv = bus_admittances.imag[pvpq_.T, pvpq_]
    Bref = bus_admittances.imag[pvpq_.T, slack_bus_indices]

    # compose the reduced power injections
    # Since we have removed the slack nodes, we must account their influence as injections Bref * Va_ref
    Pinj = complex_bus_powers[pq_and_pv_bus_indices].real + (- Bref * Va_ref + current_injections_and_extractions[pq_and_pv_bus_indices].real) * Vm[pq_and_pv_bus_indices]

    # update angles for non-reference buses
    Va[pq_and_pv_bus_indices] = spsolve(Bpqpv, Pinj)
    Va[slack_bus_indices] = Va_ref

    # re assemble the voltage
    V = Vm * exp(1j * Va)

    # compute the calculated power injection and the error of the voltage solution
    Scalc = V * conj(bus_admittances * V - current_injections_and_extractions)

    # compute the power mismatch between the specified power Sbus and the calculated power Scalc
    mis = Scalc - complex_bus_powers  # complex power mismatch
    F = r_[mis[pv_bus_indices].real, mis[pq_bus_indices].real, mis[pq_bus_indices].imag]  # concatenate again

    # check for convergence
    normF = linalg.norm(F, Inf)

    end = time.time()
    elapsed = end - start

    return V, True, normF, Scalc, 1, elapsed


def lacpf(bus_admittances, series_admittances, complex_bus_powers, current_injections_and_extractions, bus_voltages, pq_bus_indices, pv_bus_indices):
    """
    Linearized AC Load Flow

    form the article:

    Linearized AC Load Flow Applied to Analysis in Electric Power Systems
        by: P. Rossoni, W. M da Rosa and E. A. Belati
    Args:
        bus_admittances: Admittance matrix
        series_admittances: Admittance matrix of the series elements
        complex_bus_powers: Power injections vector of all the nodes
        bus_voltages: Set voltages of all the nodes (used for the slack and PV nodes)
        pq_bus_indices: list of indices of the pq nodes
        pv_bus_indices: list of indices of the pv nodes

    Returns: Voltage vector, converged?, error, calculated power and elapsed time
    """

    start = time.time()

    pvpq = r_[pv_bus_indices, pq_bus_indices]
    npq = len(pq_bus_indices)
    npv = len(pv_bus_indices)

    # compose the system matrix
    # G = Y.real
    # B = Y.imag
    # Gp = Ys.real
    # Bp = Ys.imag

    A11 = -series_admittances.imag[pvpq, :][:, pvpq]
    A12 = bus_admittances.real[pvpq, :][:, pq_bus_indices]
    A21 = -series_admittances.real[pq_bus_indices, :][:, pvpq]
    A22 = -bus_admittances.imag[pq_bus_indices, :][:, pq_bus_indices]

    Asys = vstack_s([hstack_s([A11, A12]),
                     hstack_s([A21, A22])], format="csc")

    # compose the right hand side (power vectors)
    rhs = r_[complex_bus_powers.real[pvpq], complex_bus_powers.imag[pq_bus_indices]]

    # solve the linear system
    try:
        x = spsolve(Asys, rhs)
    except Exception as e:
        voltages_vector = bus_voltages
        # Calculate the error and check the convergence
        s_calc = voltages_vector * conj(bus_admittances * voltages_vector)
        # complex power mismatch
        power_mismatch = s_calc - complex_bus_powers
        # concatenate error by type
        mismatch = r_[power_mismatch[pv_bus_indices].real, power_mismatch[pq_bus_indices].real, power_mismatch[pq_bus_indices].imag]
        # check for convergence
        norm_f = linalg.norm(mismatch, Inf)
        end = time.time()
        elapsed = end - start
        return voltages_vector, False, norm_f, s_calc, 1, elapsed

    # compose the results vector
    voltages_vector = bus_voltages.copy()

    #  set the pv voltages
    va_pv = x[0:npv]
    vm_pv = npabs(bus_voltages[pv_bus_indices])
    voltages_vector[pv_bus_indices] = vm_pv * exp(1j * va_pv)

    # set the PQ voltages
    va_pq = x[npv:npv+npq]
    vm_pq = ones(npq) + x[npv+npq::]
    voltages_vector[pq_bus_indices] = vm_pq * exp(1j * va_pq)

    # Calculate the error and check the convergence
    s_calc = voltages_vector * conj(bus_admittances * voltages_vector)
    # complex power mismatch
    power_mismatch = s_calc - complex_bus_powers
    # concatenate error by type
    mismatch = r_[power_mismatch[pv_bus_indices].real, power_mismatch[pq_bus_indices].real, power_mismatch[pq_bus_indices].imag]

    # check for convergence
    norm_f = linalg.norm(mismatch, Inf)

    end = time.time()
    elapsed = end - start

    return voltages_vector, True, norm_f, s_calc, 1, elapsed

