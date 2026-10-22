"""A complete machine/controller/grid orbit must repeat without removing unbalance."""
import numpy as np
import pytest

import VeraGridEngine.api as gce
from VeraGridEngine.enumerations import (
    DynamicIntegrationMethod, EmtInitializationMethod, EmtInitializationStatus,
    EmtSolverTypes, ShuntConnectionType, VarPowerFlowReferenceType as Ref,
)
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver
from VeraGridEngine.Simulations.PowerFlow3ph.power_flow_driver_3ph import PowerFlowDriver3Ph
from VeraGridEngine.Templates.Emt.generator_emt_type_template import get_complete_generator_template_emt
from VeraGridEngine.Templates.Emt.load_RLC_emt_template import get_shunt_rlc_combo_emt_template
from VeraGridEngine.Templates.Emt.pi_line_emt_template import get_pi_line_emt_template
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model


def build_machine_grid(unequal):
    grid = gce.MultiCircuit(name='Unbalanced machine regression', Sbase=100., fbase=50.)
    source = gce.Bus(name='Source', Vnom=230., is_slack=True)
    demand = gce.Bus(name='Demand', Vnom=230.)
    for bus in (source, demand):
        grid.add_bus(bus)
        get_bus_emt_template(grid, bus)
    tower = gce.OverheadLineType(name='Untransposed tower', Vnom=230.)
    wire = gce.Wire(name='Wire', diameter=30., r=.08, max_current=2.)
    for phase, x, y in ((1,-8.,25.), (2,0.,32.), (3,8.,25.)):
        tower.add_wire_relationship(wire, xpos=x, ypos=y, phase=phase)
    tower.compute()
    line = gce.Line(name='PI line', bus_from=source, bus_to=demand, length=10.)
    line.apply_template(tower, grid.Sbase, grid.fBase)
    grid.add_line(line)
    generator = gce.Generator(name='Machine', vset=1.02, Snom=100., r1=.003, x1=1.8, freq=50.)
    generator.R0, generator.X0, generator.R2, generator.X2 = .003, .15, .003, .225
    grid.add_generator(source, generator)
    p = (30.,20.,10.) if unequal else (20.,20.,20.)
    q = (12.,8.,5.) if unequal else (25/3,25/3,25/3)
    load = gce.Load(name='RL load', P=60., Q=25., P1=p[0],P2=p[1],P3=p[2],Q1=q[0],Q2=q[1],Q3=q[2])
    load.conn = ShuntConnectionType.GroundedStar
    grid.add_load(demand, load)
    set_emt_model(generator, get_complete_generator_template_emt(grid.var_factory).block, grid.var_factory)
    set_emt_model(line, get_pi_line_emt_template(grid.var_factory, phN=False).block, grid.var_factory)
    set_emt_model(load, get_shunt_rlc_combo_emt_template(grid.var_factory, include_r=True,
                                                       include_l=True, include_c=False).block, grid.var_factory)
    pf = PowerFlowDriver3Ph(grid, gce.PowerFlowOptions(tolerance=1e-10, max_iter=50, control_q=False))
    pf.run()
    assert pf.results.converged
    return grid, generator, pf.results


@pytest.mark.parametrize('unequal', [False, True])
def test_machine_grid_periodic_initialization_preserves_unbalance(unequal):
    grid, generator, pf = build_machine_grid(unequal)
    options = EmtOptions(time_step=1e-5, simulation_time=.04, tolerance=1e-8,
                         solver_type=EmtSolverTypes.Symbolic,
                         integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
                         initialization_method=EmtInitializationMethod.ConsistentNewton,
                         init_periodic_samples=33, verbose=0)
    problem = EmtProblemDae(grid=grid, options=options, pf_results_3ph=pf)
    assert problem.initialization_report.status == EmtInitializationStatus.RESOLVED
    assert problem.initialization_report.final_residual_inf < 1e-8
    solver = JitSymbolicSolver(problem=problem, t0=0., t_end=.04, h=1e-5,
                              method=options.integration_method,
                              pred_method=DynamicIntegrationMethod.OdeEuler, dense_threshold=0, verbose=False)
    times, values, derivatives, _, converged = solver.simulate(boundary_updater=problem)
    assert converged and len(times) >= 4000
    assert np.all(np.isfinite(values)) and np.all(np.isfinite(derivatives))
    # Check every state except the absolute angle's expected advance, and every
    # algebraic variable: this includes controllers, machine, line and load.
    indices = [problem.get_var_idx(var) for var in problem.get_state_vars() + problem.get_algebraic_vars()
               if not var.name.startswith('theta_abs_')]
    np.testing.assert_allclose(values[2000:, indices], values[:-2000, indices], atol=1e-5, rtol=0)
    currents = [generator.emt_model.external_mapping[ref] for ref in (Ref.i_A,Ref.i_B,Ref.i_C)]
    abc = values[:2000, [problem.get_var_idx(var) for var in currents]]
    fundamental = 1j*np.sqrt(2)*np.mean(abc*np.exp(-2j*np.pi*50*times[:2000,None]), axis=0)
    alpha = np.exp(2j*np.pi/3)
    negative = abs(np.dot([1,alpha**2,alpha], fundamental)/3)
    zero = abs(np.mean(fundamental))
    # A passing periodic solve must not achieve balance by dropping the demands.
    assert negative > (0.1 if unequal else 1e-5)
    assert zero > (0.1 if unequal else 1e-5)


@pytest.mark.parametrize('unequal', [False, True])
def test_machine_explicit_seed_matches_pf3_phase_currents_and_dq0(unequal):
    grid, generator, pf = build_machine_grid(unequal)
    options = EmtOptions(time_step=1e-5, simulation_time=.04, tolerance=1e-8,
                         solver_type=EmtSolverTypes.Symbolic,
                         integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
                         initialization_method=EmtInitializationMethod.Explicit,
                         init_periodic_samples=0, verbose=0)
    problem = EmtProblemDae(grid=grid, options=options, pf_results_3ph=pf)
    assert problem.initialization_report.final_residual_inf < 1e-8

    phase_voltages = np.array([pf.voltage_A[0], pf.voltage_B[0], pf.voltage_C[0]])
    phase_powers = np.array([pf.Sbus_A[0], pf.Sbus_B[0], pf.Sbus_C[0]]) / grid.Sbase
    currents_pf = np.sqrt(2) * np.imag(3 * np.conj(phase_powers / phase_voltages))
    machine = generator.emt_model
    current_vars = [machine.external_mapping[ref] for ref in (Ref.i_A, Ref.i_B, Ref.i_C)]
    seeded_currents = np.array([problem.get_x0()[problem.get_var_idx(var)] for var in current_vars])
    np.testing.assert_allclose(seeded_currents, currents_pf, atol=1e-9, rtol=0)

    def machine_var(name):
        matches = [var for block in machine.get_all_blocks()
                   for var in block.state_vars + block.algebraic_vars if var.name == name]
        assert len(matches) == 1
        return problem.get_x0()[problem.get_var_idx(matches[0])]

    angle = machine_var('theta_abs_')
    phase_angles = angle + np.array([0., -2*np.pi/3, 2*np.pi/3])
    expected_d = -2/3 * np.dot(np.cos(phase_angles), currents_pf)
    expected_q = 2/3 * np.dot(np.sin(phase_angles), currents_pf)
    expected_zero = np.mean(currents_pf)
    np.testing.assert_allclose(
        [machine_var('i_d_'), machine_var('i_q_'), machine_var('i_0_')],
        [expected_d, expected_q, expected_zero], atol=1e-9, rtol=0,
    )
    if unequal:
        assert abs(expected_zero) > .1
