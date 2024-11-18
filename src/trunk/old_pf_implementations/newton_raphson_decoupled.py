# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import time
import scipy
import numpy as np
import scipy.sparse as sp
from GridCalEngine.Utils.NumericalMethods.sparse_solve import get_sparse_type, get_linear_solver
import GridCalEngine.Simulations.PowerFlow.NumericalMethods.common_functions as cf
from GridCalEngine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults

linear_solver = get_linear_solver()
sparse = get_sparse_type()
scipy.ALLOW_THREADS = True
np.set_printoptions(precision=8, suppress=True, linewidth=320)


def Jacobian_decoupled(Ybus, V, Ibus, pq, pvpq):
    """
    Computes the decoupled Jacobian matrices
    Args:
        Ybus: Admittance matrix
        V: Array of nodal voltages
        Ibus: Array of nodal current Injections
        pq: Array with the indices of the PQ buses
        pvpq: Array with the indices of the PV and PQ buses

    Returns: J11, J22
    """
    I = Ybus * V - Ibus

    diagV = sp.diags(V)
    diagI = sp.diags(I)
    diagVnorm = sp.diags(V / np.abs(V))

    dS_dVm = diagV * np.conj(Ybus * diagVnorm) + np.conj(diagI) * diagVnorm
    dS_dVa = 1.0j * diagV * np.conj(diagI - Ybus * diagV)

    J11 = dS_dVa[np.ix_(pvpq, pvpq)].real
    J22 = dS_dVm[np.ix_(pq, pq)].imag

    return J11, J22


def NRD_LS(Ybus, S0, V0, I0, Y0, pv, pq, tol, max_it=15,
           acceleration_parameter=0.5, error_registry=None, verbose=False) -> NumericPowerFlowResults:
    """
    Solves the power flow using a full Newton's method with backtrack correction.
    @Author: Santiago Peñate Vera
    :param Ybus: Admittance matrix
    :param S0: Array of nodal power Injections
    :param V0: Array of nodal voltages (initial solution)
    :param I0: Array of nodal current Injections
    :param Y0: Array of nodal admittance Injections
    :param pv: Array with the indices of the PV buses
    :param pq: Array with the indices of the PQ buses
    :param tol: Tolerance
    :param max_it: Maximum number of iterations
    :param acceleration_parameter: parameter used to correct the "bad" iterations, typically 0.5
    :param error_registry: list to store the error for plotting
    :param verbose: Verbose?
    :return: NumericPowerFlowResults
    """

    start = time.time()

    use_norm_error = True

    # initialize
    back_track_counter = 0
    back_track_iterations = 0
    converged = 0
    iter_ = 0
    V = V0
    Va = np.angle(V)
    Vm = np.abs(V)
    dVa = np.zeros_like(Va)
    dVm = np.zeros_like(Vm)

    # set up indexing for updating V
    pvpq = np.r_[pv, pq]
    npv = len(pv)
    npq = len(pq)

    # evaluate F(x0)
    Sbus = cf.compute_zip_power(S0, I0, Y0, Vm)
    Scalc = cf.compute_power(Ybus, V)
    f = cf.compute_fx(Scalc, Sbus, pvpq, pq)

    # check tolerance
    if use_norm_error:
        norm_f = np.linalg.norm(f, np.inf)
    else:
        norm_f = 0.5 * f.dot(f)

    if error_registry is not None:
        error_registry.append(norm_f)

    if norm_f < tol:
        converged = 1

    # do Newton iterations
    while not converged and iter_ < max_it:
        # update iteration counter
        iter_ += 1

        # evaluate Jacobian
        J1, J4 = Jacobian_decoupled(Ybus, V, I0, pq, pvpq)

        # compute update step and reassign the solution vector
        dVa[pvpq] = linear_solver(J1, f[pvpq])
        dVm[pq] = linear_solver(J4, f[pq])

        # update voltage the Newton way (mu=1)
        mu_ = 1.0
        Vm -= mu_ * dVm
        Va -= mu_ * dVa
        Vnew = cf.polar_to_rect(Vm, Va)

        # compute the mismatch function f(x_new)
        Sbus = cf.compute_zip_power(S0, I0, Y0, Vm)
        Scalc = cf.compute_power(Ybus, Vnew)
        f_new = cf.compute_fx(Scalc, Sbus, pvpq, pq)

        if use_norm_error:
            norm_f_new = np.linalg.norm(f_new, np.inf)
        else:
            norm_f_new = 0.5 * f_new.dot(f_new)

        if error_registry is not None:
            error_registry.append(norm_f_new)

        cond = norm_f_new > norm_f  # condition to back track (no improvement at all)

        if not cond:
            back_track_counter += 1

        l_iter = 0
        while not cond and l_iter < 10 and mu_ > 0.01:
            # line search back
            # update voltage with a closer value to the last value in the Jacobian direction
            mu_ *= acceleration_parameter
            Vm -= mu_ * dVm
            Va -= mu_ * dVa
            Vnew = cf.polar_to_rect(Vm, Va)

            # compute the mismatch function f(x_new)
            Sbus = cf.compute_zip_power(S0, I0, Y0, Vm)
            Scalc = cf.compute_power(Ybus, Vnew)
            f_new = cf.compute_fx(Scalc, Sbus, pvpq, pq)

            if use_norm_error:
                norm_f_new = np.linalg.norm(f_new, np.inf)
            else:
                norm_f_new = 0.5 * f_new.dot(f_new)

            cond = norm_f_new > norm_f

            if error_registry is not None:
                error_registry.append(norm_f_new)

            l_iter += 1
            back_track_iterations += 1

        # update calculation variables
        V = Vnew
        f = f_new

        # check for convergence
        if use_norm_error:
            norm_f = np.linalg.norm(f_new, np.inf)
        else:
            norm_f = 0.5 * f_new.dot(f_new)

        if error_registry is not None:
            error_registry.append(norm_f)

        converged = norm_f < tol

    end = time.time()
    elapsed = end - start

    # return NumericPowerFlowResults(V, converged, norm_f, Scalc, None, None, None, None, None, None, iter_, elapsed)
    return NumericPowerFlowResults(V=V, converged=converged, norm_f=norm_f,
                                   Scalc=Scalc, m=None, tau=None,
                                   Ybus=None, Yf=None, Yt=None,
                                   iterations=iter_, elapsed=elapsed)

