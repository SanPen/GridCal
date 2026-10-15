"""Tests for the symbolic explicit-initialization workflow used by RMS problems."""

import numpy as np
import pytest
import scipy.sparse as sp

from VeraGridEngine.Simulations.Rms.problems.rms_problem_template import RmsProblemTemplate
from VeraGridEngine.Simulations.Rms.problems.rms_problem_template import project_initial_algebraic_state
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.explicit_initialization_symbolic import (
    ExplicitInitializationResult,
    SelfImplicitSolveResult,
    build_explicit_external_uid_values,
    build_explicit_init_graph,
    build_symbolic_vector_single_equation_compiler,
    evaluate_explicit_init_equation,
    init_explicit_common,
    solve_self_implicit,
)
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
from VeraGridEngine.Utils.procedural_logic import fixed_sample, flipflop, hard_saturation, sampled_value
from VeraGridEngine.enumerations import SelfImplicitSolveStatus


def evaluate_zero_self_implicit_equation(
        x: np.ndarray,
        dx: np.ndarray,
        event_params: np.ndarray,
        params: np.ndarray,
) -> float:
    """Return an exact zero self-implicit solution for black-start coverage.

    :param x: State and algebraic values.
    :param dx: Differential values.
    :param event_params: Runtime parameter values.
    :param params: Constant parameter values.
    :return: Exact zero equation value.
    """
    _unused_x: np.ndarray = x
    _unused_dx: np.ndarray = dx
    _unused_event_params: np.ndarray = event_params
    _unused_params: np.ndarray = params
    return 0.0


def evaluate_singular_self_implicit_equation(
        x: np.ndarray,
        dx: np.ndarray,
        event_params: np.ndarray,
        params: np.ndarray,
) -> float:
    """Return an equation whose fixed-point residual is always one.

    :param x: State and algebraic values.
    :param dx: Differential values.
    :param event_params: Runtime parameter values.
    :param params: Constant parameter values.
    :return: Current target value plus one.
    """
    _unused_dx: np.ndarray = dx
    _unused_event_params: np.ndarray = event_params
    _unused_params: np.ndarray = params
    return float(x[0] + 1.0)


def evaluate_non_finite_self_implicit_equation(
        x: np.ndarray,
        dx: np.ndarray,
        event_params: np.ndarray,
        params: np.ndarray,
) -> float:
    """Return a non-finite equation value for failure-path coverage.

    :param x: State and algebraic values.
    :param dx: Differential values.
    :param event_params: Runtime parameter values.
    :param params: Constant parameter values.
    :return: ``NaN``.
    """
    _unused_x: np.ndarray = x
    _unused_dx: np.ndarray = dx
    _unused_event_params: np.ndarray = event_params
    _unused_params: np.ndarray = params
    return float("nan")


def evaluate_quadratic_self_implicit_equation(
        x: np.ndarray,
        dx: np.ndarray,
        event_params: np.ndarray,
        params: np.ndarray,
) -> float:
    """Return a nonlinear equation used to exhaust a one-step secant budget.

    :param x: State and algebraic values.
    :param dx: Differential values.
    :param event_params: Runtime parameter values.
    :param params: Constant parameter values.
    :return: Square of the current target value.
    """
    _unused_dx: np.ndarray = dx
    _unused_event_params: np.ndarray = event_params
    _unused_params: np.ndarray = params
    return float(x[0] * x[0])


class DirectAlgebraicProjectionProblem(RmsProblemTemplate):
    """Minimal RMS problem exposing one direct algebraic constraint."""

    __slots__ = ()

    def get_states_number(self) -> int:
        """Return the single fixed state count.

        :return: One state variable.
        """
        return 1

    def rhs_algebraic(self, values: np.ndarray, diff_values: np.ndarray) -> np.ndarray:
        """Evaluate ``algebraic - 2 * state``.

        :param values: State and algebraic values.
        :param diff_values: Unused differential values.
        :return: Single algebraic residual.
        """
        _unused_diff_values: np.ndarray = diff_values
        return np.array([values[1] - 2.0 * values[0]], dtype=float)

    def get_j22(
            self,
            x: np.ndarray,
            dx: np.ndarray,
            h: float,
    ) -> sp.csc_matrix:
        """Return the algebraic Jacobian.

        :param x: Unused state and algebraic values.
        :param dx: Unused differential values.
        :param h: Unused integration step.
        :return: Unit sparse Jacobian.
        """
        _unused_x: np.ndarray = x
        _unused_dx: np.ndarray = dx
        _unused_h: float = h
        return sp.csc_matrix(np.array([[1.0]], dtype=float))


def test_direct_algebraic_dependency_precedes_explicit_initialization() -> None:
    """Resolve an algebraic bridge before an ``inc``-style state seed.

    :return: None.
    """
    physical_signal: Var = Var("physical_signal")
    algebraic_bridge: Var = Var("algebraic_bridge")
    controller_state: Var = Var("controller_state")
    block: Block = Block(
        state_vars=list((controller_state,)),
        state_eqs=list((Const(0.0),)),
        algebraic_vars=list((physical_signal, algebraic_bridge)),
        algebraic_eqs=list((algebraic_bridge - physical_signal,)),
        init_eqs=dict((
            (physical_signal, Const(0.275)),
            (controller_state, algebraic_bridge),
        )),
        name="Direct algebraic initialization dependency",
    )

    init_vars: dict[Var, Expr | Const]
    dependencies: dict[Var, list[Var]]
    topological_order: list[Var]
    init_events: dict[Var, Expr | Const]
    init_vars, dependencies, topological_order, init_events = build_explicit_init_graph(mdl=block)

    assert init_vars[algebraic_bridge] is physical_signal
    assert dependencies[algebraic_bridge] == list((physical_signal,))
    assert topological_order.index(physical_signal) < topological_order.index(algebraic_bridge)
    assert topological_order.index(algebraic_bridge) < topological_order.index(controller_state)
    assert len(init_events) == 0


def test_sampled_mode_source_selects_explicit_initialization_branch() -> None:
    """Evaluate a sampled mode source before a dependent state initializer.

    :return: None.
    """
    selected_output: Var = Var("selected_output")
    sampled_mode: Var = Var("sampled_mode")
    controller_state: Var = Var("controller_state")
    block: Block = Block(
        state_vars=list((controller_state,)),
        state_eqs=list((Const(0.0),)),
        algebraic_vars=list((selected_output,)),
        algebraic_eqs=list((selected_output - Const(1.0),)),
        init_eqs=dict(((controller_state, sampled_mode * Const(2.0)),)),
        mode_dict=dict(((sampled_mode, Const(0.0)),)),
        procedural_logic=list((
            sampled_value(
                output=sampled_mode,
                source=selected_output,
            ),
        )),
        name="Sampled mode initialization dependency",
    )

    init_vars: dict[Var, Expr | Const]
    dependencies: dict[Var, list[Var]]
    topological_order: list[Var]
    init_events: dict[Var, Expr | Const]
    init_vars, dependencies, topological_order, init_events = build_explicit_init_graph(mdl=block)

    selected_output_equation: Expr | Const = init_vars[selected_output]
    assert isinstance(selected_output_equation, Const)
    assert selected_output_equation.value == 1.0
    assert init_vars[sampled_mode] is selected_output
    assert dependencies[sampled_mode] == list((selected_output,))
    assert topological_order.index(selected_output) < topological_order.index(sampled_mode)
    assert topological_order.index(sampled_mode) < topological_order.index(controller_state)
    assert init_events[sampled_mode] is selected_output


def test_deterministic_procedural_outputs_join_explicit_initialization_graph() -> None:
    """Resolve sampled, saturation and latch outputs before dependent states.

    :return: None.
    """
    measured_value: Var = Var("measured_value")
    sampled_condition: Var = Var("sampled_condition")
    saturated_value: Var = Var("saturated_value")
    latched_condition: Var = Var("latched_condition")
    controller_state: Var = Var("controller_state")
    block: Block = Block(
        state_vars=list((controller_state,)),
        state_eqs=list((Const(0.0),)),
        algebraic_vars=list((measured_value,)),
        algebraic_eqs=list((measured_value - Const(2.0),)),
        init_eqs=dict(((controller_state, sampled_condition + saturated_value + latched_condition),)),
        mode_dict=dict((
            (sampled_condition, Const(0.0)),
            (saturated_value, Const(0.0)),
            (latched_condition, Const(0.0)),
        )),
        procedural_logic=list((
            fixed_sample(output=sampled_condition, when=measured_value),
            hard_saturation(
                output=saturated_value,
                u=measured_value,
                # The runtime implementation accepts inverted limits by sorting
                # them. Explicit initialization must use the same semantics.
                u_min=Const(1.0),
                u_max=Const(-1.0),
            ),
            flipflop(
                boolset=measured_value,
                boolreset=measured_value < Const(0.0),
                output=latched_condition,
            ),
        )),
        name="Deterministic procedural initialization",
    )

    init_vars: dict[Var, Expr | Const]
    dependencies: dict[Var, list[Var]]
    topological_order: list[Var]
    init_events: dict[Var, Expr | Const]
    init_vars, dependencies, topological_order, init_events = build_explicit_init_graph(mdl=block)

    evaluation_values: dict[int, float] = dict(((measured_value.uid, 2.0),))
    assert init_vars[sampled_condition].eval_uid(evaluation_values) == 1.0
    assert init_vars[saturated_value].eval_uid(evaluation_values) == 1.0
    assert init_vars[latched_condition].eval_uid(evaluation_values) == 1.0
    below_boolean_threshold_values: dict[int, float] = dict(((measured_value.uid, 0.25),))
    assert init_vars[sampled_condition].eval_uid(below_boolean_threshold_values) == 0.0
    assert init_vars[latched_condition].eval_uid(below_boolean_threshold_values) == 0.0
    assert dependencies[sampled_condition] == list((measured_value,))
    assert dependencies[saturated_value] == list((measured_value,))
    assert dependencies[latched_condition] == list((measured_value,))
    assert topological_order.index(measured_value) < topological_order.index(sampled_condition)
    assert topological_order.index(measured_value) < topological_order.index(saturated_value)
    assert topological_order.index(measured_value) < topological_order.index(latched_condition)
    assert topological_order.index(sampled_condition) < topological_order.index(controller_state)
    assert topological_order.index(saturated_value) < topological_order.index(controller_state)
    assert topological_order.index(latched_condition) < topological_order.index(controller_state)
    assert init_events[sampled_condition] is init_vars[sampled_condition]
    assert init_events[saturated_value] is init_vars[saturated_value]
    assert init_events[latched_condition] is init_vars[latched_condition]


def test_direct_algebraic_initialization_preserves_external_seed() -> None:
    """Consume a power-flow seed without replacing it from a direct residual.

    :return: None.
    """
    physical_power: Var = Var("physical_power")
    measured_power: Var = Var("measured_power")
    controller_state: Var = Var("controller_state")
    block: Block = Block(
        state_vars=list((controller_state,)),
        state_eqs=list((Const(0.0),)),
        algebraic_vars=list((physical_power, measured_power)),
        algebraic_eqs=list((
            physical_power - Const(0.0),
            measured_power - physical_power,
        )),
        init_eqs=dict(((controller_state, measured_power),)),
        name="Externally seeded physical power",
    )

    init_vars: dict[Var, Expr | Const]
    dependencies: dict[Var, list[Var]]
    topological_order: list[Var]
    init_events: dict[Var, Expr | Const]
    init_vars, dependencies, topological_order, init_events = build_explicit_init_graph(
        mdl=block,
        preserved_var_uids=set((physical_power.uid,)),
    )

    assert physical_power not in init_vars
    assert init_vars[measured_power] is physical_power
    assert dependencies[measured_power] == list()
    assert topological_order.index(measured_power) < topological_order.index(controller_state)
    assert len(init_events) == 0


def test_direct_algebraic_back_edge_remains_an_external_boundary_seed() -> None:
    """Reject an inferred terminal equation that closes a legacy EMT cycle.

    Historical PI-line models initialize the internal series current from a
    terminal current. The DAE also computes that terminal current from the same
    series current. The terminal equation is a valid runtime residual, but it
    must remain outside the explicit graph so the operating-point seed breaks
    the otherwise artificial two-equation cycle.

    :return: None.
    """
    terminal_current: Var = Var("if_Pi_A")
    series_current: Var = Var("i_ser_Pi_A")
    capacitor_current: Var = Var("i_cap_f_Pi_A")
    block: Block = Block(
        state_vars=list((series_current,)),
        state_eqs=list((Const(0.0),)),
        algebraic_vars=list((terminal_current, capacitor_current)),
        algebraic_eqs=list((
            terminal_current - (series_current + capacitor_current),
        )),
        init_eqs=dict((
            (series_current, terminal_current - capacitor_current),
            (capacitor_current, Const(0.0)),
        )),
        name="Legacy PI-line terminal initialization",
    )

    init_vars: dict[Var, Expr | Const]
    dependencies: dict[Var, list[Var]]
    topological_order: list[Var]
    init_events: dict[Var, Expr | Const]
    init_vars, dependencies, topological_order, init_events = build_explicit_init_graph(
        mdl=block,
    )

    assert terminal_current not in init_vars
    assert dependencies[series_current] == list((capacitor_current,))
    assert topological_order.index(capacitor_current) < topological_order.index(series_current)
    assert len(init_events) == 0


def test_explicit_initialization_binds_external_time_by_exact_uid() -> None:
    """Evaluate an imported ``time()`` expression at the RMS startup instant.

    :return: None.
    """
    global_time: Var = Var("glob_time")
    sampled_time: Var = Var("sampled_time")
    block: Block = Block(
        algebraic_vars=list((sampled_time,)),
        algebraic_eqs=list((sampled_time - global_time,)),
        name="External startup time",
    )
    external_uid_values: dict[int, float] = build_explicit_external_uid_values(
        mdl=block,
        external_name_values=dict((("glob_time", 0.0),)),
    )

    assert external_uid_values == dict(((global_time.uid, 0.0),))
    result: float | int | complex | None = evaluate_explicit_init_equation(
        eq=global_time,
        event_params_array=np.zeros(0, dtype=float),
        x=np.zeros(1, dtype=float),
        params_array=np.zeros(0, dtype=float),
        dx=np.zeros(0, dtype=float),
        uid2idx_event_params=dict(),
        uid2idx_vars=dict(((sampled_time.uid, 0),)),
        uid2idx_params=dict(),
        uid2idx_diff=dict(),
        external_uid_values=external_uid_values,
    )
    assert result == 0.0


def test_initial_algebraic_projection_preserves_states() -> None:
    """Project algebraics without changing explicitly initialized states.

    :return: None.
    """
    problem: DirectAlgebraicProjectionProblem = DirectAlgebraicProjectionProblem()
    initial_values: np.ndarray = np.array([3.0, 0.0], dtype=float)
    differential_values: np.ndarray = np.zeros(0, dtype=float)
    projected_values: np.ndarray
    converged: bool
    residual_inf: float

    projected_values, converged, residual_inf = project_initial_algebraic_state(
        problem=problem,
        initial_values=initial_values,
        differential_values=differential_values,
        tolerance=1.0e-12,
        max_iter=5,
    )

    assert converged
    assert residual_inf <= 1.0e-12
    assert projected_values[0] == 3.0
    assert projected_values[1] == 6.0


def test_self_implicit_solver_preserves_exact_black_start_zero() -> None:
    """Accept an exact zero fixed point without perturbing its black-start seed.

    :return: None.
    """
    values: np.ndarray = np.zeros(1, dtype=float)
    differential_values: np.ndarray = np.zeros(0, dtype=float)
    event_parameters: np.ndarray = np.zeros(0, dtype=float)
    constant_parameters: np.ndarray = np.zeros(0, dtype=float)
    result: SelfImplicitSolveResult = solve_self_implicit(
        eq_fn=evaluate_zero_self_implicit_equation,
        x=values,
        dx=differential_values,
        target_idx=0,
        target_array=values,
        event_params_array=event_parameters,
        params_array=constant_parameters,
    )

    assert result.converged
    assert result.status == SelfImplicitSolveStatus.CONVERGED
    assert result.value == 0.0
    assert result.residual == 0.0
    assert result.iterations == 0
    assert values[0] == 0.0


def test_self_implicit_solver_reports_singular_secant_and_restores_seed() -> None:
    """Reject a flat fixed-point residual without committing its last candidate.

    :return: None.
    """
    original_value: float = 0.25
    values: np.ndarray = np.array([original_value], dtype=float)
    result: SelfImplicitSolveResult = solve_self_implicit(
        eq_fn=evaluate_singular_self_implicit_equation,
        x=values,
        dx=np.zeros(0, dtype=float),
        target_idx=0,
        target_array=values,
        event_params_array=np.zeros(0, dtype=float),
        params_array=np.zeros(0, dtype=float),
    )

    assert not result.converged
    assert result.status == SelfImplicitSolveStatus.SINGULAR_SECANT
    assert result.residual == 1.0
    assert values[0] == original_value


def test_self_implicit_solver_reports_non_finite_residual_and_restores_seed() -> None:
    """Reject a non-finite residual without corrupting the target array.

    :return: None.
    """
    original_value: float = -0.5
    values: np.ndarray = np.array([original_value], dtype=float)
    result: SelfImplicitSolveResult = solve_self_implicit(
        eq_fn=evaluate_non_finite_self_implicit_equation,
        x=values,
        dx=np.zeros(0, dtype=float),
        target_idx=0,
        target_array=values,
        event_params_array=np.zeros(0, dtype=float),
        params_array=np.zeros(0, dtype=float),
    )

    assert not result.converged
    assert result.status == SelfImplicitSolveStatus.NON_FINITE_RESIDUAL
    assert np.isinf(result.residual)
    assert values[0] == original_value


def test_self_implicit_solver_reports_iteration_limit_and_restores_seed() -> None:
    """Reject a candidate when the configured secant budget is exhausted.

    :return: None.
    """
    original_value: float = 0.5
    values: np.ndarray = np.array([original_value], dtype=float)
    result: SelfImplicitSolveResult = solve_self_implicit(
        eq_fn=evaluate_quadratic_self_implicit_equation,
        x=values,
        dx=np.zeros(0, dtype=float),
        target_idx=0,
        target_array=values,
        event_params_array=np.zeros(0, dtype=float),
        params_array=np.zeros(0, dtype=float),
        max_iter=1,
    )

    assert not result.converged
    assert result.status == SelfImplicitSolveStatus.MAX_ITERATIONS
    assert result.iterations == 1
    assert values[0] == original_value


def test_common_explicit_initialization_is_transactional_on_self_implicit_failure() -> None:
    """Keep caller-owned guesses unchanged after a failed scalar solve.

    :return: None.
    """
    state: Var = Var("self_implicit_state")
    block: Block = Block(
        state_vars=list((state,)),
        state_eqs=list((Const(0.0),)),
        init_eqs=dict(((state, state + Const(1.0)),)),
        name="Singular self-implicit initializer",
    )
    initial_value: float = 0.25
    init_guess: dict[int, float | int | complex | None] = dict(((state.uid, initial_value),))
    diff_init_guess: dict[int, float | int | complex | None] = dict()
    event_param_init_dict: dict[int, float | int | complex | None] = dict()
    event_parameter_equations: list[Expr | Const] = list()
    result: ExplicitInitializationResult = init_explicit_common(
        mdl=block,
        sys_vars=dict(((state.uid, state),)),
        sys_diff_vars=dict(),
        variable_parameters=list(),
        event_parameters_eqs=event_parameter_equations,
        constant_parameters=list(),
        init_guess=init_guess,
        event_param_init_dict=event_param_init_dict,
        diff_init_guess=diff_init_guess,
        uid2idx_vars=dict(((state.uid, 0),)),
        uid2idx_diff=dict(),
        uid2idx_params=dict(),
        uid2idx_event_params=dict(),
        params_array=np.zeros(0, dtype=float),
        compile_single_equation=build_symbolic_vector_single_equation_compiler(
            compiler_names_dict=dict(((state.uid, "x[0]"),)),
            alias_names_dict=dict(((state.uid, "x_0"),)),
            vars_name="x",
            diff_name="dx",
            event_params_name="event_params",
            params_name="params",
        ),
    )

    assert not result.converged
    assert result.failed_variable is state
    assert result.self_implicit_result is not None
    assert result.self_implicit_result.status == SelfImplicitSolveStatus.SINGULAR_SECANT
    assert result.init_guess[state.uid] == initial_value
    assert init_guess[state.uid] == initial_value
    assert len(diff_init_guess) == 0
    assert len(event_param_init_dict) == 0
    assert len(event_parameter_equations) == 0


def test_explicit_initialization_result_preserves_legacy_tuple_unpacking() -> None:
    """Keep legacy phasor and TensyGrid callers unchanged on successful solves.

    :return: None.
    """
    init_guess: dict[int, float | int | complex | None] = dict(((1, 2.0),))
    diff_init_guess: dict[int, float | int | complex | None] = dict(((3, 4.0),))
    result: ExplicitInitializationResult = ExplicitInitializationResult(
        init_guess=init_guess,
        diff_init_guess=diff_init_guess,
        converged=True,
        failed_variable=None,
        self_implicit_result=None,
        message="Explicit initialization completed successfully.",
    )
    unpacked_init_guess: dict[int, float | int | complex | None]
    unpacked_diff_init_guess: dict[int, float | int | complex | None]
    unpacked_init_guess, unpacked_diff_init_guess = result

    assert unpacked_init_guess is init_guess
    assert unpacked_diff_init_guess is diff_init_guess


def test_explicit_initialization_result_rejects_failed_legacy_tuple_unpacking() -> None:
    """Prevent an unchanged legacy caller from accepting a failed result.

    :return: None.
    """
    result: ExplicitInitializationResult = ExplicitInitializationResult(
        init_guess=dict(),
        diff_init_guess=dict(),
        converged=False,
        failed_variable=None,
        self_implicit_result=None,
        message="Expected explicit-initialization failure.",
    )

    with pytest.raises(RuntimeError, match="Expected explicit-initialization failure"):
        list(result)
