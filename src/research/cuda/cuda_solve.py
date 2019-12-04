# ### Interface cuSOLVER PyCUDA

import pycuda.gpuarray as gpuarray
import pycuda.driver as cuda
import pycuda.autoinit
import numpy as np
import scipy.sparse as sp
import ctypes

## Wrap the cuSOLVER cusolverSpDcsrlsvqr() using ctypes
## http://docs.nvidia.com/cuda/cusolver/#cusolver-lt-t-gt-csrlsvqr

# cuSparse
_libcusparse = ctypes.cdll.LoadLibrary('libcusparse.so')
_libcusparse.cusparseCreate.restype = int
_libcusparse.cusparseCreate.argtypes = [ctypes.c_void_p]

_libcusparse.cusparseDestroy.restype = int
_libcusparse.cusparseDestroy.argtypes = [ctypes.c_void_p]

_libcusparse.cusparseCreateMatDescr.restype = int
_libcusparse.cusparseCreateMatDescr.argtypes = [ctypes.c_void_p]


# cuSOLVER
_libcusolver = ctypes.cdll.LoadLibrary('libcusolver.so')

_libcusolver.cusolverSpCreate.restype = int
_libcusolver.cusolverSpCreate.argtypes = [ctypes.c_void_p]

_libcusolver.cusolverSpDestroy.restype = int
_libcusolver.cusolverSpDestroy.argtypes = [ctypes.c_void_p]

_libcusolver.cusolverSpDcsrlsvqr.restype = int
_libcusolver.cusolverSpDcsrlsvqr.argtypes= [ctypes.c_void_p,
                                            ctypes.c_int,
                                            ctypes.c_int,
                                            ctypes.c_void_p,
                                            ctypes.c_void_p,
                                            ctypes.c_void_p,
                                            ctypes.c_void_p,
                                            ctypes.c_void_p,
                                            ctypes.c_double,
                                            ctypes.c_int,
                                            ctypes.c_void_p,
                                            ctypes.c_void_p]


def cuspsolve(A, b):
    Acsr = sp.csr_matrix(A, dtype=float)
    b = np.asarray(b, dtype=float)
    x = np.empty_like(b)

    # Copy arrays to GPU
    dcsrVal = gpuarray.to_gpu(Acsr.data)
    dcsrColInd = gpuarray.to_gpu(Acsr.indices)
    dcsrIndPtr = gpuarray.to_gpu(Acsr.indptr)
    dx = gpuarray.to_gpu(x)
    db = gpuarray.to_gpu(b)

    # Create solver parameters
    m = ctypes.c_int(Acsr.shape[0])  # Need check if A is square
    nnz = ctypes.c_int(Acsr.nnz)
    descrA = ctypes.c_void_p()
    reorder = ctypes.c_int(0)
    tol = ctypes.c_double(1e-10)
    singularity = ctypes.c_int(0)  # -1 if A not singular

    # create cusparse handle
    _cusp_handle = ctypes.c_void_p()
    status = _libcusparse.cusparseCreate(ctypes.byref(_cusp_handle))
    assert(status == 0)
    cusp_handle = _cusp_handle.value

    # create MatDescriptor
    status = _libcusparse.cusparseCreateMatDescr(ctypes.byref(descrA))
    assert(status == 0)

    # create cusolver handle
    _cuso_handle = ctypes.c_void_p()
    status = _libcusolver.cusolverSpCreate(ctypes.byref(_cuso_handle))
    assert(status == 0)
    cuso_handle = _cuso_handle.value

    # Solve
    res =_libcusolver.cusolverSpDcsrlsvqr(cuso_handle,
                                          m,
                                          nnz,
                                          descrA,
                                          int(dcsrVal.gpudata),
                                          int(dcsrIndPtr.gpudata),
                                          int(dcsrColInd.gpudata),
                                          int(db.gpudata),
                                          tol,
                                          reorder,
                                          int(dx.gpudata),
                                          ctypes.byref(singularity))
    assert(res == 0)
    if singularity.value != -1:
        raise ValueError('Singular matrix!')
    x = dx.get()  # Get result as numpy array

    # Destroy handles
    status = _libcusolver.cusolverSpDestroy(cuso_handle)
    assert(status == 0)
    status = _libcusparse.cusparseDestroy(cusp_handle)
    assert(status == 0)

    # Return result
    return x


# Test
if __name__ == '__main__':
    A = np.diag(np.arange(1, 5))
    b = np.ones(4)
    x = cuspsolve(A, b)
    np.testing.assert_almost_equal(x, np.array([1., 0.5, 0.33333333, 0.25]))

    # Timing comparison
    from scipy.sparse import rand, diags
    from scipy.sparse.linalg import spsolve
    import time
    n = 1000
    i = j = np.arange(n)
    A = rand(n, n, density=0.001)
    A = A.tocsr()
    A += diags(np.ones(n), shape=(n, n))
    b = np.ones(n)

    t0 = time.time()
    x = spsolve(A, b)
    dt1 = time.time() - t0
    print("scipy.sparse.linalg.spsolve time: %s" %dt1)

    t0 = time.time()
    x = cuspsolve(A, b)
    dt2 = time.time() - t0
    print("cuspsolve time: %s" %dt2)

    ratio = dt1/dt2
    if ratio > 1:
        print("CUDA is %s times faster than CPU." %ratio)
    else:
        print("CUDA is %s times slower than CPU." %(1./ratio))