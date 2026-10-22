# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import numpy as np
from enum import Enum
from typing import Union
from threading import Lock
from collections.abc import Callable
from scipy.sparse import csr_matrix, csc_matrix
from VeraGridEngine.basic_structures import Vec, Mat
from VeraGridEngine.enumerations import SparseSolver
from VeraGridEngine.Compilers.Gslv.activation import GSLV_AVAILABLE, pg
from VeraGridEngine.Utils.optional_dependencies import optional_dependency_failure


# list of available linear algebra frameworks
available_sparse_solvers = list()


# Optional native solvers can fail with ABI errors; register them only after the API loads successfully.
# SciPy remains available when CVXOPT/KLU or Pardiso cannot be imported.
try:
    import cvxopt
except (ImportError, AttributeError, OSError, RuntimeError, ValueError, TypeError) as error:
    optional_dependency_failure("cvxopt", error)
else:
    try:
        from cvxoptklu import klu
        spsolve = klu.linsolve
        available_sparse_solvers.append(SparseSolver.KLU)
    except (ImportError, AttributeError, OSError, RuntimeError, ValueError, TypeError) as error:
        optional_dependency_failure("cvxoptklu", error)


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
except (ImportError, AttributeError, OSError, RuntimeError, ValueError, TypeError) as error:
    optional_dependency_failure("pypardiso", error)


# Activation owns pygslv version and license checks; older builds may lack CLU.
if GSLV_AVAILABLE:
    try:
        pg.clu.Factorizer
    except AttributeError as error:
        optional_dependency_failure("pygslv.clu", error)
    else:
        available_sparse_solvers.append(SparseSolver.CLU)
else:
    pass


preferred_type = SparseSolver.SuperLU

if preferred_type not in available_sparse_solvers:
    if len(available_sparse_solvers) > 0:
        preferred_type = available_sparse_solvers[0]
        # print('Falling back to', preferred_type)
    else:
        raise Exception('No linear algebra solver!!!! VeraGrid cannot work without one.')
# print('Using', preferred_type)


def get_available_sparse_solvers() -> list[SparseSolver]:
    """
    Return a copy of the sparse solvers that are available in the current runtime.

    :return: List of available sparse solver enum values.
    """
    solver_types: list[SparseSolver] = list()
    for solver_type in available_sparse_solvers:
        solver_types.append(solver_type)
    return solver_types


def get_sparse_type(solver_type: SparseSolver = preferred_type):
    """
    GEt sparse matrix type matching the selected sparse linear systems solver
    :param solver_type:
    :return: sparse matrix type
    """
    if solver_type in [SparseSolver.Pardiso, SparseSolver.GMRES]:
        return csr_matrix

    elif solver_type in [SparseSolver.KLU, SparseSolver.CLU, SparseSolver.SuperLU, SparseSolver.ILU, SparseSolver.UMFPACK]:
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


class CluLinearSolver:
    """Retain serial CLU factors for one stream of sparse linear systems.

    Calls detect in-place edits using owned CSC snapshots. One instance serializes
    concurrent calls because the native factorizer owns mutable scratch storage.
    """

    __slots__ = ("_matrix", "_factorizer", "_lock")

    def __init__(self) -> None:
        """Initialize an empty factorization cache.

        :return: None.
        """
        self._matrix: csc_matrix | None = None
        self._factorizer: pg.clu.Factorizer | None = None
        self._lock: Lock = Lock()

    def solve(self, A: csc_matrix, b: Union[Vec, Mat]) -> Union[Vec, Mat]:
        """Solve with resident factors, replaying analysis when values change.

        :param A: Square CSC system matrix; caller storage is never modified.
        :param b: Right hand side vector or matrix.
        :return: Newly allocated solution with the RHS shape.
        :raises ValueError: If dimensions do not match.
        :raises numpy.linalg.LinAlgError: If factorization or solving fails.
        """
        if np.iscomplexobj(A.data) or np.iscomplexobj(b):
            # Serial CLU is real-only; retain complex system support through SuperLU.
            return super_lu_linsolver(A.astype(np.complex128, copy=False), b)
        else:
            rhs: np.ndarray = np.asarray(b, dtype=np.float64)
            if A.shape[0] != A.shape[1] or rhs.ndim not in (1, 2) or rhs.shape[0] != A.shape[0]:
                raise ValueError("CLU requires a square matrix and matching RHS dimensions")
            else:
                matrix: csc_matrix = A.astype(np.float64, copy=False)
                if not matrix.has_canonical_format or np.any(matrix.data == 0.0):
                    # Canonicalize private storage so zeros/duplicates do not inflate analysis.
                    matrix = matrix.copy()
                    matrix.sum_duplicates()
                    matrix.eliminate_zeros()
                    matrix.sort_indices()
                else:
                    pass

                with self._lock:
                    status: pg.clu.Status = pg.clu.Status.success
                    if (self._matrix is None or self._factorizer is None
                            or self._matrix.shape != matrix.shape
                            or not np.array_equal(self._matrix.indptr, matrix.indptr)
                            or not np.array_equal(self._matrix.indices, matrix.indices)):
                        # Analyze each new pattern once, with a verified symmetry guarantee.
                        self._factorizer = None
                        self._matrix = matrix.copy()
                        pattern: csc_matrix = self._matrix.copy()
                        pattern.data.fill(1.0)
                        options: pg.clu.Options = pg.clu.Options()
                        options.symmetric_pattern = (pattern != pattern.T).nnz == 0
                        self._factorizer = pg.clu.Factorizer(pg.clu.MatrixView(self._matrix), options)
                        status = self._factorizer.factorize()
                    elif not np.array_equal(self._matrix.data, matrix.data):
                        # factorize replays retained pivots and repivots if replay fails.
                        np.copyto(self._matrix.data, matrix.data)
                        status = self._factorizer.factorize()
                    else:
                        # Identical coefficients need only triangular solves with resident factors.
                        pass

                    if status != pg.clu.Status.success:
                        # Never leave a failed factorization eligible for a resident solve.
                        self._matrix = None
                        self._factorizer = None
                        raise np.linalg.LinAlgError("CLU factorization failed: " + pg.clu.status_name(status))
                    else:
                        rhs_columns: np.ndarray = rhs.reshape((A.shape[0], 1)) if rhs.ndim == 1 else rhs
                        solution: np.ndarray = np.empty(rhs_columns.shape, dtype=np.float64, order="F")
                        column: int
                        for column in range(rhs_columns.shape[1]):
                            # Write directly into the result, avoiding a native output allocation/copy.
                            status = self._factorizer.solve(
                                np.ascontiguousarray(rhs_columns[:, column]), solution[:, column])
                            if status != pg.clu.Status.success:
                                raise np.linalg.LinAlgError("CLU solve failed: " + pg.clu.status_name(status))
                            else:
                                pass
                        return solution.reshape(rhs.shape)


def clu_linsolver(A: csc_matrix, b: Union[Vec, Mat]) -> Union[Vec, Mat]:
    """Solve once with serial CLU; use get_linear_solver(CLU) for retained factors.

    :param A: Square CSC system matrix.
    :param b: Right hand side vector or matrix.
    :return: Solution with the RHS shape.
    """
    solver: CluLinearSolver = CluLinearSolver()
    return solver.solve(A, b)


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
    Provide the chosen linear solver_type function pointer to
    solver_type linear systems of the type A x = b, with x = f(A,b)
    Retain the returned CLU callable to reuse its analysis and numeric factors.
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

        elif solver_type == SparseSolver.CLU:
            return CluLinearSolver().solve

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
