# SPDX-License-Identifier: MPL-2.0
"""Backward load balance, independent rational transfer and power/torque separation."""
from __future__ import annotations

import numpy as np
import pytest
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.rational_controller import RationalStageParameters
from VeraGridEngine.Templates.Rms.international_standards.governors.ivogo import build_ivogo_template
from VeraGridEngine.Utils.Symbolic.block import Block
from tests.RMS.test_native_turbine_governors import initialized_values, linearized_response, evaluate_controller


@pytest.mark.parametrize('integral_stage',(0,1,2,3))
def test_rational_governor_independent_transfer_and_load_balance(integral_stage: int) -> None:
    """Each possible balancing integrator stores actual load without inventing steady speed error.

    :param integral_stage: No integrator, or first/second/third integrating stage.
    """
    stages: tuple[RationalStageParameters,RationalStageParameters,RationalStageParameters] = (
        RationalStageParameters(20.,1.,0. if integral_stage == 1 else 1.,.1,.2,10.,-10.),
        RationalStageParameters(2.,1.,0. if integral_stage == 2 else 1.,.1,.3,10.,-10.),
        RationalStageParameters(.5,1.,0. if integral_stage == 3 else 1.,.05,.1,10.,-10.))
    block: Block = build_ivogo_template(VarFactory(),'governor',stages).block
    values: dict[int,float] = initialized_values(block)
    assert len(block.state_vars) == 3
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs],0.,atol=1e-12)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.algebraic_eqs],0.,atol=1e-12)
    assert values[block.out_vars[0].uid] == .5
    assert values[block.in_vars[1].uid] == pytest.approx(1.025 if integral_stage == 0 else 1.)
    for frequency in (.02,.4,2.):
        s: complex = 2j*np.pi*frequency
        expected: complex = -1.+0j
        for stage in stages:
            expected *= stage.gain*(stage.numerator+stage.lead*s)/(stage.denominator+stage.lag*s)
        assert linearized_response(block,values,1.,frequency) == pytest.approx(expected,rel=3e-7,abs=1e-7)


def test_rational_governor_default_power_and_torque() -> None:
    """The torque-consuming host receives power divided by actual positive shaft speed."""
    block: Block = build_ivogo_template(VarFactory(),'governor').block
    values: dict[int,float] = initialized_values(block)
    states: np.ndarray = np.asarray([values[variable.uid] for variable in block.state_vars])
    block.out_vars[0],block.out_vars[1] = block.out_vars[1],block.out_vars[0]
    derivative: np.ndarray
    torque: float
    derivative,torque = evaluate_controller(block,values,states,1.1)
    assert torque == pytest.approx(.5/1.1)


def test_rational_governor_washout_before_load_integrator() -> None:
    """A preceding zero-DC washout is compatible with a later loaded integral memory."""
    stages: tuple[RationalStageParameters,RationalStageParameters,RationalStageParameters] = (
        RationalStageParameters(2.,0.,1.,1.,2.,10.,-10.),RationalStageParameters(maximum=10.,minimum=-10.),
        RationalStageParameters(1.,1.,0.,0.,1.,10.,-10.))
    block: Block = build_ivogo_template(VarFactory(),'governor',stages).block
    values: dict[int,float] = initialized_values(block)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs],0.,atol=1e-12)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.algebraic_eqs],0.,atol=1e-12)
    assert values[block.in_vars[1].uid] == 1.
    assert values[block.out_vars[0].uid] == .5


def test_rational_governor_disabled_integral_gain_holds_initial_load() -> None:
    """A zero input gain does not erase the initialized load of a free integral memory."""
    stages: tuple[RationalStageParameters,RationalStageParameters,RationalStageParameters] = (
        RationalStageParameters(),RationalStageParameters(0.,1.,0.,0.,1.),RationalStageParameters(lead=0.))
    block: Block = build_ivogo_template(VarFactory(),'governor',stages).block
    values: dict[int,float] = initialized_values(block)
    states: np.ndarray = np.asarray([values[variable.uid] for variable in block.state_vars])
    derivative: np.ndarray
    power: float
    derivative,power = evaluate_controller(block,values,states,1.03)
    assert power == .5


def test_rational_governor_rejects_final_unloaded_washout() -> None:
    """A final zero-DC filter cannot be seeded with fictitious nonzero steady turbine power."""
    with pytest.raises(ValueError,match='cannot sustain'):
        build_ivogo_template(VarFactory(),'invalid',(
            RationalStageParameters(),RationalStageParameters(),RationalStageParameters(numerator=0.)))
