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


# from numpy import array, angle, exp, linalg, r_, Inf, conj, diag, asmatrix, asarray, zeros_like, zeros, complex128, \
# empty, float64, int32, arange
# from scipy.sparse import issparse, hstack as hstack_sp, vstack as vstack_sp, diags
# try:
#     from cvxoptklu import klu
#     spsolve = klu.linsolve
#     from scipy.sparse import csc_matrix as sparse
#     print('Using KLU!')
# except ImportError:
#     print('Using scipy')
#     from scipy.sparse.linalg import spsolve
#     from scipy.sparse import csr_matrix as sparse
import time
import scipy
import scipy.sparse as sp
import numpy as np

from GridCal.Engine.Simulations.sparse_solve import get_sparse_type, get_linear_solver

linear_solver = get_linear_solver()
sparse = get_sparse_type()
scipy.ALLOW_THREADS = True
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

    dS_dVm = diagV * np.conj(Ybus * diagVnorm) + np.conj(diagIbus) * diagVnorm
    dS_dVa = 1.0j * diagV * np.conj(diagIbus - Ybus * diagV)

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
    I = Ybus * V - Ibus

    diagV = sp.diags(V)
    diagI = sp.diags(I)
    diagVnorm = sp.diags(V / np.abs(V))

    dS_dVm = diagV * np.conj(Ybus * diagVnorm) + np.conj(diagI) * diagVnorm
    dS_dVa = 1.0j * diagV * np.conj(diagI - Ybus * diagV)

    # J11 = dS_dVa[np.array([pvpq]).T, pvpq].real
    # J12 = dS_dVm[np.array([pvpq]).T, pq].real
    # J21 = dS_dVa[np.array([pq]).T, pvpq].imag
    # J22 = dS_dVm[np.array([pq]).T, pq].imag

    # J = sp.vstack([sp.hstack([J11, J12]),
    #                sp.hstack([J21, J22])], format="csr")

    # J11 = dS_dVa[np.ix_(pvpq, pvpq)].real
    # J12 = dS_dVm[np.ix_(pvpq, pq)].real
    # J21 = dS_dVa[np.ix_(pq, pvpq)].imag
    # J22 = dS_dVm[np.ix_(pq, pq)].imag

    J = sp.vstack([sp.hstack([dS_dVa[np.ix_(pvpq, pvpq)].real, dS_dVm[np.ix_(pvpq, pq)].real]),
                   sp.hstack([dS_dVa[np.ix_(pq, pvpq)].imag,   dS_dVm[np.ix_(pq, pq)].imag])], format="csr")

    return sparse(J)


def NR_LS(Ybus, Sbus, V0, Ibus, pv, pq, tol, max_it=15, correction_parameter=1e-4):
    """
    Solves the power flow using a full Newton's method with the backtrack improvement algorithm
    Args:
        Ybus: Admittance matrix
        Sbus: Array of nodal power injections
        V0: Array of nodal voltages (initial solution)
        Ibus: Array of nodal current injections
        pv: Array with the indices of the PV buses
        pq: Array with the indices of the PQ buses
        tol: Tolerance
        max_it: Maximum number of iterations
        correction_parameter: parameter used to correct the "bad" iterations, should be be between 1e-5 ~ 0.5
    Returns:
        Voltage solution, converged?, error, calculated power injections

    @author: Ray Zimmerman (PSERC Cornell)
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
    Va = np.angle(V)
    Vm = np.abs(V)
    dVa = np.zeros_like(Va)
    dVm = np.zeros_like(Vm)

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
    dS = Scalc - Sbus  # compute the mismatch
    f = np.r_[dS[pv].real, dS[pq].real, dS[pq].imag]

    if (npq + npv) > 0:
        # check tolerance
        norm_f = np.linalg.norm(f, np.Inf)

        if norm_f < tol:
            converged = 1

        # do Newton iterations
        while not converged and iter_ < max_it:
            # update iteration counter
            iter_ += 1

            # evaluate Jacobian
            J = Jacobian(Ybus, V, Ibus, pq, pvpq)

            # compute update step
            dx = linear_solver(J, f)

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
            Vnew = Vm * np.exp(1j * Va)

            # compute the mismatch function f(x_new)
            dS = Vnew * np.conj(Ybus * Vnew - Ibus) - Sbus  # complex power mismatch
            f_new = np.r_[dS[pv].real, dS[pq].real, dS[pq].imag]  # concatenate to form the mismatch function
            f_new_prev = f + alpha * (f * J).dot(f_new - f)
            cond = (f_new < f_new_prev).any()  # condition to back track (no improvement at all)

            if not cond:
                back_track_counter += 1

            l_iter = 0
            while not cond and l_iter < 10 and mu_ > 0.01:
                # line search back

                # to divide mu by 4 is the simplest backtracking process
                # TODO: implement the more complex mu backtrack from numerical recipes

                # update voltage with a closer value to the last value in the Jacobian direction
                mu_ *= correction_parameter
                Vm -= mu_ * dVm
                Va -= mu_ * dVa
                Vnew = Vm * np.exp(1j * Va)

                # compute the mismatch function f(x_new)
                dS = Vnew * np.conj(Ybus * Vnew - Ibus) - Sbus  # complex power mismatch
                f_new = np.r_[dS[pv].real, dS[pq].real, dS[pq].imag]  # concatenate to form the mismatch function
                f_new_prev = f + alpha * (f * J).dot(f_new - f)
                cond = (f_new < f_new_prev).any()

                l_iter += 1
                back_track_iterations += 1

            # update calculation variables
            V = Vnew
            f = f_new

            # check for convergence
            norm_f = np.linalg.norm(f, np.Inf)

            if norm_f < tol:
                converged = 1

    else:
        # there are no pq nor pv nodes
        norm_f = 0.0
        converged = True

    end = time.time()
    elapsed = end - start

    return V, converged, norm_f, Scalc, iter_, elapsed


def NR_LS2(Ybus, Sbus, V0, Ibus, pv, pq, tol, max_it=15, acceleration_parameter=0.05, error_registry=None):
    """
    Solves the power flow using a full Newton's method with backtrack correction.
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
    dS = Scalc - Sbus  # compute the mismatch
    f = np.r_[dS[pv].real, dS[pq].real, dS[pq].imag]

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
        dx = linear_solver(J, f)

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
        Vnew = Vm * np.exp(1.0j * Va)

        # compute the mismatch function f(x_new)
        dS = Vnew * np.conj(Ybus * Vnew - Ibus) - Sbus  # complex power mismatch
        f_new = np.r_[dS[pv].real, dS[pq].real, dS[pq].imag]  # concatenate to form the mismatch function
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
            Vnew = Vm * np.exp(1.0j * Va)

            # compute the mismatch function f(x_new)
            dS = Vnew * np.conj(Ybus * Vnew - Ibus) - Sbus  # complex power mismatch
            f_new = np.r_[dS[pv].real, dS[pq].real, dS[pq].imag]  # concatenate to form the mismatch function

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

    # print('iter_', iter_, '  -  back_track_counter', back_track_counter,
    #       '  -  back_track_iterations', back_track_iterations)

    return V, converged, norm_f, Scalc, iter_, elapsed


def IwamotoNR(Ybus, Sbus, V0, Ibus, pv, pq, tol, max_it=15, robust=False):
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
        robust: Boolean variable for the use of the Iwamoto optimal step factor.
    Returns:
        Voltage solution, converged?, error, calculated power injections

    @author: Ray Zimmerman (PSERC Cornell)
    @Author: Santiago Penate Vera
    """
    start = time.time()

    # initialize
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
    f = np.r_[mis[pv].real,
              mis[pq].real,
              mis[pq].imag]

    if (npq + npv) > 0:

        # check tolerance
        norm_f = np.linalg.norm(f, np.Inf)

        if norm_f < tol:
            converged = 1

        # do Newton iterations
        while not converged and iter_ < max_it:
            # update iteration counter
            iter_ += 1

            # evaluate Jacobian
            J = Jacobian(Ybus, V, Ibus, pq, pvpq)

            # compute update step
            dx = linear_solver(J, f)

            # reassign the solution vector
            if npv:
                dVa[pv] = dx[j1:j2]
            if npq:
                dVa[pq] = dx[j3:j4]
                dVm[pq] = dx[j5:j6]
            dV = dVm * np.exp(1j * dVa)  # voltage mismatch

            # update voltage
            if robust:
                # if dV contains zeros will crash the second Jacobian derivative
                if not (dV == 0.0).any():
                    # calculate the optimal multiplier for enhanced convergence
                    mu_ = mu(Ybus, Ibus, J, f, dV, dx, pvpq, pq)
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
            Scalc = V * np.conj(Ybus * V - Ibus)
            mis = Scalc - Sbus  # complex power mismatch
            f = np.r_[mis[pv].real, mis[pq].real, mis[pq].imag]  # concatenate again

            # check for convergence
            norm_f = np.linalg.norm(f, np.Inf)

            if norm_f < tol:
                converged = 1
    else:
        norm_f = 0
        converged = True

    end = time.time()
    elapsed = end - start

    return V, converged, norm_f, Scalc, iter_, elapsed


def LevenbergMarquardtPF(Ybus, Sbus, V0, Ibus, pv, pq, tol, max_it=50):
    """
    Solves the power flow problem by the Levenberg-Marquardt power flow algorithm.
    It is usually better than Newton-Raphson, but it takes an order of magnitude more time to converge.
    Args:
        Ybus: Admittance matrix
        Sbus: Array of nodal power injections
        V0: Array of nodal voltages (initial solution)
        Ibus: Array of nodal current injections
        pv: Array with the indices of the PV buses
        pq: Array with the indices of the PQ buses
        tol: Tolerance
        max_it: Maximum number of iterations
    Returns:
        Voltage solution, converged?, error, calculated power injections

    @Author: Santiago Peñate Vera
    """
    start = time.time()

    # initialize
    V = V0
    Va = np.angle(V)
    Vm = np.abs(V)
    dVa = np.zeros_like(Va)
    dVm = np.zeros_like(Vm)
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

    if (npq + npv) > 0:
        update_jacobian = True
        converged = False
        iter_ = 0
        nu = 2.0
        lbmda = 0
        f_prev = 1e9  # very large number
        nn = 2 * npq + npv
        ii = np.linspace(0, nn-1, nn)
        Idn = sparse((np.ones(nn), (ii, ii)), shape=(nn, nn))  # csr_matrix identity

        while not converged and iter_ < max_it:

            # evaluate Jacobian
            if update_jacobian:
                H = Jacobian(Ybus, V, Ibus, pq, pvpq)

            # evaluate the solution error F(x0)
            Scalc = V * np.conj(Ybus * V - Ibus)
            mis = Scalc - Sbus  # compute the mismatch
            dz = np.r_[mis[pv].real, mis[pq].real, mis[pq].imag]  # mismatch in the Jacobian order

            # system matrix
            # H1 = H^t
            H1 = H.transpose().tocsr()

            # H2 = H1·H
            H2 = H1.dot(H)

            # set first value of lmbda
            if iter_ == 0:
                lbmda = 1e-3 * H2.diagonal().max()

            # compute system matrix A = H^T·H - lambda·I
            A = H2 + lbmda * Idn

            # right hand side
            # H^t·dz
            rhs = H1.dot(dz)

            # Solve the increment
            dx = linear_solver(A, rhs)

            # objective function to minimize
            f = 0.5 * dz.dot(dz)

            # decision function
            val = dx.dot(lbmda * dx + rhs)
            if val > 0.0:
                rho = (f_prev - f) / (0.5 * val)
            else:
                rho = -1.0

            # lambda update
            if rho >= 0:
                update_jacobian = True
                lbmda *= max([1.0 / 3.0, 1 - (2 * rho - 1) ** 3])
                nu = 2.0

                # reassign the solution vector
                if npv:
                    dVa[pv] = dx[j1:j2]
                if npq:
                    dVa[pq] = dx[j3:j4]
                    dVm[pq] = dx[j5:j6]

                Vm -= dVm
                Va -= dVa
                # update Vm and Va again in case we wrapped around with a negative Vm
                V = Vm * np.exp(1j * Va)
                Vm = np.abs(V)
                Va = np.angle(V)
            else:
                update_jacobian = False
                lbmda *= nu
                nu *= 2.0

            # check convergence
            # normF = np.linalg.norm(dx, np.Inf)
            normF = np.linalg.norm(Sbus - V * np.conj(Ybus.dot(V)), np.Inf)
            converged = normF < tol
            f_prev = f

            # update iteration counter
            iter_ += 1
    else:
        normF = 0
        converged = True
        Scalc = V * np.conj(Ybus * V - Ibus)
        iter_ = 0

    end = time.time()
    elapsed = end - start

    return V, converged, normF, Scalc, iter_, elapsed


def Jacobian_I(Ybus, V, pq, pvpq):
    """
    Computes the system Jacobian matrix
    Args:
        Ybus: Admittance matrix
        V: Array of nodal voltages
        pq: Array with the indices of the PQ buses
        pvpq: Array with the indices of the PV and PQ buses

    Returns:
        The system Jacobian matrix in current equations
    """
    dI_dVm = Ybus * sp.diags(V / np.abs(V))
    dI_dVa = 1j * (Ybus * sp.diags(V))

    J11 = dI_dVa[np.array([pvpq]).T, pvpq].real
    J12 = dI_dVm[np.array([pvpq]).T, pq].real
    J21 = dI_dVa[np.array([pq]).T, pvpq].imag
    J22 = dI_dVm[np.array([pq]).T, pq].imag

    J = sp.vstack([sp.hstack([J11, J12]),
                   sp.hstack([J21, J22])], format="csr")

    return J


def condition_number(J):
    """
    Computes the condition number of a sparse matrix
    :param J: sparse matrix like the Jacobian
    :return:
    """
    norm_A = scipy.sparse.linalg.norm(J)
    norm_invA = scipy.sparse.linalg.norm(scipy.sparse.linalg.inv(J))
    cond = norm_A * norm_invA
    return cond


def NR_I_LS(Ybus, Sbus_sp, V0, Ibus_sp, pv, pq, tol, max_it=15):
    """
    Solves the power flow using a full Newton's method in current equations with current mismatch with line search
    Args:
        Ybus: Admittance matrix
        Sbus_sp: Array of nodal specified power injections
        V0: Array of nodal voltages (initial solution)
        Ibus_sp: Array of nodal specified current injections
        pv: Array with the indices of the PV buses
        pq: Array with the indices of the PQ buses
        tol: Tolerance
        max_it: Maximum number of iterations
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
    Va = np.angle(V)
    Vm = np.abs(V)
    dVa = np.zeros_like(Va)
    dVm = np.zeros_like(Vm)

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
    Icalc = Ybus * V - Ibus_sp
    dI = np.conj(Sbus_sp / V) - Icalc  # compute the mismatch
    F = np.r_[dI[pv].real, dI[pq].real, dI[pq].imag]
    normF = np.linalg.norm(F, np.Inf)  # check tolerance

    if normF < tol:
        converged = 1

    # do Newton iterations
    while not converged and iter_ < max_it:
        # update iteration counter
        iter_ += 1

        # evaluate Jacobian
        J = Jacobian_I(Ybus, V, pq, pvpq)

        # compute update step
        dx = linear_solver(J, F)

        # reassign the solution vector
        if npv:
            dVa[pv] = dx[j1:j2]
        if npq:
            dVa[pq] = dx[j3:j4]
            dVm[pq] = dx[j5:j6]

        # update voltage the Newton way (mu=1)
        mu_ = 1.0
        Vm += mu_ * dVm
        Va += mu_ * dVa
        Vnew = Vm * np.exp(1j * Va)

        # compute the mismatch function f(x_new)
        Icalc = Ybus * Vnew - Ibus_sp
        dI = np.conj(Sbus_sp / Vnew) - Icalc
        Fnew = np.r_[dI[pv].real, dI[pq].real, dI[pq].imag]

        normFprev = np.linalg.norm(F + alpha * (F * J).dot(Fnew - F), np.Inf)

        cond = normF < normFprev  # condition to back track (no improvement at all)

        if not cond:
            back_track_counter += 1

        l_iter = 0
        while not cond and l_iter < 10 and mu_ > 0.01:
            # line search back

            # to divide mu by 4 is the simplest backtracking process
            # TODO: implement the more complex mu backtrack from numerical recipes

            # update voltage with a closer value to the last value in the Jacobian direction
            mu_ *= 0.25
            Vm -= mu_ * dVm
            Va -= mu_ * dVa
            Vnew = Vm * np.exp(1j * Va)

            # compute the mismatch function f(x_new)
            Icalc = Ybus * Vnew - Ibus_sp
            dI = np.conj(Sbus_sp / Vnew) - Icalc
            Fnew = np.r_[dI[pv].real, dI[pq].real, dI[pq].imag]

            normFnew = np.linalg.norm(Fnew, np.Inf)
            normFnew_prev = np.linalg.norm(F + alpha * (F * J).dot(Fnew - F), np.Inf)

            cond = normFnew < normFnew_prev

            l_iter += 1
            back_track_iterations += 1

        # update calculation variables
        V = Vnew
        F = Fnew

        # check for convergence
        normF = np.linalg.norm(F, np.Inf)

        if normF < tol:
            converged = 1

    end = time.time()
    elapsed = end - start

    # print('iter_', iter_,
    #       '  -  back_track_counter', back_track_counter,
    #       '  -  back_track_iterations', back_track_iterations)

    Scalc = V * np.conj(Icalc)

    return V, converged, normF, Scalc, iter_, elapsed


def F(V, Ybus, S, I, pq, pv):
    """

    :param V:
    :param Ybus:
    :param S:
    :param I:
    :param pq:
    :param pv:
    :param pvpq:
    :return:
    """
    # compute the mismatch function f(x_new)
    dS = V * np.conj(Ybus * V - I) - S  # complex power mismatch
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
    :return:
    """
    n = len(S)
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
    return linear_solver(gx, g)


def ContinuousNR(Ybus, Sbus, V0, Ibus, pv, pq, tol, max_it=15):
    """
    Solves the power flow using a full Newton's method with the backtrack improvement algorithm
    Args:
        Ybus: Admittance matrix
        Sbus: Array of nodal power injections
        V0: Array of nodal voltages (initial solution)
        Ibus: Array of nodal current injections
        pv: Array with the indices of the PV buses
        pq: Array with the indices of the PQ buses
        tol: Tolerance
        max_it: Maximum number of iterations
        robust: Boolean variable for the use of the Iwamoto optimal step factor.
    Returns:
        Voltage solution, converged?, error, calculated power injections

    @author: Ray Zimmerman (PSERC Cornell)
    @Author: Santiago Penate Vera
    """

    start = time.time()

    # initialize
    converged = 0
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
    F = np.r_[mis[pv].real, mis[pq].real, mis[pq].imag]

    # check tolerance
    normF = np.linalg.norm(F, np.Inf)

    if normF < tol:
        converged = 1

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

        # reassign the solution vector
        if npv:
            Va[pv] = x[j1:j2]
        if npq:
            Va[pq] = x[j3:j4]
            Vm[pq] = x[j5:j6]
        V = Vm * np.exp(1j * Va)  # voltage mismatch

        # evaluate F(x)
        Scalc = V * np.conj(Ybus * V - Ibus)
        mis = Scalc - Sbus  # complex power mismatch
        F = np.r_[mis[pv].real, mis[pq].real, mis[pq].imag]  # concatenate again

        # check for convergence
        normF = np.linalg.norm(F, np.Inf)

        if normF > 0.01:
            dt = max(dt * 0.985, 0.75)
        else:
            dt = min(dt * 1.015, 0.75)

        print(dt)

        if normF < tol:
            converged = 1

    end = time.time()
    elapsed = end - start

    return V, converged, normF, Scalc