# Copyright 1996-2015 PSERC. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.
from typing import Any

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
from numpy import float64, int32
import numpy as np
from scipy.sparse import csr_matrix, csc_matrix
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.derivatives import (dSbus_dV_numba_sparse_csc,
                                                                              dSbus_dV_numba_sparse_csr)
from GridCalEngine.basic_structures import Vec, IntVec, CxVec
from GridCalEngine.Utils.Sparse.csc2 import create_lookup, CSC


@jit(nopython=True, cache=True)
def create_J_csr(nbus, dS_dVm_x, dS_dVa_x, Yp, Yj, pvpq, pq, Jx, Jj, Jp):  # pragma: no cover
    """
    Calculates Jacobian in CSR format.
    :param nbus:
    :param dS_dVm_x:
    :param dS_dVa_x:
    :param Yp:
    :param Yj:
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
    pvpq_lookup = create_lookup(nbus, pvpq)

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
                Jx[nnz] = dS_dVa_x[c].real
                Jj[nnz] = cc
                nnz += 1

                # if entry is found in the "pq part" of pvpq = add entry of J12
                if cc >= npv:
                    Jx[nnz] = dS_dVm_x[c].real
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
                Jx[nnz] = dS_dVa_x[c].imag
                Jj[nnz] = cc
                nnz += 1

                if cc >= npv:
                    # if entry is found in the "pq part" of pvpq = Add entry of J22
                    Jx[nnz] = dS_dVm_x[c].imag
                    Jj[nnz] = cc + npq
                    nnz += 1

        # Jp: number of nonzeros per row = nnz - nnzStart (nnz at begging of loop - nnz at end of loop)
        Jp[r + npvpq + 1] = nnz - nnzStart + Jp[r + npvpq]


def AC_jacobian_csr(Ybus: csr_matrix, V: CxVec, pvpq: IntVec, pq: IntVec) -> csc_matrix:
    """
    Create the AC Jacobian function with no embedded controls
    :param Ybus: Ybus matrix in CSC format
    :param V: Voltages vector
    :param pvpq: array of pv|pq bus indices
    :param pq: array of pq indices
    :return: Jacobian Matrix in CSR format
    """

    nbus = Ybus.shape[0]

    # create Jacobian from fast calc of dS_dV
    dS_dVm, dS_dVa = dSbus_dV_numba_sparse_csr(Ybus.data, Ybus.indptr, Ybus.indices, V, V / np.abs(V))

    # data in J, space pre-allocated is bigger than actual Jx -> will be reduced later on
    Jx = np.empty(len(dS_dVm) * 4, dtype=float64)

    # row pointer, dimension = pvpq.shape[0] + pq.shape[0] + 1
    Jp = np.zeros(pvpq.shape[0] + pq.shape[0] + 1, dtype=int32)

    # indices, same with the pre-allocated space (see Jx)
    Jj = np.empty(len(dS_dVm) * 4, dtype=int32)

    # fill Jx, Jj and Jp in CSR order
    create_J_csr(nbus, dS_dVm, dS_dVa, Ybus.indptr, Ybus.indices, pvpq, pq, Jx, Jj, Jp)

    # resize before generating the scipy sparse matrix
    Jx.resize(Jp[-1], refcheck=False)
    Jj.resize(Jp[-1], refcheck=False)

    # generate scipy sparse matrix
    nj = len(pvpq) + len(pq)
    return csr_matrix((Jx, Jj, Jp), shape=(nj, nj)).tocsc()


@jit(nopython=True, cache=True)
def create_J_csc(nbus, Yx: CxVec, Yp: IntVec, Yi: IntVec, V: CxVec, pvpq, pq) -> CSC:
    """
    Calculates Jacobian in CSC format.

    J has the shape

            pvpq      pq
    pvpq | dP_dVa | dP_dVm |
      pq | dQ_dVa | dQ_dVm |

    :param nbus:
    :param Yx:
    :param Yp:
    :param Yi:
    :param V:
    :param pvpq:
    :param pq:
    :return:
    """

    # create Jacobian from fast calc of dS_dV
    dS_dVm_x, dS_dVa_x = dSbus_dV_numba_sparse_csc(Yx, Yp, Yi, V, np.abs(V))

    nj = len(pvpq) + len(pq)
    nnz_estimate = 5 * len(dS_dVm_x)
    J = CSC(nj, nj, nnz_estimate, False)

    # Note: The row and column pointer of of dVm and dVa are the same as the one from Ybus

    lookup_pvpq = create_lookup(nbus, pvpq)
    lookup_pq = create_lookup(nbus, pq)

    # get length of vectors
    npvpq = len(pvpq)

    # nonzeros in J
    nnz = 0
    p = 0

    # J1 and J3 -----------------------------------------------------------------------------------------
    for j in pvpq:  # columns

        # J1
        for k in range(Yp[j], Yp[j + 1]):  # rows
            i = Yi[k]
            ii = lookup_pvpq[i]

            if pvpq[ii] == i:
                J.data[nnz] = dS_dVa_x[k].real
                J.indices[nnz] = ii
                nnz += 1

        # J3
        for k in range(Yp[j], Yp[j + 1]):  # rows
            i = Yi[k]
            ii = lookup_pq[i]

            if pq[ii] == i:
                J.data[nnz] = dS_dVa_x[k].imag
                J.indices[nnz] = ii + npvpq
                nnz += 1

        p += 1
        J.indptr[p] = nnz

    # J2 and J4 -----------------------------------------------------------------------------------------
    for j in pq:  # columns

        # J2
        for k in range(Yp[j], Yp[j + 1]):  # rows
            i = Yi[k]
            ii = lookup_pvpq[i]

            if pvpq[ii] == i:
                J.data[nnz] = dS_dVm_x[k].real
                J.indices[nnz] = ii
                nnz += 1

        # J4
        for k in range(Yp[j], Yp[j + 1]):  # rows
            i = Yi[k]
            ii = lookup_pq[i]

            if pq[ii] == i:
                J.data[nnz] = dS_dVm_x[k].imag
                J.indices[nnz] = ii + npvpq
                nnz += 1

        p += 1
        J.indptr[p] = nnz

    J.indptr[p] = nnz
    J.resize(nnz)
    return J


def AC_jacobian(Ybus: csc_matrix, V: CxVec, pvpq: IntVec, pq: IntVec) -> CSC:
    """
    Create the AC Jacobian function with no embedded controls
    :param Ybus: Ybus matrix in CSC format
    :param V: Voltages vector
    :param pvpq: array of pv|pq bus indices
    :param pq: array of pq indices
    :return: Jacobian Matrix in CSC format
    """
    if Ybus.format != 'csc':
        Ybus = Ybus.tocsc()

    nbus = Ybus.shape[0]

    # Create J in CSC order
    J = create_J_csc(nbus, Ybus.data, Ybus.indptr, Ybus.indices, V, pvpq, pq)

    return J


@jit(nopython=True)
def create_J_vc_csc(nbus: int, Yx: CxVec, Yp: IntVec, Yi: IntVec, V: CxVec,
                    block1_idx: IntVec, block2_idx: IntVec, block3_idx: IntVec) -> CSC:
    """
    Calculates Jacobian in CSC format.

    J has the shape

            bl1      bl2
    bl1 | dP_dVa | dP_dVm |
    bl3 | dQ_dVa | dQ_dVm |

    :param nbus:
    :param Yx:
    :param Yp:
    :param Yi:
    :param V:
    :param block1_idx: pv, pq, p, pqv
    :param block2_idx: pq, p
    :param block3_idx: pq, pqv
    :return: Jacobina matrix
    """

    # create Jacobian from fast calc of dS_dV
    dS_dVm_x, dS_dVa_x = dSbus_dV_numba_sparse_csc(Yx, Yp, Yi, V, np.abs(V))

    nj = len(block1_idx) + len(block2_idx)
    nnz_estimate = 5 * len(dS_dVm_x)
    J = CSC(nj, nj, nnz_estimate, False)

    # Note: The row and column pointer of of dVm and dVa are the same as the one from Ybus
    lookup_block1 = create_lookup(nbus, block1_idx)
    lookup_block3 = create_lookup(nbus, block3_idx)

    # get length of vectors
    n_no_slack = len(block1_idx)

    # nonzeros in J
    nnz = 0
    p = 0

    # J1 and J3 -----------------------------------------------------------------------------------------
    for j in block1_idx:  # columns

        # J1
        for k in range(Yp[j], Yp[j + 1]):  # rows
            i = Yi[k]
            ii = lookup_block1[i]

            if block1_idx[ii] == i:
                J.data[nnz] = dS_dVa_x[k].real
                J.indices[nnz] = ii
                nnz += 1

        # J3
        for k in range(Yp[j], Yp[j + 1]):  # rows
            i = Yi[k]
            ii = lookup_block3[i]

            if block3_idx[ii] == i:
                J.data[nnz] = dS_dVa_x[k].imag
                J.indices[nnz] = ii + n_no_slack
                nnz += 1

        p += 1
        J.indptr[p] = nnz

    # J2 and J4 -----------------------------------------------------------------------------------------
    for j in block2_idx:  # columns

        # J2
        for k in range(Yp[j], Yp[j + 1]):  # rows
            i = Yi[k]
            ii = lookup_block1[i]

            if block1_idx[ii] == i:
                J.data[nnz] = dS_dVm_x[k].real
                J.indices[nnz] = ii
                nnz += 1

        # J4
        for k in range(Yp[j], Yp[j + 1]):  # rows
            i = Yi[k]
            ii = lookup_block3[i]

            if block3_idx[ii] == i:
                J.data[nnz] = dS_dVm_x[k].imag
                J.indices[nnz] = ii + n_no_slack
                nnz += 1

        p += 1
        J.indptr[p] = nnz

    J.indptr[p] = nnz
    J.resize(nnz)
    return J


def AC_jacobianVc(Ybus: csc_matrix, V: CxVec, block1_idx: IntVec, block2_idx: IntVec, block3_idx: IntVec) -> CSC:
    """
    Create the AC Jacobian function with no embedded controls
    :param Ybus: Ybus matrix in CSC format
    :param V: Voltages vector
    :param block1_idx: pv, pq, p, pqv
    :param block2_idx: pq, p
    :param block3_idx: pq, pqv
    :return: Jacobian Matrix in CSC format
    """
    if Ybus.format != 'csc':
        Ybus = Ybus.tocsc()

    nbus = Ybus.shape[0]

    # Create J in CSC order
    J = create_J_vc_csc(nbus, Ybus.data, Ybus.indptr, Ybus.indices, V, block1_idx, block2_idx, block3_idx)

    return J
