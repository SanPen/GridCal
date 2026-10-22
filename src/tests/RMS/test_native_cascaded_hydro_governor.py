# SPDX-License-Identifier: MPL-2.0
"""Independent cascaded-PI hydraulic transfer, motion stops and inverse water response."""
from __future__ import annotations

import numpy as np
import pytest
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.international_standards.governors.hygov2 import CascadedHydroGovernorParameters, build_hygov2_template
from VeraGridEngine.Utils.Symbolic.block import Block
from tests.RMS.test_native_turbine_governors import initialized_values, evaluate_controller, linearized_response


@pytest.mark.parametrize('ki',(0.,.1))
@pytest.mark.parametrize('frequency',(.01,.1,1.,10.))
@pytest.mark.parametrize('droop',(0.,.05))
def test_cascaded_hydro_independent_closed_loop(ki: float, frequency: float, droop: float) -> None:
    """The speed PI, double-integrating governor/gate loop, transient droop and water zero retain distinct dynamics.

    :param ki: Integral speed gain, including structural bypass.
    :param frequency: Perturbation frequency in hertz.
    :param droop: Permanent droop, including isochronous operation.
    """
    block: Block = build_hygov2_template(VarFactory(),'hydro',CascadedHydroGovernorParameters(
        ki=ki,permanent_droop=droop,power_gain=1.3)).block
    values: dict[int,float] = initialized_values(block)
    assert len(block.state_vars) == (5 if ki == 0 else 6)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs],0.,atol=1e-12)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.algebraic_eqs],0.,atol=1e-12)
    s: complex = 2j*np.pi*frequency
    speed: complex = 1.+ki/s
    controller: complex = (1.+.1*s)*(1.+.05*s)/(s*s*(1.+.1*s))
    feedback: complex = droop+.3*5.*s/(1.+5.*s)
    water: complex = 1.3*(1.-s)/(1.+.5*s)
    expected: complex = -water*controller*speed/(1.+controller*feedback)
    assert linearized_response(block,values,1.,frequency) == pytest.approx(expected,rel=2e-7,abs=1e-8)


@pytest.mark.parametrize('speed',(.998,1.,1.001))
def test_cascaded_hydro_deadband_freezes_speed_control_inside_band(speed: float) -> None:
    """Neither proportional nor integral speed action leaks through the continuous asymmetric deadband.

    :param speed: Absolute shaft speed inside the configured control deadband.
    """
    block: Block = build_hygov2_template(VarFactory(),'hydro',CascadedHydroGovernorParameters(deadband_low=-.003,deadband_high=.002)).block
    values: dict[int,float] = initialized_values(block)
    states: np.ndarray = np.asarray([values[var.uid] for var in block.state_vars])
    derivative, output = evaluate_controller(block,values,states,speed)
    np.testing.assert_allclose(derivative,0.,atol=1e-12)
    assert output == pytest.approx(.5)


def test_cascaded_hydro_gate_rate_travel_and_upstream_windup() -> None:
    """Gate motion has independent rate/travel limits while the upstream governor PI retains its specified untracked memory."""
    block: Block = build_hygov2_template(VarFactory(),'hydro').block
    values: dict[int,float] = initialized_values(block)
    values[block.in_vars[1].uid] = .5
    states: np.ndarray = np.asarray([values[var.uid] for var in block.state_vars])
    velocity_index: int = next(index for index,var in enumerate(block.state_vars) if var.name == 'VelocityPuState_hydro')
    gate_index: int = next(index for index,var in enumerate(block.state_vars) if var.name == 'GatePu_hydro')
    governor_index: int = next(index for index,var in enumerate(block.state_vars) if var.name == 'GovernorIntegralPu_hydro')
    states[velocity_index] = 100.
    derivative, output = evaluate_controller(block,values,states,1.)
    assert derivative[gate_index] == pytest.approx(.2)
    states[gate_index] = 1.
    derivative, output = evaluate_controller(block,values,states,1.)
    assert derivative[gate_index] == 0.
    assert derivative[governor_index] > 0.
    states[velocity_index] = -100.
    derivative, output = evaluate_controller(block,values,states,1.)
    assert derivative[gate_index] == pytest.approx(-.2)


def test_cascaded_hydro_water_column_initial_inverse_response() -> None:
    """A sudden gate opening initially reduces mechanical power before penstock memory catches up."""
    block: Block = build_hygov2_template(VarFactory(),'hydro').block
    values: dict[int,float] = initialized_values(block)
    states: np.ndarray = np.asarray([values[var.uid] for var in block.state_vars])
    gate_index: int = next(index for index,var in enumerate(block.state_vars) if var.name == 'GatePu_hydro')
    water_index: int = next(index for index,var in enumerate(block.state_vars) if var.name == 'WaterPowerPuState_hydro')
    states[gate_index] = .6
    derivative, output = evaluate_controller(block,values,states,1.)
    assert output == pytest.approx(.3)
    assert derivative[water_index] == pytest.approx(.2)
    states[water_index] = .6
    derivative, output = evaluate_controller(block,values,states,1.)
    assert output == pytest.approx(.6)
