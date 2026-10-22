# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can see it at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
# ==============================================================================
# Mathematical Verification Suite for VeraGrid Unified Solvers
# ==============================================================================

from typing import Any, Callable, Dict, Iterator, List, Tuple

import numpy as np
import pytest

from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate

from VeraGridEngine.Simulations.EMT.solvers.solver_AD import JitAdSolver
from VeraGridEngine.Simulations.EMT.solvers.StructuralVectorizedSolver import StructuralVectorizedSolver
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import BoundaryUpdateWrapper
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver
from VeraGridEngine.Simulations.EMT.solvers.structural_compiled_solver import StructuralCompiledSolver
from VeraGridEngine.Utils.Symbolic.diagnostic import NewtonDiagnosticsConfig
from VeraGridEngine.enumerations import DynamicIntegrationMethod
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory


class GenericEmtProblem(EmtProblemTemplate):
    __slots__ = list()


# --- Boundary Condition Wrappers ---
class FreezeParameterWrapper(BoundaryUpdateWrapper):
    __slots__ = ['idx_k', 'threshold']

    def __init__(self, idx_k: int, threshold: float):
        self.idx_k: int = idx_k
        self.threshold: float = threshold

    def update(self, t: float, x: np.ndarray, params: np.ndarray) -> None:
        if t > self.threshold:
            params[self.idx_k] = 0.0
        else:
            pass


class SyncTimeWrapper(BoundaryUpdateWrapper):
    __slots__ = ['idx_t']

    def __init__(self, idx_t: int):
        self.idx_t: int = idx_t

    def update(self, t: float, x: np.ndarray, params: np.ndarray) -> None:
        params[self.idx_t] = t


# --- Unit Test Suite ---
@pytest.mark.parametrize("solver_class", (JitSymbolicSolver, JitAdSolver, StructuralVectorizedSolver, StructuralCompiledSolver))
@pytest.mark.parametrize("dense_threshold", (0, 100))
@pytest.mark.parametrize("backtracking", (False, True))
@pytest.mark.parametrize("initial_slope", (-1.0, 17.0))
def test_bdf2_published_derivative_and_order(
        solver_class: type[JitSymbolicSolver] | type[JitAdSolver] | type[StructuralVectorizedSolver] | type[StructuralCompiledSolver],
        dense_threshold: int, backtracking: bool, initial_slope: float) -> None:
    """Verify accepted derivatives and global order against analytic decay.

    :param solver_class: One of the four existing EMT backends.
    :param dense_threshold: Force dense or sparse linear solves.
    :param backtracking: Enable the existing line search.
    :param initial_slope: Consistent or finite inconsistent caller seed.
    :return: None.
    """
    errors: np.ndarray = np.empty(3, dtype=np.float64)
    index: int
    h: float
    solver: JitSymbolicSolver | JitAdSolver | StructuralVectorizedSolver | StructuralCompiledSolver
    problem: GenericEmtProblem
    times: np.ndarray
    values: np.ndarray
    derivatives: np.ndarray
    well: bool
    converged: bool
    for index, h in enumerate((0.1, 0.05, 0.025)):
        x: Var = Var("bdf_decay_x")
        dx: Var = Var("bdf_decay_dx", base_var=x)
        block: Block = Block(name="BdfDecay", state_vars=list((x,)), diff_vars=list((dx,)),
                             state_eqs=list((-x,)), parameters=dict())
        solver, problem = make_solver(solver_class, block, 1.0, h, DynamicIntegrationMethod.DaeBDF2,
                                      1e-10, dense_threshold, backtracking)
        seed: np.ndarray = np.ones(1)
        slope: np.ndarray = np.array((initial_slope,))
        times, values, derivatives, well, converged = solver.simulate(x0=seed, dx0=slope)
        assert well and converged
        np.testing.assert_array_equal(seed, (1.0,))
        np.testing.assert_array_equal(slope, (initial_slope,))
        np.testing.assert_array_equal(derivatives[0], slope)
        assert values[1, 0] == pytest.approx(1.0 / (1.0 + h), abs=1e-8)
        # An accepted Newton flag alone does not prove the published DAE residual.
        np.testing.assert_allclose(derivatives[1:, 0] + values[1:, 0], 0.0, atol=1e-8, rtol=0)
        np.testing.assert_allclose(derivatives[2:, 0],
                                   (1.5 * values[2:, 0] - 2.0 * values[1:-1, 0] + 0.5 * values[:-2, 0]) / h,
                                   atol=1e-8, rtol=0)
        assert times[-1] == pytest.approx(1.0)
        errors[index] = abs(values[-1, 0] - np.exp(-1.0))
    assert np.all(errors[:-1] / errors[1:] >= 3.5)


@pytest.mark.parametrize("solver_class", (JitSymbolicSolver, JitAdSolver, StructuralVectorizedSolver, StructuralCompiledSolver))
@pytest.mark.parametrize("dense_threshold", (0, 100))
def test_bdf2_derivative_uid_order(
        solver_class: type[JitSymbolicSolver] | type[JitAdSolver] | type[StructuralVectorizedSolver] | type[StructuralCompiledSolver],
        dense_threshold: int) -> None:
    """Check unequal rates with independently permuted state and derivative order.

    :param solver_class: Existing EMT backend.
    :param dense_threshold: Force dense or sparse linear solves.
    :return: None.
    """
    reverse: bool
    solver: JitSymbolicSolver | JitAdSolver | StructuralVectorizedSolver | StructuralCompiledSolver
    problem: GenericEmtProblem
    times: np.ndarray
    values: np.ndarray
    derivatives: np.ndarray
    well: bool
    converged: bool
    for reverse in (False, True):
        slow: Var = Var("bdf_slow")
        fast: Var = Var("bdf_fast")
        dslow: Var = Var("bdf_dslow", base_var=slow)
        dfast: Var = Var("bdf_dfast", base_var=fast)
        block: Block = Block(name="BdfUidOrder",
                             state_vars=list((fast, slow) if reverse else (slow, fast)),
                             state_eqs=list((-2.0 * fast, -slow) if reverse else (-slow, -2.0 * fast)),
                             diff_vars=list((dslow, dfast) if reverse else (dfast, dslow)), parameters=dict())
        solver, problem = make_solver(solver_class, block, 0.4, 0.1, DynamicIntegrationMethod.DaeBDF2,
                                      1e-10, dense_threshold)
        slow_index: int = problem.uid2idx_vars[slow.uid]
        fast_index: int = problem.uid2idx_vars[fast.uid]
        dslow_index: int = problem.uid2idx_diff[dslow.uid]
        dfast_index: int = problem.uid2idx_diff[dfast.uid]
        assert slow_index != dslow_index and fast_index != dfast_index
        seed: np.ndarray = np.empty(2)
        seed[slow_index] = 1.0
        seed[fast_index] = 2.0
        times, values, derivatives, well, converged = solver.simulate(x0=seed, dx0=np.array((13.0, 19.0)))
        assert well and converged and times.size == 5
        assert values[1, slow_index] == pytest.approx(1.0 / 1.1, abs=1e-8)
        assert values[1, fast_index] == pytest.approx(2.0 / 1.2, abs=1e-8)
        np.testing.assert_allclose(derivatives[1:, dslow_index] + values[1:, slow_index], 0.0, atol=1e-8, rtol=0)
        np.testing.assert_allclose(derivatives[1:, dfast_index] + 2.0 * values[1:, fast_index], 0.0, atol=1e-8, rtol=0)


@pytest.mark.parametrize("solver_class", (JitSymbolicSolver, JitAdSolver, StructuralVectorizedSolver, StructuralCompiledSolver))
def test_bdf2_fresh_run_and_empty_derivatives(
        solver_class: type[JitSymbolicSolver] | type[JitAdSolver] | type[StructuralVectorizedSolver] | type[StructuralCompiledSolver]) -> None:
    """Keep seeds and empty public derivative vectors intact across fresh calls.

    :param solver_class: Existing EMT backend, including cancellation.
    :return: None.
    """
    algebraic_only: bool
    solver: JitSymbolicSolver | JitAdSolver | StructuralVectorizedSolver | StructuralCompiledSolver
    fresh: JitSymbolicSolver | JitAdSolver | StructuralVectorizedSolver | StructuralCompiledSolver
    cancelled_solver: JitSymbolicSolver | JitAdSolver | StructuralVectorizedSolver | StructuralCompiledSolver
    problem: GenericEmtProblem
    fresh_problem: GenericEmtProblem
    cancelled_problem: GenericEmtProblem
    first: Tuple[np.ndarray, np.ndarray, np.ndarray, bool, bool]
    repeated: Tuple[np.ndarray, np.ndarray, np.ndarray, bool, bool]
    reference: Tuple[np.ndarray, np.ndarray, np.ndarray, bool, bool]
    changed: Tuple[np.ndarray, np.ndarray, np.ndarray, bool, bool]
    cancelled: Tuple[np.ndarray, np.ndarray, np.ndarray, bool, bool]
    for algebraic_only in (False, True):
        x: Var = Var("bdf_empty_x")
        block: Block = Block(name="BdfEmpty", state_vars=list() if algebraic_only else list((x,)),
                             state_eqs=list() if algebraic_only else list((-x,)),
                             algebraic_vars=list((x,)) if algebraic_only else list(),
                             algebraic_eqs=list((x - 2.0,)) if algebraic_only else list(),
                             diff_vars=list(), parameters=dict())
        solver, problem = make_solver(solver_class, block, 0.3, 0.1, DynamicIntegrationMethod.DaeBDF2, 1e-10)
        assert problem.get_dx0().size == 0
        first = solver.simulate(x0=np.array((2.0,)), dx0=np.empty(0))
        repeated = solver.simulate(x0=np.array((2.0,)), dx0=np.empty(0))
        fresh, fresh_problem = make_solver(solver_class, block, 0.3, 0.1, DynamicIntegrationMethod.DaeBDF2, 1e-10)
        reference = fresh.simulate(x0=np.array((3.0,)), dx0=np.empty(0))
        changed = solver.simulate(x0=np.array((3.0,)), dx0=np.empty(0))
        assert first[4] and repeated[4] and reference[4] and changed[4]
        assert first[2].shape == (first[0].size, 0)
        np.testing.assert_allclose(first[1], repeated[1], atol=1e-10, rtol=0)
        np.testing.assert_allclose(changed[1], reference[1], atol=1e-10, rtol=0)
        if algebraic_only:
            np.testing.assert_allclose(first[1][1:], 2.0, atol=1e-10, rtol=0)
        else:
            assert first[1][1, 0] == pytest.approx(2.0 / 1.1, abs=1e-8)
        # A standard iterator supplies the existing callback without a new helper.
        cancellation: Iterator[bool] = iter((False, True))
        cancelled_solver, cancelled_problem = make_solver(
            solver_class, block, 0.3, 0.1, DynamicIntegrationMethod.DaeBDF2,
            1e-10, 100, False, cancellation.__next__)
        cancelled = cancelled_solver.simulate(x0=np.array((2.0,)), dx0=np.empty(0))
        np.testing.assert_allclose(cancelled[1], first[1][:2], atol=1e-10, rtol=0)
        assert cancelled[0].size == 2 and cancelled[2].shape == (2, 0)


@pytest.mark.parametrize("solver_class", (JitSymbolicSolver, JitAdSolver, StructuralVectorizedSolver, StructuralCompiledSolver))
@pytest.mark.parametrize("dense_threshold", (0, 100))
@pytest.mark.parametrize("backtracking", (False, True))
def test_bdf2_coupled_and_nonlinear_dae(
        solver_class: type[JitSymbolicSolver] | type[JitAdSolver] | type[StructuralVectorizedSolver] | type[StructuralCompiledSolver],
        dense_threshold: int, backtracking: bool) -> None:
    """Verify coupled DAE constraints and nonlinear second-order convergence.

    :param solver_class: Existing EMT backend.
    :param dense_threshold: Force dense or sparse linear solves.
    :param backtracking: Enable the existing line search.
    :return: None.
    """
    nonlinear: bool
    solver: JitSymbolicSolver | JitAdSolver | StructuralVectorizedSolver | StructuralCompiledSolver
    problem: GenericEmtProblem
    times: np.ndarray
    values: np.ndarray
    derivatives: np.ndarray
    well: bool
    converged: bool
    for nonlinear in (False, True):
        errors: np.ndarray = np.empty(3)
        index: int
        h: float
        for index, h in enumerate((0.1, 0.05, 0.025)):
            x: Var = Var("bdf_coupled_x")
            dx: Var = Var("bdf_coupled_dx", base_var=x)
            z: Var = Var("bdf_coupled_z")
            block: Block = Block(name="BdfCoupled", state_vars=list((x,)), diff_vars=list((dx,)),
                                 state_eqs=list((-x * x if nonlinear else z,)),
                                 algebraic_vars=list() if nonlinear else list((z,)),
                                 algebraic_eqs=list() if nonlinear else list((z + x,)), parameters=dict())
            solver, problem = make_solver(solver_class, block, 1.0, h, DynamicIntegrationMethod.DaeBDF2,
                                          1e-11, dense_threshold, backtracking)
            seed: np.ndarray = np.ones(1) if nonlinear else np.array((1.0, -1.0))
            times, values, derivatives, well, converged = solver.simulate(x0=seed, dx0=np.array((23.0,)))
            assert well and converged
            if nonlinear:
                np.testing.assert_allclose(derivatives[1:, 0] + values[1:, 0] * values[1:, 0], 0.0, atol=1e-8, rtol=0)
                errors[index] = abs(values[-1, 0] - 0.5)
            else:
                np.testing.assert_allclose(values[1:, 1] + values[1:, 0], 0.0, atol=1e-8, rtol=0)
                np.testing.assert_allclose(derivatives[1:, 0] - values[1:, 1], 0.0, atol=1e-8, rtol=0)
                errors[index] = abs(values[-1, 0] - np.exp(-1.0))
        assert np.all(errors[:-1] / errors[1:] >= 3.5)


def create_decay_system(k_val: float = 1.0) -> Tuple[Block, Var, Var]:
    x: Var = Var("x")
    k: Var = Var("k")
    block: Block = Block(
        name="DecayUnit",
        state_vars=list([x]),
        state_eqs=list([-k * x]),
        parameters=dict({k: Const(k_val)})
    )
    return block, x, k


SOLVERS_TO_TEST: List[Any] = list([JitAdSolver, StructuralVectorizedSolver])


def make_solver(
    solver_class: type[JitSymbolicSolver] | type[JitAdSolver] | type[StructuralVectorizedSolver] | type[StructuralCompiledSolver],
    block: Block,
    t_end: float,
    h: float,
    method: DynamicIntegrationMethod,
    newton_tolerance: float = 1.0e-6,
    dense_threshold: int = 100,
    backtracking: bool = False,
    cancel_checker: Callable[[], bool] | None = None,
) -> Tuple[JitSymbolicSolver | JitAdSolver | StructuralVectorizedSolver | StructuralCompiledSolver, GenericEmtProblem]:
    """Construct a real EMT backend with the declared model and solver settings.

    :param solver_class: Existing implicit EMT backend constructor.
    :param block: Declared state, derivative and algebraic model.
    :param t_end: Requested simulation horizon.
    :param h: Fixed macro time step.
    :param method: Requested integration method.
    :param newton_tolerance: Accepted residual infinity-norm bound.
    :param dense_threshold: Largest system using dense linear solves.
    :param backtracking: Enable the existing line search.
    :param cancel_checker: Optional existing cancellation callback.
    :return: Solver and its canonical problem, sharing the declared variable identity.
    """
    block.unify_blocks()
    static_parameter_values_mapping: Dict[Var, Const] = dict(block.parameters)
    problem: GenericEmtProblem = GenericEmtProblem(
        sys_block=block,
        glob_time=Var("t"),
        static_parameter_values_mapping=static_parameter_values_mapping,
    )
    config: NewtonDiagnosticsConfig = NewtonDiagnosticsConfig(enable_backtracking=backtracking)
    solver: JitSymbolicSolver | JitAdSolver | StructuralVectorizedSolver | StructuralCompiledSolver = solver_class(
        problem, t0=0.0, t_end=t_end, h=h, method=method,
        newton_tolerance=newton_tolerance, dense_threshold=dense_threshold,
        newton_diag_config=config, cancel_checker=cancel_checker)
    return solver, problem


@pytest.mark.parametrize("solver_class", SOLVERS_TO_TEST, ids=lambda cls: cls.__name__)
def test_01_backward_euler_math(solver_class: Any) -> None:
    h: float = 0.1
    block, _, _ = create_decay_system(k_val=1.0)
    solver, prob = make_solver(solver_class, block, h, h, DynamicIntegrationMethod.DaeBackEuler)

    x0: np.ndarray = prob.get_x0()
    x0[0] = 1.0
    dx0: np.ndarray = np.zeros_like(x0, dtype=np.float64)
    dx0[0] = -1.0
    p0: np.ndarray = np.zeros(prob.get_variable_parameter_number(), dtype=np.float64)

    _, y, _, _, _ = solver.simulate(x0=x0, dx0=dx0, params0=p0)

    x_numeric: float = float(y[-1, 0])
    x_expected: float = 1.0 / (1.0 + h)
    assert x_numeric == pytest.approx(x_expected, abs=5e-8)


@pytest.mark.parametrize("solver_class", SOLVERS_TO_TEST, ids=lambda cls: cls.__name__)
def test_02_trapezoid_math(solver_class: Any) -> None:
    h: float = 0.1
    block, _, _ = create_decay_system(k_val=1.0)
    solver, prob = make_solver(solver_class, block, h, h, DynamicIntegrationMethod.DaeTrapezoidal)

    x0: np.ndarray = prob.get_x0()
    x0[0] = 1.0
    dx0: np.ndarray = np.zeros_like(x0, dtype=np.float64)
    dx0[0] = -1.0
    p0: np.ndarray = np.zeros(prob.get_variable_parameter_number(), dtype=np.float64)

    _, y, _, _, _ = solver.simulate(x0=x0, dx0=dx0, params0=p0)

    x_numeric: float = float(y[-1, 0])
    factor: float = (1.0 - h / 2.0) / (1.0 + h / 2.0)
    x_expected: float = 1.0 * factor
    assert x_numeric == pytest.approx(x_expected, abs=5e-8)


@pytest.mark.parametrize("solver_class", SOLVERS_TO_TEST, ids=lambda cls: cls.__name__)
def test_03_boundary_update_fn(solver_class: Any) -> None:
    block, _, k = create_decay_system(k_val=1.0)
    solver, prob = make_solver(solver_class, block, 1.0, 0.1, DynamicIntegrationMethod.DaeBackEuler)

    idx_k: int = prob.uid2idx_params.get(k.uid, 0)
    freeze_updater: FreezeParameterWrapper = FreezeParameterWrapper(idx_k=idx_k, threshold=0.5)

    x0: np.ndarray = prob.get_x0()
    x0[0] = 1.0
    dx0: np.ndarray = np.zeros_like(x0, dtype=np.float64)
    dx0[0] = -1.0
    p0: np.ndarray = np.zeros(prob.get_variable_parameter_number(), dtype=np.float64)

    _, y, _, _, _ = solver.simulate(x0=x0, dx0=dx0, params0=p0, boundary_updater=freeze_updater)

    y_06: float = float(y[6, 0])
    y_10: float = float(y[-1, 0])
    assert y_06 == pytest.approx(y_10, abs=5e-7)


@pytest.mark.parametrize("solver_class", SOLVERS_TO_TEST, ids=lambda cls: cls.__name__)
def test_04_convergence_order(solver_class: Any) -> None:
    block, _, _ = create_decay_system(k_val=1.0)
    t_target: float = 1.0
    exact_sol: float = float(np.exp(-1.0))

    solver_c, prob_c = make_solver(solver_class, block, t_target, 0.1, DynamicIntegrationMethod.DaeTrapezoidal)
    x0_c: np.ndarray = prob_c.get_x0()
    dx0_c: np.ndarray = np.zeros_like(x0_c, dtype=np.float64)
    x0_c[0] = 1.0
    dx0_c[0] = -1.0
    p0_c: np.ndarray = np.zeros(prob_c.get_variable_parameter_number(), dtype=np.float64)
    _, y_c, _, _, _ = solver_c.simulate(x0=x0_c, dx0=dx0_c, params0=p0_c)
    err_c: float = abs(float(y_c[-1, 0]) - exact_sol)

    solver_f, prob_f = make_solver(solver_class, block, t_target, 0.05, DynamicIntegrationMethod.DaeTrapezoidal)
    x0_f: np.ndarray = prob_f.get_x0()
    dx0_f: np.ndarray = np.zeros_like(x0_f, dtype=np.float64)
    x0_f[0] = 1.0
    dx0_f[0] = -1.0
    p0_f: np.ndarray = np.zeros(prob_f.get_variable_parameter_number(), dtype=np.float64)
    _, y_f, _, _, _ = solver_f.simulate(x0=x0_f, dx0=dx0_f, params0=p0_f)
    err_f: float = abs(float(y_f[-1, 0]) - exact_sol)

    ratio: float = err_c / err_f
    assert ratio > 3.8


@pytest.mark.parametrize("solver_class", SOLVERS_TO_TEST, ids=lambda cls: cls.__name__)
def test_05_stiff_system_stability(solver_class: Any) -> None:
    x: Var = Var("x")
    stiff_block: Block = Block(name="Stiff", state_vars=list([x]), state_eqs=list([(-1000) * x]), parameters=dict())

    solver, prob = make_solver(solver_class, stiff_block, 1.0, 0.1, DynamicIntegrationMethod.DaeBackEuler)
    x0: np.ndarray = prob.get_x0()
    x0[0] = 1.0
    dx0: np.ndarray = np.zeros_like(x0, dtype=np.float64)
    p0: np.ndarray = np.zeros(prob.get_variable_parameter_number(), dtype=np.float64)

    _, y, _, _, _ = solver.simulate(x0=x0, dx0=dx0, params0=p0)

    assert abs(float(y[-1, 0])) < 1e-2


@pytest.mark.parametrize("solver_class", SOLVERS_TO_TEST, ids=lambda cls: cls.__name__)
def test_06_nonlinear_jacobian(solver_class: Any) -> None:
    x: Var = Var("x")
    nl_block: Block = Block(name="NonLinear", state_vars=list([x]), state_eqs=list([x * x]), parameters=dict())

    solver, prob = make_solver(solver_class, nl_block, 0.5, 0.01, DynamicIntegrationMethod.DaeTrapezoidal)
    x0: np.ndarray = prob.get_x0()
    x0[0] = 1.0
    dx0: np.ndarray = np.ones_like(x0, dtype=np.float64)
    p0: np.ndarray = np.zeros(prob.get_variable_parameter_number(), dtype=np.float64)

    _, y, _, _, _ = solver.simulate(x0=x0, dx0=dx0, params0=p0)

    assert float(y[-1, 0]) == pytest.approx(2.0, abs=0.05)


@pytest.mark.parametrize("solver_class", SOLVERS_TO_TEST, ids=lambda cls: cls.__name__)
def test_07_energy_conservation(solver_class: Any) -> None:
    vf: VarFactory = VarFactory()
    x: Var = vf.add_var("pos")
    v: Var = vf.add_var("vel")
    dx: Var = vf.add_diff_var(name="d_pos", base_var=x)
    dv: Var = vf.add_diff_var(name="d_vel", base_var=v)
    osc_block: Block = Block(
        name="Oscillator",
        state_vars=list([x, v]),
        state_eqs=list([v, -x]),
        diff_vars=list([dx, dv]),
        parameters=dict(),
    )

    solver_trap, prob_trap = make_solver(solver_class, osc_block, 20.0, 0.1, DynamicIntegrationMethod.DaeTrapezoidal)
    x0: np.ndarray = prob_trap.get_x0()
    dx0: np.ndarray = np.zeros_like(x0, dtype=np.float64)
    x0[0] = 1.0
    dx0[1] = -1.0
    p0: np.ndarray = np.zeros(prob_trap.get_variable_parameter_number(), dtype=np.float64)

    _, y_trap, _, _, _ = solver_trap.simulate(x0=x0, dx0=dx0, params0=p0)
    amp_trap: float = float(np.max(np.abs(y_trap[-20:, 0])))
    assert amp_trap > 0.95

    solver_be, prob_be = make_solver(solver_class, osc_block, 20.0, 0.1, DynamicIntegrationMethod.DaeBackEuler)
    x0_be: np.ndarray = prob_be.get_x0()
    dx0_be: np.ndarray = np.zeros_like(x0_be, dtype=np.float64)
    x0_be[0] = 1.0
    dx0_be[1] = -1.0
    p0_be: np.ndarray = np.zeros(prob_be.get_variable_parameter_number(), dtype=np.float64)

    _, y_be, _, _, _ = solver_be.simulate(x0=x0_be, dx0=dx0_be, params0=p0_be)
    amp_be: float = float(np.max(np.abs(y_be[-20:, 0])))
    assert amp_be < 0.5


@pytest.mark.parametrize("solver_class", SOLVERS_TO_TEST, ids=lambda cls: cls.__name__)
def test_08_time_dependent_forcing(solver_class: Any) -> None:
    x: Var = Var("x")
    t_driver: Var = Var("t_driver")
    forcing_block: Block = Block(
        name="Forcing",
        state_vars=list([x]),
        state_eqs=list([t_driver]),
        event_dict=dict({t_driver: Const(0.0)}),
        parameters=dict(),
    )

    solver, prob = make_solver(solver_class, forcing_block, 2.0, 0.1, DynamicIntegrationMethod.DaeTrapezoidal)

    idx_t: int = prob.uid2idx_event_params.get(t_driver.uid, 0)
    sync_updater: SyncTimeWrapper = SyncTimeWrapper(idx_t=idx_t)

    x0: np.ndarray = prob.get_x0()
    dx0: np.ndarray = np.zeros_like(x0, dtype=np.float64)
    p0: np.ndarray = np.zeros(prob.get_variable_parameter_number(), dtype=np.float64)

    _, y, _, _, _ = solver.simulate(x0=x0, dx0=dx0, params0=p0, boundary_updater=sync_updater)

    expected: float = (2.0 ** 2) / 2.0
    assert float(y[-1, 0]) == pytest.approx(expected, abs=5e-3)
