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
from numpy import conj, abs
from numpy import complex128, float64, int32
from numpy.core.multiarray import zeros, empty
from scipy.sparse import csr_matrix
import GridCal.Engine.Simulations.PowerFlow.derivatives as deriv


def dSbus_dV(Ybus, V):
    """
    Computes partial derivatives of power injection w.r.t. voltage.
    """

    Ibus = Ybus * V
    ib = range(len(V))
    diagV = csr_matrix((V, (ib, ib)))
    diagIbus = csr_matrix((Ibus, (ib, ib)))
    diagVnorm = csr_matrix((V / abs(V), (ib, ib)))
    dS_dVm = diagV * conj(Ybus * diagVnorm) + conj(diagIbus) * diagVnorm
    dS_dVa = 1j * diagV * conj(diagIbus - Ybus * diagV)
    return dS_dVm, dS_dVa


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
    
            pvpq      pq
    pvpq | dP_dVa | dP_dVm | 
      pq | dQ_dVa | dQ_dVm | 
    
          pvpq   pq
    pvpq | J11 | J12 | 
      pq | J21 | J22 | 

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
    # first iterate pvpq (J11 and J12) (dP_dVa, dP_dVm)
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

    # second: iterate pq (J21 and J22) (dQ_dVa, dQ_dVm)
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
def create_J_no_pv(dS_dVm, dS_dVa, Yp, Yj, pvpq_lookup, pvpq, Jx, Jj, Jp):  # pragma: no cover
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


def AC_jacobian(Ybus, V, pvpq, pq, pvpq_lookup, npv, npq):
    """
    Create the AC Jacobian function with no embedded controls
    :param Ybus: Ybus matrix in CSC format
    :param V: Voltages vector
    :param pvpq: array of pv|pq bus indices
    :param pq: array of pq indices
    :param pvpq_lookup: array of pv|pq lookup indices
    :param npv: number of pv buses
    :param npq: number of pq buses
    :return: Jacobian Matrix in CSR format
    """
    Ibus = zeros(len(V), dtype=complex128)

    # create Jacobian from fast calc of dS_dV
    dS_dVm, dS_dVa = deriv.dSbus_dV_numba_sparse_csr(Ybus.data, Ybus.indptr, Ybus.indices, V, V / abs(V), Ibus)

    # data in J, space pre-allocated is bigger than actual Jx -> will be reduced later on
    Jx = empty(len(dS_dVm) * 4, dtype=float64)

    # row pointer, dimension = pvpq.shape[0] + pq.shape[0] + 1
    Jp = zeros(pvpq.shape[0] + pq.shape[0] + 1, dtype=int32)

    # indices, same with the pre-allocated space (see Jx)
    Jj = empty(len(dS_dVm) * 4, dtype=int32)

    # fill Jx, Jj and Jp in CSR order
    if len(pvpq) == len(pq):
        create_J_no_pv(dS_dVm, dS_dVa, Ybus.indptr, Ybus.indices, pvpq_lookup, pvpq, Jx, Jj, Jp)
    else:
        create_J(dS_dVm, dS_dVa, Ybus.indptr, Ybus.indices, pvpq_lookup, pvpq, pq, Jx, Jj, Jp)

    # resize before generating the scipy sparse matrix
    Jx.resize(Jp[-1], refcheck=False)
    Jj.resize(Jp[-1], refcheck=False)

    # generate scipy sparse matrix
    nj = npv + npq + npq
    return csr_matrix((Jx, Jj, Jp), shape=(nj, nj))
