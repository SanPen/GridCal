# -*- coding: utf-8 -*-
# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.
import numpy as np
from enum import Enum
from scipy.sparse import csr_matrix, csc_matrix


class SparseSolver(Enum):
    BLAS_LAPACK = 'Blas/Lapack'
    ILU = 'ILU'
    KLU = 'KLU'
    SuperLU = 'SuperLU'
    Pardiso = 'Pardiso'
    GMRES = 'GMRES'
    AMG = 'Algebraic Multigrid'

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
    from scipy.sparse.linalg import spsolve as scipy_spsolve, splu, spilu, gmres
    available_sparse_solvers.append(SparseSolver.BLAS_LAPACK)
    available_sparse_solvers.append(SparseSolver.ILU)
    available_sparse_solvers.append(SparseSolver.SuperLU)
    available_sparse_solvers.append(SparseSolver.GMRES)
except ImportError:
    print('Blas/Lapack failed')


try:
    from pypardiso import spsolve as pardiso_spsolve

    available_sparse_solvers.append(SparseSolver.Pardiso)
except ImportError:
    print('Pardiso failed')

try:
    import pyamg

    available_sparse_solvers.append(SparseSolver.AMG)
except ImportError:
    print('AMG failed')


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
    if solver_type in [SparseSolver.BLAS_LAPACK, SparseSolver.Pardiso, SparseSolver.GMRES, SparseSolver.AMG]:
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


def gmres_linsolve(A, b):
    """

    :param A:
    :param b:
    :return:
    """
    x, info = gmres(A, b)
    return x


def amg_linsolve(A, b):
    """

    :param A:
    :param b:
    :return:
    """
    ml = pyamg.smoothed_aggregation_solver(A)  # construct the multigrid hierarchy
    return ml.solve(b, tol=1e-5)


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

    elif solver_type == SparseSolver.GMRES:
            return gmres_linsolve

    elif solver_type == SparseSolver.AMG:
            return amg_linsolve


if __name__ == '__main__':

    import time
    import scipy.sparse as sp

    solver_types = [SparseSolver.BLAS_LAPACK,
                    # SparseSolver.KLU,
                    # SparseSolver.SuperLU,
                    # SparseSolver.ILU,
                    SparseSolver.AMG
                    ]

    for solver_type in solver_types:
        start = time.time()
        repetitions = 50
        n = 1000
        np.random.seed(0)

        sparse = get_sparse_type(solver_type)
        solver = get_linear_solver(solver_type)

        for r in range(repetitions):
            A = sparse(sp.rand(n, n, 0.01)) + sp.diags(np.random.rand(n) * 10.0, shape=(n, n))
            b = np.random.rand(n)
            x = solver(A, b)

        end = time.time()
        dt = end - start
        print(solver_type, '  total', dt, 's, average:', dt / repetitions, 's')
