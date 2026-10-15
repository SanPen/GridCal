# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
import numba as nb
import scipy.sparse as sp
import cProfile as profile
import time
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Expr, BinOp, UnOp, Func

from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import (
    EmtBoundaryUpdateProtocol,
    EmtProblemTemplate,
    get_solver_forced_event_time,
    is_problem_owned_boundary_updater,
    resolve_solver_boundary_step,
    resolve_solver_boundary_updater,
)
from VeraGridEngine.enumerations import DynamicIntegrationMethod

from VeraGridEngine.Utils.Symbolic.jit_compiler import EagerEquationCompiler, EquationCompiler
from VeraGridEngine.Utils.Symbolic.diagnostic import (with_newton_diagnostics, NewtonDiagnosticsConfig,
                                                       NewtonSolveContext, dense_lstsq_fallback,
                                                         sparse_lsqr_fallback, maybe_check_index1,
                                                         maybe_apply_backtracking)
from VeraGridEngine.Simulations.driver_template import DummySignal
from VeraGridEngine.basic_structures import Vec, Mat
from typing import Tuple, Callable, List, Any, Dict, Set, Union
from scipy.sparse import csc_matrix

def _safe_njit(py_func: Callable[..., Any], fastmath: bool = True, cache: bool = True, signature: Any = None) -> Callable[..., Any]:
    """
    Safely wraps a python function with Numba's njit compiler.
    The caller must explicitly pass cache=False if the function is generated via strings.

    :param py_func: The python function to compile.
    :type py_func: Callable[..., Any]
    :param fastmath: Flag to enable fastmath operations, defaults to True.
    :type fastmath: bool
    :param cache: Flag to enable caching of the compiled function, defaults to True.
    :type cache: bool
    :param signature: Optional Numba signature.
    :type signature: Any
    :return: The Numba JIT compiled function.
    :rtype: Callable[..., Any]
    """
    if signature is not None:
        compiled_kernel: Callable[..., Any] = nb.jit(signature, fastmath=fastmath, cache=cache)(py_func)
    else:
        compiled_kernel = nb.jit(fastmath=fastmath, cache=cache)(py_func)

    return compiled_kernel

# ==============================================================================
# Sparse Forward-Mode AD Jacobian with Graph Coloring (JVP-based)
# ==============================================================================

@nb.jit(cache=True, fastmath=True)
def _scatter_color_jvp_to_csc_data(jvp: np.ndarray,
                                   data: np.ndarray,
                                   color_ptr: np.ndarray,
                                   col_ptr: np.ndarray,
                                  row_idx: np.ndarray,
                                  data_idx: np.ndarray,
                                  color_id: int) -> None:
    """
    Scatter a single JVP evaluation into the CSC data array for all columns in a given color.
    """
    k0: int = int(color_ptr[color_id])
    k1: int = int(color_ptr[color_id + 1])
    for k in range(k0, k1):
        p0: int = int(col_ptr[k])
        p1: int = int(col_ptr[k + 1])
        for p in range(p0, p1):
            data[data_idx[p]] = jvp[row_idx[p]]


def _compile_master_jacobian_kernel(ad_kernel: Callable[..., Any], n_colors: int) -> Callable[..., Any]:
    """
    Build the eager sparse Jacobian dispatcher.

    :param ad_kernel: Generic AD kernel reused across graph colors.
    :type ad_kernel: Callable[..., Any]
    :param n_colors: Number of graph colors.
    :type n_colors: int
    :return: Jacobian dispatcher.
    :rtype: Callable[..., Any]
    """
    return SparseAdMasterJacobianDispatcher(ad_kernel=ad_kernel, n_colors=n_colors)


class SparseAdMasterJacobianDispatcher:
    """
    Callable dispatcher that executes one generic AD kernel across all colors.
    """

    __slots__ = ("_ad_kernel", "_n_colors")

    def __init__(self, ad_kernel: Callable[..., Any], n_colors: int) -> None:
        """
        Store the generic AD kernel and the number of graph colors.

        :param ad_kernel: Generic AD kernel reused across graph colors.
        :param n_colors: Number of graph colors.
        :return: None.
        """
        self._ad_kernel: Callable[..., Any] = ad_kernel
        self._n_colors: int = n_colors

    def __call__(self,
                 states: Vec,
                 seed_matrix: Mat,
                 params: Vec,
                 history: Vec,
                 d_history: Vec,
                 h: float,
                 history2: Vec,
                 data: Vec,
                 color_ptr: np.ndarray,
                 col_ptr: np.ndarray,
                 row_idx: np.ndarray,
                 data_idx: np.ndarray,
                 work_jvp: Mat) -> None:
        """
        Evaluate all color JVPs and scatter them into CSC data storage.

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
            local_jvp: Vec = work_jvp[color_index]
            self._ad_kernel(states, seed_matrix[color_index], params, history, d_history, h, local_jvp, history2)
            _scatter_color_jvp_to_csc_data(local_jvp, data, color_ptr, col_ptr, row_idx, data_idx, color_index)
            color_index += 1


def greedy_color_columns(col_rows: List[List[int]], n_rows: int) -> Tuple[np.ndarray, int]:
    """
    Computes a greedy coloring of the column dependency graph to minimize AD sweeps.

    :param col_rows: List of row indices where each column has non-zeros.
    :type col_rows: List[List[int]]
    :param n_rows: Total number of rows in the matrix.
    :type n_rows: int
    :return: An array of color IDs per column and the total number of colors.
    :rtype: Tuple[np.ndarray, int]
    """
    n_cols: int = len(col_rows)
    row_cols: List[List[int]] = [list() for _ in range(n_rows)]
    for j in range(n_cols):
        for r in col_rows[j]:
            row_cols[r].append(j)

    adj: List[Set[int]] = [set() for _ in range(n_cols)]
    for cols in row_cols:
        m: int = len(cols)
        for a in range(m):
            ja: int = cols[a]
            for b in range(a + 1, m):
                jb: int = cols[b]
                if jb != ja:
                    adj[ja].add(jb)
                    adj[jb].add(ja)
                else:
                    pass

    degrees: np.ndarray = np.array([len(adj[j]) for j in range(n_cols)], dtype=np.int32)
    order: List[int] = list(np.argsort(-degrees, kind="stable"))
    colors: np.ndarray = -np.ones(n_cols, dtype=np.int32)
    max_color: int = -1
    used: np.ndarray = np.zeros(n_cols, dtype=np.bool_)

    for j in order:
        used[:] = False
        for nbj in adj[j]:
            c: int = int(colors[nbj])
            if c >= 0:
                used[c] = True
            else:
                pass

        c_iter: int = 0
        while c_iter < n_cols and used[c_iter]:
            c_iter += 1

        colors[j] = c_iter
        if c_iter > max_color:
            max_color = c_iter
        else:
            pass

    return colors, int(max_color + 1)

class BoundaryUpdaterInterface:
    __slots__ = ()

    def update(
        self,
        t: float,
        x_prev: Vec,
        full_params: Vec,
    ) -> float | None:
        """Update boundary values and optionally request a shortened retry.

        :param t: Candidate endpoint time.
        :param x_prev: Accepted EMT state vector.
        :param full_params: Parameter vector updated in place.
        :return: Earlier retry target or ``None``.
        """

        raise NotImplementedError

    def get_next_forced_event_time(self, t_prev: float, t_target: float) -> float | None:
        raise NotImplementedError

class Predictor:
    """
    Computes an explicit predictor for the Newton initial guess x_iter.
    """
    __slots__ = ['n_states']

    def __init__(self,
                 n_states: int) -> None:
        self.n_states = n_states

    def predict(self,
                x_iter: Vec,
                x_prev: Vec,
                dx_prev: Vec,
                h: float,
                pred_method: Union[DynamicIntegrationMethod|None] = DynamicIntegrationMethod.DaeBackEuler) -> Vec:
        """
        Apply predictor in-place and return x_iter.
        :param x_iter: Array to be written with the predictor guess (in-place).
        :param x_prev: Previous full variable vector at time n.
        :param dx_prev: Previous derivative vector (only first n_states are meaningful).
        :param h: Time step.
        :param pred_method: Integration method enum/value at the prediction step
        :return:
        """

        # Default: no-op predictor
        x_iter[:] = x_prev

        # Dispatch per method
        if pred_method == DynamicIntegrationMethod.OdeEuler:
            return self._predict_euler_state(x_iter, x_prev, dx_prev, h)
        elif pred_method == DynamicIntegrationMethod.DaeBDF2:
            raise NotImplementedError(f"predictor method {pred_method} ")

        # Otherwise keep default x_iter = x_prev
        return x_iter

    # ---------------------------------------------------------------------
    # Predictor implementations
    # ---------------------------------------------------------------------
    def _predict_euler_state(self,
                             x_iter: Vec,
                             x_prev: Vec,
                             dx_prev: Vec,
                             h: float) -> Vec:
        """
        Explicit Euler predictor for the *state* subset:
            x_{n+1}^0 = x_n + h * dx_n   (states only)
        Algebraics remain at x_prev by default (already set in caller).
        """
        ns = self.n_states
        x_iter[:ns] = x_prev[:ns] + h * dx_prev[:ns]
        return x_iter


def fill_full_parameter_buffer(runtime_params: Vec, static_params: Vec, full_params_out: Vec) -> None:
    """
    Write runtime and static parameters into one preallocated full buffer.

    :param runtime_params: Runtime parameter slice.
    :type runtime_params: Vec
    :param static_params: Static parameter slice.
    :type static_params: Vec
    :param full_params_out: Destination full parameter vector.
    :type full_params_out: Vec
    :return: None.
    :rtype: None
    """
    n_runtime: int = runtime_params.shape[0]
    n_static: int = static_params.shape[0]

    # The runtime portion must be refreshed every local substep because events
    # and boundary updates can change it in place.
    full_params_out[:n_runtime] = runtime_params

    # The static portion is copied after the runtime slice so the solver sees a
    # stable [runtime | static] layout in every backend call.
    full_params_out[n_runtime:n_runtime + n_static] = static_params


def evaluate_batched_residual(
        kernel_list: List[Callable[..., Any]],
        x_iter: Vec,
        full_params: Vec,
        x_prev: Vec,
        dx_prev: Vec,
        h_eff: float,
        x_prev2: Vec,
        residual_out: Vec,
) -> float:
    """
    Evaluate all residual batches into a caller-owned buffer.

    :param kernel_list: Batched residual kernels.
    :type kernel_list: List[Callable[..., Any]]
    :param x_iter: Current Newton iterate.
    :type x_iter: Vec
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
    :param residual_out: Destination residual buffer.
    :type residual_out: Vec
    :return: Residual infinity norm.
    :rtype: float
    """
    residual_out[:] = 0.0

    # The residual is assembled batch by batch because the symbolic compiler
    # splits large systems to keep code generation robust.
    for kernel in kernel_list:
        kernel(x_iter, full_params, x_prev, dx_prev, h_eff, residual_out, x_prev2)

    return float(np.linalg.norm(residual_out, np.inf))


class AdBacktrackingResidualEvaluator:
    """
    Wrapper that evaluates AD residual batches for line-search backtracking.
    """

    __slots__ = ["_kernel_list", "_full_params", "_x_prev", "_dx_prev", "_h_eff", "_x_prev2"]

    def __init__(self) -> None:
        """
        Build one empty backtracking evaluator.

        :return: None.
        :rtype: None
        """
        self._kernel_list: List[Callable[..., Any]] | None = None
        self._full_params: Vec | None = None
        self._x_prev: Vec | None = None
        self._dx_prev: Vec | None = None
        self._h_eff: float = 0.0
        self._x_prev2: Vec | None = None

    def set_context(
            self,
            kernel_list: List[Callable[..., Any]],
            full_params: Vec,
            x_prev: Vec,
            dx_prev: Vec,
            h_eff: float,
            x_prev2: Vec,
    ) -> None:
        """
        Store the residual-evaluation context of the current Newton step.

        :param kernel_list: Batched residual kernels.
        :type kernel_list: List[Callable[..., Any]]
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
        :return: None.
        :rtype: None
        """
        self._kernel_list = kernel_list
        self._full_params = full_params
        self._x_prev = x_prev
        self._dx_prev = dx_prev
        self._h_eff = float(h_eff)
        self._x_prev2 = x_prev2

    def evaluate(self, candidate_x: Vec, out_res: Vec) -> float:
        """
        Evaluate one trial Newton iterate during backtracking.

        :param candidate_x: Trial iterate.
        :type candidate_x: Vec
        :param out_res: Destination residual buffer.
        :type out_res: Vec
        :return: Residual infinity norm.
        :rtype: float
        """
        if self._kernel_list is None:
            return np.inf
        else:
            pass

        if self._full_params is None or self._x_prev is None or self._dx_prev is None or self._x_prev2 is None:
            return np.inf
        else:
            pass

        return evaluate_batched_residual(
            kernel_list=self._kernel_list,
            x_iter=candidate_x,
            full_params=self._full_params,
            x_prev=self._x_prev,
            dx_prev=self._dx_prev,
            h_eff=self._h_eff,
            x_prev2=self._x_prev2,
            residual_out=out_res,
        )

class SparseADJacobian:
    """
    Sparse Jacobian evaluator with DEBUG TIMING.
    """
    __slots__ = [
        'equations', 'variables', 'parameters', 'method', 'use_cse', 'dtype',
        'n_rows', 'n_cols', 'var_map', 'param_map', 'col_rows', 'J',
        'colors', 'n_colors', 'color_groups', 'color_ptr', 'color_cols',
        'col_ptr', 'row_idx', 'data_idx', '_compiler', '_ad_kernel', '_master_dispatcher',
        '_seed_matrix', '_jvp_work_buffer', '_data_buffer'
    ]

    def __init__(self,
                 equations: List[Any],
                 variables: List[Any],
                 parameters: List[Any],
                 method: DynamicIntegrationMethod,
                 use_cse: bool = True,
                 dtype: Any=np.float64)-> None:

        t_start = time.perf_counter()
        print_enabled: bool = False

        self.equations = equations
        self.variables = variables
        self.parameters = parameters
        self.method = method
        self.use_cse = use_cse
        self.dtype = dtype

        self.n_rows = len(equations)
        self.n_cols = len(variables)

        self.var_map: Dict[int, int] = dict()
        for i, v in enumerate(variables):
            self.var_map[v.uid] = i

        self.param_map: Dict[int, int] = dict()
        for i, p in enumerate(parameters):
            self.param_map[p.uid] = i

        t_maps: float = time.perf_counter()
        if print_enabled:
            print(f"   [AD-Debug] Maps built in {t_maps - t_start:.4f}s")

        # 1) Sparsity Detection
        col_rows: List[List[int]] = [list() for _ in range(self.n_cols)]

        count_edges: int = 0
        for r, eq in enumerate(equations):
            stack: List[Any] = list()
            stack.append(eq)
            visited: Set[int] = set()
            uids: Set[int] = set()

            while stack:
                n: Any = stack.pop()
                if id(n) in visited:
                    pass
                else:
                    visited.add(id(n))

                    match n:
                        case Var(uid=u, base_var=bv):
                            uids.add(u)
                            if bv is not None:
                                uids.add(bv.uid)
                            else:
                                pass
                        case BinOp(left=l, right=r_node):
                            stack.append(l)
                            stack.append(r_node)
                        case UnOp(operand=op):
                            stack.append(op)
                        case Func(arg=a):
                            stack.append(a)
                        case _:
                            pass

            for uid in uids:
                j: int | None = self.var_map.get(uid, None)
                if j is not None:
                    col_rows[j].append(r)
                    count_edges += 1
                else:
                    pass

        self.col_rows = [sorted(set(rows)) for rows in col_rows]

        t_sparsity = time.perf_counter()
        if print_enabled:
            print(f"   [AD-Debug] Sparsity Analysis done in {t_sparsity - t_maps:.4f}s. Edges found: {count_edges}")

        # 2) CSC Structure
        indptr = np.zeros(self.n_cols + 1, dtype=np.int32)
        nnz = 0
        for j in range(self.n_cols):
            nnz += len(self.col_rows[j])
            indptr[j + 1] = nnz

        indices = np.empty(nnz, dtype=np.int32)
        data = np.zeros(nnz, dtype=self.dtype)
        k = 0
        for j in range(self.n_cols):
            for r in self.col_rows[j]:
                indices[k] = r
                k += 1

        self.J = csc_matrix((data, indices, indptr), shape=(self.n_rows, self.n_cols))

        t_csc = time.perf_counter()
        if print_enabled:
            print(f"   [AD-Debug] CSC Matrix built in {t_csc - t_sparsity:.4f}s")

        # 3) Coloring
        self.colors, self.n_colors = greedy_color_columns(self.col_rows, self.n_rows)
        groups: List[List[int]] = [list() for _ in range(self.n_colors)]
        for j in range(self.n_cols):
            groups[self.colors[j]].append(j)
        self.color_groups = groups

        t_color = time.perf_counter()
        if print_enabled:
            print(f"   [AD-Debug] Graph Coloring done in {t_color - t_csc:.4f}s. Colors: {self.n_colors}")

        # 4) Precompute scatter map
        color_cols: List[int] = list()
        color_ptr = np.zeros(self.n_colors + 1, dtype=np.int32)
        for c in range(self.n_colors):
            color_ptr[c] = len(color_cols)
            color_cols.extend(self.color_groups[c])
        color_ptr[self.n_colors] = len(color_cols)

        col_ptr = np.zeros(len(color_cols) + 1, dtype=np.int32)
        total_map = 0
        for kk, j in enumerate(color_cols):
            total_map += len(self.col_rows[j])
            col_ptr[kk + 1] = total_map

        row_idx = np.empty(total_map, dtype=np.int32)
        data_idx = np.empty(total_map, dtype=np.int32)
        pos = 0
        indptr_arr = self.J.indptr
        for kk, j in enumerate(color_cols):
            base = indptr_arr[j]
            rows = self.col_rows[j]
            for local, r in enumerate(rows):
                row_idx[pos] = r
                data_idx[pos] = base + local
                pos += 1

        self.color_ptr = color_ptr
        self.color_cols = np.asarray(color_cols, dtype=np.int32)
        self.col_ptr = col_ptr
        self.row_idx = row_idx
        self.data_idx = data_idx

        t_scatter = time.perf_counter()
        if print_enabled:
            print(f"   [AD-Debug] Scatter Map built in {t_scatter - t_color:.4f}s")

        # 5) Compile Optimization: one generic eager AD kernel reused across colors.
        self._compiler = EagerEquationCompiler(variables=variables, parameters=parameters, method=method)

        if print_enabled:
            print(f"   [AD-Opt] Compiling one generic AD kernel for {self.n_colors} colors...")
        t_comp_start = time.perf_counter()

        k_name = f"ad_step_generic_{self.method.name}_{self.n_rows}_{self.n_cols}"
        py_ad, signature_tpe = self._compiler.compile_ad_kernel(
            equations,
            func_name=k_name,
            use_cse=use_cse,
            active_indices=None,
        )

        self._ad_kernel = _safe_njit(py_ad, cache=True, fastmath=True, signature=signature_tpe)
        self._master_dispatcher = _compile_master_jacobian_kernel(self._ad_kernel, self.n_colors)

        self._seed_matrix = np.zeros((self.n_colors, self.n_cols), dtype=self.dtype)
        for c in range(self.n_colors):
            self._seed_matrix[c, self.color_groups[c]] = 1.0

        self._jvp_work_buffer = np.zeros((self.n_colors, self.n_rows), dtype=self.dtype)
        self._data_buffer = self.J.data

        t_comp_end = time.perf_counter()
        if print_enabled:
            print(f"   [AD-Opt] Generic kernel compiled in {t_comp_end - t_comp_start:.4f}s")
            print(f"   [AD-Debug] Total Init Time: {t_comp_end - t_start:.4f}s")

    def __call__(self,
                 states: np.ndarray,
                 params: np.ndarray,
                 history: np.ndarray,
                 d_history: np.ndarray,
                 h: float,
                 history2: Union[np.ndarray | None] = None) -> csc_matrix:
        """
        Evaluates the AD Jacobian.

        :param states: Current states.
        :type states: np.ndarray
        :param params: Current parameters.
        :type params: np.ndarray
        :param history: State history.
        :type history: np.ndarray
        :param d_history: Derivative history.
        :type d_history: np.ndarray
        :param h: Time step.
        :type h: float
        :param history2: Secondary state history.
        :type history2: np.ndarray | None
        :return: Evaluated sparse matrix.
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
            self.color_ptr,
            self.col_ptr,
            self.row_idx,
            self.data_idx,
            self._jvp_work_buffer,
        )
        return self.J

class JitAdSolver:
    __slots__ = [
        'problem', 't0', 't_end', 'h', 'method', 'pred_method', 'dense_threshold', 'verbose', 'newton_max_iter',
        'steps', 't', 'y', 'dy',  'jit_kernels_ad', 'jit_jacobian_ad',
        'state_vars', 'algebraic_vars', 'state_eqs', 'algebraic_eqs', '_newton_diag_config',
        '_predictor', '_runtime_param_count', '_static_parameter_buffer', '_full_parameter_buffer',
        '_residual_buffer', '_trial_state_buffer', '_trial_residual_buffer',
        '_backend_build_stats', '_last_runtime_stats', '_last_sim_loop_time', '_cancel_checker', '_progress_signal',
        '_newton_tolerance'
    ]
    def __init__(self,
                 problem: EmtProblemTemplate,
                 t0: float,
                 t_end: float,
                 h: float,
                 method: DynamicIntegrationMethod = DynamicIntegrationMethod.DaeTrapezoidal,
                 pred_method: DynamicIntegrationMethod = None,
                 dense_threshold: int = 100,
                 verbose: bool = False,
                 newton_max_iter: int = 15,
                 newton_diag_config: NewtonDiagnosticsConfig | None = None,
                 progress_signal: DummySignal | None = None,
                 cancel_checker: Callable[[], bool] | None = None,
                 newton_tolerance: float = 1.0e-6)-> None:
        """
        Initializes the JIT AD Solver.

        :param problem: The DAE problem definition.
        :type problem: EmtProblemTemplate
        :param t0: Initial time.
        :type t0: float
        :param t_end: End time.
        :type t_end: float
        :param h: Time step.
        :type h: float
        :param method: DynamicIntegrationMethod (DaeTrapezoidal, DaeBackEuler, DaeBDF2).
        :type method: DynamicIntegrationMethod
        :param pred_method: DynamicIntegrationMethod used in the predictor step if method is explicit.
        :type pred_method: DynamicIntegrationMethod
        :param dense_threshold: Threshold to switch between dense and sparse linear solvers.
        :type dense_threshold: int
        :param verbose: Print compilation and simulation timings.
        :type verbose: bool
        :param newton_max_iter: Maximum Newton iterations per local EMT substep.
        :type newton_max_iter: int
        :param newton_tolerance: Absolute infinity-norm tolerance for Newton residual convergence.
        :type newton_tolerance: float
        :param progress_signal: Optional progress signal updated during the simulation loop.
        :type progress_signal: DummySignal | None
        """
        self.problem = problem
        self.t0 = t0
        self.h = h
        self.method = method
        self.pred_method = pred_method
        self.dense_threshold = dense_threshold
        self.verbose = verbose
        self.newton_max_iter: int = int(newton_max_iter)
        self._newton_tolerance: float = float(newton_tolerance)
        if not np.isfinite(self._newton_tolerance) or self._newton_tolerance <= 0.0:
            raise ValueError("newton_tolerance must be finite and greater than zero.")
        self.t_end = t_end
        self._newton_diag_config = newton_diag_config or NewtonDiagnosticsConfig(
            compute_dense_cond=False,
            enable_fallback=False,
            enable_index1_check=False,
            enable_backtracking=False,
        )

        self.steps = int(np.ceil((t_end - t0) / h))
        self.t: Vec = np.empty(self.steps + 1)
        self.y: Mat = np.empty((self.steps + 1, self.problem.get_all_vars_number()))
        self.dy: Mat = np.empty((self.steps + 1, self.problem.get_diff_var_number()))

        # Solver specific caches
        self.jit_kernels_ad: Dict[DynamicIntegrationMethod, List[Callable]] = dict()
        self.jit_jacobian_ad: Dict[DynamicIntegrationMethod, SparseADJacobian] = dict()

        # Cache local of variables to avoid calling getters multiple times in init
        self.state_vars = self.problem.get_state_vars()
        self.algebraic_vars = self.problem.get_algebraic_vars()
        self.state_eqs = self.problem.get_state_eqs()
        self.algebraic_eqs = self.problem.get_algebraic_eqs()

        self._predictor = Predictor(n_states=self.problem.get_states_number())
        self._runtime_param_count: int = self.problem.get_variable_parameter_number()
        self._static_parameter_buffer: Vec = np.asarray(
            [float(constant.value) for constant in self.problem.get_parameters_values()],
            dtype=np.float64,
        )
        self._full_parameter_buffer: Vec = np.zeros(
            self._runtime_param_count + self._static_parameter_buffer.shape[0],
            dtype=np.float64,
        )
        self._residual_buffer: Vec = np.zeros(self.problem.get_all_vars_number(), dtype=np.float64)
        self._trial_state_buffer: Vec = np.zeros(self.problem.get_all_vars_number(), dtype=np.float64)
        self._trial_residual_buffer: Vec = np.zeros(self.problem.get_all_vars_number(), dtype=np.float64)
        self._backend_build_stats: Dict[str, float] = dict(
            residual_compile_s=0.0,
            residual_batches=0.0,
            jacobian_compile_s=0.0,
            jacobian_builds=0.0,
            total_s=0.0,
        )
        self._last_runtime_stats: Dict[str, float] = dict()
        self._last_sim_loop_time: float = 0.0
        self._progress_signal: DummySignal | None = progress_signal
        self._cancel_checker = cancel_checker

    def build_jit_ad(self, only_jacobian: bool = False)-> None:
        """
        Compiles the residual kernel using batching and prepares the Sparse AD Jacobian.

        :param only_jacobian: If True, skips residual compilation (used by Vectorized Engine fallback).
        :type only_jacobian: bool
        :rtype: None
        """
        if self.method in self.jit_kernels_ad and not only_jacobian:
            return
        else:
            pass

        t_total_start: float = time.perf_counter()

        if self.verbose:
            print(
                f"--- [JIT-AD] Compiling {'Jacobian ONLY' if only_jacobian else 'Implicit Kernel + AD Jacobian'} ({self.method}) ---")
        else:
            pass

        sorted_vars: List[Any] = list()
        sorted_vars.extend(self.state_vars)
        sorted_vars.extend(self.algebraic_vars)

        all_params: List[Any] = list()
        all_params.extend(self.problem.get_variable_parameters())
        all_params.extend(self.problem.get_constant_parameters())

        equations: List[Expr] = list()
        for i, rhs in enumerate(self.state_eqs):
            sv = self.state_vars[i]
            d_term = Var(name=f"d_{sv.name}", base_var=sv)
            equations.append(d_term - rhs)
        equations.extend(self.algebraic_eqs)

        # --- PART 1: RESIDUALS (Batched) ---
        if not only_jacobian and self.method not in self.jit_kernels_ad:
            compiler = EquationCompiler(variables=sorted_vars, parameters=all_params, method=self.method)
            BATCH_SIZE = 100
            n_eqs = len(equations)
            batched_kernels: List[Callable] = list()

            if self.verbose:
                print(f"   [JIT-AD] Splitting {n_eqs} residual eqs into {int(np.ceil(n_eqs / BATCH_SIZE))} batches...")
            t0 = time.perf_counter()

            for i in range(0, n_eqs, BATCH_SIZE):
                chunk = equations[i: i + BATCH_SIZE]
                fname = f"jit_step_{self.method}_ad_part_{i}"
                py_func = compiler.compile(chunk, func_name=fname, use_cse=True, offset=i, inplace=True)
                jit_func = _safe_njit(py_func, cache=True, fastmath=True)
                batched_kernels.append(jit_func)

            if self.verbose:
                print(f"   [JIT-AD] Residual Batches compiled in {time.perf_counter() - t0:.4f}s")
            else:
                pass
            self.jit_kernels_ad[self.method] = batched_kernels
            residual_elapsed_s: float = time.perf_counter() - t0
            self._backend_build_stats['residual_compile_s'] += residual_elapsed_s
            self._backend_build_stats['residual_batches'] += float(len(batched_kernels))
            self._backend_build_stats['total_s'] += residual_elapsed_s
        else:
            pass

        # --- PART 2: JACOBIAN (O(N) setup, needed for normal and Vectorized fallback) ---
        if self.method not in self.jit_jacobian_ad:
            jacobian_t0: float = time.perf_counter()
            jac = SparseADJacobian(equations=equations, variables=sorted_vars, parameters=all_params,
                                   method=self.method, use_cse=True)
            self.jit_jacobian_ad[self.method] = jac
            jacobian_elapsed_s: float = time.perf_counter() - jacobian_t0
            self._backend_build_stats['jacobian_compile_s'] += jacobian_elapsed_s
            self._backend_build_stats['jacobian_builds'] += 1.0
            self._backend_build_stats['total_s'] += jacobian_elapsed_s
        else:
            pass

        total_elapsed_s: float = time.perf_counter() - t_total_start
        self._backend_build_stats['total_s'] = max(self._backend_build_stats['total_s'], total_elapsed_s)

    def simulate(self,
                 x0: Union[Vec | None] = None,
                 dx0: Union[Vec | None] = None,
                 params0: Union[Vec | None] = None,
                 boundary_updater: EmtBoundaryUpdateProtocol | None = None) -> Tuple[Vec, Mat, Mat, bool, bool]:
        """
        Main JIT simulation loop using the Automatic Differentiation (AD) backend.

        :param x0: Initial state vector.
        :param dx0: Initial derivative vector.
        :param params0: Initial event parameters.
        :param boundary_updater: Optional override for the problem boundary updater.
        :return: A tuple containing the time vector and state trajectory matrix.
        """
        t_start = time.time()
        method = self.method

        converged: bool = True
        well_initialized: bool = True

        if method not in self.jit_kernels_ad:
            self.build_jit_ad()
        else:
            pass

        kernel_list = self.jit_kernels_ad[method]
        current_jacobian = self.jit_jacobian_ad[method]

        n_eqs = self.problem.get_all_vars_number()
        n_states = self.problem.get_states_number()

        use_dense_solver = (n_eqs <= self.dense_threshold)

        pr = profile.Profile()
        pr.disable()
        pr.enable()

        t = np.linspace(self.t0, self.t_end, self.steps + 1, dtype=np.float64)
        self.t = t

        if x0 is None:
            x0 = self.problem.get_x0()
        else:
            pass
        if dx0 is  None:
            dx0 = self.problem.get_dx0()
        else:
            pass

        active_boundary_updater = resolve_solver_boundary_updater(self.problem, boundary_updater, float(self.t0))

        self.y[0, :] = x0.copy()
        self.dy[0, :] = dx0.copy()

        x_prev = x0.copy()
        dx_prev = dx0.copy()
        x_prev2 = x0.copy()
        x_iter = x0.copy()
        trial_x = self._trial_state_buffer
        trial_res = self._trial_residual_buffer

        static_vals = self._static_parameter_buffer
        n_event_params = self._runtime_param_count
        full_params = self._full_parameter_buffer
        residual_buffer = self._residual_buffer

        if params0 is not None:
            ev_params = np.array(params0, dtype=np.float64, copy=True)
        else:
            ev_params = self.problem.event_params_values.copy()

        should_initialize_at_t0: bool = is_problem_owned_boundary_updater(self.problem, active_boundary_updater)

        if active_boundary_updater is not None and should_initialize_at_t0:
            runtime_params0 = self.problem.def_event_params_fn(ev_params, float(self.t0))
            fill_full_parameter_buffer(runtime_params0, static_vals, full_params)
            active_boundary_updater.update(float(self.t0), x_prev, full_params)
            ev_params[:] = full_params[:n_event_params]
        else:
            pass

        trace_collector = self.problem.get_newton_trace_collector()
        diag_cfg = self._newton_diag_config
        diagnostics_enabled: bool = (
            trace_collector is not None
            or diag_cfg.compute_dense_cond
            or diag_cfg.enable_fallback
            or diag_cfg.enable_index1_check
            or diag_cfg.enable_backtracking
        )

        dense_solve = None
        sparse_solve = None

        if diagnostics_enabled:
            dense_solve = with_newton_diagnostics(
                np.linalg.solve,
                fallback_solve=dense_lstsq_fallback,
                collector=trace_collector,
                config=diag_cfg,
                solver_name="dense",
            )
            sparse_solve = with_newton_diagnostics(
                sp.linalg.spsolve,
                fallback_solve=sparse_lsqr_fallback,
                collector=trace_collector,
                config=diag_cfg,
                solver_name="sparse",
            )
        else:
            pass

        backtracking_residual_evaluator = AdBacktrackingResidualEvaluator()

        if self.verbose:
            print(f"-> Starting JIT (AD) Simulation ({method}, {self.steps} steps)...")
        else:
            pass

        loop_start: float = time.perf_counter()
        total_newton_iterations: int = 0
        jacobian_evaluation_count: int = 0
        aligned_substep_count: int = 0

        for i in range(self.steps):

            if self._progress_signal is not None:
                self.problem.report_progress2(i, self.steps)
            else:
                pass

            if self._cancel_checker is not None and self._cancel_checker():
                return t[:i + 1].copy(), self.y[:i + 1, :].copy(), self.dy[:i + 1, :].copy(), well_initialized, converged

            t_step_start = float(t[i])
            t_step_target = float(t[i + 1])

            t_local_prev = t_step_start
            is_first_local_step = True

            while t_local_prev < (t_step_target - 1e-15):

                forced_event_time = get_solver_forced_event_time(
                    active_boundary_updater,
                    float(t_local_prev),
                    float(t_step_target),
                )

                if forced_event_time is None:
                    t_curr = t_step_target
                else:
                    t_curr = min(float(forced_event_time), t_step_target)

                    if t_curr <= t_local_prev + 1e-15:
                        t_curr = t_step_target

                is_aligned_substep = t_curr < (t_step_target - 1e-15)

                if is_aligned_substep:
                    aligned_substep_count += 1
                else:
                    aligned_substep_count = aligned_substep_count

                if method == DynamicIntegrationMethod.DaeBDF2 and is_aligned_substep:
                    raise NotImplementedError(
                        "force_step_alignment is not implemented for DaeBDF2 in JitAdSolver."
                    )
                else:
                    pass

                h_eff = float(t_curr - t_local_prev)

                # Parameter update via Problem
                runtime_params = self.problem.def_event_params_fn(ev_params, float(t_curr))
                fill_full_parameter_buffer(runtime_params, static_vals, full_params)

                if active_boundary_updater is not None:
                    state_event_retry_time: float | None = (
                        active_boundary_updater.update(
                            t_curr,
                            x_prev,
                            full_params,
                        )
                    )
                else:
                    state_event_retry_time = None

                ev_params[:] = full_params[:n_event_params]

                x_iter[:] = x_prev

                # PREDICTOR
                if i == 0 and is_first_local_step and method == DynamicIntegrationMethod.DaeTrapezoidal:
                    self._predictor.predict(
                        x_iter=x_iter,
                        x_prev=x_prev,
                        dx_prev=dx_prev,
                        h=h_eff,
                        pred_method=self.pred_method,
                    )
                else:
                    pass

                substep_converged: bool = state_event_retry_time is not None
                newton_iteration_count: int
                if state_event_retry_time is None:
                    newton_iteration_count = self.newton_max_iter
                else:
                    newton_iteration_count = 0
                for k in range(newton_iteration_count):
                    total_newton_iterations += 1
                    ctx = NewtonSolveContext(
                        t=float(t_curr),
                        step_idx=int(i),
                        newton_iter=int(k),
                        phase="jit_ad",
                        method=str(method),
                    )

                    # The residual buffer is reused across Newton iterations so
                    # the hot loop does not allocate one full residual vector.
                    res = residual_buffer
                    res_norm_inf = evaluate_batched_residual(
                        kernel_list=kernel_list,
                        x_iter=x_iter,
                        full_params=full_params,
                        x_prev=x_prev,
                        dx_prev=dx_prev,
                        h_eff=h_eff,
                        x_prev2=x_prev2,
                        residual_out=res,
                    )

                    if res_norm_inf < self._newton_tolerance:
                        substep_converged = True
                        break
                    else:
                        pass

                    # Evaluate AD Jacobian
                    J = current_jacobian(
                        states=x_iter,
                        params=full_params,
                        history=x_prev,
                        d_history=dx_prev,
                        h=h_eff,
                        history2=x_prev2,
                    )
                    jacobian_evaluation_count += 1

                    if diagnostics_enabled:
                        maybe_check_index1(J, n_states, ctx=ctx, config=diag_cfg)

                    if use_dense_solver:
                        dense_J = J.toarray()
                        if diagnostics_enabled:
                            delta = dense_solve(dense_J, -res, ctx)
                        else:
                            delta = np.linalg.solve(dense_J, -res)
                    else:
                        if diagnostics_enabled:
                            delta = sparse_solve(J, -res, ctx)
                        else:
                            delta = sp.linalg.spsolve(J, -res)

                    if diag_cfg.enable_backtracking:
                        backtracking_residual_evaluator.set_context(
                            kernel_list=kernel_list,
                            full_params=full_params,
                            x_prev=x_prev,
                            dx_prev=dx_prev,
                            h_eff=h_eff,
                            x_prev2=x_prev2,
                        )

                        maybe_apply_backtracking(
                            x_iter,
                            delta,
                            res_norm_inf,
                            trial_x,
                            trial_res,
                            evaluate_residual=backtracking_residual_evaluator.evaluate,
                            config=diag_cfg,
                        )
                    else:
                        x_iter += delta

                if not substep_converged:
                    converged = False
                    if i == 0 and is_first_local_step:
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
                    ev_params[:] = full_params[:n_event_params]
                else:
                    pass

                if state_event_retry_time is not None:
                    x_iter[:] = x_prev
                else:
                    if method == DynamicIntegrationMethod.DaeTrapezoidal:
                        dx_prev[:n_states] = (
                                (2.0 / h_eff) * (x_iter[:n_states] - x_prev[:n_states]) - dx_prev[:n_states]
                        )
                    elif method == DynamicIntegrationMethod.DaeBDF2:
                        x_prev2 = x_prev.copy()
                    else:
                        dx_prev[:n_states] = (
                                (x_iter[:n_states] - x_prev[:n_states]) / h_eff
                        )

                    if method != DynamicIntegrationMethod.DaeBDF2:
                        x_prev2 = x_prev.copy()
                    else:
                        pass

                    x_prev[:] = x_iter
                    t_local_prev = t_curr
                    is_first_local_step = False


            self.y[i + 1, :] = x_prev
            self.dy[i + 1, :] = dx_prev

        self._last_sim_loop_time = time.perf_counter() - loop_start
        self._last_runtime_stats = dict(
            sim_loop_s=self._last_sim_loop_time,
            total_newton_iterations=float(total_newton_iterations),
            jacobian_evaluations=float(jacobian_evaluation_count),
            aligned_substeps=float(aligned_substep_count),
            macro_steps=float(self.steps),
        )

        if self.verbose:
            print(f"JIT (AD) Finished: {time.time() - t_start:.4f}s")
        else:
            pass

        pr.disable()
        pr.dump_stats("profile_grid_for_loads_jac_batching_10_seconds.pstat")
        return self.t, self.y, self.dy, well_initialized, converged

    def get_backend_build_stats(self) -> Dict[str, float]:
        """
        Return setup timings collected during backend compilation.

        :return: Backend build statistics.
        :rtype: Dict[str, float]
        """
        return dict(self._backend_build_stats)

    def get_last_runtime_stats(self) -> Dict[str, float]:
        """
        Return runtime statistics collected during the latest simulation.

        :return: Runtime statistics.
        :rtype: Dict[str, float]
        """
        return dict(self._last_runtime_stats)

    def get_last_sim_loop_time(self) -> float:
        """
        Return the latest integration-loop wall time.

        :return: Latest loop time in seconds.
        :rtype: float
        """
        return self._last_sim_loop_time
