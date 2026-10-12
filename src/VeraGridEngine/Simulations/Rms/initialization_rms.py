# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from typing import Callable, Dict, List, Tuple, Union, Optional, Any
import numpy as np
import numba as nb
import math
import time
import hashlib
import os
import pickle
from pathlib import Path
import warnings
import scipy.sparse as sp
import scipy.sparse.linalg as spla

from collections import defaultdict, deque

# from VeraGridEngine.Simulations.Rms.problems import Any
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.enumerations import EmtInitializationMethod, EmtInitializationStatus, RmsInitializationMethod
from VeraGridEngine.Utils.Symbolic.compiled_functions import SymbolicJacobian, SymbolicVector
from VeraGridEngine.Utils.Symbolic.jit_compiler import RMSCompiler
from VeraGridEngine.Utils.Symbolic.symbolic import expression2numba, get_expression_vars
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const, Expr, find_vars_order


InitializationStatus = EmtInitializationStatus


class EmtInitializationReport:
    """
    Stores the outcome of the EMT-native initialization workflow.
    """

    __slots__ = [
        "status",
        "method_requested",
        "method_used",
        "initial_residual_inf",
        "final_residual_inf",
        "newton_iterations",
        "pseudo_transient_steps",
        "unknown_var_count",
        "unresolved_state_count",
        "automatic_dx0_count",
        "reduced_system_build_s",
        "runtime_param_build_s",
        "constant_param_build_s",
        "initial_residual_eval_s",
        "newton_elapsed_s",
        "pseudo_transient_elapsed_s",
        "dx0_completion_s",
        "x0_rebuild_s",
        "dx0_seed_build_s",
        "state_rhs_vector_build_s",
        "state_rhs_vector_cache_hit",
        "solution_apply_s",
        "missing_dx_problem_collect_s",
        "state_rhs_eval_s",
        "missing_dx_scatter_s",
        "persistent_cache_hit",
        "persistent_cache_load_s",
        "persistent_cache_store_s",
        "elapsed_s",
        "message",
    ]

    def __init__(self, method_requested: EmtInitializationMethod) -> None:
        """
        Build an empty EMT initialization report.

        :param method_requested: Requested initialization workflow.
        :return: None
        """
        self.status: InitializationStatus = InitializationStatus.PENDING
        self.method_requested: EmtInitializationMethod = method_requested
        self.method_used: EmtInitializationMethod = EmtInitializationMethod.Explicit
        self.initial_residual_inf: float = 0.0
        self.final_residual_inf: float = 0.0
        self.newton_iterations: int = 0
        self.pseudo_transient_steps: int = 0
        self.unknown_var_count: int = 0
        self.unresolved_state_count: int = 0
        self.automatic_dx0_count: int = 0
        self.reduced_system_build_s: float = 0.0
        self.runtime_param_build_s: float = 0.0
        self.constant_param_build_s: float = 0.0
        self.initial_residual_eval_s: float = 0.0
        self.newton_elapsed_s: float = 0.0
        self.pseudo_transient_elapsed_s: float = 0.0
        self.dx0_completion_s: float = 0.0
        self.x0_rebuild_s: float = 0.0
        self.dx0_seed_build_s: float = 0.0
        self.state_rhs_vector_build_s: float = 0.0
        self.state_rhs_vector_cache_hit: bool = False
        self.solution_apply_s: float = 0.0
        self.missing_dx_problem_collect_s: float = 0.0
        self.state_rhs_eval_s: float = 0.0
        self.missing_dx_scatter_s: float = 0.0
        self.persistent_cache_hit: bool = False
        self.persistent_cache_load_s: float = 0.0
        self.persistent_cache_store_s: float = 0.0
        self.elapsed_s: float = 0.0
        self.message: str = ""


class ReducedInitializationSystemCacheEntry:
    """
    In-process cache entry for reduced EMT initialization systems.
    """

    __slots__ = ["_residual_fn", "_jacobian_fn"]

    def __init__(self, residual_fn: SymbolicVector, jacobian_fn: SymbolicJacobian) -> None:
        """
        Build one reduced-system cache entry.

        :param residual_fn: Reduced residual evaluator.
        :type residual_fn: SymbolicVector
        :param jacobian_fn: Reduced Jacobian evaluator.
        :type jacobian_fn: SymbolicJacobian
        :return: None.
        :rtype: None
        """
        self._residual_fn = residual_fn
        self._jacobian_fn = jacobian_fn

    def get_residual_fn(self) -> SymbolicVector:
        """
        Return the cached reduced residual evaluator.

        :return: Reduced residual evaluator.
        :rtype: SymbolicVector
        """
        return self._residual_fn

    def get_jacobian_fn(self) -> SymbolicJacobian:
        """
        Return the cached reduced Jacobian evaluator.

        :return: Reduced Jacobian evaluator.
        :rtype: SymbolicJacobian
        """
        return self._jacobian_fn


class ReducedInitializationSystemCache:
    """
    In-process cache for reduced EMT initialization systems.
    """

    __slots__ = ["_cache"]

    def __init__(self) -> None:
        """
        Build the reduced-system cache.

        :return: None.
        :rtype: None
        """
        self._cache: Dict[str, ReducedInitializationSystemCacheEntry] = dict()

    def get_entry(self, cache_key: str) -> ReducedInitializationSystemCacheEntry | None:
        """
        Return one cached reduced-system entry.

        :param cache_key: Deterministic cache key.
        :type cache_key: str
        :return: Cached entry or ``None``.
        :rtype: ReducedInitializationSystemCacheEntry | None
        """
        return self._cache.get(cache_key, None)

    def set_entry(self, cache_key: str, entry: ReducedInitializationSystemCacheEntry) -> None:
        """
        Store one cached reduced-system entry.

        :param cache_key: Deterministic cache key.
        :type cache_key: str
        :param entry: Cache entry.
        :type entry: ReducedInitializationSystemCacheEntry
        :return: None.
        :rtype: None
        """
        self._cache[cache_key] = entry


REDUCED_INITIALIZATION_SYSTEM_CACHE = ReducedInitializationSystemCache()


class InitializationVectorCacheEntry:
    """
    In-process cache entry for one initialization-stage symbolic vector.
    """

    __slots__ = ["_vector"]

    def __init__(self, vector: SymbolicVector) -> None:
        """
        Build one initialization-vector cache entry.

        :param vector: Cached symbolic vector evaluator.
        :type vector: SymbolicVector
        :return: None.
        :rtype: None
        """
        self._vector = vector

    def get_vector(self) -> SymbolicVector:
        """
        Return the cached symbolic vector evaluator.

        :return: Cached symbolic vector evaluator.
        :rtype: SymbolicVector
        """
        return self._vector


class InitializationVectorCache:
    """
    In-process cache for symbolic vectors used during EMT initialization.
    """

    __slots__ = ["_cache"]

    def __init__(self) -> None:
        """
        Build the initialization-vector cache.

        :return: None.
        :rtype: None
        """
        self._cache: Dict[str, InitializationVectorCacheEntry] = dict()

    def get_entry(self, cache_key: str) -> InitializationVectorCacheEntry | None:
        """
        Return one cached initialization-vector entry.

        :param cache_key: Deterministic cache key.
        :type cache_key: str
        :return: Cached entry or ``None``.
        :rtype: InitializationVectorCacheEntry | None
        """
        return self._cache.get(cache_key, None)

    def set_entry(self, cache_key: str, entry: InitializationVectorCacheEntry) -> None:
        """
        Store one cached initialization-vector entry.

        :param cache_key: Deterministic cache key.
        :type cache_key: str
        :param entry: Cache entry.
        :type entry: InitializationVectorCacheEntry
        :return: None.
        :rtype: None
        """
        self._cache[cache_key] = entry


INITIALIZATION_VECTOR_CACHE = InitializationVectorCache()


class InitializationStateRhsVector:
    """
    Lightweight state-RHS evaluator used by ``dx0`` completion.
    """

    __slots__ = ["_func", "_data"]

    def __init__(self, source_code: str, use_jit: bool, output_size: int) -> None:
        """
        Build the state-RHS evaluator from source code.

        :param source_code: Generated Python source code.
        :type source_code: str
        :param use_jit: Whether the evaluator should be JIT-compiled.
        :type use_jit: bool
        :param output_size: Output vector length.
        :type output_size: int
        :return: None.
        :rtype: None
        """
        namespace: Dict[str, object] = dict(math=__import__("math"), np=np)
        exec(source_code, namespace)

        if use_jit:
            self._func = nb.njit(
                nb.void(nb.float64[:], nb.float64[:], nb.float64[:], nb.float64[:], nb.float64[:]),
                fastmath=True,
                cache=False,
            )(namespace["func"])
        else:
            self._func = namespace["func"]

        self._data = np.zeros(output_size, dtype=np.float64)

    def __call__(self, values: np.ndarray, diff_values: np.ndarray, event_params: np.ndarray, params: np.ndarray) -> np.ndarray:
        """
        Evaluate the state-RHS vector.

        :param values: State/algebraic vector.
        :type values: np.ndarray
        :param diff_values: Differential vector.
        :type diff_values: np.ndarray
        :param event_params: Runtime parameter vector.
        :type event_params: np.ndarray
        :param params: Constant parameter vector.
        :type params: np.ndarray
        :return: Evaluated state-RHS vector.
        :rtype: np.ndarray
        """
        self._func(values, diff_values, event_params, params, self._data)
        return self._data


def _get_state_rhs_persistent_cache_directory() -> Path:
    """
    Return the persistent cache directory used by ``dx0`` state-RHS evaluators.

    :return: Persistent cache directory.
    :rtype: Path
    """
    cache_directory: Path = _get_reduced_initialization_persistent_cache_directory() / "state_rhs_vectors"
    cache_directory.mkdir(parents=True, exist_ok=True)
    return cache_directory


def _build_state_rhs_source(
        missing_state_eqs: List[Expr],
        compiler_names_dict: Dict[int, str],
        alias_names_dict: Dict[int, str],
        vars_name: str,
        diff_name: str,
        event_params_name: str,
        params_name: str,
) -> str:
    """
    Build the Python source code of the ``dx0`` state-RHS evaluator.

    :param missing_state_eqs: State equations whose differential values are missing.
    :type missing_state_eqs: List[Expr]
    :param compiler_names_dict: Compiler variable-name map.
    :type compiler_names_dict: Dict[int, str]
    :param alias_names_dict: Alias variable-name map.
    :type alias_names_dict: Dict[int, str]
    :param vars_name: Full-variable argument name.
    :type vars_name: str
    :param diff_name: Differential-vector argument name.
    :type diff_name: str
    :param event_params_name: Runtime-parameter argument name.
    :type event_params_name: str
    :param params_name: Constant-parameter argument name.
    :type params_name: str
    :return: Generated Python source code.
    :rtype: str
    """
    used_vars_count: Dict[int, int] = dict()
    final_names_dict: Dict[int, str] = compiler_names_dict.copy()
    lines: List[str] = list()

    for eq in missing_state_eqs:
        for var in get_expression_vars(eq):
            if var.uid in used_vars_count:
                used_vars_count[var.uid] += 1
            else:
                used_vars_count[var.uid] = 1

    lines.append(f"def func({vars_name}, {diff_name}, {event_params_name}, {params_name}, out):")

    for uid, count in used_vars_count.items():
        if count > 1:
            final_names_dict[uid] = alias_names_dict[uid]
            lines.append(f"    {alias_names_dict[uid]} = {compiler_names_dict[uid]}")
        else:
            pass

    for eq_index, equation in enumerate(missing_state_eqs):
        lines.append(f"    out[{eq_index}] = {expression2numba(equation.simplify(), final_names_dict)}")

    return "\n".join(lines) + "\n"


def _load_or_build_state_rhs_vector(
        problem: EmtProblemTemplate,
        missing_state_eqs: List[Expr],
        cache_key: str,
        report: EmtInitializationReport,
) -> InitializationStateRhsVector | SymbolicVector:
    """
    Load or build the ``dx0`` state-RHS evaluator.

    :param problem: EMT problem being initialized.
    :type problem: EmtProblemTemplate
    :param missing_state_eqs: State equations whose differential values are missing.
    :type missing_state_eqs: List[Expr]
    :param cache_key: Deterministic cache key.
    :type cache_key: str
    :param report: Initialization report updated in place.
    :type report: EmtInitializationReport
    :return: State-RHS evaluator.
    :rtype: InitializationStateRhsVector | SymbolicVector
    """
    cache_entry: InitializationVectorCacheEntry | None = INITIALIZATION_VECTOR_CACHE.get_entry(cache_key)
    cache_path: Path = _get_state_rhs_persistent_cache_directory() / f"{cache_key}.pkl"

    if cache_entry is None:
        pass
    else:
        report.state_rhs_vector_build_s = 0.0
        report.state_rhs_vector_cache_hit = True
        return cache_entry.get_vector()

    phase_t0: float = time.perf_counter()

    if cache_path.exists():
        with open(cache_path, "rb") as cache_file:
            payload: Dict[str, object] = dict(pickle.load(cache_file))

        state_rhs_fn = InitializationStateRhsVector(
            source_code=str(payload["source_code"]),
            use_jit=bool(payload["use_jit"]),
            output_size=int(payload["output_size"]),
        )
        INITIALIZATION_VECTOR_CACHE.set_entry(cache_key, InitializationVectorCacheEntry(state_rhs_fn))
        report.state_rhs_vector_build_s = float(time.perf_counter() - phase_t0)
        report.state_rhs_vector_cache_hit = True
        return state_rhs_fn
    else:
        pass

    if len(missing_state_eqs) <= 16:
        use_jit_for_state_rhs: bool = False
    else:
        use_jit_for_state_rhs = True

    source_code: str = _build_state_rhs_source(
        missing_state_eqs,
        problem.get_compiler_names_dict(),
        problem.get_alias_names_dict(),
        problem.VARS_NAME,
        problem.DIFF_NAME,
        problem.VARIABLE_PARAMS_NAME,
        problem.CONSTANT_PARAMS_NAME,
    )
    state_rhs_fn = InitializationStateRhsVector(
        source_code=source_code,
        use_jit=use_jit_for_state_rhs,
        output_size=len(missing_state_eqs),
    )
    INITIALIZATION_VECTOR_CACHE.set_entry(cache_key, InitializationVectorCacheEntry(state_rhs_fn))

    with open(cache_path, "wb") as cache_file:
        pickle.dump(
            dict(
                source_code=source_code,
                use_jit=use_jit_for_state_rhs,
                output_size=len(missing_state_eqs),
            ),
            cache_file,
            protocol=pickle.HIGHEST_PROTOCOL,
        )

    report.state_rhs_vector_build_s = float(time.perf_counter() - phase_t0)
    report.state_rhs_vector_cache_hit = False
    return state_rhs_fn


def _get_reduced_initialization_persistent_cache_directory() -> Path:
    """
    Return the persistent cache directory used by reduced EMT initialization.

    :return: Persistent cache directory.
    :rtype: Path
    """
    override_path: str = os.environ.get("VERAGRID_EMT_INIT_CACHE_DIR", "")

    if len(override_path) > 0:
        cache_directory: Path = Path(override_path)
    else:
        cache_directory = Path.home() / ".VeraGrid" / "cache" / "emt_reduced_initialization"

    cache_directory.mkdir(parents=True, exist_ok=True)
    return cache_directory


def _serialize_initialization_report(report: EmtInitializationReport) -> Dict[str, object]:
    """
    Serialize an EMT initialization report into a cache-safe dictionary.

    :param report: Initialization report.
    :type report: EmtInitializationReport
    :return: Serialized report.
    :rtype: Dict[str, object]
    """
    return dict(
        status=report.status.name,
        method_requested=report.method_requested.name,
        method_used=report.method_used.name,
        initial_residual_inf=float(report.initial_residual_inf),
        final_residual_inf=float(report.final_residual_inf),
        newton_iterations=int(report.newton_iterations),
        pseudo_transient_steps=int(report.pseudo_transient_steps),
        unknown_var_count=int(report.unknown_var_count),
        unresolved_state_count=int(report.unresolved_state_count),
        automatic_dx0_count=int(report.automatic_dx0_count),
        reduced_system_build_s=float(report.reduced_system_build_s),
        runtime_param_build_s=float(report.runtime_param_build_s),
        constant_param_build_s=float(report.constant_param_build_s),
        initial_residual_eval_s=float(report.initial_residual_eval_s),
        newton_elapsed_s=float(report.newton_elapsed_s),
        pseudo_transient_elapsed_s=float(report.pseudo_transient_elapsed_s),
        dx0_completion_s=float(report.dx0_completion_s),
        x0_rebuild_s=float(report.x0_rebuild_s),
        dx0_seed_build_s=float(report.dx0_seed_build_s),
        state_rhs_vector_build_s=float(report.state_rhs_vector_build_s),
        state_rhs_vector_cache_hit=bool(report.state_rhs_vector_cache_hit),
        solution_apply_s=float(report.solution_apply_s),
        missing_dx_problem_collect_s=float(report.missing_dx_problem_collect_s),
        state_rhs_eval_s=float(report.state_rhs_eval_s),
        missing_dx_scatter_s=float(report.missing_dx_scatter_s),
        persistent_cache_hit=bool(report.persistent_cache_hit),
        persistent_cache_load_s=float(report.persistent_cache_load_s),
        persistent_cache_store_s=float(report.persistent_cache_store_s),
        elapsed_s=float(report.elapsed_s),
        message=str(report.message),
    )


def _serialize_problem_guess_map(problem: EmtProblemTemplate, guess_map: Dict[int, float], diff_guess: bool) -> Dict[str, float]:
    """
    Serialize an initialization guess map using stable variable names.

    :param problem: EMT problem instance.
    :type problem: EmtProblemTemplate
    :param guess_map: UID-keyed initialization guess map.
    :type guess_map: Dict[int, float]
    :param diff_guess: Whether the map contains differential-variable guesses.
    :type diff_guess: bool
    :return: Name-keyed initialization guess map.
    :rtype: Dict[str, float]
    """
    uid_to_name: Dict[int, str] = dict()
    serialized: Dict[str, float] = dict()
    alias_name_map: Dict[int, str] = problem.get_alias_names_dict()

    if diff_guess:
        for diff_var in problem.get_diff_vars():
            uid_to_name[diff_var.uid] = alias_name_map[diff_var.uid]
    else:
        for var in problem.get_state_vars():
            uid_to_name[var.uid] = alias_name_map[var.uid]
        for var in problem.get_algebraic_vars():
            uid_to_name[var.uid] = alias_name_map[var.uid]

    for uid, value in guess_map.items():
        if uid in uid_to_name:
            serialized[uid_to_name[uid]] = float(value)
        else:
            pass

    return serialized


def _restore_problem_guess_map(problem: Any, name_map: Dict[str, float], diff_guess: bool) -> Dict[int, float]:
    """
    Restore an initialization guess map from stable variable names.

    :param problem: EMT problem instance.
    :type problem: EmtProblemTemplate
    :param name_map: Name-keyed initialization guess map.
    :type name_map: Dict[str, float]
    :param diff_guess: Whether the map contains differential-variable guesses.
    :type diff_guess: bool
    :return: UID-keyed initialization guess map.
    :rtype: Dict[int, float]
    """
    name_to_uid: Dict[str, int] = dict()
    restored: Dict[int, float] = dict()

    alias_name_map: Dict[int, str] = problem.get_alias_names_dict()

    if diff_guess:
        for diff_var in problem.get_diff_vars():
            name_to_uid[alias_name_map[diff_var.uid]] = diff_var.uid
    else:
        for var in problem.state_vars():
            name_to_uid[alias_name_map[var.uid]] = var.uid
        for var in problem.algebraic_vars():
            name_to_uid[alias_name_map[var.uid]] = var.uid

    for name, value in name_map.items():
        if name in name_to_uid:
            restored[name_to_uid[name]] = float(value)
        else:
            pass

    return restored


def _restore_initialization_report_from_payload(
        report: EmtInitializationReport,
        payload: Dict[str, object],
) -> None:
    """
    Restore an EMT initialization report from a serialized payload.

    :param report: Initialization report updated in place.
    :type report: EmtInitializationReport
    :param payload: Serialized report payload.
    :type payload: Dict[str, object]
    :return: None.
    :rtype: None
    """
    report.status = InitializationStatus[str(payload["status"])]
    report.method_requested = EmtInitializationMethod[str(payload["method_requested"])]
    report.method_used = EmtInitializationMethod[str(payload["method_used"])]
    report.initial_residual_inf = float(payload["initial_residual_inf"])
    report.final_residual_inf = float(payload["final_residual_inf"])
    report.newton_iterations = int(payload["newton_iterations"])
    report.pseudo_transient_steps = int(payload["pseudo_transient_steps"])
    report.unknown_var_count = int(payload["unknown_var_count"])
    report.unresolved_state_count = int(payload["unresolved_state_count"])
    report.automatic_dx0_count = int(payload["automatic_dx0_count"])
    report.reduced_system_build_s = float(payload["reduced_system_build_s"])
    report.runtime_param_build_s = float(payload["runtime_param_build_s"])
    report.constant_param_build_s = float(payload["constant_param_build_s"])
    report.initial_residual_eval_s = float(payload["initial_residual_eval_s"])
    report.newton_elapsed_s = float(payload["newton_elapsed_s"])
    report.pseudo_transient_elapsed_s = float(payload["pseudo_transient_elapsed_s"])
    report.dx0_completion_s = float(payload["dx0_completion_s"])
    report.x0_rebuild_s = float(payload.get("x0_rebuild_s", 0.0))
    report.dx0_seed_build_s = float(payload.get("dx0_seed_build_s", 0.0))
    report.state_rhs_vector_build_s = float(payload.get("state_rhs_vector_build_s", 0.0))
    report.state_rhs_vector_cache_hit = bool(payload.get("state_rhs_vector_cache_hit", False))
    report.solution_apply_s = float(payload.get("solution_apply_s", 0.0))
    report.missing_dx_problem_collect_s = float(payload.get("missing_dx_problem_collect_s", 0.0))
    report.state_rhs_eval_s = float(payload.get("state_rhs_eval_s", 0.0))
    report.missing_dx_scatter_s = float(payload.get("missing_dx_scatter_s", 0.0))
    report.persistent_cache_hit = bool(payload.get("persistent_cache_hit", False))
    report.persistent_cache_load_s = float(payload.get("persistent_cache_load_s", 0.0))
    report.persistent_cache_store_s = float(payload.get("persistent_cache_store_s", 0.0))
    report.elapsed_s = float(payload["elapsed_s"])
    report.message = str(payload["message"])


def build_persistent_initialization_cache_key(
        problem: Any,
        unknown_vars: List[Var],
        residual_eqs: List[Expr],
        state_unknown_mask: np.ndarray,
        options: RmsOptions,
) -> str:
    """
    Return the deterministic cache key of one persistent reduced initialization result.

    :param problem: EMT problem being initialized.
    :type problem: EmtProblemTemplate
    :param unknown_vars: Unknown variables in the reduced system.
    :type unknown_vars: List[Var]
    :param residual_eqs: Residual equations in the reduced system.
    :type residual_eqs: List[Expr]
    :param state_unknown_mask: Reduced state mask.
    :type state_unknown_mask: np.ndarray
    :param options: EMT initialization options.
    :type options: EmtOptions
    :return: Deterministic cache key.
    :rtype: str
    """
    reduced_key: str = build_reduced_initialization_cache_key(problem, unknown_vars, residual_eqs, state_unknown_mask)

    payload: str = "|".join([
        "persistent-reduced-emt-init-v4",
        reduced_key,
        options.initialization_method.name,
        f"{float(options.init_newton_tol):.12g}",
        str(int(options.init_newton_max_iter)),
        str(int(options.init_dense_threshold)),
        str(bool(options.init_newton_backtracking)),
        str(bool(options.init_allow_state_equilibrium)),
        f"{float(options.init_ptc_dtau0):.12g}",
        f"{float(options.init_ptc_dtau_min):.12g}",
        f"{float(options.init_ptc_dtau_max):.12g}",
        str(int(options.init_ptc_max_iter)),
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _persistent_initialization_params_match(
        payload: Dict[str, object],
        runtime_params: np.ndarray,
        constant_params: np.ndarray,
) -> bool:
    """
    Return whether one persistent initialization payload matches the current parameter snapshots.

    :param payload: Cached payload.
    :type payload: Dict[str, object]
    :param runtime_params: Runtime parameter vector.
    :type runtime_params: np.ndarray
    :param constant_params: Constant parameter vector.
    :type constant_params: np.ndarray
    :return: ``True`` when the parameter snapshots match.
    :rtype: bool
    """
    runtime_snapshot_any: object = payload.get("runtime_params_snapshot", list())
    constant_snapshot_any: object = payload.get("constant_params_snapshot", list())

    if isinstance(runtime_snapshot_any, list):
        runtime_snapshot = np.asarray(runtime_snapshot_any, dtype=np.float64)
    else:
        return False

    if isinstance(constant_snapshot_any, list):
        constant_snapshot = np.asarray(constant_snapshot_any, dtype=np.float64)
    else:
        return False

    if runtime_snapshot.shape != runtime_params.shape:
        return False
    else:
        pass

    if constant_snapshot.shape != constant_params.shape:
        return False
    else:
        pass

    if runtime_snapshot.size > 0:
        if float(np.max(np.abs(runtime_snapshot - runtime_params))) > 1.0e-12:
            return False
        else:
            pass
    else:
        pass

    if constant_snapshot.size > 0:
        if float(np.max(np.abs(constant_snapshot - constant_params))) > 1.0e-12:
            return False
        else:
            pass
    else:
        pass

    return True


def load_persistent_initialization_solution(cache_key: str) -> Dict[str, object] | None:
    """
    Load one persistent reduced initialization result.

    :param cache_key: Deterministic cache key.
    :type cache_key: str
    :return: Cached payload or ``None``.
    :rtype: Dict[str, object] | None
    """
    cache_path: Path = _get_reduced_initialization_persistent_cache_directory() / f"{cache_key}.pkl"

    if cache_path.exists():
        with open(cache_path, "rb") as cache_file:
            return dict(pickle.load(cache_file))
    else:
        return None


def _store_persistent_initialization_solution(cache_key: str, payload: Dict[str, object]) -> None:
    """
    Store one persistent reduced initialization result.

    :param cache_key: Deterministic cache key.
    :type cache_key: str
    :param payload: Cache payload.
    :type payload: Dict[str, object]
    :return: None.
    :rtype: None
    """
    cache_path: Path = _get_reduced_initialization_persistent_cache_directory() / f"{cache_key}.pkl"

    with open(cache_path, "wb") as cache_file:
        pickle.dump(payload, cache_file, protocol=pickle.HIGHEST_PROTOCOL)


def build_reduced_initialization_cache_key(
        problem: Any,
        unknown_vars: List[Var],
        residual_eqs: List[Expr],
        state_unknown_mask: np.ndarray,
) -> str:
    """
    Return a deterministic cache key for one reduced Rms initialization system.

    :param problem: EMT problem being initialized.
    :type problem: EmtProblemTemplate
    :param unknown_vars: Unknown variables solved by the reduced system.
    :type unknown_vars: List[Var]
    :param residual_eqs: Residual equations enforcing consistency.
    :type residual_eqs: List[Expr]
    :param state_unknown_mask: State-mask vector.
    :type state_unknown_mask: np.ndarray
    :return: Deterministic cache key.
    :rtype: str
    """
    unknown_var_tokens: List[str] = list()
    residual_tokens: List[str] = list()
    mask_tokens: List[str] = list()
    index: int = 0

    while index < len(unknown_vars):
        unknown_var_tokens.append(unknown_vars[index].name)
        index += 1

    index = 0
    while index < len(residual_eqs):
        residual_tokens.append(expression2numba(residual_eqs[index].simplify(), problem.get_compiler_names_dict()))
        index += 1

    index = 0
    while index < state_unknown_mask.shape[0]:
        mask_tokens.append(str(float(state_unknown_mask[index])))
        index += 1

    payload: str = "|".join([
        "reduced-emt-init",
        problem.VARS_NAME,
        problem.DIFF_NAME,
        problem.VARIABLE_PARAMS_NAME,
        problem.CONSTANT_PARAMS_NAME,
        str(problem.get_states_number()),
        str(problem.get_algebraic_var_number()),
        str(len(unknown_vars)),
        str(len(residual_eqs)),
        "::".join(unknown_var_tokens),
        "::".join(mask_tokens),
        "::".join(residual_tokens),
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _build_state_rhs_cache_key(problem: EmtProblemTemplate, state_eqs: List[Expr]) -> str:
    """
    Return the cache key for the symbolic vector used to compute missing ``dx0``.

    :param problem: EMT problem being initialized.
    :type problem: EmtProblemTemplate
    :param state_eqs: State equations.
    :type state_eqs: List[Expr]
    :return: Deterministic cache key.
    :rtype: str
    """
    expr_tokens: List[str] = list()
    index: int = 0

    while index < len(state_eqs):
        expr_tokens.append(expression2numba(state_eqs[index].simplify(), problem.get_compiler_names_dict()))
        index += 1

    payload: str = "|".join([
        "state-rhs-vector",
        problem.VARS_NAME,
        problem.DIFF_NAME,
        problem.VARIABLE_PARAMS_NAME,
        problem.CONSTANT_PARAMS_NAME,
        str(problem.get_states_number()),
        "::".join(expr_tokens),
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _collect_missing_dx_problem(problem: EmtProblemTemplate) -> Tuple[List[Var], List[Expr]]:
    """
    Return the differential variables that still need ``dx0`` and their state equations.

    :param problem: EMT problem being initialized.
    :type problem: EmtProblemTemplate
    :return: Pair ``(missing_diff_vars, missing_state_eqs)``.
    :rtype: Tuple[List[Var], List[Expr]]
    """
    diff_vars: List[Var] = problem.get_diff_vars()
    state_eqs: List[Expr] = problem.get_state_eqs()
    missing_diff_vars: List[Var] = list()
    missing_state_eqs: List[Expr] = list()
    idx: int = 0

    while idx < len(diff_vars):
        diff_var: Var = diff_vars[idx]

        if diff_var.uid in problem.diff_init_guess:
            diff_var = diff_var
        else:
            missing_diff_vars.append(diff_var)
            missing_state_eqs.append(state_eqs[idx])

        idx += 1

    return missing_diff_vars, missing_state_eqs


def build_uid_bindings(
        eq: Union[Expr, Const],
        event_params_array: np.ndarray,
        x: np.ndarray,
        params_array: np.ndarray,
        dx: np.ndarray,
        uid2idx_event_params: Dict[int, int],
        uid2idx_vars: Dict[int, int],
        uid2idx_params: Dict[int, int],
        uid2idx_diff: Dict[int, int]
) -> Dict[int, float]:
    """
    Builds a mapping of Unique Identifiers (UIDs) to their current numeric values.

    :param eq: The symbolic expression to analyze.
    :param event_params_array: Array containing resolved event parameters.
    :param x: Array containing state and algebraic variables.
    :param params_array: Array containing constant model parameters.
    :param dx: Array containing derivative values.
    :param uid2idx_event_params: Mapping of UID to index for event parameters.
    :param uid2idx_vars: Mapping of UID to index for variables.
    :param uid2idx_params: Mapping of UID to index for constants.
    :param uid2idx_diff: Mapping of UID to index for derivatives.
    :return: A dictionary mapping UIDs to their float values.
    """
    uid_bindings: Dict[int, float] = dict()
    vars_list: List[Var] = find_vars_order(eq)

    for vr in vars_list:
        resolved_value: Optional[float] = None
        event_idx: Optional[int] = uid2idx_event_params.get(vr.uid, None)
        state_idx: Optional[int] = uid2idx_vars.get(vr.uid, None)
        param_idx: Optional[int] = uid2idx_params.get(vr.uid, None)
        diff_idx: Optional[int] = uid2idx_diff.get(vr.uid, None)

        if event_idx is None:
            if state_idx is None:
                if param_idx is None:
                    if diff_idx is None:
                        resolved_value = None
                    else:
                        resolved_value = float(dx[diff_idx])
                else:
                    resolved_value = float(params_array[param_idx])
            else:
                resolved_value = float(x[state_idx])
        else:
            resolved_value = float(event_params_array[event_idx])

        if resolved_value is None:
            uid_bindings = uid_bindings
        else:
            uid_bindings[vr.uid] = resolved_value

    return uid_bindings


def event_param_is_resolved(v: Var, mdl: Block) -> bool:
    """
    Checks if an event parameter has been assigned a concrete value.

    :param v: The variable representing the event parameter.
    :param mdl: The symbolic model block.
    :return: True if resolved, False otherwise.
    """
    if v in mdl.event_dict:
        eqv: Union[Expr, Const] = mdl.event_dict[v]
        if isinstance(eqv, Const):
            if eqv.value is None:
                return False
            else:
                return True
        else:
            return True
    else:
        return True


def can_compute_init(
        var: Var,
        eq: Union[Expr, Const],
        mdl: Block,
        init_guess: Dict[int, float],
        diff_init_guess: Dict[int, float],
        uid2idx_diff: Dict[int, int],
        uid2idx_vars: Dict[int, int]
) -> bool:
    """
    Determines if an initialization equation is computable based on current knowns.

    :param var: Target variable.
    :param eq: The expression to evaluate.
    :param mdl: The model block.
    :param init_guess: Current variable guesses.
    :param diff_init_guess: Current derivative guesses.
    :param uid2idx_diff: UID map for derivatives.
    :param uid2idx_vars: UID map for variables.
    :return: Boolean indicating if all dependencies are met.
    """
    vars_needed: List[Var] = get_expression_vars(eq)
    for v_dep in vars_needed:
        if v_dep.uid == var.uid:
            dependency_ready: bool = True
        elif v_dep in mdl.event_dict:
            dependency_ready = event_param_is_resolved(v_dep, mdl)
        elif v_dep.uid in uid2idx_diff:
            dependency_ready = v_dep.uid in diff_init_guess
        elif v_dep.uid in uid2idx_vars:
            dependency_ready = v_dep.uid in init_guess
        else:
            dependency_ready = True

        if dependency_ready:
            dependency_ready = dependency_ready
        else:
            return False
    return True


def init_explicit_emt(
        mdl: Block,
        sys_vars: Dict[int, Var],
        sys_diff_vars: Dict[int, Var],
        variable_parameters: List[Var],
        event_parameters_eqs: List[Union[Expr, Const]],
        constant_parameters: List[Var],
        init_guess: Dict[int, float],
        diff_init_guess: Dict[int, float],
        uid2idx_vars: Dict[int, int],
        uid2idx_diff: Dict[int, int],
        uid2idx_params: Dict[int, int],
        uid2idx_event_params: Dict[int, int],
        compiler_names_dict: Dict[int, str],
        alias_names_dict: Dict[int, str],
        VARIABLE_PARAMS_NAME: str,
        VARS_NAME: str,
        DIFF_NAME: str,
        CONSTANT_PARAMS_NAME: str,
        verbose: bool = False) -> Optional[Tuple[Dict[int, float], Dict[int, float]]]:
    """
    Initializes the EMT model by solving initialization and differential equations.

    This function performs a topological-like resolution of model variables.
    It uses fixed-point iteration for self-referencing equations and handles
    dependencies between algebraic and differential states.

    :param mdl: Symbolic model block.
    :param sys_vars: Registry of system variables.
    :param sys_diff_vars: Registry of system differential variables.
    :param variable_parameters: List of parameters that change on events.
    :param event_parameters_eqs: Initial equations for event parameters.
    :param constant_parameters: List of constant parameters.
    :param init_guess: Initial guesses for variables.
    :param diff_init_guess: Initial guesses for derivatives.
    :param uid2idx_vars: Index map for variables.
    :param uid2idx_diff: Index map for derivatives.
    :param uid2idx_params: Index map for parameters.
    :param uid2idx_event_params: Index map for event parameters.
    :param compiler_names_dict: Map for variable naming in compilation.
    :param alias_names_dict: Map for variable aliases.
    :param VARIABLE_PARAMS_NAME: Name for variable parameter array.
    :param VARS_NAME: Name for state variable array.
    :param DIFF_NAME: Name for derivative array.
    :param CONSTANT_PARAMS_NAME: Name for constant parameter array.
    :param verbose: Whether to print explicit initialization diagnostics.
    :return: Updated initial guesses and modified model block.
    """

    # Initialize memory buffers for numerical evaluation
    # EMT solvers require flat arrays for efficient computation
    x: np.ndarray = np.ones(len(sys_vars))
    dx: np.ndarray = np.zeros(len(sys_diff_vars))

    # Hydrate buffers with existing user-provided guesses
    for uid, val in init_guess.items():
        if verbose:
            print(f"Var {sys_vars[uid].name} with uid= {uid} initialized with val: {val} ")
        x[uid2idx_vars[uid]] = val

    for uid, val in diff_init_guess.items():
        if verbose:
            print(f"Diff var {sys_diff_vars[uid].name} with uid= {uid} initialized with val: {val} ")
        dx[uid2idx_diff[uid]] = val

    # Setup constant parameter array
    params_array: np.ndarray = np.zeros(len(constant_parameters))
    for param, const in mdl.parameters.items():
        params_array[uid2idx_params[param.uid]] = const.value

    # Primary pass: resolve basic event parameters that are constant or immediate
    event_params_array: np.ndarray = np.ones(len(variable_parameters))
    for event_param in mdl.event_dict.keys():
        eq: Union[Expr, Const] = mdl.event_dict[event_param]

        # Determine if the expression is concrete enough to evaluate
        is_concrete_const: bool = isinstance(eq, Const) and eq.value is not None
        is_expression: bool = not isinstance(eq, Const)

        if is_concrete_const or is_expression:
            vars_list: List[Var] = find_vars_order(eq)
            # Bind current values for calculation
            uid_bindings: Dict[int, float] = dict()
            for var in vars_list:
                uid_bindings[var.uid] = float(event_params_array[uid2idx_event_params[var.uid]])

            result: float = eq.eval_uid(uid_bindings)
            event_params_array[uid2idx_event_params[event_param.uid]] = result
            if verbose:
                print(f"event_param:{event_param.name} initialized from events_dict with: {result}")
        else:
            event_param = event_param

    # Track pending equations that require dependency resolution
    init_pending: Dict[int, Tuple[Var, Union[Expr, Const]]] = dict()
    for v, e in mdl.init_eqs.items():
        init_pending[v.uid] = (v, e)

    diff_pending: Dict[int, Tuple[Var, Union[Expr, Const]]] = dict()
    for v, e in mdl.diff_init_eqs.items():
        diff_pending[v.uid] = (v, e)

    # Iterative solver loop
    while len(init_pending) > 0 or len(diff_pending) > 0:
        progress_made: bool = False

        # Solve for Algebraic/State variables
        for uid in list(init_pending.keys()):
            var, eq = init_pending[uid]
            if can_compute_init(var, eq, mdl, init_guess, diff_init_guess, uid2idx_diff, uid2idx_vars):

                # Logic for variables that are registered as event parameters
                if var in mdl.event_dict:
                    if isinstance(eq, Const) and eq.value is not None:
                        event_params_array[uid2idx_event_params[var.uid]] = float(eq.value)
                    else:
                        bindings: Dict[int, float] = build_uid_bindings(
                            eq, event_params_array, x, params_array, dx,
                            uid2idx_event_params, uid2idx_vars, uid2idx_params, uid2idx_diff
                        )
                        res: float = eq.eval_uid(bindings)
                        mdl.event_dict[var] = Const(res)
                        event_params_array[uid2idx_event_params[var.uid]] = res
                        if verbose:
                            print(f"event_param:{var.name} initialized from init_eqs with: {res}")
                        else:
                            pass



                        param_idx: int = variable_parameters.index(var)
                        event_parameters_eqs[param_idx].value = float(res)
                        event_params_array[param_idx] = float(res)

                # Logic for standard algebraic variables
                else:
                    vars_in_eqs: List[Var] = get_expression_vars(eq)
                    if var not in vars_in_eqs:
                        # Direct assignment
                        bindings = build_uid_bindings(
                            eq, event_params_array, x, params_array, dx,
                            uid2idx_event_params, uid2idx_vars, uid2idx_params, uid2idx_diff
                        )
                        res = eq.eval_uid(bindings)
                        init_guess[var.uid] = res
                        x[uid2idx_vars[var.uid]] = res
                    else:
                        # Implicit resolution using a damped fixed-point iteration
                        eq_fn: SymbolicVector = SymbolicVector(
                            [eq], compiler_names_dict, alias_names_dict,
                            VARS_NAME, DIFF_NAME, VARIABLE_PARAMS_NAME, CONSTANT_PARAMS_NAME
                        )

                        # Fixed-point parameters
                        tol: float = 1e-8
                        error: float = 1.0
                        alpha: float = 1.3
                        curr_x: float = 1.2

                        x[uid2idx_vars[var.uid]] = curr_x
                        while error > tol:
                            try:
                                # Evaluate expression with current state
                                eval_res: float = float(eq_fn(x, dx, event_params_array, params_array)[0])
                            except Exception:
                                # Fallback/Reset on numerical instability
                                x[uid2idx_vars[var.uid]] = -0.1
                                eval_res = float(eq_fn(x, dx, event_params_array, params_array)[0])

                            # Update with damping (Successive Over-Relaxation style)
                            x[uid2idx_vars[var.uid]] = (1 - alpha) * curr_x + alpha * eval_res
                            error = float(abs(eval_res - curr_x))
                            curr_x = float(x[uid2idx_vars[var.uid]])

                        init_guess[var.uid] = curr_x

                del init_pending[uid]
                progress_made = True
            else:
                uid = uid

        # Solve for Differential variables
        for uid in list(diff_pending.keys()):
            d_var, eq = diff_pending[uid]
            # Use separate check for diff equations to ensure variables are ready
            if can_compute_init(d_var, eq, mdl, init_guess, diff_init_guess, uid2idx_diff, uid2idx_vars):
                vars_in_eqs = get_expression_vars(eq)

                if d_var not in vars_in_eqs:
                    bindings = build_uid_bindings(
                        eq, event_params_array, x, params_array, dx,
                        uid2idx_event_params, uid2idx_vars, uid2idx_params, uid2idx_diff
                    )
                    res = eq.eval_uid(bindings)
                    diff_init_guess[d_var.uid] = res
                    dx[uid2idx_diff[d_var.uid]] = res
                else:
                    # Fixed-point iteration for derivatives
                    eq_fn = SymbolicVector(
                        [eq], compiler_names_dict, alias_names_dict,
                        VARS_NAME, DIFF_NAME, VARIABLE_PARAMS_NAME, CONSTANT_PARAMS_NAME
                    )
                    tol = 1e-8
                    error = 1.0
                    alpha = 1.3
                    curr_dx: float = 1.2

                    dx[uid2idx_diff[d_var.uid]] = curr_dx
                    while error > tol:
                        try:
                            eval_res = float(eq_fn(x, dx, event_params_array, params_array)[0])
                        except Exception:
                            dx[uid2idx_diff[d_var.uid]] = -0.1
                            eval_res = float(eq_fn(x, dx, event_params_array, params_array)[0])

                        dx[uid2idx_diff[d_var.uid]] = (1 - alpha) * curr_dx + alpha * eval_res
                        error = float(abs(eval_res - curr_dx))
                        curr_dx = float(dx[uid2idx_diff[d_var.uid]])

                    diff_init_guess[d_var.uid] = curr_dx

                del diff_pending[uid]
                progress_made = True
            else:
                uid = uid

        # If no variables were resolved in this pass, the system is unsolvable
        if not progress_made:
            # We return None to signify failure rather than raising, per directive
            return None
        else:
            progress_made = progress_made

    return init_guess, diff_init_guess


def init_pseudo_transient(problem: EmtProblemTemplate, options: EmtOptions) -> EmtInitializationReport:
    """
    Run the EMT-native initialization workflow forcing the pseudo-transient path.

    :param problem: EMT problem being initialized.
    :param options: EMT simulation options.
    :return: Initialization report.
    """
    options.initialization_method = EmtInitializationMethod.PseudoTransient
    return run_rms_native_initialization(problem, options)


def run_emt_explicit_initialization(problem: EmtProblemTemplate, verbose: bool = False) -> None:
    """
    Run the explicit EMT initialization stage on a full problem object.

    :param problem: EMT problem being initialized.
    :param verbose: Print explicit initialization details.
    :return: None
    """
    sys_vars: Dict[int, Var] = {v.uid: v for v in (problem.get_state_vars() + problem.get_algebraic_vars())}
    sys_diff_vars: Dict[int, Var] = {dv.uid: dv for dv in problem.get_diff_vars()}

    init_explicit_emt(
        mdl=problem.sys_block,
        sys_vars=sys_vars,
        sys_diff_vars=sys_diff_vars,
        variable_parameters=problem.get_variable_parameters(),
        event_parameters_eqs=problem.get_event_parameter_equations(),
        constant_parameters=problem.get_constant_parameters(),
        init_guess=problem.init_guess,
        diff_init_guess=problem.diff_init_guess,
        uid2idx_vars=problem.uid2idx_vars,
        uid2idx_diff=problem.uid2idx_diff,
        uid2idx_params=problem.uid2idx_params,
        uid2idx_event_params=problem.uid2idx_event_params,
        compiler_names_dict=problem.get_compiler_names_dict(),
        alias_names_dict=problem.get_alias_names_dict(),
        VARIABLE_PARAMS_NAME=problem.VARIABLE_PARAMS_NAME,
        VARS_NAME=problem.VARS_NAME,
        DIFF_NAME=problem.DIFF_NAME,
        CONSTANT_PARAMS_NAME=problem.CONSTANT_PARAMS_NAME,
        verbose=verbose,
    )
    problem.rebuild_runtime_param_vectors()


class ReducedInitializationSystem:
    """
    Reduced RMS initialization system built on top of the unresolved variables only.
    """

    __slots__ = [
        "unknowns",
        "unknown_vars",
        "unknown_events",
        "residual_eqs",
        "state_unknown_mask",
        "residual_fn",
        "jacobian_fn",
    ]

    def __init__(
            self,
            problem: Any,
            unknowns: List[Var],
            unknown_vars: List[Var],
            unknown_events: List[Var],
            residual_eqs: List[Expr],
            state_unknown_mask: np.ndarray,
    ) -> None:
        """
        Compile the reduced residual and Jacobian used by the consistent initializer.

        :param problem: Rms problem being initialized.
        :param unknown_vars: Unknown variables solved by the reduced system.
        :param residual_eqs: Residual equations enforcing consistency.
        :param state_unknown_mask: Mask marking which reduced unknowns correspond to states.
        :return: None
        """
        self.unknowns = unknowns
        self.unknown_vars = unknown_vars
        self.unknown_events = unknown_events
        self.residual_eqs = residual_eqs
        self.state_unknown_mask = state_unknown_mask

        self.residual_fn = SymbolicVector(
            eqs=residual_eqs,
            compiler_names_dict=problem.get_compiler_names_dict(),
            alias_names_dict=problem.get_alias_names_dict(),
            VARS_NAME=problem.VARS_NAME,
            DIFF_NAME=problem.DIFF_NAME,
            EVENT_PARAMS_NAME=problem.VARIABLE_PARAMS_NAME,
            PARAMS_NAME=problem.CONSTANT_PARAMS_NAME,
        )
        self.jacobian_fn = SymbolicJacobian(
            eqs=residual_eqs,
            variables=unknowns,
            compiler_names_dict=problem.get_compiler_names_dict(),
            alias_names_dict=problem.get_alias_names_dict(),
            VARS_NAME=problem.VARS_NAME,
            DIFF_NAME=problem.DIFF_NAME,
            EVENT_PARAMS_NAME=problem.VARIABLE_PARAMS_NAME,
            PARAMS_NAME=problem.CONSTANT_PARAMS_NAME,
        )


def build_constant_param_array(problem: Any) -> np.ndarray:
    """
    Build the dense constant-parameter vector used by the initialization solvers.

    :param problem: EMT problem being initialized.
    :return: Constant-parameter array.
    """
    const_values: List[Const] = problem.get_parameters_values()
    return np.asarray([float(item.value) for item in const_values], dtype=np.float64)


def build_runtime_param_array(problem: Any) -> np.ndarray:
    """
    Build the runtime-parameter snapshot at the initialization time.

    :param problem: EMT problem being initialized.
    :return: Runtime-parameter array at time zero.
    """
    runtime_params: np.ndarray = problem.event_params_values.copy()
    runtime_params = problem.def_event_params_fn(runtime_params, 0.0)
    return runtime_params


def build_state_equation_lookup(problem: Any) -> Dict[int, Expr]:
    """
    Build a UID lookup for state equations.

    :param problem: EMT problem being initialized.
    :return: Mapping from state variable UID to its differential right-hand side.
    """
    lookup: Dict[int, Expr] = dict()
    state_vars: List[Var] = problem.state_vars
    state_eqs: List[Expr] = problem.state_eqs

    idx: int = 0
    while idx < len(state_vars):
        lookup[state_vars[idx].uid] = state_eqs[idx]
        idx += 1

    return lookup


def extract_unknown_vector(problem: Any, unknown_vars: List[Var], x: np.ndarray) -> np.ndarray:
    """
    Extract the reduced unknown vector from the full EMT variable vector.

    :param problem: Rms problem being initialized.
    :param unknown_vars: Unknown variables solved by the reduced system.
    :param x: Full EMT variable vector.
    :return: Reduced unknown vector.
    """
    n_unknown: int = len(unknown_vars)
    out: np.ndarray = np.zeros(n_unknown, dtype=np.float64)

    idx: int = 0
    while idx < n_unknown:
        var: Var = unknown_vars[idx]
        out[idx] = float(x[problem.uid2idx_vars[var.uid]])
        idx += 1

    return out

def extract_unknown_events_vector(problem: Any, unknown_events: List[Var], event_x: np.ndarray) -> np.ndarray:
    """
    Extract the reduced unknown vector from the full EMT variable vector.

    :param problem: Rms problem being initialized.
    :param unknown_vars: Unknown variables solved by the reduced system.
    :param x: Full EMT variable vector.
    :return: Reduced unknown vector.
    """
    n_unknown: int = len(unknown_events)
    out: np.ndarray = np.zeros(n_unknown, dtype=np.float64)

    idx: int = 0
    while idx < n_unknown:
        var: Var = unknown_events[idx]
        out[idx] = float(event_x[problem.uid2idx_event_params[var.uid]])
        idx += 1

    return out


def scatter_unknown_vector(problem: Any, unknown_vars: List[Var], x: np.ndarray, reduced_x: np.ndarray) -> None:
    """
    Scatter the reduced unknown vector back into the full Rms variable vector.

    :param problem: EMT problem being initialized.
    :param unknown_vars: Unknown variables solved by the reduced system.
    :param x: Full EMT variable vector updated in place.
    :param reduced_x: Reduced unknown vector.
    :return: None
    """
    idx: int = 0
    while idx < len(unknown_vars):
        var: Var = unknown_vars[idx]
        x[problem.uid2idx_vars[var.uid]] = float(reduced_x[idx])
        idx += 1

def scatter_unknown_event_vector(problem: Any, unknown_events: List[Var], event_x: np.ndarray, reduced_event_x: np.ndarray) -> None:
    """
    Scatter the reduced unknown vector back into the full Rms variable vector.

    :param problem: EMT problem being initialized.
    :param unknown_vars: Unknown variables solved by the reduced system.
    :param x: Full EMT variable vector updated in place.
    :param reduced_x: Reduced unknown vector.
    :return: None
    """
    idx: int = 0
    while idx < len(unknown_events):
        var: Var = unknown_events[idx]
        event_x[problem.uid2idx_event_params[var.uid]] = float(reduced_event_x[idx])
        idx += 1


def build_reduced_initialization_system(
        problem: Any,
        allow_state_equilibrium: bool,
) -> ReducedInitializationSystem | None:
    """
    Build the reduced initialization system for unresolved EMT variables.

    The reduced system always enforces all algebraic equations. In addition, any
    state variable still missing after the explicit stage receives one extra
    consistency equation, either from `init_eqs` or from a steady-state residual.

    :param problem: EMT problem being initialized.
    :param allow_state_equilibrium: Whether unresolved states may use f(x,z,p)=0.
    :return: Reduced initialization system or None if nothing remains to solve.
    """
    reduced_problem = collect_reduced_initialization_problem(problem, allow_state_equilibrium)

    if reduced_problem is None:
        return None
    else:
        unknowns, unknown_vars, unknown_events, residual_eqs, mask_array = reduced_problem
        return ReducedInitializationSystem(
            problem=problem,
            unknowns = unknowns,
            unknown_vars=unknown_vars,
            unknown_events=unknown_events,
            residual_eqs=residual_eqs,
            state_unknown_mask=mask_array,
        )


def collect_reduced_initialization_problem(
        problem: Any,
        allow_state_equilibrium: bool,
) -> Tuple[List[Var], List[Var], List[Var], List[Expr], np.ndarray] | None:
    """
    Collect the reduced initialization unknowns and residual equations without compiling them.

    :param problem: EMT problem being initialized.
    :type problem: EmtProblemTemplate
    :param allow_state_equilibrium: Whether unresolved states may use ``f(x,z,p)=0``.
    :type allow_state_equilibrium: bool
    :return: Tuple ``(unknown_vars, residual_eqs, state_unknown_mask)`` or ``None``.
    :rtype: Tuple[List[Var], List[Expr], np.ndarray] | None
    """
    state_unknown_vars: List[Var] = list()
    state_residual_eqs: List[Expr] = list()
    algebraic_unknown_vars: List[Var] = list()
    algebraic_residual_eqs: List[Expr] = list()
    state_eq_lookup: Dict[int, Expr] = build_state_equation_lookup(problem)
    init_eq_lookup: Dict[Var, Expr] = problem.sys_block.init_eqs
    algebraic_vars: List[Var] = problem.algebraic_vars
    algebraic_eqs: List[Expr] = problem.algebraic_eqs
    for state_var in problem.state_vars:
        if state_var.uid not in problem.init_guess:
            state_unknown_vars.append(state_var)

            if state_var in init_eq_lookup:
                state_residual_eqs.append(state_var - init_eq_lookup[state_var])
            elif allow_state_equilibrium and state_var.uid in state_eq_lookup:
                state_residual_eqs.append(state_eq_lookup[state_var.uid])
            else:
                state_residual_eqs.append(state_var)

    # Algebraic PF/explicit values are seeds, not fixed values. Consistent
    # initialization must enforce every assembled network/device residual.
    algebraic_unknown_vars.extend(algebraic_vars)
    algebraic_residual_eqs.extend(algebraic_eqs)

    unknown_vars: List[Var] = state_unknown_vars + algebraic_unknown_vars
    residual_eqs: List[Expr] = state_residual_eqs + algebraic_residual_eqs
    state_unknown_flags: List[float] = (
        [1.0] * len(state_unknown_vars)
        + [0.0] * len(algebraic_unknown_vars)
    )

    if len(unknown_vars) == 0:
        return None
    else:
        return (
            unknown_vars,
            unknown_vars,
            [],
            residual_eqs,
            np.asarray(state_unknown_flags, dtype=np.float64),
        )


def evaluate_initialization_residual(
        reduced_system: ReducedInitializationSystem,
        problem: Any,
        x: np.ndarray,
        dx: np.ndarray,
        runtime_params: np.ndarray,
        constant_params: np.ndarray,
) -> np.ndarray:
    # Todo: this function can be eliminated and calculated directly
    """
    Evaluate the reduced initialization residual.

    :param reduced_system: Reduced initialization system.
    :param problem: EMT problem being initialized.
    :param x: Full EMT variable vector.
    :param dx: Full EMT differential vector.
    :param runtime_params: Runtime-parameter vector.
    :param constant_params: Constant-parameter vector.
    :return: Reduced residual vector.
    """
    _unused = problem
    return reduced_system.residual_fn(x, dx, runtime_params, constant_params).copy()


def evaluate_initialization_jacobian(
        reduced_system: ReducedInitializationSystem,
        problem: Any,
        x: np.ndarray,
        dx: np.ndarray,
        runtime_params: np.ndarray,
        constant_params: np.ndarray,
) -> sp.csc_matrix:
    # Todo: this function can be eliminated and calculated directly
    """
    Evaluate the reduced initialization Jacobian.

    :param reduced_system: Reduced initialization system.
    :param problem: EMT problem being initialized.
    :param x: Full EMT variable vector.
    :param dx: Full EMT differential vector.
    :param runtime_params: Runtime-parameter vector.
    :param constant_params: Constant-parameter vector.
    :return: Reduced sparse Jacobian.
    """
    _unused = problem
    return reduced_system.jacobian_fn(x, dx, runtime_params, constant_params, 1.0).tocsc(copy=True)


def _max_abs_value(values: np.ndarray) -> float:
    """
    Return the infinity norm of one dense vector.

    :param values: Dense vector.
    :return: Maximum absolute value.
    """
    if values.size == 0:
        return 0.0
    else:
        return float(np.max(np.abs(values)))


def solve_reduced_linear_system(
        matrix: sp.csc_matrix,
        rhs: np.ndarray,
        dense_threshold: int,
) -> np.ndarray:
    """
    Solve one reduced linear system using a dense or sparse backend depending on size.

    :param matrix: Reduced Jacobian-like matrix.
    :param rhs: Right-hand-side vector.
    :param dense_threshold: Dense/sparse switching threshold.
    :return: Linear-system solution vector.
    """
    n_unknown: int = int(matrix.shape[0])

    if n_unknown <= dense_threshold:
        dense_matrix: np.ndarray = matrix.toarray()
        try:
            return np.linalg.solve(dense_matrix, rhs)
        except np.linalg.LinAlgError:
            solution, _, _, _ = np.linalg.lstsq(dense_matrix, rhs, rcond=None)
            return solution
    else:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error")
                return spla.spsolve(matrix, rhs)
        except Exception:
            lsqr_solution = spla.lsqr(matrix, rhs)
            return np.asarray(lsqr_solution[0], dtype=np.float64)


def run_reduced_newton_initialization(
        reduced_system: ReducedInitializationSystem,
        problem: Any,
        event_x: np.ndarray,
        x: np.ndarray,
        dx: np.ndarray,
        constant_params: np.ndarray,
) -> bool:
    """
    Solve the reduced initialization system with damped sparse Newton iterations.

    :param reduced_system: Reduced initialization system.
    :param problem: EMT problem being initialized.
    :param x: Full EMT variable vector updated in place.
    :param event_x: Full Rms variable vector updated in place.
    :param dx: Full EMT differential vector.
    :param runtime_params: Runtime-parameter vector.
    :param constant_params: Constant-parameter vector.
    :param options: EMT simulation options.
    :param report: Initialization report updated in place.
    :return: True if Newton converged.
    """
    reduced_x: np.ndarray = extract_unknown_vector(problem, reduced_system.unknown_vars, x)
    reduced_event_x: np.ndarray = extract_unknown_events_vector(problem, reduced_system.unknown_events, event_x)
    max_iter: int = max(1, int(problem.options.max_iter))
    tol: float = max(float(problem.options.tolerance), 1e-10)

    iter_idx: int = 0
    while iter_idx < max_iter:
        scatter_unknown_vector(problem, reduced_system.unknown_vars, x, reduced_x)
        scatter_unknown_event_vector(problem, reduced_system.unknown_events, event_x, reduced_event_x)
        residual: np.ndarray = evaluate_initialization_residual(reduced_system, problem, x, dx, event_x, constant_params)
        res_norm: float = _max_abs_value(residual)

        if res_norm <= tol:
            return True

        jacobian: sp.csc_matrix = evaluate_initialization_jacobian(reduced_system, problem, x, dx, event_x, constant_params)
        delta: np.ndarray = solve_reduced_linear_system(jacobian, -residual, 48)

        if not np.all(np.isfinite(delta)):
            return False

        # split delta array into vars and events


        alpha: float = 1.0
        accepted: bool = False
        while alpha >= 1.0e-4:
            if len(reduced_x) != 0:
                trial_reduced_x: np.ndarray = reduced_x + alpha * delta[:len(reduced_x)]
            else:
                trial_reduced_x = reduced_x
            if len(reduced_event_x) != 0:
                trial_reduced_event_x: np.ndarray = reduced_event_x + alpha * delta[len(reduced_x):]
            else:
                trial_reduced_event_x = reduced_event_x
            scatter_unknown_vector(problem, reduced_system.unknown_vars, x, trial_reduced_x)
            scatter_unknown_event_vector(problem, reduced_system.unknown_events, event_x, trial_reduced_event_x)
            trial_residual: np.ndarray = evaluate_initialization_residual(reduced_system, problem, x, dx, event_x, constant_params)
            trial_norm: float = _max_abs_value(trial_residual)
            init_newton_backtracking = True
            if (not init_newton_backtracking) or (trial_norm < res_norm):
                reduced_x = trial_reduced_x
                reduced_event_x = trial_reduced_event_x
                accepted = True
                break
            else:
                alpha *= 0.5

        if accepted:
            reduced_x = reduced_x
            reduced_event_x = reduced_event_x

            iter_idx += 1

        else:
            return False



    return False


def run_reduced_pseudo_transient_initialization(
        reduced_system: ReducedInitializationSystem,
        problem: EmtProblemTemplate,
        x: np.ndarray,
        event_x: np.ndarray,
        dx: np.ndarray,
        constant_params: np.ndarray,
) -> bool:
    """
    Solve the reduced initialization system with a pseudo-transient fallback.

    :param reduced_system: Reduced initialization system.
    :param problem: EMT problem being initialized.
    :param x: Full EMT variable vector updated in place.
    :param dx: Full EMT differential vector.
    :param event_x: Runtime-parameter vector.
    :param constant_params: Constant-parameter vector.
    :return: True if pseudo-transient converged.
    """
    reduced_x: np.ndarray = extract_unknown_vector(problem, reduced_system.unknown_vars, x)
    reduced_event_x: np.ndarray = extract_unknown_events_vector(problem, reduced_system.unknown_events, event_x)
    dtau: float = 1.0
    dtau_min: float = 1e-6
    dtau_max: float =  1e1
    max_iter: int = 60
    tol: float = 1e-8
    identity_mask: np.ndarray = np.ones(len(reduced_system.unknown_vars), dtype=np.float64)
    mass_matrix: sp.csc_matrix = sp.diags(identity_mask / max(dtau, dtau_min), format="csc")

    iter_idx: int = 0
    while iter_idx < max_iter:
        scatter_unknown_vector(problem, reduced_system.unknown_vars, x, reduced_x)
        scatter_unknown_event_vector(problem, reduced_system.unknown_events, x, reduced_event_x)
        residual: np.ndarray = evaluate_initialization_residual(reduced_system, problem, x, dx, event_x, constant_params)
        res_norm: float = _max_abs_value(residual)

        if res_norm <= tol:

            return True

        jacobian: sp.csc_matrix = evaluate_initialization_jacobian(reduced_system, problem, x, dx, event_x, constant_params)
        mass_matrix = sp.diags(identity_mask / max(dtau, dtau_min), format="csc")
        linear_matrix: sp.csc_matrix = (jacobian + mass_matrix).tocsc()

        delta: np.ndarray = solve_reduced_linear_system(linear_matrix, -residual, 48)

        if np.all(np.isfinite(delta)):
            trial_reduced_x: np.ndarray = reduced_x + delta[:len(reduced_x)]
            trial_reduced_event_x: np.ndarray = reduced_event_x + delta[len(reduced_x):]
            scatter_unknown_vector(problem, reduced_system.unknown_vars, x, trial_reduced_x)
            scatter_unknown_event_vector(problem, reduced_system.unknown_events, event_x, trial_reduced_event_x)
            trial_residual: np.ndarray = evaluate_initialization_residual(reduced_system, problem, x, dx, event_x, constant_params)
            trial_norm: float = _max_abs_value(trial_residual)

            if trial_norm < res_norm:
                reduced_x = trial_reduced_x
                reduced_event_x = trial_reduced_event_x
                dtau = min(dtau_max, dtau * 2.0)
            else:
                dtau = max(dtau_min, dtau * 0.5)
        else:
            delta = solve_reduced_linear_system(linear_matrix, -residual, 48)
            if np.all(np.isfinite(delta)):
                reduced_x = reduced_x + delta[len(reduced_x):]
                reduced_event_x = reduced_event_x + delta[:len(reduced_x)]
                dtau = min(dtau_max, dtau * 2.0)
            else:
                dtau = max(dtau_min, dtau * 0.5)

        iter_idx += 1

    return False


def apply_solution_to_problem(problem: Any, x: np.ndarray, event_x: np.ndarray) -> None:
    """
    Persist the reduced-solve state vector back into the initialization guess map.

    :param problem: EMT problem being initialized.
    :param x: Full EMT variable vector.
    :return: None
    """
    all_vars: List[Var] = list(problem.state_vars) + list(problem.algebraic_vars)
    for var in all_vars:
        problem.init_guess[var.uid] = float(x[problem.uid2idx_vars[var.uid]])

# def compute_missing_dx0(problem: Any,
#                         x_full: np.ndarray | None = None,
#                         dx_full: np.ndarray | None = None,
#                         runtime_params: np.ndarray | None = None,
#                         constant_params: np.ndarray | None = None) -> None:
#     """
#     Compute missing differential initial values from the state equations.
#
#     :param problem: EMT problem being initialized.
#     :param report: Initialization report updated in place.
#     :return: None
#     """
#     state_eqs: List[Expr] = problem.state_eqs()
#     if len(state_eqs) == 0:
#         return
#     else:
#         state_eqs = state_eqs
#
#     phase_t0: float = time.perf_counter()
#     missing_diff_vars: List[Var]
#     missing_state_eqs: List[Expr]
#     missing_diff_vars, missing_state_eqs = _collect_missing_dx_problem(problem)
#
#
#     if len(missing_diff_vars) == 0:
#         return
#     else:
#         pass
#
#     phase_t0 = time.perf_counter()
#     if x_full is None:
#         x0: np.ndarray = problem.get_x0()
#     else:
#         x0 = x_full
#
#     phase_t0 = time.perf_counter()
#     if dx_full is None:
#         dx0_seed: np.ndarray = problem.get_dx0()
#     else:
#         dx0_seed = dx_full
#
#
#     if runtime_params is None or len(runtime_params) != problem.get_variable_parameter_number():
#         runtime_params = build_runtime_param_array(problem)
#     else:
#         runtime_params = runtime_params
#
#     if constant_params is None or len(constant_params) != len(problem.get_parameters_values()):
#         constant_params = build_constant_param_array(problem)
#     else:
#         constant_params = constant_params
#     cache_key: str = _build_state_rhs_cache_key(problem, missing_state_eqs)
#     state_rhs_fn = _load_or_build_state_rhs_vector(problem, missing_state_eqs, cache_key, report)
#
#     phase_t0 = time.perf_counter()
#     computed_dx: np.ndarray = state_rhs_fn(x0, dx0_seed, runtime_params, constant_params).copy()
#
#
#     idx: int = 0
#     phase_t0 = time.perf_counter()
#     while idx < len(missing_diff_vars):
#         diff_var: Var = missing_diff_vars[idx]
#         problem.diff_init_guess[diff_var.uid] = float(computed_dx[idx])
#
#         idx += 1
#
#


def _build_initialization_system_if_needed(
        problem: EmtProblemTemplate,
        options: EmtOptions,
        report: EmtInitializationReport,
) -> ReducedInitializationSystem | None:
    """
    Build the reduced initialization system only when unresolved work remains.

    :param problem: EMT problem being initialized.
    :param options: EMT simulation options.
    :param report: Initialization report updated in place.
    :return: Reduced initialization system or None.
    """
    reduced_system: ReducedInitializationSystem | None = build_reduced_initialization_system(
        problem=problem,
        allow_state_equilibrium=bool(options.init_allow_state_equilibrium),
    )
    if reduced_system is None:
        report.unknown_var_count = 0
        report.unresolved_state_count = 0
    else:
        report.unknown_var_count = len(reduced_system.unknown_vars)
        report.unresolved_state_count = int(np.count_nonzero(reduced_system.state_unknown_mask))
    return reduced_system


def run_rms_native_initialization(problem: Any, options: RmsOptions) -> bool:
    """
    Run RMS consistent-Newton initialization after PF projection and explicit initialization.

    The workflow keeps the current PF/explicit seeds intact, then solves only the
    unresolved subset with a reduced consistent Newton method. When Newton fails,
    the workflow may fall back to a pseudo-transient continuation. Missing
    differential initial values are computed automatically from the state equations.

    :param problem: Fully assembled RMS DAE problem being initialized.
    :param options: RMS simulation options.
    :return: ``True`` when the reduced consistency system converges or is empty.
    """
    if options.initialization_method != RmsInitializationMethod.ConsistentNewton:
        raise ValueError(
            "run_rms_native_initialization requires ConsistentNewton"
        )
    else:
        pass

    x: np.ndarray = problem.get_x0()
    event_x: np.ndarray = problem.get_eventparams0()
    x_seed: np.ndarray = x.copy()
    dx: np.ndarray = problem.get_dx0()
    runtime_params: np.ndarray = np.zeros(0, dtype=np.float64)

    reduced_system: ReducedInitializationSystem | None
    runtime_params: np.ndarray
    constant_params: np.ndarray
    reduced_problem_payload: Tuple[List[Var], List[Var], List[Var], List[Expr], np.ndarray] | None

    reduced_problem_payload = collect_reduced_initialization_problem(
        problem=problem,
        # Missing state init equations are completed from steady-state dynamics:
        # dx/dt = f(x, y, p) becomes the initialization residual f(x, y, p) = 0.
        allow_state_equilibrium=True,
    )

    if reduced_problem_payload is not None:
        if len(reduced_problem_payload[0]) != 0:
            constant_params = build_constant_param_array(problem)

            reduced_system = ReducedInitializationSystem(
                problem=problem,
                unknowns=reduced_problem_payload[0],
                unknown_vars=reduced_problem_payload[1],
                unknown_events=reduced_problem_payload[2],
                residual_eqs=reduced_problem_payload[3],
                state_unknown_mask=reduced_problem_payload[4]
            )

            if reduced_system is not None:
                converged = run_reduced_newton_initialization(
                    reduced_system=reduced_system,
                    problem=problem,
                    x=x,
                    event_x=event_x,
                    dx=dx,
                    constant_params=constant_params,
                )

                if converged:
                    apply_solution_to_problem(problem, x, event_x)
                    return True
                else:
                    raise RuntimeError(
                        "RMS consistent Newton initialization did not converge"
                    )

    return True
