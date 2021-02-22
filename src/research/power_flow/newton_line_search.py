# Copyright (c) 1996-2015 PSERC. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE_MATPOWER file.

# Copyright 1996-2015 PSERC. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

# Copyright (c) 2016-2017 by University of Kassel and Fraunhofer Institute for Wind Energy and
# Energy System Technology (IWES), Kassel. All rights reserved. Use of this source code is governed
# by a BSD-style license that can be found in the LICENSE file.

# The file has been modified from Pypower.
# The function mu() has been added to the solver in order to provide an optimal iteration control
#
# Copyright (c) 2018 Santiago Peñate Vera
#
# This file retains the BSD-Style license


from numpy import array, angle, exp, linalg, r_, Inf, conj, diag, asmatrix, asarray, zeros_like, zeros, complex128, \
empty, float64, int32, arange
from scipy.sparse import csr_matrix as sparse, hstack, vstack
from scipy.sparse.linalg import spsolve, splu
import numpy as np
import pandas as pd
import numba as nb
import time
from warnings import warn
from scipy.sparse import coo_matrix, csc_matrix
from scipy.sparse import hstack as hs, vstack as vs
from scipy.sparse.linalg import factorized, spsolve
from matplotlib import pyplot as plt
import scipy
scipy.ALLOW_THREADS = True
import time
import numpy as np

np.set_printoptions(precision=8, suppress=True, linewidth=320)


def dSbus_dV(Ybus, V, I):
    """
    Computes partial derivatives of power injection w.r.t. voltage.
    :param Ybus: Admittance matrix
    :param V: Bus voltages array
    :param I: Bus current injections array
    :return:
    """
    '''
    Computes partial derivatives of power injection w.r.t. voltage.

    Returns two matrices containing partial derivatives of the complex bus
    power injections w.r.t voltage magnitude and voltage angle respectively
    (for all buses). If C{Ybus} is a sparse matrix, the return values will be
    also. The following explains the expressions used to form the matrices::

        Ibus = Ybus * V - I

        S = diag(V) * conj(Ibus) = diag(conj(Ibus)) * V

    Partials of V & Ibus w.r.t. voltage magnitudes::
        dV/dVm = diag(V / abs(V))
        dI/dVm = Ybus * dV/dVm = Ybus * diag(V / abs(V))

    Partials of V & Ibus w.r.t. voltage angles::
        dV/dVa = j * diag(V)
        dI/dVa = Ybus * dV/dVa = Ybus * j * diag(V)

    Partials of S w.r.t. voltage magnitudes::
        dS/dVm = diag(V) * conj(dI/dVm) + diag(conj(Ibus)) * dV/dVm
               = diag(V) * conj(Ybus * diag(V / abs(V)))
                                        + conj(diag(Ibus)) * diag(V / abs(V))

    Partials of S w.r.t. voltage angles::
        dS/dVa = diag(V) * conj(dI/dVa) + diag(conj(Ibus)) * dV/dVa
               = diag(V) * conj(Ybus * j * diag(V))
                                        + conj(diag(Ibus)) * j * diag(V)
               = -j * diag(V) * conj(Ybus * diag(V))
                                        + conj(diag(Ibus)) * j * diag(V)
               = j * diag(V) * conj(diag(Ibus) - Ybus * diag(V))

    For more details on the derivations behind the derivative code used
    in PYPOWER information, see:

    [TN2]  R. D. Zimmerman, "AC Power Flows, Generalized OPF Costs and
    their Derivatives using Complex Matrix Notation", MATPOWER
    Technical Note 2, February 2010.
    U{http://www.pserc.cornell.edu/matpower/TN2-OPF-Derivatives.pdf}

    @author: Ray Zimmerman (PSERC Cornell)
    '''

    ib = range(len(V))

    Ibus = Ybus * V - I

    diagV = sparse((V, (ib, ib)))
    diagIbus = sparse((Ibus, (ib, ib)))
    diagVnorm = sparse((V / np.abs(V), (ib, ib)))

    dS_dVm = diagV * conj(Ybus * diagVnorm) + conj(diagIbus) * diagVnorm
    dS_dVa = 1.0j * diagV * conj(diagIbus - Ybus * diagV)

    return dS_dVm, dS_dVa


def mu(Ybus, Ibus, J, incS, dV, dx, pvpq, pq):
    """
    Calculate the Iwamoto acceleration parameter as described in:
    "A Load Flow Calculation Method for Ill-Conditioned Power Systems" by Iwamoto, S. and Tamura, Y."
    Args:
        Ybus: Admittance matrix
        J: Jacobian matrix
        incS: mismatch vector
        dV: voltage increment (in complex form)
        dx: solution vector as calculated dx = solve(J, incS)
        pvpq: array of the pq and pv indices
        pq: array of the pq indices

    Returns:
        the Iwamoto's optimal multiplier for ill conditioned systems
    """
    # evaluate the Jacobian of the voltage derivative
    # theoretically this is the second derivative matrix
    # since the Jacobian (J2) has been calculated with dV instead of V
    J2 = Jacobian(Ybus, dV, Ibus, pq, pvpq)

    a = incS
    b = J * dx
    c = 0.5 * dx * J2 * dx

    g0 = -a.dot(b)
    g1 = b.dot(b) + 2 * a.dot(c)
    g2 = -3.0 * b.dot(c)
    g3 = 2.0 * c.dot(c)

    roots = np.roots([g3, g2, g1, g0])
    # three solutions are provided, the first two are complex, only the real solution is valid
    return roots[2].real


def Jacobian(Ybus, V, Ibus, pq, pvpq):
    """
    Computes the system Jacobian matrix
    Args:
        Ybus: Admittance matrix
        V: Array of nodal voltages
        Ibus: Array of nodal current injections
        pq: Array with the indices of the PQ buses
        pvpq: Array with the indices of the PV and PQ buses

    Returns:
        The system Jacobian matrix
    """
    dS_dVm, dS_dVa = dSbus_dV(Ybus, V, Ibus)  # compute the derivatives

    J11 = dS_dVa[array([pvpq]).T, pvpq].real
    J12 = dS_dVm[array([pvpq]).T, pq].real
    J21 = dS_dVa[array([pq]).T, pvpq].imag
    J22 = dS_dVm[array([pq]).T, pq].imag

    J = vstack([hstack([J11, J12]),
                hstack([J21, J22])], format="csr")

    return J


def NR(Ybus, Sbus, V0, Ibus, pv, pq, tol, max_it=15, mu0=0.05, error_registry=None):
    """
    Solves the power flow using a full Newton's method
    Args:
        Ybus: Admittance matrix
        Sbus: Array of nodal power injections
        V0: Array of nodal voltages (initial solution)
        Ibus: Array of nodal current injections
        pv: Array with the indices of the PV buses
        pq: Array with the indices of the PQ buses
        tol: Tolerance
        max_it: Maximum number of iterations
        mu0: parameter used to correct the "bad" iterations, should be be between 1e-3 ~ 0.5
        error_registry: list to store the error for plotting
    Returns:
        Voltage solution, converged?, error, calculated power injections

    @Author: Santiago Penate Vera
    """
    start = time.time()

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
    pvpq = r_[pv, pq]
    npv = len(pv)
    npq = len(pq)

    # j1:j2 - V angle of pv buses
    j1 = 0
    j2 = npv
    # j3:j4 - V angle of pq buses
    j3 = j2
    j4 = j2 + npq
    # j5:j6 - V mag of pq buses
    j5 = j4
    j6 = j4 + npq

    # evaluate F(x0)
    Scalc = V * conj(Ybus * V - Ibus)
    dS = Scalc - Sbus  # compute the mismatch
    f = r_[dS[pv].real, dS[pq].real, dS[pq].imag]

    # check tolerance
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
        J = Jacobian(Ybus, V, Ibus, pq, pvpq)

        # compute update step
        dx = spsolve(J, f)

        # reassign the solution vector
        if npv:
            dVa[pv] = dx[j1:j2]
        if npq:
            dVa[pq] = dx[j3:j4]
            dVm[pq] = dx[j5:j6]

        # update voltage the Newton way (mu=1)
        mu_ = mu0
        Vm -= mu_ * dVm
        Va -= mu_ * dVa
        V = Vm * exp(1j * Va)

        Vm = np.abs(V)  # update Vm and Va again in case
        Va = np.angle(V)  # we wrapped around with a negative Vm

        # compute the mismatch function f(x_new)
        dS = V * conj(Ybus * V - Ibus) - Sbus  # complex power mismatch
        f_new = r_[dS[pv].real, dS[pq].real, dS[pq].imag]  # concatenate to form the mismatch function
        norm_f = 0.5 * f_new.dot(f_new)

        if error_registry is not None:
            error_registry.append(norm_f)

        if norm_f < tol:
            converged = 1

    end = time.time()
    elapsed = end - start

    print('iter_', iter_, '  -  back_track_counter', back_track_counter,
          '  -  back_track_iterations', back_track_iterations)

    return V, converged, norm_f, Scalc, elapsed


def NR_LS1(Ybus, Sbus, V0, Ibus, pv, pq, tol, max_it=15, acceleration_parameter=0.05, error_registry=None):
    """
    Solves the power flow using a full Newton's method with the Iwamoto optimal step factor.
    Args:
        Ybus: Admittance matrix
        Sbus: Array of nodal power injections
        V0: Array of nodal voltages (initial solution)
        Ibus: Array of nodal current injections
        pv: Array with the indices of the PV buses
        pq: Array with the indices of the PQ buses
        tol: Tolerance
        max_it: Maximum number of iterations
        acceleration_parameter: parameter used to correct the "bad" iterations, should be be between 1e-3 ~ 0.5
        error_registry: list to store the error for plotting
    Returns:
        Voltage solution, converged?, error, calculated power injections

    @Author: Santiago Penate Vera
    """
    start = time.time()

    # initialize
    back_track_counter = 0
    back_track_iterations = 0
    alpha = 1e-4
    converged = 0
    iter_ = 0
    V = V0
    Va = angle(V)
    Vm = abs(V)
    dVa = zeros_like(Va)
    dVm = zeros_like(Vm)

    # set up indexing for updating V
    pvpq = r_[pv, pq]
    npv = len(pv)
    npq = len(pq)

    # j1:j2 - V angle of pv buses
    j1 = 0
    j2 = npv
    # j3:j4 - V angle of pq buses
    j3 = j2
    j4 = j2 + npq
    # j5:j6 - V mag of pq buses
    j5 = j4
    j6 = j4 + npq

    # evaluate F(x0)
    Scalc = V * conj(Ybus * V - Ibus)
    dS = Scalc - Sbus  # compute the mismatch
    f = r_[dS[pv].real, dS[pq].real, dS[pq].imag]

    # check tolerance
    norm_f = linalg.norm(f, Inf)

    if error_registry is not None:
        error_registry.append(norm_f)

    if norm_f < tol:
        converged = 1

    # do Newton iterations
    while not converged and iter_ < max_it:
        # update iteration counter
        iter_ += 1

        # evaluate Jacobian
        J = Jacobian(Ybus, V, Ibus, pq, pvpq)

        # compute update step
        dx = spsolve(J, f)

        # reassign the solution vector
        if npv:
            dVa[pv] = dx[j1:j2]
        if npq:
            dVa[pq] = dx[j3:j4]
            dVm[pq] = dx[j5:j6]

        # update voltage the Newton way (mu=1)
        mu_ = 1.0
        Vm -= mu_ * dVm
        Va -= mu_ * dVa
        Vnew = Vm * exp(1j * Va)

        # compute the mismatch function f(x_new)
        dS = Vnew * conj(Ybus * Vnew - Ibus) - Sbus  # complex power mismatch
        f_new = r_[dS[pv].real, dS[pq].real, dS[pq].imag]  # concatenate to form the mismatch function
        norm_f_prev = linalg.norm(f + alpha * (f * J).dot(f_new - f), Inf)

        if error_registry is not None:
            error_registry.append(norm_f_prev)

        cond = norm_f < norm_f_prev  # condition to back track (no improvement at all)

        if not cond:
            back_track_counter += 1

        l_iter = 0
        while not cond and l_iter < 10 and mu_ > 0.01:
            # line search back

            # to divide mu by 4 is the simplest backtracking process
            # TODO: implement the more complex mu backtrack from numerical recipes

            # update voltage with a closer value to the last value in the Jacobian direction
            mu_ *= acceleration_parameter
            Vm -= mu_ * dVm
            Va -= mu_ * dVa
            Vnew = Vm * exp(1j * Va)

            # compute the mismatch function f(x_new)
            dS = Vnew * conj(Ybus * Vnew - Ibus) - Sbus  # complex power mismatch
            f_new = r_[dS[pv].real, dS[pq].real, dS[pq].imag]  # concatenate to form the mismatch function

            norm_f_new = linalg.norm(f_new, Inf)
            norm_f_new_prev = linalg.norm(f + alpha * (f * J).dot(f_new - f), Inf)

            cond = norm_f_new < norm_f_new_prev

            if error_registry is not None:
                error_registry.append(norm_f_new_prev)

            l_iter += 1
            back_track_iterations += 1

        # update calculation variables
        V = Vnew
        f = f_new

        # check for convergence
        norm_f = linalg.norm(f, Inf)

        if error_registry is not None:
            error_registry.append(norm_f)

        if norm_f < tol:
            converged = 1

    end = time.time()
    elapsed = end - start

    print('iter_', iter_, '  -  back_track_counter', back_track_counter,
          '  -  back_track_iterations', back_track_iterations)

    return V, converged, norm_f, Scalc, elapsed


def NR_LS2(Ybus, Sbus, V0, Ibus, pv, pq, tol, max_it=15, acceleration_parameter=0.05, error_registry=None):
    """
    Solves the power flow using a full Newton's method with the Iwamoto optimal step factor.
    Args:
        Ybus: Admittance matrix
        Sbus: Array of nodal power injections
        V0: Array of nodal voltages (initial solution)
        Ibus: Array of nodal current injections
        pv: Array with the indices of the PV buses
        pq: Array with the indices of the PQ buses
        tol: Tolerance
        max_it: Maximum number of iterations
        acceleration_parameter: parameter used to correct the "bad" iterations, should be be between 1e-3 ~ 0.5
        error_registry: list to store the error for plotting
    Returns:
        Voltage solution, converged?, error, calculated power injections

    @Author: Santiago Penate Vera
    """
    start = time.time()

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
    pvpq = r_[pv, pq]
    npv = len(pv)
    npq = len(pq)

    # j1:j2 - V angle of pv buses
    j1 = 0
    j2 = npv
    # j3:j4 - V angle of pq buses
    j3 = j2
    j4 = j2 + npq
    # j5:j6 - V mag of pq buses
    j5 = j4
    j6 = j4 + npq

    # evaluate F(x0)
    Scalc = V * conj(Ybus * V - Ibus)
    dS = Scalc - Sbus  # compute the mismatch
    f = r_[dS[pv].real, dS[pq].real, dS[pq].imag]

    # check tolerance
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
        J = Jacobian(Ybus, V, Ibus, pq, pvpq)

        # compute update step
        dx = spsolve(J, f)

        # reassign the solution vector
        if npv:
            dVa[pv] = dx[j1:j2]
        if npq:
            dVa[pq] = dx[j3:j4]
            dVm[pq] = dx[j5:j6]

        # update voltage the Newton way (mu=1)
        mu_ = 1.0
        Vm -= mu_ * dVm
        Va -= mu_ * dVa
        Vnew = Vm * exp(1j * Va)

        # compute the mismatch function f(x_new)
        dS = Vnew * conj(Ybus * Vnew - Ibus) - Sbus  # complex power mismatch
        f_new = r_[dS[pv].real, dS[pq].real, dS[pq].imag]  # concatenate to form the mismatch function
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
            Vnew = Vm * exp(1.0j * Va)

            # compute the mismatch function f(x_new)
            dS = Vnew * conj(Ybus * Vnew - Ibus) - Sbus  # complex power mismatch
            f_new = r_[dS[pv].real, dS[pq].real, dS[pq].imag]  # concatenate to form the mismatch function

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
        norm_f = 0.5 * f_new.dot(f_new)

        if error_registry is not None:
            error_registry.append(norm_f)

        if norm_f < tol:
            converged = 1

    end = time.time()
    elapsed = end - start

    print('iter_', iter_, '  -  back_track_counter', back_track_counter,
          '  -  back_track_iterations', back_track_iterations)

    return V, converged, norm_f, Scalc, elapsed


def NR_LS3(Ybus, Sbus, V0, Ibus, pv, pq, vd, tol, bus_installed_power,
           max_it=15, acceleration_parameter=0.05, error_registry=None, correct_slack=True):
    """
    Solves the power flow using a full Newton's method with the Iwamoto optimal step factor.
    Args:
        Ybus: Admittance matrix
        Sbus: Array of nodal power injections
        V0: Array of nodal voltages (initial solution)
        Ibus: Array of nodal current injections
        pv: Array with the indices of the PV buses
        pq: Array with the indices of the PQ buses
        tol: Tolerance
        max_it: Maximum number of iterations
        acceleration_parameter: parameter used to correct the "bad" iterations, should be be between 1e-3 ~ 0.5
        error_registry: list to store the error for plotting
    Returns:
        Voltage solution, converged?, error, calculated power injections

    @Author: Santiago Penate Vera
    """
    start = time.time()

    # initialize
    back_track_counter = 0
    back_track_iterations = 0
    alpha = 1e-4
    converged = 0
    iter_ = 0
    V = V0
    Va = angle(V)
    Vm = abs(V)
    dVa = zeros_like(Va)
    dVm = zeros_like(Vm)
    slack_corrected = False

    # set up indexing for updating V
    pvpq = r_[pv, pq]
    npv = len(pv)
    npq = len(pq)

    # j1:j2 - V angle of pv buses
    j1 = 0
    j2 = npv
    # j3:j4 - V angle of pq buses
    j3 = j2
    j4 = j2 + npq
    # j5:j6 - V mag of pq buses
    j5 = j4
    j6 = j4 + npq

    # evaluate F(x0)
    Scalc = V * conj(Ybus * V - Ibus)
    dS = Scalc - Sbus  # compute the mismatch
    f = r_[dS[pv].real, dS[pq].real, dS[pq].imag]

    # check tolerance
    norm_f = linalg.norm(f, Inf)

    if error_registry is not None:
        error_registry.append(norm_f)

    if norm_f < tol:
        converged = 1

    # do Newton iterations
    while not converged and iter_ < max_it:
        # update iteration counter
        iter_ += 1

        # evaluate Jacobian
        J = Jacobian(Ybus, V, Ibus, pq, pvpq)

        # compute update step
        dx = spsolve(J, f)

        # reassign the solution vector
        if npv:
            dVa[pv] = dx[j1:j2]
        if npq:
            dVa[pq] = dx[j3:j4]
            dVm[pq] = dx[j5:j6]

        # update voltage the Newton way (mu=1)
        mu_ = 1.0
        Vm -= mu_ * dVm
        Va -= mu_ * dVa
        Vnew = Vm * exp(1j * Va)

        # compute the mismatch function f(x_new)
        dS = Vnew * conj(Ybus * Vnew - Ibus) - Sbus  # complex power mismatch
        f_new = r_[dS[pv].real, dS[pq].real, dS[pq].imag]  # concatenate to form the mismatch function
        norm_f_prev = linalg.norm(f + alpha * (f * J).dot(f_new - f), Inf)

        if error_registry is not None:
            error_registry.append(norm_f_prev)

        cond = norm_f < norm_f_prev  # condition to back track (no improvement at all)

        if not cond:
            back_track_counter += 1

        l_iter = 0
        while not cond and l_iter < 10 and mu_ > 0.01:
            # line search back

            # to divide mu by 4 is the simplest backtracking process
            # TODO: implement the more complex mu backtrack from numerical recipes

            # update voltage with a closer value to the last value in the Jacobian direction
            mu_ *= acceleration_parameter
            Vm -= mu_ * dVm
            Va -= mu_ * dVa
            Vnew = Vm * exp(1j * Va)

            # compute the mismatch function f(x_new)
            dS = Vnew * conj(Ybus * Vnew - Ibus) - Sbus  # complex power mismatch
            f_new = r_[dS[pv].real, dS[pq].real, dS[pq].imag]  # concatenate to form the mismatch function

            norm_f_new = linalg.norm(f_new, Inf)
            norm_f_new_prev = linalg.norm(f + alpha * (f * J).dot(f_new - f), Inf)

            cond = norm_f_new < norm_f_new_prev

            if error_registry is not None:
                error_registry.append(norm_f_new_prev)

            l_iter += 1
            back_track_iterations += 1

        # update calculation variables
        V = Vnew
        f = f_new

        # correct slack
        if correct_slack:
            if norm_f <= 0.01 and not slack_corrected:
                Svd = V[vd] * np.conj(Ybus[vd, :].dot(V))
                slack_power = Svd.real.sum()
                total_installed_power = bus_installed_power.sum()
                if total_installed_power > 0.0:
                    delta = slack_power * bus_installed_power / total_installed_power
                    Sbus += delta
                    slack_corrected = True
                    print('Corrected slack!', delta.sum() * 100, 'MW')

        # check for convergence
        norm_f = linalg.norm(f, Inf)

        if error_registry is not None:
            error_registry.append(norm_f)

        if norm_f < tol:
            converged = 1

    end = time.time()
    elapsed = end - start

    print('iter_', iter_, '  -  back_track_counter', back_track_counter,
          '  -  back_track_iterations', back_track_iterations)

    if slack_corrected:
        Svd = V[vd] * np.conj(Ybus[vd, :].dot(V))
        slack_power = Svd.real.sum()
        print('Final slack', slack_power.real * 100, 'MW')

    return V, converged, norm_f, Scalc, elapsed


def F(V, Ybus, S, I, pq, pv):
    """

    :param V:
    :param Ybus:
    :param S:
    :param I:
    :param pq:
    :param pv:
    :return:
    """

    # compute the mismatch function f(x_new)
    dS = V * np.conj(Ybus * V - I) - S

    return np.r_[dS[pv].real, dS[pq].real, dS[pq].imag]  # concatenate to form the mismatch function


def fx(x, Ybus, S, I, pq, pv, pvpq, j1, j2, j3, j4, j5, j6, Va, Vm):
    """

    :param x:
    :param Ybus:
    :param S:
    :param I:
    :param pq:
    :param pv:
    :param pvpq:
    :param j1:
    :param j2:
    :param j3:
    :param j4:
    :param j5:
    :param j6:
    :param Va:
    :param Vm:
    :return:
    """

    npv = len(pv)
    npq = len(pq)

    # reassign the solution vector
    if npv:
        Va[pv] = x[j1:j2]
    if npq:
        Va[pq] = x[j3:j4]
        Vm[pq] = x[j5:j6]

    V = Vm * np.exp(1j * Va)  # voltage mismatch

    # right hand side
    g = F(V, Ybus, S, I, pq, pv)

    # jacobian
    gx = Jacobian(Ybus, V, I, pq, pvpq)

    # return the increment of x
    return spsolve(gx, g)


def runge_kutta_nr(Ybus, Sbus, V0, Ibus, pv, pq, tol, max_it=15, error_registry=None):
    """
    Solves the power flow using a the runge-kutta integration algorithm
    Args:
        Ybus: Admittance matrix
        Sbus: Array of nodal power injections
        V0: Array of nodal voltages (initial solution)
        Ibus: Array of nodal current injections
        pv: Array with the indices of the PV buses
        pq: Array with the indices of the PQ buses
        tol: Tolerance
        max_it: Maximum number of iterations
        error_registry: list of function evaluations
    Returns:
        Voltage solution, converged?, error, calculated power injections, elapsed time

    @Author: Santiago Peñate Vera
    """

    start = time.time()

    # initialize
    converged = False
    iter_ = 0
    V = V0.copy()

    # set up indexing for updating V
    pvpq = np.r_[pv, pq]
    npv = len(pv)
    npq = len(pq)

    # j1:j2 - V angle of pv buses
    j1 = 0
    j2 = npv
    # j3:j4 - V angle of pq buses
    j3 = j2
    j4 = j2 + npq
    # j5:j6 - V mag of pq buses
    j5 = j4
    j6 = j4 + npq

    # evaluate F(x0)
    Scalc = V * np.conj(Ybus * V - Ibus)
    mis = Scalc - Sbus  # compute the mismatch
    f = np.r_[mis[pv].real, mis[pq].real, mis[pq].imag]

    # check tolerance
    norm_f = np.linalg.norm(f, np.Inf)

    if norm_f < tol:
        converged = True

    if error_registry is not None:
        error_registry.append(norm_f)

    dt = 1.0

    # Compose x
    x = np.zeros(2 * npq + npv)
    Va = np.angle(V)
    Vm = np.abs(V)

    # do Newton iterations
    while not converged and iter_ < max_it:
        # update iteration counter
        iter_ += 1

        if npv:
            x[j1:j2] = Va[pv]
        if npq:
            x[j3:j4] = Va[pq]
            x[j5:j6] = Vm[pq]

        # Compute the Runge-Kutta steps
        k1 = fx(x,
                Ybus, Sbus, Ibus, pq, pv, pvpq, j1, j2, j3, j4, j5, j6, Va, Vm)

        k2 = fx(x + 0.5 * dt * k1,
                Ybus, Sbus, Ibus, pq, pv, pvpq, j1, j2, j3, j4, j5, j6, Va, Vm)

        k3 = fx(x + 0.5 * dt * k2,
                Ybus, Sbus, Ibus, pq, pv, pvpq, j1, j2, j3, j4, j5, j6, Va, Vm)

        k4 = fx(x + dt * k3,
                Ybus, Sbus, Ibus, pq, pv, pvpq, j1, j2, j3, j4, j5, j6, Va, Vm)

        x -= dt * (k1 + 2.0 * k2 + 2.0 * k3 + k4) / 6.0

        # re-assign the solution vector
        if npv:
            Va[pv] = x[j1:j2]
        if npq:
            Va[pq] = x[j3:j4]
            Vm[pq] = x[j5:j6]
        V = Vm * np.exp(1.0j * Va)  # voltage mismatch

        # evaluate F(x)
        Scalc = V * np.conj(Ybus * V - Ibus)
        mis = Scalc - Sbus  # complex power mismatch
        f = np.r_[mis[pv].real, mis[pq].real, mis[pq].imag]  # concatenate again

        # check for convergence
        norm_f = np.linalg.norm(f, np.Inf)

        if error_registry is not None:
            error_registry.append(norm_f)

        if norm_f > 0.01:
            dt = max(dt * 0.985, 0.75)
        else:
            dt = min(dt * 1.015, 0.75)

        if norm_f < tol:
            converged = True

    end = time.time()
    elapsed = end - start

    return V, converged, norm_f, Scalc, elapsed



########################################################################################################################
#  HELM
########################################################################################################################

@nb.njit("(c16[:])(c16[:, :], c16[:, :], i8, i8[:])")
def conv1(A, B, c, indices):
    """
    Performs the convolution of A* and B
    :param A: Coefficients matrix 1 (orders, buses)
    :param B: Coefficients matrix 2 (orders, buses)
    :param c: order of the coefficients
    :param indices: bus indices array
    :return: Array with the convolution for the buses given by "indices"
    """
    suma = np.zeros(len(indices), dtype=nb.complex128)
    for k in range(1, c + 1):
        for i, d in enumerate(indices):
            suma[i] += np.conj(A[k, d]) * B[c - k, d]
    return suma


@nb.njit("(c16[:])(c16[:, :], c16[:, :], i8, i8[:])")
def conv2(A, B, c, indices):
    """
    Performs the convolution of A and B
    :param A: Coefficients matrix 1 (orders, buses)
    :param B: Coefficients matrix 2 (orders, buses)
    :param c: order of the coefficients
    :param indices: bus indices array
    :return: Array with the convolution for the buses given by "indices"
    """
    suma = np.zeros(len(indices), dtype=nb.complex128)
    for k in range(1, c):
        for i, d in enumerate(indices):
            suma[i] += A[k, d] * B[c - 1 - k, d]
    return suma


@nb.njit("(c16[:])(c16[:, :], c16[:, :], i8, i8[:])")
def conv3(A, B, c, indices):
    """
    Performs the convolution of A and B*
    :param A: Coefficients matrix 1 (orders, buses)
    :param B: Coefficients matrix 2 (orders, buses)
    :param c: order of the coefficients
    :param indices: bus indices array
    :return: Array with the convolution for the buses given by "indices"
    """
    suma = np.zeros(len(indices), dtype=nb.complex128)
    for k in range(1, c):
        for i, d in enumerate(indices):
            suma[i] += A[k, d] * np.conj(B[c - k, d])
    return suma


def helm_coefficients_josep(Ybus, Yseries, V0, S0, Ysh0, pq, pv, sl, pqpv, tolerance=1e-6, max_coeff=30, verbose=False):
    """
    Holomorphic Embedding LoadFlow Method as formulated by Josep Fanals Batllori in 2020
    THis function just returns the coefficients for further usage in other routines
    :param Yseries: Admittance matrix of the series elements
    :param V0: vector of specified voltages
    :param S0: vector of specified power
    :param Ysh0: vector of shunt admittances (including the shunts of the branches)
    :param pq: list of pq nodes
    :param pv: list of pv nodes
    :param sl: list of slack nodes
    :param pqpv: sorted list of pq and pv nodes
    :param tolerance: target error (or tolerance)
    :param max_coeff: maximum number of coefficients
    :param verbose: print intermediate information
    :return: U, X, Q, iterations
    """

    npqpv = len(pqpv)
    npv = len(pv)
    nsl = len(sl)
    n = Yseries.shape[0]

    # --------------------------- PREPARING IMPLEMENTATION -------------------------------------------------------------
    U = np.zeros((max_coeff, npqpv), dtype=complex)  # voltages
    W = np.zeros((max_coeff, npqpv), dtype=complex)  # compute X=1/conj(U)
    Q = np.zeros((max_coeff, npqpv), dtype=complex)  # unknown reactive powers
    Vm0 = np.abs(V0)
    Vm2 = Vm0 * Vm0

    if n < 2:
        return U, W, Q, 0

    if verbose:
        print('Yseries')
        print(Yseries.toarray())
        df = pd.DataFrame(data=np.c_[Ysh0.imag, S0.real, S0.imag, Vm0],
                          columns=['Ysh', 'P0', 'Q0', 'V0'])
        print(df)

    Yred = Yseries[np.ix_(pqpv, pqpv)]  # admittance matrix without slack buses
    Yslack = -Yseries[np.ix_(pqpv, sl)]  # yes, it is the negative of this
    Yslack_vec = Yslack.sum(axis=1).A1
    G = np.real(Yred)  # real parts of Yij
    B = np.imag(Yred)  # imaginary parts of Yij
    P_red = S0.real[pqpv]
    Q_red = S0.imag[pqpv]
    Vslack = V0[sl]
    Ysh_red = Ysh0[pqpv]

    # indices 0 based in the internal scheme
    nsl_counted = np.zeros(n, dtype=int)
    compt = 0
    for i in range(n):
        if i in sl:
            compt += 1
        nsl_counted[i] = compt

    pq_ = pq - nsl_counted[pq]
    pv_ = pv - nsl_counted[pv]

    # .......................CALCULATION OF TERMS [0] ------------------------------------------------------------------

    U[0, :] = spsolve(Yred, Yslack_vec)
    W[0, :] = 1 / np.conj(U[0, :])

    # .......................CALCULATION OF TERMS [1] ------------------------------------------------------------------
    valor = np.zeros(npqpv, dtype=complex)

    # get the current injections that appear due to the slack buses reduction
    I_inj_slack = Yslack * Vslack

    valor[pq_] = I_inj_slack[pq_] - Yslack_vec[pq_] + (P_red[pq_] - Q_red[pq_] * 1j) * W[0, pq_] - U[0, pq_] * Ysh_red[pq_]
    valor[pv_] = I_inj_slack[pv_] - Yslack_vec[pv_] + P_red[pv_] * W[0, pv_] - U[0, pv_] * Ysh_red[pv_]

    # compose the right-hand side vector
    RHS = np.r_[valor.real,
                valor.imag,
                Vm2[pv] - (U[0, pv_] * U[0, pv_]).real]

    # Form the system matrix (MAT)
    Upv = U[0, pv_]
    Xpv = W[0, pv_]
    VRE = coo_matrix((2 * Upv.real, (np.arange(npv), pv_)), shape=(npv, npqpv)).tocsc()
    VIM = coo_matrix((2 * Upv.imag, (np.arange(npv), pv_)), shape=(npv, npqpv)).tocsc()
    XIM = coo_matrix((-Xpv.imag, (pv_, np.arange(npv))), shape=(npqpv, npv)).tocsc()
    XRE = coo_matrix((Xpv.real, (pv_, np.arange(npv))), shape=(npqpv, npv)).tocsc()
    EMPTY = csc_matrix((npv, npv))

    MAT = vs((hs((G,  -B,   XIM)),
              hs((B,   G,   XRE)),
              hs((VRE, VIM, EMPTY))), format='csc')

    if verbose:
        print('MAT')
        print(MAT.toarray())

    # factorize (only once)
    MAT_LU = factorized(MAT.tocsc())

    # solve
    LHS = MAT_LU(RHS)

    # update coefficients
    U[1, :] = LHS[:npqpv] + 1j * LHS[npqpv:2 * npqpv]
    Q[0, pv_] = LHS[2 * npqpv:]
    W[1, :] = -W[0, :] * np.conj(U[1, :]) / np.conj(U[0, :])

    # .......................CALCULATION OF TERMS [>=2] ----------------------------------------------------------------
    iter_ = 1
    range_pqpv = np.arange(npqpv, dtype=np.int64)
    V = V0.copy()
    c = 2
    converged = False
    norm_f = tolerance + 1.0  # any number that violates the convergence

    while c < max_coeff and not converged:  # c defines the current depth

        valor[pq_] = (P_red[pq_] - Q_red[pq_] * 1j) * W[c - 1, pq_] - U[c - 1, pq_] * Ysh_red[pq_]
        valor[pv_] = -1j * conv2(W, Q, c, pv_) - U[c - 1, pv_] * Ysh_red[pv_] + W[c - 1, pv_] * P_red[pv_]

        RHS = np.r_[valor.real,
                    valor.imag,
                    -conv3(U, U, c, pv_).real]

        LHS = MAT_LU(RHS)

        # update voltage coefficients
        U[c, :] = LHS[:npqpv] + 1j * LHS[npqpv:2 * npqpv]

        # update reactive power
        Q[c - 1, pv_] = LHS[2 * npqpv:]

        # update voltage inverse coefficients
        W[c, range_pqpv] = -conv1(U, W, c, range_pqpv) / np.conj(U[0, range_pqpv])

        # compute power mismatch
        if not np.mod(c, 2):  # check the mismatch every 4 iterations
            V[pqpv] = U.sum(axis=0)
            Scalc = V * np.conj(Ybus * V)
            dP = np.abs(S0[pqpv].real - Scalc[pqpv].real)
            dQ = np.abs(S0[pq].imag - Scalc[pq].imag)
            norm_f = np.linalg.norm(np.r_[dP, dQ], np.inf)  # same as max(abs())

            # check convergence
            converged = norm_f < tolerance
            print('mismatch check at c=', c)

        c += 1
        iter_ += 1

    return U, W, Q, iter_, norm_f


########################################################################################################################
#  MAIN
########################################################################################################################
if __name__ == "__main__":
    from GridCal.Engine import FileOpen, compile_snapshot_circuit
    from matplotlib import pyplot as plt
    import pandas as pd
    import os
    import time
    np.set_printoptions(linewidth=10000)
    pd.set_option('display.max_rows', 500)
    pd.set_option('display.max_columns', 500)
    pd.set_option('display.width', 1000)

    # fname = os.path.join('..', '..', '..', 'Grids_and_profiles', 'grids', 'IEEE 30 Bus with storage.xlsx')
    # fname = os.path.join('..', '..', '..', 'Grids_and_profiles', 'grids', 'Illinois200Bus.xlsx')
    # fname = os.path.join('..', '..', '..', 'Grids_and_profiles', 'grids', 'Pegase 2869.xlsx')
    # fname = os.path.join('..', '..', '..', 'Grids_and_profiles', 'grids', '1354 Pegase.xlsx')
    # fname = os.path.join('..', '..', '..', 'Grids_and_profiles', 'grids', 'IEEE 14.xlsx')
    # fname = '/home/santi/Documentos/Private_Grids/2026_INVIERNO_para Plexos_FINAL_9.raw'
    fname = '/home/santi/Documentos/Private_Grids/201902271115 caso TReal Israel.raw'

    grid = FileOpen(file_name=fname).open()
    nc = compile_snapshot_circuit(grid)
    islands = nc.split_into_islands(ignore_single_node_islands=True)
    circuit = islands[0]

    # declare figure
    fig = plt.figure(figsize=(12, 7))
    ax = fig.add_subplot(1, 1, 1)

    # circuit.Vbus = np.ones(len(circuit.Vbus), dtype=complex)

    print('Newton-Raphson-Line-search 3')
    for acc in [0.5]:  # [1e-6, 1e-5, 1e-4, 1e-3, 1e-2, 0.1]
        start_time = time.time()

        # print('Ybus')
        # print(circuit.Ybus.toarray())

        error_data1 = list()
        V1, converged_, err, S, el = NR_LS3(Ybus=circuit.Ybus,
                                            Sbus=circuit.Sbus,
                                            V0=circuit.Vbus,
                                            Ibus=circuit.Ibus,
                                            pv=circuit.pv,
                                            pq=circuit.pq,
                                            vd=circuit.vd,
                                            bus_installed_power=circuit.bus_installed_power / circuit.Sbase,
                                            tol=1e-10,
                                            max_it=50,
                                            acceleration_parameter=acc,
                                            error_registry=error_data1,
                                            correct_slack=True)

        print("--- %s seconds ---" % (time.time() - start_time))
        print('error: \t', err)
        ax.plot(error_data1, lw=2, label='NRLS 1:' + str(acc))

    # print('\nNewton-Raphson-Line-search 2')
    # for acc in [1e-6, 1e-5, 1e-4, 1e-3, 1e-2, 0.1]:
    #
    #     start_time = time.time()
    #     error_data2 = list()
    #     V1, converged_, err, S, el = NR_LS2(Ybus=circuit.Ybus,
    #                                         Sbus=circuit.Sbus,
    #                                         V0=circuit.Vbus,
    #                                         Ibus=circuit.Ibus,
    #                                         pv=circuit.pv,
    #                                         pq=circuit.pq,
    #                                         tol=1e-9,
    #                                         max_it=100,
    #                                         acceleration_parameter=acc,
    #                                         error_registry=error_data2)
    #
    #     print("--- %s seconds ---" % (time.time() - start_time))
    #     print('error: \t', err)
    #
    #     ax.plot(error_data2, lw=2, linestyle=':', label='NRLS 2: ' + str(acc))
    #
    # print('\nVanilla NR ---')
    # start_time = time.time()
    # error_data3 = list()
    # V1, converged_, err, S, el = NR(Ybus=circuit.Ybus,
    #                                 Sbus=circuit.Sbus,
    #                                 V0=circuit.Vbus,
    #                                 Ibus=circuit.Ibus,
    #                                 pv=circuit.pv,
    #                                 pq=circuit.pq,
    #                                 tol=1e-9,
    #                                 max_it=5,
    #                                 mu0=1.0,
    #                                 error_registry=error_data3)
    # ax.plot(error_data3, lw=2, linestyle='--', label='NR')
    #
    # print("--- %s seconds ---" % (time.time() - start_time))
    # print('error: \t', err)

    # print('\nRunge kutta ---')
    # start_time = time.time()
    # error_data3 = list()
    # V1, converged_, err, S, el = runge_kutta_nr(Ybus=circuit.Ybus,
    #                                             Sbus=circuit.Sbus,
    #                                             V0=circuit.Vbus,
    #                                             Ibus=circuit.Ibus,
    #                                             pv=circuit.pv,
    #                                             pq=circuit.pq,
    #                                             tol=1e-15,
    #                                             max_it=30,
    #                                             error_registry=error_data3)
    # ax.plot(error_data3, lw=2, linestyle='--', label='runge-kutta')
    #
    # print("--- %s seconds ---" % (time.time() - start_time))
    # print('error: \t', err)
    #
    # ax.set_yscale('log')
    # ax.set_xlabel('Evaluations of $f(x)$')
    # ax.set_ylabel('Error')
    # ax.legend()


    # print('\nHELM ---')
    # start_time = time.time()
    # n_coeff = 30
    #
    # # compute the series of coefficients
    # U, X, Q, iter_, norm_f = helm_coefficients_josep(Ybus=circuit.Ybus,
    #                                                  Yseries=circuit.Yseries,
    #                                                  V0=circuit.Vbus,
    #                                                  S0=circuit.Sbus,
    #                                                  Ysh0=circuit.Ysh_helm,
    #                                                  pv=circuit.pv,
    #                                                  pq=circuit.pq,
    #                                                  sl=circuit.ref,
    #                                                  pqpv=circuit.pqpv,
    #                                                  tolerance=1e-15,
    #                                                  max_coeff=n_coeff,
    #                                                  verbose=False)
    #
    # V = circuit.Vbus.copy()
    # Sbus = circuit.Sbus
    # Ybus = circuit.Ybus
    # pv = circuit.pv
    # pq = circuit.pq
    # error_data4 = list()
    # for c in range(n_coeff):
    #     V[circuit.pqpv] = U[:c, :].sum(axis=0)
    #     # evaluate F(x0)
    #     Scalc = V * np.conj(Ybus * V)
    #     mis = Scalc - Sbus  # compute the mismatch
    #     f = np.r_[mis[pv].real, mis[pq].real, mis[pq].imag]
    #
    #     # check tolerance
    #     norm_f = np.linalg.norm(f, np.Inf)
    #     error_data4.append(norm_f)
    #
    # ax.plot(error_data4, lw=2, linestyle='--', label='HELM')
    #
    # print("--- %s seconds ---" % (time.time() - start_time))
    # print('error: \t', err)
    #
    # ax.set_yscale('log')
    # ax.set_xlabel('Evaluations of $f(x)$')
    # ax.set_ylabel('Error')
    # ax.legend()
    # check against the standard NR power flow used in GridCal
    # print('\nNR implemented in GridCal ---')
    # options = PowerFlowOptions(SolverType.NR, verbose=False, tolerance=1e-9, control_q=False)
    # power_flow = PowerFlowDriver(grid, options)
    #
    # start_time = time.time()
    # power_flow.run()
    # print("--- %s seconds ---" % (time.time() - start_time))
    # vnr = power_flow.results.voltage
    #
    # print('error: \t', power_flow.results.error)
    #
    # # check
    # data = np.c_[np.abs(V1), angle(V1), np.abs(vnr), angle(vnr),  np.abs(V1 - vnr)]
    # cols = ['|V|', 'angle', '|V| benchmark NR', 'angle benchmark NR', 'Diff']
    # df = pd.DataFrame(data, columns=cols)

    print()
    # print(df)

    # plt.show()
