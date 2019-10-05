
import numpy as np
from scipy.sparse import csc_matrix
from scipy.sparse.linalg import gmres
import scipy.sparse.linalg as spla


A = csc_matrix([[3, 2, 0], [1, -1, 0], [0, 5, 1]], dtype=float)
b = np.array([2, 4, -1], dtype=float)

n = A.shape[0]

# build the preconditioning matrix
P = spla.inv(A)
M_x = lambda x: spla.spsolve(P, x)
M = spla.LinearOperator((n, n), M_x)

# solve with the preconditioning matrix
x, exit_code = gmres(A, b, M=M)

if exit_code >= 0:
    # 0 indicates successful convergence
    # >0 indicated iterations limit reached
    print(exit_code)
    print("All close", np.allclose(A.dot(x), b))
else:
    print('GMRES Failed')
