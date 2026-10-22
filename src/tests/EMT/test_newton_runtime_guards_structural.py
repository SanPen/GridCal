# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can see it at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Any, Dict, cast

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
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.Simulations.EMT.solvers.StructuralVectorizedSolver import StructuralVectorizedSolver
from VeraGridEngine.Simulations.EMT.solvers.structural_compiled_solver import StructuralCompiledSolver
from VeraGridEngine.enumerations import DynamicIntegrationMethod


class GenericEmtProblem(EmtProblemTemplate):
    __slots__ = list()


def build_decay_block(n_states: int = 2, k_val: float = 1.5) -> Block:
    k = Var("k")
    state_vars = []
    diff_vars = []
    state_eqs = []

    for i in range(n_states):
        x_i = Var(f"x_{i}")
        dx_i = Var(f"d_x_{i}", base_var=x_i)
        state_vars.append(x_i)
        diff_vars.append(dx_i)
        state_eqs.append(-k * x_i)

    block = Block(
        name="DecayBlock",
        state_vars=state_vars,
        diff_vars=diff_vars,
        state_eqs=state_eqs,
        parameters={k: Const(k_val)},
    )
    block.unify_blocks()
    return block


def build_scalar_state_block() -> Block:
    x = Var("x")
    dx = Var("d_x", base_var=x)
    block = Block(
        name="ScalarState",
        state_vars=[x],
        diff_vars=[dx],
        state_eqs=[Const(0.0)],
        parameters=dict(),
    )
    block.unify_blocks()
    return block


def build_singular_dae_block() -> Block:
    x = Var("x")
    y = Var("y")
    dx = Var("d_x", base_var=x)
    block = Block(
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


class InexactCompiledResidualAssembler:
    __slots__ = ["_tag"]

    def __init__(self) -> None:
        self._tag = "compiled_inexact_residual"

    def evaluate(
        self,
        states: np.ndarray,
        params: np.ndarray,
        history: np.ndarray,
        d_history: np.ndarray,
        h: float,
        history2: np.ndarray,
        data_out: np.ndarray,
    ) -> None:
        _unused = (self._tag, params, history, d_history, h, history2)
        data_out[:] = 0.0
        data_out[0] = states[0] ** 2 - 1.0


class InexactCompiledJacobian:
    __slots__ = ["_tag"]

    def __init__(self) -> None:
        self._tag = "compiled_inexact_jacobian"

    def evaluate(
        self,
        states: np.ndarray,
        params: np.ndarray,
        history: np.ndarray,
        d_history: np.ndarray,
        h: float,
        history2: np.ndarray,
    ) -> csc_matrix:
        _unused = (self._tag, params, history, d_history, h, history2)
        return csc_matrix([[0.2 * states[0]]], dtype=np.float64)

    def get_data_buffer(self) -> np.ndarray:
        _unused = self._tag
        return np.zeros(1, dtype=np.float64)


class SingularCompiledResidualAssembler:
    __slots__ = ["_tag"]

    def __init__(self) -> None:
        self._tag = "compiled_singular_residual"

    def evaluate(
        self,
        states: np.ndarray,
        params: np.ndarray,
        history: np.ndarray,
        d_history: np.ndarray,
        h: float,
        history2: np.ndarray,
        data_out: np.ndarray,
    ) -> None:
        _unused = (self._tag, states, params, history, d_history, h, history2)
        data_out[:] = 0.0
        data_out[0] = 1.0


class SingularCompiledJacobian:
    __slots__ = ["_tag"]

    def __init__(self) -> None:
        self._tag = "compiled_singular_jacobian"

    def evaluate(
        self,
        states: np.ndarray,
        params: np.ndarray,
        history: np.ndarray,
        d_history: np.ndarray,
        h: float,
        history2: np.ndarray,
    ) -> csc_matrix:
        _unused = (self._tag, states, params, history, d_history, h, history2)
        return csc_matrix(np.array([[1.0, 0.0], [0.0, 1.0e-16]], dtype=np.float64))

    def get_data_buffer(self) -> np.ndarray:
        _unused = self._tag
        return np.zeros(1, dtype=np.float64)


def inexact_vectorized_residual(
    x_iter: np.ndarray,
    full_params: np.ndarray,
    x_prev: np.ndarray,
    dx_prev: np.ndarray,
    h: float,
    vec_flat_args: np.ndarray,
    res_global: np.ndarray,
    x_prev2: np.ndarray,
) -> None:
    _unused = (full_params, x_prev, dx_prev, h, vec_flat_args, x_prev2)
    res_global[:] = 0.0
    res_global[0] = x_iter[0] ** 2 - 1.0


class InexactVectorizedJacobian:
    __slots__ = ["_tag"]

    def __init__(self) -> None:
        self._tag = "vectorized_inexact_jacobian"

    def __call__(
        self,
        states: np.ndarray,
        params: np.ndarray,
        history: np.ndarray,
        d_history: np.ndarray,
        h: float,
        history2: np.ndarray | None = None,
    ) -> csc_matrix:
        _unused = (self._tag, params, history, d_history, h, history2)
        return csc_matrix([[0.2 * states[0]]], dtype=np.float64)


def singular_vectorized_residual(
    x_iter: np.ndarray,
    full_params: np.ndarray,
    x_prev: np.ndarray,
    dx_prev: np.ndarray,
    h: float,
    vec_flat_args: np.ndarray,
    res_global: np.ndarray,
    x_prev2: np.ndarray,
) -> None:
    _unused = (x_iter, full_params, x_prev, dx_prev, h, vec_flat_args, x_prev2)
    res_global[:] = 0.0
    res_global[0] = 1.0


class SingularVectorizedJacobian:
    __slots__ = ["_tag"]

    def __init__(self) -> None:
        self._tag = "vectorized_singular_jacobian"

    def __call__(
        self,
        states: np.ndarray,
        params: np.ndarray,
        history: np.ndarray,
        d_history: np.ndarray,
        h: float,
        history2: np.ndarray | None = None,
    ) -> csc_matrix:
        _unused = (self._tag, states, params, history, d_history, h, history2)
        return csc_matrix(np.array([[1.0, 0.0], [0.0, 1.0e-16]], dtype=np.float64))


@pytest.mark.parametrize(
    "solver_class",
    [StructuralVectorizedSolver, StructuralCompiledSolver],
    ids=["StructuralVectorizedSolver", "StructuralCompiledSolver"],
)
def test_structural_solver_defaults_keep_expensive_diagnostics_disabled(solver_class: type) -> None:
    block = build_scalar_state_block()
    static_parameter_values_mapping: Dict[Var, Const] = dict(block.parameters)
    problem = GenericEmtProblem(
        sys_block=block,
        glob_time=Var(f"t_{solver_class.__name__}"),
        static_parameter_values_mapping=static_parameter_values_mapping,
    )

    if solver_class is StructuralVectorizedSolver:
        solver = solver_class(
            problem=problem,
            t0=0.0,
            t_end=1e-3,
            h=1e-4,
            method=DynamicIntegrationMethod.DaeBackEuler,
            dense_threshold=100,
            verbose=False,
            auto_vectorization=False,
        )
    else:
        solver = solver_class(
            problem=problem,
            t0=0.0,
            t_end=1e-3,
            h=1e-4,
            method=DynamicIntegrationMethod.DaeBackEuler,
            dense_threshold=100,
            verbose=False,
            auto_build=False,
        )

    cfg = solver._newton_diag_config
    assert not cfg.compute_dense_cond
    assert not cfg.enable_fallback
    assert not cfg.enable_index1_check
    assert not cfg.enable_backtracking


def test_dense_index1_helper_raises_on_singular_gy() -> None:
    jacobian = np.array([[1.0, 0.0], [0.0, 0.0]], dtype=np.float64)
    config = NewtonDiagnosticsConfig(
        enable_index1_check=True,
        index1_max_block_n=8,
        compute_dense_cond=False,
        enable_fallback=False,
    )

    with pytest.raises(RuntimeError):
        maybe_check_index1(jacobian, n_state=1, config=config)


def test_sparse_index1_helper_raises_on_singular_gy() -> None:
    jacobian = csc_matrix(np.array([[1.0, 0.0], [0.0, 0.0]], dtype=np.float64))
    config = NewtonDiagnosticsConfig(
        enable_index1_check=True,
        index1_max_block_n=8,
        compute_dense_cond=False,
        enable_fallback=False,
    )

    with pytest.raises(RuntimeError):
        maybe_check_index1(jacobian, n_state=1, config=config)


def test_backtracking_helper_accepts_reduced_step() -> None:
    x_iter = np.array([0.0], dtype=np.float64)
    delta = np.array([10.0], dtype=np.float64)
    trial_x = np.zeros(1, dtype=np.float64)
    trial_res = np.zeros(1, dtype=np.float64)
    config = NewtonDiagnosticsConfig(
        enable_backtracking=True,
        backtracking_beta=0.5,
        backtracking_min_alpha=1e-3,
        backtracking_max_iter=8,
        compute_dense_cond=False,
        enable_fallback=False,
    )

    def evaluate(candidate_x: np.ndarray, out_res: np.ndarray) -> float:
        out_res[0] = (candidate_x[0] - 1.0) ** 2
        return float(abs(out_res[0]))

    maybe_apply_backtracking(
        x_iter,
        delta,
        res_norm=1.0,
        trial_x=trial_x,
        trial_res=trial_res,
        evaluate_residual=evaluate,
        config=config,
    )

    assert (x_iter[0] - 1.0) ** 2 < 1.0
    assert float(x_iter[0]) != pytest.approx(10.0)


def test_backtracking_helper_keeps_full_step_when_disabled() -> None:
    x_iter = np.array([0.0], dtype=np.float64)
    delta = np.array([10.0], dtype=np.float64)
    trial_x = np.zeros(1, dtype=np.float64)
    trial_res = np.zeros(1, dtype=np.float64)
    config = NewtonDiagnosticsConfig(enable_backtracking=False)

    def evaluate(candidate_x: np.ndarray, out_res: np.ndarray) -> float:
        out_res[0] = (candidate_x[0] - 1.0) ** 2
        return float(abs(out_res[0]))

    maybe_apply_backtracking(
        x_iter,
        delta,
        res_norm=1.0,
        trial_x=trial_x,
        trial_res=trial_res,
        evaluate_residual=evaluate,
        config=config,
    )

    assert float(x_iter[0]) == pytest.approx(10.0)


def test_structural_vectorized_records_newton_trace() -> None:
    block = build_decay_block(n_states=2)
    static_parameter_values_mapping: Dict[Var, Const] = dict(block.parameters)
    problem = GenericEmtProblem(
        sys_block=block,
        glob_time=Var("t_trace_vec"),
        static_parameter_values_mapping=static_parameter_values_mapping,
    )
    collector = NewtonTraceCollector()
    problem.set_newton_trace_collector(collector)

    solver = StructuralVectorizedSolver(
        problem=problem,
        t0=0.0,
        t_end=0.05,
        h=0.01,
        method=DynamicIntegrationMethod.DaeTrapezoidal,
        pred_method=DynamicIntegrationMethod.OdeEuler,
        dense_threshold=100,
        verbose=False,
    )

    x0 = np.array([1.0, -0.5], dtype=np.float64)
    dx0 = -1.5 * x0
    solver.simulate(x0=x0, dx0=dx0, params0=np.zeros(0, dtype=np.float64))

    assert len(collector.records) > 0
    assert "res_norm_inf" in collector.records[0]
    assert not collector.records[0]["used_fallback"]
    assert collector.records[0]["cond_J"] is None


def test_structural_compiled_records_newton_trace() -> None:
    block = build_decay_block(n_states=2)
    static_parameter_values_mapping: Dict[Var, Const] = dict(block.parameters)
    problem = GenericEmtProblem(
        sys_block=block,
        glob_time=Var("t_trace_compiled"),
        static_parameter_values_mapping=static_parameter_values_mapping,
    )
    collector = NewtonTraceCollector()
    problem.set_newton_trace_collector(collector)

    solver = StructuralCompiledSolver(
        problem=problem,
        t0=0.0,
        t_end=0.05,
        h=0.01,
        method=DynamicIntegrationMethod.DaeTrapezoidal,
        pred_method=DynamicIntegrationMethod.OdeEuler,
        dense_threshold=100,
        verbose=False,
    )

    x0 = np.array([1.0, -0.5], dtype=np.float64)
    dx0 = -1.5 * x0
    solver.simulate(x0=x0, dx0=dx0, params0=np.zeros(0, dtype=np.float64))

    assert len(collector.records) > 0
    assert "res_norm_inf" in collector.records[0]
    assert not collector.records[0]["used_fallback"]
    assert collector.records[0]["cond_J"] is None


def test_structural_vectorized_runtime_index1_guard_raises() -> None:
    block = build_singular_dae_block()
    static_parameter_values_mapping: Dict[Var, Const] = dict(block.parameters)
    problem = GenericEmtProblem(
        sys_block=block,
        glob_time=Var("t_idx_vec"),
        static_parameter_values_mapping=static_parameter_values_mapping,
    )
    cfg = NewtonDiagnosticsConfig(
        enable_index1_check=True,
        index1_max_block_n=8,
        compute_dense_cond=False,
        enable_fallback=False,
    )

    solver = StructuralVectorizedSolver(
        problem=problem,
        t0=0.0,
        t_end=0.1,
        h=0.1,
        method=DynamicIntegrationMethod.DaeBackEuler,
        dense_threshold=0,
        verbose=False,
        auto_vectorization=False,
        newton_diag_config=cfg,
    )
    solver.vectorized_ready = True
    solver.vec_flat_args = np.zeros(0, dtype=np.float64)
    solver.fused_residual = singular_vectorized_residual
    solver.vec_jacobian = SingularVectorizedJacobian()

    with pytest.raises(RuntimeError):
        solver.simulate(
            x0=np.array([0.0, 0.0], dtype=np.float64),
            dx0=np.array([0.0], dtype=np.float64),
            params0=np.zeros(0, dtype=np.float64),
        )


def test_structural_compiled_runtime_index1_guard_raises() -> None:
    block = build_singular_dae_block()
    static_parameter_values_mapping: Dict[Var, Const] = dict(block.parameters)
    problem = GenericEmtProblem(
        sys_block=block,
        glob_time=Var("t_idx_compiled"),
        static_parameter_values_mapping=static_parameter_values_mapping,
    )
    cfg = NewtonDiagnosticsConfig(
        enable_index1_check=True,
        index1_max_block_n=8,
        compute_dense_cond=False,
        enable_fallback=False,
    )

    solver = StructuralCompiledSolver(
        problem=problem,
        t0=0.0,
        t_end=0.1,
        h=0.1,
        method=DynamicIntegrationMethod.DaeBackEuler,
        dense_threshold=0,
        verbose=False,
        auto_build=False,
        newton_diag_config=cfg,
    )
    solver._vectorized_ready = True
    solver._residual_assembler = cast(Any, SingularCompiledResidualAssembler())
    solver._jacobian_evaluator = cast(Any, SingularCompiledJacobian())

    with pytest.raises(RuntimeError):
        solver.simulate(
            x0=np.array([0.0, 0.0], dtype=np.float64),
            dx0=np.array([0.0], dtype=np.float64),
            params0=np.zeros(0, dtype=np.float64),
        )


def test_structural_vectorized_backtracking_improves_inexact_newton_residual() -> None:
    block = build_scalar_state_block()
    static_parameter_values_mapping: Dict[Var, Const] = dict(block.parameters)
    problem = GenericEmtProblem(
        sys_block=block,
        glob_time=Var("t_bt_vec"),
        static_parameter_values_mapping=static_parameter_values_mapping,
    )

    solver_plain = StructuralVectorizedSolver(
        problem=problem,
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

    solver_bt = StructuralVectorizedSolver(
        problem=problem,
        t0=0.0,
        t_end=0.1,
        h=0.1,
        method=DynamicIntegrationMethod.DaeBackEuler,
        dense_threshold=100,
        verbose=False,
        auto_vectorization=False,
        newton_max_iter=100,
        newton_diag_config=NewtonDiagnosticsConfig(
            enable_backtracking=True,
            backtracking_beta=0.5,
            backtracking_min_alpha=1e-3,
            backtracking_max_iter=8,
            compute_dense_cond=False,
            enable_fallback=False,
        ),
    )
    solver_bt.vectorized_ready = True
    solver_bt.vec_flat_args = np.zeros(0, dtype=np.float64)
    solver_bt.fused_residual = inexact_vectorized_residual
    solver_bt.vec_jacobian = InexactVectorizedJacobian()

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

    res_plain = abs(float(y_plain[-1, 0] ** 2 - 1.0))
    res_bt = abs(float(y_bt[-1, 0] ** 2 - 1.0))

    # A failed iterate is unavailable; the initial sample remains intact.
    assert not converged_plain
    assert not well_plain
    assert t_plain.shape == (1,)
    assert y_plain.shape == dy_plain.shape == (1, 1)
    np.testing.assert_array_equal(y_plain, np.array([[0.1]]))
    np.testing.assert_array_equal(dy_plain, np.zeros((1, 1)))
    assert res_plain > 1e-1
    assert converged_bt
    assert well_bt
    assert t_bt.shape == (2,)
    assert y_bt.shape == dy_bt.shape == (2, 1)
    assert res_bt < 1e-6
    assert res_bt < res_plain


def test_structural_compiled_backtracking_improves_inexact_newton_residual() -> None:
    block = build_scalar_state_block()
    static_parameter_values_mapping: Dict[Var, Const] = dict(block.parameters)
    problem = GenericEmtProblem(
        sys_block=block,
        glob_time=Var("t_bt_compiled"),
        static_parameter_values_mapping=static_parameter_values_mapping,
    )

    solver_plain = StructuralCompiledSolver(
        problem=problem,
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

    solver_bt = StructuralCompiledSolver(
        problem=problem,
        t0=0.0,
        t_end=0.1,
        h=0.1,
        method=DynamicIntegrationMethod.DaeBackEuler,
        dense_threshold=100,
        verbose=False,
        auto_build=False,
        newton_max_iter=100,
        newton_diag_config=NewtonDiagnosticsConfig(
            enable_backtracking=True,
            backtracking_beta=0.5,
            backtracking_min_alpha=1e-3,
            backtracking_max_iter=8,
            compute_dense_cond=False,
            enable_fallback=False,
        ),
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

    res_plain = abs(float(y_plain[-1, 0] ** 2 - 1.0))
    res_bt = abs(float(y_bt[-1, 0] ** 2 - 1.0))

    # A failed iterate is unavailable; the initial sample remains intact.
    assert not converged_plain
    assert not well_plain
    assert t_plain.shape == (1,)
    assert y_plain.shape == dy_plain.shape == (1, 1)
    np.testing.assert_array_equal(y_plain, np.array([[0.1]]))
    np.testing.assert_array_equal(dy_plain, np.zeros((1, 1)))
    assert res_plain > 1e-1
    assert converged_bt
    assert well_bt
    assert t_bt.shape == (2,)
    assert y_bt.shape == dy_bt.shape == (2, 1)
    assert res_bt < 1e-6
    assert res_bt < res_plain
