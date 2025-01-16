# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0


import time
import numpy as np
import GridCalEngine.Simulations.PowerFlow.NumericalMethods.common_functions as cf
from GridCalEngine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
from GridCalEngine.DataStructures.numerical_circuit import NumericalCircuit
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.common_functions import power_flow_post_process_nonlinear
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.discrete_controls import (control_q_inside_method,
                                                                                    compute_slack_distribution)
from GridCalEngine.basic_structures import Logger, CxVec, IntVec, Vec, CscMat


def gausspf(nc: NumericalCircuit,
            Ybus: CscMat, Yf: CscMat, Yt: CscMat, Yshunt_bus: CxVec,
            S0: CxVec, I0: CxVec, Y0: CxVec, V0: CxVec,
            pv: IntVec, pq: IntVec, p: IntVec, pqv: IntVec, vd: IntVec,
            bus_installed_power: Vec, Qmin: Vec, Qmax: Vec, tol=1e-3, max_it=50,
            control_q=False, distribute_slack=False, verbose=False, logger: Logger = None) -> NumericPowerFlowResults:
    """
    Gauss-Seidel Power flow
    :param nc: NumericalCircuit
    :param Ybus: Admittance matrix
    :param Yf: Admittance from matrix
    :param Yt: Admittance to matrix
    :param Yshunt_bus: Vector of admittance due to devices
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

    if len(pvpq) == 0:
        return NumericPowerFlowResults(V=V,
                                       Scalc=S0 * nc.Sbase,
                                       m=np.ones(nc.nbr, dtype=float),
                                       tau=np.zeros(nc.nbr, dtype=float),
                                       Sf=np.zeros(nc.nbr, dtype=float),
                                       St=np.zeros(nc.nbr, dtype=float),
                                       If=np.zeros(nc.nbr, dtype=float),
                                       It=np.zeros(nc.nbr, dtype=float),
                                       loading=np.zeros(nc.nbr, dtype=float),
                                       losses=np.zeros(nc.nbr, dtype=float),
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
                                       norm_f=0.0,
                                       converged=True,
                                       iterations=0,
                                       elapsed=0.0)

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

    # compute the flows
    Sf, St, If, It, Vbranch, loading, losses, Sbus = power_flow_post_process_nonlinear(
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
        Sbase=nc.Sbase)

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
                                   norm_f=normF,
                                   converged=converged,
                                   iterations=iter_,
                                   elapsed=elapsed)
