# SPDX-License-Identifier: MPL-2.0
"""Independent static output-feedback transfer, firing dynamics and moving capability."""
from __future__ import annotations

import numpy as np
import pytest
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.self_feedback_exciter import (
    ExcitationBridgeDynamics, ExcitationLimiterLocation, SelfFeedbackExciterParameters,
    build_self_feedback_exciter,
)
from VeraGridEngine.Utils.Symbolic.block import Block
from tests.RMS.test_native_turbine_governors import initialized_values, linearized_response, evaluate_controller


@pytest.mark.parametrize('bridge',tuple(ExcitationBridgeDynamics))
@pytest.mark.parametrize('minimum',tuple(ExcitationLimiterLocation))
@pytest.mark.parametrize('maximum',tuple(ExcitationLimiterLocation))
def test_self_feedback_independent_transfer(bridge: ExcitationBridgeDynamics, minimum: ExcitationLimiterLocation, maximum: ExcitationLimiterLocation) -> None:
    """Inactive gates retain the independently derived positive output-feedback and bridge dynamics.

    :param bridge: Instantaneous or firing-control bridge.
    :param minimum: Minimum limiter insertion.
    :param maximum: Maximum limiter insertion.
    """
    block: Block = build_self_feedback_exciter(VarFactory(),'feedback',bridge,SelfFeedbackExciterParameters(
        tr=.03,tg=.1,tf=.2,tc=.04,tb=.08,kpa=4.,kia=.8,tia=.5,ta=.07,
        minimum_location=minimum,maximum_location=maximum)).block
    values: dict[int,float] = initialized_values(block)
    assert len(block.state_vars) == (4 if bridge == ExcitationBridgeDynamics.INSTANTANEOUS else 5)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs],0.,atol=1e-12)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.algebraic_eqs],0.,atol=1e-12)
    if minimum != ExcitationLimiterLocation.REFERENCE_SUM:
        values[block.in_vars[3].uid] = -100.
    else:
        pass
    if maximum != ExcitationLimiterLocation.REFERENCE_SUM:
        values[block.in_vars[5].uid] = 100.
    else:
        pass
    for frequency in (.02,.4,2.):
        s: complex = 2j*np.pi*frequency
        sensor: complex = (1.+.1*s)/((1.+.03*s)*(1.+.2*s))
        phase: complex = (1.+.04*s)/(1.+.08*s)
        bridge_gain: complex = 1./(1.+.07*s) if bridge == ExcitationBridgeDynamics.FIRING_LAG else 1.+0j
        feedback: complex = .8/(1.+.5*s)
        expected: complex = -4.*sensor*phase*bridge_gain/(1.-feedback*bridge_gain)
        assert linearized_response(block,values,1.,frequency) == pytest.approx(expected,rel=3e-7,abs=1e-8)


@pytest.mark.parametrize('bridge',tuple(ExcitationBridgeDynamics))
def test_self_feedback_terminal_collapse(bridge: ExcitationBridgeDynamics) -> None:
    """Terminal collapse enforces zero delivered field with finite internal feedback derivatives.

    :param bridge: Explicit bridge dynamics.
    """
    block: Block = build_self_feedback_exciter(VarFactory(),'feedback',bridge).block
    values: dict[int,float] = initialized_values(block)
    values[block.in_vars[4].uid] = 0.
    states: np.ndarray = np.asarray([values[variable.uid] for variable in block.state_vars])
    derivative: np.ndarray
    output: float
    derivative,output = evaluate_controller(block,values,states,1.)
    assert output == 0. and np.all(np.isfinite(derivative))


@pytest.mark.parametrize('bridge',tuple(ExcitationBridgeDynamics))
def test_self_feedback_exact_zero_measurement_stages(bridge: ExcitationBridgeDynamics) -> None:
    """Zero sensing and phase pairs remove memories exactly while preserving field-feedback equilibrium.

    :param bridge: Explicit bridge dynamics.
    """
    block: Block = build_self_feedback_exciter(VarFactory(),'feedback',bridge,SelfFeedbackExciterParameters(
        tr=0.,tg=0.,tf=0.,tc=0.,tb=0.,kia=.8,kpa=4.)).block
    values: dict[int,float] = initialized_values(block)
    assert len(block.state_vars) == (1 if bridge == ExcitationBridgeDynamics.INSTANTANEOUS else 2)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs],0.,atol=1e-12)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.algebraic_eqs],0.,atol=1e-12)
