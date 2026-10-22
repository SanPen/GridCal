# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Module: JIT Equation Compiler & Numerical Discretization Engine
===============================================================

Abstract
--------
This module implements a symbolic-to-numeric translation engine designed to generate
optimized executable kernels for Differential-Algebraic Equation (DAE) systems.
It operates by traversing the symbolic Abstract Syntax Tree (AST) of the model and
injecting discrete time-stepping schemes (e.g., Implicit Trapezoidal, BDF2) directly
into the residual evaluation code.

Architectural Rationale
-----------------------
The decoupling of the compilation logic from the `DiffBlockSolver` enforces a strict
separation of concerns between the network topology management (Solver) and the
numerical discretization strategy (Compiler). This abstraction allows for the
interchangeability of integration methods—facilitating the switch between A-stable
and L-stable schemes—without altering the solver's core iterative algorithms.

Performance Optimization

------------------------
By fusing the physical model equations with the numerical integration formulas into
a single JIT-compiled kernel, this module eliminates the interpreter overhead and
intermediate memory allocations typical of vectorized Numpy operations. This results
in a monolithic residual evaluation function optimized for the high-frequency
computation requirements of Electromagnetic Transient (EMT) simulations.
"""

# Import libraries for utils
import ast
import numpy as np
from abc import ABC, abstractmethod
from enum import Enum
from numba import njit, types
from typing import Dict, List, Callable, Tuple, Set, Any
import os
from pathlib import Path
import importlib.util
import hashlib
import scipy.sparse as sp
from collections import defaultdict

#RMS
from VeraGridEngine.Utils.Symbolic.symbolic import expression2numba, get_expression_vars
from VeraGridEngine.enumerations import DynamicIntegrationMethod
#Totally integrated
from VeraGridEngine.Utils.Symbolic.symbolic import Expr, BinOp, UnOp, Func, Func2, Var, Const
from VeraGridEngine.basic_structures import Vec


class GeneratedKernelCacheEntry:
    """
    In-process cache entry for one generated eager kernel.
    """

    __slots__ = ["_python_function", "_signature_tpe"]

    def __init__(self, python_function: Callable, signature_tpe: object) -> None:
        """
        Build one generated-kernel cache entry.

        :param python_function: Generated Python function.
        :type python_function: Callable
        :param signature_tpe: Eager Numba signature.
        :type signature_tpe: object
        :return: None.
        :rtype: None
        """
        self._python_function = python_function
        self._signature_tpe = signature_tpe

    def get_python_function(self) -> Callable:
        """
        Return the generated Python function.

        :return: Generated Python function.
        :rtype: Callable
        """
        return self._python_function

    def get_signature_tpe(self) -> object:
        """
        Return the eager Numba signature.

        :return: Eager Numba signature.
        :rtype: object
        """
        return self._signature_tpe


def _get_cse_sort_key(entry: Tuple[str, str]) -> int:
    """
    Return the numeric ordering key of one generated CSE temporary.

    :param entry: Pair ``(expression_hash, temporary_name)``.
    :return: Integer suffix used by the generated temporary name.
    """
    return int(entry[1][2:])


def _get_triplet_sort_key(triplet: Tuple[int, int, Expr]) -> Tuple[int, int]:
    """
    Return the deterministic column-row ordering of one sparse Jacobian triplet.

    :param triplet: Sparse Jacobian triplet ``(col, row, expr)``.
    :return: Sorting key ``(col, row)``.
    """
    return triplet[0], triplet[1]


def _collect_related_wrt_uids(var: Var,
                              wrt_map: Dict[int, Tuple[int, Var]],
                              output_uids: Set[int],
                              seen_uids: Set[int]) -> None:
    """
    Collect all differentiated UIDs related to one symbolic variable chain.

    :param var: Symbolic variable from one expression.
    :param wrt_map: Differentiation variables keyed by UID.
    :param output_uids: Output UID set updated in place.
    :param seen_uids: Visited UID set used to avoid recursion loops.
    :return: None.
    """
    if var.uid in seen_uids:
        return
    else:
        pass

    seen_uids.add(var.uid)

    if var.uid in wrt_map:
        output_uids.add(var.uid)
    else:
        pass

    if var.base_var is not None:
        _collect_related_wrt_uids(var.base_var, wrt_map, output_uids, seen_uids)
    else:
        pass

    if var.diff_var is not None:
        _collect_related_wrt_uids(var.diff_var, wrt_map, output_uids, seen_uids)
    else:
        pass


def _collect_candidate_wrt_uids(eq: Expr, wrt_map: Dict[int, Tuple[int, Var]]) -> Set[int]:
    """
    Return the differentiated variable UIDs that appear in one equation.

    :param eq: Symbolic equation.
    :param wrt_map: Differentiation variables keyed by UID.
    :return: Candidate UIDs present in the equation dependency graph.
    """
    candidates: Set[int] = set()
    seen_uids: Set[int] = set()
    variable_in_equation: Var

    for variable_in_equation in get_expression_vars(eq):
        _collect_related_wrt_uids(variable_in_equation, wrt_map, candidates, seen_uids)

    return candidates


class EmptySparseJacobianEvaluator:
    """
    Reusable callable returning one prebuilt empty CSC Jacobian matrix.
    """

    __slots__ = ("_matrix",)

    def __init__(self, matrix: sp.csc_matrix) -> None:
        """
        Store the empty sparse Jacobian matrix.

        :param matrix: Prebuilt empty CSC matrix.
        :return: None.
        """
        self._matrix: sp.csc_matrix = matrix

    def __call__(self, vrs: Vec, diff: Vec, vprms: Vec, cprms: Vec, h: float) -> sp.csc_matrix:
        """
        Return the prebuilt empty sparse Jacobian matrix.

        :param vrs: Runtime variables.
        :param diff: Differential variables.
        :param vprms: Variable parameters.
        :param cprms: Constant parameters.
        :param h: Integration step.
        :return: Empty CSC Jacobian matrix.
        """
        _unused_args: Tuple[Vec, Vec, Vec, Vec, float] = (vrs, diff, vprms, cprms, h)
        return self._matrix

    def get_sparsity(self) -> Tuple[np.ndarray, np.ndarray, int, int]:
        """Return the empty CSC structure through the common evaluator contract.

        :return: Row indices, column pointers, row count, and column count.
        """
        row_count: int = int(self._matrix.shape[0])
        column_count: int = int(self._matrix.shape[1])
        return (
            self._matrix.indices,
            self._matrix.indptr,
            row_count,
            column_count,
        )


class EmptyVecSparseJacobianEvaluator:
    """
    Reusable callable returning a zero 2D data array for vectorized Jacobians.
    """

    __slots__ = ("_n_rows", "_n_cols")

    def __init__(self, n_rows: int, n_cols: int) -> None:
        self._n_rows: int = n_rows
        self._n_cols: int = n_cols

    def __call__(self, vrs: Vec, diff: Vec, vprms: Vec, cprms: Vec, h: float) -> np.ndarray:
        n_inst: int = vrs.shape[1]
        return np.zeros((0, n_inst), dtype=np.float64)

    def get_sparsity(self) -> Tuple[np.ndarray, np.ndarray, int, int]:
        n_vars: int = self._n_cols
        return (np.zeros(0, dtype=np.int32),
                np.zeros(n_vars + 1, dtype=np.int32),
                self._n_rows,
                n_vars)


class SparseJacobianEvaluatorVecWrapper:
    """
    Callable wrapper around a vectorized sparse Jacobian filler.

    The filler function fills a 2D data_out array of shape (nnz, n_instances).
    This wrapper allocates the output array, calls the filler, and returns it.
    It also exposes the sparsity pattern (row indices, column pointers) so the
    problem class can assemble the global sparse Jacobian.
    """

    __slots__ = ("_filler_fn", "_nnz", "_n_rows", "_n_cols",
                 "_rows", "_cols", "_indices", "_indptr")

    def __init__(self, filler_fn: Callable, nnz: int, n_rows: int, n_cols: int,
                 rows: List[int], cols: List[int],
                 indices: np.ndarray, indptr: np.ndarray) -> None:
        self._filler_fn: Callable = filler_fn
        self._nnz: int = nnz
        self._n_rows: int = n_rows
        self._n_cols: int = n_cols
        self._rows: List[int] = rows
        self._cols: List[int] = cols
        self._indices: np.ndarray = indices
        self._indptr: np.ndarray = indptr

    def __call__(self, vrs: Vec, diff: Vec, vprms: Vec, cprms: Vec, h: float) -> np.ndarray:
        n_inst: int = vrs.shape[1]
        data_out: np.ndarray = np.zeros((self._nnz, n_inst), dtype=np.float64)
        self._filler_fn(vrs, diff, vprms, cprms, h, data_out)
        return data_out

    def get_sparsity(self) -> Tuple[np.ndarray, np.ndarray, int, int]:
        return self._indices, self._indptr, self._n_rows, self._n_cols


class SparseJacobianEvaluatorWrapper:
    """
    Callable sparse Jacobian wrapper around one generated CSC filler function.
    """

    __slots__ = ("_filler_fn", "_matrix")

    def __init__(self, filler_fn: Callable, matrix: sp.csc_matrix) -> None:
        """
        Store the generated filler function and the reusable CSC matrix shell.

        :param filler_fn: Generated sparse Jacobian filler function.
        :param matrix: Reusable CSC matrix shell.
        :return: None.
        """
        self._filler_fn: Callable = filler_fn
        self._matrix: sp.csc_matrix = matrix

    def __call__(self, vrs: Vec, diff: Vec, vprms: Vec, cprms: Vec, h: float) -> sp.csc_matrix:
        """
        Fill and return the reusable CSC Jacobian matrix.

        :param vrs: Runtime variables.
        :param diff: Differential variables.
        :param vprms: Variable parameters.
        :param cprms: Constant parameters.
        :param h: Integration step.
        :return: Filled CSC Jacobian matrix.
        """
        self._filler_fn(vrs, diff, vprms, cprms, h, self._matrix.data)
        return self._matrix

    def get_sparsity(self) -> Tuple[np.ndarray, np.ndarray, int, int]:
        """Return the reusable CSC structure through the evaluator contract.

        :return: Row indices, column pointers, row count, and column count.
        """
        row_count: int = int(self._matrix.shape[0])
        column_count: int = int(self._matrix.shape[1])
        return (
            self._matrix.indices,
            self._matrix.indptr,
            row_count,
            column_count,
        )


class EventParameterFunctionWrapper:
    """
    Callable runtime-parameter wrapper around one generated event-parameter kernel.
    """

    __slots__ = ("_raw_fn", "_equation_count")

    def __init__(self, raw_fn: Callable, equation_count: int) -> None:
        """
        Store the generated event-parameter kernel.

        :param raw_fn: Generated event-parameter kernel.
        :param equation_count: Number of output equations.
        :return: None.
        """
        self._raw_fn: Callable = raw_fn
        self._equation_count: int = equation_count

    def __call__(self, event_params: Vec, glob_time: float) -> Vec:
        """
        Evaluate the event-parameter kernel into a fresh output vector.

        :param event_params: Runtime parameter vector.
        :param glob_time: Current simulation time.
        :return: Evaluated runtime-parameter vector.
        """
        output_vector: Vec = np.zeros(self._equation_count, dtype=np.float64)
        self._raw_fn(event_params, glob_time, output_vector)
        return output_vector


class DerivativeFunctionWrapper:
    """
    Callable derivative wrapper around one generated lag-derivative kernel.
    """

    __slots__ = ("_raw_fn", "_diff_var_count")

    def __init__(self, raw_fn: Callable, diff_var_count: int) -> None:
        """
        Store the generated derivative kernel.

        :param raw_fn: Generated derivative kernel.
        :param diff_var_count: Number of derivative outputs.
        :return: None.
        """
        self._raw_fn: Callable = raw_fn
        self._diff_var_count: int = diff_var_count

    def __call__(self, vrs: Vec, lagvars: Vec, lagdx: Vec, h: float) -> Vec:
        """
        Evaluate the derivative kernel into a fresh output vector.

        :param vrs: Runtime variable vector.
        :param lagvars: Lagged state vector.
        :param lagdx: Lagged derivative vector.
        :param h: Integration step.
        :return: Evaluated derivative vector.
        """
        output_vector: Vec = np.zeros(self._diff_var_count, dtype=np.float64)
        self._raw_fn(vrs, lagvars, lagdx, h, output_vector)
        return output_vector


def _build_equation_compiler_residual_cache_key(equations: List[Expr],
                                                var_map: Dict[int, int],
                                                param_map: Dict[int, int],
                                                method_name: str,
                                                use_cse: bool,
                                                offset: int,
                                                inplace: bool,
                                                diff_var_map: Dict[int, int] | None = None) -> str:
    """
    Return a deterministic cache key for one ``EquationCompiler`` residual kernel.

    :param equations: Residual equations.
    :type equations: List[Expr]
    :param var_map: Runtime variable index map.
    :type var_map: Dict[int, int]
    :param param_map: Parameter index map.
    :type param_map: Dict[int, int]
    :param method_name: Discretization strategy name.
    :type method_name: str
    :param use_cse: Whether CSE is enabled.
    :type use_cse: bool
    :param offset: Output offset.
    :type offset: int
    :param inplace: Whether the kernel writes in place.
    :type inplace: bool
    :param diff_var_map: Base UID to derivative-history slot; missing entries use the state slot.
    :type diff_var_map: Dict[int, int] | None
    :return: Deterministic cache key.
    :rtype: str
    """
    expr_fingerprints: List[str] = list()
    equation_index: int = 0

    while equation_index < len(equations):
        expr_fingerprints.append(
            _fingerprint_codegen_expr(
                equations[equation_index],
                var_map,
                param_map,
                method_name,
                None,
                diff_var_map,
            )
        )
        equation_index += 1

    payload: str = "|".join([
        "eq-compiler-residual",
        method_name,
        str(use_cse),
        str(offset),
        str(inplace),
        str(len(var_map)),
        str(len(param_map)),
        "::".join(expr_fingerprints),
    ])
    return _build_codegen_cache_key(payload)


def _build_equation_compiler_ad_cache_key(equations: List[Expr],
                                          var_map: Dict[int, int],
                                          param_map: Dict[int, int],
                                          method_name: str,
                                          use_cse: bool,
                                          active_indices: set | None,
                                          diff_var_map: Dict[int, int] | None = None) -> str:
    """
    Return a deterministic cache key for one ``EquationCompiler`` AD kernel.

    :param equations: Residual equations.
    :type equations: List[Expr]
    :param var_map: Runtime variable index map.
    :type var_map: Dict[int, int]
    :param param_map: Parameter index map.
    :type param_map: Dict[int, int]
    :param method_name: Discretization strategy name.
    :type method_name: str
    :param use_cse: Whether CSE is enabled.
    :type use_cse: bool
    :param active_indices: Optional active seed indices.
    :type active_indices: set | None
    :param diff_var_map: Base UID to derivative-history slot; missing entries use the state slot.
    :type diff_var_map: Dict[int, int] | None
    :return: Deterministic cache key.
    :rtype: str
    """
    expr_fingerprints: List[str] = list()
    active_index_tokens: List[str] = list()
    dynamic_seeds: bool = active_indices is None
    equation_index: int = 0

    while equation_index < len(equations):
        expr_fingerprints.append(
            _fingerprint_codegen_expr(
                equations[equation_index],
                var_map,
                param_map,
                method_name,
                None,
                diff_var_map,
            )
        )
        equation_index += 1

    if active_indices is None:
        active_index_tokens = list()
    else:
        active_index_tokens = [str(index) for index in sorted(list(active_indices))]

    payload: str = "|".join([
        "eq-compiler-ad",
        method_name,
        str(use_cse),
        str(len(var_map)),
        str(len(param_map)),
        # A runtime seed vector and an explicitly empty selection emit different code.
        str(dynamic_seeds),
        ",".join(active_index_tokens),
        "::".join(expr_fingerprints),
    ])
    return _build_codegen_cache_key(payload)


def _build_equation_compiler_matrix_cache_key(template_eq: Expr,
                                              var_map: Dict[int, int],
                                              param_map: Dict[int, int],
                                              method_name: str,
                                              col_map: Dict[int, int]) -> str:
    """
    Return a deterministic cache key for one ``MatrixVectorizedCompiler`` kernel.

    :param template_eq: Structural template equation.
    :type template_eq: Expr
    :param var_map: Runtime variable index map.
    :type var_map: Dict[int, int]
    :param param_map: Parameter index map.
    :type param_map: Dict[int, int]
    :param method_name: Discretization strategy name.
    :type method_name: str
    :param col_map: Runtime UID to canonical matrix gather column.
    :type col_map: Dict[int, int]
    :return: Deterministic cache key.
    :rtype: str
    """
    sorted_col_items: List[str] = list()
    col_index: int

    # Generated code consumes column positions; recreated UIDs and display
    # names must not create another kernel for the same binding topology.
    for col_index in sorted(col_map.values()):
        sorted_col_items.append(str(col_index))

    payload: str = "|".join([
        "eq-compiler-matrix-uid-v2",
        method_name,
        str(len(var_map)),
        str(len(param_map)),
        ",".join(sorted_col_items),
        _fingerprint_codegen_expr(template_eq, var_map, param_map, method_name, col_map),
    ])
    return _build_codegen_cache_key(payload)


class GeneratedKernelCache:
    """
    In-process cache for generated eager kernels keyed by structural signature.
    """

    __slots__ = ["_residual_cache", "_ad_cache", "_matrix_cache"]

    def __init__(self) -> None:
        """
        Build the generated-kernel cache.

        :return: None.
        :rtype: None
        """
        self._residual_cache: Dict[str, GeneratedKernelCacheEntry] = dict()
        self._ad_cache: Dict[str, GeneratedKernelCacheEntry] = dict()
        self._matrix_cache: Dict[str, GeneratedKernelCacheEntry] = dict()

    def get_entry(self, cache_kind: str, cache_key: str) -> GeneratedKernelCacheEntry | None:
        """
        Return one cached kernel entry.

        :param cache_kind: Cache family identifier.
        :type cache_kind: str
        :param cache_key: Deterministic cache key.
        :type cache_key: str
        :return: Cached entry or ``None``.
        :rtype: GeneratedKernelCacheEntry | None
        """
        if cache_kind == "residual":
            return self._residual_cache.get(cache_key, None)
        elif cache_kind == "ad":
            return self._ad_cache.get(cache_key, None)
        elif cache_kind == "matrix":
            return self._matrix_cache.get(cache_key, None)
        else:
            raise ValueError(f"Unknown generated-kernel cache kind: {cache_kind}")

    def set_entry(self, cache_kind: str, cache_key: str, entry: GeneratedKernelCacheEntry) -> None:
        """
        Store one cached kernel entry.

        :param cache_kind: Cache family identifier.
        :type cache_kind: str
        :param cache_key: Deterministic cache key.
        :type cache_key: str
        :param entry: Cache entry.
        :type entry: GeneratedKernelCacheEntry
        :return: None.
        :rtype: None
        """
        if cache_kind == "residual":
            self._residual_cache[cache_key] = entry
        elif cache_kind == "ad":
            self._ad_cache[cache_key] = entry
        elif cache_kind == "matrix":
            self._matrix_cache[cache_key] = entry
        else:
            raise ValueError(f"Unknown generated-kernel cache kind: {cache_kind}")


GENERATED_KERNEL_CACHE = GeneratedKernelCache()


def _is_zero(s: str) -> bool:
    return s in ["0.0", "0", "0.00", "(-0.0)"]

def _is_one(s: str) -> bool:
    return s in ["1.0", "1", "1.00"]


def _stable_digest(payload: str, length: int | None = None) -> str:
    """
    Return a deterministic SHA-256 digest for cache keys and generated-module names.

    :param payload: Deterministic payload string.
    :type payload: str
    :param length: Optional prefix length to keep.
    :type length: int | None
    :return: Hex digest string.
    :rtype: str
    """
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return digest if length is None else digest[:length]

def _compile_to_file(full_source: str, func_name: str) -> Callable:
    """
    Writes source code to a file in __pycache_jit__ and imports it.
    This allows Numba's cache=True to work.
    """
    import sys

    header = "import numpy as np\nimport math\nfrom numpy import nan\nfrom VeraGridEngine.Utils.Symbolic.symbolic import heaviside_num as _heaviside\n\n"
    full_content = header + full_source

    repo_root = Path(__file__).resolve().parents[4]
    cache_dir = os.environ.get(
        "VERAGRID_JIT_CACHE_DIR",
        str(repo_root / "__pycache_jit__"),
    )
    os.makedirs(cache_dir, exist_ok=True)

    if cache_dir not in sys.path:
        sys.path.append(cache_dir)

    content_hash = _stable_digest(full_content, length=16)
    mod_name = f"{func_name}_{content_hash}"
    filename = f"{mod_name}.py"
    filepath = os.path.join(cache_dir, filename)

    if not os.path.exists(filepath):
        with open(filepath, "w") as f:
            f.write(full_content)

    if mod_name in sys.modules:
        return sys.modules[mod_name].__dict__[func_name]

    spec = importlib.util.spec_from_file_location(mod_name, filepath)
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)

    return module.__dict__[func_name]


def _build_codegen_cache_key(payload: str) -> str:
    """
    Return a deterministic cache key for generated eager kernels.

    :param payload: Deterministic payload string.
    :type payload: str
    :return: Cache key.
    :rtype: str
    """
    # Regenerate kernels whose old identity omitted history bindings or seed mode.
    cache_version: str = "jit-codegen-v2"
    return _stable_digest(cache_version + "|" + payload)


def _fingerprint_codegen_var(node: Var,
                             var_map: Dict[int, int],
                             param_map: Dict[int, int],
                             method_name: str,
                             col_map: Dict[int, int] | None = None,
                             diff_var_map: Dict[int, int] | None = None,
                             force_derivative_discretization: bool = False) -> str:
    """
    Return a stable code-generation fingerprint for one variable node.

    :param node: Variable node.
    :type node: Var
    :param var_map: Runtime variable index map.
    :type var_map: Dict[int, int]
    :param param_map: Parameter index map.
    :type param_map: Dict[int, int]
    :param method_name: Discretization strategy name.
    :type method_name: str
    :param col_map: Optional matrix-kernel column map.
    :type col_map: Dict[int, int] | None
    :param diff_var_map: Base UID to scalar derivative-history slot, with state-slot fallback.
    :type diff_var_map: Dict[int, int] | None
    :param force_derivative_discretization: Follow nested derivative visitor recursion directly,
        bypassing an intermediate derivative's own runtime or parameter mapping.
    :type force_derivative_discretization: bool
    :return: Stable fingerprint string.
    :rtype: str
    """
    # Top-level variables keep their mapped meaning. Nested scalar visitors call
    # visit_diffvar directly, so their intermediate derivatives must follow the base.
    if not force_derivative_discretization and node.uid in param_map:
        return f"P{param_map[node.uid]}"
    elif not force_derivative_discretization and col_map is None and node.uid in var_map:
        return f"S{var_map[node.uid]}"
    elif not force_derivative_discretization and col_map is not None and node.uid in var_map:
        # Match the visitor's direct runtime lookup exactly: a missing UID is
        # invalid even if another column happens to belong to its origin.
        return f"M{col_map[node.uid]}"
    elif node.base_var is not None:
        if node.base_var.base_var is not None:
            # Both visitors recurse directly through visit_diffvar. An
            # intermediate runtime/parameter mapping cannot replace that
            # derivative traversal or hide its actual origin gather column.
            nested_fp: str = _fingerprint_codegen_var(
                node.base_var, var_map, param_map, method_name, col_map,
                diff_var_map, True)
            return f"DD[{method_name}|{nested_fp}]"
        elif col_map is None:
            state_index: int = var_map[node.base_var.uid]
            history_index: int
            if diff_var_map is None:
                history_index = state_index
            else:
                history_index = diff_var_map.get(node.base_var.uid, state_index)
            # Encode only the binding consumed by this leaf. Unused mappings and
            # renamed UIDs must not prevent equivalent kernels from being reused.
            return f"D[{method_name}|S{state_index}|H{history_index}]"
        else:
            return f"D[{method_name}|M{col_map[node.origin_var.uid]}]"
    elif node.name == 'h':
        return "H"
    else:
        return f"N:{node.name}"


class _StructuralExpressionContext:
    """
    Bind structural variable occurrences during one expression fingerprint walk.

    Runtime slots follow first occurrence, whereas parameter tokens retain
    concrete identity because grouped kernels read a shared parameter vector.
    This context is discarded after its ordered runtime variables are returned.
    """

    __slots__: Tuple[str, ...] = (
        "runtime_uids", "parameter_uids", "runtime_slots", "parameter_slots", "runtime_variables",
    )

    def __init__(self, runtime_uids: Set[int], parameter_uids: Set[int]) -> None:
        """
        Initialize expression-local binding lookups without copying the model.

        :param runtime_uids: UIDs belonging to the runtime state/algebraic vector.
        :param parameter_uids: UIDs belonging to the shared parameter vector.
        :return: None.
        """
        # Borrow the classification sets only for this traversal. The number of
        # encountered variables is unknown until the expression has been walked.
        self.runtime_uids: Set[int] = runtime_uids
        self.parameter_uids: Set[int] = parameter_uids
        self.runtime_slots: Dict[int, str] = dict()
        self.parameter_slots: Dict[int, str] = dict()
        self.runtime_variables: List[Var] = list()

    def fingerprint_variable(self, node: Var) -> str:
        """
        Classify an occurrence and retain its role and first runtime gather slot.

        :param node: Variable occurrence, including a derivative or same-UID alias.
        :return: Structural token preserving the occurrence's binding semantics.
        :raises RuntimeError: If the immediate-base UID has no classification.
        """
        # Group gather tables use the immediate base UID. Derivative order is
        # separate metadata: a value and its derivative share a column, not code.
        target_uid: int = node.uid if node.base_var is None else node.base_var.uid
        if target_uid in self.runtime_uids:
            runtime_slot: str | None = self.runtime_slots.get(target_uid, None)
            if runtime_slot is None:
                runtime_slot = f"__RVAR_{len(self.runtime_slots)}__"
                self.runtime_slots[target_uid] = runtime_slot
                self.runtime_variables.append(node)
            else:
                pass
            return f"{runtime_slot}:D{node.diff_order}"
        elif target_uid in self.parameter_uids:
            parameter_slot: str | None = self.parameter_slots.get(target_uid, None)
            if parameter_slot is None:
                # Keep the original first-name-per-UID policy. Different global
                # parameter entries must not normalize into a runtime placeholder.
                parameter_slot = f"__PARAM_{node.name}_{target_uid}__"
                self.parameter_slots[target_uid] = parameter_slot
            else:
                pass
            return parameter_slot
        else:
            raise RuntimeError(
                f"Unclassified symbolic variable name={node.name}, target_uid={target_uid}"
            )


def _fingerprint_codegen_expr(node: Expr,
                              var_map: Dict[int, int],
                              param_map: Dict[int, int],
                              method_name: str,
                              col_map: Dict[int, int] | None = None,
                              diff_var_map: Dict[int, int] | None = None,
                              structural_context: _StructuralExpressionContext | None = None) -> str:
    """
    Return a stable code-generation fingerprint for one symbolic expression.

    :param node: Symbolic expression node.
    :type node: Expr
    :param var_map: Runtime variable index map.
    :type var_map: Dict[int, int]
    :param param_map: Parameter index map.
    :type param_map: Dict[int, int]
    :param method_name: Discretization strategy name.
    :type method_name: str
    :param col_map: Optional matrix-kernel column map.
    :type col_map: Dict[int, int] | None
    :param diff_var_map: Base UID to scalar derivative-history slot; propagated through all nodes.
    :type diff_var_map: Dict[int, int] | None
    :param structural_context: Optional expression-local structural variable bindings.
        When present, code-generation maps and method are not consumed by variable nodes.
    :type structural_context: _StructuralExpressionContext | None
    :return: Stable fingerprint string.
    :rtype: str
    """
    if isinstance(node, Const):
        # Exact literal tokens are shared by grouping and cache identity; decimal
        # rounding here would substitute a different constant in grouped kernels.
        return f"C[{repr(node.value)}]"
    elif isinstance(node, Var):
        if structural_context is None:
            return _fingerprint_codegen_var(node, var_map, param_map, method_name, col_map, diff_var_map)
        else:
            return structural_context.fingerprint_variable(node)
    elif isinstance(node, BinOp):
        # Visit operands before sorting their tokens: runtime gather columns must
        # stay in source occurrence order for the corresponding compiled template.
        left_fp: str = _fingerprint_codegen_expr(
            node.left, var_map, param_map, method_name, col_map, diff_var_map, structural_context)
        right_fp: str = _fingerprint_codegen_expr(
            node.right, var_map, param_map, method_name, col_map, diff_var_map, structural_context)

        if node.op in ['+', '*'] and left_fp > right_fp:
            left_fp, right_fp = right_fp, left_fp
        else:
            pass

        return f"B[{node.op}|{left_fp}|{right_fp}]"
    elif isinstance(node, UnOp):
        operand_fp: str = _fingerprint_codegen_expr(
            node.operand, var_map, param_map, method_name, col_map, diff_var_map, structural_context)
        return f"U[{node.op}|{operand_fp}]"
    elif isinstance(node, Func):
        arg_fp: str = _fingerprint_codegen_expr(
            node.arg, var_map, param_map, method_name, col_map, diff_var_map, structural_context)
        return f"F[{node.op}|{arg_fp}]"
    else:
        return f"RAW[{type(node).__name__}|{str(node)}]"


def _build_residual_codegen_cache_key(equations: List[Expr],
                                      var_map: Dict[int, int],
                                      param_map: Dict[int, int],
                                      method_name: str,
                                      use_cse: bool,
                                      offset: int,
                                      n_variables: int,
                                      n_parameters: int,
                                      diff_var_map: Dict[int, int] | None = None) -> str:
    """
    Return the cache key of one residual kernel.

    :param equations: Residual equations.
    :type equations: List[Expr]
    :param var_map: Runtime variable index map.
    :type var_map: Dict[int, int]
    :param param_map: Parameter index map.
    :type param_map: Dict[int, int]
    :param method_name: Discretization strategy name.
    :type method_name: str
    :param use_cse: Whether CSE is enabled.
    :type use_cse: bool
    :param offset: Output offset.
    :type offset: int
    :param n_variables: Number of runtime variables.
    :type n_variables: int
    :param n_parameters: Number of parameters.
    :type n_parameters: int
    :param diff_var_map: Base UID to derivative-history slot; missing entries use the state slot.
    :type diff_var_map: Dict[int, int] | None
    :return: Deterministic cache key.
    :rtype: str
    """
    expr_fingerprints: List[str] = list()
    equation_index: int = 0

    while equation_index < len(equations):
        expr_fingerprints.append(_fingerprint_codegen_expr(
            equations[equation_index], var_map, param_map, method_name, None, diff_var_map))
        equation_index += 1

    payload: str = "|".join([
        "residual",
        method_name,
        str(use_cse),
        str(offset),
        str(n_variables),
        str(n_parameters),
        str(len(equations)),
        "::".join(expr_fingerprints),
    ])
    return _build_codegen_cache_key(payload)


def _build_ad_codegen_cache_key(equations: List[Expr],
                                var_map: Dict[int, int],
                                param_map: Dict[int, int],
                                method_name: str,
                                use_cse: bool,
                                active_indices: set | None,
                                n_variables: int,
                                n_parameters: int,
                                diff_var_map: Dict[int, int] | None = None) -> str:
    """
    Return the cache key of one AD kernel.

    :param equations: Residual equations.
    :type equations: List[Expr]
    :param var_map: Runtime variable index map.
    :type var_map: Dict[int, int]
    :param param_map: Parameter index map.
    :type param_map: Dict[int, int]
    :param method_name: Discretization strategy name.
    :type method_name: str
    :param use_cse: Whether CSE is enabled.
    :type use_cse: bool
    :param active_indices: Active seed indices or ``None``.
    :type active_indices: set | None
    :param n_variables: Number of runtime variables.
    :type n_variables: int
    :param n_parameters: Number of parameters.
    :type n_parameters: int
    :param diff_var_map: Base UID to derivative-history slot; missing entries use the state slot.
    :type diff_var_map: Dict[int, int] | None
    :return: Deterministic cache key.
    :rtype: str
    """
    expr_fingerprints: List[str] = list()
    active_index_list: List[str] = list()
    dynamic_seeds: bool = active_indices is None
    equation_index: int = 0

    while equation_index < len(equations):
        expr_fingerprints.append(_fingerprint_codegen_expr(
            equations[equation_index], var_map, param_map, method_name, None, diff_var_map))
        equation_index += 1

    if active_indices is None:
        active_index_list = list()
    else:
        active_index_list = [str(index) for index in sorted(list(active_indices))]

    payload: str = "|".join([
        "ad",
        method_name,
        str(use_cse),
        str(n_variables),
        str(n_parameters),
        str(len(equations)),
        # None consumes runtime seeds; an empty set emits a zero JVP.
        str(dynamic_seeds),
        ",".join(active_index_list),
        "::".join(expr_fingerprints),
    ])
    return _build_codegen_cache_key(payload)


def _build_matrix_codegen_cache_key(template_eq: Expr,
                                    var_map: Dict[int, int],
                                    param_map: Dict[int, int],
                                    method_name: str,
                                    col_map: Dict[int, int],
                                    n_variables: int,
                                    n_parameters: int) -> str:
    """
    Return the cache key of one matrix-vectorized kernel.

    :param template_eq: Structural template equation.
    :type template_eq: Expr
    :param var_map: Runtime variable index map.
    :type var_map: Dict[int, int]
    :param param_map: Parameter index map.
    :type param_map: Dict[int, int]
    :param method_name: Discretization strategy name.
    :type method_name: str
    :param col_map: Runtime UID to canonical matrix gather column.
    :type col_map: Dict[int, int]
    :param n_variables: Number of runtime variables.
    :type n_variables: int
    :param n_parameters: Number of parameters.
    :type n_parameters: int
    :return: Deterministic cache key.
    :rtype: str
    """
    expr_fingerprint: str = _fingerprint_codegen_expr(template_eq, var_map, param_map, method_name, col_map)
    sorted_col_items: List[str] = list()
    col_index: int

    # Keep the cache independent of author labels and per-model UIDs. The
    # expression fingerprint retains the actual ordered column references.
    for col_index in sorted(col_map.values()):
        sorted_col_items.append(str(col_index))

    payload: str = "|".join([
        "matrix-uid-v2",
        method_name,
        str(n_variables),
        str(n_parameters),
        ",".join(sorted_col_items),
        expr_fingerprint,
    ])
    return _build_codegen_cache_key(payload)

# ==============================================================================
# 1. Discretization strategy (Numerical Methods)
# ==============================================================================
class DiscretizationMethod(ABC):
    """Abstract base class for discretization strategies."""
    __slots__ = ()

    @abstractmethod
    def discretize(self, state_idx: int, h_var: str = 'h', history_idx: int | None = None) -> str:
        pass

    @abstractmethod
    def discretize_dot(self, state_idx: int, h_var: str = 'h', seeds_var: str = 'seeds') -> str:
        pass


class TrapezoidalMethod(DiscretizationMethod):
    __slots__ = ()

    def discretize(self, state_idx: int, h_var: str = 'h', history_idx: int | None = None) -> str:
        diff_idx = state_idx if history_idx is None else history_idx
        return f"((2.0/{h_var}) * (states[{state_idx}] - history[{state_idx}]) - d_history[{diff_idx}])"

    def discretize_dot(self, state_idx: int, h_var: str = 'h', seeds_var: str = 'seeds') -> str:
        return f"((2.0/{h_var}) * ({seeds_var}[{state_idx}]))"


class BackwardEulerMethod(DiscretizationMethod):
    __slots__ = ()

    def discretize(self, state_idx: int, h_var: str = 'h', history_idx: int | None = None) -> str:
        return f"((states[{state_idx}] - history[{state_idx}]) / {h_var})"

    def discretize_dot(self, state_idx: int, h_var: str = 'h', seeds_var: str = 'seeds') -> str:
        return f"(({seeds_var}[{state_idx}]) / {h_var})"


class BDF2Method(DiscretizationMethod):
    __slots__ = ()

    def discretize(self, state_idx: int, h_var: str = 'h', history_idx: int | None = None) -> str:
        return f"((1.5*states[{state_idx}] - 2.0*history[{state_idx}] + 0.5*history2[{state_idx}]) / {h_var})"

    def discretize_dot(self, state_idx: int, h_var: str = 'h', seeds_var: str = 'seeds') -> str:
        return f"((1.5*{seeds_var}[{state_idx}]) / {h_var})"

class ContinuousMethod(DiscretizationMethod):
    """Strategy for continuous systems (RMS Small Signal). Does not discretize."""
    __slots__ = ()

    def discretize(self, state_idx: int, h_var: str = 'h', history_idx: int | None = None) -> str:
        return f"dx[{state_idx}]"

    def discretize_dot(self, state_idx: int, h_var: str = 'h', seeds_var: str = 'seeds') -> str:
        return "0.0"

# ==============================================================================
# 2. CSE (Common Subexpression Elimination) Analyzer (large systems)
# ==============================================================================
class SubexpressionAnalyzer:
    """
    Find and catalog subexpressions that appear multiple times.
    OPTIMIZED: Uses memoization for complexity calc and string generation.
    """
    __slots__ = ['threshold', 'expr_counts', 'expr_objects', 'expr_complexity', 'memo_complexity', 'memo_canonical',
                 'visited_traversal']

    def __init__(self, threshold: int = 2)-> None:
        self.threshold: int = threshold
        self.expr_counts: Dict[str, int] = dict()
        self.expr_objects: Dict[str, Expr] = dict()
        self.expr_complexity: Dict[str, int] = dict()

        # Caches
        self.memo_complexity: Dict[int, int] = dict()
        self.memo_canonical: Dict[int, str] = dict()
        self.visited_traversal: Set[int] = set()

    def analyze(self, equations: List[Expr]) -> Dict[str, str]:
        # Reset caches
        self.expr_counts.clear()
        self.expr_objects.clear()
        self.expr_complexity.clear()
        self.memo_complexity.clear()
        self.memo_canonical.clear()

        self.visited_traversal.clear()

        for eq in equations:
            self._count_subexpressions(eq)

        candidates: List[Tuple[int, str]] = list()
        for expr_hash, count in self.expr_counts.items():
            if count >= self.threshold:
                complexity = self.expr_complexity[expr_hash]
                benefit = count * complexity
                candidates.append((benefit, expr_hash))

        candidates.sort(reverse=True)
        temp_vars: Dict[str, str] = dict()
        for i, (_, expr_hash) in enumerate(candidates):
            temp_vars[expr_hash] = f"_t{i}"
        return temp_vars

    def emit_ordered_assignments(self,
                                 equation: Expr,
                                 compiler_names_dict: Dict[int, str],
                                 reserved_names: Tuple[str, ...] = ()) -> Tuple[List[str], Dict[int, str]]:
        """Emit one pure scalar expression as ordered, reusable assignments.

        This path follows node identity in postorder, then reuses only identical
        emitted operations with already bound children. It neither hashes nor
        sorts operands. Each caller resets the plan before the next output write.
        Unsupported nodes, stochastic functions or effectful binding syntax keep
        the original inline emission for the complete equation.

        :param equation: Existing expression graph, including cloned subexpressions.
        :param compiler_names_dict: Variable UID to slot or scalar alias binding.
        :param reserved_names: All generated function arguments and other reserved locals.
        :return: Indented assignments and node identity to scalar temporary lookup;
            both are empty when the original inline path is required.
        """
        # Discovery is bounded by unique node identities; the cardinality is not
        # known until this walk completes. A fresh plan cannot cross output writes.
        self.visited_traversal.clear()
        pending: List[Tuple[Expr, bool]] = list(((equation, False),))
        ordered: List[Expr] = list()
        binding_names: Set[str] = set(reserved_names)
        node: Expr
        ready: bool
        binding: str | None
        parsed_binding: ast.expr
        binding_node: ast.AST
        # Aliases are declared for the complete compiled batch before any root.
        # A temporary must not overwrite a name read only by a later equation.
        for binding in compiler_names_dict.values():
            try:
                parsed_binding = ast.parse(binding, mode="eval").body
            except SyntaxError:
                return list(), dict()
            for binding_node in ast.walk(parsed_binding):
                if isinstance(binding_node, ast.Name):
                    binding_names.add(binding_node.id)
                else:
                    pass
        while pending:
            node, ready = pending.pop()
            if ready:
                ordered.append(node)
            elif id(node) not in self.visited_traversal:
                self.visited_traversal.add(id(node))
                if isinstance(node, Var):
                    binding = compiler_names_dict.get(node.uid, None)
                    if binding is None:
                        if node.name in {"time", "glob_time"}:
                            binding = "glob_time"
                        else:
                            return list(), dict()
                    else:
                        pass
                    # Runtime arrays are float vectors and aliases are scalars.
                    # A caller-supplied call/expression must retain its original
                    # evaluation multiplicity, even without a symbolic rand node.
                    try:
                        parsed_binding = ast.parse(binding, mode="eval").body
                    except SyntaxError:
                        return list(), dict()
                    if isinstance(parsed_binding, ast.Name):
                        binding_names.add(parsed_binding.id)
                    elif (isinstance(parsed_binding, ast.Subscript)
                          and isinstance(parsed_binding.value, ast.Name)
                          and isinstance(parsed_binding.slice, ast.Constant)
                          and isinstance(parsed_binding.slice.value, int)):
                        binding_names.add(parsed_binding.value.id)
                    else:
                        return list(), dict()
                elif isinstance(node, Const):
                    pass
                elif isinstance(node, BinOp) and node.op in {"+", "-", "*", "/", "**"}:
                    pending.append((node, True))
                    pending.append((node.right, False))
                    pending.append((node.left, False))
                elif isinstance(node, UnOp) and node.op == "-":
                    pending.append((node, True))
                    pending.append((node.operand, False))
                elif (isinstance(node, Func) and node.op in {
                        "sin", "cos", "tan", "exp", "log", "log10", "sqrt",
                        "asin", "acos", "atan", "sinh", "cosh", "tanh",
                        "floor", "ceil", "round", "real", "imag", "conj",
                        "angle", "abs", "heaviside"}):
                    pending.append((node, True))
                    pending.append((node.arg, False))
                elif isinstance(node, Func2) and node.name in {"atan2", "min", "max"}:
                    pending.append((node, True))
                    pending.append((node.arg2, False))
                    pending.append((node.arg1, False))
                else:
                    return list(), dict()
            else:
                pass

        # Retain exact emitted operation order and literal precision. The lookup
        # key is the actual shallow source, never a display name or lossy hash.
        prefix: str = "_vg_shared_"
        name: str
        while any(name.startswith(prefix) for name in binding_names):
            prefix += "_"
        assignments: List[str] = [""] * len(ordered)
        expression_names: Dict[int, str] = dict()
        source_names: Dict[str, str] = dict()
        source: str
        temporary: str | None
        assignment_count: int = 0
        for node in ordered:
            source = expression2numba(node, compiler_names_dict, 0, expression_names)
            temporary = source_names.get(source, None)
            if temporary is None:
                temporary = f"{prefix}{assignment_count}"
                assignments[assignment_count] = f"    {temporary} = {source}"
                assignment_count += 1
                source_names[source] = temporary
            else:
                pass
            expression_names[id(node)] = temporary
        return assignments[:assignment_count], expression_names

    def _count_subexpressions(self, node: Expr)->None:
        if isinstance(node, (Const, Var)):
            return

        complexity = self._calculate_complexity(node)

        if complexity > 1:
            expr_hash = self.hash_expr(node)
            self.expr_counts[expr_hash] = self.expr_counts.get(expr_hash, 0) + 1
            self.expr_objects[expr_hash] = node
            self.expr_complexity[expr_hash] = complexity
        else:
            pass

        if id(node) in self.visited_traversal:
            return
        self.visited_traversal.add(id(node))

        if isinstance(node, BinOp):
            self._count_subexpressions(node.left)
            self._count_subexpressions(node.right)
        elif isinstance(node, UnOp):
            self._count_subexpressions(node.operand)
        elif isinstance(node, Func):
            self._count_subexpressions(node.arg)

    def _calculate_complexity(self, node: Expr) -> int:
        if id(node) in self.memo_complexity:
            return self.memo_complexity[id(node)]

        res: int
        if isinstance(node, (Const, Var)):
            res = 0
        elif isinstance(node, BinOp):
            op_cost = 2 if node.op in ['*', '/', '**'] else 1
            res = op_cost + self._calculate_complexity(node.left) + \
                  self._calculate_complexity(node.right)
        elif isinstance(node, UnOp):
            res = 1 + self._calculate_complexity(node.operand)
        elif isinstance(node, Func):
            res = 5 + self._calculate_complexity(node.arg)
        else:
            res = 1

        self.memo_complexity[id(node)] = res
        return res

    def hash_expr(self, node: Expr) -> str:
        canonical = self._expr_to_canonical_string(node)
        return _stable_digest(canonical, length=12)

    def _expr_to_canonical_string(self, node: Expr) -> str:
        if id(node) in self.memo_canonical:
            return self.memo_canonical[id(node)]

        res: str
        if isinstance(node, Const):
            res = f"C{node.value}"
        elif isinstance(node, Var):
            if node.base_var is not None:
                res = f"D{node.base_var.uid}"
            else:
                res = f"V{node.uid}"
        elif isinstance(node, BinOp):
            left = self._expr_to_canonical_string(node.left)
            right = self._expr_to_canonical_string(node.right)
            if node.op in ['+', '*']:
                if left > right:
                    left, right = right, left
                else:
                    pass
            else:
                pass
            res = f"({left}{node.op}{right})"
        elif isinstance(node, UnOp):
            operand = self._expr_to_canonical_string(node.operand)
            res = f"{node.op}{operand}"
        elif isinstance(node, Func):
            res = f"{node.op}({self._expr_to_canonical_string(node.arg)})"
        else:
            res = str(node)

        self.memo_canonical[id(node)] = res
        return res


# ==============================================================================
# 3. Conversion to string based on visitor pattern (sequentiality)
# ==============================================================================

class SymbolicToPythonVisitor:
    __slots__ = ['var_map', 'param_map', 'method', 'diff_var_map', 'cse_map', 'analyzer', 'in_cse_def', '_str_cache']

    OP_PRECEDENCE = {'+': 10, '-': 10, '*': 20, '/': 20, '**': 30}

    def __init__(self, var_map: Dict[int, int], param_map: Dict[int, int], method: DiscretizationMethod,
                 diff_var_map: Dict[int, int] | None = None) -> None:
        self.var_map = var_map
        self.param_map = param_map or dict()
        self.method = method
        self.diff_var_map = diff_var_map or dict()
        self.cse_map: Dict[str, str] = dict()
        self.analyzer = None
        self.in_cse_def = False
        self._str_cache: Dict[Tuple[int, int], str] = dict()

    def _prec(self, node: Expr) -> int:
        """Return precedence of a node. Non-operators get 'infinite' precedence."""
        # BinOp nodes define precedence; everything else we treat as atomic.
        if isinstance(node, BinOp):
            return self.OP_PRECEDENCE.get(node.op, 0)
        return 10 ** 9

    def _maybe_parenthesize(self,
                            code: str,
                            child_node: Expr,
                            parent_op: str,
                            parent_prec: int,
                            side: str) -> str:
        """
        Decide whether to wrap child expression in parentheses.

        Rules:
          - If child's precedence < parent's precedence => need parentheses.
          - If child's precedence == parent's precedence:
              * For non-associative ops (-, /): right child must be parenthesized.
              * For exponent (**), which is right-associative: left child must be parenthesized when equal precedence.
              * For associative ops (+, *): no parentheses needed.
        """
        child_prec = self._prec(child_node)

        # Lower precedence always needs parentheses
        if child_prec < parent_prec:
            return f"({code})"

        # Equal precedence: depends on operator and side
        if child_prec == parent_prec:
            if parent_op in ('-', '/'):
                # a - (b - c) and a / (b / c) must keep parentheses on right
                if side == 'right':
                    return f"({code})"
            if parent_op == '**':
                # (a ** b) ** c must keep parentheses on left (since ** is right-associative)
                if side == 'left':
                    return f"({code})"
            # + and * are associative enough here -> no parentheses
        return code

    def visit(self, node: Expr, precedence: int = 0) -> str:
        """
        Dispatches node processing using explicit type matching to avoid reflection.

        :param node: The symbolic expression node to visit.
        :type node: Expr
        :param precedence: Operator precedence level.
        :type precedence: int
        :return: Python code string representation of the node.
        :rtype: str
        """
        # 1. CSE (Common Subexpression Elimination) Check
        if self.analyzer is not None and self.cse_map is not None and not self.in_cse_def:
            if not isinstance(node, (Var, Const)):
                h: str = self.analyzer.hash_expr(node)
                if h in self.cse_map:
                    return self.cse_map[h]
                else:
                    pass
            else:
                pass
        else:
            pass

        # 2. Cache Check
        cache_key: Tuple[int, int] = (id(node), precedence)
        if cache_key in self._str_cache:
            return self._str_cache[cache_key]
        else:
            pass

        result: str = ""

        match node:
            case BinOp():
                result = self.visit_binop(node, precedence)
            case UnOp():
                result = self.visit_unop(node, precedence)
            case Const():
                result = self.visit_const(node, precedence)
            case Var():
                result = self.visit_var(node, precedence)
            case Func():
                result = self.visit_func(node, precedence)
            case _:
                result = self.generic_visit(node, precedence)

        # 5. Store and Return
        self._str_cache[cache_key] = result
        return result

    def generic_visit(self, node: Expr, _: int) -> str:
        raise NotImplementedError(f"Node not supported: {type(node)}")

    # def visit_binop(self, node: BinOp, prec: int) -> str:
    #     curr_prec = self.OP_PRECEDENCE.get(node.op, 0)
    #     l = self.visit(node.left, curr_prec)
    #     r = self.visit(node.right, curr_prec)
    #     code = f"{l} {node.op} {r}"
    #     return f"({code})" if curr_prec < prec else code

    def visit_binop(self, node: 'BinOp', prec: int) -> str:
        """
        Emit Python code for a binary operation with correct parentheses.

        Important:
        - We do NOT just compare prec numerically in a naive way; we also handle
          associativity for '-', '/', and '**' to avoid sign/structure bugs.
        """
        op = node.op
        curr_prec = self.OP_PRECEDENCE.get(op, 0)

        # Visit children using current operator precedence as the "context"
        l_code = self.visit(node.left, curr_prec)
        r_code = self.visit(node.right, curr_prec)

        # Parenthesize children if needed (precedence + associativity)
        l_code = self._maybe_parenthesize(l_code, node.left, op, curr_prec, side='left')
        r_code = self._maybe_parenthesize(r_code, node.right, op, curr_prec, side='right')

        code = f"{l_code} {op} {r_code}"

        # If parent context has higher precedence, wrap the whole expression
        return f"({code})" if curr_prec < prec else code

    def visit_unop(self, node: UnOp, _precedence: int) -> str:
        return f"{node.op}{self.visit(node.operand, 100)}"

    def visit_const(self, node: Const, _precedence: int) -> str:
        return str(node.value)

    def visit_var(self, node: Var, prec: int) -> str:
        if node.uid in self.var_map:
            return f"states[{self.var_map[node.uid]}]"
        else:
            pass

        if node.uid in self.param_map:
            return f"params[{self.param_map[node.uid]}]"
        else:
            pass

        if node.base_var is not None:
            return self.visit_diffvar(node, prec)
        else:
            pass

        if node.name == 'h':
            return 'h'

        raise ValueError(f"Variable '{node.name}' (UID: {node.uid}) Not mapped in compiler.")

    def visit_diffvar(self, node: Var, prec: int) -> str:
        # If base_var is also a DiffVar, recursively discretize it
        if node.base_var.base_var is not None:
            # Recursively get discretized base (e.g., dx from x)
            base_discretized = self.visit_diffvar(node.base_var, prec)
            # Apply discretization to the discretized base using d_history
            # For Backward Euler: d2x = (dx - dx_history) / h
            # Use base_var's origin since base_var is itself a DiffVar
            base_idx = self.var_map[node.base_var.origin_var.uid]
            term = f"(({base_discretized} - d_history[{base_idx}]) / h)"
        else:
            # Base is a regular state variable
            base_uid = node.base_var.uid
            if base_uid not in self.var_map:
                raise ValueError(f"Base var '{node.base_var.name}' (UID: {base_uid})"
                                 f" for DiffVar does not exist in states.")
            state_idx = self.var_map[base_uid]
            term = self.method.discretize(state_idx, history_idx=self.diff_var_map.get(base_uid, state_idx))
        return f"({term})" if prec > 10 else term

    def visit_func(self, node: Func, _precedence: int) -> str:
        arg = self.visit(node.arg, 0)

        op = node.op
        if op == 'heaviside':
            return f"_heaviside({arg})"
        if op == 'abs':
            return f"np.abs({arg})"

        return f"np.{op}({arg})"


class RuntimeParameterToPythonVisitor(SymbolicToPythonVisitor):
    """Emit expressions for an ordered runtime-parameter update kernel."""

    __slots__ = ["runtime_map", "fixed_map", "time_uids"]

    def __init__(
            self,
            runtime_map: Dict[int, int],
            fixed_map: Dict[int, int],
            time_uids: Set[int],
    ) -> None:
        """Initialize the runtime expression visitor.

        :param runtime_map: Runtime-vector indices keyed by variable UID.
        :param fixed_map: Frozen-binding indices keyed by variable UID.
        :param time_uids: Variable UIDs that represent simulation time.
        :return: None.
        """
        super().__init__(
            var_map=dict(),
            param_map=dict(),
            method=ContinuousMethod(),
            diff_var_map=dict(),
        )
        self.runtime_map: Dict[int, int] = runtime_map
        self.fixed_map: Dict[int, int] = fixed_map
        self.time_uids: Set[int] = time_uids

    def visit_var(self, node: Var, prec: int) -> str:
        """Return the direct array access for one runtime expression variable.

        Unknown variables preserve the interpreted evaluator's zero fallback.

        :param node: Symbolic variable to translate.
        :param prec: Parent expression precedence.
        :return: Python source fragment for the variable value.
        """
        runtime_idx: int | None
        fixed_idx: int | None

        if node.uid in self.time_uids or node.name in {"time", "glob_time"}:
            return "tm"
        else:
            pass

        runtime_idx = self.runtime_map.get(node.uid, None)
        if runtime_idx is not None:
            return f"runtime_values[{runtime_idx}]"
        else:
            pass

        fixed_idx = self.fixed_map.get(node.uid, None)
        if fixed_idx is not None:
            return f"fixed_values[{fixed_idx}]"
        else:
            return "0.0"


class RuntimeParameterCompiler:
    """Compile sequential runtime-parameter expressions into one eager kernel."""

    __slots__ = ["_visitor"]

    def __init__(
            self,
            runtime_map: Dict[int, int],
            fixed_map: Dict[int, int],
            time_uids: Set[int],
    ) -> None:
        """Initialize the runtime parameter compiler.

        :param runtime_map: Runtime-vector indices keyed by variable UID.
        :param fixed_map: Frozen-binding indices keyed by variable UID.
        :param time_uids: Variable UIDs that represent simulation time.
        :return: None.
        """
        self._visitor: RuntimeParameterToPythonVisitor = RuntimeParameterToPythonVisitor(
            runtime_map=runtime_map,
            fixed_map=fixed_map,
            time_uids=time_uids,
        )

    def compile(self, equations: List[Any], output_offset: int = 0) -> Callable:
        """Compile ordered expressions into an eagerly specialized Numba kernel.

        Each assignment is emitted in declaration order. Consequently, an
        expression that reads an earlier runtime parameter observes its value
        from the current update sweep, while later and self references retain
        their incoming value.

        :param equations: Ordered continuous runtime equations.
        :param output_offset: First runtime-vector index written by the kernel.
        :return: Eagerly compiled in-place runtime update function.
        """
        source_lines: List[str] = list()
        equation_index: int
        expression: Any
        expression_code: str
        full_source: str
        python_function: Callable
        signature_tpe: object

        source_lines.append("def runtime_parameter_update(runtime_values, fixed_values, tm):")
        for equation_index, expression in enumerate(equations):
            # CSE is deliberately local to one expression so generated reads
            # cannot move ahead of preceding runtime-vector writes.
            self._visitor._str_cache = dict()
            if isinstance(expression, Const) and expression.value is None:
                expression_code = "0.0"
            elif isinstance(expression, Expr):
                expression_code = self._visitor.visit(expression)
            else:
                expression_code = repr(float(expression))
            source_lines.append(
                f"    runtime_values[{output_offset + equation_index}] = {expression_code}"
            )

        if len(equations) == 0:
            source_lines.append("    pass")
        else:
            pass

        full_source = "\n".join(source_lines)
        python_function = _compile_to_file(full_source, "runtime_parameter_update")
        signature_tpe = types.void(
            types.float64[::1],
            types.float64[::1],
            types.float64,
        )
        return njit(signature_tpe, cache=True, fastmath=True)(python_function)


class ProceduralExpressionCompiler:
    """Compile and cache procedural expressions for one finalized problem."""

    __slots__ = [
        "_state_map",
        "_runtime_map",
        "_constant_map",
        "_global_time_uid",
        "_fixed_values",
        "_kernel_cache",
    ]

    def __init__(
            self,
            state_map: Dict[int, int],
            runtime_map: Dict[int, int],
            constant_map: Dict[int, int],
            constant_values: List[Const],
            global_time_uid: int,
    ) -> None:
        """Initialize one problem-local procedural expression compiler.

        :param state_map: State and algebraic indexes keyed by variable UID.
        :param runtime_map: Mutable runtime-parameter indexes keyed by UID.
        :param constant_map: Constant-parameter indexes keyed by UID.
        :param constant_values: Constant values in problem order.
        :param global_time_uid: Canonical target-boundary time UID.
        :return: None.
        """
        self._state_map: Dict[int, int] = dict(state_map)
        self._runtime_map: Dict[int, int] = dict(runtime_map)
        self._constant_map: Dict[int, int] = dict(constant_map)
        self._global_time_uid: int = int(global_time_uid)
        self._fixed_values: np.ndarray = np.asarray(
            [float(constant.value) for constant in constant_values],
            dtype=np.float64,
        )
        self._kernel_cache: Dict[str, Callable[..., float]] = dict()

    @property
    def fixed_values(self) -> np.ndarray:
        """Return the immutable constant vector used by compiled kernels.

        :return: Problem-local constant values.
        """
        return self._fixed_values

    def compile(self, expression: Expr) -> Callable[..., float]:
        """Compile one expression with accepted-state boundary semantics.

        Structurally identical generated expressions share one eager Numba
        dispatcher inside the problem, including across different logic entries.

        :param expression: Normalized procedural expression.
        :return: Eagerly compiled scalar evaluator.
        """
        expression_code: str = self.render(expression)
        cached_kernel: Callable[..., float] | None = self._kernel_cache.get(
            expression_code,
            None,
        )
        if cached_kernel is not None:
            return cached_kernel
        else:
            pass

        function_source: str = (
            "def procedural_expression(states, runtime_values, fixed_values, sample_time, target_time):\n"
            + f"    return float({expression_code})"
        )
        python_function: Callable[..., float] = _compile_to_file(
            function_source,
            "procedural_expression",
        )
        signature_tpe: object = types.float64(
            types.float64[::1],
            types.float64[::1],
            types.float64[::1],
            types.float64,
            types.float64,
        )
        compiled_kernel: Callable[..., float] = njit(
            signature_tpe,
            cache=True,
            fastmath=False,
        )(python_function)
        self._kernel_cache[expression_code] = compiled_kernel
        return compiled_kernel

    def render(self, expression: Expr) -> str:
        """Render one expression for inclusion in a fused procedural kernel.

        The generated source uses the same state, runtime, constant and time
        mapping as the standalone procedural-expression kernels.  Keeping one
        mapping implementation prevents the fused and fallback paths from
        assigning different numerical meanings to the same symbolic variable.

        :param expression: Normalized procedural expression.
        :return: Numba-compatible scalar Python expression.
        """
        compiler_names: Dict[int, str] = dict()
        expression_var: Var

        # Resolve every symbolic leaf to the arrays owned by the runtime problem.
        for expression_var in expression.get_vars():
            if expression_var.name == "glob_time" or expression_var.uid == self._global_time_uid:
                compiler_names[expression_var.uid] = "target_time"
            elif expression_var.name == "time":
                compiler_names[expression_var.uid] = "sample_time"
            elif expression_var.uid in self._state_map:
                compiler_names[expression_var.uid] = f"states[{self._state_map[expression_var.uid]}]"
            elif expression_var.uid in self._runtime_map:
                compiler_names[expression_var.uid] = f"runtime_values[{self._runtime_map[expression_var.uid]}]"
            elif expression_var.uid in self._constant_map:
                compiler_names[expression_var.uid] = f"fixed_values[{self._constant_map[expression_var.uid]}]"
            else:
                raise KeyError(
                    f"Unknown procedural variable '{expression_var.name}' "
                    + f"(uid={expression_var.uid})."
                )

        return expression2numba(
            expr=expression,
            compiler_names_dict=compiler_names,
        )

    def compile_boundary_kernel(self, function_source: str) -> Callable[..., int]:
        """Compile one model-specific procedural boundary-update function eagerly.

        :param function_source: Complete source defining ``procedural_boundary_update``.
        :return: Eager Numba kernel returning zero or a one-based logic error index.
        """
        python_function: Callable[..., int] = _compile_to_file(
            function_source,
            "procedural_boundary_update",
        )
        signature_tpe: object = types.int64(
            types.float64[::1],
            types.float64[::1],
            types.float64[::1],
            types.float64,
            types.float64,
            types.float64[::1],
        )
        return njit(
            signature_tpe,
            cache=True,
            fastmath=False,
        )(python_function)

# =============================================================================================
# 4. Solution for large-scale algebraic frameworks, based on differential automatic composition
# =============================================================================================

class ADVisitor(SymbolicToPythonVisitor):
    __slots__ = ['seeds_var', 'active_indices', 'cse_has_dot']

    def __init__(self,
                 var_map: Dict[int, int],
                 param_map: Dict[int, int],
                 method: DiscretizationMethod,
                 diff_var_map: Dict[int, int] | None = None,
                 seeds_var: str = 'seeds',
                 active_indices: set | None = None) -> None:
        super().__init__(var_map, param_map, method, diff_var_map=diff_var_map)
        self.seeds_var = seeds_var
        self.active_indices = active_indices
        self.cse_has_dot: Set[str] = set()
        self._str_cache: Dict[Tuple[int, int], Tuple[str, str]] = dict()

    def generic_visit(self, node: Expr, _: int) -> Tuple[str, str]:
        raise NotImplementedError(f"Node not supported in AD: {type(node)}")

    def visit(self, node: Expr, precedence: int = 0) -> Tuple[str, str]:
        """
        Dispatches node processing for Automatic Differentiation using explicit type matching.
        """
        # 1. CSE Check
        if self.analyzer is not None and self.cse_map is not None and not self.in_cse_def:
            if not isinstance(node, (Var, Const)):
                h_hash: str = self.analyzer.hash_expr(node)
                if h_hash in self.cse_map:
                    var_name = self.cse_map[h_hash]
                    dot_name = f"{var_name}_d" if var_name in self.cse_has_dot else "0.0"
                    return var_name, dot_name
                else:
                    pass
            else:
                pass
        else:
            pass

        # 2. Cache Check (Critical for AD speed)
        cache_key: Tuple[int, int] = (id(node), precedence)
        if cache_key in self._str_cache:
            return self._str_cache[cache_key]
        else:
            pass

        res: Tuple[str, str] = ("", "")

        match node:
            case BinOp():
                res = self.visit_binop(node, precedence)
            case UnOp():
                res = self.visit_unop(node, precedence)
            case Const():
                res = self.visit_const(node, precedence)
            case Var():
                res = self.visit_var(node, precedence)
            case Func():
                res = self.visit_func(node, precedence)
            case _:
                # Fallback for generic or unsupported nodes
                res = self.generic_visit(node, precedence)

        # 5. Store and Return
        self._str_cache[cache_key] = res
        return res

    def visit_const(self, node: Const, _: int) -> Tuple[str, str]:
        return str(node.value), "0.0"

    def visit_var(self, node: Var, _precedence: int) -> Tuple[str, str]:
        # 1. Standard mapping for states
        if node.uid in self.var_map:
            i: int = self.var_map[node.uid]
            val: str = f"states[{i}]"

            # Seed value for the specific column being differentiated
            if self.active_indices is not None:
                seed_val: str = "1.0" if i in self.active_indices else "0.0"
            else:
                seed_val: str = f"{self.seeds_var}[{i}]"
            return val, seed_val
        else:
            pass

        # 2. Parameter mapping (Parameters have a seed of 0.0)
        if node.uid in self.param_map:
            return f"params[{self.param_map[node.uid]}]", "0.0"
        else:
            pass

        if node.base_var is not None:
            return self.visit_diffvar(node, 100)
        else:
            pass

        raise ValueError(f"Var '{node.name}' (UID: {node.uid}) Not mapped in ADVisitor.")

    def visit_diffvar(self, node: Var, prec: int) -> Tuple[str, str]:
        # If base_var is also a DiffVar, recursively discretize it
        if node.base_var.base_var is not None:
            # Recursively get discretized base (value, dot)
            base_val, base_dot = self.visit_diffvar(node.base_var, prec)
            # Use base_var's origin since base_var is itself a DiffVar
            base_idx = self.var_map[node.base_var.origin_var.uid]
            
            if isinstance(self.method, BackwardEulerMethod):
                # d2x = (dx - dx_history) / h
                val = f"(({base_val} - d_history[{base_idx}]) / h)"
                dot = "0.0" if base_dot == "0.0" else f"({base_dot}/h)"
            elif isinstance(self.method, TrapezoidalMethod):
                # d2x = (2/h)*(dx - dx_history) - d2x_history
                val = f"((2.0/h)*({base_val} - d_history[{base_idx}]) - d2_history[{base_idx}])"
                dot = "0.0" if base_dot == "0.0" else f"(2.0*{base_dot}/h)"
            elif isinstance(self.method, BDF2Method):
                # Not implemented for nested diff vars with BDF2
                raise NotImplementedError("Nested DiffVar not supported with BDF2")
            else:
                raise NotImplementedError
        else:
            # Base is a regular state variable
            base_uid = node.base_var.uid
            i = self.var_map[base_uid]
            if self.active_indices is not None:
                seed = "1.0" if i in self.active_indices else "0.0"
            else:
                seed = f"{self.seeds_var}[{i}]"

            if isinstance(self.method, BackwardEulerMethod):
                val = f"((states[{i}] - history[{i}]) / h)"
                dot = "0.0" if seed == "0.0" else ("(1.0/h)" if seed == "1.0" else f"({seed}/h)")
            elif isinstance(self.method, TrapezoidalMethod):
                diff_idx = self.diff_var_map.get(base_uid, i)
                val = f"((2.0/h)*(states[{i}] - history[{i}]) - d_history[{diff_idx}])"
                dot = "0.0" if seed == "0.0" else ("(2.0/h)" if seed == "1.0" else f"(2.0*{seed}/h)")
            elif isinstance(self.method, BDF2Method):
                val = f"((1.5*states[{i}] - 2.0*history[{i}] + 0.5*history2[{i}]) / h)"
                dot = "0.0" if seed == "0.0" else ("(1.5/h)" if seed == "1.0" else f"(1.5*{seed}/h)")
            else:
                raise NotImplementedError
        
        return (f"({val})", f"({dot})") if prec > 10 else (val, dot)

    def visit_binop(self, node: BinOp, prec: int) -> Tuple[str, str]:
        curr_prec = self.OP_PRECEDENCE.get(node.op, 0)
        lv, ld = self.visit(node.left, curr_prec)
        rv, rd = self.visit(node.right, curr_prec)
        op = node.op

        v = ""
        if op == '+':
            v = rv if _is_zero(lv) else (lv if _is_zero(rv) else f"{lv} + {rv}")
        elif op == '-':
            v = lv if _is_zero(rv) else (f"-{rv}" if _is_zero(lv) else f"{lv} - {rv}")
        elif op == '*':
            v = "0.0" if (_is_zero(lv) or _is_zero(rv)) else (
                rv if _is_one(lv) else (lv if _is_one(rv) else f"{lv} * {rv}"))
        elif op == '/':
            v = "0.0" if _is_zero(lv) else (lv if _is_one(rv) else f"{lv} / {rv}")
        elif op == '**':
            v = "1.0" if _is_zero(rv) else (lv if _is_one(rv) else (
                f"({lv})**({node.right.value})" if isinstance(node.right, Const) else f"({lv})**({rv})"))

        d = "0.0"
        if op == '+':
            d = rd if _is_zero(ld) else (ld if _is_zero(rd) else f"({ld} + {rd})")
        elif op == '-':
            d = f"(-{rd})" if _is_zero(ld) else (ld if _is_zero(rd) else f"({ld} - {rd})")
        elif op == '*':
            t1 = "0.0"
            if not _is_zero(ld): t1 = rv if _is_one(ld) else (ld if _is_one(rv) else f"({ld})*({rv})")
            t2 = "0.0"
            if not _is_zero(rd): t2 = lv if _is_one(rd) else (rd if _is_one(lv) else f"({lv})*({rd})")
            d = t2 if t1 == "0.0" else (t1 if t2 == "0.0" else f"({t1} + {t2})")
        elif op == '/':
            if _is_zero(lv):
                d = "0.0"
            elif _is_zero(ld) and _is_zero(rd):
                d = "0.0"
            elif _is_zero(rd):
                d = ld if _is_one(rv) else f"({ld}) / ({rv})"
            else:
                d = f"(({ld})*({rv}) - ({lv})*({rd})) / (({rv})*({rv}))"
        elif op == '**':
            if not (_is_zero(ld) and _is_zero(rd)):
                if isinstance(node.right, Const):
                    val = float(node.right.value)
                    if val == 1.0:
                        d = ld
                    elif val == 2.0:
                        d = f"2.0*({lv})*({ld})"
                    else:
                        d = f"({val})*(({lv})**({val - 1}))*({ld})"
                else:
                    d = f"(({v}) * ( ({rd})*np.log({lv}) + ({rv})*({ld})/({lv}) ))"

        return (f"({v})", f"({d})") if curr_prec < prec else (v, d)

    def visit_unop(self, node: UnOp, _: int) -> Tuple[str, str]:
        ov, od = self.visit(node.operand, 100)
        if _is_zero(od):
            s = f"{node.op}({ov})"
            if node.op == '+': s = ov
            return s, "0.0"
        if node.op == '+': return f"(+({ov}))", f"(+({od}))"
        if node.op == '-': return f"(-({ov}))", f"(-({od}))"
        raise NotImplementedError

    # def visit_func(self, node: Func, _: int) -> Tuple[str, str]:
    #     av, ad = self.visit(node.arg, 0)
    #     eps_str = "1e-15"
    #
    #     if _is_zero(ad):
    #         if node.op == 'heaviside': return f"_heaviside({av})", "0.0"
    #         if node.op == 'abs': return f"np.abs({av})", "0.0"
    #         return f"np.{node.op}({av})", "0.0"
    #
    #     if node.op == 'sin': return f"np.sin({av})", f"(np.cos({av})*({ad}))"
    #     if node.op == 'cos': return f"np.cos({av})", f"(-np.sin({av})*({ad}))"
    #
    #     if node.op == 'log':
    #         return f"np.log({av})", f"({ad})/({av} + {eps_str})"
    #     if node.op == 'sqrt':
    #         return f"np.sqrt({av})", f"0.5*({ad})/(np.sqrt({av}) + {eps_str})"
    #
    #     raise NotImplementedError(f"Function {node.op} not supported in AD")

    def visit_func(self, node: Func, _: int) -> Tuple[str, str]:
        av, ad = self.visit(node.arg, 0)
        eps_str = "1e-15"

        # Support non-smooth functions with zero AD derivative
        if node.op == 'heaviside':
            return f"_heaviside({av})", "0.0"

        if node.op == 'abs':
            if _is_zero(ad):
                return f"np.abs({av})", "0.0"
            return f"np.abs({av})", f"(np.sign({av})*({ad}))"

        if _is_zero(ad):
            return f"np.{node.op}({av})", "0.0"

        if node.op == 'sin':
            return f"np.sin({av})", f"(np.cos({av})*({ad}))"

        if node.op == 'cos':
            return f"np.cos({av})", f"(-np.sin({av})*({ad}))"

        if node.op == 'exp':
            return f"np.exp({av})", f"(np.exp({av})*({ad}))"

        if node.op == 'log':
            return f"np.log({av})", f"({ad})/({av} + {eps_str})"

        if node.op == 'sqrt':
            return f"np.sqrt({av})", f"0.5*({ad})/(np.sqrt({av}) + {eps_str})"

        raise NotImplementedError(f"Function {node.op} not supported in AD")

# ==============================================================================
# 5. Compiler (sym-num)(discretized)
# ==============================================================================

class EquationCompiler:
    """Main interface for compiling symbolic equations into executable functions."""

    __slots__ = ['variables_objs', 'parameters_objs', 'diff_vars_objs', 'strategy', 'var_map', 'param_map', 'diff_var_map', 'visitor']

    METHODS = {
        DynamicIntegrationMethod.DaeTrapezoidal: TrapezoidalMethod(),
        DynamicIntegrationMethod.DaeBackEuler: BackwardEulerMethod(),
        DynamicIntegrationMethod.DaeBDF2: BDF2Method(),
        DynamicIntegrationMethod.DaeContinuous: ContinuousMethod()
    }

    def __init__(self,
                 variables: List[Var],
                 parameters: List[Var] | None = None,
                 diff_vars: List[Var] | None = None,
                 method: DynamicIntegrationMethod = DynamicIntegrationMethod.DaeTrapezoidal) -> None:
        self.variables_objs = variables
        self.parameters_objs = parameters if parameters is not None else list()
        self.diff_vars_objs = diff_vars if diff_vars is not None else list()

        if method not in self.METHODS:
            raise ValueError(f"Method '{method}' Unknown. Options: {list(self.METHODS.keys())}")

        self.strategy = self.METHODS[method]

        self.var_map = {v.uid: i for i, v in enumerate(self.variables_objs)}
        self.param_map = {p.uid: i for i, p in enumerate(self.parameters_objs)}
        self.diff_var_map = {
            diff_var.base_var.uid: i
            for i, diff_var in enumerate(self.diff_vars_objs)
            if getattr(diff_var, 'base_var', None) is not None
        }

        self.visitor = SymbolicToPythonVisitor(self.var_map, self.param_map, self.strategy, diff_var_map=self.diff_var_map)

    def compile(self, equations: List[Expr], func_name: str = "step_fn", use_cse: bool = True,
                offset: int = 0, inplace: bool = False) -> Callable:

        lines: List[str] = list()
        cache_key: str = _build_equation_compiler_residual_cache_key(
            equations,
            self.var_map,
            self.param_map,
            type(self.strategy).__name__,
            use_cse,
            offset,
            inplace,
            self.diff_var_map,
        )
        cache_entry: GeneratedKernelCacheEntry | None = GENERATED_KERNEL_CACHE.get_entry("residual", cache_key)

        if cache_entry is None:
            pass
        else:
            return cache_entry.get_python_function()

        canonical_func_name: str = f"eq_step_{cache_key[:16]}"

        # Header depends on mode
        if inplace:
            lines.append(f"def {canonical_func_name}(states, params, history, d_history, h, residuals, history2=None):")
        else:
            lines.append(f"def {canonical_func_name}(states, params, history, d_history, h, history2=None):")

        # --- CSE Block ---
        if use_cse:
            analyzer = SubexpressionAnalyzer()
            cse_map = analyzer.analyze(equations)
            self.visitor.analyzer = analyzer
            self.visitor.cse_map = cse_map
            self.visitor._str_cache = dict()

            if cse_map:
                sorted_cse = sorted(cse_map.items(), key=_get_cse_sort_key)
                for expr_hash, var_name in sorted_cse:
                    expr_obj = analyzer.expr_objects[expr_hash]
                    self.visitor.in_cse_def = True
                    expr_code = self.visitor.visit(expr_obj)
                    self.visitor.in_cse_def = False
                    lines.append(f"    {var_name} = {expr_code}")
            else:
                pass
        else:
            pass

        # --- Body ---
        if not inplace:
            lines.append(f"    residuals = np.zeros({len(equations)}, dtype=np.float64)")
        else:
            pass

        for i, eq in enumerate(equations):
            code = self.visitor.visit(eq)
            # Apply offset if inplace
            target_idx = i + offset if inplace else i
            lines.append(f"    residuals[{target_idx}] = {code}")

        if not inplace:
            lines.append("    return residuals")
        else:
            pass

        # Clean visitor
        self.visitor.cse_map = dict()
        self.visitor.analyzer = None
        self.visitor._str_cache = dict()

        full_source = "\n".join(lines)
        py_func: Callable = _compile_to_file(full_source, canonical_func_name)
        GENERATED_KERNEL_CACHE.set_entry("residual", cache_key, GeneratedKernelCacheEntry(py_func, None))
        return py_func

    def compile_ad_kernel(self, equations: List[Expr], func_name: str = "ad_step", use_cse: bool = True,
                          active_indices: set | None = None) -> Callable:

        adv = ADVisitor(self.var_map, self.param_map, self.strategy, diff_var_map=self.diff_var_map,
                        seeds_var='seeds', active_indices=active_indices)
        cache_key: str = _build_equation_compiler_ad_cache_key(
            equations,
            self.var_map,
            self.param_map,
            type(self.strategy).__name__,
            use_cse,
            active_indices,
            self.diff_var_map,
        )
        cache_entry: GeneratedKernelCacheEntry | None = GENERATED_KERNEL_CACHE.get_entry("ad", cache_key)

        if cache_entry is None:
            pass
        else:
            return cache_entry.get_python_function()

        canonical_func_name: str = f"eq_ad_{cache_key[:16]}"

        lines: List[str] = list()
        lines.append(f"def {canonical_func_name}(states, seeds, params, history, d_history, h, history2=None):")

        if use_cse:
            analyzer = SubexpressionAnalyzer()
            cse_map = analyzer.analyze(equations)
            adv.analyzer = analyzer
            adv.cse_map = cse_map
            adv._str_cache = dict()

            if cse_map:
                sorted_cse = sorted(cse_map.items(), key=_get_cse_sort_key)
                for expr_hash, var_name in sorted_cse:
                    expr_obj = analyzer.expr_objects[expr_hash]
                    adv.in_cse_def = True
                    expr_val, expr_dot = adv.visit(expr_obj)
                    adv.in_cse_def = False

                    lines.append(f"    {var_name} = {expr_val}")

                    if expr_dot != "0.0":
                        lines.append(f"    {var_name}_d = {expr_dot}")
                        adv.cse_has_dot.add(var_name)
                    else:
                        pass
            else:
                pass
        else:
            pass

        n: int = len(equations)  # RULE: Local type hint
        lines.append(f"    jvp = np.zeros({n}, dtype=np.float64)")

        for i, eq in enumerate(equations):
            val, dot = adv.visit(eq)
            if dot != "0.0":
                lines.append(f"    jvp[{i}] = {dot}")
            else:
                pass

        lines.append("    return jvp")

        adv.cse_map = dict()
        adv.analyzer = None
        adv._str_cache = dict()

        full_source: str = "\n".join(lines)
        py_func: Callable = _compile_to_file(full_source, canonical_func_name)
        GENERATED_KERNEL_CACHE.set_entry("ad", cache_key, GeneratedKernelCacheEntry(py_func, None))
        return py_func


# ==============================================================================
# 6. Matrix Vectorized Compiler (HPC Optimized - No Dictionaries)
# ==============================================================================

class MatrixVectorizedVisitor(SymbolicToPythonVisitor):
    """
    HPC-optimized visitor. Instead of performing dictionary lookups (slow),
    it accesses state variable indices directly from a mapping matrix (fast).
    Generates code such as: states[indices[:, 5]]
    """
    __slots__ = ['col_map']

    def __init__(self,
                 var_map: Dict[int, int],
                 param_map: Dict[int, int],
                 method: DiscretizationMethod,
                 col_map: Dict[int, int]) -> None:
        """Bind matrix gathers to declared runtime identities.

        :param var_map: Runtime UID to scalar-vector slot.
        :param param_map: Parameter UID to shared parameter slot.
        :param method: Existing derivative discretization strategy.
        :param col_map: Runtime UID to grouped gather column.
        :return: None.
        """
        super().__init__(var_map, param_map, method)
        self.col_map: Dict[int, int] = col_map

    def visit_var(self, node: Var, _precedence: int) -> str:
        """Emit a parameter or runtime gather before derivative fallback.

        :param node: Variable occurrence whose UID defines its identity.
        :param _precedence: Parent expression precedence.
        :return: Generated vector expression for the declared binding.
        """
        if node.uid in self.param_map:
            return f"params[{self.param_map[node.uid]}]"
        else:
            pass

        if node.uid in self.var_map:
            # Independent devices may share names; only UID identifies the
            # column retained by the structural grouping owner.
            col_idx: int = self.col_map[node.uid]
            return f"states[indices[:, {col_idx}]]"
        else:
            pass

        # EMT Support: If the node is a derivative, call visit_diffvar
        if node.base_var is not None:
            return self.visit_diffvar(node, 100)
        else:
            pass

        raise ValueError(f"Var '{node.name}' (UID: {node.uid}) Not mapped in matrix visitor.")

    def visit_diffvar(self, node: Var, prec: int) -> str:
        """Discretize a derivative with its existing origin/history semantics.

        :param node: Derivative occurrence with an explicitly declared base.
        :param prec: Parent precedence used to delimit the generated term.
        :return: Vector derivative expression for the selected method.
        """
        col_idx: int
        idx_access: str
        term: str
        # If base_var is also a DiffVar, recursively discretize it
        if node.base_var.base_var is not None:
            # Use base_var's origin for history lookup since base_var is a DiffVar
            base_origin_uid: int = node.base_var.origin_var.uid
            col_idx = self.col_map[base_origin_uid]
            idx_access = f"indices[:, {col_idx}]"
            
            # Recursively get discretized base
            base_discretized: str = self.visit_diffvar(node.base_var, prec)
            # Apply discretization using d_history
            if isinstance(self.method, BackwardEulerMethod):
                term = f"(({base_discretized} - d_history[{idx_access}]) / h)"
            elif isinstance(self.method, TrapezoidalMethod):
                term = f"((2.0/h)*({base_discretized} - d_history[{idx_access}]) - d2_history[{idx_access}])"
            else:
                raise NotImplementedError(f"Nested DiffVar not supported with {type(self.method)}")
        else:
            # Base is a regular state variable - use standard discretization
            # History belongs to the declared origin, regardless of its label.
            origin_uid: int = node.origin_var.uid
            col_idx = self.col_map[origin_uid]
            idx_access = f"indices[:, {col_idx}]"
            
            if isinstance(self.method, TrapezoidalMethod):
                term = f"((2.0/h) * (states[{idx_access}] - history[{idx_access}]) - d_history[{idx_access}])"
            elif isinstance(self.method, BackwardEulerMethod):
                term = f"((states[{idx_access}] - history[{idx_access}]) / h)"
            elif isinstance(self.method, BDF2Method):
                term = f"((1.5*states[{idx_access}] - 2.0*history[{idx_access}] + 0.5*history2[{idx_access}]) / h)"
            else:
                raise NotImplementedError(f"Method {type(self.method)} not supported in matrix vectorization.")

        return f"({term})" if prec > 10 else term


class MatrixVectorizedCompiler(EquationCompiler):
    """
    Compiler utilizing the Matrix Vectorized Visitor.
    Generates kernels that accept 'indices' as a 2D int32 array for batch processing.
    """
    __slots__ = []

    def compile_matrix_kernel(self, template_eq: Expr, func_name: str, template_vars: List[Var]) -> Callable:
        """Compile one grouped residual using the declared runtime UID slots.

        :param template_eq: Equation shared by the grouped batch rows.
        :param func_name: Requested name; canonical cache identity names the kernel.
        :param template_vars: Ordered runtime gathers supplied by structural grouping.
        :return: Python batch residual kernel, reused for equivalent bindings.
        """
        # 1. Create a deterministic column map (Var index within the kernel)
        col_map: Dict[int, int] = dict()
        i: int
        v: Var
        for i, v in enumerate(template_vars):
            target_uid: int = v.uid if v.uid in self.var_map or v.base_var is None else v.base_var.uid
            if target_uid not in col_map:
                col_map[target_uid] = i
            else:
                pass

        cache_key: str = _build_equation_compiler_matrix_cache_key(
            template_eq,
            self.var_map,
            self.param_map,
            type(self.strategy).__name__,
            col_map,
        )
        cache_entry: GeneratedKernelCacheEntry | None = GENERATED_KERNEL_CACHE.get_entry("matrix", cache_key)

        if cache_entry is None:
            pass
        else:
            return cache_entry.get_python_function()

        canonical_func_name: str = f"eq_matrix_{cache_key[:16]}"

        # 2. Generate source code using the Matrix Visitor
        visitor: MatrixVectorizedVisitor = MatrixVectorizedVisitor(self.var_map, self.param_map, self.strategy, col_map)
        rhs_code: str = visitor.visit(template_eq)

        # 3. Package into a function (indices is now a 2D int32 array)
        lines: List[str] = list()
        lines.append(f"def {canonical_func_name}(states, params, history, d_history, h, indices, history2=None):")
        lines.append(f"    # Vectorized Matrix Kernel (No Dicts)")
        lines.append(f"    residuals = {rhs_code}")
        lines.append(f"    return residuals")
        full_source: str = "\n".join(lines)

        # 4. Compile to file (enabling Numba's persistent cache)
        py_func: Callable = _compile_to_file(full_source, canonical_func_name)
        GENERATED_KERNEL_CACHE.set_entry("matrix", cache_key, GeneratedKernelCacheEntry(py_func, None))
        return py_func


class EagerKernelKind(Enum):
    """
    Enumeration of eager kernel application binary interfaces.

    The eager compiler needs an explicit kernel family because the Python source
    and the Numba signature differ between residual kernels, AD kernels and
    vectorized matrix kernels.
    """
    __slots__ = ()

    Residual = "residual"
    AutomaticDifferentiation = "automatic_differentiation"
    MatrixVectorized = "matrix_vectorized"


def _get_cse_sort_index(cse_item: Tuple[str, str]) -> int:
    """
    Return the numeric order of a generated CSE temporary.

    :param cse_item: Pair ``(expr_hash, temp_name)`` produced by the analyzer.
    :type cse_item: Tuple[str, str]
    :return: Numeric suffix of the temporary variable.
    :rtype: int
    """
    temp_name: str = cse_item[1]
    numeric_part: str = temp_name[2:]
    return int(numeric_part)


def _reset_symbolic_codegen_state(visitor: "SymbolicToPythonVisitor | ADVisitor") -> None:
    """
    Reset visitor caches before and after eager code generation.

    :param visitor: Symbolic or AD visitor instance.
    :type visitor: SymbolicToPythonVisitor | ADVisitor
    :return: None
    :rtype: None
    """
    visitor.cse_map = dict()
    visitor.analyzer = None
    visitor.in_cse_def = False
    visitor._str_cache = dict()

    if isinstance(visitor, ADVisitor):
        visitor.cse_has_dot = set()
    else:
        pass


class EagerEquationCompiler(EquationCompiler):
    """
    Strict eager compiler that emits in-place kernels with explicit signatures.

    The generated functions do not allocate or return temporary arrays. Instead,
    they receive a caller-provided ``data_out`` vector and write their results in
    place. This removes Numba's type inference cost at first call and reduces the
    runtime allocation pressure inside Newton iterations.
    """

    __slots__ = []

    def generate_signature(
            self,
            kernel_tpe: EagerKernelKind,
            n_variables: int,
            n_parameters: int,
            nnz: int,
            with_history2: bool = True,
    ) -> object:
        """
        Build the eager Numba signature for a generated kernel.

        :param kernel_tpe: Kernel family to be compiled eagerly.
        :type kernel_tpe: EagerKernelKind
        :param n_variables: Number of runtime variables of the DAE system.
        :type n_variables: int
        :param n_parameters: Number of parameters visible to the kernel.
        :type n_parameters: int
        :param nnz: Number of output values written by the kernel.
        :type nnz: int
        :param with_history2: Whether the generated ABI includes ``history2``.
        :type with_history2: bool
        :return: Numba eager signature object.
        :rtype: object
        """
        float64_vector_tpe: object = types.Array(types.float64, 1, "C")
        int32_matrix_tpe: object = types.Array(types.int32, 2, "C", readonly=True)

        if n_variables <= 0:
            raise ValueError("n_variables must be greater than zero")
        else:
            pass

        if n_parameters < 0:
            raise ValueError("n_parameters must be greater than or equal to zero")
        else:
            pass

        if nnz < 0:
            raise ValueError("nnz must be greater than or equal to zero")
        else:
            pass

        if with_history2:
            pass
        else:
            raise ValueError(
                "EagerEquationCompiler requires an explicit history2 array to keep a strict ABI."
            )

        signature_tpe: object
        if kernel_tpe == EagerKernelKind.Residual:
            signature_tpe = types.void(
                float64_vector_tpe,
                float64_vector_tpe,
                float64_vector_tpe,
                float64_vector_tpe,
                types.float64,
                float64_vector_tpe,
                float64_vector_tpe,
            )
        elif kernel_tpe == EagerKernelKind.AutomaticDifferentiation:
            signature_tpe = types.void(
                float64_vector_tpe,
                float64_vector_tpe,
                float64_vector_tpe,
                float64_vector_tpe,
                float64_vector_tpe,
                types.float64,
                float64_vector_tpe,
                float64_vector_tpe,
            )
        elif kernel_tpe == EagerKernelKind.MatrixVectorized:
            signature_tpe = types.void(
                float64_vector_tpe,
                float64_vector_tpe,
                float64_vector_tpe,
                float64_vector_tpe,
                types.float64,
                int32_matrix_tpe,
                float64_vector_tpe,
                float64_vector_tpe,
            )
        else:
            raise ValueError(f"Unsupported eager kernel kind: {kernel_tpe}")

        return signature_tpe

    def compile(
            self,
            equations: List[Expr],
            func_name: str = "step_fn",
            use_cse: bool = True,
            offset: int = 0,
            inplace: bool = True,
    ) -> Tuple[Callable, object]:
        """
        Compile residual equations into an in-place eager kernel.

        :param equations: Residual equations to be emitted.
        :type equations: List[Expr]
        :param func_name: Deterministic function name used in the source file.
        :type func_name: str
        :param use_cse: Whether to emit common subexpressions.
        :type use_cse: bool
        :param offset: Output offset inside ``data_out``.
        :type offset: int
        :param inplace: Compatibility argument that must stay ``True``.
        :type inplace: bool
        :return: Pair ``(python_function, eager_signature)``.
        :rtype: Tuple[Callable, object]
        """
        lines: List[str] = list()
        py_func: Callable
        signature_tpe: object
        full_source: str
        cache_key: str
        cache_entry: GeneratedKernelCacheEntry | None
        canonical_func_name: str
        cache_key: str
        cache_entry: GeneratedKernelCacheEntry | None
        canonical_func_name: str

        if inplace:
            pass
        else:
            raise ValueError("EagerEquationCompiler only supports inplace residual kernels")

        cache_key = _build_residual_codegen_cache_key(
            equations,
            self.var_map,
            self.param_map,
            type(self.strategy).__name__,
            use_cse,
            offset,
            len(self.variables_objs),
            len(self.parameters_objs),
            self.diff_var_map,
        )
        cache_entry = GENERATED_KERNEL_CACHE.get_entry("residual", cache_key)

        if cache_entry is None:
            pass
        else:
            return cache_entry.get_python_function(), cache_entry.get_signature_tpe()

        _reset_symbolic_codegen_state(self.visitor)
        canonical_func_name = f"eager_residual_{cache_key[:16]}"

        # The eager ABI receives an explicit output vector and writes residuals in place.
        lines.append(f"def {canonical_func_name}(states, params, history, d_history, h, data_out, history2):")

        # Common subexpressions are emitted first so the body performs direct writes only once.
        if use_cse:
            analyzer: SubexpressionAnalyzer = SubexpressionAnalyzer()
            cse_map: Dict[str, str] = analyzer.analyze(equations)
            sorted_cse: List[Tuple[str, str]] = sorted(cse_map.items(), key=_get_cse_sort_index)

            self.visitor.analyzer = analyzer
            self.visitor.cse_map = cse_map
            self.visitor._str_cache = dict()

            for expr_hash, var_name in sorted_cse:
                expr_obj: Expr = analyzer.expr_objects[expr_hash]
                expr_code: str

                self.visitor.in_cse_def = True
                expr_code = self.visitor.visit(expr_obj)
                self.visitor.in_cse_def = False
                lines.append(f"    {var_name} = {expr_code}")
        else:
            pass

        # Each equation writes directly into the preallocated output buffer.
        for i, eq in enumerate(equations):
            expr_code = self.visitor.visit(eq)
            lines.append(f"    data_out[{offset + i}] = {expr_code}")

        full_source = "\n".join(lines)
        py_func = _compile_to_file(full_source, canonical_func_name)
        signature_tpe = self.generate_signature(
            kernel_tpe=EagerKernelKind.Residual,
            n_variables=len(self.variables_objs),
            n_parameters=len(self.parameters_objs),
            nnz=offset + len(equations),
            with_history2=True,
        )

        _reset_symbolic_codegen_state(self.visitor)
        GENERATED_KERNEL_CACHE.set_entry("residual", cache_key, GeneratedKernelCacheEntry(py_func, signature_tpe))
        return py_func, signature_tpe

    def compile_ad_kernel(
            self,
            equations: List[Expr],
            func_name: str = "ad_step",
            use_cse: bool = True,
            active_indices: set | None = None,
    ) -> Tuple[Callable, object]:
        """
        Compile a sparse forward-mode AD kernel into an in-place eager function.

        :param equations: Residual equations to differentiate.
        :type equations: List[Expr]
        :param func_name: Deterministic function name used in the source file.
        :type func_name: str
        :param use_cse: Whether to emit common subexpressions.
        :type use_cse: bool
        :param active_indices: Colored column subset activated in the current JVP sweep.
        :type active_indices: set | None
        :return: Pair ``(python_function, eager_signature)``.
        :rtype: Tuple[Callable, object]
        """
        adv: ADVisitor = ADVisitor(
            self.var_map,
            self.param_map,
            self.strategy,
            diff_var_map=self.diff_var_map,
            seeds_var='seeds',
            active_indices=active_indices,
        )
        lines: List[str] = list()
        py_func: Callable
        signature_tpe: object
        full_source: str
        cache_key: str
        cache_entry: GeneratedKernelCacheEntry | None
        canonical_func_name: str

        cache_key = _build_ad_codegen_cache_key(
            equations,
            self.var_map,
            self.param_map,
            type(self.strategy).__name__,
            use_cse,
            active_indices,
            len(self.variables_objs),
            len(self.parameters_objs),
            self.diff_var_map,
        )
        cache_entry = GENERATED_KERNEL_CACHE.get_entry("ad", cache_key)

        if cache_entry is None:
            pass
        else:
            return cache_entry.get_python_function(), cache_entry.get_signature_tpe()

        _reset_symbolic_codegen_state(adv)
        canonical_func_name = f"eager_ad_{cache_key[:16]}"

        # The eager AD ABI also writes into a caller-owned buffer to avoid JVP allocations.
        lines.append(f"def {canonical_func_name}(states, seeds, params, history, d_history, h, data_out, history2):")

        # Emit CSE definitions first so both values and directional derivatives can be reused.
        if use_cse:
            analyzer = SubexpressionAnalyzer()
            cse_map = analyzer.analyze(equations)
            sorted_cse = sorted(cse_map.items(), key=_get_cse_sort_index)

            adv.analyzer = analyzer
            adv.cse_map = cse_map
            adv._str_cache = dict()

            for expr_hash, var_name in sorted_cse:
                expr_obj = analyzer.expr_objects[expr_hash]
                expr_val: str
                expr_dot: str

                adv.in_cse_def = True
                expr_val, expr_dot = adv.visit(expr_obj)
                adv.in_cse_def = False

                lines.append(f"    {var_name} = {expr_val}")

                if expr_dot != "0.0":
                    lines.append(f"    {var_name}_d = {expr_dot}")
                    adv.cse_has_dot.add(var_name)
                else:
                    pass
        else:
            pass

        # The JVP values are written directly in CSC scatter order by the caller later on.
        for i, eq in enumerate(equations):
            _value_code: str
            dot_code: str
            _value_code, dot_code = adv.visit(eq)

            if dot_code != "0.0":
                lines.append(f"    data_out[{i}] = {dot_code}")
            else:
                lines.append(f"    data_out[{i}] = 0.0")

        full_source = "\n".join(lines)
        py_func = _compile_to_file(full_source, canonical_func_name)
        signature_tpe = self.generate_signature(
            kernel_tpe=EagerKernelKind.AutomaticDifferentiation,
            n_variables=len(self.variables_objs),
            n_parameters=len(self.parameters_objs),
            nnz=len(equations),
            with_history2=True,
        )

        _reset_symbolic_codegen_state(adv)
        GENERATED_KERNEL_CACHE.set_entry("ad", cache_key, GeneratedKernelCacheEntry(py_func, signature_tpe))
        return py_func, signature_tpe

    def compile_matrix_kernel(
            self,
            template_eq: Expr,
            func_name: str,
            template_vars: List[Var],
    ) -> Tuple[Callable, object]:
        """
        Compile a vectorized matrix kernel into an in-place eager function.

        :param template_eq: Canonical template equation for a structural group.
        :type template_eq: Expr
        :param func_name: Deterministic function name used in the source file.
        :type func_name: str
        :param template_vars: Ordered runtime variables of the structural group.
        :type template_vars: List[Var]
        :return: Pair ``(python_function, eager_signature)``.
        :rtype: Tuple[Callable, object]
        """
        col_map: Dict[int, int] = dict()
        visitor: MatrixVectorizedVisitor
        rhs_code: str
        lines: List[str] = list()
        py_func: Callable
        signature_tpe: object
        full_source: str

        # The template variables define the deterministic position of each grouped runtime value.
        i: int
        v: Var
        for i, v in enumerate(template_vars):
            target_uid: int = v.uid if v.uid in self.var_map or v.base_var is None else v.base_var.uid
            if target_uid not in col_map:
                col_map[target_uid] = i
            else:
                pass

        cache_key = _build_matrix_codegen_cache_key(
            template_eq,
            self.var_map,
            self.param_map,
            type(self.strategy).__name__,
            col_map,
            len(self.variables_objs),
            len(self.parameters_objs),
        )
        cache_entry = GENERATED_KERNEL_CACHE.get_entry("matrix", cache_key)

        if cache_entry is None:
            pass
        else:
            return cache_entry.get_python_function(), cache_entry.get_signature_tpe()

        # The matrix visitor resolves vectorized gather operations through the grouped index matrix.
        visitor = MatrixVectorizedVisitor(self.var_map, self.param_map, self.strategy, col_map)
        rhs_code = visitor.visit(template_eq)
        canonical_func_name = f"eager_matrix_{cache_key[:16]}"

        # The eager matrix ABI writes directly into the caller-owned batch buffer.
        lines.append(f"def {canonical_func_name}(states, params, history, d_history, h, indices, data_out, history2):")
        lines.append(f"    data_out[:indices.shape[0]] = {rhs_code}")

        full_source = "\n".join(lines)
        py_func = _compile_to_file(full_source, canonical_func_name)
        signature_tpe = self.generate_signature(
            kernel_tpe=EagerKernelKind.MatrixVectorized,
            n_variables=len(self.variables_objs),
            n_parameters=len(self.parameters_objs),
            nnz=len(template_vars),
            with_history2=True,
        )

        GENERATED_KERNEL_CACHE.set_entry("matrix", cache_key, GeneratedKernelCacheEntry(py_func, signature_tpe))
        return py_func, signature_tpe

# ==============================================================================
# 7. RMS Native Compiler (Continuous Time & Sparse Jacobians)
# ==============================================================================
class RMSCompiler(EquationCompiler):
    """
    O(N) compiler for RMS (Root Mean Square) Continuous-Time Simulations.

    This compiler generates highly optimized Right-Hand Side (RHS) vectors and
    Sparse Jacobian matrices using a structural analysis approach. By leveraging
    the official `expression2numba` translator, it ensures 100% mathematical
    consistency with legacy systems while drastically reducing symbolic evaluation
    and compilation times.
    """
    __slots__ = ['dt_var', 'compiler_names_dict', 'diff_vars', 'v_params']

    def __init__(self,
                 variables: List[Var],
                 diff_vars: List[Var],
                 v_params: List[Var],
                 c_params: List[Var],
                 compiler_names_dict: Dict[int, str]) -> None:
        """
        Initializes the RMS Compiler with the system's mathematical components.

        Args:
            variables (List[Var]): State and algebraic variables of the system.
            diff_vars (List[Var]): Differential variables (dx/dt).
            v_params (List[Var]): Variable (event-driven) parameters.
            c_params (List[Var]): Constant parameters.
            compiler_names_dict (Dict[int, str]): Dictionary mapping variable UIDs to
                                                  their executable string representations.
        """
        super().__init__(variables=variables, parameters=c_params, method=DynamicIntegrationMethod.DaeBackEuler)
        self.dt_var = Var(name="dt")
        self.compiler_names_dict = compiler_names_dict
        self.diff_vars = diff_vars
        self.v_params = v_params
        self.compiler_names_dict[self.dt_var.uid] = 'h'

    def compile_rhs(self, equations: List[Expr], func_name: str) -> Callable[[Vec, Vec, Vec, Vec], Vec]:
        """
        Compiles the residual equations (RHS) into a fast, executable JIT function.

        Args:
            equations (List[Expr]): The list of symbolic expressions to evaluate.
            func_name (str): The desired name for the compiled target function.

        Returns:
            Callable: An executable function computing the RHS residuals.
        """
        # Keep legacy signature (`vrs`) while also exposing `vars` alias,
        # so equations compiled with either naming convention work.
        lines: List[str] = list()
        lines.append(f"def {func_name}(vrs, diff, vprms, cprms):")
        lines.append("    vars = vrs")
        lines.append(f"    out = np.zeros({len(equations)}, dtype=np.float64)")

        for i, eq in enumerate(equations):
            expr_str = expression2numba(eq, self.compiler_names_dict)
            lines.append(f"    out[{i}] = {expr_str}")

        lines.append("    return out")

        return _compile_to_file("\n".join(lines), func_name)

    def compile_sparse_jacobian(self, eqs: List[Expr],
                                wrt_vars: List[Var],
                                func_name: str) -> Callable[[Vec, Vec, Vec, Vec, float], sp.csc_matrix]:
        """
        Compiles a sparse Jacobian evaluator using an O(N) structural extraction algorithm.

        Args:
            eqs (List[Expr]): The list of symbolic equations (F or G).
            wrt_vars (List[Var]): The variables to differentiate with respect to (x or y).
            func_name (str): The desired name for the compiled target function.

        Returns:
            Callable: A function that populates and returns a scipy.sparse.csc_matrix.
        """
        wrt_map = {v.uid: (i, v) for i, v in enumerate(wrt_vars)}
        triplets: List[Tuple[int, int, Expr]] = list()

        for row, eq in enumerate(eqs):
            for uid in _collect_candidate_wrt_uids(eq, wrt_map):
                col, var = wrt_map[uid]
                d_expr = eq.diff(var, dt=self.dt_var)
                if not (isinstance(d_expr, Const) and d_expr.value == 0):
                    triplets.append((col, row, d_expr))

        triplets.sort(key=_get_triplet_sort_key)

        # Handle edge case: Empty Jacobian matrix (no dependencies found)
        if not triplets:
            J_empty = sp.csc_matrix((len(eqs), len(wrt_vars)))
            return EmptySparseJacobianEvaluator(J_empty)
        # Extract sorted coordinates and corresponding symbolic derivatives
        cols_sorted = [t[0] for t in triplets]
        rows_sorted = [t[1] for t in triplets]
        d_exprs = [t[2] for t in triplets]

        # Precompute CSC (Compressed Sparse Column) pointer arrays
        nnz = len(cols_sorted)
        indices = np.fromiter(rows_sorted, dtype=np.int32, count=nnz)
        indptr = np.zeros(len(wrt_vars) + 1, dtype=np.int32)
        for c in cols_sorted:
            indptr[c + 1] += 1
        np.cumsum(indptr, out=indptr)

        # Initialize the sparse matrix template
        J_template = sp.csc_matrix((np.zeros(nnz), indices, indptr), shape=(len(eqs), len(wrt_vars)))

        # The Jacobian receives 'h' in its signature for solver compatibility,
        # even though 'expression2numba' internally resolves 'dt' via vprms[...]
        lines = [f"def {func_name}_filler(vrs, diff, vprms, cprms, h, data_out):"]
        lines.append("    vars = vrs")
        for i, expr in enumerate(d_exprs):
            expr_str = expression2numba(expr, self.compiler_names_dict)
            # in case of vectorization
            # lines.append(f"    data_out[{i}] = {expr_str}")
            lines.append(f"    data_out[{i}] = {expr_str}")

        filler_fn = _compile_to_file("\n".join(lines), f"{func_name}_filler")

        return SparseJacobianEvaluatorWrapper(filler_fn=filler_fn, matrix=J_template)

    def compile_event_params_fn(self, eqs: List[Expr], alias_names_dict: Dict[int, str],
                                EVENT_PARAMS_NAME: str, TIME_NAME: str,
                                func_name: str = "event_params_fn") -> Callable[[Vec, float], Vec]:
        """
        Compiles event parameters equations into a fast, executable JIT function.

        This is the equivalent of SymbolicParamsVector.

        Args:
            eqs (List[Expr]): The list of symbolic expressions for event parameters.
            alias_names_dict (Dict[int, str]): Dictionary mapping var UIDs to alias names.
            EVENT_PARAMS_NAME (str): Name of the event parameters array (e.g., "vprms").
            TIME_NAME (str): Name of the time variable (e.g., "glob_time").
            func_name (str): The desired name for the compiled target function.

        Returns:
            Callable: An executable function with signature (event_params, time, out) -> out.
        """
        used_vars_count = defaultdict(int)
        for eq in eqs:
            for var in get_expression_vars(eq):
                used_vars_count[var.uid] += 1

        lines: List[str] = list()
        lines.append(f"def {func_name}({EVENT_PARAMS_NAME}, {TIME_NAME}, out):")

        final_names_dict: Dict[int, str] = self.compiler_names_dict.copy()
        for uid, count in used_vars_count.items():
            if count > 1:
                final_names_dict[uid] = alias_names_dict[uid]
                lines.append(f"    {alias_names_dict[uid]} = {self.compiler_names_dict[uid]}")
            else:
                pass

        for i, eq in enumerate(eqs):
            # Event-parameter expressions may reuse the same runtime variable many
            # times, especially for piecewise ramps built from time-dependent
            # expressions. The compiled expression must therefore use the alias-
            # aware name map prepared above, otherwise the generated code can
            # evaluate a simplified step-like path instead of the intended ramp.
            expr_str = expression2numba(eq, final_names_dict)
            lines.append(f"    out[{i}] = {expr_str}")

        lines.append("    return out")

        raw_fn = _compile_to_file("\n".join(lines), func_name)
        return EventParameterFunctionWrapper(raw_fn=raw_fn, equation_count=len(eqs))

    def compile_derivative_fn(self, uid2idx_vars: Dict[int, int],
                              func_name: str = "derivative_fn") -> Callable[[Vec, Vec, Vec, float], Vec]:
        """
        Compiles the derivative evaluation function for differential variables.

        This is the equivalent of SymbolicDerivative.

        Args:
            uid2idx_vars (Dict[int, int]): Dictionary mapping var UIDs to their indices.
            func_name (str): The desired name for the compiled target function.

        Returns:
            Callable: An executable function with signature (vrs, lagvars, lagdx, h, out) -> out.
        """
        lines: List[str] = list()
        lines.append(f"def {func_name}(vrs, lagvars, lagdx, h, out):")

        uid2dx_expression = {}
        for i, diff_var in enumerate(self.diff_vars):
            base_var_uid = diff_var.base_var.uid
            uid = diff_var.uid
            if diff_var.diff_order == 1:
                j = uid2idx_vars[base_var_uid]
                rhs = f" (vrs[{j}] - lagvars[{j}]) / h"
            else:
                dx_expression = uid2dx_expression[diff_var.base_var.uid]
                rhs = f" ({dx_expression} - lagdx[{i}]) / h"
            lines.append(f"    out[{i}] = {rhs}")
            uid2dx_expression[uid] = rhs

        lines.append("    return out")

        raw_fn = _compile_to_file("\n".join(lines), func_name)
        return DerivativeFunctionWrapper(raw_fn=raw_fn, diff_var_count=len(self.diff_vars))


class RMSCompilerVec(EquationCompiler):
    """
    O(N) compiler for RMS (Root Mean Square) Continuous-Time Simulations.

    This compiler generates highly optimized Right-Hand Side (RHS) vectors and
    Sparse Jacobian matrices using a structural analysis approach. By leveraging
    the official `expression2numba` translator, it ensures 100% mathematical
    consistency with legacy systems while drastically reducing symbolic evaluation
    and compilation times.
    """
    __slots__ = ['dt_var', 'compiler_names_dict', 'diff_vars', 'v_params']

    def __init__(self,
                 variables: List[Var],
                 diff_vars: List[Var],
                 v_params: List[Var],
                 c_params: List[Var],
                 compiler_names_dict: Dict[int, str]) -> None:
        """
        Initializes the RMS Compiler with the system's mathematical components.

        Args:
            variables (List[Var]): State and algebraic variables of the system.
            diff_vars (List[Var]): Differential variables (dx/dt).
            v_params (List[Var]): Variable (event-driven) parameters.
            c_params (List[Var]): Constant parameters.
            compiler_names_dict (Dict[int, str]): Dictionary mapping variable UIDs to
                                                  their executable string representations.
        """
        super().__init__(variables=variables, parameters=c_params, method=DynamicIntegrationMethod.DaeBackEuler)
        self.dt_var = Var(name="dt")
        self.compiler_names_dict = compiler_names_dict
        self.diff_vars = diff_vars
        self.v_params = v_params
        self.compiler_names_dict[self.dt_var.uid] = 'h'

    def compile_rhs(self, equations: List[Expr], func_name: str) -> Callable[[Vec, Vec, Vec, Vec], Vec]:
        """
        Compiles the residual equations (RHS) into a fast, executable JIT function.

        Args:
            equations (List[Expr]): The list of symbolic expressions to evaluate.
            func_name (str): The desired name for the compiled target function.

        Returns:
            Callable: An executable function computing the RHS residuals.
        """
        # Keep legacy signature (`vrs`) while also exposing `vars` alias,
        # so equations compiled with either naming convention work.

        lines: List[str] = list()
        lines.append(f"def {func_name}(vrs, diff, vprms, cprms):")
        lines.append("    vars = vrs")
        lines.append("    n_models = vars.shape[1]")
        lines.append(f"    out = np.zeros(({len(equations)}, n_models), dtype=np.float64)")

        for i, eq in enumerate(equations):
            expr_str = expression2numba(eq, self.compiler_names_dict)
            lines.append(f"    out[{i}, :] = {expr_str}")

        lines.append("    return out")

        return _compile_to_file("\n".join(lines), func_name)

    def compile_sparse_jacobian(self, eqs: List[Expr],
                                wrt_vars: List[Var],
                                func_name: str) -> Callable[[Vec, Vec, Vec, Vec, float], np.ndarray]:
        """
        Compiles a vectorized sparse Jacobian evaluator.

        Args:
            eqs (List[Expr]): The list of symbolic equations (F or G).
            wrt_vars (List[Var]): The variables to differentiate with respect to (x or y).
            func_name (str): The desired name for the compiled target function.

        Returns:
            Callable: A function that returns a 2D data array (nnz, n_instances).
        """
        wrt_map = {v.uid: (i, v) for i, v in enumerate(wrt_vars)}
        triplets: List[Tuple[int, int, Expr]] = list()

        for row, eq in enumerate(eqs):
            for uid in _collect_candidate_wrt_uids(eq, wrt_map):
                col, var = wrt_map[uid]
                d_expr = eq.diff(var, dt=self.dt_var)
                if not (isinstance(d_expr, Const) and d_expr.value == 0):
                    triplets.append((col, row, d_expr))

        triplets.sort(key=_get_triplet_sort_key)

        # Handle edge case: Empty Jacobian matrix (no dependencies found)
        if not triplets:
            return EmptyVecSparseJacobianEvaluator(len(eqs), len(wrt_vars))

        d_exprs = [t[2] for t in triplets]
        nnz = len(d_exprs)

        # The generated code fills a 2D data_out array (nnz, n_models) using
        # numpy broadcasting over the instance dimension.
        lines = [f"def {func_name}_filler(vrs, diff, vprms, cprms, h, data_out):"]
        lines.append("    vars = vrs")
        for i, expr in enumerate(d_exprs):
            expr_str = expression2numba(expr, self.compiler_names_dict)
            lines.append(f"    data_out[{i}, :] = {expr_str}")

        filler_fn = _compile_to_file("\n".join(lines), f"{func_name}_filler")

        rows_sorted = [t[1] for t in triplets]
        cols_sorted = [t[0] for t in triplets]
        indices = np.fromiter(rows_sorted, dtype=np.int32, count=nnz)
        indptr = np.zeros(len(wrt_vars) + 1, dtype=np.int32)
        for c in cols_sorted:
            indptr[c + 1] += 1
        np.cumsum(indptr, out=indptr)

        return SparseJacobianEvaluatorVecWrapper(
            filler_fn=filler_fn,
            nnz=nnz,
            n_rows=len(eqs),
            n_cols=len(wrt_vars),
            rows=rows_sorted,
            cols=cols_sorted,
            indices=indices,
            indptr=indptr,
        )

    def compile_event_params_fn(self, eqs: List[Expr], alias_names_dict: Dict[int, str],
                                EVENT_PARAMS_NAME: str, TIME_NAME: str,
                                func_name: str = "event_params_fn") -> Callable[[Vec, float], Vec]:
        """
        Compiles event parameters equations into a fast, executable JIT function.

        This is the equivalent of SymbolicParamsVector.

        Args:
            eqs (List[Expr]): The list of symbolic expressions for event parameters.
            alias_names_dict (Dict[int, str]): Dictionary mapping var UIDs to alias names.
            EVENT_PARAMS_NAME (str): Name of the event parameters array (e.g., "vprms").
            TIME_NAME (str): Name of the time variable (e.g., "glob_time").
            func_name (str): The desired name for the compiled target function.

        Returns:
            Callable: An executable function with signature (event_params, time, out) -> out.
        """
        used_vars_count = defaultdict(int)
        for eq in eqs:
            for var in get_expression_vars(eq):
                used_vars_count[var.uid] += 1

        lines: List[str] = list()
        lines.append(f"def {func_name}({EVENT_PARAMS_NAME}, {TIME_NAME}, out):")

        final_names_dict: Dict[int, str] = self.compiler_names_dict.copy()
        for uid, count in used_vars_count.items():
            if count > 1:
                final_names_dict[uid] = alias_names_dict[uid]
                lines.append(f"    {alias_names_dict[uid]} = {self.compiler_names_dict[uid]}")
            else:
                pass

        for i, eq in enumerate(eqs):
            # Event-parameter expressions may reuse the same runtime variable many
            # times, especially for piecewise ramps built from time-dependent
            # expressions. The compiled expression must therefore use the alias-
            # aware name map prepared above, otherwise the generated code can
            # evaluate a simplified step-like path instead of the intended ramp.
            expr_str = expression2numba(eq, final_names_dict)
            lines.append(f"    out[{i}] = {expr_str}")

        lines.append("    return out")

        raw_fn = _compile_to_file("\n".join(lines), func_name)
        return EventParameterFunctionWrapper(raw_fn=raw_fn, equation_count=len(eqs))

    def compile_derivative_fn(self, uid2idx_vars: Dict[int, int],
                              func_name: str = "derivative_fn") -> Callable[[Vec, Vec, Vec, float], Vec]:
        """
        Compiles the derivative evaluation function for differential variables.

        This is the equivalent of SymbolicDerivative.

        Args:
            uid2idx_vars (Dict[int, int]): Dictionary mapping var UIDs to their indices.
            func_name (str): The desired name for the compiled target function.

        Returns:
            Callable: An executable function with signature (vrs, lagvars, lagdx, h, out) -> out.
        """
        lines: List[str] = list()
        lines.append(f"def {func_name}(vrs, lagvars, lagdx, h, out):")

        uid2dx_expression = {}
        for i, diff_var in enumerate(self.diff_vars):
            base_var_uid = diff_var.base_var.uid
            uid = diff_var.uid
            if diff_var.diff_order == 1:
                j = uid2idx_vars[base_var_uid]
                rhs = f" (vrs[{j}] - lagvars[{j}]) / h"
            else:
                dx_expression = uid2dx_expression[diff_var.base_var.uid]
                rhs = f" ({dx_expression} - lagdx[{i}]) / h"
            lines.append(f"    out[{i}] = {rhs}")
            uid2dx_expression[uid] = rhs

        lines.append("    return out")

        raw_fn = _compile_to_file("\n".join(lines), func_name)
        return DerivativeFunctionWrapper(raw_fn=raw_fn, diff_var_count=len(self.diff_vars))
