import numpy as np


# "cimport" is used to import special compile-time information
# about the numpy module (this is stored in a file numpy.pxd which is
# currently part of the Cython distribution).
cimport numpy as np

from cpython cimport array as c_array

from array import array

cimport cython

@cython.boundscheck(False) # turn off bounds-checking for entire function
@cython.wraparound(False)  # turn off negative index wrapping for entire function

#cpdef tuple busca_min_cython9(np.ndarray[double, ndim = 2] malla):
cpdef tuple busca_min_(double [:,:] malla):
    cdef c_array.array minimosx, minimosy
    cdef unsigned int i, j
    cdef unsigned int ii = malla.shape[1]-1
    cdef unsigned int jj = malla.shape[0]-1
    cdef unsigned int start = 1
    #cdef float [:, :] malla_view = malla
    minimosx = array('L', [])
    minimosy = array('L', []) 
    for i in range(start, ii):
        for j in range(start, jj):
            if (malla[j, i] < malla[j-1, i-1] and
                malla[j, i] < malla[j-1, i] and
                malla[j, i] < malla[j-1, i+1] and
                malla[j, i] < malla[j, i-1] and
                malla[j, i] < malla[j, i+1] and
                malla[j, i] < malla[j+1, i-1] and
                malla[j, i] < malla[j+1, i] and
                malla[j, i] < malla[j+1, i+1]):
                minimosx.append(i)
                minimosy.append(j)

    return np.array(minimosx), np.array(minimosy)