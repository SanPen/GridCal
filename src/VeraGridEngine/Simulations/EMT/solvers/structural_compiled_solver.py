# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from enum import Enum
from typing import Any, Callable, Dict, List, Set, Tuple, Optional
import hashlib
import time

import numba as nb
from numba import types
import numpy as np
import numpy.typing as npt
from scipy.linalg import lu_factor, lu_solve
from scipy.sparse import csc_matrix
from scipy.sparse.linalg import SuperLU, splu

from VeraGridEngine.Utils.Symbolic.diagnostic import (
    NewtonDiagnosticsConfig,
    NewtonSolveContext,
    dense_lstsq_fallback,
    maybe_apply_backtracking,
    maybe_check_index1,
    sparse_lsqr_fallback,
    with_newton_diagnostics,
)
from VeraGridEngine.Utils.Symbolic.symbolic import BinOp, Const, Expr, Func, UnOp, Var
from VeraGridEngine.Utils.Symbolic.jit_compiler import (
    EagerEquationCompiler, _compile_to_file, _fingerprint_codegen_expr, _StructuralExpressionContext,
)
from VeraGridEngine.Utils.NumericalMethods.emt_sparse_superlu_backend import SuperLUSparseBackendProvider
from VeraGridEngine.Utils.NumericalMethods.external_sparse_solver_interface import (
    SparseLinearFactorizationHandle,
    SparseLinearSolverBackend,
    SparseLinearSolverBackendProvider,
)
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import (
    EmtBoundaryUpdateProtocol,
    EmtProblemTemplate,
    get_solver_forced_event_time,
    resolve_solver_boundary_step,
    resolve_solver_boundary_updater,
)
from VeraGridEngine.Simulations.driver_template import DummySignal
from VeraGridEngine.enumerations import DynamicIntegrationMethod
from VeraGridEngine.basic_structures import Mat, Vec


Float64Vector = npt.NDArray[np.float64]
Float64Matrix = npt.NDArray[np.float64]
Int32Vector = npt.NDArray[np.int32]
Int32Matrix = npt.NDArray[np.int32]
DenseFactorization = Tuple[Any, Any]
DenseSolveBundle = Tuple[DenseFactorization, np.ndarray]
SparseSolveBundle = Tuple[SuperLU, csc_matrix]


class StructuralCompiledWarmupPolicy(Enum):
    """
    Warmup policy used by the structural compiled backend.
    """

    Off = "off"
    Adaptive = "adaptive"
    Full = "full"


class CompiledNumbaKernelCache:
    """
    In-process cache of Numba-compiled eager kernels.
    """

    __slots__ = ["_cache"]

    def __init__(self) -> None:
        """
        Build the compiled-kernel cache.

        :return: None.
        :rtype: None
        """
        self._cache: Dict[str, Callable[..., Any]] = dict()

    def get(self, cache_key: str) -> Callable[..., Any] | None:
        """
        Return one cached compiled kernel.

        :param cache_key: Deterministic cache key.
        :type cache_key: str
        :return: Cached compiled kernel or ``None``.
        :rtype: Callable[..., Any] | None
        """
        return self._cache.get(cache_key, None)

    def set(self, cache_key: str, kernel: Callable[..., Any]) -> None:
        """
        Store one compiled kernel.

        :param cache_key: Deterministic cache key.
        :type cache_key: str
        :param kernel: Compiled kernel.
        :type kernel: Callable[..., Any]
        :return: None.
        :rtype: None
        """
        self._cache[cache_key] = kernel


COMPILED_NUMBA_KERNEL_CACHE = CompiledNumbaKernelCache()


def _safe_njit(
        py_func: Callable[..., Any],
        signature_tpe: Any,
        fastmath: bool = True,
        cache: bool = True,
) -> Callable[..., Any]:
    """
    Compile a Python function with Numba using an eager signature when provided.

    :param py_func: Python function created from generated symbolic source.
    :type py_func: Callable[..., Any]
    :param signature_tpe: Eager Numba signature or ``None``.
    :type signature_tpe: Any
    :param fastmath: Whether Numba should enable fastmath rewrites.
    :type fastmath: bool
    :param cache: Whether Numba should persist the compiled machine code.
    :type cache: bool
    :return: Compiled Numba function.
    :rtype: Callable[..., Any]
    """
    compiled_func: Callable[..., Any]
    signature_repr: str
    cache_payload: str
    cache_key: str
    cached_kernel: Callable[..., Any] | None

    if signature_tpe is None:
        signature_repr = "none"
    else:
        signature_repr = str(signature_tpe)

    cache_payload = "|".join([
        py_func.__module__,
        py_func.__name__,
        signature_repr,
        str(fastmath),
        str(cache),
    ])
    cache_key = hashlib.sha256(cache_payload.encode("utf-8")).hexdigest()
    cached_kernel = COMPILED_NUMBA_KERNEL_CACHE.get(cache_key)

    if cached_kernel is None:
        pass
    else:
        return cached_kernel

    if signature_tpe is None:
        compiled_func = nb.njit(fastmath=fastmath, cache=cache)(py_func)
    else:
        compiled_func = nb.njit(signature_tpe, fastmath=fastmath, cache=cache)(py_func)

    COMPILED_NUMBA_KERNEL_CACHE.set(cache_key, compiled_func)
    return compiled_func


def _build_fused_residual_signature() -> Any:
    """
    Return the eager signature of the fused residual dispatcher.

    :return: Eager Numba signature.
    :rtype: Any
    """
    float64_vector_tpe: Any = types.Array(types.float64, 1, "C")
    float64_matrix_tpe: Any = types.Array(types.float64, 2, "C")

    return types.void(
        float64_vector_tpe,
        float64_vector_tpe,
        float64_vector_tpe,
        float64_vector_tpe,
        types.float64,
        float64_vector_tpe,
        float64_vector_tpe,
        float64_matrix_tpe,
    )


def _build_master_jacobian_signature() -> Any:
    """
    Return the eager signature of the sparse Jacobian dispatcher.

    :return: Eager Numba signature.
    :rtype: Any
    """
    float64_vector_tpe: Any = types.Array(types.float64, 1, "C")
    float64_matrix_tpe: Any = types.Array(types.float64, 2, "C")
    int32_vector_tpe: Any = types.Array(types.int32, 1, "C")

    return types.void(
        float64_vector_tpe,
        float64_matrix_tpe,
        float64_vector_tpe,
        float64_vector_tpe,
        float64_vector_tpe,
        types.float64,
        float64_vector_tpe,
        float64_vector_tpe,
        int32_vector_tpe,
        int32_vector_tpe,
        int32_vector_tpe,
        int32_vector_tpe,
        float64_matrix_tpe,
    )


def _build_scatter_color_signature() -> Any:
    """
    Return the eager signature of the CSC scatter helper.

    :return: Eager helper signature.
    :rtype: Any
    """
    float64_vector_tpe: Any = types.Array(types.float64, 1, "C")
    int32_vector_tpe: Any = types.Array(types.int32, 1, "C")

    return types.void(
        float64_vector_tpe,
        float64_vector_tpe,
        int32_vector_tpe,
        int32_vector_tpe,
        int32_vector_tpe,
        int32_vector_tpe,
        types.int64,
    )


def _build_max_abs_signature() -> Any:
    """
    Return the eager signature of the infinity-norm helper.

    :return: Eager helper signature.
    :rtype: Any
    """
    float64_vector_tpe: Any = types.Array(types.float64, 1, "C")
    return types.float64(float64_vector_tpe)


def _build_copy_negated_signature() -> Any:
    """
    Return the eager signature of the negated-copy helper.

    :return: Eager helper signature.
    :rtype: Any
    """
    float64_vector_tpe: Any = types.Array(types.float64, 1, "C")
    return types.void(float64_vector_tpe, float64_vector_tpe)


def _build_fill_full_parameter_signature() -> Any:
    """
    Return the eager signature of the full-parameter fill helper.

    :return: Eager helper signature.
    :rtype: Any
    """
    float64_vector_tpe: Any = types.Array(types.float64, 1, "C")
    return types.void(float64_vector_tpe, float64_vector_tpe, float64_vector_tpe)


def _dense_lu_bundle_solve(bundle: DenseSolveBundle, rhs: Vec) -> Vec:
    """
    Solve one dense LU linear system.

    :param bundle: Dense LU bundle ``(factorization, matrix)``.
    :param rhs: Right-hand side vector.
    :return: Solution vector.
    """
    return lu_solve(bundle[0], rhs)


def _dense_lu_bundle_fallback(bundle: DenseSolveBundle, rhs: Vec) -> Vec:
    """
    Solve one dense fallback least-squares system.

    :param bundle: Dense LU bundle ``(factorization, matrix)``.
    :param rhs: Right-hand side vector.
    :return: Fallback solution vector.
    """
    return dense_lstsq_fallback(bundle[1], rhs)


def _dense_lu_bundle_matrix(bundle: DenseSolveBundle) -> np.ndarray:
    """
    Return the dense matrix stored in one LU bundle.

    :param bundle: Dense LU bundle ``(factorization, matrix)``.
    :return: Dense Jacobian matrix.
    """
    return bundle[1]


def _sparse_factor_manager_solve(factor_manager: "StructuralCompiledSparseFactorizationManager", rhs: Vec) -> Vec:
    """
    Solve one sparse linear system through the compiled sparse factor manager.

    :param factor_manager: Sparse factorization manager.
    :param rhs: Right-hand side vector.
    :return: Solution vector.
    """
    return factor_manager.solve(rhs)


def _sparse_factor_manager_fallback(factor_manager: "StructuralCompiledSparseFactorizationManager", rhs: Vec) -> Vec:
    """
    Solve one sparse fallback least-squares system.

    :param factor_manager: Sparse factorization manager.
    :param rhs: Right-hand side vector.
    :return: Fallback solution vector.
    """
    return factor_manager.solve_fallback(rhs)


def _sparse_factor_manager_matrix(factor_manager: "StructuralCompiledSparseFactorizationManager") -> csc_matrix:
    """
    Return the active sparse Jacobian matrix held by the factor manager.

    :param factor_manager: Sparse factorization manager.
    :return: Active sparse Jacobian matrix.
    """
    return factor_manager.get_active_matrix()


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


def _get_runtime_uid(var_obj: Var) -> int:
    """
    Return the canonical runtime UID of a symbolic variable.

    :param var_obj: Symbolic variable or differential placeholder.
    :type var_obj: Var
    :return: Canonical runtime UID.
    :rtype: int
    """
    runtime_uid: int

    if var_obj.base_var is None:
        runtime_uid = var_obj.uid
    else:
        runtime_uid = var_obj.base_var.uid

    return runtime_uid


def canonicalize_expression(
        expr: Expr,
        runtime_uids: Set[int],
        parameter_uids: Set[int],
) -> Tuple[str, List[Var]]:
    """
    Return the shared structural signature and first-occurrence runtime gathers.

    :param expr: Symbolic expression whose literal values must remain exact.
    :param runtime_uids: UIDs belonging to the runtime state/algebraic vector.
    :param parameter_uids: UIDs belonging to the shared parameter vector.
    :return: Structural fingerprint and one gathered variable per runtime UID.
    :raises RuntimeError: If a supported variable has no runtime/parameter classification.
    """
    # Bind structural roles only for this expression. The existing compiler walk
    # preserves exact constants; its code-generation maps are unused in this context.
    context: _StructuralExpressionContext = _StructuralExpressionContext(runtime_uids, parameter_uids)
    signature: str = _fingerprint_codegen_expr(expr, dict(), dict(), "", None, None, context)
    return signature, context.runtime_variables


def _build_full_residual_equations(
        state_vars: List[Var],
        state_eqs: List[Expr],
        algebraic_eqs: List[Expr],
) -> List[Expr]:
    """
    Build the full implicit residual system used by Newton iterations.

    :param state_vars: Ordered state variables.
    :type state_vars: List[Var]
    :param state_eqs: Differential right-hand sides.
    :type state_eqs: List[Expr]
    :param algebraic_eqs: Algebraic constraints.
    :type algebraic_eqs: List[Expr]
    :return: Full residual system in solver order.
    :rtype: List[Expr]
    """
    n_state: int = len(state_eqs)
    n_alg: int = len(algebraic_eqs)
    full_eqs: List[Expr] = [Const(0.0) for _ in range(n_state + n_alg)]
    i: int = 0

    # The differential block is converted into d_x - f(x, y, p) = 0.
    while i < n_state:
        state_var: Var = state_vars[i]
        differential_term: Var = Var(name=f"d_{state_var.name}", base_var=state_var)
        full_eqs[i] = differential_term - state_eqs[i]
        i += 1

    # The algebraic block is appended directly after the state residuals.
    i = 0
    while i < n_alg:
        full_eqs[n_state + i] = algebraic_eqs[i]
        i += 1

    return full_eqs


def _build_structural_residual_debug_info(state_vars: List[Var],
                                          algebraic_vars: List[Var],
                                          state_eqs: List[Expr],
                                          algebraic_eqs: List[Expr],
                                          uid2idx_vars: Dict[int, int]) -> List[Dict[str, Any]]:
    """
    Build metadata aligned with the structural residual ordering.

    :param state_vars: Ordered state variables.
    :type state_vars: List[Var]
    :param algebraic_vars: Ordered algebraic variables.
    :type algebraic_vars: List[Var]
    :param state_eqs: Differential right-hand sides.
    :type state_eqs: List[Expr]
    :param algebraic_eqs: Algebraic constraints.
    :type algebraic_eqs: List[Expr]
    :param uid2idx_vars: Runtime uid-to-index lookup.
    :type uid2idx_vars: Dict[int, int]
    :return: Residual metadata list.
    :rtype: List[Dict[str, Any]]
    """
    debug_info: List[Dict[str, Any]] = list()
    state_index: int = 0
    algebraic_index: int = 0

    while state_index < len(state_eqs):
        state_var: Var = state_vars[state_index]
        debug_info.append({
            "kind": "STATE",
            "label": f"d_{state_var.name} - rhs_{state_var.name}",
            "var_name": state_var.name,
            "state_idx": uid2idx_vars.get(state_var.uid, None),
        })
        state_index += 1

    while algebraic_index < len(algebraic_eqs):
        if algebraic_index < len(algebraic_vars):
            algebraic_var: Var = algebraic_vars[algebraic_index]
            debug_info.append({
                "kind": "ALG",
                "label": f"alg for {algebraic_var.name}",
                "var_name": algebraic_var.name,
                "state_idx": uid2idx_vars.get(algebraic_var.uid, None),
            })
        else:
            debug_info.append({
                "kind": "ALG",
                "label": f"ALG_EQ_{algebraic_index}",
                "var_name": f"<no algebraic var for eq {algebraic_index}>",
                "state_idx": None,
            })
        algebraic_index += 1

    return debug_info


def _format_structural_residual_zero_division_message(failed_index: int | None,
                                                      debug_info: List[Dict[str, Any]] | None) -> str:
    """
    Format one divide-by-zero diagnostic for the structural residual path.

    :param failed_index: Residual index when known.
    :type failed_index: int | None
    :param debug_info: Residual metadata.
    :type debug_info: List[Dict[str, Any]] | None
    :return: Diagnostic message.
    :rtype: str
    """
    if failed_index is None:
        return "StructuralCompiled residual evaluation failed with division by zero; failing residual index could not be resolved."
    else:
        pass

    if debug_info is None:
        return f"StructuralCompiled residual evaluation failed with division by zero at residual index {failed_index}."
    else:
        pass

    if failed_index < 0 or failed_index >= len(debug_info):
        return f"StructuralCompiled residual evaluation failed with division by zero at residual index {failed_index}."
    else:
        pass

    info: Dict[str, Any] = debug_info[failed_index]
    kind: Any = info.get("kind", "UNK")
    label: Any = info.get("label", f"residual_{failed_index}")
    var_name: Any = info.get("var_name", "<?>")
    return (
        f"StructuralCompiled residual evaluation failed with division by zero at residual index {failed_index} "
        f"[{kind}] for '{var_name}' ({label})."
    )


def _locate_failing_residual_with_single_equation_kernels(equations: List[Expr],
                                                          variables: List[Var],
                                                          parameters: List[Var],
                                                          method: DynamicIntegrationMethod,
                                                          states: Vec,
                                                          params: Vec,
                                                          history: Vec,
                                                          d_history: Vec,
                                                          h: float,
                                                          history2: Vec) -> int | None:
    """
    Locate the first residual index that fails under one-equation Python kernels.

    :param equations: Full residual equation list.
    :type equations: List[Expr]
    :param variables: Ordered runtime variables.
    :type variables: List[Var]
    :param parameters: Ordered parameter list.
    :type parameters: List[Var]
    :param method: Implicit integration method.
    :type method: DynamicIntegrationMethod
    :param states: Current Newton iterate.
    :type states: Vec
    :param params: Full parameter vector.
    :type params: Vec
    :param history: Previous state vector.
    :type history: Vec
    :param d_history: Previous derivative vector.
    :type d_history: Vec
    :param h: Local time step.
    :type h: float
    :param history2: Secondary history vector.
    :type history2: Vec
    :return: Failing residual index or ``None``.
    :rtype: int | None
    """
    compiler: EagerEquationCompiler = EagerEquationCompiler(variables=variables, parameters=parameters, method=method)
    equation_index: int = 0

    while equation_index < len(equations):
        equation_list: List[Expr] = list([equations[equation_index]])
        out_vec: Vec = np.zeros(1, dtype=np.float64)
        py_kernel: Callable[..., Any]
        signature_tpe: object
        py_kernel, signature_tpe = compiler.compile(
            equations=equation_list,
            func_name=f"structural_single_eq_debug_{equation_index}",
            use_cse=True,
            offset=0,
            inplace=True,
        )
        _unused_signature_tpe: object = signature_tpe

        try:
            py_kernel(states, params, history, d_history, h, out_vec, history2)
            equation_index += 1
        except ZeroDivisionError:
            return equation_index

    return None


def _build_parameter_uid_set(
        variable_parameters: List[Var],
        constant_parameters: List[Var],
) -> Set[int]:
    """
    Build the parameter UID set used by structural canonicalization.

    :param variable_parameters: Runtime parameters.
    :type variable_parameters: List[Var]
    :param constant_parameters: Constant parameters.
    :type constant_parameters: List[Var]
    :return: UID set of all parameters visible to the solver.
    :rtype: Set[int]
    """
    parameter_uids: Set[int] = set()
    parameter: Var

    for parameter in variable_parameters:
        parameter_uids.add(parameter.uid)

    for parameter in constant_parameters:
        parameter_uids.add(parameter.uid)

    return parameter_uids


def _build_backend_cache_token(
        method: DynamicIntegrationMethod,
        n_rows: int,
        n_cols: int,
        group_keys: List[str],
) -> str:
    """
    Return a deterministic cache token for backend-generated dispatchers.

    :param method: Integration method used by the backend.
    :type method: DynamicIntegrationMethod
    :param n_rows: Number of residual equations.
    :type n_rows: int
    :param n_cols: Number of runtime variables.
    :type n_cols: int
    :param group_keys: Structural group signatures.
    :type group_keys: List[str]
    :return: Stable cache token.
    :rtype: str
    """
    payload: str = "|".join([method.name, str(n_rows), str(n_cols), str(len(group_keys))])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _greedy_color_columns(col_rows: List[List[int]], n_rows: int) -> Tuple[Int32Vector, int, List[List[int]]]:
    """
    Color the sparse column dependency graph with a greedy heuristic.

    :param col_rows: Row indices present in each sparse column.
    :type col_rows: List[List[int]]
    :param n_rows: Total number of rows in the Jacobian.
    :type n_rows: int
    :return: Colors per column, number of colors and explicit color groups.
    :rtype: Tuple[Int32Vector, int, List[List[int]]]
    """
    n_cols: int = len(col_rows)
    row_cols: List[List[int]] = list()
    adjacency: List[Set[int]] = list()
    color_groups: List[List[int]] = list()
    degrees: Int32Vector
    order: Int32Vector
    colors: Int32Vector
    used: npt.NDArray[np.bool_]
    row_index: int
    col_index: int

    row_index = 0
    while row_index < n_rows:
        row_cols.append(list())
        row_index += 1

    col_index = 0
    while col_index < n_cols:
        row_list: List[int] = col_rows[col_index]
        row_position: int = 0

        while row_position < len(row_list):
            row_cols[row_list[row_position]].append(col_index)
            row_position += 1

        col_index += 1

    col_index = 0
    while col_index < n_cols:
        adjacency.append(set())
        col_index += 1

    row_index = 0
    while row_index < n_rows:
        cols_in_row: List[int] = row_cols[row_index]
        left_pos: int = 0

        while left_pos < len(cols_in_row):
            right_pos: int = left_pos + 1

            while right_pos < len(cols_in_row):
                left_col: int = cols_in_row[left_pos]
                right_col: int = cols_in_row[right_pos]

                if left_col == right_col:
                    pass
                else:
                    adjacency[left_col].add(right_col)
                    adjacency[right_col].add(left_col)

                right_pos += 1

            left_pos += 1

        row_index += 1

    degrees = np.zeros(n_cols, dtype=np.int32)
    col_index = 0
    while col_index < n_cols:
        degrees[col_index] = len(adjacency[col_index])
        col_index += 1

    order = np.argsort(-degrees, kind="stable").astype(np.int32)
    colors = -np.ones(n_cols, dtype=np.int32)
    used = np.zeros(n_cols, dtype=np.bool_)
    max_color: int = -1

    col_index = 0
    while col_index < len(order):
        candidate_col: int = int(order[col_index])
        used[:] = False

        neighbor_col: int
        for neighbor_col in adjacency[candidate_col]:
            neighbor_color: int = int(colors[neighbor_col])

            if neighbor_color >= 0:
                used[neighbor_color] = True
            else:
                pass

        color_value: int = 0
        while color_value < n_cols and used[color_value]:
            color_value += 1

        colors[candidate_col] = color_value

        if color_value > max_color:
            max_color = color_value
        else:
            pass

        col_index += 1

    color_index: int = 0
    while color_index < max_color + 1:
        color_groups.append(list())
        color_index += 1

    col_index = 0
    while col_index < n_cols:
        color_groups[int(colors[col_index])].append(col_index)
        col_index += 1

    return colors, int(max_color + 1), color_groups


@nb.jit(_build_scatter_color_signature(), cache=True, fastmath=True)
def _scatter_color_jvp_to_csc_data(
        jvp: Float64Vector,
        data: Float64Vector,
        color_ptr: Int32Vector,
        col_ptr: Int32Vector,
        row_idx: Int32Vector,
        data_idx: Int32Vector,
        color_id: int,
) -> None:
    """
    Scatter a colored JVP vector into CSC numeric storage.

    :param jvp: JVP vector for the active color.
    :type jvp: Float64Vector
    :param data: Target CSC numeric values.
    :type data: Float64Vector
    :param color_ptr: Pointer to the column-color groups.
    :type color_ptr: Int32Vector
    :param col_ptr: Pointer to each grouped column map.
    :type col_ptr: Int32Vector
    :param row_idx: Row indices in CSC order.
    :type row_idx: Int32Vector
    :param data_idx: Direct positions inside ``data``.
    :type data_idx: Int32Vector
    :param color_id: Active color identifier.
    :type color_id: int
    :return: None
    :rtype: None
    """
    k0: int = int(color_ptr[color_id])
    k1: int = int(color_ptr[color_id + 1])
    k: int = k0

    while k < k1:
        p0: int = int(col_ptr[k])
        p1: int = int(col_ptr[k + 1])
        p: int = p0

        while p < p1:
            data[data_idx[p]] = jvp[row_idx[p]]
            p += 1

        k += 1


@nb.jit(_build_max_abs_signature(), cache=True, fastmath=True)
def _max_abs_value(values: Float64Vector) -> float:
    """
    Compute the infinity norm without allocating temporary arrays.

    :param values: Vector to inspect.
    :type values: Float64Vector
    :return: Maximum absolute value.
    :rtype: float
    """
    max_value: float = 0.0
    index: int = 0

    while index < values.shape[0]:
        raw_value: float = float(values[index])
        abs_value: float

        if raw_value < 0.0:
            abs_value = -raw_value
        else:
            abs_value = raw_value

        if abs_value > max_value:
            max_value = abs_value
        else:
            pass

        index += 1

    return max_value


@nb.jit(_build_copy_negated_signature(), cache=True, fastmath=True)
def _copy_negated_vector(values: Float64Vector, out: Float64Vector) -> None:
    """
    Write the negated vector into a preallocated buffer.

    :param values: Source vector.
    :type values: Float64Vector
    :param out: Destination vector.
    :type out: Float64Vector
    :return: None
    :rtype: None
    """
    index: int = 0

    while index < values.shape[0]:
        out[index] = -values[index]
        index += 1


@nb.jit(_build_fill_full_parameter_signature(), cache=True, fastmath=True)
def _fill_full_parameter_buffer(
        runtime_params: Float64Vector,
        static_params: Float64Vector,
        full_params_out: Float64Vector,
) -> None:
    """
    Write runtime and static parameters into one preallocated full buffer.

    :param runtime_params: Runtime parameter slice.
    :type runtime_params: Float64Vector
    :param static_params: Static parameter slice.
    :type static_params: Float64Vector
    :param full_params_out: Destination full parameter vector.
    :type full_params_out: Float64Vector
    :return: None
    :rtype: None
    """
    runtime_count: int = int(runtime_params.shape[0])
    static_count: int = int(static_params.shape[0])
    index: int = 0

    while index < runtime_count:
        full_params_out[index] = runtime_params[index]
        index += 1

    index = 0
    while index < static_count:
        full_params_out[runtime_count + index] = static_params[index]
        index += 1


@nb.jit(cache=True, fastmath=True)
def _max_abs_diff_vectors(left_values: Float64Vector, right_values: Float64Vector) -> float:
    """
    Return the maximum absolute difference between two vectors.

    :param left_values: Left vector.
    :type left_values: Float64Vector
    :param right_values: Right vector.
    :type right_values: Float64Vector
    :return: Maximum absolute difference.
    :rtype: float
    """
    max_value: float = 0.0
    index: int = 0

    while index < left_values.shape[0]:
        diff_value: float = left_values[index] - right_values[index]

        if diff_value < 0.0:
            diff_value = -diff_value
        else:
            diff_value = diff_value

        if diff_value > max_value:
            max_value = diff_value
        else:
            max_value = max_value

        index += 1

    return max_value




@nb.jit(_build_permute_csc_signature(), cache=True, fastmath=True)
def _permute_csc_data_by_columns(
        source_data: Float64Vector,
        source_indptr: Int32Vector,
        column_perm: Int32Vector,
        target_indptr: Int32Vector,
        target_data: Float64Vector,
) -> None:
    """
    Reorder CSC numeric values according to a persistent column permutation.

    :param source_data: Numeric values in the original column order.
    :type source_data: Float64Vector
    :param source_indptr: Original CSC column pointer.
    :type source_indptr: Int32Vector
    :param column_perm: Persistent destination-to-source column permutation.
    :type column_perm: Int32Vector
    :param target_indptr: Target CSC column pointer.
    :type target_indptr: Int32Vector
    :param target_data: Destination numeric buffer.
    :type target_data: Float64Vector
    :return: None
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
        permuted_solution: Float64Vector,
        inverse_column_perm: Int32Vector,
        out_solution: Float64Vector,
) -> None:
    """
    Scatter a solution computed on a column-permuted system back to original order.

    :param permuted_solution: Solution in the permuted variable order.
    :type permuted_solution: Float64Vector
    :param inverse_column_perm: Mapping from original index to permuted index.
    :type inverse_column_perm: Int32Vector
    :param out_solution: Destination vector in original solver order.
    :type out_solution: Float64Vector
    :return: None
    :rtype: None
    """
    var_index: int = 0

    while var_index < out_solution.shape[0]:
        out_solution[var_index] = permuted_solution[int(inverse_column_perm[var_index])]
        var_index += 1


def _warmup_compiled_numba_helpers() -> None:
    """
    Trigger one eager call to the small Numba helper kernels.

    :return: None
    :rtype: None
    """
    sample_vector: Vec = np.zeros(2, dtype=np.float64)
    sample_out_vector: Vec = np.zeros(2, dtype=np.float64)
    sample_runtime_params: Vec = np.zeros(1, dtype=np.float64)
    sample_static_params: Vec = np.zeros(1, dtype=np.float64)
    sample_full_params: Vec = np.zeros(2, dtype=np.float64)
    sample_source_data: Vec = np.zeros(2, dtype=np.float64)
    sample_target_data: Vec = np.zeros(2, dtype=np.float64)
    sample_indptr: Int32Vector = np.array([0, 1, 2], dtype=np.int32)
    sample_perm: Int32Vector = np.array([0, 1], dtype=np.int32)
    sample_inverse_perm: Int32Vector = np.array([0, 1], dtype=np.int32)
    sample_color_ptr: Int32Vector = np.array([0, 2], dtype=np.int32)
    sample_col_ptr: Int32Vector = np.array([0, 1, 2], dtype=np.int32)
    sample_row_idx: Int32Vector = np.array([0, 1], dtype=np.int32)
    sample_data_idx: Int32Vector = np.array([0, 1], dtype=np.int32)

    _max_abs_value(sample_vector)
    _copy_negated_vector(sample_vector, sample_out_vector)
    _fill_full_parameter_buffer(sample_runtime_params, sample_static_params, sample_full_params)
    _permute_csc_data_by_columns(sample_source_data, sample_indptr, sample_perm, sample_indptr, sample_target_data)
    _scatter_permuted_solution_to_original_order(sample_vector, sample_inverse_perm, sample_out_vector)
    _scatter_color_jvp_to_csc_data(
        sample_vector,
        sample_target_data,
        sample_color_ptr,
        sample_col_ptr,
        sample_row_idx,
        sample_data_idx,
        0,
    )


def _should_run_full_backend_warmup(
        warmup_policy: StructuralCompiledWarmupPolicy,
        n_vars: int,
        estimated_steps: int,
        use_direct_residual: bool,
) -> bool:
    """
    Decide whether the backend should perform a full residual/Jacobian warmup.

    :param warmup_policy: Configured warmup policy.
    :type warmup_policy: StructuralCompiledWarmupPolicy
    :param n_vars: Number of runtime variables.
    :type n_vars: int
    :param estimated_steps: Estimated macro time steps.
    :type estimated_steps: int
    :param use_direct_residual: Whether the backend uses the direct residual path.
    :type use_direct_residual: bool
    :return: ``True`` when a full warmup should run.
    :rtype: bool
    """
    if warmup_policy == StructuralCompiledWarmupPolicy.Full:
        return True
    elif warmup_policy == StructuralCompiledWarmupPolicy.Off:
        return False
    else:
        pass

    # Adaptive mode only pays the full warmup when the run is large enough for
    # the saved runtime to amortize the up-front cost. The direct residual path
    # especially benefits on long trajectories because it is called every Newton step.
    if estimated_steps >= 1000:
        return True
    elif estimated_steps >= 200 and n_vars >= 48:
        return True
    elif use_direct_residual and estimated_steps >= 100:
        return True
    else:
        return False


class StructuralCompiledBoundaryUpdateWrapper:
    """
    Boundary update interface for the structural compiled solver.

    The structural compiled solver keeps the linear algebra outside Numba, but it still needs a
    typed boundary update object to refresh runtime parameters between local
    substeps.
    """

    __slots__ = []

    def update(self, t: float, x: Vec, params: Vec) -> None:
        """
        Update the parameter vector in place.

        :param t: Current simulation time.
        :type t: float
        :param x: Current Newton iterate.
        :type x: Vec
        :param params: Full parameter vector.
        :type params: Vec
        :return: None
        :rtype: None
        """
        _unused: Tuple[float, Vec, Vec] = (t, x, params)
        return None

    def get_next_forced_event_time(self, t_prev: float, t_target: float) -> float | None:
        """
        Return the next forced event time inside the local substep.

        :param t_prev: Local substep start.
        :type t_prev: float
        :param t_target: Local substep nominal end.
        :type t_target: float
        :return: Next forced event time or ``None``.
        :rtype: float | None
        """
        _unused: Tuple[float, float] = (t_prev, t_target)
        return None


class StructuralCompiledPredictor:
    """
    Explicit predictor used to initialize the Newton iteration.
    """

    __slots__ = ["_n_states"]

    def __init__(self, n_states: int) -> None:
        """
        Create the predictor.

        :param n_states: Number of differential states.
        :type n_states: int
        :return: None
        :rtype: None
        """
        self._n_states = n_states

    def predict(
            self,
            x_iter: Vec,
            x_prev: Vec,
            dx_prev: Vec,
            h: float,
            pred_method: DynamicIntegrationMethod | None,
    ) -> Vec:
        """
        Write the predictor guess in place.

        :param x_iter: Destination vector for the predictor guess.
        :type x_iter: Vec
        :param x_prev: Previous variable vector.
        :type x_prev: Vec
        :param dx_prev: Previous differential vector.
        :type dx_prev: Vec
        :param h: Local time step.
        :type h: float
        :param pred_method: Predictor integration method.
        :type pred_method: DynamicIntegrationMethod | None
        :return: Updated predictor vector.
        :rtype: Vec
        """
        # The default predictor is a no-op copy because it is always safe.
        x_iter[:] = x_prev

        # Explicit Euler is only applied to the differential subset.
        if pred_method == DynamicIntegrationMethod.OdeEuler:
            x_iter[:self._n_states] = x_prev[:self._n_states] + h * dx_prev[:self._n_states]
        else:
            pass

        return x_iter


class StructuralCompiledResidualTrialEvaluator:
    """
    Callable helper that evaluates residuals during Newton backtracking.
    """

    __slots__ = ["_residual_assembler", "_full_params", "_x_prev", "_dx_prev", "_h_eff", "_x_prev2"]

    def __init__(self) -> None:
        """
        Build one empty trial-residual evaluator.

        :return: None
        :rtype: None
        """
        self._residual_assembler: StructuralCompiledResidualAssembler | StructuralCompiledDirectResidualAssembler | None = None
        self._full_params: Vec | None = None
        self._x_prev: Vec | None = None
        self._dx_prev: Vec | None = None
        self._h_eff: float = 0.0
        self._x_prev2: Vec | None = None

    def set_context(
            self,
            residual_assembler: StructuralCompiledResidualAssembler | StructuralCompiledDirectResidualAssembler,
            full_params: Vec,
            x_prev: Vec,
            dx_prev: Vec,
            h_eff: float,
            x_prev2: Vec,
    ) -> None:
        """
        Store the residual-evaluation context of the current Newton step.

        :param residual_assembler: Residual assembler.
        :type residual_assembler: StructuralCompiledResidualAssembler | StructuralCompiledDirectResidualAssembler
        :param full_params: Full parameter vector.
        :type full_params: Vec
        :param x_prev: Previous accepted state.
        :type x_prev: Vec
        :param dx_prev: Previous derivative vector.
        :type dx_prev: Vec
        :param h_eff: Effective local time step.
        :type h_eff: float
        :param x_prev2: Secondary state history.
        :type x_prev2: Vec
        :return: None
        :rtype: None
        """
        self._residual_assembler = residual_assembler
        self._full_params = full_params
        self._x_prev = x_prev
        self._dx_prev = dx_prev
        self._h_eff = float(h_eff)
        self._x_prev2 = x_prev2

    def evaluate(self, trial_x: Vec, out_res: Vec) -> float:
        """
        Evaluate one trial Newton iterate during backtracking.

        :param trial_x: Trial iterate.
        :type trial_x: Vec
        :param out_res: Destination residual buffer.
        :type out_res: Vec
        :return: Residual infinity norm.
        :rtype: float
        """
        if self._residual_assembler is None:
            return np.inf
        else:
            pass

        if self._full_params is None or self._x_prev is None or self._dx_prev is None or self._x_prev2 is None:
            return np.inf
        else:
            pass

        self._residual_assembler.evaluate(
            trial_x,
            self._full_params,
            self._x_prev,
            self._dx_prev,
            self._h_eff,
            self._x_prev2,
            out_res,
        )
        return _max_abs_value(out_res)


class StructuralCompiledEquationGroup:
    """
    Structural group of equations that share the same vectorized template.
    """

    __slots__ = ["_index_matrix", "_row_indices", "_template_eq", "_template_vars"]

    def __init__(self) -> None:
        """
        Create an empty structural group.

        :return: None
        :rtype: None
        """
        self._index_matrix: List[List[int]] = list()
        self._row_indices: List[int] = list()
        self._template_eq: Expr | None = None
        self._template_vars: List[Var] | None = None

    def set_template(self, template_eq: Expr, template_vars: List[Var]) -> None:
        """
        Store the canonical template of the group.

        :param template_eq: Canonical structural equation.
        :type template_eq: Expr
        :param template_vars: Ordered runtime variables of the template.
        :type template_vars: List[Var]
        :return: None
        :rtype: None
        """
        self._template_eq = template_eq
        self._template_vars = list(template_vars)

    def add_indices(self, variable_indices: List[int], row_index: int) -> None:
        """
        Append one grouped equation instance.

        :param variable_indices: Runtime indices used by this equation instance.
        :type variable_indices: List[int]
        :param row_index: Global residual row index.
        :type row_index: int
        :return: None
        :rtype: None
        """
        self._index_matrix.append(list(variable_indices))
        self._row_indices.append(row_index)

    def get_index_matrix(self) -> List[List[int]]:
        """
        Return the grouped runtime index matrix.

        :return: Grouped runtime index matrix.
        :rtype: List[List[int]]
        """
        return self._index_matrix

    def get_row_indices(self) -> List[int]:
        """
        Return the residual rows covered by the group.

        :return: Residual row indices.
        :rtype: List[int]
        """
        return self._row_indices

    def get_template_eq(self) -> Expr | None:
        """
        Return the template equation.

        :return: Template equation or ``None``.
        :rtype: Expr | None
        """
        return self._template_eq

    def get_template_vars(self) -> List[Var] | None:
        """
        Return the template runtime variables.

        :return: Ordered template runtime variables or ``None``.
        :rtype: List[Var] | None
        """
        return self._template_vars


class StructuralCompiledVectorKernel:
    """
    Typed container for one vectorized residual kernel.
    """

    __slots__ = ["_kernel", "_indices", "_target_rows", "_row_count"]

    def __init__(self, kernel: Callable[..., Any], indices: Int32Matrix, target_rows: Int32Vector) -> None:
        """
        Create the vectorized kernel container.

        :param kernel: Compiled eager kernel.
        :type kernel: Callable[..., Any]
        :param indices: Runtime gather matrix.
        :type indices: Int32Matrix
        :param target_rows: Residual rows written by the kernel.
        :type target_rows: Int32Vector
        :return: None
        :rtype: None
        """
        self._kernel = kernel
        self._indices = indices
        self._target_rows = target_rows
        self._row_count = int(target_rows.shape[0])

    def get_kernel(self) -> Callable[..., Any]:
        """
        Return the compiled kernel.

        :return: Compiled kernel.
        :rtype: Callable[..., Any]
        """
        return self._kernel

    def get_indices(self) -> Int32Matrix:
        """
        Return the runtime gather matrix.

        :return: Runtime gather matrix.
        :rtype: Int32Matrix
        """
        return self._indices

    def get_target_rows(self) -> Int32Vector:
        """
        Return the residual target rows.

        :return: Residual target rows.
        :rtype: Int32Vector
        """
        return self._target_rows

    def get_row_count(self) -> int:
        """
        Return the number of rows emitted by the kernel.

        :return: Number of grouped rows.
        :rtype: int
        """
        return self._row_count


class StructuralCompiledResidualDispatcher:
    """
    Residual dispatcher that orchestrates compiled group kernels explicitly.

    The structural group kernels are already eagerly compiled with Numba. Keeping
    the final scatter loop in Python avoids fragile JIT/global binding behavior in
    the dispatcher layer and mirrors the residual assembly strategy used by the
    vectorized solver.
    """

    __slots__ = ["_kernel_specs"]

    def __init__(self, kernel_specs: List[StructuralCompiledVectorKernel]) -> None:
        self._kernel_specs = kernel_specs

    def __call__(
            self,
            states: Vec,
            params: Vec,
            history: Vec,
            d_history: Vec,
            h: float,
            history2: Vec,
            data_out: Vec,
            work_buffers: Float64Matrix,
    ) -> None:
        data_out[:] = 0.0

        kernel_index: int = 0
        while kernel_index < len(self._kernel_specs):
            kernel_spec: StructuralCompiledVectorKernel = self._kernel_specs[kernel_index]
            row_count: int = kernel_spec.get_row_count()
            local_out: Float64Vector = work_buffers[kernel_index, :row_count]

            kernel_spec.get_kernel()(
                states,
                params,
                history,
                d_history,
                h,
                kernel_spec.get_indices(),
                local_out,
                history2,
            )

            data_out[kernel_spec.get_target_rows()] = local_out[:row_count]
            kernel_index += 1


def _compile_master_jacobian_kernel(
        ad_kernel: Callable[..., Any],
        n_colors: int,
        cache_token: str,
) -> Callable[..., Any]:
    """
    Build the eager sparse Jacobian dispatcher.

    :param ad_kernel: Generic AD kernel reused across colors.
    :type ad_kernel: Callable[..., Any]
    :param n_colors: Number of graph colors.
    :type n_colors: int
    :return: Compiled master Jacobian dispatcher.
    :rtype: Callable[..., Any]
    """
    _unused = cache_token

    return StructuralCompiledMasterJacobianDispatcher(ad_kernel=ad_kernel, n_colors=n_colors)


class StructuralCompiledMasterJacobianDispatcher:
    """
    Callable dispatcher that evaluates structural AD colors into CSC storage.
    """

    __slots__ = ("_ad_kernel", "_n_colors")

    def __init__(self, ad_kernel: Callable[..., Any], n_colors: int) -> None:
        """
        Store the generic AD kernel and the number of graph colors.

        :param ad_kernel: Generic AD kernel reused across colors.
        :param n_colors: Number of graph colors.
        :return: None.
        """
        self._ad_kernel: Callable[..., Any] = ad_kernel
        self._n_colors: int = n_colors

    def __call__(self,
                 states: Vec,
                 seed_matrix: Float64Matrix,
                 params: Vec,
                 history: Vec,
                 d_history: Vec,
                 h: float,
                 history2: Vec,
                 data: Vec,
                 color_ptr: Int32Vector,
                 col_ptr: Int32Vector,
                 row_idx: Int32Vector,
                 data_idx: Int32Vector,
                 work_jvp: Float64Matrix) -> None:
        """
        Evaluate one full structural AD sweep and scatter it into CSC storage.

        :param states: Current Newton iterate.
        :param seed_matrix: Coloring seed matrix.
        :param params: Full parameter vector.
        :param history: Previous accepted state.
        :param d_history: Previous derivative vector.
        :param h: Effective time step.
        :param history2: Secondary history vector.
        :param data: CSC numeric data buffer.
        :param color_ptr: Color-to-column pointer array.
        :param col_ptr: Column-to-scatter pointer array.
        :param row_idx: Row indices used by the scatter map.
        :param data_idx: CSC data positions used by the scatter map.
        :param work_jvp: Reusable JVP work buffer.
        :return: None.
        """
        color_index: int = 0

        while color_index < self._n_colors:
            local_jvp: Float64Vector = work_jvp[color_index]
            self._ad_kernel(states, seed_matrix[color_index], params, history, d_history, h, local_jvp, history2)
            _scatter_color_jvp_to_csc_data(local_jvp, data, color_ptr, col_ptr, row_idx, data_idx, color_index)
            color_index += 1


class StructuralCompiledResidualAssembler:
    """
    Residual dispatcher that reuses preallocated grouped work buffers.
    """

    __slots__ = ["_kernel_specs", "_dispatcher", "_work_buffer", "_build_stats"]

    def __init__(self, kernel_specs: List[StructuralCompiledVectorKernel], cache_token: str) -> None:
        """
        Create the residual assembler.

        :param kernel_specs: Vectorized residual kernels.
        :type kernel_specs: List[StructuralCompiledVectorKernel]
        :return: None
        :rtype: None
        """
        t_start: float = time.perf_counter()
        self._kernel_specs: List[StructuralCompiledVectorKernel] = kernel_specs
        _unused_cache_token: str = cache_token

        t_dispatcher_start: float = time.perf_counter()
        self._dispatcher: Callable[..., Any] = StructuralCompiledResidualDispatcher(kernel_specs)
        dispatcher_build_s: float = time.perf_counter() - t_dispatcher_start

        max_kernel_size: int = 0
        kernel_spec: StructuralCompiledVectorKernel
        for kernel_spec in kernel_specs:
            if kernel_spec.get_row_count() > max_kernel_size:
                max_kernel_size = kernel_spec.get_row_count()
            else:
                pass

        t_buffer_start: float = time.perf_counter()

        # The work matrix has one row per structural group and enough columns for the largest group.
        self._work_buffer: Float64Matrix = np.zeros((len(kernel_specs), max_kernel_size), dtype=np.float64)

        buffer_alloc_s: float = time.perf_counter() - t_buffer_start
        self._build_stats: Dict[str, float] = {
            "dispatcher_build_s": dispatcher_build_s,
            "buffer_alloc_s": buffer_alloc_s,
            "total_s": time.perf_counter() - t_start,
        }

    def evaluate(
            self,
            states: Vec,
            params: Vec,
            history: Vec,
            d_history: Vec,
            h: float,
            history2: Vec,
            data_out: Vec,
    ) -> None:
        """
        Evaluate the grouped residual system in place.

        :param states: Current Newton iterate.
        :type states: Vec
        :param params: Full parameter vector.
        :type params: Vec
        :param history: Previous state vector.
        :type history: Vec
        :param d_history: Previous differential vector.
        :type d_history: Vec
        :param h: Local time step.
        :type h: float
        :param history2: Secondary history vector.
        :type history2: Vec
        :param data_out: Residual output buffer.
        :type data_out: Vec
        :return: None
        :rtype: None
        """
        self._dispatcher(states, params, history, d_history, h, history2, data_out, self._work_buffer)

    def get_work_buffer(self) -> Float64Matrix:
        """
        Return the grouped work buffer.

        :return: Grouped work buffer.
        :rtype: Float64Matrix
        """
        return self._work_buffer

    def get_build_stats(self) -> Dict[str, float]:
        """
        Return residual assembler setup timings.

        :return: Residual assembler build timings.
        :rtype: Dict[str, float]
        """
        return dict(self._build_stats)


class StructuralCompiledDirectResidualAssembler:
    """
    Residual assembler backed by one monolithic in-place kernel.
    """

    __slots__ = ["_kernel", "_equations", "_variables", "_parameters", "_method", "_debug_info", "_build_stats"]

    def __init__(self,
                 kernel: Callable[..., Any],
                 equations: List[Expr],
                 variables: List[Var],
                 parameters: List[Var],
                 method: DynamicIntegrationMethod,
                 debug_info: List[Dict[str, Any]] | None) -> None:
        """
        Create the direct residual assembler.

        :param kernel: Residual kernel.
        :type kernel: Callable[..., Any]
        :param equations: Full residual equation list.
        :type equations: List[Expr]
        :param variables: Ordered runtime variables.
        :type variables: List[Var]
        :param parameters: Ordered parameter list.
        :type parameters: List[Var]
        :param method: Implicit integration method.
        :type method: DynamicIntegrationMethod
        :param debug_info: Residual metadata aligned with the kernel ordering.
        :type debug_info: List[Dict[str, Any]] | None
        :return: None
        :rtype: None
        """
        self._kernel = kernel
        self._equations = equations
        self._variables = variables
        self._parameters = parameters
        self._method = method
        self._debug_info = debug_info
        self._build_stats = {
            "dispatcher_build_s": 0.0,
            "buffer_alloc_s": 0.0,
            "total_s": 0.0,
        }

    def evaluate(
            self,
            states: Vec,
            params: Vec,
            history: Vec,
            d_history: Vec,
            h: float,
            history2: Vec,
            data_out: Vec,
    ) -> None:
        try:
            self._kernel(states, params, history, d_history, h, data_out, history2)
        except ZeroDivisionError as exc:
            failed_index: int | None = _locate_failing_residual_with_single_equation_kernels(
                equations=self._equations,
                variables=self._variables,
                parameters=self._parameters,
                method=self._method,
                states=states,
                params=params,
                history=history,
                d_history=d_history,
                h=h,
                history2=history2,
            )
            raise ZeroDivisionError(
                _format_structural_residual_zero_division_message(failed_index, self._debug_info)
            ) from exc

    def get_work_buffer(self) -> None:
        return None

    def get_build_stats(self) -> Dict[str, float]:
        return dict(self._build_stats)


class StructuralCompiledSparseADJacobian:
    """
    Sparse structural AD Jacobian that writes directly into CSC storage.
    """

    __slots__ = [
        "_equations",
        "_variables",
        "_parameters",
        "_method",
        "_dtype",
        "_n_rows",
        "_n_cols",
        "_column_rows",
        "_jacobian_matrix",
        "_colors",
        "_n_colors",
        "_color_groups",
        "_color_ptr",
        "_col_ptr",
        "_row_idx",
        "_data_idx",
        "_compiler",
        "_ad_kernel",
        "_master_dispatcher",
        "_seed_matrix",
        "_jvp_work_buffer",
        "_data_buffer",
        "_build_stats",
    ]

    def __init__(
            self,
            equations: List[Expr],
            variables: List[Var],
            parameters: List[Var],
            method: DynamicIntegrationMethod,
            dtype: Any = np.float64,
            use_cse: bool = True,
            eager_machine_code: bool = True,
            cache_token: str = "default",
    ) -> None:
        """
        Create the sparse AD Jacobian evaluator.

        :param equations: Full residual equations.
        :type equations: List[Expr]
        :param variables: Runtime variables of the DAE system.
        :type variables: List[Var]
        :param parameters: Full parameter list.
        :type parameters: List[Var]
        :param method: Implicit integration method.
        :type method: DynamicIntegrationMethod
        :param dtype: Numeric dtype of the Jacobian storage.
        :type dtype: Any
        :param use_cse: Whether color kernels should emit CSE temporaries.
        :type use_cse: bool
        :return: None
        :rtype: None
        """
        t_start: float = time.perf_counter()

        self._equations = equations
        self._variables = variables
        self._parameters = parameters
        self._method = method
        self._dtype = dtype
        self._n_rows = len(equations)
        self._n_cols = len(variables)

        # The sparsity pattern is extracted once from the symbolic graph and then reused forever.
        t_column_rows_start: float = time.perf_counter()
        self._column_rows = self._build_column_rows()
        column_rows_s: float = time.perf_counter() - t_column_rows_start

        t_csc_start: float = time.perf_counter()
        self._jacobian_matrix, self._data_buffer = self._build_csc_matrix()
        csc_shell_s: float = time.perf_counter() - t_csc_start

        t_coloring_start: float = time.perf_counter()
        self._colors, self._n_colors, self._color_groups = _greedy_color_columns(self._column_rows, self._n_rows)
        coloring_s: float = time.perf_counter() - t_coloring_start

        t_scatter_start: float = time.perf_counter()
        self._color_ptr, self._col_ptr, self._row_idx, self._data_idx = self._build_scatter_map()
        scatter_map_s: float = time.perf_counter() - t_scatter_start

        # The eager compiler emits strictly typed kernels that write into caller-owned buffers.
        self._compiler = EagerEquationCompiler(variables=variables, parameters=parameters, method=method)

        t_ad_kernels_start: float = time.perf_counter()
        self._ad_kernel = self._build_ad_kernel(use_cse, eager_machine_code)
        ad_kernels_s: float = time.perf_counter() - t_ad_kernels_start

        t_dispatcher_start: float = time.perf_counter()
        self._master_dispatcher = _compile_master_jacobian_kernel(self._ad_kernel, self._n_colors, cache_token)
        dispatcher_build_s: float = time.perf_counter() - t_dispatcher_start

        self._seed_matrix = np.zeros((self._n_colors, self._n_cols), dtype=self._dtype)
        color_index = 0
        while color_index < self._n_colors:
            for column_index in self._color_groups[color_index]:
                self._seed_matrix[color_index, column_index] = 1.0
            color_index += 1

        # One JVP row per color is enough because colors are executed sequentially.
        self._jvp_work_buffer = np.zeros((self._n_colors, self._n_rows), dtype=self._dtype)
        self._build_stats: Dict[str, float] = {
            "column_rows_s": column_rows_s,
            "csc_shell_s": csc_shell_s,
            "coloring_s": coloring_s,
            "scatter_map_s": scatter_map_s,
            "ad_kernels_s": ad_kernels_s,
            "dispatcher_build_s": dispatcher_build_s,
            "total_s": time.perf_counter() - t_start,
        }

    def _build_column_rows(self) -> List[List[int]]:
        """
        Build the symbolic sparsity pattern column by column.

        :return: Row indices present in each sparse column.
        :rtype: List[List[int]]
        """
        variable_index_by_uid: Dict[int, int] = dict()
        column_rows: List[List[int]] = list()
        row_index: int = 0
        variable_index: int = 0

        while variable_index < self._n_cols:
            variable_obj: Var = self._variables[variable_index]
            variable_index_by_uid[variable_obj.uid] = variable_index
            column_rows.append(list())
            variable_index += 1

        while row_index < self._n_rows:
            equation: Expr = self._equations[row_index]
            stack: List[Expr] = list()
            visited_nodes: Set[int] = set()
            dependent_uids: Set[int] = set()

            stack.append(equation)

            while len(stack) > 0:
                node: Expr = stack.pop()
                node_identifier: int = id(node)

                if node_identifier in visited_nodes:
                    pass
                else:
                    visited_nodes.add(node_identifier)

                    if isinstance(node, Var):
                        dependent_uids.add(node.uid)

                        if node.base_var is None:
                            pass
                        else:
                            dependent_uids.add(node.base_var.uid)
                    elif isinstance(node, BinOp):
                        stack.append(node.left)
                        stack.append(node.right)
                    elif isinstance(node, UnOp):
                        stack.append(node.operand)
                    elif isinstance(node, Func):
                        stack.append(node.arg)
                    else:
                        pass

            dependent_uid: int
            for dependent_uid in dependent_uids:
                column_index: int | None = variable_index_by_uid.get(dependent_uid, None)

                if column_index is None:
                    pass
                else:
                    column_rows[column_index].append(row_index)

            row_index += 1

        column_index = 0
        while column_index < self._n_cols:
            column_rows[column_index] = sorted(set(column_rows[column_index]))
            column_index += 1

        return column_rows

    def _build_csc_matrix(self) -> Tuple[csc_matrix, Vec]:
        """
        Build the reusable CSC matrix shell and numeric data buffer.

        :return: CSC matrix shell and numeric data buffer.
        :rtype: Tuple[csc_matrix, Vec]
        """
        indptr: Int32Vector = np.zeros(self._n_cols + 1, dtype=np.int32)
        column_index: int = 0
        nnz: int = 0

        while column_index < self._n_cols:
            nnz += len(self._column_rows[column_index])
            indptr[column_index + 1] = nnz
            column_index += 1

        indices: Int32Vector = np.empty(nnz, dtype=np.int32)
        data: Vec = np.zeros(nnz, dtype=self._dtype)
        data_position: int = 0

        column_index = 0
        while column_index < self._n_cols:
            local_index: int = 0
            rows_in_column: List[int] = self._column_rows[column_index]

            while local_index < len(rows_in_column):
                indices[data_position] = rows_in_column[local_index]
                data_position += 1
                local_index += 1

            column_index += 1

        matrix: csc_matrix = csc_matrix((data, indices, indptr), shape=(self._n_rows, self._n_cols))
        return matrix, matrix.data

    def _build_scatter_map(self) -> Tuple[Int32Vector, Int32Vector, Int32Vector, Int32Vector]:
        """
        Precompute the CSC scatter topology for colored JVPs.

        :return: ``color_ptr``, ``col_ptr``, ``row_idx`` and ``data_idx`` arrays.
        :rtype: Tuple[Int32Vector, Int32Vector, Int32Vector, Int32Vector]
        """
        color_cols: List[int] = list()
        color_ptr: Int32Vector = np.zeros(self._n_colors + 1, dtype=np.int32)
        color_index: int = 0

        while color_index < self._n_colors:
            color_ptr[color_index] = len(color_cols)
            group_columns: List[int] = self._color_groups[color_index]
            group_position: int = 0

            while group_position < len(group_columns):
                color_cols.append(group_columns[group_position])
                group_position += 1

            color_index += 1

        color_ptr[self._n_colors] = len(color_cols)

        col_ptr: Int32Vector = np.zeros(len(color_cols) + 1, dtype=np.int32)
        total_map: int = 0
        color_column_index: int = 0

        while color_column_index < len(color_cols):
            total_map += len(self._column_rows[color_cols[color_column_index]])
            col_ptr[color_column_index + 1] = total_map
            color_column_index += 1

        row_idx: Int32Vector = np.empty(total_map, dtype=np.int32)
        data_idx: Int32Vector = np.empty(total_map, dtype=np.int32)
        position: int = 0
        indptr_array: Int32Vector = self._jacobian_matrix.indptr.astype(np.int32, copy=False)

        color_column_index = 0
        while color_column_index < len(color_cols):
            column_index: int = color_cols[color_column_index]
            base_position: int = int(indptr_array[column_index])
            rows_in_column: List[int] = self._column_rows[column_index]
            local_index: int = 0

            while local_index < len(rows_in_column):
                row_idx[position] = rows_in_column[local_index]
                data_idx[position] = base_position + local_index
                position += 1
                local_index += 1

            color_column_index += 1

        return color_ptr, col_ptr, row_idx, data_idx

    def _build_ad_kernel(self, use_cse: bool, eager_machine_code: bool) -> Callable[..., Any]:
        """
        Compile one generic eager AD kernel reused for every graph color.

        :param use_cse: Whether color kernels should emit CSE temporaries.
        :type use_cse: bool
        :return: Compiled generic AD kernel.
        :rtype: Callable[..., Any]
        """
        kernel_name: str = f"structural_compiled_ad_generic_{self._method.name}_{self._n_rows}_{self._n_cols}"
        py_func, signature_tpe = self._compiler.compile_ad_kernel(
            equations=self._equations,
            func_name=kernel_name,
            use_cse=use_cse,
            active_indices=None,
        )
        if eager_machine_code:
            return _safe_njit(py_func, signature_tpe=signature_tpe, fastmath=True, cache=True)
        else:
            return py_func

    def evaluate(
            self,
            states: Vec,
            params: Vec,
            history: Vec,
            d_history: Vec,
            h: float,
            history2: Vec,
    ) -> csc_matrix:
        """
        Evaluate the sparse Jacobian into the reusable CSC storage.

        :param states: Current Newton iterate.
        :type states: Vec
        :param params: Full parameter vector.
        :type params: Vec
        :param history: Previous state vector.
        :type history: Vec
        :param d_history: Previous differential vector.
        :type d_history: Vec
        :param h: Local time step.
        :type h: float
        :param history2: Secondary history vector.
        :type history2: Vec
        :return: Reused CSC Jacobian matrix.
        :rtype: csc_matrix
        """
        self._master_dispatcher(
            states,
            self._seed_matrix,
            params,
            history,
            d_history,
            h,
            history2,
            self._data_buffer,
            self._color_ptr,
            self._col_ptr,
            self._row_idx,
            self._data_idx,
            self._jvp_work_buffer,
        )
        return self._jacobian_matrix

    def get_data_buffer(self) -> Vec:
        """
        Return the reusable CSC numeric buffer.

        :return: CSC numeric buffer.
        :rtype: Vec
        """
        return self._data_buffer

    def get_matrix(self) -> csc_matrix:
        """
        Return the reusable CSC matrix shell.

        :return: CSC Jacobian matrix.
        :rtype: csc_matrix
        """
        return self._jacobian_matrix

    def get_build_stats(self) -> Dict[str, float]:
        """
        Return sparse Jacobian build timings.

        :return: Sparse Jacobian build timings.
        :rtype: Dict[str, float]
        """
        return dict(self._build_stats)


class StructuralCompiledSparseFactorizationManager:
    """
    Sparse linear-solve manager for ``StructuralCompiledSolver``.

    The manager keeps the current numeric factorization alive across time steps,
    caches one column ordering once it has been discovered, and reuses
    persistent numeric buffers so the solver hot loop does not rebuild sparse
    matrix shells.
    """

    __slots__ = ["_base_matrix", "_backend", "_analysis_handle", "_cached_handle", "_solution_buffer", "_stats"]

    def __init__(self,
                 base_matrix: csc_matrix,
                 base_data: Vec,
                 backend_provider: SparseLinearSolverBackendProvider | None = None) -> None:
        """
        Create the sparse factorization manager.

        :param base_matrix: Reusable Jacobian CSC shell in original variable order.
        :type base_matrix: csc_matrix
        :param base_data: Reusable CSC numeric buffer of ``base_matrix``.
        :type base_data: Vec
        :return: None
        :rtype: None
        """
        n_cols: int = int(base_matrix.shape[1])
        resolved_provider: SparseLinearSolverBackendProvider

        if backend_provider is None:
            resolved_provider = SuperLUSparseBackendProvider()
        else:
            resolved_provider = backend_provider

        self._base_matrix: csc_matrix = base_matrix
        self._backend: SparseLinearSolverBackend = resolved_provider.create_backend(base_matrix, base_data)
        self._analysis_handle: Any | None = None
        self._cached_handle: SparseLinearFactorizationHandle | None = None
        self._solution_buffer: Vec = np.zeros(n_cols, dtype=np.float64)
        self._stats: Dict[str, float] = {
            "numeric_factorizations": 0.0,
            "invalidations": 0.0,
            "solve_calls": 0.0,
            "fallback_solves": 0.0,
        }

        if self._backend.supports_symbolic_analysis_reuse():
            self._analysis_handle = self._backend.analyze(base_matrix)
        else:
            self._analysis_handle = None

    def invalidate(self) -> None:
        """
        Drop the current numeric factorization while keeping all persistent shells.

        :return: None
        :rtype: None
        """
        self._cached_handle = None
        self._stats["invalidations"] += 1.0

    def has_factorization(self) -> bool:
        """
        Return whether one numeric factorization is currently cached.

        :return: ``True`` when a factorization is available.
        :rtype: bool
        """
        return self._cached_handle is not None

    def factorize(self) -> SparseLinearFactorizationHandle:
        """
        Factorize the current Jacobian numeric values.

        :return: Active sparse factorization handle.
        :rtype: SparseLinearFactorizationHandle
        """
        self._cached_handle = self._backend.factorize(self._base_matrix, self._analysis_handle)
        self._stats["numeric_factorizations"] += 1.0
        return self._cached_handle

    def solve(self, rhs: Vec) -> Vec:
        """
        Solve the linear system using the current numeric factorization.

        :param rhs: Right-hand side vector.
        :type rhs: Vec
        :return: Solution buffer in original solver order.
        :rtype: Vec
        """
        self._stats["solve_calls"] += 1.0

        if self._cached_handle is None:
            self._solution_buffer[:] = 0.0
        else:
            self._cached_handle.solve_into(rhs, self._solution_buffer)

        return self._solution_buffer

    def solve_fallback(self, rhs: Vec) -> Vec:
        """
        Solve the linear system with an iterative sparse fallback.

        :param rhs: Right-hand side vector.
        :type rhs: Vec
        :return: Solution buffer in original solver order.
        :rtype: Vec
        """
        active_matrix: csc_matrix = self.get_active_matrix()
        raw_solution: Vec = np.asarray(sparse_lsqr_fallback(active_matrix, rhs), dtype=np.float64)
        self._stats["fallback_solves"] += 1.0

        self._solution_buffer[:] = raw_solution

        return self._solution_buffer

    def get_active_matrix(self) -> csc_matrix:
        """
        Return the matrix used by the active numeric factorization path.

        :return: Active sparse matrix.
        :rtype: csc_matrix
        """
        if self._cached_handle is None:
            return self._base_matrix
        else:
            return self._cached_handle.get_active_matrix()

    def get_stats(self) -> Dict[str, float]:
        """
        Return cumulative factorization-manager statistics.

        :return: Cumulative statistics dictionary.
        :rtype: Dict[str, float]
        """
        merged_stats: Dict[str, float] = dict(self._stats)
        backend_stats: Dict[str, float] = self._backend.get_backend_stats()

        for key, value in backend_stats.items():
            merged_stats[key] = float(value)

        return merged_stats


class StructuralCompiledSolver:
    """
    Standalone structural EMT solver with eager kernels and reusable buffers.

    The solver keeps the linear algebra in SciPy, but it removes the Python-side
    allocation churn from residual assembly and sparse Jacobian evaluation.
    """

    __slots__ = [
        "_problem",
        "_t0",
        "_t_end",
        "_h",
        "_method",
        "_pred_method",
        "_dense_threshold",
        "_verbose",
        "_warmup_policy",
        "_state_vars",
        "_algebraic_vars",
        "_diff_vars",
        "_state_eqs",
        "_algebraic_eqs",
        "_sorted_vars",
        "_event_parameters",
        "_constant_parameters",
        "_parameter_values",
        "_uid2idx_vars",
        "_n_state",
        "_n_vars",
        "_n_diff",
        "_n_event_parameters",
        "_n_constant_parameters",
        "_residual_assembler",
        "_jacobian_evaluator",
        "_residual_buffer",
        "_linear_rhs_buffer",
        "_jacobian_data_buffer",
        "_static_parameter_buffer",
        "_full_parameter_buffer",
        "_last_factorization_parameter_snapshot",
        "_has_factorization_parameter_snapshot",
        "_delta_buffer",
        "_trial_state_buffer",
        "_trial_residual_buffer",
        "_trial_residual_evaluator",
        "_vectorized_ready",
        "_backend_warmup_done",
        "_last_macro_newton_iterations",
        "_last_sim_loop_time",
        "_last_runtime_stats",
        "_predictor",
        "_backend_build_stats",
        "_newton_max_iter",
        "_newton_tolerance",
        "_newton_diag_config",
        "_sparse_factorization_manager",
        "_sparse_solver_backend_provider",
        "_cancel_checker",
        "_progress_signal",
    ]

    def __init__(
            self,
            problem: EmtProblemTemplate,
            t0: float,
            t_end: float,
            h: float,
            method: DynamicIntegrationMethod = DynamicIntegrationMethod.DaeTrapezoidal,
            pred_method: DynamicIntegrationMethod | None = None,
            dense_threshold: int = 100,
            verbose: bool = False,
            newton_max_iter: int = 15,
            auto_build: bool = True,
            warmup_policy: StructuralCompiledWarmupPolicy = StructuralCompiledWarmupPolicy.Adaptive,
            sparse_solver_backend_provider: SparseLinearSolverBackendProvider | None = None,
            newton_diag_config: NewtonDiagnosticsConfig | None = None,
            progress_signal: DummySignal | None = None,
            cancel_checker: Callable[[], bool] | None = None,
            newton_tolerance: float = 1.0e-6,
    ) -> None:
        """
        Create the structural compiled EMT solver.

        :param problem: EMT problem wrapper.
        :type problem: EmtProblemTemplate
        :param t0: Initial time.
        :type t0: float
        :param t_end: End time.
        :type t_end: float
        :param h: Nominal time step.
        :type h: float
        :param method: Implicit integration method.
        :type method: DynamicIntegrationMethod
        :param pred_method: Predictor method used on the first trapezoidal step.
        :type pred_method: DynamicIntegrationMethod | None
        :param dense_threshold: Threshold to switch between dense and sparse linear algebra.
        :type dense_threshold: int
        :param verbose: Whether to print build and simulation timings.
        :type verbose: bool
        :param newton_max_iter: Maximum Newton iterations per local EMT substep.
        :type newton_max_iter: int
        :param newton_tolerance: Absolute infinity-norm tolerance for Newton residual convergence.
        :type newton_tolerance: float
        :param auto_build: Whether to build the vectorized backend during construction.
        :type auto_build: bool
        :param warmup_policy: Warmup policy used during backend build.
        :type warmup_policy: StructuralCompiledWarmupPolicy
        :param sparse_solver_backend_provider: Sparse linear solver backend provider.
        :type sparse_solver_backend_provider: SparseLinearSolverBackendProvider | None
        :param progress_signal: Optional progress signal updated during the simulation loop.
        :type progress_signal: DummySignal | None
        :return: None
        :rtype: None
        """
        self._problem = problem
        self._t0 = t0
        self._t_end = t_end
        self._h = h
        self._method = method
        self._pred_method = pred_method
        self._dense_threshold = dense_threshold
        self._verbose = verbose
        self._newton_max_iter: int = int(newton_max_iter)
        self._newton_tolerance: float = float(newton_tolerance)
        if not np.isfinite(self._newton_tolerance) or self._newton_tolerance <= 0.0:
            raise ValueError("newton_tolerance must be finite and greater than zero.")
        self._warmup_policy = warmup_policy
        self._sparse_solver_backend_provider = sparse_solver_backend_provider
        self._newton_diag_config = newton_diag_config or NewtonDiagnosticsConfig(
            compute_dense_cond=False,
            enable_fallback=False,
            enable_index1_check=False,
            enable_backtracking=False,
        )

        # The solver captures the problem structure once so all hot loops use local buffers only.
        self._state_vars = self._problem.get_state_vars()
        self._algebraic_vars = self._problem.get_algebraic_vars()
        self._diff_vars = self._problem.get_diff_vars()
        self._state_eqs = self._problem.get_state_eqs()
        self._algebraic_eqs = self._problem.get_algebraic_eqs()
        self._sorted_vars = list()
        self._sorted_vars.extend(self._state_vars)
        self._sorted_vars.extend(self._algebraic_vars)

        self._event_parameters = self._problem.get_variable_parameters()
        self._constant_parameters = self._problem.get_constant_parameters()
        self._parameter_values = self._problem.get_parameters_values()

        self._uid2idx_vars = dict()
        self._n_state = len(self._state_vars)
        self._n_vars = len(self._sorted_vars)
        self._n_diff = len(self._diff_vars)
        self._n_event_parameters = len(self._event_parameters)
        self._n_constant_parameters = len(self._constant_parameters)

        variable_index: int = 0
        while variable_index < self._n_vars:
            variable_obj: Var = self._sorted_vars[variable_index]
            self._uid2idx_vars[variable_obj.uid] = variable_index
            variable_index += 1

        # The residual and right-hand-side buffers are persistent across all Newton iterations.
        self._residual_buffer = np.zeros(self._n_vars, dtype=np.float64)
        self._linear_rhs_buffer = np.zeros(self._n_vars, dtype=np.float64)
        self._jacobian_data_buffer = np.zeros(0, dtype=np.float64)

        # Constant parameters are flattened once because they never change during simulation.
        self._static_parameter_buffer = np.zeros(self._n_constant_parameters, dtype=np.float64)
        variable_index = 0
        while variable_index < self._n_constant_parameters:
            self._static_parameter_buffer[variable_index] = float(self._parameter_values[variable_index].value)
            variable_index += 1

        # The full parameter vector is reused and refreshed in place at every local substep.
        self._full_parameter_buffer = np.zeros(
            self._n_event_parameters + self._n_constant_parameters,
            dtype=np.float64,
        )
        self._last_factorization_parameter_snapshot = np.zeros(
            self._n_event_parameters + self._n_constant_parameters,
            dtype=np.float64,
        )
        self._has_factorization_parameter_snapshot = False
        self._delta_buffer = np.zeros(self._n_vars, dtype=np.float64)
        self._trial_state_buffer = np.zeros(self._n_vars, dtype=np.float64)
        self._trial_residual_buffer = np.zeros(self._n_vars, dtype=np.float64)
        self._trial_residual_evaluator = StructuralCompiledResidualTrialEvaluator()

        self._residual_assembler: StructuralCompiledResidualAssembler | None = None
        self._jacobian_evaluator: StructuralCompiledSparseADJacobian | None = None
        self._sparse_factorization_manager: StructuralCompiledSparseFactorizationManager | None = None
        self._vectorized_ready = False
        self._backend_warmup_done = False
        self._last_macro_newton_iterations = 0
        self._last_sim_loop_time = 0.0
        self._last_runtime_stats: Dict[str, float] = dict()
        self._predictor = StructuralCompiledPredictor(self._n_state)
        self._backend_build_stats: Dict[str, float] = dict()
        self._progress_signal: DummySignal | None = progress_signal
        self._cancel_checker = cancel_checker

        if auto_build:
            self._build_vectorized_backend(method)
        else:
            pass

    def _build_vectorized_backend(self, method: DynamicIntegrationMethod) -> None:
        """
        Analyze the symbolic structure and build the eager numerical backend.

        :param method: Integration method used by the generated kernels.
        :type method: DynamicIntegrationMethod
        :return: None
        :rtype: None
        """
        t_start: float = time.perf_counter()
        groups: Dict[str, StructuralCompiledEquationGroup] = dict()
        runtime_uids: Set[int] = set(self._uid2idx_vars.keys())
        parameter_uids: Set[int] = _build_parameter_uid_set(self._event_parameters, self._constant_parameters)
        full_eqs: List[Expr] = _build_full_residual_equations(
            self._state_vars,
            self._state_eqs,
            self._algebraic_eqs,
        )
        equation_index: int = 0

        t_grouping_start: float = time.perf_counter()

        # Structural grouping uses the full canonical string as the lookup key to avoid hash collisions.
        while equation_index < len(full_eqs):
            equation: Expr = full_eqs[equation_index]
            signature_str: str
            runtime_vars: List[Var]
            group: StructuralCompiledEquationGroup
            variable_indices: List[int] = list()
            runtime_var_index: int = 0

            signature_str, runtime_vars = canonicalize_expression(equation, runtime_uids, parameter_uids)

            if signature_str in groups:
                group = groups[signature_str]
            else:
                group = StructuralCompiledEquationGroup()
                groups[signature_str] = group

            while runtime_var_index < len(runtime_vars):
                runtime_uid: int = _get_runtime_uid(runtime_vars[runtime_var_index])
                mapped_index: int | None = self._uid2idx_vars.get(runtime_uid, None)

                if mapped_index is None:
                    raise RuntimeError(f"Missing runtime variable mapping for uid={runtime_uid}")
                else:
                    variable_indices.append(mapped_index)

                runtime_var_index += 1

            if group.get_template_eq() is None:
                group.set_template(equation, runtime_vars)
            else:
                template_vars: List[Var] | None = group.get_template_vars()

                if template_vars is None:
                    raise RuntimeError("Internal structural group without template variables")
                else:
                    if len(template_vars) == len(variable_indices):
                        pass
                    else:
                        raise RuntimeError("Inconsistent runtime variable count inside structural group")

            group.add_indices(variable_indices, equation_index)
            equation_index += 1

        grouping_s: float = time.perf_counter() - t_grouping_start

        if self._verbose:
            print(f"--- [STRUCT-COMPILED] Detected {len(groups)} structural groups ---", flush=True)
        else:
            pass

        all_parameters: List[Var] = list()
        all_parameters.extend(self._event_parameters)
        all_parameters.extend(self._constant_parameters)
        eager_compiler: EagerEquationCompiler = EagerEquationCompiler(
            variables=self._sorted_vars,
            parameters=all_parameters,
            method=method,
        )

        # Group kernels are compiled in deterministic order so disk cache keys remain stable.
        group_keys: List[str] = sorted(list(groups.keys()))
        backend_cache_token: str = _build_backend_cache_token(method, len(full_eqs), self._n_vars, group_keys)
        avg_group_size: float = float(len(full_eqs) / max(len(group_keys), 1))
        use_direct_residual: bool = len(group_keys) >= 20 and avg_group_size <= 3.0
        estimated_steps: int = int(max(1.0, round((self._t_end - self._t0) / self._h)))
        full_warmup_enabled: bool = _should_run_full_backend_warmup(
            self._warmup_policy,
            self._n_vars,
            estimated_steps,
            use_direct_residual,
        )
        residual_use_cse: bool = True
        jacobian_use_cse: bool = True
        # Short runs should avoid paying the full Numba compilation cost up front. In those cases the
        # generated Python kernels are fast enough and keep the structural backend usable.
        eager_machine_code: bool = full_warmup_enabled
        kernel_specs: List[StructuralCompiledVectorKernel] = list()
        group_key_index: int = 0

        if self._verbose:
            print(
                f"--- [STRUCT-COMPILED] Grouping ready in {grouping_s:.4f}s | "
                f"n_vars={self._n_vars} | n_eqs={len(full_eqs)} | "
                f"direct_residual={use_direct_residual} | warmup={self._warmup_policy.value} ---",
                flush=True,
            )
        else:
            pass

        t_vec_kernel_compile_start: float = time.perf_counter()

        if use_direct_residual:
            direct_name: str = f"structural_compiled_residual_{backend_cache_token}"
            py_func, signature_tpe = eager_compiler.compile(
                equations=full_eqs,
                func_name=direct_name,
                use_cse=residual_use_cse,
                offset=0,
                inplace=True,
            )
            if eager_machine_code:
                compiled_residual = _safe_njit(py_func, signature_tpe=signature_tpe, fastmath=True, cache=True)
            else:
                compiled_residual = py_func
        else:
            while group_key_index < len(group_keys):
                group_key: str = group_keys[group_key_index]
                group: StructuralCompiledEquationGroup = groups[group_key]
                template_eq: Expr | None = group.get_template_eq()
                template_vars: List[Var] | None = group.get_template_vars()

                if template_eq is None or template_vars is None:
                    raise RuntimeError("Invalid structural group without template information")
                else:
                    pass

                kernel_name: str = f"structural_compiled_vec_{method.name}_{group_key_index}"
                py_func: Callable[..., Any]
                signature_tpe: Any
                compiled_kernel: Callable[..., Any]
                indices: Int32Matrix = np.asarray(group.get_index_matrix(), dtype=np.int32)
                target_rows: Int32Vector = np.asarray(group.get_row_indices(), dtype=np.int32)

                py_func, signature_tpe = eager_compiler.compile_matrix_kernel(
                    template_eq=template_eq,
                    func_name=kernel_name,
                    template_vars=template_vars,
                )
                if eager_machine_code:
                    compiled_kernel = _safe_njit(py_func, signature_tpe=signature_tpe, fastmath=True, cache=True)
                else:
                    compiled_kernel = py_func
                kernel_specs.append(StructuralCompiledVectorKernel(compiled_kernel, indices, target_rows))

                group_key_index += 1

        vec_kernel_compile_s: float = time.perf_counter() - t_vec_kernel_compile_start

        if self._verbose:
            print(f"--- [STRUCT-COMPILED] Residual kernels ready in {vec_kernel_compile_s:.4f}s ---", flush=True)
        else:
            pass

        # The residual assembler owns the reusable grouped work buffers.
        t_residual_assembler_start: float = time.perf_counter()
        residual_debug_info: List[Dict[str, Any]] = _build_structural_residual_debug_info(
            self._state_vars,
            self._algebraic_vars,
            self._state_eqs,
            self._algebraic_eqs,
            self._uid2idx_vars,
        )

        if use_direct_residual:
            self._residual_assembler = StructuralCompiledDirectResidualAssembler(
                compiled_residual,
                full_eqs,
                self._sorted_vars,
                all_parameters,
                method,
                residual_debug_info,
            )
        else:
            self._residual_assembler = StructuralCompiledResidualAssembler(kernel_specs, backend_cache_token)
        residual_assembler_s: float = time.perf_counter() - t_residual_assembler_start

        if self._verbose:
            print(f"--- [STRUCT-COMPILED] Residual assembler ready in {residual_assembler_s:.4f}s ---", flush=True)
        else:
            pass

        # The sparse Jacobian evaluator owns the reusable CSC numeric storage.
        t_jacobian_evaluator_start: float = time.perf_counter()
        self._jacobian_evaluator = StructuralCompiledSparseADJacobian(
            equations=full_eqs,
            variables=self._sorted_vars,
            parameters=all_parameters,
            method=method,
            dtype=np.float64,
            use_cse=jacobian_use_cse,
            eager_machine_code=eager_machine_code,
            cache_token=backend_cache_token,
        )
        jacobian_evaluator_s: float = time.perf_counter() - t_jacobian_evaluator_start
        self._jacobian_data_buffer = self._jacobian_evaluator.get_data_buffer()
        self._sparse_factorization_manager = StructuralCompiledSparseFactorizationManager(
            self._jacobian_evaluator.get_matrix(),
            self._jacobian_data_buffer,
            self._sparse_solver_backend_provider,
        )

        if self._verbose:
            print(f"--- [STRUCT-COMPILED] Jacobian evaluator ready in {jacobian_evaluator_s:.4f}s ---", flush=True)
        else:
            pass

        # The helper kernels are always warmed because they are tiny and their
        # first-use compilation would otherwise show up as jitter inside the loop.
        helper_warmup_t0: float = time.perf_counter()
        _warmup_compiled_numba_helpers()
        helper_warmup_s: float = time.perf_counter() - helper_warmup_t0

        residual_warmup_s: float = 0.0
        jacobian_warmup_s: float = 0.0

        if full_warmup_enabled:
            warmup_x: Vec = self._problem.get_x0().copy()
            warmup_dx: Vec = self._problem.get_dx0().copy()
            warmup_x2: Vec = warmup_x.copy()
            warmup_runtime_params: Vec = self._problem.event_params_values.copy()
            warmup_full_params: Vec = self._full_parameter_buffer

            # The warmup only needs stable shapes and valid memory layouts, so the
            # raw event parameter vector is enough here and avoids one extra Python
            # parameter-refresh pass during backend build.
            _fill_full_parameter_buffer(warmup_runtime_params, self._static_parameter_buffer, warmup_full_params)

            residual_warmup_t0: float = time.perf_counter()
            self._residual_assembler.evaluate(warmup_x, warmup_full_params, warmup_x, warmup_dx, self._h, warmup_x2, self._residual_buffer)
            residual_warmup_s = time.perf_counter() - residual_warmup_t0

            jacobian_warmup_t0: float = time.perf_counter()
            self._jacobian_evaluator.evaluate(warmup_x, warmup_full_params, warmup_x, warmup_dx, self._h, warmup_x2)
            jacobian_warmup_s = time.perf_counter() - jacobian_warmup_t0
        else:
            pass

        warmup_s: float = helper_warmup_s + residual_warmup_s + jacobian_warmup_s

        if self._verbose:
            print(
                f"--- [STRUCT-COMPILED] Warmup ready in {warmup_s:.4f}s | "
                f"helpers={helper_warmup_s:.4f}s | residual={residual_warmup_s:.4f}s | "
                f"jacobian={jacobian_warmup_s:.4f}s ---",
                flush=True,
            )
        else:
            pass

        self._vectorized_ready = True
        self._backend_warmup_done = full_warmup_enabled

        residual_stats: Dict[str, float] = self._residual_assembler.get_build_stats()
        jacobian_stats: Dict[str, float] = self._jacobian_evaluator.get_build_stats()
        self._backend_build_stats = {
            "grouping_s": grouping_s,
            "vec_kernel_compile_s": vec_kernel_compile_s,
            "residual_assembler_s": residual_assembler_s,
            "residual_dispatcher_s": residual_stats.get("dispatcher_build_s", 0.0),
            "residual_buffer_alloc_s": residual_stats.get("buffer_alloc_s", 0.0),
            "jacobian_evaluator_s": jacobian_evaluator_s,
            "warmup_s": warmup_s,
            "helper_warmup_s": helper_warmup_s,
            "residual_warmup_s": residual_warmup_s,
            "jacobian_warmup_s": jacobian_warmup_s,
            "full_warmup_enabled": 1.0 if full_warmup_enabled else 0.0,
            "eager_machine_code": 1.0 if eager_machine_code else 0.0,
            "residual_use_cse": 1.0 if residual_use_cse else 0.0,
            "jacobian_use_cse": 1.0 if jacobian_use_cse else 0.0,
            "estimated_steps": float(estimated_steps),
            "jac_column_rows_s": jacobian_stats.get("column_rows_s", 0.0),
            "jac_csc_shell_s": jacobian_stats.get("csc_shell_s", 0.0),
            "jac_coloring_s": jacobian_stats.get("coloring_s", 0.0),
            "jac_scatter_map_s": jacobian_stats.get("scatter_map_s", 0.0),
            "jac_ad_kernels_s": jacobian_stats.get("ad_kernels_s", 0.0),
            "jac_dispatcher_s": jacobian_stats.get("dispatcher_build_s", 0.0),
            "total_s": time.perf_counter() - t_start,
        }

        if self._verbose:
            elapsed: float = self._backend_build_stats["total_s"]
            print(f"--- [STRUCT-COMPILED] Backend ready in {elapsed:.4f}s ---", flush=True)
        else:
            pass

    def get_last_sim_loop_time(self) -> float:
        """
        Return the last measured integration loop wall time.

        :return: Last measured loop time.
        :rtype: float
        """
        return self._last_sim_loop_time

    def is_vectorized_ready(self) -> bool:
        """
        Return whether the eager backend has already been built.

        :return: ``True`` when the backend is ready.
        :rtype: bool
        """
        return self._vectorized_ready

    def get_residual_buffer(self) -> Vec:
        """
        Return the persistent residual buffer.

        :return: Persistent residual buffer.
        :rtype: Vec
        """
        return self._residual_buffer

    def get_jacobian_data_buffer(self) -> Vec:
        """
        Return the persistent CSC numeric buffer.

        :return: Persistent CSC numeric buffer.
        :rtype: Vec
        """
        return self._jacobian_data_buffer

    def get_backend_build_stats(self) -> Dict[str, float]:
        """
        Return setup timings for the structural compiled backend build.

        :return: Setup timings grouped by build phase.
        :rtype: Dict[str, float]
        """
        return dict(self._backend_build_stats)

    def get_last_runtime_stats(self) -> Dict[str, float]:
        """
        Return runtime statistics collected during the latest simulation.

        :return: Latest runtime statistics.
        :rtype: Dict[str, float]
        """
        return dict(self._last_runtime_stats)

    def simulate(
            self,
            x0: Optional[Vec] = None,
            dx0: Optional[Vec] = None,
            params0: Optional[Vec] = None,
            boundary_updater: EmtBoundaryUpdateProtocol | None = None,
    ) -> Tuple[Vec, Mat, Mat, bool, bool]:
        """
        Run the implicit EMT simulation with eager structural kernels.

        :param x0: Optional initial state vector.
        :type x0: Vec | None
        :param dx0: Optional initial differential vector.
        :type dx0: Vec | None
        :param params0: Optional initial runtime parameters.
        :type params0: Vec | None
        :param boundary_updater: Optional override for the problem boundary updater.
        :type boundary_updater: EmtBoundaryUpdateProtocol | None
        :return: Time vector, state trajectory and differential trajectory.
        :rtype: Tuple[Vec, Mat, Mat]
        """
        converged: bool = True
        well_initialized: bool = True

        if self._vectorized_ready:
            pass
        else:
            self._build_vectorized_backend(self._method)

        if self._residual_assembler is None or self._jacobian_evaluator is None:
            raise RuntimeError("Structural compiled backend was not built correctly")
        else:
            pass

        steps: int = int(np.ceil((self._t_end - self._t0) / self._h))
        t: Vec = self._t0 + self._h * np.arange(steps + 1, dtype=np.float64)
        y: Mat = np.zeros((steps + 1, self._n_vars), dtype=np.float64)
        dy: Mat = np.zeros((steps + 1, self._n_diff), dtype=np.float64)

        if x0 is None:
            x_prev: Vec = self._problem.get_x0().copy()
        else:
            x_prev = np.array(x0, dtype=np.float64, copy=True)

        if dx0 is None:
            dx_prev: Vec = self._problem.get_dx0().copy()
        else:
            dx_prev = np.array(dx0, dtype=np.float64, copy=True)

        active_boundary_updater = resolve_solver_boundary_updater(self._problem, boundary_updater, float(self._t0))

        x_prev2: Vec = x_prev.copy()
        x_iter: Vec = x_prev.copy()
        trial_state: Vec = self._trial_state_buffer
        trial_residual: Vec = self._trial_residual_buffer

        if params0 is None:
            runtime_params = self._problem.event_params_values.copy()
        else:
            runtime_params = np.array(params0, dtype=np.float64, copy=True)

        y[0, :] = x_prev
        dy[0, :] = dx_prev

        full_params: Vec = self._full_parameter_buffer
        if self._n_event_parameters > 0:
            runtime_params[:] = self._problem.def_event_params_fn(runtime_params, float(self._t0))
        else:
            runtime_params = runtime_params

        _fill_full_parameter_buffer(runtime_params, self._static_parameter_buffer, full_params)

        if active_boundary_updater is None:
            pass
        else:
            active_boundary_updater.update(float(self._t0), x_prev, full_params)

        if self._n_event_parameters > 0:
            runtime_params[:] = full_params[:self._n_event_parameters]
        else:
            pass

        use_dense_solver: bool = self._n_vars <= self._dense_threshold
        sparse_factor_manager: StructuralCompiledSparseFactorizationManager | None

        if use_dense_solver:
            sparse_factor_manager = None
        else:
            sparse_factor_manager = self._sparse_factorization_manager

        trace_collector = self._problem.get_newton_trace_collector()
        diag_cfg = self._newton_diag_config
        diagnostics_enabled: bool = (
            trace_collector is not None
            or diag_cfg.compute_dense_cond
            or diag_cfg.enable_fallback
            or diag_cfg.enable_index1_check
            or diag_cfg.enable_backtracking
        )

        dense_solve: Callable[..., Vec] | None = None
        sparse_solve: Callable[..., Vec] | None = None

        if sparse_factor_manager is None:
            sparse_stats_start: Dict[str, float] = dict()
        else:
            sparse_stats_start = sparse_factor_manager.get_stats()

        jacobian_eval_count: int = 0
        dense_factorization_count: int = 0
        factorization_reuse_hits: int = 0
        forced_factorization_invalidations: int = 0

        if diagnostics_enabled:
            dense_solve = with_newton_diagnostics(
                _dense_lu_bundle_solve,
                fallback_solve=_dense_lu_bundle_fallback,
                collector=trace_collector,
                config=diag_cfg,
                solver_name="dense_lu",
                matrix_getter=_dense_lu_bundle_matrix,
            )
            sparse_solve = with_newton_diagnostics(
                _sparse_factor_manager_solve,
                fallback_solve=_sparse_factor_manager_fallback,
                collector=trace_collector,
                config=diag_cfg,
                solver_name="superlu",
                matrix_getter=_sparse_factor_manager_matrix,
            )
        else:
            pass

        # The eager kernels only need one warmup per solver lifetime. Skipping
        # repeated warmups removes avoidable overhead from successive benchmark runs.
        if self._backend_warmup_done:
            pass
        else:
            self._residual_assembler.evaluate(x_prev, full_params, x_prev, dx_prev, self._h, x_prev2, self._residual_buffer)
            self._jacobian_evaluator.evaluate(x_prev, full_params, x_prev, dx_prev, self._h, x_prev2)
            self._backend_warmup_done = True

        loop_start: float = time.perf_counter()

        if self._verbose:
            print("-> StructuralCompiled simulation started")
        else:
            pass

        step_index: int = 0
        while step_index < steps:
            if self._progress_signal is not None:
                self._problem.report_progress2(step_index, steps)
            else:
                pass

            if self._cancel_checker is not None and self._cancel_checker():
                return t[:step_index + 1].copy(), y[:step_index + 1, :].copy(), dy[:step_index + 1, :].copy(), well_initialized, converged

            t_step_start: float = float(t[step_index])
            t_step_target: float = float(t[step_index + 1])
            t_local_prev: float = t_step_start
            is_first_local_step: bool = True

            while t_local_prev < (t_step_target - 1e-15):
                forced_event_time: float | None

                forced_event_time = get_solver_forced_event_time(
                    active_boundary_updater,
                    float(t_local_prev),
                    float(t_step_target),
                )

                if forced_event_time is None:
                    t_curr: float = t_step_target
                else:
                    t_curr = min(float(forced_event_time), t_step_target)

                    if t_curr <= t_local_prev + 1e-15:
                        t_curr = t_step_target
                    else:
                        pass

                is_aligned_substep: bool = t_curr < (t_step_target - 1e-15)

                if self._method == DynamicIntegrationMethod.DaeBDF2 and is_aligned_substep:
                    raise NotImplementedError(
                        "force_step_alignment is not implemented for DaeBDF2 in StructuralCompiledSolver"
                    )
                else:
                    pass

                h_eff: float = float(t_curr - t_local_prev)

                # Runtime parameters are refreshed before every Newton solve because events may move them.
                if self._n_event_parameters > 0:
                    runtime_params[:] = self._problem.def_event_params_fn(runtime_params, float(t_curr))
                else:
                    runtime_params = runtime_params

                _fill_full_parameter_buffer(runtime_params, self._static_parameter_buffer, full_params)

                if active_boundary_updater is None:
                    state_event_retry_time: float | None = None
                else:
                    state_event_retry_time = active_boundary_updater.update(
                        float(t_curr),
                        x_prev,
                        full_params,
                    )

                if self._n_event_parameters > 0:
                    runtime_params[:] = full_params[:self._n_event_parameters]
                else:
                    pass

                x_iter[:] = x_prev
                last_res_norm: float = 1.0
                cached_lu_dense: DenseSolveBundle | None = None

                if sparse_factor_manager is None:
                    pass
                else:
                    if is_aligned_substep and sparse_factor_manager.has_factorization():
                        params_changed: bool = True

                        if self._has_factorization_parameter_snapshot:
                            params_changed = _max_abs_diff_vectors(
                                full_params,
                                self._last_factorization_parameter_snapshot,
                            ) > 1.0e-14
                        else:
                            params_changed = True

                        if params_changed:
                            sparse_factor_manager.invalidate()
                            forced_factorization_invalidations += 1
                        else:
                            forced_factorization_invalidations = forced_factorization_invalidations
                    else:
                        pass

                # The first trapezoidal step benefits from a cheap explicit predictor.
                if step_index == 0 and is_first_local_step and self._method == DynamicIntegrationMethod.DaeTrapezoidal:
                    self._predictor.predict(x_iter, x_prev, dx_prev, h_eff, self._pred_method)
                else:
                    pass

                substep_converged: bool = state_event_retry_time is not None
                newton_index: int = 0
                while (
                    state_event_retry_time is None
                    and newton_index < self._newton_max_iter
                ):
                    ctx: NewtonSolveContext | None = None
                    # Residual assembly is fully in-place and reuses the grouped work buffers.
                    self._residual_assembler.evaluate(
                        x_iter,
                        full_params,
                        x_prev,
                        dx_prev,
                        h_eff,
                        x_prev2,
                        self._residual_buffer,
                    )
                    res_norm: float = _max_abs_value(self._residual_buffer)

                    if res_norm < self._newton_tolerance:
                        substep_converged = True
                        break
                    else:
                        pass

                    if diagnostics_enabled:
                        ctx = NewtonSolveContext(
                            t=float(t_curr),
                            step_idx=int(step_index),
                            newton_iter=int(newton_index),
                            phase="jit_structural_compiled",
                            method=str(self._method),
                        )
                        ctx.res_norm_inf = res_norm
                    else:
                        pass

                    if self._last_macro_newton_iterations <= 2:
                        adaptive_recompute_threshold: float = 0.8
                    elif self._last_macro_newton_iterations <= 4:
                        adaptive_recompute_threshold = 0.6
                    else:
                        adaptive_recompute_threshold = 0.5

                    recompute_factorization: bool = (
                        (cached_lu_dense is None and (sparse_factor_manager is None or not sparse_factor_manager.has_factorization()))
                        or (newton_index > 0 and (res_norm / (last_res_norm + 1e-16)) > adaptive_recompute_threshold)
                    )

                    if recompute_factorization:
                        # The Jacobian numeric values are written directly into CSC storage.
                        cached_jacobian: csc_matrix = self._jacobian_evaluator.evaluate(
                            x_iter,
                            full_params,
                            x_prev,
                            dx_prev,
                            h_eff,
                            x_prev2,
                        )
                        jacobian_eval_count += 1

                        if use_dense_solver:
                            dense_jacobian = cached_jacobian.toarray()

                            if diagnostics_enabled and ctx is not None:
                                maybe_check_index1(dense_jacobian, self._n_state, ctx=ctx, config=diag_cfg)
                            else:
                                pass

                            cached_lu_dense = (lu_factor(dense_jacobian), dense_jacobian)
                            dense_factorization_count += 1
                        else:
                            if diagnostics_enabled and ctx is not None:
                                maybe_check_index1(cached_jacobian, self._n_state, ctx=ctx, config=diag_cfg)
                            else:
                                pass

                            if sparse_factor_manager is None:
                                raise RuntimeError("Missing sparse factorization manager in sparse StructuralCompiled path")
                            else:
                                sparse_factor_manager.factorize()
                                self._last_factorization_parameter_snapshot[:] = full_params
                                self._has_factorization_parameter_snapshot = True

                            cached_lu_dense = None
                    else:
                        factorization_reuse_hits += 1

                    # The right-hand side is also written in place to avoid creating -res arrays.
                    _copy_negated_vector(self._residual_buffer, self._linear_rhs_buffer)

                    if use_dense_solver:
                        if cached_lu_dense is None:
                            self._delta_buffer[:] = 0.0
                            delta: Vec = self._delta_buffer
                        else:
                            if diagnostics_enabled and ctx is not None:
                                assert dense_solve is not None
                                self._delta_buffer[:] = dense_solve(cached_lu_dense, self._linear_rhs_buffer, ctx)
                                delta = self._delta_buffer
                            else:
                                self._delta_buffer[:] = lu_solve(cached_lu_dense[0], self._linear_rhs_buffer)
                                delta = self._delta_buffer
                    else:
                        if sparse_factor_manager is None or not sparse_factor_manager.has_factorization():
                            self._delta_buffer[:] = 0.0
                            delta = self._delta_buffer
                        else:
                            if diagnostics_enabled and ctx is not None:
                                assert sparse_solve is not None
                                delta = sparse_solve(sparse_factor_manager, self._linear_rhs_buffer, ctx)
                            else:
                                delta = sparse_factor_manager.solve(self._linear_rhs_buffer)

                    if diag_cfg.enable_backtracking:
                        self._trial_residual_evaluator.set_context(
                            self._residual_assembler,
                            full_params,
                            x_prev,
                            dx_prev,
                            h_eff,
                            x_prev2,
                        )

                        maybe_apply_backtracking(
                            x_iter,
                            delta,
                            res_norm,
                            trial_state,
                            trial_residual,
                            evaluate_residual=self._trial_residual_evaluator.evaluate,
                            config=diag_cfg,
                        )
                    else:
                        x_iter += delta

                    last_res_norm = res_norm
                    newton_index += 1

                if not substep_converged:
                    converged = False
                    if step_index == 0 and is_first_local_step:
                        well_initialized = False

                if state_event_retry_time is None:
                    state_event_retry_time = resolve_solver_boundary_step(
                        boundary_updater=active_boundary_updater,
                        accepted=substep_converged,
                        params=full_params,
                        committed_time=float(t_curr),
                        committed_state=x_iter,
                    )
                else:
                    pass

                if substep_converged and state_event_retry_time is None:
                    # A post-acceptance native sample may publish new held
                    # outputs. Retain them for the next aligned sub-step.
                    runtime_params[:] = full_params[:self._n_event_parameters]
                else:
                    pass

                if state_event_retry_time is not None:
                    # Do not advance differential history beyond a newly found
                    # event; the next loop targets its global earliest time.
                    x_iter[:] = x_prev
                else:
                    # Differential history is updated only for an accepted
                    # continuous interval or its post-event re-solve.
                    self._last_macro_newton_iterations = int(newton_index)

                    if self._method == DynamicIntegrationMethod.DaeTrapezoidal:
                        dx_prev[:self._n_state] = (
                            (2.0 / h_eff) * (x_iter[:self._n_state] - x_prev[:self._n_state])
                            - dx_prev[:self._n_state]
                        )
                    elif self._method == DynamicIntegrationMethod.DaeBDF2:
                        x_prev2[:] = x_prev
                        dx_prev[:self._n_state] = (
                            1.5 * x_iter[:self._n_state]
                            - 2.0 * x_prev[:self._n_state]
                            + 0.5 * x_prev2[:self._n_state]
                        ) / h_eff
                    else:
                        dx_prev[:self._n_state] = (
                            x_iter[:self._n_state] - x_prev[:self._n_state]
                        ) / h_eff

                    if self._method == DynamicIntegrationMethod.DaeBDF2:
                        pass
                    else:
                        x_prev2[:] = x_prev

                    x_prev[:] = x_iter
                    t_local_prev = t_curr
                    is_first_local_step = False


            y[step_index + 1, :] = x_prev
            dy[step_index + 1, :] = dx_prev
            step_index += 1

        self._last_sim_loop_time = time.perf_counter() - loop_start

        if self._verbose:
            print(f"-> StructuralCompiled simulation finished in {self._last_sim_loop_time:.4f}s")
        else:
            pass

        if sparse_factor_manager is None:
            sparse_stats_end: Dict[str, float] = dict()
        else:
            sparse_stats_end = sparse_factor_manager.get_stats()

        self._last_runtime_stats = {
            "jacobian_evaluations": float(jacobian_eval_count),
            "dense_factorizations": float(dense_factorization_count),
            "factorization_reuse_hits": float(factorization_reuse_hits),
            "forced_factorization_invalidations": float(forced_factorization_invalidations),
            "sparse_numeric_factorizations": float(
                sparse_stats_end.get("numeric_factorizations", 0.0) - sparse_stats_start.get("numeric_factorizations", 0.0)
            ),
            "sparse_ordering_builds": float(
                sparse_stats_end.get("ordering_builds", 0.0) - sparse_stats_start.get("ordering_builds", 0.0)
            ),
            "sparse_ordering_reuses": float(
                sparse_stats_end.get("ordering_reuses", 0.0) - sparse_stats_start.get("ordering_reuses", 0.0)
            ),
            "sparse_invalidations": float(
                sparse_stats_end.get("invalidations", 0.0) - sparse_stats_start.get("invalidations", 0.0)
            ),
            "sparse_solve_calls": float(
                sparse_stats_end.get("solve_calls", 0.0) - sparse_stats_start.get("solve_calls", 0.0)
            ),
            "sparse_fallback_solves": float(
                sparse_stats_end.get("fallback_solves", 0.0) - sparse_stats_start.get("fallback_solves", 0.0)
            ),
        }

        return t, y, dy,well_initialized, converged
