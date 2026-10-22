# SPDX-License-Identifier: MPL-2.0
"""Independent rational transfer products, steady bias and distinct integral limiting."""
from __future__ import annotations

import numpy as np
import pytest
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.control_realization import ControlRealization
from VeraGridEngine.Templates.Rms.rational_controller import RationalStageLimiting, RationalStageParameters, build_rational_stage
from VeraGridEngine.Templates.Rms.international_standards.power_system_stabilizers.ivost import build_ivost_template
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
from tests.RMS.test_native_turbine_governors import initialized_values, linearized_response, evaluate_controller


@pytest.mark.parametrize('washout,integral_stage,integral_lead',((True,0,0.),(False,0,0.),(True,2,0.),(True,2,.1),(True,3,0.)))
@pytest.mark.parametrize('gain',(-2.,2.))
def test_rational_power_stabilizer_independent_transfer(washout: bool, integral_stage: int, integral_lead: float, gain: float) -> None:
    """Normalized lead-lags, washout and balanced integrators retain their complete analytic transfer.

    :param washout: Zero or positive first numerator constant.
    :param integral_stage: Optional balanced second/third integrating denominator.
    :param integral_lead: Pure integral or PI numerator when the second stage integrates.
    :param gain: Signed first-stage gain.
    """
    first: RationalStageParameters = RationalStageParameters(gain,0. if washout else 1.,1.,1.,2.,10.,-10.)
    second: RationalStageParameters = RationalStageParameters(3.,1.5,0. if integral_stage == 2 else 2.,
        integral_lead if integral_stage == 2 else .1,.4,10.,-10.)
    third: RationalStageParameters = RationalStageParameters(.5,1.,0. if integral_stage == 3 else 1.,
        0. if integral_stage == 3 else .05,.2,10.,-10.)
    block: Block = build_ivost_template(VarFactory(),'rational',(first,second,third)).block
    values: dict[int,float] = initialized_values(block)
    assert len(block.state_vars) == 3
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs],0.,atol=1e-12)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.algebraic_eqs],0.,atol=1e-12)
    for frequency in (.02,.4,2.):
        s: complex = 2j*np.pi*frequency
        expected: complex = 1.+0j
        for stage in (first,second,third):
            expected *= stage.gain*(stage.numerator+stage.lead*s)/(stage.denominator+stage.lag*s)
        assert linearized_response(block,values,.5,frequency) == pytest.approx(expected,rel=3e-7,abs=1e-7)


@pytest.mark.parametrize('limiting',(RationalStageLimiting.OUTPUT_TRACKING,RationalStageLimiting.OUTPUT_ONLY))
def test_rational_integral_tracking_versus_external_clip(limiting: RationalStageLimiting) -> None:
    """The final external limiter does not silently gain the preceding stages' integral stops.

    :param limiting: Explicit physical limiter realization.
    """
    c: ControlRealization = ControlRealization(VarFactory(),'integral')
    signal: Var = c.input('InputPu',Const(0.))
    output: Var
    initial: Expr
    zero: bool
    output,initial,zero = build_rational_stage(c,1,signal,Const(0.),True,
        RationalStageParameters(1.,1.,0.,0.,1.,.1,-.1),limiting)
    block: Block = c.finish((output,),'Integral stage limiting').block
    values: dict[int,float] = initialized_values(block)
    derivative: np.ndarray
    result: float
    derivative,result = evaluate_controller(block,values,np.array([.1]),1.)
    assert result == .1
    if limiting == RationalStageLimiting.OUTPUT_TRACKING:
        assert derivative[0] == 0.
    else:
        assert derivative[0] == 1.


def test_rational_stabilizer_preserves_nonzero_dc_bias() -> None:
    """Positive DC gains propagate actual power rather than inventing an unmodeled subtraction."""
    stages: tuple[RationalStageParameters,RationalStageParameters,RationalStageParameters] = (
        RationalStageParameters(gain=2.,maximum=10.,minimum=-10.),
        RationalStageParameters(gain=3.,maximum=10.,minimum=-10.),
        RationalStageParameters(gain=.5,maximum=10.,minimum=-10.))
    block: Block = build_ivost_template(VarFactory(),'rational',stages).block
    values: dict[int,float] = initialized_values(block)
    assert values[block.out_vars[0].uid] == pytest.approx(1.5)


def test_rational_stabilizer_rejects_unbalanced_integrator() -> None:
    """Nonzero electrical-power input cannot be assigned a fictitious steady integral state."""
    with pytest.raises(ValueError,match='guaranteed zero steady input'):
        build_ivost_template(VarFactory(),'unbalanced',(
            RationalStageParameters(denominator=0.),RationalStageParameters(),RationalStageParameters()))


def test_rational_stabilizer_exact_constant_stage() -> None:
    """A canceled numerator/denominator origin becomes a static gain without a hidden memory."""
    stages: tuple[RationalStageParameters,RationalStageParameters,RationalStageParameters] = (
        RationalStageParameters(2.,0.,0.,.1,.2,10.,-10.),
        RationalStageParameters(maximum=10.,minimum=-10.),RationalStageParameters(maximum=10.,minimum=-10.))
    block: Block = build_ivost_template(VarFactory(),'rational',stages).block
    values: dict[int,float] = initialized_values(block)
    assert len(block.state_vars) == 2
    assert values[block.out_vars[0].uid] == pytest.approx(.5)
