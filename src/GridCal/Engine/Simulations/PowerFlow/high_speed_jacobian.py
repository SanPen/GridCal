# Copyright 1996-2015 PSERC. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

# Copyright (c) 2016-2020 by University of Kassel and Fraunhofer Institute for for Energy Economics
# and Energy System Technology (IEE) Kassel and individual contributors (see AUTHORS file for details).
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification, are permitted
# provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this list of conditions
# and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice, this list of
# conditions and the following disclaimer in the documentation and/or other materials provided
# with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its contributors may be used to
# endorse or promote products derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND
# FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY
# WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


from numba import jit
from scipy.sparse import issparse
from numpy import conj, abs
from numpy import complex128, float64, int32
from numpy.core.multiarray import zeros, empty, array
from scipy.sparse import csr_matrix as sparse, vstack, hstack


def dSbus_dV(Ybus, V):
    """
    Computes partial derivatives of power injection w.r.t. voltage.
    """

    Ibus = Ybus * V
    ib = range(len(V))
    diagV = sparse((V, (ib, ib)))
    diagIbus = sparse((Ibus, (ib, ib)))
    diagVnorm = sparse((V / abs(V), (ib, ib)))
    dS_dVm = diagV * conj(Ybus * diagVnorm) + conj(diagIbus) * diagVnorm
    dS_dVa = 1j * diagV * conj(diagIbus - Ybus * diagV)
    return dS_dVm, dS_dVa


# @jit(Tuple((c16[:], c16[:]))(c16[:], i4[:], i4[:], c16[:], c16[:]), nopython=True, cache=False)
@jit(nopython=True, cache=False)
def dSbus_dV_numba_sparse(Yx, Yp, Yj, V, Vnorm, Ibus):  # pragma: no cover
    """
    Computes partial derivatives of power injection w.r.t. voltage.

    Calculates faster with numba and sparse matrices.

    Input: Ybus in CSR sparse form (Yx = data, Yp = indptr, Yj = indices), V and Vnorm (= V / abs(V))

    OUTPUT: data from CSR form of dS_dVm, dS_dVa
    (index pointer and indices are the same as the ones from Ybus)

    Translation of: dS_dVm = dS_dVm = diagV * conj(Ybus * diagVnorm) + conj(diagIbus) * diagVnorm
                             dS_dVa = 1j * diagV * conj(diagIbus - Ybus * diagV)
    """

    # transform input

    # init buffer vector
    buffer = zeros(len(V), dtype=complex128)
    dS_dVm = Yx.copy()
    dS_dVa = Yx.copy()

    # iterate through sparse matrix
    for r in range(len(Yp) - 1):
        for k in range(Yp[r], Yp[r + 1]):
            # Ibus = Ybus * V
            buffer[r] += Yx[k] * V[Yj[k]]

            # Ybus * diag(Vnorm)
            dS_dVm[k] *= Vnorm[Yj[k]]

            # Ybus * diag(V)
            dS_dVa[k] *= V[Yj[k]]

        Ibus[r] += buffer[r]

        # conj(diagIbus) * diagVnorm
        buffer[r] = conj(buffer[r]) * Vnorm[r]

    for r in range(len(Yp) - 1):
        for k in range(Yp[r], Yp[r + 1]):
            # diag(V) * conj(Ybus * diagVnorm)
            dS_dVm[k] = conj(dS_dVm[k]) * V[r]

            if r == Yj[k]:
                # diagonal elements
                dS_dVa[k] = -Ibus[r] + dS_dVa[k]
                dS_dVm[k] += buffer[r]

            # 1j * diagV * conj(diagIbus - Ybus * diagV)
            dS_dVa[k] = conj(-dS_dVa[k]) * (1j * V[r])

    return dS_dVm, dS_dVa


def dSbus_dV_with_numba(Ybus, V, I):
    """
    Calls functions to calculate dS/dV depending on whether Ybus is sparse or not
    """

    # I is substracted from Y*V,
    # therefore it must be negative for numba version of dSbus_dV if it is not zeros anyways
    # calculates sparse data
    dS_dVm, dS_dVa = dSbus_dV_numba_sparse(Ybus.data, Ybus.indptr, Ybus.indices, V, V / abs(V), I)
    # generate sparse CSR matrices with computed data and return them
    return sparse((dS_dVm, Ybus.indices, Ybus.indptr)), sparse((dS_dVa, Ybus.indices, Ybus.indptr))


# @jit(i8(c16[:], c16[:], i4[:], i4[:], i8[:], i8[:], f8[:], i8[:], i8[:]), nopython=True, cache=False)
@jit(nopython=True, cache=False)
def create_J(dVm_x, dVa_x, Yp, Yj, pvpq_lookup, pvpq, pq, Jx, Jj, Jp):  # pragma: no cover
    """
    Calculates Jacobian in CSR format.
    :param dVm_x:
    :param dVa_x:
    :param Yp:
    :param Yj:
    :param pvpq_lookup:
    :param pvpq:
    :param pq:
    :param Jx:
    :param Jj:
    :param Jp:
    :return:
    """
    """
    

    Input: dS_dVa and dS_dVm in CSR sparse form (Yx = data, Yp = indptr, Yj = indices), pvpq, pq from pypower

    ** The values Yp and Yj are the internal structures of Y in CSC format!

    OUTPUT:  data from CSR form of Jacobian (Jx, Jj, Jp) and number of non zeros (nnz)

    @author: Florian Schaefer

    Calculate Jacobian entries

    J11 = dS_dVa[array([pvpq]).T, pvpq].real
    J12 = dS_dVm[array([pvpq]).T, pq].real
    J21 = dS_dVa[array([pq]).T, pvpq].imag
    J22 = dS_dVm[array([pq]).T, pq].imag

    Explanation of code:
    To understand the concept the CSR storage method should be known. See:
    https://de.wikipedia.org/wiki/Compressed_Row_Storage

    J has the shape
    | J11 | J12 |               | (pvpq, pvpq) | (pvpq, pq) |
    | --------- | = dimensions: | ------------------------- |
    | J21 | J22 |               |  (pq, pvpq)  |  (pq, pq)  |

    We first iterate the rows of J11 and J12 (for r in range lpvpq) and add the entries which are stored in dS_dV
    Then we iterate the rows of J21 and J22 (for r in range lpq) and add the entries from dS_dV

    Note: The row and column pointer of of dVm and dVa are the same as the one from Ybus
    """
    # Jacobi Matrix in sparse form
    # Jp, Jx, Jj equal J like:
    # J = zeros(shape=(ndim, ndim), dtype=float64)

    # get length of vectors
    npvpq = len(pvpq)
    npq = len(pq)
    npv = npvpq - npq

    # nonzeros in J
    nnz = 0

    # iterate rows of J
    # first iterate pvpq (J11 and J12)
    for r in range(npvpq):
        # nnzStar is necessary to calculate nonzeros per row
        nnzStart = nnz
        # iterate columns of J11 = dS_dVa.real at positions in pvpq
        # check entries in row pvpq[r] of dS_dV
        for c in range(Yp[pvpq[r]], Yp[pvpq[r] + 1]):
            # check if column Yj is in pvpq
            cc = pvpq_lookup[Yj[c]]
            # entries for J11 and J12
            if pvpq[cc] == Yj[c]:
                # entry found
                # equals entry of J11: J[r,cc] = dS_dVa[c].real
                Jx[nnz] = dVa_x[c].real
                Jj[nnz] = cc
                nnz += 1
                # if entry is found in the "pq part" of pvpq = add entry of J12
                if cc >= npv:
                    Jx[nnz] = dVm_x[c].real
                    Jj[nnz] = cc + npq
                    nnz += 1

        # Jp: number of nonzeros per row = nnz - nnzStart (nnz at begging of loop - nnz at end of loop)
        Jp[r + 1] = nnz - nnzStart + Jp[r]

    # second: iterate pq (J21 and J22)
    for r in range(npq):
        nnzStart = nnz
        # iterate columns of J21 = dS_dVa.imag at positions in pvpq
        for c in range(Yp[pq[r]], Yp[pq[r] + 1]):
            cc = pvpq_lookup[Yj[c]]
            if pvpq[cc] == Yj[c]:
                # entry found
                # equals entry of J21: J[r + lpvpq, cc] = dS_dVa[c].imag
                Jx[nnz] = dVa_x[c].imag
                Jj[nnz] = cc
                nnz += 1

                if cc >= npv:
                    # if entry is found in the "pq part" of pvpq = Add entry of J22
                    Jx[nnz] = dVm_x[c].imag
                    Jj[nnz] = cc + npq
                    nnz += 1

        # Jp: number of nonzeros per row = nnz - nnzStart (nnz at begging of loop - nnz at end of loop)
        Jp[r + npvpq + 1] = nnz - nnzStart + Jp[r + npvpq]


# @jit(i8(c16[:], c16[:], i4[:], i4[:], i8[:], i8[:], f8[:], i8[:], i8[:]), nopython=True, cache=True)
@jit(nopython=True, cache=False)
def create_J2(dS_dVm, dS_dVa, Yp, Yj, pvpq_lookup, pvpq, pq, Jx, Jj, Jp):  # pragma: no cover
    """
        Calculates Jacobian faster with numba and sparse matrices. This version is similar to create_J except that
        if pvpq = pq (when no pv bus is available) some if statements are obsolete and J11 = J12 and J21 = J22

        Input: dS_dVa and dS_dVm in CSR sparse form (Yx = data, Yp = indptr, Yj = indices), pvpq, pq from pypower

        OUTPUT: data from CSR form of Jacobian (Jx, Jj, Jp) and number of non zeros (nnz)

        @author: Florian Schaefer
        @date: 30.08.2016

        see comments in create_J
    """
    # Jacobi Matrix in sparse form
    # Jp, Jx, Jj equal J like:
    # J = zeros(shape=(ndim, ndim), dtype=float64)

    # get info of vector
    lpvpq = len(pvpq)

    # nonzeros in J
    nnz = 0

    # iterate rows of J
    # first iterate pvpq (J11 and J12)
    for r in range(lpvpq):
        # nnzStart is necessary to calculate nonzeros per row
        nnzStart = nnz
        # iterate columns of J11 = dS_dVa.real at positions in pvpq
        # iterate columns of J12 = dS_dVm.real at positions in pq (=pvpq)
        for c in range(Yp[pvpq[r]], Yp[pvpq[r] + 1]):
            cc = pvpq_lookup[Yj[c]]

            '''
            pvpq_lookup = zeros(Ybus.n_nonzero + 1)        
            for i in range(npvpq): 
                pvpq_lookup[pvpq[i]] = i;
            '''

            if pvpq[cc] == Yj[c]:
                # entry found J11
                # J[r,cc] = dS_dVa[c].real
                Jx[nnz] = dS_dVa[c].real
                Jj[nnz] = cc
                nnz += 1
                # also entry in J12
                Jx[nnz] = dS_dVm[c].real
                Jj[nnz] = cc + lpvpq
                nnz += 1
        # Jp: number of nonzeros per row = nnz - nnzStart (nnz at begging of loop - nnz at end of loop)
        Jp[r + 1] = nnz - nnzStart + Jp[r]
    # second: iterate pq (J21 and J22)
    for r in range(lpvpq):
        nnzStart = nnz
        # iterate columns of J21 = dS_dVa.imag at positions in pvpq
        # iterate columns of J22 = dS_dVm.imag at positions in pq (=pvpq)
        for c in range(Yp[pvpq[r]], Yp[pvpq[r] + 1]):
            cc = pvpq_lookup[Yj[c]]
            if pvpq[cc] == Yj[c]:
                # entry found J21
                # J[r + lpvpq, cc] = dS_dVa[c].imag
                Jx[nnz] = dS_dVa[c].imag
                Jj[nnz] = cc
                nnz += 1
                # also entry in J22
                Jx[nnz] = dS_dVm[c].imag
                Jj[nnz] = cc + lpvpq
                nnz += 1
        # Jp: number of nonzeros per row = nnz - nnzStart (nnz at begging of loop - nnz at end of loop)
        Jp[r + lpvpq + 1] = nnz - nnzStart + Jp[r + lpvpq]


def _create_J_with_numba(Ybus, V, pvpq, pq, pvpq_lookup, npv, npq):
    """

    :param Ybus:
    :param V:
    :param pvpq:
    :param pq:
    :param createJ:
    :param pvpq_lookup:
    :param npv:
    :param npq:
    :return:
    """
    Ibus = zeros(len(V), dtype=complex128)

    # create Jacobian from fast calc of dS_dV
    dS_dVm, dS_dVa = dSbus_dV_numba_sparse(Ybus.data, Ybus.indptr, Ybus.indices, V, V / abs(V), Ibus)

    # data in J, space pre-allocated is bigger than actual Jx -> will be reduced later on
    Jx = empty(len(dS_dVm) * 4, dtype=float64)
    # row pointer, dimension = pvpq.shape[0] + pq.shape[0] + 1
    Jp = zeros(pvpq.shape[0] + pq.shape[0] + 1, dtype=int32)
    # indices, same with the pre-allocated space (see Jx)
    Jj = empty(len(dS_dVm) * 4, dtype=int32)

    # fill Jx, Jj and Jp
    # createJ(dS_dVm, dS_dVa, Ybus.indptr, Ybus.indices, pvpq_lookup, pvpq, pq, Jx, Jj, Jp)
    if len(pvpq) == len(pq):
        create_J2(dS_dVm, dS_dVa, Ybus.indptr, Ybus.indices, pvpq_lookup, pvpq, pq, Jx, Jj, Jp)
    else:
        create_J(dS_dVm, dS_dVa, Ybus.indptr, Ybus.indices, pvpq_lookup, pvpq, pq, Jx, Jj, Jp)

    # resize before generating the scipy sparse matrix
    Jx.resize(Jp[-1], refcheck=False)
    Jj.resize(Jp[-1], refcheck=False)

    # generate scipy sparse matrix
    dimJ = npv + npq + npq
    J = sparse((Jx, Jj, Jp), shape=(dimJ, dimJ))

    return J


def _create_J_without_numba(Ybus, V, pvpq, pq):
    """
    Standard matpower-like implementation
    :param Ybus:
    :param V:
    :param pvpq:
    :param pq:
    :return:
    """
    dS_dVm, dS_dVa = dSbus_dV(Ybus, V)

    # evaluate Jacobian
    J11 = dS_dVa[array([pvpq]).T, pvpq].real
    J12 = dS_dVm[array([pvpq]).T, pq].real
    if len(pq) > 0:
        J21 = dS_dVa[array([pq]).T, pvpq].imag
        J22 = dS_dVm[array([pq]).T, pq].imag
        J = vstack([
                    hstack([J11, J12]),
                    hstack([J21, J22])
                    ], format="csr")
    else:
        J = vstack([
                    hstack([J11, J12])
                    ], format="csr")
    return J


def get_fastest_jacobian_function(pvpq, pq):
    """
    Determine the fastest jacobian function given the amount of PV nodes
    :param pvpq:
    :param pq:
    :return:
    """
    if len(pvpq) == len(pq):
        return create_J2
    else:
        return create_J
