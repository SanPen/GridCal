# Copyright (c) 1996-2015 PSERC. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE_MATPOWER file.

# Copyright 1996-2015 PSERC. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

# Copyright (c) 2018 Santiago Peñate Vera
#
# This file retains the BSD-Style license
import numpy as np
from enum import Enum
from scipy.sparse import csr_matrix, csc_matrix


class SparseSolver(Enum):
    BLAS_LAPACK = 'Blas/Lapack'
    ILU = 'ILU'
    KLU = 'KLU'
    SuperLU = 'SuperLU'
    Pardiso = 'Pardiso'

    def __str__(self):
        return self.value


# list of available linear algebra frameworks
available_sparse_solvers = list()


try:
    import cvxopt
    from cvxoptklu import klu
    spsolve = klu.linsolve

    available_sparse_solvers.append(SparseSolver.KLU)
except ImportError:
    print('KLU failed')


try:
    from scipy.sparse.linalg import spsolve as scipy_spsolve, splu, spilu
    available_sparse_solvers.append(SparseSolver.BLAS_LAPACK)
    available_sparse_solvers.append(SparseSolver.ILU)
    available_sparse_solvers.append(SparseSolver.SuperLU)
except ImportError:
    print('Blas/Lapack failed')


try:
    from pypardiso import spsolve as pardiso_spsolve

    available_sparse_solvers.append(SparseSolver.Pardiso)
except ImportError:
    print('Pardiso failed')


preferred_type = SparseSolver.BLAS_LAPACK

if preferred_type not in available_sparse_solvers:
    if len(available_sparse_solvers) > 0:
        preferred_type = available_sparse_solvers[0]
        print('Falling back to', preferred_type)
    else:
        raise Exception('No linear algebra solver!!!! GridCal cannot work without one.')
print('Using', preferred_type)


def get_sparse_type(solver_type: SparseSolver = preferred_type):
    """
    GEt sparse matrix type matching the selected sparse linear systems solver
    :param solver_type:
    :return: sparse matrix type
    """
    if solver_type in [SparseSolver.BLAS_LAPACK, SparseSolver.Pardiso]:
        return csr_matrix

    elif solver_type in [SparseSolver.KLU, SparseSolver.SuperLU, SparseSolver.ILU]:
        return csc_matrix

    else:
        raise Exception('Unknown solver' + str(solver_type))


def super_lu_linsolver(A, b):
    """
    SuperLU wrapper function for linear system solve A x = b
    :param A: System matrix
    :param b: right hand side
    :return: solution
    """
    return splu(A).solve(b)


def ilu_linsolver(A, b):
    """
    ILU wrapper function for linear system solve A x = b
    :param A: System matrix
    :param b: right hand side
    :return: solution
    """
    return spilu(A).solve(b)


def klu_linsolve(A, b):
    """
    KLU wrapper function for linear system solve A x = b
    :param A: System matrix
    :param b: right hand side
    :return: solution
    """
    A2 = A.tocoo()
    A_cvxopt = cvxopt.spmatrix(A2.data, A2.row, A2.col, A2.shape, 'd')
    x = cvxopt.matrix(b)
    klu.linsolve(A_cvxopt, x)
    return np.array(x)[:, 0]


def get_linear_solver(solver_type: SparseSolver = preferred_type):
    """
    Privide the chosen linear solver function pointer to solver linear systems of the type A x = b, with x = f(A,b)
    :param solver_type: SparseSolver option
    :return: function pointer f(A, b)
    """
    if solver_type == SparseSolver.BLAS_LAPACK:
        return scipy_spsolve

    elif solver_type == SparseSolver.KLU:
        return klu_linsolve

    elif solver_type == SparseSolver.SuperLU:
        return super_lu_linsolver

    elif solver_type == SparseSolver.Pardiso:
        return pardiso_spsolve

    elif solver_type == SparseSolver.ILU:
        return ilu_linsolver
