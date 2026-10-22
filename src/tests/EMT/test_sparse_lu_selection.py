# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""LU-agnostic sparse solver selection, native LU runtime backends and EMT wiring."""

from __future__ import annotations

import importlib
from types import ModuleType
from typing import Any, Dict, Iterator, List, Tuple

import numpy as np
import pytest
import scipy.sparse as sp
from scipy.sparse import csc_matrix
from scipy.sparse.linalg import splu

import VeraGridEngine.Compilers.Gslv.activation as gslv_activation
import VeraGridEngine.Simulations.EMT.emt_solver_factory as emt_solver_factory
import VeraGridEngine.Utils.NumericalMethods.emt_sparse_solver_registry as sparse_registry
import VeraGridEngine.Utils.NumericalMethods.native_lu_runtime_backend as native_backend_module
import VeraGridEngine.Utils.NumericalMethods.sparse_lu_selection as sparse_selection
from tests.EMT.test_kundur_emt_initialization import _build_kundur_problem
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.EMT.solvers.StructuralVectorizedSolver import StructuralVectorizedSolver
from VeraGridEngine.Simulations.EMT.solvers.structural_compiled_solver import StructuralCompiledSolver
from VeraGridEngine.Utils.NumericalMethods.emt_sparse_superlu_backend import SuperLUSparseBackendProvider
from VeraGridEngine.Utils.NumericalMethods.external_sparse_solver_interface import (
    SparseLinearSolverBackend,
    SparseLinearSolverBackendProvider,
)
from VeraGridEngine.Utils.NumericalMethods.native_lu_runtime_backend import (
    NativeLuRuntimeBackendProvider,
    NativeLuRuntimeFactorizationHandle,
    load_native_lu_runtime,
    validate_native_lu_runtime,
)
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.enumerations import DynamicIntegrationMethod, EmtSolverTypes, SparseSolver


@pytest.fixture(autouse=True)
def isolated_provider_cache() -> Iterator[None]:
    """
    Clear the process-wide native provider cache around every test.

    :return: Iterator yielding once.
    """
    sparse_selection.clear_sparse_lu_provider_cache()
    yield None
    sparse_selection.clear_sparse_lu_provider_cache()


def _fake_analyze(indptr: np.ndarray, indices: np.ndarray, n: int) -> Dict[str, Any]:
    """
    Fake symbolic analysis: remember the pattern.

    :param indptr: CSC column pointer.
    :param indices: CSC row indices.
    :param n: Matrix size.
    :return: Symbolic object.
    """
    return {"indptr": indptr.copy(), "indices": indices.copy(), "n": n}


def _fake_factorize(indptr: np.ndarray, indices: np.ndarray, data: np.ndarray, symbolic: Dict[str, Any]) -> Any:
    """
    Fake numeric factorization with SciPy SuperLU.

    :param indptr: CSC column pointer.
    :param indices: CSC row indices.
    :param data: CSC values.
    :param symbolic: Symbolic object.
    :return: SciPy SuperLU object.
    """
    return splu(csc_matrix((data.copy(), indices, indptr), shape=(symbolic["n"], symbolic["n"])))


def _fake_refactor(indptr: np.ndarray, indices: np.ndarray, data: np.ndarray, symbolic: Dict[str, Any], numeric: Any) -> Any:
    """
    Fake refactorization.

    :param indptr: CSC column pointer.
    :param indices: CSC row indices.
    :param data: CSC values.
    :param symbolic: Symbolic object.
    :param numeric: Previous numeric object (unused).
    :return: New SciPy SuperLU object.
    """
    return _fake_factorize(indptr, indices, data, symbolic)


def _fake_solve_into(numeric: Any, rhs: np.ndarray, out: np.ndarray) -> None:
    """
    Fake solve into a caller buffer.

    :param numeric: SciPy SuperLU object.
    :param rhs: Right-hand side.
    :param out: Output buffer.
    :return: None
    """
    out[:] = numeric.solve(rhs)


def _fake_runtime(name: str) -> ModuleType:
    """
    Build a module object implementing the native LU runtime contract with SciPy.

    :param name: Module name.
    :return: Fake runtime module.
    """
    runtime: ModuleType = ModuleType(name)
    runtime.analyze = _fake_analyze
    runtime.factorize = _fake_factorize
    runtime.refactor = _fake_refactor
    runtime.solve_into = _fake_solve_into
    return runtime


def _random_system(n: int, seed: int) -> csc_matrix:
    """
    Build a well-conditioned canonical random sparse matrix.

    :param n: Matrix size.
    :param seed: Random seed.
    :return: CSC matrix.
    """
    matrix: csc_matrix = (sp.random(n, n, density=0.08, random_state=seed, format="csc") + sp.eye(n, format="csc") * 4.0).tocsc()
    matrix.sort_indices()
    return matrix


class _ImportRaiser:
    """Stand-in for importlib that raises a prepared exception."""

    __slots__ = ("error",)

    def __init__(self, error: BaseException) -> None:
        """
        :param error: Exception raised by import_module.
        """
        self.error: BaseException = error

    def import_module(self, name: str) -> ModuleType:
        """
        Raise the prepared exception.

        :param name: Requested module name.
        :return: Never returns.
        """
        raise self.error


class _FakePluginProvider(SparseLinearSolverBackendProvider):
    """Plugin provider with configurable identity and availability."""

    __slots__ = ("solver_type", "available")

    def __init__(self, solver_type: SparseSolver, available: bool) -> None:
        """
        :param solver_type: Reported solver type.
        :param available: Reported availability.
        """
        self.solver_type: SparseSolver = solver_type
        self.available: bool = available

    def get_name(self) -> str:
        """:return: Provider name."""
        return "fake_plugin"

    def get_solver_type(self) -> SparseSolver:
        """:return: Reported solver type."""
        return self.solver_type

    def is_available(self) -> bool:
        """:return: Reported availability."""
        return self.available

    def create_backend(self, base_matrix: csc_matrix, base_data: np.ndarray) -> SparseLinearSolverBackend:
        """:return: Never used."""
        raise RuntimeError("not used")


class _RecordingAnalyze:
    """Analyze stand-in that records every symbolic object it returns."""

    __slots__ = ("records",)

    def __init__(self) -> None:
        """Create an empty record list."""
        self.records: List[Any] = list()

    def __call__(self, indptr: np.ndarray, indices: np.ndarray, n: int) -> Dict[str, Any]:
        """
        Analyse and record.

        :param indptr: CSC column pointer.
        :param indices: CSC row indices.
        :param n: Matrix size.
        :return: Symbolic object.
        """
        symbolic: Dict[str, Any] = _fake_analyze(indptr, indices, n)
        self.records.append(symbolic)
        return symbolic


class _MissingRuntimeLoader:
    """load_native_lu_runtime stand-in reporting a missing package and counting calls."""

    __slots__ = ("calls",)

    def __init__(self) -> None:
        """Create an empty call list."""
        self.calls: List[str] = list()

    def __call__(self, module_name: str, top_level_module: str, distribution_name: str) -> Tuple[ModuleType | None, str]:
        """
        Record the call and report the package as missing.

        :param module_name: Runtime module name.
        :param top_level_module: Top-level import name.
        :param distribution_name: Distribution name.
        :return: No runtime and the reason.
        """
        self.calls.append(module_name)
        return None, "veragrid-cvxoptklu is not installed"


class _PluginLoader:
    """load_sparse_solver_backend_provider stand-in returning a prepared provider."""

    __slots__ = ("provider",)

    def __init__(self, provider: SparseLinearSolverBackendProvider) -> None:
        """
        :param provider: Provider to return.
        """
        self.provider: SparseLinearSolverBackendProvider = provider

    def __call__(self, plugin_name: str, plugin_directory_override: str) -> SparseLinearSolverBackendProvider:
        """
        :param plugin_name: Plugin name.
        :param plugin_directory_override: Plugin directory.
        :return: Prepared provider.
        """
        return self.provider


def _failing_plugin_loader(plugin_name: str, plugin_directory_override: str) -> SparseLinearSolverBackendProvider:
    """
    Plugin loader stand-in that cannot find the plugin.

    :param plugin_name: Plugin name.
    :param plugin_directory_override: Plugin directory.
    :return: Never returns.
    """
    raise FileNotFoundError("no plugin " + plugin_name)


class _RecordingSolver:
    """Stand-in solver class recording its keyword arguments."""

    __slots__ = ("kwargs",)

    def __init__(self, **kwargs: Any) -> None:
        """
        :param kwargs: Constructor keyword arguments.
        """
        self.kwargs: Dict[str, Any] = kwargs


def test_native_backend_matches_direct_runtime_calls() -> None:
    """A native LU runtime backend solves exactly like direct calls of the runtime."""
    runtime: ModuleType = _fake_runtime("fake_runtime")
    matrix: csc_matrix = _random_system(40, 4)
    rhs: np.ndarray = np.random.default_rng(1).normal(size=40)
    provider: NativeLuRuntimeBackendProvider = NativeLuRuntimeBackendProvider("fake", SparseSolver.KLU, runtime, "")
    backend: SparseLinearSolverBackend = provider.create_backend(matrix, matrix.data)
    solution: np.ndarray = np.zeros(40)
    backend.factorize(matrix, None).solve_into(rhs, solution)
    direct: np.ndarray = splu(matrix).solve(rhs)
    assert np.array_equal(solution, direct)
    assert backend.supports_symbolic_analysis_reuse()
    assert backend.supports_numeric_refactorization()


def test_handle_keeps_the_symbolic_analysis_and_refactor_reuses_it() -> None:
    """Every factorization handle owns its symbolic analysis; refactorization passes the same object."""
    recording_analyze: _RecordingAnalyze = _RecordingAnalyze()
    recorded: List[Any] = recording_analyze.records
    runtime: ModuleType = _fake_runtime("recording_runtime")
    runtime.analyze = recording_analyze
    matrix: csc_matrix = _random_system(30, 5)
    backend: SparseLinearSolverBackend = NativeLuRuntimeBackendProvider("rec", SparseSolver.KLU, runtime, "").create_backend(matrix, matrix.data)
    handle = backend.factorize(matrix, None)
    assert isinstance(handle, NativeLuRuntimeFactorizationHandle)
    assert len(recorded) == 1
    assert handle.get_symbolic() is recorded[0]
    matrix.data *= 1.05
    refactored = backend.refactor_numeric(matrix, None, handle)
    assert isinstance(refactored, NativeLuRuntimeFactorizationHandle)
    assert refactored.get_symbolic() is recorded[0]
    assert backend.get_backend_stats()["numeric_refactorizations"] == 1.0


def test_create_backend_rejects_invalid_shells() -> None:
    """Non-square, non-canonical shells and copied values are rejected."""
    provider: NativeLuRuntimeBackendProvider = NativeLuRuntimeBackendProvider("fake", SparseSolver.KLU, _fake_runtime("rt"), "")
    matrix: csc_matrix = _random_system(20, 6)
    with pytest.raises(ValueError):
        provider.create_backend(matrix, matrix.data.copy())
    rectangular: csc_matrix = sp.random(3, 4, density=0.5, random_state=1, format="csc")
    with pytest.raises(ValueError):
        provider.create_backend(rectangular, rectangular.data)
    duplicated: csc_matrix = csc_matrix((np.array([1.0, 2.0, 3.0]), np.array([1, 0, 1]), np.array([0, 2, 3])), shape=(2, 2))
    with pytest.raises(ValueError):
        provider.create_backend(duplicated, duplicated.data)
    unavailable: NativeLuRuntimeBackendProvider = NativeLuRuntimeBackendProvider("none", SparseSolver.KLU, None, "missing")
    with pytest.raises(RuntimeError):
        unavailable.create_backend(matrix, matrix.data)


def test_loader_reports_reasons_without_raising(monkeypatch: pytest.MonkeyPatch, recwarn: pytest.WarningsRecorder) -> None:
    """Missing packages, broken installations and incomplete contracts become reasons."""
    monkeypatch.setattr(native_backend_module, "importlib", _ImportRaiser(ModuleNotFoundError("absent", name="cvxoptklu")))
    runtime, reason = load_native_lu_runtime("cvxoptklu._klu_native", "cvxoptklu", "veragrid-cvxoptklu")
    assert runtime is None
    assert reason.startswith("veragrid-cvxoptklu is not installed")
    assert len(recwarn) == 0

    monkeypatch.setattr(native_backend_module, "importlib", _ImportRaiser(ModuleNotFoundError("no submodule", name="cvxoptklu._klu_native")))
    runtime, reason = load_native_lu_runtime("cvxoptklu._klu_native", "cvxoptklu", "veragrid-cvxoptklu")
    assert runtime is None
    assert "veragrid-cvxoptklu" in reason

    for error in (ImportError("x"), AttributeError("x"), OSError("x"), RuntimeError("x"), ValueError("x"), TypeError("x"), SystemError("x")):
        monkeypatch.setattr(native_backend_module, "importlib", _ImportRaiser(error))
        runtime, reason = load_native_lu_runtime("cvxoptklu._klu_native", "cvxoptklu", "veragrid-cvxoptklu")
        assert runtime is None
        assert len(reason) > 0

    monkeypatch.setattr(native_backend_module, "importlib", importlib)
    runtime, reason = load_native_lu_runtime("json", "json", "json")
    assert runtime is None
    assert "native LU contract" in reason
    assert validate_native_lu_runtime(_fake_runtime("complete")) == ""


def test_selection_falls_back_to_superlu_with_a_logged_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    """An unavailable selection logs its reason once per resolution and uses SciPy SuperLU."""
    missing_loader: _MissingRuntimeLoader = _MissingRuntimeLoader()
    monkeypatch.setattr(sparse_selection, "load_native_lu_runtime", missing_loader)
    logger: Logger = Logger()
    provider: SparseLinearSolverBackendProvider = sparse_selection.resolve_sparse_lu_provider(SparseSolver.KLU, logger)
    assert isinstance(provider, SuperLUSparseBackendProvider)
    assert len(logger) == 1
    assert "Sparse LU solver KLU is unavailable: veragrid-cvxoptklu is not installed" in str(logger)
    sparse_selection.resolve_sparse_lu_provider(SparseSolver.KLU, logger)
    assert missing_loader.calls == ["cvxoptklu._klu_native"]
    with pytest.warns(RuntimeWarning, match="Sparse LU solver KLU is unavailable"):
        sparse_selection.resolve_sparse_lu_provider(SparseSolver.KLU, None)


def test_selection_status_without_fallback() -> None:
    """SuperLU is always available; solvers without a reuse provider report why."""
    provider, reason = sparse_selection.get_sparse_lu_provider_status(SparseSolver.SuperLU)
    assert isinstance(provider, SuperLUSparseBackendProvider)
    assert reason == ""
    for solver_type in (SparseSolver.Pardiso, SparseSolver.UMFPACK, SparseSolver.ILU, SparseSolver.GMRES, SparseSolver.UMFPACKTriangular):
        provider, reason = sparse_selection.get_sparse_lu_provider_status(solver_type)
        assert provider is None
        assert reason == "no factorisation-reusing provider is registered for " + solver_type.value


def test_klu_provider_is_available_whenever_the_runtime_imports() -> None:
    """No silent skip: the native KLU provider is available exactly when its runtime imports."""
    provider, reason = sparse_selection.get_sparse_lu_provider_status(SparseSolver.KLU)
    try:
        runtime: ModuleType = importlib.import_module("cvxoptklu._klu_native")
    except ImportError:
        assert provider is None
        assert len(reason) > 0
    else:
        if validate_native_lu_runtime(runtime) == "":
            assert isinstance(provider, NativeLuRuntimeBackendProvider)
            assert provider.get_name() == "native_klu"
        else:
            assert provider is None


def test_gslv_slot_follows_activation_and_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    """GSLV is available only with an activated pygslv exposing a complete sparse_lu attribute."""
    monkeypatch.setattr(gslv_activation, "GSLV_AVAILABLE", False)
    monkeypatch.setattr(gslv_activation, "GSLV_UNAVAILABLE_REASON", "not licensed")
    provider, reason = sparse_selection.get_sparse_lu_provider_status(SparseSolver.GSLV)
    assert provider is None
    assert reason == "GSLV unavailable: not licensed"

    sparse_selection.clear_sparse_lu_provider_cache()
    monkeypatch.setattr(gslv_activation, "GSLV_AVAILABLE", True)
    monkeypatch.setattr(gslv_activation, "pg", ModuleType("fake_pygslv_without_lu"))
    provider, reason = sparse_selection.get_sparse_lu_provider_status(SparseSolver.GSLV)
    assert provider is None
    assert reason == "the installed pygslv does not expose the sparse_lu native LU runtime"

    sparse_selection.clear_sparse_lu_provider_cache()
    fake_pygslv: ModuleType = ModuleType("fake_pygslv")
    fake_pygslv.sparse_lu = _fake_runtime("sparse_lu")
    monkeypatch.setattr(gslv_activation, "pg", fake_pygslv)
    provider, reason = sparse_selection.get_sparse_lu_provider_status(SparseSolver.GSLV)
    assert isinstance(provider, NativeLuRuntimeBackendProvider)
    assert provider.get_solver_type() == SparseSolver.GSLV
    assert reason == ""


def test_registry_plugin_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    """Plugin failures fall back through the selection layer or raise, as configured."""
    monkeypatch.setattr(sparse_registry, "load_sparse_solver_backend_provider", _failing_plugin_loader)
    logger: Logger = Logger()
    provider = sparse_registry.resolve_emt_sparse_solver_backend_provider(SparseSolver.SuperLU, "missing", "", True, logger)
    assert isinstance(provider, SuperLUSparseBackendProvider)
    assert "could not be loaded" in str(logger)
    with pytest.raises(FileNotFoundError):
        sparse_registry.resolve_emt_sparse_solver_backend_provider(SparseSolver.SuperLU, "missing", "", False, logger)

    monkeypatch.setattr(sparse_registry, "load_sparse_solver_backend_provider", _PluginLoader(_FakePluginProvider(SparseSolver.SuperLU, False)))
    logger = Logger()
    provider = sparse_registry.resolve_emt_sparse_solver_backend_provider(SparseSolver.SuperLU, "fake", "", True, logger)
    assert isinstance(provider, SuperLUSparseBackendProvider)
    assert "plugin reported unavailable without a reason" in str(logger)
    with pytest.raises(RuntimeError):
        sparse_registry.resolve_emt_sparse_solver_backend_provider(SparseSolver.SuperLU, "fake", "", False, None)

    monkeypatch.setattr(sparse_registry, "load_sparse_solver_backend_provider", _PluginLoader(_FakePluginProvider(SparseSolver.Pardiso, True)))
    with pytest.raises(ValueError):
        sparse_registry.resolve_emt_sparse_solver_backend_provider(SparseSolver.SuperLU, "fake", "", True, None)


def test_registry_internal_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    """Internal resolution logs and falls back, or raises with the reason when fallback is off."""
    monkeypatch.setattr(sparse_selection, "load_native_lu_runtime", _MissingRuntimeLoader())
    logger: Logger = Logger()
    provider = sparse_registry.resolve_emt_sparse_solver_backend_provider(SparseSolver.KLU, "", "", True, logger)
    assert isinstance(provider, SuperLUSparseBackendProvider)
    assert len(logger) == 1
    with pytest.raises(RuntimeError, match="veragrid-cvxoptklu is not installed"):
        sparse_registry.resolve_emt_sparse_solver_backend_provider(SparseSolver.KLU, "", "", False, logger)
    assert isinstance(sparse_registry.resolve_emt_sparse_solver_backend_provider(SparseSolver.SuperLU, "", "", False, None), SuperLUSparseBackendProvider)


def test_factory_passes_logger_and_reports_ignored_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    """build_emt_solver forwards its logger and reports a selection ignored by non-structural solvers."""
    monkeypatch.setattr(sparse_selection, "load_native_lu_runtime", _MissingRuntimeLoader())
    for solver_type in (EmtSolverTypes.StructuralCompiled, EmtSolverTypes.StructuralAD, EmtSolverTypes.Symbolic, EmtSolverTypes.Automatic):
        monkeypatch.setitem(emt_solver_factory.EMT_SOLVER_CLASS_MAP, solver_type, _RecordingSolver)
    structural_logger: Logger = Logger()
    solver = emt_solver_factory.build_emt_solver(options=EmtOptions(solver_type=EmtSolverTypes.StructuralCompiled, sparse_solver=SparseSolver.KLU),
                                                 problem=None, t0=0.0, t_end=1.0, h=1.0, logger=structural_logger)
    assert isinstance(solver.kwargs["sparse_solver_backend_provider"], SuperLUSparseBackendProvider)
    assert len(structural_logger) == 1
    symbolic_logger: Logger = Logger()
    emt_solver_factory.build_emt_solver(options=EmtOptions(solver_type=EmtSolverTypes.Symbolic, sparse_solver=SparseSolver.KLU),
                                        problem=None, t0=0.0, t_end=1.0, h=1.0, logger=symbolic_logger)
    assert "sparse_solver KLU is ignored by the" in str(symbolic_logger)
    default_logger: Logger = Logger()
    emt_solver_factory.build_emt_solver(options=EmtOptions(solver_type=EmtSolverTypes.Symbolic), problem=None, t0=0.0, t_end=1.0, h=1.0, logger=default_logger)
    assert len(default_logger) == 0


@pytest.fixture(scope="module")
def kundur_problem() -> EmtProblemDae:
    """
    Build the self-contained Kundur EMT problem once for this module.

    :return: Kundur EMT problem.
    """
    return _build_kundur_problem()[0]


def _klu_provider_or_skip() -> SparseLinearSolverBackendProvider:
    """
    Return the native KLU provider, or skip with the unavailability reason.

    :return: Native KLU provider.
    """
    provider, reason = sparse_selection.get_sparse_lu_provider_status(SparseSolver.KLU)
    if provider is None:
        pytest.skip("native KLU runtime unavailable: " + reason)
    else:
        pass
    assert provider.get_name() == "native_klu"
    return provider


@pytest.mark.parametrize("solver_class", [StructuralCompiledSolver, StructuralVectorizedSolver])
def test_kundur_native_klu_matches_superlu(kundur_problem: EmtProblemDae, solver_class: type) -> None:
    """Both structural solvers converge with native KLU and match the SuperLU trajectories."""
    klu_provider: SparseLinearSolverBackendProvider = _klu_provider_or_skip()
    trajectories: Dict[str, np.ndarray] = dict()
    for label, provider in (("superlu", SuperLUSparseBackendProvider()), ("klu", klu_provider)):
        solver = solver_class(kundur_problem, t0=0.0, t_end=0.001, h=5e-6, method=DynamicIntegrationMethod.DaeTrapezoidal,
                              verbose=False, sparse_solver_backend_provider=provider)
        result = solver.simulate()
        assert result[4]
        trajectories[label] = result[1]
    assert trajectories["superlu"].shape == trajectories["klu"].shape
    assert float(np.max(np.abs(trajectories["superlu"] - trajectories["klu"]))) <= 1e-8
