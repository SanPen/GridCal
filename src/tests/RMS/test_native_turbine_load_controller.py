# SPDX-License-Identifier: MPL-2.0
"""Independent measured-power and frequency-bias response of an outer turbine controller."""
from __future__ import annotations

import numpy as np
import pytest
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.international_standards.governors.lcfb1 import (
    TurbineLoadControllerParameters, build_lcfb1_template)
from VeraGridEngine.Utils.Symbolic.block import Block
from tests.RMS.test_native_turbine_governors import initialized_values, evaluate_controller, linearized_response


@pytest.mark.parametrize('time', (0.0, 2.0))
@pytest.mark.parametrize('frequency', (.02, .4, 2.0))
@pytest.mark.parametrize('path', (0, 1))
def test_load_controller_frequency_response(time: float, frequency: float, path: int) -> None:
    """Speed bias and measured electrical power enter distinct independently derived PI responses.

    :param time: Positive measurement time or the exact algebraic reduction.
    :param frequency: Perturbation frequency in hertz.
    :param path: Speed or electrical-power measurement input.
    """
    block: Block = build_lcfb1_template(VarFactory(), 'load', TurbineLoadControllerParameters(
        frequency_bias=2, power_time=time, proportional_gain=.3, integral_gain=.05)).block
    values: dict[int, float] = initialized_values(block)
    if path == 1:
        block.in_vars[0], block.in_vars[1] = block.in_vars[1], block.in_vars[0]
    else:
        pass
    s: complex = 2j*np.pi*frequency
    pi: complex = .3+.05/s
    expected: complex = -2*pi if path == 0 else -pi/(1+time*s)
    assert linearized_response(block, values, 1 if path == 0 else .5, frequency) == pytest.approx(expected, rel=1e-7, abs=1e-9)


@pytest.mark.parametrize('time', (0.0, 2.0))
@pytest.mark.parametrize('ki', (0.0, .05))
def test_load_controller_equilibrium_and_exact_reductions(time: float, ki: float) -> None:
    """Measurement stores actual power while reference offset and controller memory remain separate.

    :param time: Measurement time, including its exact-zero reduction.
    :param ki: Active integration or a constant initialized integral memory.
    """
    block: Block = build_lcfb1_template(VarFactory(), 'load', TurbineLoadControllerParameters(
        power_time=time, integral_gain=ki)).block
    values: dict[int, float] = initialized_values(block)
    assert len(block.state_vars) == (1 if time == 0 else 2)
    assert len(block.algebraic_vars) == len(block.algebraic_eqs)
    assert values[block.out_vars[0].uid] == .5
    assert values[block.out_vars[1].uid] == 0
    np.testing.assert_allclose([eq.eval_uid(values) for eq in block.state_eqs], 0, atol=1e-12)
    np.testing.assert_allclose([eq.eval_uid(values) for eq in block.algebraic_eqs], 0, atol=1e-12)


@pytest.mark.parametrize('error,expected', ((0.0, 0.0), (.03125, 0.0), (-.03125, 0.0),
    (.0625, .03125), (-.0625, -.03125), (.5, .125), (-.5, -.125)))
def test_load_error_deadband_and_limit(error: float, expected: float) -> None:
    """Deadband subtracts its threshold before the independent symmetric error limiter.

    :param error: Power setpoint mismatch at nominal speed.
    :param expected: Independently calculated integral-memory derivative with unit gain.
    """
    block: Block = build_lcfb1_template(VarFactory(), 'load', TurbineLoadControllerParameters(
        power_time=0, deadband=.03125, error_limit=.125, integral_gain=1)).block
    values: dict[int, float] = initialized_values(block)
    values[block.in_vars[3].uid] = .5+error
    states: np.ndarray = np.asarray([values[var.uid] for var in block.state_vars])
    derivative, output = evaluate_controller(block, values, states, 1)
    assert derivative[0] == pytest.approx(expected)


@pytest.mark.parametrize('upper', (False, True))
def test_load_reference_memory_stop_and_recovery(upper: bool) -> None:
    """Bounded integral memory blocks outward motion and recovers without freezing proportional demand.

    :param upper: Upper correction bound rather than lower correction bound.
    """
    block: Block = build_lcfb1_template(VarFactory(), 'load', TurbineLoadControllerParameters(
        power_time=0, integral_gain=1, proportional_gain=1, correction_limit=.05)).block
    values: dict[int, float] = initialized_values(block)
    values[block.in_vars[3].uid] = 1 if upper else 0
    states: np.ndarray = np.asarray([.05 if upper else -.05])
    derivative, output = evaluate_controller(block, values, states, 1)
    assert derivative[0] == 0
    assert output == pytest.approx(.55 if upper else .45)
    values[block.in_vars[3].uid] = 0 if upper else 1
    derivative, output = evaluate_controller(block, values, states, 1)
    assert derivative[0] < 0 if upper else derivative[0] > 0
