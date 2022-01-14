GridCal
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

import sys
import time
import numpy as np
from GridCal.Engine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults


def gausspf(Ybus, Sbus, V0, pv, pq, tol=1e-3, max_it=50, verbose=False):
    """

    :param Ybus:
    :param Sbus:
    :param V0:
    :param pv:
    :param pq:
    :param tol:
    :param max_it:
    :param verbose:
    :return:
    """
    start = time.time()

    # initialize
    iter_ = 0
    V = V0.copy()
    Vm = np.abs(V)

    # set up indexing for updating V
    npv = len(pv)
    npq = len(pq)
    pvpq = np.r_[pv, pq]

    # evaluate F(x0)
    Scalc = V * np.conj(Ybus * V)
    mis = Scalc - Sbus
    F = np.r_[mis[pvpq].real, mis[pq].imag]

    # check tolerance
    normF = np.linalg.norm(F, np.Inf)
    converged = normF < tol

    # do Gauss-Seidel iterations
    while not converged and iter_ < max_it:

        # update the voltage at PQ buses
        V[pq] += (np.conj(Sbus[pq] / V[pq]) - Ybus[pq, :] * V) / Ybus.diagonal()[pq]

        # update the voltage at PV buses
        if npv:
            # update reactive power at the pv nodes
            Q = (V[pv] * np.conj(Ybus[pv, :] * V)).imag
            Sbus[pv] = Sbus[pv].real + 1j * Q

            # update the pv voltage
            V[pv] += (np.conj(Sbus[pv] / V[pv]) - Ybus[pv, :] * V) / Ybus.diagonal()[pv]
            V[pv] = Vm[pv] * V[pv] / np.abs(V[pv])

        # evaluate F(x)
        Scalc = V * np.conj(Ybus * V)
        mis = Scalc - Sbus
        F = np.r_[mis[pv].real, mis[pq].real, mis[pq].imag]

        # check for convergence
        normF = np.linalg.norm(F, np.Inf)  # same as max(abs(F))
        converged = normF < tol

        # update iteration counter
        iter_ += 1

    if verbose:
        if not converged:
            sys.stdout.write('Gauss-Seidel power did not converge in %d '
                             'iterations.' % iter_)

    end = time.time()
    elapsed = end - start

    return NumericPowerFlowResults(V, converged, normF, Scalc, None, None, None, None, None, None, iter_, elapsed)
