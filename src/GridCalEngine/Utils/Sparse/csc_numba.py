# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
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
import numba as nb
from numba.typed import List
import math
from typing import Tuple
from GridCalEngine.basic_structures import Mat, Vec, IntVec

# @nb.njit("i4[:](i8)")
@nb.njit(cache=True)
def ialloc(n):
    return np.zeros(n, dtype=nb.int32)


# @nb.njit("f8[:](i8)")
@nb.njit(cache=True)
def xalloc(n):
    return np.zeros(n, dtype=nb.float64)


# @nb.njit("Tuple((i8, i8, i4[:], i4[:], f8[:], i8))(i8, i8, i8)")
@nb.njit()
def csc_spalloc_f(m, n, nzmax):
    """
    Allocate a sparse matrix (triplet form or compressed-column form).

    @param m: number of rows
    @param n: number of columns
    @param nzmax: maximum number of entries
    @return: m, n, Aindptr, Aindices, Adata, Anzmax
    """
    Anzmax = max(nzmax, 1)
    Aindptr = ialloc(n + 1)
    Aindices = ialloc(Anzmax)
    Adata = xalloc(Anzmax)
    return m, n, Aindptr, Aindices, Adata, Anzmax


# @nb.njit("(f8[:], f8[:], i8)")
@nb.njit()
def _copy_f(src, dest, length):
    for i in range(length):
        dest[i] = src[i]


# @nb.njit("(i4[:], i4[:], i8)")
@nb.njit()
def _copy_i(src, dest, length):
    for i in range(length):
        dest[i] = src[i]


# @nb.njit("i8(i4[:], i4[:], i8)")
@nb.njit()
def csc_cumsum_i(p, c, n):
    """
    p [0..n] = cumulative sum of c [0..n-1], and then copy p [0..n-1] into c

    @param p: size n+1, cumulative sum of c
    @param c: size n, overwritten with p [0..n-1] on output
    @param n: length of c
    @return: sum (c), null on error
    """
    nz = 0
    nz2 = 0.0

    for i in range(n):
        p[i] = nz
        nz += c[i]
        nz2 += c[i]              # also in double to avoid CS_INT overflow
        c[i] = p[i]             # also copy p[0..n-1] back into c[0..n-1]
    p[n] = nz
    return int(nz2)               # return sum (c [0..n-1])


# @nb.njit("Tuple((i4[:], f8[:], i8))(i8, i4[:], i4[:], f8[:], i8)")
@nb.njit()
def csc_sprealloc_f(An, Aindptr, Aindices, Adata, nzmax):
    """
    Change the max # of entries a sparse matrix can hold.
    :param An: number of columns
    :param Aindptr: csc column pointers
    :param Aindices: csc row indices
    :param Adata: csc data
    :param nzmax:new maximum number of entries
    :return: indices, data, nzmax
    """

    if nzmax <= 0:
        nzmax = Aindptr[An]

    length = min(nzmax, len(Aindices))
    Ainew = np.empty(nzmax, dtype=nb.int32)
    for i in range(length):
        Ainew[i] = Aindices[i]

    length = min(nzmax, len(Adata))
    Axnew = np.empty(nzmax, dtype=nb.float64)
    for i in range(length):
        Axnew[i] = Adata[i]

    return Ainew, Axnew, nzmax


# @nb.njit("i8(i4[:], i4[:], f8[:], i8, f8, i4[:], f8[:], i8, i4[:], i8)")
@nb.njit()
def csc_scatter_f(Ap, Ai, Ax, j, beta, w, x, mark, Ci, nz):
    """
    Scatters and sums a sparse vector A(:,j) into a dense vector, x = x + beta * A(:,j)
    :param Ap:
    :param Ai:
    :param Ax:
    :param j: the column of A to use
    :param beta: scalar multiplied by A(:,j)
    :param w: size m, node i is marked if w[i] = mark
    :param x: size m, ignored if null
    :param mark: mark value of w
    :param Ci: pattern of x accumulated in C.i
    :param nz: pattern of x placed in C starting at C.i[nz]
    :return: new value of nz, -1 on error, x and w are modified
    """

    for p in range(Ap[j], Ap[j + 1]):
        i = Ai[p]  # A(i,j) is nonzero
        if w[i] < mark:
            w[i] = mark  # i is new entry in column j
            Ci[nz] = i  # add i to pattern of C(:,j)
            nz += 1
            x[i] = beta * Ax[p]  # x(i) = beta*A(i,j)
        else:
            x[i] += beta * Ax[p]  # i exists in C(:,j) already
    return nz


# @nb.njit("i8(i4[:], i4[:], f8[:], i8, f8, i4[:], f8[:], i8, i4[:], i8)")
@nb.njit()
def csc_scatter_ff(Aindptr, Aindices, Adata, j, beta, w, x, mark, Ci, nz):
    """
    Scatters and sums a sparse vector A(:,j) into a dense vector, x = x + beta * A(:,j)
    :param Aindptr:
    :param Aindices:
    :param Adata:
    :param j: the column of A to use
    :param beta: scalar multiplied by A(:,j)
    :param w: size m, node i is marked if w[i] = mark
    :param x: size m, ignored if null
    :param mark: mark value of w
    :param Ci: pattern of x accumulated in C.i
    :param nz: pattern of x placed in C starting at C.i[nz]
    :return: new value of nz, -1 on error, x and w are modified
    """

    for p in range(Aindptr[j], Aindptr[j + 1]):
        i = Aindices[p]  # A(i,j) is nonzero
        if w[i] < mark:
            w[i] = mark  # i is new entry in column j
            Ci[nz] = i  # add i to pattern of C(:,j)
            nz += 1
            x[i] = beta * Adata[p]  # x(i) = beta*A(i,j)
        else:
            x[i] += beta * Adata[p]  # i exists in C(:,j) already
    return nz


# @nb.njit("Tuple((i8, i8, i4[:], i4[:], f8[:]))(i8, i8, i4[:], i4[:], f8[:], i8, i8, i4[:], i4[:], f8[:], f8, f8)")
@nb.njit()
def csc_add_ff(Am, An, Aindptr, Aindices, Adata,
               Bm, Bn, Bindptr, Bindices, Bdata, alpha, beta):
    """
    C = alpha*A + beta*B

    @param A: column-compressed matrix
    @param B: column-compressed matrix
    @param alpha: scalar alpha
    @param beta: scalar beta
    @return: C=alpha*A + beta*B, null on error (Cm, Cn, Cp, Ci, Cx)
    """
    nz = 0

    m, anz, n, Bp, Bx = Am, Aindptr[An], Bn, Bindptr, Bdata

    bnz = Bp[n]

    w = np.zeros(m, dtype=nb.int32)

    x = xalloc(m)   # get workspace

    Cm, Cn, Cp, Ci, Cx, Cnzmax = csc_spalloc_f(m, n, anz + bnz)  # allocate result

    for j in range(n):
        Cp[j] = nz  # column j of C starts here

        nz = csc_scatter_f(Aindptr, Aindices, Adata, j, alpha, w, x, j + 1, Ci, nz)  # alpha*A(:,j)

        nz = csc_scatter_f(Bindptr, Bindices, Bdata, j, beta, w, x, j + 1, Ci, nz)  # beta*B(:,j)

        for p in range(Cp[j], nz):
            Cx[p] = x[Ci[p]]

    Cp[n] = nz  # finalize the last column of C

    return Cm, Cn, Cp, Ci, Cx  # success; free workspace, return C


# @nb.njit("Tuple((i8, i8, i4[:], i4[:], f8[:], i8))(i8, i8, i4[:], i4[:], f8[:], i8, i8, i4[:], i4[:], f8[:])",
#          parallel=False, nogil=True, fastmath=False, cache=True)  # fastmath=True breaks the code
@nb.njit()
def csc_multiply_ff(Am, An, Ap, Ai, Ax,
                    Bm, Bn, Bp, Bi, Bx):
    """
    Sparse matrix multiplication, C = A*B where A and B are CSC sparse matrices
    :param Am: number of rows in A
    :param An: number of columns in A
    :param Ap: column pointers of A
    :param Ai: indices of A
    :param Ax: data of A
    :param Bm: number of rows in B
    :param Bn: number of columns in B
    :param Bp: column pointers of B
    :param Bi: indices of B
    :param Bx: data of B
    :return: Cm, Cn, Cp, Ci, Cx, Cnzmax
    """
    assert An == Bm
    nz = 0
    anz = Ap[An]
    bnz = Bp[Bn]
    Cm = Am
    Cn = Bn

    t = nb
    w = np.zeros(Cn, dtype=t.int32)  # ialloc(m)  # get workspace
    x = np.empty(Cn, dtype=t.float64)  # xalloc(m)  # get workspace

    # allocate result

    Cnzmax = int(math.sqrt(Cm)) * anz + bnz  # the trick here is to allocate just enough memory to avoid reallocating
    Cp = np.empty(Cn + 1, dtype=t.int32)
    Ci = np.empty(Cnzmax, dtype=t.int32)
    Cx = np.empty(Cnzmax, dtype=t.float64)

    for j in range(Cn):

        # claim more space
        if nz + Cm > Cnzmax:
            # Ci, Cx, Cnzmax = csc_sprealloc_f(Cn, Cp, Ci, Cx, 2 * Cnzmax + m)
            print('Re-Allocating')
            Cnzmax = 2 * Cnzmax + Cm
            if Cnzmax <= 0:
                Cnzmax = Cp[An]

            length = min(Cnzmax, len(Ci))
            Cinew = np.empty(Cnzmax, dtype=nb.int32)
            for i in range(length):
                Cinew[i] = Ci[i]
            Ci = Cinew

            length = min(Cnzmax, len(Cx))
            Cxnew = np.empty(Cnzmax, dtype=nb.float64)
            for i in range(length):
                Cxnew[i] = Cx[i]
            Cx = Cxnew

        # column j of C starts here
        Cp[j] = nz

        # perform the multiplication
        for pb in range(Bp[j], Bp[j + 1]):
            for pa in range(Ap[Bi[pb]], Ap[Bi[pb] + 1]):
                ia = Ai[pa]
                if w[ia] < j + 1:
                    w[ia] = j + 1
                    Ci[nz] = ia
                    nz += 1
                    x[ia] = Bx[pb] * Ax[pa]
                else:
                    x[ia] += Bx[pb] * Ax[pa]

        for pc in range(Cp[j], nz):
            Cx[pc] = x[Ci[pc]]

    Cp[Cn] = nz  # finalize the last column of C

    # cut the arrays to their nominal size nnz
    # Ci, Cx, Cnzmax = csc_sprealloc_f(Cn, Cp, Ci, Cx, 0)
    Cnzmax = Cp[Cn]
    Cinew = Ci[:Cnzmax]
    Cxnew = Cx[:Cnzmax]

    return Cm, Cn, Cp, Cinew, Cxnew, Cnzmax


# @nb.njit("f8[:](i8, i8, i4[:], i4[:], f8[:], f8[:])", parallel=False)
@nb.njit()
def csc_mat_vec_ff(m, n, Ap, Ai, Ax, x):
    """
    Sparse matrix times dense column vector, y = A * x.
    :param m: number of rows
    :param n: number of columns
    :param Ap: pointers
    :param Ai: indices
    :param Ax: data
    :param x: vector x (n)
    :return: vector y (m)
    """

    assert n == x.shape[0]

    y = np.zeros(m, dtype=nb.float64)
    for j in range(n):
        for p in range(Ap[j], Ap[j + 1]):
            y[Ai[p]] += Ax[p] * x[j]
    return y


# @nb.njit("Tuple((i8, i8, i4[:], i4[:], f8[:]))(i8, i8, i4[:], i4[:], f8[:], i8)")
@nb.njit()
def coo_to_csc(m, n, Ti, Tj, Tx, nz):
    """
    C = compressed-column form of a triplet matrix T. The columns of C are
    not sorted, and duplicate entries may be present in C.

    @param T: triplet matrix
    @return: Cm, Cn, Cp, Ci, Cx
    """

    Cm, Cn, Cp, Ci, Cx, nz = csc_spalloc_f(m, n, nz)  # allocate result

    w = w = np.zeros(n, dtype=nb.int32)  # get workspace

    for k in range(nz):
        w[Tj[k]] += 1  # column counts

    csc_cumsum_i(Cp, w, n)  # column pointers

    for k in range(nz):
        p = w[Tj[k]]
        w[Tj[k]] += 1
        Ci[p] = Ti[k]  # A(i,j) is the pth entry in C
        # if Cx is not None:
        Cx[p] = Tx[k]

    return Cm, Cn, Cp, Ci, Cx


# @nb.njit("void(i8, i8, i4[:], i4[:], f8[:], i4[:], i4[:], f8[:])")
@nb.njit()
def csc_to_csr(m, n, Ap, Ai, Ax, Bp, Bi, Bx):
    """
    Convert a CSC Matrix into a CSR Matrix
    :param m: number of rows
    :param n: number of columns
    :param Ap: indptr of the CSC matrix
    :param Ai: indices of the CSC matrix
    :param Ax: data of the CSC matrix
    :param Bp: indptr of the CSR matrix (to compute, size 'm+1', has to be initialized to zeros)
    :param Bi: indices of the CSR matrix (to compute, size nnz)
    :param Bx: data of the CSR matrix (to compute, size nnz)
    """
    nnz = Ap[n]

    for k in range(nnz):
        Bp[Ai[k]] += 1

    cum_sum = 0
    for col in range(m):
        temp = Bp[col]
        Bp[col] = cum_sum
        cum_sum += temp
    Bp[m] = nnz

    for row in range(n):
        for jj in range(Ap[row], Ap[row+1]):
            col = Ai[jj]
            dest = Bp[col]
            Bi[dest] = row
            Bx[dest] = Ax[jj]
            Bp[col] += 1

    last = 0
    for col in range(m):
        temp = Bp[col]
        Bp[col] = last
        last = temp


# @nb.njit("Tuple((i8, i8, i4[:], i4[:], f8[:]))(i8, i8, i4[:], i4[:], f8[:])")
@nb.njit()
def csc_transpose(m, n, Ap, Ai, Ax):
    """
    Transpose matrix
    :param m: A.m
    :param n: A.n
    :param Ap: A.indptr
    :param Ai: A.indices
    :param Ax: A.data
    :return: Cm, Cn, Cp, Ci, Cx
    """

    """
    Computes the transpose of a sparse matrix, C =A';

    @param A: column-compressed matrix
    @param allocate_values: pattern only if false, both pattern and values otherwise
    @return: C=A', null on error
    """

    Cm, Cn, Cp, Ci, Cx, Cnzmax = csc_spalloc_f(m=n, n=m, nzmax=Ap[n])  # allocate result

    w = ialloc(m)  # get workspace

    for p in range(Ap[n]):
        w[Ai[p]] += 1  # row counts

    csc_cumsum_i(Cp, w, m)  # row pointers

    for j in range(n):
        for p in range(Ap[j], Ap[j + 1]):
            q = w[Ai[p]]
            w[Ai[p]] += 1
            Ci[q] = j  # place A(i,j) as entry C(j,i)
            Cx[q] = Ax[p]

    return Cm, Cn, Cp, Ci, Cx


# @nb.njit("i4(i4, i4, i4[:])")
@nb.njit()
def binary_find(N, x, array):
    """
    Binary search
    :param N: size of the array
    :param x: value
    :param array: array
    :return: position where it is found. -1 if it is not found
    """
    lower = 0
    upper = N

    while (lower + 1) < upper:
        mid = int((lower + upper) / 2)
        if x < array[mid]:
            upper = mid
        else:
            lower = mid

    if array[lower] <= x:
        return lower
    return -1


# @nb.njit("Tuple((i8, i4[:], i4[:], f8[:]))(i8, i8, i4[:], i4[:], f8[:], i4[:], i4[:])")
def csc_sub_matrix_old(Am, Anz, Ap, Ai, Ax, rows, cols):
    """
    Get SCS arbitrary sub-matrix
    :param Am: number of rows
    :param Anz: number of non-zero entries
    :param Ap: Column pointers
    :param Ai: Row indices
    :param Ax: Data
    :param rows: row indices to keep
    :param cols: column indices to keep
    :return: CSC sub-matrix (n, new_col_ptr, new_row_ind, new_val)
    """
    n_cols = len(cols)

    Bx = np.zeros(Anz, dtype=np.float64)
    Bi = np.empty(Anz, dtype=np.int32)
    Bp = np.empty(n_cols + 1, dtype=np.int32)

    n = 0
    p = 0
    Bp[p] = 0

    for j in cols:  # for each column selected ...
        i = 0
        for r in rows:
            for k in range(Ap[j], Ap[j + 1]):  # for each row of the column j of A...
                if Ai[k] == r:
                    Bx[n] = Ax[k]  # store the value
                    Bi[n] = i  # row index in the new matrix
                    i += 1
                    n += 1
            if i == 0:
                i += 1
        p += 1
        Bp[p] = n

    Bp[p] = n

    return n, Bp, Bi[:n], Bx[:n]


@nb.njit()
def csc_sub_matrix(Am, Annz, Ap, Ai, Ax, rows, cols):
    """
    CSC matrix sub-matrix view
    :param Am: number of rows
    :param Annz: number of non-zero entries
    :param Ap: Column pointers
    :param Ai: Row indices
    :param Ax: Data
    :param rows: array of selected rows: must be sorted! to use the binary search
    :param cols: array of columns: should be sorted
    :return:
    """
    n_rows = len(rows)
    n_cols = len(cols)

    nnz = 0
    p = 0
    Bx = np.empty(Annz, dtype=nb.float64)  # data
    Bi = np.empty(Annz, dtype=nb.int32)  # indices
    Bp = np.empty(n_cols + 1, dtype=nb.int32)  # pointers
    Bp[p] = 0

    # generate lookup for the non immediate axis (for CSC it is the rows) -> index lookup
    lookup = np.zeros(Am, dtype=nb.int32)
    lookup[rows] = np.arange(len(rows), dtype=nb.int32)

    for j in cols:  # sliced columns

        for k in range(Ap[j], Ap[j + 1]):  # rows of A[:, j]

            # row index translation to the "rows" space
            i = Ai[k]
            ii = lookup[i]

            if rows[ii] == i:
                # entry found
                Bx[nnz] = Ax[k]
                Bi[nnz] = ii
                nnz += 1

        p += 1
        Bp[p] = nnz

    Bp[p] = nnz

    # numba does not support resize...
    # new_val = np.resize(new_val, nnz)
    # new_row_ind = np.resize(new_row_ind, nnz)

    return Bx, Bi, Bp, n_rows, n_cols, nnz


@nb.njit()
def csc_sub_matrix_cols(Am, Anz, Ap, Ai, Ax, cols):
    """
    Get SCS arbitrary sub-matrix with all the rows
    :param Am: number of rows
    :param Anz: number of non-zero entries
    :param Ap: Column pointers
    :param Ai: Row indices
    :param Ax: Data
    :param cols: column indices to keep
    :return: CSC sub-matrix (n, new_col_ptr, new_row_ind, new_val)
    """

    n_cols = len(cols)
    n = 0
    p = 0
    Bx = np.empty(Anz, dtype=nb.float64)
    Bi = np.empty(Anz, dtype=nb.int32)
    Bp = np.empty(n_cols + 1, dtype=nb.int32)

    Bp[p] = 0

    for j in cols:  # for each column selected ...
        for k in range(Ap[j], Ap[j + 1]):  # for each row of the column j of A...
            # store the values if the row was found in rows
            Bx[n] = Ax[k]  # store the value
            Bi[n] = Ai[k]  # store the row index
            n += 1
        p += 1
        Bp[p] = n

    Bp[p] = n

    return n, Bp, Bi[:n], Bx[:n]


def csc_sub_matrix_rows(An, Anz, Ap, Ai, Ax, rows):
    """
    Get SCS arbitrary sub-matrix
    :param An: number of rows
    :param Anz: number of non-zero entries
    :param Ap: Column pointers
    :param Ai: Row indices
    :param Ax: Data
    :param rows: row indices to keep
    :return: CSC sub-matrix (n, new_col_ptr, new_row_ind, new_val)
    """
    n_rows = len(rows)
    n = 0
    p = 0
    Bx = np.zeros(Anz, dtype=np.float64)
    Bi = np.empty(Anz, dtype=np.int32)
    Bp = np.empty(An + 1, dtype=np.int32)

    Bp[p] = 0

    for j in range(An):  # for each column selected ...
        i = 0
        for r in rows:
            for k in range(Ap[j], Ap[j + 1]):  # for each row of the column j of A...
                if Ai[k] == r:
                    Bx[n] = Ax[k]  # store the value
                    Bi[n] = i  # row index in the new matrix
                    n += 1
                    i += 1
            if i == 0:
                i += 1
        p += 1
        Bp[p] = n

    Bp[p] = n

    return n, Bp, Bi[:n], Bx[:n]


# @nb.njit("f8[:, :](i8, i8, i4[:], i4[:], f8[:])")
def csc_to_dense(m, n, indptr, indices, data):
    """
    Convert csc matrix to dense
    :param m:
    :param n:
    :param indptr:
    :param indices:
    :param data:
    :return: 2d numpy array
    """
    val = np.zeros((m, n), dtype=np.float64)

    for j in range(n):
        for p in range(indptr[j], indptr[j + 1]):
            val[indices[p], j] = data[p]
    return val


# @nb.njit("Tuple((i4[:], i4[:], f8[:]))(i8, f8)")
@nb.njit()
def csc_diagonal(m, value=1.0):
    """
    Build CSC diagonal matrix of the given value
    :param m: size
    :param value: value
    :return: CSC matrix
    """
    indptr = np.empty(m + 1, dtype=np.int32)
    indices = np.empty(m, dtype=np.int32)
    data = np.empty(m, dtype=np.float64)
    for i in range(m):
        indptr[i] = i
        indices[i] = i
        data[i] = value
    indptr[m] = m

    return indices, indptr, data


# @nb.njit("Tuple((i4[:], i4[:], f8[:]))(i8, f8[:])")
@nb.njit()
def csc_diagonal_from_array(m, array):
    """

    :param m:
    :param array:
    :return:
    """
    indptr = np.empty(m + 1, dtype=np.int32)
    indices = np.empty(m, dtype=np.int32)
    data = np.empty(m, dtype=np.float64)
    for i in range(m):
        indptr[i] = i
        indices[i] = i
        data[i] = array[i]
    indptr[m] = m

    return indices, indptr, data


# @nb.njit("Tuple((i8, i8, i4[:], i4[:], f8[:]))"
#          "(i8, i8, i4[:], i4[:], f8[:], "
#          "i8, i8, i4[:], i4[:], f8[:], "
#          "i8, i8, i4[:], i4[:], f8[:], "
#          "i8, i8, i4[:], i4[:], f8[:])",
#          parallel=False, nogil=True, fastmath=True, cache=True)
@nb.njit()
def csc_stack_4_by_4_ff(am, an, Ai, Ap, Ax,
                        bm, bn, Bi, Bp, Bx,
                        cm, cn, Ci, Cp, Cx,
                        dm, dn, Di, Dp, Dx):
    """
    stack csc sparse float matrices like this:
    | A | B |
    | C | D |

    :param am:
    :param an:
    :param Ai:
    :param Ap:
    :param Ax:
    :param bm:
    :param bn:
    :param Bi:
    :param Bp:
    :param Bx:
    :param cm:
    :param cn:
    :param Ci:
    :param Cp:
    :param Cx:
    :param dm:
    :param dn:
    :param Di:
    :param Dp:
    :param Dx:
    :return:
    """

    # check dimensional compatibility
    assert am == bm
    assert cm == dm
    assert an == cn
    assert bn == dn

    nnz = Ap[an] + Bp[bn] + Cp[cn] + Dp[dn]

    m = am + cm
    n = an + bn

    indptr = np.zeros(n + 1, dtype=nb.int32)
    indices = np.zeros(nnz, dtype=nb.int32)
    data = np.zeros(nnz, dtype=nb.float64)
    cnt = 0
    indptr[0] = 0
    for j in range(an):  # for every column, same as range(cols + 1) For A and C
        for k in range(Ap[j], Ap[j + 1]):  # for every entry in the column from A
            indices[cnt] = Ai[k]  # row index
            data[cnt] = Ax[k]
            cnt += 1

        for k in range(Cp[j], Cp[j + 1]):  # for every entry in the column from C
            indices[cnt] = Ci[k] + am  # row index
            data[cnt] = Cx[k]
            cnt += 1

        indptr[j + 1] = cnt

    for j in range(bn):  # for every column, same as range(cols + 1) For B and D
        for k in range(Bp[j], Bp[j + 1]):  # for every entry in the column from B
            indices[cnt] = Bi[k]  # row index
            data[cnt] = Bx[k]
            cnt += 1

        for k in range(Dp[j], Dp[j + 1]):  # for every entry in the column from D
            indices[cnt] = Di[k] + bm  # row index
            data[cnt] = Dx[k]
            cnt += 1

        indptr[an + j + 1] = cnt

    return m, n, indices, indptr, data


# @nb.njit("f8(i8, i4[:], f8[:])")
@nb.njit()
def csc_norm(n, Ap, Ax):
    """
    Computes the 1-norm of a sparse matrix = max (sum (abs (A))), largest
    column sum.

    @param A: column-compressed matrix
    @return: the 1-norm if successful, -1 on error
    """
    norm = 0

    for j in range(n):
        s = 0
        for p in range(Ap[j], Ap[j + 1]):
            s += abs(Ax[p])
        norm = max(norm, s)
    return norm


@nb.njit()
def find_islands(node_number, indptr, indices):
    """
    Method to get the islands of a graph
    This is the non-recursive version
    :return: islands list where each element is a list of the node indices of the island
    """

    # Mark all the vertices as not visited
    visited = np.zeros(node_number, dtype=nb.boolean)

    # storage structure for the islands (list of lists)
    islands = List.empty_list(List.empty_list(nb.int64))

    # set the island index
    island_idx = 0

    # go though all the vertices...
    for node in range(node_number):

        # if the node has not been visited...
        if not visited[node]:

            # add new island, because the recursive process has already visited all the island connected to v
            # if island_idx >= len(islands):
            islands.append(List.empty_list(nb.int64))

            # ------------------------------------------------------------------------------------------------------
            # DFS: store in the island all the reachable vertices from current vertex "node"
            #
            # declare a stack with the initial node to visit (node)
            stack = List.empty_list(nb.int64)
            stack.append(node)

            while len(stack) > 0:

                # pick the first element of the stack
                v = stack.pop(0)

                # if v has not been visited...
                if not visited[v]:

                    # mark as visited
                    visited[v] = True

                    # add element to the island
                    islands[island_idx].append(v)

                    # Add the neighbours of v to the stack
                    start = indptr[v]
                    end = indptr[v + 1]
                    for i in range(start, end):
                        k = indices[i]  # get the column index in the CSC scheme
                        if not visited[k]:
                            stack.append(k)
            # ------------------------------------------------------------------------------------------------------

            # increase the islands index, because all the other connected vertices have been visited
            island_idx += 1

    # sort the islands to maintain raccord
    # for island in islands:
    #     island.sort()
    return islands



# @nb.njit("Tuple((i4[:], i4[:], f8[:], i8, i8))(i8, i4[:], i4[:], f8[:], i8[:])")
@nb.njit()
def sp_submat_c_numba(nrows, ptrs, indices, values, cols):
    """
    slice CSC columns
    :param nrows: number of rows of the matrix
    :param ptrs: row pointers
    :param indices: column indices
    :param values: data
    :param cols: vector of columns to slice
    :return: new_indices, new_col_ptr, new_val, nrows, ncols
    """
    # pass1: determine the number of non-zeros
    nnz = 0
    for j in cols:
        for k in range(ptrs[j], ptrs[j+1]):
            nnz += 1

    # pass2: size the vector and perform the slicing
    ncols = len(cols)
    n = 0
    p = 0

    new_val = np.empty(nnz, dtype=nb.float64)
    new_indices = np.empty(nnz, dtype=nb.int32)
    new_col_ptr = np.empty(ncols + 1, dtype=nb.int32)

    new_col_ptr[p] = 0

    for j in cols:
        for k in range(ptrs[j], ptrs[j + 1]):
            new_val[n] = values[k]
            new_indices[n] = indices[k]
            n += 1

        p += 1
        new_col_ptr[p] = n

    return new_indices, new_col_ptr, new_val, nrows, ncols


@nb.njit(nogil=True, fastmath=True, cache=True)
def csc_stack_2d_ff_row_major(mats_data, mats_indptr, mats_indices, mats_cols, mats_rows, m_rows=1, m_cols=1):
    """
    Assemble matrix from a list of matrices representing a "super matrix"

    |mat11 | mat12 | mat13 |
    |mat21 | mat22 | mat23 |

    turns into:

    mats = [mat11, mat12, mat13, mat21, mat22, mat23]
    m_rows = 2
    m_cols = 3

    :param mats_data: array of numpy arrays with the data of each CSC matrix
    :param mats_indptr: array of numpy arrays with the indptr of each CSC matrix
    :param mats_indices: array of numpy arrays with the indices of each CSC matrix
    :param mats_cols: array with the number of columns of each CSC matrix
    :param mats_rows: array with the number of rows of each CSC matrix
    :param m_rows: number of rows of the mats structure
    :param m_cols: number of cols of the mats structure
    :return: Final assembled matrix
    """

    '''
    Row major: A(r,c) element is at A[c + r * n_columns]; 
    Col major: A(r,c) element is at A[r + c * n_rows];    
    '''

    # pass 1: compute the number of non zero
    nnz = 0
    nrows = 0
    ncols = 0
    for r in range(m_rows):
        nrows += mats_rows[r * m_cols]  # equivalent to mats[r, 0]
        for c in range(m_cols):
            col = mats_cols[c + r * m_cols]  # equivalent to mats[r, c]
            nnz += mats_indptr[r * m_cols + c][col]
            if r == 0:
                ncols += col

    # pass 2: fill in the data
    indptr = np.empty(ncols + 1, dtype=np.int32)
    indices = np.empty(nnz, dtype=np.int32)
    data = np.empty(nnz, dtype=np.float64)
    cnt = 0
    indptr[0] = 0
    offset_col = 0
    for c in range(m_cols):  # for each column of the array of matrices

        # number of columns
        n = mats_cols[c]  # equivalent to mats[0, c]

        if n > 0:
            for j in range(n):  # for every column of the column of matrices

                offset_row = 0

                for r in range(m_rows):  # for each row of the array of rows

                    # number of rows
                    m = mats_rows[r * m_cols + c]  # equivalent to mats[r, c].shape[0]

                    if m > 0:
                        Ap = mats_indptr[r * m_cols + c]
                        Ai = mats_indices[r * m_cols + c]
                        Ax = mats_data[r * m_cols + c]

                        for k in range(Ap[j], Ap[j + 1]):  # for every entry in the column from A
                            indices[cnt] = Ai[k] + offset_row  # row index
                            data[cnt] = Ax[k]
                            cnt += 1

                        offset_row += m

                indptr[offset_col + j + 1] = cnt
            offset_col += n

    return data, indices, indptr, nrows, ncols


@nb.njit(nogil=True, fastmath=True, cache=True)
def csc_stack_2d_ff_col_major(mats_data, mats_indptr, mats_indices, mats_cols, mats_rows, m_rows=1, m_cols=1):
    """
    Assemble matrix from a list of matrices representing a "super matrix"

    |mat11 | mat12 | mat13 |
    |mat21 | mat22 | mat23 |

    turns into:

    mats = [mat11, mat12, mat13, mat21, mat22, mat23]
    m_rows = 2
    m_cols = 3

    :param mats_data: array of numpy arrays with the data of each CSC matrix
    :param mats_indptr: array of numpy arrays with the indptr of each CSC matrix
    :param mats_indices: array of numpy arrays with the indices of each CSC matrix
    :param mats_cols: array with the number of columns of each CSC matrix
    :param mats_rows: array with the number of rows of each CSC matrix
    :param m_rows: number of rows of the mats structure
    :param m_cols: number of cols of the mats structure
    :return: Final assembled matrix
    """

    '''
    Col major: A(r,c) element is at A[r + c * n_rows];    
    '''

    # pass 1: compute the number of non zero
    nnz = 0
    nrows = 0
    ncols = 0
    for r in range(m_rows):
        nrows += mats_rows[r]  # equivalent to mats[r, 0]
        for c in range(m_cols):
            col = mats_cols[r + c * m_rows]  # equivalent to mats[r, c]
            nnz += mats_indptr[r + c * m_rows][col]
            if r == 0:
                ncols += col

    # pass 2: fill in the data
    indptr = np.empty(ncols + 1, dtype=np.int32)
    indices = np.empty(nnz, dtype=np.int32)
    data = np.empty(nnz, dtype=np.float64)
    cnt = 0
    indptr[0] = 0
    offset_col = 0
    for c in range(m_cols):  # for each column of the array of matrices

        # number of columns
        n = mats_cols[c * m_rows]  # equivalent to mats[0, c]

        if n > 0:
            for j in range(n):  # for every column of the column of matrices

                offset_row = 0

                for r in range(m_rows):  # for each row of the array of rows

                    # number of rows
                    m = mats_rows[r + c * m_rows]  # equivalent to mats[r, c].shape[0]

                    if m > 0:
                        Ap = mats_indptr[r + c * m_rows]
                        Ai = mats_indices[r + c * m_rows]
                        Ax = mats_data[r + c * m_rows]

                        for k in range(Ap[j], Ap[j + 1]):  # for every entry in the column from A
                            indices[cnt] = Ai[k] + offset_row  # row index
                            data[cnt] = Ax[k]
                            cnt += 1

                        offset_row += m

                indptr[offset_col + j + 1] = cnt
            offset_col += n

    return data, indices, indptr, nrows, ncols


@nb.njit(cache=True)
def dense_to_csc_numba(mat: Mat, threshold: float) -> Tuple[Vec, IntVec, IntVec]:
    """
    Extract the sparse matrix from a dense matrix where abs values are below a threshold
    :param mat: dense matrix
    :param threshold: threshold
    :return: data, indices, indptr
    """
    n_row, n_col = mat.shape

    indptr = np.empty(n_col + 1)
    indices = np.empty(n_row * n_col)
    data = np.empty(n_row * n_col)
    k = 0
    for j in range(n_col):

        indptr[j] = k

        for i in range(n_row):

            if abs(mat[i, j]) > threshold:
                data[k] = mat[i, j]
                indices[k] = i
                k += 1

    indptr[n_col] = k
    if k < (n_col * n_row):
        data = data[:k]
        indices = indices[:k]

    return data, indices, indptr