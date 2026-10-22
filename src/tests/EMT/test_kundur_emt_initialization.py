# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""Self-contained initialization regression for the Kundur EMT model."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, cast

import numpy as np
import pytest

import VeraGridEngine.api as gce
from VeraGridEngine.enumerations import (
    DynamicIntegrationMethod,
    EmtInitializationMethod,
    EmtInitializationStatus,
    EmtSolverTypes,
    ShuntConnectionType,
)
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.initialization_emt import run_emt_device_pseudo_transient_initialization
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver
from VeraGridEngine.Templates.Emt.generator_emt_type_template import get_complete_generator_template_emt
from VeraGridEngine.Templates.Emt.load_RLC_emt_template import get_shunt_rlc_combo_emt_template
from VeraGridEngine.Templates.Emt.pi_line_emt_template import get_pi_line_emt_template
from VeraGridEngine.Templates.Emt.transformer_emt_template import get_series_transformer_emt_template
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model
from VeraGridEngine.Utils.Symbolic.symbolic import Const


def _set_three_phase_line_matrices(line: gce.Line) -> None:
    """Give a positive-sequence Kundur line a passive transposed ABC model."""
    a = np.exp(2j * np.pi / 3.0)
    seq_to_abc = np.array(
        [[1.0, 1.0, 1.0], [1.0, a ** 2, a], [1.0, a, a ** 2]],
        dtype=complex,
    )
    abc_to_seq = np.linalg.inv(seq_to_abc)
    z012 = np.diag([3.0 * complex(line.R, line.X), complex(line.R, line.X), complex(line.R, line.X)])
    y012 = np.diag(1j * 1e6 * np.array([line.B, line.B, line.B]))

    line.ys.values = np.pad(np.linalg.inv(seq_to_abc @ z012 @ abc_to_seq), ((1, 0), (1, 0)))
    line.ysh.values = np.pad(seq_to_abc @ y012 @ abc_to_seq, ((1, 0), (1, 0)))
    for matrix in (line.ys, line.ysh):
        matrix.phN = False
        matrix.phA = matrix.phB = matrix.phC = True


def _build_kundur_problem(
    initialization_method: EmtInitializationMethod = EmtInitializationMethod.Explicit,
    clear_init_eqs: bool = False,
    null_references: bool = False,
) -> tuple[
    EmtProblemDae, list[gce.Bus], list[gce.Generator], list[gce.Line]
]:
    """Build the complete 11-bus, four-machine Kundur case without external fixtures."""
    grid = gce.MultiCircuit(name="Kundur EMT initialization test", Sbase=100.0, fbase=60.0)
    buses = [
        gce.Bus(name=f"Bus{i}", Vnom=20.0 if i <= 4 else 230.0, is_slack=i == 3)
        for i in range(1, 12)
    ]
    for bus in buses:
        grid.add_bus(bus)

    line_data = [
        (5, 6, .005, .05, .02187, 750), (5, 6, .005, .05, .02187, 750),
        (6, 7, .003, .03, .00583, 700), (6, 7, .003, .03, .00583, 700),
        (6, 7, .003, .03, .00583, 700), (7, 8, .011, .11, .19250, 400),
        (7, 8, .011, .11, .19250, 400), (8, 9, .011, .11, .19250, 400),
        (8, 9, .011, .11, .19250, 400), (9, 10, .003, .03, .00583, 700),
        (9, 10, .003, .03, .00583, 700), (9, 10, .003, .03, .00583, 700),
        (10, 11, .005, .05, .02187, 750), (10, 11, .005, .05, .02187, 750),
    ]
    lines: list[gce.Line] = []
    for index, (bus_from, bus_to, r, x, b, rate) in enumerate(line_data):
        line = gce.Line(
            name=f"Kundur line {index}", bus_from=buses[bus_from - 1], bus_to=buses[bus_to - 1],
            r=r, x=x, b=b, rate=rate,
        )
        _set_three_phase_line_matrices(line)
        grid.add_line(line)
        lines.append(line)

    transformer_x = 0.15 * grid.Sbase / 900.0
    transformer_pairs = [(5, 1), (6, 2), (11, 3), (10, 4)]
    transformers: list[gce.Transformer2W] = []
    for index, (bus_hv, bus_lv) in enumerate(transformer_pairs):
        transformer = gce.Transformer2W(
            name=f"Kundur transformer {index}",
            bus_from=buses[bus_hv - 1], bus_to=buses[bus_lv - 1],
            HV=230.0, LV=20.0, nominal_power=900.0, rate=900.0, r=0.0, x=transformer_x,
            r0=0.0, x0=transformer_x, r2=0.0, x2=transformer_x,
        )
        grid.add_transformer2w(transformer)
        transformers.append(transformer)

    loads: list[gce.Load] = []
    for index, bus_number in enumerate((7, 9)):
        load = gce.Load(
            name=f"Kundur load {index}", P=9.999999, Q=.999999,
            P1=3.333333, P2=3.333333, P3=3.333333,
            Q1=.333333, Q2=.333333, Q3=.333333,
        )
        load.conn = ShuntConnectionType.FloatingStar
        grid.add_load(bus=buses[bus_number - 1], api_obj=load)
        loads.append(load)

    xd = 0.3 * grid.Sbase / 900.0
    generators = [
        # The slack absorbs about 9.88 MW in this low-load fixture. Its static
        # limit must permit the operating point now that governors use it.
        gce.Generator(name=f"Gen{i}", P=10.0, Pmin=-100.0, vset=vset, Snom=900.0, x1=xd, r1=0.0, freq=60.0)
        for i, vset in enumerate((1.03, 1.01, 1.03, 1.01), start=1)
    ]
    for generator, bus in zip(generators, buses[:4]):
        grid.add_generator(bus=bus, api_obj=generator)

    for bus in buses:
        get_bus_emt_template(grid, bus)
    for generator in generators:
        set_emt_model(generator, get_complete_generator_template_emt(grid.var_factory).block, grid.var_factory)
    for index, line in enumerate(lines):
        model = get_pi_line_emt_template(
            grid.var_factory, phN=False, phA=True, phB=True, phC=True,
            name=f"Kundur line EMT {index}", numerical_damping_conductance=0.0,
        ).block
        set_emt_model(line, model, grid.var_factory)
    for index, transformer in enumerate(transformers):
        model = get_series_transformer_emt_template(
            grid.var_factory, name=f"Kundur transformer EMT {index}",
            r=transformer.R, x=transformer.X, tap_module=transformer.tap_module,
        ).block
        set_emt_model(transformer, model, grid.var_factory)
    for load in loads:
        model = get_shunt_rlc_combo_emt_template(
            grid.var_factory, include_r=True, include_l=True, include_c=False,
            phA=True, phB=True, phC=True, connection_type=ShuntConnectionType.FloatingStar,
            name=f"{load.name} EMT",
        ).block
        set_emt_model(load, model, grid.var_factory)

    if clear_init_eqs:
        for device in [*buses, *generators, *lines, *transformers, *loads]:
            for block in device.emt_model.get_all_blocks():
                block.init_eqs = {}
                block.diff_init_eqs = {}

    if null_references:
        for generator in generators:
            for block in generator.emt_model.get_all_blocks():
                for variable in block.event_dict:
                    if variable.name == "UsRefPu":
                        block.event_dict[variable] = Const(None)

    pf_options = gce.PowerFlowOptions(
        solver_type=gce.SolverType.NR, retry_with_other_methods=False, tolerance=1e-6,
        max_iter=25, control_q=False, distributed_slack=False, generate_report=False,
    )
    power_flow = PowerFlowDriver(grid, pf_options)
    power_flow.run()
    assert bool(power_flow.results.converged)

    options = EmtOptions(
        time_step=5e-6, simulation_time=5e-5, tolerance=1e-6,
        solver_type=EmtSolverTypes.Symbolic,
        integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
        initialization_method=initialization_method,
        verbose=0,
    )
    problem = EmtProblemDae(grid=grid, options=options, pf_results=power_flow.results)
    return problem, buses, generators, lines


def _find_model_var(device: Any, name: str) -> Any:
    """Find one named variable in a device EMT block hierarchy."""
    matches = [
        var
        for block in device.emt_model.get_all_blocks()
        for var in block.algebraic_vars + block.state_vars + list(block.event_dict) + block.diff_vars
        if var.name == name
    ]
    assert len(matches) == 1, f"Expected one {name!r} in {device.name}, found {len(matches)}"
    return matches[0]


def _initial_phasor(problem: EmtProblemDae, device: Any, state_name: str) -> complex:
    """Reconstruct an RMS phasor from one initialized sinusoidal EMT state."""
    state = _find_model_var(device, state_name)
    differential = next(
        var for var in problem.get_diff_vars()
        if var.base_var is not None and var.base_var.uid == state.uid
    )
    instantaneous = problem.get_x0()[problem.get_var_idx(state)]
    derivative = problem.get_dx0()[problem.get_diff_var_idx(differential)]
    omega_base = 2.0 * np.pi * problem.grid.fBase
    return complex(
        derivative / (omega_base * np.sqrt(2.0)),
        instantaneous / np.sqrt(2.0),
    )


def _assert_conventional_emt_pu_power(problem: EmtProblemDae, line: gce.Line) -> None:
    """Check the initialized EMT phasors against the conventional three-phase pu identity."""
    phases = ("A", "B", "C")
    alpha = np.exp(2j * np.pi / 3.0)
    rotations = np.asarray([1.0, 1.0 / alpha, alpha])
    bus_indices = {bus.idtag: index for index, bus in enumerate(problem.grid.buses)}
    voltage_from = problem.power_flow_results.voltage[bus_indices[line.bus_from.idtag]] * rotations
    voltage_to = problem.power_flow_results.voltage[bus_indices[line.bus_to.idtag]] * rotations
    for device, voltage in ((line.bus_from, voltage_from), (line.bus_to, voltage_to)):
        instantaneous_voltage = np.asarray([
            problem.get_x0()[problem.get_var_idx(_find_model_var(device, f"v_{phase}"))]
            for phase in phases
        ])
        np.testing.assert_allclose(
            instantaneous_voltage,
            np.sqrt(2.0) * np.imag(voltage),
            rtol=1e-8,
            atol=1e-9,
        )
    series_current = np.asarray([
        _initial_phasor(problem, line, f"i_ser_{phase}") for phase in phases
    ])

    # With Vphase based on VLL/sqrt(3), I based on Sbase/(sqrt(3)*VLL),
    # and Z based on VLL^2/Sbase, the EMT series equation is dV=Z*I.
    expected_series_current = (voltage_from - voltage_to) / complex(line.R, line.X)
    np.testing.assert_allclose(series_current, expected_series_current, rtol=1e-6, atol=1e-8)

    # PF branch power includes the from-side half shunt. Each phase power is
    # based on Sbase/3, hence total three-phase pu power is the phase average.
    terminal_current = series_current + 0.5j * line.B * voltage_from
    emt_power = np.mean(voltage_from * np.conj(terminal_current))
    pf_power = problem.power_flow_results.Sf[0] / problem.grid.Sbase
    np.testing.assert_allclose(emt_power, pf_power, rtol=1e-7, atol=1e-8)


def test_kundur_emt_initialization_and_short_trajectory_match_reference() -> None:
    """Kundur initialization and a short EMT trajectory must match the golden result."""
    problem, buses, generators, lines = _build_kundur_problem()

    assert problem.initialization_report is not None
    assert problem.initialization_report.status == EmtInitializationStatus.RESOLVED

    us_ref_vars = [
        var
        for generator in generators
        for block in generator.emt_model.get_all_blocks()
        for var in block.event_dict
        if var.name == "UsRefPu"
    ]
    assert len(us_ref_vars) == len(generators) == 4
    for us_ref in us_ref_vars:
        initialized = problem.event_params_init_dict[us_ref.uid]
        runtime = problem.event_params_values[problem.uid2idx_event_params[us_ref.uid]]
        assert initialized is not None
        assert np.isfinite(runtime)
        np.testing.assert_allclose(runtime, float(initialized), rtol=0.0, atol=1e-12)

    # A runtime refresh must preserve the PF voltage used to derive the load
    # impedances. Restoring the template's Vm=1 would disturb the first cycle.
    refreshed_params = problem.def_event_params_fn(problem.event_params_values.copy(), 0.0)
    for load in problem.grid.loads:
        vm_var = next(var for var in load.emt_model.event_dict if var.name.startswith("Vm_pf_"))
        vm_index = problem.uid2idx_event_params[vm_var.uid]
        bus_index = problem.grid.buses.index(load.bus)
        expected_vm = abs(problem.power_flow_results.voltage[bus_index])
        np.testing.assert_allclose(refreshed_params[vm_index], expected_vm, rtol=0.0, atol=1e-12)

    exciter_derivatives = [
        var for var in problem.get_diff_vars()
        if var.name in {"d_y_exciter2", "d_y_exciter3", "d_Vf"}
    ]
    assert len(exciter_derivatives) == 3 * len(generators)
    derivative_values = np.array([
        problem.get_dx0()[problem.get_diff_var_idx(var)] for var in exciter_derivatives
    ])
    np.testing.assert_allclose(derivative_values, 0.0, rtol=0.0, atol=1e-10)

    _assert_conventional_emt_pu_power(problem, lines[0])

    solver = JitSymbolicSolver(
        problem=problem,
        t0=0.0,
        t_end=problem.options.simulation_time,
        h=problem.options.time_step,
        method=problem.options.integration_method,
        pred_method=DynamicIntegrationMethod.OdeEuler,
        dense_threshold=0,
        verbose=False,
    )
    time, values, _, well_initialized, converged = solver.simulate(
        boundary_updater=cast(Any, problem)
    )
    assert well_initialized
    assert converged

    selected_vars = {
        "bus1_v_A": _find_model_var(buses[0], "v_A"),
        "bus7_v_A": _find_model_var(buses[6], "v_A"),
        "bus9_v_A": _find_model_var(buses[8], "v_A"),
        "gen1_omega": _find_model_var(generators[0], "omega_"),
        "gen1_Vf": _find_model_var(generators[0], "Vf"),
        "tie_7_8_if_A": _find_model_var(lines[5], "if_A"),
    }
    actual = np.column_stack([
        time,
        *[values[:, problem.get_var_idx(var)] for var in selected_vars.values()],
    ])

    reference_path = Path(__file__).resolve().parents[1] / "data" / "dynamics" / "kundur_emt_short.csv"
    with reference_path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        expected_columns = ["time_s", *selected_vars]
        assert reader.fieldnames == expected_columns
        expected = np.asarray([
            [float(row[column]) for column in expected_columns]
            for row in reader
        ])

    assert actual.shape == expected.shape
    np.testing.assert_allclose(actual, expected, rtol=1e-7, atol=3e-7)



@pytest.mark.parametrize("clear_init_eqs,null_references", [(False, False), (True, False), (True, True)])
def test_kundur_emt_device_pseudotransient_has_periodic_operating_point(
        monkeypatch: pytest.MonkeyPatch, clear_init_eqs: bool, null_references: bool,
) -> None:
    """PTC must produce the orbit itself, including when every init equation is absent."""
    def forbidden(*args: Any, **kwargs: Any) -> None:
        pytest.fail("PseudoTransient initialization called explicit init or EMT time integration")

    with monkeypatch.context() as guard:
        guard.setattr(EmtProblemDae, "_run_explicit_initialization", forbidden)
        guard.setattr(JitSymbolicSolver, "simulate", forbidden)
        problem, _, generators, _ = _build_kundur_problem(
            EmtInitializationMethod.PseudoTransient,
            clear_init_eqs=clear_init_eqs,
            null_references=null_references,
        )
    report = problem.initialization_report
    assert report is not None
    assert report.status == EmtInitializationStatus.RESOLVED
    assert report.method_used == EmtInitializationMethod.PseudoTransient
    assert report.final_residual_inf < problem.options.tolerance
    assert report.pseudo_transient_steps > 0
    assert report.newton_iterations == 0
    if clear_init_eqs:
        assert all(not block.init_eqs and not block.diff_init_eqs
                   for root in problem._device_models_for_ptc for block in root.get_all_blocks())
    for generator in generators:
        reference = _find_model_var(generator, "UsRefPu")
        assert np.isfinite(problem.event_params_init_dict[reference.uid])

    period = 1.0 / problem.grid.fBase
    steps = 400
    solver = JitSymbolicSolver(
        problem=problem,
        t0=0.0,
        t_end=period,
        h=period / steps,
        method=problem.options.integration_method,
        pred_method=DynamicIntegrationMethod.OdeEuler,
        dense_threshold=0,
        verbose=False,
    )
    _, values, _, well_initialized, converged = solver.simulate(
        boundary_updater=cast(Any, problem),
    )
    assert well_initialized and converged
    angular_indices = [
        index for index, var in enumerate(problem.state_and_algebraic_vars())
        if var.name == "theta_abs_"
    ]
    np.testing.assert_allclose(
        values[-1, angular_indices] - values[0, angular_indices],
        2.0 * np.pi,
        atol=1e-6,
    )
    periodic_indices = [
        index for index, var in enumerate(problem.state_and_algebraic_vars())
        if var.name != "theta_abs_"
    ]
    assert np.max(np.abs(values[-1, periodic_indices] - values[0, periodic_indices])) < 1e-5


def test_kundur_emt_device_pseudotransient_corrects_local_line_state() -> None:
    """A perturbed line state should relax locally while the PF buses stay fixed."""
    problem, _, _, lines = _build_kundur_problem()
    line_state = _find_model_var(lines[5], "i_ser_A")
    original = problem.init_guess[line_state.uid]
    problem.init_guess[line_state.uid] = original + 0.1

    report = run_emt_device_pseudo_transient_initialization(
        problem=problem,
        blocks=problem._device_models_for_ptc,
        options=problem.options,
    )

    assert report.status == EmtInitializationStatus.RESOLVED
    assert report.pseudo_transient_steps > 0
    assert report.final_residual_inf < problem.options.tolerance
    np.testing.assert_allclose(problem.init_guess[line_state.uid], original, atol=1e-8)


def test_kundur_emt_auto_uses_device_ptc_when_explicit_equations_are_missing() -> None:
    """Auto must use periodic device PTC and verify the assembled EMT orbit."""
    problem, _, _, _ = _build_kundur_problem(
        EmtInitializationMethod.Auto,
        clear_init_eqs=True,
        null_references=False,
    )

    report = problem.initialization_report
    assert report is not None
    assert report.status == EmtInitializationStatus.RESOLVED
    assert report.method_requested == EmtInitializationMethod.Auto
    assert report.method_used == EmtInitializationMethod.PseudoTransient
    assert report.pseudo_transient_steps > 0
    assert report.newton_iterations == 0
    assert report.final_residual_inf <= max(
        float(problem.options.init_newton_tol),
        float(problem.options.tolerance),
    )
    assert "verified the assembled periodic DAE" in report.message
