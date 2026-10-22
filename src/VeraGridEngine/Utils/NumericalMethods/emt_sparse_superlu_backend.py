# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from typing import Any, Dict

import numba as nb
from numba import types
import numpy as np
from scipy.sparse import csc_matrix
from scipy.sparse.linalg import SuperLU, splu

from VeraGridEngine.Utils.NumericalMethods.external_sparse_solver_interface import (
    SparseLinearFactorizationHandle,
    SparseLinearSolverBackend,
    SparseLinearSolverBackendProvider,
)
from VeraGridEngine.basic_structures import Vec
from VeraGridEngine.enumerations import SparseSolver


def _build_permute_csc_signature() -> Any:
    """
    Return the eager signature of the CSC permutation helper.

    :return: Eager helper signature.
    :rtype: Any
    """
    float64_vector_tpe: Any = types.Array(types.float64, 1, "C")
    int32_vector_tpe: Any = types.Array(types.int32, 1, "C")
    return types.void(float64_vector_tpe, int32_vector_tpe, int32_vector_tpe, int32_vector_tpe, float64_vector_tpe)


def _build_scatter_permuted_solution_signature() -> Any:
    """
    Return the eager signature of the solution scatter helper.

    :return: Eager helper signature.
    :rtype: Any
    """
    float64_vector_tpe: Any = types.Array(types.float64, 1, "C")
    int32_vector_tpe: Any = types.Array(types.int32, 1, "C")
    return types.void(float64_vector_tpe, int32_vector_tpe, float64_vector_tpe)


@nb.jit(_build_permute_csc_signature(), cache=True, fastmath=True)
def _permute_csc_data_by_columns(
        source_data: Vec,
        source_indptr: np.ndarray,
        column_perm: np.ndarray,
        target_indptr: np.ndarray,
        target_data: Vec,
) -> None:
    """
    Reorder CSC numeric values according to a persistent column permutation.

    :param source_data: Numeric values in the original column order.
    :type source_data: Vec
    :param source_indptr: Original CSC column pointer (int32).
    :type source_indptr: np.ndarray
    :param column_perm: Persistent destination-to-source column permutation (int32).
    :type column_perm: np.ndarray
    :param target_indptr: Target CSC column pointer (int32).
    :type target_indptr: np.ndarray
    :param target_data: Destination numeric buffer.
    :type target_data: Vec
    :return: None.
    :rtype: None
    """
    dst_col: int = 0

    while dst_col < column_perm.shape[0]:
        src_col: int = int(column_perm[dst_col])
        src_ptr_0: int = int(source_indptr[src_col])
        src_ptr_1: int = int(source_indptr[src_col + 1])
        dst_ptr_0: int = int(target_indptr[dst_col])
        local_index: int = 0

        while src_ptr_0 + local_index < src_ptr_1:
            target_data[dst_ptr_0 + local_index] = source_data[src_ptr_0 + local_index]
            local_index += 1

        dst_col += 1


@nb.jit(_build_scatter_permuted_solution_signature(), cache=True, fastmath=True)
def _scatter_permuted_solution_to_original_order(
        permuted_solution: Vec,
        inverse_column_perm: np.ndarray,
        out_solution: Vec,
) -> None:
    """
    Scatter a solution computed on a column-permuted system back to original order.

    :param permuted_solution: Solution in permuted order.
    :type permuted_solution: Vec
    :param inverse_column_perm: Mapping from original index to permuted index (int32).
    :type inverse_column_perm: np.ndarray
    :param out_solution: Destination vector in original order.
    :type out_solution: Vec
    :return: None.
    :rtype: None
    """
    var_index: int = 0

    while var_index < out_solution.shape[0]:
        out_solution[var_index] = permuted_solution[int(inverse_column_perm[var_index])]
        var_index += 1


class SuperLUFactorizationHandle(SparseLinearFactorizationHandle):
    """
    Factorization handle backed by SciPy SuperLU.
    """

    __slots__ = ["_lu_obj", "_active_matrix", "_ordered_bundle_active", "_has_persistent_ordering", "_inverse_column_perm"]

    def __init__(
            self,
            lu_obj: SuperLU,
            active_matrix: csc_matrix,
            ordered_bundle_active: bool,
            has_persistent_ordering: bool,
            inverse_column_perm: np.ndarray,
    ) -> None:
        """
        Build the SuperLU factorization handle.

        :param lu_obj: SuperLU factorization object.
        :type lu_obj: SuperLU
        :param active_matrix: Active sparse matrix.
        :type active_matrix: csc_matrix
        :param ordered_bundle_active: Whether the ordered bundle is active.
        :type ordered_bundle_active: bool
        :param has_persistent_ordering: Whether a persistent ordering exists.
        :type has_persistent_ordering: bool
        :param inverse_column_perm: Mapping from original to permuted order.
        :type inverse_column_perm: np.ndarray
        :return: None.
        :rtype: None
        """
        self._lu_obj: SuperLU = lu_obj
        self._active_matrix: csc_matrix = active_matrix
        self._ordered_bundle_active: bool = ordered_bundle_active
        self._has_persistent_ordering: bool = has_persistent_ordering
        self._inverse_column_perm: np.ndarray = inverse_column_perm

    def solve_into(self, rhs: Vec, out_solution: Vec) -> None:
        """
        Solve the sparse system into a caller-owned output buffer.

        :param rhs: Right-hand side vector.
        :type rhs: Vec
        :param out_solution: Caller-owned output buffer.
        :type out_solution: Vec
        :return: None.
        :rtype: None
        """
        raw_solution: Vec = np.asarray(self._lu_obj.solve(rhs), dtype=np.float64)

        if self._ordered_bundle_active and self._has_persistent_ordering:
            _scatter_permuted_solution_to_original_order(raw_solution, self._inverse_column_perm, out_solution)
        else:
            out_solution[:] = raw_solution

    def get_active_matrix(self) -> csc_matrix:
        """
        Return the sparse matrix associated with the current factorization.

        :return: Active sparse matrix.
        :rtype: csc_matrix
        """
        return self._active_matrix


class SuperLUSparseBackend(SparseLinearSolverBackend):
    """
    EMT sparse backend backed by SciPy SuperLU.
    """

    __slots__ = [
        "_base_matrix",
        "_base_data",
        "_base_indptr_i32",
        "_ordered_matrix",
        "_ordered_data",
        "_ordered_indptr_i32",
        "_column_perm",
        "_inverse_column_perm",
        "_has_persistent_ordering",
        "_stats",
    ]

    def __init__(self, base_matrix: csc_matrix, base_data: Vec) -> None:
        """
        Build the SuperLU EMT sparse backend.

        :param base_matrix: Reusable EMT Jacobian CSC shell.
        :type base_matrix: csc_matrix
        :param base_data: Reusable EMT Jacobian numeric buffer.
        :type base_data: Vec
        :return: None.
        :rtype: None
        """
        n_cols: int = int(base_matrix.shape[1])
        identity_perm: np.ndarray = np.arange(n_cols, dtype=np.int32)

        self._base_matrix: csc_matrix = base_matrix
        self._base_data: Vec = base_data
        self._base_indptr_i32: np.ndarray = np.asarray(base_matrix.indptr, dtype=np.int32)
        self._ordered_matrix: csc_matrix | None = None
        self._ordered_data: Vec | None = None
        self._ordered_indptr_i32: np.ndarray | None = None
        self._column_perm: np.ndarray = identity_perm.copy()
        self._inverse_column_perm: np.ndarray = identity_perm.copy()
        self._has_persistent_ordering: bool = False
        self._stats: Dict[str, float] = dict(
            numeric_factorizations=0.0,
            ordering_builds=0.0,
            ordering_reuses=0.0,
            fallback_solves=0.0,
        )

    def get_name(self) -> str:
        """
        Return the backend name.

        :return: Backend name.
        :rtype: str
        """
        return "internal_superlu"

    def get_solver_type(self) -> SparseSolver:
        """
        Return the sparse solver type.

        :return: Sparse solver type.
        :rtype: SparseSolver
        """
        return SparseSolver.SuperLU

    def is_available(self) -> bool:
        """
        Return whether the backend is available.

        :return: ``True``.
        :rtype: bool
        """
        return True

    def supports_symbolic_analysis_reuse(self) -> bool:
        """
        Return whether this backend supports persistent symbolic reuse.

        :return: ``True``.
        :rtype: bool
        """
        return True

    def _try_build_persistent_ordering(self, lu_obj: SuperLU) -> None:
        """
        Store one persistent column ordering discovered by SuperLU.

        :param lu_obj: SuperLU factorization object.
        :type lu_obj: SuperLU
        :return: None.
        :rtype: None
        """
        if self._has_persistent_ordering:
            return
        else:
            pass

        raw_perm: np.ndarray = np.asarray(lu_obj.perm_c, dtype=np.int32)
        n_cols: int = int(self._base_matrix.shape[1])

        if raw_perm.shape[0] != n_cols:
            return
        else:
            pass

        sorted_perm: np.ndarray = np.sort(raw_perm)

        if np.array_equal(sorted_perm, np.arange(n_cols, dtype=np.int32)):
            if np.array_equal(raw_perm, np.arange(n_cols, dtype=np.int32)):
                return
            else:
                self._column_perm = raw_perm.copy()
                inverse_perm: np.ndarray = np.zeros(n_cols, dtype=np.int32)
                perm_index: int = 0

                while perm_index < n_cols:
                    inverse_perm[int(self._column_perm[perm_index])] = perm_index
                    perm_index += 1

                ordered_matrix: csc_matrix = self._base_matrix[:, self._column_perm].copy()
                self._ordered_matrix = ordered_matrix
                self._ordered_data = ordered_matrix.data
                self._ordered_indptr_i32 = np.asarray(ordered_matrix.indptr, dtype=np.int32)
                self._inverse_column_perm = inverse_perm
                self._has_persistent_ordering = True
                self._stats["ordering_builds"] += 1.0
        else:
            return

    def factorize(self, matrix: csc_matrix, analysis_handle: object | None) -> SparseLinearFactorizationHandle:
        """
        Factorize the current EMT Jacobian.

        :param matrix: Sparse matrix in EMT solver order.
        :type matrix: csc_matrix
        :param analysis_handle: Optional symbolic-analysis handle.
        :type analysis_handle: object | None
        :return: SuperLU factorization handle.
        :rtype: SparseLinearFactorizationHandle
        """
        _unused_matrix: csc_matrix = matrix
        _unused_analysis_handle: object | None = analysis_handle
        lu_obj: SuperLU

        if self._has_persistent_ordering and self._ordered_matrix is not None and self._ordered_data is not None and self._ordered_indptr_i32 is not None:
            _permute_csc_data_by_columns(
                self._base_data,
                self._base_indptr_i32,
                self._column_perm,
                self._ordered_indptr_i32,
                self._ordered_data,
            )
            lu_obj = splu(self._ordered_matrix, permc_spec="NATURAL")
            self._stats["ordering_reuses"] += 1.0
            active_matrix: csc_matrix = self._ordered_matrix
            ordered_bundle_active: bool = True
        else:
            lu_obj = splu(self._base_matrix, permc_spec="COLAMD")
            self._try_build_persistent_ordering(lu_obj)
            active_matrix = self._base_matrix
            ordered_bundle_active = False

        self._stats["numeric_factorizations"] += 1.0
        return SuperLUFactorizationHandle(
            lu_obj=lu_obj,
            active_matrix=active_matrix,
            ordered_bundle_active=ordered_bundle_active,
            has_persistent_ordering=self._has_persistent_ordering,
            inverse_column_perm=self._inverse_column_perm,
        )

    def get_backend_stats(self) -> Dict[str, float]:
        """
        Return backend-specific statistics.

        :return: Backend-specific statistics.
        :rtype: Dict[str, float]
        """
        return dict(self._stats)


class SuperLUSparseBackendProvider(SparseLinearSolverBackendProvider):
    """
    Provider for the internal SuperLU EMT sparse backend.
    """

    __slots__ = []

    def get_name(self) -> str:
        """
        Return the provider name.

        :return: Provider name.
        :rtype: str
        """
        return "internal_superlu"

    def get_solver_type(self) -> SparseSolver:
        """
        Return the sparse solver type.

        :return: Sparse solver type.
        :rtype: SparseSolver
        """
        return SparseSolver.SuperLU

    def is_available(self) -> bool:
        """
        Return whether the provider is available.

        :return: ``True``.
        :rtype: bool
        """
        return True

    def create_backend(self, base_matrix: csc_matrix, base_data: Vec) -> SparseLinearSolverBackend:
        """
        Create the internal SuperLU sparse backend.

        :param base_matrix: Reusable EMT Jacobian CSC shell.
        :type base_matrix: csc_matrix
        :param base_data: Reusable EMT Jacobian numeric buffer.
        :type base_data: Vec
        :return: Sparse solver backend.
        :rtype: SparseLinearSolverBackend
        """
        return SuperLUSparseBackend(base_matrix=base_matrix, base_data=base_data)
