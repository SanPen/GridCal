# SPDX-License-Identifier: MPL-2.0
"""Independent loop responses, fuel conversion, controller tracking and servo-limit evidence."""
from __future__ import annotations

import numpy as np
import pytest
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.international_standards.governors.ggov1 import (
    GovernorDroopFeedback, FuelFlowCharacteristic, TrackedGovernorParameters, build_ggov1_template)
from VeraGridEngine.Utils.Symbolic.block import Block
from tests.RMS.test_native_turbine_governors import initialized_values, evaluate_controller, linearized_response


@pytest.mark.parametrize('feedback', tuple(GovernorDroopFeedback))
@pytest.mark.parametrize('fuel', tuple(FuelFlowCharacteristic))
@pytest.mark.parametrize('frequency', (.03, .3, 2.))
@pytest.mark.parametrize('integral_gain', (0., 1.))
def test_fuel_governor_independent_response(feedback: GovernorDroopFeedback,
        fuel: FuelFlowCharacteristic, frequency: float, integral_gain: float) -> None:
    """Selected droop closes the intended loop and shaft-driven fuel adds its direct speed dependence.

    :param feedback: Electrical, valve, requested-stroke or isochronous feedback.
    :param fuel: Independent or shaft-driven fuel source.
    :param frequency: Perturbation frequency in hertz.
    :param integral_gain: Zero selects proportional/derivative-only regulation.
    """
    p: TrackedGovernorParameters = TrackedGovernorParameters(feedback=feedback, fuel_characteristic=fuel,
        droop=.03, governor_gains=(4., integral_gain, .15), error_limits=(-1.,1.),
        turbine_gain=1.2, no_load_fuel=.1, turbine_times=(.02,.4), damping=.2,
        load_gains=(0.,0.))
    block: Block = build_ggov1_template(VarFactory(), 'fuel', p).block
    values: dict[int,float] = initialized_values(block)
    s: complex = 2j*np.pi*frequency
    regulator: complex = (4.+.15*s/(1.+.1*s))*(1.+integral_gain/(4.*s))
    actuator: complex = 1./(1.+.2*s)
    feedback_path: complex = actuator if feedback == GovernorDroopFeedback.VALVE_STROKE else (
        1. if feedback == GovernorDroopFeedback.REQUESTED_STROKE else 0.)
    valve: complex = -regulator*actuator/(1.+.03*regulator*feedback_path)
    flow: complex = valve+(.5/1.2+.1 if fuel == FuelFlowCharacteristic.SHAFT_DRIVEN else 0.)
    expected: complex = 1.2*(1.+.02*s)/(1.+.4*s)*flow-.2
    assert linearized_response(block, values, 1., frequency) == pytest.approx(expected, rel=2e-6, abs=2e-8)


@pytest.mark.parametrize('feedback', tuple(GovernorDroopFeedback))
@pytest.mark.parametrize('zero_times', (False, True))
@pytest.mark.parametrize('load_enabled', (False, True))
def test_fuel_governor_equilibrium_and_structure(feedback: GovernorDroopFeedback,
        zero_times: bool, load_enabled: bool) -> None:
    """Tracked memories initialize without free-running inactive PI loops and zero-time stages disappear.

    :param feedback: Structural droop-measurement choice.
    :param zero_times: Exact measurement and turbine bypasses.
    :param load_enabled: Enable the continuous tracked fuel-load regulator.
    """
    block: Block = build_ggov1_template(VarFactory(), 'fuel', TrackedGovernorParameters(
        feedback=feedback, power_time=0 if zero_times else .1,
        turbine_times=(0.,0.) if zero_times else (0.,.5), load_time=3. if load_enabled or not zero_times else 0.,
        temperature_times=(0.,0.) if zero_times else (0.,1.),
        load_gains=(1.,1.) if load_enabled else (0.,0.))).block
    values: dict[int,float] = initialized_values(block)
    np.testing.assert_allclose([eq.eval_uid(values) for eq in block.state_eqs],0,atol=1e-12)
    np.testing.assert_allclose([eq.eval_uid(values) for eq in block.algebraic_eqs],0,atol=1e-12)
    assert values[block.out_vars[0].uid] == pytest.approx(.5)
    expected_states: int = (5 if load_enabled else 3) if zero_times else (8 if load_enabled else 7)
    assert len(block.state_vars) == expected_states
    assert len(block.algebraic_vars) == len(block.algebraic_eqs)


@pytest.mark.parametrize('upper', (False,True))
def test_fuel_valve_rate_stop_and_recovery(upper: bool) -> None:
    """Servo travel has separate velocity limits and directional position stops.

    :param upper: Upper rather than lower position stop.
    """
    block: Block = build_ggov1_template(VarFactory(), 'fuel', TrackedGovernorParameters(
        load_gains=(0.,0.), valve_rates=(-.03,.04))).block
    values: dict[int,float] = initialized_values(block)
    states: np.ndarray = np.asarray([values[var.uid] for var in block.state_vars])
    valve_index: int = block.state_vars.index(block.out_vars[1])
    states[valve_index] = 1. if upper else 0.
    values[block.in_vars[2].uid] = 2. if upper else -2.
    derivative, output = evaluate_controller(block,values,states,1.)
    assert derivative[valve_index] == pytest.approx(0.)
    values[block.in_vars[2].uid] = -2. if upper else 2.
    derivative, output = evaluate_controller(block,values,states,1.)
    assert derivative[valve_index] == pytest.approx(-.03 if upper else .04)


def test_inactive_governor_memory_tracks_load_takeover() -> None:
    """A limiting load controller pulls the inactive speed-regulator memory toward the selected command."""
    block: Block = build_ggov1_template(VarFactory(), 'fuel', TrackedGovernorParameters(
        governor_gains=(4.,2.,0.), load_reference=.5, load_gains=(2.,1.))).block
    values: dict[int,float] = initialized_values(block)
    states: np.ndarray = np.asarray([values[var.uid] for var in block.state_vars])
    memory_index: int = next(index for index,var in enumerate(block.state_vars)
        if var.name.startswith('GovernorIntegralPu_'))
    load_index: int = next(index for index,var in enumerate(block.state_vars) if var.name.startswith('LoadDemandPu_'))
    states[load_index] = 0.
    values[block.in_vars[2].uid] = 1.
    derivative, output = evaluate_controller(block,values,states,1.)
    # Load demand is clipped to zero, so tracking gives (Ki/Kp)*(0-.6).
    assert derivative[memory_index] == pytest.approx(-.3)


@pytest.mark.parametrize('feedback', tuple(GovernorDroopFeedback))
def test_supervisory_reset_uses_electrical_power(feedback: GovernorDroopFeedback) -> None:
    """The slow reset loop senses electrical output even when permanent droop uses another signal.

    :param feedback: Independent permanent-droop choice.
    """
    block: Block = build_ggov1_template(VarFactory(), 'fuel', TrackedGovernorParameters(
        feedback=feedback, reset_gain=.01, load_gains=(0.,0.))).block
    values: dict[int,float] = initialized_values(block)
    states: np.ndarray = np.asarray([values[var.uid] for var in block.state_vars])
    values[block.in_vars[3].uid] = .7
    derivative, output = evaluate_controller(block,values,states,1.)
    reset_index: int = next(index for index,var in enumerate(block.state_vars) if var.name.startswith('MwIntegralPu_'))
    assert derivative[reset_index] == pytest.approx(.002)


@pytest.mark.parametrize('setting', (
    TrackedGovernorParameters(governor_gains=(0.,1.,0.)),
    TrackedGovernorParameters(governor_gains=(1.,1.,1.),derivative_time=0),
    TrackedGovernorParameters(valve_limits=(0.,1.1)),
    TrackedGovernorParameters(load_gains=(1.,0.)),
    TrackedGovernorParameters(turbine_times=(.1,0.)),
    TrackedGovernorParameters(temperature_times=(.1,0.)),
))
def test_unreviewed_or_invalid_fuel_settings_are_rejected(setting: TrackedGovernorParameters) -> None:
    """Invalid physical coefficients cannot silently select a nearby realization.

    :param setting: Nonphysical or explicitly unreviewed structural settings.
    """
    with pytest.raises(ValueError):
        build_ggov1_template(VarFactory(), 'fuel', setting)


@pytest.mark.parametrize('opening', (False,True))
def test_load_output_slew_limits(opening: bool) -> None:
    """The total PI demand, including proportional measurement response, obeys independent slew bounds.

    :param opening: Increasing rather than decreasing fuel demand.
    """
    block: Block = build_ggov1_template(VarFactory(), 'fuel', TrackedGovernorParameters(
        load_time=.2, load_rates=(-.03,.04))).block
    values: dict[int,float] = initialized_values(block)
    states: np.ndarray = np.asarray([values[var.uid] for var in block.state_vars])
    measurement_index: int = next(index for index,var in enumerate(block.state_vars) if var.name.startswith('LoadMeasuredPu_'))
    demand_index: int = next(index for index,var in enumerate(block.state_vars) if var.name.startswith('LoadDemandPu_'))
    states[measurement_index] = 10. if opening else -10.
    derivative, output = evaluate_controller(block,values,states,1.)
    assert derivative[demand_index] == pytest.approx(.04 if opening else -.03)


@pytest.mark.parametrize('damping', (-1.5,-.3,.2))
@pytest.mark.parametrize('fuel', tuple(FuelFlowCharacteristic))
@pytest.mark.parametrize('frequency', (.03,.3,2.))
def test_active_fuel_load_controller_response(damping: float, fuel: FuelFlowCharacteristic,
                                             frequency: float) -> None:
    """Load takeover follows an independently closed PI/temperature/fuel loop with the correct speed sensitivity.

    :param damping: Negative fuel-capability exponent or positive output damping.
    :param fuel: Fuel source's shaft-speed dependence.
    :param frequency: Perturbation frequency in hertz.
    """
    block: Block = build_ggov1_template(VarFactory(), 'fuel', TrackedGovernorParameters(
        fuel_characteristic=fuel, damping=damping, load_gains=(2.,.7), load_reference=.5,
        load_time=.4, temperature_times=(.02,.2), turbine_gain=1.2,
        turbine_times=(.03,.5))).block
    values: dict[int,float] = initialized_values(block)
    # Move the speed regulator above the active load gate without changing the
    # selected fuel or its tracking equilibrium.
    values[block.in_vars[2].uid] += .1
    s: complex = 2j*np.pi*frequency
    regulator: complex = (2.+.7/s)*(1.+.02*s)/((1.+.2*s)*(1.+.4*s))
    servo: complex = 1./(1.+.2*s)
    fuel0: float = .5/1.2+.1
    shaft_gain: float = 1. if fuel == FuelFlowCharacteristic.SHAFT_DRIVEN else 0.
    measurement_gain: float = shaft_gain+(damping if damping < 0 else 0.)
    valve: complex = -servo*regulator*fuel0*measurement_gain/(1.+servo*regulator)
    expected: complex = 1.2*(1.+.03*s)/(1.+.5*s)*(valve+fuel0*shaft_gain)-(damping if damping > 0 else 0.)
    assert linearized_response(block,values,1.,frequency) == pytest.approx(expected,rel=2e-6,abs=2e-8)


@pytest.mark.parametrize('speed,expected', ((1.001,0.),(.998,0.),(1.0025,0.),(.9965,0.),
    (1.004,-.005),(.995,.005)))
def test_asymmetric_speed_and_combined_error_deadbands(speed: float, expected: float) -> None:
    """Asymmetric shaft deadband precedes the separate symmetric regulation-error deadband.

    :param speed: Absolute per-unit shaft speed.
    :param expected: Independent expected actuator velocity before rate clipping.
    """
    block: Block = build_ggov1_template(VarFactory(), 'fuel', TrackedGovernorParameters(
        feedback=GovernorDroopFeedback.ISOCHRONOUS, governor_gains=(1.,1.,0.),
        actuator_time=.2, speed_deadband=(-.002,.001), deadband=.002,
        load_gains=(0.,0.))).block
    values: dict[int,float] = initialized_values(block)
    states: np.ndarray = np.asarray([values[var.uid] for var in block.state_vars])
    derivative, output = evaluate_controller(block,values,states,speed)
    valve_index: int = block.state_vars.index(block.out_vars[1])
    assert derivative[valve_index] == pytest.approx(expected,abs=1e-12)
