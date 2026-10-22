# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Selection of factorisation-reusing sparse LU providers by SparseSolver.

The selected provider is used when it is available; otherwise the reason is
reported and the SciPy SuperLU provider is used, as before. Native runtimes are
imported lazily, by name only, the first time a selection needs them, and the
result is cached for the process; installing a runtime or a GSLV licence takes
effect after restarting VeraGrid. GSLV activation state is read from the
activation module at call time.
"""

from __future__ import annotations

from functools import lru_cache
from types import ModuleType
from typing import Tuple
import warnings

import numpy as np
from scipy.sparse import csc_matrix, spmatrix
from scipy.sparse.linalg import MatrixRankWarning, spsolve

import VeraGridEngine.Compilers.Gslv.activation as gslv_activation
from VeraGridEngine.Utils.NumericalMethods.emt_sparse_superlu_backend import SuperLUSparseBackendProvider
from VeraGridEngine.Utils.NumericalMethods.external_sparse_solver_interface import (
    SparseLinearFactorizationHandle,
    SparseLinearSolverBackend,
    SparseLinearSolverBackendProvider,
)
from VeraGridEngine.Utils.NumericalMethods.native_lu_runtime_backend import (
    NativeLuRuntimeBackendProvider,
    load_native_lu_runtime,
    validate_native_lu_runtime,
)
from VeraGridEngine.basic_structures import Logger, Vec
from VeraGridEngine.enumerations import SparseSolver


@lru_cache(maxsize=1)
def _load_klu_provider() -> NativeLuRuntimeBackendProvider:
    """
    Load the native KLU runtime once per process.

    :return: KLU provider, available or carrying its unavailability reason.
    """
    runtime, reason = load_native_lu_runtime("cvxoptklu._klu_native", "cvxoptklu", "veragrid-cvxoptklu")
    return NativeLuRuntimeBackendProvider("native_klu", SparseSolver.KLU, runtime, reason)


@lru_cache(maxsize=1)
def _load_gslv_provider() -> NativeLuRuntimeBackendProvider:
    """
    Resolve the GSLV sparse LU runtime once per process from the licensed pygslv module.

    :return: GSLV provider, available or carrying its unavailability reason.
    """
    if not gslv_activation.GSLV_AVAILABLE:
        provider: NativeLuRuntimeBackendProvider = NativeLuRuntimeBackendProvider("gslv_sparse_lu", SparseSolver.GSLV, None, "GSLV unavailable: " + gslv_activation.GSLV_UNAVAILABLE_REASON)
    else:
        try:
            runtime: ModuleType = gslv_activation.pg.sparse_lu
        except AttributeError:
            provider = NativeLuRuntimeBackendProvider("gslv_sparse_lu", SparseSolver.GSLV, None,
                                                      "the installed pygslv does not expose the sparse_lu native LU runtime")
        else:
            problem: str = validate_native_lu_runtime(runtime)
            if len(problem) == 0:
                provider = NativeLuRuntimeBackendProvider("gslv_sparse_lu", SparseSolver.GSLV, runtime, "")
            else:
                provider = NativeLuRuntimeBackendProvider("gslv_sparse_lu", SparseSolver.GSLV, None, "pygslv.sparse_lu " + problem)
    return provider


def clear_sparse_lu_provider_cache() -> None:
    """
    Forget the cached native runtime providers (test-isolation hook).

    It does not re-run GSLV activation nor guarantee that a runtime installed after
    a failed import becomes importable; restarting VeraGrid is the supported way.

    :return: None.
    """
    _load_klu_provider.cache_clear()
    _load_gslv_provider.cache_clear()


def get_sparse_lu_provider_status(solver_type: SparseSolver) -> Tuple[SparseLinearSolverBackendProvider | None, str]:
    """
    Return the provider registered for a sparse solver, without any fallback.

    :param solver_type: Requested sparse solver.
    :return: The available provider and an empty reason, or None and the reason it cannot be used.
    """
    if solver_type == SparseSolver.SuperLU:
        result: Tuple[SparseLinearSolverBackendProvider | None, str] = (SuperLUSparseBackendProvider(), "")
    elif solver_type == SparseSolver.KLU or solver_type == SparseSolver.GSLV:
        native: NativeLuRuntimeBackendProvider = _load_klu_provider() if solver_type == SparseSolver.KLU else _load_gslv_provider()
        if native.is_available():
            result = (native, "")
        else:
            result = (None, native.get_unavailable_reason())
    else:
        result = (None, "no factorisation-reusing provider is registered for " + solver_type.value)
    return result


def resolve_sparse_lu_provider(solver_type: SparseSolver, logger: Logger | None) -> SparseLinearSolverBackendProvider:
    """
    Resolve the selected sparse LU provider, falling back to SciPy SuperLU with a reported reason.

    :param solver_type: Requested sparse solver.
    :param logger: Logger receiving the fallback warning; a RuntimeWarning is emitted when None.
    :return: The selected provider when available, otherwise the SciPy SuperLU provider.
    """
    provider, reason = get_sparse_lu_provider_status(solver_type)
    if provider is not None:
        result: SparseLinearSolverBackendProvider = provider
    else:
        message: str = f"Sparse LU solver {solver_type.value} is unavailable: {reason}. Using SciPy SuperLU."
        if logger is None:
            warnings.warn(message, RuntimeWarning, stacklevel=2)
        else:
            logger.add_warning(message)
        result = SuperLUSparseBackendProvider()
    return result


def solve_sparse_system_once(matrix: spmatrix, rhs: Vec, provider: SparseLinearSolverBackendProvider | None) -> Vec:
    """
    Solve one sparse linear system with the selected LU provider, keeping no state.

    A provider that is None or reports SparseSolver.SuperLU solves exactly with
    scipy.sparse.linalg.spsolve, including its in-place canonicalisation of
    ``matrix``. Any other provider factorizes a canonical float64 copy, so
    ``matrix`` is left untouched. A RuntimeError raised by the provider (for
    example, KLU on a singular system) is reported as spsolve reports it: a
    MatrixRankWarning and an all-NaN solution. Other exceptions propagate.

    :param matrix: Square sparse system matrix.
    :param rhs: Right-hand side vector.
    :param provider: Selected sparse LU provider, or None for SciPy SuperLU.
    :return: Solution vector.
    """
    if provider is None or provider.get_solver_type() == SparseSolver.SuperLU:
        solution: Vec = spsolve(matrix, rhs)
    else:
        system: csc_matrix = csc_matrix(matrix).astype(np.float64, copy=True)
        system.sum_duplicates()
        system.sort_indices()
        n_rows: int = int(system.shape[0])
        backend: SparseLinearSolverBackend = provider.create_backend(system, system.data)
        right_hand_side: Vec = np.ascontiguousarray(rhs, dtype=np.float64).ravel()
        solution = np.zeros(n_rows, dtype=np.float64)
        try:
            handle: SparseLinearFactorizationHandle = backend.factorize(system, None)
            handle.solve_into(right_hand_side, solution)
        except RuntimeError:
            warnings.warn("Matrix is exactly singular", MatrixRankWarning, stacklevel=2)
            solution = np.full(n_rows, np.nan, dtype=np.float64)
    return solution
