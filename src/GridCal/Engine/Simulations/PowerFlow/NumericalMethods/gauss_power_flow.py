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

"""
Solves the power flow using a Gauss-Seidel method.
"""

import time
import numpy as np
from GridCal.Engine.Simulations.PowerFlow.NumericalMethods.common_functions import *
from GridCal.Engine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
from GridCal.Engine.basic_structures import Logger


def gausspf(Ybus, S0, I0, Y0, V0, pv, pq, tol=1e-3, max_it=50,
            verbose=False, logger: Logger = None) -> NumericPowerFlowResults:
    """
    Gauss-Seidel Power flow
    :param Ybus: Admittance matrix
    :param S0: Power injections array
    :param I0: Current injections array
    :param Y0: Admittance injections array
    :param V0: Voltage seed solution array
    :param pv: array of pv-node indices
    :param pq: array of pq-node indices
    :param tol: Tolerance
    :param max_it: Maximum number of iterations
    :param verbose: Verbose?
    :param logger: Logger to store the debug information
    :return: NumericPowerFlowResults instance
    """
    start = time.time()

    # initialize
    iter_ = 0
    V = V0.copy()
    Vm = np.abs(V)

    Ydiag = Ybus.diagonal()

    # set up indexing for updating V
    npv = len(pv)
    npq = len(pq)
    pvpq = np.r_[pv, pq]

    # evaluate F(x0)
    Sbus = compute_zip_power(S0, I0, Y0, Vm)
    Scalc = compute_power(Ybus, V)
    F = compute_fx(Scalc, Sbus, pvpq, pq)
    normF = compute_fx_error(F)

    # check tolerance
    converged = normF < tol

    if verbose:
        logger.add_debug('GS Iteration {0}'.format(iter_) + '-' * 200)
        logger.add_debug('error', normF)

    # do Gauss-Seidel iterations
    while not converged and iter_ < max_it:

        # update the voltage at PQ buses
        V[pq] += (np.conj(Sbus[pq] / V[pq]) - Ybus[pq, :] * V) / Ydiag[pq]

        # update the voltage at PV buses
        if npv:
            # update reactive power at the pv nodes
            Q = (V[pv] * np.conj(Ybus[pv, :] * V)).imag
            Sbus[pv] = Sbus[pv].real + 1j * Q

            # update the pv voltage
            V[pv] += (np.conj(Sbus[pv] / V[pv]) - Ybus[pv, :] * V) / Ydiag[pv]
            V[pv] = Vm[pv] * V[pv] / np.abs(V[pv])

        # evaluate F(x)
        Vm = np.abs(V)
        Sbus = compute_zip_power(S0, I0, Y0, Vm)
        Scalc = compute_power(Ybus, V)
        F = compute_fx(Scalc, Sbus, pvpq, pq)
        normF = compute_fx_error(F)

        # check for convergence
        converged = normF < tol

        if verbose:
            logger.add_debug('GS Iteration {0}'.format(iter_) + '-' * 200)

            if verbose > 1:
                logger.add_debug('Vm:\n', np.abs(V))
                logger.add_debug('Va:\n', np.angle(V))

            logger.add_debug('error', normF)

        # update iteration counter
        iter_ += 1

    end = time.time()
    elapsed = end - start

    return NumericPowerFlowResults(V, converged, normF, Scalc, None, None, None, None, None, None, iter_, elapsed)
