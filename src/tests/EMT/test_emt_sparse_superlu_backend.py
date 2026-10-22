# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""Compiled permutation kernels, ordering reuse and LSQR fallback of the EMT SuperLU sparse path."""

from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np
import pytest
import scipy.sparse as sp
from scipy.sparse import csc_matrix

import VeraGridEngine.Simulations.EMT.solvers.StructuralVectorizedSolver as structural_vectorized_module
import VeraGridEngine.Simulations.EMT.solvers.structural_compiled_solver as structural_compiled_module
import VeraGridEngine.Utils.NumericalMethods.emt_sparse_superlu_backend as superlu_backend_module
from tests.EMT.test_kundur_emt_initialization import _build_kundur_problem
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.EMT.solvers.StructuralVectorizedSolver import StructuralVectorizedSolver
from VeraGridEngine.Simulations.EMT.solvers.structural_compiled_solver import (
    StructuralCompiledSolver,
    StructuralCompiledSparseFactorizationManager,
)
from VeraGridEngine.Utils.NumericalMethods.emt_sparse_superlu_backend import (
    SuperLUSparseBackend,
    SuperLUSparseBackendProvider,
)
from VeraGridEngine.Utils.NumericalMethods.external_sparse_solver_interface import SparseLinearSolverBackend
from VeraGridEngine.Utils.Symbolic.diagnostic import sparse_lsqr_fallback
from VeraGridEngine.enumerations import DynamicIntegrationMethod


class _RecordingSuperLUProvider(SuperLUSparseBackendProvider):
    """SuperLU provider that keeps every backend it creates so tests can read its statistics."""

    __slots__ = ("backends",)

    def __init__(self) -> None:
        """Create an empty recording provider."""
        super().__init__()
        self.backends: List[SparseLinearSolverBackend] = list()

    def create_backend(self, base_matrix: csc_matrix, base_data: np.ndarray) -> SparseLinearSolverBackend:
        """
        Create and record one SuperLU backend.

        :param base_matrix: Reusable Jacobian CSC shell.
        :param base_data: Reusable Jacobian numeric buffer.
        :return: Created backend.
        """
        backend: SparseLinearSolverBackend = super().create_backend(base_matrix, base_data)
        self.backends.append(backend)
        return backend


def _random_system(n: int, seed: int) -> csc_matrix:
    """
    Build a well-conditioned random sparse system whose COLAMD ordering is not the identity.

    :param n: Matrix size.
    :param seed: Random seed.
    :return: CSC matrix with sorted indices and float64 data.
    """
    matrix: csc_matrix = (sp.random(n, n, density=0.08, random_state=seed, format="csc") + sp.eye(n, format="csc") * 4.0).tocsc()
    matrix.sort_indices()
    return matrix


def _factorize_twice_and_solve(matrix: csc_matrix, rhs: np.ndarray) -> Tuple[np.ndarray, np.ndarray, Dict[str, float]]:
    """
    Factorize, change the values, factorize again (ordering reuse) and solve after each factorisation.

    :param matrix: System matrix; its data buffer is modified in place.
    :param rhs: Right-hand side.
    :return: First solution, second solution and backend statistics.
    """
    backend: SuperLUSparseBackend = SuperLUSparseBackend(matrix, matrix.data)
    first: np.ndarray = np.zeros(matrix.shape[0], dtype=np.float64)
    second: np.ndarray = np.zeros(matrix.shape[0], dtype=np.float64)
    backend.factorize(matrix, None).solve_into(rhs, first)
    matrix.data *= 1.01
    backend.factorize(matrix, None).solve_into(rhs, second)
    return first, second, backend.get_backend_stats()


def test_compiled_kernels_match_interpreted_reference() -> None:
    """The compiled kernels equal their own interpreted bodies bitwise on random inputs."""
    rng: np.random.Generator = np.random.default_rng(20261020)
    for n in (2, 537, 5000):
        permuted: np.ndarray = rng.normal(size=n)
        inverse_perm: np.ndarray = rng.permutation(n).astype(np.int32)
        compiled_out: np.ndarray = np.zeros(n, dtype=np.float64)
        reference_out: np.ndarray = np.zeros(n, dtype=np.float64)
        superlu_backend_module._scatter_permuted_solution_to_original_order(permuted, inverse_perm, compiled_out)
        superlu_backend_module._scatter_permuted_solution_to_original_order.py_func(permuted, inverse_perm, reference_out)
        assert np.array_equal(compiled_out, reference_out)

    matrix: csc_matrix = _random_system(60, 7)
    column_perm: np.ndarray = rng.permutation(60).astype(np.int32)
    ordered: csc_matrix = matrix[:, column_perm].copy()
    source_indptr: np.ndarray = np.asarray(matrix.indptr, dtype=np.int32)
    target_indptr: np.ndarray = np.asarray(ordered.indptr, dtype=np.int32)
    compiled_data: np.ndarray = np.zeros(ordered.data.shape[0], dtype=np.float64)
    reference_data: np.ndarray = np.zeros(ordered.data.shape[0], dtype=np.float64)
    superlu_backend_module._permute_csc_data_by_columns(matrix.data, source_indptr, column_perm, target_indptr, compiled_data)
    superlu_backend_module._permute_csc_data_by_columns.py_func(matrix.data, source_indptr, column_perm, target_indptr, reference_data)
    assert np.array_equal(compiled_data, reference_data)
    assert np.array_equal(compiled_data, ordered.data)


def test_backend_matches_interpreted_reference_on_both_factorisation_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    """The first COLAMD path and the ordering-reuse path are bitwise identical to the interpreted kernels."""
    rhs: np.ndarray = np.random.default_rng(3).normal(size=40)
    compiled_first, compiled_second, stats = _factorize_twice_and_solve(_random_system(40, 4), rhs)
    assert stats["ordering_builds"] >= 1.0
    assert stats["ordering_reuses"] >= 1.0

    monkeypatch.setattr(superlu_backend_module, "_scatter_permuted_solution_to_original_order",
                        superlu_backend_module._scatter_permuted_solution_to_original_order.py_func)
    monkeypatch.setattr(superlu_backend_module, "_permute_csc_data_by_columns",
                        superlu_backend_module._permute_csc_data_by_columns.py_func)
    reference_first, reference_second, reference_stats = _factorize_twice_and_solve(_random_system(40, 4), rhs)
    assert reference_stats == stats
    assert np.array_equal(compiled_first, reference_first)
    assert np.array_equal(compiled_second, reference_second)

    original: csc_matrix = _random_system(40, 4)
    first_error: float = float(np.linalg.norm(original @ compiled_first - rhs) / np.linalg.norm(rhs))
    original.data *= 1.01
    second_error: float = float(np.linalg.norm(original @ compiled_second - rhs) / np.linalg.norm(rhs))
    assert first_error <= 1e-12
    assert second_error <= 1e-12


def test_manager_fallback_solves_in_original_order_after_ordering_reuse() -> None:
    """The LSQR fallback returns the original-order least-squares solution once ordering reuse is active."""
    matrix: csc_matrix = _random_system(40, 4)
    manager: StructuralCompiledSparseFactorizationManager = StructuralCompiledSparseFactorizationManager(matrix, matrix.data)
    manager.factorize()
    matrix.data *= 1.01
    manager.factorize()
    assert manager.get_stats()["ordering_reuses"] >= 1.0

    rhs: np.ndarray = np.random.default_rng(3).normal(size=40)
    fallback: np.ndarray = manager.solve_fallback(rhs).copy()
    expected: np.ndarray = np.asarray(sparse_lsqr_fallback(matrix, rhs), dtype=np.float64)
    assert np.array_equal(fallback, expected)
    assert np.linalg.norm(matrix @ fallback - rhs) / np.linalg.norm(rhs) <= 1e-4

    # The previous behaviour (LSQR on the column-permuted active matrix, not un-permuted) violates the bound.
    permuted_fallback: np.ndarray = np.asarray(sparse_lsqr_fallback(manager.get_active_matrix(), rhs), dtype=np.float64)
    assert np.linalg.norm(matrix @ permuted_fallback - rhs) / np.linalg.norm(rhs) > 1e-4


def test_single_owner_of_kernels_and_fallback_helper() -> None:
    """The solvers use the backend kernels and one shared fallback helper."""
    assert structural_compiled_module._permute_csc_data_by_columns is superlu_backend_module._permute_csc_data_by_columns
    assert structural_compiled_module._scatter_permuted_solution_to_original_order is superlu_backend_module._scatter_permuted_solution_to_original_order
    assert structural_vectorized_module._sparse_factor_manager_fallback is structural_compiled_module._sparse_factor_manager_fallback


@pytest.fixture(scope="module")
def kundur_problem() -> EmtProblemDae:
    """
    Build the self-contained Kundur EMT problem once for this module.

    :return: Kundur EMT problem.
    """
    return _build_kundur_problem()[0]


def test_kundur_structural_compiled_solver_runs_compiled_kernels(kundur_problem: EmtProblemDae) -> None:
    """StructuralCompiledSolver reaches the ordering-reuse path on Kundur and converges."""
    provider: _RecordingSuperLUProvider = _RecordingSuperLUProvider()
    solver: StructuralCompiledSolver = StructuralCompiledSolver(
        kundur_problem, t0=0.0, t_end=0.001, h=5e-6, method=DynamicIntegrationMethod.DaeTrapezoidal,
        verbose=False, sparse_solver_backend_provider=provider,
    )
    converged: bool = solver.simulate()[4]
    assert converged
    assert len(provider.backends) == 1
    stats: Dict[str, float] = provider.backends[0].get_backend_stats()
    assert stats["ordering_builds"] >= 1.0
    assert stats["ordering_reuses"] >= 1.0


def test_kundur_structural_vectorized_solver_runs_compiled_kernels(kundur_problem: EmtProblemDae) -> None:
    """StructuralVectorizedSolver reaches the ordering-reuse path on Kundur and converges."""
    provider: _RecordingSuperLUProvider = _RecordingSuperLUProvider()
    solver: StructuralVectorizedSolver = StructuralVectorizedSolver(
        kundur_problem, t0=0.0, t_end=0.001, h=5e-6, method=DynamicIntegrationMethod.DaeTrapezoidal,
        verbose=False, sparse_solver_backend_provider=provider,
    )
    converged: bool = solver.simulate()[4]
    assert converged
    assert len(provider.backends) == 1
    stats: Dict[str, float] = provider.backends[0].get_backend_stats()
    assert stats["ordering_builds"] >= 1.0
    assert stats["ordering_reuses"] >= 1.0
