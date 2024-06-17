import numpy as np
import numba as nb
from numba_scipy.sparse import CSCMatrixType
from scipy.sparse import csc_matrix


@nb.njit()
def example(mat_):

    return np.sum(mat_.data)


mat = csc_matrix(np.ones((4, 4)))

ret = example(mat)

print(ret)