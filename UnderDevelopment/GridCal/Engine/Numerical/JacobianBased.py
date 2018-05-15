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
from scipy.sparse import issparse, csr_matrix as sparse, hstack, vstack
from scipy.sparse.linalg import spsolve, splu
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

    if issparse(Ybus):
        Ibus = Ybus * V - I

        diagV = sparse((V, (ib, ib)))
        diagIbus = sparse((Ibus, (ib, ib)))
        diagVnorm = sparse((V / abs(V), (ib, ib)))
    else:
        Ibus = Ybus * asmatrix(V).T - I

        diagV = asmatrix(diag(V))
        diagIbus = asmatrix(diag(asarray(Ibus).flatten()))
        diagVnorm = asmatrix(diag(V / abs(V)))

    dS_dVm = diagV * conj(Ybus * diagVnorm) + conj(diagIbus) * diagVnorm
    dS_dVa = 1j * diagV * conj(diagIbus - Ybus * diagV)

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

    J = vstack([
        hstack([J11, J12]),
        hstack([J21, J22])
    ], format="csr")

    return J


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
    mis = Scalc - Sbus  # compute the mismatch
    F = r_[mis[pv].real,
           mis[pq].real,
           mis[pq].imag]

    # check tolerance
    normF = linalg.norm(F, Inf)

    if normF < tol:
        converged = 1

    # do Newton iterations
    while not converged and iter_ < max_it:
        # update iteration counter
        iter_ += 1

        # evaluate Jacobian
        J = Jacobian(Ybus, V, Ibus, pq, pvpq)

        # compute update step
        dx = spsolve(J, F)

        # reassign the solution vector
        if npv:
            dVa[pv] = dx[j1:j2]
        if npq:
            dVa[pq] = dx[j3:j4]
            dVm[pq] = dx[j5:j6]
        dV = dVm * exp(1j * dVa)  # voltage mismatch

        # update voltage
        if robust:
            if not (dV == 0.0).any():  # if dV contains zeros will crash the second Jacobian drivative
                mu_ = mu(Ybus, Ibus, J, F, dV, dx, pvpq, pq)  # calculate the optimal multiplier for enhanced convergence
            else:
                mu_ = 1.0
        else:
            mu_ = 1.0

        Vm -= mu_ * dVm
        Va -= mu_ * dVa

        V = Vm * exp(1j * Va)

        Vm = abs(V)  # update Vm and Va again in case
        Va = angle(V)  # we wrapped around with a negative Vm

        # evaluate F(x)
        Scalc = V * conj(Ybus * V - Ibus)
        mis = Scalc - Sbus  # complex power mismatch
        F = r_[mis[pv].real, mis[pq].real, mis[pq].imag]  # concatenate again

        # check for convergence
        normF = linalg.norm(F, Inf)

        if normF < tol:
            converged = 1

    end = time.time()
    elapsed = end - start

    return V, converged, normF, Scalc, iter_, elapsed


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
    Va = angle(V)
    Vm = np.abs(V)
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
        Scalc = V * conj(Ybus * V - Ibus)
        mis = Scalc - Sbus  # compute the mismatch
        dz = r_[mis[pv].real, mis[pq].real, mis[pq].imag]  # mismatch in the Jacobian order

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
        dx = spsolve(A, rhs)

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
            V = Vm * exp(1j * Va)
            Vm = np.abs(V)
            Va = angle(V)
        else:
            update_jacobian = False
            lbmda *= nu
            nu *= 2.0

        # check convergence
        # normF = np.linalg.norm(dx, np.Inf)
        normF = np.linalg.norm(Sbus - V * conj(Ybus.dot(V)), np.Inf)
        converged = normF < tol
        f_prev = f

        # update iteration counter
        iter_ += 1

    end = time.time()
    elapsed = end - start

    return V, converged, normF, Scalc, iter_, elapsed
