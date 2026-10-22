# SPDX-License-Identifier: MPL-2.0
"""Independent parallel PI transfer, separate memory stops and exact zero-time stages."""
from __future__ import annotations

import numpy as np
import pytest
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.budczt import LimitedPiExciterParameters, build_budczt_template
from VeraGridEngine.Utils.Symbolic.block import Block
from tests.RMS.test_native_turbine_governors import initialized_values, evaluate_controller, linearized_response


@pytest.mark.parametrize('instantaneous',(False,True))
@pytest.mark.parametrize('frequency',(.01,.1,1.,10.))
def test_limited_pi_exciter_independent_transfer(instantaneous: bool, frequency: float) -> None:
    """Parallel PI, actuator and exciter retain independent gains and time constants.

    :param instantaneous: Remove permitted sensing, actuator and exciter lag memories exactly.
    :param frequency: Perturbation frequency in hertz.
    """
    tr: float = 0. if instantaneous else .02
    ta: float = 0. if instantaneous else .1
    te: float = 0. if instantaneous else .4
    block: Block = build_budczt_template(VarFactory(),'pi',LimitedPiExciterParameters(tr=tr,ta=ta,te=te)).block
    values: dict[int,float] = initialized_values(block)
    assert len(block.state_vars) == (1 if instantaneous else 4)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs],0.,atol=1e-12)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.algebraic_eqs],0.,atol=1e-12)
    s: complex = 2j*np.pi*frequency
    expected: complex = -3.*(5.+1./s)/((1.+tr*s)*(1.+ta*s)*(1.+te*s))
    assert linearized_response(block,values,1.,frequency) == pytest.approx(expected,rel=2e-7,abs=1e-8)


def test_pi_total_output_clipping_does_not_stop_unsaturated_integral_memory() -> None:
    """Integral and total-PI limits are independent; only memory at its own stop rejects outward motion."""
    block: Block = build_budczt_template(VarFactory(),'pi',LimitedPiExciterParameters(
        tr=0.,kp=20.,regulator_max=1.)).block
    values: dict[int,float] = initialized_values(block)
    values[block.in_vars[1].uid] = 1.2
    states: np.ndarray = np.asarray([values[var.uid] for var in block.state_vars])
    derivative, output = evaluate_controller(block,values,states,1.)
    assert derivative[0] == pytest.approx(.2)
    assert derivative[1] == pytest.approx((2.-2./3.)/.1)
    states[0] = 1.
    derivative, output = evaluate_controller(block,values,states,1.)
    assert derivative[0] == 0.
    values[block.in_vars[1].uid] = .8
    derivative, output = evaluate_controller(block,values,states,1.)
    assert derivative[0] == pytest.approx(-.2)


def test_exciter_field_stop_is_independent_of_actuator_memory() -> None:
    """Exciter capability constrains delivered excitation without clipping the upstream actuator state."""
    block: Block = build_budczt_template(VarFactory(),'pi',LimitedPiExciterParameters(field_max=2.)).block
    values: dict[int,float] = initialized_values(block)
    states: np.ndarray = np.asarray([values[var.uid] for var in block.state_vars])
    states[-2] = 10.
    states[-1] = 2.
    derivative, output = evaluate_controller(block,values,states,1.)
    assert output == 2. and derivative[-1] == 0.
    assert derivative[-2] < 0.
    states[-2] = .1
    derivative, output = evaluate_controller(block,values,states,1.)
    assert derivative[-1] == pytest.approx((.15-2.)/.4)


@pytest.mark.parametrize('ka,ti,te',((0.,1.,.4),(2.,0.,.4),(2.,1.,-.1),(float('nan'),1.,.4)))
def test_limited_pi_invalid_dynamics_are_rejected(ka: float, ti: float, te: float) -> None:
    """Reject undefined gain/integration domains and nonfinite coefficients.

    :param ka: Actuator gain.
    :param ti: Integral time.
    :param te: Exciter time.
    """
    with pytest.raises(ValueError):
        build_budczt_template(VarFactory(),parameters=LimitedPiExciterParameters(ka=ka,ti=ti,te=te))
