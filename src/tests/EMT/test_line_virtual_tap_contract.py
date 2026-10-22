"""Power-preserving Line coordinates through EMT equations and native startup."""

from pathlib import Path

import numpy as np
import pytest

import VeraGridEngine.api as gce
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.static_parameter_mapping_unified import assign_static_api_object_mapping_for_device
from VeraGridEngine.Devices.Events.emt_events_group import EmtEventsGroup
from VeraGridEngine.IO.file_open import FileOpen
from VeraGridEngine.IO.file_save import FileSave
from VeraGridEngine.Simulations.EMT.emt_solver_factory import build_emt_solver
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.EMT.solvers.structural_compiled_solver import StructuralCompiledSolver
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from VeraGridEngine.Simulations.PowerFlow3ph.power_flow_results_3ph import PowerFlowResults3Ph
from VeraGridEngine.Templates.Emt.pi_line_emt_template import get_pi_line_emt_template
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
from VeraGridEngine.enumerations import DynamicIntegrationMethod, EmtInitializationMethod, EmtInitializationStatus, ParamPowerFlowReferenceType, VarPowerFlowReferenceType
from tests.EMT.test_emt_initialization_workflow import TwoBusRealEmtContext, build_two_bus_real_emt_case, evaluate_algebraic_residual_inf


@pytest.mark.parametrize("frequency", (50.0, 60.0))
@pytest.mark.parametrize("reverse", (False, True))
@pytest.mark.parametrize("phase_mask", ((True, True, True, True), (False, True, True, True), (False, True, False, True)))
@pytest.mark.parametrize("damping", (0.0, 1.0e-5))
def test_pi_line_virtual_tap_runtime_init_and_derivatives(
        frequency: float, reverse: bool, phase_mask: tuple[bool, bool, bool, bool], damping: float) -> None:
    """Check every PI equation against independent sinusoidal physical matrices.

    :param frequency: Fundamental frequency in Hz.
    :param reverse: Reverse the unequal terminal voltage bases.
    :param phase_mask: Active NABC coordinates, including reduced phase layouts.
    :param damping: Local port damping, separate from the physical half-shunt.
    :return: None.
    """
    grid: gce.MultiCircuit = gce.MultiCircuit(Sbase=100.0, fbase=frequency)
    source: gce.Bus = grid.add_bus(gce.Bus(Vnom=128.04 if reverse else 132.0))
    target: gce.Bus = grid.add_bus(gce.Bus(Vnom=132.0 if reverse else 128.04))
    line: gce.Line = grid.add_line(gce.Line(bus_from=source, bus_to=target, r=0.02, x=0.15))
    # Fixed SI equipment is represented on the from-terminal reference.
    impedance_scale: float = grid.Sbase / source.Vnom ** 2
    resistance: np.ndarray = (3.0 * np.eye(4) + 0.2 * np.ones((4, 4))) * impedance_scale
    reactance: np.ndarray = (24.0 * np.eye(4) + 1.0 * np.ones((4, 4))) * impedance_scale
    conductance: np.ndarray = (2.0e-5 * np.eye(4) + 1.0e-6 * np.ones((4, 4))) / impedance_scale
    susceptance: np.ndarray = (4.0e-5 * np.eye(4) + 2.0e-6 * np.ones((4, 4))) / impedance_scale
    active: np.ndarray = np.flatnonzero(np.array(phase_mask, dtype=bool))
    selector: tuple[np.ndarray, np.ndarray] = np.ix_(active, active)
    count: int = len(active)
    line.fill_3_phase_from_sequence()
    line.disable_auto_updates()
    line.ys.phN, line.ys.phA, line.ys.phB, line.ys.phC = phase_mask
    line.ysh.phN, line.ysh.phA, line.ysh.phB, line.ysh.phC = phase_mask
    line.ys.values[:] = 0.0
    line.ys.values[selector] = np.linalg.inv((resistance + 1j * reactance)[selector])
    line.ysh.values[:] = 0.0
    line.ysh.values[selector] = (conductance + 1j * susceptance)[selector] * 1.0e6
    model: Block = get_pi_line_emt_template(grid.var_factory, phase_mask[0], phase_mask[1], phase_mask[2], phase_mask[3], numerical_damping_conductance=damping).block
    child: Block = model.children[0]
    mapped: dict[Var, Const] = dict()
    assign_static_api_object_mapping_for_device(grid, line, model, mapped, None)
    bindings: dict[int, float] = dict()
    parameter: Var
    value: Const
    for parameter, value in child.parameters.items():
        assert value.value is not None
        bindings[parameter.uid] = float(value.value)
    for parameter, value in mapped.items():
        assert value.value is not None
        bindings[parameter.uid] = float(value.value)
    tap_f: float = 1.0
    tap_t: float = source.Vnom / target.Vnom
    assert bindings[child.api_obj_mapping[ParamPowerFlowReferenceType.vtap_f].uid] == tap_f
    assert bindings[child.api_obj_mapping[ParamPowerFlowReferenceType.vtap_t].uid] == pytest.approx(tap_t)
    assert child.parameters[child.api_obj_mapping[ParamPowerFlowReferenceType.vtap_t]].value == 1.0
    vf_ph: np.ndarray = np.array((0.05 + 0.02j, 1.0 + 0.1j, -0.45 - 0.86j, -0.53 + 0.88j))[active]
    vt_ph: np.ndarray = np.array((0.03 + 0.01j, 0.95 + 0.06j, -0.44 - 0.80j, -0.50 + 0.83j))[active]
    uf: np.ndarray = vf_ph / tap_f
    ut: np.ndarray = vt_ph / tap_t
    series: np.ndarray = np.linalg.solve((resistance + 1j * reactance)[selector], uf - ut)
    current_f: np.ndarray = (series + (conductance + 1j * susceptance)[selector] @ uf / 2.0) / tap_f + damping * vf_ph
    current_t: np.ndarray = (-series + (conductance + 1j * susceptance)[selector] @ ut / 2.0) / tap_t + damping * vt_ph
    capacitance: np.ndarray = susceptance[selector] / (4.0 * np.pi * frequency)
    derivative_f_keys: tuple[VarPowerFlowReferenceType, ...] = (VarPowerFlowReferenceType.d_v_N_f, VarPowerFlowReferenceType.d_v_A_f, VarPowerFlowReferenceType.d_v_B_f, VarPowerFlowReferenceType.d_v_C_f)
    derivative_t_keys: tuple[VarPowerFlowReferenceType, ...] = (VarPowerFlowReferenceType.d_v_N_t, VarPowerFlowReferenceType.d_v_A_t, VarPowerFlowReferenceType.d_v_B_t, VarPowerFlowReferenceType.d_v_C_t)
    powers: np.ndarray = np.empty(8)
    sample: int
    for sample in range(8):
        rotation: complex = complex(np.exp(1j * sample * np.pi / 4.0))
        omega: float = 2.0 * np.pi * frequency
        vf: np.ndarray = np.sqrt(2.0) * np.imag(vf_ph * rotation)
        vt: np.ndarray = np.sqrt(2.0) * np.imag(vt_ph * rotation)
        dvf: np.ndarray = omega * np.sqrt(2.0) * np.real(vf_ph * rotation)
        dvt: np.ndarray = omega * np.sqrt(2.0) * np.real(vt_ph * rotation)
        icap_f: np.ndarray = capacitance @ dvf / tap_f
        icap_t: np.ndarray = capacitance @ dvt / tap_t
        if_port: np.ndarray = np.sqrt(2.0) * np.imag(current_f * rotation)
        it_port: np.ndarray = np.sqrt(2.0) * np.imag(current_t * rotation)
        states: np.ndarray = np.concatenate((np.sqrt(2.0) * np.imag(series * rotation), capacitance @ vf / tap_f, capacitance @ vt / tap_t))
        algebraic: np.ndarray = np.concatenate((icap_f, icap_t, if_port, it_port))
        derivatives: np.ndarray = np.concatenate((omega * np.sqrt(2.0) * np.real(series * rotation), icap_f, icap_t))
        index: int
        for index in range(count):
            bindings[child.in_vars[index].uid] = float(vf[index])
            bindings[child.in_vars[count + index].uid] = float(vt[index])
            bindings[child.external_mapping[derivative_f_keys[active[index]]].uid] = float(dvf[index])
            bindings[child.external_mapping[derivative_t_keys[active[index]]].uid] = float(dvt[index])
        variable: Var
        for index, variable in enumerate(child.state_vars):
            bindings[variable.uid] = float(states[index])
        for index, variable in enumerate(child.algebraic_vars):
            bindings[variable.uid] = float(algebraic[index])
        for index, variable in enumerate(child.diff_vars):
            bindings[variable.uid] = float(derivatives[index])
        # Evaluate runtime, explicit initialization and derivative initialization separately.
        equation: Expr
        for equation in child.algebraic_eqs:
            assert abs(float(equation.eval_uid(bindings))) < 1.0e-12
        for index, equation in enumerate(child.state_eqs):
            np.testing.assert_allclose(equation.eval_uid(bindings), derivatives[index], rtol=1.0e-10, atol=1.0e-12)
        for variable, equation in child.init_eqs.items():
            np.testing.assert_allclose(equation.eval_uid(bindings), bindings[variable.uid], rtol=1.0e-10, atol=1.0e-12)
        for variable, equation in child.diff_init_eqs.items():
            np.testing.assert_allclose(equation.eval_uid(bindings), bindings[variable.uid], rtol=1.0e-10, atol=1.0e-12)
        powers[sample] = float((vf @ if_port + vt @ it_port) / 3.0)
    series_loss: float = float(np.vdot(series, resistance[selector] @ series).real / 3.0)
    shunt_loss: float = float((np.vdot(uf, conductance[selector] @ uf).real + np.vdot(ut, conductance[selector] @ ut).real) / 6.0)
    damping_loss: float = float(damping * (np.vdot(vf_ph, vf_ph).real + np.vdot(vt_ph, vt_ph).real) / 3.0)
    np.testing.assert_allclose(np.mean(powers), series_loss + shunt_loss + damping_loss, rtol=1.0e-10, atol=1.0e-12)


@pytest.mark.parametrize("balanced_pf", (True, False))
@pytest.mark.parametrize("reverse", (False, True))
@pytest.mark.parametrize("frequency", (50.0, 60.0))
def test_pi_line_pf_pf3_startup_and_steps(balanced_pf: bool, reverse: bool, frequency: float) -> None:
    """Preserve unequal-base PF seeds through native projection and refined steps.

    :param balanced_pf: Select balanced PF or actual three-phase PF initialization.
    :param reverse: Reverse the terminal voltage bases.
    :param frequency: Fundamental frequency in Hz.
    :return: None.
    """
    errors: np.ndarray = np.empty(2)
    step_index: int
    step: float
    for step_index, step in enumerate((5.0e-6, 2.5e-6)):
        original: EmtProblemDae
        context: TwoBusRealEmtContext
        original, context = build_two_bus_real_emt_case(initialization_method=EmtInitializationMethod.ConsistentNewton, balanced_pf=balanced_pf, physical_conductance=0.003)
        grid: gce.MultiCircuit = context.get_grid()
        grid.buses[0].Vnom = 9.7 if reverse else 10.0
        grid.buses[1].Vnom = 10.0 if reverse else 9.7
        grid.fBase = frequency
        grid.generators[0].freq = frequency
        # Reuse the fixture's native solver configuration without changing tolerances.
        pf: PowerFlowResults | None = None
        pf3: PowerFlowResults3Ph | None = None
        if balanced_pf:
            pf = gce.power_flow(grid)
            assert pf.converged
        else:
            pf3 = gce.power_flow3ph(grid)
            assert pf3.converged
        problem: EmtProblemDae = EmtProblemDae(grid=grid, options=original.options, pf_results=pf, pf_results_3ph=pf3)
        assert problem.initialization_report is not None
        assert problem.initialization_report.status == EmtInitializationStatus.RESOLVED
        assert evaluate_algebraic_residual_inf(problem) < problem.options.tolerance
        line: gce.Line = grid.lines[0]
        child: Block = line.emt_model.children[0]
        tap_f: float
        tap_t: float
        tap_f, tap_t = line.get_virtual_taps()
        phase_rotation: np.ndarray = np.exp(2j * np.pi * np.array((0.0, -1.0, 1.0)) / 3.0)
        if pf is not None:
            vf: np.ndarray = pf.voltage[0] * phase_rotation
            vt: np.ndarray = pf.voltage[1] * phase_rotation
        else:
            assert pf3 is not None
            vf = np.array((pf3.voltage_A[0], pf3.voltage_B[0], pf3.voltage_C[0]))
            vt = np.array((pf3.voltage_A[1], pf3.voltage_B[1], pf3.voltage_C[1]))
        series: np.ndarray = (vf / tap_f - vt / tap_t) / complex(line.R, line.X)
        current_f: np.ndarray = (series + complex(line.G, line.B) * vf / tap_f / 2.0) / tap_f
        current_t: np.ndarray = (-series + complex(line.G, line.B) * vt / tap_t / 2.0) / tap_t
        indices: np.ndarray = np.array(tuple(problem.get_var_idx(variable) for collection in (child.state_vars[:3], child.algebraic_vars[6:12]) for variable in collection), dtype=int)
        initial: np.ndarray = np.sqrt(2.0) * np.imag(np.concatenate((series, current_f, current_t)))
        np.testing.assert_allclose(problem.get_x0()[indices], initial, rtol=1.0e-6, atol=1.0e-6)
        # Retained seed caches are inspected independently from the final native vector.
        variable: Var
        index: int
        for index, variable in enumerate(child.state_vars[:3]):
            assert problem._temp_post_init_guess[variable.uid] == pytest.approx(initial[index], rel=1.0e-6, abs=1.0e-6)
            assert problem.diff_init_guess[child.diff_vars[index].uid] == pytest.approx(2.0 * np.pi * frequency * np.sqrt(2.0) * series[index].real, rel=1.0e-6, abs=1.0e-6)
        problem.set_events_group(emt_events_group=EmtEventsGroup())
        solver: StructuralCompiledSolver = build_emt_solver(options=problem.options, problem=problem, t0=0.0, t_end=2.0e-4, h=step, method=DynamicIntegrationMethod.DaeTrapezoidal)
        times: np.ndarray
        values: np.ndarray
        derivatives: np.ndarray
        initialized: bool
        converged: bool
        times, values, derivatives, initialized, converged = solver.simulate(boundary_updater=problem)
        assert initialized and converged and np.all(np.isfinite(values)) and np.all(np.isfinite(derivatives))
        expected: np.ndarray = np.sqrt(2.0) * np.imag(np.exp(2j * np.pi * frequency * times[:, None]) * np.concatenate((series, current_f, current_t))[None, :])
        errors[step_index] = float(np.max(np.abs(values[:, indices] - expected)))
        assert errors[step_index] < 1.0e-4
        np.testing.assert_allclose(values[0, indices], initial, rtol=1.0e-6, atol=1.0e-6)
    assert errors[1] <= errors[0] + 1.0e-10


def test_pi_line_port_damping_and_legacy_mapping(tmp_path: Path) -> None:
    """Keep the zero default port damping and preserve saved no-tap Blocks on load/copy.

    :param tmp_path: Native archive output directory.
    :return: None.
    """
    grid: gce.MultiCircuit = gce.MultiCircuit()
    source: gce.Bus = grid.add_bus(gce.Bus(Vnom=128.04))
    target: gce.Bus = grid.add_bus(gce.Bus(Vnom=132.0))
    modern: EmtModelTemplate = get_pi_line_emt_template(grid.var_factory)
    grid.add_emt_model(modern)
    line: gce.Line = grid.add_line(gce.Line(bus_from=source, bus_to=target, r=0.02, x=0.15, g=0.003))
    line.emt_template = modern
    child: Block = line.emt_model.children[0]
    parameter: Var
    value: Const
    damping: float = 0.0
    for parameter, value in child.parameters.items():
        if parameter.name == "G_damp":
            assert value.value is not None
            damping = float(value.value)
        else:
            pass
    assert damping == 0.0
    # A recorded Block owns its original equations and declared slots.
    legacy: EmtModelTemplate = EmtModelTemplate(name="recorded untapped line")
    old_voltage: Var = grid.var_factory.add_var("old_voltage")
    old_current: Var = grid.var_factory.add_var("old_current")
    legacy.block = Block(in_vars=list((old_voltage,)), algebraic_vars=list((old_current,)),
                         algebraic_eqs=list((old_current - old_voltage,)))
    grid.add_emt_model(legacy)
    old_line: gce.Line = grid.add_line(gce.Line(bus_from=source, bus_to=target, r=0.02, x=0.15))
    old_line.emt_template = legacy
    equations: tuple[str, ...] = tuple(str(equation) for equation in old_line.emt_model.algebraic_eqs)
    path: Path = tmp_path / "emt-line-taps.veragrid"
    FileSave(circuit=grid, file_name=str(path)).save()
    loaded: gce.MultiCircuit = FileOpen(str(path)).open()
    circuit: gce.MultiCircuit
    for circuit in (loaded, loaded.copy()):
        assert circuit.lines[0].emt_template is circuit.emt_models[0]
        model: Block = circuit.lines[1].emt_model
        mapped: dict[Var, Const] = dict()
        assign_static_api_object_mapping_for_device(circuit, circuit.lines[1], model, mapped, None)
        assert ParamPowerFlowReferenceType.vtap_f not in model.api_obj_mapping
        assert ParamPowerFlowReferenceType.vtap_t not in model.api_obj_mapping
        assert tuple(str(equation) for equation in model.algebraic_eqs) == equations
        assert len(mapped) == 0
    original: EmtProblemDae
    context: TwoBusRealEmtContext
    original, context = build_two_bus_real_emt_case(initialization_method=EmtInitializationMethod.ConsistentNewton, balanced_pf=True, physical_conductance=0.003)
    runtime_grid: gce.MultiCircuit = context.get_grid()
    runtime_grid.buses[1].Vnom = 9.7
    runtime_line: gce.Line = runtime_grid.lines[0]
    # The fixture disables numerical damping for physical comparisons; restore
    # the builder's actual default for this independent native-startup check.
    runtime_line.emt_model.set_parameter_in_model(var_name="G_damp", new_value=damping)
    pf: PowerFlowResults = gce.power_flow(runtime_grid)
    assert pf.converged
    problem: EmtProblemDae = EmtProblemDae(grid=runtime_grid, options=original.options, pf_results=pf)
    assert problem.initialization_report is not None
    assert problem.initialization_report.status == EmtInitializationStatus.RESOLVED
    assert evaluate_algebraic_residual_inf(problem) < problem.options.tolerance
    problem.set_events_group(emt_events_group=EmtEventsGroup())
    solver: StructuralCompiledSolver = build_emt_solver(options=problem.options, problem=problem, t0=0.0, t_end=2.0e-4, h=5.0e-6, method=DynamicIntegrationMethod.DaeTrapezoidal)
    times: np.ndarray
    values: np.ndarray
    derivatives: np.ndarray
    initialized: bool
    converged: bool
    times, values, derivatives, initialized, converged = solver.simulate(boundary_updater=problem)
    assert initialized and converged and times.size > 1
    assert np.all(np.isfinite(values)) and np.all(np.isfinite(derivatives))
    assert evaluate_algebraic_residual_inf(problem) < problem.options.tolerance
