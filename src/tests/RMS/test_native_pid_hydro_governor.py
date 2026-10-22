# SPDX-License-Identifier: MPL-2.0
"""Independent PID hydraulic transfer, curve inversion, raw damping and gate motion checks."""
from __future__ import annotations

import numpy as np
import pytest
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.international_standards.governors.pidgov import HydroDroopFeedback, PidHydroGovernorParameters, build_pidgov_template
from VeraGridEngine.Templates.Rms.genrou_exc_gov_rms_template import set_rms_model_parameter
from VeraGridEngine.Utils.Symbolic.block import Block
from tests.RMS.test_native_turbine_governors import initialized_values, evaluate_controller, linearized_response


@pytest.mark.parametrize('feedback',tuple(HydroDroopFeedback))
@pytest.mark.parametrize('detector',(0.,.02))
@pytest.mark.parametrize('frequency',(.02,.2,2.))
def test_pid_hydro_independent_closed_loop(feedback: HydroDroopFeedback, detector: float, frequency: float) -> None:
    """Droop selection and both controller filters appear in the independently derived small-signal response.

    :param feedback: Electrical power held externally or actual internal gate feedback.
    :param detector: Droop-error lag, including exact algebraic sensing.
    :param frequency: Perturbation frequency in hertz.
    """
    block: Block = build_pidgov_template(VarFactory(),'pid',PidHydroGovernorParameters(feedback=feedback,detector_time=detector)).block
    values: dict[int,float] = initialized_values(block)
    assert len(block.state_vars) == (6 if detector == 0 else 7)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs],0.,atol=1e-12)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.algebraic_eqs],0.,atol=1e-12)
    s: complex = 2j*np.pi*frequency
    controller: complex = (2.+1./s+.1*s)/((1.+.1*s)**2*(1.+.2*s))
    feedback_gain: complex = .05/(1.+detector*s) if feedback == HydroDroopFeedback.GATE_POSITION else 0.
    water: complex = (1.-s)/(1.+.5*s)
    slope: float = (.65-.3)/(.7-.4)
    expected: complex = -slope*water*controller/(1.+controller*feedback_gain)-.5
    assert linearized_response(block,values,1.,frequency) == pytest.approx(expected,rel=3e-7,abs=1e-8)


@pytest.mark.parametrize('power',(.1,.3,.5,.65,.9))
def test_pid_hydro_exact_curve_inverse_initialization(power: float) -> None:
    """The declared four-point turbine characteristic and monotone inverse balance at all three segments and joins.

    :param power: Initial mechanical power on the turbine base.
    """
    vf: VarFactory = VarFactory()
    block: Block = build_pidgov_template(vf,'pid').block
    set_rms_model_parameter(block,'Pm0Pu_pid',power,vf)
    values: dict[int,float] = initialized_values(block)
    expected_gate: float = float(np.interp(power,(0.,.3,.65,1.),(.08,.4,.7,1.)))
    assert values[block.out_vars[1].uid] == pytest.approx(expected_gate)
    assert values[block.out_vars[0].uid] == pytest.approx(power)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs],0.,atol=1e-12)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.algebraic_eqs],0.,atol=1e-12)


@pytest.mark.parametrize('speed',(.998,1.,1.001))
def test_pid_hydro_damping_remains_live_inside_control_deadband(speed: float) -> None:
    """Deadband suppresses speed control while raw-speed mechanical damping continues responding.

    :param speed: Absolute shaft speed inside the asymmetric control deadband.
    """
    block: Block = build_pidgov_template(VarFactory(),'pid',PidHydroGovernorParameters(deadband_low=-.003,deadband_high=.002)).block
    values: dict[int,float] = initialized_values(block)
    states: np.ndarray = np.asarray([values[var.uid] for var in block.state_vars])
    derivative, output = evaluate_controller(block,values,states,speed)
    np.testing.assert_allclose(derivative,0.,atol=1e-12)
    assert output == pytest.approx(.5-.5*(speed-1.))


def test_pid_hydro_signed_velocity_and_gate_stops() -> None:
    """Opening and closing velocities are distinct and gate travel limits permit inward recovery."""
    block: Block = build_pidgov_template(VarFactory(),'pid').block
    values: dict[int,float] = initialized_values(block)
    states: np.ndarray = np.asarray([values[var.uid] for var in block.state_vars])
    regulator_index: int = next(index for index,var in enumerate(block.state_vars) if var.name == 'SecondRegulatorPu_pid')
    gate_index: int = next(index for index,var in enumerate(block.state_vars) if var.name == 'GatePu_pid')
    states[regulator_index] = 2.
    derivative, output = evaluate_controller(block,values,states,1.)
    assert derivative[gate_index] == pytest.approx(.2)
    states[gate_index] = 1.
    derivative, output = evaluate_controller(block,values,states,1.)
    assert derivative[gate_index] == 0.
    states[regulator_index] = -2.
    derivative, output = evaluate_controller(block,values,states,1.)
    assert derivative[gate_index] == pytest.approx(-.15)


def test_pid_hydro_rejects_nonmonotone_curve() -> None:
    """An ambiguous static-characteristic inverse must not initialize a plausible but incorrect gate."""
    with pytest.raises(ValueError,match='strictly ordered'):
        build_pidgov_template(VarFactory(),parameters=PidHydroGovernorParameters(p1=.7,p2=.65))
