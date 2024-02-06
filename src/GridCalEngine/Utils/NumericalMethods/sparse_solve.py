# -*- coding: utf-8 -*-
# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
import numpy as np
from enum import Enum
from typing import Union
from collections.abc import Callable
from scipy.sparse import csr_matrix, csc_matrix
from GridCalEngine.basic_structures import Vec, Mat
from GridCalEngine.enumerations import SparseSolver


# list of available linear algebra frameworks
available_sparse_solvers = list()


try:
    import cvxopt
    from cvxoptklu import klu
    spsolve = klu.linsolve

    available_sparse_solvers.append(SparseSolver.KLU)
except ImportError:
    pass
    # print(SparseSolver.KLU.value + ' failed')


try:
    from scipy.sparse.linalg import spsolve as scipy_spsolve, splu, spilu, gmres, spsolve_triangular
    available_sparse_solvers.append(SparseSolver.UMFPACK)  # default linsolve solver
    available_sparse_solvers.append(SparseSolver.ILU)
    available_sparse_solvers.append(SparseSolver.SuperLU)
    available_sparse_solvers.append(SparseSolver.GMRES)
    available_sparse_solvers.append(SparseSolver.UMFPACKTriangular)
except ImportError:
    pass
    # print(SparseSolver.BLAS_LAPACK.value + ' failed')


try:
    from pypardiso import spsolve as pardiso_spsolve

    available_sparse_solvers.append(SparseSolver.Pardiso)  # pypardiso
except ImportError:
    pass
    # print(SparseSolver.Pardiso.value + ' failed')


preferred_type = SparseSolver.SuperLU

if preferred_type not in available_sparse_solvers:
    if len(available_sparse_solvers) > 0:
        preferred_type = available_sparse_solvers[0]
        # print('Falling back to', preferred_type)
    else:
        raise Exception('No linear algebra solver!!!! GridCal cannot work without one.')
# print('Using', preferred_type)


def get_sparse_type(solver_type: SparseSolver = preferred_type):
    """
    GEt sparse matrix type matching the selected sparse linear systems solver
    :param solver_type:
    :return: sparse matrix type
    """
    if solver_type in [SparseSolver.Pardiso, SparseSolver.GMRES]:
        return csr_matrix

    elif solver_type in [SparseSolver.KLU, SparseSolver.SuperLU, SparseSolver.ILU, SparseSolver.UMFPACK]:
        return csc_matrix

    else:
        raise Exception('Unknown solver' + str(solver_type))


def super_lu_linsolver(A: csc_matrix, b: Union[Vec, Mat]) -> Union[Vec, Mat]:
    """
    SuperLU wrapper function for linear system solve A x = b
    :param A: System matrix
    :param b: right hand side
    :return: solution
    """
    return splu(A).solve(b)


def ilu_linsolver(A: csc_matrix, b: Union[Vec, Mat]) -> Union[Vec, Mat]:
    """
    ILU wrapper function for linear system solve A x = b
    :param A: System matrix
    :param b: right hand side
    :return: solution
    """
    return spilu(A).solve(b)


def klu_linsolve(A: csc_matrix, b: Union[Vec, Mat]) -> Union[Vec, Mat]:
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


def gmres_linsolve(A: csc_matrix, b: Union[Vec, Mat]) -> Union[Vec, Mat]:
    """

    :param A:
    :param b:
    :return:
    """
    x, info = gmres(A, b)
    return x


def get_linear_solver(solver_type: SparseSolver = preferred_type) -> Callable[[csc_matrix, Union[Vec, Mat]], Union[Vec, Mat]]:
    """
    Privide the chosen linear solver_type function pointer to
    solver_type linear systems of the type A x = b, with x = f(A,b)
    :param solver_type: SparseSolver option
    :return: function pointer f(A, b)
    """
    if solver_type in available_sparse_solvers:

        if solver_type == SparseSolver.UMFPACK:
            return scipy_spsolve

        elif solver_type == SparseSolver.UMFPACKTriangular:
            return spsolve_triangular

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

        else:
            raise Exception('Unrecognized LU solver')

    else:
        return scipy_spsolve

