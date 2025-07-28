# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import time
import numpy as np
import math
import uuid
import scipy.sparse as sp
from typing import Optional

from GridCalEngine.Utils.Symbolic.block import Block
from GridCalEngine.Utils.Symbolic.block_solver import BlockSolver
from GridCalEngine.Utils.Symbolic.symbolic import Var, Const, Expr, Func, cos, sin, _emit
from differential_var import DiffVar, LagVar
from __future__ import annotations
from enum import Enum
from scipy.sparse import csc_matrix
import numba as nb
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Callable, ClassVar, Dict, Mapping, Union, List, Sequence, Tuple, Set
from GridCalEngine.Utils.Sparse.csc import pack_4_by_4_scipy

# from GridCalEngine.Utils.Symbolic.events import EventParam

NUMBER = Union[int, float]
NAME = 'name'


# -----------------------------------------------------------------------------
# UUID helper
# -----------------------------------------------------------------------------

def _new_uid() -> int:
    """Generate a fresh UUID‑v4 string."""
    return uuid.uuid4().int

def _compile_equations(eqs: Sequence[Expr],
                       uid2sym_vars: Dict[int, str],
                       uid2sym_params: Dict[int, str],
                       add_doc_string: bool = True) -> Callable[[np.ndarray, np.ndarray], np.ndarray]:

    """
    Compile the array of expressions to a function that returns an array of values for those expressions
    :param eqs: Iterable of expressions (Expr)
    :param uid2sym_vars: dictionary relating the uid of a var with its array name (i.e. var[0])
    :param uid2sym_params:
    :param add_doc_string: add the docstring?
    :return: Function pointer that returns an array
    """
    # Build source
    src = f"def _f(vars, params):\n"
    src += f"    out = np.zeros({len(eqs)})\n"
    src += "\n".join([f"    out[{i}] = {_emit(e, uid2sym_vars, uid2sym_params)}" for i, e in enumerate(eqs)]) + "\n"
    src += f"    return out"
    ns: Dict[str, Any] = {"math": math, "np": np}
    exec(src, ns)
    fn = nb.njit(ns["_f"], fastmath=True)

    if add_doc_string:
        fn.__doc__ = "def _f(vars)"
    return fn



@dataclass(frozen=False)
class DiffBlock(Block):
    diff_vars: List[Expr] = list()


class DiffBlockSolver(BlockSolver):
    differential_vars : List[DiffVar]

    def __init__(self, block_system: Block):
        """
        Constructor        
        :param block_system: BlockSystem
        """
        self.block_system: Block = block_system

        # Flatten the block lists, preserving declaration order
        self._algebraic_vars: List[Var] = list()
        self._algebraic_eqs: List[Expr] = list()
        self._algebraic_eqs_substituted: List[Expr] = list()
        self._state_vars: List[Var] = list()
        self._state_eqs: List[Expr] = list()
        self._state_eqs_substituted: List[Expr] = list()
        self._diff_vars: List[DiffVar] = list()
        self._lag_vars: List[LagVar] = list()
        self._lag_vars_set: Set[LagVar] = set()
        self._parameters: List[Var] = list()

        for b in self.block_system.get_all_blocks():
            self._algebraic_vars.extend(b.algebraic_vars)
            self._algebraic_eqs.extend(b.algebraic_eqs)
            self._state_vars.extend(b.state_vars)
            self._state_eqs.extend(b.state_eqs)
            self._parameters.extend(b.parameters)

            if isinstance(b, DiffBlock):
                self._diff_vars.extend(b.diff_vars)
        for v in self._diff_vars:
            self._lag_vars.extend(v.lag_var)
        self._lag_vars_set.update(v.lag_var)

        #We define the parameter dt
        self.dt = Const(value = 0.001, name='dt')
        self._parameters.extend(self.dt)

        self._n_state = len(self._state_vars)
        self._n_alg = len(self._algebraic_vars)
        self._n_vars = self._n_state + self._n_alg
        self._n_params = len(self._parameters)
        self._n_diff = len(self._diff_vars)

        # generate the in-code names for each variable
        # inside the compiled functions the variables are
        # going to be represented by an array called vars[]

        uid2sym_vars: Dict[int, str] = dict()
        uid2sym_params: Dict[int, str] = dict()
        self.uid2idx_vars: Dict[int, int] = dict()
        self.uid2idx_params: Dict[int, int] = dict()
        i = 0
        for v in self._state_vars:
            uid2sym_vars[v.uid] = f"vars[{i}]"
            self.uid2idx_vars[v.uid] = i
            i += 1

        for v in self._algebraic_vars:
            uid2sym_vars[v.uid] = f"vars[{i}]"
            self.uid2idx_vars[v.uid] = i
            i += 1

        j = 0
        for j, ep in enumerate(self._parameters):
            uid2sym_params[ep.uid] = f"params[{j}]"
            self.uid2idx_params[ep.uid] = j
            j += 1

        #We substitute the differential variable by the Forward Approximation:
        self._lag_vars = set(self._lag_vars)
        for eq in self._state_eqs:
            for var in self._diff_vars:
                approximation, total_lag = var.approximation_expr(self.dt)
                eq_substituted = eq.subs({var:approximation})
                self._state_eqs_substituted.append(eq_substituted)
                self._lag_vars_set.update(LagVar(base_var=var.original_var, lag = lag) for lag in range(1, total_lag+1))

        for eq in self._algebraic_eqs_substituted:
            for var in self._diff_vars:
                approximation, total_lag = var.approximation_expr(self.dt)
                eq_substituted = eq.subs({var:approximation})
                self._state_eqs_substituted.append(eq_substituted)
                self._lag_vars_set.update(LagVar(base_var=var.original_var, lag = lag) for lag in range(1, total_lag+1))

        self._lag_vars = sorted(self._lag_vars_set, key=lambda x: x.uid)
        for v in self._lag_vars:  # deterministic
            uid2sym_vars[v.uid] = f"vars[{i}]"
            self.uid2idx_vars[v.uid] = i
            i += 1

        # Compile RHS and Jacobian

        """
                   state Var   algeb var  
        state eq |J11        | J12       |    | ∆ state var|    | ∆ state eq |
                 |           |           |    |            |    |            |
                 ------------------------- x  |------------|  = |------------|
        algeb eq |J21        | J22       |    | ∆ algeb var|    | ∆ algeb eq |
                 |           |           |    |            |    |            |
        """
        print("Compiling...", end="")
        self._rhs_state_fn = _compile_equations(eqs=self._state_eqs_substituted, uid2sym_vars=uid2sym_vars,
                                                uid2sym_params=uid2sym_params)

        self._rhs_algeb_fn = _compile_equations(eqs=self._algebraic_eqs_substituted, uid2sym_vars=uid2sym_vars,
                                                uid2sym_params=uid2sym_params)

        self._j11_fn = self._get_jacobian(eqs=self._state_eqs_substituted, variables=self._state_vars, uid2sym_vars=uid2sym_vars,
                                     uid2sym_params=uid2sym_params, dt = self.dt)
        self._j12_fn = self._get_jacobian(eqs=self._state_eqs_substituted, variables=self._algebraic_vars, uid2sym_vars=uid2sym_vars,
                                     uid2sym_params=uid2sym_params, dt = self.dt)
        self._j21_fn = self._get_jacobian(eqs=self._algebraic_eqs_substituted, variables=self._state_vars, uid2sym_vars=uid2sym_vars,
                                     uid2sym_params=uid2sym_params, dt = self.dt)
        self._j22_fn = self._get_jacobian(eqs=self._algebraic_eqs_substituted, variables=self._algebraic_vars, uid2sym_vars=uid2sym_vars,
                                     uid2sym_params=uid2sym_params, dt = self.dt)
    
    def jacobian_implicit(self, x: np.ndarray, params: np.ndarray, h: float) -> sp.csc_matrix:
        """
        :param x: vector or variables' values
        :param params: params array
        :param h: step
        :return:
        """

        """
                  state Var    algeb var
        state eq |I - h * J11 | - h* J12  |    | ∆ state var|    | ∆ state eq |
                 |            |           |    |            |    |            |
                 -------------------------- x  |------------|  = |------------|
        algeb eq |J21         | J22       |    | ∆ algeb var|    | ∆ algeb eq |
                 |            |           |    |            |    |            |
        """

        I = sp.eye(m=self._n_state, n=self._n_state)
        j11: sp.csc_matrix = (I - h * self._j11_fn(x, params)).tocsc()
        j12: sp.csc_matrix = - h * self._j12_fn(x, params)
        j21: sp.csc_matrix = self._j21_fn(x, params)
        j22: sp.csc_matrix = self._j22_fn(x, params)
        J = pack_4_by_4_scipy(j11, j12, j21, j22)
        return J

    def _get_jacobian(self,
                      eqs: List[Expr],
                      variables: List[Var],
                      uid2sym_vars: Dict[int, str],
                      uid2sym_params: Dict[int, str],
                      diff_vars: List[Var] = list(),
                      dt: Const = Const(0.001)):
        """
        JIT‑compile a sparse Jacobian evaluator for *equations* w.r.t *variables*.
        :param eqs: Array of equations
        :param variables: Array of variables to differentiate against
        :param uid2sym_vars: dictionary relating the uid of a var with its array name (i.e. var[0])
        :param uid2sym_params:
        :return:
                jac_fn : callable(values: np.ndarray) -> scipy.sparse.csc_matrix
                    Fast evaluator in which *values* is a 1‑D NumPy vector of length
                    ``len(variables)``.
                sparsity_pattern : tuple(np.ndarray, np.ndarray)
                    Row/col indices of structurally non‑zero entries.
        """

        # Ensure deterministic variable order
        check_set = set()
        for v in variables:
            if v in check_set:
                raise ValueError(f"Repeated var {v.name} in the variables' list :(")
            else:
                check_set.add(v)

        # Cache compiled partials by UID so duplicates are reused
        fn_cache: Dict[str, Callable] = {}
        triplets: List[Tuple[int, int, Callable]] = []  # (col, row, fn)

    
        for row, eq in enumerate(eqs):
            for col, var in enumerate(variables):
                d_expression = eq.diff(var).simplify()
                for diff_var in diff_vars:
                    if eq.diff(diff_var) != 0:

                        diff_2_var = DiffVar(base_var=diff_var)
                        dx2_dt2, lags1 = diff_2_var.approximation_expr(dt=dt)
                        dx_dt, lags2   = diff_var.approximation_expr(dt=dt)
                        d_expression = dx_dt*d_expression + dx2_dt2*eq.diff(diff_var).simplify()

                        set_lags1 = set( LagVar(base_var=var.original_var, lag = lag) for lag in range(1, lags1+1))
                        set_lags2 = set( LagVar(base_var=var.original_var, lag = lag) for lag in range(1, lags2+1))
                        new_lags = (set_lags1 | set_lags2) - self._lag_vars_set

                        new_lag_vars = sorted(new_lags, key=lambda x: x.uid)
                        self._lag_vars_set.update(new_lags)
                        for v in new_lag_vars:  # deterministic
                            uid2sym_vars[v.uid] = f"vars[{i}]"
                            self.uid2idx_vars[v.uid] = i
                            self._lag_vars.append(v)
                        i += 1
                if isinstance(d_expression, Const) and d_expression.value == 0:
                    continue  # structural zero

                function_ptr = _compile_equations(eqs=[d_expression], uid2sym_vars=uid2sym_vars,
                                                  uid2sym_params=uid2sym_params)

                fn = fn_cache.setdefault(d_expression.uid, function_ptr)

                triplets.append((col, row, fn))

        # Sort by column, then row for CSC layout
        triplets.sort(key=lambda t: (t[0], t[1]))
        cols_sorted, rows_sorted, fns_sorted = zip(*triplets) if triplets else ([], [], [])

        nnz = len(fns_sorted)
        indices = np.fromiter(rows_sorted, dtype=np.int32, count=nnz)
        data = np.empty(nnz, dtype=np.float64)

        indptr = np.zeros(len(variables) + 1, dtype=np.int32)
        for c in cols_sorted:
            indptr[c + 1] += 1
        np.cumsum(indptr, out=indptr)

        def jac_fn(values: np.ndarray, params) -> sp.csc_matrix:  # noqa: D401 – simple
            assert len(values) >= len(variables)
            for k, fn_ in enumerate(fns_sorted):
                data[k] = fn_(values, params)
            return sp.csc_matrix((data, indices, indptr), shape=(len(eqs), len(variables)))

        return jac_fn
