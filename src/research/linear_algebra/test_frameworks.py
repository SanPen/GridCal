import time
import scipy.sparse as sp
from GridCal.Engine import *

# Jacobian and right hand side for the 2869-node Pegase grid
J = sp.load_npz("J.npz")
F = np.load("F.npz")['F']
n, m = J.shape

solver_types = [SparseSolver.BLAS_LAPACK,
                SparseSolver.KLU,
                SparseSolver.SuperLU,
                SparseSolver.ILU,
                # SparseSolver.AMG
                SparseSolver.Pardiso
                ]

for solver_type in solver_types:
    repetitions = 1000
    np.random.seed(0)
    sparse = get_sparse_type(solver_type)
    solver = get_linear_solver(solver_type)
    J2 = sparse(J)

    start = time.time()
    for r in range(repetitions):
        x = solver(J2, F)

    end = time.time()
    dt = end - start
    print(solver_type, '  total', dt, 's, average:', dt / repetitions, 's')
