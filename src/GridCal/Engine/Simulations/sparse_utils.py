
import numpy as np
import numba as nb
from numba.typed import List
from scipy.sparse import csc_matrix


@nb.njit("i4[:](i8)")
def ialloc(n):
    return np.zeros(n, dtype=nb.int32)


@nb.njit("f8[:](i8)")
def xalloc(n):
    return np.zeros(n, dtype=nb.float64)


@nb.njit("Tuple((i8, i8, i4[:], i4[:], f8[:], i8))(i8, i8, i8)")
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


@nb.njit("i8(i4[:], i4[:], i8)")
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


@nb.njit("Tuple((i8, i8, i4[:], i4[:], f8[:]))(i8, i8, i4[:], i4[:], f8[:])")
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


def sp_transpose(mat: csc_matrix):
    """
    Actual CSC transpose unlike scipy's
    :param mat: CSC matrix
    :return: CSC transposed matrix
    """
    Cm, Cn, Cp, Ci, Cx = csc_transpose(m=mat.shape[0],
                                       n=mat.shape[1],
                                       Ap=mat.indptr,
                                       Ai=mat.indices,
                                       Ax=mat.data)
    return csc_matrix((Cx, Ci, Cp), shape=(Cm, Cn))


# @nb.jit(nopython=True, cache=False)
# new_indices, new_col_ptr, new_val, nrows, ncols
@nb.njit("Tuple((i4[:], i4[:], f8[:], i8, i8))(i8, i4[:], i4[:], f8[:], i8[:])")
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


def sp_slice_cols(mat: csc_matrix, cols: np.ndarray):
    """
    Slice columns
    :param mat: Matrix to slice
    :param cols: vector of columns
    :return: New sliced matrix
    """
    new_indices, new_col_ptr, new_val, nrows, ncols = sp_submat_c_numba(nrows=mat.shape[0],
                                                                        ptrs=mat.indptr,
                                                                        indices=mat.indices,
                                                                        values=mat.data,
                                                                        cols=cols)
    return csc_matrix((new_val, new_indices, new_col_ptr), shape=(nrows, ncols))


def sp_slice_rows(mat: csc_matrix, rows: np.ndarray):
    """
    Slice rows
    :param mat:
    :param rows:
    :return: CSC matrix
    """
    # mat2 = sp_transpose(mat)
    # return sp_transpose(sp_slice_cols(mat2, rows))

    return sp_transpose(sp_slice_cols(sp_transpose(mat), np.array(rows)))


def sp_slice(mat: csc_matrix, rows, cols):
    """
    /*
     * This function performs the trivial slicing of the CSC sparse matrix A
     *
     * Steps:
     *  - Slice the columns with "sp_submat_c(A, cols)"
     *  - convert to CSR with .t() {transpose}
     *  - Slice the rows with sp_submat_c(B, rows), because it is a CSR now
     *  - Convert the result back to CSC with the final .t()
     * */
    :param mat:
    :param rows:
    :param cols:
    :return:
    """
    mat2 = sp_transpose(sp_slice_cols(mat, cols))
    return sp_transpose(sp_slice_cols(mat2, rows))
    # return sp_transpose(sp_slice_cols(sp_transpose(sp_slice_cols(mat, cols)), rows))


@nb.njit("Tuple((i8, i8, i4[:], i4[:], f8[:]))"
         "(i8, i8, i4[:], i4[:], f8[:], "
         "i8, i8, i4[:], i4[:], f8[:], "
         "i8, i8, i4[:], i4[:], f8[:], "
         "i8, i8, i4[:], i4[:], f8[:])",
         parallel=False, nogil=True, fastmath=True, cache=True)
def csc_stack_4_by_4_ff(am, an, Ai, Ap, Ax,
                        bm, bn, Bi, Bp, Bx,
                        cm, cn, Ci, Cp, Cx,
                        dm, dn, Di, Dp, Dx):
    """
    stack csc sparse float matrices like this:
    | A | B |
    | C | D |

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

    indptr = np.zeros(n + 1, dtype=np.int32)
    indices = np.zeros(nnz, dtype=np.int32)
    data = np.zeros(nnz, dtype=np.float64)
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


@nb.jit(nopython=True, nogil=True)
def csc_stack_2d_ff_numba(mats_data, mats_indptr, mats_indices, mats_cols, mats_rows, m_rows=1, m_cols=1):
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

    # pass 1: compute the number of non zero
    nnz = 0
    nrows = 0
    ncols = 0
    for r in range(m_rows):

        nrows += mats_rows[r * m_cols]  # equivalent to mats[r, 0]

        for c in range(m_cols):
            col = mats_cols[r * m_cols + c]  # equivalent to mats[r, c]
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


def csc_stack_2d_ff(mats, m_rows=1, m_cols=1):
    """
    Assemble matrix from a list of matrices representing a "super matrix"

    |mat11 | mat12 | mat13 |
    |mat21 | mat22 | mat23 |

    turns into:

    mats = [mat11, mat12, mat13, mat21, mat22, mat23]
    m_rows = 2
    m_cols = 3

    :param mats: array of CSC matrices arranged in row-major order into a list
    :param m_rows: number of rows of the mats structure
    :param m_cols: number of cols of the mats structure
    :return: Final assembled matrix in CSC format
    """

    mats_data = List()
    mats_indptr = List()
    mats_indices = List()
    mats_cols = List()
    mats_rows = List()
    for x in mats:
        mats_data.append(x.data)
        mats_indptr.append(x.indptr)
        mats_indices.append(x.indices)
        mats_cols.append(x.shape[1])
        mats_rows.append(x.shape[0])

    data, indices, indptr, nrows, ncols = csc_stack_2d_ff_numba(mats_data,
                                                                mats_indptr,
                                                                mats_indices,
                                                                mats_cols,
                                                                mats_rows,
                                                                m_rows,
                                                                m_cols)

    return csc_matrix((data, indices, indptr), shape=(nrows, ncols))


def csc_stack_2d_ff_old(mats, m_rows=1, m_cols=1):
    """
    Assemble matrix from a list of matrices representing a "super matrix"

    |mat11 | mat12 | mat13 |
    |mat21 | mat22 | mat23 |

    turns into:

    mats = [mat11, mat12, mat13, mat21, mat22, mat23]
    m_rows = 2
    m_cols = 3

    :param mats: array of CSC matrices arranged in row-major order into a list
    :param m_rows: number of rows of the mats structure
    :param m_cols: number of cols of the mats structure
    :return: Final assembled matrix
    """

    # pass 1: compute the number of non zero
    nnz = 0
    nrows = 0
    ncols = 0
    for r in range(m_rows):

        nrows += mats[r * m_cols].shape[0]  # equivalent to mats[r, 0]

        for c in range(m_cols):
            mat = mats[r * m_cols + c]  # equivalent to mats[r, c]
            nnz += mat.indptr[mat.shape[1]]

            if r == 0:
                ncols += mat.shape[1]

    # pass 2: fill in the data
    indptr = np.empty(ncols + 1, dtype=np.int32)
    indices = np.empty(nnz, dtype=np.int32)
    data = np.empty(nnz, dtype=np.float64)
    cnt = 0
    indptr[0] = 0
    offset_col = 0
    for c in range(m_cols):  # for each column of the array of matrices

        n = mats[c].shape[1]  # equivalent to mats[0, c]

        for j in range(n):  # for every column of the column of matrices

            offset_row = 0

            for r in range(m_rows):  # for each row of the array of rows

                mat = mats[r * m_cols + c]  # equivalent to mats[r, c]
                m = mat.shape[0]
                Ap = mat.indptr
                Ai = mat.indices
                Ax = mat.data

                for k in range(Ap[j], Ap[j + 1]):  # for every entry in the column from A
                    indices[cnt] = Ai[k] + offset_row  # row index
                    data[cnt] = Ax[k]
                    cnt += 1

                offset_row += m

            indptr[offset_col + j + 1] = cnt
        offset_col += n

    # return nrows, ncols, indices, indptr, data
    return csc_matrix((data, indices, indptr), shape=(nrows, ncols))


if __name__ == '__main__':
    m = 6
    n = 3
    data = np.array([4, 3, 3, 9, 7, 8, 4, 8, 8, 9]).astype(np.float64)
    indices = np.array([0, 1, 3, 1, 2, 4, 5, 2, 3, 4]).astype(np.int32)
    indptr = np.array([0, 3, 7, 10]).astype(np.int32)

    A = csc_matrix((data, indices, indptr), shape=(m, n))

    list_a = np.array([1, 2, 5])
    list_b = np.array([0, 2])

    A1 = A[np.ix_(list_a, list_b)]
    A2 = sp_slice(A, list_a, list_b)

    ok = np.allclose(A1.toarray(), A2.toarray())

    print(ok)

    A3 = A[list_a, :]
    A4 = sp_slice_rows(A, list_a)

    ok2 = np.allclose(A3.toarray(), A4.toarray())

    print(ok2)
