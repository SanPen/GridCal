# SPDX-License-Identifier: MPL-2.0
"""Independent transfer-function and switching checks for polynomial stabilizers."""
from __future__ import annotations

import numpy as np
import pytest

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.international_standards.power_system_stabilizers.ieeest import (
    IeeestParameters, build_ieeest_template,
)
from VeraGridEngine.Utils.Symbolic.block import Block
from tests.RMS.test_native_turbine_governors import initialized_values, linearized_response, evaluate_controller


@pytest.mark.parametrize('coefficients,state_count', (
    ((.3, .02, .4, .03, .2, .01), 7),
    ((.3, 0, .4, 0, .2, .01), 5),
    ((.3, .02, 0, 0, .2, .01), 5),
    ((.3, 0, 0, 0, .2, 0), 4),
    ((0, 0, 0, 0, 0, 0), 3),
))
@pytest.mark.parametrize('frequency', (.02, .4, 2.0))
@pytest.mark.parametrize('reset_numerator', (0.0, 5.0))
def test_polynomial_stabilizer_transfer(coefficients: tuple[float, float, float, float, float, float],
                                       state_count: int, frequency: float, reset_numerator: float) -> None:
    """Running equations reproduce the independently evaluated complex rational transfer."""
    settings: IeeestParameters = IeeestParameters(filter_coefficients=coefficients, reset_numerator=reset_numerator)
    block: Block = build_ieeest_template(VarFactory(), parameters=settings).block
    values: dict[int, float] = initialized_values(block)
    assert len(block.state_vars) == state_count
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs], 0, atol=1e-12)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.algebraic_eqs], 0, atol=1e-12)
    a1, a2, a3, a4, a5, a6 = coefficients
    s: complex = 2j*np.pi*frequency
    expected: complex = (1+a5*s+a6*s*s)/((1+a1*s+a2*s*s)*(1+a3*s+a4*s*s))
    expected *= (1+settings.lead1*s)/(1+settings.lag1*s)*(1+settings.lead2*s)/(1+settings.lag2*s)
    expected *= settings.gain*(s*reset_numerator if reset_numerator != 0 else 1)/(1+s*settings.reset_denominator)
    assert linearized_response(block, values, 0.0, frequency) == pytest.approx(expected, rel=1e-8, abs=1e-10)


@pytest.mark.parametrize('voltage,upper,lower,expected', (
    (1.0, 1.1, .9, .1), (.8, 1.1, .9, 0), (1.2, 1.1, .9, 0),
    (.8, 1.1, 0, .1), (1.2, 0, .9, .1),
))
def test_voltage_supervision_preserves_memory(voltage: float, upper: float, lower: float, expected: float) -> None:
    """Each voltage threshold can be disabled independently and blocking does not freeze states."""
    block: Block = build_ieeest_template(VarFactory(), parameters=IeeestParameters(
        filter_coefficients=(0, 0, 0, 0, 0, 0), lead1=0, lag1=0, lead2=0, lag2=0,
        reset_numerator=0, voltage_upper=upper, voltage_lower=lower)).block
    values: dict[int, float] = initialized_values(block)
    values[block.in_vars[1].uid] = voltage
    derivative: np.ndarray
    output: float
    derivative, output = evaluate_controller(block, values, np.array([.2]), .5)
    assert output == pytest.approx(expected)
    assert derivative[0] == pytest.approx(.3/5)


@pytest.mark.parametrize('coefficients', ((0, 0, 0, 0, 1, 0), (.1, 0, 0, 0, 0, .1), (-.1, 0, 0, 0, 0, 0)))
def test_improper_or_negative_filter_is_rejected(coefficients: tuple[float, float, float, float, float, float]) -> None:
    """Unavailable derivatives never become arbitrary tiny-time approximations."""
    with pytest.raises(ValueError):
        build_ieeest_template(VarFactory(), parameters=IeeestParameters(filter_coefficients=coefficients))


@pytest.mark.parametrize('channel', (0, 1))
@pytest.mark.parametrize('frequency', (.02, .4, 2.0))
@pytest.mark.parametrize('reset_numerator', (0.0, 5.0))
@pytest.mark.parametrize('transducer_times,phase_times,state_count', (
    ((.02, .1), ((.2, .05), (.3, .1), (.1, .05)), 6),
    ((0, 0), ((0, 0), (.3, .1), (0, 0)), 2),
))
def test_dual_input_stabilizer_transfer(channel: int, frequency: float, reset_numerator: float,
                                        transducer_times: tuple[float, float],
                                        phase_times: tuple[tuple[float, float], tuple[float, float], tuple[float, float]],
                                        state_count: int) -> None:
    """Both signed measurement paths independently reproduce the full six-stage transfer."""
    from VeraGridEngine.Templates.Rms.international_standards.power_system_stabilizers.iee2st import (
        Iee2stParameters, build_iee2st_template,
    )
    settings: Iee2stParameters = Iee2stParameters(gains=(2, -3), transducer_times=transducer_times,
        reset_numerator=reset_numerator, phase_times=phase_times)
    block: Block = build_iee2st_template(VarFactory(), parameters=settings).block
    values: dict[int, float] = initialized_values(block)
    assert len(block.state_vars) == state_count
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs], 0, atol=1e-12)
    s: complex = 2j*np.pi*frequency
    expected: complex = settings.gains[channel]/(1+s*transducer_times[channel])
    expected *= (s*reset_numerator if reset_numerator != 0 else 1)/(1+s*settings.reset_denominator)
    for lead, lag in phase_times:
        expected *= (1+s*lead)/(1+s*lag)
    # The response evaluator perturbs the first public input; select either
    # independent path without changing the equations or the other measurement.
    block.in_vars[0], block.in_vars[channel] = block.in_vars[channel], block.in_vars[0]
    assert linearized_response(block, values, 0.0, frequency) == pytest.approx(expected, rel=1e-8, abs=1e-10)


def test_stabilizer_unipolar_output_limit_initializes_consistently() -> None:
    """A limit interval excluding zero has its actual clipped steady output as the seed."""
    block: Block = build_ieeest_template(VarFactory(), parameters=IeeestParameters(lower=.01, upper=.1)).block
    values: dict[int, float] = initialized_values(block)
    assert values[block.out_vars[0].uid] == pytest.approx(.01)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.algebraic_eqs], 0, atol=1e-12)
