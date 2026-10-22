# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""Sparse LU selection in the RMS Backward Euler solvers, the RMS driver and the small-signal pre-simulation.

The tests observe the solvers through explicit test objects (counting provider wrappers and a recording factory)
passed through the public construction paths.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import numpy as np
import pytest
import scipy.sparse as sp
from scipy.sparse import csc_matrix
from scipy.sparse.linalg import MatrixRankWarning, spsolve, splu

import VeraGridEngine.Utils.NumericalMethods.sparse_lu_selection as sparse_selection
from tests.Base.test_dynamic_results_save_load import _build_rms_driver
from VeraGridEngine.Devices.Events.rms_event import RmsEvent
from VeraGridEngine.Devices.Events.rms_events_group import RmsEventsGroup
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Simulations.Rms.initialization_rms import solve_rms_newton_correction
from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx import BackEulerImplicitIntegration
from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx_full_vectorized import BackEulerImplicitIntegrationFullVec
from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx_vectorized import BackEulerImplicitIntegrationVec
from VeraGridEngine.Simulations.Rms.problems.rms_problem_template import RmsProblemTemplate
from VeraGridEngine.Simulations.Rms.rms_driver import RmsSimulationDriver
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Simulations.Rms.rms_problem_factory import build_rms_problem
from VeraGridEngine.Simulations.SmallSignalStabilityRms.small_signal_driver import SmallSignalStabilityRmsDriver
from VeraGridEngine.Simulations.SmallSignalStabilityRms.small_signal_options import RmsSmallSignalStabilityOptions
from VeraGridEngine.Utils.NumericalMethods.emt_sparse_superlu_backend import SuperLUSparseBackendProvider
from VeraGridEngine.Utils.NumericalMethods.external_sparse_solver_interface import (
    SparseLinearFactorizationHandle,
    SparseLinearSolverBackend,
    SparseLinearSolverBackendProvider,
)
from VeraGridEngine.Utils.NumericalMethods.native_lu_runtime_backend import NativeLuRuntimeBackendProvider
from VeraGridEngine.basic_structures import Logger, Mat, Vec
from VeraGridEngine.enumerations import (
    DynamicIntegrationMethod,
    LogSeverity,
    RmsInitializationMethod,
    RmsProblemTypes,
    SparseSolver,
)


class CountingScipyLuRuntime:
    """
    SciPy-backed object implementing the native LU runtime contract and counting its solves.
    """

    __slots__ = ("solves",)

    def __init__(self) -> None:
        """
        Create the fake runtime with no solves recorded.
        """
        self.solves: int = 0

    def analyze(self, indptr: np.ndarray, indices: np.ndarray, n: int) -> Dict[str, Any]:
        """
        Remember the matrix size as the symbolic analysis.

        :param indptr: CSC column pointer.
        :param indices: CSC row indices.
        :param n: Matrix size.
        :return: Symbolic object.
        """
        return {"n": n, "nnz": int(indices.shape[0]), "columns": int(indptr.shape[0]) - 1}

    def factorize(self, indptr: np.ndarray, indices: np.ndarray, data: np.ndarray, symbolic: Dict[str, Any]) -> Any:
        """
        Factorize with SciPy SuperLU.

        :param indptr: CSC column pointer.
        :param indices: CSC row indices.
        :param data: CSC values.
        :param symbolic: Symbolic object.
        :return: SciPy SuperLU object.
        """
        return splu(csc_matrix((data.copy(), indices.copy(), indptr.copy()), shape=(symbolic["n"], symbolic["n"])))

    def refactor(self, indptr: np.ndarray, indices: np.ndarray, data: np.ndarray, symbolic: Dict[str, Any], numeric: Any) -> Any:
        """
        Refactorize by factorizing again.

        :param indptr: CSC column pointer.
        :param indices: CSC row indices.
        :param data: CSC values.
        :param symbolic: Symbolic object.
        :param numeric: Previous numeric object (unused).
        :return: New SciPy SuperLU object.
        """
        _unused_numeric: Any = numeric
        return self.factorize(indptr, indices, data, symbolic)

    def solve_into(self, numeric: Any, rhs: np.ndarray, out: np.ndarray) -> None:
        """
        Solve into the caller buffer and count the solve.

        :param numeric: SciPy SuperLU object.
        :param rhs: Right-hand side.
        :param out: Output buffer.
        :return: None.
        """
        self.solves += 1
        out[:] = numeric.solve(rhs)


class CountingProvider(SparseLinearSolverBackendProvider):
    """
    Test-only provider wrapper that counts the factorizations and solves of the backends it creates.
    """

    __slots__ = ("_provider", "factorizations", "solves")

    def __init__(self, provider: SparseLinearSolverBackendProvider) -> None:
        """
        Wrap a provider.

        :param provider: Provider whose backends are counted.
        """
        self._provider: SparseLinearSolverBackendProvider = provider
        self.factorizations: int = 0
        self.solves: int = 0

    def get_name(self) -> str:
        """
        Return the wrapped provider name.

        :return: Provider name.
        """
        return self._provider.get_name()

    def get_solver_type(self) -> SparseSolver:
        """
        Return the wrapped solver type.

        :return: Sparse solver type.
        """
        return self._provider.get_solver_type()

    def is_available(self) -> bool:
        """
        Return whether the wrapped provider is available.

        :return: Availability.
        """
        return self._provider.is_available()

    def get_unavailable_reason(self) -> str:
        """
        Return the wrapped provider unavailability reason.

        :return: Reason, empty when available.
        """
        return self._provider.get_unavailable_reason()

    def create_backend(self, base_matrix: csc_matrix, base_data: Vec) -> SparseLinearSolverBackend:
        """
        Create a counting backend around the wrapped provider's backend.

        :param base_matrix: CSC shell.
        :param base_data: Live values of the shell.
        :return: Counting backend.
        """
        return CountingBackend(self._provider.create_backend(base_matrix, base_data), self)


class CountingHandle(SparseLinearFactorizationHandle):
    """
    Test-only factorization handle wrapper that counts solves on its provider wrapper.
    """

    __slots__ = ("_handle", "_counter")

    def __init__(self, handle: SparseLinearFactorizationHandle, counter: CountingProvider) -> None:
        """
        Wrap a factorization handle.

        :param handle: Wrapped handle.
        :param counter: Provider wrapper receiving the counts.
        """
        self._handle: SparseLinearFactorizationHandle = handle
        self._counter: CountingProvider = counter

    def solve_into(self, rhs: Vec, out_solution: Vec) -> None:
        """
        Count and delegate one solve.

        :param rhs: Right-hand side.
        :param out_solution: Output buffer.
        :return: None.
        """
        self._counter.solves += 1
        self._handle.solve_into(rhs, out_solution)

    def get_active_matrix(self) -> csc_matrix:
        """
        Return the wrapped active matrix.

        :return: Active matrix.
        """
        return self._handle.get_active_matrix()


class CountingBackend(SparseLinearSolverBackend):
    """
    Test-only backend wrapper that counts factorizations on its provider wrapper.
    """

    __slots__ = ("_backend", "_counter")

    def __init__(self, backend: SparseLinearSolverBackend, counter: CountingProvider) -> None:
        """
        Wrap a backend.

        :param backend: Wrapped backend.
        :param counter: Provider wrapper receiving the counts.
        """
        self._backend: SparseLinearSolverBackend = backend
        self._counter: CountingProvider = counter

    def get_name(self) -> str:
        """
        Return the wrapped backend name.

        :return: Backend name.
        """
        return self._backend.get_name()

    def get_solver_type(self) -> SparseSolver:
        """
        Return the wrapped solver type.

        :return: Sparse solver type.
        """
        return self._backend.get_solver_type()

    def is_available(self) -> bool:
        """
        Return whether the wrapped backend is available.

        :return: Availability.
        """
        return self._backend.is_available()

    def factorize(self, matrix: csc_matrix, analysis_handle: Any | None) -> SparseLinearFactorizationHandle:
        """
        Count and delegate one factorization.

        :param matrix: Matrix argument.
        :param analysis_handle: Symbolic analysis or None.
        :return: Counting handle around the wrapped factorization.
        """
        self._counter.factorizations += 1
        return CountingHandle(self._backend.factorize(matrix, analysis_handle), self._counter)


class SmallSignalRecorder:
    """
    Test-only factory registered in SmallSignalStabilityRmsDriver.integration_methods_dict that records the provider it receives.
    """

    __slots__ = ("providers",)

    def __init__(self) -> None:
        """
        Create the recorder with no recorded provider.
        """
        self.providers: List[SparseLinearSolverBackendProvider | None] = list()

    def __call__(self, problem: Any, t0: float, t_end: float, h: float, max_iter: int,
                 sparse_solver_backend_provider: SparseLinearSolverBackendProvider | None = None) -> BackEulerImplicitIntegration:
        """
        Record the provider and build the real Backward Euler solver.

        :param problem: RMS problem.
        :param t0: Initial time.
        :param t_end: Final time.
        :param h: Time step.
        :param max_iter: Maximum Newton corrections.
        :param sparse_solver_backend_provider: Provider passed by the small-signal driver.
        :return: Backward Euler solver.
        """
        self.providers.append(sparse_solver_backend_provider)
        return BackEulerImplicitIntegration(problem=problem, t0=t0, t_end=t_end, h=h, max_iter=max_iter,
                                            sparse_solver_backend_provider=sparse_solver_backend_provider)


def _klu_provider_or_skip() -> SparseLinearSolverBackendProvider:
    """
    Return the native KLU provider, skipping the test with the reason when it is not installed.

    :return: Native KLU provider.
    """
    provider: SparseLinearSolverBackendProvider | None
    reason: str
    provider, reason = sparse_selection.get_sparse_lu_provider_status(SparseSolver.KLU)
    if provider is None:
        pytest.skip("native KLU unavailable: " + reason)
    else:
        pass
    return provider


def _fake_native_provider() -> Tuple[NativeLuRuntimeBackendProvider, CountingScipyLuRuntime]:
    """
    Build a native provider over the SciPy-backed counting runtime.

    :return: Provider and its runtime.
    """
    runtime: CountingScipyLuRuntime = CountingScipyLuRuntime()
    return NativeLuRuntimeBackendProvider("fake_native", SparseSolver.KLU, runtime, ""), runtime


def _square_case() -> Tuple[csc_matrix, Vec, List[str]]:
    """
    Return the square Newton system and its golden correction produced by the scipy spsolve implementation at commit 0af0a36ad.

    :return: Jacobian, residual and the correction as float.hex strings.
    """
    jacobian: csc_matrix = csc_matrix(np.array([[4.0, 1.0, 0.0], [1.0, 3.0, 0.5], [0.0, 0.5, 2.0]]))
    residual: Vec = np.array([0.3, -0.2, 0.1])
    golden: List[str] = ["-0x1.a83a83a83a83bp-4", "0x1.d41d41d41d41fp-4", "-0x1.41d41d41d41d5p-4"]
    return jacobian, residual, golden


def _gauge_case() -> Tuple[csc_matrix, Vec, int, List[str]]:
    """
    Return the gauge-augmented Newton system and its golden correction produced at commit 0af0a36ad (SciPy 1.17.1).

    :return: Jacobian, residual, reference column and the correction as float.hex strings.
    """
    jacobian: csc_matrix = csc_matrix(np.array([[2.0e3, -1.0e3, 0.0], [-1.0e3, 2.0e3, -1.0e-2]]))
    residual: Vec = np.array([1.5e-3, -2.5e-6])
    golden: List[str] = ["0x0.0p+0", "0x1.92a737110e454p-20", "0x1.32f1a9fbe76cap-2"]
    return jacobian, residual, 0, golden


def _messages(logger: Logger, severity: LogSeverity, prefix: str) -> List[str]:
    """
    Return the logger messages of one severity starting with a prefix.

    :param logger: Logger.
    :param severity: Severity to keep.
    :param prefix: Message prefix.
    :return: Matching messages.
    """
    return [entry.msg for entry in logger.entries if entry.severity == severity and entry.msg.startswith(prefix)]


def _base_options(problem_type: RmsProblemTypes) -> RmsOptions:
    """
    Build the options of the Base 2-bus driver case for one problem type.

    :param problem_type: RMS problem formulation.
    :return: RMS options for 0.2 s with a 1 ms step.
    """
    return RmsOptions(time_step=1.0e-3, simulation_time=0.2, tolerance=1.0e-6, integration_method=DynamicIntegrationMethod.DaeBackEuler,
                      initialization_method=RmsInitializationMethod.Explicit, problem_type=problem_type, use_init_values=False,
                      max_iter=1000, verbose=0)


def _helper_solver(problem_type: RmsProblemTypes, provider: SparseLinearSolverBackendProvider
                   ) -> BackEulerImplicitIntegration | BackEulerImplicitIntegrationVec | BackEulerImplicitIntegrationFullVec:
    """
    Build a fresh Base 2-bus problem of one type and its solver through RmsSimulationDriver._build_back_euler_solver.

    :param problem_type: RMS problem formulation.
    :param provider: Sparse LU provider passed to the helper.
    :return: Solver ready for simulation.
    """
    built: RmsSimulationDriver = _build_rms_driver()
    options: RmsOptions = _base_options(problem_type)
    driver: RmsSimulationDriver = RmsSimulationDriver(grid=built.grid, options=options, pf_results=built.pf_results)
    problem: RmsProblemTemplate = build_rms_problem(grid=built.grid, options=options, pf_results=built.pf_results, logger=driver.logger)
    problem.set_events_group(built.grid.rms_events_groups[0])
    problem.reset_boundary_update_state(0.0)
    return driver._build_back_euler_solver(problem=problem, provider=provider)


def _simulate(solver: BackEulerImplicitIntegration | BackEulerImplicitIntegrationVec | BackEulerImplicitIntegrationFullVec) -> Mat:
    """
    Run a solver and return its trajectory after checking convergence.

    :param solver: Solver to run.
    :return: State trajectory.
    """
    t: Vec
    y: Mat
    well_initialized: bool
    converged: bool
    t, y, well_initialized, converged = solver.simulate()
    assert well_initialized and converged
    return y


def test_solve_once_superlu_or_none_is_exactly_spsolve() -> None:
    """
    The default provider and a SuperLU provider return exactly spsolve.

    :return: None.
    """
    matrix: csc_matrix
    rhs: Vec
    golden: List[str]
    matrix, rhs, golden = _square_case()
    expected: Vec = spsolve(matrix.copy(), rhs)
    assert np.array_equal(sparse_selection.solve_sparse_system_once(matrix.copy(), rhs, None), expected)
    assert np.array_equal(sparse_selection.solve_sparse_system_once(matrix.copy(), rhs, SuperLUSparseBackendProvider()), expected)


def test_solve_once_native_provider_copies_noncanonical_input() -> None:
    """
    A native provider solves a non-canonical int64 matrix with duplicates and leaves it untouched.

    :return: None.
    """
    data: Vec = np.array([3.0, 1.0, 1.0, 1.0, 4.0, 2.0])
    indices: np.ndarray = np.array([1, 0, 0, 2, 1, 2], dtype=np.int64)
    indptr: np.ndarray = np.array([0, 3, 5, 6], dtype=np.int64)
    matrix: csc_matrix = csc_matrix((data.copy(), indices.copy(), indptr.copy()), shape=(3, 3))
    stacked: csc_matrix = sp.vstack((matrix[:2, :], sp.diags([1.0], offsets=[2], shape=(1, 3), format="csc")), format="csc")
    rhs: Vec = np.array([1.0, -2.0, 0.5])
    provider: NativeLuRuntimeBackendProvider
    runtime: CountingScipyLuRuntime
    provider, runtime = _fake_native_provider()
    data_before: Vec = matrix.data.copy()
    indices_before: np.ndarray = matrix.indices.copy()
    assert not matrix.has_canonical_format

    solution: Vec = sparse_selection.solve_sparse_system_once(matrix, rhs, provider)

    assert runtime.solves == 1
    assert solution.dtype == np.float64 and solution.shape == (3,)
    assert np.allclose(solution, spsolve(csc_matrix(matrix.toarray()), rhs), rtol=0.0, atol=1e-12)
    assert np.array_equal(matrix.data, data_before) and np.array_equal(matrix.indices, indices_before)
    assert np.allclose(sparse_selection.solve_sparse_system_once(stacked, rhs, provider),
                       spsolve(csc_matrix(stacked.toarray()), rhs), rtol=0.0, atol=1e-12)


def test_solve_once_native_contract_violation_propagates() -> None:
    """
    Contract violations of the native backend propagate instead of being reported as singular.

    :return: None.
    """
    provider: NativeLuRuntimeBackendProvider
    runtime: CountingScipyLuRuntime
    provider, runtime = _fake_native_provider()
    with pytest.raises(ValueError):
        sparse_selection.solve_sparse_system_once(csc_matrix(np.ones((2, 3))), np.ones(2), provider)
    assert runtime.solves == 0


@pytest.mark.parametrize("dense", [[[1.0, 0.0], [2.0, 0.0]], [[1.0, 2.0], [2.0, 4.0]]])
def test_solve_once_real_klu_singular_matches_spsolve(dense: List[List[float]]) -> None:
    """
    Real KLU on singular systems reports like spsolve: MatrixRankWarning and an all-NaN vector.

    :param dense: Exactly singular (zero column) or rank-deficient matrix.
    :return: None.
    """
    provider: SparseLinearSolverBackendProvider = _klu_provider_or_skip()
    matrix: csc_matrix = csc_matrix(np.array(dense))
    with pytest.warns(MatrixRankWarning, match="Matrix is exactly singular"):
        reference: Vec = spsolve(matrix.copy(), np.ones(2))
    with pytest.warns(MatrixRankWarning, match="Matrix is exactly singular"):
        solution: Vec = sparse_selection.solve_sparse_system_once(matrix, np.ones(2), provider)
    assert solution.dtype == np.float64 and solution.shape == (2,)
    assert np.all(np.isnan(solution)) and np.all(np.isnan(reference))


def test_newton_correction_default_square_is_exactly_spsolve() -> None:
    """
    The default square Newton correction equals spsolve bit for bit.

    :return: None.
    """
    jacobian: csc_matrix
    residual: Vec
    golden: List[str]
    jacobian, residual, golden = _square_case()
    correction: Vec = solve_rms_newton_correction(jacobian, residual, None)
    assert np.array_equal(correction, spsolve(jacobian.copy(), -residual))
    assert [float(value).hex() for value in correction] == golden


def test_newton_correction_default_gauge_matches_golden() -> None:
    """
    The default gauge-augmented Newton correction equals the golden vector bit for bit.

    :return: None.
    """
    jacobian: csc_matrix
    residual: Vec
    reference_column: int
    golden: List[str]
    jacobian, residual, reference_column, golden = _gauge_case()
    correction: Vec = solve_rms_newton_correction(jacobian, residual, reference_column)
    assert [float(value).hex() for value in correction] == golden


def test_newton_correction_native_provider_routes_both_branches() -> None:
    """
    A native provider performs one runtime solve per square or gauge-augmented correction.

    :return: None.
    """
    provider: NativeLuRuntimeBackendProvider
    runtime: CountingScipyLuRuntime
    provider, runtime = _fake_native_provider()
    square_jacobian: csc_matrix
    square_residual: Vec
    square_golden: List[str]
    square_jacobian, square_residual, square_golden = _square_case()
    gauge_jacobian: csc_matrix
    gauge_residual: Vec
    reference_column: int
    gauge_golden: List[str]
    gauge_jacobian, gauge_residual, reference_column, gauge_golden = _gauge_case()
    square: Vec = solve_rms_newton_correction(square_jacobian, square_residual, None, sparse_solver_backend_provider=provider)
    assert runtime.solves == 1
    gauge: Vec = solve_rms_newton_correction(gauge_jacobian, gauge_residual, reference_column, sparse_solver_backend_provider=provider)
    assert runtime.solves == 2
    assert np.allclose(square, [float.fromhex(value) for value in square_golden], rtol=0.0, atol=1e-12)
    assert np.allclose(gauge, [float.fromhex(value) for value in gauge_golden], rtol=0.0, atol=1e-12)


@pytest.mark.parametrize(
    "problem_type, solver_class",
    [
        (RmsProblemTypes.PowerBalance, BackEulerImplicitIntegration),
        (RmsProblemTypes.PowerBalanceVectorized, BackEulerImplicitIntegrationVec),
        (RmsProblemTypes.PowerBalanceFullVectorized, BackEulerImplicitIntegrationFullVec),
    ],
)
def test_build_back_euler_solver_selects_class_and_passes_provider(problem_type: RmsProblemTypes, solver_class: type) -> None:
    """
    The driver helper builds the solver class of the problem type with the driver options and the provider.

    :param problem_type: RMS problem type.
    :param solver_class: Expected solver class.
    :return: None.
    """
    provider: SuperLUSparseBackendProvider = SuperLUSparseBackendProvider()
    solver: BackEulerImplicitIntegration | BackEulerImplicitIntegrationVec | BackEulerImplicitIntegrationFullVec = _helper_solver(problem_type, provider)
    options: RmsOptions = _base_options(problem_type)
    assert type(solver) is solver_class
    assert solver._sparse_solver_backend_provider is provider
    assert solver.h == options.time_step and solver.max_iter_0 == options.max_iter and solver.tol == options.tolerance
    assert solver.steps == int(np.ceil(options.simulation_time / options.time_step))
    assert solver._cancel_checker is not None


@pytest.mark.parametrize("problem_type", [RmsProblemTypes.CurrentBalance, RmsProblemTypes.Multilinear])
def test_build_back_euler_solver_rejects_types_without_back_euler(problem_type: RmsProblemTypes) -> None:
    """
    Problem types without a Backward Euler solver raise ValueError naming the type.

    :param problem_type: RMS problem type without a Backward Euler solver.
    :return: None.
    """
    driver: RmsSimulationDriver = RmsSimulationDriver(grid=MultiCircuit(), options=RmsOptions(problem_type=problem_type), pf_results=None)
    with pytest.raises(ValueError, match=problem_type.value):
        driver._build_back_euler_solver(problem=None, provider=SuperLUSparseBackendProvider())


@pytest.mark.parametrize("problem_type", [RmsProblemTypes.PowerBalance, RmsProblemTypes.PowerBalanceVectorized,
                                          RmsProblemTypes.PowerBalanceFullVectorized])
def test_every_fx_class_forwards_the_provider(problem_type: RmsProblemTypes) -> None:
    """
    Every fx solver built by the helper forwards the provider to its Newton corrections (fake runtime, any venv).

    :param problem_type: RMS problem type.
    :return: None.
    """
    provider: NativeLuRuntimeBackendProvider
    runtime: CountingScipyLuRuntime
    provider, runtime = _fake_native_provider()
    y_fake: Mat = _simulate(_helper_solver(problem_type, provider))
    y_superlu: Mat = _simulate(_helper_solver(problem_type, SuperLUSparseBackendProvider()))
    assert runtime.solves > 0
    assert np.allclose(y_fake, y_superlu, rtol=0.0, atol=1e-8)


@pytest.mark.parametrize("problem_type", [RmsProblemTypes.PowerBalance, RmsProblemTypes.PowerBalanceVectorized,
                                          RmsProblemTypes.PowerBalanceFullVectorized])
def test_real_klu_factorizes_every_direct_correction(problem_type: RmsProblemTypes) -> None:
    """
    With real KLU every direct Newton correction is factorized natively: as many factorizations as fake-runtime solves (101 observed).

    :param problem_type: RMS problem type.
    :return: None.
    """
    klu: CountingProvider = CountingProvider(_klu_provider_or_skip())
    provider: NativeLuRuntimeBackendProvider
    runtime: CountingScipyLuRuntime
    provider, runtime = _fake_native_provider()
    y_klu: Mat = _simulate(_helper_solver(problem_type, klu))
    _simulate(_helper_solver(problem_type, provider))
    y_superlu: Mat = _simulate(_helper_solver(problem_type, SuperLUSparseBackendProvider()))
    assert klu.factorizations == runtime.solves
    assert klu.factorizations > 0 and klu.solves == klu.factorizations
    assert np.allclose(y_klu, y_superlu, rtol=0.0, atol=1e-8)


def test_fallback_branch_uses_the_selected_provider() -> None:
    """
    The non-BackEuler fallback branch logs the fallback and gives exactly the BackEuler KLU results.

    KLU and SuperLU trajectories differ in the last bits on this case, so exact equality shows the
    fallback branch used the selected KLU provider.

    :return: None.
    """
    _klu_provider_or_skip()
    back_euler_run: RmsSimulationDriver = _build_rms_driver(sparse_solver=SparseSolver.KLU)
    superlu_run: RmsSimulationDriver = _build_rms_driver()
    driver: RmsSimulationDriver = _build_rms_driver(sparse_solver=SparseSolver.KLU, integration_method=DynamicIntegrationMethod.DaeTrapezoidal)
    assert len(_messages(driver.logger, LogSeverity.Information, "Falling back to DAE-BackEuler method")) == 1
    assert len(_messages(driver.logger, LogSeverity.Warning, "Sparse LU solver")) == 0
    assert np.array_equal(driver.results.values, back_euler_run.results.values)
    assert not np.array_equal(back_euler_run.results.values, superlu_run.results.values)


def test_driver_reports_an_unavailable_selection_once_per_run() -> None:
    """
    With two active event groups an unavailable selection is reported once per run.

    :return: None.
    """
    first_run: RmsSimulationDriver = _build_rms_driver()
    grid: MultiCircuit = first_run.grid
    template_event: RmsEvent = grid.rms_events[0]
    second_group: RmsEventsGroup = RmsEventsGroup(name="simulation2")
    grid.add_rms_events_group(second_group)
    grid.add_rms_event(RmsEvent(device=template_event.device, parameter=template_event.parameter, time=0.15,
                                value=-0.098, group=second_group))
    options: RmsOptions = RmsOptions(time_step=1.0e-3, simulation_time=0.2, tolerance=1.0e-6,
                                     integration_method=DynamicIntegrationMethod.DaeBackEuler,
                                     initialization_method=RmsInitializationMethod.Explicit,
                                     use_init_values=False, max_iter=1000, verbose=0, sparse_solver=SparseSolver.Pardiso)
    driver: RmsSimulationDriver = RmsSimulationDriver(grid=grid, options=options, pf_results=first_run.pf_results)

    driver.run()

    assert len([group for group in grid.rms_events_groups if group.active]) == 2
    assert len(_messages(driver.logger, LogSeverity.Warning, "Sparse LU solver Pardiso is unavailable")) == 1


def _small_signal_run(grid: MultiCircuit, pf_results: Any, sparse_solver: SparseSolver) -> Tuple[Vec, Logger, SmallSignalRecorder]:
    """
    Run the small-signal driver with a pre-simulation and a recording factory for the Backward Euler solver.

    :param grid: Grid with RMS models.
    :param pf_results: Power-flow results of the grid.
    :param sparse_solver: Sparse LU selected through the RMS options.
    :return: Sorted eigenvalues, driver logger and the recorder.
    """
    options: RmsOptions = RmsOptions(time_step=1.0e-3, simulation_time=0.2, tolerance=1.0e-6,
                                     integration_method=DynamicIntegrationMethod.DaeBackEuler,
                                     initialization_method=RmsInitializationMethod.Explicit,
                                     use_init_values=False, max_iter=1000, verbose=0, sparse_solver=sparse_solver)
    driver: SmallSignalStabilityRmsDriver = SmallSignalStabilityRmsDriver(
        grid=grid,
        rms_options=options,
        sss_options=RmsSmallSignalStabilityOptions(ss_assessment_time=0.05),
        pf_results=pf_results,
    )
    # The driver looks the solver up in its public integration-method registry; registering the recorder there
    # observes the provider without replacing any attribute.
    recorder: SmallSignalRecorder = SmallSignalRecorder()
    driver.integration_methods_dict[DynamicIntegrationMethod.DaeBackEuler] = recorder
    driver.run()
    return np.sort_complex(driver.results.eigenvalues), driver.logger, recorder


@pytest.mark.parametrize("sparse_solver, expected_type, warnings_expected",
                         [(SparseSolver.SuperLU, SparseSolver.SuperLU, 0),
                          (SparseSolver.Pardiso, SparseSolver.SuperLU, 1),
                          (SparseSolver.KLU, SparseSolver.KLU, 0)])
def test_small_signal_pre_simulation_receives_the_provider(sparse_solver: SparseSolver, expected_type: SparseSolver, warnings_expected: int) -> None:
    """
    The small-signal pre-simulation resolves the provider once and passes it to its solver.

    The spectrum contains infinite eigenvalues, so it is compared with exact equality.

    :param sparse_solver: Sparse LU selected through the RMS options.
    :param expected_type: Solver type of the provider the pre-simulation must receive.
    :param warnings_expected: Number of sparse LU fallback warnings expected.
    :return: None.
    """
    if sparse_solver == SparseSolver.KLU:
        _klu_provider_or_skip()
    else:
        pass
    built: RmsSimulationDriver = _build_rms_driver()
    reference: Vec
    reference_logger: Logger
    reference_recorder: SmallSignalRecorder
    reference, reference_logger, reference_recorder = _small_signal_run(built.grid, built.pf_results, SparseSolver.SuperLU)
    eigenvalues: Vec
    logger: Logger
    recorder: SmallSignalRecorder
    eigenvalues, logger, recorder = _small_signal_run(built.grid, built.pf_results, sparse_solver)

    assert len(reference_recorder.providers) == 1 and len(_messages(reference_logger, LogSeverity.Warning, "Sparse LU solver")) == 0
    assert len(recorder.providers) == 1
    assert recorder.providers[0].get_solver_type() == expected_type
    assert len(_messages(logger, LogSeverity.Warning, "Sparse LU solver")) == warnings_expected
    assert np.array_equal(eigenvalues, reference)
