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
from VeraGridEngine.Utils.emt_boundary_update_wrapper import BoundaryUpdateWrapper
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const
from VeraGridEngine.enumerations import EmtSolverTypes
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory


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

    def __init__(self, forced_times: Sequence[float], tol: float = 1e-12) -> None:
        self._forced_times: List[float] = [float(v) for v in forced_times]
        self._tol: float = float(tol)
        self._cursor: int = 0
        self.query_calls: List[Tuple[float, float]] = []
        self.update_calls: List[float] = []
        self.update_parameter_values: List[float] = []
        self.resolve_calls: List[bool] = []
        self.commit_calls: List[float] = []

    def get_next_forced_event_time(self, t_prev: float, t_target: float) -> float | None:
        self.query_calls.append((float(t_prev), float(t_target)))

        idx: int = self._cursor
        while idx < len(self._forced_times):
            event_time: float = self._forced_times[idx]
            if (t_prev + self._tol) < event_time <= (t_target + self._tol):
                return event_time
            idx += 1

        return None

    def update(self, t: float, x_prev: np.ndarray, full_params: np.ndarray) -> None:
        _unused: np.ndarray = x_prev

        t_float: float = float(t)
        self.update_calls.append(t_float)

        self.update_parameter_values.append(float(full_params[0]))
        while self._cursor < len(self._forced_times):
            if self._forced_times[self._cursor] <= t_float + self._tol:
                self._cursor += 1
            else:
                break

    def resolve_step(self, accepted: bool, params: np.ndarray) -> None:
        """Record one solver decision for the prepared boundary step.

        :param accepted: Whether the EMT numerical step converged.
        :param params: Full runtime-parameter vector.
        :return: None.
        """

        _unused: np.ndarray = params
        self.resolve_calls.append(bool(accepted))

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
