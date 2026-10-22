from __future__ import annotations
import numpy as np
import pytest
from tests.RMS.test_rms_terminal_power_assembly import (
    build_supported_vectorized_ac_load_case,
    build_current_balance_load_case,
)
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.Branches.line import Line
from VeraGridEngine.Devices.Branches.transformer import Transformer2W
from VeraGridEngine.Templates.Rms.transformer_rms_template import get_transformer2w_rms
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_rms_model
from VeraGridEngine.api import power_flow
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Utils.Symbolic.bus_rms_template import BusRmsTemplate
from VeraGridEngine.Devices.Events.rms_events_group import RmsEventsGroup
from VeraGridEngine.Devices.Events.rms_event import RmsEvent
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from VeraGridEngine.Simulations.Rms.rms_problem_factory import build_rms_problem
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae_vectorized import RmsProblemDaeVec
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae_full_vectorized import RmsProblemDaeFullVec
from VeraGridEngine.Simulations.Rms.problems.rms_problem_phasor import RmsProblemPhasor
from VeraGridEngine.Simulations.Rms.problems.rms_problem_template import RmsProblemTemplate
from VeraGridEngine.Simulations.Rms.rms_driver import RmsSimulationDriver
from VeraGridEngine.Simulations.Rms.initialization import _select_rms_initialization_method
from VeraGridEngine.Simulations.Rms.initialization_rms import (
    project_initial_algebraic_state,
    run_rms_consistent_initialization,
    _collect_fixed_pf_bus_voltage_uids,
)
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var, Expr
from VeraGridEngine.enumerations import (
    RmsInitializationMethod,
    RmsProblemTypes,
    ParamPowerFlowReferenceType,
    DynamicEventTransitionType,
    VarPowerFlowReferenceType,
)
from VeraGridEngine.basic_structures import Logger


class _ScalarRmsInitializationProblem(RmsProblemTemplate):
    """Minimal RMS problem contract for the global consistent-Newton stage."""

    __slots__ = (
        "y", "options", "init_guess", "event_params_init_dict", "sys_block",
        "state_vars", "state_eqs", "algebraic_vars", "algebraic_eqs",
        "variable_parameters", "event_parameters_eqs", "event_parameters_eqs0",
        "uid2idx_vars", "uid2idx_event_params",
    )

    VARS_NAME = "x"
    DIFF_NAME = "dx"
    VARIABLE_PARAMS_NAME = "event_x"
    CONSTANT_PARAMS_NAME = "params"

    def __init__(self) -> None:
        """Set up a scalar algebraic problem with a deliberately wrong guess.

        :return: None.
        """
        super().__init__()
        self.grid: MultiCircuit | None = None
        self.y = Var("y")
        self.options = RmsOptions(
            initialization_method=RmsInitializationMethod.ConsistentNewton,
            tolerance=1.0e-10,
            max_iter=20,
        )
        self.init_guess = {self.y.uid: 9.0}
        self.event_params_init_dict = {}
        self.sys_block = Block(children=[], in_vars=[])
        self.state_vars = []
        self.state_eqs = []
        self.algebraic_vars = [self.y]
        self.algebraic_eqs = [self.y - Const(2.0)]
        self.variable_parameters = []
        self.event_parameters_eqs = []
        self.event_parameters_eqs0 = []
        self.uid2idx_vars = {self.y.uid: 0}
        self.uid2idx_event_params = {}

    def get_x0(self) -> np.ndarray:
        """Return the current scalar state guess.

        :return: Initial unknown vector.
        """
        return np.asarray([self.init_guess[self.y.uid]], dtype=np.float64)

    def get_dx0(self) -> np.ndarray:
        """Return the empty derivative vector.

        :return: Empty derivative vector.
        """
        return np.zeros(0, dtype=np.float64)

    def rhs_algebraic(self, values: np.ndarray, diff_values: np.ndarray) -> np.ndarray:
        """Evaluate the scalar constraint or the subclass's empty algebraic set.

        :param values: Ordered initial unknown vector.
        :param diff_values: Derivatives, unused by this algebraic fixture.
        :return: Scalar algebraic residual, or an empty vector for state-only tests.
        """
        # Reuse the same fixture hierarchy to distinguish algebraic consistency
        # from the missing-state subclass's differential equilibrium equation.
        if len(self.algebraic_eqs) > 0:
            return np.asarray((values[0] - 2.0,), dtype=np.float64)
        else:
            return np.zeros(0, dtype=np.float64)

    def get_states_number(self) -> int:
        """Locate the algebraic coordinates after the declared fixed states.

        :return: Number of differential states in the fixture.
        """
        return len(self.state_vars)

    def get_eventparams0(self) -> np.ndarray:
        """Return the empty event parameter vector.

        :return: Empty event parameter vector.
        """
        return np.zeros(0, dtype=np.float64)

    def get_parameters_values(self) -> list[Const]:
        """Return the absent constant parameters.

        :return: Empty parameter list.
        """
        return []

    def get_compiler_names_dict(self) -> dict[int, str]:
        """Name the only compiled unknown.

        :return: UID to compiler name mapping.
        """
        return {self.y.uid: "x[0]"}

    def get_alias_names_dict(self) -> dict[int, str]:
        """Name the only alias in the initialization problem.

        :return: UID to alias mapping.
        """
        return {self.y.uid: "x_0"}


class _MissingStateInitializationProblem(_ScalarRmsInitializationProblem):
    """Scalar state with dynamics but deliberately no explicit init equation."""

    __slots__ = ("x",)

    def __init__(self) -> None:
        """Replace the algebraic variable with an uninitialized state.

        :return: None.
        """
        super().__init__()
        self.x = self.y
        self.init_guess = {}
        self.state_vars = [self.x]
        self.state_eqs = [self.x - Const(3.0)]
        self.algebraic_vars = []
        self.algebraic_eqs = []

    def get_x0(self) -> np.ndarray:
        """Supply a neutral guess for the state equilibrium solve.

        :return: Initial state vector.
        """
        # An absent seed retains the established neutral Newton starting point;
        # an explicit seed also lets the PTC finite-vector contract be exercised.
        initial_value: float | None = self.init_guess.get(self.x.uid, None)
        if initial_value is None:
            initial_value = 0.0
        else:
            pass
        return np.asarray((initial_value,), dtype=np.float64)


def test_consistent_newton_is_an_rms_initialization_option() -> None:
    """Expose the global solver as an RMS initialization choice.

    :return: None.
    """
    assert "ConsistentNewton" in RmsInitializationMethod.list()


@pytest.mark.parametrize("method", (RmsInitializationMethod.ConsistentNewton, RmsInitializationMethod.Auto, RmsInitializationMethod.PseudoTransient))
@pytest.mark.parametrize("initial_value,tolerance,zero_constraint,impossible_constraint", (
    (9.0, 1e-10, False, False),
    (2.0 + 5e-11, 1e-14, False, False),
    (np.inf, 1e-10, True, False),
    (9.0, 1e-10, False, True),
))
def test_consistent_newton_solves_initialized_algebraic_variables(
        method: RmsInitializationMethod, initial_value: float, tolerance: float,
        zero_constraint: bool, impossible_constraint: bool) -> None:
    """Correct finite roots exactly and reject invalid candidates without writeback.

    :param method: Strict or Auto consistency mode at the same existing owner.
    :param initial_value: Deliberate valid or nonfinite initial algebraic coordinate.
    :param tolerance: Exact requested physical residual tolerance.
    :param zero_constraint: Expose finite-vector acceptance with a zero residual row.
    :param impossible_constraint: Exercise the known scalar sparse least-squares boundary.
    :return: None; every success closes original g and every failure preserves guesses.
    """
    problem: _ScalarRmsInitializationProblem = _ScalarRmsInitializationProblem()
    logger: Logger = Logger()
    problem.options.initialization_method = method
    problem.options.tolerance = tolerance
    problem.init_guess[problem.y.uid] = initial_value
    if zero_constraint:
        problem.algebraic_eqs = list((Const(0.0),))
    elif impossible_constraint:
        problem.algebraic_eqs = list((problem.y * problem.y + Const(1.0),))
        problem.options.max_iter = 5
    else:
        pass
    before: dict[int, float | int | complex | None] = problem.init_guess.copy()
    if not np.isfinite(initial_value) or impossible_constraint:
        if method == RmsInitializationMethod.Auto:
            assert not run_rms_consistent_initialization(problem, problem.options, logger=logger)
        else:
            with pytest.raises(RuntimeError):
                run_rms_consistent_initialization(problem, problem.options, logger=logger)
        np.testing.assert_equal(before, problem.init_guess)
    else:
        assert run_rms_consistent_initialization(problem, problem.options, logger=logger)
        assert abs(problem.init_guess[problem.y.uid] - 2.0) <= tolerance
        assert np.max(np.abs(problem.rhs_algebraic(problem.get_x0(), problem.get_dx0()))) <= tolerance
        assert len(logger.entries) == 0


@pytest.mark.parametrize("method", (RmsInitializationMethod.ConsistentNewton, RmsInitializationMethod.Auto, RmsInitializationMethod.PseudoTransient))
@pytest.mark.parametrize("seed", (None, 0.0, np.nan))
def test_consistent_newton_uses_equilibrium_for_state_without_init_eq(
        method: RmsInitializationMethod, seed: float | None) -> None:
    """Solve missing states while preserving fixed finite seeds and rejecting NaN.

    :param method: Existing strict or Auto global consistency selection.
    :param seed: Missing equilibrium state, deliberately fixed seed, or NaN input.
    :return: None; seeded fixed-state preservation is not a universal f=0 certificate.
    """
    problem: _MissingStateInitializationProblem = _MissingStateInitializationProblem()
    problem.options.initialization_method = method
    if seed is None:
        pass
    else:
        problem.init_guess[problem.x.uid] = seed
    before: dict[int, float | int | complex | None] = problem.init_guess.copy()
    if seed is not None and not np.isfinite(seed):
        if method == RmsInitializationMethod.Auto:
            assert not run_rms_consistent_initialization(problem, problem.options)
        else:
            with pytest.raises(RuntimeError, match="finite initial values"):
                run_rms_consistent_initialization(problem, problem.options)
        np.testing.assert_equal(before, problem.init_guess)
    else:
        assert run_rms_consistent_initialization(problem, problem.options)
        assert problem.get_x0()[0] == pytest.approx(3.0 if seed is None else seed, abs=1e-10)


@pytest.mark.parametrize("formulation,use_transformer", (
    (RmsProblemTypes.PowerBalance, False),
    (RmsProblemTypes.PowerBalanceVectorized, False),
    (RmsProblemTypes.PowerBalanceFullVectorized, False),
    (RmsProblemTypes.CurrentBalance, False),
    (RmsProblemTypes.Multilinear, False),
    pytest.param(RmsProblemTypes.PowerBalanceFullVectorized, True, id="transformer-full-vectorized"),
))
@pytest.mark.parametrize("method", (
    RmsInitializationMethod.Explicit, RmsInitializationMethod.Auto,
    RmsInitializationMethod.PseudoTransient, RmsInitializationMethod.ConsistentNewton))
def test_native_rms_initialization_selection_and_residuals(
        formulation: RmsProblemTypes, use_transformer: bool, method: RmsInitializationMethod) -> None:
    """Exercise every supported native selection on a fresh converged PF grid.

    :param formulation: Existing RMS factory formulation to assemble.
    :param use_transformer: Exercise recursive transformer initialization instead of the fixture line.
    :param method: Existing startup selection to execute.
    :return: None; verify finite startup and independently evaluated global rows.
    """
    grid: MultiCircuit
    pf: PowerFlowResults
    if formulation in (RmsProblemTypes.CurrentBalance, RmsProblemTypes.Multilinear):
        grid, pf = build_current_balance_load_case(((0.2, 0.04),), 2.0, 0.97)
    else:
        grid, pf = build_supported_vectorized_ac_load_case()
    if use_transformer:
        # Keep the established two-bus operating-point fixture and replace only
        # its branch family so the actual transformer startup paths are covered.
        line: Line = grid.lines[0]
        transformer: Transformer2W = Transformer2W(
            bus_from=line.bus_from,
            bus_to=line.bus_to,
            name="Initialization transformer",
            HV=10.0,
            LV=10.0,
            nominal_power=grid.Sbase,
            r=line.R,
            x=line.X,
            g=0.0,
            b=0.0,
            rate=line.rate,
        )
        grid.delete_line(obj=line)
        grid.add_transformer2w(obj=transformer)
        set_rms_model(
            device=transformer,
            model=get_transformer2w_rms(vf=grid.var_factory).block,
            var_factory=grid.var_factory,
        )
        pf = power_flow(grid=grid)
    else:
        pass
    options: RmsOptions = RmsOptions(problem_type=formulation, initialization_method=method, tolerance=1e-6)
    problem: RmsProblemTemplate = build_rms_problem(grid=grid, options=options, pf_results=pf)
    assert isinstance(problem, (RmsProblemDae, RmsProblemDaeVec, RmsProblemDaeFullVec, RmsProblemPhasor))
    # Native PB constructors retain seeds; this existing binding prepares
    # the runtime snapshot before its global consistency certificate.
    problem.set_events_group(RmsEventsGroup(name="Native initialization regression"))
    values: np.ndarray = problem.get_x0()
    assert np.all(np.isfinite(values))
    problem.update_variable_params(t=0.0, x_snapshot=values)
    residual: np.ndarray = problem.rhs_algebraic(values, problem.get_dx0())
    assert len(problem.algebraic_eqs) == len(problem.algebraic_vars)
    assert np.max(np.abs(residual)) <= options.tolerance


@pytest.mark.parametrize("formulation", (
    RmsProblemTypes.PowerBalance, RmsProblemTypes.PowerBalanceVectorized,
    RmsProblemTypes.PowerBalanceFullVectorized, RmsProblemTypes.CurrentBalance, RmsProblemTypes.Multilinear))
def test_native_rms_newton_corrects_seeded_algebraic_values(formulation: RmsProblemTypes) -> None:
    """Correct native algebraic seeds while holding states and events fixed.

    :param formulation: Existing RMS factory formulation to assemble.
    :return: None; confirm all global constraints and fixed input snapshots.
    """
    grid: MultiCircuit
    pf: PowerFlowResults
    if formulation in (RmsProblemTypes.CurrentBalance, RmsProblemTypes.Multilinear):
        grid, pf = build_current_balance_load_case(((0.2, 0.04),), 2.0, 0.97)
    else:
        grid, pf = build_supported_vectorized_ac_load_case()
    options: RmsOptions = RmsOptions(problem_type=formulation, initialization_method=RmsInitializationMethod.ConsistentNewton, tolerance=1e-8)
    problem: RmsProblemTemplate = build_rms_problem(grid=grid, options=options, pf_results=pf)
    assert isinstance(problem, (RmsProblemDae, RmsProblemDaeVec, RmsProblemDaeFullVec, RmsProblemPhasor))
    problem.set_events_group(RmsEventsGroup(name="Reduced initialization perturbation"))
    before: np.ndarray = problem.get_x0()
    events: np.ndarray = problem.get_eventparams0().copy()
    rows: tuple[int, ...] = tuple(eq.uid for eq in problem.algebraic_eqs)
    variable: Var = problem.algebraic_vars[-1]
    problem.init_guess[variable.uid] += 0.03
    assert run_rms_consistent_initialization(problem=problem, options=options)
    after: np.ndarray = problem.get_x0()
    np.testing.assert_array_equal(before[:len(problem.state_vars)], after[:len(problem.state_vars)])
    np.testing.assert_array_equal(events, problem.get_eventparams0())
    assert rows == tuple(eq.uid for eq in problem.algebraic_eqs)
    problem.update_variable_params(t=0.0, x_snapshot=after)
    assert np.max(np.abs(problem.rhs_algebraic(after, problem.get_dx0()))) <= options.tolerance


def test_auto_reuses_complete_explicit_selection() -> None:
    """Keep the established presence-based selection independent of validity.

    :return: None; distinguish absent initialization sources from nonfinite seeds.
    """
    variable: Var = Var("selection variable")
    model: Block = Block(algebraic_vars=list((variable,)), algebraic_eqs=list((variable,)))
    indices: dict[int, int] = dict(((variable.uid, 0),))
    seeds: dict[int, float | int | complex | None] = dict()
    assert _select_rms_initialization_method(RmsInitializationMethod.Auto, model, seeds, indices) == RmsInitializationMethod.PseudoTransient
    seeds[variable.uid] = np.nan
    assert _select_rms_initialization_method(RmsInitializationMethod.Auto, model, seeds, indices) == RmsInitializationMethod.Explicit
    seeds[variable.uid] = None
    model.init_eqs[variable] = Const(np.inf)
    assert _select_rms_initialization_method(RmsInitializationMethod.Auto, model, seeds, indices) == RmsInitializationMethod.Explicit
    assert _select_rms_initialization_method(RmsInitializationMethod.ConsistentNewton, model, seeds, indices) == RmsInitializationMethod.ConsistentNewton


@pytest.mark.parametrize("formulation", (RmsProblemTypes.CurrentBalance, RmsProblemTypes.Multilinear))
@pytest.mark.parametrize("history", (False, True))
def test_native_rms_ptc_global_projection_preserves_operating_point(
        formulation: RmsProblemTypes, history: bool) -> None:
    """Close ideal-source KCL and qualify terminal powers on the physical fixture.

    :param formulation: Native phasor formulation or its Multilinear subclass.
    :param history: Apply a pre-zero load event to change the effective startup.
    :return: None; check every algebraic row and original physical/PF evidence.
    """
    grid: MultiCircuit
    pf: PowerFlowResults
    grid, pf = build_current_balance_load_case(((0.2, 0.04),), 2.0, 0.97)
    source_data: tuple[float, float] = (grid.loads[0].P, grid.loads[0].Q)
    pf_voltage: np.ndarray = pf.voltage.copy()
    pf_power: np.ndarray = pf.Sbus.copy()
    group: RmsEventsGroup = RmsEventsGroup(name="PTC physical startup")
    expected_load_power: complex
    if history:
        power_parameter: Var = grid.loads[0].rms_model.api_obj_mapping[ParamPowerFlowReferenceType.Pl0]
        grid.add_rms_event(RmsEvent(device=grid.loads[0], parameter=power_parameter,
                                   time=-0.1, value=-0.16, group=group))
        expected_load_power = complex(0.32, 0.04)
    else:
        expected_load_power = complex(0.2, 0.04)
    source_events: tuple[RmsEvent, ...] = tuple(grid.rms_events)
    options: RmsOptions = RmsOptions(problem_type=formulation,
        initialization_method=RmsInitializationMethod.PseudoTransient, tolerance=1e-8)
    problem: RmsProblemTemplate = build_rms_problem(grid=grid, options=options, pf_results=pf)
    assert isinstance(problem, RmsProblemPhasor)
    # Certify the actual constructor before a group or integrator can repair it.
    values: np.ndarray = problem.get_x0()
    assert np.all(np.isfinite(values))
    assert np.max(np.abs(problem.rhs_algebraic(values, problem.get_dx0()))) <= options.tolerance
    snapshot: np.ndarray = problem.get_eventparams0().copy()
    np.testing.assert_array_equal(snapshot, problem._variable_parameters_values)
    problem.set_events_group(group)
    values = problem.get_x0()
    assert np.max(np.abs(problem.rhs_algebraic(values, problem.get_dx0()))) <= options.tolerance
    np.testing.assert_array_equal(snapshot, problem.get_eventparams0())
    np.testing.assert_array_equal(snapshot, problem._variable_parameters_values)
    # Derive powers from terminal V/I rather than accepting residual or PF labels
    # as independent evidence for the physical load and ideal-source currents.
    source_model: Block = grid.generators[0].rms_model
    source_bus: Block = grid.buses[0].rms_model
    load_model: Block = grid.loads[0].rms_model
    target_bus: Block = grid.buses[1].rms_model
    source_current: complex = complex(
        values[problem.uid2idx_vars[source_model.external_mapping[VarPowerFlowReferenceType.Ir].uid]],
        values[problem.uid2idx_vars[source_model.external_mapping[VarPowerFlowReferenceType.Ii].uid]])
    source_voltage: complex = complex(
        values[problem.uid2idx_vars[source_bus.external_mapping[VarPowerFlowReferenceType.Vr].uid]],
        values[problem.uid2idx_vars[source_bus.external_mapping[VarPowerFlowReferenceType.Vi].uid]])
    load_current: complex = complex(
        values[problem.uid2idx_vars[load_model.external_mapping[VarPowerFlowReferenceType.Ir].uid]],
        values[problem.uid2idx_vars[load_model.external_mapping[VarPowerFlowReferenceType.Ii].uid]])
    target_voltage: complex = complex(
        values[problem.uid2idx_vars[target_bus.external_mapping[VarPowerFlowReferenceType.Vr].uid]],
        values[problem.uid2idx_vars[target_bus.external_mapping[VarPowerFlowReferenceType.Vi].uid]])
    source_power: complex = source_voltage * np.conj(source_current) * grid.Sbase
    consumed_power: complex = -target_voltage * np.conj(load_current) * grid.Sbase
    assert source_voltage == pytest.approx(pf_voltage[0], abs=1e-8)
    assert consumed_power == pytest.approx(expected_load_power, abs=1e-7)
    if history:
        assert source_power.real > consumed_power.real
        assert source_power.imag > consumed_power.imag
    else:
        assert source_power == pytest.approx(pf_power[0], abs=1e-6)
        assert target_voltage == pytest.approx(pf_voltage[1], abs=1e-6)
    np.testing.assert_array_equal(pf_voltage, pf.voltage)
    np.testing.assert_array_equal(pf_power, pf.Sbus)
    assert source_data == (grid.loads[0].P, grid.loads[0].Q)
    assert source_events == tuple(grid.rms_events)
    assert options.initialization_method == RmsInitializationMethod.PseudoTransient


@pytest.mark.parametrize("formulation", (
    RmsProblemTypes.PowerBalance, RmsProblemTypes.PowerBalanceVectorized,
    RmsProblemTypes.PowerBalanceFullVectorized, RmsProblemTypes.CurrentBalance, RmsProblemTypes.Multilinear))
def test_native_rms_ptc_projection_preserves_seeded_states(formulation: RmsProblemTypes) -> None:
    """Qualify the compiled PTC stage separately from device-local preparation.

    :param formulation: Existing native formulation supplying compiled g/J22.
    :return: None; verify full-g closure and preservation of fixed seeds/data.
    """
    grid: MultiCircuit
    pf: PowerFlowResults
    if formulation in (RmsProblemTypes.CurrentBalance, RmsProblemTypes.Multilinear):
        grid, pf = build_current_balance_load_case(((0.2, 0.04),), 2.0, 0.97)
    else:
        grid, pf = build_supported_vectorized_ac_load_case()
    source_data: tuple[float, float] = (grid.loads[0].P, grid.loads[0].Q)
    pf_voltage: np.ndarray = pf.voltage.copy()
    pf_power: np.ndarray = pf.Sbus.copy()
    # The established preparation tolerance has separate provenance: strict
    # scalar Newton startup at 1e-8 is a baseline limitation, not this stage.
    options: RmsOptions = RmsOptions(problem_type=formulation,
        initialization_method=RmsInitializationMethod.ConsistentNewton, tolerance=1e-6)
    problem: RmsProblemTemplate = build_rms_problem(grid=grid, options=options, pf_results=pf)
    assert isinstance(problem, (RmsProblemDae, RmsProblemDaeVec, RmsProblemDaeFullVec, RmsProblemPhasor))
    problem.set_events_group(RmsEventsGroup(name="Compiled stage preparation"))
    before: np.ndarray = problem.get_x0().copy()
    problem.update_variable_params(t=0.0, x_snapshot=before)
    events: np.ndarray = problem.get_eventparams0().copy()
    runtime_parameters: np.ndarray = problem._variable_parameters_values.copy()
    rows: tuple[int, ...] = tuple(eq.uid for eq in problem.algebraic_eqs)
    columns: tuple[tuple[int, ...], tuple[int, ...]] = (
        tuple(var.uid for var in problem.state_vars), tuple(var.uid for var in problem.algebraic_vars))
    variable: Var = problem.algebraic_vars[-1]
    problem.init_guess[variable.uid] += 0.03
    options.initialization_method = RmsInitializationMethod.PseudoTransient
    options.tolerance = 1e-8
    # Calling the common compiled stage does not imply a new PowerBalance hook
    # or qualification of its unchanged random local PTC initialization.
    input_values: np.ndarray = problem.get_x0().copy()
    input_guesses: dict[int, float | int | complex | None] = problem.init_guess.copy()
    after: np.ndarray
    projection_converged: bool
    projection_residual: float
    after, projection_converged, projection_residual = project_initial_algebraic_state(
        problem=problem, initial_values=input_values, differential_values=problem.get_dx0(),
        tolerance=options.tolerance, max_iter=options.max_iter,
    )
    assert projection_converged
    assert projection_residual <= options.tolerance
    np.testing.assert_array_equal(input_values, problem.get_x0())
    np.testing.assert_equal(input_guesses, problem.init_guess)
    np.testing.assert_array_equal(before[:len(problem.state_vars)], after[:len(problem.state_vars)])
    np.testing.assert_array_equal(events, problem.get_eventparams0())
    np.testing.assert_array_equal(runtime_parameters, problem._variable_parameters_values)
    assert rows == tuple(eq.uid for eq in problem.algebraic_eqs)
    assert columns == (tuple(var.uid for var in problem.state_vars), tuple(var.uid for var in problem.algebraic_vars))
    assert np.max(np.abs(problem.rhs_algebraic(after, problem.get_dx0()))) <= options.tolerance
    np.testing.assert_array_equal(pf_voltage, pf.voltage)
    np.testing.assert_array_equal(pf_power, pf.Sbus)
    assert source_data == (grid.loads[0].P, grid.loads[0].Q)
    assert options.initialization_method == RmsInitializationMethod.PseudoTransient


@pytest.mark.parametrize("formulation", (RmsProblemTypes.CurrentBalance, RmsProblemTypes.Multilinear))
@pytest.mark.parametrize("nonfinite", (False, True))
def test_native_rms_ptc_projection_rejects_unclosed_network(
        formulation: RmsProblemTypes, nonfinite: bool) -> None:
    """Require actual failed group retries to respect algebraic acceptance.

    :param formulation: Native phasor owner or its Multilinear subclass.
    :param nonfinite: Reject a NaN seed instead of exhausting one iteration.
    :return: None; check repeated failures preserve guesses and recovery closes g.
    """
    grid: MultiCircuit
    pf: PowerFlowResults
    grid, pf = build_current_balance_load_case(((0.2, 0.04),), 2.0, 0.97)
    options: RmsOptions = RmsOptions(problem_type=formulation,
        initialization_method=RmsInitializationMethod.PseudoTransient, tolerance=1e-8)
    problem: RmsProblemTemplate = build_rms_problem(grid=grid, options=options, pf_results=pf)
    assert isinstance(problem, RmsProblemPhasor)
    accepted_group: RmsEventsGroup = RmsEventsGroup(name="Previously accepted PTC group")
    problem.set_events_group(accepted_group)
    assert problem.is_initialized()
    target_voltage: Var = grid.buses[1].rms_model.external_mapping[VarPowerFlowReferenceType.Vr]
    accepted_seed: float = float(problem.init_guess[target_voltage.uid])
    if nonfinite:
        problem.init_guess[target_voltage.uid] = np.nan
    else:
        # Disturb both the bus voltage and its load auxiliary coordinate:
        # the linked bus row alone can close in one linear correction, while
        # this pair also activates the nonlinear constant-power product.
        problem.init_guess[target_voltage.uid] = accepted_seed + 0.2
        voltage_auxiliary: Var = grid.loads[0].rms_model.algebraic_vars[2]
        problem.init_guess[voltage_auxiliary.uid] += 0.2
        options.max_iter = 1
    failed_guesses: np.ndarray = problem.get_x0().copy()
    failed_map: dict[int, float | int | complex | None] = problem.init_guess.copy()
    guess_keys: tuple[int, ...] = tuple(problem.init_guess)
    group: RmsEventsGroup = RmsEventsGroup(name="Failed PTC group")
    attempt: int
    for attempt in range(2):
        with pytest.raises(RuntimeError, match="RMS PTC algebraic projection"):
            problem.set_events_group(group if attempt == 0 else accepted_group)
        assert not problem.is_initialized()
        np.testing.assert_array_equal(failed_guesses, problem.get_x0())
        np.testing.assert_equal(failed_map, problem.init_guess)
        assert guess_keys == tuple(problem.init_guess)
    # The identical group must execute again rather than bypass the failed
    # certificate. Fix only the injected cause, then require original-g success.
    if nonfinite:
        problem.init_guess[target_voltage.uid] = accepted_seed
    else:
        options.max_iter = 1000
    problem.set_events_group(group)
    assert problem.is_initialized()
    assert np.max(np.abs(problem.rhs_algebraic(problem.get_x0(), problem.get_dx0()))) <= options.tolerance


@pytest.mark.parametrize("nonfinite", (False, True))
def test_native_rms_ptc_projection_handles_empty_algebraic_system(nonfinite: bool) -> None:
    """Qualify empty-g helper preservation and the actual phasor finite guard.

    :param nonfinite: Exercise NaN rejection at the retained native lifecycle site.
    :return: None; no differential equilibrium or helper-only NaN claim.
    """
    if nonfinite:
        grid: MultiCircuit
        pf: PowerFlowResults
        grid, pf = build_current_balance_load_case(((0.2, 0.04),), 2.0, 0.97)
        options: RmsOptions = RmsOptions(problem_type=RmsProblemTypes.CurrentBalance,
            initialization_method=RmsInitializationMethod.PseudoTransient, tolerance=1e-8)
        native_problem: RmsProblemTemplate = build_rms_problem(grid=grid, options=options, pf_results=pf)
        assert isinstance(native_problem, RmsProblemPhasor)
        target_voltage: Var = grid.buses[1].rms_model.external_mapping[VarPowerFlowReferenceType.Vr]
        native_problem.init_guess[target_voltage.uid] = np.nan
        before_native: np.ndarray = native_problem.get_x0().copy()
        native_guesses: dict[int, float | int | complex | None] = native_problem.init_guess.copy()
        with pytest.raises(RuntimeError, match="finite initial values"):
            native_problem.set_events_group(RmsEventsGroup(name="Nonfinite projection boundary"))
        np.testing.assert_array_equal(before_native, native_problem.get_x0())
        np.testing.assert_equal(native_guesses, native_problem.init_guess)
    else:
        problem: _MissingStateInitializationProblem = _MissingStateInitializationProblem()
        before: np.ndarray = problem.get_x0().copy()
        before_guesses: dict[int, float | int | complex | None] = problem.init_guess.copy()
        after: np.ndarray
        converged: bool
        residual: float
        after, converged, residual = project_initial_algebraic_state(
            problem=problem, initial_values=before, differential_values=problem.get_dx0(),
            tolerance=problem.options.tolerance, max_iter=problem.options.max_iter,
        )
        assert converged
        assert residual == 0.0
        np.testing.assert_array_equal(before, after)
        np.testing.assert_array_equal(before, problem.get_x0())
        np.testing.assert_equal(before_guesses, problem.init_guess)
        assert after[0] == 0.0
        # No algebraic rows exist, so the fixed x-3 dynamics remain unpolished.
        assert after[0] != 3.0


@pytest.mark.parametrize("formulation", (RmsProblemTypes.CurrentBalance, RmsProblemTypes.Multilinear))
@pytest.mark.parametrize("transition", (DynamicEventTransitionType.Step, DynamicEventTransitionType.Ramp))
@pytest.mark.parametrize("method", (RmsInitializationMethod.ConsistentNewton, RmsInitializationMethod.PseudoTransient))
def test_phasor_initial_event_snapshot_matches_replay(
        formulation: RmsProblemTypes, transition: DynamicEventTransitionType,
        method: RmsInitializationMethod) -> None:
    """Preserve the complete prepared snapshot through native consistency stages.

    :param formulation: Phasor problem or its inherited Multilinear formulation.
    :param transition: History type applied before startup.
    :param method: Native consistency stage applied after existing replay.
    :return: None; check retained expressions, resets and source declarations.
    """
    grid: MultiCircuit
    pf: PowerFlowResults
    grid, pf = build_current_balance_load_case(((0.2, 0.04),), 2.0, 0.97)
    power: Var = grid.loads[0].rms_model.api_obj_mapping[ParamPowerFlowReferenceType.Pl0]
    reactive: Var = grid.loads[0].rms_model.api_obj_mapping[ParamPowerFlowReferenceType.Ql0]
    dependent: Var = grid.var_factory.add_var("retained line expression")
    declaration: Expr = reactive + Const(-0.127)
    grid.lines[0].rms_model.event_dict[dependent] = declaration
    # These unused line parameters expose a third-evaluation bug without
    # changing the electrical fixture or its existing two-pass replay policy.
    chain_a: Var = grid.var_factory.add_var("retained chain a")
    chain_b: Var = grid.var_factory.add_var("retained chain b")
    chain_c: Var = grid.var_factory.add_var("retained chain c")
    chain_variables: tuple[Var, ...] = (chain_a, chain_b, chain_c)
    chain_declarations: tuple[Expr, ...] = (chain_b + Const(1.0), chain_c + Const(1.0), Const(2.0))
    chain_variable: Var
    chain_declaration: Expr
    for chain_variable, chain_declaration in zip(chain_variables, chain_declarations):
        grid.lines[0].rms_model.event_dict[chain_variable] = chain_declaration
    group: RmsEventsGroup = RmsEventsGroup(name="Startup history")
    events: list[RmsEvent] = list((
        RmsEvent(device=grid.loads[0], parameter=power, time=-0.2, end_time=-0.1,
                 value=-0.16, group=group, transition_type=transition),
        RmsEvent(device=grid.lines[0], parameter=dependent, time=-0.2, end_time=-0.1,
                 value=-0.18, group=group, transition_type=transition),
        RmsEvent(device=grid.loads[0], parameter=power, time=0.05, value=-0.08, group=group)))
    event: RmsEvent
    for event in events:
        grid.add_rms_event(event)
    options: RmsOptions = RmsOptions(problem_type=formulation, initialization_method=method, tolerance=1e-8)
    problem: RmsProblemTemplate = build_rms_problem(grid=grid, options=options, pf_results=pf)
    assert isinstance(problem, RmsProblemPhasor)
    initial: np.ndarray = problem.get_eventparams0()
    np.testing.assert_array_equal(initial, problem._variable_parameters_values)
    assert initial[problem.uid2idx_event_params[power.uid]] == pytest.approx(-0.16)
    assert initial[problem.uid2idx_event_params[dependent.uid]] == pytest.approx(-0.18)
    assert problem.event_parameters_eqs0[problem.uid2idx_event_params[dependent.uid]] is declaration
    expected_chain: tuple[float, ...] = (3.0, 3.0, 2.0)
    expected_value: float
    for chain_variable, chain_declaration, expected_value in zip(chain_variables, chain_declarations, expected_chain):
        assert initial[problem.uid2idx_event_params[chain_variable.uid]] == expected_value
        assert problem.event_parameters_eqs0[problem.uid2idx_event_params[chain_variable.uid]] is chain_declaration
    assert np.max(np.abs(problem.rhs_algebraic(problem.get_x0(), problem.get_dx0()))) <= options.tolerance
    # Group reset must share replay, while later updates and interior restarts
    # leave the recorded startup snapshot stable.
    problem.set_events_group(group)
    np.testing.assert_array_equal(initial, problem.get_eventparams0())
    np.testing.assert_array_equal(initial, problem._variable_parameters_values)
    problem.update_variable_params(t=0.075)
    assert problem._variable_parameters_values[problem.uid2idx_event_params[power.uid]] == pytest.approx(-0.08)
    np.testing.assert_array_equal(initial, problem.get_eventparams0())
    problem.reset_boundary_update_state(t0=0.075)
    np.testing.assert_array_equal(initial, problem.get_eventparams0())
    problem.reset_boundary_update_state(t0=0.0)
    np.testing.assert_array_equal(problem.get_eventparams0(), problem._variable_parameters_values)
    problem.set_events_group(RmsEventsGroup(name="No histories"))
    baseline: np.ndarray = problem.get_eventparams0()
    np.testing.assert_array_equal(baseline, problem._variable_parameters_values)
    assert baseline[problem.uid2idx_event_params[dependent.uid]] == pytest.approx(-0.147)
    assert grid.lines[0].rms_model.event_dict[dependent] is declaration
    for chain_variable, chain_declaration, expected_value in zip(chain_variables, chain_declarations, expected_chain):
        assert baseline[problem.uid2idx_event_params[chain_variable.uid]] == expected_value
        assert grid.lines[0].rms_model.event_dict[chain_variable] is chain_declaration
    assert tuple(grid.rms_events) == tuple(events)


@pytest.mark.parametrize("formulation", (
    RmsProblemTypes.PowerBalance, RmsProblemTypes.PowerBalanceVectorized, RmsProblemTypes.PowerBalanceFullVectorized))
def test_power_balance_initialization_step_refinement(formulation: RmsProblemTypes) -> None:
    """Qualify no-disturbance native trajectories at two integration steps.

    :param formulation: Existing supported power-balance driver formulation.
    :return: None; check convergence, state drift and independent final residues.
    """
    drifts: np.ndarray = np.empty(2, dtype=np.float64)
    index: int
    step: float
    for index, step in enumerate((0.01, 0.005)):
        grid: MultiCircuit
        pf: PowerFlowResults
        grid, pf = build_supported_vectorized_ac_load_case()
        grid.add_rms_events_group(RmsEventsGroup(name="No disturbance"))
        options: RmsOptions = RmsOptions(problem_type=formulation, initialization_method=RmsInitializationMethod.ConsistentNewton,
            time_step=step, simulation_time=0.02, tolerance=1e-6)
        driver: RmsSimulationDriver = RmsSimulationDriver(grid=grid, options=options, pf_results=pf)
        driver.run()
        problem: RmsProblemTemplate | None = driver.problem
        assert isinstance(problem, (RmsProblemDae, RmsProblemDaeVec, RmsProblemDaeFullVec))
        assert np.all(driver.results.converged)
        initial: np.ndarray = problem.get_x0()
        final: np.ndarray = driver.results.values[-1, :, 0]
        drifts[index] = np.max(np.abs(final[:len(problem.state_vars)] - initial[:len(problem.state_vars)]))
        assert drifts[index] <= max(10.0 * options.tolerance, 1e-6)
        problem.update_variable_params(t=0.02, x_snapshot=final)
        assert np.max(np.abs(problem.rhs_algebraic(final, problem.get_dx0()))) <= options.tolerance
    assert drifts[1] <= drifts[0] + 1e-6


@pytest.mark.parametrize("method", (RmsInitializationMethod.ConsistentNewton, RmsInitializationMethod.Auto, RmsInitializationMethod.PseudoTransient))
@pytest.mark.parametrize("previous_ready", (False, True))
def test_consistent_newton_rejects_original_gauge_row_mismatch(method: RmsInitializationMethod, previous_ready: bool) -> None:
    """Reject an incompatible physical row compiled before consistency certification.

    :param method: Strict or Auto global acceptance mode after existing preparation.
    :param previous_ready: Retry the old accepted group after a failed new preparation.
    :return: None; compiled original g rejects the mismatch and the same failed group retries.
    """
    grid: MultiCircuit
    pf: PowerFlowResults
    grid, pf = build_supported_vectorized_ac_load_case()
    # Device preparation remains explicit; the selected global acceptance mode is exercised below.
    options: RmsOptions = RmsOptions(initialization_method=RmsInitializationMethod.ConsistentNewton, tolerance=1e-6)
    problem: RmsProblemDae = RmsProblemDae(grid=grid, options=options, pf_results=pf)
    accepted_group: RmsEventsGroup = RmsEventsGroup(name="Previously accepted RMS group")
    if previous_ready:
        problem.set_events_group(accepted_group)
        assert problem.is_initialized()
    else:
        assert not problem.is_initialized()
    reference: tuple[int, int] | None = problem.get_small_signal_reference_indices()
    assert reference is not None
    original_row: int = reference[0] - len(problem.state_vars)
    # Inject before group compilation so both declared and original compiled g own the same row.
    problem.algebraic_eqs[original_row] = Const(1.0)
    options.initialization_method = method
    before: dict[int, float | int | complex | None] = problem.init_guess.copy()
    equations: tuple[int, ...] = tuple(eq.uid for eq in problem.algebraic_eqs)
    group: RmsEventsGroup = RmsEventsGroup(name="Incompatible original gauge row")
    initial_events: np.ndarray | None = None
    attempt: int
    for attempt in range(2):
        with pytest.raises(RuntimeError, match="did not converge"):
            problem.set_events_group(accepted_group if previous_ready and attempt == 1 else group)
        np.testing.assert_equal(before, problem.init_guess)
        assert not problem.is_initialized()
        assert equations == tuple(eq.uid for eq in problem.algebraic_eqs)
        compiled_original_g: np.ndarray = problem.rhs_algebraic(problem.get_x0(), problem.get_dx0())
        assert compiled_original_g[original_row] == 1.0
        if initial_events is None:
            initial_events = problem.get_eventparams0().copy()
        else:
            np.testing.assert_array_equal(initial_events, problem.get_eventparams0())


def test_consistent_newton_fixes_only_declared_pf_voltage_coordinates() -> None:
    """Keep a canonical capacitive DC nodal power variable free under voltage fixing.

    :return: None; verify quantity ownership using the actual bus template and enum references.
    """
    grid: MultiCircuit = MultiCircuit()
    bus: Bus = Bus(name="Capacitive DC fixed-voltage regression", is_dc=True)
    grid.add_bus(bus)
    bus.rms_model = BusRmsTemplate(vf=grid.var_factory, is_dc=True, dc_shunt_capacitance_pu_seconds=0.1).block
    problem: _ScalarRmsInitializationProblem = _ScalarRmsInitializationProblem()
    problem.grid = grid
    fixed_uids: set[int] = _collect_fixed_pf_bus_voltage_uids(problem)
    power_variable: Var = bus.rms_model.external_mapping[VarPowerFlowReferenceType.P]
    voltage_variable: Var = bus.rms_model.external_mapping[VarPowerFlowReferenceType.Vdc]
    assert power_variable is bus.rms_model.algebraic_vars[0]
    assert voltage_variable is bus.rms_model.state_vars[0]
    assert power_variable.uid not in fixed_uids
    assert len(fixed_uids) == 0


class _NonConvergingRmsInitializationProblem(_ScalarRmsInitializationProblem):
    """Scalar initialization problem with an unsatisfiable residual."""

    __slots__ = ()

    def __init__(self) -> None:
        """
        Replace the solvable residual with a non-zero constant equation.

        :return: None.
        """
        super().__init__()

        # A constant non-zero residual cannot be reduced by changing the only
        # unknown, so it provides a deterministic non-convergence scenario.
        self.algebraic_eqs = [Const(1.0)]


def test_auto_non_convergence_adds_one_warning() -> None:
    """
    Report one warning when Auto keeps a non-converged initialization candidate.

    :return: None.
    """
    problem: _NonConvergingRmsInitializationProblem = _NonConvergingRmsInitializationProblem()
    problem.options.initialization_method = RmsInitializationMethod.Auto
    logger: Logger = Logger()

    converged: bool = run_rms_consistent_initialization(
        problem=problem,
        options=problem.options,
        logger=logger,
    )

    assert converged is False
    assert logger.warning_count() == 1
    assert logger.error_count() == 0
    assert logger.entries[0].device_class == "RMS"
    assert logger.entries[0].device_property == "initialization"
    assert "Auto mode is continuing" in logger.entries[0].msg


def test_consistent_newton_non_convergence_logs_error_before_raising() -> None:
    """
    Record one error before strict consistent initialization stops construction.

    :return: None.
    """
    problem: _NonConvergingRmsInitializationProblem = _NonConvergingRmsInitializationProblem()
    logger: Logger = Logger()

    with pytest.raises(RuntimeError, match="simulation construction is stopping"):
        run_rms_consistent_initialization(
            problem=problem,
            options=problem.options,
            logger=logger,
        )

    assert logger.warning_count() == 0
    assert logger.error_count() == 1
    assert logger.entries[0].device_class == "RMS"
    assert logger.entries[0].device_property == "initialization"
