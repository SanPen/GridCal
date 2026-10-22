from __future__ import annotations

import re

import numpy as np
from PySide6 import QtWidgets

from tests.DynamicEditor._dynamic_runtime_equivalence import (
    build_dynamic_model_with_editor,
    get_qt_application,
)
from VeraGridEngine.Devices.Branches.line import Line
from VeraGridEngine.Devices.Events.rms_event import RmsEvent
from VeraGridEngine.Devices.Events.rms_events_group import RmsEventsGroup
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver, PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae
from VeraGridEngine.Simulations.Rms.rms_driver import RmsSimulationDriver
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Simulations.Rms.rms_results import RmsResults
from VeraGridEngine.Templates.Rms.genqec_exc_gov_sat_template import get_complete_generator_template_rms
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.load_rms_template import get_load_rms_template
from VeraGridEngine.Utils.Symbolic.block import Block, build_name_to_var_lookup
from VeraGridEngine.Utils.Symbolic.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var, expression2numba
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_rms_model
from VeraGridEngine.enumerations import (
    BranchImpedanceMode,
    DynamicIntegrationMethod,
    DynamicSimulationMode,
    RmsInitializationMethod,
    SolverType,
)


def _build_two_bus_rms_grid() -> tuple[MultiCircuit, Generator, Line, Load]:
    """Build the static network shared by the scripting and GUI workflows.

    The devices deliberately start without RMS models. The scripting branch
    initializes bus shells explicitly, while the GUI branch relies on the
    Dynamic Editor Apply workflow to perform that initialization.

    :return: Circuit, generator, line and load under test.
    """
    grid: MultiCircuit = MultiCircuit(Sbase=100.0, fbase=50.0)
    bus0: Bus = Bus(name="Bus0", idtag="rms-bus-0", Vnom=10.0, is_slack=True)
    bus1: Bus = Bus(name="Bus1", idtag="rms-bus-1", Vnom=10.0)
    grid.add_bus(bus0)
    grid.add_bus(bus1)

    line0: Line = Line(
        name="line 0-1",
        idtag="rms-line-0-1",
        bus_from=bus0,
        bus_to=bus1,
        r=0.029585,
        x=0.071005,
        b=0.03,
        rate=900.0,
    )
    load: Load = Load(name="Load0", idtag="rms-load-0", P=9.999999, Q=0.999999)
    generator: Generator = Generator(
        name="Gen0",
        idtag="rms-generator-0",
        P=10.0,
        vset=1.0,
        Snom=900.0,
        x1=0.86138701,
        r1=0.3,
        freq=50.0,
    )
    grid.add_line(line0)
    grid.add_load(bus=bus1, api_obj=load)
    grid.add_generator(bus=bus0, api_obj=generator)

    # Populate the real circuit catalog consumed by the Dynamic Editor Library.
    grid.add_rms_model(get_complete_generator_template_rms(grid.var_factory))
    grid.add_rms_model(get_line_rms_template(grid.var_factory))
    grid.add_rms_model(get_load_rms_template(grid.var_factory))
    return grid, generator, line0, load


def _build_power_flow_options() -> PowerFlowOptions:
    """Build the balanced Power Flow configuration used by the GUI workflow.

    :return: Deterministic Power Flow options.
    """
    return PowerFlowOptions(
        solver_type=SolverType.NR,
        retry_with_other_methods=False,
        verbose=0,
        initialize_with_existing_solution=True,
        tolerance=1e-6,
        max_iter=25,
        control_q=False,
        control_taps_modules=True,
        control_taps_phase=True,
        control_remote_voltage=True,
        orthogonalize_controls=True,
        apply_temperature_correction=True,
        branch_impedance_tolerance_mode=BranchImpedanceMode.Specified,
        distributed_slack=False,
        ignore_single_node_islands=False,
        trust_radius=1.0,
        backtracking_parameter=0.05,
        use_stored_guess=False,
        initialize_angles=False,
        generate_report=False,
    )


def _build_rms_options() -> RmsOptions:
    """Build RMS options equivalent to values selectable in GUI settings.

    :return: Deterministic RMS simulation options.
    """
    return RmsOptions(
        time_step=0.001,
        simulation_time=0.02,
        tolerance=1e-6,
        integration_method=DynamicIntegrationMethod.DaeBackEuler,
        initialization_method=RmsInitializationMethod.Explicit,
        use_init_values=False,
        max_iter=1000,
        verbose=0,
    )


def _assemble_rms_models_from_script(grid: MultiCircuit,
                                     generator: Generator,
                                     line: Line,
                                     load: Load) -> None:
    """Assemble all RMS models with the documented scripting API.

    :param grid: Circuit whose variable factory owns the models.
    :param generator: Generator receiving the complete RMS template.
    :param line: Line receiving the RMS branch template.
    :param load: Load receiving the constant-power RMS template.
    :return: None.
    """
    bus: Bus
    for bus in grid.buses:
        initialize_bus_rms(bus=bus, vf=grid.var_factory)

    set_rms_model(
        device=generator,
        model=get_complete_generator_template_rms(grid.var_factory).block,
        var_factory=grid.var_factory,
    )
    set_rms_model(
        device=line,
        model=get_line_rms_template(grid.var_factory).block,
        var_factory=grid.var_factory,
    )
    set_rms_model(
        device=load,
        model=get_load_rms_template(grid.var_factory).block,
        var_factory=grid.var_factory,
    )


def _add_rms_event(grid: MultiCircuit, load: Load) -> None:
    """Add the active event group required by the GUI RMS dispatcher.

    :param grid: Circuit receiving the group and event.
    :param load: Load whose active-power parameter is stepped.
    :return: None.
    """
    variable_lookup: dict[str, Var] = build_name_to_var_lookup(load.rms_model)
    active_power_parameter: Var | None = variable_lookup.get("Pl0", None)
    if active_power_parameter is None:
        raise AssertionError("The RMS load model does not expose event parameter 'Pl0'.")
    else:
        pass

    event_group: RmsEventsGroup = RmsEventsGroup(
        name="RMS GUI equivalence",
        idtag="rms-equivalence-group",
    )
    event: RmsEvent = RmsEvent(
        name="RMS load step",
        idtag="rms-equivalence-event",
        device=load,
        parameter=active_power_parameter,
        time=0.01,
        value=-0.08,
        group=event_group,
        force_step_alignment=True,
    )
    grid.add_rms_events_group(obj=event_group)
    grid.add_rms_event(obj=event)


def _run_power_flow(grid: MultiCircuit) -> PowerFlowResults:
    """Run the balanced Power Flow used to initialize RMS simulation.

    :param grid: Circuit to solve.
    :return: Converged Power Flow results.
    """
    driver: PowerFlowDriver = PowerFlowDriver(grid=grid, options=_build_power_flow_options())
    driver.run()
    assert driver.results.converged
    assert driver.logger.has_errors() is False
    return driver.results


def _run_rms_driver(grid: MultiCircuit, pf_results: PowerFlowResults) -> RmsSimulationDriver:
    """Run RMS through the same Engine driver constructed by the GUI session.

    :param grid: Validated dynamic circuit.
    :param pf_results: Balanced Power Flow initialization.
    :return: Completed RMS driver retaining the exact simulated problem.
    """
    driver: RmsSimulationDriver = RmsSimulationDriver(
        grid=grid,
        options=_build_rms_options(),
        pf_results=pf_results,
    )
    driver.run()
    assert driver.problem is not None
    assert driver.results is not None
    assert driver.logger.has_errors() is False
    return driver


def _equation_strings(equations: list[Expr], problem: RmsProblemDae) -> tuple[str, ...]:
    """Compare equations by solver bindings rather than mutable display names.

    :param equations: Symbolic equations from one compiled problem.
    :param problem: Problem defining the ordered runtime variable bindings.
    :return: Sorted expressions using identical positional names in both workflows.
    """
    # The compiler mapping distinguishes FROM and TO even when both bus voltage
    # variables are displayed as Vm/Va after connection propagation.
    return tuple(sorted(expression2numba(equation, problem._compiler_names_dict) for equation in equations))


def _canonical_rms_runtime_text(runtime_text: str) -> str:
    """Normalize GUI boundary labels to their RMS semantic references.

    Dynamic Editor wrapper outputs use the generic references ``P`` and ``Q``.
    Native scripted templates retain device-specific labels such as ``Pg`` and
    ``Pl``. These labels share one network reference and compile to the same
    numerical variable, so the comparison canonicalizes only complete tokens.

    :param runtime_text: Variable label or serialized symbolic equation.
    :return: Canonical semantic text.
    """
    canonical_text: str = runtime_text.replace("net_conn_", "")
    canonical_text = re.sub(r"\b(?:Pg|Pl)\b", "P", canonical_text)
    canonical_text = re.sub(r"\b(?:Qg|Ql)\b", "Q", canonical_text)
    # Result labels concatenate the variable and device names without a
    # separator (for example ``PgGen0``), so token boundaries are unavailable.
    if canonical_text.startswith("Pg") or canonical_text.startswith("Pl"):
        canonical_text = "P" + canonical_text[2:]
    elif canonical_text.startswith("Qg") or canonical_text.startswith("Ql"):
        canonical_text = "Q" + canonical_text[2:]
    else:
        pass
    return canonical_text


def _constant_values(constants: list[Const]) -> tuple[str, ...]:
    """Convert problem constants into stable comparable scalar records.

    :param constants: Ordered compiled problem constants.
    :return: Scalar values represented without clone-generated identities.
    """
    return tuple(str(constant.value) for constant in constants)


def _assert_problem_equivalence(script_problem: RmsProblemDae, gui_problem: RmsProblemDae) -> None:
    """Compare the complete compiled RMS contracts used by both drivers.

    :param script_problem: Problem produced from scripted models.
    :param gui_problem: Problem produced from Dynamic Editor models.
    :return: None.
    """
    assert [_canonical_rms_runtime_text(variable.name) for variable in script_problem.state_vars] == [
        _canonical_rms_runtime_text(variable.name) for variable in gui_problem.state_vars
    ]
    assert [_canonical_rms_runtime_text(variable.name) for variable in script_problem.algebraic_vars] == [
        _canonical_rms_runtime_text(variable.name) for variable in gui_problem.algebraic_vars
    ]
    assert [_canonical_rms_runtime_text(variable.name) for variable in script_problem.get_diff_vars()] == [
        _canonical_rms_runtime_text(variable.name) for variable in gui_problem.get_diff_vars()
    ]
    assert [variable.name for variable in script_problem.variable_parameters] == [
        variable.name for variable in gui_problem.variable_parameters
    ]
    assert _equation_strings(script_problem.state_eqs, script_problem) == _equation_strings(gui_problem.state_eqs, gui_problem)
    assert _equation_strings(script_problem.algebraic_eqs, script_problem) == _equation_strings(gui_problem.algebraic_eqs, gui_problem)
    assert _constant_values(script_problem.get_parameters_values()) == _constant_values(
        gui_problem.get_parameters_values()
    )
    assert np.allclose(script_problem.get_x0(), gui_problem.get_x0(), rtol=1e-10, atol=1e-10)
    assert np.allclose(script_problem.get_dx0(), gui_problem.get_dx0(), rtol=1e-10, atol=1e-10)
    assert np.allclose(script_problem.get_eventparams0(), gui_problem.get_eventparams0(), rtol=1e-10, atol=1e-10)


def _assert_result_equivalence(script_results: RmsResults,
                               gui_results: RmsResults,
                               load: Load) -> None:
    """Compare numerical trajectories and all RMS group/result metadata.

    :param script_results: Results from scripted assembly.
    :param gui_results: Results from Dynamic Editor assembly.
    :param load: Deterministically identified load used by the event.
    :return: None.
    """
    assert np.array_equal(script_results.time_array, gui_results.time_array)
    script_variable_names: list[str] = list(
        _canonical_rms_runtime_text(str(variable_name))
        for variable_name in script_results.variable_array
    )
    gui_variable_names: list[str] = list(
        _canonical_rms_runtime_text(str(variable_name))
        for variable_name in gui_results.variable_array
    )
    assert script_variable_names == gui_variable_names
    assert np.array_equal(script_results.rms_events_group_names, gui_results.rms_events_group_names)
    assert np.array_equal(script_results.rms_events_group_idtags, gui_results.rms_events_group_idtags)
    assert np.array_equal(script_results.has_event_group_results, gui_results.has_event_group_results)
    assert np.array_equal(script_results.well_initialized, gui_results.well_initialized)
    assert np.array_equal(script_results.converged, gui_results.converged)
    assert script_results.initial_parameter_value_maps == gui_results.initial_parameter_value_maps
    assert script_results.parameter_value_maps == gui_results.parameter_value_maps
    assert np.all(script_results.has_event_group_results)
    assert np.all(script_results.well_initialized)
    assert np.all(script_results.converged)
    assert np.allclose(script_results.values, gui_results.values, rtol=1e-8, atol=1e-8)

    initial_value: float | None = script_results.get_initial_parameter_value(
        group_idx=0,
        device_idtag=load.idtag,
        parameter_name="Pl0",
    )
    final_value: float | None = script_results.get_parameter_value(
        group_idx=0,
        device_idtag=load.idtag,
        parameter_name="Pl0",
    )
    assert initial_value is not None
    assert final_value == -0.08


def test_rms_gui_and_scripting_follow_same_runtime_workflow() -> None:
    """Prove real Dynamic Editor and scripting RMS workflows are equivalent.

    The GUI branch uses a live ``DynamicEditorTab`` from an empty device model,
    performs library creation, graphical wiring, Apply and reopen. Both branches
    then pass the GUI prechecks, run Power Flow, execute a non-trivial event and
    compare the persisted models, compiled problems and complete result sets.

    :return: None.
    """
    application: QtWidgets.QApplication = get_qt_application()

    script_grid: MultiCircuit
    script_generator: Generator
    script_line: Line
    script_load: Load
    script_grid, script_generator, script_line, script_load = _build_two_bus_rms_grid()
    _assemble_rms_models_from_script(
        grid=script_grid,
        generator=script_generator,
        line=script_line,
        load=script_load,
    )

    gui_grid: MultiCircuit
    gui_generator: Generator
    gui_line: Line
    gui_load: Load
    gui_grid, gui_generator, gui_line, gui_load = _build_two_bus_rms_grid()
    gui_generator_template: Block = build_dynamic_model_with_editor(
        application=application,
        circuit=gui_grid,
        device=gui_generator,
        mode=DynamicSimulationMode.RMS,
        template_name="complete_generator_rms_template",
    )
    gui_line_template: Block = build_dynamic_model_with_editor(
        application=application,
        circuit=gui_grid,
        device=gui_line,
        mode=DynamicSimulationMode.RMS,
        template_name="Line_rms_template",
    )
    gui_load_template: Block = build_dynamic_model_with_editor(
        application=application,
        circuit=gui_grid,
        device=gui_load,
        mode=DynamicSimulationMode.RMS,
        template_name="Load rms template",
    )
    assert gui_generator_template.name == "complete_generator_rms_template"
    assert gui_line_template.name == "Line_rms_template"
    assert gui_load_template.name == "Load rms template"

    _add_rms_event(grid=script_grid, load=script_load)
    _add_rms_event(grid=gui_grid, load=gui_load)
    assert script_grid.valid_for_simulation()
    assert gui_grid.valid_for_simulation()
    assert script_grid.check_rms_models().has_errors() is False
    assert gui_grid.check_rms_models().has_errors() is False
    assert len(script_grid.rms_events_groups) == 1
    assert len(gui_grid.rms_events_groups) == 1

    script_pf_results: PowerFlowResults = _run_power_flow(script_grid)
    gui_pf_results: PowerFlowResults = _run_power_flow(gui_grid)
    assert np.allclose(script_pf_results.voltage, gui_pf_results.voltage, rtol=1e-10, atol=1e-10)
    assert np.allclose(script_pf_results.Sf, gui_pf_results.Sf, rtol=1e-10, atol=1e-10)
    assert np.allclose(script_pf_results.St, gui_pf_results.St, rtol=1e-10, atol=1e-10)

    script_driver: RmsSimulationDriver = _run_rms_driver(script_grid, script_pf_results)
    gui_driver: RmsSimulationDriver = _run_rms_driver(gui_grid, gui_pf_results)
    assert script_driver.problem is not None
    assert gui_driver.problem is not None
    assert script_driver.results is not None
    assert gui_driver.results is not None
    _assert_problem_equivalence(script_problem=script_driver.problem, gui_problem=gui_driver.problem)
    _assert_result_equivalence(
        script_results=script_driver.results,
        gui_results=gui_driver.results,
        load=script_load,
    )
