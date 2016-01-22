# Copyright (c) 1996-2015 PSERC. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

"""Solves the power flow using a full Newton's method.
"""

import sys

from numpy import array, angle, exp, linalg, r_, Inf, conj, diag, asmatrix, asarray

from scipy.sparse import issparse, csr_matrix as sparse, hstack, vstack

from scipy.sparse.linalg import spsolve


def dSbus_dV(Ybus, V):
    """
    Computes partial derivatives of power injection w.r.t. voltage.

    Returns two matrices containing partial derivatives of the complex bus
    power injections w.r.t voltage magnitude and voltage angle respectively
    (for all buses). If C{Ybus} is a sparse matrix, the return values will be
    also. The following explains the expressions used to form the matrices::

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
    """
    ib = range(len(V))

    if issparse(Ybus):
        Ibus = Ybus * V

        diagV = sparse((V, (ib, ib)))
        diagIbus = sparse((Ibus, (ib, ib)))
        diagVnorm = sparse((V / abs(V), (ib, ib)))
    else:
        Ibus = Ybus * asmatrix(V).T

        diagV = asmatrix(diag(V))
        diagIbus = asmatrix(diag( asarray(Ibus).flatten()))
        diagVnorm = asmatrix(diag(V / abs(V)))

    dS_dVm = diagV * conj(Ybus * diagVnorm) + conj(diagIbus) * diagVnorm
    dS_dVa = 1j * diagV * conj(diagIbus - Ybus * diagV)

    return dS_dVm, dS_dVa

def newtonpf(Ybus, Sbus, V0, pv, pq, tol, max_it, verbose=False):
    """
    Solves the power flow using a full Newton's method.

    Solves for bus voltages given the full system admittance matrix (for
    all buses), the complex bus power injection vector (for all buses),
    the initial vector of complex bus voltages, and column vectors with
    the lists of bus indices for the swing bus, PV buses, and PQ buses,
    respectively. The bus voltage vector contains the set point for
    generator (including ref bus) buses, and the reference angle of the
    swing bus, as well as an initial guess for remaining magnitudes and
    angles. C{ppopt} is a PYPOWER options vector which can be used to
    set the termination tolerance, maximum number of iterations, and
    output options (see L{ppoption} for details). Uses default options if
    this parameter is not given. Returns the final complex voltages, a
    flag which indicates whether it converged or not, and the number of
    iterations performed.

    Args:
        Ybus: Admittance matrix
        Sbus: Array of nodal power injections
        V0: Array of nodal voltages (initial solution)
        ref: Array with the indices of the slack buses
        pv: Array with the indices of the PV buses
        pq: Array with the indices of the PQ buses
        tol: Tolerance
        max_it: Maximum number of iterations
        verbose: Boolean variable for the verbose mode activation
    Returns:

    @see: L{runpf}

    @author: Ray Zimmerman (PSERC Cornell)
    """

    # initialize
    converged = 0
    i = 0
    V = V0
    Va = angle(V)
    Vm = abs(V)

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
    mis = V * conj(Ybus * V) - Sbus  # compute the mismatch
    F = r_[mis[pv].real,
           mis[pq].real,
           mis[pq].imag]

    # check tolerance
    normF = linalg.norm(F, Inf)

    if verbose > 1:
        sys.stdout.write('\n it    max P & Q mismatch (p.u.)')
        sys.stdout.write('\n----  ---------------------------')
        sys.stdout.write('\n%3d        %10.3e' % (i, normF))

    if normF < tol:
        converged = 1
        if verbose > 1:
            sys.stdout.write('\nConverged!\n')

    # do Newton iterations
    while not converged and i < max_it:
        # update iteration counter
        i += 1

        # evaluate Jacobian
        dS_dVm, dS_dVa = dSbus_dV(Ybus, V)  # compute the derivatives

        J11 = dS_dVa[array([pvpq]).T, pvpq].real
        J12 = dS_dVm[array([pvpq]).T, pq].real
        J21 = dS_dVa[array([pq]).T, pvpq].imag
        J22 = dS_dVm[array([pq]).T, pq].imag

        J = vstack([
                hstack([J11, J12]),
                hstack([J21, J22])
            ], format="csr")

        # compute update step
        dx = -1 * spsolve(J, F)

        # update voltage
        if npv:
            Va[pv] += dx[j1:j2]
        if npq:
            Va[pq] += dx[j3:j4]
            Vm[pq] += dx[j5:j6]
        V = Vm * exp(1j * Va)
        Vm = abs(V)  # update Vm and Va again in case
        Va = angle(V)  # we wrapped around with a negative Vm

        # evaluate F(x)
        mis = V * conj(Ybus * V) - Sbus
        F = r_[mis[pv].real,
               mis[pq].real,
               mis[pq].imag]  # concatenate again

        # check for convergence
        normF = linalg.norm(F, Inf)
        if verbose > 1:
            sys.stdout.write('\n%3d        %10.3e' % (i, normF))

        if normF < tol:
            converged = 1
            if verbose:
                sys.stdout.write("\nNewton's method power flow converged in "
                                 "%d iterations.\n" % i)

    if verbose:
        if not converged:
            sys.stdout.write("\nNewton's method power did not converge in %d "
                             "iterations.\n" % i)

    return V, converged, normF
