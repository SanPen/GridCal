# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import time
import scipy
import numpy as np
from GridCalEngine.Utils.NumericalMethods.sparse_solve import get_sparse_type, get_linear_solver
from GridCalEngine.Utils.Sparse.csc2 import spsolve_csc
from GridCalEngine.Simulations.Derivatives.ac_jacobian import AC_jacobianVc, CSC
import GridCalEngine.Simulations.PowerFlow.NumericalMethods.common_functions as cf
from GridCalEngine.DataStructures.numerical_circuit import NumericalCircuit
from GridCalEngine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.common_functions import power_flow_post_process_nonlinear
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.discrete_controls import control_q_inside_method
from GridCalEngine.basic_structures import Vec, CxVec, IntVec, Logger, CscMat

linear_solver = get_linear_solver()
sparse = get_sparse_type()
scipy.ALLOW_THREADS = True
np.set_printoptions(precision=8, suppress=True, linewidth=320)


def mu(Ybus: CscMat, J: CSC, incS: Vec, dV: CxVec, dx: Vec, block1_idx: IntVec, block2_idx: IntVec, block3_idx: IntVec):
    """
    Calculate the Iwamoto acceleration parameter as described in:
    "A Load Flow Calculation Method for Ill-Conditioned Power Systems" by Iwamoto, S. and Tamura, Y."
    :param Ybus: Admittance matrix
    :param J: Jacobian matrix
    :param incS: mismatch vector
    :param dV: voltage increment (in complex form)
    :param dx: solution vector as calculated dx = solve(J, incS)
    :param block1_idx: pv, pq, p, pqv
    :param block2_idx: pq, p
    :param block3_idx: pq, pqv
    :return: the Iwamoto's optimal multiplier for ill conditioned systems
    """

    # evaluate the Jacobian of the voltage derivative
    # theoretically this is the second derivative matrix
    # since the Jacobian (J2) has been calculated with dV instead of V

    J2 = AC_jacobianVc(Ybus, dV, block1_idx, block2_idx, block3_idx)

    a = incS
    b = J.dot(dx)
    c = 0.5 * dx * J2.dot(dx)

    g0 = -a.dot(b)
    g1 = b.dot(b) + 2 * a.dot(c)
    g2 = -3.0 * b.dot(c)
    g3 = 2.0 * c.dot(c)

    roots = np.roots([g3, g2, g1, g0])

    # three solutions are provided, the first two are complex, only the real solution is valid
    return roots[2].real


def IwamotoNR(nc: NumericalCircuit,
              Ybus: CscMat, Yf: CscMat, Yt: CscMat, Yshunt_bus: CxVec,
              S0: CxVec, V0: CxVec, I0: CxVec, Y0: CxVec,
              pv_: IntVec, pq_: IntVec, pqv_: IntVec, p_: IntVec, vd_: IntVec,
              Qmin: Vec, Qmax: Vec, tol: float, max_it: int = 15,
              control_q: bool = False, robust: bool = False, logger: Logger = None) -> NumericPowerFlowResults:
    """
    Solves the power flow using a full Newton's method with the Iwamoto optimal step factor.
    :param nc: NumericalCircuit instance
    :param Ybus: Admittance matrix
    :param Yf: Admittance from matrix
    :param Yt: Admittance to matrix
    :param S0: Array of nodal power Injections
    :param V0: Array of nodal voltages (initial solution)
    :param I0: Array of nodal current Injections
    :param Y0: Array of nodal admittance Injections
    :param pv_: Array with the indices of the PV buses
    :param pq_: Array with the indices of the PQ buses
    :param pqv_: Array with the indices of the PQV buses
    :param p_: Array with the indices of the P buses
    :param vd_: Array with the indices of the slack buses
    :param Qmin: Array of nodal minimum reactive power injections
    :param Qmax: Array of nodal maximum reactive power injections
    :param tol: Tolerance
    :param max_it: Maximum number of iterations
    :param control_q: Control reactive power?
    :param robust: use of the Iwamoto optimal step factor?.
    :param logger: Logger
    :return: Voltage solution, converged?, error, calculated power Injections
    """
    start = time.time()

    # initialize
    iter_ = 0
    V = V0
    Va = np.angle(V)
    Vm = np.abs(V)
    dVa = np.zeros_like(Va)
    dVm = np.zeros_like(Vm)

    # set up indexing for updating V
    pq = pq_.copy()
    pv = pv_.copy()
    pqv = pqv_.copy()
    p = p_.copy()
    blck1_idx = np.r_[pv, pq, p, pqv]
    blck2_idx = np.r_[pq, p]
    blck3_idx = np.r_[pq, pqv]
    n_block1 = len(blck1_idx)

    if n_block1 > 0:

        # evaluate F(x0)
        Sbus = cf.compute_zip_power(S0, I0, Y0, Vm)
        Scalc = cf.compute_power(Ybus, V)
        f = cf.compute_fx(Scalc, Sbus, blck1_idx, blck3_idx)
        norm_f = cf.compute_fx_error(f)

        # check tolerance
        converged = norm_f < tol

        # do Newton iterations
        while not converged and iter_ < max_it:
            # update iteration counter
            iter_ += 1

            # evaluate Jacobian
            J = AC_jacobianVc(Ybus, V, blck1_idx, blck2_idx, blck3_idx)

            # compute update step
            try:
                dx, ok = spsolve_csc(J, f)

                if not ok:
                    end = time.time()
                    elapsed = end - start
                    logger.add_error('NR Singular matrix @iter:'.format(iter_))

                    return NumericPowerFlowResults(V=V,
                                                   Scalc=Scalc,
                                                   m=np.ones(nc.nbr, dtype=float),
                                                   tau=np.zeros(nc.nbr, dtype=float),
                                                   Sf=np.zeros(nc.nbr, dtype=complex),
                                                   St=np.zeros(nc.nbr, dtype=complex),
                                                   If=np.zeros(nc.nbr, dtype=complex),
                                                   It=np.zeros(nc.nbr, dtype=complex),
                                                   loading=np.zeros(nc.nbr, dtype=complex),
                                                   losses=np.zeros(nc.nbr, dtype=complex),
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
                                                   norm_f=norm_f,
                                                   converged=converged,
                                                   iterations=iter_,
                                                   elapsed=elapsed)

            except RuntimeError:
                converged = False
                iter_ = max_it + 1  # exit condition
                end = time.time()
                elapsed = end - start
                return NumericPowerFlowResults(V=V,
                                               Scalc=Scalc,
                                               m=np.ones(nc.nbr, dtype=float),
                                               tau=np.zeros(nc.nbr, dtype=float),
                                               Sf=np.zeros(nc.nbr, dtype=complex),
                                               St=np.zeros(nc.nbr, dtype=complex),
                                               If=np.zeros(nc.nbr, dtype=complex),
                                               It=np.zeros(nc.nbr, dtype=complex),
                                               loading=np.zeros(nc.nbr, dtype=complex),
                                               losses=np.zeros(nc.nbr, dtype=complex),
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
                                               norm_f=norm_f,
                                               converged=converged,
                                               iterations=iter_,
                                               elapsed=elapsed)

            # assign the solution vector
            dVa[blck1_idx] = dx[:n_block1]
            dVm[blck2_idx] = dx[n_block1:]
            dV = dVm * np.exp(1j * dVa)  # voltage mismatch

            # update voltage
            if robust:
                # if dV contains zeros will crash the second Jacobian derivative
                if not np.any(dV == 0.0):
                    # calculate the optimal multiplier for enhanced convergence
                    mu_ = mu(Ybus, J, f, dV, dx, blck1_idx, blck2_idx, blck3_idx)
                else:
                    mu_ = 1.0
            else:
                mu_ = 1.0

            Vm -= mu_ * dVm
            Va -= mu_ * dVa
            V = Vm * np.exp(1j * Va)

            Vm = np.abs(V)  # update Vm and Va again in case
            Va = np.angle(V)  # we wrapped around with a negative Vm

            # evaluate F(x)
            Sbus = cf.compute_zip_power(S0, I0, Y0, Vm)
            Scalc = cf.compute_power(Ybus, V)
            f = cf.compute_fx(Scalc, Sbus, blck1_idx, blck3_idx)
            norm_f = cf.compute_fx_error(f)

            # review reactive power limits
            # it is only worth checking Q limits with a low error
            # since with higher errors, the Q values may be far from realistic
            # finally, the Q control only makes sense if there are pv nodes
            if control_q and norm_f < 1e-2 and (len(pv) + len(p)) > 0:

                # check and adjust the reactive power
                # this function passes pv buses to pq when the limits are violated,
                # but not pq to pv because that is unstable
                changed, pv, pq, pqv, p = control_q_inside_method(Scalc, S0, pv, pq, pqv, p, Qmin, Qmax)

                if len(changed) > 0:
                    # adjust internal variables to the new pq|pv values
                    blck1_idx = np.r_[pv, pq, p, pqv]
                    blck2_idx = np.r_[pq, p]
                    blck3_idx = np.r_[pq, pqv]
                    n_block1 = len(blck1_idx)

                    # recompute the error based on the new Sbus
                    f = cf.compute_fx(Scalc, Sbus, blck1_idx, blck3_idx)
                    norm_f = cf.compute_fx_error(f)

            # check convergence
            converged = norm_f < tol

            # check for absurd values
            if np.any(np.isnan(V)) or np.any(Vm == 0):
                converged = False
                break

    else:
        norm_f = 0
        converged = True
        Scalc = S0 + I0 * Vm + Y0 * np.power(Vm, 2)  # compute the ZIP power injection

    end = time.time()
    elapsed = end - start

    # Compute the Branches power and the slack buses power
    Sf, St, If, It, Vbranch, loading, losses, Sbus = power_flow_post_process_nonlinear(
        Sbus=Scalc,
        V=V,
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
                                   norm_f=norm_f,
                                   converged=converged,
                                   iterations=iter_,
                                   elapsed=elapsed)
