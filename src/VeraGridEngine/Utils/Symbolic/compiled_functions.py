# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Dict, List, Sequence, Callable, Any, Tuple, Set
from collections import defaultdict
import numpy as np
import numba as nb
import scipy.sparse as sp
import math
import concurrent.futures

from VeraGridEngine.Utils.Symbolic.symbolic import (Var, Const, Expr, heaviside_num, expression2numba,
                                                    get_expression_vars)
from VeraGridEngine.basic_structures import Vec, IntVec
from VeraGridEngine.Utils.Symbolic.jit_compiler import SubexpressionAnalyzer, _collect_candidate_wrt_uids


def compile_jac_block(block_id,
                      block_eqs,
                      block_offsets,
                      used_vars_count,
                      compiler_names_dict,
                      alias_names_dict,
                      namespace,
                      VARS_NAME: str,
                      DIFF_NAME: str,
                      EVENT_PARAMS_NAME: str,
                      PARAMS_NAME: str,
                      use_jit):
    """
    function that builds the compiled functions

    :param block_id:
    :param block_eqs:
    :param block_offsets:
    :param used_vars_count:
    :param compiler_names_dict:
    :param alias_names_dict:
    :param namespace:
    :param VARS_NAME:
    :param DIFF_NAME:
    :param EVENT_PARAMS_NAME:
    :param PARAMS_NAME:
    :param use_jit:
    :return:
    """
    fname = f"jac_block_{block_id}"
    src = f"def {fname}({VARS_NAME}, {DIFF_NAME}, {EVENT_PARAMS_NAME}, {PARAMS_NAME}, h, out):\n"
    final_names_dict = {}
    for uid, count in used_vars_count.items():
        if count > 1:
            final_names_dict[uid] = alias_names_dict[uid]
            src += f"    {alias_names_dict[uid]} = {compiler_names_dict[uid]}\n"
        else:
            final_names_dict[uid] = compiler_names_dict[uid]

    offset = block_offsets[block_id]
    analyzer: SubexpressionAnalyzer = SubexpressionAnalyzer()
    simplified: Expr
    i: int
    e: Expr
    assignments: List[str]
    expression_names: Dict[int, str]
    for i, e in enumerate(block_eqs):
        # Finish each expression before its existing output write. Reuse only
        # within that expression so output aliasing and exception order remain.
        simplified = e.simplify()
        assignments, expression_names = analyzer.emit_ordered_assignments(
            simplified, final_names_dict, (VARS_NAME, DIFF_NAME, EVENT_PARAMS_NAME, PARAMS_NAME, "h", "out"))
        if assignments:
            src += "\n".join(assignments) + "\n"
        else:
            pass
        src += f"    out[{offset + i}] = {expression2numba(simplified, final_names_dict, 0, expression_names)}\n"

    exec(src, namespace)

    if use_jit:
        func = nb.njit(
            nb.void(nb.float64[:], nb.float64[:], nb.float64[:], nb.float64[:], nb.float64, nb.float64[:]),
            fastmath=True,
            cache=False
        )(namespace[fname])
    else:
        func = namespace[fname]

    return block_id, func


class SymbolicJacobian:
    """
       Class to store and evaluate a symbolic jacobian
       """
    __slots__ = (
        "nvar",
        "J",
        "namespace",
        "block_offsets",
        "funcs",
    )

    def __init__(self,
                 eqs: list,
                 variables: list,
                 compiler_names_dict: dict,
                 alias_names_dict: dict,
                 VARS_NAME: str,
                 DIFF_NAME: str,
                 EVENT_PARAMS_NAME: str,
                 PARAMS_NAME: str,
                 dt=None,
                 use_jit=True,
                 batch_size=500,
                 n_jobs=4,
                 static=False):  # número de threads para compilación paralela

        """
                JIT‑compile a sparse Jacobian evaluator for *equations* w.r.t *variables*.
                :param eqs: Array of equations
                :param variables: Array of variables to differentiate against
                :param uid2sym_vars: dictionary relating the uid of a var with its array name (i.e. var[0])
                :param uid2sym_params:
                :param use_jit: if true, the function is compiled by numba
                :return:
                        jac_fn : callable(values: np.ndarray, params: np.ndarray) -> scipy.sparse.csc_matrix
                            Fast evaluator in which *values* is a 1‑D NumPy vector of length
                            ``len(variables)``and *params* is a 1‑D NumPy vector of length
                            ``len(parameters)``
                        sparsity_pattern : tuple(np.ndarray, np.ndarray)
                            Row/col indices of structurally non‑zero entries.
                """

        h = Var('h')
        alias_names_dict[h.uid] = 'h'
        compiler_names_dict[h.uid] = 'h'
        if static:
            h = None
        # --- Build triplets and count variable usage ---------------------------------
        used_vars_count = defaultdict(int)
        triplets = []

        row: int
        col: int
        var: Var
        eq: Expr
        candidates: Set[int]
        d_expression: Expr
        v: Var
        wrt_map: Dict[int, Tuple[int, Var]] = dict((var.uid, (col, var)) for col, var in enumerate(variables))
        for row, eq in enumerate(eqs):
            # Reuse the RMS compiler's dependency selection, including related
            # derivative UIDs, before differentiating. Unrelated coordinates
            # must not expand large initialization formulas into zero terms.
            candidates = _collect_candidate_wrt_uids(eq, wrt_map)
            # Keep the original column iteration so repeated requested UIDs
            # retain all of their columns rather than collapsing in the lookup.
            for col, var in enumerate(variables):
                if var.uid in candidates:
                    d_expression = eq.diff(var, dt=h)
                    if not (isinstance(d_expression, Const) and d_expression.value == 0):
                        triplets.append((col, row, d_expression))
                    else:
                        pass
                    for v in get_expression_vars(d_expression):
                        used_vars_count[v.uid] += 1
                else:
                    pass

        triplets.sort(key=lambda t: (t[0], t[1]))
        cols_sorted, rows_sorted, equations_sorted = zip(*triplets) if triplets else ([], [], [])

        # --- Assemble sparse CSC Jacobian structure ---------------------------------
        nnz = len(cols_sorted)
        indices = np.fromiter(rows_sorted, dtype=np.int32, count=nnz)
        indptr = np.zeros(len(variables) + 1, dtype=np.int32)
        for c in cols_sorted:
            indptr[c + 1] += 1
        np.cumsum(indptr, out=indptr)

        self.nvar = len(variables)
        neq = len(eqs)
        self.J = sp.csc_matrix((np.zeros(nnz), indices, indptr), shape=(neq, self.nvar))

        # --- Batch compilation ------------------------------------------------------
        self.namespace: Dict[str, Any] = {
            "math": math,
            "np": np,
            "nb": nb,
            "_heaviside": heaviside_num,
        }

        blocks = [
            equations_sorted[i:i + batch_size]
            for i in range(0, len(equations_sorted), batch_size)
        ]
        self.block_offsets = [i for i in range(0, len(equations_sorted), batch_size)]
        self.funcs: List[Callable[[Vec, Vec, Vec, Vec, float, Vec], None] | None] = [None] * len(blocks)

        # --- Compile blocks sequentially -------------------------------------------
        # --- Compile blocks in parallel ---------------------------------------------
        with concurrent.futures.ThreadPoolExecutor(max_workers=n_jobs) as executor:
            futures = [
                executor.submit(
                    compile_jac_block,
                    i, block, self.block_offsets, used_vars_count,
                    compiler_names_dict, alias_names_dict,
                    self.namespace, VARS_NAME, DIFF_NAME, EVENT_PARAMS_NAME, PARAMS_NAME, use_jit
                )
                for i, block in enumerate(blocks)
            ]
            for f in concurrent.futures.as_completed(futures):
                block_id, func = f.result()
                self.funcs[block_id] = func

    def __call__(self,
                 x: Vec,
                 dx: Vec,
                 variable_params: Vec,
                 constant_params: Vec,
                 h: float):
        """

        :param x:
        :param dx:
        :param variable_params:
        :param constant_params:
        :param h:
        :return:
        """
        for func in self.funcs:
            if func is not None:
                func(x, dx, variable_params, constant_params, h, self.J.data)
        return self.J


class SymbolicVector:
    """
    SymbolicFunction
    """
    __slots__ = (
        "func",
        "namespace",
        "data",
    )

    def __init__(self,
                 eqs: List[Expr],
                 compiler_names_dict: Dict[int, str],
                 alias_names_dict: Dict[int, str],
                 VARS_NAME: str,
                 DIFF_NAME: str,
                 EVENT_PARAMS_NAME: str,
                 PARAMS_NAME: str,
                 use_jit: bool = True):
        """
        Compile the array of expressions to a function that returns an array of values for those expressions
        :param eqs: Iterable of expressions (Expr)
        :param uid2sym_vars: dictionary relating the uid of a var with its array name (i.e. var[0])
        :param uid2sym_params:
        :return: Function pointer that returns an array
        """
        self.func: Callable[[Vec, Vec, Vec, Vec, Vec], None] | None = None
        used_vars_count = defaultdict(int)
        for eq in eqs:
            for var in get_expression_vars(eq):
                used_vars_count[var.uid] += 1
                if var.uid not in compiler_names_dict.keys():
                    print()
                if var.uid not in alias_names_dict.keys():
                    print()

        if len(eqs):
            self.namespace: Dict[str, Any] = {
                "math": math,
                "np": np,
                "nb": nb,
                "_heaviside": heaviside_num,
            }

            fname = f"func"  # since we compile into a namespace, there won't be repeated names

            # Build source
            src = f"def {fname}({VARS_NAME}, {DIFF_NAME}, {EVENT_PARAMS_NAME}, {PARAMS_NAME}, out):\n"
            final_names_dict = compiler_names_dict.copy()
            for uid, count in used_vars_count.items():
                if count > 1:
                    final_names_dict[uid] = alias_names_dict[uid]
                    src += f"    {alias_names_dict[uid]} = {compiler_names_dict[uid]}\n"
            analyzer: SubexpressionAnalyzer = SubexpressionAnalyzer()
            simplified: Expr
            i: int
            e: Expr
            assignments: List[str]
            expression_names: Dict[int, str]
            for i, e in enumerate(eqs):
                # A per-expression plan limits generated IR without changing
                # residual ordering, derivative formulas or solver policy.
                simplified = e.simplify()
                assignments, expression_names = analyzer.emit_ordered_assignments(
                    simplified, final_names_dict, (VARS_NAME, DIFF_NAME, EVENT_PARAMS_NAME, PARAMS_NAME, "out"))
                if assignments:
                    src += "\n".join(assignments) + "\n"
                else:
                    pass
                src += f"    out[{i}] = {expression2numba(simplified, final_names_dict, 0, expression_names)}\n"

            # compile in python namespace
            exec(src, self.namespace)

            # compile in numba
            if use_jit:
                self.func = nb.njit(
                    nb.void(nb.float64[:], nb.float64[:], nb.float64[:], nb.float64[:], nb.float64[:]),
                    fastmath=True)(self.namespace[fname])
            else:
                self.func = self.namespace[fname]
        else:
            self.func = None

        self.data: Vec = np.zeros(len(eqs))

    def __call__(self, values: Vec, diff_values: Vec, event_params: Vec, params: Vec) -> Vec:
        """
        Call the compiled function
        :param values:
        :param diff_values:
        :param event_params:
        :param params:
        :return:
        """
        if self.func is not None:
            self.func(values, diff_values, event_params, params, self.data)
        return self.data


def get_compiled_functions_cache_stats() -> Dict[str, float]:
    """
    Return cache statistics for compiled symbolic helper functions.

    The legacy compiled-function module does not yet expose a persistent cache,
    so the reported cache entry count is zero. The function exists so EMT build
    reports can depend on a stable interface while the cache work remains staged.

    :return: Cache statistics.
    :rtype: Dict[str, float]
    """
    return dict(entry_count=0.0)


class SymbolicParamsVector:
    """
    SymbolicFunction
    """
    __slots__ = (
        "func",
        "namespace",
        "data",
    )

    def __init__(self, eqs: Sequence[Expr],
                 compiler_names_dict: Dict[int, str],
                 alias_names_dict: Dict[int, str],
                 EVENT_PARAMS_NAME: str,
                 TIME_NAME: str,
                 use_jit: bool = True):
        """
        Compile the array of expressions to a function that returns an array of values for those expressions
        :param eqs: Iterable of expressions (Expr)
        :param uid2sym_t: dictionary relating the uid of a var with its array name (i.e. var[0])
        :return: Function pointer that returns an array
        """
        self.func: Callable[[Vec, float, Vec], None] | None = None
        used_vars_count = defaultdict(int)
        for eq in eqs:
            for var in get_expression_vars(eq):
                used_vars_count[var.uid] += 1

        if len(eqs):
            self.namespace: Dict[str, Any] = {
                "math": math,
                "np": np,
                "nb": nb,
                "_heaviside": heaviside_num,
            }

            fname = f"func"  # since we compile into a namespace, there won't be repeated names

            # Build source
            src = f"def {fname}({EVENT_PARAMS_NAME}, {TIME_NAME}, out):\n"
            final_names_dict = compiler_names_dict.copy()
            for uid, count in used_vars_count.items():
                if count > 1:
                    final_names_dict[uid] = alias_names_dict[uid]
                    src += f"    {alias_names_dict[uid]} = {compiler_names_dict[uid]}\n"
            src += "\n".join(
                [f"    out[{i}] = {expression2numba(e, compiler_names_dict)}" for i, e in enumerate(eqs)]) + "\n"

            # compile in python namespace
            exec(src, self.namespace)

            # compile in numba
            if use_jit:
                self.func = nb.njit(nb.void(nb.float64[:], nb.float64, nb.float64[:]),
                                    fastmath=True)(self.namespace[fname])
            else:
                self.func = self.namespace[fname]
        else:
            self.func = None

        self.data = np.zeros(len(eqs))

    def __call__(self, event_params: Vec, glob_time: float) -> Vec:
        """
        Call the compiled function
        :param glob_time:
        :return:
        """
        if self.func is not None:
            self.func(event_params, glob_time, self.data)
        return self.data


class SymbolicDerivative:
    """
    SymbolicFunction
    """
    __slots__ = (
        "func",
        "data",
        "index_map",
        "namespace",
    )

    def __init__(self,
                 vars: Sequence[Var],
                 uid2idx_vars: Dict[int, int],
                 diff_vars: Sequence[Var],
                 compiler_names_dict: Dict[int, str],
                 use_jit: bool = True):
        self.func: Callable[[Vec, Vec, Vec, float, Vec], Vec] | None = None

        self.data: Vec = np.zeros(len(diff_vars))
        self.index_map: IntVec = np.zeros(len(diff_vars), dtype=np.int32)

        self.namespace: Dict[str, Any] = {
            "math": math,
            "np": np,
            "nb": nb,
            "_heaviside": heaviside_num,
        }
        fname = f"func"  # since we compile into a namespace, there won't be repeated names
        # Build source
        uid2dx_expression = {}
        # TODO: order diff vars by order
        src = f"def {fname}(vars, lagvars, lagdx, h, out):\n"
        for i, diff_var in enumerate(diff_vars):
            base_var_uid = diff_var.base_var.uid
            uid = diff_var.uid
            if diff_var.diff_order == 1:
                j = uid2idx_vars[base_var_uid]
                rhs = f" (vars[{j}] - lagvars[{j}]) / h\n"
            else:
                dx_expression = uid2dx_expression[diff_var.base_var.uid]
                rhs = f" ({dx_expression}- lagdx[{i}]) / h\n"
            to_src = f"    out[{i}] = {rhs}\n"
            uid2dx_expression[uid] = rhs

            src += to_src
        src += f"    return out"
        exec(src, self.namespace)

        # compile in python namespace
        # compile in numba
        if use_jit:
            self.func = nb.njit(nb.float64[:](nb.float64[:], nb.float64[:], nb.float64[:], nb.float64, nb.float64[:]),
                                fastmath=True)(self.namespace[fname])
        else:
            self.func = self.namespace[fname]

    def __call__(self, x: Vec, xn: Vec, dx: Vec, h: float) -> Vec:
        """
        Call the compiled function
        :param x:
        :param xn:
        :param dx:
        :param h:
        :return:
        """
        if self.func is not None:
            self.func(x, xn, dx, h, self.data)
        return self.data


class SymbolicParamsVectorInit:
    """
    SymbolicFunction
    """
    __slots__ = (
        "func",
        "namespace",
        "data",
    )

    def __init__(self, eqs: Sequence[Expr],
                 compiler_names_dict: Dict[int, str],
                 alias_names_dict: Dict[int, str],
                 VARS_NAME: str,
                 EVENT_PARAMS_NAME: str,
                 TIME_NAME: str,
                 use_jit: bool = True,
                 ):
        """
        Compile the array of expressions to a function that returns an array of values for those expressions
        :param eqs: Iterable of expressions (Expr)
        :param uid2sym_t: dictionary relating the uid of a var with its array name (i.e. var[0])
        :return: Function pointer that returns an array
        """
        self.func: Callable[[Vec, Vec, float, Vec], None] | None = None
        used_vars_count = defaultdict(int)
        for eq in eqs:
            for var in get_expression_vars(eq):
                used_vars_count[var.uid] += 1

        if len(eqs):
            self.namespace: Dict[str, Any] = {
                "math": math,
                "np": np,
                "nb": nb,
                "_heaviside": heaviside_num,
            }

            fname = f"func"  # since we compile into a namespace, there won't be repeated names

            # Build source
            src = f"def {fname}({VARS_NAME}, {EVENT_PARAMS_NAME}, {TIME_NAME}, out):\n"
            final_names_dict = compiler_names_dict.copy()
            for uid, count in used_vars_count.items():
                if count > 1:
                    final_names_dict[uid] = alias_names_dict[uid]
                    src += f"    {alias_names_dict[uid]} = {compiler_names_dict[uid]}\n"
            src += "\n".join(
                [f"    out[{i}] = {expression2numba(e, compiler_names_dict)}" for i, e in enumerate(eqs)]) + "\n"

            # compile in python namespace
            exec(src, self.namespace)

            # compile in numba
            if use_jit:
                self.func = nb.njit(nb.void(nb.float64[:], nb.float64[:], nb.float64, nb.float64[:]),
                                    fastmath=True)(self.namespace[fname])
            else:
                self.func = self.namespace[fname]
        else:
            self.func = None

        self.data = np.zeros(len(eqs))

    def __call__(self, variables, event_params: Vec, glob_time: float) -> Vec:
        """
        Call the compiled function
        :param glob_time:
        :return:
        """
        if self.func is not None:
            self.func(variables, event_params, glob_time, self.data)
        return self.data
