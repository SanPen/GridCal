# SPDX-License-Identifier: MPL-2.0
"""Independent terminal-fed PID transfer, non-windup motion and supply collapse."""
from __future__ import annotations

import numpy as np
import pytest
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.dc_exciter import DcExciterParameters, RotatingLimiterLocation
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.dc4b import build_dc4b_template
from VeraGridEngine.Utils.Symbolic.block import Block
from tests.RMS.test_native_turbine_governors import initialized_values, evaluate_controller, linearized_response


@pytest.mark.parametrize('minimum',tuple(RotatingLimiterLocation))
@pytest.mark.parametrize('maximum',tuple(RotatingLimiterLocation))
@pytest.mark.parametrize('ki',(0.,1.))
def test_terminal_pid_independent_transfer(minimum: RotatingLimiterLocation, maximum: RotatingLimiterLocation, ki: float) -> None:
    """PID, regulator, field and washout equations reproduce the independently closed feedback loop.

    :param minimum: Minimum-excitation insertion.
    :param maximum: Maximum-excitation insertion.
    :param ki: Integral gain or exact proportional special case.
    """
    block: Block = build_dc4b_template(VarFactory(),'pid',DcExciterParameters(tr=.03,ta=.07,ka=3.,ke=1.4,te=.7,
        kf=.06,tf=.8,se1=0.,se2=0.),kp=4.,ki=ki,kd=.2,td=.12,minimum_location=minimum,maximum_location=maximum).block
    values: dict[int,float] = initialized_values(block)
    assert len(block.state_vars) == 5+int(ki>0)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs],0.,atol=1e-12)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.algebraic_eqs],0.,atol=1e-12)
    if minimum == RotatingLimiterLocation.TAKEOVER_GATE:
        values[block.in_vars[3].uid] = -100.
    else:
        pass
    if maximum == RotatingLimiterLocation.TAKEOVER_GATE:
        values[block.in_vars[5].uid] = 100.
    else:
        pass
    for frequency in (.02,.4,2.):
        s: complex = 2j*np.pi*frequency
        forward: complex = 3.*(4.+ki/s+.2*s/(1.+.12*s))/((1.+.07*s)*(1.4+.7*s))
        feedback: complex = .06*s/(1.+.8*s)
        expected: complex = -forward/((1.+.03*s)*(1.+forward*feedback))
        assert linearized_response(block,values,1.,frequency) == pytest.approx(expected,rel=3e-7,abs=1e-8)


def test_terminal_pid_integral_stop_recovers() -> None:
    """The total PID stop blocks outward integral motion and releases it under inward voltage error."""
    block: Block = build_dc4b_template(VarFactory(),'pid',DcExciterParameters(ka=2.,vrmax=3.,se1=0.,se2=0.),kp=1.,ki=4.,kd=0.).block
    values: dict[int,float] = initialized_values(block)
    integral_index: int = next(index for index,var in enumerate(block.state_vars) if var.name == 'IntegralPu_pid')
    states: np.ndarray = np.asarray([values[var.uid] for var in block.state_vars])
    states[integral_index] = 1.5
    values[block.in_vars[1].uid] = 2.
    derivative: np.ndarray
    output: float
    derivative, output = evaluate_controller(block,values,states,1.)
    assert derivative[integral_index] == 0.
    values[block.in_vars[1].uid] = .9
    derivative: np.ndarray
    output: float
    derivative, output = evaluate_controller(block,values,states,1.)
    assert derivative[integral_index] < 0.


@pytest.mark.parametrize('terminal',(0.,.2))
def test_terminal_pid_live_capability(terminal: float) -> None:
    """Supply changes immediately enforce actual amplifier capability with finite collapsed-supply equations.

    :param terminal: Actual terminal voltage after the event.
    """
    block: Block = build_dc4b_template(VarFactory(),'pid',DcExciterParameters(se1=0.,se2=0.),kd=0.).block
    values: dict[int,float] = initialized_values(block)
    values[block.in_vars[4].uid] = terminal
    states: np.ndarray = np.asarray([values[var.uid] for var in block.state_vars])
    regulator_index: int = next(index for index,var in enumerate(block.state_vars) if var.name == 'RegulatorPu_pid')
    field_index: int = next(index for index,var in enumerate(block.state_vars) if var.name == 'EfdPu_pid')
    states[regulator_index] = 5.
    derivative: np.ndarray
    output: float
    derivative, output = evaluate_controller(block,values,states,1.)
    assert derivative[field_index] == pytest.approx((5.*terminal-1.)/.5)
    assert np.all(np.isfinite(derivative)) and output == 1.


def test_terminal_pid_exact_zero_time_stages() -> None:
    """Disabled memories reduce algebraically while the remaining field state balances actual forcing."""
    block: Block = build_dc4b_template(VarFactory(),'pid',DcExciterParameters(
        tr=0.,ta=0.,kf=0.,tf=0.,se1=0.,se2=0.),kp=2.,ki=0.,kd=0.).block
    values: dict[int,float] = initialized_values(block)
    assert len(block.state_vars) == 1
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs],0.,atol=1e-12)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.algebraic_eqs],0.,atol=1e-12)
    values[block.in_vars[4].uid] = 0.
    derivative: np.ndarray
    output: float
    derivative: np.ndarray
    output: float
    derivative, output = evaluate_controller(block,values,np.asarray([0.]),1.)
    assert derivative[0] == 0. and output == 0.
    values[block.in_vars[4].uid] = 1.
    derivative: np.ndarray
    output: float
    derivative, output = evaluate_controller(block,values,np.asarray([0.]),1.)
    assert derivative[0] > 0.
