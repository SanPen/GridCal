# SPDX-License-Identifier: MPL-2.0
"""Independent reset slopes, rapid-action thresholds and rotating-field equilibria."""
from __future__ import annotations

import numpy as np
import pytest
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.electromechanical_exciter import (
    ElectromechanicalExciterKind, ElectromechanicalExciterParameters, build_electromechanical_exciter)
from VeraGridEngine.Utils.Symbolic.block import Block
from tests.RMS.test_native_turbine_governors import initialized_values, evaluate_controller, linearized_response


@pytest.mark.parametrize('kind', tuple(ElectromechanicalExciterKind))
@pytest.mark.parametrize('automatic', (False, True))
def test_electromechanical_equilibrium(kind: ElectromechanicalExciterKind, automatic: bool) -> None:
    """Reset memory balances saturated field losses under explicit and calibrated coefficients.

    :param kind: Physical regulator mechanism.
    :param automatic: Derive capability and resistance from saturation and initial field.
    """
    p: ElectromechanicalExciterParameters = ElectromechanicalExciterParameters(
        regulator_max=None if automatic else 5, field_gain=None if automatic else 1,
        e1=.8, se1=.1, e2=1.2, se2=.4)
    block: Block = build_electromechanical_exciter(VarFactory(), 'mechanics', kind, p).block
    values: dict[int, float] = initialized_values(block)
    assert len(block.state_vars) == (3 if kind in (ElectromechanicalExciterKind.NORMALIZED_RESET,ElectromechanicalExciterKind.BOUNDED_NORMALIZED_RESET) else 2)
    assert len(block.algebraic_vars) == len(block.algebraic_eqs)
    np.testing.assert_allclose([eq.eval_uid(values) for eq in block.state_eqs], 0, atol=1e-12)
    np.testing.assert_allclose([eq.eval_uid(values) for eq in block.algebraic_eqs], 0, atol=1e-12)
    if automatic:
        assert values[block.out_vars[1].uid] == pytest.approx(.048)
    else:
        pass


@pytest.mark.parametrize('kind', tuple(ElectromechanicalExciterKind))
@pytest.mark.parametrize('frequency', (.02, .4, 2.0))
@pytest.mark.parametrize('zero_time', (False, True))
def test_electromechanical_transfer(kind: ElectromechanicalExciterKind, frequency: float, zero_time: bool) -> None:
    """Running equations reproduce independently derived small-signal transfer functions.

    :param kind: Physical reset mechanism.
    :param frequency: Perturbation frequency in hertz.
    :param zero_time: Remove sensing delay and select integral rather than lag regulation.
    """
    reset_time: float = 0 if zero_time and kind == ElectromechanicalExciterKind.LAG_OR_INTEGRAL else 2
    sensing_time: float = 0 if zero_time else .03
    block: Block = build_electromechanical_exciter(VarFactory(), 'mechanics', kind,
        ElectromechanicalExciterParameters(tr=sensing_time, reset_time=reset_time,
            gain=4, fast_band=.125, regulator_max=4, regulator_min=-4, se1=0, se2=0)).block
    values: dict[int, float] = initialized_values(block)
    actual: complex = linearized_response(block, values, 1.0, frequency)
    s: complex = 2j*np.pi*frequency
    expected: complex
    if kind == ElectromechanicalExciterKind.DEADBAND_RESET:
        expected = 0j
    elif kind == ElectromechanicalExciterKind.INTEGRAL_RESET:
        expected = -1/(2*s*(1+.5*s))
    elif kind in (ElectromechanicalExciterKind.NORMALIZED_RESET,ElectromechanicalExciterKind.BOUNDED_NORMALIZED_RESET):
        expected = -8/(.125*2*s*(1+.5*s)*(1+sensing_time*s))
    elif zero_time:
        expected = -4/(s*(1+.5*s))
    else:
        expected = -4/((1+2*s)*(1+.5*s))
    assert actual == pytest.approx(expected, rel=2e-8, abs=1e-10)


@pytest.mark.parametrize('kind', (ElectromechanicalExciterKind.DEADBAND_RESET,
    ElectromechanicalExciterKind.INTEGRAL_RESET, ElectromechanicalExciterKind.NORMALIZED_RESET, ElectromechanicalExciterKind.BOUNDED_NORMALIZED_RESET))
@pytest.mark.parametrize('error', (.0625, .125, .25, -.25))
def test_electromechanical_reset_and_rapid_forcing(kind: ElectromechanicalExciterKind, error: float) -> None:
    """Independent relay slopes and equality conventions remain observable at exact binary thresholds.

    :param kind: Physical reset mechanism.
    :param error: Positive or negative voltage error, including the exact forcing threshold.
    """
    block: Block = build_electromechanical_exciter(VarFactory(), 'mechanics', kind,
        ElectromechanicalExciterParameters(tr=0, reset_time=2, reset_deadband=.03125,
            fast_band=.125, regulator_max=4, regulator_min=-4, se1=0, se2=0)).block
    values: dict[int, float] = initialized_values(block)
    states: np.ndarray = np.asarray([values[var.uid] for var in block.state_vars])
    derivative, output = evaluate_controller(block, values, states, 1-error)
    reset: float
    if kind == ElectromechanicalExciterKind.DEADBAND_RESET:
        reset = .5 if error > 0 else -.5
    elif kind == ElectromechanicalExciterKind.INTEGRAL_RESET:
        reset = error/2
    else:
        reset = 8*np.clip(error, -.125, .125)/(.125*2)
    rapid: bool = abs(error) >= .125 if kind == ElectromechanicalExciterKind.NORMALIZED_RESET else abs(error) > .125
    forcing: float = (4 if error > 0 else -4) if rapid else 1
    assert derivative[0] == pytest.approx(reset)
    assert derivative[1] == pytest.approx((forcing-1)/.5)
    assert output == 1


@pytest.mark.parametrize('reset_time', (0.0, 2.0))
def test_lag_regulator_rapid_path_uses_initial_voltage(reset_time: float) -> None:
    """A biased normal reference does not trigger rapid forcing at the operating point.

    :param reset_time: Positive lag time or the exact integral special case.
    """
    block: Block = build_electromechanical_exciter(VarFactory(), 'mechanics',
        ElectromechanicalExciterKind.LAG_OR_INTEGRAL, ElectromechanicalExciterParameters(
            gain=2, reset_time=reset_time, fast_band=.125, se1=0, se2=0)).block
    values: dict[int, float] = initialized_values(block)
    states: np.ndarray = np.asarray([values[var.uid] for var in block.state_vars])
    derivative, output = evaluate_controller(block, values, states, 1)
    np.testing.assert_allclose(derivative, 0, atol=1e-12)
    derivative, output = evaluate_controller(block, values, states, 1-.0625)
    assert derivative[0] == pytest.approx(.125 if reset_time == 0 else .0625)
    assert derivative[1] == 0
    assert output == 1


def test_external_field_clip_preserves_internal_loss_feedback() -> None:
    """The delivered field is capped while its raw memory continues to discharge through raw resistance."""
    block: Block = build_electromechanical_exciter(VarFactory(), 'mechanics',
        ElectromechanicalExciterKind.LAG_OR_INTEGRAL, ElectromechanicalExciterParameters(
            gain=2, field_max=1.5, se1=0, se2=0)).block
    values: dict[int, float] = initialized_values(block)
    states: np.ndarray = np.asarray([values[var.uid] for var in block.state_vars])
    states[1] = 2
    derivative, output = evaluate_controller(block, values, states, 1)
    assert output == 1.5
    assert derivative[1] == -2


@pytest.mark.parametrize('kind', tuple(ElectromechanicalExciterKind))
def test_reset_stop_releases_inward(kind: ElectromechanicalExciterKind) -> None:
    """The upper reset-memory stop prevents outward motion and permits inward recovery.

    :param kind: Physical reset mechanism.
    """
    block: Block = build_electromechanical_exciter(VarFactory(), 'mechanics', kind,
        ElectromechanicalExciterParameters(tr=0, gain=10, se1=0, se2=0)).block
    values: dict[int, float] = initialized_values(block)
    states: np.ndarray = np.asarray([values[var.uid] for var in block.state_vars])
    states[0] = 5
    derivative, output = evaluate_controller(block, values, states, 0)
    assert derivative[0] == 0
    derivative, output = evaluate_controller(block, values, states, 2)
    assert derivative[0] < 0
