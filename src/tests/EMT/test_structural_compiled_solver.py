# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can see it at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Any, Dict, List, Sequence, Tuple, cast

import numba as nb
import numpy as np
import pytest
from scipy.sparse import csc_matrix

from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.diagnostic import (
    NewtonDiagnosticsConfig,
    NewtonTraceCollector,
    maybe_apply_backtracking,
    maybe_check_index1,
)
from VeraGridEngine.Utils.Symbolic.symbolic import BinOp, Const, Expr, Func, UnOp, Var
from VeraGridEngine.Utils.Symbolic.jit_compiler import EagerEquationCompiler, _fingerprint_codegen_expr
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.Simulations.EMT.solvers.StructuralVectorizedSolver import (
    StructuralVectorizedSolver,
    canonicalize_expression as canonicalize_vectorized_expression,
)
from VeraGridEngine.Simulations.EMT.solvers.structural_compiled_solver import (
    StructuralCompiledBoundaryUpdateWrapper,
    StructuralCompiledSolver,
    canonicalize_expression as canonicalize_compiled_expression,
)
from VeraGridEngine.enumerations import DynamicIntegrationMethod
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver, evaluate_batched_residual as evaluate_symbolic_residual
from VeraGridEngine.Simulations.EMT.solvers.solver_AD import JitAdSolver, evaluate_batched_residual as evaluate_ad_residual
from VeraGridEngine.Simulations.EMT.solvers.StructuralVectorizedSolver import build_residual_evaluator, evaluate_vectorized_residual
from tests.EMT.test_discretization_verify import make_solver


@pytest.mark.parametrize("solver_class", (JitSymbolicSolver, JitAdSolver, StructuralVectorizedSolver, StructuralCompiledSolver))
def test_bdf2_effective_startup_jacobian(
        solver_class: type[JitSymbolicSolver] | type[JitAdSolver] | type[StructuralVectorizedSolver] | type[StructuralCompiledSolver]) -> None:
    """Check BE and BDF2 Jacobians against independent central differences.

    :param solver_class: Existing backend, including both structural implementations.
    :return: None.
    """
    x: Var = Var("bdf_jac_x")
    dx: Var = Var("bdf_jac_dx", base_var=x)
    z: Var = Var("bdf_jac_z")
    block: Block = Block(name="BdfJacobian", state_vars=list((x,)), diff_vars=list((dx,)),
                         state_eqs=list((z,)), algebraic_vars=list((z,)),
                         algebraic_eqs=list((z + x,)), parameters=dict())
    solver: JitSymbolicSolver | JitAdSolver | StructuralVectorizedSolver | StructuralCompiledSolver
    problem: EmtProblemTemplate
    solver, problem = make_solver(solver_class, block, 0.3, 0.1, DynamicIntegrationMethod.DaeBDF2, 1e-10, 0)
    state: np.ndarray = np.array((0.8, -0.8))
    previous: np.ndarray = np.array((1.0, -1.0))
    previous2: np.ndarray = np.array((1.2, -1.2))
    params: np.ndarray = build_full_params(problem)
    residual: np.ndarray = np.empty(2)
    numeric: np.ndarray = np.empty((2, 2))
    method: DynamicIntegrationMethod
    alpha: float
    for method, alpha in ((DynamicIntegrationMethod.DaeBackEuler, 10.0), (DynamicIntegrationMethod.DaeBDF2, 15.0)):
        # Match every backend's existing compiler history convention explicitly.
        history_slope: np.ndarray = np.zeros(1) if isinstance(solver, StructuralVectorizedSolver) else np.zeros(2)
        analytic: np.ndarray
        if isinstance(solver, JitSymbolicSolver):
            solver.build_jit_kernel(method)
            solver._build_jit_symbolic_hybrid(method, use_sparse=False)
            analytic = solver.jit_jacobian_symbolic[f"{method}_False"].evaluate(
                state, params, previous, history_slope, 0.1, previous2).copy()
        elif isinstance(solver, JitAdSolver):
            solver.build_jit_ad(method=method)
            analytic = solver.jit_jacobian_ad[method](state, params, previous, history_slope, 0.1, previous2).toarray().copy()
        elif isinstance(solver, StructuralVectorizedSolver):
            solver.auto_detect_vectorization(method)
            analytic = solver.vec_jacobian(state, params, previous, history_slope, 0.1, previous2).toarray().copy()
        else:
            solver._build_vectorized_backend(method)
            assert solver._jacobian_evaluator is not None
            analytic = solver._jacobian_evaluator.evaluate(state, params, previous, history_slope, 0.1, previous2).toarray().copy()
        column: int
        for column in range(2):
            samples: np.ndarray = np.empty((2, 2))
            sign_index: int
            sign: float
            for sign_index, sign in enumerate((-1.0, 1.0)):
                trial: np.ndarray = state.copy()
                trial[column] += sign * 1e-6
                if isinstance(solver, JitSymbolicSolver):
                    evaluate_symbolic_residual(solver.jit_kernels[method], trial, params, previous,
                                               history_slope, 0.1, previous2, residual)
                elif isinstance(solver, JitAdSolver):
                    evaluate_ad_residual(solver.jit_kernels_ad[method], trial, params, previous,
                                         history_slope, 0.1, previous2, residual)
                elif isinstance(solver, StructuralVectorizedSolver):
                    evaluate_vectorized_residual(build_residual_evaluator(solver.fused_residual, solver.vec_flat_args),
                                                 trial, params, previous, history_slope, 0.1, previous2, residual)
                else:
                    assert solver._residual_assembler is not None
                    solver._residual_assembler.evaluate(trial, params, previous, history_slope, 0.1, previous2, residual)
                samples[sign_index, :] = residual
            numeric[:, column] = (samples[1, :] - samples[0, :]) / 2e-6
        np.testing.assert_allclose(analytic, np.array(((alpha, -1.0), (1.0, 1.0))), atol=1e-7, rtol=1e-7)
        np.testing.assert_allclose(analytic, numeric, atol=1e-7, rtol=1e-7)

    # Runtime diagnostics must identify the method actually solved at each phase.
    collector: NewtonTraceCollector = NewtonTraceCollector()
    problem.set_newton_trace_collector(collector)
    result: Tuple[np.ndarray, np.ndarray, np.ndarray, bool, bool] = solver.simulate(
        x0=np.array((1.0, -1.0)), dx0=np.array((17.0,)))
    assert result[4] and collector.records
    assert collector.records[0]["method"] == str(DynamicIntegrationMethod.DaeBackEuler)
    assert collector.records[-1]["method"] == str(DynamicIntegrationMethod.DaeBDF2)
    if isinstance(solver, StructuralCompiledSolver):
        stats: Dict[str, float] = solver.get_last_runtime_stats()
        assert stats["sparse_numeric_factorizations"] == 2.0
        assert stats["sparse_solve_calls"] == 3.0
    else:
        pass


class GenericEmtProblem(EmtProblemTemplate):
    """
    Minimal EMT problem implementation for structural compiled solver tests.
    """
    __slots__ = []


def build_full_params(problem: EmtProblemTemplate) -> np.ndarray:
    """
    Build full parameters array combining variable and static parameters.

    :param problem: EMT problem instance.
    :returns: Concatenated parameter array.
    """
    ev: np.ndarray = np.zeros(problem.get_variable_parameter_number(), dtype=np.float64)
    static_vals: np.ndarray = np.array([float(p.value) for p in problem.get_parameters_values()], dtype=np.float64)
    return np.concatenate((ev, static_vals))


def build_repeated_decay_block(n_states: int = 4, k_val: float = 2.0) -> Tuple[Block, Var]:
    """
    Build a block with repeated decay equations sharing the same parameter.

    Creates n_states identical decay equations: dx_i/dt = -k * x_i
    for i in [0, n_states).

    :param n_states: Number of decay state variables.
    :param k_val: Decay rate constant.
    :returns: Tuple of (block, k_var).
    """
    k: Var = Var("k")
    state_vars: List[Var] = list()
    diff_vars: List[Var] = list()
    state_eqs: List[Expr] = list()

    for i in range(n_states):
        x_i: Var = Var(f"x_{i}")
        dx_i: Var = Var(f"d_x_{i}", base_var=x_i)
        state_vars.append(x_i)
        diff_vars.append(dx_i)
        state_eqs.append(-k * x_i)

    block: Block = Block(
        name="RepeatedDecay",
        state_vars=state_vars,
        state_eqs=state_eqs,
        diff_vars=diff_vars,
        parameters={k: Const(k_val)},
    )
    block.unify_blocks()
    return block, k


def build_zero_dynamics_block() -> Block:
    """
    Build a block with zero dynamics (constant state).

    State equation is dx/dt = 0, so the state remains constant.

    :returns: Block representing zero dynamics.
    """
    x: Var = Var("x")
    dx: Var = Var("d_x", base_var=x)

    held_output: Var = Var("held_native_output")
    block: Block = Block(
        name="ZeroDynamics",
        state_vars=[x],
        state_eqs=[Const(0.0)],
        diff_vars=[dx],
        parameters=dict(),
    )
    block.unify_blocks()
    block.mode_dict = {held_output: Const(0.0)}
    return block


def build_singular_dae_block() -> Block:
    """
    Build a singular DAE block for index-1 guard testing.

    Creates a minimal DAE where the algebraic equation is identically zero,
    which violates the index-1 condition and should trigger the runtime guard.

    :returns: Block representing a singular DAE system.
    """
    x: Var = Var("x")
    y: Var = Var("y")
    dx: Var = Var("d_x", base_var=x)
    block: Block = Block(
        name="SingularDae",
        state_vars=[x],
        algebraic_vars=[y],
        diff_vars=[dx],
        state_eqs=[Const(0.0)],
        algebraic_eqs=[Const(0.0)],
        parameters=dict(),
    )
    block.unify_blocks()
    return block


def build_scalar_state_block() -> Block:
    """
    Build a scalar state block for backtracking tests.

    :returns: Block with single state variable.
    """
    x: Var = Var("x")
    dx: Var = Var("d_x", base_var=x)
    block: Block = Block(
        name="ScalarState",
        state_vars=[x],
        diff_vars=[dx],
        state_eqs=[Const(0.0)],
        parameters=dict(),
    )
    block.unify_blocks()
    return block


def array_ptr(arr: np.ndarray) -> int:
    """
    Get memory address of numpy array data buffer.

    :param arr: NumPy array.
    :returns: Integer memory address.
    """
    return int(arr.__array_interface__["data"][0])


class InexactCompiledResidualAssembler:
    """
    Inexact residual assembler for backtracking tests.

    Provides a residual function that produces inaccurate results,
    requiring backtracking to converge properly.

    :ivar _tag: Internal identifier.
    """
    __slots__ = ["_tag"]

    def __init__(self) -> None:
        self._tag = "compiled_inexact_residual"

    def evaluate(self, states, params, history, d_history, h, history2, data_out) -> None:
        """Compute inexact residual for testing backtracking."""
        _unused = (self._tag, params, history, d_history, h, history2)
        data_out[:] = 0.0
        data_out[0] = states[0] ** 2 - 1.0


class InexactCompiledJacobian:
    """
    Inexact Jacobian for backtracking tests.

    :ivar _tag: Internal identifier.
    """
    __slots__ = ["_tag"]

    def __init__(self) -> None:
        self._tag = "compiled_inexact_jacobian"

    def evaluate(self, states, params, history, d_history, h, history2) -> csc_matrix:
        """Compute inexact Jacobian for testing backtracking."""
        _unused = (self._tag, params, history, d_history, h, history2)
        return csc_matrix([[0.2 * states[0]]], dtype=np.float64)

    def get_data_buffer(self) -> np.ndarray:
        """Return data buffer allocation."""
        _unused = self._tag
        return np.zeros(1, dtype=np.float64)


class SingularCompiledResidualAssembler:
    """
    Singular residual assembler for index-1 guard tests.

    :ivar _tag: Internal identifier.
    """
    __slots__ = ["_tag"]

    def __init__(self) -> None:
        self._tag = "compiled_singular_residual"

    def evaluate(self, states, params, history, d_history, h, history2, data_out) -> None:
        """Compute singular residual for testing index guard."""
        _unused = (self._tag, states, params, history, d_history, h, history2)
        data_out[:] = 0.0
        data_out[0] = 1.0


class SingularCompiledJacobian:
    """
    Near-singular Jacobian for index-1 guard tests.

    :ivar _tag: Internal identifier.
    """
    __slots__ = ["_tag"]

    def __init__(self) -> None:
        self._tag = "compiled_singular_jacobian"

    def evaluate(self, states, params, history, d_history, h, history2) -> csc_matrix:
        """Compute near-singular Jacobian matrix."""
        _unused = (self._tag, states, params, history, d_history, h, history2)
        return csc_matrix(np.array([[1.0, 0.0], [0.0, 1.0e-16]], dtype=np.float64))

    def get_data_buffer(self) -> np.ndarray:
        """Return data buffer allocation."""
        _unused = self._tag
        return np.zeros(1, dtype=np.float64)


def inexact_vectorized_residual(x_iter, full_params, x_prev, dx_prev, h, vec_flat_args, res_global, x_prev2) -> None:
    """Vectorized inexact residual for backtracking tests."""
    _unused = (full_params, x_prev, dx_prev, h, vec_flat_args, x_prev2)
    res_global[:] = 0.0
    res_global[0] = x_iter[0] ** 2 - 1.0


class InexactVectorizedJacobian:
    """
    Inexact Jacobian for vectorized backtracking tests.

    :ivar _tag: Internal identifier.
    """
    __slots__ = ["_tag"]

    def __init__(self) -> None:
        self._tag = "vectorized_inexact_jacobian"

    def __call__(self, states, params, history, d_history, h, history2=None) -> csc_matrix:
        """Compute inexact Jacobian for backtracking."""
        _unused = (self._tag, params, history, d_history, h, history2)
        return csc_matrix([[0.2 * states[0]]], dtype=np.float64)


def singular_vectorized_residual(x_iter, full_params, x_prev, dx_prev, h, vec_flat_args, res_global, x_prev2) -> None:
    """Vectorized singular residual for index-1 guard tests."""
    _unused = (x_iter, full_params, x_prev, dx_prev, h, vec_flat_args, x_prev2)
    res_global[:] = 0.0
    res_global[0] = 1.0


class SingularVectorizedJacobian:
    """
    Near-singular Jacobian for vectorized index-1 guard tests.

    :ivar _tag: Internal identifier.
    """
    __slots__ = ["_tag"]

    def __init__(self) -> None:
        self._tag = "vectorized_singular_jacobian"

    def __call__(self, states, params, history, d_history, h, history2=None) -> csc_matrix:
        """Compute near-singular Jacobian matrix."""
        _unused = (self._tag, states, params, history, d_history, h, history2)
        return csc_matrix(np.array([[1.0, 0.0], [0.0, 1.0e-16]], dtype=np.float64))


class ForcedEventTracker(StructuralCompiledBoundaryUpdateWrapper):
    """
    Boundary updater that tracks forced event times for alignment testing.

    :ivar _forced_times: List of forced event times.
    :ivar _tol: Tolerance for time comparisons.
    :ivar _cursor: Current index in forced times.
    :ivar query_calls: Record of get_next_forced_event_time calls.
    :ivar update_calls: Record of update() calls.
    """
    __slots__ = [
        "_forced_times",
        "_tol",
        "_cursor",
        "query_calls",
        "update_calls",
        "update_parameter_values",
        "commit_calls",
    ]

    def __init__(self, forced_times: Sequence[float], tol: float = 1e-12) -> None:
        self._forced_times = [float(v) for v in forced_times]
        self._tol = float(tol)
        self._cursor = 0
        self.query_calls: List[Tuple[float, float]] = list()
        self.update_calls: List[float] = list()
        self.update_parameter_values: List[float] = list()
        self.commit_calls: List[float] = list()

    def get_next_forced_event_time(self, t_prev: float, t_target: float) -> float | None:
        """Return next forced event time within the target interval."""
        self.query_calls.append((float(t_prev), float(t_target)))

        idx: int = self._cursor
        while idx < len(self._forced_times):
            event_time: float = self._forced_times[idx]
            if (t_prev + self._tol) < event_time <= (t_target + self._tol):
                return event_time
            idx += 1

        return None

    def update(self, t: float, x: np.ndarray, params: np.ndarray) -> None:
        """Record update call and advance cursor."""
        _unused: np.ndarray = x
        t_float: float = float(t)
        self.update_calls.append(t_float)

        self.update_parameter_values.append(float(params[0]))
        while self._cursor < len(self._forced_times):
            if self._forced_times[self._cursor] <= t_float + self._tol:
                self._cursor += 1
            else:
                break

    def commit_boundary(
            self,
            t: float,
            x: np.ndarray,
            params: np.ndarray,
    ) -> None:
        """Record one post-convergence manufacturer sample boundary.

        :param t: Accepted solver boundary time.
        :param x: Accepted network state.
        :param params: Runtime parameter vector receiving held outputs.
        :return: None.
        """
        _unused: np.ndarray = x
        commit_time: float = float(t)
        self.commit_calls.append(commit_time)
        params[0] = commit_time


# =============================================================================
# TESTS
# =============================================================================

@pytest.mark.parametrize("compiled", (False, True))
def test_canonical_signatures_preserve_runtime_derivative_roles(compiled: bool) -> None:
    """
    Check occurrence roles without changing UID-based runtime gather columns.

    :param compiled: Whether to check the compiled backend canonicalizer.
    :return: None.
    """
    x: Var = Var("role_x")
    y: Var = Var("role_y")
    dx: Var = Var("role_dx", base_var=x)
    dy: Var = Var("role_dy", base_var=y)
    x_alias: Var = Var("role_x", uid=x.uid)
    dx_alias: Var = Var("role_dx", uid=dx.uid, base_var=x_alias)
    expressions: List[Expr] = list((x, dx, y, dy, dx + x, dy + y,
                                    dx_alias + x_alias, x + x, dx + dx,
                                    dx + y, x + dy, dx_alias + y))
    runtime_uids: set[int] = set((x.uid, y.uid))
    signatures: List[str] = list("" for _ in expressions)
    collected: List[List[Var]] = list(list() for _ in expressions)
    expression_index: int
    expression: Expr

    # Renaming and aliasing may change objects, but must preserve structural roles.
    for expression_index, expression in enumerate(expressions):
        if compiled:
            signatures[expression_index], collected[expression_index] = canonicalize_compiled_expression(
                expression, runtime_uids, set(),
            )
        else:
            signatures[expression_index], collected[expression_index] = canonicalize_vectorized_expression(
                expression, runtime_uids, set(),
            )

    assert signatures[0] != signatures[1]
    assert signatures[0] == signatures[2]
    assert signatures[1] == signatures[3]
    assert signatures[4] == signatures[5] == signatures[6]
    assert signatures[7] != signatures[8]
    assert signatures[9] == signatures[11]
    assert signatures[9] != signatures[10]
    assert signatures[4] != signatures[9]

    # A value and its derivative still consume one base-variable column, even
    # when the first occurrence is a derivative or a fresh same-UID alias.
    for expression_index in (4, 6, 7, 8):
        assert len(collected[expression_index]) == 1
        variable: Var = collected[expression_index][0]
        runtime_uid: int = variable.uid if variable.base_var is None else variable.base_var.uid
        assert runtime_uid == x.uid
    assert collected[9][0] is dx
    assert collected[9][1] is y
    assert collected[10][0] is x
    assert collected[10][1] is dy


@pytest.mark.parametrize("method", (DynamicIntegrationMethod.DaeBackEuler,
                                   DynamicIntegrationMethod.DaeTrapezoidal,
                                   DynamicIntegrationMethod.DaeBDF2))
@pytest.mark.parametrize("compiled", (False, True))
@pytest.mark.parametrize("permuted", (False, True))
def test_structural_backends_separate_derivative_and_value_residuals(
        method: DynamicIntegrationMethod, compiled: bool, permuted: bool,
) -> None:
    """
    Compare grouped residuals and Jacobians with independent linear DAE oracles.

    The system has two states satisfying ``x'=1`` and two algebraic rows
    satisfying ``z-1=0``. Equivalent rows must share two kernels, while the
    differential and algebraic roles must remain distinct. Fresh renamed models
    and repeated evaluations cover sequential construction and warm execution.

    :param method: Existing implicit discretization to verify.
    :param compiled: Whether to construct the compiled structural backend.
    :param permuted: Whether to reverse variable ordering independently of algebraic rows.
    :return: None.
    """
    h: float = 0.1
    epsilon: float = 1e-6
    generation: int

    for generation in range(2):
        x0: Var = Var(f"mixed_{generation}_x0")
        x1: Var = Var(f"mixed_{generation}_x1")
        z0: Var = Var(f"mixed_{generation}_z0")
        z1: Var = Var(f"mixed_{generation}_z1")
        dx0: Var = Var(f"mixed_{generation}_dx0", base_var=x0)
        dx1: Var = Var(f"mixed_{generation}_dx1", base_var=x1)
        state_vars: List[Var]
        algebraic_vars: List[Var]
        diff_vars: List[Var]
        if permuted:
            state_vars = list((x1, x0))
            algebraic_vars = list((z1, z0))
            diff_vars = list((dx1, dx0))
        else:
            state_vars = list((x0, x1))
            algebraic_vars = list((z0, z1))
            diff_vars = list((dx0, dx1))
        algebraic_z0: Var
        algebraic_z1: Var
        # Persisted expressions may refer to fresh objects sharing the runtime
        # UID. Exercise that identity boundary through the actual grouped kernel.
        if generation == 1:
            algebraic_z0 = Var(z0.name, uid=z0.uid)
            algebraic_z1 = Var(z1.name, uid=z1.uid)
        else:
            algebraic_z0 = z0
            algebraic_z1 = z1
        block: Block = Block(
            name="MixedRuntimeRoles", state_vars=state_vars, algebraic_vars=algebraic_vars,
            diff_vars=diff_vars, state_eqs=list((Const(1.0), Const(1.0))),
            algebraic_eqs=list((algebraic_z0 - Const(1.0), algebraic_z1 - Const(1.0))),
            parameters=dict(),
        )
        block.unify_blocks()
        problem: GenericEmtProblem = GenericEmtProblem(
            sys_block=block, glob_time=Var(f"mixed_{generation}_time"),
            static_parameter_values_mapping=dict(),
        )
        assert problem.get_state_vars() == state_vars
        assert problem.get_algebraic_vars() == algebraic_vars
        history: np.ndarray = np.zeros(4, dtype=np.float64)
        history2: np.ndarray = np.zeros(4, dtype=np.float64)
        d_history: np.ndarray = np.zeros(4, dtype=np.float64)
        history[problem.get_var_idx(x1)] = 0.2
        history2[problem.get_var_idx(x0)] = -0.08
        history2[problem.get_var_idx(x1)] = 0.11
        d_history[problem.get_var_idx(x0)] = 1.0
        d_history[problem.get_var_idx(x1)] = 0.7
        params: np.ndarray = build_full_params(problem)
        samples: np.ndarray = np.ones((11, 4), dtype=np.float64)
        expected: np.ndarray = np.zeros_like(samples)
        expected_jacobian: np.ndarray = np.zeros((4, 4), dtype=np.float64)
        coefficient: float
        row: int
        variable: Var
        column: int

        # Solve each scalar history formula independently for the zero-residual
        # point. Algebraic rows keep their own order when variables reverse.
        for variable in state_vars:
            column = problem.get_var_idx(variable)
            if method == DynamicIntegrationMethod.DaeBackEuler:
                samples[0, column] = history[column] + h
            elif method == DynamicIntegrationMethod.DaeTrapezoidal:
                samples[0, column] = history[column] + 0.5 * h * (1.0 + d_history[column])
            else:
                samples[0, column] = (h + 2.0 * history[column] - 0.5 * history2[column]) / 1.5
        samples[1, problem.get_var_idx(x0)] = 0.15
        samples[1, problem.get_var_idx(x1)] = 0.4
        samples[1, problem.get_var_idx(z0)] = 1.25
        samples[1, problem.get_var_idx(z1)] = 0.75
        samples[2] = samples[1]
        for column in range(4):
            samples[3 + 2 * column] = samples[1]
            samples[4 + 2 * column] = samples[1]
            samples[3 + 2 * column, column] += epsilon
            samples[4 + 2 * column, column] -= epsilon

        # These analytic residuals do not call either compiler or canonicalizer.
        for row, variable in enumerate(state_vars):
            column = problem.get_var_idx(variable)
            if method == DynamicIntegrationMethod.DaeBackEuler:
                coefficient = 1.0 / h
                expected[:, row] = (samples[:, column] - history[column]) / h - 1.0
            elif method == DynamicIntegrationMethod.DaeTrapezoidal:
                coefficient = 2.0 / h
                expected[:, row] = 2.0 * (samples[:, column] - history[column]) / h - d_history[column] - 1.0
            else:
                coefficient = 1.5 / h
                expected[:, row] = (
                    1.5 * samples[:, column] - 2.0 * history[column] + 0.5 * history2[column]
                ) / h - 1.0
            expected_jacobian[row, column] = coefficient
        for row, variable in enumerate((z0, z1), start=2):
            column = problem.get_var_idx(variable)
            expected[:, row] = samples[:, column] - 1.0
            expected_jacobian[row, column] = 1.0

        solver: StructuralCompiledSolver | StructuralVectorizedSolver
        if compiled:
            solver = StructuralCompiledSolver(
                problem=problem, t0=0.0, t_end=0.2, h=h, method=method,
                verbose=False, auto_build=True,
            )
            assert solver._residual_assembler is not None
            assert len(solver._residual_assembler._kernel_specs) == 2
        else:
            solver = StructuralVectorizedSolver(
                problem=problem, t0=0.0, t_end=0.2, h=h, method=method,
                verbose=False, auto_vectorization=True,
            )
            assert len(solver.vec_kernels) == 2
            assert solver._backend_build_stats["direct_residual_mode"] == 0.0

        # Evaluate true grouped residuals including central-difference probes.
        # An AD-only comparison would miss the original shared residual defect.
        actual: np.ndarray = np.zeros_like(samples)
        sample_index: int
        sample: np.ndarray
        for sample_index, sample in enumerate(samples):
            if isinstance(solver, StructuralCompiledSolver):
                assert solver._residual_assembler is not None
                solver._residual_assembler.evaluate(
                    sample, params, history, d_history, h, history2, actual[sample_index],
                )
            else:
                solver.fused_residual.evaluate(
                    sample, params, history, d_history, h, history2, actual[sample_index],
                )
        np.testing.assert_allclose(actual, expected, rtol=0.0, atol=1e-12)
        np.testing.assert_allclose(actual[0], np.zeros(4), rtol=0.0, atol=1e-12)

        jacobian: np.ndarray
        if isinstance(solver, StructuralCompiledSolver):
            assert solver._jacobian_evaluator is not None
            jacobian = solver._jacobian_evaluator.evaluate(
                samples[1], params, history, d_history, h, history2,
            ).toarray()
        else:
            jacobian = solver.vec_jacobian(
                samples[1], params, history, d_history, h, history2,
            ).toarray()
        finite_difference: np.ndarray = np.zeros((4, 4), dtype=np.float64)
        for column in range(4):
            finite_difference[:, column] = (
                actual[3 + 2 * column] - actual[4 + 2 * column]
            ) / (2.0 * epsilon)
        np.testing.assert_allclose(jacobian, expected_jacobian, rtol=0.0, atol=1e-12)
        np.testing.assert_allclose(finite_difference, expected_jacobian, rtol=1e-7, atol=1e-7)


@pytest.mark.parametrize("method", (DynamicIntegrationMethod.DaeBackEuler,
                                   DynamicIntegrationMethod.DaeTrapezoidal,
                                   DynamicIntegrationMethod.DaeBDF2))
@pytest.mark.parametrize("compiled", (False, True))
@pytest.mark.parametrize("reverse_equations", (False, True))
@pytest.mark.parametrize("permuted", (False, True))
def test_structural_grouping_preserves_exact_constants(
        method: DynamicIntegrationMethod, compiled: bool,
        reverse_equations: bool, permuted: bool,
) -> None:
    """
    Compare grouped kernels with each row's original constant and analytic slope.

    Four nearby constants appear twice each. The next float after one must not
    use the kernel containing one, even though a tolerant comparison would pass.
    Independent equation and variable permutations exercise the gather contract.

    :param method: Existing implicit discretization of the zero-dynamics state.
    :param compiled: Whether to exercise the compiled structural backend.
    :param reverse_equations: Whether to reverse the algebraic equation rows.
    :param permuted: Whether to reverse the algebraic runtime variable vector.
    :return: None.
    """
    constants: np.ndarray = np.array(
        (1.0000001, 1.0000002, 1.0, float(np.nextafter(1.0, 2.0))), dtype=np.float64,
    )
    h: float = 0.1
    epsilon: float = 1e-6
    generation: int

    # A second, renamed construction must also remain correct with warm caches
    # and same-UID expression aliases, independently of the first template.
    for generation in range(2):
        x: Var = Var(f"exact_{generation}_x")
        dx: Var = Var(f"exact_{generation}_dx", base_var=x)
        variables: List[Var] = list(Var(f"exact_{generation}_z{i}") for i in range(8))
        ordered_variables: List[Var]
        if permuted:
            ordered_variables = list(reversed(variables))
        else:
            ordered_variables = list(variables)
        equation_order: np.ndarray = np.arange(8, dtype=np.int32)
        if reverse_equations:
            equation_order = equation_order[::-1].copy()
        else:
            pass
        equations: List[Expr] = list(Const(0.0) for _ in range(8))
        row: int
        source_index: np.int32
        variable: Var
        for row, source_index in enumerate(equation_order):
            if generation == 1:
                variable = Var(variables[source_index].name, uid=variables[source_index].uid)
            else:
                variable = variables[source_index]
            equations[row] = variable - Const(float(constants[source_index // 2]))
        block: Block = Block(
            name="ExactStructuralConstants", state_vars=list((x,)), diff_vars=list((dx,)),
            state_eqs=list((Const(0.0),)), algebraic_vars=ordered_variables,
            algebraic_eqs=equations, parameters=dict(),
        )
        block.unify_blocks()
        problem: GenericEmtProblem = GenericEmtProblem(
            sys_block=block, glob_time=Var(f"exact_{generation}_time"),
            static_parameter_values_mapping=dict(),
        )
        solver: StructuralCompiledSolver | StructuralVectorizedSolver
        if compiled:
            solver = StructuralCompiledSolver(
                problem=problem, t0=0.0, t_end=0.2, h=h, method=method,
                verbose=False, auto_build=True,
            )
        else:
            solver = StructuralVectorizedSolver(
                problem=problem, t0=0.0, t_end=0.2, h=h, method=method,
                verbose=False, auto_vectorization=True,
            )
            assert solver._backend_build_stats["direct_residual_mode"] == 0.0
        params: np.ndarray = build_full_params(problem)
        history: np.ndarray = np.zeros(9, dtype=np.float64)
        history2: np.ndarray = np.zeros(9, dtype=np.float64)
        d_history: np.ndarray = np.zeros(9, dtype=np.float64)
        state_column: int = problem.get_var_idx(x)
        history[state_column] = 0.13
        history2[state_column] = 0.08
        d_history[state_column] = 0.07
        samples: np.ndarray = np.zeros((21, 9), dtype=np.float64)
        samples[1] = np.linspace(0.3, 2.1, 9)
        samples[2] = samples[1]
        column: int
        for column in range(9):
            samples[3 + 2 * column] = samples[1]
            samples[4 + 2 * column] = samples[1]
            samples[3 + 2 * column, column] += epsilon
            samples[4 + 2 * column, column] -= epsilon
        expected: np.ndarray = np.zeros_like(samples)
        expected_jacobian: np.ndarray = np.zeros((9, 9), dtype=np.float64)
        coefficient: float

        # Compute the scalar discretization and each literal residual without
        # either canonicalizer or compiler, so shared mistakes cannot agree.
        if method == DynamicIntegrationMethod.DaeBackEuler:
            coefficient = 1.0 / h
            expected[:, 0] = (samples[:, state_column] - history[state_column]) / h
        elif method == DynamicIntegrationMethod.DaeTrapezoidal:
            coefficient = 2.0 / h
            expected[:, 0] = (
                2.0 * (samples[:, state_column] - history[state_column]) / h
                - d_history[state_column]
            )
        else:
            coefficient = 1.5 / h
            expected[:, 0] = (
                1.5 * samples[:, state_column] - 2.0 * history[state_column]
                + 0.5 * history2[state_column]
            ) / h
        expected_jacobian[0, state_column] = coefficient
        for row, source_index in enumerate(equation_order, start=1):
            column = problem.get_var_idx(variables[source_index])
            expected[:, row] = samples[:, column] - constants[source_index // 2]
            expected_jacobian[row, column] = 1.0
        actual: np.ndarray = np.zeros_like(samples)
        sample_index: int
        sample: np.ndarray
        for sample_index, sample in enumerate(samples):
            if isinstance(solver, StructuralCompiledSolver):
                assert solver._residual_assembler is not None
                solver._residual_assembler.evaluate(
                    sample, params, history, d_history, h, history2, actual[sample_index],
                )
            else:
                solver.fused_residual.evaluate(
                    sample, params, history, d_history, h, history2, actual[sample_index],
                )

        # Exact zero-input subtraction exposes even a one-ulp substitution.
        # Equal literal pairs must still batch; fixing this by disabling grouping
        # would violate the five-group invariant.
        np.testing.assert_array_equal(actual[0, 1:], expected[0, 1:])
        np.testing.assert_allclose(actual, expected, rtol=0.0, atol=1e-12)
        np.testing.assert_array_equal(actual[1], actual[2])
        jacobian: np.ndarray
        if isinstance(solver, StructuralCompiledSolver):
            assert solver._residual_assembler is not None
            assert len(solver._residual_assembler._kernel_specs) == 5
            assert solver._jacobian_evaluator is not None
            jacobian = solver._jacobian_evaluator.evaluate(
                samples[1], params, history, d_history, h, history2,
            ).toarray()
        else:
            assert len(solver.vec_kernels) == 5
            jacobian = solver.vec_jacobian(
                samples[1], params, history, d_history, h, history2,
            ).toarray()
        finite_difference: np.ndarray = np.zeros((9, 9), dtype=np.float64)
        for column in range(9):
            finite_difference[:, column] = (
                actual[3 + 2 * column] - actual[4 + 2 * column]
            ) / (2.0 * epsilon)
        np.testing.assert_allclose(jacobian, expected_jacobian, rtol=0.0, atol=1e-12)
        np.testing.assert_allclose(finite_difference, expected_jacobian, rtol=1e-7, atol=1e-7)


@pytest.mark.parametrize("compiled", (False, True))
def test_structural_signatures_preserve_binding_semantics(compiled: bool) -> None:
    """
    Check lossless tokens, occurrence bindings and unchanged default fingerprints.

    Parameters with identical names remain bound by UID. Their independent
    grouped residuals must read modified input parameters without rebuilding.
    Captured scalar and matrix fingerprint strings guard the absent-context path.

    :param compiled: Whether to use the compiled backend's keyword-compatible entry.
    :return: None.
    """
    x: Var = Var("binding_x")
    y: Var = Var("binding_y")
    dx: Var = Var("binding_dx", base_var=x)
    dy: Var = Var("binding_dy", base_var=y)
    x_alias: Var = Var(x.name, uid=x.uid)
    dx_alias: Var = Var(dx.name, uid=dx.uid, base_var=x_alias)
    k0: Var = Var("shared_parameter_name")
    k1: Var = Var("shared_parameter_name")
    k0_alias: Var = Var(k0.name, uid=k0.uid)
    runtime_uids: set[int] = set((x.uid, y.uid))
    parameter_uids: set[int] = set((k0.uid, k1.uid))
    constants: Tuple[float | int, ...] = (
        1.0000001, 1.0000002, 1.0, float(np.nextafter(1.0, 2.0)), 0.0, -0.0,
        1e-10, 1.0000001e-10, -1.0000001, -1.0000002,
        1e100, float(np.nextafter(1e100, np.inf)), 9007199254740992, 9007199254740993, 1,
    )
    literal_signatures: List[str] = list("" for _ in constants)
    index: int
    value: float | int
    gathered: List[Var]

    # Literal identity is conservative: signed zero, integer versus float and
    # large integers must not disappear through an intermediate float cast.
    for index, value in enumerate(constants):
        if compiled:
            literal_signatures[index], gathered = canonicalize_compiled_expression(
                expr=Const(value), runtime_uids=runtime_uids, parameter_uids=parameter_uids,
            )
        else:
            literal_signatures[index], gathered = canonicalize_vectorized_expression(
                expr=Const(value), runtime_uids=runtime_uids, param_uids=parameter_uids,
            )
        assert len(gathered) == 0
    assert len(set(literal_signatures)) == len(constants)

    expressions: Tuple[Expr, ...] = (
        x, dx, y, dy, dx + x, dy + y, dx_alias + x_alias,
        x + y, y + x, dx + y, x + dy, x - Const(2) * y, Const(2) * x - y,
        BinOp(x, "/", y), BinOp(x, "*", y), BinOp(x, "+", y),
        Func(UnOp("-", dx - y), "sin"), Func(UnOp("-", dy - x), "sin"),
        Func(UnOp("-", dx_alias - y), "sin"), Func(UnOp("-", x - dy), "sin"),
        UnOp("-", x), Func(x, "sin"), k0 - x, k1 - x, k0_alias - x,
        dx + dx, x + x,
    )
    signatures: List[str] = list("" for _ in expressions)
    collected: List[List[Var]] = list(list() for _ in expressions)
    expression: Expr
    for index, expression in enumerate(expressions):
        if compiled:
            signatures[index], collected[index] = canonicalize_compiled_expression(
                expr=expression, runtime_uids=runtime_uids, parameter_uids=parameter_uids,
            )
        else:
            signatures[index], collected[index] = canonicalize_vectorized_expression(
                expr=expression, runtime_uids=runtime_uids, param_uids=parameter_uids,
            )
    assert signatures[0] == signatures[2] != signatures[1]
    assert signatures[1] == signatures[3]
    assert signatures[4] == signatures[5] == signatures[6]
    assert signatures[7] == signatures[8] == signatures[15]
    assert signatures[9] != signatures[10]
    assert signatures[11] != signatures[12]
    assert len(set(signatures[13:16])) == 3
    assert signatures[16] == signatures[17] == signatures[18]
    assert signatures[16] != signatures[19]
    assert signatures[20].startswith("U[-|")
    assert signatures[21].startswith("F[sin|")
    assert signatures[22] == signatures[24] != signatures[23]
    assert signatures[25] != signatures[26]
    assert collected[7][0] is x and collected[7][1] is y
    assert collected[8][0] is y and collected[8][1] is x
    assert collected[16][0] is dx and collected[16][1] is y
    assert collected[18][0] is dx_alias and collected[18][1] is y
    assert collected[22][0] is x and len(collected[22]) == 1
    for index in (4, 5, 6, 25, 26):
        assert len(collected[index]) == 1

    # An overlapping classification retains runtime precedence. Unclassified
    # supported variables still fail before a template can enter a group.
    overlapping_signature: str
    overlapping_vars: List[Var]
    if compiled:
        overlapping_signature, overlapping_vars = canonicalize_compiled_expression(
            expr=x, runtime_uids=runtime_uids, parameter_uids=set((x.uid,)),
        )
    else:
        overlapping_signature, overlapping_vars = canonicalize_vectorized_expression(
            expr=x, runtime_uids=runtime_uids, param_uids=set((x.uid,)),
        )
    assert overlapping_signature == signatures[0]
    assert len(overlapping_vars) == 1 and overlapping_vars[0] is x
    unknown: Var = Var("unclassified_binding")
    with pytest.raises(RuntimeError):
        if compiled:
            canonicalize_compiled_expression(unknown, runtime_uids, parameter_uids)
        else:
            canonicalize_vectorized_expression(unknown, runtime_uids, parameter_uids)

    # These golden strings were captured before the refactor from all three
    # default cache contexts, including a derivative beneath a unary function.
    default_expressions: Tuple[Expr, ...] = (
        Const(1.0000000000000002), Const(-0.0), Const(9007199254740993), x - k0, y - x,
        UnOp("-", Func(dx + x, "sin")), dx * x,
    )
    contexts: Tuple[Tuple[Dict[int, int] | None, Dict[int, int] | None], ...] = (
        (None, None), (None, dict(((x.uid, 1),))), (dict(((x.uid, 0), (y.uid, 1))), None),
    )
    expected_fingerprints: Tuple[Tuple[str, ...], ...] = (
        ("C[1.0000000000000002]", "C[-0.0]", "C[9007199254740993]", "B[-|S0|P0]",
         "B[-|S1|S0]", "U[-|F[sin|B[+|D[Trapezoidal|S0|H0]|S0]]]",
         "B[*|D[Trapezoidal|S0|H0]|S0]"),
        ("C[1.0000000000000002]", "C[-0.0]", "C[9007199254740993]", "B[-|S0|P0]",
         "B[-|S1|S0]", "U[-|F[sin|B[+|D[Trapezoidal|S0|H1]|S0]]]",
         "B[*|D[Trapezoidal|S0|H1]|S0]"),
        ("C[1.0000000000000002]", "C[-0.0]", "C[9007199254740993]", "B[-|M0|P0]",
         "B[-|M1|M0]", "U[-|F[sin|B[+|D[Trapezoidal|M0]|M0]]]",
         "B[*|D[Trapezoidal|M0]|M0]"),
    )
    var_map: Dict[int, int] = dict(((x.uid, 0), (y.uid, 1)))
    param_map: Dict[int, int] = dict(((k0.uid, 0),))
    context_index: int
    col_map: Dict[int, int] | None
    diff_map: Dict[int, int] | None
    for context_index, (col_map, diff_map) in enumerate(contexts):
        for index, expression in enumerate(default_expressions):
            assert _fingerprint_codegen_expr(
                expression, var_map, param_map, "Trapezoidal", col_map, diff_map,
            ) == expected_fingerprints[context_index][index]

    # Same-named global parameters must retain separate concrete vector entries,
    # even when their initial values coincide and runtime rows are renamed.
    generation: int
    for generation in range(2):
        state: Var = Var(f"parameter_{generation}_state")
        derivative: Var = Var(f"parameter_{generation}_derivative", base_var=state)
        variables: List[Var] = list(Var(f"parameter_{generation}_z{i}") for i in range(4))
        p0: Var = Var("same_parameter_name")
        p1: Var = Var("same_parameter_name")
        block: Block = Block(
            name="ParameterBindingGroups", state_vars=list((state,)),
            diff_vars=list((derivative,)), state_eqs=list((Const(0.0),)),
            algebraic_vars=list(reversed(variables)),
            algebraic_eqs=list((variables[0] - p0, variables[1] - p0,
                               variables[2] - p1, variables[3] - p1)),
            parameters=dict(((p0, Const(1.0)), (p1, Const(1.0)))),
        )
        block.unify_blocks()
        problem: GenericEmtProblem = GenericEmtProblem(
            sys_block=block, glob_time=Var(f"parameter_{generation}_time"),
            static_parameter_values_mapping=dict(),
        )
        solver: StructuralCompiledSolver | StructuralVectorizedSolver
        if compiled:
            solver = StructuralCompiledSolver(
                problem=problem, t0=0.0, t_end=0.2, h=0.1,
                method=DynamicIntegrationMethod.DaeBackEuler, verbose=False, auto_build=True,
            )
            assert solver._residual_assembler is not None
            assert len(solver._residual_assembler._kernel_specs) == 3
        else:
            solver = StructuralVectorizedSolver(
                problem=problem, t0=0.0, t_end=0.2, h=0.1,
                method=DynamicIntegrationMethod.DaeBackEuler, verbose=False, auto_vectorization=True,
            )
            assert solver._backend_build_stats["direct_residual_mode"] == 0.0
            assert len(solver.vec_kernels) == 3
        params: np.ndarray = build_full_params(problem)
        p0_column: int = problem.get_variable_parameter_number() + problem.get_constant_parameters().index(p0)
        p1_column: int = problem.get_variable_parameter_number() + problem.get_constant_parameters().index(p1)
        assert p0_column != p1_column
        sample: np.ndarray = np.zeros(5, dtype=np.float64)
        history: np.ndarray = np.zeros(5, dtype=np.float64)
        row: int
        variable: Var
        for row, variable in enumerate(variables):
            sample[problem.get_var_idx(variable)] = 0.25 * (row + 1)
        actual: np.ndarray = np.zeros(5, dtype=np.float64)
        expected: np.ndarray = np.zeros(5, dtype=np.float64)
        p0_value: float
        p1_value: float
        for p0_value, p1_value in ((1.0, 1.0), (2.0, 7.0), (-4.0, 0.25), (1.0, 1.0)):
            params[p0_column] = p0_value
            params[p1_column] = p1_value
            for row, variable in enumerate(variables, start=1):
                if row <= 2:
                    expected[row] = sample[problem.get_var_idx(variable)] - p0_value
                else:
                    expected[row] = sample[problem.get_var_idx(variable)] - p1_value
            if isinstance(solver, StructuralCompiledSolver):
                assert solver._residual_assembler is not None
                solver._residual_assembler.evaluate(sample, params, history, history, 0.1, history, actual)
            else:
                solver.fused_residual.evaluate(sample, params, history, history, 0.1, history, actual)
            np.testing.assert_array_equal(actual, expected)


def test_eager_compiler_smoke_for_residual_ad_and_matrix_kernels() -> None:
    """
    Test EagerEquationCompiler produces correct residual, AD, and matrix kernels.

    Verifies that:
    - Residual kernel: dx/dt + k*x with BackEuler gives correct residual
    - AD kernel: produces correct Jacobian-vector product
    - Matrix kernel: produces correct grouped outputs
    """
    x: Var = Var("x")
    dx: Var = Var("d_x", base_var=x)
    k: Var = Var("k")
    eq: Expr = dx + k * x

    compiler: EagerEquationCompiler = EagerEquationCompiler(
        variables=[x],
        parameters=[k],
        method=DynamicIntegrationMethod.DaeBackEuler,
    )

    states: np.ndarray = np.array([2.0], dtype=np.float64)
    params: np.ndarray = np.array([3.0], dtype=np.float64)
    history: np.ndarray = np.array([1.0], dtype=np.float64)
    d_history: np.ndarray = np.zeros(1, dtype=np.float64)
    history2: np.ndarray = history.copy()

    py_res, sig_res = compiler.compile(
        equations=[eq],
        func_name="unit_test_compiled_eager_residual",
        use_cse=True,
        offset=0,
        inplace=True,
    )
    res_fn = nb.njit(sig_res, cache=False, fastmath=True)(py_res)
    residual_out: np.ndarray = np.zeros(1, dtype=np.float64)
    res_fn(states, params, history, d_history, 0.5, residual_out, history2)

    assert abs(float(residual_out[0]) - 8.0) < 1e-11

    py_ad, sig_ad = compiler.compile_ad_kernel(
        equations=[eq],
        func_name="unit_test_compiled_eager_ad",
        use_cse=True,
        active_indices={0},
    )
    ad_fn = nb.njit(sig_ad, cache=False, fastmath=True)(py_ad)
    jvp_out: np.ndarray = np.zeros(1, dtype=np.float64)
    seeds: np.ndarray = np.zeros(1, dtype=np.float64)
    ad_fn(states, seeds, params, history, d_history, 0.5, jvp_out, history2)

    assert abs(float(jvp_out[0]) - 5.0) < 1e-11

    py_mat, sig_mat = compiler.compile_matrix_kernel(
        template_eq=eq,
        func_name="unit_test_compiled_eager_matrix",
        template_vars=[x],
    )
    mat_fn = nb.njit(sig_mat, cache=False, fastmath=True)(py_mat)

    grouped_states: np.ndarray = np.array([2.0, 4.0], dtype=np.float64)
    grouped_history: np.ndarray = np.array([1.0, 3.0], dtype=np.float64)
    grouped_d_history: np.ndarray = np.zeros(2, dtype=np.float64)
    grouped_history2: np.ndarray = grouped_history.copy()
    grouped_indices: np.ndarray = np.array([[0], [1]], dtype=np.int32)
    grouped_out: np.ndarray = np.zeros(2, dtype=np.float64)

    mat_fn(
        grouped_states,
        params,
        grouped_history,
        grouped_d_history,
        0.5,
        grouped_indices,
        grouped_out,
        grouped_history2,
    )

    np.testing.assert_allclose(
        grouped_out,
        np.array([8.0, 14.0], dtype=np.float64),
        rtol=0.0,
        atol=1e-12,
    )


def test_structural_compiled_backend_builds_and_collapses_repeated_structure() -> None:
    """
    Test StructuralCompiledSolver collapses repeated structure into single kernel.

    Verifies that 4 identical decay equations with same k produce
    exactly 1 kernel spec (not 4 separate kernels).
    """
    block, _ = build_repeated_decay_block(n_states=4, k_val=2.0)
    static_parameter_values_mapping: Dict[Var, Const] = dict(block.parameters)
    problem: GenericEmtProblem = GenericEmtProblem(
        sys_block=block,
        glob_time=Var("t_glob"),
        static_parameter_values_mapping=static_parameter_values_mapping,
    )

    solver: StructuralCompiledSolver = StructuralCompiledSolver(
        problem=problem,
        t0=0.0,
        t_end=1e-3,
        h=1e-4,
        method=DynamicIntegrationMethod.DaeBackEuler,
        dense_threshold=100,
        verbose=False,
        auto_build=True,
    )

    assert solver.is_vectorized_ready() is True
    assert solver._residual_assembler is not None
    assert solver._jacobian_evaluator is not None
    assert len(solver._residual_assembler._kernel_specs) == 1
    assert solver.get_residual_buffer().shape == (4,)
    assert solver.get_jacobian_data_buffer().size > 0
    assert np.shares_memory(
        solver.get_jacobian_data_buffer(),
        solver._jacobian_evaluator.get_data_buffer(),
    )
    assert solver._residual_assembler.get_work_buffer().shape[0] == 1


def test_structural_compiled_residual_and_jacobian_buffers_are_reused_in_place() -> None:
    """
    Test that residual and Jacobian buffers are reused across evaluations.

    Verifies that calling evaluate() twice produces the same buffer
    memory locations (no reallocation).
    """
    block, _ = build_repeated_decay_block(n_states=3, k_val=2.0)
    static_parameter_values_mapping: Dict[Var, Const] = dict(block.parameters)
    problem: GenericEmtProblem = GenericEmtProblem(
        sys_block=block,
        glob_time=Var("t_glob"),
        static_parameter_values_mapping=static_parameter_values_mapping,
    )

    solver: StructuralCompiledSolver = StructuralCompiledSolver(
        problem=problem,
        t0=0.0,
        t_end=1e-3,
        h=1e-4,
        method=DynamicIntegrationMethod.DaeBackEuler,
        dense_threshold=100,
        verbose=False,
        auto_build=True,
    )

    full_params: np.ndarray = build_full_params(problem)
    x: np.ndarray = np.array([1.0, -0.5, 2.0], dtype=np.float64)
    dx: np.ndarray = np.zeros_like(x)
    history2: np.ndarray = x.copy()

    residual_ptr_before: int = array_ptr(solver.get_residual_buffer())
    work_ptr_before: int = array_ptr(solver._residual_assembler.get_work_buffer())
    jac_data_ptr_before: int = array_ptr(solver.get_jacobian_data_buffer())

    solver._residual_assembler.evaluate(
        x,
        full_params,
        x,
        dx,
        1e-4,
        history2,
        solver.get_residual_buffer(),
    )
    jacobian_1: csc_matrix = solver._jacobian_evaluator.evaluate(
        x,
        full_params,
        x,
        dx,
        1e-4,
        history2,
    )

    x_2: np.ndarray = np.array([0.75, -0.25, 1.5], dtype=np.float64)
    history2_2: np.ndarray = x_2.copy()

    solver._residual_assembler.evaluate(
        x_2,
        full_params,
        x_2,
        dx,
        1e-4,
        history2_2,
        solver.get_residual_buffer(),
    )
    jacobian_2: csc_matrix = solver._jacobian_evaluator.evaluate(
        x_2,
        full_params,
        x_2,
        dx,
        1e-4,
        history2_2,
    )

    assert array_ptr(solver.get_residual_buffer()) == residual_ptr_before
    assert array_ptr(solver._residual_assembler.get_work_buffer()) == work_ptr_before
    assert array_ptr(solver.get_jacobian_data_buffer()) == jac_data_ptr_before
    assert jacobian_1 is jacobian_2
    assert np.all(np.isfinite(solver.get_residual_buffer()))
    assert np.all(np.isfinite(jacobian_2.data))


def test_structural_compiled_jacobian_matches_structural_vectorized_backend_and_csc_layout() -> None:
    """
    Test that compiled and vectorized Jacobians match numerically and structurally.

    Verifies:
    - Same sparse matrix shape
    - Same CSC indptr and indices arrays
    - Same data values within tolerance
    """
    block_fast, _ = build_repeated_decay_block(n_states=4, k_val=2.0)
    block_base, _ = build_repeated_decay_block(n_states=4, k_val=2.0)

    static_parameter_values_mapping: Dict[Var, Const] = dict(block_fast.parameters)
    problem_fast: GenericEmtProblem = GenericEmtProblem(
        sys_block=block_fast,
        glob_time=Var("t_fast"),
        static_parameter_values_mapping=static_parameter_values_mapping,
    )
    static_parameter_values_mapping = dict(block_base.parameters)
    problem_base: GenericEmtProblem = GenericEmtProblem(
        sys_block=block_base,
        glob_time=Var("t_base"),
        static_parameter_values_mapping=static_parameter_values_mapping,
    )

    compiled_solver: StructuralCompiledSolver = StructuralCompiledSolver(
        problem=problem_fast,
        t0=0.0,
        t_end=1e-3,
        h=1e-4,
        method=DynamicIntegrationMethod.DaeBackEuler,
        dense_threshold=100,
        verbose=False,
        auto_build=True,
    )
    base_solver: StructuralVectorizedSolver = StructuralVectorizedSolver(
        problem=problem_base,
        t0=0.0,
        t_end=1e-3,
        h=1e-4,
        method=DynamicIntegrationMethod.DaeBackEuler,
        dense_threshold=100,
        verbose=False,
        auto_vectorization=True,
    )

    x: np.ndarray = np.array([1.0, -0.5, 2.0, 0.25], dtype=np.float64)
    dx: np.ndarray = np.zeros_like(x)
    full_params_fast: np.ndarray = build_full_params(problem_fast)
    full_params_base: np.ndarray = build_full_params(problem_base)
    history2: np.ndarray = x.copy()

    j_compiled: csc_matrix = compiled_solver._jacobian_evaluator.evaluate(
        x,
        full_params_fast,
        x,
        dx,
        1e-4,
        history2,
    )
    j_base: csc_matrix = base_solver.vec_jacobian(
        states=x,
        params=full_params_base,
        history=x,
        d_history=dx,
        h=1e-4,
        history2=history2,
    )

    assert j_compiled.shape == j_base.shape
    assert np.array_equal(j_compiled.indptr, j_base.indptr)
    assert np.array_equal(j_compiled.indices, j_base.indices)
    np.testing.assert_allclose(j_compiled.data, j_base.data, rtol=1e-11, atol=1e-12)


def test_structural_compiled_simulation_matches_structural_vectorized_solver() -> None:
    """
    Test that compiled and vectorized solvers produce identical trajectories.

    Verifies:
    - Same time array exactly
    - Same state trajectories within tight tolerance
    - Same derivative trajectories within tight tolerance
    """
    block_fast, _ = build_repeated_decay_block(n_states=3, k_val=1.5)
    block_base, _ = build_repeated_decay_block(n_states=3, k_val=1.5)

    static_parameter_values_mapping: Dict[Var, Const] = dict(block_fast.parameters)
    problem_fast: GenericEmtProblem = GenericEmtProblem(
        sys_block=block_fast,
        glob_time=Var("t_fast"),
        static_parameter_values_mapping=static_parameter_values_mapping,
    )
    static_parameter_values_mapping = dict(block_base.parameters)
    problem_base: GenericEmtProblem = GenericEmtProblem(
        sys_block=block_base,
        glob_time=Var("t_base"),
        static_parameter_values_mapping=static_parameter_values_mapping,
    )

    x0: np.ndarray = np.array([1.0, -0.5, 2.0], dtype=np.float64)
    dx0: np.ndarray = -1.5 * x0
    p0_fast: np.ndarray = np.zeros(problem_fast.get_variable_parameter_number(), dtype=np.float64)
    p0_base: np.ndarray = np.zeros(problem_base.get_variable_parameter_number(), dtype=np.float64)

    compiled_solver: StructuralCompiledSolver = StructuralCompiledSolver(
        problem=problem_fast,
        t0=0.0,
        t_end=0.2,
        h=0.01,
        method=DynamicIntegrationMethod.DaeTrapezoidal,
        pred_method=DynamicIntegrationMethod.OdeEuler,
        dense_threshold=100,
        verbose=False,
        auto_build=True,
    )
    base_solver: StructuralVectorizedSolver = StructuralVectorizedSolver(
        problem=problem_base,
        t0=0.0,
        t_end=0.2,
        h=0.01,
        method=DynamicIntegrationMethod.DaeTrapezoidal,
        pred_method=DynamicIntegrationMethod.OdeEuler,
        dense_threshold=100,
        verbose=False,
        auto_vectorization=True,
    )

    t_compiled, y_compiled, dy_compiled, _, _ = compiled_solver.simulate(x0=x0, dx0=dx0, params0=p0_fast)
    t_base, y_base, dy_base, _, _ = base_solver.simulate(x0=x0.copy(), dx0=dx0.copy(), params0=p0_base)

    np.testing.assert_allclose(t_compiled, t_base, rtol=0.0, atol=0.0)
    np.testing.assert_allclose(y_compiled, y_base, rtol=1e-9, atol=1e-10)
    np.testing.assert_allclose(dy_compiled, dy_base, rtol=1e-9, atol=1e-10)
    assert compiled_solver.get_last_sim_loop_time() > 0.0


def test_structural_compiled_solver_uses_forced_alignment_and_boundary_updates() -> None:
    """
    Test that boundary updater alignment works correctly.

    Verifies:
    - Time steps align to forced event times
    - State remains constant (zero dynamics)
    - All forced events are captured
    """
    block: Block = build_zero_dynamics_block()
    static_parameter_values_mapping: Dict[Var, Const] = dict(block.parameters)
    problem: GenericEmtProblem = GenericEmtProblem(
        sys_block=block,
        glob_time=Var("t_glob"),
        static_parameter_values_mapping=static_parameter_values_mapping,
    )

    solver: StructuralCompiledSolver = StructuralCompiledSolver(
        problem=problem,
        t0=0.0,
        t_end=0.2,
        h=0.1,
        method=DynamicIntegrationMethod.DaeBackEuler,
        dense_threshold=100,
        verbose=False,
        auto_build=True,
    )

    updater: ForcedEventTracker = ForcedEventTracker(forced_times=[0.05, 0.15])

    x0: np.ndarray = np.array([1.234], dtype=np.float64)
    dx0: np.ndarray = np.array([0.0], dtype=np.float64)
    p0: np.ndarray = np.zeros(problem.get_variable_parameter_number(), dtype=np.float64)

    t, y, dy, _, _ = solver.simulate(
        x0=x0,
        dx0=dx0,
        params0=p0,
        boundary_updater=updater,
    )

    np.testing.assert_allclose(t, np.array([0.0, 0.1, 0.2], dtype=np.float64), rtol=0.0, atol=0.0)
    np.testing.assert_allclose(y[:, 0], np.array([1.234, 1.234, 1.234], dtype=np.float64), rtol=0.0, atol=1e-12)
    np.testing.assert_allclose(dy[:, 0], np.array([0.0, 0.0, 0.0], dtype=np.float64), rtol=0.0, atol=1e-12)

    assert len(updater.query_calls) >= 4
    np.testing.assert_allclose(
        np.array(updater.update_calls, dtype=np.float64),
        np.array([0.0, 0.05, 0.10, 0.15, 0.20], dtype=np.float64),
        rtol=0.0,
        atol=1e-12,
    )

    rounded_updates: List[float] = [round(v, 8) for v in updater.update_calls]
    np.testing.assert_allclose(
        np.array(updater.update_parameter_values, dtype=np.float64),
        np.array([0.00, 0.00, 0.05, 0.10, 0.15], dtype=np.float64),
        rtol=0.0,
        atol=1e-12,
    )
    assert 0.05 in rounded_updates
    assert 0.15 in rounded_updates
    np.testing.assert_allclose(
        np.array(updater.commit_calls, dtype=np.float64),
        np.array([0.05, 0.10, 0.15, 0.20], dtype=np.float64),
        rtol=0.0,
        atol=1e-12,
    )


def test_structural_solvers_record_newton_trace_data() -> None:
    """
    Test that NewtonTraceCollector records diagnostic data during simulation.

    Verifies:
    - Records are populated during solve
    - Each record contains solver identifier
    - Each record contains residual norm
    """
    for solver_class in (StructuralVectorizedSolver, StructuralCompiledSolver):
        block, _ = build_repeated_decay_block(n_states=2, k_val=1.5)
        static_parameter_values_mapping: Dict[Var, Const] = dict(block.parameters)
        problem: GenericEmtProblem = GenericEmtProblem(
            sys_block=block,
            glob_time=Var(f"t_{solver_class.__name__}"),
            static_parameter_values_mapping=static_parameter_values_mapping,
        )
        collector: NewtonTraceCollector = NewtonTraceCollector()
        problem.set_newton_trace_collector(collector)

        solver: Any = solver_class(
            problem=problem,
            t0=0.0,
            t_end=0.05,
            h=0.01,
            method=DynamicIntegrationMethod.DaeTrapezoidal,
            pred_method=DynamicIntegrationMethod.OdeEuler,
            dense_threshold=100,
            verbose=False,
        )

        x0: np.ndarray = np.array([1.0, 0.5], dtype=np.float64)
        dx0: np.ndarray = -1.5 * x0
        p0: np.ndarray = np.zeros(problem.get_variable_parameter_number(), dtype=np.float64)

        solver.simulate(x0=x0, dx0=dx0, params0=p0)

        assert len(collector.records) > 0
        assert "solver" in collector.records[0]
        assert "res_norm_inf" in collector.records[0]


def test_runtime_index1_check_detects_singular_algebraic_block() -> None:
    """
    Test that maybe_check_index1 raises RuntimeError for singular Jacobian.

    A 2x2 matrix with second row being all zeros is rank-deficient
    and should trigger the index-1 check.
    """
    jacobian: np.ndarray = np.array(
        [
            [1.0, 0.0],
            [0.0, 0.0],
        ],
        dtype=np.float64,
    )
    config: NewtonDiagnosticsConfig = NewtonDiagnosticsConfig(
        enable_index1_check=True,
        index1_max_block_n=10,
        enable_fallback=False,
        compute_dense_cond=False,
    )

    try:
        maybe_check_index1(jacobian, n_state=1, config=config)
        assert False, "Expected RuntimeError to be raised"
    except RuntimeError:
        pass


def test_backtracking_helper_reduces_step_when_full_newton_worsens_residual() -> None:
    """
    Test that backtracking reduces step magnitude when full Newton diverges.

    Starting from x_iter=0 with delta=10, backtracking should move
    x_iter toward 1 (where residual is 0).
    """
    x_iter: np.ndarray = np.array([0.0], dtype=np.float64)
    delta: np.ndarray = np.array([10.0], dtype=np.float64)
    trial_x: np.ndarray = np.zeros(1, dtype=np.float64)
    trial_res: np.ndarray = np.zeros(1, dtype=np.float64)
    config: NewtonDiagnosticsConfig = NewtonDiagnosticsConfig(
        enable_backtracking=True,
        backtracking_beta=0.5,
        backtracking_min_alpha=1.0e-3,
        backtracking_max_iter=6,
        enable_fallback=False,
        compute_dense_cond=False,
    )

    def evaluate_residual(candidate_x: np.ndarray, out_res: np.ndarray) -> float:
        out_res[0] = (candidate_x[0] - 1.0) ** 2
        return float(abs(out_res[0]))

    maybe_apply_backtracking(
        x_iter,
        delta,
        res_norm=1.0,
        trial_x=trial_x,
        trial_res=trial_res,
        evaluate_residual=evaluate_residual,
        config=config,
    )

    assert abs(x_iter[0] - 1.0) < abs(10.0 - 1.0)
    assert (x_iter[0] - 1.0) ** 2 < 1.0


def test_backtracking_improves_convergence_in_difficult_solve() -> None:
    """
    Test that backtracking produces better convergence in difficult solves.

    For the same difficult problem, the solver WITH backtracking
    should achieve lower residual than WITHOUT backtracking.

    The deliberately inexact Jacobian needs a larger test-only success budget.
    A rejected solve must expose its initial sample instead of a failed iterate.

    :return: None.
    """
    solver_name: str
    solver_class: type[StructuralVectorizedSolver] | type[StructuralCompiledSolver]
    solver_plain: StructuralVectorizedSolver | StructuralCompiledSolver
    solver_bt: StructuralVectorizedSolver | StructuralCompiledSolver
    for solver_name, solver_class in (("StructuralVectorized", StructuralVectorizedSolver), ("StructuralCompiled", StructuralCompiledSolver)):
        cfg_bt: NewtonDiagnosticsConfig = NewtonDiagnosticsConfig(
            enable_backtracking=True,
            backtracking_beta=0.5,
            backtracking_min_alpha=1e-3,
            backtracking_max_iter=8,
            compute_dense_cond=False,
            enable_fallback=False,
        )

        if solver_class is StructuralVectorizedSolver:
            static_parameter_values_mapping: Dict[Var, Const] = dict()
            solver_plain = solver_class(
                problem=GenericEmtProblem(
                    sys_block=build_scalar_state_block(),
                    glob_time=Var(f"t_bt_{solver_name}_plain"),
                    static_parameter_values_mapping=static_parameter_values_mapping,
                ),
                t0=0.0,
                t_end=0.1,
                h=0.1,
                method=DynamicIntegrationMethod.DaeBackEuler,
                dense_threshold=100,
                verbose=False,
                auto_vectorization=False,
                newton_diag_config=NewtonDiagnosticsConfig(enable_backtracking=False),
            )
            solver_plain.vectorized_ready = True
            solver_plain.vec_flat_args = np.zeros(0, dtype=np.float64)
            solver_plain.fused_residual = inexact_vectorized_residual
            solver_plain.vec_jacobian = InexactVectorizedJacobian()

            solver_bt = solver_class(
                problem=GenericEmtProblem(
                    sys_block=build_scalar_state_block(),
                    glob_time=Var(f"t_bt_{solver_name}_bt"),
                    static_parameter_values_mapping=static_parameter_values_mapping,
                ),
                t0=0.0,
                t_end=0.1,
                h=0.1,
                method=DynamicIntegrationMethod.DaeBackEuler,
                dense_threshold=100,
                verbose=False,
                auto_vectorization=False,
                newton_max_iter=100,
                newton_diag_config=cfg_bt,
            )
            solver_bt.vectorized_ready = True
            solver_bt.vec_flat_args = np.zeros(0, dtype=np.float64)
            solver_bt.fused_residual = inexact_vectorized_residual
            solver_bt.vec_jacobian = InexactVectorizedJacobian()
        else:
            static_parameter_values_mapping: Dict[Var, Const] = dict()
            solver_plain = solver_class(
                problem=GenericEmtProblem(
                    sys_block=build_scalar_state_block(),
                    glob_time=Var(f"t_bt_{solver_name}_plain"),
                    static_parameter_values_mapping=static_parameter_values_mapping,
                ),
                t0=0.0,
                t_end=0.1,
                h=0.1,
                method=DynamicIntegrationMethod.DaeBackEuler,
                dense_threshold=100,
                verbose=False,
                auto_build=False,
                newton_diag_config=NewtonDiagnosticsConfig(enable_backtracking=False),
            )
            solver_plain._vectorized_ready = True
            solver_plain._residual_assembler = cast(Any, InexactCompiledResidualAssembler())
            solver_plain._jacobian_evaluator = cast(Any, InexactCompiledJacobian())

            solver_bt = solver_class(
                problem=GenericEmtProblem(
                    sys_block=build_scalar_state_block(),
                    glob_time=Var(f"t_bt_{solver_name}_bt"),
                    static_parameter_values_mapping=static_parameter_values_mapping,
                ),
                t0=0.0,
                t_end=0.1,
                h=0.1,
                method=DynamicIntegrationMethod.DaeBackEuler,
                dense_threshold=100,
                verbose=False,
                auto_build=False,
                newton_max_iter=100,
                newton_diag_config=cfg_bt,
            )
            solver_bt._vectorized_ready = True
            solver_bt._residual_assembler = cast(Any, InexactCompiledResidualAssembler())
            solver_bt._jacobian_evaluator = cast(Any, InexactCompiledJacobian())

        t_plain: np.ndarray
        y_plain: np.ndarray
        dy_plain: np.ndarray
        well_plain: bool
        converged_plain: bool
        t_plain, y_plain, dy_plain, well_plain, converged_plain = solver_plain.simulate(
            x0=np.array([0.1], dtype=np.float64),
            dx0=np.array([0.0], dtype=np.float64),
            params0=np.zeros(0, dtype=np.float64),
        )
        t_bt: np.ndarray
        y_bt: np.ndarray
        dy_bt: np.ndarray
        well_bt: bool
        converged_bt: bool
        t_bt, y_bt, dy_bt, well_bt, converged_bt = solver_bt.simulate(
            x0=np.array([0.1], dtype=np.float64),
            dx0=np.array([0.0], dtype=np.float64),
            params0=np.zeros(0, dtype=np.float64),
        )

        res_plain: float = abs(float(y_plain[-1, 0] ** 2 - 1.0))
        res_bt: float = abs(float(y_bt[-1, 0] ** 2 - 1.0))

        # Compare available accepted output only after verifying both solver statuses.
        assert not converged_plain
        assert not well_plain
        assert t_plain.shape == (1,)
        assert y_plain.shape == dy_plain.shape == (1, 1)
        np.testing.assert_array_equal(y_plain, np.array([[0.1]]))
        np.testing.assert_array_equal(dy_plain, np.zeros((1, 1)))
        assert converged_bt
        assert well_bt
        assert t_bt.shape == (2,)
        assert y_bt.shape == dy_bt.shape == (2, 1)
        np.testing.assert_allclose(t_bt, (0.0, 0.1), rtol=0, atol=1e-12)
        assert res_bt < 1e-6
        assert res_bt < res_plain, f"{solver_name}: Backtracking residual {res_bt} should be less than plain residual {res_plain}"


def test_index1_guard_triggers_runtime_error_during_simulation() -> None:
    """
    Test that index-1 guard raises RuntimeError during actual solver simulation.

    This tests the full guard integration through solver.simulate(),
    not just the maybe_check_index1 function in isolation.

    This is the test from demo_structural_newton_runtime_guards.py Demo 3.
    """
    for solver_name, solver_class in (("StructuralVectorized", StructuralVectorizedSolver), ("StructuralCompiled", StructuralCompiledSolver)):
        cfg_idx: NewtonDiagnosticsConfig = NewtonDiagnosticsConfig(
            enable_index1_check=True,
            index1_max_block_n=8,
            compute_dense_cond=False,
            enable_fallback=False,
        )

        if solver_class is StructuralVectorizedSolver:
            static_parameter_values_mapping: Dict[Var, Const] = dict()
            solver = solver_class(
                problem=GenericEmtProblem(
                    sys_block=build_singular_dae_block(),
                    glob_time=Var(f"t_idx_{solver_name}"),
                    static_parameter_values_mapping=static_parameter_values_mapping,
                ),
                t0=0.0,
                t_end=0.1,
                h=0.1,
                method=DynamicIntegrationMethod.DaeBackEuler,
                dense_threshold=0,
                verbose=False,
                auto_vectorization=False,
                newton_diag_config=cfg_idx,
            )
            solver.vectorized_ready = True
            solver.vec_flat_args = np.zeros(0, dtype=np.float64)
            solver.fused_residual = singular_vectorized_residual
            solver.vec_jacobian = SingularVectorizedJacobian()
        else:
            static_parameter_values_mapping: Dict[Var, Const] = dict()
            solver = solver_class(
                problem=GenericEmtProblem(
                    sys_block=build_singular_dae_block(),
                    glob_time=Var(f"t_idx_{solver_name}"),
                    static_parameter_values_mapping=static_parameter_values_mapping,
                ),
                t0=0.0,
                t_end=0.1,
                h=0.1,
                method=DynamicIntegrationMethod.DaeBackEuler,
                dense_threshold=0,
                verbose=False,
                auto_build=False,
                newton_diag_config=cfg_idx,
            )
            solver._vectorized_ready = True
            solver._residual_assembler = cast(Any, SingularCompiledResidualAssembler())
            solver._jacobian_evaluator = cast(Any, SingularCompiledJacobian())

        try:
            solver.simulate(
                x0=np.array([0.0, 0.0], dtype=np.float64),
                dx0=np.array([0.0], dtype=np.float64),
                params0=np.zeros(0, dtype=np.float64),
            )
            assert False, f"{solver_name}: Expected RuntimeError to be raised for singular DAE"
        except RuntimeError:
            pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
