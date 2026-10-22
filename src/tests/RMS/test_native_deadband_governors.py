# SPDX-License-Identifier: MPL-2.0
"""Physical deadband, damping, total PI limiting and nonlinear hydraulic response checks."""
from __future__ import annotations

import numpy as np
import pytest
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.international_standards.governors.gast import GasGovernorParameters
from VeraGridEngine.Templates.Rms.international_standards.governors.gastd import build_gastd_template
from VeraGridEngine.Templates.Rms.international_standards.governors.ieesgo import SteamGovernorParameters
from VeraGridEngine.Templates.Rms.international_standards.governors.ieesgod import build_ieesgod_template
from VeraGridEngine.Templates.Rms.international_standards.governors.hygov import NonlinearHydroGovernorParameters, build_hygov_template
from VeraGridEngine.Templates.Rms.international_standards.governors.hygovd import build_hygovd_template
from VeraGridEngine.Templates.Rms.international_standards.governors.tgov1d import build_tgov1d_template
from VeraGridEngine.Templates.Rms.genrou_exc_gov_rms_template import Tgov1RmsParameters
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import InternationalStandardModel
from tests.RMS.test_native_turbine_governors import initialized_values, evaluate_controller, linearized_response


def deadband_governor(model: InternationalStandardModel, enabled: bool) -> Block:
    """Build physical settings that distinguish controlled speed from raw mechanical damping.

    :param model: Native deadband family member.
    :param enabled: Apply asymmetric thresholds rather than exact structural bypass.
    :return: Native physical graph, without source-format metadata.
    """
    low: float = -.003 if enabled else 0.
    high: float = .002 if enabled else 0.
    vf: VarFactory = VarFactory()
    if model == InternationalStandardModel.GASTD:
        return build_gastd_template(vf,'test',GasGovernorParameters(damping=2.,deadband_low=low,deadband_high=high)).block
    elif model == InternationalStandardModel.IEESGOD:
        return build_ieesgod_template(vf,'test',SteamGovernorParameters(deadband_low=low,deadband_high=high)).block
    elif model == InternationalStandardModel.TGOV1D:
        return build_tgov1d_template(vf,'test',Tgov1RmsParameters(1.,.05,1.2,0.,.1,.2,10.,2.),low,high).block
    else:
        assert model == InternationalStandardModel.HYGOVD
        return build_hygovd_template(vf,'test',NonlinearHydroGovernorParameters(
            damping=2.,deadband_low=low,deadband_high=high)).block


@pytest.mark.parametrize('model',(InternationalStandardModel.GASTD,InternationalStandardModel.IEESGOD,
    InternationalStandardModel.TGOV1D,InternationalStandardModel.HYGOVD))
@pytest.mark.parametrize('speed',(.998,1.,1.001))
def test_deadband_does_not_disable_mechanical_damping(model: InternationalStandardModel, speed: float) -> None:
    """Control memories remain at equilibrium inside the band while raw-speed mechanical damping remains live.

    :param model: Native physical governor family.
    :param speed: Shaft speed strictly inside its asymmetric control deadband.
    """
    block: Block = deadband_governor(model,True)
    values: dict[int,float] = initialized_values(block)
    states: np.ndarray = np.asarray([values[var.uid] for var in block.state_vars])
    derivative, output = evaluate_controller(block,values,states,speed)
    np.testing.assert_allclose(derivative,0.,atol=1e-12)
    damping: float = 0. if model == InternationalStandardModel.IEESGOD else (2.*.58 if model == InternationalStandardModel.HYGOVD else 2.)
    assert output == pytest.approx(.5-damping*(speed-1.))


@pytest.mark.parametrize('frequency',(.02,.2,2.))
@pytest.mark.parametrize('model',(InternationalStandardModel.GASTD,InternationalStandardModel.IEESGOD,InternationalStandardModel.TGOV1D))
def test_deadband_families_exact_zero_band_response(model: InternationalStandardModel, frequency: float) -> None:
    """Structural zero deadband retains the independently specified speed-to-power transfer, including raw damping.

    :param model: Gas or steam family member.
    :param frequency: Sinusoidal perturbation frequency in hertz.
    """
    block: Block = deadband_governor(model,False)
    values: dict[int,float] = initialized_values(block)
    s: complex = 2j*np.pi*frequency
    expected: complex
    if model == InternationalStandardModel.GASTD:
        expected = -20./((1.+.1*s)*(1.+.4*s))-2.
    elif model == InternationalStandardModel.TGOV1D:
        expected = -20.*(1.+.2*s)/((1.+.1*s)*(1.+10.*s))-2.
    else:
        turbine: complex = ((1.-.6)+.6*((1.-.5)+.5/(1.+.5*s))/(1.+5.*s))/(1.+.3*s)
        expected = -20.*turbine/((1.+.1*s)*(1.+.2*s))
    assert linearized_response(block,values,1.,frequency) == pytest.approx(expected,rel=1e-7,abs=1e-8)


@pytest.mark.parametrize('frequency',(.01,.1,.7,3.))
@pytest.mark.parametrize('gain,no_load,water',((1.,.08,1.),(1.3,.09,2.)))
def test_nonlinear_hydro_independent_closed_loop(frequency: float, gain: float, no_load: float, water: float) -> None:
    """The PI/servo/droop loop closes through actual gate and the nonlinear column has the correct operating-point inverse response.

    :param frequency: Perturbation frequency in hertz.
    :param gain: Hydraulic power gain.
    :param no_load: No-load turbine flow.
    :param water: Rigid-column acceleration time.
    """
    block: Block = build_hygov_template(VarFactory(),'hydro',NonlinearHydroGovernorParameters(
        gain=gain,no_load_flow=no_load,water_time=water,damping=.7)).block
    values: dict[int,float] = initialized_values(block)
    gate0: float = .5/gain+no_load
    s: complex = 2j*np.pi*frequency
    loop: complex = (1.+5.*s)/(.3*5.*s*(1.+.05*s)*(1.+.5*s))
    gate_response: complex = -loop/(1.+.05*loop)
    hydraulic_weight: float = 2.*(gate0-no_load)/gate0
    column: complex = gain*((1.+hydraulic_weight)/(1.+.5*gate0*water*s)-hydraulic_weight)
    expected: complex = gate_response*column-.7*gate0
    assert linearized_response(block,values,1.,frequency) == pytest.approx(expected,rel=2e-6,abs=1e-8)


@pytest.mark.parametrize('upper',(False,True))
def test_hydro_total_pi_rate_and_position_limits(upper: bool) -> None:
    """Desired gate limits apply to the full PI output and release inward at exact position boundaries.

    :param upper: Upper rather than lower desired-gate travel stop.
    """
    block: Block = build_hygov_template(VarFactory(),'hydro').block
    values: dict[int,float] = initialized_values(block)
    states: np.ndarray = np.asarray([values[var.uid] for var in block.state_vars])
    states[1] = 1. if upper else 0.
    derivative, output = evaluate_controller(block,values,states,.9 if upper else 1.1)
    assert derivative[1] == pytest.approx(0.)
    derivative, output = evaluate_controller(block,values,states,1.1 if upper else .9)
    assert derivative[1] == pytest.approx(-.2 if upper else .2)


def test_hydro_head_accelerates_water_in_the_physical_direction() -> None:
    """Flow above the equilibrium gate raises head and decelerates the rigid column."""
    block: Block = build_hygov_template(VarFactory(),'hydro').block
    values: dict[int,float] = initialized_values(block)
    states: np.ndarray = np.asarray([values[var.uid] for var in block.state_vars])
    states[3] *= 1.5
    derivative, output = evaluate_controller(block,values,states,1.)
    assert derivative[3] == pytest.approx(1.-1.5**2)


@pytest.mark.parametrize('model',(InternationalStandardModel.GASTD,InternationalStandardModel.IEESGOD,
    InternationalStandardModel.HYGOVD,InternationalStandardModel.TGOV1D))
@pytest.mark.parametrize('speed',(.996,1.003))
def test_asymmetric_pickup_changes_controller_motion(model: InternationalStandardModel, speed: float) -> None:
    """Excess speed beyond either unequal threshold produces directional governor motion.

    :param model: Native family member.
    :param speed: Shaft speed outside the lower or upper pickup threshold.
    """
    block: Block = deadband_governor(model,True)
    values: dict[int,float] = initialized_values(block)
    states: np.ndarray = np.asarray([values[var.uid] for var in block.state_vars])
    derivative, output = evaluate_controller(block,values,states,speed)
    if model == InternationalStandardModel.IEESGOD:
        assert derivative[0] > 0 if speed > 1. else derivative[0] < 0
    else:
        assert derivative[0] < 0 if speed > 1. else derivative[0] > 0
