import scipy.sparse as sp
from scipy.sparse.linalg import spsolve
import numpy as np
import time
start = time.time()

repetitions = 50
n = 1000
np.random.seed(0)
for r in range(repetitions):
    A = sp.csr_matrix(sp.rand(n, n, 0.01))
    b = np.random.rand(n)
    x = spsolve(A, b)

end = time.time()
dt = end - start
print('total', dt, 'average:', dt/repetitions)


