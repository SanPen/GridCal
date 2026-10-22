# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from typing import Tuple, Callable, List, Any, Dict, Union, Set, Optional
import time
import hashlib

import numpy as np
import numba as nb
from scipy.sparse import csc_matrix
from scipy.linalg import lu_factor, lu_solve
from scipy.sparse.linalg import splu, SuperLU

from VeraGridEngine.Utils.Symbolic.symbolic import Var, Expr, Const, BinOp, UnOp, Func
from VeraGridEngine.Utils.Symbolic.diagnostic import (
    NewtonDiagnosticsConfig,
    NewtonSolveContext,
    dense_lstsq_fallback,
    maybe_apply_backtracking,
    maybe_check_index1,
    with_newton_diagnostics,
)
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import (
    EmtBoundaryUpdateProtocol,
    EmtProblemTemplate,
    get_solver_forced_event_time,
    resolve_solver_boundary_step,
    resolve_solver_boundary_updater,
)
from VeraGridEngine.Utils.emt_boundary_update_wrapper import BoundaryUpdateWrapper
from VeraGridEngine.Utils.Symbolic.jit_compiler import (
    EagerEquationCompiler, EquationCompiler, MatrixVectorizedCompiler,
    _compile_to_file, _fingerprint_codegen_expr, _StructuralExpressionContext,
)
from VeraGridEngine.Simulations.EMT.solvers.structural_compiled_solver import (
    StructuralCompiledSparseFactorizationManager,
    _sparse_factor_manager_fallback,
)
from VeraGridEngine.Simulations.driver_template import DummySignal
from VeraGridEngine.Utils.NumericalMethods.external_sparse_solver_interface import SparseLinearSolverBackendProvider
from VeraGridEngine.enumerations import DynamicIntegrationMethod
from VeraGridEngine.basic_structures import Vec, Mat


DenseFactorization = Tuple[Any, Any]
DenseSolveBundle = Tuple[DenseFactorization, np.ndarray]
SparseSolveBundle = Tuple[SuperLU, csc_matrix]


def _build_backend_cache_token(
        method: DynamicIntegrationMethod,
        n_rows: int,
        n_cols: int,
        group_keys: List[str],
) -> str:
    """
    Return a deterministic cache token for backend-generated kernels.

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

    # The runtime slice changes at every local substep because events and
    # boundary updaters may mutate it in place.
    full_params_out[:n_runtime] = runtime_params

    # The static slice remains fixed, but copying it explicitly preserves the
    # stable [runtime | static] memory contract seen by compiled kernels.
    full_params_out[n_runtime:n_runtime + n_static] = static_params


def evaluate_vectorized_residual(
        residual_evaluator: Callable[..., Any],
        states: Vec,
        params: Vec,
        history: Vec,
        d_history: Vec,
        h: float,
        history2: Vec,
        residual_out: Vec,
) -> float:
    """
    Evaluate the fused vectorized residual into a caller-owned buffer.

    :param residual_evaluator: Fixed-signature residual evaluator.
    :type residual_evaluator: Callable[..., Any]
    :param states: Current Newton iterate.
    :type states: Vec
    :param params: Full parameter vector.
    :type params: Vec
    :param history: Previous accepted state.
    :type history: Vec
    :param d_history: Previous derivative vector.
    :type d_history: Vec
    :param h: Effective local time step.
    :type h: float
    :param history2: Secondary state history.
    :type history2: Vec
    :param residual_out: Destination residual buffer.
    :type residual_out: Vec
    :return: Residual infinity norm.
    :rtype: float
    """
    residual_evaluator(states, params, history, d_history, h, history2, residual_out)
    return float(np.max(np.abs(residual_out)))


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


def _sparse_factor_manager_solve(manager: StructuralCompiledSparseFactorizationManager, rhs: Vec) -> Vec:
    """
    Solve one sparse linear system through the factor manager.

    :param manager: Sparse factorization manager.
    :param rhs: Right-hand side vector.
    :return: Solution vector.
    """
    return manager.solve(rhs)


def _sparse_factor_manager_matrix(manager: StructuralCompiledSparseFactorizationManager) -> csc_matrix:
    """
    Return the active sparse Jacobian matrix held by one factor manager.

    :param manager: Sparse factorization manager.
    :return: Active sparse Jacobian matrix.
    """
    return manager.get_active_matrix()


class LegacyResidualEvaluatorAdapter:
    """
    Adapt one legacy 8-argument residual callable to the fixed 7-argument solver interface.
    """

    __slots__ = ["_residual_callable", "_vec_flat_args"]

    def __init__(self, residual_callable: Callable[..., Any], vec_flat_args: Vec) -> None:
        """
        Build one legacy residual adapter.

        :param residual_callable: Legacy residual callable.
        :param vec_flat_args: Legacy flat vectorized arguments.
        :return: None.
        """
        self._residual_callable = residual_callable
        self._vec_flat_args = vec_flat_args

    def __call__(
            self,
            states: Vec,
            params: Vec,
            history: Vec,
            d_history: Vec,
            h: float,
            history2: Vec,
            out: Vec,
    ) -> None:
        """
        Evaluate the wrapped legacy residual callable.

        :param states: Current Newton iterate.
        :param params: Full parameter vector.
        :param history: Previous accepted state.
        :param d_history: Previous derivative vector.
        :param h: Effective local time step.
        :param history2: Secondary state history.
        :param out: Residual output buffer.
        :return: None.
        """
        self._residual_callable(states, params, history, d_history, h, self._vec_flat_args, out, history2)


def build_residual_evaluator(
        residual_dispatcher: FusedResidualDispatcher | DirectResidualDispatcher,
        vec_flat_args: Optional[Vec] = None,
) -> Callable[[Vec, Vec, Vec, Vec, float, Vec, Vec], None]:
    """
    Build one fixed-signature residual evaluator for the current dispatcher.

    The fused and direct dispatchers expose the same ``evaluate()`` API, so the
    Newton hot path can call one fixed-signature method without any dynamic
    attribute probing or signature branching.

    :param residual_dispatcher: Residual dispatcher.
    :type residual_dispatcher: FusedResidualDispatcher | DirectResidualDispatcher
    :param vec_flat_args: Optional flat vectorized argument buffer used by legacy residual callables.
    :type vec_flat_args: Optional[Vec]
    :return: Residual evaluator with signature ``(states, params, history,
        d_history, h, history2, out)``.
    :rtype: Callable[[Vec, Vec, Vec, Vec, float, Vec, Vec], None]
    """
    if isinstance(residual_dispatcher, (FusedResidualDispatcher, DirectResidualDispatcher)):
        return residual_dispatcher.evaluate
    else:
        pass

    if callable(residual_dispatcher):
        legacy_vec_flat_args: Vec

        if vec_flat_args is None:
            legacy_vec_flat_args = np.zeros(0, dtype=np.float64)
        else:
            legacy_vec_flat_args = vec_flat_args

        return LegacyResidualEvaluatorAdapter(residual_dispatcher, legacy_vec_flat_args)
    else:
        raise TypeError("Unsupported residual dispatcher type")


# ==============================================================================
# Generic helpers
# ==============================================================================

def _safe_njit(py_func: Callable[..., Any], fastmath: bool = True, cache: bool = True, signature: Any = None) -> \
Callable[..., Any]:
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
        return nb.jit(signature, fastmath=fastmath, cache=cache)(py_func)
    else:
        return nb.jit(fastmath=fastmath, cache=cache)(py_func)


def canonicalize_expression(
        expr: Expr,
        runtime_uids: Set[int],
        param_uids: Set[int],
) -> Tuple[str, List[Var]]:
    """
    Return the shared structural signature and first-occurrence runtime gathers.

    :param expr: Symbolic expression whose literal values must remain exact.
    :param runtime_uids: UIDs belonging to the runtime state/algebraic vector.
    :param param_uids: UIDs belonging to the shared parameter vector.
    :return: Structural fingerprint and one gathered variable per runtime UID.
    :raises RuntimeError: If a supported variable has no runtime/parameter classification.
    """
    # Bind structural roles only for this expression. The existing compiler walk
    # preserves exact constants; its code-generation maps are unused in this context.
    context: _StructuralExpressionContext = _StructuralExpressionContext(runtime_uids, param_uids)
    signature: str = _fingerprint_codegen_expr(expr, dict(), dict(), "", None, None, context)
    return signature, context.runtime_variables


class VectorizedKernelSpec:
    """
    Typed container for one vectorized residual kernel.
    """

    __slots__ = ["_kernel", "_indices", "_target_rows", "_row_count"]

    def __init__(self, kernel: Callable[..., Any], indices: np.ndarray, target_rows: np.ndarray) -> None:
        """
        Build one vectorized residual-kernel specification.

        :param kernel: Compiled eager kernel.
        :type kernel: Callable[..., Any]
        :param indices: Runtime gather matrix.
        :type indices: np.ndarray
        :param target_rows: Residual rows written by the kernel.
        :type target_rows: np.ndarray
        :return: None.
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

    def get_indices(self) -> np.ndarray:
        """
        Return the runtime gather matrix.

        :return: Runtime gather matrix.
        :rtype: np.ndarray
        """
        return self._indices

    def get_target_rows(self) -> np.ndarray:
        """
        Return the residual target rows.

        :return: Residual target rows.
        :rtype: np.ndarray
        """
        return self._target_rows

    def get_row_count(self) -> int:
        """
        Return the number of rows emitted by the kernel.

        :return: Number of grouped rows.
        :rtype: int
        """
        return self._row_count


class FusedResidualDispatcher:
    """
    Dispatcher that applies all vectorized residual kernels in order.

    The structural group kernels are already eagerly compiled with Numba. The
    dispatcher keeps one reusable work row per group so the hot loop does not
    allocate temporary residual blocks.
    """

    __slots__ = ["_kernel_specs", "_work_buffer"]

    def __init__(self, kernel_specs: List[VectorizedKernelSpec]) -> None:
        """
        Build the fused residual dispatcher.

        :param kernel_specs: Vectorized residual-kernel specifications.
        :type kernel_specs: List[VectorizedKernelSpec]
        :return: None.
        :rtype: None
        """
        max_kernel_size: int = 0
        kernel_spec: VectorizedKernelSpec

        self._kernel_specs = kernel_specs

        for kernel_spec in kernel_specs:
            if kernel_spec.get_row_count() > max_kernel_size:
                max_kernel_size = kernel_spec.get_row_count()
            else:
                pass

        # The work buffer keeps one row per structural group and enough columns
        # for the largest group output.
        self._work_buffer: Mat = np.zeros((len(kernel_specs), max_kernel_size), dtype=np.float64)

    def evaluate(
            self,
            states: Vec,
            params: Vec,
            history: Vec,
            d_history: Vec,
            h: float,
            history2: Vec,
            out: Vec,
    ) -> None:
        """
        Evaluate the grouped residual system in place.

        :param states: Current Newton iterate.
        :type states: Vec
        :param params: Full parameter vector.
        :type params: Vec
        :param history: Previous accepted state.
        :type history: Vec
        :param d_history: Previous derivative vector.
        :type d_history: Vec
        :param h: Effective local time step.
        :type h: float
        :param history2: Secondary state history.
        :type history2: Vec
        :param out: Residual output buffer.
        :type out: Vec
        :return: None.
        :rtype: None
        """
        out[:] = 0.0

        kernel_index: int = 0

        while kernel_index < len(self._kernel_specs):
            kernel_spec: VectorizedKernelSpec = self._kernel_specs[kernel_index]
            row_count: int = kernel_spec.get_row_count()
            local_out: Vec = self._work_buffer[kernel_index, :row_count]

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
            out[kernel_spec.get_target_rows()] = local_out[:row_count]
            kernel_index += 1

    def __call__(self, *args: Any) -> None:
        """
        Evaluate the grouped residual system in place.

        :param states: Current Newton iterate.
        :type states: Vec
        :param params: Full parameter vector.
        :type params: Vec
        :param history: Previous accepted state.
        :type history: Vec
        :param d_history: Previous derivative vector.
        :type d_history: Vec
        :param h: Effective local time step.
        :type h: float
        :param history2: Secondary state history.
        :type history2: Vec
        :param out: Residual output buffer.
        :type out: Vec
        :return: None.
        :rtype: None
        """
        if len(args) == 7:
            states, params, history, d_history, h, history2, out = args
        elif len(args) == 8:
            states, params, history, d_history, h, _vec_flat_args, out, history2 = args
        else:
            raise TypeError(f"Unsupported fused residual signature with {len(args)} arguments")

        self.evaluate(states, params, history, d_history, h, history2, out)


class VectorizedResidualTrialEvaluator:
    """
    Callable helper that evaluates vectorized residuals during backtracking.
    """

    __slots__ = ["_residual_evaluator", "_full_params", "_x_prev", "_dx_prev", "_h_eff", "_x_prev2"]

    def __init__(self) -> None:
        """
        Build one empty trial-residual evaluator.

        :return: None.
        :rtype: None
        """
        self._residual_evaluator: Callable[..., Any] | None = None
        self._full_params: Vec | None = None
        self._x_prev: Vec | None = None
        self._dx_prev: Vec | None = None
        self._h_eff: float = 0.0
        self._x_prev2: Vec | None = None

    def set_context(
            self,
            residual_evaluator: Callable[..., Any],
            full_params: Vec,
            x_prev: Vec,
            dx_prev: Vec,
            h_eff: float,
            x_prev2: Vec,
    ) -> None:
        """
        Store the residual-evaluation context of the current Newton step.

        :param residual_evaluator: Fixed-signature residual evaluator.
        :type residual_evaluator: Callable[..., Any]
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
        self._residual_evaluator = residual_evaluator
        self._full_params = full_params
        self._x_prev = x_prev
        self._dx_prev = dx_prev
        self._h_eff = float(h_eff)
        self._x_prev2 = x_prev2

    def __call__(self, trial_x: Vec, out_res: Vec) -> float:
        """
        Evaluate one trial Newton iterate during backtracking.

        :param trial_x: Trial iterate.
        :type trial_x: Vec
        :param out_res: Destination residual buffer.
        :type out_res: Vec
        :return: Residual infinity norm.
        :rtype: float
        """
        if self._residual_evaluator is None:
            return np.inf
        else:
            pass

        if self._full_params is None or self._x_prev is None or self._dx_prev is None or self._x_prev2 is None:
            return np.inf
        else:
            pass

        return evaluate_vectorized_residual(
            residual_evaluator=self._residual_evaluator,
            states=trial_x,
            params=self._full_params,
            history=self._x_prev,
            d_history=self._dx_prev,
            h=self._h_eff,
            history2=self._x_prev2,
            residual_out=out_res,
        )


class DirectResidualDispatcher:
    """
    Residual dispatcher backed by one monolithic in-place kernel.
    """

    __slots__ = ["_kernel"]

    def __init__(self, kernel: Callable[..., Any]) -> None:
        """
        Build the direct residual dispatcher.

        :param kernel: Monolithic in-place residual kernel.
        :type kernel: Callable[..., Any]
        :return: None.
        :rtype: None
        """
        self._kernel = kernel

    def evaluate(
            self,
            states: Vec,
            params: Vec,
            history: Vec,
            d_history: Vec,
            h: float,
            history2: Vec,
            out: Vec,
    ) -> None:
        """
        Evaluate the full residual system in place.

        :param states: Current Newton iterate.
        :type states: Vec
        :param params: Full parameter vector.
        :type params: Vec
        :param history: Previous accepted state.
        :type history: Vec
        :param d_history: Previous derivative vector.
        :type d_history: Vec
        :param h: Effective local time step.
        :type h: float
        :param history2: Secondary state history.
        :type history2: Vec
        :param out: Residual output buffer.
        :type out: Vec
        :return: None.
        :rtype: None
        """
        self._kernel(states, params, history, d_history, h, out, history2)

    def __call__(self, *args: Any) -> None:
        """
        Evaluate the full residual system in place.

        :param states: Current Newton iterate.
        :type states: Vec
        :param params: Full parameter vector.
        :type params: Vec
        :param history: Previous accepted state.
        :type history: Vec
        :param d_history: Previous derivative vector.
        :type d_history: Vec
        :param h: Effective local time step.
        :type h: float
        :param history2: Secondary state history.
        :type history2: Vec
        :param out: Residual output buffer.
        :type out: Vec
        :return: None.
        :rtype: None
        """
        if len(args) == 7:
            states, params, history, d_history, h, history2, out = args
        elif len(args) == 8:
            states, params, history, d_history, h, _vec_flat_args, out, history2 = args
        else:
            raise TypeError(f"Unsupported direct residual signature with {len(args)} arguments")

        self.evaluate(states, params, history, d_history, h, history2, out)

@nb.jit(cache=True, fastmath=True)
def _scatter_color_jvp_to_csc_data(
        jvp: np.ndarray, data: np.ndarray, color_ptr: np.ndarray,col_ptr: np.ndarray,
        row_idx: np.ndarray, data_idx: np.ndarray, color_id: int) -> None:
    k0 = color_ptr[color_id]
    k1 = color_ptr[color_id + 1]
    for k in range(k0, k1):
        p0 = col_ptr[k]
        p1 = col_ptr[k + 1]
        for p in range(p0, p1):
            data[data_idx[p]] = jvp[row_idx[p]]


def _compile_master_jacobian_kernel(ad_kernel: Callable[..., Any], n_colors: int) -> Callable[..., Any]:
    """
    Build the eager sparse Jacobian dispatcher.

    :param ad_kernel: Generic AD kernel reused across colors.
    :type ad_kernel: Callable[..., Any]
    :param n_colors: Number of graph colors.
    :type n_colors: int
    :return: Jacobian dispatcher.
    :rtype: Callable[..., Any]
    """
    return StructuralVectorizedMasterJacobianDispatcher(ad_kernel=ad_kernel, n_colors=n_colors)


class StructuralVectorizedMasterJacobianDispatcher:
    """
    Callable dispatcher that evaluates one generic AD kernel across all colors.
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
        Evaluate all color JVPs and scatter them into CSC storage.

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


class Predictor:
    """
    Computes an explicit predictor for the Newton initial guess x_iter.
    """
    __slots__ = ['n_states', 'algebraic_derivative_by_index']

    def __init__(self,
                 n_states: int,
                 algebraic_derivative_by_index: Dict[int, float] | None = None) -> None:
        self.n_states = n_states
        self.algebraic_derivative_by_index = dict() if algebraic_derivative_by_index is None else algebraic_derivative_by_index

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
        for idx, derivative in self.algebraic_derivative_by_index.items():
            x_iter[idx] = x_prev[idx] + h * derivative
        return x_iter

class EquationGroup:
    """
    Data structure to hold clustered equations for auto-vectorization.
    Replaces the generic dictionary for strict type hinting and safety.
    """
    __slots__ = ['_idx_matrix', '_row_indices', '_template_eq', '_template_vars']

    def __init__(self) -> None:
        self._idx_matrix: List[List[int]] = list()
        self._row_indices: List[int] = list()
        self._template_eq: Expr | None = None
        self._template_vars: List[Var] | None = None

    def add_indices(self, var_indices: List[int], row_index: int) -> None:
        """Adds matrix indices and row index to the cluster."""
        self._idx_matrix.append(var_indices)
        self._row_indices.append(row_index)

    def set_template(self, template_eq: Expr, template_vars: List[Var]) -> None:
        """Sets the structural template for this group."""
        self._template_eq = template_eq
        self._template_vars = template_vars

    def get_idx_matrix(self) -> List[List[int]]:
        """Returns the index matrix."""
        return self._idx_matrix

    def get_row_indices(self) -> List[int]:
        """Returns the row indices."""
        return self._row_indices

    def get_template_eq(self) -> Expr | None:
        """Returns the template equation."""
        return self._template_eq

    def get_template_vars(self) -> List[Var] | None:
        """Returns the template variables."""
        return self._template_vars


# ==============================================================================
# Sparse AD Jacobian
# ==============================================================================

class SparseADJacobian:
    __slots__ = [
        'verbose', 'equations', 'variables', 'parameters', 'diff_vars', 'method', 'dtype',
        'n_rows', 'n_cols', 'var_map', 'col_rows', 'J', 'colors', 'n_colors',
        'color_groups', 'color_ptr', 'color_cols', 'col_ptr', 'row_idx', 'data_idx',
        '_compiler', '_ad_kernel', '_master_dispatcher', '_seed_matrix', '_jvp_work_buffer', '_data_buffer'
    ]
    def __init__(
            self,
            equations: List[Expr],
            variables: List[Var],
            parameters: List[Var],
            diff_vars: List[Var],
            method: DynamicIntegrationMethod,
            use_cse: bool = True,
            dtype: Any = np.float64,
            verbose: bool = False,
    ) -> None:
        self.verbose = verbose
        self.equations = equations
        self.variables = variables
        self.parameters = parameters
        self.diff_vars = diff_vars
        self.method = method
        self.dtype = dtype

        self.n_rows = len(equations)
        self.n_cols = len(variables)

        self.var_map: Dict[int, int] = dict({v.uid: i for i, v in enumerate(variables)})

        # Sparsity detection
        col_rows: List[List[int]] = list([list() for _ in range(self.n_cols)])
        for r_idx, eq in enumerate(equations):
            stack: List[Expr] = list([eq])
            visited: set = set()
            uids: set = set()

            while stack:
                node: Expr = stack.pop()
                if id(node) in visited:
                    pass
                else:
                    visited.add(id(node))

                    match node:
                        case Var():
                            uids.add(node.uid)
                            if node.base_var is not None:
                                uids.add(node.base_var.uid)
                            else:
                                pass

                        case BinOp(left=l, right=r):
                            stack.append(l)
                            stack.append(r)

                        case UnOp(operand=op):
                            stack.append(op)

                        case Func(arg=a):
                            stack.append(a)

                        case _:
                            pass

            for uid in uids:
                j: int = self.var_map.get(uid, -1)
                if j >= 0:
                    col_rows[j].append(r_idx)
                else:
                    pass

        self.col_rows = list([sorted(set(rows)) for rows in col_rows])

        # CSC structure
        indptr = np.zeros(self.n_cols + 1, dtype=np.int32)
        nnz: int = 0
        for j in range(self.n_cols):
            nnz += len(self.col_rows[j])
            indptr[j + 1] = nnz

        indices = np.empty(nnz, dtype=np.int32)
        data = np.zeros(nnz, dtype=self.dtype)

        k: int = 0
        for j in range(self.n_cols):
            for r_idx in self.col_rows[j]:
                indices[k] = r_idx
                k += 1

        self.J = csc_matrix((data, indices, indptr), shape=(self.n_rows, self.n_cols))

        # Coloring
        self.colors, self.n_colors = self._greedy_color_columns(self.col_rows, self.n_rows)
        groups: List[List[int]] = list([list() for _ in range(self.n_colors)])
        for j in range(self.n_cols):
            groups[self.colors[j]].append(j)
        self.color_groups = groups

        # Scatter map
        color_cols: List[int] = []
        color_ptr = np.zeros(self.n_colors + 1, dtype=np.int32)
        for c in range(self.n_colors):
            color_ptr[c] = len(color_cols)
            color_cols.extend(self.color_groups[c])
        color_ptr[self.n_colors] = len(color_cols)

        col_ptr = np.zeros(len(color_cols) + 1, dtype=np.int32)
        total_map:int = 0
        for kk, j in enumerate(color_cols):
            total_map += len(self.col_rows[j])
            col_ptr[kk + 1] = total_map

        row_idx = np.empty(total_map, dtype=np.int32)
        data_idx = np.empty(total_map, dtype=np.int32)

        pos: int = 0
        indptr_arr = self.J.indptr
        for kk, j in enumerate(color_cols):
            base = indptr_arr[j]
            for local, r_idx in enumerate(self.col_rows[j]):
                row_idx[pos] = r_idx
                data_idx[pos] = base + local
                pos += 1

        self.color_ptr, self.color_cols = color_ptr, np.asarray(color_cols, dtype=np.int32)
        self.col_ptr, self.row_idx, self.data_idx = col_ptr, row_idx, data_idx

        # Compile the generic eager AD kernel once and reuse it across graph colors.
        self._compiler = EagerEquationCompiler(variables=variables, parameters=parameters, diff_vars=diff_vars, method=method)
        k_name = f"advec_step_generic_{method.name}_{self.n_rows}_{self.n_cols}"
        py_ad, signature_tpe = self._compiler.compile_ad_kernel(
            equations,
            func_name=k_name,
            use_cse=use_cse,
            active_indices=None,
        )
        self._ad_kernel = _safe_njit(py_ad, cache=True, fastmath=True, signature=signature_tpe)

        self._seed_matrix = np.zeros((self.n_colors, self.n_cols), dtype=self.dtype)
        for c in range(self.n_colors):
            self._seed_matrix[c, self.color_groups[c]] = 1.0

        self._master_dispatcher = _compile_master_jacobian_kernel(self._ad_kernel, self.n_colors)
        self._jvp_work_buffer = np.zeros((self.n_colors, self.n_rows), dtype=self.dtype)
        self._data_buffer = self.J.data

    @staticmethod
    def _greedy_color_columns(col_rows: List[List[int]], n_rows: int) -> Tuple[np.ndarray, int]:
        n_cols: int = len(col_rows)
        row_cols: List[List[int]] = list([list() for _ in range(n_rows)])
        for j in range(n_cols):
            for r_idx in col_rows[j]:
                row_cols[r_idx].append(j)

        adj: List[set] = list([set() for _ in range(n_cols)])
        for cols in row_cols:
            m: int = len(cols)
            for a in range(m):
                for b in range(a + 1, m):
                    if cols[b] != cols[a]:
                        adj[cols[a]].add(cols[b])
                        adj[cols[b]].add(cols[a])
                    else:
                        pass

        degrees = np.array([len(adj[j]) for j in range(n_cols)], dtype=np.int32)
        order = list(np.argsort(-degrees, kind="stable"))
        colors = -np.ones(n_cols, dtype=np.int32)
        max_color = -1
        used = np.zeros(n_cols, dtype=np.bool_)

        for j in order:
            used[:] = False
            for nbj in adj[j]:
                if colors[nbj] >= 0:
                    used[colors[nbj]] = True
                else:
                    pass
            c: int = 0
            while c < n_cols and used[c]:
                c += 1
            colors[j] = c
            if c > max_color:
                max_color = c
            else:
                pass
        return colors, int(max_color + 1)

    def __call__(self,
                 states: Vec,
                 params: Vec,
                 history: Vec,
                 d_history: Vec,
                 h: float,
                 history2: Vec | None = None) -> csc_matrix:
        if history2 is None:
            history2 = history

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

    def get_matrix(self) -> csc_matrix:
        """
        Return the reusable CSC Jacobian shell.

        :return: CSC Jacobian shell.
        :rtype: csc_matrix
        """
        return self.J

    def get_data_buffer(self) -> Vec:
        """
        Return the reusable CSC numeric buffer.

        :return: CSC numeric buffer.
        :rtype: Vec
        """
        return self._data_buffer

# ==============================================================================
# StructuralVectorizedSolver
# ==============================================================================
class StructuralVectorizedSolver:
    __slots__ = [
        'problem', 't0', 't_end', 'h', 'method', 'pred_method', 'dense_threshold', 'verbose', 'newton_max_iter',
        '_newton_tolerance',
        'vec_jacobian', 'vec_flat_args', 'fused_residual', 'vec_kernels',
        '_state_vars', '_algebraic_vars', '_diff_vars', '_state_eqs', '_algebraic_eqs',
        'sorted_vars', '_n_state', '_n_vars', '_n_diff', 'uid2idx_vars',
        '_event_parameters', '_parameters', '_parameters_values', '_event_params_fn',
        'jit_jacobians_ad', 'vectorized_ready', '_last_sim_loop_time', '_newton_diag_config', '_vectorized_warmup_done',
        '_predictor', '_runtime_param_count', '_static_parameter_buffer', '_full_parameter_buffer', '_residual_buffer',
        '_trial_state_buffer', '_trial_residual_buffer', '_trial_residual_evaluator',
        '_backend_build_stats', '_last_runtime_stats', '_sparse_solver_backend_provider', '_sparse_factorization_manager', '_cancel_checker', '_progress_signal',
        '_diff_base_var_indices', '_use_compiled_runtime_parameters'
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
                 newton_max_iter: int = 20,
                 auto_vectorization: bool = True,
                 sparse_solver_backend_provider: SparseLinearSolverBackendProvider | None = None,
                 newton_diag_config: NewtonDiagnosticsConfig | None = None,
                 progress_signal: DummySignal | None = None,
                 cancel_checker: Callable[[], bool] | None = None,
                 newton_tolerance: float = 1.0e-6,
                 use_compiled_runtime_parameters: bool = True)-> None:
        """
        :param problem: The DAE problem definition.
        :param t0: Initial time.
        :param t_end: End time.
        :param h: Time step.
        :param method: DynamicIntegrationMethod (DaeTrapezoidal, DaeBackEuler, DaeBDF2).
        :param pred_method: DynamicIntegrationMethod used in the predictor step if method is explicit.
        :param dense_threshold: Threshold to switch between dense and sparse linear solvers.
        :param verbose: Print compilation and simulation timings.
        :param newton_max_iter: Maximum Newton corrections per local EMT substep.
            The final corrected candidate is checked without another correction.
        :param newton_tolerance: Absolute infinity-norm tolerance for Newton residual convergence.
        :param sparse_solver_backend_provider: Sparse linear solver backend provider.
        :type sparse_solver_backend_provider: SparseLinearSolverBackendProvider | None
        :param progress_signal: Optional progress signal updated during the simulation loop.
        :type progress_signal: DummySignal | None
        :param use_compiled_runtime_parameters: Activate the compiled runtime-parameter evaluator at
            the start of simulate; False keeps the interpreted evaluator on a problem not enabled before.
        """
        self.problem = problem
        self._use_compiled_runtime_parameters: bool = bool(use_compiled_runtime_parameters)
        self.t0 = t0
        self.t_end = t_end
        self.h = h
        self.method = method
        self.pred_method = DynamicIntegrationMethod.OdeEuler if pred_method is None else pred_method
        self.dense_threshold = dense_threshold
        self.verbose = verbose
        self.newton_max_iter: int = int(newton_max_iter)
        self._newton_tolerance: float = float(newton_tolerance)
        if not np.isfinite(self._newton_tolerance) or self._newton_tolerance <= 0.0:
            raise ValueError("newton_tolerance must be finite and greater than zero.")
        self._newton_diag_config = newton_diag_config or NewtonDiagnosticsConfig(
            compute_dense_cond=False,
            enable_fallback=False,
            enable_index1_check=False,
            enable_backtracking=False,
        )

        self.vec_jacobian = None
        self.vec_flat_args = None
        self.fused_residual = None
        self.vec_kernels = None

        self._state_vars = self.problem.get_state_vars()
        self._algebraic_vars = self.problem.get_algebraic_vars()
        self._diff_vars = self.problem.get_diff_vars()
        self._state_eqs = self.problem.get_state_eqs()
        self._algebraic_eqs = self.problem.get_algebraic_eqs()


        self.sorted_vars: List[Any] = list()
        self.sorted_vars.extend(self._state_vars)
        self.sorted_vars.extend(self._algebraic_vars)
        self._n_state = len(self._state_vars)
        self._n_vars = len(self.sorted_vars)
        self._n_diff = len(self._diff_vars)

        self.uid2idx_vars = {v.uid: i for i, v in enumerate(self.sorted_vars)}
        self._diff_base_var_indices = np.full(self._n_diff, -1, dtype=np.int64)
        for diff_idx, diff_var in enumerate(self._diff_vars):
            base_var = diff_var.base_var
            if base_var is not None:
                self._diff_base_var_indices[diff_idx] = self.uid2idx_vars.get(base_var.uid, -1)

        self._event_parameters = self.problem.get_variable_parameters()
        self._parameters = self.problem.get_constant_parameters()
        self._parameters_values = self.problem.get_parameters_values()

        self.jit_jacobians_ad: Dict[DynamicIntegrationMethod, SparseADJacobian] = dict()
        self.vectorized_ready = False
        self._last_sim_loop_time = 0.0
        self._vectorized_warmup_done = False
        algebraic_predictor_derivatives = problem.algebraic_predictor_derivatives if hasattr(problem, "algebraic_predictor_derivatives") else {}
        algebraic_derivative_by_index: Dict[int, float] = {}
        for var_uid, derivative in algebraic_predictor_derivatives.items():
            var_idx = self.uid2idx_vars.get(var_uid, None)
            if var_idx is not None and var_idx >= self._n_state:
                algebraic_derivative_by_index[var_idx] = float(derivative)
        self._predictor = Predictor(
            n_states=self._n_state,
            algebraic_derivative_by_index=algebraic_derivative_by_index,
        )
        self._runtime_param_count: int = len(self._event_parameters)
        self._static_parameter_buffer: Vec = np.asarray(
            [float(constant.value) for constant in self._parameters_values],
            dtype=np.float64,
        )
        self._full_parameter_buffer: Vec = np.zeros(
            self._runtime_param_count + self._static_parameter_buffer.shape[0],
            dtype=np.float64,
        )
        self._residual_buffer: Vec = np.zeros(self._n_vars, dtype=np.float64)
        self._trial_state_buffer: Vec = np.zeros(self._n_vars, dtype=np.float64)
        self._trial_residual_buffer: Vec = np.zeros(self._n_vars, dtype=np.float64)
        self._trial_residual_evaluator = VectorizedResidualTrialEvaluator()
        self._backend_build_stats: Dict[str, float] = dict()
        self._last_runtime_stats: Dict[str, float] = dict()
        self._sparse_solver_backend_provider = sparse_solver_backend_provider
        self._sparse_factorization_manager = None
        self._progress_signal: DummySignal | None = progress_signal
        self._cancel_checker = cancel_checker

        if auto_vectorization:
            self.auto_detect_vectorization(method)

    def auto_detect_vectorization(self, method: DynamicIntegrationMethod | None = None) -> None:
        """
        Infers the algebraic structure of the DAE system (clustering) and compiles
        the vectorized matrix kernels.
        """
        if method is None:
            method = self.method

        if self.verbose:
            print("--- [AUTO-VEC] Inferring Algebraic Structure (Clustering) ---")
        else:
            pass
        t0 = time.perf_counter()

        groups: Dict[str, EquationGroup] = dict()

        n_state: int = len(self._state_eqs)
        n_alg: int = len(self._algebraic_eqs)
        full_eq_list: List[Expr] = [Const(0.0) for _ in range(n_state + n_alg)]

        # Build full residual system:
        #   differential eqs -> d_x - f(x, y, p) = 0
        #   algebraic eqs    -> g(x, y, p) = 0
        for i, rhs_eq in enumerate(self._state_eqs):
            sv = self._state_vars[i]
            d_term = Var(name=f"d_{sv.name}", base_var=sv)
            full_eq_list[i] = d_term - rhs_eq

        for j, alg_eq in enumerate(self._algebraic_eqs):
            full_eq_list[n_state + j] = alg_eq

        # UIDs of runtime variables (states + algebraics + diff placeholders through base_var)
        runtime_uids: Set[int] = set(self.uid2idx_vars.keys())

        # UIDs of parameters
        param_uids: Set[int] = set()
        for p in self._event_parameters:
            param_uids.add(p.uid)
        for p in self._parameters:
            param_uids.add(p.uid)

        # -----------------------------
        # PHASE 2: CLUSTERING
        # -----------------------------
        grouping_t0: float = time.perf_counter()

        for i, residual_eq in enumerate(full_eq_list):
            sig_str, runtime_vars = canonicalize_expression(
                residual_eq,
                runtime_uids=runtime_uids,
                param_uids=param_uids
            )

            # Cluster by structural signature
            eq_hash = hashlib.sha256(sig_str.encode("utf-8")).hexdigest()

            if eq_hash in groups:
                group = groups[eq_hash]
            else:
                group = EquationGroup()
                groups[eq_hash] = group

            var_indices: List[int] = []
            for v in runtime_vars:
                target_uid: int = v.uid if v.base_var is None else v.base_var.uid
                idx: int | None = self.uid2idx_vars.get(target_uid, None)

                if idx is None:
                    raise RuntimeError(
                        f"Runtime variable missing in uid2idx_vars. "
                        f"eq={i}, var={v.name}, target_uid={target_uid}"
                    )

                var_indices.append(idx)

            if group.get_template_eq() is None:
                group.set_template(residual_eq, runtime_vars)
            else:
                template_vars = group.get_template_vars()
                if template_vars is None:
                    raise RuntimeError(f"Internal error: template_vars is None for group {eq_hash}")

                if len(var_indices) != len(template_vars):
                    raise RuntimeError(
                        f"Inconsistent clustered runtime var count for group {eq_hash}. "
                        f"eq={i}, got={len(var_indices)}, expected={len(template_vars)}"
                    )

            group.add_indices(var_indices, i)

        if self.verbose:
            print(f"   [AUTO-VEC] Detected {len(groups)} patterns in {len(full_eq_list)} total equations.")
        else:
            pass
        grouping_s: float = time.perf_counter() - grouping_t0

        # -----------------------------
        # PHASE 3: KERNEL COMPILATION
        # -----------------------------
        self.vec_kernels: List[VectorizedKernelSpec] = list()
        group_keys: List[str] = sorted(list(groups.keys()))
        backend_cache_token: str = _build_backend_cache_token(method, len(full_eq_list), self._n_vars, group_keys)
        avg_group_size: float = float(len(full_eq_list) / max(len(group_keys), 1))
        use_direct_residual: bool = len(group_keys) >= 20 and avg_group_size <= 3.0

        all_params: List[Any] = list()
        all_params.extend(self._event_parameters)
        all_params.extend(self._parameters)

        vec_compiler = EagerEquationCompiler(self.sorted_vars, all_params, diff_vars=self._diff_vars, method=method)

        residual_compile_t0: float = time.perf_counter()

        if use_direct_residual:
            direct_name: str = f"structural_vectorized_residual_{backend_cache_token}"
            py_func: Callable[..., Any]
            signature_tpe: Any
            py_func, signature_tpe = vec_compiler.compile(
                equations=full_eq_list,
                func_name=direct_name,
                use_cse=False,
                offset=0,
                inplace=True,
            )
            self.fused_residual = DirectResidualDispatcher(
                _safe_njit(py_func, cache=True, fastmath=True, signature=signature_tpe)
            )
            self.vec_kernels = list()
        else:
            for group_key_index, signature in enumerate(group_keys):
                group_data = groups[signature]
                k_name = f"vec_kernel_{method.name}_{group_key_index}"

                py_func, signature_tpe = vec_compiler.compile_matrix_kernel(
                    group_data.get_template_eq(),
                    func_name=k_name,
                    template_vars=group_data.get_template_vars()
                )

                self.vec_kernels.append(
                    VectorizedKernelSpec(
                        # The vectorized residual kernels are compiled eagerly so the
                        # benchmark build phase captures their cost explicitly and the
                        # simulation phase measures the hot loop more cleanly.
                        kernel=_safe_njit(py_func, cache=True, fastmath=True, signature=signature_tpe),
                        indices=np.array(group_data.get_idx_matrix(), dtype=np.int32),
                        target_rows=np.array(group_data.get_row_indices(), dtype=np.int32),
                    )
                )

            self.fused_residual = FusedResidualDispatcher(self.vec_kernels)

        residual_compile_s: float = time.perf_counter() - residual_compile_t0

        # -----------------------------
        # PHASE 4: DISPATCHER SETUP
        # -----------------------------
        temp_args: List[Any] = list()
        kernel_spec: VectorizedKernelSpec
        for kernel_spec in self.vec_kernels:
            temp_args.extend([kernel_spec.get_target_rows(), kernel_spec.get_indices()])

        self.vec_flat_args = tuple(temp_args)

        # -----------------------------
        # PHASE 5: JACOBIAN SETUP
        # -----------------------------
        jacobian_build_t0: float = time.perf_counter()

        if method not in self.jit_jacobians_ad:
            self.jit_jacobians_ad[method] = SparseADJacobian(
                full_eq_list, self.sorted_vars, all_params, self._diff_vars, method, verbose=self.verbose
            )

        self.vec_jacobian = self.jit_jacobians_ad[method]
        self._sparse_factorization_manager = StructuralCompiledSparseFactorizationManager(
            self.vec_jacobian.get_matrix(),
            self.vec_jacobian.get_data_buffer(),
            self._sparse_solver_backend_provider,
        )
        self.vectorized_ready = True
        jacobian_build_s: float = time.perf_counter() - jacobian_build_t0

        self._backend_build_stats = dict(
            grouping_s=grouping_s,
            residual_compile_s=residual_compile_s,
            jacobian_build_s=jacobian_build_s,
            direct_residual_mode=1.0 if use_direct_residual else 0.0,
            structural_groups=float(len(group_keys)),
            total_s=time.perf_counter() - t0,
        )

        if self.verbose:
            print(f"   [AUTO-VEC] Setup finished in {self._backend_build_stats['total_s']:.4f}s")
        else:
            pass


    def simulate(self,
                 x0: Union[Vec| None] = None,
                 dx0: Union[Vec| None] = None,
                 params0: Union[Vec| None] = None,
                 boundary_updater: EmtBoundaryUpdateProtocol | None = None) -> Tuple[Vec, Mat, Mat, bool, bool]:

        """
        Run the vectorized DAE time-domain simulation.

        :param x0: Initial state vector.
        :param dx0: Initial derivative vector.
        :param params0: Initial event parameters.
        :param boundary_updater: Optional override for the problem boundary updater.
        :return: Matching completed macro prefixes for time, state and derivative,
                 followed by initialization and convergence flags.
        """

        # Problem construction, initialization and event-group selection are complete
        # here. Activate the compiled runtime-parameter evaluator before the boundary
        # updater reset evaluates the runtime parameters, as StructuralCompiledSolver does.
        if self._use_compiled_runtime_parameters:
            self.problem.enable_compiled_runtime_parameter_evaluator()
        else:
            pass

        if x0 is None:
            x0 = self.problem.get_x0()
        else: pass

        if dx0 is None:
            dx0 = self.problem.get_dx0()
        else: pass

        active_boundary_updater = resolve_solver_boundary_updater(self.problem, boundary_updater, float(self.t0))

        if params0 is not None:
            params0 =  np.array(params0, dtype=np.float64, copy=True)
        else:
            params0 = self.problem.event_params_values.copy()

        return self._simulate_vectorized(self.t0, self.t_end, self.h, x0, dx0, params0, self.method,
                                         active_boundary_updater, self.verbose, self.dense_threshold)

    def _simulate_vectorized(self,
                             t0:float,
                             t_end:float,
                             h: float,
                             x0: Vec,
                             dx0: Vec,
                             params0: Vec,
                             method: DynamicIntegrationMethod,
                             boundary_updater: EmtBoundaryUpdateProtocol | None,
                             verbose: bool,
                             dense_threshold: int)-> Tuple[Vec, Mat, Mat, bool, bool]:
        """Integrate accepted local steps and publish completed macro samples.

        :param t0: Initial simulation time.
        :param t_end: Requested simulation horizon.
        :param h: Requested macro time step.
        :param x0: Initial state and algebraic vector.
        :param dx0: Initial differential vector.
        :param params0: Initial runtime parameters.
        :param method: Implicit integration scheme.
        :param boundary_updater: Optional transactional boundary provider.
        :param verbose: Whether to print integration progress.
        :param dense_threshold: Largest system using dense factorization.
        :return: Completed time/state/derivative prefixes and solver status flags.
        """
        bdf2_startup_pending: bool = method == DynamicIntegrationMethod.DaeBDF2
        prepared_method: DynamicIntegrationMethod = (
            DynamicIntegrationMethod.DaeBackEuler if bdf2_startup_pending else method
        )
        method_transition_s: float = 0.0
        # Rebuild the complete startup backend on every fresh BDF2 call, so no
        # accepted history or factorization leaks from an earlier simulation.
        if bdf2_startup_pending or not self.vectorized_ready:
            self.auto_detect_vectorization(prepared_method)
        else:
            pass

        steps: int = int(np.ceil((t_end - t0) / h))
        t: Vec = t0 + h * np.arange(steps + 1, dtype=np.float64)
        y: Mat = np.zeros((steps + 1, self._n_vars), dtype=np.float64)
        dy: Mat = np.zeros((steps + 1, self._n_diff), dtype=np.float64)
        y[0] = x0.copy()
        dy[0] = dx0.copy()

        converged: bool = True
        well_initialized: bool = True

        x_prev: Vec = x0.copy()
        dx_prev: Vec = dx0.copy()
        x_prev2: Vec = x0.copy()
        base_slopes: Vec = np.zeros(x_prev.size if bdf2_startup_pending else 0, dtype=np.float64)
        x_iter: Vec = x0.copy()
        res_global: Vec = self._residual_buffer
        trial_state: Vec = self._trial_state_buffer
        trial_residual: Vec = self._trial_residual_buffer

        static_params = self._static_parameter_buffer
        ev_params = np.array(params0, dtype=np.float64, copy=True)

        full_params = self._full_parameter_buffer

        if len(ev_params) > 0:
            runtime_params = self.problem.def_event_params_fn(ev_params, float(t0))
            fill_full_parameter_buffer(runtime_params, static_params, full_params)
        else:
            fill_full_parameter_buffer(ev_params, static_params, full_params)

        if boundary_updater is not None:
            boundary_updater.update(float(t0), x_prev, full_params)

        if len(ev_params) > 0:
            ev_params[:] = full_params[:len(ev_params)]

        use_dense: bool = (self._n_vars <= dense_threshold)
        trace_collector = self.problem.get_newton_trace_collector()
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
        residual_evaluator = build_residual_evaluator(self.fused_residual, self.vec_flat_args)

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
                solver_name="emt_sparse_backend",
                matrix_getter=_sparse_factor_manager_matrix,
            )
        else:
            pass

        if verbose:
            print("-> JIT Warmup.")
        else:
            pass

        _ = evaluate_vectorized_residual(
            residual_evaluator=residual_evaluator,
            states=x_prev,
            params=full_params,
            history=x_prev,
            d_history=dx_prev,
            h=h,
            history2=x_prev2,
            residual_out=res_global,
        )
        _ = self.vec_jacobian(
            states=x_prev,
            params=full_params,
            history=x_prev,
            d_history=dx_prev,
            h=h,
            history2=x_prev2
        )

        # Only completed macro rows are published after a local rejection.
        completed_samples: int = 1
        t_start_loop: float = time.perf_counter()
        total_newton_iterations: int = 0
        jacobian_evaluation_count: int = 0
        aligned_substep_count: int = 0
        sparse_factor_manager = self._sparse_factorization_manager

        if verbose:
            print(f"-> Starting VECTORIZED Simulation (Integration loop)...")
        else:
            pass

        for i in range(steps):

            if self._progress_signal is not None:
                self.problem.report_progress2(i, steps)
            else:
                pass

            if self._cancel_checker is not None and self._cancel_checker():
                return t[:i + 1].copy(), y[:i + 1, :].copy(), dy[:i + 1, :].copy(), well_initialized, converged

            t_step_start: float = float(t[i])
            t_step_target: float = float(t[i + 1])

            t_local_prev: float = t_step_start
            is_first_local_step: bool = True

            while t_local_prev < (t_step_target - 1e-15):

                forced_event_time = get_solver_forced_event_time(
                    boundary_updater,
                    float(t_local_prev),
                    float(t_step_target),
                )

                if forced_event_time is None:
                    t_curr = t_step_target
                else:
                    t_curr = min(float(forced_event_time), t_step_target)

                    if t_curr <= t_local_prev + 1e-15:
                        t_curr = t_step_target
                    else:
                        pass

                is_aligned_substep: bool = t_curr < (t_step_target - 1e-15)

                if is_aligned_substep:
                    aligned_substep_count += 1
                else:
                    aligned_substep_count = aligned_substep_count

                if method == DynamicIntegrationMethod.DaeBDF2 and is_aligned_substep:
                    raise NotImplementedError(
                        "force_step_alignment is not implemented for DaeBDF2 in StructuralVectorizedSolver."
                    )
                else:
                    pass

                h_eff: float = float(t_curr - t_local_prev)

                effective_method: DynamicIntegrationMethod = (
                    DynamicIntegrationMethod.DaeBackEuler if bdf2_startup_pending else method
                )
                if prepared_method != effective_method:
                    # Switch all residual/Jacobian/layout/factor owners together;
                    # a BE factorization cannot solve the BDF2 Jacobian.
                    transition_start: float = time.perf_counter()
                    self.auto_detect_vectorization(effective_method)
                    residual_evaluator = build_residual_evaluator(self.fused_residual, self.vec_flat_args)
                    sparse_factor_manager = self._sparse_factorization_manager
                    prepared_method = effective_method
                    method_transition_s += time.perf_counter() - transition_start
                else:
                    pass

                # Update params in-place for the local substep end
                runtime_params = self.problem.def_event_params_fn(ev_params, float(t_curr))
                fill_full_parameter_buffer(runtime_params, static_params, full_params)

                if boundary_updater is not None:
                    state_event_retry_time: float | None = (
                        boundary_updater.update(t_curr, x_prev, full_params)
                    )
                else:
                    state_event_retry_time = None

                ev_params[:] = full_params[:len(ev_params)]

                x_iter[:] = x_prev
                last_res_norm: float = 1.0

                # IMPORTANT:
                # LU factors must be local to each substep, because x_prev, params and h_eff may change.
                cached_lu_dense: DenseSolveBundle | None = None
                if sparse_factor_manager is None:
                    pass
                else:
                    if sparse_factor_manager.has_factorization():
                        sparse_factor_manager.invalidate()
                    else:
                        pass

                # PREDICTOR
                if (
                    i == 0
                    and is_first_local_step
                    and method in {DynamicIntegrationMethod.DaeBackEuler, DynamicIntegrationMethod.DaeTrapezoidal}
                ):
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
                    newton_iteration_count = self.newton_max_iter + 1
                else:
                    newton_iteration_count = 0
                for k in range(newton_iteration_count):
                    # Check in Python, outside fastmath, before assembling a candidate.
                    if not np.all(np.isfinite(x_iter)):
                        break
                    else:
                        pass
                    total_newton_iterations += 1
                    ctx: NewtonSolveContext | None = None
                    res_norm: float = evaluate_vectorized_residual(
                        residual_evaluator=residual_evaluator,
                        states=x_iter,
                        params=full_params,
                        history=x_prev,
                        d_history=dx_prev,
                        h=h_eff,
                        history2=x_prev2,
                        residual_out=res_global,
                    )

                    # The compiled norm may hide NaN entries; inspect the full buffer.
                    if not np.all(np.isfinite(res_global)):
                        break
                    else:
                        pass

                    if res_norm < self._newton_tolerance:
                        substep_converged = True
                        break
                    else:
                        pass

                    # Validate the last iterate even when the correction budget is exhausted.
                    if k >= self.newton_max_iter:
                        break
                    else:
                        pass

                    if diagnostics_enabled:
                        ctx = NewtonSolveContext(
                            t=float(t_curr),
                            step_idx=int(i),
                            newton_iter=int(k),
                            phase="jit_vec",
                            method=str(effective_method),
                        )
                        ctx.res_norm_inf = res_norm
                    else:
                        pass

                    recompute: bool = (cached_lu_dense is None and (sparse_factor_manager is None or not sparse_factor_manager.has_factorization())) or \
                                      (k > 0 and (res_norm / (last_res_norm + 1e-16)) > 0.5)

                    if recompute:
                        cached_J: csc_matrix = self.vec_jacobian(
                            states=x_iter,
                            params=full_params,
                            history=x_prev,
                            d_history=dx_prev,
                            h=h_eff,
                            history2=x_prev2
                        )
                        jacobian_evaluation_count += 1

                        if use_dense:
                            dense_jacobian = cached_J.toarray()

                            if diagnostics_enabled and ctx is not None:
                                maybe_check_index1(dense_jacobian, self._n_state, ctx=ctx, config=diag_cfg)
                            else:
                                pass

                            cached_lu_dense = (lu_factor(dense_jacobian), dense_jacobian)
                        else:
                            if diagnostics_enabled and ctx is not None:
                                maybe_check_index1(cached_J, self._n_state, ctx=ctx, config=diag_cfg)
                            else:
                                pass

                            if sparse_factor_manager is None:
                                raise RuntimeError("StructuralVectorizedSolver sparse factorization manager is not initialized")
                            else:
                                sparse_factor_manager.factorize()
                            cached_lu_dense = None
                    else:
                        pass

                    if use_dense:
                        if diagnostics_enabled and ctx is not None:
                            assert dense_solve is not None
                            assert cached_lu_dense is not None
                            delta = dense_solve(cached_lu_dense, -res_global, ctx)
                        else:
                            assert cached_lu_dense is not None
                            delta = lu_solve(cached_lu_dense[0], -res_global)
                    else:
                        if diagnostics_enabled and ctx is not None:
                            assert sparse_solve is not None
                            assert sparse_factor_manager is not None
                            delta = sparse_solve(sparse_factor_manager, -res_global, ctx)
                        else:
                            assert sparse_factor_manager is not None
                            delta = sparse_factor_manager.solve(-res_global)

                    max_step_inf = diag_cfg.max_newton_step_inf
                    if max_step_inf is not None and max_step_inf > 0.0:
                        step_inf = float(np.max(np.abs(delta))) if delta.size > 0 else 0.0
                        if step_inf > max_step_inf:
                            delta *= float(max_step_inf) / step_inf

                    if diag_cfg.enable_backtracking:
                        self._trial_residual_evaluator.set_context(
                            residual_evaluator=residual_evaluator,
                            full_params=full_params,
                            x_prev=x_prev,
                            dx_prev=dx_prev,
                            h_eff=h_eff,
                            x_prev2=x_prev2,
                        )

                        maybe_apply_backtracking(
                            x_iter,
                            delta,
                            res_norm,
                            trial_state,
                            trial_residual,
                            evaluate_residual=self._trial_residual_evaluator,
                            config=diag_cfg,
                        )
                    else:
                        x_iter += delta

                    last_res_norm = res_norm

                if not substep_converged:
                    converged = False
                    if i == 0 and is_first_local_step:
                        well_initialized = False
                    else:
                        pass
                else:
                    pass

                if state_event_retry_time is None:
                    state_event_retry_time = resolve_solver_boundary_step(
                        boundary_updater=boundary_updater,
                        accepted=substep_converged,
                        params=full_params,
                        committed_time=float(t_curr),
                        committed_state=x_iter,
                    )
                else:
                    pass

                # Resolve rejection once, then stop before any accepted history changes.
                if not substep_converged:
                    break
                else:
                    pass

                if substep_converged and state_event_retry_time is None:
                    # A post-acceptance native sample may publish new held
                    # outputs. Retain them for the next aligned sub-step.
                    ev_params[:] = full_params[:len(ev_params)]
                else:
                    pass

                if state_event_retry_time is not None:
                    x_iter[:] = x_prev
                else:
                    if method == DynamicIntegrationMethod.DaeBDF2:
                        # Keep runtime slopes separate from canonical derivative
                        # slots, and calculate them before rotating state history.
                        if bdf2_startup_pending:
                            base_slopes[:] = (x_iter - x_prev) / h_eff
                        else:
                            base_slopes[:] = (1.5 * x_iter - 2.0 * x_prev + 0.5 * x_prev2) / h_eff
                        diff_idx: int
                        base_idx: int
                        for diff_idx, base_idx in enumerate(self._diff_base_var_indices):
                            if base_idx >= 0:
                                dx_prev[diff_idx] = base_slopes[base_idx]
                            else:
                                pass
                        bdf2_startup_pending = False
                    elif method == DynamicIntegrationMethod.DaeTrapezoidal:
                        if self._n_diff == 0:
                            dx_prev[:self._n_state] = (
                                    (2.0 / h_eff) * (x_iter[:self._n_state] - x_prev[:self._n_state])
                                    - dx_prev[:self._n_state]
                            )
                        else:
                            for diff_idx, base_idx in enumerate(self._diff_base_var_indices):
                                if base_idx >= 0:
                                    dx_prev[diff_idx] = (2.0 / h_eff) * (x_iter[base_idx] - x_prev[base_idx]) - dx_prev[diff_idx]
                                else:
                                    pass
                    else:
                        dx_prev[:self._n_state] = (
                                                          x_iter[:self._n_state] - x_prev[:self._n_state]
                                                  ) / h_eff

                    x_prev2[:] = x_prev

                    x_prev[:] = x_iter
                    t_local_prev = t_curr
                    is_first_local_step = False



            # A partially accepted macro interval is not an output sample.
            if not converged:
                break
            else:
                pass

            y[i + 1] = x_prev
            dy[i + 1] = dx_prev
            completed_samples += 1

        self._last_sim_loop_time = time.perf_counter() - t_start_loop - method_transition_s
        self._last_runtime_stats = dict(
            sim_loop_s=self._last_sim_loop_time,
            method_transition_s=method_transition_s,
            total_newton_iterations=float(total_newton_iterations),
            jacobian_evaluations=float(jacobian_evaluation_count),
            aligned_substeps=float(aligned_substep_count),
            macro_steps=float(completed_samples - 1),
        )

        if verbose:
            print(f"VECTORIZED INTEGRATION LOOP Finished: {self._last_sim_loop_time:.4f}s")
        else:
            pass

        return t[:completed_samples].copy(), y[:completed_samples, :].copy(), dy[:completed_samples, :].copy(), well_initialized, converged

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
