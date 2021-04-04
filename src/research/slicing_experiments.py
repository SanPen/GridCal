import random
import numpy as np
from scipy.sparse import csc_matrix, lil_matrix


def binary_search(array, x):
    """
    Binary search
    :param array: array: Must be sorted
    :param x: value to search
    :return: position where it is found, -1 if not found
    """
    lower = 0
    upper = len(array)
    while lower < upper:   # use < instead of <=
        mid = lower + (upper - lower) // 2  # // is the integer division
        val = array[mid]
        if x == val:
            return mid
        elif x > val:
            if lower == mid:
                break
            lower = mid
        elif x < val:
            upper = mid

    return -1


def slice(A: csc_matrix, rows, cols):
    """
    CSC matrix sub-matrix view
    :param A: CSC matrix to get the view from
    :param rows: array of selected rows: must be sorted! to use the binary search
    :param cols: array of columns: should be sorted
    :return:
    """
    n_rows = len(rows)
    n_cols = len(cols)

    n = 0
    p = 0
    new_val = np.empty(A.nnz)
    new_row_ind = np.empty(A.nnz)
    new_col_ptr = np.empty(n_cols + 1)
    new_col_ptr[p] = 0

    for j in cols:  # sliced columns

        for k in range(A.indptr[j], A.indptr[j + 1]):  # columns from A

            found_idx = binary_search(rows, A.indices[k])  # look for the row index of A in the rows vector

            if found_idx > -1:
                new_val[n] = A.data[k]
                new_row_ind[n] = found_idx
                n += 1

        p += 1
        new_col_ptr[p] = n

    new_col_ptr[p] = n

    new_val = np.resize(new_val, n)
    new_row_ind = np.resize(new_row_ind, n)
    return csc_matrix((new_val, new_row_ind, new_col_ptr), shape=(n_rows, n_cols))


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
    new_val = np.empty(Annz)
    new_row_ind = np.empty(Annz)
    new_col_ptr = np.empty(n_cols + 1)
    new_col_ptr[p] = 0

    # generate lookup -> index lookup
    lookup = np.zeros(Am, dtype=int)
    lookup[rows] = np.arange(len(rows), dtype=int)

    for j in cols:  # sliced columns

        for k in range(Ap[j], Ap[j + 1]):  # columns from A

            # row index translation to the "rows" space
            i = Ai[k]
            ii = lookup[i]

            if rows[ii] == i:
                # entry found
                new_val[nnz] = Ax[k]
                new_row_ind[nnz] = ii
                nnz += 1

        p += 1
        new_col_ptr[p] = nnz

    new_col_ptr[p] = nnz
    new_val = np.resize(new_val, nnz)
    new_row_ind = np.resize(new_row_ind, nnz)

    return new_val, new_row_ind, new_col_ptr, n_rows, n_cols


def slice2(A: csc_matrix, rows, cols):
    """
    CSC matrix sub-matrix view
    :param A: CSC matrix to get the view from
    :param rows: array of selected rows: must be sorted! to use the binary search
    :param cols: array of columns: should be sorted
    :return:
    """

    new_val, new_row_ind, new_col_ptr, n_rows, n_cols = csc_sub_matrix(Am=A.shape[0], Annz=A.nnz,
                                                                       Ap=A.indptr, Ai=A.indices, Ax=A.data,
                                                                       rows=rows, cols=cols)

    return csc_matrix((new_val, new_row_ind, new_col_ptr), shape=(n_rows, n_cols))


def slice_r(A: csc_matrix, rows):
    """
    CSC matrix sub-matrix view
    :param A: CSC matrix to get the view from
    :param rows: array of selected rows: must be sorted! to use the binary search
    :return:
    """
    n_rows = len(rows)
    n_cols = A.shape[1]

    n = 0
    p = 0
    new_val = np.empty(A.nnz)
    new_row_ind = np.empty(A.nnz)
    new_col_ptr = np.empty(n_cols + 1)
    new_col_ptr[p] = 0

    for j in range(n_cols):  # sliced columns

        for k in range(A.indptr[j], A.indptr[j + 1]):  # columns from A

            found_idx = binary_search(rows, A.indices[k])  # look for the row index of A in the rows vector

            if found_idx > -1:
                new_val[n] = A.data[k]
                new_row_ind[n] = found_idx
                n += 1

        p += 1
        new_col_ptr[p] = n

    new_col_ptr[p] = n

    new_val = np.resize(new_val, n)
    new_row_ind = np.resize(new_row_ind, n)
    return csc_matrix((new_val, new_row_ind, new_col_ptr), shape=(n_rows, n_cols))


def slice_c(A: csc_matrix, cols):
    """
    CSC matrix sub-matrix view
    :param A: CSC matrix to get the view from
    :param cols: array of columns: should be sorted
    :return:
    """
    n_rows = A.shape[0]
    n_cols = len(cols)

    n = 0
    p = 0
    new_val = np.empty(A.nnz)
    new_row_ind = np.empty(A.nnz)
    new_col_ptr = np.empty(n_cols + 1)
    new_col_ptr[p] = 0

    for j in cols:  # sliced columns
        st = A.indptr[j]
        nd = A.indptr[j + 1]
        for k in range(st, nd):  # columns from A
            new_val[n] = A.data[k]
            new_row_ind[n] = A.indices[k]
            n += 1

        p += 1
        new_col_ptr[p] = n

    new_col_ptr[p] = n

    new_val = np.resize(new_val, n)
    new_row_ind = np.resize(new_row_ind, n)
    return csc_matrix((new_val, new_row_ind, new_col_ptr), shape=(n_rows, n_cols))


def _minor_index_fancy(A, idx):
    """
    Rows of a CSC matrix
    :param A:
    :param idx:
    :return:
    """

    """Index along the minor axis where idx is an array of ints.
    """
    idx_dtype = A.indices.dtype
    idx = np.asarray(idx, dtype=idx_dtype).ravel()

    M, N = A._swap(A.shape)
    k = len(idx)
    new_shape = A._swap((M, k))
    if k == 0:
        return A.__class__(new_shape)

    # pass 1: count idx entries and compute new indptr
    col_offsets = np.zeros(N, dtype=idx_dtype)
    res_indptr = np.empty_like(A.indptr)
    csr_column_index1(k, idx, M, N, A.indptr, A.indices,
                      col_offsets, res_indptr)

    # pass 2: copy indices/data for selected idxs
    col_order = np.argsort(idx).astype(idx_dtype, copy=False)
    nnz = res_indptr[-1]
    res_indices = np.empty(nnz, dtype=idx_dtype)
    res_data = np.empty(nnz, dtype=A.dtype)
    csr_column_index2(col_order, col_offsets, len(A.indices),
                      A.indices, A.data, res_indices, res_data)
    return csc_matrix((res_data, res_indices, res_indptr), shape=new_shape, copy=False)


if __name__ == '__main__':

    # binary search test
    array_ = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    r = binary_search(array_, 4)

    # Slicing test
    nn = 7
    random.seed(0)
    mat = lil_matrix((nn, nn))
    for i in range(nn):
        mat[i, i] = i + 1

        a = random.randint(0, nn-1)
        b = random.randint(0, nn-1)
        mat[a, b] = 8

    mat = mat.tocsc()
    cols_ = [1, 2, 5, 6]
    rows_ = [2, 3, 6]
    mat2 = slice(A=mat, rows=rows_, cols=cols_)
    mat5 = slice2(A=mat, rows=rows_, cols=cols_)
    mat3 = slice_r(A=mat, rows=rows_)
    mat4 = slice_c(A=mat, cols=cols_)

    slc = mat[np.ix_(rows_, cols_)]

    # check that the slicing is ok
    print('-' * 80)
    print('Col + Row slicing with binary search')
    check1 = np.all(mat2.todense() == mat[rows_, :][:, cols_].todense())
    print('Original:\n', mat.todense())
    print('cols:', cols_)
    print('rows:', rows_)
    print('Sliced:\n', mat2.todense())
    print('pass', check1)
    print('-' * 80)

    # check that the slicing is ok
    print('Col + Row slicing with lookup array')
    check5 = np.all(mat5.todense() == mat[rows_, :][:, cols_].todense())
    print('Original:\n', mat.todense())
    print('cols:', cols_)
    print('rows:', rows_)
    print('Sliced:\n', mat5.todense())
    print('pass', check5)
    print('-' * 80)

    print('Row slicing')
    check2 = np.all(mat3.todense() == mat[rows_, :].todense())
    print('Original:\n', mat.todense())
    print('cols:', cols_)
    print('rows:', rows_)
    print('Sliced:\n', mat3.todense())
    print('pass', check2)
    print('-' * 80)

    print('Column slicing')
    check3 = np.all(mat4.todense() == mat[:, cols_].todense())
    print('Original:\n', mat.todense())
    print('cols:', cols_)
    print('rows:', rows_)
    print('Sliced:\n', mat4.todense())
    print('pass', check3)

    print('-' * 80)
    print('all pass', check3 and check2 and check1 and check5)
