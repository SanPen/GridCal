# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from typing import Any, Dict

from scipy.sparse import csc_matrix

from VeraGridEngine.basic_structures import Vec
from VeraGridEngine.enumerations import SparseSolver


class SparseLinearFactorizationHandle:
    """
    Abstract sparse factorization handle used by factorisation-reusing sparse backends.

    The factorization handle owns the solver-specific numeric factorization state
    and exposes a uniform solve interface to the solver's factorization manager.
    """

    __slots__ = []

    def solve_into(self, rhs: Vec, out_solution: Vec) -> None:
        """
        Solve the factored sparse system into a caller-owned output buffer.

        :param rhs: Right-hand side vector.
        :type rhs: Vec
        :param out_solution: Caller-owned output buffer.
        :type out_solution: Vec
        :return: None.
        :rtype: None
        """
        raise NotImplementedError()

    def get_active_matrix(self) -> csc_matrix:
        """
        Return the sparse matrix associated with the active factorization path.

        :return: Active sparse matrix.
        :rtype: csc_matrix
        """
        raise NotImplementedError()

    def get_stats(self) -> Dict[str, float]:
        """
        Return factorization-handle statistics.

        :return: Factorization-handle statistics.
        :rtype: Dict[str, float]
        """
        return dict()


class SparseLinearSolverBackend:
    """
    Abstract factorisation-reusing sparse LU backend (EMT today; any Newton-based solver).

    The backend owns solver-specific symbolic and numeric reuse state. VeraGrid
    keeps the solver policy for invalidation and event handling above this layer.
    """

    __slots__ = []

    def get_name(self) -> str:
        """
        Return the human-readable backend name.

        :return: Backend name.
        :rtype: str
        """
        raise NotImplementedError()

    def get_solver_type(self) -> SparseSolver:
        """
        Return the sparse solver type associated with this backend.

        :return: Sparse solver type.
        :rtype: SparseSolver
        """
        raise NotImplementedError()

    def is_available(self) -> bool:
        """
        Return whether the backend can be used in the current process.

        :return: ``True`` when the backend is available.
        :rtype: bool
        """
        raise NotImplementedError()

    def requires_csc(self) -> bool:
        """
        Return whether the backend expects CSC matrices.

        :return: ``True`` when CSC input is required.
        :rtype: bool
        """
        return True

    def supports_symbolic_analysis_reuse(self) -> bool:
        """
        Return whether the backend exposes reusable symbolic analysis.

        :return: ``True`` when symbolic analysis can be reused.
        :rtype: bool
        """
        return False

    def supports_numeric_refactorization(self) -> bool:
        """
        Return whether the backend supports numeric-only refactorization.

        :return: ``True`` when numeric-only refactorization is supported.
        :rtype: bool
        """
        return False

    def analyze(self, matrix: csc_matrix) -> Any | None:
        """
        Perform reusable symbolic analysis on the sparse matrix if supported.

        :param matrix: Sparse matrix in EMT solver order.
        :type matrix: csc_matrix
        :return: Symbolic-analysis handle or ``None``.
        :rtype: Any | None
        """
        _unused_matrix: csc_matrix = matrix
        return None

    def factorize(
            self,
            matrix: csc_matrix,
            analysis_handle: Any | None,
    ) -> SparseLinearFactorizationHandle:
        """
        Build a sparse factorization handle for the current numeric values.

        :param matrix: Sparse matrix in EMT solver order.
        :type matrix: csc_matrix
        :param analysis_handle: Optional symbolic-analysis handle.
        :type analysis_handle: Any | None
        :return: Sparse factorization handle.
        :rtype: SparseLinearFactorizationHandle
        """
        raise NotImplementedError()

    def refactor_numeric(
            self,
            matrix: csc_matrix,
            analysis_handle: Any | None,
            previous_factorization: SparseLinearFactorizationHandle | None,
    ) -> SparseLinearFactorizationHandle | None:
        """
        Rebuild only the numeric factorization when supported.

        :param matrix: Sparse matrix in EMT solver order.
        :type matrix: csc_matrix
        :param analysis_handle: Optional symbolic-analysis handle.
        :type analysis_handle: Any | None
        :param previous_factorization: Previous factorization handle.
        :type previous_factorization: SparseLinearFactorizationHandle | None
        :return: New factorization handle or ``None`` when unsupported.
        :rtype: SparseLinearFactorizationHandle | None
        """
        _unused_matrix: csc_matrix = matrix
        _unused_analysis_handle: Any | None = analysis_handle
        _unused_previous_factorization: SparseLinearFactorizationHandle | None = previous_factorization
        return None

    def get_backend_stats(self) -> Dict[str, float]:
        """
        Return backend-specific statistics.

        :return: Backend-specific statistics.
        :rtype: Dict[str, float]
        """
        return dict()


class SparseLinearSolverBackendProvider:
    """
    Factory object that creates factorisation-reusing sparse LU backends.
    """

    __slots__ = []

    def get_name(self) -> str:
        """
        Return the provider name.

        :return: Provider name.
        :rtype: str
        """
        raise NotImplementedError()

    def get_solver_type(self) -> SparseSolver:
        """
        Return the sparse solver type associated with the provider.

        :return: Sparse solver type.
        :rtype: SparseSolver
        """
        raise NotImplementedError()

    def is_available(self) -> bool:
        """
        Return whether the provider is available.

        :return: ``True`` when the provider is available.
        :rtype: bool
        """
        raise NotImplementedError()

    def get_unavailable_reason(self) -> str:
        """
        Return why the provider is unavailable.

        :return: Reason, or an empty string when available or when the provider gives none.
        :rtype: str
        """
        return ""

    def create_backend(self, base_matrix: csc_matrix, base_data: Vec) -> SparseLinearSolverBackend:
        """
        Create one sparse backend bound to the EMT Jacobian buffers.

        :param base_matrix: Reusable EMT Jacobian CSC shell.
        :type base_matrix: csc_matrix
        :param base_data: Reusable EMT Jacobian numeric buffer.
        :type base_data: Vec
        :return: Sparse solver backend.
        :rtype: SparseLinearSolverBackend
        """
        raise NotImplementedError()
