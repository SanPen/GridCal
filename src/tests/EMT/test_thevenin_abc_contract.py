# SPDX-License-Identifier: MPL-2.0
"""Independent phase-matrix and native lifecycle checks of the passive source."""

import copy
from pathlib import Path

import numpy as np
import pytest

import VeraGridEngine.api as gce
from VeraGrid.Gui.DynamicModelEditor.Editor.dynamic_editor_models import copy_block_state
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.static_parameter_mapping_unified import (
    assign_thevenin_source_static_api_mapping, assign_static_api_object_mapping_for_device,
    resolve_constant_parameter_initial_value,
)
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.Parents.injection_parent import InjectionParent
from VeraGridEngine.IO.file_open import FileOpen
from VeraGridEngine.IO.file_save import FileSave
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.EMT.injection_operating_point import EmtInjectionOperatingPoint
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver
from VeraGridEngine.Simulations.PowerFlow3ph.power_flow_driver_3ph import PowerFlowDriver3Ph
from VeraGridEngine.Templates.Emt.load_RLC_emt_template import get_shunt_r_emt_template
from VeraGridEngine.Templates.Emt.load_zip_emt_template import get_load_ZIP_emt_template
from VeraGridEngine.Templates.Emt.pi_line_emt_template import get_pi_line_emt_template
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import get_generator_thevenin_rl_emt_template_with_ref
from VeraGridEngine.Utils.Symbolic.block import (
    Block, DynamicModelContract, EmtTerminalCurrentContribution,
    dynamic_model_contract_from_data, validate_dynamic_model_contract,
)
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
from VeraGridEngine.Utils.Symbolic.symbolic_io import BlockSaver, duplicate_block, duplicate_block_vars_uid
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.enumerations import (
    DynamicIntegrationMethod, EmtInitializationMethod, EmtInitializationStatus,
    EmtSolverTypes, ParamPowerFlowReferenceType, ShuntConnectionType, TheveninSourceVoltageMode,
    GeneratorControlMode, VarPowerFlowReferenceType, EmtTerminalSide, EmtTerminalConductor,
    DynamicSimulationMode,
)


def _find_source_var(block: Block, name: str) -> Var:
    """Locate one declared source symbol through the canonical Block tree.

    :param block: Model root or electrical child.
    :param name: Unique symbol name.
    :return: Declared symbol; ambiguity is a test failure.
    """
    matches: list[Var] = list()
    child: Block
    for child in block.get_all_blocks():
        collection: list[Var] | dict[Var, Expr]
        for collection in (child.state_vars, child.algebraic_vars, child.diff_vars,
                           child.in_vars, child.parameters, child.event_dict):
            variable: Var
            for variable in collection:
                if variable.name == name and variable not in matches:
                    matches.append(variable)
                else:
                    pass
    assert len(matches) == 1, name
    return matches[0]


def _evaluate_source_contract(
        block: Block, voltage: np.ndarray, current: np.ndarray,
        z0: complex = 0.04 + 0.6j, time: float = 0.0,
        events: tuple[tuple[str, float], ...] = (),
) -> tuple[np.ndarray, dict[int, float]]:
    """Evaluate authored equations against independently prescribed RMS phasors.

    :param block: Actual source electrical child, including parsed copies.
    :param voltage: Terminal ABC phasors on the phase voltage base.
    :param current: Injected ABC phasors on the conventional current base.
    :param z0: Homopolar impedance; Z1 and Z2 are 0.02+j0.2 pu.
    :param time: Waveform sample time after the declared seed.
    :param events: Registered source controls to override.
    :return: Rows of emf, current and derivative, plus numeric UID bindings.
    """
    omega: float = 2.0 * np.pi * 50.0
    rotation: np.ndarray = np.exp(-2j * np.pi * np.arange(3) / 3.0)
    v1: complex = complex(np.mean(voltage / rotation))
    i1: complex = complex(np.mean(current / rotation))
    bindings: dict[int, float] = dict()
    variable: Var
    expression: Expr
    for variable, expression in block.parameters.items():
        if variable.name == "omega_base":
            bindings[variable.uid] = omega
        elif variable.name == "R_s":
            bindings[variable.uid] = 0.02
        elif variable.name == "X_s":
            bindings[variable.uid] = 0.2
        elif variable.name == "R_0":
            bindings[variable.uid] = z0.real
        elif variable.name == "X_0":
            bindings[variable.uid] = z0.imag
        else:
            bindings[variable.uid] = float(expression.eval_uid(bindings))
    for variable, expression in block.event_dict.items():
        if variable.name == "phi_v":
            bindings[variable.uid] = float(np.angle(v1))
        elif variable.name == "phi":
            bindings[variable.uid] = float(np.angle(i1) - np.angle(v1))
        elif variable.name == "Vpk":
            bindings[variable.uid] = np.sqrt(2.0) * abs(v1)
        elif variable.name == "Ipk":
            bindings[variable.uid] = np.sqrt(2.0) * abs(i1)
        elif variable.name.startswith(("UR_", "UI_", "IR_", "II_")):
            index: int = ("A", "B", "C").index(variable.name[-1])
            phasor: complex = complex(voltage[index] if variable.name.startswith("U") else current[index])
            bindings[variable.uid] = phasor.real if variable.name[1] == "R" else phasor.imag
        elif isinstance(expression, Const) and expression.value is None:
            bindings[variable.uid] = 0.0
        else:
            bindings[variable.uid] = float(expression.eval_uid(bindings))
    event_name: str
    event_value: float
    for event_name, event_value in events:
        variable = _find_source_var(block, event_name)
        assert variable in block.event_dict
        bindings[variable.uid] = event_value
    phase_index: int
    for phase_index in range(3):
        bindings[block.in_vars[phase_index].uid] = float(np.sqrt(2.0) * voltage[phase_index].imag)
    # Resolve state seeds before internal voltage and measured power seeds.
    for variable in block.state_vars:
        bindings[variable.uid] = float(block.init_eqs[variable].eval_uid(bindings))
    theta: Var = _find_source_var(block, "theta")
    frequency: float = bindings[_find_source_var(block, "f_scale").uid]
    bindings[theta.uid] += omega * frequency * time
    wave_voltage: np.ndarray = np.sqrt(2.0) * (voltage * np.exp(1j * omega * time)).imag
    wave_current: np.ndarray = np.sqrt(2.0) * (current * np.exp(1j * omega * time)).imag
    for phase_index in range(3):
        bindings[block.in_vars[phase_index].uid] = float(wave_voltage[phase_index])
        bindings[block.state_vars[phase_index].uid] = float(wave_current[phase_index])
    for variable in block.algebraic_vars:
        bindings[variable.uid] = float(block.init_eqs[variable].eval_uid(bindings))
    result: np.ndarray = np.empty((3, 3), dtype=float)
    for phase_index in range(3):
        result[0, phase_index] = bindings[block.algebraic_vars[phase_index].uid]
        result[1, phase_index] = bindings[block.state_vars[phase_index].uid]
        result[2, phase_index] = float(block.state_eqs[phase_index].eval_uid(bindings))
        np.testing.assert_allclose(block.diff_init_eqs[block.diff_vars[phase_index]].eval_uid(bindings),
                                   result[2, phase_index], atol=1e-12)
    residual: np.ndarray = np.array(tuple(float(expression.eval_uid(bindings)) for expression in block.algebraic_eqs))
    np.testing.assert_allclose(residual, 0.0, atol=1e-12)
    return result, bindings


def _build_source_case(
        mode: TheveninSourceVoltageMode, three_phase: bool = False,
) -> tuple[EmtProblemDae, gce.Generator]:
    """Solve and initialize a real single-source-per-bus network.

    :param mode: Explicit source voltage capability.
    :param three_phase: Use unbalanced PF3 instead of balanced PF.
    :return: Native EMT problem and its physical source.
    """
    grid: gce.MultiCircuit = gce.MultiCircuit(name="Grounded ABC source", Sbase=100.0, fbase=50.0)
    source: gce.Bus = gce.Bus(name="Source", Vnom=230.0, is_slack=True)
    demand: gce.Bus = gce.Bus(name="Demand", Vnom=230.0)
    grid.add_bus(source)
    grid.add_bus(demand)
    tower: gce.OverheadLineType = gce.OverheadLineType(name="Tower", Vnom=230.0)
    wire: gce.Wire = gce.Wire(name="Wire", diameter=30.0, r=0.08, max_current=2.0)
    tower.add_wire_relationship(wire, xpos=-8.0, ypos=25.0, phase=1)
    tower.add_wire_relationship(wire, xpos=0.0, ypos=32.0, phase=2)
    tower.add_wire_relationship(wire, xpos=8.0, ypos=25.0, phase=3)
    tower.compute()
    line: gce.Line = gce.Line(name="Line", bus_from=source, bus_to=demand, rate=200.0)
    if three_phase:
        line.apply_template(tower, grid.Sbase, grid.fBase)
    else:
        # Balanced PF and EMT must describe the same sequence-derived line.
        line.R = 0.01
        line.X = 0.1
    generator: gce.Generator = gce.Generator(name="Source", vset=1.02, Snom=200.0,
        r1=0.01, x1=0.25, r0=0.04, x0=0.6, r2=0.01, x2=0.25)
    p: tuple[float, float, float] = (12.0, 8.0, 5.0) if three_phase else (10.0, 10.0, 10.0)
    load: gce.Load = gce.Load(name="Load", P=sum(p), P1=p[0], P2=p[1], P3=p[2])
    grid.add_line(line)
    grid.add_generator(source, generator)
    grid.add_load(demand, load)
    bus: gce.Bus
    for bus in grid.buses:
        get_bus_emt_template(grid, bus)
    set_emt_model(generator, get_generator_thevenin_rl_emt_template_with_ref(
        grid.var_factory, source_voltage_mode=mode).block, grid.var_factory)
    set_emt_model(line, get_pi_line_emt_template(grid.var_factory, phN=False, phA=True, phB=True, phC=True).block,
                  grid.var_factory)
    set_emt_model(load, get_shunt_r_emt_template(grid.var_factory, phA=True, phB=True, phC=True).block,
                  grid.var_factory)
    pf_options: gce.PowerFlowOptions = gce.PowerFlowOptions(tolerance=1e-10, max_iter=50, control_q=False,
        retry_with_other_methods=False, solver_type=gce.SolverType.NR)
    options: EmtOptions = EmtOptions(time_step=5e-6, simulation_time=2e-5, tolerance=1e-7,
        solver_type=EmtSolverTypes.Symbolic, integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
        initialization_method=EmtInitializationMethod.Explicit)
    problem: EmtProblemDae
    if three_phase:
        pf3: PowerFlowDriver3Ph = PowerFlowDriver3Ph(grid, pf_options)
        pf3.run()
        assert bool(pf3.results.converged)
        problem = EmtProblemDae(grid=grid, options=options, pf_results_3ph=pf3.results)
    else:
        pf: PowerFlowDriver = PowerFlowDriver(grid, pf_options)
        pf.run()
        assert bool(pf.results.converged)
        problem = EmtProblemDae(grid=grid, options=options, pf_results=pf.results)
    return problem, generator


@pytest.mark.parametrize("mode", (TheveninSourceVoltageMode.Balanced, TheveninSourceVoltageMode.Phase))
@pytest.mark.parametrize("z0", (0.02 + 0.2j, 0.04 + 0.6j))
def test_source_abc_law_matches_reciprocal_matrix(mode: TheveninSourceVoltageMode, z0: complex) -> None:
    """Compare authored runtime derivatives with an independent dense R/L solve.

    :param mode: Source voltage capability.
    :param z0: Equal or coupled homopolar impedance.
    :return: None.
    """
    rotation: np.ndarray = np.exp(-2j * np.pi * np.arange(3) / 3.0)
    impedance: np.ndarray = (0.02 + 0.2j) * np.eye(3) + (z0 - (0.02 + 0.2j)) * np.ones((3, 3)) / 3.0
    voltage: np.ndarray = 0.98 * np.exp(0.2j) * rotation + (0.03 - 0.015j) + (0.025 + 0.01j) * rotation.conj()
    emf: np.ndarray = (1.05 + 0.12j) * rotation
    if mode == TheveninSourceVoltageMode.Phase:
        emf = emf + 0.01j + (0.02 - 0.03j) * rotation.conj()
    else:
        pass
    current: np.ndarray = np.linalg.solve(impedance, emf - voltage)
    block: Block = get_generator_thevenin_rl_emt_template_with_ref(VarFactory(), source_voltage_mode=mode).block.children[0]
    time: float
    for time in np.arange(32) / (32.0 * 50.0):
        actual: np.ndarray
        bindings: dict[int, float]
        actual, bindings = _evaluate_source_contract(block, voltage, current, z0, float(time))
        wave_emf: np.ndarray = np.sqrt(2.0) * (emf * np.exp(2j * np.pi * 50.0 * time)).imag
        wave_voltage: np.ndarray = np.sqrt(2.0) * (voltage * np.exp(2j * np.pi * 50.0 * time)).imag
        expected: np.ndarray = np.linalg.solve(impedance.imag / (2.0 * np.pi * 50.0),
                                               wave_emf - wave_voltage - impedance.real @ actual[1])
        np.testing.assert_allclose(actual[0], wave_emf, rtol=0.0, atol=1e-12)
        np.testing.assert_allclose(actual[2], expected, rtol=0.0, atol=1e-9)
        np.testing.assert_allclose(actual[2], 2.0 * np.pi * 50.0 * np.sqrt(2.0)
                                   * (current * np.exp(2j * np.pi * 50.0 * time)).real, rtol=0.0, atol=1e-9)


def test_source_phase_mode_retains_internal_unbalance() -> None:
    """Preserve E0/E2 in phase mode and expose an incompatible balanced seed.

    :return: None.
    """
    rotation: np.ndarray = np.exp(-2j * np.pi * np.arange(3) / 3.0)
    voltage: np.ndarray = rotation + 0.02j + (0.04 - 0.02j) * rotation.conj()
    current: np.ndarray = (0.3 - 0.1j) * rotation + 0.01 + 0.02j * rotation.conj()
    phase_block: Block = get_generator_thevenin_rl_emt_template_with_ref(
        VarFactory(), source_voltage_mode=TheveninSourceVoltageMode.Phase).block.children[0]
    balanced_block: Block = get_generator_thevenin_rl_emt_template_with_ref(VarFactory()).block.children[0]
    phase_result: np.ndarray
    balanced_result: np.ndarray
    phase_result, _ = _evaluate_source_contract(phase_block, voltage, current)
    balanced_result, _ = _evaluate_source_contract(balanced_block, voltage, current)
    expected_derivative: np.ndarray = 2.0 * np.pi * 50.0 * np.sqrt(2.0) * current.real
    np.testing.assert_allclose(phase_result[2], expected_derivative, rtol=0.0, atol=1e-9)
    assert np.linalg.norm(balanced_result[2] - expected_derivative, ord=np.inf) > 1.0
    assert abs(np.sum(balanced_result[0])) < 1e-12


@pytest.mark.parametrize("mode", (TheveninSourceVoltageMode.Balanced, TheveninSourceVoltageMode.Phase))
@pytest.mark.parametrize("three_phase", (False, True))
def test_source_mode_does_not_follow_pf_snapshot_type(mode: TheveninSourceVoltageMode, three_phase: bool) -> None:
    """Native receiving paths preserve the explicit physical mode.

    :param mode: Explicit source capability.
    :param three_phase: Receiving PF result type.
    :return: None.
    """
    problem: EmtProblemDae
    source: gce.Generator
    problem, source = _build_source_case(mode, three_phase)
    marker: Var = _find_source_var(source.emt_model, "source_voltage_mode")
    owner: Block = source.emt_model.children[0]
    assert owner.parameters[marker].value == (0.0 if mode == TheveninSourceVoltageMode.Balanced else 1.0)
    assert problem.grid.generators[0] is source


def test_source_phase_seed_keeps_current_base() -> None:
    """Native PF3 transports quadratures without a second base conversion.

    :return: None.
    """
    problem: EmtProblemDae
    source: gce.Generator
    problem, source = _build_source_case(TheveninSourceVoltageMode.Phase, True)
    pf3: gce.PowerFlowResults3Ph | None = problem.power_flow_results_3ph
    assert pf3 is not None
    voltage: np.ndarray = np.array((pf3.voltage_A[0], pf3.voltage_B[0], pf3.voltage_C[0]))
    power: np.ndarray = np.array((pf3.Sbus_A[0], pf3.Sbus_B[0], pf3.Sbus_C[0])) / problem.grid.Sbase
    current: np.ndarray = 3.0 * np.conj(power / voltage)
    index: int
    phase: str
    for index, phase in enumerate(("A", "B", "C")):
        variable: Var = _find_source_var(source.emt_model, f"i_{phase}")
        derivative: Var = _find_source_var(source.emt_model, f"d_i_{phase}")
        np.testing.assert_allclose(problem.get_x0()[problem.get_var_idx(variable)],
                                   np.sqrt(2.0) * current[index].imag, rtol=0.0, atol=1e-9)
        np.testing.assert_allclose(problem.get_dx0()[problem.get_diff_var_idx(derivative)],
                                   2.0 * np.pi * 50.0 * np.sqrt(2.0) * current[index].real, rtol=0.0, atol=1e-7)


@pytest.mark.parametrize("mode", (TheveninSourceVoltageMode.Balanced, TheveninSourceVoltageMode.Phase))
def test_source_native_balanced_startup(mode: TheveninSourceVoltageMode) -> None:
    """Both capabilities support a native balanced solve and short simulation.

    :param mode: Explicit source capability.
    :return: None.
    """
    problem: EmtProblemDae
    source: gce.Generator
    problem, source = _build_source_case(mode)
    assert problem.initialization_report is not None
    assert problem.initialization_report.status == EmtInitializationStatus.RESOLVED
    solver: JitSymbolicSolver = JitSymbolicSolver(problem=problem, t0=0.0, t_end=2e-5, h=5e-6,
        method=DynamicIntegrationMethod.DaeTrapezoidal, pred_method=DynamicIntegrationMethod.OdeEuler,
        dense_threshold=0, verbose=False)
    values: np.ndarray
    derivatives: np.ndarray
    well_initialized: bool
    converged: bool
    _, values, derivatives, well_initialized, converged = solver.simulate(boundary_updater=problem)
    assert well_initialized and converged
    assert np.all(np.isfinite(values)) and np.all(np.isfinite(derivatives))


def test_source_native_pf3_startup() -> None:
    """A physically consistent per-phase source starts from solved unbalanced PF3.

    :return: None.
    """
    problem: EmtProblemDae
    source: gce.Generator
    problem, source = _build_source_case(TheveninSourceVoltageMode.Phase, True)
    assert problem.initialization_report is not None
    assert problem.initialization_report.status == EmtInitializationStatus.RESOLVED
    solver: JitSymbolicSolver = JitSymbolicSolver(problem=problem, t0=0.0, t_end=2e-5, h=5e-6,
        method=DynamicIntegrationMethod.DaeTrapezoidal, pred_method=DynamicIntegrationMethod.OdeEuler,
        dense_threshold=0, verbose=False)
    values: np.ndarray
    derivatives: np.ndarray
    well_initialized: bool
    converged: bool
    _, values, derivatives, well_initialized, converged = solver.simulate(boundary_updater=problem)
    assert well_initialized and converged
    assert np.all(np.isfinite(values)) and np.all(np.isfinite(derivatives))


@pytest.mark.parametrize("mode", (TheveninSourceVoltageMode.Balanced, TheveninSourceVoltageMode.Phase))
def test_source_runtime_event_controls(mode: TheveninSourceVoltageMode) -> None:
    """Magnitude, angle and frequency controls affect the actual runtime equations.

    :param mode: Explicit source capability.
    :return: None.
    """
    rotation: np.ndarray = np.exp(-2j * np.pi * np.arange(3) / 3.0)
    voltage: np.ndarray = rotation
    current: np.ndarray = (0.3 - 0.1j) * rotation
    block: Block = get_generator_thevenin_rl_emt_template_with_ref(VarFactory(), source_voltage_mode=mode).block.children[0]
    result: np.ndarray
    bindings: dict[int, float]
    result, bindings = _evaluate_source_contract(block, voltage, current, time=0.001,
        events=(("E_scale", 0.8), ("theta_deviation_param", 0.2), ("f_scale", 1.1)))
    emf: np.ndarray = voltage + (0.02 + 0.2j) * current
    expected: np.ndarray = 0.8 * np.sqrt(2.0) * (emf * np.exp(1j * (0.2 + 2.0 * np.pi * 50.0 * 1.1 * 0.001))).imag
    np.testing.assert_allclose(result[0], expected, rtol=0.0, atol=1e-12)
    np.testing.assert_allclose(block.state_eqs[3].eval_uid(bindings), 2.0 * np.pi * 50.0 * 1.1)


@pytest.mark.parametrize("method", (EmtInitializationMethod.Explicit, EmtInitializationMethod.ConsistentNewton))
def test_source_native_colocated_pv_initialization(method: EmtInitializationMethod) -> None:
    """Unequal colocated PV sources retain individual P/Q and passive sequences.

    Evaluate actual native t=0 equations and current derivatives without seed
    replay. Applicability probes then use a separate scratch seed store; an
    unsupported member must leave every existing seed unchanged.

    :param method: Existing native initialization algorithm.
    :return: None.
    """
    grid: gce.MultiCircuit = gce.MultiCircuit(Sbase=2.0, fbase=50.0)
    reference_bus: gce.Bus = grid.add_bus(gce.Bus(name="Phase reference", Vnom=10.0, is_slack=True))
    pv_bus: gce.Bus = grid.add_bus(gce.Bus(name="Balanced PV", Vnom=10.0))
    load_bus: gce.Bus = grid.add_bus(gce.Bus(name="Unequal load", Vnom=10.0))
    reference: gce.Generator = gce.Generator(name="Reference", vset=1.0, Snom=0.75,
        r1=0.001, x1=1.7, r2=0.001, x2=1.7, r0=0.004, x0=0.6)
    first: gce.Generator = gce.Generator(name="PV1", P=0.1, vset=1.01, Snom=1.25,
        Qmin=-0.4, Qmax=0.8, r1=0.02, x1=0.4, r2=0.02, x2=0.4, r0=0.03, x0=0.15)
    second: gce.Generator = gce.Generator(name="PV2", P=0.08, vset=1.01, Snom=0.75,
        Qmin=-0.8, Qmax=0.6, r1=0.03, x1=0.7, r2=0.03, x2=0.7, r0=0.04, x0=0.25)
    grid.add_generator(reference_bus, reference)
    grid.add_generator(pv_bus, first)
    grid.add_generator(pv_bus, second)
    load: gce.Load = gce.Load(name="Load", P=0.4, P1=0.16, P2=0.4 / 3.0, P3=0.4 * 4.0 / 15.0)
    grid.add_load(load_bus, load)
    # Declare the independent reciprocal diagonal primitive through the normal
    # matrix allocation lifecycle; unequal loads create nonzero V0 and V2.
    bus_from: gce.Bus
    bus_to: gce.Bus
    for bus_from, bus_to in ((reference_bus, pv_bus), (pv_bus, load_bus)):
        line: gce.Line = gce.Line(name=bus_from.name + "-" + bus_to.name,
            bus_from=bus_from, bus_to=bus_to, r=0.02, x=0.15)
        line.fill_3_phase_from_sequence()
        line.disable_auto_updates()
        line.ys.values[:] = 0.0
        line.ys.values[1:4, 1:4] = np.eye(3) / complex(0.02, 0.15)
        line.ysh.values[:] = 0.0
        line.ysh.values[1:4, 1:4] = np.eye(3) * complex(0.003, 0.006) * 1e6
        grid.add_line(line)
    bus: gce.Bus
    for bus in grid.buses:
        get_bus_emt_template(grid, bus)
    generator: gce.Generator
    index: int
    for index, generator in enumerate(grid.generators):
        mode: TheveninSourceVoltageMode = TheveninSourceVoltageMode.Phase if index == 0 else TheveninSourceVoltageMode.Balanced
        set_emt_model(generator, get_generator_thevenin_rl_emt_template_with_ref(
            grid.var_factory, source_voltage_mode=mode).block, grid.var_factory)
    # Establish bus voltage identity before setters bind the branch terminals.
    for line in grid.lines:
        template: EmtModelTemplate = get_pi_line_emt_template(grid.var_factory,
            phN=False, phA=True, phB=True, phC=True)
        template.block.set_parameter_in_model(var_name="G_damp", new_value=0.0)
        set_emt_model(line, template.block, grid.var_factory)
    set_emt_model(load, get_load_ZIP_emt_template(grid.var_factory, phA=True, phB=True, phC=True).block,
                  grid.var_factory)
    pf: PowerFlowDriver3Ph = PowerFlowDriver3Ph(grid, gce.PowerFlowOptions(solver_type=gce.SolverType.NR,
        tolerance=1e-9, max_iter=100, control_q=False, retry_with_other_methods=False))
    pf.run()
    assert bool(pf.results.converged)
    problem: EmtProblemDae = EmtProblemDae(grid=grid, options=EmtOptions(
        initialization_method=method, tolerance=1e-6), pf_results_3ph=pf.results)
    solver: JitSymbolicSolver = JitSymbolicSolver(problem=problem, t0=0.0, t_end=0.0, h=5e-6,
        method=DynamicIntegrationMethod.DaeTrapezoidal, pred_method=DynamicIntegrationMethod.OdeEuler,
        dense_threshold=0, verbose=False)
    times: np.ndarray
    samples: np.ndarray
    derivatives: np.ndarray
    initialized: bool
    converged: bool
    times, samples, derivatives, initialized, converged = solver.simulate(boundary_updater=problem)
    assert initialized and len(times) == 1 and times[0] == 0.0
    assert np.all(np.isfinite(samples)) and np.all(np.isfinite(derivatives))

    # Bind all actual native values by UID, including the t=0 runtime parameter
    # buffer. A consistent Newton point alone does not prove individual power.
    bindings: dict[int, float] = dict()
    uid: int
    position: int
    for uid, position in problem.uid2idx_vars.items():
        bindings[uid] = float(samples[0, position])
    for uid, position in problem.uid2idx_diff.items():
        bindings[uid] = float(derivatives[0, position])
    for uid, position in problem.uid2idx_event_params.items():
        bindings[uid] = float(solver._full_parameter_buffer[position])
    for uid, position in problem.uid2idx_params.items():
        bindings[uid] = float(solver._full_parameter_buffer[problem.get_variable_parameter_number() + position])
    bindings[problem.glob_time.uid] = float(times[0])
    equation: Expr
    for equation in problem.get_algebraic_eqs():
        assert abs(float(equation.eval_uid(bindings))) <= 1e-6
    differential: Var
    for position, differential in enumerate(problem.get_diff_vars()):
        assert abs(bindings[differential.uid] - float(problem.get_state_eqs()[position].eval_uid(bindings))) <= 1e-6
    rotation: np.ndarray = np.exp(-2j * np.pi * np.arange(3) / 3.0)
    voltage: np.ndarray = np.array((pf.results.voltage_A[1], pf.results.voltage_B[1], pf.results.voltage_C[1]))
    v0: complex = complex(np.mean(voltage))
    v1: complex = complex(np.mean(voltage / rotation))
    v2: complex = complex(np.mean(voltage * rotation))
    total_q: float = float((pf.results.Sbus_A[1] + pf.results.Sbus_B[1] + pf.results.Sbus_C[1]).imag)
    qshare: float = (total_q - first.Qmin - second.Qmin) / (first.Qmax + second.Qmax - first.Qmin - second.Qmin)
    group_current: np.ndarray = np.zeros(3, dtype=np.complex128)
    current_refs: tuple[VarPowerFlowReferenceType, ...] = (
        VarPowerFlowReferenceType.i_A, VarPowerFlowReferenceType.i_B, VarPowerFlowReferenceType.i_C,
    )
    omega: float = 2.0 * np.pi * grid.fBase
    current_ref: VarPowerFlowReferenceType
    for generator in (first, second):
        current: np.ndarray = np.zeros(3, dtype=np.complex128)
        for position, current_ref in enumerate(current_refs):
            variable: Var = generator.emt_model.external_mapping[current_ref]
            state_position: int = problem.get_state_vars().index(variable)
            differential = problem.get_diff_vars()[state_position]
            current[position] = complex(bindings[differential.uid] / omega, bindings[variable.uid]) / np.sqrt(2.0)
        group_current += current
        expected_q: float = generator.Qmin + qshare * (generator.Qmax - generator.Qmin)
        power: complex = complex(np.mean(voltage * current.conj()) * grid.Sbase)
        np.testing.assert_allclose(power, complex(generator.P, expected_q), rtol=0.0, atol=1e-6)
        np.testing.assert_allclose(np.mean(current), -v0 / complex(generator.R0, generator.X0), rtol=0.0, atol=1e-6)
        np.testing.assert_allclose(np.mean(current * rotation), -v2 / complex(generator.R1, generator.X1), rtol=0.0, atol=1e-6)
    np.testing.assert_allclose(group_current, 3.0 * np.conj(np.array((pf.results.Sbus_A[1],
        pf.results.Sbus_B[1], pf.results.Sbus_C[1])) / grid.Sbase / voltage), rtol=0.0, atol=1e-6)

    # Normal construction above proves identical-UID source wrappers work.
    # Probe whole-group rejection independently, without replaying any seed into
    # the accepted problem or changing its solver state or runtime parameters.
    injections: list[InjectionParent] = list(grid.get_injection_devices_iter())
    source_indices: np.ndarray = np.array((injections.index(first), injections.index(second)), dtype=np.int64)
    residual: np.ndarray = np.array((pf.results.Sbus_N[1], pf.results.Sbus_A[1],
        pf.results.Sbus_B[1], pf.results.Sbus_C[1])) / grid.Sbase
    mapping: dict[Var, Const] = dict()
    for generator in (first, second):
        assign_static_api_object_mapping_for_device(grid, generator, generator.emt_model, mapping, Logger())
    sentinel: np.ndarray = np.full((len(injections), 4), 0.3 + 0.2j)
    scratch: np.ndarray = sentinel.copy()
    # Both unsupported unit/capability flags must reject every member atomically.
    second.use_reactive_power_curve = True
    assert not problem._try_seed_colocated_balanced_pv_sources(grid, 1, injections, source_indices, residual,
        grid.Sbase, mapping, scratch)
    second.use_reactive_power_curve = False
    second.use_kw = True
    assert not problem._try_seed_colocated_balanced_pv_sources(grid, 1, injections, source_indices, residual,
        grid.Sbase, mapping, scratch)
    second.use_kw = False
    for index in range(len(injections)):
        np.testing.assert_array_equal(scratch[index], sentinel[index])
    # Preserve legacy allocation for every unsupported complete-group shape.
    second.active = False
    assert not problem._try_seed_colocated_balanced_pv_sources(grid, 1, injections, source_indices, residual,
        grid.Sbase, mapping, scratch)
    second.active = True
    second.control_mode = GeneratorControlMode.Q
    assert not problem._try_seed_colocated_balanced_pv_sources(grid, 1, injections, source_indices, residual,
        grid.Sbase, mapping, scratch)
    second.control_mode = GeneratorControlMode.V
    second.control_bus = reference_bus
    assert not problem._try_seed_colocated_balanced_pv_sources(grid, 1, injections, source_indices, residual,
        grid.Sbase, mapping, scratch)
    second.control_bus = None
    pv_bus.is_slack = True
    assert not problem._try_seed_colocated_balanced_pv_sources(grid, 1, injections, source_indices, residual,
        grid.Sbase, mapping, scratch)
    pv_bus.is_slack = False
    pv_bus.is_dc = True
    assert not problem._try_seed_colocated_balanced_pv_sources(grid, 1, injections, source_indices, residual,
        grid.Sbase, mapping, scratch)
    pv_bus.is_dc = False
    assert not problem._try_seed_colocated_balanced_pv_sources(grid, 1, injections, source_indices[:1], residual,
        grid.Sbase, mapping, scratch)
    load.bus = pv_bus
    assert not problem._try_seed_colocated_balanced_pv_sources(grid, 1, injections, source_indices, residual,
        grid.Sbase, mapping, scratch)
    load.bus = load_bus
    source: Block
    for source in first.emt_model.get_all_blocks():
        mode_uid: int | None = source.dynamic_model_contract.emt_finite_reciprocal_source_mode_var_uid
        if mode_uid is None:
            pass
        else:
            source.dynamic_model_contract.emt_finite_reciprocal_source_mode_var_uid = None
            assert not problem._try_seed_colocated_balanced_pv_sources(grid, 1, injections, source_indices, residual,
                grid.Sbase, mapping, scratch)
            source.dynamic_model_contract.emt_finite_reciprocal_source_mode_var_uid = mode_uid
            parameter: Var
            for parameter in source.parameters:
                if parameter.uid == mode_uid:
                    mapping[parameter] = Const(1)
                    assert not problem._try_seed_colocated_balanced_pv_sources(grid, 1, injections, source_indices, residual,
                        grid.Sbase, mapping, scratch)
                    del mapping[parameter]
                else:
                    pass
    for index in range(len(injections)):
        np.testing.assert_array_equal(scratch[index], sentinel[index])
    # A changed consumed voltage/current/phasor UID is not a compatible wrapper.
    ref: VarPowerFlowReferenceType
    for ref in (VarPowerFlowReferenceType.i_A, VarPowerFlowReferenceType.v_A, VarPowerFlowReferenceType.UR_A):
        original_ref: Var = first.emt_model.external_mapping[ref]
        first.emt_model.external_mapping[ref] = grid.var_factory.add_var("Unrelated wrapper reference")
        assert not problem._try_seed_colocated_balanced_pv_sources(grid, 1, injections, source_indices, residual,
            grid.Sbase, mapping, scratch)
        first.emt_model.external_mapping[ref] = original_ref
    first.emt_model.dynamic_model_contract.emt_terminal_current_contributions = list((
        EmtTerminalCurrentContribution(EmtTerminalSide.BUS, EmtTerminalConductor.PHASE_A, VarPowerFlowReferenceType.i_A),
    ))
    assert not problem._try_seed_colocated_balanced_pv_sources(grid, 1, injections, source_indices, residual,
        grid.Sbase, mapping, scratch)
    first.emt_model.dynamic_model_contract.emt_terminal_current_contributions = list()
    first.emt_model.external_mapping[VarPowerFlowReferenceType.i_N] = first.emt_model.external_mapping[VarPowerFlowReferenceType.i_A]
    assert not problem._try_seed_colocated_balanced_pv_sources(grid, 1, injections, source_indices, residual,
        grid.Sbase, mapping, scratch)
    del first.emt_model.external_mapping[VarPowerFlowReferenceType.i_N]
    # Legacy differential residuals belong to an additional equation owner even
    # when that wrapper has no declared derivative variables.
    assert first.emt_model.dynamic_model_contract.emt_finite_reciprocal_source_mode_var_uid is None
    legacy_equations: list[Expr] = first.emt_model.differential_eqs
    first.emt_model.differential_eqs = list((Const(1.0),))
    assert not problem._try_seed_colocated_balanced_pv_sources(grid, 1, injections, source_indices, residual,
        grid.Sbase, mapping, scratch)
    first.emt_model.differential_eqs = legacy_equations
    for index in range(len(injections)):
        np.testing.assert_array_equal(scratch[index], sentinel[index])
    # Check both applicability tolerances on the representable inside/outside
    # boundary. Static limits/units and the solved snapshot remain untouched.
    voltage_offset: float
    accepted: bool
    for voltage_offset, accepted in ((np.nextafter(1e-6, 0.0), True), (1.000001e-6, False)):
        first.Vset = np.nextafter(abs(v1) + voltage_offset, abs(v1)) if accepted else abs(v1) + voltage_offset
        second.Vset = first.Vset
        assert problem._try_seed_colocated_balanced_pv_sources(grid, 1, injections, source_indices, residual,
            grid.Sbase, mapping, scratch) == accepted
    first.Vset = abs(v1)
    setpoint_offset: float
    for setpoint_offset, accepted in ((np.nextafter(1e-8, 0.0), True), (1.000001e-8, False)):
        second.Vset = np.nextafter(first.Vset + setpoint_offset, first.Vset) if accepted else first.Vset + setpoint_offset
        assert problem._try_seed_colocated_balanced_pv_sources(grid, 1, injections, source_indices, residual,
            grid.Sbase, mapping, scratch) == accepted


def test_source_default_impedance_fallback_is_runtime_only() -> None:
    """Absent optional sequences are logged without changing physical data.

    :return: None.
    """
    source: gce.Generator = gce.Generator(r1=0.02, x1=0.2)
    block: Block = get_generator_thevenin_rl_emt_template_with_ref(VarFactory()).block.children[0]
    before: dict[str, object] = block.to_dict()
    mapping: dict[Var, Const] = dict()
    logger: Logger = Logger()
    assign_thevenin_source_static_api_mapping(source, block, mapping, logger)
    assert source.R0 == source.X0 == source.R2 == source.X2 == 1e-20
    assert block.to_dict() == before
    assert mapping[block.api_obj_mapping[ParamPowerFlowReferenceType.thevenin_source_r0_pu]].value == source.R1
    assert mapping[block.api_obj_mapping[ParamPowerFlowReferenceType.thevenin_source_x0_pu]].value == source.X1
    assert "Z0" in str(logger) and "Z2" in str(logger)


@pytest.mark.parametrize("r1,x1,r0,x0,r2,x2,connection", (
    (-0.01, 0.2, 0.04, 0.6, 0.02, 0.2, ShuntConnectionType.GroundedStar),
    (0.02, 0.0, 0.04, 0.6, 0.02, 0.2, ShuntConnectionType.GroundedStar),
    (0.02, np.nan, 0.04, 0.6, 0.02, 0.2, ShuntConnectionType.GroundedStar),
    (0.02, 0.2, 0.04, 0.0, 0.02, 0.2, ShuntConnectionType.GroundedStar),
    (0.02, 0.2, -0.04, 0.6, 0.02, 0.2, ShuntConnectionType.GroundedStar),
    (0.02, 0.2, 0.04, np.inf, 0.02, 0.2, ShuntConnectionType.GroundedStar),
    (0.02, 0.2, 0.04, 0.6, 0.03, 0.35, ShuntConnectionType.GroundedStar),
    (0.02, 0.2, 0.04, 0.6, 1e-20, 0.2, ShuntConnectionType.GroundedStar),
    (0.02, 0.2, 0.04, 0.6, 0.02, 0.2, ShuntConnectionType.Delta),
))
def test_source_rejects_known_incompatible_family(
        r1: float, x1: float, r0: float, x0: float, r2: float, x2: float,
        connection: ShuntConnectionType,
) -> None:
    """Known incompatibilities leave required aliases unresolved and data intact.

    :param r1: Physical positive resistance.
    :param x1: Physical positive reactance.
    :param r0: Physical zero resistance.
    :param x0: Physical zero reactance.
    :param r2: Physical negative resistance.
    :param x2: Physical negative reactance.
    :param connection: Physical connection.
    :return: None.
    """
    source: gce.Generator = gce.Generator(r1=r1, x1=x1, r0=r0, x0=x0, r2=r2, x2=x2)
    source.conn = connection
    block: Block = get_generator_thevenin_rl_emt_template_with_ref(VarFactory()).block.children[0]
    mapping: dict[Var, Const] = dict()
    logger: Logger = Logger()
    before: np.ndarray = np.array((source.R1, source.X1, source.R0, source.X0, source.R2, source.X2))
    assign_thevenin_source_static_api_mapping(source, block, mapping, logger)
    assert not mapping
    assert logger.has_errors()
    np.testing.assert_equal(np.array((source.R1, source.X1, source.R0, source.X0, source.R2, source.X2)), before)
    assert source.conn == connection
    parameter: Var = block.api_obj_mapping[ParamPowerFlowReferenceType.thevenin_source_r0_pu]
    with pytest.raises(ValueError, match="thevenin_source_r0_pu"):
        resolve_constant_parameter_initial_value(
            device=source,
            simulation_mode=DynamicSimulationMode.EMT,
            root_block=block,
            owner_block=block,
            parameter=parameter,
            declared_value=block.parameters[parameter],
            problem_mapping=mapping,
        )


@pytest.mark.parametrize("mode", (TheveninSourceVoltageMode.Balanced, TheveninSourceVoltageMode.Phase))
def test_source_block_roundtrip_preserves_contract(mode: TheveninSourceVoltageMode) -> None:
    """Declarative reconstruction preserves the authored equations and marker.

    :param mode: Persisted source capability.
    :return: None.
    """
    original: Block = get_generator_thevenin_rl_emt_template_with_ref(VarFactory(), source_voltage_mode=mode).block
    restored: Block = Block.parse(original.to_dict())
    # Only the electrical child declares capability, through its own parameter.
    assert restored.dynamic_model_contract.emt_finite_reciprocal_source_mode_var_uid is None
    restored_mode: Var = _find_source_var(restored, "source_voltage_mode")
    assert restored.children[0].dynamic_model_contract.emt_finite_reciprocal_source_mode_var_uid == restored_mode.uid
    validate_dynamic_model_contract(restored.children[0])
    rotation: np.ndarray = np.exp(-2j * np.pi * np.arange(3) / 3.0)
    voltage: np.ndarray = rotation + 0.02j
    current: np.ndarray = (0.3 - 0.1j) * rotation + 0.01j
    expected: np.ndarray
    actual: np.ndarray
    expected, _ = _evaluate_source_contract(original.children[0], voltage, current)
    actual, _ = _evaluate_source_contract(restored.children[0], voltage, current)
    np.testing.assert_allclose(actual, expected, rtol=0.0, atol=1e-12)
    assert restored.to_dict() == original.to_dict()


@pytest.mark.parametrize("mode", (TheveninSourceVoltageMode.Balanced, TheveninSourceVoltageMode.Phase))
def test_source_project_roundtrip_and_instance_lifecycle(tmp_path: Path, mode: TheveninSourceVoltageMode) -> None:
    """Use real project persistence and independent template instance ownership.

    :param tmp_path: Pytest project output directory.
    :param mode: Authored source capability to preserve through the native codec.
    :return: None.
    """
    grid: gce.MultiCircuit = gce.MultiCircuit()
    bus: gce.Bus = grid.add_bus(gce.Bus(name="Source", is_slack=True))
    template: EmtModelTemplate = get_generator_thevenin_rl_emt_template_with_ref(
        grid.var_factory, source_voltage_mode=mode)
    grid.add_emt_model(template)
    first: gce.Generator = grid.add_generator(bus, gce.Generator(name="First"))
    second: gce.Generator = grid.add_generator(bus, gce.Generator(name="Second"))
    first.emt_template = template
    second.emt_template = template
    assert first.emt_model is not second.emt_model and first.emt_model is not template.block
    first_marker: Var = _find_source_var(first.emt_model, "source_voltage_mode")
    second_marker: Var = _find_source_var(second.emt_model, "source_voltage_mode")
    assert first_marker is not second_marker
    assert first.emt_model.children[0].dynamic_model_contract.emt_finite_reciprocal_source_mode_var_uid == first_marker.uid
    assert second.emt_model.children[0].dynamic_model_contract.emt_finite_reciprocal_source_mode_var_uid == second_marker.uid
    path: Path = tmp_path / "thevenin.veragrid"
    assert not FileSave(circuit=grid, file_name=str(path)).save().has_errors()
    loaded: gce.MultiCircuit | None = FileOpen(str(path)).open()
    assert loaded is not None
    assert loaded.generators[0].emt_template is loaded.emt_models[0]
    assert loaded.generators[1].emt_template is loaded.emt_models[0]
    assert loaded.generators[0].emt_model is not loaded.generators[1].emt_model
    original_mode: Var = _find_source_var(loaded.emt_models[0].block, "source_voltage_mode")
    expected_mode_code: float = 0.0 if mode == TheveninSourceVoltageMode.Balanced else 1.0
    assert loaded.emt_models[0].block.children[0].parameters[original_mode].value == expected_mode_code
    # Providers and both independent instances retain local identity after load.
    persisted_root: Block
    for persisted_root in (loaded.emt_models[0].block, loaded.generators[0].emt_model, loaded.generators[1].emt_model):
        persisted_mode: Var = _find_source_var(persisted_root, "source_voltage_mode")
        assert persisted_root.dynamic_model_contract.emt_finite_reciprocal_source_mode_var_uid is None
        assert persisted_root.children[0].dynamic_model_contract.emt_finite_reciprocal_source_mode_var_uid == persisted_mode.uid
        validate_dynamic_model_contract(persisted_root.children[0])
    else:
        pass
    replacement: EmtModelTemplate = get_generator_thevenin_rl_emt_template_with_ref(loaded.var_factory)
    loaded.add_emt_model(replacement)
    loaded.generators[0].emt_template = replacement
    replacement_mode: Var = _find_source_var(loaded.generators[0].emt_model, "source_voltage_mode")
    assert loaded.generators[0].emt_model.children[0].dynamic_model_contract.emt_finite_reciprocal_source_mode_var_uid == replacement_mode.uid
    retained_model: Block = loaded.generators[1].emt_model
    assert loaded.generators[1].emt_template is loaded.emt_models[0]
    loaded.delete_emt_model(replacement)
    assert replacement not in loaded.emt_models
    assert loaded.generators[1].emt_template is loaded.emt_models[0]
    assert loaded.generators[1].emt_model is retained_model
    validate_dynamic_model_contract(retained_model.children[0])


@pytest.mark.parametrize("invalid_kind", (
    "unreachable", "boolean_uid", "wrapper", "event", "expression", "undefined", "bad_code", "boolean_code",
    "missing_r1", "missing_x1", "missing_r0", "missing_x0", "foreign_alias",
    "dual_event", "dual_mode", "dual_diff", "ancestor_event", "ancestor_mode", "ancestor_diff",
    "sibling_event", "sibling_mode", "sibling_diff",
))
def test_source_capability_declared_reference_validation(invalid_kind: str) -> None:
    """Reject declarations that could misclassify an unsupported source.

    :param invalid_kind: Corrupt identity, ownership, static mode or impedance boundary.
    :return: None.
    """
    factory: VarFactory = VarFactory()
    root: Block = get_generator_thevenin_rl_emt_template_with_ref(factory).block
    owner: Block = root.children[0]
    marker: Var = _find_source_var(owner, "source_voltage_mode")
    validate_dynamic_model_contract(owner)
    expected_error: type[Exception] = KeyError
    # Exercise the actual validator rather than guessing capability from names.
    if invalid_kind in (
            "dual_event", "dual_mode", "dual_diff", "ancestor_event", "ancestor_mode", "ancestor_diff",
            "sibling_event", "sibling_mode", "sibling_diff",
    ):
        collision_owner: Block = owner
        if invalid_kind.startswith("ancestor_"):
            collision_owner = root
        elif invalid_kind.startswith("sibling_"):
            collision_owner = Block(name="Runtime sibling")
            root.children = list((owner, collision_owner))
        else:
            pass
        # Distinct objects must still collide by their canonical symbolic UID.
        runtime_marker: Var = Var(name="runtime_mode_alias", uid=marker.uid)
        if invalid_kind.endswith("_event"):
            collision_owner.event_dict[runtime_marker] = factory.add_const(1.0)
        elif invalid_kind.endswith("_mode"):
            collision_owner.mode_dict[runtime_marker] = factory.add_const(1.0)
        else:
            collision_owner.diff_vars = list((runtime_marker,))
        owner = root
        expected_error = ValueError
    elif invalid_kind == "unreachable":
        owner.dynamic_model_contract.emt_finite_reciprocal_source_mode_var_uid = factory.add_var(name="unowned").uid
    elif invalid_kind == "boolean_uid":
        owner.dynamic_model_contract.emt_finite_reciprocal_source_mode_var_uid = True
        expected_error = TypeError
    elif invalid_kind == "wrapper":
        root.dynamic_model_contract.emt_finite_reciprocal_source_mode_var_uid = marker.uid
        owner = root
    elif invalid_kind == "event":
        owner.event_dict[marker] = owner.parameters.pop(marker)
        expected_error = ValueError
    elif invalid_kind == "expression":
        owner.parameters[marker] = marker + factory.add_const(0.0)
        expected_error = TypeError
    elif invalid_kind == "undefined":
        owner.parameters[marker] = factory.add_const(None)
        expected_error = ValueError
    elif invalid_kind == "bad_code":
        owner.parameters[marker] = factory.add_const(2.0)
        expected_error = ValueError
    elif invalid_kind == "boolean_code":
        owner.parameters[marker] = factory.add_const(True)
        expected_error = ValueError
    elif invalid_kind == "missing_r1":
        del owner.api_obj_mapping[ParamPowerFlowReferenceType.R1]
    elif invalid_kind == "missing_x1":
        del owner.api_obj_mapping[ParamPowerFlowReferenceType.X1]
    elif invalid_kind == "missing_r0":
        del owner.api_obj_mapping[ParamPowerFlowReferenceType.thevenin_source_r0_pu]
    elif invalid_kind == "missing_x0":
        del owner.api_obj_mapping[ParamPowerFlowReferenceType.thevenin_source_x0_pu]
    else:
        owner.api_obj_mapping[ParamPowerFlowReferenceType.R1] = factory.add_var(name="foreign_resistance")
    with pytest.raises(expected_error):
        validate_dynamic_model_contract(owner)
    # Both canonical writers reject the same malformed declaration before data leaves the tree.
    with pytest.raises(expected_error):
        root.to_dict()
    with pytest.raises(expected_error):
        BlockSaver(var_factory=factory).save_block(root, main=True)


@pytest.mark.parametrize("version, has_modal_fields", (
    (1, False), (2, False), (3, False), (4, False), (5, False), (6, False),
    (7, False), (7, True), (8, True),
))
def test_source_capability_legacy_contract_versions(version: int, has_modal_fields: bool) -> None:
    """Read old contracts without inferred capability and enforce the new schema.

    :param version: Persisted contract version whose exact field set is exercised.
    :param has_modal_fields: Whether this historical schema owns modal metadata.
    :return: None.
    """
    data: dict[str, object] = DynamicModelContract().to_data()
    data["version"] = version
    # Reproduce the declared historical key sets, including discarded metadata.
    if version < 7 or (version == 7 and has_modal_fields):
        del data["emt_finite_reciprocal_source_mode_var_uid"]
    else:
        pass
    if has_modal_fields:
        data["modal_template_kind"] = "configurable_integrator"
        data["modal_template_config"] = dict((("scaling", "GAIN"),))
    else:
        del data["modal_template_kind"]
        del data["modal_template_config"]
    if version in (2, 3, 4, 5):
        data["rms_terminal_power_contributions"] = list()
    else:
        pass
    if version in (1, 2):
        del data["emt_terminal_current_contributions"]
    else:
        pass
    if version in (1, 2, 3):
        del data["emt_internal_grounding_link"]
    else:
        pass
    if version in (1, 2, 3, 4):
        del data["rms_physical_measurement_point"]
    else:
        pass
    restored: DynamicModelContract = dynamic_model_contract_from_data(data)
    assert restored.emt_finite_reciprocal_source_mode_var_uid is None
    assert restored.to_data()["version"] == 8
    if has_modal_fields:
        assert restored.modal_template_kind == "configurable_integrator"
        assert restored.modal_template_config == data["modal_template_config"]
    else:
        assert restored.modal_template_kind is None
        assert restored.modal_template_config is None

    # Each branch declaration is mandatory only in the complete schema that
    # owns it. Mixed, partial and combined version-seven records fail closed.
    field_name: str
    for field_name in (
            "emt_finite_reciprocal_source_mode_var_uid",
            "modal_template_kind", "modal_template_config",
    ):
        malformed: dict[str, object] = dict(data)
        if field_name in malformed:
            del malformed[field_name]
        else:
            malformed[field_name] = None
        with pytest.raises(KeyError):
            dynamic_model_contract_from_data(malformed)
    else:
        pass
    if version == 7 or version == 8:
        combined_seven: dict[str, object] = DynamicModelContract().to_data()
        combined_seven["version"] = 7
        with pytest.raises(KeyError):
            dynamic_model_contract_from_data(combined_seven)
    else:
        pass

    # Reuse the typed readers: metadata names remain data, while nested
    # objects and noninteger source identities are never accepted as records.
    if has_modal_fields:
        invalid_kind: dict[str, object] = dict(data)
        invalid_kind["modal_template_kind"] = True
        with pytest.raises(TypeError):
            dynamic_model_contract_from_data(invalid_kind)
        invalid_config: dict[str, object] = dict(data)
        invalid_config["modal_template_config"] = dict((("nested", list()),))
        with pytest.raises(TypeError):
            dynamic_model_contract_from_data(invalid_config)
    else:
        pass
    # Neither an implicit missing declaration nor unexpected fields are accepted.
    if "emt_finite_reciprocal_source_mode_var_uid" in data:
        del data["emt_finite_reciprocal_source_mode_var_uid"]
        with pytest.raises(KeyError):
            dynamic_model_contract_from_data(data)
        invalid_uid: object
        for invalid_uid in (True, False, "123", 1.5):
            data["emt_finite_reciprocal_source_mode_var_uid"] = invalid_uid
            with pytest.raises(TypeError):
                dynamic_model_contract_from_data(data)
        else:
            pass
        data["emt_finite_reciprocal_source_mode_var_uid"] = 123
        assert dynamic_model_contract_from_data(data).emt_finite_reciprocal_source_mode_var_uid == 123
        data["unexpected_capability"] = None
    else:
        data["emt_finite_reciprocal_source_mode_var_uid"] = 123
    with pytest.raises(KeyError):
        dynamic_model_contract_from_data(data)


@pytest.mark.parametrize("mode", (TheveninSourceVoltageMode.Balanced, TheveninSourceVoltageMode.Phase))
def test_source_capability_copy_identity(mode: TheveninSourceVoltageMode) -> None:
    """Bind each copy to its local mode through instance and editor lifecycles.

    :param mode: Source mode retained while symbolic copy identities change.
    :return: None.
    """
    factory: VarFactory = VarFactory()
    original: Block = get_generator_thevenin_rl_emt_template_with_ref(factory, source_voltage_mode=mode).block
    original_marker: Var = _find_source_var(original, "source_voltage_mode")
    instance: Block = duplicate_block(block=original, var_factory=factory)
    editor: Block = duplicate_block_vars_uid(block=original, source_var_factory=factory, target_var_factory=VarFactory())
    deep: Block = copy.deepcopy(original)
    # Copying editor state retains its actual variable objects and owning tree.
    committed: Block = Block(name="Persistent editor root")
    copy_block_state(source_block=editor, target_block=committed)
    candidate: Block
    for candidate in (instance, editor, deep, committed):
        candidate_marker: Var = _find_source_var(candidate, "source_voltage_mode")
        assert candidate_marker is not original_marker
        assert candidate.children[0].dynamic_model_contract.emt_finite_reciprocal_source_mode_var_uid == candidate_marker.uid
        assert candidate.dynamic_model_contract.emt_finite_reciprocal_source_mode_var_uid is None
        validate_dynamic_model_contract(candidate.children[0])
        if candidate is instance:
            assert candidate_marker.uid != original_marker.uid
        else:
            assert candidate_marker.uid == original_marker.uid
        assert candidate.children[0].parameters[candidate_marker].value == original.children[0].parameters[original_marker].value
    else:
        pass
    assert committed.children[0] is editor.children[0]
    assert committed.dynamic_model_contract is editor.dynamic_model_contract


@pytest.mark.parametrize("generic_delete", (False, True))
def test_delete_emt_template_uses_canonical_references(generic_delete: bool) -> None:
    """Clear matching native references without altering independent Blocks.

    :param generic_delete: Route removal through generic Assets dispatch.
    :return: None.
    """
    grid: gce.MultiCircuit = gce.MultiCircuit()
    source_bus: gce.Bus = grid.add_bus(gce.Bus(name="Source", is_slack=True))
    demand_bus: gce.Bus = grid.add_bus(gce.Bus(name="Demand"))
    bus: gce.Bus
    for bus in grid.buses:
        get_bus_emt_template(grid, bus)

    # Reusable providers are registered before materialized device instances.
    removed_source: EmtModelTemplate = get_generator_thevenin_rl_emt_template_with_ref(
        grid.var_factory, name="Removed source")
    retained_source: EmtModelTemplate = get_generator_thevenin_rl_emt_template_with_ref(
        grid.var_factory, name="Retained source", source_voltage_mode=TheveninSourceVoltageMode.Phase)
    removed_line: EmtModelTemplate = get_pi_line_emt_template(grid.var_factory, name="Removed line")
    retained_line: EmtModelTemplate = get_pi_line_emt_template(grid.var_factory, name="Retained line")
    template: EmtModelTemplate
    for template in (removed_source, retained_source, removed_line, retained_line):
        grid.add_emt_model(template)

    matching_generator: gce.Generator = grid.add_generator(source_bus, gce.Generator(name="Matching"))
    unrelated_generator: gce.Generator = grid.add_generator(source_bus, gce.Generator(name="Unrelated"))
    unassigned_generator: gce.Generator = grid.add_generator(source_bus, gce.Generator(name="Unassigned"))
    matching_generator.emt_template = removed_source
    unrelated_generator.emt_template = retained_source
    matching_line: gce.Line = gce.Line(bus_from=source_bus, bus_to=demand_bus, name="Matching line")
    unrelated_line: gce.Line = gce.Line(bus_from=source_bus, bus_to=demand_bus, name="Unrelated line")
    unassigned_line: gce.Line = gce.Line(bus_from=source_bus, bus_to=demand_bus, name="Unassigned line")
    line: gce.Line
    for line in (matching_line, unrelated_line, unassigned_line):
        grid.add_line(line)
    matching_line.emt_template = removed_line
    unrelated_line.emt_template = retained_line

    # Snapshot identity after ordinary assignment/rebinding has completed.
    devices: tuple[gce.Generator | gce.Line, ...] = (
        matching_generator, unrelated_generator, unassigned_generator,
        matching_line, unrelated_line, unassigned_line,
    )
    device: gce.Generator | gce.Line
    models_before: tuple[Block, ...] = tuple(device.emt_model for device in devices)
    bus_models_before: tuple[Block, ...] = tuple(bus.emt_model for bus in grid.buses)
    for template in (removed_source, removed_line, removed_source, removed_line):
        if generic_delete:
            grid.delete_element(template)
        else:
            grid.delete_emt_model(template)
        assert template not in grid.emt_models
        assert matching_generator.emt_template is None
        assert unrelated_generator.emt_template is retained_source
        assert unassigned_generator.emt_template is None
        assert unrelated_line.emt_template is retained_line
        assert unassigned_line.emt_template is None
    assert matching_line.emt_template is None
    index: int
    for index, device in enumerate(devices):
        assert device.emt_model is models_before[index]
    for index, bus in enumerate(grid.buses):
        assert bus.emt_model is bus_models_before[index]

    # A device reference can be cleared even when the provider is absent.
    absent_template: EmtModelTemplate = get_generator_thevenin_rl_emt_template_with_ref(
        grid.var_factory, name="Unregistered source")
    matching_generator.emt_template = absent_template
    absent_model: Block = matching_generator.emt_model
    if generic_delete:
        grid.delete_element(absent_template)
    else:
        grid.delete_emt_model(absent_template)
    assert matching_generator.emt_template is None
    assert matching_generator.emt_model is absent_model
    assert unrelated_generator.emt_template is retained_source
    assert unrelated_line.emt_template is retained_line
