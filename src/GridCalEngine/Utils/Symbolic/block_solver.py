# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0


from __future__ import annotations

import pdb
from typing import Tuple
import numpy as np
import numba as nb
import math
import scipy.sparse as sp
from scipy.sparse.linalg import spsolve
from scipy.sparse import csr_matrix, coo_matrix
from typing import Dict, List, Literal, Any, Callable, Sequence

from GridCalEngine.Utils.Symbolic.events import Events, Event
from GridCalEngine.Utils.Symbolic.symbolic import Var, Expr, Const, _emit
from GridCalEngine.Utils.Symbolic.block import Block
from GridCalEngine.Utils.Sparse.csc import pack_4_by_4_scipy


def _fully_substitute(expr: Expr, mapping: Dict[Var, Expr], max_iter: int = 10) -> Expr:
    cur = expr
    for _ in range(max_iter):
        nxt = cur.subs(mapping).simplify()
        if str(nxt) == str(cur):  # no further change
            break
        cur = nxt
    return cur


def _compile_equations(eqs: Sequence[Expr],
                       uid2sym_vars: Dict[int, str],
                       uid2sym_params: Dict[int, str],
                       add_doc_string: bool = True) -> Callable[[np.ndarray, np.ndarray], np.ndarray]:
    """
    Compile the array of expressions to a function that returns an array of values for those expressions
    :param eqs: Iterable of expressions (Expr)
    :param uid2sym: dictionary relating the uid of a var with its array name (i.e. var[0])
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


def _get_jacobian(eqs: List[Expr],
                  variables: List[Var],
                  uid2sym_vars: Dict[int, str],
                  uid2sym_params: Dict[int, str],):
    """
    JIT‑compile a sparse Jacobian evaluator for *equations* w.r.t *variables*.
    :param eqs: Array of equations
    :param variables: Array of variables to differentiate against
    :param uid2sym: dictionary relating the uid of a var with its array name (i.e. var[0])
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
            if isinstance(d_expression, Const) and d_expression.value == 0:
                continue  # structural zero

            function_ptr = _compile_equations(eqs=[d_expression], uid2sym_vars=uid2sym_vars, uid2sym_params=uid2sym_params)

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
        for k, fn in enumerate(fns_sorted):
            data[k] = fn(values, params)
        return sp.csc_matrix((data, indices, indptr), shape=(len(eqs), len(variables)))

    return jac_fn


class BlockSolver:
    """
    A network of Blocks that behaves roughly like a Simulink diagram.
    """

    def __init__(self, block_system: Block):
        """
        Constructor        
        :param block_system: BlockSystem
        """
        self.block_system: Block = block_system

        # Flatten the block lists, preserving declaration order
        self._algebraic_vars: List[Var] = list()
        self._algebraic_eqs: List[Expr] = list()
        self._state_vars: List[Var] = list()
        self._state_eqs: List[Expr] = list()
        self._parameters: List[Const] = list()

        for b in self.block_system.get_all_blocks():
            self._algebraic_vars.extend(b.algebraic_vars)
            self._algebraic_eqs.extend(b.algebraic_eqs)
            self._state_vars.extend(b.state_vars)
            self._state_eqs.extend(b.state_eqs)
            self._parameters.extend(b.parameters)

        self._n_state = len(self._state_vars)
        self._n_vars = len(self._state_vars) + len(self._algebraic_vars)
        self._n_params = len(self._parameters)

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

        for i, ep in enumerate(self._parameters):
            uid2sym_params[ep.uid] = f"params[{i}]"
            self.uid2idx_params[ep.uid] = i
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
        self._rhs_state_fn = _compile_equations(eqs=self._state_eqs, uid2sym_vars=uid2sym_vars,uid2sym_params=uid2sym_params)
        self._rhs_algeb_fn = _compile_equations(eqs=self._algebraic_eqs, uid2sym_vars=uid2sym_vars,uid2sym_params=uid2sym_params)

        self._j11_fn = _get_jacobian(eqs=self._state_eqs, variables=self._state_vars, uid2sym_vars=uid2sym_vars,uid2sym_params=uid2sym_params)
        self._j12_fn = _get_jacobian(eqs=self._state_eqs, variables=self._algebraic_vars, uid2sym_vars=uid2sym_vars,uid2sym_params=uid2sym_params)
        self._j21_fn = _get_jacobian(eqs=self._algebraic_eqs, variables=self._state_vars, uid2sym_vars=uid2sym_vars,uid2sym_params=uid2sym_params)
        self._j22_fn = _get_jacobian(eqs=self._algebraic_eqs, variables=self._algebraic_vars, uid2sym_vars=uid2sym_vars,uid2sym_params=uid2sym_params)

        print("done!")

    def get_var_idx(self, v: Var) -> int:
        return self.uid2idx_vars[v.uid]

    def get_vars_idx(self, variables: Sequence[Var]) -> np.ndarray:
        return np.array([self.uid2idx_vars[v.uid] for v in variables])

    def sort_vars(self, mapping: dict[Var, float]) -> np.ndarray:
        """
        Helper function to build the initial vector
        :param mapping: var->initial value mapping
        :return: array matching with the mapping, matching the solver ordering
        """
        x = np.zeros(len(self._state_vars) + len(self._algebraic_vars), dtype=object)

        for key, val in mapping.items():
            i = self.uid2idx_vars[key.uid]
            x[i] = key

        return x

    def build_init_vars_vector(self, mapping: dict[Var, float]) -> np.ndarray:
        """
        Helper function to build the initial vector
        :param mapping: var->initial value mapping
        :return: array matching with the mapping, matching the solver ordering
        """
        x = np.zeros(len(self._state_vars) + len(self._algebraic_vars))

        for key, val in mapping.items():
            i = self.uid2idx_vars[key.uid]
            x[i] = val

        return x

    def build_init_params_vector(self, mapping: dict[Var, float]) -> np.ndarray:
        """
        Helper function to build the initial vector
        :param mapping: var->initial value mapping
        :return: array matching with the mapping, matching the solver ordering
        """
        x = np.zeros(self._n_params)

        for key, val in mapping.items():
            i = self.uid2idx_params[key.uid]
            x[i] = val

        return x

    def rhs_fixed(self, x: np.ndarray) -> np.ndarray:
        """
        Return 𝑑x/dt given the current *state* vector.
        :param x: get the right-hand-side give a state vector
        :return [f_state_update, f_algeb]
        """
        f_algeb = np.array(self._rhs_algeb_fn(x))

        if self._n_state > 0:
            f_state = np.array(self._rhs_state_fn(x))
            return np.r_[f_state, f_algeb]
        else:
            return f_algeb

    def rhs_implicit(self, x: np.ndarray, xn: np.ndarray, params: np.ndarray, sim_step, h: float) -> np.ndarray:
        """
        Return 𝑑x/dt given the current *state* vector.
        :param x: get the right-hand-side give a state vector
        :param xn:
        :param params: params array
        :param sim_step: simulation step
        :param h: simulation step
        :return [f_state_update, f_algeb]
        """
        f_algeb = np.array(self._rhs_algeb_fn(x, params))
        sim_step = sim_step
        if self._n_state > 0:
            f_state = np.array(self._rhs_state_fn(x, params))
            f_state_update = x[:self._n_state] - xn[:self._n_state] - h * f_state
            return np.r_[f_state_update, f_algeb]

        else:
            return f_algeb

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

    def get_dummy_x0(self):
        return np.zeros(self._n_state)

    def equations(self) -> Tuple[List[Expr], List[Expr]]:
        """
        Return (algebraic_eqs, state_eqs) as *originally declared* (no substitution).
        """
        return self._algebraic_eqs, self._state_eqs


    def build_params_matrix(self, n_steps: int, params0: np.ndarray, events_list: Events) -> csr_matrix:
        events_matrix = np.zeros((n_steps, len(params0)))
        diff_params_matrix = np.zeros((n_steps, len(params0)))
        params_matrix_current = params0

        # get events info
        rows, cols, values = events_list.build_triplets_list()

        # build diff sparse matrix
        for i, row in enumerate(events_matrix):
            if i in rows:
                positions = np.where(rows == i)
                for position in positions:
                    time_step = i
                    prop_idx = self.uid2idx_params[cols[position][0].uid]
                    value = values[position]
                    diff_val = value - params_matrix_current[prop_idx]
                    diff_params_matrix[time_step][prop_idx] += diff_val
                    params_matrix_current[prop_idx] = value

        # make params matrix sparse
        diff_params_matrix_spa = csr_matrix(diff_params_matrix)
        return diff_params_matrix_spa

    def simulate(
            self,
            t0: float,
            t_end: float,
            h: float,
            x0: np.ndarray,
            params0: np.ndarray,
            events_list: Events,
            method: Literal["rk4", "euler", "implicit_euler"] = "rk4",
            newton_tol: float = 1e-8,
            newton_max_iter: int = 1000,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        :param events_list:
        :param params0:
        :param t0: start time
        :param t_end: end time
        :param h: step
        :param x0: initial values
        :param method: method
        :param newton_tol:
        :param newton_max_iter:
        :return: 1D time array, 2D array of simulated variables
        """
        params_matrix = self.build_params_matrix(int(np.ceil((t_end - t0) / h)), params0, events_list)
        if method == "euler":
            return self._simulate_fixed(t0, t_end, h, x0, stepper="euler")
        if method == "rk4":
            return self._simulate_fixed(t0, t_end, h, x0, stepper="rk4")
        if method == "implicit_euler":
            return self._simulate_implicit_euler(
                t0, t_end, h, x0, params0, params_matrix,
                tol=newton_tol, max_iter=newton_max_iter,
            )
        raise ValueError(f"Unknown method '{method}'")

    def _simulate_fixed(self, t0, t_end, h, x0, stepper="euler"):
        """
        Fixed‑step helpers (Euler, RK‑4)
        :param t0:
        :param t_end:
        :param h:
        :param x0:
        :param stepper:
        :return:
        """
        steps = int(np.ceil((t_end - t0) / h))
        t = np.empty(steps + 1)
        y = np.empty((steps + 1, self._n_vars))
        t[0] = t0
        y[0, :] = x0.copy()

        for i in range(steps):
            tn = t[i]
            xn = y[i]
            if stepper == "euler":
                k1 = self.rhs_fixed(xn)
                y[i + 1] = xn + h * k1
            elif stepper == "rk4":
                k1 = self.rhs_fixed(xn)
                k2 = self.rhs_fixed(xn + 0.5 * h * k1)
                k3 = self.rhs_fixed(xn + 0.5 * h * k2)
                k4 = self.rhs_fixed(xn + h * k3)
                y[i + 1] = xn + (h / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)
            else:
                raise RuntimeError("unknown stepper")
            t[i + 1] = tn + h
        return t, y

    def _simulate_implicit_euler(self, t0, t_end, h, x0, params0: np.ndarray, diff_params_matrix, tol=1e-8, max_iter=1000):
        """
        :param t0:
        :param t_end:
        :param h:
        :param x0:
        :params_matrix:
        :param tol:
        :param max_iter:
        :return:
        """
        steps = int(np.ceil((t_end - t0) / h))
        t = np.empty(steps + 1)
        y = np.empty((steps + 1, self._n_vars))
        params_current = params0
        diff_params_matrix = diff_params_matrix
        t[0] = t0
        y[0] = x0.copy()

        for step_idx in range(steps):
            params_current += diff_params_matrix[step_idx, :].toarray().ravel()
            xn = y[step_idx]
            x_new = xn.copy()  # initial guess
            converged = False
            n_iter = 0
            while not converged and n_iter < max_iter:
                rhs = self.rhs_implicit(x_new, xn, params_current, step_idx, h)
                converged = np.linalg.norm(rhs, np.inf) < tol

                if converged:
                    break
                Jf = self.jacobian_implicit(x_new,params_current, h)  # sparse matrix
                delta = sp.linalg.spsolve(Jf, -rhs)
                x_new += delta
                n_iter += 1

            if converged:

                y[step_idx + 1] = x_new
                t[step_idx + 1] = t[step_idx] + h

            else:
                print(f"Failed to converge at step {step_idx}")
                break

        return t, y
