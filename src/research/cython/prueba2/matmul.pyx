import numpy as np
cimport numpy as np

cdef extern from "cblas.h":
    double ddot "cblas_ddot"(int N,
                             double *X,
                             int incX,
                             double *Y,
                             int incY)

ctypedef np.float64_t dtype_t
def matmul(np.ndarray[dtype_t, ndim=2] A, np.ndarray[dtype_t, ndim=2] B):
    """

    :param A:
    :param B:
    :return:
    """
    cdef Py_ssize_t i, j
    cdef np.ndarray[dtype_t,ndim=2] out = np.zeros((A.shape[0],B.shape[1]))
    cdef np.ndarray[dtype_t, ndim=1] A_row, B_col

    for i in range(A.shape[0]):

        A_row = A[i,:]

        for j in range(B.shape[1]):

            B_col = B[:, j]

            out[i,j] = ddot(A_row.shape[0],
                            <dtype_t*>A_row.data,
                            A_row.strides[0] // sizeof(dtype_t),
                            <dtype_t*>B_col.data,
                            B_col.strides[0] // sizeof(dtype_t))


