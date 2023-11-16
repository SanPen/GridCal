import time
import scipy.sparse as sp
from GridCalEngine.api import *

solver_types = [SparseSolver.BLAS_LAPACK,
                SparseSolver.KLU,
                SparseSolver.SuperLU,
                SparseSolver.ILU,
                SparseSolver.UMFPACK
                ]

for solver_type_ in solver_types:
    start = time.time()
    repetitions = 50
    n = 4000
    np.random.seed(0)

    sparse = get_sparse_type(solver_type_)
    solver = get_linear_solver(solver_type_)

    for r in range(repetitions):
        A = sparse(sp.rand(n, n, 0.01)) + sp.diags(np.random.rand(n) * 10.0, shape=(n, n))
        b = np.random.rand(n)
        x = solver(A, b)

    end = time.time()
    dt = end - start
    print(solver_type_, '  total', dt, 's, average:', dt / repetitions, 's')