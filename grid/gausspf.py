# Copyright (c) 1996-2015 PSERC. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

"""
Solves the power flow using a Gauss-Seidel method.
"""

import sys

from numpy import linalg, conj, r_, Inf, asscalar


def gausspf(Ybus, Sbus, V0, ref, pv, pq, tol=1e-3, max_it=50, verbose=False):
    """Solves the power flow using a Gauss-Seidel method.

    Solves for bus voltages given the full system admittance matrix (for
    all buses), the complex bus power injection vector (for all buses),
    the initial vector of complex bus voltages, and column vectors with
    the lists of bus indices for the swing bus, PV buses, and PQ buses,
    respectively. The bus voltage vector contains the set point for
    generator (including ref bus) buses, and the reference angle of the
    swing bus, as well as an initial guess for remaining magnitudes and
    angles. C{ppopt} is a PYPOWER options vector which can be used to
    set the termination tolerance, maximum number of iterations, and
    output options (see C{ppoption} for details). Uses default options
    if this parameter is not given. Returns the final complex voltages,
    a flag which indicates whether it converged or not, and the number
    of iterations performed.

    @see: L{runpf}

    @author: Ray Zimmerman (PSERC Cornell)
    @author: Alberto Borghetti (University of Bologna, Italy)
    """

    # initialize
    converged = 0
    i = 0
    V = V0.copy()
    #Va = angle(V)
    Vm = abs(V)

    # set up indexing for updating V
    npv = len(pv)
    npq = len(pq)
    pvpq = r_[pv, pq]

    # evaluate F(x0)
    mis = V * conj(Ybus * V) - Sbus
    F = r_[  mis[pvpq].real,
             mis[pq].imag   ]

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

    # do Gauss-Seidel iterations
    while not converged and i < max_it:
        # update iteration counter
        i += 1

        # update voltage
        # at PQ buses
        for k in pq[list(range(npq))]:
            incV = (conj(Sbus[k] / V[k]) - Ybus[k, :] * V) / Ybus[k, k]
            V[k] += asscalar(incV)

        # at PV buses
        if npv:
            # for k in pv[list(range(npv))]:
            for k in pv:
                Q = (V[k] * conj(Ybus[k,:] * V)).imag  # reactive power
                Sbus[k] = Sbus[k].real + 1j * asscalar(Q)
                incV = (conj(Sbus[k] / V[k]) - Ybus[k, :] * V) / Ybus[k, k]
                V[k] += asscalar(incV)
#               V[k] = Vm[k] * V[k] / abs(V[k])
            V[pv] = Vm[pv] * V[pv] / abs(V[pv])

        # evaluate F(x)
        mis = V * conj(Ybus * V) - Sbus
        F = r_[mis[pv].real,
               mis[pq].real,
               mis[pq].imag]

        # check for convergence
        normF = linalg.norm(F, Inf)  # same as max(abs(F))
        if verbose > 1:
            sys.stdout.write('\n%3d        %10.3e' % (i, normF))
        if normF < tol:
            converged = 1
            if verbose:
                sys.stdout.write('\nGauss-Seidel power flow converged in '
                                 '%d iterations.\n' % i)

    if verbose:
        if not converged:
            sys.stdout.write('Gauss-Seidel power did not converge in %d '
                             'iterations.' % i)

    return V, converged, i
