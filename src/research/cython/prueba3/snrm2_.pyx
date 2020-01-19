cimport numpy as np

cdef extern float snrm2_(int* N, float* X, int* incX)

def snrm2(np.ndarray[float] x):
    cdef int n = len(x)
    cdef int incX = 1

    return snrm2_(&n, <float *>x.data, &incX)