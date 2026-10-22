# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""Consistency of the compiled EMT runtime-parameter kernel with the runtime equations it was generated from."""

from __future__ import annotations

from typing import List, Tuple

import numpy as np
import pytest

from tests.Base.test_dynamic_results_save_load import _build_emt_driver
from tests.EMT.test_kundur_emt_initialization import _build_kundur_problem
from VeraGridEngine.Devices.Events.emt_event import EmtEvent
from VeraGridEngine.Devices.Events.emt_events_group import EmtEventsGroup
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Simulations.EMT.emt_driver import EmtSimulationDriver
from VeraGridEngine.Simulations.EMT.emt_problem_factory import build_emt_problem
from VeraGridEngine.Simulations.EMT.initialization_emt import run_emt_device_pseudo_transient_initialization
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver
from VeraGridEngine.Simulations.EMT.solvers.structural_compiled_solver import StructuralCompiledSolver
from VeraGridEngine.Simulations.EMT.solvers.StructuralVectorizedSolver import StructuralVectorizedSolver
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.basic_structures import Mat, Vec
from VeraGridEngine.enumerations import DynamicEventTransitionType, DynamicIntegrationMethod, VarPowerFlowReferenceType


def _mapped_continuous_runtime_parameter(problem: EmtProblemDae, devices: List[object]) -> Tuple[Block, VarPowerFlowReferenceType, int]:
    """
    Find a model block whose external mapping targets a continuous runtime parameter of the problem.

    :param problem: EMT problem.
    :param devices: Devices whose EMT models are searched.
    :return: Block, mapping key and runtime-parameter index.
    """
    continuous_count: int = len(problem.get_runtime_continuous_parameters())
    device: object
    for device in devices:
        model: Block = device.emt_model
        block: Block
        for block in [model] + list(model.get_all_blocks()):
            key: VarPowerFlowReferenceType
            mapped: Var | None
            for key, mapped in block.external_mapping.items():
                if mapped is None:
                    pass
                else:
                    index: int | None = problem.uid2idx_event_params.get(mapped.uid, None)
                    if index is not None and index < continuous_count:
                        return block, key, index
                    else:
                        pass
    raise AssertionError("No mapped continuous runtime parameter found")


def _two_group_problem() -> Tuple[EmtProblemDae, EmtEventsGroup, EmtEventsGroup]:
    """
    Build a fresh EMT problem of the Base two-bus system with two event groups that differ at t = 0.

    Both groups step the load resistances to different values 1 ms before t = 0
    (a continuous step is active strictly after its time), so the initial runtime
    values of the two groups differ at t = 0.

    :return: Problem, first group and second group.
    """
    built: EmtSimulationDriver = _build_emt_driver()
    grid: MultiCircuit = built.grid
    template_event: EmtEvent = grid.emt_events[0]
    load_model: Block = template_event.device.emt_model
    first: EmtEventsGroup = EmtEventsGroup(name="step to 3 before t=0")
    second: EmtEventsGroup = EmtEventsGroup(name="step to 9 before t=0")
    grid.add_emt_events_group(first)
    grid.add_emt_events_group(second)
    name: str
    for name in ("R_A_Shunt_R_3ph", "R_B_Shunt_R_3ph", "R_C_Shunt_R_3ph"):
        parameter: Var = _find_parameter(load_model, name)
        grid.add_emt_event(EmtEvent(device=template_event.device, parameter=parameter, time=-1.0e-3, value=3.0, group=first))
        grid.add_emt_event(EmtEvent(device=template_event.device, parameter=parameter, time=-1.0e-3, value=9.0, group=second))
    problem: EmtProblemDae = build_emt_problem(grid=grid, options=built.options, pf_results=None, pf_results_3ph=built.pf_results_3Ph)
    return problem, first, second


def _find_parameter(block: Block, name: str) -> Var:
    """
    Find a named runtime parameter in a block tree.

    :param block: Root block.
    :param name: Parameter name.
    :return: Parameter variable.
    """
    candidate: Block
    for candidate in [block] + list(block.get_all_blocks()):
        variable: Var
        for variable in candidate.event_dict.keys():
            if variable.name == name:
                return variable
            else:
                pass
    raise AssertionError("Parameter not found: " + name)


def test_setter_after_kernel_build_is_used_by_the_compiled_evaluator() -> None:
    """
    Production order: kernel built by set_events_group, runtime value set through the public mapping, then compiled activation.

    :return: None.
    """
    problem: EmtProblemDae
    buses: list
    generators: list
    lines: list
    problem, buses, generators, lines = _build_kundur_problem()
    block: Block
    key: VarPowerFlowReferenceType
    index: int
    block, key, index = _mapped_continuous_runtime_parameter(problem, list(lines))
    new_value: float = float(problem.event_params_values[index]) + 12.5

    problem.set_external_param(mdl=block, key=key, value=new_value)
    interpreted: Vec = problem.def_event_params_fn(problem.event_params_values, 0.0)
    problem.enable_compiled_runtime_parameter_evaluator()
    compiled: Vec = problem.def_event_params_fn(problem.event_params_values, 0.0)

    assert interpreted[index] == new_value
    assert compiled[index] == new_value
    assert np.allclose(compiled, interpreted, rtol=1e-12, atol=1e-12)


def test_new_event_group_uses_its_own_equations_after_a_compiled_run() -> None:
    """
    After compiled evaluation with one event group, activating another group gives that group's initial runtime values.

    :return: None.
    """
    problem: EmtProblemDae
    first: EmtEventsGroup
    second: EmtEventsGroup
    problem, first, second = _two_group_problem()
    problem.set_events_group(first)
    problem.enable_compiled_runtime_parameter_evaluator()
    problem.def_event_params_fn(problem.event_params_values, 0.0)
    problem.set_events_group(second)
    switched: Vec = problem.event_params_values.copy()

    reference: EmtProblemDae
    reference_first: EmtEventsGroup
    reference_second: EmtEventsGroup
    reference, reference_first, reference_second = _two_group_problem()
    reference.set_events_group(reference_second)
    expected: Vec = reference.event_params_values.copy()

    assert not np.allclose(_first_group_values(), expected, rtol=0.0, atol=1e-9)
    assert np.allclose(switched, expected, rtol=1e-12, atol=1e-12)


def _first_group_values() -> Vec:
    """
    Return the initial runtime values of the first group on a fresh problem (interpreted).

    :return: Runtime parameter values.
    """
    problem: EmtProblemDae
    first: EmtEventsGroup
    second: EmtEventsGroup
    problem, first, second = _two_group_problem()
    problem.set_events_group(first)
    return problem.event_params_values.copy()


def test_compiled_evaluator_is_not_rebuilt_per_call() -> None:
    """
    Once enabled, repeated compiled evaluations keep their frozen bindings: no rebuild happens per call.

    :return: None.
    """
    source_var: Var = Var("bound_source")
    runtime_parameter: Var = Var("derived_runtime_parameter")
    block: Block = Block(name="runtime owner", algebraic_vars=list((source_var,)), algebraic_eqs=list((source_var,)),
                         event_dict=dict(((runtime_parameter, source_var),)))
    problem: EmtProblemTemplate = EmtProblemTemplate(sys_block=block, static_parameter_values_mapping=dict(), glob_time=Var("time"))
    problem.init_guess[source_var.uid] = 2.0
    problem.enable_compiled_runtime_parameter_evaluator()
    first: Vec = problem.def_event_params_fn(problem.event_params_values, 0.0)
    problem.init_guess[source_var.uid] = 5.0
    repeated: List[float] = [float(problem.def_event_params_fn(problem.event_params_values, 0.0)[0]) for _ in range(5)]

    assert float(first[0]) == 2.0
    assert repeated == [2.0, 2.0, 2.0, 2.0, 2.0]


def _synthetic_problem() -> Tuple[EmtProblemTemplate, Var]:
    """
    Build a one-variable EMT problem whose continuous runtime parameter is bound to an algebraic variable.

    :return: Problem and the algebraic source variable.
    """
    source_var: Var = Var("bound_source")
    runtime_parameter: Var = Var("derived_runtime_parameter")
    block: Block = Block(name="runtime owner", algebraic_vars=list((source_var,)), algebraic_eqs=list((source_var,)),
                         event_dict=dict(((runtime_parameter, source_var),)))
    problem: EmtProblemTemplate = EmtProblemTemplate(sys_block=block, static_parameter_values_mapping=dict(), glob_time=Var("time"))
    problem.init_guess[source_var.uid] = 2.0
    return problem, source_var


def _activation_probe(problem: EmtProblemTemplate, source_var: Var) -> bool:
    """
    Tell whether the compiled evaluator is active, through the public init_guess dict.

    The compiled evaluator reads frozen bindings, so changing the initial value of the
    bound variable does not change its output; the interpreted evaluator reads it live.

    :param problem: Problem whose runtime parameter is bound to source_var.
    :param source_var: Algebraic variable the runtime parameter is bound to.
    :return: True when the compiled evaluator is active.
    """
    before: float = float(problem.def_event_params_fn(problem.event_params_values, 0.0)[0])
    problem.init_guess[source_var.uid] = before + 3.0
    after: float = float(problem.def_event_params_fn(problem.event_params_values, 0.0)[0])
    problem.init_guess[source_var.uid] = before
    return after == before


def _build_solver(solver_name: str, problem: EmtProblemTemplate, t_end: float, use_compiled: bool) -> object:
    """
    Build one of the EMT solvers that activate the compiled runtime-parameter evaluator.

    :param solver_name: "structural_compiled", "structural_vectorized" or "jit_symbolic".
    :param problem: EMT problem.
    :param t_end: Final simulation time (h = 5e-6, trapezoidal).
    :param use_compiled: Value of use_compiled_runtime_parameters.
    :return: Solver exposing simulate().
    """
    if solver_name == "structural_compiled":
        return StructuralCompiledSolver(problem, t0=0.0, t_end=t_end, h=5.0e-6, method=DynamicIntegrationMethod.DaeTrapezoidal,
                                        use_compiled_runtime_parameters=use_compiled)
    elif solver_name == "structural_vectorized":
        return StructuralVectorizedSolver(problem, t0=0.0, t_end=t_end, h=5.0e-6, method=DynamicIntegrationMethod.DaeTrapezoidal,
                                          use_compiled_runtime_parameters=use_compiled)
    elif solver_name == "jit_symbolic":
        return JitSymbolicSolver(problem, t0=0.0, t_end=t_end, h=5.0e-6, method=DynamicIntegrationMethod.DaeTrapezoidal,
                                 use_compiled_runtime_parameters=use_compiled)
    else:
        raise AssertionError("Unknown solver " + solver_name)


@pytest.mark.parametrize("solver_name", ["structural_compiled", "structural_vectorized", "jit_symbolic"])
@pytest.mark.parametrize("use_compiled", [True, False])
def test_solver_activates_the_compiled_evaluator(solver_name: str, use_compiled: bool) -> None:
    """
    Each solver activates the compiled evaluator by default and keeps the interpreted one with False.

    :param solver_name: Solver under test.
    :param use_compiled: Value of use_compiled_runtime_parameters.
    :return: None.
    """
    problem: EmtProblemTemplate
    source_var: Var
    problem, source_var = _synthetic_problem()
    solver: object = _build_solver(solver_name, problem, 1.0e-4, use_compiled)
    t: Vec
    y: Mat
    dy: Mat
    well_initialized: bool
    converged: bool
    t, y, dy, well_initialized, converged = solver.simulate()

    assert converged
    assert _activation_probe(problem, source_var) == use_compiled


def _kundur_run(use_compiled: bool, pseudo_transient: bool, solver_name: str) -> Tuple[Mat, bool]:
    """
    Run one solver on a freshly built Kundur EMT problem.

    :param use_compiled: Value of use_compiled_runtime_parameters.
    :param pseudo_transient: Run device pseudo-transient initialization before the solver.
    :param solver_name: Solver to run (see _build_solver).
    :return: Trajectory and convergence flag.
    """
    problem: EmtProblemDae
    buses: list
    generators: list
    lines: list
    problem, buses, generators, lines = _build_kundur_problem()
    if pseudo_transient:
        run_emt_device_pseudo_transient_initialization(problem=problem, blocks=problem._device_models_for_ptc, options=problem.options)
    else:
        pass
    solver: object = _build_solver(solver_name, problem, 2.0e-3, use_compiled)
    t: Vec
    y: Mat
    dy: Mat
    well_initialized: bool
    converged: bool
    t, y, dy, well_initialized, converged = solver.simulate()
    return y, converged


@pytest.mark.parametrize("solver_name", ["structural_compiled", "structural_vectorized", "jit_symbolic"])
def test_kundur_trajectory_is_identical_with_the_compiled_evaluator(solver_name: str) -> None:
    """
    Kundur EMT gives bit-identical trajectories with the compiled and the interpreted evaluator (fresh problems).

    :param solver_name: Solver under test.
    :return: None.
    """
    y_compiled: Mat
    y_interpreted: Mat
    converged_compiled: bool
    converged_interpreted: bool
    y_compiled, converged_compiled = _kundur_run(True, False, solver_name)
    y_interpreted, converged_interpreted = _kundur_run(False, False, solver_name)

    assert converged_compiled and converged_interpreted
    assert np.array_equal(y_compiled.view(np.int64), y_interpreted.view(np.int64))


@pytest.mark.parametrize("solver_name", ["structural_compiled", "structural_vectorized"])
def test_kundur_after_pseudo_transient_initialization_matches_the_interpreted_evaluator(solver_name: str) -> None:
    """
    After device pseudo-transient initialization, Kundur EMT trajectories agree within 1e-12 on both evaluators (fresh problems).

    :param solver_name: Solver under test.
    :return: None.
    """
    y_compiled: Mat
    y_interpreted: Mat
    converged_compiled: bool
    converged_interpreted: bool
    y_compiled, converged_compiled = _kundur_run(True, True, solver_name)
    y_interpreted, converged_interpreted = _kundur_run(False, True, solver_name)

    assert converged_compiled and converged_interpreted
    assert np.allclose(y_compiled, y_interpreted, rtol=1e-12, atol=1e-12)


def _ramp_runtime_values(use_compiled: bool) -> Mat:
    """
    Evaluate the runtime parameters of a fresh Base two-bus problem with a resistance ramp, after a solver run.

    :param use_compiled: Value of use_compiled_runtime_parameters for the solver run.
    :return: Runtime parameter values at several times (one row per time).
    """
    built: EmtSimulationDriver = _build_emt_driver()
    grid: MultiCircuit = built.grid
    template_event: EmtEvent = grid.emt_events[0]
    ramp: EmtEventsGroup = EmtEventsGroup(name="ramp")
    grid.add_emt_events_group(ramp)
    grid.add_emt_event(EmtEvent(device=template_event.device, parameter=_find_parameter(template_event.device.emt_model, "R_A_Shunt_R_3ph"),
                                time=1.0e-3, end_time=3.0e-3, value=9.0, group=ramp, transition_type=DynamicEventTransitionType.Ramp))
    problem: EmtProblemDae = build_emt_problem(grid=grid, options=built.options, pf_results=None, pf_results_3ph=built.pf_results_3Ph)
    problem.set_events_group(ramp)
    solver: StructuralCompiledSolver = StructuralCompiledSolver(problem, t0=0.0, t_end=1.0e-4, h=5.0e-6, method=DynamicIntegrationMethod.DaeTrapezoidal,
                                                                use_compiled_runtime_parameters=use_compiled)
    solver.simulate()
    times: Vec = np.linspace(0.0, 4.0e-3, 9)
    values: Mat = np.zeros((times.shape[0], problem.event_params_values.shape[0]))
    row: int
    for row in range(times.shape[0]):
        values[row, :] = problem.def_event_params_fn(problem.event_params_values, float(times[row]))
    return values


def test_ramp_runtime_parameters_agree_on_both_evaluators() -> None:
    """
    A resistance ramp and its time-dependent runtime values agree within 1e-12 on the compiled and interpreted evaluators.

    :return: None.
    """
    compiled: Mat = _ramp_runtime_values(True)
    interpreted: Mat = _ramp_runtime_values(False)

    assert not np.allclose(compiled[0, :], compiled[-1, :], rtol=0.0, atol=1e-9)
    assert np.allclose(compiled, interpreted, rtol=1e-12, atol=1e-12)
