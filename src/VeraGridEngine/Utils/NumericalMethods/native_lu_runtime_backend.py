# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Sparse LU backends driven by an installed native LU runtime module.

Native LU runtime contract (KLU today, GSLV later). A runtime is a Python module
object located only by import name, exposing:

- ``analyze(indptr, indices, n) -> symbolic``
- ``factorize(indptr, indices, data, symbolic) -> numeric``
- ``refactor(indptr, indices, data, symbolic, numeric) -> numeric``: reuses the pivot
  sequence of ``numeric`` and may update it in place; after a failed refactor the
  previous numeric object must not be used again.
- ``solve_into(numeric, rhs, out) -> None``

Arrays are a canonical CSC pattern (sorted indices, no duplicates) with int32
``indptr`` of length n + 1 and int32 ``indices``, float64 ``data``, and 1-D float64
C-contiguous vectors. Failures raise ``RuntimeError``. A numeric object may depend on
its symbolic object, so callers keep both alive together. Handles are used by one
thread at a time. KLU is provided by ``cvxoptklu._klu_native`` (distribution
``veragrid-cvxoptklu``); GSLV must expose the same contract as the attribute
``pygslv.sparse_lu`` of the licensed ``pygslv`` module.
"""

from __future__ import annotations

import importlib
from types import ModuleType
from typing import Any, Dict, Tuple

import numpy as np
from scipy.sparse import csc_matrix

from VeraGridEngine.Utils.NumericalMethods.external_sparse_solver_interface import (
    SparseLinearFactorizationHandle,
    SparseLinearSolverBackend,
    SparseLinearSolverBackendProvider,
)
from VeraGridEngine.Utils.optional_dependencies import optional_dependency_failure
from VeraGridEngine.basic_structures import Vec
from VeraGridEngine.enumerations import SparseSolver

class NativeLuRuntimeFactorizationHandle(SparseLinearFactorizationHandle):
    """
    Numeric factorization owned by a native LU runtime module, kept together with its symbolic analysis.
    """

    __slots__ = ["_runtime", "_symbolic", "_numeric", "_active_matrix"]

    def __init__(self, runtime: ModuleType, symbolic: Any, numeric: Any, active_matrix: csc_matrix) -> None:
        """
        Wrap one native numeric factorization.

        :param runtime: Native LU runtime module.
        :param symbolic: Symbolic analysis the numeric factorization depends on.
        :param numeric: Opaque numeric factorization returned by the runtime.
        :param active_matrix: Matrix whose values were factorised.
        """
        self._runtime: ModuleType = runtime
        self._symbolic: Any = symbolic
        self._numeric: Any = numeric
        self._active_matrix: csc_matrix = active_matrix

    def get_symbolic(self) -> Any:
        """
        Return the symbolic analysis kept alive by this handle.

        :return: Runtime symbolic handle.
        """
        return self._symbolic

    def get_numeric(self) -> Any:
        """
        Return the opaque numeric factorization.

        :return: Runtime numeric handle.
        """
        return self._numeric

    def solve_into(self, rhs: Vec, out_solution: Vec) -> None:
        """
        Solve with the native factorization into a caller-owned buffer.

        :param rhs: Right-hand side vector.
        :param out_solution: Caller-owned float64 output buffer.
        :return: None.
        """
        self._runtime.solve_into(self._numeric, rhs, out_solution)

    def get_active_matrix(self) -> csc_matrix:
        """
        Return the matrix associated with this factorization.

        :return: Active sparse matrix in original order.
        """
        return self._active_matrix


class NativeLuRuntimeBackend(SparseLinearSolverBackend):
    """
    Sparse backend delegating analysis, factorization, refactorization and solves to a native LU runtime module.
    """

    __slots__ = ["_runtime", "_name", "_solver_type", "_base_matrix", "_base_data", "_indptr", "_indices", "_stats"]

    def __init__(self, runtime: ModuleType, name: str, solver_type: SparseSolver, base_matrix: csc_matrix, base_data: Vec) -> None:
        """
        Bind the backend to one persistent canonical CSC shell.

        :param runtime: Native LU runtime module.
        :param name: Backend name.
        :param solver_type: Sparse solver identity.
        :param base_matrix: Persistent square CSC shell in solver order.
        :param base_data: Live float64 values of ``base_matrix``.
        """
        n_rows: int = int(base_matrix.shape[0])
        if n_rows != int(base_matrix.shape[1]):
            raise ValueError("The native LU runtime requires a square matrix")
        elif not base_matrix.has_canonical_format:
            raise ValueError("The native LU runtime requires a canonical CSC pattern (sorted indices, no duplicates)")
        elif base_data.dtype != np.float64 or base_data.shape[0] != base_matrix.nnz:
            raise ValueError("The native LU runtime requires float64 values matching the CSC pattern")
        elif not np.shares_memory(base_data, base_matrix.data):
            raise ValueError("The native LU runtime requires base_data to be the live values of base_matrix")
        else:
            pass
        self._runtime: ModuleType = runtime
        self._name: str = name
        self._solver_type: SparseSolver = solver_type
        self._base_matrix: csc_matrix = base_matrix
        self._base_data: Vec = base_data
        self._indptr: np.ndarray = np.ascontiguousarray(base_matrix.indptr, dtype=np.int32)
        self._indices: np.ndarray = np.ascontiguousarray(base_matrix.indices, dtype=np.int32)
        self._stats: Dict[str, float] = dict(analyses=0.0, numeric_factorizations=0.0, numeric_refactorizations=0.0)

    def get_name(self) -> str:
        """
        Return the backend name.

        :return: Backend name.
        """
        return self._name

    def get_solver_type(self) -> SparseSolver:
        """
        Return the sparse solver identity.

        :return: Sparse solver type.
        """
        return self._solver_type

    def is_available(self) -> bool:
        """
        Return whether the backend can be used.

        :return: True, since the runtime module is already loaded.
        """
        return True

    def supports_symbolic_analysis_reuse(self) -> bool:
        """
        Return whether the symbolic analysis is reused across factorizations.

        :return: True.
        """
        return True

    def supports_numeric_refactorization(self) -> bool:
        """
        Return whether numeric refactorization with the previous pivot sequence is supported.

        :return: True.
        """
        return True

    def analyze(self, matrix: csc_matrix) -> Any:
        """
        Analyse the persistent sparsity pattern.

        :param matrix: Unused; the backend is bound to its persistent shell.
        :return: Opaque symbolic analysis.
        """
        _unused_matrix: csc_matrix = matrix
        self._stats["analyses"] += 1.0
        return self._runtime.analyze(self._indptr, self._indices, int(self._base_matrix.shape[0]))

    def factorize(self, matrix: csc_matrix, analysis_handle: Any | None) -> SparseLinearFactorizationHandle:
        """
        Factorize the current values of the persistent shell.

        :param matrix: Unused; the backend is bound to its persistent shell.
        :param analysis_handle: Symbolic analysis, or None to analyse first.
        :return: Native factorization handle owning its symbolic analysis.
        """
        _unused_matrix: csc_matrix = matrix
        if analysis_handle is None:
            symbolic: Any = self.analyze(self._base_matrix)
        else:
            symbolic = analysis_handle
        numeric: Any = self._runtime.factorize(self._indptr, self._indices, self._base_data, symbolic)
        self._stats["numeric_factorizations"] += 1.0
        return NativeLuRuntimeFactorizationHandle(self._runtime, symbolic, numeric, self._base_matrix)

    def refactor_numeric(self, matrix: csc_matrix, analysis_handle: Any | None,
                         previous: SparseLinearFactorizationHandle) -> SparseLinearFactorizationHandle | None:
        """
        Refactorize the current values reusing the previous pivot sequence.

        The runtime may update the previous numeric object in place; when this raises,
        the caller must discard ``previous``.

        :param matrix: Unused; the backend is bound to its persistent shell.
        :param analysis_handle: Unused; the symbolic analysis of ``previous`` is reused.
        :param previous: Previous factorization of this backend.
        :return: Refactorized handle, or None when ``previous`` is not a native handle.
        """
        _unused_matrix: csc_matrix = matrix
        _unused_analysis: Any | None = analysis_handle
        if isinstance(previous, NativeLuRuntimeFactorizationHandle):
            numeric: Any = self._runtime.refactor(self._indptr, self._indices, self._base_data, previous.get_symbolic(), previous.get_numeric())
            self._stats["numeric_refactorizations"] += 1.0
            result: SparseLinearFactorizationHandle | None = NativeLuRuntimeFactorizationHandle(self._runtime, previous.get_symbolic(), numeric, self._base_matrix)
        else:
            result = None
        return result

    def get_backend_stats(self) -> Dict[str, float]:
        """
        Return backend statistics.

        :return: Statistics dictionary.
        """
        return dict(self._stats)


class NativeLuRuntimeBackendProvider(SparseLinearSolverBackendProvider):
    """
    Provider of native LU runtime backends for one sparse solver identity.
    """

    __slots__ = ["_name", "_solver_type", "_runtime", "_unavailable_reason"]

    def __init__(self, name: str, solver_type: SparseSolver, runtime: ModuleType | None, unavailable_reason: str) -> None:
        """
        Create the provider.

        :param name: Provider name.
        :param solver_type: Sparse solver identity.
        :param runtime: Loaded native LU runtime module, or None when unavailable.
        :param unavailable_reason: Why the runtime is unavailable; empty when available.
        """
        self._name: str = name
        self._solver_type: SparseSolver = solver_type
        self._runtime: ModuleType | None = runtime
        self._unavailable_reason: str = unavailable_reason

    def get_name(self) -> str:
        """
        Return the provider name.

        :return: Provider name.
        """
        return self._name

    def get_solver_type(self) -> SparseSolver:
        """
        Return the sparse solver identity.

        :return: Sparse solver type.
        """
        return self._solver_type

    def is_available(self) -> bool:
        """
        Return whether the runtime module is loaded.

        :return: True when backends can be created.
        """
        return self._runtime is not None

    def get_unavailable_reason(self) -> str:
        """
        Return why the provider is unavailable.

        :return: Reason, or an empty string when available.
        """
        return self._unavailable_reason

    def create_backend(self, base_matrix: csc_matrix, base_data: Vec) -> SparseLinearSolverBackend:
        """
        Create a backend bound to one persistent CSC shell.

        :param base_matrix: Persistent canonical square CSC shell.
        :param base_data: Live float64 values of ``base_matrix``.
        :return: Native LU runtime backend.
        """
        if self._runtime is None:
            raise RuntimeError(f"Sparse LU solver {self._solver_type.value} is unavailable: {self._unavailable_reason}")
        else:
            return NativeLuRuntimeBackend(self._runtime, self._name, self._solver_type, base_matrix, base_data)


def validate_native_lu_runtime(runtime: Any) -> str:
    """
    Check that an object exposes the native LU runtime contract.

    :param runtime: Candidate runtime object.
    :return: Empty string when complete, otherwise a description of the missing part.
    """
    try:
        complete: bool = (callable(runtime.analyze) and callable(runtime.factorize)
                          and callable(runtime.refactor) and callable(runtime.solve_into))
    except AttributeError as error:
        problem: str = "does not implement the native LU contract (" + str(error) + ")"
    else:
        if complete:
            problem = ""
        else:
            problem = "exposes non-callable native LU contract members"
    return problem


def load_native_lu_runtime(module_name: str, top_level_module: str, distribution_name: str) -> Tuple[ModuleType | None, str]:
    """
    Import a native LU runtime module by name and validate its contract.

    Never raises for third-party failures: a missing package, a broken installation or
    an incomplete contract is returned as the unavailability reason.

    :param module_name: Import name of the runtime module.
    :param top_level_module: Top-level import name whose absence means "not installed".
    :param distribution_name: Distribution to name in diagnostics and to read the installed version from.
    :return: Loaded module (or None) and the unavailability reason (empty when loaded).
    """
    try:
        runtime: ModuleType = importlib.import_module(module_name)
    except ModuleNotFoundError as error:
        if error.name == top_level_module:
            result: Tuple[ModuleType | None, str] = (None, f"{distribution_name} is not installed; install it in this Python environment and restart VeraGrid")
        else:
            result = (None, optional_dependency_failure(distribution_name, error))
    except (ImportError, AttributeError, OSError, RuntimeError, ValueError, TypeError, SystemError) as error:
        result = (None, optional_dependency_failure(distribution_name, error))
    else:
        problem: str = validate_native_lu_runtime(runtime)
        if len(problem) == 0:
            result = (runtime, "")
        else:
            result = (None, module_name + " " + problem)
    return result
