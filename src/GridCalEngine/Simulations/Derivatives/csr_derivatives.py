# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

import numpy as np
from numba import njit, complex128, int32, float64
from typing import Tuple
import scipy.sparse as sp
from scipy.sparse import lil_matrix, diags, csc_matrix, csr_matrix
from GridCalEngine.basic_structures import CxVec, IntVec
from GridCalEngine.Utils.Sparse.csc2 import CSC, CxCSC


@njit(cache=True)
def dSbus_dV_numba_sparse_csr(Yx: CxVec, Yp: IntVec, Yj: IntVec, V: CxVec, E: CxVec) -> Tuple[
    CxVec, CxVec]:  # pragma: no cover
    """
    partial derivatives of power injection w.r.t. voltage.
    :param Yx: Ybus data in CSC format
    :param Yp: Ybus indptr in CSC format
    :param Yj: Ybus indices in CSC format
    :param V: Voltage vector
    :param E: Normalized voltage vector
    :return: dS_dVm, dS_dVa data in CSR format, index pointer and indices are the same as the ones from Ybus
    """

    # init buffer vector
    n = len(V)
    buffer = np.zeros(n, dtype=complex128)
    Ibus = np.zeros(n, dtype=complex128)

    # buffer = np.zeros(n, dtype=complex)
    # Ibus = np.zeros(n, dtype=complex)

    dS_dVm = Yx.copy()
    dS_dVa = Yx.copy()

    # iterate through sparse matrix
    for r in range(len(Yp) - 1):
        for k in range(Yp[r], Yp[r + 1]):
            # Ibus = Ybus * V
            buffer[r] += Yx[k] * V[Yj[k]]

            # Ybus * diag(Vnorm)
            dS_dVm[k] *= E[Yj[k]]

            # Ybus * diag(V)
            dS_dVa[k] *= V[Yj[k]]

        Ibus[r] += buffer[r]

        # conj(diagIbus) * diagVnorm
        buffer[r] = np.conj(buffer[r]) * E[r]

    for r in range(len(Yp) - 1):
        for k in range(Yp[r], Yp[r + 1]):
            # diag(V) * conj(Ybus * diagVnorm)
            dS_dVm[k] = np.conj(dS_dVm[k]) * V[r]

            if r == Yj[k]:
                # diagonal elements
                dS_dVa[k] = -Ibus[r] + dS_dVa[k]
                dS_dVm[k] += buffer[r]

            # 1j * diagV * conj(diagIbus - Ybus * diagV)
            dS_dVa[k] = np.conj(-dS_dVa[k]) * (1j * V[r])

    return dS_dVm, dS_dVa


def dSbus_dV_csr(Ybus: csc_matrix, V: CxVec) -> Tuple[csr_matrix, csr_matrix]:
    """
    Calls functions to calculate dS/dV depending on whether Ybus is sparse or not
    :param Ybus: Ybus in CSC
    :param V: Voltages vector
    :return: dS_dVm, dS_dVa in CSR format
    """

    # I is subtracted from Y*V,
    # therefore it must be negative for numba version of dSbus_dV if it is not zeros anyways
    # calculates sparse data
    dS_dVm, dS_dVa = dSbus_dV_numba_sparse_csr(Ybus.data, Ybus.indptr, Ybus.indices, V, V / np.abs(V))

    # generate sparse CSR matrices with computed data and return them
    return (sp.csr_matrix((dS_dVm, Ybus.indices, Ybus.indptr)),
            sp.csr_matrix((dS_dVa, Ybus.indices, Ybus.indptr)))


