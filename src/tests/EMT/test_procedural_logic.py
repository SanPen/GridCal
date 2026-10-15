# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can see it at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import math
import time
import statistics
from typing import Dict, List, Mapping, Optional, Tuple

import numpy as np
import pytest

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import BoundaryUpdateWrapper, JitSymbolicSolver
from VeraGridEngine.Utils.procedural_logic import (
    aflipflop,
    BlockProceduralLogicUpdater,
    DelayedThresholdLatchLogic,
    bool_and,
    bool_or,
    build_boundary_updater_from_block,
    flipflop,
    ifelse,
    lastvalue,
    picdro,
    ProceduralLogicCodec,
    reset,
    sampled_value,
    select,
)
from VeraGridEngine.Utils.Symbolic.diagnostic import NewtonTraceCollector
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import atan2, Comparison, Const, Expr, Var
from VeraGridEngine.enumerations import DynamicIntegrationMethod


def _read_benchmark_float(
        statistics_data: Mapping[str, object],
        field_name: str,
) -> float:
    """Read one numeric statistic from an offline benchmark result.

    :param statistics_data: Benchmark fields produced by the local test run.
    :param field_name: Required numeric statistic name.
    :return: Statistic converted to floating-point representation.
    """
    raw_value: object = statistics_data.get(field_name, None)
    if isinstance(raw_value, (float, int)) and not isinstance(raw_value, bool):
        return float(raw_value)
    else:
        raise TypeError(f"Benchmark field '{field_name}' must be numeric")


def _read_benchmark_integer(
        statistics_data: Mapping[str, object],
        field_name: str,
) -> int:
    """Read one exact integer statistic from an offline benchmark result.

    :param statistics_data: Benchmark fields produced by the local test run.
    :param field_name: Required integer statistic name.
    :return: Exact integer statistic.
    """
    raw_value: object = statistics_data.get(field_name, None)
    if isinstance(raw_value, int) and not isinstance(raw_value, bool):
        return raw_value
    else:
        raise TypeError(f"Benchmark field '{field_name}' must be an integer")


class GenericEmtProblem(EmtProblemTemplate):
    """Minimal generic EMT problem used for unit testing."""

    __slots__ = []


class ThresholdDelayTripWrapper(BoundaryUpdateWrapper):
    """
    Protection chain that latches a trip after a threshold pickup plus a delay.

    The wrapper drives a retained runtime mode parameter stored in ``mode_dict``.
    When the monitored state exceeds the threshold, the protection starts a timer.
    Once the delay expires, the wrapper forces the solver to align an EMT substep
    exactly at the trip time and then sets the mode to zero.
    """

    __slots__ = [
        "mode_idx",
        "monitored_idx",
        "threshold",
        "delay",
        "pickup_time",
        "pending_trip_time",
        "tripped",
        "trip_applied_time",
        "trip_applied_solver_time",
        "last_t_prev",
    ]

    def __init__(
        self,
        problem: EmtProblemTemplate,
        monitored_var: Var,
        mode_var: Var,
        threshold: float,
        delay: float,
    ) -> None:
        self.mode_idx: int = problem.uid2idx_event_params[mode_var.uid]
        self.monitored_idx: int = problem.get_var_idx(monitored_var)
        self.threshold: float = float(threshold)
        self.delay: float = float(delay)

        self.pickup_time: Optional[float] = None
        self.pending_trip_time: Optional[float] = None
        self.tripped: bool = False
        self.trip_applied_time: Optional[float] = None
        self.trip_applied_solver_time: Optional[float] = None
        self.last_t_prev: Optional[float] = None

    def get_next_forced_event_time(self, t_prev: float, t_target: float) -> Optional[float]:
        """
        Return a forced-alignment time if the pending trip lies inside the current EMT step.
        """
        self.last_t_prev = float(t_prev)

        if self.pending_trip_time is None:
            return None

        if t_prev < self.pending_trip_time <= t_target:
            return float(self.pending_trip_time)

        return None

    def update(self, t: float, x: np.ndarray, params: np.ndarray) -> None:
        """
        Update the retained mode parameter from the protection logic.

        Notes
        -----
        ``x`` is the previously accepted state vector. Therefore, the physical
        sample time associated with ``x`` is the last accepted time ``t_prev``,
        not the target time ``t`` passed by the solver.
        """
        if self.tripped:
            params[self.mode_idx] = 0.0
            return

        sample_time: float = float(self.last_t_prev if self.last_t_prev is not None else t)
        measured_value: float = float(x[self.monitored_idx])

        if measured_value >= self.threshold:
            if self.pickup_time is None:
                self.pickup_time = sample_time
                self.pending_trip_time = sample_time + self.delay
        else:
            self.pickup_time = None
            self.pending_trip_time = None

        if self.pending_trip_time is not None and t >= (self.pending_trip_time - 1e-15):
            params[self.mode_idx] = 0.0
            self.tripped = True
            self.trip_applied_time = float(self.pending_trip_time)
            self.trip_applied_solver_time = float(t)
            self.pending_trip_time = None
        else:
            params[self.mode_idx] = 1.0


def _unsafe_bool_expr(expr: Expr | Comparison | float | int) -> Expr:
    if isinstance(expr, Comparison):
        return expr.to_expression()
    if isinstance(expr, Expr):
        return expr
    return Const(float(expr))


def _unsafe_value_expr(expr: Expr | Comparison | float | int) -> Expr:
    if isinstance(expr, Comparison):
        return expr.to_expression()
    if isinstance(expr, Expr):
        return expr
    return Const(float(expr))


def _unsafe_select_expr(
    boolexpr: Expr | Comparison | float | int,
    when_true: Expr | Comparison | float | int,
    when_false: Expr | Comparison | float | int,
) -> Expr:
    cond_expr = _unsafe_bool_expr(boolexpr)
    true_expr = _unsafe_value_expr(when_true)
    false_expr = _unsafe_value_expr(when_false)
    return cond_expr * true_expr + (Const(1.0) - cond_expr) * false_expr


def _unsafe_ifelse_expr(
    boolexpr: Expr | Comparison | float | int,
    when_true: Expr | Comparison | float | int,
    when_false: Expr | Comparison | float | int,
) -> Expr:
    return _unsafe_select_expr(boolexpr, when_true, when_false)


def create_integrator_trip_system(vf: VarFactory) -> Tuple[Block, Dict[str, Var]]:
    """
    Build a compact dynamic system to test retained runtime modes.

    Dynamics
    --------
    x_i_dot = mode_int_enable * k_i * (ref - y)
    y_dot   = (x_i - y) / tau

    The protection acts on ``mode_int_enable``. Before the trip, the integrator is
    active. After the trip, the integrator derivative becomes exactly zero and the
    state ``x_i`` must remain frozen.
    """
    x_i: Var = vf.add_var("x_i")
    y: Var = vf.add_var("y")

    d_x_i: Var = vf.add_diff_var(name="d_x_i", base_var=x_i)
    d_y: Var = vf.add_diff_var(name="d_y", base_var=y)

    mode_int_enable: Var = vf.add_var("mode_int_enable")

    ref: Var = vf.add_var("ref")
    k_i: Var = vf.add_var("k_i")
    tau: Var = vf.add_var("tau")

    state_vars: List[Var] = [x_i, y]
    diff_vars: List[Var] = [d_x_i, d_y]
    state_eqs: List[Expr] = [
        mode_int_enable * k_i * (ref - y),
        (x_i - y) / tau,
    ]

    parameters: Dict[Var, Const] = {
        ref: Const(1.0),
        k_i: Const(200.0),
        tau: Const(2.0e-3),
    }

    mode_dict: Dict[Var, Const] = {
        mode_int_enable: Const(1.0),
    }

    block = Block(
        name="ModeProtectionIntegratorTest",
        state_vars=state_vars,
        diff_vars=diff_vars,
        state_eqs=state_eqs,
        parameters=parameters,
        mode_dict=mode_dict,
    )

    return block, {
        "x_i": x_i,
        "y": y,
        "d_x_i": d_x_i,
        "mode_int_enable": mode_int_enable,
    }


def create_integrator_trip_system_with_logic(vf: VarFactory) -> Tuple[Block, Dict[str, Var]]:
    """
    Build the integrator trip system with procedural logic attached to the block.
    """
    x_i = vf.add_var("x_i")
    y = vf.add_var("y")

    d_x_i = vf.add_diff_var(name="d_x_i", base_var=x_i)
    d_y = vf.add_diff_var(name="d_y", base_var=y)

    mode_int_enable = vf.add_var("mode_int_enable")

    ref = vf.add_var("ref")
    k_i = vf.add_var("k_i")
    tau = vf.add_var("tau")

    state_vars = [x_i, y]
    diff_vars = [d_x_i, d_y]
    state_eqs: list[Expr] = [
        mode_int_enable * k_i * (ref - y),
        (x_i - y) / tau,
    ]

    parameters = {
        ref: Const(1.0),
        k_i: Const(200.0),
        tau: Const(2.0e-3),
    }
    mode_dict = {mode_int_enable: Const(1.0)}

    block = Block(
        name="ModeProtectionIntegratorDemo",
        state_vars=state_vars,
        diff_vars=diff_vars,
        state_eqs=state_eqs,
        parameters=parameters,
        mode_dict=mode_dict,
    )

    block.procedural_logic = [
        DelayedThresholdLatchLogic(
            monitored_var_name="y",
            mode_var_name="mode_int_enable",
            threshold=0.2,
            delay=1.5e-3,
            reset_delay=None,
            name="trip_logic",
        )
    ]

    return block, {
        "x_i": x_i,
        "y": y,
        "mode_var": mode_int_enable,
    }


def create_antiwindup_trip_system(vf: VarFactory) -> Tuple[Block, Dict[str, Var]]:
    """
    Build a compact dynamic system to test a retained mode that disables an
    anti-windup-like feedback branch.

    Dynamics
    --------
    x_i_dot   = k_i * (ref - y) - mode_aw_enable * k_aw * (x_i - u_act)
    u_act_dot = (x_i - u_act) / tau_act
    y_dot     = (u_act - y) / tau_y

    Interpretation
    --------------
    - ``x_i`` is the controller integrator state.
    - ``u_act`` is a delayed actuator / limited actuator proxy.
    - ``(x_i - u_act)`` plays the role of the back-calculation mismatch.
    - ``mode_aw_enable`` enables/disables the anti-windup branch.

    Before the trip, the anti-windup branch damps the integrator derivative.
    After the trip, the protection sets ``mode_aw_enable = 0`` and the
    anti-windup term disappears, but the integrator remains dynamic.
    """
    x_i: Var = vf.add_var("x_i_aw")
    u_act: Var = vf.add_var("u_act_aw")
    y: Var = vf.add_var("y_aw")

    d_x_i: Var = vf.add_diff_var(name="d_x_i_aw", base_var=x_i)
    d_u_act: Var = vf.add_diff_var(name="d_u_act_aw", base_var=u_act)
    d_y: Var = vf.add_diff_var(name="d_y_aw", base_var=y)

    mode_aw_enable: Var = vf.add_var("mode_aw_enable")

    ref: Var = vf.add_var("ref_aw")
    k_i: Var = vf.add_var("k_i_aw")
    k_aw: Var = vf.add_var("k_aw")
    tau_act: Var = vf.add_var("tau_act")
    tau_y: Var = vf.add_var("tau_y")

    state_vars: List[Var] = [x_i, u_act, y]
    diff_vars: List[Var] = [d_x_i, d_u_act, d_y]
    state_eqs: List[Expr] = [
        k_i * (ref - y) - mode_aw_enable * k_aw * (x_i - u_act),
        (x_i - u_act) / tau_act,
        (u_act - y) / tau_y,
    ]

    parameters: Dict[Var, Const] = {
        ref: Const(1.0),
        k_i: Const(200.0),
        k_aw: Const(150.0),
        tau_act: Const(4.0e-3),
        tau_y: Const(2.0e-3),
    }

    mode_dict: Dict[Var, Const] = {
        mode_aw_enable: Const(1.0),
    }

    block = Block(
        name="ModeProtectionAntiWindupTest",
        state_vars=state_vars,
        diff_vars=diff_vars,
        state_eqs=state_eqs,
        parameters=parameters,
        mode_dict=mode_dict,
    )

    return block, {
        "x_i": x_i,
        "u_act": u_act,
        "y": y,
        "d_x_i": d_x_i,
        "d_u_act": d_u_act,
        "d_y": d_y,
        "mode_aw_enable": mode_aw_enable,
    }


def create_boolean_operator_system(vf: VarFactory) -> Tuple[Block, Dict[str, Var]]:
    x_fast = vf.add_var("x_fast")
    x_slow = vf.add_var("x_slow")
    x_mem = vf.add_var("x_mem")

    d_x_fast = vf.add_diff_var(name="d_x_fast", base_var=x_fast)
    d_x_slow = vf.add_diff_var(name="d_x_slow", base_var=x_slow)
    d_x_mem = vf.add_diff_var(name="d_x_mem", base_var=x_mem)

    trip_fast = vf.add_var("trip_fast")
    trip_and = vf.add_var("trip_and")
    master_trip = vf.add_var("master_trip")
    x_mem_last = vf.add_var("x_mem_last")

    tau_fast = vf.add_var("tau_fast")
    tau_slow = vf.add_var("tau_slow")
    k_mem = vf.add_var("k_mem")

    block = Block(
        name="BooleanOperatorProceduralDemo",
        state_vars=[x_fast, x_slow, x_mem],
        diff_vars=[d_x_fast, d_x_slow, d_x_mem],
        state_eqs=[
            (Const(1.0) - x_fast) / tau_fast,
            (Const(1.0) - x_slow) / tau_slow,
            (Const(1.0) - master_trip) * k_mem * (x_fast - x_mem),
        ],
        parameters={
            tau_fast: Const(3.0e-3),
            tau_slow: Const(8.0e-3),
            k_mem: Const(120.0),
        },
        mode_dict={
            trip_fast: Const(0.0),
            trip_and: Const(0.0),
            master_trip: Const(0.0),
            x_mem_last: Const(0.0),
        },
    )

    block.procedural_logic = [
        picdro(x_fast > 0.65, Const(1.0e-3), Const(0.0), output=trip_fast),
        picdro(
            bool_and(x_fast > 0.45, x_slow > 0.30),
            Const(2.0e-3),
            Const(0.0),
            output=trip_and,
        ),
        flipflop(
            bool_or(trip_fast > 0.5, trip_and > 0.5),
            Const(0.0),
            output=master_trip,
        ),
        lastvalue(x_mem, output=x_mem_last),
        reset(x_mem, master_trip > 0.5, Const(0.0)),
    ]

    return block, {
        "x_fast": x_fast,
        "x_slow": x_slow,
        "x_mem": x_mem,
        "trip_fast": trip_fast,
        "trip_and": trip_and,
        "master_trip": master_trip,
        "x_mem_last": x_mem_last,
    }


def create_analog_flipflop_system(vf: VarFactory) -> Tuple[Block, Dict[str, Var]]:
    x_in = vf.add_var("x_in_af")
    x_reset = vf.add_var("x_reset_af")

    d_x_in = vf.add_diff_var(name="d_x_in_af", base_var=x_in)
    d_x_reset = vf.add_diff_var(name="d_x_reset_af", base_var=x_reset)

    y_hold = vf.add_var("y_hold_af")
    ff_state = vf.add_var("ff_state_af")

    tau_in = vf.add_var("tau_in_af")
    tau_reset = vf.add_var("tau_reset_af")

    block = Block(
        name="AnalogFlipFlopDemo",
        state_vars=[x_in, x_reset],
        diff_vars=[d_x_in, d_x_reset],
        state_eqs=[
            (Const(1.0) - x_in) / tau_in,
            (Const(1.0) - x_reset) / tau_reset,
        ],
        parameters={
            tau_in: Const(2.5e-3),
            tau_reset: Const(7.5e-3),
        },
        mode_dict={
            y_hold: Const(0.0),
            ff_state: Const(0.0),
        },
    )

    set_expr = x_in > 0.45
    reset_expr = x_reset > 0.70
    block.procedural_logic = [
        aflipflop(x_in, set_expr, reset_expr, output=y_hold, name="analog_hold"),
        flipflop(set_expr, reset_expr, output=ff_state, name="analog_hold_state"),
    ]

    return block, {
        "x_in": x_in,
        "x_reset": x_reset,
        "y_hold": y_hold,
        "ff_state": ff_state,
    }


def create_internal_ifelse_switch_system(vf: VarFactory) -> Tuple[Block, Dict[str, Var]]:
    x = vf.add_var("x_ifelse")
    d_x = vf.add_diff_var(name="d_x_ifelse", base_var=x)
    gain = vf.add_var("gain_ifelse")

    block = Block(
        name="InternalIfElseSwitchDemo",
        state_vars=[x],
        diff_vars=[d_x],
        state_eqs=[gain * (_unsafe_ifelse_expr(x > 0.5, 0.0, 1.0) - x)],
        parameters={gain: Const(2000.0)},
        init_eqs={x: Const(0.49)},
    )
    return block, {"x": x}


def create_internal_select_switch_system(vf: VarFactory) -> Tuple[Block, Dict[str, Var]]:
    x = vf.add_var("x_select")
    d_x = vf.add_diff_var(name="d_x_select", base_var=x)
    gain = vf.add_var("gain_select")

    block = Block(
        name="InternalSelectSwitchDemo",
        state_vars=[x],
        diff_vars=[d_x],
        state_eqs=[gain * (_unsafe_select_expr(x > 0.5, 0.0, 1.0) - x)],
        parameters={gain: Const(2000.0)},
        init_eqs={x: Const(0.49)},
    )
    return block, {"x": x}


def create_procedural_mode_switch_system(vf: VarFactory) -> Tuple[Block, Dict[str, Var]]:
    x = vf.add_var("x_mode")
    d_x = vf.add_diff_var(name="d_x_mode", base_var=x)
    gain = vf.add_var("gain_mode")
    mode_switch = vf.add_var("mode_switch")

    block = Block(
        name="ProceduralModeSwitchDemo",
        state_vars=[x],
        diff_vars=[d_x],
        state_eqs=[gain * ((Const(1.0) - mode_switch) - x)],
        parameters={gain: Const(2000.0)},
        mode_dict={mode_switch: Const(0.0)},
        init_eqs={x: Const(0.49)},
    )
    block.procedural_logic = [
        picdro(x > 0.5, Const(0.0), Const(0.0), output=mode_switch, name="external_switch_mode"),
    ]
    return block, {"x": x, "mode_switch": mode_switch}


def _collector_iterations_per_local_step(collector: NewtonTraceCollector) -> np.ndarray:
    per_step: dict[tuple[int, float], int] = dict()
    for record in collector.records:
        key = (int(record["step"]), round(float(record["t"]), 12))
        per_step[key] = max(per_step.get(key, 0), int(record["newton_iter"]) + 1)
    return np.asarray(list(per_step.values()), dtype=float)


def _build_benchmark_case(builder) -> Tuple[GenericEmtProblem, JitSymbolicSolver, list[dict[str, object]]]:
    vf = VarFactory()
    block, _ = builder(vf)
    block.unify_blocks()

    static_parameter_values_mapping: Dict[Var, Const] = dict(block.parameters)
    problem = GenericEmtProblem(
        sys_block=block,
        glob_time=vf.add_var(f"t_{block.name}"),
        static_parameter_values_mapping=static_parameter_values_mapping,
    )
    solver = JitSymbolicSolver(
        problem=problem,
        t0=0.0,
        t_end=1.0e-2,
        h=1.0e-3,
        method=DynamicIntegrationMethod.DaeTrapezoidal,
        verbose=False,
    )
    logic_snapshot = problem.sys_block.serialize_procedural_logic_entries()
    return problem, solver, logic_snapshot


def _run_benchmark_simulation(
    problem: GenericEmtProblem,
    solver: JitSymbolicSolver,
    logic_snapshot: list[dict[str, object]],
) -> Dict[str, object]:
    problem.sys_block.procedural_logic = Block.reconstruct_procedural_logic_entries(
        data=logic_snapshot,
        procedural_logic_codec=ProceduralLogicCodec(),
    )
    updater: BlockProceduralLogicUpdater | None = build_boundary_updater_from_block(problem)

    collector = NewtonTraceCollector()
    problem.set_newton_trace_collector(collector)

    t_start = time.perf_counter()
    t, y_hist, _, _, _ = solver.simulate(
        params0=problem.event_params_values.copy(),
        boundary_updater=updater,
    )
    elapsed_s = time.perf_counter() - t_start

    return {
        "elapsed_s": elapsed_s,
        "iterations_per_step": _collector_iterations_per_local_step(collector),
        "trace_records": len(collector.records),
        "t": t,
        "y_hist": y_hist,
    }


def benchmark_switch_formulation(builder, measured_runs: int = 3) -> Dict[str, object]:
    problem, solver, logic_snapshot = _build_benchmark_case(builder)

    _run_benchmark_simulation(problem, solver, logic_snapshot)
    measured = [
        _run_benchmark_simulation(problem, solver, logic_snapshot)
        for _ in range(measured_runs)
    ]

    elapsed = [_read_benchmark_float(item, "elapsed_s") for item in measured]
    mean_iterations = [float(np.mean(item["iterations_per_step"])) for item in measured]
    max_iterations = [float(np.max(item["iterations_per_step"])) for item in measured]

    return {
        "median_elapsed_s": statistics.median(elapsed),
        "mean_newton_iterations": statistics.median(mean_iterations),
        "max_newton_iterations": statistics.median(max_iterations),
        "records_per_run": [
            _read_benchmark_integer(item, "trace_records") for item in measured
        ],
        "elapsed_samples": elapsed,
        "mean_iteration_samples": mean_iterations,
        "max_iteration_samples": max_iterations,
    }


@pytest.fixture(scope="module")
def internal_ifelse_stats():
    """Benchmark statistics for internal ifelse switch formulation."""
    return benchmark_switch_formulation(create_internal_ifelse_switch_system)


@pytest.fixture(scope="module")
def internal_select_stats():
    """Benchmark statistics for internal select switch formulation."""
    return benchmark_switch_formulation(create_internal_select_switch_system)


@pytest.fixture(scope="module")
def procedural_stats():
    """Benchmark statistics for procedural mode switch formulation."""
    return benchmark_switch_formulation(create_procedural_mode_switch_system)


def test_boolean_helper_exprs_eval_like_pf_logic() -> None:
    """
    Test that bool_and and bool_or helper expressions evaluate correctly.
    """
    x = Var("x_eval")
    y = Var("y_eval")

    expr_and = bool_and(x > 0.5, y > 0.5)
    expr_or = bool_or(x > 0.5, y > 0.5)

    assert expr_and.eval(x_eval=1.0, y_eval=1.0) == 1
    assert expr_and.eval(x_eval=1.0, y_eval=0.0) == 0
    assert expr_or.eval(x_eval=0.0, y_eval=1.0) == 1
    assert expr_or.eval(x_eval=0.0, y_eval=0.0) == 0


def test_select_and_ifelse_are_blocked_in_equation_api() -> None:
    """
    Test that select and ifelse raise RuntimeError when used in equation API.
    """
    x = Var("x_eval_guard")

    with pytest.raises(RuntimeError):
        _ = select(x > 0.5, 10.0, 20.0)

    with pytest.raises(RuntimeError):
        _ = ifelse(x > 0.5, 10.0, 20.0)


def test_block_roundtrip_preserves_procedural_logic() -> None:
    """
    Test that procedural logic survives block serialization roundtrip.
    """
    vf = VarFactory()
    block, _ = create_integrator_trip_system_with_logic(vf)

    restored = Block.parse(
        data=block.to_dict(),
        procedural_logic_codec=ProceduralLogicCodec(),
    )

    assert len(restored.procedural_logic) == 1
    logic = restored.procedural_logic[0]
    assert isinstance(logic, DelayedThresholdLatchLogic)
    assert logic.monitored_var_name == "y"
    assert logic.mode_var_name == "mode_int_enable"
    assert pytest.approx(logic.threshold) == 0.2


def test_boundary_updater_builds_from_block_logic() -> None:
    """
    Test that a boundary updater can be built from block procedural logic.
    """
    vf = VarFactory()
    block, vars_map = create_integrator_trip_system_with_logic(vf)
    block.unify_blocks()
    static_parameter_values_mapping: Dict[Var, Const] = dict(block.parameters)
    problem = GenericEmtProblem(
        sys_block=block,
        glob_time=vf.add_var("t_glob"),
        static_parameter_values_mapping=static_parameter_values_mapping,
    )
    canonical_logic: object = block.procedural_logic[0]

    updater = build_boundary_updater_from_block(problem)
    assert updater is not None
    assert len(updater.logic_entries) == 1
    assert updater.logic_entries[0] is not canonical_logic

    params = problem.event_params_values.copy()
    x = problem.get_x0().copy()
    x[problem.get_var_idx(vars_map["y"])] = 0.25

    updater.update(0.0, x, params)
    forced_time = updater.get_next_forced_event_time(0.0, 0.01)
    assert forced_time is not None
    assert pytest.approx(forced_time, abs=1e-7) == 1.5e-3


def test_boundary_updater_re_evaluates_memoryless_mode_at_same_timestamp() -> None:
    """Refresh a memoryless mode when its state snapshot changes at one time.

    :return: None.
    """
    vf: VarFactory = VarFactory()
    source: Var = vf.add_var("sample_source")
    sampled_mode: Var = vf.add_var("sample_mode")
    block: Block = Block(
        algebraic_vars=list((source,)),
        algebraic_eqs=list((source - Const(1.0),)),
        mode_dict=dict(((sampled_mode, Const(0.0)),)),
        procedural_logic=list((sampled_value(output=sampled_mode, source=source),)),
        name="Procedural startup reevaluation",
    )
    problem: GenericEmtProblem = GenericEmtProblem(
        sys_block=block,
        glob_time=vf.add_var("t_glob_startup"),
        static_parameter_values_mapping=dict(),
    )
    updater = build_boundary_updater_from_block(problem)

    assert updater is not None
    state: np.ndarray = problem.get_x0().copy()
    parameters: np.ndarray = problem.event_params_values.copy()
    source_index: int = problem.get_var_idx(source)
    mode_index: int = problem.uid2idx_event_params[sampled_mode.uid]
    state[source_index] = 1.0

    updater.initialize_modes(t=0.0, x=state, params=parameters)
    assert parameters[mode_index] == 1.0

    # Nonlinear initialization and equilibrium solves can improve the state
    # without advancing time. The memoryless mode must follow that new state.
    state[source_index] = 2.0
    updater.update(t=0.0, x=state, params=parameters)
    assert parameters[mode_index] == 2.0


def test_boundary_updater_rejects_duplicate_procedural_mode_writers() -> None:
    """Reject update order as an implicit owner for one retained mode.

    :return: None.
    """
    vf: VarFactory = VarFactory()
    source_a: Var = vf.add_var("source_a")
    source_b: Var = vf.add_var("source_b")
    sampled_mode: Var = vf.add_var("shared_mode")
    block: Block = Block(
        algebraic_vars=list((source_a, source_b)),
        algebraic_eqs=list((source_a, source_b)),
        mode_dict=dict(((sampled_mode, Const(0.0)),)),
        procedural_logic=list((
            sampled_value(output=sampled_mode, source=source_a),
            sampled_value(output=sampled_mode, source=source_b),
        )),
        name="Duplicate procedural mode ownership",
    )
    problem: GenericEmtProblem = GenericEmtProblem(
        sys_block=block,
        glob_time=vf.add_var("t_glob_duplicate_owner"),
        static_parameter_values_mapping=dict(),
    )

    with pytest.raises(ValueError, match="Multiple procedural logic entries write runtime parameter"):
        _ = build_boundary_updater_from_block(problem)


def test_sampled_value_uses_declarative_atan2_argument_order() -> None:
    """Evaluate procedural ``atan2(imaginary, real)`` without generated code.

    :return: None.
    """
    vf: VarFactory = VarFactory()
    imaginary: Var = vf.add_var("imaginary")
    real: Var = vf.add_var("real")
    angle: Var = vf.add_var("angle")
    block: Block = Block(
        name="ProceduralAtan2Test",
        algebraic_vars=list((imaginary, real)),
        algebraic_eqs=list((imaginary, real)),
        event_dict=dict(((angle, Const(0.0)),)),
        procedural_logic=list((
            sampled_value(
                output=angle,
                source=atan2(imaginary, real),
                name="sample_angle",
            ),
        )),
    )
    block.unify_blocks()
    block = Block.parse(
        data=block.to_dict(),
        procedural_logic_codec=ProceduralLogicCodec(),
    )
    problem: GenericEmtProblem = GenericEmtProblem(
        sys_block=block,
        glob_time=vf.add_var("t_glob_atan2"),
        static_parameter_values_mapping=dict(),
    )
    updater: BoundaryUpdateWrapper | None = build_boundary_updater_from_block(problem)

    assert updater is not None

    state: np.ndarray = problem.get_x0().copy()
    parameters: np.ndarray = problem.event_params_values.copy()
    state[problem.get_var_idx(imaginary)] = 1.0
    state[problem.get_var_idx(real)] = 0.0
    updater.update(t=0.0, x=state, params=parameters)

    angle_idx: int = problem.uid2idx_event_params[angle.uid]
    assert parameters[angle_idx] == pytest.approx(math.pi / 2.0)


def test_procedural_logic_demo_path_trips_mode_during_simulation() -> None:
    """
    Test that procedural logic trips the mode during simulation.
    """
    vf = VarFactory()
    block, vars_map = create_integrator_trip_system_with_logic(vf)
    block.unify_blocks()
    static_parameter_values_mapping: Dict[Var, Const] = dict(block.parameters)
    problem = GenericEmtProblem(
        sys_block=block,
        glob_time=vf.add_var("t_glob"),
        static_parameter_values_mapping=static_parameter_values_mapping,
    )

    solver = JitSymbolicSolver(
        problem=problem,
        t0=0.0,
        t_end=2.0e-2,
        h=1.0e-3,
        method=DynamicIntegrationMethod.DaeTrapezoidal,
        verbose=False,
    )

    updater = build_boundary_updater_from_block(problem)
    assert updater is not None
    logic = updater.logic_entries[0]

    params0 = problem.event_params_values.copy()
    _, y_hist, _, _, _ = solver.simulate(params0=params0, boundary_updater=updater)

    assert logic.trip_applied_time is not None
    assert logic.trip_applied_time > 0.0
    assert len(logic.trace_t) > 0
    assert np.max(y_hist[:, problem.get_var_idx(vars_map["y"])]) > 0.2


def test_helper_based_logic_supports_and_or_picdro_flipflop_reset() -> None:
    """
    Test that boolean helpers (AND, OR) and sequential logic (PICDRO, flipflop, reset) work together.
    """
    vf = VarFactory()
    block, vars_map = create_boolean_operator_system(vf)
    block.unify_blocks()
    static_parameter_values_mapping: Dict[Var, Const] = dict(block.parameters)
    problem = GenericEmtProblem(
        sys_block=block,
        glob_time=vf.add_var("t_glob_bool"),
        static_parameter_values_mapping=static_parameter_values_mapping,
    )

    updater = build_boundary_updater_from_block(problem)
    assert updater is not None

    params = problem.event_params_values.copy()
    x = problem.get_x0().copy()

    idx_x_fast = problem.get_var_idx(vars_map["x_fast"])
    idx_x_slow = problem.get_var_idx(vars_map["x_slow"])
    idx_x_mem = problem.get_var_idx(vars_map["x_mem"])

    idx_trip_fast = problem.uid2idx_event_params[vars_map["trip_fast"].uid]
    idx_trip_and = problem.uid2idx_event_params[vars_map["trip_and"].uid]
    idx_master_trip = problem.uid2idx_event_params[vars_map["master_trip"].uid]

    x[idx_x_fast] = 0.70
    x[idx_x_slow] = 0.10
    x[idx_x_mem] = 0.35

    updater.update(0.0, x, params)
    forced_time = updater.get_next_forced_event_time(0.0, 0.01)
    assert forced_time is not None
    assert pytest.approx(forced_time, abs=1e-7) == 1.0e-3

    updater.update(forced_time, x, params)
    assert params[idx_trip_fast] == 1.0
    assert params[idx_master_trip] == 1.0
    assert x[idx_x_mem] == 0.0
    assert params[idx_trip_and] == 0.0


def test_helper_based_logic_supports_and_branch_pickup() -> None:
    """
    Test that the AND branch pickup (PICDRO) triggers correctly.
    """
    vf = VarFactory()
    block, vars_map = create_boolean_operator_system(vf)
    block.unify_blocks()
    static_parameter_values_mapping: Dict[Var, Const] = dict(block.parameters)
    problem = GenericEmtProblem(
        sys_block=block,
        glob_time=vf.add_var("t_glob_bool_2"),
        static_parameter_values_mapping=static_parameter_values_mapping,
    )

    updater = build_boundary_updater_from_block(problem)
    assert updater is not None

    params = problem.event_params_values.copy()
    x = problem.get_x0().copy()

    idx_x_fast = problem.get_var_idx(vars_map["x_fast"])
    idx_x_slow = problem.get_var_idx(vars_map["x_slow"])

    idx_trip_fast = problem.uid2idx_event_params[vars_map["trip_fast"].uid]
    idx_trip_and = problem.uid2idx_event_params[vars_map["trip_and"].uid]
    idx_master_trip = problem.uid2idx_event_params[vars_map["master_trip"].uid]

    x[idx_x_fast] = 0.55
    x[idx_x_slow] = 0.40

    updater.update(0.0, x, params)
    forced_time = updater.get_next_forced_event_time(0.0, 0.01)
    assert forced_time is not None
    assert pytest.approx(forced_time, abs=1e-7) == 2.0e-3

    updater.update(forced_time, x, params)
    assert params[idx_trip_fast] == 0.0
    assert params[idx_trip_and] == 1.0
    assert params[idx_master_trip] == 1.0


def test_aflipflop_holds_analog_value_until_reset() -> None:
    """
    Test that analog flipflop holds the input value until reset triggers.
    """
    vf = VarFactory()
    block, vars_map = create_analog_flipflop_system(vf)
    block.unify_blocks()
    static_parameter_values_mapping: Dict[Var, Const] = dict(block.parameters)
    problem = GenericEmtProblem(
        sys_block=block,
        glob_time=vf.add_var("t_glob_af"),
        static_parameter_values_mapping=static_parameter_values_mapping,
    )

    updater = build_boundary_updater_from_block(problem)
    assert updater is not None

    params = problem.event_params_values.copy()
    x = problem.get_x0().copy()

    idx_x_in = problem.get_var_idx(vars_map["x_in"])
    idx_x_reset = problem.get_var_idx(vars_map["x_reset"])
    idx_y_hold = problem.uid2idx_event_params[vars_map["y_hold"].uid]
    idx_ff_state = problem.uid2idx_event_params[vars_map["ff_state"].uid]

    x[idx_x_in] = 0.30
    x[idx_x_reset] = 0.10
    updater.update(0.0, x, params)
    assert pytest.approx(params[idx_y_hold]) == 0.30
    assert params[idx_ff_state] == 0.0

    x[idx_x_in] = 0.55
    updater.update(0.001, x, params)
    assert pytest.approx(params[idx_y_hold]) == 0.55
    assert params[idx_ff_state] == 1.0

    x[idx_x_in] = 0.90
    updater.update(0.002, x, params)
    assert pytest.approx(params[idx_y_hold]) == 0.55
    assert params[idx_ff_state] == 1.0

    x[idx_x_in] = 0.20
    x[idx_x_reset] = 0.80
    updater.update(0.003, x, params)
    assert pytest.approx(params[idx_y_hold]) == 0.20
    assert params[idx_ff_state] == 0.0


def test_protection_chain_freezes_integrator_with_exact_substep_alignment() -> None:
    """
    The retained mode parameter must freeze the integrator after the protection trips.

    This test validates four behaviors:
    1. ``mode_dict`` parameters are classified as retained runtime modes.
    2. The protection chain can latch a future trip time.
    3. The solver can align a substep exactly at a non-grid trip time.
    4. After the trip, the integrator derivative is zero and the integrator state is frozen.
    """
    vf = VarFactory()
    block, vars_map = create_integrator_trip_system(vf=vf)
    block.unify_blocks()

    glob_time: Var = vf.add_var("t_glob")
    static_parameter_values_mapping: Dict[Var, Const] = dict(block.parameters)
    problem = GenericEmtProblem(
        sys_block=block,
        glob_time=glob_time,
        static_parameter_values_mapping=static_parameter_values_mapping,
    )

    mode_params: List[Var] = problem.get_runtime_mode_parameters()
    assert len(mode_params) == 1
    assert mode_params[0].uid == vars_map["mode_int_enable"].uid

    dt: float = 1.0e-3
    solver = JitSymbolicSolver(
        problem=problem,
        t0=0.0,
        t_end=2.0e-2,
        h=dt,
        method=DynamicIntegrationMethod.DaeTrapezoidal,
        verbose=False,
    )

    protection = ThresholdDelayTripWrapper(
        problem=problem,
        monitored_var=vars_map["y"],
        mode_var=vars_map["mode_int_enable"],
        threshold=0.20,
        delay=1.5e-3,
    )

    params0 = problem.event_params_values.copy()

    t, y_hist, dy_hist, _, _ = solver.simulate(params0=params0, boundary_updater=protection)

    assert protection.tripped
    assert protection.trip_applied_time is not None
    assert protection.trip_applied_solver_time is not None

    trip_time: float = float(protection.trip_applied_time)
    trip_solver_time: float = float(protection.trip_applied_solver_time)

    assert abs((trip_time / dt) - round(trip_time / dt)) > 1.0e-9
    assert pytest.approx(trip_time, abs=1e-12) == trip_solver_time

    idx_x_i: int = problem.get_var_idx(vars_map["x_i"])
    idx_y: int = problem.get_var_idx(vars_map["y"])
    idx_d_x_i: int = problem.get_diff_var_idx(vars_map["d_x_i"])

    x_i_hist: np.ndarray = y_hist[:, idx_x_i]
    y_hist_only: np.ndarray = y_hist[:, idx_y]
    d_x_i_hist: np.ndarray = dy_hist[:, idx_d_x_i]

    pre_mask = t <= (trip_time - dt)
    post_mask = t >= (trip_time + dt)

    assert np.any(pre_mask)
    assert np.any(post_mask)

    assert np.max(np.abs(d_x_i_hist[pre_mask])) > 1.0e-6
    assert np.max(np.abs(d_x_i_hist[post_mask])) < 1.0e-10
    assert np.max(np.abs(np.diff(x_i_hist[post_mask]))) < 1.0e-10
    assert np.max(y_hist_only[pre_mask]) > protection.threshold


def test_protection_chain_disables_antiwindup_branch_with_exact_substep_alignment() -> None:
    """
    The retained mode parameter must disable the anti-windup branch after the protection trips.

    This test validates:
    1. ``mode_dict`` parameters are classified as retained runtime modes.
    2. The protection can latch a future trip time and force exact EMT substep alignment.
    3. Before the trip, the anti-windup term actively modifies the integrator derivative.
    4. After the trip, the anti-windup term disappears, but the integrator remains dynamic.
    """
    vf = VarFactory()
    block, vars_map = create_antiwindup_trip_system(vf=vf)
    block.unify_blocks()

    glob_time: Var = vf.add_var("t_glob")
    static_parameter_values_mapping: Dict[Var, Const] = dict(block.parameters)
    problem = GenericEmtProblem(
        sys_block=block,
        glob_time=glob_time,
        static_parameter_values_mapping=static_parameter_values_mapping,
    )

    mode_params: List[Var] = problem.get_runtime_mode_parameters()
    assert len(mode_params) == 1
    assert mode_params[0].uid == vars_map["mode_aw_enable"].uid

    dt: float = 1.0e-3
    solver = JitSymbolicSolver(
        problem=problem,
        t0=0.0,
        t_end=3.0e-2,
        h=dt,
        method=DynamicIntegrationMethod.DaeTrapezoidal,
        verbose=False,
    )

    protection = ThresholdDelayTripWrapper(
        problem=problem,
        monitored_var=vars_map["y"],
        mode_var=vars_map["mode_aw_enable"],
        threshold=0.12,
        delay=1.5e-3,
    )

    params0 = problem.event_params_values.copy()

    t, y_hist, dy_hist, _, _ = solver.simulate(params0=params0, boundary_updater=protection)

    assert protection.tripped
    assert protection.trip_applied_time is not None
    assert protection.trip_applied_solver_time is not None

    trip_time: float = float(protection.trip_applied_time)
    trip_solver_time: float = float(protection.trip_applied_solver_time)

    assert abs((trip_time / dt) - round(trip_time / dt)) > 1.0e-9
    assert pytest.approx(trip_time, abs=1e-12) == trip_solver_time

    idx_x_i: int = problem.get_var_idx(vars_map["x_i"])
    idx_u_act: int = problem.get_var_idx(vars_map["u_act"])
    idx_y: int = problem.get_var_idx(vars_map["y"])
    idx_d_x_i: int = problem.get_diff_var_idx(vars_map["d_x_i"])

    x_i_hist: np.ndarray = y_hist[:, idx_x_i]
    u_act_hist: np.ndarray = y_hist[:, idx_u_act]
    y_hist_only: np.ndarray = y_hist[:, idx_y]
    d_x_i_hist: np.ndarray = dy_hist[:, idx_d_x_i]

    pre_idx = np.where(t <= (trip_time - dt))[0]
    post_idx = np.where(t >= (trip_time + dt))[0]

    assert pre_idx.size > 0
    assert post_idx.size > 0

    i_pre: int = int(pre_idx[-1])
    i_post: int = int(post_idx[0])

    ref: float = 1.0
    k_i: float = 200.0
    k_aw: float = 150.0

    aw_feedback_pre: float = k_aw * (x_i_hist[i_pre] - u_act_hist[i_pre])
    expected_pre: float = k_i * (ref - y_hist_only[i_pre]) - aw_feedback_pre
    expected_post: float = k_i * (ref - y_hist_only[i_post])

    assert abs(aw_feedback_pre) > 1.0e-6
    assert pytest.approx(d_x_i_hist[i_pre], abs=1e-6) == expected_pre
    assert pytest.approx(d_x_i_hist[i_post], abs=1e-6) == expected_post

    assert np.max(np.abs(d_x_i_hist[post_idx])) > 1.0e-6
    assert np.max(np.abs(np.diff(x_i_hist[post_idx]))) > 1.0e-8

    assert d_x_i_hist[i_post] > d_x_i_hist[i_pre] + 1.0

    assert np.max(y_hist_only[pre_idx]) > protection.threshold


def test_procedural_switch_reduces_newton_iterations(
        internal_ifelse_stats: Dict[str, object],
        internal_select_stats: Dict[str, object],
        procedural_stats: Dict[str, object]
) -> None:
    """
    Test that procedural mode switch reduces Newton iterations compared to embedded ifelse/select.
    """
    procedural_mean = _read_benchmark_float(
        procedural_stats,
        "mean_newton_iterations",
    )
    procedural_max = _read_benchmark_float(
        procedural_stats,
        "max_newton_iterations",
    )

    for label, stats in {
        "ifelse_internal": internal_ifelse_stats,
        "select_internal": internal_select_stats,
    }.items():
        internal_mean = _read_benchmark_float(stats, "mean_newton_iterations")
        internal_max = _read_benchmark_float(stats, "max_newton_iterations")

        assert internal_mean > 4.0 * procedural_mean, \
            f"Expected embedded {label} to require much more Newton work: internal={stats}, procedural={procedural_stats}"
        assert internal_max >= 10.0, \
            f"Expected embedded {label} to push Newton near the iteration cap: {stats}"

    assert procedural_max <= 2.0, \
        f"Expected procedural mode switch to keep Newton nearly linear per step: {procedural_stats}"


def test_procedural_switch_reduces_runtime_after_warmup(
        internal_ifelse_stats: Dict[str, object],
        internal_select_stats: Dict[str, object],
        procedural_stats: Dict[str, object]
) -> None:
    """
    Test that procedural mode switch is faster after warmup compared to embedded ifelse/select.
    """
    procedural_elapsed = _read_benchmark_float(
        procedural_stats,
        "median_elapsed_s",
    )

    for label, stats in {
        "ifelse_internal": internal_ifelse_stats,
        "select_internal": internal_select_stats,
    }.items():
        internal_elapsed = _read_benchmark_float(stats, "median_elapsed_s")

        assert procedural_elapsed < internal_elapsed, \
            f"Expected procedural mode switch to be faster after warm-up than {label}: internal={stats}, procedural={procedural_stats}"


def test_internal_select_and_ifelse_have_same_benchmark_profile(
        internal_ifelse_stats: Dict[str, object],
        internal_select_stats: Dict[str, object]
) -> None:
    """
    Test that internal select and ifelse have the same benchmark profile.
    """
    assert pytest.approx(
        _read_benchmark_float(internal_ifelse_stats, "mean_newton_iterations"),
        abs=1e-9
    ) == _read_benchmark_float(internal_select_stats, "mean_newton_iterations")
    assert pytest.approx(
        _read_benchmark_float(internal_ifelse_stats, "max_newton_iterations"),
        abs=1e-9
    ) == _read_benchmark_float(internal_select_stats, "max_newton_iterations")
