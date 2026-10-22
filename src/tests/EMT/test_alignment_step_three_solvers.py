# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can see it at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import math
from typing import Any, List, Sequence, Tuple, cast, Dict

import numpy as np
import pytest
from scipy.sparse import csc_matrix
from VeraGridEngine.enumerations import DynamicIntegrationMethod
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import (
    JitSymbolicSolver,
)
from VeraGridEngine.Simulations.EMT.solvers.solver_AD import (
    JitAdSolver,
    BoundaryUpdaterInterface,
)
from VeraGridEngine.Simulations.EMT.solvers.StructuralVectorizedSolver import (
    StructuralVectorizedSolver,
)
from VeraGridEngine.Simulations.EMT.solvers.structural_compiled_solver import StructuralCompiledSolver
from VeraGridEngine.Utils.Symbolic.diagnostic import NewtonDiagnosticsConfig
from VeraGridEngine.Utils.emt_boundary_update_wrapper import BoundaryUpdateWrapper
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const
from VeraGridEngine.enumerations import EmtSolverTypes
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory


@pytest.mark.parametrize("dense_threshold", (0, 100))
@pytest.mark.parametrize("backtracking", (False, True))
def test_bdf2_symbolic_rejection_prefix(dense_threshold: int, backtracking: bool) -> None:
    """Reject Symbolic candidates without publishing or committing their history.

    :param dense_threshold: Force dense or sparse linear solves.
    :param backtracking: Enable the existing line search.
    :return: None.
    """
    accepted_steps: int
    for accepted_steps in (0, 1, 2):
        x: Var = Var("bdf_reject_x")
        dx: Var = Var("bdf_reject_dx", base_var=x)
        z: Var = Var("bdf_reject_z")
        p: Var = Var("bdf_reject_p")
        block: Block = Block(name="BdfSymbolicRejection", state_vars=list((x,)), diff_vars=list((dx,)),
                             state_eqs=list((-x,)), algebraic_vars=list((z,)),
                             algebraic_eqs=list((z * z - p,)), parameters=dict())
        block.unify_blocks()
        block.mode_dict = dict(((p, Const(1.0)),))
        problem: EmtProblemTemplate = EmtProblemTemplate(sys_block=block, glob_time=Var("bdf_reject_time"),
                                                        static_parameter_values_mapping=dict())
        tracker: ForcedEventTracker = ForcedEventTracker(forced_times=tuple(),
                                                        change_time=(accepted_steps + 1) * 0.1,
                                                        parameter_value=4.0)
        config: NewtonDiagnosticsConfig = NewtonDiagnosticsConfig(enable_backtracking=backtracking)
        solver: JitSymbolicSolver = JitSymbolicSolver(problem=problem, t0=0.0, t_end=0.4, h=0.1,
                                                     method=DynamicIntegrationMethod.DaeBDF2,
                                                     dense_threshold=dense_threshold, newton_max_iter=1,
                                                     newton_tolerance=1e-10, newton_diag_config=config)
        times: np.ndarray
        values: np.ndarray
        derivatives: np.ndarray
        well: bool
        converged: bool
        times, values, derivatives, well, converged = solver.simulate(
            x0=np.ones(2), dx0=np.array((17.0,)), params0=np.ones(1), boundary_updater=tracker)
        rows: int = accepted_steps + 1
        assert not converged and well == (accepted_steps > 0)
        assert values.shape == (rows, 2) and derivatives.shape == (rows, 1)
        np.testing.assert_allclose(times, np.arange(rows) * 0.1, atol=1e-12, rtol=0)
        np.testing.assert_allclose(values[:, 1], 1.0, atol=1e-12, rtol=0)
        np.testing.assert_allclose(derivatives[1:, 0] + values[1:, 0], 0.0, atol=1e-8, rtol=0)
        assert derivatives[0, 0] == 17.0
        np.testing.assert_allclose(tracker.commit_calls, times[1:], atol=1e-12, rtol=0)
        assert tracker.resolve_calls == list((True,) * accepted_steps + (False,))
        assert solver.get_last_runtime_stats()["macro_steps"] == accepted_steps
        # A fresh call must obtain its own BE state even after a rejected main step.
        restart: Tuple[np.ndarray, np.ndarray, np.ndarray, bool, bool] = solver.simulate(
            x0=np.array((2.0, 1.0)), dx0=np.array((29.0,)), params0=np.ones(1))
        assert restart[4] and restart[1][1, 0] == pytest.approx(2.0 / 1.1, abs=1e-8)
        # Startup does not extend the existing fixed-step BDF2 alignment contract.
        forced_tracker: ForcedEventTracker = ForcedEventTracker(forced_times=(0.05,))
        with pytest.raises(NotImplementedError, match="force_step_alignment"):
            solver.simulate(x0=np.ones(2), dx0=np.array((17.0,)), params0=np.ones(1),
                            boundary_updater=forced_tracker)


class DummyProblem(EmtProblemTemplate):
    """
    Minimal EMT problem compatible with the three solvers.

    It uses the real EmtProblemTemplate initialization path so that static type
    checkers accept it cleanly.
    """

    def __init__(self) -> None:
        vf: VarFactory = VarFactory()
        sys_block: Block = Block(children=[], in_vars=[])
        glob_time: Var = Var(self.TIME_NAME)

        x: Var = vf.add_var("x")
        dx: Var = vf.add_diff_var("dx", base_var=x)
        held_output: Var = Var("held_native_output")

        sys_block.state_vars = [x]
        sys_block.algebraic_vars = []
        sys_block.diff_vars = [dx]

        sys_block.state_eqs = [Const(0.0)]
        sys_block.algebraic_eqs = []

        sys_block.parameters = {}
        sys_block.event_dict = {}
        sys_block.mode_dict = {held_output: Const(0.0)}
        static_parameter_values_mapping: Dict[Var, Const] = dict()

        super().__init__(sys_block=sys_block, static_parameter_values_mapping=static_parameter_values_mapping, glob_time=glob_time)

        self._x0: np.ndarray = np.array([1.234], dtype=np.float64)
        self._dx0: np.ndarray = np.array([0.0], dtype=np.float64)

    def get_x0(self) -> np.ndarray:
        return self._x0.copy()

    def get_dx0(self) -> np.ndarray:
        return self._dx0.copy()

    def def_event_params_fn(
            self,
            ev_params: np.ndarray,
            t: float,
            defer_unavailable_dependencies: bool = False,
    ) -> np.ndarray:
        _unused: Tuple[float, bool] = (t, defer_unavailable_dependencies)
        return ev_params

    def get_newton_trace_collector(self) -> Any:
        return None


class ForcedEventTracker(
    BoundaryUpdaterInterface,
    BoundaryUpdateWrapper,
):
    """
    Boundary updater used to verify aligned substeps.

    It records:
    - every query to get_next_forced_event_time(...)
    - every call to update(...)

    Events are considered consumed when update(...) reaches their time.
    """

    def __init__(self, forced_times: Sequence[float], tol: float = 1e-12,
                 change_time: float | None = None, parameter_value: float | None = None,
                 retry_time: float | None = None) -> None:
        """Track accepted boundaries with an optional parameter change and retry.

        :param forced_times: Required local alignment boundaries.
        :param tol: Floating-point boundary comparison tolerance.
        :param change_time: Time from which the scheduled parameter is used.
        :param parameter_value: Scheduled value; None preserves held-output behavior.
        :param retry_time: Earlier event discovered while preparing a later step.
        :return: None.
        """
        self._forced_times: List[float] = [float(v) for v in forced_times]
        self._tol: float = float(tol)
        self._cursor: int = 0
        self.query_calls: List[Tuple[float, float]] = []
        self.update_calls: List[float] = []
        self.update_parameter_values: List[float] = []
        self.resolve_calls: List[bool] = []
        self.commit_calls: List[float] = list()
        self.update_states: List[np.ndarray] = list()
        self.commit_states: List[np.ndarray] = list()
        self._change_time: float | None = change_time
        self._parameter_value: float | None = parameter_value
        self._retry_time: float | None = retry_time
        self._retry_pending: float | None = None
        self._retry_requested: bool = False

    def get_next_forced_event_time(self, t_prev: float, t_target: float) -> float | None:
        self.query_calls.append((float(t_prev), float(t_target)))

        # A discovered event must be retried from the last accepted history.
        if self._retry_pending is not None:
            return self._retry_pending
        else:
            pass
        idx: int = self._cursor
        while idx < len(self._forced_times):
            event_time: float = self._forced_times[idx]
            if (t_prev + self._tol) < event_time <= (t_target + self._tol):
                return event_time
            else:
                pass
            idx += 1

        return None

    def update(self, t: float, x_prev: np.ndarray, full_params: np.ndarray) -> float | None:
        """Prepare the scheduled parameter without advancing accepted history.

        :param t: Target time being prepared by the solver.
        :param x_prev: Last accepted state, copied for regression assertions.
        :param full_params: Mutable parameter buffer consumed by real kernels.
        :return: Earlier discovered event time, or None.
        """
        self.update_states.append(x_prev.copy())

        t_float: float = float(t)
        self.update_calls.append(t_float)

        if self._parameter_value is not None and self._change_time is not None:
            if t_float >= self._change_time - self._tol:
                full_params[0] = self._parameter_value
            else:
                full_params[0] = 1.0
        else:
            pass
        self.update_parameter_values.append(float(full_params[0]))
        while self._cursor < len(self._forced_times):
            if self._forced_times[self._cursor] <= t_float + self._tol:
                self._cursor += 1
            else:
                break

        # Preparation discovers an event once; reaching it clears the retry.
        if self._retry_time is not None and not self._retry_requested and t_float > self._retry_time + self._tol:
            self._retry_requested = True
            self._retry_pending = self._retry_time
            return self._retry_pending
        else:
            if self._retry_pending is not None and t_float >= self._retry_pending - self._tol:
                self._retry_pending = None
            else:
                pass
        return None

    def resolve_step(self, accepted: bool, params: np.ndarray) -> float | None:
        """Record one solver decision for the prepared boundary step.

        :param accepted: Whether the EMT numerical step converged.
        :param params: Full runtime-parameter vector.
        :return: None.
        """

        _unused: np.ndarray = params
        self.resolve_calls.append(bool(accepted))
        return None

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
        self.commit_states.append(x.copy())
        commit_time: float = float(t)
        self.commit_calls.append(commit_time)
        if self._parameter_value is None:
            params[0] = commit_time
        else:
            pass


class DummyJacobian:
    """
    Constant 1x1 Jacobian used by the three solvers.
    """

    def __call__(
        self,
        states: np.ndarray,
        params: np.ndarray,
        history: np.ndarray,
        d_history: np.ndarray,
        h: float,
        history2: np.ndarray | None = None,
    ) -> csc_matrix:
        _unused: Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, float, np.ndarray | None] = (
            states,
            params,
            history,
            d_history,
            h,
            history2,
        )
        return csc_matrix([[1.0]], dtype=np.float64)


def _dummy_kernel(
    x_iter: np.ndarray,
    full_params: np.ndarray,
    x_prev: np.ndarray,
    dx_prev: np.ndarray,
    h: float,
    res: np.ndarray,
    x_prev2: np.ndarray,
) -> None:
    _unused: Tuple[np.ndarray, np.ndarray, np.ndarray, float, np.ndarray] = (
        full_params,
        dx_prev,
        x_prev2,
        h,
        x_iter,
    )
    res[0] = x_iter[0] - x_prev[0]


def _dummy_fused_residual(
    x_iter: np.ndarray,
    full_params: np.ndarray,
    x_prev: np.ndarray,
    dx_prev: np.ndarray,
    h: float,
    vec_flat_args: np.ndarray,
    res_global: np.ndarray,
    x_prev2: np.ndarray,
) -> None:
    _unused: Tuple[np.ndarray, np.ndarray, np.ndarray, float, np.ndarray, np.ndarray] = (
        full_params,
        dx_prev,
        vec_flat_args,
        h,
        x_prev2,
        x_iter,
    )
    res_global[0] = x_iter[0] - x_prev[0]


@pytest.mark.parametrize(
    ("solver_kind", "expected_updates"),
    [
        (EmtSolverTypes.Symbolic, [0.00, 0.05, 0.10, 0.15, 0.20]),
        (EmtSolverTypes.Automatic, [0.05, 0.10, 0.15, 0.20]),
        (EmtSolverTypes.StructuralAD, [0.00, 0.05, 0.10, 0.15, 0.20]),
    ],
)
def test_force_step_alignment_is_used_by_all_three_solvers(
    override_attrs,
    solver_kind: EmtSolverTypes,
    expected_updates: Sequence[float],
) -> None:
    """
    Verify that the three EMT solvers stop exactly at forced alignment times.

    Scenario:
    - t0 = 0.0 s
    - t_end = 0.2 s
    - macro-step h = 0.1 s
    - forced events at 0.05 s and 0.15 s

    Without alignment, the solvers would only step at 0.1 s and 0.2 s.
    With alignment, each macro-step must be split.
    """

    problem: EmtProblemTemplate = DummyProblem()
    updater: BoundaryUpdaterInterface = ForcedEventTracker(forced_times=[0.05, 0.15])
    integration_method = DynamicIntegrationMethod.DaeBackEuler

    if solver_kind == EmtSolverTypes.Symbolic:
        solver = JitSymbolicSolver(
            problem=problem,
            t0=0.0,
            t_end=0.2,
            h=0.1,
            method=integration_method,
            dense_threshold=100,
            verbose=False,
        )

        solver.jit_kernels[integration_method] = [_dummy_kernel]
        solver.jit_jacobian_symbolic[f"{integration_method}_{False}"] = cast(Any, DummyJacobian())
        override_attrs.setattr(JitSymbolicSolver, "build_jit_kernel", lambda self, method: None)
        override_attrs.setattr(
            JitSymbolicSolver,
            "_build_jit_symbolic_hybrid",
            lambda self, method, use_sparse: None,
        )
        t, y, dy, _, _ = solver.simulate(
            boundary_updater=cast(BoundaryUpdateWrapper, cast(object, updater))
        )

    elif solver_kind == EmtSolverTypes.Automatic:
        solver = JitAdSolver(
            problem=problem,
            t0=0.0,
            t_end=0.2,
            h=0.1,
            method=integration_method,
            dense_threshold=100,
            verbose=False,
        )

        solver.jit_kernels_ad[integration_method] = [_dummy_kernel]
        solver.jit_jacobian_ad[integration_method] = cast(Any, DummyJacobian())

        t, y, dy, _, _ = solver.simulate(boundary_updater=updater)

    elif solver_kind == EmtSolverTypes.StructuralAD:
        solver = StructuralVectorizedSolver(
            problem=problem,
            t0=0.0,
            t_end=0.2,
            h=0.1,
            method=integration_method,
            dense_threshold=100,
            verbose=False,
            auto_vectorization=False,
        )

        solver.vectorized_ready = True
        solver.vec_flat_args = np.zeros(0, dtype=np.float64)
        solver.fused_residual = cast(Any, _dummy_fused_residual)
        solver.vec_jacobian = cast(Any, DummyJacobian())

        t, y, dy, _, _ = solver.simulate(
            boundary_updater=cast(BoundaryUpdateWrapper, cast(object, updater))
        )

    else:
        raise ValueError(f"Unsupported solver kind: {solver_kind}")

    assert np.allclose(t, np.array([0.0, 0.1, 0.2], dtype=np.float64))
    assert np.allclose(y[:, 0], np.array([1.234, 1.234, 1.234], dtype=np.float64))
    assert np.allclose(dy[:, 0], np.array([0.0, 0.0, 0.0], dtype=np.float64))

    assert len(updater.query_calls) >= 4
    assert np.allclose(
        np.array(updater.update_calls, dtype=np.float64),
        np.array(expected_updates, dtype=np.float64),
    )
    assert updater.resolve_calls == [True, True, True, True]
    expected_parameter_values: np.ndarray
    if solver_kind == EmtSolverTypes.Automatic:
        expected_parameter_values = np.array(
            [0.00, 0.05, 0.10, 0.15], dtype=np.float64
        )
    else:
        expected_parameter_values = np.array(
            [0.00, 0.00, 0.05, 0.10, 0.15], dtype=np.float64
        )
    assert np.allclose(
        np.array(updater.update_parameter_values, dtype=np.float64),
        expected_parameter_values,
    )
    assert np.allclose(
        np.array(updater.commit_calls, dtype=np.float64),
        np.array([0.05, 0.10, 0.15, 0.20], dtype=np.float64),
    )

    rounded_updates = [round(v, 8) for v in updater.update_calls]
    assert 0.05 in rounded_updates
    assert 0.15 in rounded_updates

    first_query = updater.query_calls[0]
    assert math.isclose(first_query[0], 0.0, abs_tol=1e-12)
    assert math.isclose(first_query[1], 0.1, abs_tol=1e-12)


@pytest.mark.parametrize("solver_kind", (EmtSolverTypes.Automatic, EmtSolverTypes.StructuralAD, EmtSolverTypes.StructuralCompiled))
@pytest.mark.parametrize("method", (DynamicIntegrationMethod.DaeBackEuler, DynamicIntegrationMethod.DaeTrapezoidal, DynamicIntegrationMethod.DaeBDF2))
@pytest.mark.parametrize("dense_threshold", (0, 100))
@pytest.mark.parametrize("backtracking", (False, True))
def test_newton_final_correction_acceptance(
        solver_kind: EmtSolverTypes, method: DynamicIntegrationMethod,
        dense_threshold: int, backtracking: bool) -> None:
    """Validate terminal candidates using an independent algebraic oracle.

    :param solver_kind: Real implicit EMT backend under test.
    :param method: Existing time integration method.
    :param dense_threshold: Dense or sparse linear solve selection.
    :param backtracking: Whether the existing line search is enabled.
    :return: None.
    """
    # Each tuple fixes the correction budget and strict residual threshold.
    scenarios: Tuple[Tuple[bool, float, int, float, bool, float], ...] = (
        (False, 2.0, 1, 1e-6, True, 2.0),
        (False, 1.0, 0, 1e-6, True, 1.0),
        (False, 2.0, 0, 1e-6, False, 1.0),
        (True, 4.0, 1, 2.25, False, 1.0),
        (True, 4.0, 1, 2.250001, True, 2.5),
    )
    nonlinear: bool
    value: float
    budget: int
    tolerance: float
    expected_converged: bool
    expected_z: float
    for nonlinear, value, budget, tolerance, expected_converged, expected_z in scenarios:
        x: Var = Var("accept_x")
        dx: Var = Var("accept_dx", base_var=x)
        z: Var = Var("accept_z")
        p: Var = Var("accept_p")
        # Zero dynamics isolates Newton acceptance from integration error.
        block: Block = Block(name="Acceptance", state_vars=list((x,)), diff_vars=list((dx,)),
                             state_eqs=list((Const(0.0),)), algebraic_vars=list((z,)),
                             algebraic_eqs=list((z * z - p if nonlinear else z - p,)), parameters=dict())
        block.unify_blocks()
        block.mode_dict = dict(((p, Const(1.0)),))
        problem: EmtProblemTemplate = EmtProblemTemplate(sys_block=block, glob_time=Var("accept_time"),
                                                        static_parameter_values_mapping=dict())
        tracker: ForcedEventTracker = ForcedEventTracker(forced_times=tuple(), change_time=0.1, parameter_value=value)
        config: NewtonDiagnosticsConfig = NewtonDiagnosticsConfig(enable_backtracking=backtracking)
        solver: JitAdSolver | StructuralVectorizedSolver | StructuralCompiledSolver
        if solver_kind == EmtSolverTypes.Automatic:
            solver = JitAdSolver(problem=problem, t0=0.0, t_end=0.1, h=0.1, method=method,
                                 dense_threshold=dense_threshold, newton_max_iter=budget,
                                 newton_tolerance=tolerance, newton_diag_config=config)
        elif solver_kind == EmtSolverTypes.StructuralAD:
            solver = StructuralVectorizedSolver(problem=problem, t0=0.0, t_end=0.1, h=0.1, method=method,
                                                dense_threshold=dense_threshold, newton_max_iter=budget,
                                                newton_tolerance=tolerance, newton_diag_config=config)
        else:
            solver = StructuralCompiledSolver(problem=problem, t0=0.0, t_end=0.1, h=0.1, method=method,
                                              dense_threshold=dense_threshold, newton_max_iter=budget,
                                              newton_tolerance=tolerance, newton_diag_config=config)
        times: np.ndarray
        values: np.ndarray
        derivatives: np.ndarray
        well_initialized: bool
        converged: bool
        times, values, derivatives, well_initialized, converged = solver.simulate(
            x0=np.array((0.0, 1.0)), dx0=np.zeros(1), params0=np.ones(1), boundary_updater=tracker)
        # Runtime counters exclude backend warmup and count local Jacobians.
        expected_corrections: int = 1 if budget > 0 else 0
        runtime_stats: dict[str, float] = solver.get_last_runtime_stats()
        assert runtime_stats["jacobian_evaluations"] == expected_corrections
        rows: int = 2 if expected_converged else 1
        assert converged == expected_converged
        assert well_initialized == expected_converged
        assert values.shape == (rows, 2)
        assert derivatives.shape == (rows, 1)
        np.testing.assert_allclose(times, np.arange(rows) * 0.1, rtol=0, atol=1e-12)
        np.testing.assert_allclose(values[:, 0], 0.0, rtol=0, atol=1e-12)
        np.testing.assert_allclose(values[-1, 1], expected_z, rtol=0, atol=1e-12)
        np.testing.assert_allclose(derivatives, 0.0, rtol=0, atol=1e-12)
        assert tracker.resolve_calls == list((expected_converged,))
        if expected_converged:
            residual: float = abs(expected_z * expected_z - value) if nonlinear else abs(expected_z - value)
            assert residual < tolerance
            np.testing.assert_allclose(tracker.commit_calls, (0.1,), rtol=0, atol=1e-12)
            np.testing.assert_allclose(tracker.commit_states[0], values[-1], rtol=0, atol=1e-12)
        else:
            assert tracker.commit_calls == list()
        stats: Dict[str, float] = solver.get_last_runtime_stats()
        if solver_kind != EmtSolverTypes.StructuralCompiled:
            assert stats["macro_steps"] == rows - 1
        else:
            pass


@pytest.mark.parametrize("solver_kind", (EmtSolverTypes.Automatic, EmtSolverTypes.StructuralAD, EmtSolverTypes.StructuralCompiled))
@pytest.mark.parametrize("method", (DynamicIntegrationMethod.DaeBackEuler, DynamicIntegrationMethod.DaeTrapezoidal, DynamicIntegrationMethod.DaeBDF2))
@pytest.mark.parametrize("dense_threshold", (0, 100))
@pytest.mark.parametrize("backtracking", (False, True))
def test_newton_rejection_preserves_completed_samples(
        solver_kind: EmtSolverTypes, method: DynamicIntegrationMethod,
        dense_threshold: int, backtracking: bool) -> None:
    """Reject failed candidates without committing them or advancing history.

    :param solver_kind: Real implicit EMT backend under test.
    :param method: Existing time integration method.
    :param dense_threshold: Dense or sparse linear solve selection.
    :param backtracking: Whether the existing line search is enabled.
    :return: None.
    """
    scenarios: Tuple[Tuple[float, float, Tuple[float, ...], bool, float | None, int, Tuple[float, ...], bool], ...] = (
        (0.3, 4.0, tuple(), True, None, 3, (0.1, 0.2), True),
        (0.2, 4.0, tuple(), True, None, 2, (0.1,), True),
        (0.1, 4.0, tuple(), True, None, 1, tuple(), False),
        (0.15, 4.0, (0.05, 0.15), True, None, 2, (0.05, 0.1), True),
        (0.1, 4.0, (0.05, 0.15), True, None, 1, (0.05,), True),
        (0.1, float("nan"), tuple(), False, None, 1, tuple(), False),
        (0.1, float("inf"), tuple(), False, None, 1, tuple(), False),
        (0.1, -float("inf"), tuple(), False, None, 1, tuple(), False),
        (0.1, 1e308, tuple(), True, None, 1, tuple(), False),
        (0.2, 2.0, tuple(), False, 0.05, 4, (0.05, 0.1, 0.2, 0.3), True),
    )
    change_time: float
    value: float
    forced_times: Tuple[float, ...]
    nonlinear: bool
    retry_time: float | None
    rows: int
    commits: Tuple[float, ...]
    expected_well: bool
    for change_time, value, forced_times, nonlinear, retry_time, rows, commits, expected_well in scenarios:
        x: Var = Var("reject_x")
        dx: Var = Var("reject_dx", base_var=x)
        z: Var = Var("reject_z")
        p: Var = Var("reject_p")
        block: Block = Block(name="Rejection", state_vars=list((x,)), diff_vars=list((dx,)),
                             state_eqs=list((Const(0.0),)), algebraic_vars=list((z,)),
                             algebraic_eqs=list((z * z - p if nonlinear else z - p,)), parameters=dict())
        block.unify_blocks()
        block.mode_dict = dict(((p, Const(1.0)),))
        problem: EmtProblemTemplate = EmtProblemTemplate(sys_block=block, glob_time=Var("reject_time"),
                                                        static_parameter_values_mapping=dict())
        tracker: ForcedEventTracker = ForcedEventTracker(forced_times=forced_times, change_time=change_time,
                                                        parameter_value=value, retry_time=retry_time)
        config: NewtonDiagnosticsConfig = NewtonDiagnosticsConfig(enable_backtracking=backtracking)
        solver: JitAdSolver | StructuralVectorizedSolver | StructuralCompiledSolver
        if solver_kind == EmtSolverTypes.Automatic:
            solver = JitAdSolver(problem=problem, t0=0.0, t_end=0.3, h=0.1, method=method,
                                 dense_threshold=dense_threshold, newton_max_iter=1, newton_diag_config=config)
        elif solver_kind == EmtSolverTypes.StructuralAD:
            solver = StructuralVectorizedSolver(problem=problem, t0=0.0, t_end=0.3, h=0.1, method=method,
                                                dense_threshold=dense_threshold, newton_max_iter=1, newton_diag_config=config)
        else:
            solver = StructuralCompiledSolver(problem=problem, t0=0.0, t_end=0.3, h=0.1, method=method,
                                              dense_threshold=dense_threshold, newton_max_iter=1, newton_diag_config=config)
        # Preserve the established rejection instead of silently omitting it.
        if method == DynamicIntegrationMethod.DaeBDF2 and (len(forced_times) > 0 or retry_time is not None):
            with pytest.raises(NotImplementedError, match="force_step_alignment"):
                solver.simulate(x0=np.array((0.0, 1.0)), dx0=np.zeros(1),
                                params0=np.ones(1), boundary_updater=tracker)
        else:
            times: np.ndarray
            values: np.ndarray
            derivatives: np.ndarray
            well_initialized: bool
            converged: bool
            times, values, derivatives, well_initialized, converged = solver.simulate(
                x0=np.array((0.0, 1.0)), dx0=np.zeros(1), params0=np.ones(1), boundary_updater=tracker)
            assert converged == (retry_time is not None)
            assert well_initialized == expected_well
            assert values.shape == (rows, 2)
            assert derivatives.shape == (rows, 1)
            np.testing.assert_allclose(times, np.arange(rows) * 0.1, rtol=0, atol=1e-12)
            np.testing.assert_allclose(values[:, 0], 0.0, rtol=0, atol=1e-12)
            np.testing.assert_allclose(derivatives, 0.0, rtol=0, atol=1e-12)
            expected_z: np.ndarray = np.ones(rows)
            if retry_time is not None:
                expected_z[2:] = 2.0
            else:
                pass
            np.testing.assert_allclose(values[:, 1], expected_z, rtol=0, atol=1e-12)
            np.testing.assert_allclose(tracker.commit_calls, commits, rtol=0, atol=1e-12)
            if retry_time is None:
                assert tracker.resolve_calls == list((True,) * len(commits) + (False,))
                assert max(tracker.update_calls) <= change_time + 1e-12
                snapshot: np.ndarray
                for snapshot in tracker.update_states:
                    np.testing.assert_allclose(snapshot, (0.0, 1.0), rtol=0, atol=1e-12)
            else:
                assert tracker.resolve_calls == list((True,) * len(commits))
            commit_time: float
            commit_state: np.ndarray
            for commit_time, commit_state in zip(tracker.commit_calls, tracker.commit_states):
                expected_commit_z: float = 2.0 if retry_time is not None and commit_time >= change_time - 1e-12 else 1.0
                np.testing.assert_allclose(commit_state, (0.0, expected_commit_z), rtol=0, atol=1e-12)
            if solver_kind != EmtSolverTypes.StructuralCompiled:
                assert solver.get_last_runtime_stats()["macro_steps"] == rows - 1
            else:
                pass
