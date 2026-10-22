# SPDX-License-Identifier: MPL-2.0
"""Independent steam-stage transfer functions, valve limits and asymmetric deadband checks."""
from __future__ import annotations

import numpy as np
import pytest
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.international_standards.governors.ieeeg1 import (
    MultiStageSteamGovernorParameters, build_ieeeg1_template)
from VeraGridEngine.Utils.Symbolic.block import Block
from tests.RMS.test_native_turbine_governors import initialized_values, evaluate_controller, linearized_response


@pytest.mark.parametrize('shaft', (0, 1, 2))
@pytest.mark.parametrize('frequency', (.02, .4, 2.0))
@pytest.mark.parametrize('times', ((.3, 5.0, .5, .1), (.3, 0.0, .5, 0.0), (0.0, 0.0, 0.0, 0.0)))
def test_multistage_steam_frequency_response(shaft: int, frequency: float,
                                           times: tuple[float, float, float, float]) -> None:
    """Each shaft and their total reproduce independently summed steam-stage responses.

    :param shaft: First shaft, second shaft or total output.
    :param frequency: Perturbation frequency in hertz.
    :param times: Positive stage times or exact zero-time reductions.
    """
    weights: tuple[float, ...] = (.3, .1, .2, .1, .1, .1, .05, .05)
    block: Block = build_ieeeg1_template(VarFactory(), 'steam', MultiStageSteamGovernorParameters(
        gain=20, speed_lag=.1, speed_lead=.03, turbine_times=times, fractions=weights)).block
    values: dict[int, float] = initialized_values(block)
    block.out_vars[0], block.out_vars[shaft] = block.out_vars[shaft], block.out_vars[0]
    s: complex = 2j*np.pi*frequency
    cumulative: complex = 1
    turbine: complex = 0j
    index: int
    for index in range(4):
        cumulative /= 1+times[index]*s
        coefficient: float = weights[2*index]+weights[2*index+1] if shaft == 2 else weights[2*index+shaft]
        turbine += coefficient*cumulative
    expected: complex = -20*(1+.03*s)*turbine/((1+.1*s)*(1+.2*s))
    assert linearized_response(block, values, 1, frequency) == pytest.approx(expected, rel=1e-7, abs=1e-9)


@pytest.mark.parametrize('instantaneous', (False, True))
@pytest.mark.parametrize('total_gain', (.8, 1.0, 1.5))
def test_multistage_steam_equilibrium_and_state_count(instantaneous: bool, total_gain: float) -> None:
    """Nonunit combined shaft fractions initialize valve and steam memories from actual total power.

    :param instantaneous: Remove speed compensation and all steam lags exactly.
    :param total_gain: Sum of first- and second-shaft fractions.
    """
    block: Block = build_ieeeg1_template(VarFactory(), 'steam', MultiStageSteamGovernorParameters(
        speed_lag=0 if instantaneous else .1, turbine_times=(0, 0, 0, 0) if instantaneous else (.3, 5, .5, .1),
        fractions=(.2*total_gain, .1*total_gain, .2*total_gain, .1*total_gain,
                   .1*total_gain, .1*total_gain, .1*total_gain, .1*total_gain))).block
    values: dict[int, float] = initialized_values(block)
    assert len(block.state_vars) == (1 if instantaneous else 6)
    assert len(block.algebraic_vars) == len(block.algebraic_eqs)
    assert values[block.out_vars[0].uid] == pytest.approx(.3)
    assert values[block.out_vars[1].uid] == pytest.approx(.2)
    assert values[block.out_vars[2].uid] == pytest.approx(.5)
    np.testing.assert_allclose([eq.eval_uid(values) for eq in block.state_eqs], 0, atol=1e-12)
    np.testing.assert_allclose([eq.eval_uid(values) for eq in block.algebraic_eqs], 0, atol=1e-12)


@pytest.mark.parametrize('upper', (False, True))
def test_steam_valve_rate_and_position_stops(upper: bool) -> None:
    """Travel speed is bounded before independent valve-position stops and inward recovery.

    :param upper: Opening rather than closing movement.
    """
    block: Block = build_ieeeg1_template(VarFactory(), 'steam', MultiStageSteamGovernorParameters(
        speed_lag=0, opening_rate=.1, closing_rate=-.2)).block
    values: dict[int, float] = initialized_values(block)
    states: np.ndarray = np.asarray([values[var.uid] for var in block.state_vars])
    speed: float = 0 if upper else 2
    derivative, output = evaluate_controller(block, values, states, speed)
    assert derivative[0] == pytest.approx(.1 if upper else -.2)
    states[0] = 1.2 if upper else 0
    derivative, output = evaluate_controller(block, values, states, speed)
    assert derivative[0] == 0
    derivative, output = evaluate_controller(block, values, states, 2 if upper else 0)
    assert derivative[0] < 0 if upper else derivative[0] > 0


@pytest.mark.parametrize('speed,expected', ((1.0, 0.0), (1.125, 0.0), (.9375, 0.0),
    (1.25, -.125), (.875, .0625)))
def test_steam_governor_asymmetric_deadband(speed: float, expected: float) -> None:
    """The asymmetric speed deadband subtracts its threshold continuously before valve demand.

    :param speed: Absolute per-unit shaft speed.
    :param expected: Valve derivative with unit gain/time and inactive travel limits.
    """
    block: Block = build_ieeeg1_template(VarFactory(), 'steam', MultiStageSteamGovernorParameters(
        gain=1, speed_lag=0, servo_time=1, opening_rate=1, closing_rate=-1,
        deadband_high=.125, deadband_low=-.0625)).block
    values: dict[int, float] = initialized_values(block)
    states: np.ndarray = np.asarray([values[var.uid] for var in block.state_vars])
    derivative, output = evaluate_controller(block, values, states, speed)
    assert derivative[0] == pytest.approx(expected)
