from __future__ import annotations

import numpy as np
from PySide6 import QtWidgets

from tests.DynamicEditor._dynamic_runtime_equivalence import (
    build_dynamic_model_with_editor,
    get_qt_application,
)
from VeraGridEngine.Devices.Branches.line import Line
from VeraGridEngine.Devices.Branches.overhead_line_type import OverheadLineType
from VeraGridEngine.Devices.Branches.wire import Wire
from VeraGridEngine.Devices.Events.emt_event import EmtEvent
from VeraGridEngine.Devices.Events.emt_events_group import EmtEventsGroup
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Simulations.EMT.emt_driver import EmtSimulationDriver
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.emt_results import EmtResults
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow3ph.power_flow_driver_3ph import PowerFlowDriver3Ph
from VeraGridEngine.Simulations.PowerFlow3ph.power_flow_results_3ph import PowerFlowResults3Ph
from VeraGridEngine.Templates.Emt.load_zip_emt_template import get_load_ZIP_emt_template
from VeraGridEngine.Templates.Emt.pi_line_emt_template import get_pi_line_emt_template
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import (
    get_generator_thevenin_rl_emt_template_with_ref,
)
from VeraGridEngine.Utils.Symbolic.block import Block, build_name_to_var_lookup
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var, symbolic_to_string
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model
from VeraGridEngine.enumerations import (
    BranchImpedanceMode,
    DynamicIntegrationMethod,
    DynamicSimulationMode,
    EmtInitializationMethod,
    EmtSolverTypes,
    ShuntConnectionType,
    SolverType,
)


def _build_two_bus_emt_grid() -> tuple[MultiCircuit, Generator, Line, Load]:
    """Build the static three-phase grid shared by both EMT workflows.

    The GUI devices intentionally retain their initially empty EMT blocks so
    editor Apply must create and attach the bus-side EMT shells itself.

    :return: Circuit, generator, line and ZIP load under test.
    """
    grid: MultiCircuit = MultiCircuit(Sbase=2.0, fbase=50.0)
    nominal_voltage: float = 10.0
    bus0: Bus = Bus(
        name="Bus0",
        idtag="emt-bus-0",
        Vnom=nominal_voltage,
        is_slack=True,
    )
    bus1: Bus = Bus(name="Bus1", idtag="emt-bus-1", Vnom=nominal_voltage)
    grid.add_bus(bus0)
    grid.add_bus(bus1)

    line0: Line = Line(
        name="line 0-1",
        idtag="emt-line-0-1",
        bus_from=bus0,
        bus_to=bus1,
        length=10.0,
        rate=900.0,
    )
    tower: OverheadLineType = OverheadLineType(name="Tower", Vnom=nominal_voltage)
    wire: Wire = Wire(
        name="Panther 30/7 ACSR",
        diameter=21.0,
        diameter_internal=9.0,
        is_tube=True,
        r=0.1363,
        max_current=1.0,
    )
    tower.add_wire_relationship(wire=wire, xpos=-12.65, ypos=27.5, phase=1)
    tower.add_wire_relationship(wire=wire, xpos=0.0, ypos=27.5, phase=2)
    tower.add_wire_relationship(wire=wire, xpos=12.65, ypos=27.5, phase=3)
    tower.compute()
    line0.apply_template(obj=tower, Sbase=grid.Sbase, freq=grid.fBase)

    phase_resistance: float = 100.0
    phase_voltage: float = nominal_voltage / np.sqrt(3.0)
    phase_power: float = phase_voltage ** 2 / phase_resistance
    load: Load = Load(
        name="Load0",
        idtag="emt-load-0",
        P1=phase_power,
        P2=phase_power,
        P3=phase_power,
        Q1=0.0,
        Q2=0.0,
        Q3=0.0,
    )
    load.conn = ShuntConnectionType.GroundedStar
    generator: Generator = Generator(
        name="Gen0",
        idtag="emt-generator-0",
        vset=1.0,
        Snom=grid.Sbase,
        freq=50.0,
        r1=0.001,
        x1=1.7,
    )
    grid.add_line(line0)
    grid.add_generator(bus=bus0, api_obj=generator)
    grid.add_load(bus=bus1, api_obj=load)

    # Populate the same EMT catalog rendered by the Dynamic Editor Library.
    grid.add_emt_model(get_generator_thevenin_rl_emt_template_with_ref(vf=grid.var_factory))
    grid.add_emt_model(
        get_pi_line_emt_template(
            vf=grid.var_factory,
            phN=False,
            phA=True,
            phB=True,
            phC=True,
        )
    )
    grid.add_emt_model(
        get_load_ZIP_emt_template(
            vf=grid.var_factory,
            phA=True,
            phB=True,
            phC=True,
        )
    )
    return grid, generator, line0, load


def _build_power_flow_options() -> PowerFlowOptions:
    """Build the three-phase Power Flow configuration used before EMT.

    :return: Deterministic three-phase Power Flow options.
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


def _build_emt_options() -> EmtOptions:
    """Build EMT options equivalent to values selectable in GUI settings.

    :return: Deterministic EMT simulation options.
    """
    return EmtOptions(
        time_step=5e-6,
        simulation_time=2e-4,
        tolerance=1e-6,
        solver_type=EmtSolverTypes.StructuralCompiled,
        integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
        initialization_method=EmtInitializationMethod.Auto,
        verbose=0,
    )


def _assemble_emt_models_from_script(grid: MultiCircuit,
                                     generator: Generator,
                                     line: Line,
                                     load: Load) -> None:
    """Assemble every EMT model through the documented scripting API.

    :param grid: Circuit whose variable factory owns all symbolic models.
    :param generator: Generator receiving the Thevenin model.
    :param line: Line receiving the three-phase Pi model.
    :param load: Load receiving the three-phase ZIP model.
    :return: None.
    """
    bus: Bus
    for bus in grid.buses:
        get_bus_emt_template(grid=grid, bus=bus)

    set_emt_model(
        device=generator,
        model=get_generator_thevenin_rl_emt_template_with_ref(vf=grid.var_factory).block,
        var_factory=grid.var_factory,
    )
    set_emt_model(
        device=line,
        model=get_pi_line_emt_template(
            vf=grid.var_factory,
            phN=False,
            phA=True,
            phB=True,
            phC=True,
        ).block,
        var_factory=grid.var_factory,
    )
    set_emt_model(
        device=load,
        model=get_load_ZIP_emt_template(
            vf=grid.var_factory,
            phA=True,
            phB=True,
            phC=True,
        ).block,
        var_factory=grid.var_factory,
    )


def _add_emt_event(grid: MultiCircuit, load: Load) -> str:
    """Add the active event group required by the GUI EMT dispatcher.

    :param grid: Circuit receiving the event group.
    :param load: ZIP load whose impedance coefficient is stepped.
    :return: Exact persisted event-parameter name used in result metadata.
    """
    variable_lookup: dict[str, Var] = build_name_to_var_lookup(load.emt_model)
    impedance_parameter: Var | None = variable_lookup.get("a1", None)
    if impedance_parameter is None:
        raise AssertionError("The EMT ZIP model does not expose event parameter 'a1'.")
    else:
        pass

    event_group: EmtEventsGroup = EmtEventsGroup(
        name="EMT GUI equivalence",
        idtag="emt-equivalence-group",
    )
    event: EmtEvent = EmtEvent(
        name="EMT ZIP step",
        idtag="emt-equivalence-event",
        device=load,
        parameter=impedance_parameter,
        time=1e-4,
        value=0.8,
        group=event_group,
        force_step_alignment=True,
    )
    grid.add_emt_events_group(obj=event_group)
    grid.add_emt_event(obj=event)
    return impedance_parameter.name


def _run_power_flow(grid: MultiCircuit) -> PowerFlowResults3Ph:
    """Run the three-phase Power Flow used to initialize EMT simulation.

    :param grid: Circuit to solve.
    :return: Converged three-phase Power Flow results.
    """
    driver: PowerFlowDriver3Ph = PowerFlowDriver3Ph(grid=grid, options=_build_power_flow_options())
    driver.run()
    assert driver.results.converged
    assert driver.logger.has_errors() is False
    return driver.results


def _run_emt_driver(grid: MultiCircuit, pf_results: PowerFlowResults3Ph) -> EmtSimulationDriver:
    """Run EMT through the same Engine driver constructed by the GUI session.

    :param grid: Validated EMT circuit.
    :param pf_results: Three-phase Power Flow initialization.
    :return: Completed EMT driver retaining the exact simulated problem.
    """
    driver: EmtSimulationDriver = EmtSimulationDriver(
        grid=grid,
        options=_build_emt_options(),
        pf_results_3ph=pf_results,
        pf_results=None,
    )
    driver.run()
    assert driver.problem is not None
    assert driver.results is not None
    assert driver.logger.has_errors() is False
    return driver


def _equation_strings(equations: list[Expr]) -> tuple[str, ...]:
    """Convert EMT equations into an identity-independent representation.

    :param equations: Symbolic equations from one compiled problem.
    :return: Sorted equation strings.
    """
    return tuple(sorted(
        symbolic_to_string(equation).replace("net_conn_", "")
        for equation in equations
    ))


def _constant_values(constants: list[Const]) -> tuple[str, ...]:
    """Convert problem constants into stable comparable scalar records.

    :param constants: Ordered compiled problem constants.
    :return: Scalar values represented without clone-generated identities.
    """
    return tuple(str(constant.value) for constant in constants)


def _assert_problem_equivalence(script_problem: EmtProblemDae, gui_problem: EmtProblemDae) -> None:
    """Compare the complete compiled EMT contracts used by both drivers.

    :param script_problem: Problem produced from scripted models.
    :param gui_problem: Problem produced from Dynamic Editor models.
    :return: None.
    """
    assert [variable.name.replace("net_conn_", "") for variable in script_problem.get_state_vars()] == [
        variable.name.replace("net_conn_", "") for variable in gui_problem.get_state_vars()
    ]
    assert [variable.name.replace("net_conn_", "") for variable in script_problem.get_algebraic_vars()] == [
        variable.name.replace("net_conn_", "") for variable in gui_problem.get_algebraic_vars()
    ]
    assert [variable.name.replace("net_conn_", "") for variable in script_problem.get_diff_vars()] == [
        variable.name.replace("net_conn_", "") for variable in gui_problem.get_diff_vars()
    ]
    assert [variable.name for variable in script_problem.get_variable_parameters()] == [
        variable.name for variable in gui_problem.get_variable_parameters()
    ]
    assert [variable.name for variable in script_problem.get_constant_parameters()] == [
        variable.name for variable in gui_problem.get_constant_parameters()
    ]
    assert _equation_strings(script_problem.get_state_eqs()) == _equation_strings(gui_problem.get_state_eqs())
    assert _equation_strings(script_problem.get_algebraic_eqs()) == _equation_strings(
        gui_problem.get_algebraic_eqs()
    )
    assert _constant_values(script_problem.get_parameters_values()) == _constant_values(
        gui_problem.get_parameters_values()
    )
    assert np.allclose(script_problem.get_x0(), gui_problem.get_x0(), rtol=1e-10, atol=1e-10)
    assert np.allclose(script_problem.get_dx0(), gui_problem.get_dx0(), rtol=1e-10, atol=1e-10)
    assert script_problem.initialization_report is not None
    assert gui_problem.initialization_report is not None
    assert script_problem.initialization_report.status == gui_problem.initialization_report.status


def _assert_result_equivalence(script_results: EmtResults,
                               gui_results: EmtResults,
                               load: Load,
                               parameter_name: str) -> None:
    """Compare numerical trajectories and all EMT group/result metadata.

    :param script_results: Results from scripted assembly.
    :param gui_results: Results from Dynamic Editor assembly.
    :param load: Deterministically identified load used by the event.
    :param parameter_name: Persisted event-parameter name.
    :return: None.
    """
    assert np.array_equal(script_results.time_array, gui_results.time_array)
    script_variable_names: list[str] = list(
        str(variable_name).replace("net_conn_", "")
        for variable_name in script_results.variable_array
    )
    gui_variable_names: list[str] = list(
        str(variable_name).replace("net_conn_", "")
        for variable_name in gui_results.variable_array
    )
    assert script_variable_names == gui_variable_names
    assert [variable.name.replace("net_conn_", "") for variable in script_results.diff_variables] == [
        variable.name.replace("net_conn_", "") for variable in gui_results.diff_variables
    ]
    assert np.array_equal(script_results.emt_events_group_names, gui_results.emt_events_group_names)
    assert np.array_equal(script_results.emt_events_group_idtags, gui_results.emt_events_group_idtags)
    assert np.array_equal(script_results.has_event_group_results, gui_results.has_event_group_results)
    assert np.array_equal(script_results.well_initialized, gui_results.well_initialized)
    assert np.array_equal(script_results.converged, gui_results.converged)
    assert script_results.initial_parameter_value_maps == gui_results.initial_parameter_value_maps
    assert script_results.parameter_value_maps == gui_results.parameter_value_maps
    assert np.all(script_results.has_event_group_results)
    assert np.all(script_results.well_initialized)
    assert np.all(script_results.converged)
    assert np.allclose(script_results.values, gui_results.values, rtol=1e-8, atol=1e-8)
    assert np.allclose(script_results.diff_values, gui_results.diff_values, rtol=1e-8, atol=1e-8)

    initial_value: float | None = script_results.get_initial_parameter_value(
        group_idx=0,
        device_idtag=load.idtag,
        parameter_name=parameter_name,
    )
    final_value: float | None = script_results.get_parameter_value(
        group_idx=0,
        device_idtag=load.idtag,
        parameter_name=parameter_name,
    )
    assert initial_value is not None
    assert final_value == 0.8


def test_emt_gui_and_scripting_follow_same_runtime_workflow() -> None:
    """Prove real Dynamic Editor and scripting EMT workflows are equivalent.

    The GUI branch starts from empty device models and uses a live
    ``DynamicEditorTab`` for catalog creation, graphical wiring, Apply and
    reopen. Both circuits then follow the GUI precheck/Power Flow requirements,
    execute a real event and compare models, compiled problems and all results.

    :return: None.
    """
    application: QtWidgets.QApplication = get_qt_application()

    script_grid: MultiCircuit
    script_generator: Generator
    script_line: Line
    script_load: Load
    script_grid, script_generator, script_line, script_load = _build_two_bus_emt_grid()
    _assemble_emt_models_from_script(
        grid=script_grid,
        generator=script_generator,
        line=script_line,
        load=script_load,
    )

    gui_grid: MultiCircuit
    gui_generator: Generator
    gui_line: Line
    gui_load: Load
    gui_grid, gui_generator, gui_line, gui_load = _build_two_bus_emt_grid()
    gui_generator_template: Block = build_dynamic_model_with_editor(
        application=application,
        circuit=gui_grid,
        device=gui_generator,
        mode=DynamicSimulationMode.EMT,
        template_name="emt_thevenin_eq_generator_template",
    )
    gui_line_template: Block = build_dynamic_model_with_editor(
        application=application,
        circuit=gui_grid,
        device=gui_line,
        mode=DynamicSimulationMode.EMT,
        template_name="Pi",
    )
    gui_load_template: Block = build_dynamic_model_with_editor(
        application=application,
        circuit=gui_grid,
        device=gui_load,
        mode=DynamicSimulationMode.EMT,
        template_name="ZIP_Load_EMT_3ph",
    )

    assert gui_generator_template.name == "emt_thevenin_eq_generator_template"
    assert gui_line_template.name == "Pi"
    assert gui_load_template.name == "ZIP_Load_EMT_3ph"

    script_parameter_name: str = _add_emt_event(grid=script_grid, load=script_load)
    gui_parameter_name: str = _add_emt_event(grid=gui_grid, load=gui_load)
    assert script_parameter_name == gui_parameter_name
    assert script_grid.valid_for_simulation()
    assert gui_grid.valid_for_simulation()
    assert script_grid.check_emt_models().has_errors() is False
    assert gui_grid.check_emt_models().has_errors() is False
    assert len(script_grid.emt_events_groups) == 1
    assert len(gui_grid.emt_events_groups) == 1

    script_pf_results: PowerFlowResults3Ph = _run_power_flow(script_grid)
    gui_pf_results: PowerFlowResults3Ph = _run_power_flow(gui_grid)
    assert np.allclose(script_pf_results.voltage_A, gui_pf_results.voltage_A, rtol=1e-10, atol=1e-10)
    assert np.allclose(script_pf_results.voltage_B, gui_pf_results.voltage_B, rtol=1e-10, atol=1e-10)
    assert np.allclose(script_pf_results.voltage_C, gui_pf_results.voltage_C, rtol=1e-10, atol=1e-10)
    assert np.allclose(script_pf_results.Sf_A, gui_pf_results.Sf_A, rtol=1e-10, atol=1e-10)
    assert np.allclose(script_pf_results.Sf_B, gui_pf_results.Sf_B, rtol=1e-10, atol=1e-10)
    assert np.allclose(script_pf_results.Sf_C, gui_pf_results.Sf_C, rtol=1e-10, atol=1e-10)

    script_driver: EmtSimulationDriver = _run_emt_driver(script_grid, script_pf_results)
    gui_driver: EmtSimulationDriver = _run_emt_driver(gui_grid, gui_pf_results)
    assert script_driver.problem is not None
    assert gui_driver.problem is not None
    assert script_driver.results is not None
    assert gui_driver.results is not None
    _assert_problem_equivalence(script_problem=script_driver.problem, gui_problem=gui_driver.problem)
    _assert_result_equivalence(
        script_results=script_driver.results,
        gui_results=gui_driver.results,
        load=script_load,
        parameter_name=script_parameter_name,
    )
