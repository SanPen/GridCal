# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from typing import Dict, List, Tuple, Union, Optional, BinaryIO, Set
import numpy as np
import numba as nb
import time
import hashlib
import os
import pickle
from pathlib import Path
from collections.abc import Callable
from typing import cast
import warnings
import scipy.sparse as sp
import scipy.sparse.linalg as spla

from VeraGridEngine.enumerations import EmtInitializationMethod, EmtInitializationStatus
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.Simulations.Rms.numerical.pseudo_transient import PseudoTransient
from VeraGridEngine.Simulations.Rms.problems.rms_problem_template import RmsProblemTemplate
from VeraGridEngine.Utils.Symbolic.compiled_functions import SymbolicJacobian, SymbolicVector
from VeraGridEngine.Utils.Symbolic.symbolic import expression2numba, get_expression_vars, heaviside_num
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const, Expr


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

    def __init__(self, vector: InitializationStateRhsVector | SymbolicVector) -> None:
        """
        Build one initialization-vector cache entry.

        :param vector: Cached symbolic vector evaluator.
        :type vector: InitializationStateRhsVector | SymbolicVector
        :return: None.
        :rtype: None
        """
        self._vector = vector

    def get_vector(self) -> InitializationStateRhsVector | SymbolicVector:
        """
        Return the cached symbolic vector evaluator.

        :return: Cached symbolic vector evaluator.
        :rtype: InitializationStateRhsVector | SymbolicVector
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


StateRhsCallable = Callable[[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray], None]


def _payload_str(value: object) -> str:
    """
    Return one payload value as a string.

    :param value: Serialized payload value.
    :type value: object
    :return: String representation.
    :rtype: str
    """
    return str(value)


def _payload_float(value: object) -> float:
    """
    Return one payload value as a float.

    :param value: Serialized payload value.
    :type value: object
    :return: Float representation.
    :rtype: float
    """
    return float(cast(float | int | str, value))


def _payload_int(value: object) -> int:
    """
    Return one payload value as an integer.

    :param value: Serialized payload value.
    :type value: object
    :return: Integer representation.
    :rtype: int
    """
    return int(cast(int | float | str, value))


def _payload_bool(value: object) -> bool:
    """
    Return one payload value as a boolean.

    :param value: Serialized payload value.
    :type value: object
    :return: Boolean representation.
    :rtype: bool
    """
    return bool(cast(bool | int | float | str, value))


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
        namespace: Dict[str, object] = dict(math=__import__("math"), np=np, _heaviside=heaviside_num)
        compiled_func: StateRhsCallable
        exec(source_code, namespace)

        if use_jit:
            compiled_func = nb.jit(
                nb.void(nb.float64[:], nb.float64[:], nb.float64[:], nb.float64[:], nb.float64[:]),
                fastmath=True,
                cache=False,
            )(cast(StateRhsCallable, namespace["func"]))
        else:
            compiled_func = cast(StateRhsCallable, namespace["func"])

        self._func: StateRhsCallable = compiled_func

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


def _collect_block_sequence(root_block: Block) -> List[Block]:
    """
    Return one root-first block traversal sequence.

    :param root_block: Root symbolic block.
    :type root_block: Block
    :return: Ordered block list including every descendant.
    :rtype: List[Block]
    """
    ordered_blocks: List[Block] = list()
    pending_blocks: List[Block] = list([root_block])
    pending_index: int = 0
    current_block: Block
    child_block: Block

    while pending_index < len(pending_blocks):
        current_block = pending_blocks[pending_index]
        pending_index += 1
        ordered_blocks.append(current_block)

        for child_block in current_block.children:
            pending_blocks.append(child_block)

    return ordered_blocks


def _build_hierarchical_event_equation_lookup(mdl: Block) -> Dict[int, Union[Expr, Const]]:
    """
    Build one uid-keyed runtime-event equation lookup from the full block hierarchy.

    :param mdl: Root symbolic block.
    :type mdl: Block
    :return: Runtime-event equation lookup keyed by variable uid.
    :rtype: Dict[int, Union[Expr, Const]]
    """
    block_sequence: List[Block] = _collect_block_sequence(mdl)
    event_equation_lookup: Dict[int, Union[Expr, Const]] = dict()
    block_item: Block
    event_var: Var
    event_eq: Union[Expr, Const]

    for block_item in block_sequence:
        for event_var, event_eq in block_item.event_dict.items():
            event_equation_lookup[event_var.uid] = event_eq

        for event_var, event_eq in block_item.mode_dict.items():
            event_equation_lookup[event_var.uid] = event_eq

    return event_equation_lookup


def _build_hierarchical_event_equation_list(
        mdl: Block,
        variable_parameters: List[Var],
        fallback_event_parameters_eqs: List[Union[Expr, Const]],
) -> List[Union[Expr, Const]]:
    """
    Build one runtime-equation list aligned with the canonical variable-parameter order.

    :param mdl: Root symbolic block.
    :type mdl: Block
    :param variable_parameters: Canonical runtime parameter order.
    :type variable_parameters: List[Var]
    :param fallback_event_parameters_eqs: Existing runtime equation list used as fallback.
    :type fallback_event_parameters_eqs: List[Union[Expr, Const]]
    :return: Runtime equation list aligned with ``variable_parameters``.
    :rtype: List[Union[Expr, Const]]
    """
    event_equation_lookup: Dict[int, Union[Expr, Const]] = _build_hierarchical_event_equation_lookup(mdl)
    ordered_equations: List[Union[Expr, Const]] = list()
    parameter_index: int = 0
    runtime_parameter: Var

    while parameter_index < len(variable_parameters):
        runtime_parameter = variable_parameters[parameter_index]
        if runtime_parameter.uid in event_equation_lookup:
            ordered_equations.append(event_equation_lookup[runtime_parameter.uid])
        else:
            if parameter_index < len(fallback_event_parameters_eqs):
                ordered_equations.append(fallback_event_parameters_eqs[parameter_index])
            else:
                ordered_equations.append(Const(None))
        parameter_index += 1

    return ordered_equations


def _build_event_equation_lookup_from_problem_order(
        variable_parameters: List[Var],
        event_parameters_eqs: List[Union[Expr, Const]],
) -> Dict[int, Union[Expr, Const]]:
    """
    Build one uid-keyed runtime-equation lookup from the canonical problem order.

    :param variable_parameters: Canonical runtime parameter order.
    :type variable_parameters: List[Var]
    :param event_parameters_eqs: Runtime equations aligned with ``variable_parameters``.
    :type event_parameters_eqs: List[Union[Expr, Const]]
    :return: Runtime-equation lookup keyed by uid.
    :rtype: Dict[int, Union[Expr, Const]]
    """
    equation_lookup: Dict[int, Union[Expr, Const]] = dict()
    parameter_index: int = 0
    runtime_parameter: Var

    while parameter_index < len(variable_parameters) and parameter_index < len(event_parameters_eqs):
        runtime_parameter = variable_parameters[parameter_index]
        equation_lookup[runtime_parameter.uid] = event_parameters_eqs[parameter_index]
        parameter_index += 1

    return equation_lookup


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
            source_code=_payload_str(payload["source_code"]),
            use_jit=_payload_bool(payload["use_jit"]),
            output_size=_payload_int(payload["output_size"]),
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
        cache_file_typed: BinaryIO = cache_file
        pickle.dump(
            dict(
                source_code=source_code,
                use_jit=use_jit_for_state_rhs,
                output_size=len(missing_state_eqs),
            ),
            cache_file_typed,
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


def _restore_problem_guess_map(problem: EmtProblemTemplate, name_map: Dict[str, float], diff_guess: bool) -> Dict[int, float]:
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
        for var in problem.get_state_vars():
            name_to_uid[alias_name_map[var.uid]] = var.uid
        for var in problem.get_algebraic_vars():
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
    status_name: str = _payload_str(payload["status"])
    method_requested_name: str = _payload_str(payload["method_requested"])
    method_used_name: str = _payload_str(payload["method_used"])
    initial_residual_inf_value: float = _payload_float(payload["initial_residual_inf"])
    final_residual_inf_value: float = _payload_float(payload["final_residual_inf"])
    newton_iterations_value: int = _payload_int(payload["newton_iterations"])
    pseudo_transient_steps_value: int = _payload_int(payload["pseudo_transient_steps"])
    unknown_var_count_value: int = _payload_int(payload["unknown_var_count"])
    unresolved_state_count_value: int = _payload_int(payload["unresolved_state_count"])
    automatic_dx0_count_value: int = _payload_int(payload["automatic_dx0_count"])
    reduced_system_build_s_value: float = _payload_float(payload["reduced_system_build_s"])
    runtime_param_build_s_value: float = _payload_float(payload["runtime_param_build_s"])
    constant_param_build_s_value: float = _payload_float(payload["constant_param_build_s"])
    initial_residual_eval_s_value: float = _payload_float(payload["initial_residual_eval_s"])
    newton_elapsed_s_value: float = _payload_float(payload["newton_elapsed_s"])
    pseudo_transient_elapsed_s_value: float = _payload_float(payload["pseudo_transient_elapsed_s"])
    dx0_completion_s_value: float = _payload_float(payload["dx0_completion_s"])
    x0_rebuild_s_value: float = _payload_float(payload.get("x0_rebuild_s", 0.0))
    dx0_seed_build_s_value: float = _payload_float(payload.get("dx0_seed_build_s", 0.0))
    state_rhs_vector_build_s_value: float = _payload_float(payload.get("state_rhs_vector_build_s", 0.0))
    state_rhs_vector_cache_hit_value: bool = _payload_bool(payload.get("state_rhs_vector_cache_hit", False))
    solution_apply_s_value: float = _payload_float(payload.get("solution_apply_s", 0.0))
    missing_dx_problem_collect_s_value: float = _payload_float(payload.get("missing_dx_problem_collect_s", 0.0))
    state_rhs_eval_s_value: float = _payload_float(payload.get("state_rhs_eval_s", 0.0))
    missing_dx_scatter_s_value: float = _payload_float(payload.get("missing_dx_scatter_s", 0.0))
    persistent_cache_hit_value: bool = _payload_bool(payload.get("persistent_cache_hit", False))
    persistent_cache_load_s_value: float = _payload_float(payload.get("persistent_cache_load_s", 0.0))
    persistent_cache_store_s_value: float = _payload_float(payload.get("persistent_cache_store_s", 0.0))
    elapsed_s_value: float = _payload_float(payload["elapsed_s"])
    message_value: str = _payload_str(payload["message"])

    report.status = EmtInitializationStatus[status_name]
    report.method_requested = EmtInitializationMethod[method_requested_name]
    report.method_used = EmtInitializationMethod[method_used_name]
    report.initial_residual_inf = initial_residual_inf_value
    report.final_residual_inf = final_residual_inf_value
    report.newton_iterations = newton_iterations_value
    report.pseudo_transient_steps = pseudo_transient_steps_value
    report.unknown_var_count = unknown_var_count_value
    report.unresolved_state_count = unresolved_state_count_value
    report.automatic_dx0_count = automatic_dx0_count_value
    report.reduced_system_build_s = reduced_system_build_s_value
    report.runtime_param_build_s = runtime_param_build_s_value
    report.constant_param_build_s = constant_param_build_s_value
    report.initial_residual_eval_s = initial_residual_eval_s_value
    report.newton_elapsed_s = newton_elapsed_s_value
    report.pseudo_transient_elapsed_s = pseudo_transient_elapsed_s_value
    report.dx0_completion_s = dx0_completion_s_value
    report.x0_rebuild_s = x0_rebuild_s_value
    report.dx0_seed_build_s = dx0_seed_build_s_value
    report.state_rhs_vector_build_s = state_rhs_vector_build_s_value
    report.state_rhs_vector_cache_hit = state_rhs_vector_cache_hit_value
    report.solution_apply_s = solution_apply_s_value
    report.missing_dx_problem_collect_s = missing_dx_problem_collect_s_value
    report.state_rhs_eval_s = state_rhs_eval_s_value
    report.missing_dx_scatter_s = missing_dx_scatter_s_value
    report.persistent_cache_hit = persistent_cache_hit_value
    report.persistent_cache_load_s = persistent_cache_load_s_value
    report.persistent_cache_store_s = persistent_cache_store_s_value
    report.elapsed_s = elapsed_s_value
    report.message = message_value


def _build_persistent_initialization_cache_key(
        problem: EmtProblemTemplate,
        unknown_vars: List[Var],
        residual_eqs: List[Expr],
        state_unknown_mask: np.ndarray,
        options: EmtOptions,
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
    reduced_key: str = _build_reduced_initialization_cache_key(problem, unknown_vars, residual_eqs, state_unknown_mask)

    payload: str = "|".join([
        "persistent-reduced-emt-init-v5",
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


def _load_persistent_initialization_solution(cache_key: str) -> Dict[str, object] | None:
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
        cache_file_typed: BinaryIO = cache_file
        pickle.dump(payload, cache_file_typed, protocol=pickle.HIGHEST_PROTOCOL)


def _build_reduced_initialization_cache_key(
        problem: EmtProblemTemplate,
        unknown_vars: List[Var],
        residual_eqs: List[Expr],
        state_unknown_mask: np.ndarray,
) -> str:
    """
    Return a deterministic cache key for one reduced EMT initialization system.

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


def _collect_missing_dx_problem(problem: EmtProblemTemplate,
                                include_existing: bool = False) -> Tuple[List[Var], List[Expr]]:
    """
    Return the differential variables that still need ``dx0`` and their state equations.

    :param problem: EMT problem being initialized.
    :type problem: EmtProblemTemplate
    :param include_existing: When ``True``, collect all differential variables.
    :return: Pair ``(missing_diff_vars, missing_state_eqs)``.
    :rtype: Tuple[List[Var], List[Expr]]
    """
    diff_vars: List[Var] = problem.get_diff_vars()
    state_vars: List[Var] = problem.get_state_vars()
    state_eqs: List[Expr] = problem.get_state_eqs()
    state_eq_by_uid: Dict[int, Expr] = {
        state_var.uid: state_eqs[idx]
        for idx, state_var in enumerate(state_vars)
        if idx < len(state_eqs)
    }
    missing_diff_vars: List[Var] = list()
    missing_state_eqs: List[Expr] = list()
    idx: int = 0

    while idx < len(diff_vars):
        diff_var: Var = diff_vars[idx]
        base_var: Var | None = diff_var.base_var
        state_eq: Expr | None = None if base_var is None else state_eq_by_uid.get(base_var.uid, None)

        if include_existing:
            if state_eq is not None:
                missing_diff_vars.append(diff_var)
                missing_state_eqs.append(state_eq)
        else:
            if diff_var.uid in problem.diff_init_guess:
                diff_var = diff_var
            else:
                if state_eq is not None:
                    missing_diff_vars.append(diff_var)
                    missing_state_eqs.append(state_eq)

        idx += 1

    return missing_diff_vars, missing_state_eqs


def init_pseudo_transient(problem: EmtProblemTemplate, options: EmtOptions) -> EmtInitializationReport:
    """
    Run the EMT-native initialization workflow forcing the pure pseudo-transient path.

    This helper does not execute explicit initialization. It starts from the
    current problem seed, which in the main EMT build workflow corresponds to
    the power-flow projected variables.

    :param problem: EMT problem being initialized.
    :param options: EMT simulation options.
    :return: Initialization report.
    """
    options.initialization_method = EmtInitializationMethod.PseudoTransient
    return run_emt_native_initialization(problem, options)


class ReducedInitializationSystem:
    """
    Reduced EMT initialization system built on top of the unresolved variables only.
    """

    __slots__ = [
        "unknown_vars",
        "residual_eqs",
        "state_unknown_mask",
        "residual_fn",
        "jacobian_fn",
    ]

    def __init__(
            self,
            problem: EmtProblemTemplate,
            unknown_vars: List[Var],
            residual_eqs: List[Expr],
            state_unknown_mask: np.ndarray,
    ) -> None:
        """
        Compile the reduced residual and Jacobian used by the consistent initializer.

        :param problem: EMT problem being initialized.
        :param unknown_vars: Unknown variables solved by the reduced system.
        :param residual_eqs: Residual equations enforcing consistency.
        :param state_unknown_mask: Mask marking which reduced unknowns correspond to states.
        :return: None
        """
        self.unknown_vars = unknown_vars
        self.residual_eqs = residual_eqs
        self.state_unknown_mask = state_unknown_mask
        cache_key: str = _build_reduced_initialization_cache_key(
            problem=problem,
            unknown_vars=unknown_vars,
            residual_eqs=residual_eqs,
            state_unknown_mask=state_unknown_mask,
        )
        cache_entry: ReducedInitializationSystemCacheEntry | None = REDUCED_INITIALIZATION_SYSTEM_CACHE.get_entry(cache_key)

        if cache_entry is None:
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
                variables=unknown_vars,
                compiler_names_dict=problem.get_compiler_names_dict(),
                alias_names_dict=problem.get_alias_names_dict(),
                VARS_NAME=problem.VARS_NAME,
                DIFF_NAME=problem.DIFF_NAME,
                EVENT_PARAMS_NAME=problem.VARIABLE_PARAMS_NAME,
                PARAMS_NAME=problem.CONSTANT_PARAMS_NAME,
            )
            REDUCED_INITIALIZATION_SYSTEM_CACHE.set_entry(
                cache_key,
                ReducedInitializationSystemCacheEntry(self.residual_fn, self.jacobian_fn),
            )
        else:
            self.residual_fn = cache_entry.get_residual_fn()
            self.jacobian_fn = cache_entry.get_jacobian_fn()


def _build_constant_param_array(problem: EmtProblemTemplate) -> np.ndarray:
    """
    Build the dense constant-parameter vector used by the initialization solvers.

    :param problem: EMT problem being initialized.
    :return: Constant-parameter array.
    """
    const_values: List[Const] = problem.get_parameters_values()
    return np.asarray([float(item.value) for item in const_values], dtype=np.float64)


def _emt_phase_groups(variables: List[Var]) -> List[Tuple[Var, Var, Var]]:
    """Find the template convention ``<quantity>_A/B/C`` within one block.

    These groups represent balanced fundamental quantities. Their rotating-frame
    derivative is omega/sqrt(3) * (x_C-x_B, x_A-x_C, x_B-x_A).
    """
    families: Dict[str, Dict[str, Var]] = {}
    for var in variables:
        if var.name.endswith(("_A", "_B", "_C")):
            families.setdefault(var.name[:-1], {})[var.name[-1]] = var
    return [(phases["A"], phases["B"], phases["C"])
            for phases in families.values() if all(phase in phases for phase in "ABC")]


def _emt_is_absolute_angle(var: Var) -> bool:
    """Identify absolute machine/PLL phase states in the EMT templates."""
    return var.name.rstrip("_") in ("theta_abs", "theta", "theta_pll")


def _emt_periodic_derivatives(
        states: List[Var], groups: List[Tuple[Var, Var, Var]], omega: float,
) -> Dict[int, Expr]:
    """Build periodic derivatives from state roles, without initialization equations."""
    derivatives: Dict[int, Expr] = {var.uid: Const(0.0) for var in states}
    for var in states:
        # Absolute electrical rotor angles advance once per fundamental cycle;
        # rotor-relative angles and dq/controller quantities remain constant.
        if _emt_is_absolute_angle(var):
            derivatives[var.uid] = Const(omega)
    for a, b, c in groups:
        if a.uid in derivatives and b.uid in derivatives and c.uid in derivatives:
            derivatives[a.uid] = omega / np.sqrt(3.0) * (c - b)
            derivatives[b.uid] = omega / np.sqrt(3.0) * (a - c)
            derivatives[c.uid] = omega / np.sqrt(3.0) * (b - a)
    return derivatives


def _emt_initialization_bindings(problem: EmtProblemTemplate) -> Dict[int, float]:
    x, dx = problem.get_x0(), problem.get_dx0()
    constants = _build_constant_param_array(problem)
    bindings = {uid: float(x[index]) for uid, index in problem.uid2idx_vars.items()}
    bindings.update({uid: float(dx[index]) for uid, index in problem.uid2idx_diff.items()})
    bindings.update({uid: float(problem.event_params_values[index])
                     for uid, index in problem.uid2idx_event_params.items()})
    bindings.update({uid: float(constants[index]) for uid, index in problem.uid2idx_params.items()})
    bindings[problem.glob_time.uid] = 0.0
    return bindings


def run_emt_device_pseudo_transient_initialization(
        problem: EmtProblemTemplate,
        blocks: List[Block],
        options: EmtOptions,
        check_kcl: bool = True,
) -> EmtInitializationReport:
    """Solve each complete device at a balanced periodic PF operating point.

    Device registration and residuals use only dynamic equations. Machine and
    controller children share one solve. PF terminal voltages remain fixed and
    mapped terminal currents anchor the operating point. Unseeded Const(None)
    event parameters become unknown references; symbolic references also carry
    their defining residual. Neither init_eqs nor diff_init_eqs is evaluated.

    Pseudo time relaxes f(x)-D_periodic(x)=0. ABC state triples use their
    fundamental sinusoidal derivatives; dq/controller states use zero and
    absolute rotor angles advance at grid frequency. This balanced fundamental
    approximation is checked against the assembled DAE at four cycle phases.
    """
    from VeraGridEngine.enumerations import VarPowerFlowReferenceType
    from VeraGridEngine.Simulations.Rms.initialization import _build_reference_update_from_residual

    report = EmtInitializationReport(method_requested=EmtInitializationMethod.PseudoTransient)
    report.method_used = EmtInitializationMethod.PseudoTransient
    start_time = time.perf_counter()
    omega = 2.0 * np.pi * float(problem.grid.fBase)
    if not np.isfinite(omega) or omega <= 0.0:
        report.status = InitializationStatus.FAILED
        report.message = "Periodic initialization requires a positive grid frequency."
        return report
    for index, bus in enumerate(problem.grid.buses):
        if bus.is_dc:
            continue
        bus_vars = [var for block in bus.emt_model.get_all_blocks() for var in block.algebraic_vars]
        if not _emt_phase_groups(bus_vars):
            report.status = InitializationStatus.FAILED
            report.message = f"Periodic initialization requires an ABC voltage group at bus {bus.name!r}."
            return report
        if getattr(problem, "power_flow_results_3ph", None) is not None:
            voltages = problem._get_bus_voltage_vector_3ph(index)
            rotation = np.exp(-2j * np.pi / 3.0)
            balanced = voltages[1] * np.asarray([1.0, rotation, rotation ** 2])
            if not np.allclose(voltages[1:], balanced, rtol=0.0, atol=float(options.tolerance)):
                report.status = InitializationStatus.FAILED
                report.message = "Device-local periodic PTC currently requires a balanced power-flow operating point."
                return report
    bindings = _emt_initialization_bindings(problem)
    original_bindings = dict(bindings)
    solved_values: Dict[int, float] = {}
    solved_derivatives: Dict[int, float] = {}
    solved_references: Dict[int, float] = {}
    tolerance = float(options.init_newton_tol)
    current_refs = {
        VarPowerFlowReferenceType.i_A, VarPowerFlowReferenceType.i_B, VarPowerFlowReferenceType.i_C,
        VarPowerFlowReferenceType.if_A, VarPowerFlowReferenceType.if_B, VarPowerFlowReferenceType.if_C,
        VarPowerFlowReferenceType.it_A, VarPowerFlowReferenceType.it_B, VarPowerFlowReferenceType.it_C,
    }
    covered_uids: Set[int] = set()
    seen_roots: Set[int] = set()

    for root in blocks:
        if root.uid in seen_roots:
            continue
        seen_roots.add(root.uid)
        children = root.get_all_blocks()
        states = [var for block in children for var in block.state_vars]
        algebraics = [var for block in children for var in block.algebraic_vars]
        state_eqs = [eq for block in children for eq in block.state_eqs]
        algebraic_eqs = [eq for block in children for eq in block.algebraic_eqs]
        if not states and not algebraics:
            continue
        owner = getattr(problem, "_vars2device", {}).get((states + algebraics)[0].uid)
        label = f"{owner.name} / {root.name}" if owner is not None else root.name
        if len(states) != len(state_eqs) or len(algebraics) != len(algebraic_eqs):
            report.status = InitializationStatus.FAILED
            report.message = f"Device {label!r} has mismatched dynamic equations."
            break
        owned_uids = {var.uid for var in states + algebraics}
        if covered_uids & owned_uids:
            report.status = InitializationStatus.FAILED
            report.message = "Pseudo-transient device roots overlap."
            break
        covered_uids.update(owned_uids)
        groups = [group for block in children for group in _emt_phase_groups(block.state_vars)]
        derivatives = _emt_periodic_derivatives(states, groups, omega)
        # Positive mass on target-rhs gives the usual pseudo-time equation
        # M dx/dtau = rhs - target. Algebraic and PF rows have zero mass.
        residual_eqs = [derivatives[var.uid] - eq for var, eq in zip(states, state_eqs)]
        residual_eqs.extend(algebraic_eqs)
        references: List[Var] = []
        inferred_references: Dict[int, Expr] = {}
        event_sources = {var: expression for block in children for var, expression in block.event_dict.items()}
        for var, expression in event_sources.items():
            if var.uid not in problem.uid2idx_event_params or var.uid in problem.event_params_init_dict:
                continue
            if isinstance(expression, Const):
                if expression.value is not None:
                    continue
                # As in RMS, a null event parameter is a reference to solve,
                # not a zero-valued fixed input. The dynamic/PF equations own it.
                if not any(var.uid in {v.uid for v in eq.get_vars()} for eq in residual_eqs):
                    report.status = InitializationStatus.FAILED
                    report.message = f"Reference {var.name!r} has no dynamic equation in {label!r}."
                    break
                # Reuse RMS's affine isolation, applied to the periodic
                # residual rather than assuming every physical derivative is zero.
                inferred = next((update for eq in residual_eqs
                                 if (update := _build_reference_update_from_residual(eq, var)) is not None), None)
                if inferred is not None:
                    inferred_references[var.uid] = inferred
                    continue
            elif any(v.uid in problem.uid2idx_vars for v in expression.get_vars()):
                residual_eqs.append(var - expression)
            else:
                continue  # Runtime expressions depending only on PF/constants are already resolved.
            references.append(var)
        if report.status == InitializationStatus.FAILED:
            break

        mapping = {key: var for block in children for key, var in block.external_mapping.items()}
        anchor_uids = {
            var.uid for key, var in mapping.items()
            if key in current_refs and isinstance(var, Var)
            and var.uid in owned_uids and var.uid in problem.init_guess
        }
        local_vars = states + algebraics + references
        local_uids = [var.uid for var in local_vars]
        # PF terminal data has the network tolerance; dynamic residuals keep
        # the tighter initialization tolerance (e.g. tiny winding regularizers).
        branch_anchor_weight = tolerance / max(tolerance, float(options.tolerance))
        injection_uids = {var.uid for key, var in mapping.items()
                          if key in {VarPowerFlowReferenceType.i_A, VarPowerFlowReferenceType.i_B,
                                     VarPowerFlowReferenceType.i_C} and isinstance(var, Var)}
        residual_eqs.extend((1.0 if var.uid in injection_uids else branch_anchor_weight)
                            * (var - original_bindings[var.uid])
                            for var in local_vars if var.uid in anchor_uids)
        current = np.asarray([bindings[uid] for uid in local_uids], dtype=np.float64)
        for index, var in enumerate(states):
            if var.name in ("omega", "omega_") and var.uid not in problem.init_guess:
                current[index] = 1.0
        report.unknown_var_count += len(local_vars)
        report.unresolved_state_count += len(states)

        def evaluate(values: np.ndarray) -> np.ndarray:
            bindings.update(zip(local_uids, map(float, values)))
            for uid, expression in inferred_references.items():
                bindings[uid] = float(expression.eval_uid(bindings))
            # Residuals that explicitly contain dx see the same periodic target.
            for block in children:
                for derivative in block.diff_vars:
                    if derivative.base_var is not None and derivative.base_var.uid in derivatives:
                        bindings[derivative.uid] = float(derivatives[derivative.base_var.uid].eval_uid(bindings))
            return np.asarray([float(eq.eval_uid(bindings)) for eq in residual_eqs], dtype=np.float64)

        try:
            residual = evaluate(current)
            initial_norm = _max_abs_value(residual)
            if not np.isfinite(initial_norm):
                raise ValueError("non-finite initial residual")
            report.initial_residual_inf = max(report.initial_residual_inf, initial_norm)
            dtau = float(options.init_ptc_dtau0)
            stalled = 0
            for _ in range(int(options.init_ptc_max_iter)):
                if _max_abs_value(residual) <= tolerance:
                    break
                jacobian = np.empty((len(residual), len(current)))
                for column in range(len(current)):
                    epsilon = 1e-6 * max(1.0, abs(current[column]))
                    trial = current.copy()
                    trial[column] += epsilon
                    positive = evaluate(trial)
                    trial[column] -= 2.0 * epsilon
                    jacobian[:, column] = (positive - evaluate(trial)) / (2.0 * epsilon)
                if references or inferred_references or any(_emt_is_absolute_angle(var) for var in states):
                    # Reference inference can eliminate a state residual and PF
                    # anchors make the system rectangular. Relax J.T F with a
                    # positive artificial mass in scaled local coordinates.
                    # The mass decreases with the residual; every correction
                    # remains a pseudo-time step, with no Newton-only fallback.
                    row_scale = np.maximum(np.linalg.norm(jacobian, axis=1), 1e-8)
                    row_jacobian = jacobian / row_scale[:, None]
                    column_scale = np.maximum(np.linalg.norm(row_jacobian, axis=0), 1e-8)
                    scaled_jacobian = row_jacobian / column_scale
                    pseudo_mass = max(1e-14, min(1.0, np.linalg.norm(residual / row_scale)) ** 2)
                    relaxation = np.sqrt(pseudo_mass / max(dtau, 1e-30))
                    augmented = np.vstack((scaled_jacobian, relaxation * np.eye(len(current))))
                    rhs = np.r_[-residual / row_scale, np.zeros(len(current))]
                    correction = np.linalg.lstsq(augmented, rhs, rcond=None)[0] / column_scale
                else:
                    row_scale = np.ones(len(residual))
                    for index in range(len(states)):
                        jacobian[index, index] += 1.0 / max(dtau, 1e-30)
                    correction = np.linalg.lstsq(jacobian, -residual, rcond=None)[0]
                accepted = False
                alpha = 1.0
                for _ in range(12):
                    candidate = current + alpha * correction
                    candidate_residual = evaluate(candidate)
                    if np.all(np.isfinite(candidate_residual)) and np.linalg.norm(candidate_residual / row_scale) < np.linalg.norm(residual / row_scale):
                        current, residual = candidate, candidate_residual
                        accepted = True
                        break
                    alpha *= 0.5
                report.pseudo_transient_steps += 1
                if accepted:
                    dtau = min(float(options.init_ptc_dtau_max), 2.0 * dtau)
                    stalled = 0
                else:
                    dtau = max(float(options.init_ptc_dtau_min), 0.5 * dtau)
                    stalled += 1
                    if stalled >= 3:
                        break
            if options.verbose:
                print(f"[EMT PTC] {label}: residual={_max_abs_value(residual):.3g}")
            final_norm = _max_abs_value(residual)
            report.final_residual_inf = max(report.final_residual_inf, final_norm)
            if not np.isfinite(final_norm) or final_norm > tolerance:
                raise ValueError(f"periodic residual {final_norm:.3g} exceeds {tolerance:.3g}")
            evaluate(current)
            solved_references.update({uid: bindings[uid] for uid in inferred_references})
            for var, value in zip(local_vars, current):
                if var.uid in problem.uid2idx_event_params:
                    solved_references[var.uid] = float(value)
                else:
                    solved_values[var.uid] = float(value)
            for block in children:
                for derivative in block.diff_vars:
                    if derivative.base_var is not None and derivative.base_var.uid in derivatives:
                        solved_derivatives[derivative.uid] = float(derivatives[derivative.base_var.uid].eval_uid(bindings))
        except (FloatingPointError, ZeroDivisionError, ValueError, RuntimeError, OverflowError, KeyError, TypeError, np.linalg.LinAlgError) as exc:
            report.status = InitializationStatus.FAILED
            report.message = f"Device {label!r} failed: {exc}"
            break

    if report.status != InitializationStatus.FAILED:
        bus_uids = {var.uid for bus in problem.grid.buses
                    for block in bus.emt_model.get_all_blocks() for var in block.algebraic_vars}
        missing = set(problem.uid2idx_vars) - covered_uids - bus_uids
        if missing:
            report.status = InitializationStatus.FAILED
            report.message = f"Device-local initialization does not cover {len(missing)} variables."
        elif check_kcl:
            kcl = [float(eq.eval_uid(bindings))
                   for var, eq in zip(problem.get_algebraic_vars(), problem.get_algebraic_eqs())
                   if var.uid in bus_uids]
            kcl_norm = _max_abs_value(np.asarray(kcl))
            report.final_residual_inf = max(report.final_residual_inf, kcl_norm)
            if not np.isfinite(kcl_norm) or kcl_norm > max(tolerance, float(options.tolerance)):
                report.status = InitializationStatus.FAILED
                report.message = f"Assembled device initialization violates bus KCL ({kcl_norm:.3g})."

    # Apply atomically: a failed local solve must not leave a partially modified
    # runtime reference graph or preserved post-init snapshot.
    if report.status != InitializationStatus.FAILED:
        problem.init_guess.update(solved_values)
        problem.diff_init_guess.update(solved_derivatives)
        if hasattr(problem, "_temp_post_init_guess"):
            problem._temp_post_init_guess.update(solved_values)
            problem._temp_post_diff_init_guess.update(solved_derivatives)
        for uid, value in solved_references.items():
            problem.event_params_init_dict[uid] = value
            problem._set_runtime_parameter_value_by_uid(uid=uid, value=value)
        report.status = InitializationStatus.RESOLVED
        report.message = "Device-local periodic pseudo-transient initialization converged."
    report.pseudo_transient_elapsed_s = time.perf_counter() - start_time
    report.elapsed_s = report.pseudo_transient_elapsed_s
    return report


def validate_emt_periodic_initialization(
        problem: EmtProblemTemplate, blocks: List[Block], options: EmtOptions,
        report: EmtInitializationReport,
) -> EmtInitializationReport:
    """Check the assembled periodic DAE at four phases without time integration."""
    if report.status != InitializationStatus.RESOLVED:
        return report
    omega = 2.0 * np.pi * float(problem.grid.fBase)
    children = [block for root in blocks for block in root.get_all_blocks()]
    children.extend(block for bus in problem.grid.buses for block in bus.emt_model.get_all_blocks())
    # Static phase powers such as P_A/Q_A are ABC-labelled but do not rotate
    # with the fundamental waveform. Restrict the phase transform to the
    # lower-case waveform families used by EMT voltages, currents and states.
    groups = [group for block in children
              for group in _emt_phase_groups(block.state_vars + block.algebraic_vars)
              if group[0].name[0].islower()]
    states = problem.get_state_vars()
    derivatives = _emt_periodic_derivatives(states, groups, omega)
    baseline = _emt_initialization_bindings(problem)
    worst = 0.0
    try:
        for phase in (0.0, np.pi / 2.0, np.pi, 3.0 * np.pi / 2.0):
            bindings = dict(baseline)
            for a, b, c in groups:
                for var, plus, minus in ((a, c, b), (b, a, c), (c, b, a)):
                    bindings[var.uid] = (
                        baseline[var.uid] * np.cos(phase)
                        + (baseline[plus.uid] - baseline[minus.uid]) / np.sqrt(3.0) * np.sin(phase)
                    )
            for var in states:
                if _emt_is_absolute_angle(var):
                    bindings[var.uid] = baseline[var.uid] + phase
            bindings[problem.glob_time.uid] = phase / omega
            for derivative in problem.get_diff_vars():
                if derivative.base_var is not None and derivative.base_var.uid in derivatives:
                    bindings[derivative.uid] = float(derivatives[derivative.base_var.uid].eval_uid(bindings))
            residual = [float(eq.eval_uid(bindings) - derivatives[var.uid].eval_uid(bindings))
                        for var, eq in zip(states, problem.get_state_eqs())]
            residual.extend(float(eq.eval_uid(bindings)) for eq in problem.get_algebraic_eqs())
            norm = _max_abs_value(np.asarray(residual))
            if not np.isfinite(norm):
                raise ValueError("non-finite assembled periodic residual")
            worst = max(worst, norm)
        report.final_residual_inf = max(report.final_residual_inf, worst)
        if worst > max(float(options.init_newton_tol), float(options.tolerance)):
            raise ValueError(f"assembled periodic DAE residual is {worst:.3g}")
        report.message = "Periodic steady state verified at four phases without EMT time integration."
    except (FloatingPointError, ZeroDivisionError, ValueError, RuntimeError, OverflowError, KeyError, TypeError) as exc:
        report.status = InitializationStatus.FAILED
        report.message = str(exc)
    return report


def _build_runtime_param_array(problem: EmtProblemTemplate) -> np.ndarray:
    """
    Build the runtime-parameter snapshot at the initialization time.

    :param problem: EMT problem being initialized.
    :return: Runtime-parameter array at time zero.
    """
    runtime_params: np.ndarray = problem.event_params_values.copy()
    runtime_params = problem.def_event_params_fn(runtime_params, 0.0)
    return runtime_params


def _build_state_equation_lookup(problem: EmtProblemTemplate) -> Dict[int, Expr]:
    """
    Build a UID lookup for state equations.

    :param problem: EMT problem being initialized.
    :return: Mapping from state variable UID to its differential right-hand side.
    """
    lookup: Dict[int, Expr] = dict()
    state_vars: List[Var] = problem.get_state_vars()
    state_eqs: List[Expr] = problem.get_state_eqs()

    idx: int = 0
    while idx < len(state_vars):
        lookup[state_vars[idx].uid] = state_eqs[idx]
        idx += 1

    return lookup


def _extract_unknown_vector(problem: EmtProblemTemplate, unknown_vars: List[Var], x: np.ndarray) -> np.ndarray:
    """
    Extract the reduced unknown vector from the full EMT variable vector.

    :param problem: EMT problem being initialized.
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


def _scatter_unknown_vector(problem: EmtProblemTemplate, unknown_vars: List[Var], x: np.ndarray, reduced_x: np.ndarray) -> None:
    """
    Scatter the reduced unknown vector back into the full EMT variable vector.

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


def _build_reduced_initialization_system(
        problem: EmtProblemTemplate,
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
    reduced_problem = _collect_reduced_initialization_problem(problem, allow_state_equilibrium)

    if reduced_problem is None:
        return None
    else:
        unknown_vars, residual_eqs, mask_array = reduced_problem
        return ReducedInitializationSystem(
            problem=problem,
            unknown_vars=unknown_vars,
            residual_eqs=residual_eqs,
            state_unknown_mask=mask_array,
        )


class EmtPseudoTransientProblemAdapter(RmsProblemTemplate):
    """
    Adapt one EMT reduced initialization system to the RMS pseudo-transient solver API.

    The RMS pseudo-transient implementation expects a problem object exposing the
    RMS numerical interface. This adapter provides that interface on top of the
    EMT reduced initialization residual and Jacobian so the EMT initializer can
    reuse the existing pseudo-transient algorithm without changing the solver.
    """

    __slots__ = [
        "_reduced_system",
        "_emt_problem",
        "_runtime_params",
        "_constant_params",
        "_x_full",
        "_dx_full",
        "_reduced_uid2idx_vars",
        "uid2idx_vars",
    ]

    def __init__(
            self,
            reduced_system: ReducedInitializationSystem,
            problem: EmtProblemTemplate,
            x_full: np.ndarray,
            dx_full: np.ndarray,
            runtime_params: np.ndarray,
            constant_params: np.ndarray,
    ) -> None:
        """
        Build one RMS-compatible pseudo-transient view over an EMT reduced system.

        :param reduced_system: EMT reduced initialization system.
        :type reduced_system: ReducedInitializationSystem
        :param problem: EMT problem being initialized.
        :type problem: EmtProblemTemplate
        :param x_full: Full EMT variable vector used as the backing storage.
        :type x_full: np.ndarray
        :param dx_full: Full EMT differential vector used during residual evaluation.
        :type dx_full: np.ndarray
        :param runtime_params: Runtime-parameter snapshot for initialization.
        :type runtime_params: np.ndarray
        :param constant_params: Constant-parameter snapshot for initialization.
        :type constant_params: np.ndarray
        :return: None.
        :rtype: None
        """
        super().__init__(progress_signal=None, progress_text=None)
        self._reduced_system: ReducedInitializationSystem = reduced_system
        self._emt_problem: EmtProblemTemplate = problem
        self._runtime_params: np.ndarray = runtime_params
        self._constant_params: np.ndarray = constant_params
        self._x_full: np.ndarray = x_full
        self._dx_full: np.ndarray = dx_full
        self._reduced_uid2idx_vars: Dict[int, int] = dict()
        self.uid2idx_vars: Dict[int, int] = dict()

        reduced_index: int = 0
        for reduced_var in self._reduced_system.unknown_vars:
            self._reduced_uid2idx_vars[reduced_var.uid] = reduced_index
            self.uid2idx_vars[reduced_var.uid] = reduced_index
            reduced_index += 1

    def get_x0(self) -> np.ndarray:
        """
        Return the reduced unknown vector used to seed pseudo-transient iterations.

        :return: Reduced initialization vector.
        :rtype: np.ndarray
        """
        reduced_x0: np.ndarray = _extract_unknown_vector(self._emt_problem, self._reduced_system.unknown_vars, self._x_full)
        return reduced_x0

    def get_all_vars_number(self) -> int:
        """
        Return the number of reduced initialization unknowns.

        :return: Number of reduced unknowns.
        :rtype: int
        """
        return len(self._reduced_system.unknown_vars)

    def get_diff_var_number(self) -> int:
        """
        Return the number of differential variables used by the reduced solver.

        The RMS pseudo-transient solver asks for a differential-vector size even
        when the EMT reduced initialization stage does not solve an explicit EMT
        differential system in local coordinates. Returning the full EMT `dx`
        length preserves compatibility with the residual evaluation helpers.

        :return: Differential-vector size expected by the EMT residual evaluation.
        :rtype: int
        """
        return int(self._dx_full.size)

    def get_algebraic_var_number(self) -> int:
        """
        Return the number of reduced algebraic-like unknowns.

        The reduced initialization system mixes algebraic variables with any
        unresolved states. The RMS solver only needs a partition size, so the
        complementary block to the unresolved-state count is returned here.

        :return: Number of reduced unknowns treated as non-state variables.
        :rtype: int
        """
        total_unknowns: int = len(self._reduced_system.unknown_vars)
        n_states: int = self.get_states_number()
        return total_unknowns - n_states

    def get_states_number(self) -> int:
        """
        Return the number of reduced unknowns that correspond to unresolved states.

        :return: Count of reduced state unknowns.
        :rtype: int
        """
        n_states: int = int(np.count_nonzero(self._reduced_system.state_unknown_mask))
        return n_states

    def get_algebraic_vars(self) -> List[Var]:
        """
        Return the reduced unknowns treated as algebraic by the adapter partition.

        :return: Reduced non-state unknown list.
        :rtype: List[Var]
        """
        algebraic_vars: List[Var] = list()
        idx: int = 0
        n_unknowns: int = len(self._reduced_system.unknown_vars)
        while idx < n_unknowns:
            if float(self._reduced_system.state_unknown_mask[idx]) > 0.5:
                pass
            else:
                algebraic_vars.append(self._reduced_system.unknown_vars[idx])
            idx += 1
        return algebraic_vars

    def algebraic_vars(self) -> List[Var]:
        """
        Return the reduced non-state unknowns.

        :return: Reduced non-state unknown list.
        :rtype: List[Var]
        """
        return self.get_algebraic_vars()

    def state_vars(self) -> List[Var]:
        """
        Return the reduced unknowns treated as states by the adapter partition.

        :return: Reduced state unknown list.
        :rtype: List[Var]
        """
        state_vars_list: List[Var] = list()
        idx: int = 0
        n_unknowns: int = len(self._reduced_system.unknown_vars)
        while idx < n_unknowns:
            if float(self._reduced_system.state_unknown_mask[idx]) > 0.5:
                state_vars_list.append(self._reduced_system.unknown_vars[idx])
            else:
                pass
            idx += 1
        return state_vars_list

    def update_variable_params(self, t: float, x_snapshot: Optional[np.ndarray] = None) -> None:
        """
        Keep the EMT runtime-parameter snapshot aligned with the RMS solver API.

        The EMT reduced initializer freezes the runtime parameters before entering
        the pseudo-transient solve. The RMS solver still invokes this hook at the
        beginning of the loop, so the adapter accepts the call and intentionally
        preserves the already prepared parameter arrays.

        :param t: Pseudo-time value requested by the solver
        :type t: float
        :param x_snapshot: Optional reduced state snapshot
        :type x_snapshot: np.ndarray | None
        :return: None
        :rtype: None
        """
        if x_snapshot is None:
            t = float(t)
        else:
            t = float(t)
            x_snapshot = np.array(x_snapshot, dtype=np.float64, copy=False)

    def get_dx(self, x: np.ndarray, xn: np.ndarray, dx: np.ndarray, h: float) -> np.ndarray:
        """
        Return the EMT differential vector used by the reduced residual helpers.

        The RMS pseudo-transient code requests a derivative estimate for its DAE
        residual construction. The EMT reduced initialization residual already
        carries all required differential information through the full EMT `dx`
        buffer, so the adapter returns a copy of that frozen vector.

        :param x: Current reduced iterate.
        :type x: np.ndarray
        :param xn: Previous reduced iterate.
        :type xn: np.ndarray
        :param dx: Previous differential estimate.
        :type dx: np.ndarray
        :param h: Pseudo-time step size.
        :type h: float
        :return: Differential vector used by EMT residual evaluation.
        :rtype: np.ndarray
        """
        x = np.array(x, dtype=np.float64, copy=False)
        xn = np.array(xn, dtype=np.float64, copy=False)
        dx = np.array(dx, dtype=np.float64, copy=False)
        h = float(h)
        return self._dx_full.copy()

    def rhs_state(self, x: np.ndarray, dx: np.ndarray) -> np.ndarray:
        """
        Return the reduced residual entries associated with unresolved states.

        :param x: Current reduced iterate.
        :type x: np.ndarray
        :param dx: Differential vector requested by the solver.
        :type dx: np.ndarray
        :return: Reduced residual state block.
        :rtype: np.ndarray
        """
        full_residual: np.ndarray = self._evaluate_full_reduced_residual(x, dx)
        n_states: int = self.get_states_number()
        if n_states > 0:
            return full_residual[:n_states]
        else:
            return np.zeros(0, dtype=np.float64)

    def rhs_algebraic(self, values: np.ndarray, diff_values: np.ndarray) -> np.ndarray:
        """
        Return the reduced residual entries associated with non-state unknowns.

        :param values: Current reduced iterate.
        :type values: np.ndarray
        :param diff_values: Differential vector requested by the solver.
        :type diff_values: np.ndarray
        :return: Reduced residual algebraic block.
        :rtype: np.ndarray
        """
        full_residual: np.ndarray = self._evaluate_full_reduced_residual(values, diff_values)
        n_states: int = self.get_states_number()
        return full_residual[n_states:]

    def get_j11(self, x: np.ndarray, dx: np.ndarray, h: float) -> sp.csc_matrix:
        """
        Return the reduced Jacobian state-state block.

        :param x: Current reduced iterate.
        :type x: np.ndarray
        :param dx: Differential vector requested by the solver.
        :type dx: np.ndarray
        :param h: Pseudo-time step size.
        :type h: float
        :return: State-state Jacobian block.
        :rtype: sp.csc_matrix
        """
        jacobian: sp.csc_matrix = self._compute_numerical_jacobian(x, dx, h)
        n_states: int = self.get_states_number()
        if n_states > 0:
            return jacobian[:n_states, :n_states].tocsc()
        else:
            return sp.csc_matrix((0, 0), dtype=np.float64)

    def get_j12(self, x: np.ndarray, dx: np.ndarray, h: float) -> sp.csc_matrix:
        """
        Return the reduced Jacobian state-algebraic block.

        :param x: Current reduced iterate.
        :type x: np.ndarray
        :param dx: Differential vector requested by the solver.
        :type dx: np.ndarray
        :param h: Pseudo-time step size.
        :type h: float
        :return: State-algebraic Jacobian block.
        :rtype: sp.csc_matrix
        """
        jacobian: sp.csc_matrix = self._compute_numerical_jacobian(x, dx, h)
        n_states: int = self.get_states_number()
        return jacobian[:n_states, n_states:].tocsc()

    def get_j21(self, x: np.ndarray, dx: np.ndarray, h: float) -> sp.csc_matrix:
        """
        Return the reduced Jacobian algebraic-state block.

        :param x: Current reduced iterate.
        :type x: np.ndarray
        :param dx: Differential vector requested by the solver.
        :type dx: np.ndarray
        :param h: Pseudo-time step size.
        :type h: float
        :return: Algebraic-state Jacobian block.
        :rtype: sp.csc_matrix
        """
        jacobian: sp.csc_matrix = self._compute_numerical_jacobian(x, dx, h)
        n_states: int = self.get_states_number()
        return jacobian[n_states:, :n_states].tocsc()

    def get_j22(self, x: np.ndarray, dx: np.ndarray, h: float) -> sp.csc_matrix:
        """
        Return the reduced Jacobian algebraic-algebraic block.

        :param x: Current reduced iterate.
        :type x: np.ndarray
        :param dx: Differential vector requested by the solver.
        :type dx: np.ndarray
        :param h: Pseudo-time step size.
        :type h: float
        :return: Algebraic-algebraic Jacobian block.
        :rtype: sp.csc_matrix
        """
        jacobian: sp.csc_matrix = self._compute_numerical_jacobian(x, dx, h)
        n_states: int = self.get_states_number()
        return jacobian[n_states:, n_states:].tocsc()

    def _compute_numerical_jacobian(self, x: np.ndarray, dx: np.ndarray, h: float) -> sp.csc_matrix:
        """
        Return the EMT reduced Jacobian in the matrix form expected by RMS.

        The EMT reduced system already exposes a compiled Jacobian evaluator over
        the reduced unknown ordering. The adapter scatters the reduced iterate to
        the backing EMT vectors and forwards the call directly.

        :param x: Current reduced iterate.
        :type x: np.ndarray
        :param dx: Differential vector requested by the solver.
        :type dx: np.ndarray
        :param h: Pseudo-time step size.
        :type h: float
        :return: Reduced Jacobian matrix.
        :rtype: sp.csc_matrix
        """
        h = float(h)
        full_dx: np.ndarray = self._select_full_dx(dx)
        _scatter_unknown_vector(self._emt_problem, self._reduced_system.unknown_vars, self._x_full, x)
        jacobian: sp.csc_matrix = _evaluate_initialization_jacobian(
            reduced_system=self._reduced_system,
            problem=self._emt_problem,
            x=self._x_full,
            dx=full_dx,
            runtime_params=self._runtime_params,
            constant_params=self._constant_params,
        )
        return jacobian.tocsc(copy=True)

    def _evaluate_full_reduced_residual(self, reduced_x: np.ndarray, dx: np.ndarray) -> np.ndarray:
        """
        Evaluate the full EMT reduced residual at one reduced iterate.

        :param reduced_x: Current reduced iterate.
        :type reduced_x: np.ndarray
        :param dx: Differential vector requested by the solver.
        :type dx: np.ndarray
        :return: Reduced residual vector.
        :rtype: np.ndarray
        """
        full_dx: np.ndarray = self._select_full_dx(dx)
        _scatter_unknown_vector(self._emt_problem, self._reduced_system.unknown_vars, self._x_full, reduced_x)
        residual: np.ndarray = _evaluate_initialization_residual(
            reduced_system=self._reduced_system,
            problem=self._emt_problem,
            x=self._x_full,
            dx=full_dx,
            runtime_params=self._runtime_params,
            constant_params=self._constant_params,
        )
        return residual.copy()

    def _select_full_dx(self, dx: np.ndarray) -> np.ndarray:
        """
        Resolve the full EMT differential vector used for residual evaluation.

        :param dx: Differential vector received from the RMS solver.
        :type dx: np.ndarray
        :return: Full EMT differential vector.
        :rtype: np.ndarray
        """
        if dx.size == self._dx_full.size:
            return np.array(dx, dtype=np.float64, copy=True)
        else:
            return self._dx_full.copy()


def _collect_reduced_initialization_problem(
        problem: EmtProblemTemplate,
        allow_state_equilibrium: bool,
        fixed_algebraic_uids: Optional[Set[int]] = None,
) -> Tuple[List[Var], List[Expr], np.ndarray] | None:
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
    state_eq_lookup: Dict[int, Expr] = _build_state_equation_lookup(problem)
    init_eq_lookup: Dict[Var, Expr] = problem.sys_block.init_eqs
    algebraic_vars: List[Var] = problem.get_algebraic_vars()
    algebraic_eqs: List[Expr] = problem.get_algebraic_eqs()
    alg_idx: int = 0

    fixed_uids: Set[int] = set() if fixed_algebraic_uids is None else fixed_algebraic_uids
    while alg_idx < len(algebraic_vars):
        algebraic_var: Var = algebraic_vars[alg_idx]
        if algebraic_var.uid not in fixed_uids:
            algebraic_unknown_vars.append(algebraic_var)
        algebraic_residual_eqs.append(algebraic_eqs[alg_idx])
        alg_idx += 1

    for state_var in problem.get_state_vars():
        if state_var.uid in problem.init_guess:
            state_var = state_var
        else:
            state_unknown_vars.append(state_var)

            if state_var in init_eq_lookup:
                state_residual_eqs.append(state_var - init_eq_lookup[state_var])
            elif allow_state_equilibrium and state_var.uid in state_eq_lookup:
                state_residual_eqs.append(state_eq_lookup[state_var.uid])
            else:
                state_residual_eqs.append(state_var)

    unknown_vars: List[Var] = state_unknown_vars + algebraic_unknown_vars
    residual_eqs: List[Expr] = state_residual_eqs + algebraic_residual_eqs
    state_unknown_flags: List[float] = [1.0] * len(state_unknown_vars) + [0.0] * len(algebraic_unknown_vars)

    if len(unknown_vars) == 0:
        return None
    else:
        return unknown_vars, residual_eqs, np.asarray(state_unknown_flags, dtype=np.float64)


def _evaluate_initialization_residual(
        reduced_system: ReducedInitializationSystem,
        problem: EmtProblemTemplate,
        x: np.ndarray,
        dx: np.ndarray,
        runtime_params: np.ndarray,
        constant_params: np.ndarray,
) -> np.ndarray:
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


def _evaluate_initialization_jacobian(
        reduced_system: ReducedInitializationSystem,
        problem: EmtProblemTemplate,
        x: np.ndarray,
        dx: np.ndarray,
        runtime_params: np.ndarray,
        constant_params: np.ndarray,
) -> sp.csc_matrix:
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


def _evaluate_reduced_pseudo_transient_residual(
        reduced_system: ReducedInitializationSystem,
        problem: EmtProblemTemplate,
        x: np.ndarray,
        x_prev_reduced: np.ndarray,
        dx: np.ndarray,
        runtime_params: np.ndarray,
        constant_params: np.ndarray,
        dtau: float,
) -> np.ndarray:
    """
    Evaluate the reduced EMT pseudo-transient residual.

    State rows use a backward-Euler pseudo-time term while algebraic rows keep the
    original reduced steady-state residual.

    :param reduced_system: Reduced initialization system.
    :param problem: EMT problem being initialized.
    :param x: Full EMT variable vector at the current reduced iterate.
    :param x_prev_reduced: Previous reduced iterate used as the pseudo-time reference.
    :param dx: Full EMT differential vector.
    :param runtime_params: Runtime-parameter vector.
    :param constant_params: Constant-parameter vector.
    :param dtau: Pseudo-time step.
    :return: Reduced pseudo-transient residual vector.
    """
    # Start from the steady-state reduced residual because the EMT initialization
    # problem is defined in those equilibrium equations already.
    residual: np.ndarray = _evaluate_initialization_residual(
        reduced_system=reduced_system,
        problem=problem,
        x=x,
        dx=dx,
        runtime_params=runtime_params,
        constant_params=constant_params,
    )
    # Recover the current reduced iterate so the state rows can add the
    # backward-Euler pseudo-time difference against the previous iterate.
    reduced_x: np.ndarray = _extract_unknown_vector(problem, reduced_system.unknown_vars, x)
    state_mask: np.ndarray = np.asarray(reduced_system.state_unknown_mask, dtype=np.float64)
    dtau_eff: float = float(max(dtau, 1.0e-30))
    residual = residual.copy()
    # Only unresolved state rows receive the pseudo-time term. Algebraic rows stay
    # unchanged so they continue to enforce the original consistency equations.
    residual += state_mask * ((reduced_x - x_prev_reduced) / dtau_eff)
    return residual


def _evaluate_reduced_pseudo_transient_jacobian(
        reduced_system: ReducedInitializationSystem,
        problem: EmtProblemTemplate,
        x: np.ndarray,
        dx: np.ndarray,
        runtime_params: np.ndarray,
        constant_params: np.ndarray,
        dtau: float,
) -> sp.csc_matrix:
    """
    Evaluate the Jacobian of the reduced EMT pseudo-transient residual.

    :param reduced_system: Reduced initialization system.
    :param problem: EMT problem being initialized.
    :param x: Full EMT variable vector at the current reduced iterate.
    :param dx: Full EMT differential vector.
    :param runtime_params: Runtime-parameter vector.
    :param constant_params: Constant-parameter vector.
    :param dtau: Pseudo-time step.
    :return: Reduced pseudo-transient Jacobian matrix in CSC format.
    """
    # Reuse the steady-state Jacobian because it already differentiates the reduced
    # EMT equilibrium equations with respect to the reduced unknown ordering.
    jacobian: sp.csc_matrix = _evaluate_initialization_jacobian(
        reduced_system=reduced_system,
        problem=problem,
        x=x,
        dx=dx,
        runtime_params=runtime_params,
        constant_params=constant_params,
    )
    state_mask: np.ndarray = np.asarray(reduced_system.state_unknown_mask, dtype=np.float64)
    dtau_eff: float = float(max(dtau, 1.0e-30))
    # The backward-Euler pseudo-time term contributes only on state rows, so the
    # Jacobian adds a diagonal 1/dtau term only for reduced state unknowns.
    return (jacobian + sp.diags(state_mask / dtau_eff, format="csc")).tocsc(copy=True)


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


def _solve_reduced_linear_system(
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

    if matrix.shape[0] != matrix.shape[1]:
        least_squares_solution = spla.lsqr(matrix, rhs)
        return np.asarray(least_squares_solution[0], dtype=np.float64)

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


def _run_reduced_newton_initialization(
        reduced_system: ReducedInitializationSystem,
        problem: EmtProblemTemplate,
        x: np.ndarray,
        dx: np.ndarray,
        runtime_params: np.ndarray,
        constant_params: np.ndarray,
        options: EmtOptions,
        report: EmtInitializationReport,
) -> bool:
    """
    Solve the reduced initialization system with damped sparse Newton iterations.

    :param reduced_system: Reduced initialization system.
    :param problem: EMT problem being initialized.
    :param x: Full EMT variable vector updated in place.
    :param dx: Full EMT differential vector.
    :param runtime_params: Runtime-parameter vector.
    :param constant_params: Constant-parameter vector.
    :param options: EMT simulation options.
    :param report: Initialization report updated in place.
    :return: True if Newton converged.
    """
    reduced_x: np.ndarray = _extract_unknown_vector(problem, reduced_system.unknown_vars, x)
    max_iter: int = int(options.init_newton_max_iter)
    tol: float = float(options.init_newton_tol)

    iter_idx: int = 0
    while iter_idx < max_iter:
        _scatter_unknown_vector(problem, reduced_system.unknown_vars, x, reduced_x)
        residual: np.ndarray = _evaluate_initialization_residual(reduced_system, problem, x, dx, runtime_params, constant_params)
        res_norm: float = _max_abs_value(residual)

        # report

        if iter_idx == 0:
            report.initial_residual_inf = res_norm
        else:
            report.initial_residual_inf = report.initial_residual_inf

        report.final_residual_inf = res_norm
        if res_norm <= tol:
            report.newton_iterations = iter_idx
            return True
        else:
            report.final_residual_inf = report.final_residual_inf

        jacobian: sp.csc_matrix = _evaluate_initialization_jacobian(reduced_system, problem, x, dx, runtime_params, constant_params)
        delta: np.ndarray = _solve_reduced_linear_system(jacobian, -residual, int(options.init_dense_threshold))

        if np.all(np.isfinite(delta)):
            delta = delta
        else:
            return False

        alpha: float = 1.0
        accepted: bool = False
        while alpha >= 1.0e-4:
            trial_reduced_x: np.ndarray = reduced_x + alpha * delta
            _scatter_unknown_vector(problem, reduced_system.unknown_vars, x, trial_reduced_x)
            trial_residual: np.ndarray = _evaluate_initialization_residual(reduced_system, problem, x, dx, runtime_params, constant_params)
            trial_norm: float = _max_abs_value(trial_residual)

            if (not options.init_newton_backtracking) or (trial_norm < res_norm):
                reduced_x = trial_reduced_x
                accepted = True
                break
            else:
                alpha *= 0.5

        if accepted:
            reduced_x = reduced_x
        else:
            return False

        iter_idx += 1

    report.newton_iterations = max_iter
    return False


def _run_reduced_pseudo_transient_initialization(
        reduced_system: ReducedInitializationSystem,
        problem: EmtProblemTemplate,
        x: np.ndarray,
        dx: np.ndarray,
        runtime_params: np.ndarray,
        constant_params: np.ndarray,
        options: EmtOptions,
        report: EmtInitializationReport,
) -> bool:
    """
    Solve the reduced initialization system with pseudo-transient iterations.

    :param reduced_system: Reduced initialization system.
    :param problem: EMT problem being initialized.
    :param x: Full EMT variable vector updated in place.
    :param dx: Full EMT differential vector.
    :param runtime_params: Runtime-parameter vector.
    :param constant_params: Constant-parameter vector.
    :param options: EMT simulation options.
    :param report: Initialization report updated in place.
    :return: True if pseudo-transient converged.
    """
    # The reduced vector stores only unresolved EMT unknowns. The pseudo-transient
    # loop advances those unknowns while the full EMT storage remains authoritative.
    reduced_x: np.ndarray = _extract_unknown_vector(problem, reduced_system.unknown_vars, x)
    dtau: float = float(options.init_ptc_dtau0)
    dtau_min: float = float(options.init_ptc_dtau_min)
    dtau_max: float = float(options.init_ptc_dtau_max)
    max_iter: int = int(options.init_ptc_max_iter)
    tol: float = float(options.init_newton_tol)
    # The previous reduced iterate supplies the pseudo-time reference for state rows.
    x_prev_reduced: np.ndarray = reduced_x.copy()

    iter_idx: int = 0
    while iter_idx < max_iter:
        # Scatter first so all residual and Jacobian evaluations see one consistent
        # full EMT state assembled from the current reduced iterate.
        _scatter_unknown_vector(problem, reduced_system.unknown_vars, x, reduced_x)
        residual: np.ndarray = _evaluate_reduced_pseudo_transient_residual(
            reduced_system=reduced_system,
            problem=problem,
            x=x,
            x_prev_reduced=x_prev_reduced,
            dx=dx,
            runtime_params=runtime_params,
            constant_params=constant_params,
            dtau=dtau,
        )
        res_norm: float = _max_abs_value(residual)
        report.final_residual_inf = res_norm

        if res_norm <= tol:
            report.pseudo_transient_steps = iter_idx
            return True
        else:
            report.final_residual_inf = report.final_residual_inf

        # Build the Jacobian of the pseudo-transient residual, not just the original
        # steady-state residual, so the Newton-like correction matches the algorithm.
        linear_matrix: sp.csc_matrix = _evaluate_reduced_pseudo_transient_jacobian(
            reduced_system=reduced_system,
            problem=problem,
            x=x,
            dx=dx,
            runtime_params=runtime_params,
            constant_params=constant_params,
            dtau=max(dtau, dtau_min),
        )

        delta: np.ndarray = _solve_reduced_linear_system(linear_matrix, -residual, int(options.init_dense_threshold))

        if np.all(np.isfinite(delta)):
            # Form one trial iterate and accept it only when the pseudo-transient
            # residual decreases. This keeps the continuation monotone enough for
            # the small initialization problems solved here.
            trial_reduced_x: np.ndarray = reduced_x + delta
            _scatter_unknown_vector(problem, reduced_system.unknown_vars, x, trial_reduced_x)
            trial_residual: np.ndarray = _evaluate_reduced_pseudo_transient_residual(
                reduced_system=reduced_system,
                problem=problem,
                x=x,
                x_prev_reduced=x_prev_reduced,
                dx=dx,
                runtime_params=runtime_params,
                constant_params=constant_params,
                dtau=max(dtau, dtau_min),
            )
            trial_norm: float = _max_abs_value(trial_residual)

            if trial_norm < res_norm:
                # Once a step is accepted, the old iterate becomes the new pseudo-time
                # reference and dtau is expanded to accelerate convergence.
                x_prev_reduced = reduced_x.copy()
                reduced_x = trial_reduced_x
                dtau = min(dtau_max, dtau * 2.0)
            else:
                # Rejected steps shrink dtau so the next pseudo-time correction is
                # more damped and therefore more likely to be accepted.
                dtau = max(dtau_min, dtau * 0.5)
        else:
            # Non-finite linear corrections indicate an unusable local model, so the
            # next attempt must reduce dtau instead of updating the iterate.
            dtau = max(dtau_min, dtau * 0.5)

        iter_idx += 1

    report.pseudo_transient_steps = max_iter
    return False


def _run_pseudo_transient_initialization(
        reduced_system: ReducedInitializationSystem,
        problem: EmtProblemTemplate,
        x: np.ndarray,
        dx: np.ndarray,
        runtime_params: np.ndarray,
        constant_params: np.ndarray,
        options: EmtOptions,
        report: EmtInitializationReport,
) -> bool:
    """
    Solve the EMT reduced initialization system using the RMS pseudo-transient solver.

    This function is intentionally shaped like
    ``_run_reduced_pseudo_transient_initialization()`` so the EMT initialization
    workflow can switch between both pseudo-transient implementations by only
    changing the callee in the native initialization dispatcher.

    The adapter created here maps the EMT reduced residual and Jacobian to the
    problem interface expected by the RMS ``PseudoTransient`` solver. The solver
    operates on the reduced EMT unknown vector, and the accepted solution is then
    scattered back into the full EMT state vector before returning.

    :param reduced_system: Reduced initialization system.
    :type reduced_system: ReducedInitializationSystem
    :param problem: EMT problem being initialized.
    :type problem: EmtProblemTemplate
    :param x: Full EMT variable vector updated in place.
    :type x: np.ndarray
    :param dx: Full EMT differential vector.
    :type dx: np.ndarray
    :param runtime_params: Runtime-parameter vector.
    :type runtime_params: np.ndarray
    :param constant_params: Constant-parameter vector.
    :type constant_params: np.ndarray
    :param options: EMT simulation options.
    :type options: EmtOptions
    :param report: Initialization report updated in place.
    :type report: EmtInitializationReport
    :return: ``True`` when the RMS pseudo-transient solver reaches the EMT tolerance.
    :rtype: bool
    """
    adapter_problem: EmtPseudoTransientProblemAdapter = EmtPseudoTransientProblemAdapter(
        reduced_system=reduced_system,
        problem=problem,
        x_full=x,
        dx_full=dx,
        runtime_params=runtime_params,
        constant_params=constant_params,
    )

    # The RMS pseudo-transient solver works on its own reduced local vector. The
    # EMT x-vector therefore remains the authoritative storage and is updated only
    # once a candidate solution has been produced.
    reduced_x0: np.ndarray = adapter_problem.get_x0()
    solver: PseudoTransient = PseudoTransient(
        problem=adapter_problem,
        h=1.0,
        dtau0=float(options.init_ptc_dtau0),
        dtau_max=float(options.init_ptc_dtau_max),
        dtau_min=float(options.init_ptc_dtau_min),
        tol=float(options.init_newton_tol),
        max_iter=int(options.init_ptc_max_iter),
        verbose=bool(options.verbose > 0),
        reference_error_tol=-1.0,
        fixed_var_uids=list(),
    )

    reduced_solution: np.ndarray
    reduced_solution: np.ndarray
    init_guess_map: Dict[Var, float]
    reduced_solution, init_guess_map = solver.simulate(plot=False, x0=reduced_x0)
    if len(init_guess_map) > 0:
        init_guess_map = init_guess_map
    else:
        init_guess_map = init_guess_map

    # The RMS solver returns the reduced unknown vector. That vector must be
    # scattered back to the full EMT variable storage before the residual is
    # evaluated under EMT convergence rules.
    _scatter_unknown_vector(problem, reduced_system.unknown_vars, x, reduced_solution)
    final_residual: np.ndarray = _evaluate_initialization_residual(
        reduced_system=reduced_system,
        problem=problem,
        x=x,
        dx=dx,
        runtime_params=runtime_params,
        constant_params=constant_params,
    )
    final_residual_inf: float = _max_abs_value(final_residual)
    report.final_residual_inf = final_residual_inf

    if np.isfinite(final_residual_inf):
        report.pseudo_transient_steps = int(options.init_ptc_max_iter)
    else:
        report.pseudo_transient_steps = int(options.init_ptc_max_iter)

    if final_residual_inf <= float(options.init_newton_tol):
        return True
    else:
        return False


def _apply_solution_to_problem(problem: EmtProblemTemplate, x: np.ndarray) -> None:
    """
    Persist the reduced-solve state vector back into the initialization guess map.

    :param problem: EMT problem being initialized.
    :param x: Full EMT variable vector.
    :return: None
    """
    all_vars: List[Var] = list(problem.get_state_vars()) + list(problem.get_algebraic_vars())
    for var in all_vars:
        problem.init_guess[var.uid] = float(x[problem.uid2idx_vars[var.uid]])


def _compute_missing_dx0(problem: EmtProblemTemplate,
                         report: EmtInitializationReport,
                         x_full: Optional[np.ndarray] = None,
                         dx_full: Optional[np.ndarray] = None,
                         runtime_params: Optional[np.ndarray] = None,
                         constant_params: Optional[np.ndarray] = None,
                         include_existing: bool = False) -> None:
    """
    Compute missing differential initial values from the state equations.

    :param problem: EMT problem being initialized.
    :param report: Initialization report updated in place.
    :return: None
    """
    state_eqs: List[Expr] = problem.get_state_eqs()
    if len(state_eqs) == 0:
        return
    else:
        state_eqs = state_eqs

    phase_t0: float = time.perf_counter()
    missing_diff_vars: List[Var]
    missing_state_eqs: List[Expr]
    missing_diff_vars, missing_state_eqs = _collect_missing_dx_problem(problem, include_existing=include_existing)
    report.missing_dx_problem_collect_s = float(time.perf_counter() - phase_t0)

    if len(missing_diff_vars) == 0:
        return
    else:
        pass

    phase_t0 = time.perf_counter()
    if x_full is None:
        x0: np.ndarray = problem.get_x0()
    else:
        x0 = x_full
    report.x0_rebuild_s = float(time.perf_counter() - phase_t0)

    phase_t0 = time.perf_counter()
    if dx_full is None:
        dx0_seed: np.ndarray = problem.get_dx0()
    else:
        dx0_seed = dx_full
    report.dx0_seed_build_s = float(time.perf_counter() - phase_t0)

    if runtime_params is None or len(runtime_params) != problem.get_variable_parameter_number():
        runtime_params = _build_runtime_param_array(problem)
    else:
        runtime_params = runtime_params

    if constant_params is None or len(constant_params) != len(problem.get_parameters_values()):
        constant_params = _build_constant_param_array(problem)
    else:
        constant_params = constant_params
    cache_key: str = _build_state_rhs_cache_key(problem, missing_state_eqs)
    state_rhs_fn = _load_or_build_state_rhs_vector(problem, missing_state_eqs, cache_key, report)

    phase_t0 = time.perf_counter()
    computed_dx: np.ndarray = state_rhs_fn(x0, dx0_seed, runtime_params, constant_params).copy()
    report.state_rhs_eval_s = float(time.perf_counter() - phase_t0)

    idx: int = 0
    phase_t0 = time.perf_counter()
    while idx < len(missing_diff_vars):
        diff_var: Var = missing_diff_vars[idx]
        problem.diff_init_guess[diff_var.uid] = float(computed_dx[idx])
        report.automatic_dx0_count += 1
        idx += 1
    report.missing_dx_scatter_s = float(time.perf_counter() - phase_t0)



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
    reduced_system: ReducedInitializationSystem | None = _build_reduced_initialization_system(
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


def run_emt_native_initialization(problem: EmtProblemTemplate, options: EmtOptions) -> EmtInitializationReport:
    """
    Run the EMT-native initialization stages after power-flow variable projection.

    The workflow keeps the current seed intact, then solves only the unresolved
    subset with the native initialization algorithm requested by
    ``options.initialization_method``. The concrete EMT build uses device-local
    periodic pseudo-transient initialization directly from PF seeds for
    ``PseudoTransient``; this native dispatcher remains available for direct
    helper calls and the other initialization methods.
    Missing differential initial values are computed automatically from the state
    equations.

    :param problem: EMT problem being initialized.
    :param options: EMT simulation options.
    :return: Initialization report.
    """
    report = EmtInitializationReport(method_requested=options.initialization_method)
    start_time: float = time.perf_counter()
    x: np.ndarray = problem.get_x0()
    x_seed: np.ndarray = x.copy()
    dx: np.ndarray = problem.get_dx0()
    method_requested: EmtInitializationMethod = options.initialization_method
    runtime_params: np.ndarray = np.zeros(0, dtype=np.float64)
    constant_params: np.ndarray = np.zeros(0, dtype=np.float64)
    reduced_cache_key: str | None = None

    if method_requested == EmtInitializationMethod.Explicit:
        report.status = InitializationStatus.RESOLVED
        report.method_used = EmtInitializationMethod.Explicit
    else:
        reduced_system: ReducedInitializationSystem | None
        runtime_params: np.ndarray
        constant_params: np.ndarray
        reduced_problem_payload: Tuple[List[Var], List[Expr], np.ndarray] | None

        try:
            phase_t0: float = time.perf_counter()
            fixed_algebraic_uids: Set[int] = set()
            if options.init_fix_pf_bus_voltages:
                grid = getattr(problem, "grid", None)
                for bus in getattr(grid, "buses", []):
                    bus_model = getattr(bus, "emt_model", None)
                    for bus_var in getattr(bus_model, "algebraic_vars", []):
                        if isinstance(bus_var, Var):
                            fixed_algebraic_uids.add(bus_var.uid)
            reduced_problem_payload = _collect_reduced_initialization_problem(
                problem=problem,
                allow_state_equilibrium=bool(options.init_allow_state_equilibrium),
                fixed_algebraic_uids=fixed_algebraic_uids,
            )

            if reduced_problem_payload is None:
                reduced_system = None
                report.unknown_var_count = 0
                report.unresolved_state_count = 0
            else:
                report.unknown_var_count = len(reduced_problem_payload[0])
                report.unresolved_state_count = int(np.count_nonzero(reduced_problem_payload[2]))
                reduced_system = None

            report.reduced_system_build_s = float(time.perf_counter() - phase_t0)

            phase_t0 = time.perf_counter()
            runtime_params = _build_runtime_param_array(problem)
            report.runtime_param_build_s = float(time.perf_counter() - phase_t0)

            phase_t0 = time.perf_counter()
            constant_params = _build_constant_param_array(problem)
            report.constant_param_build_s = float(time.perf_counter() - phase_t0)

            if reduced_problem_payload is None:
                reduced_cache_key = None
            else:
                reduced_cache_key = _build_persistent_initialization_cache_key(
                    problem=problem,
                    unknown_vars=reduced_problem_payload[0],
                    residual_eqs=reduced_problem_payload[1],
                    state_unknown_mask=reduced_problem_payload[2],
                    options=options,
                )

                phase_t0 = time.perf_counter()
                cached_payload: Dict[str, object] | None = _load_persistent_initialization_solution(reduced_cache_key)
                report.persistent_cache_load_s = float(time.perf_counter() - phase_t0)

                if cached_payload is None:
                    reduced_system = ReducedInitializationSystem(
                        problem=problem,
                        unknown_vars=reduced_problem_payload[0],
                        residual_eqs=reduced_problem_payload[1],
                        state_unknown_mask=reduced_problem_payload[2],
                    )
                    report.reduced_system_build_s += 0.0
                else:
                    if "init_guess_by_name" in cached_payload and "diff_init_guess_by_name" in cached_payload and _persistent_initialization_params_match(cached_payload, runtime_params, constant_params):
                        init_guess_payload: Dict[str, float] = cast(Dict[str, float], cached_payload["init_guess_by_name"])
                        report_payload: Dict[str, object] = cast(Dict[str, object], cached_payload["report"])
                        problem.init_guess = _restore_problem_guess_map(problem, dict(init_guess_payload), False)
                        problem.diff_init_guess = dict()
                        _compute_missing_dx0(
                            problem,
                            report,
                            runtime_params=runtime_params,
                            constant_params=constant_params,
                            include_existing=True,
                        )
                        _restore_initialization_report_from_payload(report, dict(report_payload))
                        report.persistent_cache_hit = True
                        report.persistent_cache_load_s = float(report.persistent_cache_load_s)
                        report.elapsed_s = float(time.perf_counter() - start_time)
                        return report
                    else:
                        reduced_system = ReducedInitializationSystem(
                            problem=problem,
                            unknown_vars=reduced_problem_payload[0],
                            residual_eqs=reduced_problem_payload[1],
                            state_unknown_mask=reduced_problem_payload[2],
                        )
        except (FloatingPointError, ZeroDivisionError, ValueError, RuntimeError):
            reduced_system = None
            runtime_params = np.zeros(0, dtype=np.float64)
            constant_params = np.zeros(0, dtype=np.float64)
            reduced_cache_key = None
            report.status = InitializationStatus.FAILED
            report.method_used = EmtInitializationMethod.Explicit
            report.message = "Reduced initialization system construction failed; keeping explicit initialization."

        if reduced_system is None:
            if report.status == InitializationStatus.FAILED:
                x[:] = x_seed
            else:
                report.status = InitializationStatus.RESOLVED
                report.method_used = EmtInitializationMethod.Explicit
        else:
            try:
                phase_t0 = time.perf_counter()
                residual0: np.ndarray = _evaluate_initialization_residual(reduced_system, problem, x, dx, runtime_params, constant_params)
                report.initial_residual_eval_s = float(time.perf_counter() - phase_t0)
                report.initial_residual_inf = _max_abs_value(residual0)
            except (FloatingPointError, ZeroDivisionError, ValueError, RuntimeError):
                x[:] = x_seed
                report.status = InitializationStatus.FAILED
                report.method_used = EmtInitializationMethod.Explicit
                report.message = "Reduced initialization residual evaluation failed; keeping explicit initialization."
                reduced_system = None

        if reduced_system is None:
            report.final_residual_inf = report.initial_residual_inf
        else:
            use_newton: bool = method_requested in {EmtInitializationMethod.Auto, EmtInitializationMethod.ConsistentNewton}
            use_ptc: bool = method_requested in {EmtInitializationMethod.Auto, EmtInitializationMethod.PseudoTransient}

            converged: bool = False
            if use_newton:
                phase_t0 = time.perf_counter()
                converged = _run_reduced_newton_initialization(
                    reduced_system=reduced_system,
                    problem=problem,
                    x=x,
                    dx=dx,
                    runtime_params=runtime_params,
                    constant_params=constant_params,
                    options=options,
                    report=report,
                )
                report.newton_elapsed_s += float(time.perf_counter() - phase_t0)
                if converged:
                    report.method_used = EmtInitializationMethod.ConsistentNewton
                else:
                    converged = converged
            else:
                converged = False

            if converged:
                report.status = InitializationStatus.RESOLVED
            elif use_ptc:
                phase_t0 = time.perf_counter()
                converged = _run_reduced_pseudo_transient_initialization(
                    reduced_system=reduced_system,
                    problem=problem,
                    x=x,
                    dx=dx,
                    runtime_params=runtime_params,
                    constant_params=constant_params,
                    options=options,
                    report=report,
                )
                # converged = _run_pseudo_transient_initialization(
                #     reduced_system=reduced_system,
                #     problem=problem,
                #     x=x,
                #     dx=dx,
                #     runtime_params=runtime_params,
                #     constant_params=constant_params,
                #     options=options,
                #     report=report,
                # )
                report.pseudo_transient_elapsed_s += float(time.perf_counter() - phase_t0)
                if converged:
                    converged = converged
                else:
                    # Pure PseudoTransient mode must remain pseudo-transient only.
                    # The broader initialization policy requested by the user is
                    # interpreted here, not in the reduced solver itself. When the
                    # method is explicitly PseudoTransient, failing the PTC loop must
                    # keep the explicit seed instead of retrying with Newton. Auto
                    # and ConsistentNewton continue to own the Newton-capable paths.
                    if method_requested == EmtInitializationMethod.PseudoTransient:
                        converged = False
                    else:
                        phase_t0 = time.perf_counter()
                        converged = _run_reduced_newton_initialization(
                            reduced_system=reduced_system,
                            problem=problem,
                            x=x,
                            dx=dx,
                            runtime_params=runtime_params,
                            constant_params=constant_params,
                            options=options,
                            report=report,
                        )
                        report.newton_elapsed_s += float(time.perf_counter() - phase_t0)
                if converged:
                    report.status = InitializationStatus.RESOLVED
                    if method_requested == EmtInitializationMethod.PseudoTransient:
                        report.method_used = EmtInitializationMethod.PseudoTransient
                    elif method_requested == EmtInitializationMethod.Auto:
                        report.method_used = EmtInitializationMethod.PseudoTransient
                    else:
                        report.method_used = EmtInitializationMethod.ConsistentNewton
                else:
                    x[:] = x_seed
                    report.status = InitializationStatus.FAILED
                    if method_requested == EmtInitializationMethod.PseudoTransient:
                        report.method_used = EmtInitializationMethod.PseudoTransient
                        report.message = "Pseudo-transient initialization failed."
                    else:
                        report.method_used = EmtInitializationMethod.Explicit
                        report.message = "Consistent initialization failed after pseudo-transient fallback; keeping explicit initialization."
            else:
                x[:] = x_seed
                report.status = InitializationStatus.FAILED
                report.method_used = EmtInitializationMethod.Explicit
                report.message = "Consistent initialization failed and pseudo-transient fallback was disabled."

    phase_t0 = time.perf_counter()
    _apply_solution_to_problem(problem, x)
    solution_apply_s: float = float(time.perf_counter() - phase_t0)
    report.solution_apply_s = solution_apply_s
    phase_t0 = time.perf_counter()
    _compute_missing_dx0(
        problem,
        report,
        x_full=x,
        dx_full=dx,
        runtime_params=runtime_params,
        constant_params=constant_params,
        include_existing=True,
    )
    report.dx0_completion_s = float(time.perf_counter() - phase_t0)
    report.elapsed_s = float(time.perf_counter() - start_time)
    report.dx0_completion_s += solution_apply_s

    if report.status == InitializationStatus.RESOLVED and reduced_cache_key is not None:
        phase_t0 = time.perf_counter()
        _store_persistent_initialization_solution(
            reduced_cache_key,
            dict(
                init_guess_by_name=_serialize_problem_guess_map(problem, dict(problem.init_guess), False),
                diff_init_guess_by_name=_serialize_problem_guess_map(problem, dict(problem.diff_init_guess), True),
                runtime_params_snapshot=runtime_params.tolist(),
                constant_params_snapshot=constant_params.tolist(),
                report=_serialize_initialization_report(report),
            ),
        )
        report.persistent_cache_store_s = float(time.perf_counter() - phase_t0)
    else:
        report.persistent_cache_store_s = 0.0

    return report
