# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""Focused regression for model-owned Thevenin EMT initialization."""

from __future__ import annotations

from typing import Any, cast

import numpy as np
import pytest
from types import SimpleNamespace

from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory

import VeraGridEngine.api as gce
from VeraGridEngine.enumerations import (
    DynamicIntegrationMethod,
    EmtInitializationMethod,
    EmtInitializationStatus,
    EmtSolverTypes,
    ShuntConnectionType,
)
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver
from VeraGridEngine.Simulations.PowerFlow3ph.power_flow_driver_3ph import PowerFlowDriver3Ph
from VeraGridEngine.Templates.Emt.load_RLC_emt_template import get_shunt_rlc_combo_emt_template
from VeraGridEngine.Templates.Emt.pi_line_emt_template import get_pi_line_emt_template
from VeraGridEngine.Templates.Emt.bergeron_line_emt_template import get_bergeron_line_emt_template
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import (
    get_generator_thevenin_rl_emt_template_with_ref,
    get_generator_unbalanced_thevenin_rl_emt_template,
)
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model


def _find_var(device: Any, name: str) -> Any:
    matches = [
        var
        for block in device.emt_model.get_all_blocks()
        for var in block.state_vars + block.algebraic_vars + list(block.event_dict) + block.diff_vars
        if var.name == name
    ]
    assert len(matches) == 1
    return matches[0]


def _build_thevenin_case(unbalanced_source=False, unequal_load=False, bergeron=False,
                         balanced_line=False, balanced_pf=False, time_step=5e-6) -> tuple[EmtProblemDae, gce.Generator]:
    grid = gce.MultiCircuit(name="Thevenin EMT initialization", Sbase=100.0, fbase=50.0)
    source = gce.Bus(name="Source", Vnom=230.0, is_slack=True)
    demand = gce.Bus(name="Demand", Vnom=230.0)
    grid.add_bus(source)
    grid.add_bus(demand)

    line = gce.Line(name="Line", bus_from=source, bus_to=demand, r=0.015, x=0.12, b=0.02, rate=200.0,
                    length=10.0 if bergeron else 1.0)
    tower = gce.OverheadLineType(name="Tower", Vnom=230.0)
    wire = gce.Wire(name="Conductor", diameter=30.0, r=0.08, max_current=2.0)
    tower.add_wire_relationship(wire, xpos=-8.0, ypos=25.0, phase=1)
    tower.add_wire_relationship(wire, xpos=0.0, ypos=32.0, phase=2)
    tower.add_wire_relationship(wire, xpos=8.0, ypos=25.0, phase=3)
    tower.compute()
    line.apply_template(tower, grid.Sbase, grid.fBase)
    if balanced_line:
        line.template = None
        line.R2, line.X2, line.B2 = line.R, line.X, line.B
        line.fill_3_phase_from_sequence()

    generator = gce.Generator(name="Thevenin source", vset=1.02, Snom=200.0, r1=0.01, x1=0.25, freq=50.0)
    phase_p = (30., 20., 10.) if unequal_load else (20., 20., 20.)
    phase_q = (12., 8., 5.) if unequal_load else (25./3, 25./3, 25./3)
    load = gce.Load(name="Load", P=60., Q=25.,
                    P1=phase_p[0], P2=phase_p[1], P3=phase_p[2],
                    Q1=phase_q[0], Q2=phase_q[1], Q3=phase_q[2])
    load.conn = ShuntConnectionType.GroundedStar
    grid.add_line(line)
    grid.add_generator(source, generator)
    grid.add_load(demand, load)

    for bus in grid.buses:
        get_bus_emt_template(grid, bus)
    source_template = (get_generator_unbalanced_thevenin_rl_emt_template if unbalanced_source
                       else get_generator_thevenin_rl_emt_template_with_ref)
    set_emt_model(generator, source_template(grid.var_factory).block, grid.var_factory)
    line_template = get_bergeron_line_emt_template if bergeron else get_pi_line_emt_template
    set_emt_model(
        line,
        line_template(grid.var_factory, phN=False, phA=True, phB=True, phC=True).block,
        grid.var_factory,
    )
    set_emt_model(
        load,
        get_shunt_rlc_combo_emt_template(
            grid.var_factory, include_r=True, include_l=True, include_c=False,
            phA=True, phB=True, phC=True,
        ).block,
        grid.var_factory,
    )

    pf_driver = gce.PowerFlowDriver if balanced_pf else PowerFlowDriver3Ph
    power_flow = pf_driver(grid, gce.PowerFlowOptions(
        solver_type=gce.SolverType.NR, retry_with_other_methods=False,
        tolerance=1e-10, max_iter=50, control_q=False,
    ))
    power_flow.run()
    assert bool(power_flow.results.converged)

    problem = EmtProblemDae(
        grid=grid,
        options=EmtOptions(
            time_step=time_step, simulation_time=2e-5, tolerance=1e-7,
            solver_type=EmtSolverTypes.Symbolic,
            integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
            initialization_method=EmtInitializationMethod.Explicit,
            verbose=0,
        ),
        pf_results_3ph=None if balanced_pf else power_flow.results,
        pf_results=power_flow.results if balanced_pf else None,
        logger=Logger(),
    )
    return problem, generator


def test_thevenin_model_initializes_internal_emf_without_problem_specific_seeding() -> None:
    problem, generator = _build_thevenin_case()
    assert any("Balanced EMT Thevenin" in entry.msg for entry in problem.logger.entries)
    assert problem.initialization_report is not None
    assert problem.initialization_report.status == EmtInitializationStatus.RESOLVED
    assert problem.initialization_report.final_residual_inf < problem.options.tolerance

    results = problem.power_flow_results_3ph
    phase_voltages = np.array([results.voltage_A[0], results.voltage_B[0], results.voltage_C[0]])
    phase_powers = np.array([results.Sbus_A[0], results.Sbus_B[0], results.Sbus_C[0]])
    phase_currents = 3.0 * np.conj(phase_powers / problem.grid.Sbase / phase_voltages)
    alpha = np.exp(2j * np.pi / 3.0)
    positive_sequence = np.array([1.0, alpha, alpha ** 2]) / 3.0
    voltage = positive_sequence @ phase_voltages
    current = positive_sequence @ phase_currents
    voltage_peak = np.sqrt(2.0) * abs(voltage)
    current_peak = np.sqrt(2.0) * abs(current)
    phi_v = np.angle(voltage)
    phi = np.angle(current) - phi_v
    e_relative = voltage_peak + complex(generator.R1, generator.X1) * current_peak * np.exp(1j * phi)
    theta_expected = phi_v + np.angle(e_relative)
    emf_peak = abs(e_relative)

    expected_values = {
        "i_A": np.sqrt(2.0) * np.imag(phase_currents[0]),
        "i_B": np.sqrt(2.0) * np.imag(phase_currents[1]),
        "i_C": np.sqrt(2.0) * np.imag(phase_currents[2]),
        "theta": theta_expected,
        "e_A": emf_peak * np.sin(theta_expected),
        "e_B": emf_peak * np.sin(theta_expected - 2.0 * np.pi / 3.0),
        "e_C": emf_peak * np.sin(theta_expected + 2.0 * np.pi / 3.0),
    }
    for name, expected in expected_values.items():
        var = _find_var(generator, name)
        actual = problem.get_x0()[problem.get_var_idx(var)]
        np.testing.assert_allclose(actual, expected, rtol=1e-7, atol=1e-9)

    omega_base = 2.0 * np.pi * problem.grid.fBase
    # PF3 phase currents can be unbalanced, while the internal source stays
    # balanced. Derivatives must satisfy the source RL equations at t=0.
    for phase, phase_voltage, phase_current in zip("ABC", phase_voltages, phase_currents):
        name = f"d_i_{phase}"
        var = _find_var(generator, name)
        actual = problem.get_dx0()[problem.get_diff_var_idx(var)]
        expected = omega_base / generator.X1 * (
            expected_values[f"e_{phase}"]
            - generator.R1 * np.sqrt(2.0) * np.imag(phase_current)
            - np.sqrt(2.0) * np.imag(phase_voltage)
        )
        np.testing.assert_allclose(actual, expected, rtol=1e-7, atol=1e-7)

    solver = JitSymbolicSolver(
        problem=problem, t0=0.0, t_end=problem.options.simulation_time,
        h=problem.options.time_step, method=problem.options.integration_method,
        pred_method=DynamicIntegrationMethod.OdeEuler, dense_threshold=0, verbose=False,
    )
    _, values, derivatives, well_initialized, converged = solver.simulate(
        boundary_updater=cast(Any, problem)
    )
    assert well_initialized
    assert converged
    assert np.all(np.isfinite(values))
    assert np.all(np.isfinite(derivatives))


@pytest.mark.parametrize("bergeron", [False, True])
@pytest.mark.parametrize("unequal_load", [False, True])
def test_independent_phase_emfs_preserve_pf_and_repeat_each_cycle(unequal_load, bergeron):
    problem, generator = _build_thevenin_case(unbalanced_source=True, unequal_load=unequal_load, bergeron=bergeron)
    pf = problem.power_flow_results_3ph
    voltages = np.array([pf.voltage_A[0], pf.voltage_B[0], pf.voltage_C[0]])
    powers = np.array([pf.Sbus_A[0], pf.Sbus_B[0], pf.Sbus_C[0]]) / problem.grid.Sbase
    currents = 3 * np.conj(powers / voltages)
    expected_emfs = voltages + complex(generator.R1, generator.X1) * currents
    omega = 2 * np.pi * problem.grid.fBase
    for phase, emf, current in zip("ABC", expected_emfs, currents):
        np.testing.assert_allclose(
            problem.get_x0()[problem.get_var_idx(_find_var(generator, f"e_{phase}"))],
            np.sqrt(2) * emf.imag, atol=1e-9,
        )
        np.testing.assert_allclose(
            problem.get_dx0()[problem.get_diff_var_idx(_find_var(generator, f"d_i_{phase}"))],
            omega * np.sqrt(2) * current.real, atol=1e-7,
        )
    solver = JitSymbolicSolver(
        problem=problem, t0=0., t_end=.04, h=problem.options.time_step,
        method=problem.options.integration_method,
        pred_method=DynamicIntegrationMethod.OdeEuler, dense_threshold=0, verbose=False,
    )
    times, values, derivatives, initialized, converged = solver.simulate(boundary_updater=problem)
    assert initialized and converged
    assert np.all(np.isfinite(values)) and np.all(np.isfinite(derivatives))
    samples = round(1 / (problem.grid.fBase * problem.options.time_step))
    assert len(times) >= 2 * samples
    for phase in "ABC":
        current = values[:, problem.get_var_idx(_find_var(generator, f"i_{phase}"))]
        np.testing.assert_allclose(current[samples:], current[:-samples], atol=1e-6, rtol=0)
    for bus in problem.grid.buses:
        for phase in "ABC":
            voltage = values[:, problem.get_var_idx(_find_var(bus, f"v_{phase}"))]
            np.testing.assert_allclose(voltage[samples:], voltage[:-samples], atol=1e-6, rtol=0)
    assert not any("Balanced EMT Thevenin" in entry.msg for entry in problem.logger.entries)


@pytest.mark.parametrize("unbalanced_source", [False, True])
@pytest.mark.parametrize("compatible_emf", [False, True])
def test_balanced_source_warning_checks_required_emf(unbalanced_source, compatible_emf):
    factory = VarFactory()
    template = (get_generator_unbalanced_thevenin_rl_emt_template if unbalanced_source
                else get_generator_thevenin_rl_emt_template_with_ref)
    model = template(factory).block
    generator = SimpleNamespace(name="Test source", R1=.01, X1=.25)
    logger = Logger()
    problem = SimpleNamespace(logger=logger)
    phase_rotation = np.exp(-2j * np.pi * np.arange(3) / 3)
    currents = np.array([.8-.2j, -.2-.3j, -.1+.4j])
    impedance = complex(generator.R1, generator.X1)
    if compatible_emf:
        # Unbalanced terminal voltages can still arise from balanced internal EMF.
        voltages = 1.05 * phase_rotation - impedance * currents
    else:
        # Balanced terminal voltages do not guarantee compatible internal EMF.
        voltages = phase_rotation
    EmtProblemDae._warn_balanced_thevenin_operating_point(
        problem, generator, model, np.r_[0j, voltages], np.r_[0j, currents],
    )
    expected_warnings = 0 if unbalanced_source or compatible_emf else 1
    assert len(logger.entries) == expected_warnings
    if expected_warnings:
        assert "requires unbalanced internal phase EMFs" in logger.entries[0].msg
        assert logger.entries[0].device == generator.name


@pytest.mark.parametrize("balanced_pf", [False, True], ids=["PF3", "balanced-PF"])
@pytest.mark.parametrize("time_step", [1e-5, 5e-6])
def test_balanced_bergeron_grid_stays_balanced_and_periodic(balanced_pf, time_step):
    problem, generator = _build_thevenin_case(
        bergeron=True, balanced_line=True, balanced_pf=balanced_pf, time_step=time_step,
    )
    assert problem.grid.lines[0].template is None
    assert problem.initialization_report.final_residual_inf < problem.options.tolerance
    phase_rotation = np.exp(-2j*np.pi*np.arange(3)/3)
    for bus_index in range(2):
        voltages = problem._get_bus_voltage_vector(bus_index)[1:]
        np.testing.assert_allclose(voltages, voltages[0]*phase_rotation, atol=1e-9, rtol=0)
    assert not any("Balanced EMT Thevenin" in entry.msg for entry in problem.logger.entries)
    assert problem.options.init_periodic_samples == 0

    solver = JitSymbolicSolver(
        problem=problem, t0=0., t_end=.06, h=time_step,
        method=problem.options.integration_method,
        pred_method=DynamicIntegrationMethod.OdeEuler, dense_threshold=0, verbose=False,
    )
    times, values, derivatives, initialized, converged = solver.simulate(boundary_updater=problem)
    assert initialized and converged
    assert np.all(np.isfinite(values)) and np.all(np.isfinite(derivatives))
    samples = round(1/(problem.grid.fBase*time_step))
    assert len(times) >= 3*samples
    for device, prefix in ((generator, "i"), (problem.grid.buses[0], "v"), (problem.grid.buses[1], "v")):
        abc = values[:, [problem.get_var_idx(_find_var(device, f"{prefix}_{phase}")) for phase in "ABC"]]
        np.testing.assert_allclose(abc[samples:], abc[:-samples], atol=1e-5, rtol=0)
        np.testing.assert_allclose(abc.sum(axis=1), 0., atol=1e-9, rtol=0)
        first_cycle_rms = np.sqrt(np.mean(abc[:samples]**2, axis=0))
        np.testing.assert_allclose(first_cycle_rms, first_cycle_rms[0], atol=1e-5, rtol=0)
