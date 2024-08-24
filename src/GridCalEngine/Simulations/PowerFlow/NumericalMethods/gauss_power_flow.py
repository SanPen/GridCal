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
import numpy as np
import GridCalEngine.Simulations.PowerFlow.NumericalMethods.common_functions as cf
from GridCalEngine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.discrete_controls import (control_q_inside_method,
                                                                                    compute_slack_distribution)
from GridCalEngine.basic_structures import Logger


def gausspf(Ybus, S0, I0, Y0, V0, pv, pq, p, pqv, vd, bus_installed_power, Qmin, Qmax, tol=1e-3, max_it=50,
            control_q=False, distribute_slack=False, verbose=False, logger: Logger = None) -> NumericPowerFlowResults:
    """
    Gauss-Seidel Power flow
    :param Ybus: Admittance matrix
    :param S0: Power Injections array
    :param I0: Current Injections array
    :param Y0: Admittance Injections array
    :param V0: Voltage seed solution array
    :param pv: array of pv-node indices
    :param pq: array of pq-node indices
    :param p: array of p-node indices
    :param pqv: array of pqv-node indices
    :param vd: array of vd-node indices
    :param bus_installed_power: array of bus installed power
    :param Qmin: Minimum Q limits per bus
    :param Qmax: Maximum Q limits per bus
    :param tol: Tolerance
    :param max_it: Maximum number of iterations
    :param control_q: Control Q limits?
    :param distribute_slack: Distribute Slack?
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
    pvpq = np.r_[pv, pq]

    # evaluate F(x0)
    Sbus = cf.compute_zip_power(S0, I0, Y0, Vm)
    Scalc = cf.compute_power(Ybus, V)
    F = cf.compute_fx(Scalc, Sbus, pvpq, pq)
    normF = cf.compute_fx_error(F)

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
        Sbus = cf.compute_zip_power(S0, I0, Y0, Vm)
        Scalc = cf.compute_power(Ybus, V)
        F = cf.compute_fx(Scalc, Sbus, pvpq, pq)
        normF = cf.compute_fx_error(F)

        # check for convergence
        converged = normF < tol

        # control of Q limits --------------------------------------------------------------------------------------
        # review reactive power limits
        # it is only worth checking Q limits with a low error
        # since with higher errors, the Q values may be far from realistic
        # finally, the Q control only makes sense if there are pv nodes
        if control_q and normF < 1e-2 and (len(pv) + len(p)) > 0:

            # check and adjust the reactive power
            # this function passes pv buses to pq when the limits are violated,
            # but not pq to pv because that is unstable
            changed, pv, pq, pqv, p = control_q_inside_method(Scalc, S0, pv, pq, pqv, p, Qmin, Qmax)

            if len(changed) > 0:
                # adjust internal variables to the new pq|pv values
                F = cf.compute_fx(Scalc, Sbus, pvpq, pq)
                normF = cf.compute_fx_error(F)
                converged = normF < tol

        if distribute_slack and normF < 1e-2:
            ok, delta = compute_slack_distribution(Scalc=Scalc,
                                                   vd=vd,
                                                   bus_installed_power=bus_installed_power)
            if ok:
                S0 += delta
                Sbus = cf.compute_zip_power(S0, I0, Y0, Vm)
                F = cf.compute_fx(Scalc, Sbus, pvpq, pq)
                normF = cf.compute_fx_error(F)
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

    return NumericPowerFlowResults(V=V, converged=converged, norm_f=normF,
                                   Scalc=Scalc, m=None, tau=None, Beq=None,
                                   Ybus=None, Yf=None, Yt=None,
                                   iterations=iter_, elapsed=elapsed)
