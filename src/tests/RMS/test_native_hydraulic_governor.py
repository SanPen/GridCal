# SPDX-License-Identifier: MPL-2.0
"""Independent hydraulic governor equilibrium, water-column response and physical stops."""
from __future__ import annotations

import numpy as np
import pytest
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.international_standards.governors.ieeeg3 import (
    HydraulicGovernorParameters, build_ieeeg3_template)
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Expr
from tests.RMS.test_native_turbine_governors import initialized_values, evaluate_controller, linearized_response


@pytest.mark.parametrize('turbine_gain', (.8, 1.0, 1.5))
def test_hydraulic_governor_equilibrium(turbine_gain: float) -> None:
    """Steady gate-to-power gain determines gate and reference initialization.

    :param turbine_gain: Nonunit steady hydraulic power coefficient.
    """
    block: Block = build_ieeeg3_template(VarFactory(), 'hydro',
        HydraulicGovernorParameters(a23=turbine_gain)).block
    values: dict[int, float] = initialized_values(block)
    assert len(block.state_vars) == 4
    assert len(block.algebraic_vars) == len(block.algebraic_eqs)
    assert values[block.out_vars[0].uid] == .5
    assert values[block.out_vars[1].uid] == pytest.approx(.5/turbine_gain)
    np.testing.assert_allclose([eq.eval_uid(values) for eq in block.state_eqs], 0, atol=1e-12)
    np.testing.assert_allclose([eq.eval_uid(values) for eq in block.algebraic_eqs], 0, atol=1e-12)


@pytest.mark.parametrize('frequency', (.02, .4, 2.0))
@pytest.mark.parametrize('transient_droop', (0.0, .4))
@pytest.mark.parametrize('a23', (.8, 1.5))
def test_hydraulic_governor_frequency_response(frequency: float, transient_droop: float, a23: float) -> None:
    """Pilot/gate dynamics, both droop paths and inverse hydraulic response match an independent loop equation.

    :param frequency: Perturbation frequency in hertz.
    :param transient_droop: Disable or enable transient droop feedback.
    :param a23: Steady gate-to-power gain.
    """
    block: Block = build_ieeeg3_template(VarFactory(), 'hydro',
        HydraulicGovernorParameters(transient_droop=transient_droop, a23=a23)).block
    values: dict[int, float] = initialized_values(block)
    s: complex = 2j*np.pi*frequency
    servo: complex = 1/(.2*s*(1+.05*s))
    feedback: complex = .05+transient_droop*5*s/(1+5*s)
    turbine: complex = a23*(1+(.5-1.5/a23)*s)/(1+.5*s)
    expected: complex = -servo*turbine/(1+servo*feedback)
    assert linearized_response(block, values, 1, frequency) == pytest.approx(expected, rel=1e-7, abs=1e-10)


@pytest.mark.parametrize('deviation,expected', ((0.0, 0.0), (.125, 0.0), (-.0625, 0.0),
    (.25, .125), (-.125, -.0625)))
def test_hydraulic_governor_asymmetric_deadband(deviation: float, expected: float) -> None:
    """Deadband subtracts its directional threshold without an output jump.

    :param deviation: Absolute-speed deviation from nominal.
    :param expected: Independently calculated adjusted speed signal.
    """
    block: Block = build_ieeeg3_template(VarFactory(), 'hydro',
        HydraulicGovernorParameters(deadband_high=.125, deadband_low=-.0625)).block
    values: dict[int, float] = initialized_values(block)
    values[block.in_vars[0].uid] = 1+deviation
    equation: Expr = block.algebraic_eqs[0]
    assert values[block.out_vars[2].uid]-equation.eval_uid(values) == pytest.approx(expected)


def test_hydraulic_governor_initial_inverse_power_response() -> None:
    """An instantaneous gate increase initially decreases mechanical power before the water column settles."""
    block: Block = build_ieeeg3_template(VarFactory(), 'hydro').block
    values: dict[int, float] = initialized_values(block)
    states: np.ndarray = np.asarray([.6 if var.name == 'GatePu_hydro' else values[var.uid] for var in block.state_vars])
    derivative, output = evaluate_controller(block, values, states, 1)
    assert output == pytest.approx(.3)
    assert derivative[3] == pytest.approx(.2)


@pytest.mark.parametrize('opening', (False, True))
def test_hydraulic_pilot_rate_stop_recovers(opening: bool) -> None:
    """Pilot velocity cannot increase outward at its travel-rate limit and can immediately recover inward.

    :param opening: Select upper opening rather than lower closing rate.
    """
    block: Block = build_ieeeg3_template(VarFactory(), 'hydro').block
    values: dict[int, float] = initialized_values(block)
    states: np.ndarray = np.asarray([(.1 if opening else -.1) if var.name == 'PilotVelocityPu_hydro'
        else values[var.uid] for var in block.state_vars])
    derivative, output = evaluate_controller(block, values, states, 0 if opening else 2)
    assert derivative[1] == 0
    derivative, output = evaluate_controller(block, values, states, 2 if opening else 0)
    assert derivative[1] < 0 if opening else derivative[1] > 0


@pytest.mark.parametrize('upper', (False, True))
def test_hydraulic_gate_stop_recovers(upper: bool) -> None:
    """Position stops remain separate from pilot velocity limits and release inward.

    :param upper: Select upper opening rather than lower closing stop.
    """
    block: Block = build_ieeeg3_template(VarFactory(), 'hydro').block
    values: dict[int, float] = initialized_values(block)
    states: np.ndarray = np.asarray([values[var.uid] for var in block.state_vars])
    states[2] = 1.2 if upper else 0
    states[1] = .1 if upper else -.1
    derivative, output = evaluate_controller(block, values, states, 1)
    assert derivative[2] == 0
    states[1] *= -1
    derivative, output = evaluate_controller(block, values, states, 1)
    assert derivative[2] == states[1]
