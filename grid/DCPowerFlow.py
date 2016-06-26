# Copyright (c) 1996-2015 PSERC. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

"""Solves a DC power flow.
"""

from numpy import copy, r_, matrix, hstack
from scipy.sparse.linalg import spsolve

def dcpf(B, Pbus, Va0, ref, pvpq):
    """
    Solves a DC power flow.

    Solves for the bus voltage angles at all but the reference bus, given the
    full system C{B} matrix and the vector of bus real power injections, the
    initial vector of bus voltage angles (in radians), and column vectors with
    the lists of bus indices for the swing bus, PV buses, and PQ buses,
    respectively. Returns a vector of bus voltage angles in radians.

    @see: L{rundcpf}, L{runpf}

    @author: Carlos E. Murillo-Sanchez (PSERC Cornell & Universidad
    Autonoma de Manizales)
    @author: Ray Zimmerman (PSERC Cornell)
    """
    #pvpq = matrix(r_[pv, pq])

    # initialize result vector
    Va = copy(Va0)

    pvpq_ = matrix(pvpq)

    # update angles for non-reference buses
    Va[pvpq_] = spsolve(B[pvpq_.T, pvpq_], (Pbus[pvpq_] - B[pvpq_.T, ref] * Va0[ref]).T)

    return Va, True, 0
