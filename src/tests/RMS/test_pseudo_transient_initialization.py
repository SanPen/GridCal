from __future__ import annotations

import numpy as np
import pytest

import VeraGridEngine.api as gce
from VeraGridEngine.Simulations.Rms.rms_driver import RmsSimulationDriver
from VeraGridEngine.Simulations.Rms.rms_problem_factory import build_rms_problem
from VeraGridEngine.Simulations.Rms.problems.rms_problem_template import RmsProblemTemplate
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae_vectorized import RmsProblemDaeVec
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae_full_vectorized import RmsProblemDaeFullVec
from VeraGridEngine.Simulations.Rms.initialization import PseudoTransientInitProblem, init_pseudo_transient
from VeraGridEngine.Simulations.Rms.numerical.pseudo_transient import PseudoTransient, PseudoTransientOptions
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Expr, Const, log
from tests.RMS.test_rms_terminal_power_assembly import build_supported_vectorized_ac_load_case
from VeraGridEngine.Templates.Rms.genqec_exc_gov_sat_template import get_complete_generator_template_rms
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.load_rms_template import get_load_rms_template
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.block_helpers import to_explicit
from VeraGridEngine.Utils.Symbolic.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_rms_model
from VeraGridEngine.basic_structures import Vec
from VeraGridEngine.enumerations import DynamicIntegrationMethod
from VeraGridEngine.enumerations import RmsInitializationMethod, RmsProblemTypes, VarPowerFlowReferenceType


@pytest.mark.parametrize("seed,bistable,invalid_rhs,invalid_update", (
    (-2.0, True, False, False), (2.0, True, False, False),
    (7.0, False, False, False), (None, False, False, False),
    (np.nan, False, False, False), (-1.0, False, True, False),
    (0.0, False, False, True),
))
def test_local_pseudo_transient_uses_supplied_seed_before_random_retry(
        seed: float | None, bistable: bool, invalid_rhs: bool, invalid_update: bool) -> None:
    """Use real native solves to distinguish first seeds from random backups.

    :param seed: Supplied state value, or no supplied value for ``None``.
    :param bistable: Use two exact equilibria to identify the selected branch.
    :param invalid_rhs: Put the first seed outside a logarithmic residual's domain.
    :param invalid_update: Put the first seed at a reciprocal reference's pole.
    :return: None; verify branch, unfreezing, random backup and source/writeback.
    """
    state: Var = Var("seeded_state")
    reference: Var = Var("computed_reference")
    equation: Expr
    expected_state: float
    if bistable:
        equation = (state - Const(2.0)) * (state + Const(2.0))
        assert seed is not None
        expected_state = float(seed)
    elif invalid_rhs:
        equation = -log(state)
        expected_state = 1.0
    else:
        equation = Const(3.0) - state
        expected_state = 3.0

    # Allocate the known source declarations before constructing the block.
    # The optional reference remains source Const(None) after runtime recovery.
    algebraic_variables: list[Var] = list((reference,)) if invalid_update else list()
    algebraic_equations: list[Expr] = list((reference - Const(1.0) / state,)) if invalid_update else list()
    model: Block = Block(state_vars=list((state,)), state_eqs=list((equation,)),
        algebraic_vars=algebraic_variables, algebraic_eqs=algebraic_equations,
        event_dict=dict(((reference, Const(None)),)) if invalid_update else dict())
    seeds: dict[int, float] = dict()
    if seed is not None:
        seeds[state.uid] = float(seed)
    else:
        pass
    names: dict[int, str] = dict(((state.uid, "x[0]"),))
    aliases: dict[int, str] = dict(((state.uid, "state"),))
    if invalid_update:
        names[reference.uid] = "events[0]"
        aliases[reference.uid] = "reference"
    else:
        pass
    event_equations: list[Expr | Const] = list((Const(None),)) if invalid_update else list()
    rng_before: tuple[str, np.ndarray, int, int, float] = np.random.get_state()
    solved: dict[int, float] = init_pseudo_transient(
        mdl=model, sys_vars=dict(((state.uid, state),)),
        variable_parameters=list((reference,)) if invalid_update else list(),
        event_parameters_eqs=event_equations, constant_parameters=list(), init_guess=seeds,
        uid2idx_vars=dict(((state.uid, 0),)), uid2idx_params=dict(),
        uid2idx_event_params=dict(((reference.uid, 0),)) if invalid_update else dict(),
        compiler_names_dict=names, alias_names_dict=aliases, VARIABLE_PARAMS_NAME="events",
        TIME_NAME="glob_time", VARS_NAME="x", DIFF_NAME="dx", CONSTANT_PARAMS_NAME="parameters",
        tol=1e-8, pseudo_transient_options=PseudoTransientOptions(equilibrium_references_as_params=True))
    rng_after: tuple[str, np.ndarray, int, int, float] = np.random.get_state()
    random_consumed: bool = (rng_before[0] != rng_after[0]
        or not np.array_equal(rng_before[1], rng_after[1]) or rng_before[2:] != rng_after[2:])
    if invalid_rhs or invalid_update:
        assert random_consumed
    else:
        # A successful supplied or structural-zero candidate must not touch
        # the existing random state. No global RNG reseeding or patch is used.
        assert not random_consumed
    assert solved[state.uid] == pytest.approx(expected_state, abs=1e-8)
    assert seeds[state.uid] == solved[state.uid]
    assert model.state_eqs[0] is equation
    if invalid_update:
        assert isinstance(event_equations[0], Const)
        assert event_equations[0].value == pytest.approx(1.0 / solved[state.uid], abs=1e-8)
        assert model.algebraic_eqs[0] is algebraic_equations[0]
        assert isinstance(model.event_dict[reference], Const)
        assert model.event_dict[reference].value is None
    else:
        assert len(model.algebraic_vars) == 0


@pytest.mark.parametrize("update_inputs,update_references,references_as_equations", (
    (False, False, False), (True, False, False), (False, True, False),
    (True, True, False), (True, True, True),
))
def test_local_pseudo_transient_jacobian_matches_equilibrium_updates(
        update_inputs: bool, update_references: bool, references_as_equations: bool) -> None:
    """Differentiate the native composed residual and preserve evaluation state.

    :param update_inputs: Prepare the input as the original reference squared.
    :param update_references: Prepare the reference as state plus prepared input.
    :param references_as_equations: Disable preparation and append its constraint.
    :return: None; verify exact derivatives, consumers and final reference writeback.
    """
    state: Var = Var("state")
    reference: Var = Var("reference")
    input_var: Var = Var("input")
    model: Block = Block(
        state_vars=list((state,)), state_eqs=list((state - input_var,)),
        algebraic_vars=list((reference,)), algebraic_eqs=list((reference - state - input_var,)),
        in_vars=list((input_var,)), event_dict=dict(((input_var, Const(3.0)),)))
    options: PseudoTransientOptions = PseudoTransientOptions(
        equilibrium_inputs_as_params=update_inputs,
        equilibrium_references_as_params=update_references,
        equilibrium_references_as_equations=references_as_equations)
    problem: PseudoTransientInitProblem = PseudoTransientInitProblem(
        block=model, x_global=np.asarray((1.0, 2.0, 3.0)),
        compiler_names_dict=dict(((state.uid, "x[0]"), (reference.uid, "x[1]"), (input_var.uid, "x[2]"))),
        alias_names_dict=dict(((state.uid, "state"), (reference.uid, "reference"), (input_var.uid, "input"))),
        uid2idx_vars=dict(((state.uid, 0), (reference.uid, 1), (input_var.uid, 2))),
        variable_parameters=list((input_var,)), constant_parameters=list(),
        ordered_init_update_eqs=dict(((input_var, reference * reference),)),
        equilibrium_reference_update_eqs=dict(((reference, state + input_var),)) if update_references else dict(),
        pseudo_transient_options=options, VARS_NAME="x")
    solver: PseudoTransient = PseudoTransient(
        problem=problem, h=1.0, dtau0=1.0, tol=1e-8, max_iter=10,
        reference_error_tol=-1.0, options=options)
    values: np.ndarray = np.asarray((1.0, 2.0))
    derivatives: np.ndarray = np.zeros(problem.get_diff_var_number())
    # An intentional prior preparation supplies nonempty reference lookup and
    # different mutable input contents for the subsequent observational calls.
    problem.update_equilibrium_parameters(np.asarray((-1.0, 3.0)))
    parameters_before: np.ndarray = problem._variable_parameters_values.copy()
    references_before: dict[str, float] = problem._equilibrium_reference_values.copy()
    parameters_owner: np.ndarray = problem._variable_parameters_values
    references_owner: dict[str, float] = problem._equilibrium_reference_values
    active_input: bool = update_inputs and not references_as_equations
    active_reference: bool = update_references and not references_as_equations
    expected_input: float = 4.0 if active_input else 3.0
    expected_reference: float = 1.0 + expected_input if active_reference else 2.0
    row_count: int = 3 if references_as_equations else 2
    expected: np.ndarray = np.empty(row_count)
    expected[0] = 1.0 - expected_input
    expected[1] = expected_reference - 1.0 - expected_input
    expected_jacobian: np.ndarray = np.zeros((row_count, 2))
    expected_jacobian[0, :] = (1.0, -4.0 if active_input else 0.0)
    if active_reference:
        expected_jacobian[1, :] = (0.0, 0.0)
    else:
        expected_jacobian[1, :] = (-1.0, -3.0 if active_input else 1.0)
    if references_as_equations:
        expected[2] = -2.0
        expected_jacobian[2, :] = (-1.0, 1.0)
    else:
        pass

    # Compare both component orders and repeats to a separately derived target.
    # Saved outputs must survive later calls to the reusable compiled buffers.
    repetition: int
    for repetition in range(3):
        algebraic_first: np.ndarray = problem.rhs_algebraic(values, derivatives)
        state_second: np.ndarray = problem.rhs_state(values, derivatives)
        state_first: np.ndarray = problem.rhs_state(values, derivatives)
        algebraic_second: np.ndarray = problem.rhs_algebraic(values, derivatives)
        np.testing.assert_allclose(np.concatenate((state_second, algebraic_first)), expected, atol=1e-12)
        np.testing.assert_allclose(np.concatenate((state_first, algebraic_second)), expected, atol=1e-12)
        np.testing.assert_allclose(solver._rhs_steady(values, derivatives), expected, atol=1e-12)
        pseudo_expected: np.ndarray = expected.copy()
        pseudo_expected[0] *= -1.0
        np.testing.assert_allclose(solver._rhs_pseudo_transient(values, values.copy(), derivatives, 0.5),
                                   pseudo_expected, atol=1e-12)
        jacobian: np.ndarray = problem._compute_numerical_jacobian(values, derivatives, 1.0).toarray()
        np.testing.assert_allclose(jacobian, expected_jacobian, atol=1e-9, rtol=1e-9)
        np.testing.assert_allclose(solver._jacobian_steady(values, derivatives).toarray(),
                                   expected_jacobian, atol=1e-9, rtol=1e-9)
        direction: np.ndarray = np.asarray((0.3, -0.7))
        probe_step: float = 2e-5
        direction_rhs: np.ndarray = (
            problem._compute_rhs_full(values + probe_step * direction, derivatives, 1.0)
            - problem._compute_rhs_full(values - probe_step * direction, derivatives, 1.0)
        ) / (2.0 * probe_step)
        np.testing.assert_allclose(jacobian @ direction, direction_rhs, atol=1e-9, rtol=1e-9)
        np.testing.assert_array_equal(values, np.asarray((1.0, 2.0)))
        np.testing.assert_array_equal(derivatives, np.zeros(problem.get_diff_var_number()))
        np.testing.assert_array_equal(parameters_owner, parameters_before)
        assert references_owner == references_before
        assert problem._variable_parameters_values is parameters_owner
        assert problem._equilibrium_reference_values is references_owner

    if active_input or active_reference:
        # Native signature rejection happens in the full residual after the
        # preparation stages; no replacement function or mocked solver is used.
        with pytest.raises(TypeError):
            problem._compute_rhs_full(values, np.asarray(("invalid derivative",)), 1.0)
        np.testing.assert_array_equal(parameters_owner, parameters_before)
        assert references_owner == references_before
        np.testing.assert_array_equal(values, np.asarray((1.0, 2.0)))
    else:
        # The inactive compiled path must retain its established exact values.
        assert problem._jacobian_fn is not None
        np.testing.assert_array_equal(jacobian, problem._jacobian_fn(
            values, derivatives, parameters_owner, problem._constant_params, 1.0).toarray())

    if update_inputs and update_references and not references_as_equations:
        # Use a declared derivative that the residual actually reads. Holding
        # dx=0.5 gives f=s-u+0.5*s and df/ds=1.5; silently zeroing dx would fail.
        derivative: Var = Var("declared derivative", base_var=state)
        derivative_model: Block = Block(
            state_vars=list((state,)), state_eqs=list((state - input_var + derivative * state,)),
            diff_vars=list((derivative,)), algebraic_vars=list((reference,)),
            algebraic_eqs=list((reference - state - input_var,)), in_vars=list((input_var,)),
            event_dict=dict(((input_var, Const(3.0)),)))
        derivative_problem: PseudoTransientInitProblem = PseudoTransientInitProblem(
            block=derivative_model, x_global=np.asarray((1.0, 2.0, 3.0)),
            compiler_names_dict=dict(((state.uid, "x[0]"), (reference.uid, "x[1]"),
                                      (input_var.uid, "x[2]"), (derivative.uid, "dx[0]"))),
            alias_names_dict=dict(((state.uid, "state"), (reference.uid, "reference"),
                                   (input_var.uid, "input"), (derivative.uid, "derivative"))),
            uid2idx_vars=dict(((state.uid, 0), (reference.uid, 1), (input_var.uid, 2))),
            variable_parameters=list((input_var,)), constant_parameters=list(),
            ordered_init_update_eqs=dict(((input_var, reference * reference),)),
            equilibrium_reference_update_eqs=dict(((reference, state + input_var),)),
            pseudo_transient_options=options, VARS_NAME="x", DIFF_NAME="dx")
        derivative_problem.update_equilibrium_parameters(np.asarray((-1.0, 3.0)))
        derivative_parameters: np.ndarray = derivative_problem._variable_parameters_values.copy()
        derivative_references: dict[str, float] = derivative_problem._equilibrium_reference_values.copy()
        fixed_derivatives: np.ndarray = np.asarray((0.5,))
        assert derivative_problem.get_diff_var_number() == 1
        derivative_rhs: np.ndarray = derivative_problem._compute_rhs_full(values, fixed_derivatives, 1.0)
        np.testing.assert_allclose(derivative_rhs, np.asarray((-2.5, 0.0)), atol=1e-12)
        derivative_jacobian: np.ndarray = derivative_problem._compute_numerical_jacobian(
            values, fixed_derivatives, 1.0).toarray()
        np.testing.assert_allclose(derivative_jacobian, np.asarray(((1.5, -4.0), (0.0, 0.0))),
                                   atol=1e-9, rtol=1e-9)
        np.testing.assert_allclose(
            (derivative_problem._compute_rhs_full(values + probe_step * direction, fixed_derivatives, 1.0)
             - derivative_problem._compute_rhs_full(values - probe_step * direction, fixed_derivatives, 1.0))
            / (2.0 * probe_step), derivative_jacobian @ direction, atol=1e-9, rtol=1e-9)
        derivative_solver: PseudoTransient = PseudoTransient(
            problem=derivative_problem, h=1.0, dtau0=1.0, tol=1e-8, max_iter=10,
            reference_error_tol=-1.0, options=options)
        np.testing.assert_allclose(derivative_solver._rhs_steady(values, fixed_derivatives),
                                   derivative_rhs, atol=1e-12)
        # PTC deliberately evaluates the steady residual at zero dx; retain
        # that native convention while separately testing the fixed-dx getter.
        np.testing.assert_allclose(derivative_solver._rhs_pseudo_transient(
            values, values.copy(), fixed_derivatives, 0.5), np.asarray((3.0, 0.0)), atol=1e-12)
        np.testing.assert_array_equal(fixed_derivatives, np.asarray((0.5,)))
        np.testing.assert_array_equal(values, np.asarray((1.0, 2.0)))
        np.testing.assert_array_equal(derivative_problem._variable_parameters_values, derivative_parameters)
        assert derivative_problem._equilibrium_reference_values == derivative_references

        # Exercise actual initializer completion with an independently known
        # equilibrium and unresolved runtime reference: state=3, reference=9.
        stable_state: Var = Var("stable state")
        computed_reference: Var = Var("computed reference")
        stable_expression: Expr = Const(3.0) - stable_state
        reference_expression: Expr = computed_reference - stable_state * stable_state
        stable_model: Block = Block(
            state_vars=list((stable_state,)), state_eqs=list((stable_expression,)),
            algebraic_vars=list((computed_reference,)), algebraic_eqs=list((reference_expression,)),
            event_dict=dict(((computed_reference, Const(None)),)))
        seeds: dict[int, float] = dict(((stable_state.uid, 1.0),))
        event_equations: list[Expr | Const] = list((Const(None),))
        solved: dict[int, float] = init_pseudo_transient(
            mdl=stable_model, sys_vars=dict(((stable_state.uid, stable_state),)),
            variable_parameters=list((computed_reference,)), event_parameters_eqs=event_equations,
            constant_parameters=list(), init_guess=seeds,
            uid2idx_vars=dict(((stable_state.uid, 0),)), uid2idx_params=dict(),
            uid2idx_event_params=dict(((computed_reference.uid, 0),)),
            compiler_names_dict=dict(((stable_state.uid, "x[0]"), (computed_reference.uid, "events[0]"))),
            alias_names_dict=dict(((stable_state.uid, "state"), (computed_reference.uid, "reference"))),
            VARIABLE_PARAMS_NAME="events", TIME_NAME="glob_time", VARS_NAME="x", DIFF_NAME="dx",
            CONSTANT_PARAMS_NAME="parameters", tol=1e-8,
            pseudo_transient_options=PseudoTransientOptions(equilibrium_references_as_params=True))
        assert solved[stable_state.uid] == pytest.approx(3.0, abs=1e-8)
        assert isinstance(event_equations[0], Const)
        assert event_equations[0].value == pytest.approx(solved[stable_state.uid] * solved[stable_state.uid], abs=1e-8)
        assert stable_model.state_eqs[0] is stable_expression
        assert stable_model.algebraic_eqs[0] is reference_expression
        assert isinstance(stable_model.event_dict[computed_reference], Const)
        assert stable_model.event_dict[computed_reference].value is None
    else:
        pass


@pytest.mark.parametrize("reverse_indices", (False, True))
def test_local_pseudo_transient_preserves_global_boundary_inputs(reverse_indices: bool) -> None:
    """Keep fixed global input UIDs independent of a local unknown's index.

    :param reverse_indices: Reverse the global ordering to expose index assumptions.
    :return: None; verify the independently known residual and source preservation.
    """
    boundary: Var = Var("same display name")
    unknown: Var = Var("same display name")
    expression: Expr = unknown - boundary
    model: Block = Block(in_vars=list((boundary,)), algebraic_vars=list((unknown,)), algebraic_eqs=list((expression,)))
    indices: dict[int, int] = dict(((boundary.uid, 1 if reverse_indices else 0), (unknown.uid, 0 if reverse_indices else 1)))
    snapshot: np.ndarray = np.asarray((9.0, 3.0) if reverse_indices else (3.0, 9.0))
    names: dict[int, str] = dict((uid, f"x[{index}]") for uid, index in indices.items())
    aliases: dict[int, str] = dict((uid, f"global_{index}") for uid, index in indices.items())
    problem: PseudoTransientInitProblem = PseudoTransientInitProblem(
        block=model, x_global=snapshot, compiler_names_dict=names, alias_names_dict=aliases,
        uid2idx_vars=indices, variable_parameters=list(), constant_parameters=list(),
        VARS_NAME="x", DIFF_NAME="dx", VARIABLE_PARAMS_NAME="events", CONSTANT_PARAMS_NAME="parameters")
    empty: np.ndarray = np.zeros(0)
    assert problem.rhs_algebraic(np.asarray((9.0,)), empty)[0] == pytest.approx(6.0)
    assert problem.rhs_algebraic(np.asarray((3.0,)), empty)[0] == pytest.approx(0.0)
    assert model.algebraic_eqs[0] is expression
    assert names[boundary.uid] == f"x[{indices[boundary.uid]}]"
    np.testing.assert_array_equal(snapshot, np.asarray((9.0, 3.0) if reverse_indices else (3.0, 9.0)))


def test_external_boundary_seed_availability_is_not_array_finiteness() -> None:
    """Distinguish a supplied boundary from the historical absent-seed fallback.

    :return: None; certify the supplied case and expose the unqualified zero case.
    """
    seed: float | None
    for seed in (3.0, None, np.nan):
        supplied: bool = seed is not None and np.isfinite(seed)
        boundary: Var = Var("external boundary")
        unknown: Var = Var("local unknown")
        model: Block = Block(in_vars=list((boundary,)), algebraic_vars=list((unknown,)), algebraic_eqs=list((unknown - boundary,)))
        seeds: dict[int, float | None] = dict(((unknown.uid, 9.0),))
        if seed is not None:
            seeds[boundary.uid] = seed
        else:
            pass
        indices: dict[int, int] = dict(((boundary.uid, 0), (unknown.uid, 1)))
        names: dict[int, str] = dict(((boundary.uid, "x[0]"), (unknown.uid, "x[1]")))
        aliases: dict[int, str] = dict(((boundary.uid, "boundary"), (unknown.uid, "unknown")))
        solved: dict[int, float] = init_pseudo_transient(
            mdl=model, sys_vars=dict(((boundary.uid, boundary), (unknown.uid, unknown))),
            variable_parameters=list(), event_parameters_eqs=list(), constant_parameters=list(),
            init_guess=seeds, uid2idx_vars=indices, uid2idx_params=dict(), uid2idx_event_params=dict(),
            compiler_names_dict=names, alias_names_dict=aliases, VARIABLE_PARAMS_NAME="events",
            TIME_NAME="glob_time", VARS_NAME="x", DIFF_NAME="dx", CONSTANT_PARAMS_NAME="parameters")
        assert np.isfinite(solved[unknown.uid])
        assert solved[unknown.uid] == pytest.approx(3.0 if supplied else 0.0, abs=1e-6)
        # A finite solution using structural zero is not evidence that PF data
        # was supplied. Neither initialization nor this test invents that data.
        assert (boundary.uid in seeds and seeds[boundary.uid] is not None and np.isfinite(seeds[boundary.uid])) is supplied
        assert seeds[unknown.uid] == solved[unknown.uid]


@pytest.mark.parametrize("startup_q_error", (0.0, 3e-6))
@pytest.mark.parametrize("formulation", (RmsProblemTypes.PowerBalance, RmsProblemTypes.PowerBalanceVectorized, RmsProblemTypes.PowerBalanceFullVectorized))
def test_native_rms_pseudo_transient_preserves_pf_operating_point(
        startup_q_error: float, formulation: RmsProblemTypes) -> None:
    """Validate native PTC against the original converged network boundaries.

    :param startup_q_error: Bounded reactive runtime-guess mismatch before global acceptance.
    :param formulation: Existing native power-balance assembly owning the compiled equations.
    :return: None; verify terminal voltages, fixed states, source data and original residuals.
    """
    grid: gce.MultiCircuit
    pf: gce.PowerFlowResults
    grid, pf = build_supported_vectorized_ac_load_case()
    powers: np.ndarray = np.asarray((grid.loads[0].P, grid.loads[0].Q))
    problem: RmsProblemTemplate = build_rms_problem(
        grid=grid, options=gce.RmsOptions(problem_type=formulation,
        initialization_method=RmsInitializationMethod.PseudoTransient), pf_results=pf)
    initial_states: np.ndarray = problem.get_x0()[:problem.get_states_number()].copy()
    pf_voltage: np.ndarray = pf.voltage.copy()
    reactive_power: Var = grid.generators[0].rms_model.E(VarPowerFlowReferenceType.Q)
    # Perturb only a runtime algebraic guess. The global owner must close the
    # original assembled equations without inventing physical data or moving PF.
    problem.init_guess[reactive_power.uid] += startup_q_error
    problem.set_events_group(gce.RmsEventsGroup(name="PF preservation"))
    values: np.ndarray = problem.get_x0()
    problem.update_variable_params(t=0.0, x_snapshot=values)
    assert np.max(np.abs(problem.rhs_algebraic(values, problem.get_dx0()))) <= 1e-6
    # Each existing formulation owns a different state-residual interface.
    state_residual: np.ndarray
    if isinstance(problem, (RmsProblemDaeVec, RmsProblemDaeFullVec)):
        problem.update_input_matrices_by_model(values, problem.get_dx0())
        state_residual = problem.rhs_state_vec()
    else:
        assert isinstance(problem, RmsProblemDae)
        state_residual = problem.rhs_state(values, problem.get_dx0())
    assert np.max(np.abs(state_residual)) <= 1e-6
    index: int
    bus: gce.Bus
    for index, bus in enumerate(grid.buses):
        magnitude: Var = bus.rms_model.E(VarPowerFlowReferenceType.Vm)
        angle: Var = bus.rms_model.E(VarPowerFlowReferenceType.Va)
        assert values[problem.uid2idx_vars[magnitude.uid]] == pytest.approx(abs(pf.voltage[index]), abs=1e-6)
        assert values[problem.uid2idx_vars[angle.uid]] == pytest.approx(np.angle(pf.voltage[index]), abs=1e-6)
    np.testing.assert_array_equal(powers, np.asarray((grid.loads[0].P, grid.loads[0].Q)))

    np.testing.assert_array_equal(initial_states, values[:problem.get_states_number()])
    np.testing.assert_array_equal(pf_voltage, pf.voltage)


def _build_complete_generator_grid_without_init_equations() -> gce.MultiCircuit:
    """
    Build the complete-generator pseudo-transient regression grid.

    :return: Grid with RMS models assigned and generator ``init_eqs`` cleared.
    """
    grid: gce.MultiCircuit = gce.MultiCircuit(Sbase=100.0, fbase=50.0)
    bus0: gce.Bus = gce.Bus(name="Bus0", Vnom=90.0, is_slack=True)
    bus1: gce.Bus = gce.Bus(name="Bus1", Vnom=90.0)

    initialize_bus_rms(bus0, vf=grid.var_factory)
    initialize_bus_rms(bus1, vf=grid.var_factory)
    grid.add_bus(bus0)
    grid.add_bus(bus1)

    line: gce.Line = gce.Line(
        name="Line0-1",
        bus_from=bus0,
        bus_to=bus1,
        r=0.029585798816568046,
        x=0.07100591715976332,
        b=0.03,
        rate=900.0,
    )
    grid.add_line(line)

    load: gce.Load = gce.Load(name="Load1", P=10.0, Q=1.0)
    grid.add_load(bus=bus1, api_obj=load)

    generator: gce.Generator = gce.Generator(
        name="Gen0",
        P=100.0,
        vset=1.0,
        Snom=900.0,
        r1=0.3,
        x1=0.86138701,
        freq=50.0,
    )
    grid.add_generator(bus=bus0, api_obj=generator)

    set_rms_model(
        device=line,
        model=get_line_rms_template(grid.var_factory, name=line.name).block,
        var_factory=grid.var_factory,
    )
    set_rms_model(
        device=load,
        model=get_load_rms_template(grid.var_factory, name=load.name).block,
        var_factory=grid.var_factory,
    )

    generator_model: Block = get_complete_generator_template_rms(grid.var_factory, name=generator.name).block
    generator_model = to_explicit(generator_model, grid.var_factory)
    for block in generator_model.get_all_blocks():
        block.init_eqs = dict()

    set_rms_model(
        device=generator,
        model=generator_model,
        var_factory=grid.var_factory,
    )
    grid.add_rms_events_group(gce.RmsEventsGroup(name="BaseCase"))

    return grid


@pytest.mark.parametrize("repetition", (0, 1, 2, 3))
def test_pseudo_transient_initializes_complete_generator_without_init_equations(repetition: int) -> None:
    """
    Test pseudo-transient initialization on the complete-generator RMS script model.

    The script builds the complete synchronous-generator RMS template and clears
    its ``init_eqs`` before assigning it to the grid, so this test exercises the
    intended pseudo-transient fallback path without relying on symbolic explicit
    initialization equations.

    :param repetition: Independent native initialization without RNG reseeding.
    :return: None.
    """
    grid: gce.MultiCircuit = _build_complete_generator_grid_without_init_equations()
    power_flow_options: gce.PowerFlowOptions = gce.PowerFlowOptions(
        solver_type=gce.SolverType.NR,
        retry_with_other_methods=False,
        verbose=0,
        tolerance=1.0e-6,
        max_iter=25,
        control_q=False,
        distributed_slack=False,
    )
    power_flow_results = gce.power_flow(grid, options=power_flow_options)

    assert bool(power_flow_results.converged)

    rms_options: gce.RmsOptions = gce.RmsOptions(
        time_step=0.01,
        simulation_time=0.01,
        integration_method=DynamicIntegrationMethod.DaeBackEuler,
        initialization_method=RmsInitializationMethod.PseudoTransient,
        max_iter=1000,
        tolerance=1.0e-8,
        verbose=0,
    )
    rms_driver: RmsSimulationDriver = RmsSimulationDriver(
        grid=grid,
        options=rms_options,
        pf_results=power_flow_results,
    )
    rms_driver.run()

    problem: RmsProblemDae | None = rms_driver.problem
    assert problem is not None

    x0: Vec = problem.get_x0()
    assert x0.size == problem.get_all_vars_number()
    assert bool(np.all(np.isfinite(x0)))
    assert bool(np.all(rms_driver.results.converged))
