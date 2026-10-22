# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""Check independent cycle constraints, rather than trusting convergence flags."""
from types import SimpleNamespace

import numpy as np
import pytest

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.initialization_emt import run_emt_native_initialization
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, sin
from VeraGridEngine.enumerations import EmtInitializationMethod, EmtInitializationStatus


class PeriodicProblem(EmtProblemTemplate):
    __slots__ = ("grid",)


def build_periodic_problem(harmonic=2):
    vf = VarFactory()
    theta, x, y = (vf.add_var(name) for name in ("theta_abs_", "x", "y"))
    dtheta = vf.add_diff_var("dtheta", base_var=theta)
    dx = vf.add_diff_var("dx", base_var=x)
    omega = 2 * np.pi
    block = Block(
        state_vars=[theta, x], diff_vars=[dtheta, dx],
        state_eqs=[Const(omega), -4 * x + sin(harmonic * theta)],
        algebraic_vars=[y], algebraic_eqs=[y - x],
        # This assignment duplicates the algebraic equation. Treating it as
        # another global constraint would leave the amplitude undetermined.
        init_eqs={x: y, theta: Const(50.0)},
    )
    problem = PeriodicProblem(sys_block=block, glob_time=vf.add_var("t"),
                              static_parameter_values_mapping={})
    problem.grid = SimpleNamespace(fBase=1., buses=[], lines=[], transformers2w=[], loads=[], generators=[])
    problem.init_guess.update({theta.uid: .3, x.uid: .8, y.uid: .8})
    problem.diff_init_guess.update({dtheta.uid: omega, dx.uid: 0.})
    return problem, theta, x, y, dx


@pytest.mark.parametrize("method", [EmtInitializationMethod.ConsistentNewton, EmtInitializationMethod.PseudoTransient])
@pytest.mark.parametrize("clear_assignments", [False, True])
def test_periodic_constraints_solve_original_dynamics(method, clear_assignments):
    problem, theta, x, y, dx = build_periodic_problem()
    if clear_assignments:
        problem.sys_block.init_eqs.clear()
    options = EmtOptions(initialization_method=method, init_periodic_samples=17)
    report = run_emt_native_initialization(problem, options)
    assert report.status == EmtInitializationStatus.RESOLVED, report.message
    assert report.method_used == method
    # Analytic response of x' + 4*x = sin(2*theta), theta'=2*pi.
    w = 4 * np.pi
    expected = (4 * np.sin(.6) - w * np.cos(.6)) / (16 + w*w)
    values = problem.get_x0()
    assert values[problem.get_var_idx(theta)] == pytest.approx(.3, abs=1e-9)
    assert values[problem.get_var_idx(x)] == pytest.approx(expected, abs=1e-9)
    assert values[problem.get_var_idx(y)] == pytest.approx(expected, abs=1e-9)
    assert problem.get_dx0()[problem.get_diff_var_idx(dx)] == pytest.approx(
        -4 * expected + np.sin(.6), abs=1e-8,
    )


def test_underresolved_cycle_does_not_apply_false_solution():
    problem, *_ = build_periodic_problem(harmonic=8)
    before, before_dx = problem.get_x0().copy(), problem.get_dx0().copy()
    report = run_emt_native_initialization(problem, EmtOptions(
        initialization_method=EmtInitializationMethod.ConsistentNewton, init_periodic_samples=9,
    ))
    assert report.status == EmtInitializationStatus.FAILED
    assert "between samples" in report.message
    np.testing.assert_array_equal(problem.get_x0(), before)
    np.testing.assert_array_equal(problem.get_dx0(), before_dx)


def test_time_dependent_runtime_source_is_rejected():
    problem, *_ = build_periodic_problem()
    source = VarFactory().add_var("forcing")
    problem.sys_block.event_dict[source] = sin(problem.glob_time)
    before = problem.get_x0().copy()
    report = run_emt_native_initialization(problem, EmtOptions(
        initialization_method=EmtInitializationMethod.ConsistentNewton, init_periodic_samples=17,
    ))
    assert report.status == EmtInitializationStatus.FAILED
    assert "time-dependent runtime parameters" in report.message
    np.testing.assert_array_equal(problem.get_x0(), before)
