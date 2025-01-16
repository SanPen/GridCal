# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
from numpy.linalg import norm
from scipy.sparse.linalg import splu
import time
import GridCalEngine.Simulations.PowerFlow.NumericalMethods.common_functions as cf
from GridCalEngine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.discrete_controls import (control_q_inside_method,
                                                                                    compute_slack_distribution)
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.common_functions import power_flow_post_process_nonlinear
from GridCalEngine.basic_structures import Vec, CxVec, CscMat, IntVec
from GridCalEngine.DataStructures.numerical_circuit import NumericalCircuit

np.set_printoptions(linewidth=320)


def FDPF(nc: NumericalCircuit,
         Vbus: CxVec,
         S0: CxVec,
         I0: CxVec,
         Y0: CxVec,
         Ybus: CscMat, Yf: CscMat, Yt: CscMat, Yshunt_bus: CxVec,
         B1: CscMat,
         B2: CscMat,
         pv_: IntVec,
         pq_: IntVec,
         pqv_: IntVec,
         p_: IntVec,
         vd_: IntVec,
         Qmin: Vec,
         Qmax: Vec,
         bus_installed_power: Vec,
         tol: float = 1e-9,
         max_it: float = 100,
         control_q: bool = False,
         distribute_slack: bool = False) -> NumericPowerFlowResults:
    """
    Fast decoupled power flow
    :param nc: NumericalCircuit instance
    :param Vbus: array of initial voltages
    :param S0: array of power Injections
    :param I0: array of current Injections
    :param Y0: array of admittance Injections
    :param Ybus: Admittance matrix
    :param Yf: Admittance from matrix
    :param Yt: Admittance to matrix
    :param B1: B' matrix for the fast decoupled algorithm
    :param B2: B'' matrix for the fast decoupled algorithm
    :param pv_: Array with the indices of the PV buses
    :param pq_: Array with the indices of the PQ buses
    :param pqv_: Array with the indices of the PQV buses
    :param p_: Array with the indices of the P buses
    :param vd_: Array with the indices of the VD buses
    :param Qmin: Minimum voltage
    :param Qmax: Maximum voltage
    :param tol: Tolerance
    :param bus_installed_power: Array of installed power per bus
    :param max_it: maximum number of iterations
    :param control_q: Control Q method
    :param distribute_slack: Distribute Slack method
    :return: NumericPowerFlowResults instance
    """

    start = time.time()

    # set voltage vector for the iterations
    voltage = Vbus.copy()
    Va = np.angle(voltage)
    Vm = np.abs(voltage)

    # set up indexing for updating V
    pq = pq_.copy()
    pv = pv_.copy()
    pqv = pqv_.copy()
    p = p_.copy()
    blck1_idx = np.r_[pv, pq, p, pqv]
    blck2_idx = np.r_[pq, p]
    blck3_idx = np.r_[pq, pqv]
    n_block1 = len(blck1_idx)

    # Factorize B1 and B2
    B1_factorization = splu(B1[np.ix_(blck1_idx, blck1_idx)])
    B2_factorization = splu(B2[np.ix_(blck3_idx, blck2_idx)])

    # evaluate initial mismatch
    Sbus = cf.compute_zip_power(S0, I0, Y0, Vm)  # compute the ZIP power injection
    Scalc = voltage * np.conj(Ybus * voltage)
    mis = (Scalc - Sbus) / Vm  # complex power mismatch
    dP = mis[blck1_idx].real
    dQ = mis[blck3_idx].imag

    if n_block1 > 0:
        normP = norm(dP, np.inf)
        normQ = norm(dQ, np.inf)
        converged = normP < tol and normQ < tol

        # iterate
        iter_ = 0
        while not converged and iter_ < max_it:

            iter_ += 1

            # ----------------------------- P iteration to update Va ----------------------
            # solve voltage angles
            dVa = B1_factorization.solve(dP)

            # update voltage
            Va[blck1_idx] -= dVa
            voltage = Vm * np.exp(1j * Va)

            # evaluate mismatch
            # (Sbus does not change here since Vm is fixed ...)
            Scalc = cf.compute_power(Ybus, voltage)
            mis = (Scalc - Sbus) / Vm  # complex power mismatch
            dP = mis[blck1_idx].real
            dQ = mis[blck3_idx].imag
            normP = norm(dP, np.inf)
            normQ = norm(dQ, np.inf)

            if normP < tol and normQ < tol:
                converged = True
            else:
                # ----------------------------- Q iteration to update Vm ----------------------
                # Solve voltage modules
                dVm = B2_factorization.solve(dQ)

                # update voltage
                Vm[blck2_idx] -= dVm
                voltage = Vm * np.exp(1j * Va)

                # evaluate mismatch
                Sbus = cf.compute_zip_power(S0, I0, Y0, Vm)  # compute the ZIP power injection
                Scalc = cf.compute_power(Ybus, voltage)
                mis = (Scalc - Sbus) / Vm  # complex power mismatch
                dP = mis[blck1_idx].real
                dQ = mis[blck3_idx].imag
                normP = norm(dP, np.inf)
                normQ = norm(dQ, np.inf)

                if normP < tol and normQ < tol:
                    converged = True

            # control of Q limits --------------------------------------------------------------------------------------
            # review reactive power limits
            # it is only worth checking Q limits with a low error
            # since with higher errors, the Q values may be far from realistic
            # finally, the Q control only makes sense if there are pv nodes
            if control_q and normQ < 1e-2 and (len(pv) + len(p)) > 0:

                # check and adjust the reactive power
                # this function passes pv buses to pq when the limits are violated,
                # but not pq to pv because that is unstable
                changed, pv, pq, pqv, p = control_q_inside_method(Scalc, S0, pv, pq, pqv, p, Qmin, Qmax)

                if len(changed) > 0:
                    # adjust internal variables to the new pq|pv values
                    blck1_idx = np.r_[pv, pq, p, pqv]
                    blck2_idx = np.r_[pq, p]
                    blck3_idx = np.r_[pq, pqv]

                    # Factorize B1 and B2
                    B1_factorization = splu(B1[np.ix_(blck1_idx, blck1_idx)])
                    B2_factorization = splu(B2[np.ix_(blck3_idx, blck2_idx)])

            if distribute_slack and normQ < 1e-2:
                ok, delta = compute_slack_distribution(Scalc=Scalc,
                                                       vd=vd_,
                                                       bus_installed_power=bus_installed_power)
                if ok:
                    S0 += delta

        F = np.r_[dP, dQ]  # concatenate again
        normF = norm(F, np.inf)

    else:
        converged = True
        iter_ = 0
        normF = 0

    end = time.time()
    elapsed = end - start

    # compute the flows
    Sf, St, If, It, Vbranch, loading, losses, Sbus = power_flow_post_process_nonlinear(
        Sbus=Scalc,
        V=voltage,
        F=nc.passive_branch_data.F,
        T=nc.passive_branch_data.T,
        pv=pv,
        vd=vd_,
        Ybus=Ybus,
        Yf=Yf,
        Yt=Yt,
        Yshunt_bus=Yshunt_bus,
        branch_rates=nc.passive_branch_data.rates,
        Sbase=nc.Sbase)

    return NumericPowerFlowResults(V=voltage,
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
