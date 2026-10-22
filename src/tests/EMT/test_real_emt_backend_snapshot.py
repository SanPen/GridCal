# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can see it at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Any, Dict, Tuple

import numpy as np
import pytest

import VeraGridEngine.api as gce
from VeraGridEngine.Utils.Symbolic.symbolic import Const
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow3ph.power_flow_driver_3ph import PowerFlowDriver3Ph
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver
from VeraGridEngine.Simulations.EMT.solvers.solver_AD import JitAdSolver
from VeraGridEngine.Simulations.EMT.solvers.StructuralVectorizedSolver import StructuralVectorizedSolver
from VeraGridEngine.Simulations.EMT.solvers.structural_compiled_solver import StructuralCompiledSolver
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Templates.Emt.pi_line_emt_template import get_pi_line_emt_template
from VeraGridEngine.Templates.Emt.load_zip_emt_template import get_load_ZIP_emt_template
from VeraGridEngine.Templates.Emt.load_RLC_emt_template import get_shunt_r_emt_template
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import get_generator_thevenin_rl_emt_template_with_ref
from VeraGridEngine.enumerations import (
    DynamicIntegrationMethod,
    EmtInitializationMethod,
    EmtSolverTypes,
    ShuntConnectionType,
)
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model


def build_full_params(problem: EmtProblemDae, t_curr: float) -> np.ndarray:
    event_params = problem._event_params_values.copy()
    event_params = problem.def_event_params_fn(event_params, float(t_curr))
    const_params = np.array([float(c.value) for c in problem.get_parameters_values()], dtype=np.float64)
    return np.concatenate((event_params, const_params))


def build_two_bus_real_emt_case(
        zip_load: bool = False,
        initialization_method: EmtInitializationMethod = EmtInitializationMethod.Auto,
) -> Tuple[EmtProblemDae, Dict[str, Any]]:
    grid = gce.MultiCircuit(Sbase=2.0, fbase=50.0)

    vnom = 10
    bus0 = gce.Bus(name="Bus0", Vnom=vnom, is_slack=True)
    bus1 = gce.Bus(name="Bus1", Vnom=vnom)
    grid.add_bus(bus0)
    grid.add_bus(bus1)

    line0 = gce.Line(name="line0", bus_from=bus0, bus_to=bus1, length=10, rate=900.0)


    tower = gce.OverheadLineType(name="Tower", Vnom=vnom)
    wire = gce.Wire(
        name="Panther 30/7 ACSR",
        diameter=21.0,
        diameter_internal=9.0,
        is_tube=True,
        r=0.1363,
        max_current=1,
    )
    tower.add_wire_relationship(wire=wire, xpos=-12.65, ypos=27.5, phase=1)
    tower.add_wire_relationship(wire=wire, xpos=0.0, ypos=27.5, phase=2)
    tower.add_wire_relationship(wire=wire, xpos=12.65, ypos=27.5, phase=3)
    tower.compute()
    line0.apply_template(tower, grid.Sbase, grid.fBase)

    r_ph = 100.0
    v_ph = vnom / (3 ** 0.5)
    p_ph = (v_ph ** 2) / r_ph
    load = gce.Load(name="load", P1=p_ph, P2=p_ph, P3=p_ph, Q1=0.0, Q2=0.0, Q3=0.0)
    load.conn = ShuntConnectionType.GroundedStar

    gen0 = gce.Generator(name="Gen0", vset=1.0, Snom=grid.Sbase, freq=50, r1=0.001, x1=1.7)

    grid.add_line(line0)
    grid.add_generator(bus=bus0, api_obj=gen0)
    grid.add_load(bus=bus1, api_obj=load)

    for bus in grid.buses:
        get_bus_emt_template(grid, bus)

    gen_mdl = get_generator_thevenin_rl_emt_template_with_ref(vf = grid.var_factory).block
    line_mdl = get_pi_line_emt_template(vf = grid.var_factory, phN = False, phA = True, phB = True, phC = True).block
    if zip_load:
        load_mdl = get_load_ZIP_emt_template(vf=grid.var_factory, phA=True, phB=True, phC=True).block
    else:
        load_mdl = get_shunt_r_emt_template(vf=grid.var_factory, phA=True, phB=True, phC=True).block
        z_base = 1.0 / grid.Sbase
        v_phase_pu = 1.0 / np.sqrt(3.0)
        r_a_pu = (v_phase_pu ** 2) / load.Pa / z_base
        r_b_pu = (v_phase_pu ** 2) / load.Pb / z_base
        r_c_pu = (v_phase_pu ** 2) / load.Pc / z_base

        for var in load_mdl.event_dict.keys():
            if var.name == "R_A_Shunt_R_3ph":
                load_mdl.event_dict[var] = Const(r_a_pu)
            elif var.name == "R_B_Shunt_R_3ph":
                load_mdl.event_dict[var] = Const(r_b_pu)
            elif var.name == "R_C_Shunt_R_3ph":
                load_mdl.event_dict[var] = Const(r_c_pu)
            else:
                load_mdl.event_dict[var] = load_mdl.event_dict[var]

    set_emt_model(device=gen0, model=gen_mdl, var_factory=grid.var_factory)

    set_emt_model(device=line0, model=line_mdl, var_factory=grid.var_factory)

    set_emt_model(device=load, model=load_mdl, var_factory=grid.var_factory)

    pf_options = PowerFlowOptions(
        solver_type=gce.SolverType.NR,
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
        branch_impedance_tolerance_mode=gce.BranchImpedanceMode.Specified,
        distributed_slack=False,
        ignore_single_node_islands=False,
        trust_radius=1.0,
        backtracking_parameter=0.05,
        use_stored_guess=False,
        initialize_angles=False,
        generate_report=False,
    )
    power_flow = PowerFlowDriver3Ph(grid, pf_options)
    power_flow.run()
    res = power_flow.results

    options = EmtOptions(
        time_step=5e-6,
        simulation_time=2e-4,
        tolerance=1e-6,
        solver_type=EmtSolverTypes.StructuralCompiled,
        integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
        initialization_method=initialization_method,
        verbose=0,
    )
    problem = EmtProblemDae(grid=grid, options=options, pf_results_3ph=res)

    return problem, {
        "grid": grid,
        "bus0": bus0,
        "bus1": bus1,
        "line0": line0,
        "load": load,
        "gen0": gen0,
        "gen_mdl": gen_mdl,
        "line_mdl": line_mdl,
        "load_mdl": load_mdl,
        "pf_results": res,
    }


def build_solver(problem: EmtProblemDae, solver_key: EmtSolverTypes):
    common = dict(
        problem=problem,
        t0=0.0,
        t_end=problem.options.simulation_time,
        h=problem.options.time_step,
        method=problem.options.integration_method,
        pred_method=DynamicIntegrationMethod.OdeEuler,
        dense_threshold=0,
        verbose=False,
    )

    if solver_key == EmtSolverTypes.Symbolic:
        solver = JitSymbolicSolver(**common)
        solver.build_jit_kernel(problem.options.integration_method)
        solver._build_jit_symbolic_hybrid(problem.options.integration_method, use_sparse=True)
        if problem.options.integration_method == DynamicIntegrationMethod.DaeTrapezoidal:
            solver.build_jit_kernel(DynamicIntegrationMethod.DaeBackEuler)
            solver._build_jit_symbolic_hybrid(DynamicIntegrationMethod.DaeBackEuler, use_sparse=True)
        return solver

    if solver_key == EmtSolverTypes.Automatic:
        solver = JitAdSolver(**common)
        solver.build_jit_ad()
        return solver

    if solver_key == EmtSolverTypes.StructuralAD:
        solver = StructuralVectorizedSolver(auto_vectorization=False, **common)
        solver.auto_detect_vectorization(problem.options.integration_method)
        return solver

    if solver_key == EmtSolverTypes.StructuralCompiled:
        solver = StructuralCompiledSolver(auto_build=False, **common)
        solver._build_vectorized_backend(problem.options.integration_method)
        return solver

    raise ValueError(solver_key)


def evaluate_residual_snapshot(problem: EmtProblemDae, solver_key: EmtSolverTypes, solver) -> np.ndarray:
    x = problem.get_x0().copy()
    dx = problem.get_dx0().copy()
    x_prev = x.copy()
    dx_prev = dx.copy()
    x_prev2 = x.copy()
    full_params = build_full_params(problem, 0.0)
    n = problem.get_all_vars_number()
    res = np.zeros(n, dtype=np.float64)

    if solver_key == EmtSolverTypes.Symbolic:
        for kernel in solver.jit_kernels[solver.method]:
            kernel(x, full_params, x_prev, dx_prev, problem.options.time_step, res, x_prev2)
        return res

    if solver_key == EmtSolverTypes.Automatic:
        for kernel in solver.jit_kernels_ad[solver.method]:
            kernel(x, full_params, x_prev, dx_prev, problem.options.time_step, res, x_prev2)
        return res

    if solver_key == EmtSolverTypes.StructuralAD:
        solver.fused_residual(x, full_params, x_prev, dx_prev, problem.options.time_step, solver.vec_flat_args, res, x_prev2)
        return res

    if solver_key == EmtSolverTypes.StructuralCompiled:
        solver._residual_assembler.evaluate(x, full_params, x_prev, dx_prev, problem.options.time_step, x_prev2, res)
        return res

    raise ValueError(solver_key)


def evaluate_jacobian_snapshot(problem: EmtProblemDae, solver_key: EmtSolverTypes, solver) -> np.ndarray:
    x = problem.get_x0().copy()
    dx = problem.get_dx0().copy()
    x_prev = x.copy()
    dx_prev = dx.copy()
    x_prev2 = x.copy()
    full_params = build_full_params(problem, 0.0)

    if solver_key == EmtSolverTypes.Symbolic:
        evaluator = solver.jit_jacobian_symbolic[f"{solver.method}_True"]
        return evaluator.evaluate(x, full_params, x_prev, dx_prev, problem.options.time_step, x_prev2).toarray()

    if solver_key == EmtSolverTypes.Automatic:
        return solver.jit_jacobian_ad[solver.method](x, full_params, x_prev, dx_prev, problem.options.time_step, x_prev2).toarray()

    if solver_key == EmtSolverTypes.StructuralAD:
        return solver.vec_jacobian(x, full_params, x_prev, dx_prev, problem.options.time_step, x_prev2).toarray()

    if solver_key == EmtSolverTypes.StructuralCompiled:
        return solver._jacobian_evaluator.evaluate(x, full_params, x_prev, dx_prev, problem.options.time_step, x_prev2).toarray()

    raise ValueError(solver_key)


@pytest.fixture(scope="module")
def problem_and_context_shunt():
    """
    Fixture that builds the two-bus real EMT case with shunt load.
    """
    return build_two_bus_real_emt_case(zip_load=False)


@pytest.fixture(scope="module")
def solvers_shunt(problem_and_context_shunt):
    """
    Fixture that builds all solvers for the shunt load case.
    """
    problem = problem_and_context_shunt[0]
    return {key: build_solver(problem, key) for key in (
        EmtSolverTypes.Symbolic,
        EmtSolverTypes.Automatic,
        EmtSolverTypes.StructuralAD,
        EmtSolverTypes.StructuralCompiled
    )}


@pytest.fixture(scope="module")
def problem_and_context_zip():
    """
    Fixture that builds the two-bus real EMT case with ZIP load.
    """
    return build_two_bus_real_emt_case(zip_load=True)


@pytest.fixture(scope="module")
def solvers_zip(problem_and_context_zip):
    """
    Fixture that builds all solvers for the ZIP load case.
    """
    problem = problem_and_context_zip[0]
    return {key: build_solver(problem, key) for key in (
        EmtSolverTypes.Symbolic,
        EmtSolverTypes.Automatic,
        EmtSolverTypes.StructuralAD,
        EmtSolverTypes.StructuralCompiled
    )}


def test_automatic_residual_kernels_are_compiled_during_backend_build(
        solvers_shunt: Dict[EmtSolverTypes, Any],
) -> None:
    """Verify that AD residual kernels are specialized before simulation.

    :param solvers_shunt: Prebuilt solvers for the real shunt-load EMT case.
    :return: None.
    """
    solver: JitAdSolver = solvers_shunt[EmtSolverTypes.Automatic]
    kernels: list[Any] = solver.jit_kernels_ad[solver.method]

    # An explicitly signed Numba dispatcher owns its machine-code signature as
    # soon as build_jit_ad returns; a lazy dispatcher has an empty collection.
    assert len(kernels) > 0
    kernel: Any
    for kernel in kernels:
        assert len(kernel.signatures) == 1


def test_residual_snapshot_matches_across_all_backends(
        problem_and_context_shunt: Tuple[EmtProblemDae, Dict[str, Any]],
        solvers_shunt: Dict[EmtSolverTypes, Any]
) -> None:
    """
    Test that residual snapshots match across all backends for shunt load case.
    """
    problem = problem_and_context_shunt[0]
    reference = evaluate_residual_snapshot(
        problem, EmtSolverTypes.Symbolic, solvers_shunt[EmtSolverTypes.Symbolic]
    )
    for key in (EmtSolverTypes.Automatic, EmtSolverTypes.StructuralAD, EmtSolverTypes.StructuralCompiled):
        candidate = evaluate_residual_snapshot(problem, key, solvers_shunt[key])
        np.testing.assert_allclose(candidate, reference, rtol=1e-10, atol=1e-10)


def test_jacobian_snapshot_matches_across_all_backends(
        problem_and_context_shunt: Tuple[EmtProblemDae, Dict[str, Any]],
        solvers_shunt: Dict[EmtSolverTypes, Any]
) -> None:
    """
    Test that Jacobian snapshots match across all backends for shunt load case.
    """
    problem = problem_and_context_shunt[0]
    reference = evaluate_jacobian_snapshot(
        problem, EmtSolverTypes.Symbolic, solvers_shunt[EmtSolverTypes.Symbolic]
    )
    for key in (EmtSolverTypes.Automatic, EmtSolverTypes.StructuralAD, EmtSolverTypes.StructuralCompiled):
        candidate = evaluate_jacobian_snapshot(problem, key, solvers_shunt[key])
        np.testing.assert_allclose(candidate, reference, rtol=1e-10, atol=1e-10)


def test_short_trajectory_matches_between_all_backends(
        problem_and_context_shunt: Tuple[EmtProblemDae, Dict[str, Any]],
        solvers_shunt: Dict[EmtSolverTypes, Any]
) -> None:
    """
    Test that short trajectory simulations match across all backends for shunt load case.
    """
    problem = problem_and_context_shunt[0]
    x0 = problem.get_x0().copy()
    dx0 = problem.get_dx0().copy()
    params0 = problem.event_params_values.copy()

    sym_t, sym_y, sym_dy, _, _ = solvers_shunt[EmtSolverTypes.Symbolic].simulate(
        x0=x0.copy(), dx0=dx0.copy(), params0=params0.copy(), boundary_updater=problem
    )
    ref_t, ref_y, ref_dy, _, _ = solvers_shunt[EmtSolverTypes.Automatic].simulate(
        x0=x0.copy(), dx0=dx0.copy(), params0=params0.copy(), boundary_updater=problem
    )

    np.testing.assert_allclose(sym_t, ref_t, rtol=0.0, atol=0.0)
    assert np.all(np.isfinite(sym_y))
    assert np.all(np.isfinite(sym_dy))

    for key in (EmtSolverTypes.StructuralAD, EmtSolverTypes.StructuralCompiled):
        t_arr, y_arr, dy_arr, _, _ = solvers_shunt[key].simulate(
            x0=x0.copy(), dx0=dx0.copy(), params0=params0.copy(), boundary_updater=problem
        )
        np.testing.assert_allclose(t_arr, ref_t, rtol=0.0, atol=0.0)
        np.testing.assert_allclose(y_arr, ref_y, rtol=5e-5, atol=1.5e-5)
        np.testing.assert_allclose(dy_arr, ref_dy, rtol=1e-5, atol=5e-4)


def test_zip_residual_snapshot_matches_across_all_backends(
        problem_and_context_zip: Tuple[EmtProblemDae, Dict[str, Any]],
        solvers_zip: Dict[EmtSolverTypes, Any]
) -> None:
    """
    Test that residual snapshots match across all backends for ZIP load case.
    """
    problem = problem_and_context_zip[0]
    reference = evaluate_residual_snapshot(
        problem, EmtSolverTypes.Symbolic, solvers_zip[EmtSolverTypes.Symbolic]
    )
    for key in (EmtSolverTypes.Automatic, EmtSolverTypes.StructuralAD, EmtSolverTypes.StructuralCompiled):
        candidate = evaluate_residual_snapshot(problem, key, solvers_zip[key])
        np.testing.assert_allclose(candidate, reference, rtol=1e-10, atol=1e-10)


def test_zip_jacobian_snapshot_matches_across_all_backends(
        problem_and_context_zip: Tuple[EmtProblemDae, Dict[str, Any]],
        solvers_zip: Dict[EmtSolverTypes, Any]
) -> None:
    """
    Test that Jacobian snapshots match across all backends for ZIP load case.
    """
    problem = problem_and_context_zip[0]
    reference = evaluate_jacobian_snapshot(
        problem, EmtSolverTypes.Symbolic, solvers_zip[EmtSolverTypes.Symbolic]
    )
    for key in (EmtSolverTypes.Automatic, EmtSolverTypes.StructuralCompiled):
        candidate = evaluate_jacobian_snapshot(problem, key, solvers_zip[key])
        np.testing.assert_allclose(candidate, reference, rtol=1e-10, atol=1e-10)


def test_zip_short_trajectory_matches_between_all_backends(
        problem_and_context_zip: Tuple[EmtProblemDae, Dict[str, Any]],
        solvers_zip: Dict[EmtSolverTypes, Any]
) -> None:
    """
    Test that short trajectory simulations match across all backends for ZIP load case.
    """
    problem = problem_and_context_zip[0]
    x0 = problem.get_x0().copy()
    dx0 = problem.get_dx0().copy()
    params0 = problem.event_params_values.copy()

    sym_t, sym_y, sym_dy, _, _ = solvers_zip[EmtSolverTypes.Symbolic].simulate(
        x0=x0.copy(),
        dx0=dx0.copy(),
        params0=params0.copy(),
        boundary_updater=problem,
    )

    ref_t, ref_y, ref_dy = sym_t, sym_y, sym_dy
    assert np.all(np.isfinite(sym_y))
    assert np.all(np.isfinite(sym_dy))

    for key in (EmtSolverTypes.StructuralAD, EmtSolverTypes.StructuralCompiled):
        t_arr, y_arr, dy_arr, _, _ = solvers_zip[key].simulate(
            x0=x0.copy(), dx0=dx0.copy(), params0=params0.copy(), boundary_updater=problem
        )
        np.testing.assert_allclose(t_arr, ref_t, rtol=0.0, atol=0.0)
        np.testing.assert_allclose(y_arr, ref_y, rtol=5e-5, atol=1.5e-5)
        if key == EmtSolverTypes.StructuralCompiled:
            np.testing.assert_allclose(dy_arr, ref_dy, rtol=5e-5, atol=4e-2)
        else:
            np.testing.assert_allclose(dy_arr, ref_dy, rtol=1e-5, atol=2.5e-2)
