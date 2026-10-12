# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Set, Tuple, Callable, List, Any, Union, Optional, Dict
import numpy as np
import numba as nb
import scipy.sparse as sp
import time
import hashlib
from scipy.linalg import lu_factor, lu_solve
from scipy.sparse.linalg import SuperLU, splu
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import (
    EmtBoundaryUpdateProtocol,
    EmtProblemTemplate,
    get_solver_forced_event_time,
    resolve_solver_boundary_step,
    resolve_solver_boundary_updater,
)
from VeraGridEngine.Utils.emt_boundary_update_wrapper import BoundaryUpdateWrapper
from VeraGridEngine.enumerations import DynamicIntegrationMethod

from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const, Expr, BinOp, UnOp, Func
from VeraGridEngine.Utils.Symbolic.jit_compiler import EquationCompiler

from VeraGridEngine.Utils.Symbolic.diagnostic import (with_newton_diagnostics, NewtonDiagnosticsConfig,
                                                       NewtonSolveContext, dense_lstsq_fallback,
                                                        sparse_lsqr_fallback, maybe_check_index1,
                                                        maybe_apply_backtracking)
from VeraGridEngine.Simulations.driver_template import DummySignal
from VeraGridEngine.basic_structures import Vec, Mat, IntVec, CscMat


DenseFactorization = Tuple[Any, Any]
DenseSolveBundle = Tuple[DenseFactorization, np.ndarray]
SparseSolveBundle = Tuple[SuperLU, CscMat]


def _has_consistent_initial_state_derivatives(
        problem: EmtProblemTemplate,
        x0: np.ndarray,
        dx0: np.ndarray,
        runtime_params: np.ndarray,
        t0: float,
) -> bool:
    """Use trapezoidal BDF2 startup only when its initial slope is valid."""
    try:
        bindings: Dict[int, float] = {
            uid: float(x0[idx]) for uid, idx in problem.uid2idx_vars.items()
        }
        bindings.update({
            uid: float(dx0[idx]) for uid, idx in problem.uid2idx_diff.items()
        })
        bindings.update({
            uid: float(runtime_params[idx])
            for uid, idx in problem.uid2idx_event_params.items()
        })
        bindings.update({
            uid: float(problem.get_parameters_values()[idx].value)
            for uid, idx in problem.uid2idx_params.items()
        })
        bindings[problem.glob_time.uid] = float(t0)

        for differential, equation in zip(problem.get_diff_vars(), problem.get_state_eqs()):
            rhs = float(equation.eval_uid(bindings))
            stored = float(dx0[problem.uid2idx_diff[differential.uid]])
            if not np.isfinite(rhs) or not np.isfinite(stored):
                return False
            if abs(stored - rhs) > 1e-6 * (1.0 + max(abs(stored), abs(rhs))):
                return False
    except (KeyError, TypeError, ValueError, AttributeError, ZeroDivisionError):
        return False
    return True


class SymbolicCompiledNumbaKernelCache:
    """
    In-process cache of Numba-compiled symbolic kernels.
    """

    __slots__ = ["_cache"]

    def __init__(self) -> None:
        """
        Build the symbolic compiled-kernel cache.

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


SYMBOLIC_NUMBA_KERNEL_CACHE = SymbolicCompiledNumbaKernelCache()


def _safe_njit(py_func: Callable[..., Any], fastmath: bool = True, cache: bool = True) -> Callable[..., Any]:
    """
    Compile one symbolic kernel with an in-process Numba cache.

    :param py_func: Python function to compile.
    :type py_func: Callable[..., Any]
    :param fastmath: Whether fastmath is enabled.
    :type fastmath: bool
    :param cache: Whether Numba persistent cache is enabled.
    :type cache: bool
    :return: Compiled kernel.
    :rtype: Callable[..., Any]
    """
    cache_payload: str = "|".join([py_func.__module__, py_func.__name__, str(fastmath), str(cache)])
    cache_key: str = hashlib.sha256(cache_payload.encode("utf-8")).hexdigest()
    cached_kernel: Callable[..., Any] | None = SYMBOLIC_NUMBA_KERNEL_CACHE.get(cache_key)

    if cached_kernel is None:
        pass
    else:
        return cached_kernel

    compiled_kernel: Callable[..., Any] = nb.jit(cache=cache, fastmath=fastmath)(py_func)
    SYMBOLIC_NUMBA_KERNEL_CACHE.set(cache_key, compiled_kernel)
    return compiled_kernel


def _should_use_numba_residual_backend(total_equation_count: int) -> bool:
    """
    Decide whether one residual backend should be wrapped with Numba.

    Small and medium EMT systems often spend much more wall time in the first
    lazy Numba compilation than in the actual Newton loop. For those systems the
    generated Python kernel gives a better end-to-end turnaround, especially for
    interactive debugging and tests.

    :param total_equation_count: Total number of residual equations.
    :type total_equation_count: int
    :return: ``True`` when the residual backend should use Numba.
    :rtype: bool
    """
    # Avoid disproportionate Numba lowering time for medium sparse EMT cases.
    small_system_threshold: int = 800

    if total_equation_count <= small_system_threshold:
        return False
    else:
        return True


def _should_use_numba_jacobian_backend(total_variable_count: int, jacobian_expression_count: int) -> bool:
    """
    Decide whether one Jacobian backend should be wrapped with Numba.

    The Jacobian kernel is usually much larger than the residual kernel. Moderate
    EMT systems can therefore hit a severe cold-start penalty when the generated
    kernel is compiled lazily on the first Newton iteration. Keeping those cases
    in eager Python form avoids that startup cliff while preserving the exact
    numerical formulation.

    :param total_variable_count: Number of state plus algebraic variables.
    :type total_variable_count: int
    :param jacobian_expression_count: Number of generated Jacobian expressions.
    :type jacobian_expression_count: int
    :return: ``True`` when the Jacobian backend should use Numba.
    :rtype: bool
    """
    small_variable_threshold: int = 160
    medium_variable_threshold: int = 220
    moderate_jacobian_threshold: int = 4000

    # Small EMT systems are faster and more predictable when they avoid the first
    # lazy Numba compilation altogether, even if the Jacobian is assembled densely.
    if jacobian_expression_count <= moderate_jacobian_threshold:
        return False
    elif total_variable_count <= small_variable_threshold:
        return False
    elif total_variable_count <= medium_variable_threshold:
        return False
    else:
        return True


def get_vars_in_expr(expr: Expr) -> Set[int]:
    """
    Recursively collects UIDs of all variables present in an expression.

    :param expr: The symbolic expression to analyze.
    :type expr: Expr
    :return: A set containing the unique identifiers (UIDs) of the variables.
    :rtype: Set[int]
    """
    found: Set[int] = set()
    stack: List[Expr] = list()
    visited: Set[int] = set()

    stack.append(expr)

    while stack:
        node: Expr = stack.pop()
        node_id: int = id(node)

        if node_id in visited:
            # Explicit state: The node has already been processed.
            # We do nothing to prevent infinite loops in Directed Acyclic Graphs (DAGs).
            pass
        else:
            visited.add(node_id)

            # Flat type dispatch to evaluate AST nodes.
            # This avoids deep nesting and keeps the execution path predictable.
            if isinstance(node, Var):
                found.add(node.uid)

                # Since the node is guaranteed to be a Var instance, we can safely
                # access the base_var property directly.
                if node.base_var is not None:
                    found.add(node.base_var.uid)
                else:
                    # Terminal state: The variable is a base state, no derivative to track.
                    pass

            elif isinstance(node, Func):
                stack.append(node.arg)

            elif isinstance(node, UnOp):
                stack.append(node.operand)

            elif isinstance(node, BinOp):
                stack.append(node.left)
                stack.append(node.right)

            else:
                # Terminal state: Const nodes or unknown types have no children to traverse.
                pass

    return found

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

    # The runtime slice changes every local substep because events and boundary
    # updates can alter the parameter values in place.
    full_params_out[:n_runtime] = runtime_params

    # The static slice remains immutable for the whole simulation, but keeping
    # the explicit copy here preserves the stable [runtime | static] contract.
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

    # The residual stays split in batches to keep code generation tractable for
    # large symbolic systems while still avoiding per-iteration allocations.
    for kernel in kernel_list:
        kernel(x_iter, full_params, x_prev, dx_prev, h_eff, residual_out, x_prev2)

    return float(np.linalg.norm(residual_out, np.inf))


def _dense_lu_bundle_solve(bundle: DenseSolveBundle, rhs: Vec) -> Vec:
    """
    Solve one dense LU system.

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
    Return the dense Jacobian matrix stored in one LU bundle.

    :param bundle: Dense LU bundle ``(factorization, matrix)``.
    :return: Dense Jacobian matrix.
    """
    return bundle[1]


def _sparse_lu_bundle_solve(bundle: SparseSolveBundle, rhs: Vec) -> Vec:
    """
    Solve one sparse LU system.

    :param bundle: Sparse LU bundle ``(factorization, matrix)``.
    :param rhs: Right-hand side vector.
    :return: Solution vector.
    """
    return bundle[0].solve(rhs)


def _sparse_lu_bundle_fallback(bundle: SparseSolveBundle, rhs: Vec) -> Vec:
    """
    Solve one sparse fallback least-squares system.

    :param bundle: Sparse LU bundle ``(factorization, matrix)``.
    :param rhs: Right-hand side vector.
    :return: Fallback solution vector.
    """
    return sparse_lsqr_fallback(bundle[1], rhs)


def _sparse_lu_bundle_matrix(bundle: SparseSolveBundle) -> CscMat:
    """
    Return the sparse Jacobian matrix stored in one LU bundle.

    :param bundle: Sparse LU bundle ``(factorization, matrix)``.
    :return: Sparse Jacobian matrix.
    """
    return bundle[1]


class HybridJacobianEvaluator:
    """
    Evaluates the JIT-compiled Jacobian and formats it as either Dense or Sparse.
    This class replaces nested functions to ensure memory determinism and strict type safety.
    """
    __slots__ = [
        'kernel_jit', 'use_sparse', 'n_vars', 'alpha_mult', 'np_rows', 'np_cols',
        '_params_with_alpha_buffer', '_dense_data_buffer'
    ]

    def __init__(self,
                 kernel_jit: Callable,
                 use_sparse: bool,
                 n_vars: int,
                 alpha_mult: float,
                 parameter_count: int,
                 np_rows: Union[IntVec| None] = None,
                 np_cols: Union[IntVec| None] = None) -> None:
        """
        Initializes the evaluator with the compiled Numba kernel and matrix topology.

        :param kernel_jit: The compiled Numba function for the Jacobian.
        :type kernel_jit: Callable
        :param use_sparse: Flag indicating if the output should be a sparse matrix.
        :type use_sparse: bool
        :param n_vars: The number of variables (size of the N x N matrix).
        :type n_vars: int
        :param alpha_mult: The scaling factor for the integration method.
        :type alpha_mult: float
        :param np_rows: Row indices for the sparse matrix format.
        :type np_rows: IntVec
        :param np_cols: Column indices for the sparse matrix format.
        :type np_cols: IntVec
        :rtype: None
        """
        self.kernel_jit = kernel_jit
        self.use_sparse = use_sparse
        self.n_vars = n_vars
        self.alpha_mult = alpha_mult
        self.np_rows = np_rows
        self.np_cols = np_cols
        self._params_with_alpha_buffer: Vec = np.empty(parameter_count + 1, dtype=np.float64)

        if self.use_sparse:
            self._dense_data_buffer = None
        else:
            self._dense_data_buffer = np.zeros(self.n_vars * self.n_vars, dtype=np.float64)

    def evaluate(self, states: Vec, params: Vec, history: Vec, d_history: Vec, h: float,
                 history2: Union[Vec| None] = None) -> Mat | CscMat:
        """
        Executes the JIT kernel and constructs the resulting Jacobian matrix.

        :param states: The current state vector.
        :type states: Vec
        :param params: The parameter vector.
        :type params: Vec
        :param history: The state history vector.
        :type history: Vec
        :param d_history: The derivative history vector.
        :type d_history: Vec
        :param h: The integration time step.
        :type h: float
        :param history2: The secondary history vector (for BDF2).
        :type history2: Vec
        :return: The assembled Jacobian matrix (Dense or Sparse CSC).
        :rtype: Mat | CscMat
        """
        # The Jacobian kernel expects the extra alpha scaling factor appended at
        # the end of the parameter vector. The buffer is reused every call.
        params_with_alpha: Vec = self._params_with_alpha_buffer
        params_with_alpha[:-1] = params
        params_with_alpha[-1] = self.alpha_mult / h

        # Execute the JIT compiled kernel to obtain the raw data values
        data: Vec = self.kernel_jit(states, params_with_alpha, history, d_history, h, history2)

        # Assemble the matrix based on the requested storage format
        if self.use_sparse:
            # Sparse symbolic Jacobians may contain duplicate coordinates that
            # SciPy canonicalizes during construction, so the matrix shell is
            # rebuilt here to preserve the exact numerical semantics.
            return sp.csc_matrix((data, (self.np_rows, self.np_cols)), shape=(self.n_vars, self.n_vars))
        else:
            if self._dense_data_buffer is None:
                return data.reshape((self.n_vars, self.n_vars))
            else:
                self._dense_data_buffer[:] = data
                return self._dense_data_buffer.reshape((self.n_vars, self.n_vars))

class ResidualTrialEvaluator:
    """
    Callable helper to evaluate residual norms during Newton backtracking.
    """
    __slots__ = ['kernel_list', 'full_params', 'x_prev', 'dx_prev', 'h_eff', 'x_prev2']

    def __init__(self) -> None:
        """
        Build one empty backtracking evaluator.

        :return: None.
        :rtype: None
        """
        self.kernel_list: List[Callable[..., Any]] | None = None
        self.full_params: Vec | None = None
        self.x_prev: Vec | None = None
        self.dx_prev: Vec | None = None
        self.h_eff: float = 0.0
        self.x_prev2: Vec | None = None

    def set_context(self,
                    kernel_list: List[Callable[..., Any]],
                    full_params: Vec,
                    x_prev: Vec,
                    dx_prev: Vec,
                    h_eff: float,
                    x_prev2: Vec) -> None:
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
        self.kernel_list = kernel_list
        self.full_params = full_params
        self.x_prev = x_prev
        self.dx_prev = dx_prev
        self.h_eff = h_eff
        self.x_prev2 = x_prev2

    def __call__(self, candidate_x: Vec, out_res: Vec) -> float:
        """
        Evaluate one trial Newton iterate during backtracking.

        :param candidate_x: Trial iterate.
        :type candidate_x: Vec
        :param out_res: Destination residual buffer.
        :type out_res: Vec
        :return: Residual infinity norm.
        :rtype: float
        """
        if self.kernel_list is None:
            return np.inf
        else:
            pass

        if self.full_params is None or self.x_prev is None or self.dx_prev is None or self.x_prev2 is None:
            return np.inf
        else:
            pass

        return evaluate_batched_residual(
            kernel_list=self.kernel_list,
            x_iter=candidate_x,
            full_params=self.full_params,
            x_prev=self.x_prev,
            dx_prev=self.dx_prev,
            h_eff=self.h_eff,
            x_prev2=self.x_prev2,
            residual_out=out_res,
        )

class JitSymbolicSolver:

    __slots__ = [
        'problem', 't0', 't_end', 'h', 'method', 'pred_method', 'dense_threshold', 'verbose', 'newton_max_iter',
        'steps', 't', 'y', 'dy', 'jit_kernels', 'jit_jacobian_symbolic',
        'state_vars', 'algebraic_vars', 'state_eqs', 'algebraic_eqs', 'diff_vars',
        'jit_compiler', '_residual_debug_info', '_newton_diag_config',
        '_predictor', '_runtime_param_count', '_static_parameter_buffer', '_full_parameter_buffer',
        '_residual_buffer', '_trial_state_buffer', '_trial_residual_buffer', '_trial_residual_evaluator',
        '_backend_build_stats', '_last_runtime_stats', '_last_sim_loop_time',
        '_max_residual_inf_fail', '_max_state_residual_inf_fail', '_cancel_checker', '_progress_signal',
        '_newton_tolerance'
    ]

    def __init__(self,
                 problem: EmtProblemTemplate,
                 t0: float,
                 t_end: float,
                 h: float,
                 method: DynamicIntegrationMethod = DynamicIntegrationMethod.DaeTrapezoidal,
                 pred_method:DynamicIntegrationMethod = None,
                 dense_threshold: int = 100,
                 verbose: bool = False,
                 newton_max_iter: int = 15,
                 newton_diag_config: NewtonDiagnosticsConfig | None = None,
                 max_residual_inf_fail: float = np.inf,
                 max_state_residual_inf_fail: float = np.inf,
                 progress_signal: DummySignal | None = None,
                 cancel_checker: Callable[[], bool] | None = None,
                 newton_tolerance: float = 1.0e-6)-> None:
        """
        :param problem: The DAE problem definition.
        :param t0: Initial time.
        :param t_end: End time.
        :param h: Time step.
        :param method: DynamicIntegrationMethod (DaeTrapezoidal, DaeBackEuler, DaeBDF2).
        :param pred_method: DynamicIntegrationMethod used in the predictor step if method is explicit.
        :param dense_threshold: Threshold to switch between dense and sparse linear solvers.
        :param verbose: Print compilation and simulation timings.
        :param newton_max_iter: Maximum Newton iterations per local EMT substep.
        :param newton_tolerance: Absolute infinity-norm tolerance for Newton residual convergence.
        :param progress_signal: Optional progress signal updated during the simulation loop.
        :type progress_signal: DummySignal | None
        """
        self.jit_compiler = None
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
        self._max_residual_inf_fail: float = float(max_residual_inf_fail)
        self._max_state_residual_inf_fail: float = float(max_state_residual_inf_fail)
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
        self.jit_kernels = dict()
        self.jit_jacobian_symbolic = dict()

        self.state_vars = self.problem.get_state_vars()
        self.algebraic_vars = self.problem.get_algebraic_vars()
        self.state_eqs = self.problem.get_state_eqs()
        self.algebraic_eqs = self.problem.get_algebraic_eqs()
        self.diff_vars  = self.problem.get_diff_vars()

        self._residual_debug_info = list()
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
        self._trial_residual_evaluator = ResidualTrialEvaluator()
        self._backend_build_stats: Dict[str, float] = dict(
            residual_compile_s=0.0,
            residual_batches=0.0,
            jacobian_compile_s=0.0,
            jacobian_builds=0.0,
            total_s=0.0,
        )
        self._last_runtime_stats: Dict[str, Any] = dict()
        self._last_sim_loop_time: float = 0.0
        self._progress_signal: DummySignal | None = progress_signal
        self._cancel_checker = cancel_checker

    # ==============================================================================
    # 2. JIT IMPLICIT ENGINE (Optimized with Batching)
    # ==============================================================================

    def build_jit_kernel(self, method: DynamicIntegrationMethod)-> None:
        """
        Compiles the numerical residual function using JIT.
        It uses a batching strategy (splitting equations into chunks) to prevent
        Numba/LLVM from hanging when compiling very large non-linear systems.

        :param method: The dynamic integration method to compile for.
        :type method: DynamicIntegrationMethod
        :rtype: None
        """
        t_start_build: float = time.perf_counter()

        if self.verbose:
            print(f"--- [JIT] Compiling Implicit Kernel ({method}) ---")
        else:
            pass

        sorted_vars: List[Any] = list()
        sorted_vars.extend(self.state_vars)
        sorted_vars.extend(self.algebraic_vars)

        var_uid_to_global_idx: dict = dict()
        for idx, v in enumerate(sorted_vars):
            var_uid_to_global_idx[v.uid] = idx

        all_params: List[Any] = list()
        all_params.extend(self.problem.get_variable_parameters())
        all_params.extend(self.problem.get_constant_parameters())

        equations: List[Expr] = list()
        residual_debug_info: List[dict] = list()
        synthetic_diff_terms: List[Var] = [Var(name=f"d_{sv.name}", base_var=sv) for sv in self.state_vars]

        for i, rhs in enumerate(self.state_eqs):
            sv = self.state_vars[i]
            d_term = synthetic_diff_terms[i]

            equations.append(d_term - rhs)

            residual_debug_info.append({
                "kind": "STATE",
                "label": f"d_{sv.name} - rhs_{sv.name}",
                "var_name": sv.name,
                "state_idx": var_uid_to_global_idx[sv.uid],
            })

        equations.extend(self.algebraic_eqs)

        for j, eq in enumerate(self.algebraic_eqs):
            av = self.algebraic_vars[j] if j < len(self.algebraic_vars) else None

            # equations.append(eq)
            #
            if av is not None:
                residual_debug_info.append({
                    "kind": "ALG",
                    "label": f"alg for {av.name}",
                    "var_name": av.name,
                    "state_idx": var_uid_to_global_idx.get(av.uid, None),
                })
            else:
                residual_debug_info.append({
                    "kind": "ALG",
                    "label": f"ALG_EQ_{j}",
                    "var_name": f"<no algebraic var for eq {j}>",
                    "state_idx": None,
                })

        self.jit_compiler = EquationCompiler(variables=sorted_vars, parameters=all_params, method=method)

        self._residual_debug_info = residual_debug_info

        # Batch compilation strategy
        BATCH_SIZE = 100
        n_eqs = len(equations)
        batched_kernels: List[Callable[..., Any]] = list()
        use_numba_residual_backend: bool = _should_use_numba_residual_backend(total_equation_count=n_eqs)

        if self.verbose:
            if use_numba_residual_backend:
                print("   [JIT] Residual backend uses Numba kernels.")
            else:
                print("   [JIT] Residual backend uses generated Python kernels to avoid cold-start compilation cost.")
        else:
            pass

        for i in range(0, n_eqs, BATCH_SIZE):
            chunk = equations[i: i + BATCH_SIZE]
            f_name = f"jit_step_{method}_part_{i}"
            py_func: Callable[..., Any]
            wrapped_kernel: Callable[..., Any]

            # Compile inplace: the function writes directly to the 'residuals' array
            py_func = self.jit_compiler.compile(chunk, func_name=f_name, use_cse=True, offset=i, inplace=True)

            # Small systems are faster end-to-end when they avoid the first lazy Numba compilation.
            if use_numba_residual_backend:
                wrapped_kernel = _safe_njit(py_func, cache=True, fastmath=True)
            else:
                wrapped_kernel = py_func

            batched_kernels.append(wrapped_kernel)

        self.jit_kernels[method] = batched_kernels
        elapsed_s: float = time.perf_counter() - t_start_build
        self._backend_build_stats['residual_compile_s'] += elapsed_s
        self._backend_build_stats['residual_batches'] += float(len(batched_kernels))
        self._backend_build_stats['total_s'] += elapsed_s

    def _build_jit_symbolic_hybrid(self, method: DynamicIntegrationMethod, use_sparse: bool)-> None:
        """
        Compiles a Hybrid Symbolic Jacobian.
        It generates a Numba kernel that evaluates the Jacobian entries and
        returns either a Scipy CSC Matrix (Sparse mode) or a Numpy Array (Dense mode).
        """
        cache_key = f"{method}_{use_sparse}"
        if cache_key in self.jit_jacobian_symbolic:
            return
        else:
            pass

        if self.verbose:
            print(f"--- [JIT-SD] Compiling Hybrid Symbolic Jacobian ({'SPARSE' if use_sparse else 'DENSE'}) ---")
        else:
            pass
        t0 = time.perf_counter()

        sorted_vars: List[Any] = list()
        sorted_vars.extend(self.state_vars)
        sorted_vars.extend(self.algebraic_vars)

        all_params: List[Any] = list()
        all_params.extend(self.problem.get_variable_parameters())
        all_params.extend(self.problem.get_constant_parameters())

        var_uid_to_idx: dict = dict()
        for i, v in enumerate(sorted_vars):
            var_uid_to_idx[v.uid] = i

        equations: List[Expr] = list()
        synthetic_diff_terms: List[Var] = [Var(name=f"d_{sv.name}", base_var=sv) for sv in self.state_vars]

        for i, rhs in enumerate(self.state_eqs):
            d_term = synthetic_diff_terms[i]
            equations.append(d_term - rhs)
        base_var_uid_to_diff_var: dict = {sv.uid: synthetic_diff_terms[i] for i, sv in enumerate(self.state_vars)}
        equations.extend(self.algebraic_eqs)

        N = len(sorted_vars)
        n_states = len(self.state_vars)
        jac_expression: List[Expr] = list()
        rows: List[int] = list()
        cols: List[int] = list()
        alpha_sym = Var("alpha_scaling_factor")

        if use_sparse:
            nnz = 0
            for r, eq in enumerate(equations):
                dependencies = get_vars_in_expr(eq)

                if r < n_states:
                    dependencies.add(self.state_vars[r].uid)
                else:
                    pass

                for v in sorted_vars:
                    if v.uid in dependencies:

                        c = var_uid_to_idx[v.uid]
                        d_direct = eq.diff(v)

                        dv = base_var_uid_to_diff_var.get(v.uid, None)
                        d_diff = eq.diff(dv) if dv is not None else Const(0)

                        final_expr = d_direct if (isinstance(d_diff, Const) and d_diff.value == 0) else (
                                    d_direct + alpha_sym * d_diff)
                        final_expr = final_expr.simplify()

                        if not (isinstance(final_expr, Const) and final_expr.value == 0):
                            jac_expression.append(final_expr)
                            rows.append(r)
                            cols.append(c)
                            nnz += 1
                        else:
                            pass

                    else:
                        pass

            if self.verbose:
                print(f"   [JIT-SD] Topology Analysis: {nnz} non-zeros (Sparsity: {1.0 - nnz / (N ** 2):.2%})")
        else:
            for r, eq in enumerate(equations):
                for c, v in enumerate(sorted_vars):

                    d_direct = eq.diff(v)

                    dv = base_var_uid_to_diff_var.get(v.uid, None)
                    d_diff = eq.diff(dv) if dv is not None else Const(0)

                    final_expr = (d_direct + alpha_sym * d_diff).simplify()
                    jac_expression.append(final_expr)

        compile_params: List[Any] = list()
        compile_params.extend(all_params)
        compile_params.append(alpha_sym)
        compiler = EquationCompiler(variables=sorted_vars, parameters=compile_params, method=method)
        func_name = f"jac_eval_{method.name}_{N}_{'sparse' if use_sparse else 'dense'}"
        kernel_py = compiler.compile(jac_expression, func_name=func_name, use_cse=True)
        use_numba_jacobian_backend: bool = _should_use_numba_jacobian_backend(
            total_variable_count=N,
            jacobian_expression_count=len(jac_expression),
        )

        # The symbolic Jacobian structure is deterministic for a given method and
        # sparsity mode, so persistent caching is safe and accelerates warm runs.
        if use_numba_jacobian_backend:
            kernel_jit = _safe_njit(kernel_py, cache=True, fastmath=True)
        else:
            kernel_jit = kernel_py

        if self.verbose:
            if use_numba_jacobian_backend:
                print("   [JIT-SD] Jacobian backend uses Numba kernels.")
            else:
                print("   [JIT-SD] Jacobian backend uses generated Python kernels to avoid cold-start compilation cost.")
        else:
            pass

        if method == DynamicIntegrationMethod.DaeTrapezoidal:
            alpha_mult = 2.0
        elif method == DynamicIntegrationMethod.DaeBDF2:
            alpha_mult = 1.5
        else:
            alpha_mult = 1.0

        np_rows: Union[IntVec | None] = np.array(rows, dtype=np.int32) if use_sparse else None
        np_cols: Union[IntVec | None] = np.array(cols, dtype=np.int32) if use_sparse else None

        evaluator_obj = HybridJacobianEvaluator(
            kernel_jit=kernel_jit,
            use_sparse=use_sparse,
            n_vars=N,
            alpha_mult=alpha_mult,
            parameter_count=len(all_params),
            np_rows=np_rows,
            np_cols=np_cols
        )

        self.jit_jacobian_symbolic[cache_key] = evaluator_obj
        elapsed_s: float = time.perf_counter() - t0
        self._backend_build_stats['jacobian_compile_s'] += elapsed_s
        self._backend_build_stats['jacobian_builds'] += 1.0
        self._backend_build_stats['total_s'] += elapsed_s
        if self.verbose:
            print(f"   [JIT-SD] Compilation finished in {elapsed_s:.4f}s")
        else:
            pass

    def simulate(self,
                 x0: Union[Vec | None] = None,
                 dx0: Union[Vec | None] = None,
                 params0: Union[Vec | None] = None,
                 boundary_updater: EmtBoundaryUpdateProtocol | None = None) -> Tuple[Vec, Mat, Mat, bool, bool]:
        """
        Main JIT simulation loop using the Symbolic Differentiation (SD) backend.
        :param x0: Initial state vector.
        :param dx0: Initial derivative vector.
        :param params0: Initial event parameters.
        :param boundary_updater: Optional override for the problem boundary updater.
        :return: A tuple containing the time vector and the state trajectory matrix. Tuple[Vec, Mat]
        """
        t_start = time.time()
        method = self.method

        converged: bool = True
        well_initialized: bool = True

        n_eqs = self.problem.get_all_vars_number()
        n_states = self.problem.get_states_number()

        use_dense_solver = (n_eqs <= self.dense_threshold)
        is_sparse = not use_dense_solver

        # Prepare main method kernels and Jacobian
        if method not in self.jit_kernels:
            self.build_jit_kernel(method)
        else:
            pass
        self._build_jit_symbolic_hybrid(method, use_sparse=is_sparse)
        jac_key_main = f"{method}_{is_sparse}"

        if self.verbose:
            mode_str = "DENSE" if use_dense_solver else "SPARSE"
            print(f"   [Config] System N={n_eqs}. Using {mode_str} linear solver (Threshold={self.dense_threshold}).")
        else:
            pass

        if x0 is None:
            x0 = self.problem.get_x0()
        else:
            pass
        if dx0 is None:
            dx0 = self.problem.get_dx0()
        else:
            pass

        active_boundary_updater = resolve_solver_boundary_updater(self.problem, boundary_updater, float(self.t0))

        self.t[0] = self.t0
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
            ev_params =  np.array(params0, dtype=np.float64, copy=True)
        else:
            ev_params = self.problem.event_params_values.copy()

        if active_boundary_updater is not None:
            ev_params = self.problem.def_event_params_fn(ev_params, float(self.t0))
            fill_full_parameter_buffer(ev_params, static_vals, full_params)
            active_boundary_updater.update(float(self.t0), x_prev, full_params)
            ev_params[:] = full_params[:len(ev_params)]
        else:
            pass

        use_trapezoidal_startup = (
            method == DynamicIntegrationMethod.DaeBDF2
            and _has_consistent_initial_state_derivatives(
                problem=self.problem,
                x0=x_prev,
                dx0=dx_prev,
                runtime_params=ev_params,
                t0=float(self.t0),
            )
        )
        if use_trapezoidal_startup:
            startup_method = DynamicIntegrationMethod.DaeTrapezoidal
            if startup_method not in self.jit_kernels:
                self.build_jit_kernel(startup_method)
            self._build_jit_symbolic_hybrid(startup_method, use_sparse=is_sparse)
            startup_jac_key = f"{startup_method}_{is_sparse}"

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
                _dense_lu_bundle_solve,
                fallback_solve=_dense_lu_bundle_fallback,
                collector=trace_collector,
                config=diag_cfg,
                solver_name="dense_lu",
                matrix_getter=_dense_lu_bundle_matrix,
            )
            sparse_solve = with_newton_diagnostics(
                _sparse_lu_bundle_solve,
                fallback_solve=_sparse_lu_bundle_fallback,
                collector=trace_collector,
                config=diag_cfg,
                solver_name="superlu",
                matrix_getter=_sparse_lu_bundle_matrix,
            )
        else:
            pass

        if self.verbose:
            print(f"-> Starting JIT Simulation ({method}, {self.steps} steps)...")
        else:
            pass

        loop_start: float = time.perf_counter()
        total_newton_iterations: int = 0
        jacobian_evaluation_count: int = 0
        aligned_substep_count: int = 0
        failed_substep_count: int = 0
        first_failed_time_s: float = float("nan")
        failed_substep_times_s: list[float] = list()

        for i in range(self.steps):

            if self._progress_signal is not None:
                self.problem.report_progress2(i, self.steps)
            else:
                pass

            if self._cancel_checker is not None and self._cancel_checker():
                return self.t[:i + 1].copy(), self.y[:i + 1, :].copy(), self.dy[:i + 1, :].copy(), well_initialized, converged

            t_step_start: float = self.t0 + i * self.h
            t_step_target: float = self.t0 + (i + 1) * self.h
            self.t[i + 1] = t_step_target

            t_local_prev: float = t_step_start
            is_first_local_step: bool = True

            while t_local_prev < (t_step_target - 1e-15):
                forced_event_time = get_solver_forced_event_time(
                    active_boundary_updater,
                    t_local_prev,
                    t_step_target,
                )

                if forced_event_time is None:
                    t_curr: float = t_step_target
                else:
                    t_curr = forced_event_time

                if t_curr < (t_step_target - 1e-15):
                    aligned_substep_count += 1
                else:
                    aligned_substep_count = aligned_substep_count

                h_eff: float = t_curr - t_local_prev

                if h_eff <= 0.0:
                    raise RuntimeError(
                        f"Invalid EMT substep size h_eff={h_eff} at macro step {i}."
                    )
                else:
                    pass

                if method == DynamicIntegrationMethod.DaeBDF2 and t_curr != t_step_target:
                    raise NotImplementedError(
                        "force_step_alignment with DAE BDF2 is not implemented yet. "
                        "Use DaeTrapezoidal or implement variable-step BDF2 coefficients."
                    )
                else:
                    pass

                effective_method = (
                    startup_method
                    if use_trapezoidal_startup and i == 0
                    else method
                )
                kernel_list_eff = self.jit_kernels[effective_method]
                current_jacobian_eff = self.jit_jacobian_symbolic[
                    startup_jac_key if effective_method != method else jac_key_main
                ]

                ev_params = self.problem.def_event_params_fn(ev_params, float(t_curr))
                fill_full_parameter_buffer(ev_params, static_vals, full_params)

                if i == 0 and is_first_local_step and self.verbose:
                    _print_full_params_debug(full_params=full_params)
                else:
                    pass

                if active_boundary_updater is None:
                    state_event_retry_time: float | None = None
                else:
                    state_event_retry_time = active_boundary_updater.update(
                        t_curr,
                        x_prev,
                        full_params,
                    )
                    ev_params[:] = full_params[:len(ev_params)]

                x_iter[:] = x_prev
                x_iter[:n_states] = x_prev[:n_states] + h_eff * dx_prev[:n_states]
                last_res_norm: float = 1.0

                # The factorization cache is local to the substep because the
                # Jacobian depends on the current state, parameters and h_eff.
                cached_lu_dense: DenseSolveBundle | None = None
                cached_lu_sparse: SparseSolveBundle | None = None

                if i == 0 and is_first_local_step and effective_method == DynamicIntegrationMethod.DaeTrapezoidal:
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
                substep_numerical_failure: bool = False
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
                        phase="jit",
                        method=str(method)
                    )

                    # The residual buffer is reused across Newton iterations to
                    # remove one full-size allocation from the hot loop.
                    res = residual_buffer
                    try:
                        res_norm_inf = evaluate_batched_residual(
                            kernel_list=kernel_list_eff,
                            x_iter=x_iter,
                            full_params=full_params,
                            x_prev=x_prev,
                            dx_prev=dx_prev,
                            h_eff=h_eff,
                            x_prev2=x_prev2,
                            residual_out=res,
                        )
                    except (FloatingPointError, OverflowError, ZeroDivisionError, ValueError, RuntimeError):
                        substep_numerical_failure = True
                        break

                    if np.isfinite(res_norm_inf) and np.all(np.isfinite(res)):
                        pass
                    else:
                        substep_numerical_failure = True
                        break

                    if res_norm_inf > self._max_residual_inf_fail:
                        #raise RuntimeError(
                        #    "JIT solver aborted due to large nonlinear residual: "
                        #    f"res_inf={res_norm_inf:.6e} at t={t_curr:.6e}, step={i}, iter={k}, "
                        #    f"limit={self._max_residual_inf_fail:.6e}."
                        #)
                        _ = 0

                    if n_states > 0:
                        state_res_inf = float(np.max(np.abs(res[:n_states])))
                        if state_res_inf > self._max_state_residual_inf_fail:
                            raise RuntimeError(
                                "JIT solver aborted due to large state residual: "
                                f"state_res_inf={state_res_inf:.6e} at t={t_curr:.6e}, step={i}, iter={k}, "
                                f"limit={self._max_state_residual_inf_fail:.6e}."
                            )

                    ctx.res_norm_inf = float(res_norm_inf)
                    if trace_collector is not None and hasattr(trace_collector, "record_residual_vector"):
                        trace_collector.record_residual_vector(
                            ctx=ctx,
                            residual=res,
                            top_k=5,
                            debug_info=self._residual_debug_info,
                        )

                    if i == 0 and self.verbose:
                        _print_residual_debug_table(
                            res=res,
                            n_eqs=n_eqs,
                            x_iter=x_iter,
                            x_prev=x_prev,
                            dx_prev=dx_prev,
                            debug_info=self._residual_debug_info,
                            step_idx=i,
                            iter_idx=k,
                        )

                    if res_norm_inf < self._newton_tolerance:
                        substep_converged = True
                        break
                    else:
                        pass

                    recompute: bool = (cached_lu_dense is None and cached_lu_sparse is None) or \
                                      (k > 0 and (res_norm_inf / (last_res_norm + 1e-16)) > 0.5)

                    if recompute:
                        J_final = current_jacobian_eff.evaluate(
                            states=x_iter,
                            params=full_params,
                            history=x_prev,
                            d_history=dx_prev,
                            h=h_eff,
                            history2=x_prev2
                        )
                        jacobian_evaluation_count += 1

                        if use_dense_solver:
                            if diagnostics_enabled:
                                maybe_check_index1(J_final, n_states, ctx=ctx, config=diag_cfg)
                            else:
                                pass

                            cached_lu_dense = (lu_factor(J_final), J_final)
                            cached_lu_sparse = None
                        else:
                            if diagnostics_enabled:
                                maybe_check_index1(J_final, n_states, ctx=ctx, config=diag_cfg)
                            else:
                                pass

                            try:
                                cached_lu_sparse = (splu(J_final), J_final)
                            except (FloatingPointError, OverflowError, ZeroDivisionError, ValueError, RuntimeError):
                                if diagnostics_enabled and diag_cfg.enable_fallback:
                                    cached_lu_sparse = (None, J_final)  # type: ignore[arg-type]
                                else:
                                    raise
                            cached_lu_dense = None
                    else:
                        pass

                    if use_dense_solver:
                        try:
                            if diagnostics_enabled:
                                assert dense_solve is not None
                                assert cached_lu_dense is not None
                                delta = dense_solve(cached_lu_dense, -res, ctx)
                            else:
                                assert cached_lu_dense is not None
                                delta = lu_solve(cached_lu_dense[0], -res)
                        except (FloatingPointError, OverflowError, ZeroDivisionError, ValueError, RuntimeError):
                            substep_numerical_failure = True
                            break
                    else:
                        try:
                            if diagnostics_enabled:
                                assert sparse_solve is not None
                                assert cached_lu_sparse is not None
                                delta = sparse_solve(cached_lu_sparse, -res, ctx)
                            else:
                                assert cached_lu_sparse is not None
                                delta = cached_lu_sparse[0].solve(-res)
                        except (FloatingPointError, OverflowError, ZeroDivisionError, ValueError, RuntimeError):
                            substep_numerical_failure = True
                            break

                    if np.all(np.isfinite(delta)):
                        pass
                    else:
                        substep_numerical_failure = True
                        break

                    if diag_cfg.enable_backtracking:
                        self._trial_residual_evaluator.set_context(
                            kernel_list=kernel_list_eff,
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
                            evaluate_residual=self._trial_residual_evaluator,
                            config=diag_cfg,
                        )
                    else:
                        x_iter += delta

                    if np.all(np.isfinite(x_iter)):
                        pass
                    else:
                        substep_numerical_failure = True
                        break

                    last_res_norm = res_norm_inf

                if not substep_converged:
                    converged = False
                    failed_substep_count += 1
                    failed_substep_times_s.append(float(t_curr))
                    if np.isnan(first_failed_time_s):
                        first_failed_time_s = float(t_curr)
                    else:
                        pass
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
                    if substep_numerical_failure:
                        # Preserve the last accepted solution when Newton breaks down
                        # numerically so the EMT driver can report a failed substep
                        # instead of crashing the whole simulation.
                        x_iter[:] = x_prev
                    else:
                        pass

                    if substep_numerical_failure:
                        pass
                    else:
                        if effective_method == DynamicIntegrationMethod.DaeTrapezoidal:
                            dx_prev[:n_states] = (
                                    (2.0 / h_eff) * (x_iter[:n_states] - x_prev[:n_states])
                                    - dx_prev[:n_states]
                            )
                        elif effective_method == DynamicIntegrationMethod.DaeBackEuler:
                            dx_prev[:n_states] = (
                                    (x_iter[:n_states] - x_prev[:n_states]) / h_eff
                            )
                        elif effective_method == DynamicIntegrationMethod.DaeBDF2:
                            x_prev2[:] = x_prev
                            dx_prev[:n_states] = (
                                1.5 * x_iter[:n_states]
                                - 2.0 * x_prev[:n_states]
                                + 0.5 * x_prev2[:n_states]
                            ) / h_eff
                        else:
                            dx_prev[:n_states] = (
                                    (x_iter[:n_states] - x_prev[:n_states]) / h_eff
                            )

                    if effective_method != DynamicIntegrationMethod.DaeBDF2 and not substep_numerical_failure:
                        x_prev2[:] = x_prev
                    else:
                        pass

                    x_prev[:] = x_iter
                    t_local_prev = t_curr
                    is_first_local_step = False



            self.y[i + 1, :] = x_prev
            self.dy[i + 1, :] = dx_prev

        if self.verbose:
            print(f"JIT Finished: {time.time() - t_start:.4f}s")
        else:
            pass

        self._last_sim_loop_time = time.perf_counter() - loop_start
        self._last_runtime_stats = dict(
            sim_loop_s=self._last_sim_loop_time,
            total_newton_iterations=float(total_newton_iterations),
            jacobian_evaluations=float(jacobian_evaluation_count),
            aligned_substeps=float(aligned_substep_count),
            macro_steps=float(self.steps),
            failed_substeps=float(failed_substep_count),
            first_failed_time_s=float(first_failed_time_s),
            failed_substep_times_s=list(failed_substep_times_s),
        )

        return self.t, self.y, self.dy, well_initialized, converged

    def get_backend_build_stats(self) -> Dict[str, float]:
        """
        Return setup timings collected during backend compilation.

        :return: Backend build statistics.
        :rtype: Dict[str, float]
        """
        return dict(self._backend_build_stats)

    def get_last_runtime_stats(self) -> Dict[str, Any]:
        """
        Return runtime statistics collected during the latest simulation.

        :return: Runtime statistics.
        :rtype: Dict[str, Any]
        """
        return dict(self._last_runtime_stats)

    def get_last_sim_loop_time(self) -> float:
        """
        Return the latest integration-loop wall time.

        :return: Latest loop time in seconds.
        :rtype: float
        """
        return self._last_sim_loop_time

def _clip_debug_text(value: Any, width: int) -> str:
    """
    Format text for residual debug tables with width clipping.

    :param value: Value to be converted to string.
    :type value: Any
    :param width: Target column width.
    :type width: int
    :return: Left-justified clipped text.
    :rtype: str
    """
    text = str(value)
    if len(text) <= width:
        return text.ljust(width)
    if width <= 3:
        return text[:width]
    return text[:width - 3] + "..."


def _format_debug_number(value: Any, width: int = 13) -> str:
    """
    Format numeric values for debug output tables.

    :param value: Value to format.
    :type value: Any
    :param width: Target column width.
    :type width: int
    :return: Right-justified formatted value.
    :rtype: str
    """
    if value is None:
        return " " * width

    try:
        float_value = float(value)
    except Exception:
        return str(value).rjust(width)

    if np.isnan(float_value):
        return "nan".rjust(width)

    return f"{float_value: .6e}".rjust(width)


def _print_full_params_debug(full_params: Vec) -> None:
    """
    Print the numeric contents of the assembled solver parameter vector.

    :param full_params: Full parameter vector passed to the residual kernels.
    :type full_params: Vec
    :rtype: None
    """
    print("\nFULL params[] ORDER (numeric values):")
    for idx, param_value in enumerate(full_params):
        print(f"{idx:3d}  val={float(param_value)}")


def _print_residual_debug_table(res: Vec,
                                n_eqs: int,
                                x_iter: Vec,
                                x_prev: Vec,
                                dx_prev: Vec,
                                debug_info: list | None,
                                step_idx: int,
                                iter_idx: int) -> None:
    """
    Print a formatted table with the largest residuals and relevant state values.

    :param res: Current residual vector.
    :type res: Vec
    :param n_eqs: Number of equations in the nonlinear system.
    :type n_eqs: int
    :param x_iter: Current Newton iterate.
    :type x_iter: Vec
    :param x_prev: Previous converged solution vector.
    :type x_prev: Vec
    :param dx_prev: Previous derivative vector.
    :type dx_prev: Vec
    :param debug_info: Residual metadata collected during kernel build.
    :type debug_info: list | None
    :param step_idx: Macro time-step index.
    :type step_idx: int
    :param iter_idx: Newton iteration index.
    :type iter_idx: int
    :rtype: None
    """
    print("\n[Residual Debug] Sizes:")
    print(f"  n_eqs(res)       = {n_eqs}")
    print(f"  len(debug_info)  = {len(debug_info) if debug_info is not None else 'None'}")
    print(f"  n_states(vec)    = {len(x_iter)}")

    if debug_info is None:
        print("  [WARNING] self._residual_debug_info is missing.")
    elif len(debug_info) != n_eqs:
        print("  [WARNING] len(self._residual_debug_info) != n_eqs")
        print("            residual table labels may be wrong.\n")

    abs_res = np.abs(res)
    top_indices = np.argsort(abs_res, kind="stable")[::-1]

    width_idx = 4
    width_kind = 6
    width_state_idx = 8
    width_var_name = 40
    width_label = 62
    width_res = 13
    width_abs = 13
    width_xit = 13
    width_xpr = 13
    width_dxpr = 13

    title = f">>> TOP 20 LARGEST RESIDUALS (Step {step_idx}, Iter {iter_idx}) <<<"
    print("\n" + title)
    header = (
        f"{'idx':>{width_idx}} | "
        f"{'kind':<{width_kind}} | "
        f"{'state_i':>{width_state_idx}} | "
        f"{'var_name':<{width_var_name}} | "
        f"{'label':<{width_label}} | "
        f"{'res':>{width_res}} | "
        f"{'|res|':>{width_abs}} | "
        f"{'x_iter':>{width_xit}} | "
        f"{'x_prev':>{width_xpr}} | "
        f"{'dx_prev':>{width_dxpr}}"
    )
    print(header)
    print("-" * len(header))

    for idx in top_indices[:20]:
        if debug_info is not None and idx < len(debug_info):
            info = debug_info[idx]
            kind = info.get("kind", "UNK")
            var_name = info.get("var_name", "<?>")
            label = info.get("label", f"residual_{idx}")
            state_idx = info.get("state_idx", None)
        else:
            kind = "UNK"
            var_name = "<?>"
            label = f"residual_{idx}"
            state_idx = None

        if state_idx is not None and 0 <= state_idx < len(x_iter):
            x_it = x_iter[state_idx]
            x_pr = x_prev[state_idx]
        else:
            x_it = np.nan
            x_pr = np.nan

        if kind == "STATE" and state_idx is not None and 0 <= state_idx < len(dx_prev):
            dx_pr = dx_prev[state_idx]
        else:
            dx_pr = np.nan

        row = (
            f"{idx:>{width_idx}d} | "
            f"{kind:<{width_kind}} | "
            f"{state_idx if state_idx is not None else -1:>{width_state_idx}d} | "
            f"{_clip_debug_text(var_name, width_var_name)} | "
            f"{_clip_debug_text(label, width_label)} | "
            f"{_format_debug_number(res[idx], width_res)} | "
            f"{_format_debug_number(abs_res[idx], width_abs)} | "
            f"{_format_debug_number(x_it, width_xit)} | "
            f"{_format_debug_number(x_pr, width_xpr)} | "
            f"{_format_debug_number(dx_pr, width_dxpr)}"
        )
        print(row)

    print("-" * len(header))
    print("=" * len(header) + "\n")
