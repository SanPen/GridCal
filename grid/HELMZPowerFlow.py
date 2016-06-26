# -*- coding: utf-8 -*-

import numpy as np
np.set_printoptions(precision=6, suppress=True, linewidth=320)
from numpy import where, zeros, ones, mod, conj, array, dot, complex128
from numpy import poly1d, r_, eye, hstack, linalg, Inf

from scipy.linalg import solve

from scipy.sparse.linalg import factorized, spsolve, inv
from scipy.sparse import issparse, csr_matrix as sparse

# from numba import jit

# Set the complex precision to use
complex_type = complex128




# @jit(cache=True)
def helmz(admittances, slackIndices, maxcoefficientCount, powerInjections, voltageSetPoints, types,
          eps=1e-3, usePade=True):
    """

    TO BE DONE
    """

    best_V = voltageSetPoints
    converged = False
    normF = 10

    return best_V, converged, normF


