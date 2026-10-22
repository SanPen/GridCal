# SPDX-License-Identifier: MPL-2.0
"""Independent terminal-fed exciter transfer, signal placement and current-dependent capability checks."""
from __future__ import annotations

import numpy as np
import pytest
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.esst1a import StaticMinimumExcitationLocation, StaticStabilizerLocation, TerminalFedExciterParameters, build_esst1a_template
from VeraGridEngine.Templates.Rms.genrou_exc_gov_rms_template import set_rms_model_parameter
from VeraGridEngine.Utils.Symbolic.block import Block
from tests.RMS.test_native_turbine_governors import initialized_values, evaluate_controller, linearized_response


@pytest.mark.parametrize('minimum',tuple(StaticMinimumExcitationLocation))
@pytest.mark.parametrize('stabilizer',tuple(StaticStabilizerLocation))
def test_terminal_fed_exciter_independent_transfer(minimum: StaticMinimumExcitationLocation, stabilizer: StaticStabilizerLocation) -> None:
    """Both phase stages and delivered-field washout appear in the independently closed voltage-regulation loop.

    :param minimum: Physical minimum-excitation insertion point.
    :param stabilizer: Physical supplementary-voltage insertion point.
    """
    block: Block = build_esst1a_template(VarFactory(),'static',TerminalFedExciterParameters(minimum_location=minimum,stabilizer_location=stabilizer)).block
    values: dict[int,float] = initialized_values(block)
    assert len(block.state_vars) == 5
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs],0.,atol=1e-12)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.algebraic_eqs],0.,atol=1e-12)
    values[block.in_vars[6].uid] = 100.
    if minimum != StaticMinimumExcitationLocation.ERROR_SUM:
        values[block.in_vars[3].uid] = -100.
    else:
        pass
    for frequency in (.02,.2,2.):
        s: complex = 2j*np.pi*frequency
        forward: complex = 20.*(1.+.05*s)*(1.+.03*s)/((1.+.2*s)*(1.+.1*s)*(1.+.05*s))
        feedback: complex = .05*s/(1.+s)
        expected: complex = -forward/((1.+.02*s)*(1.+forward*feedback))
        assert linearized_response(block,values,1.,frequency) == pytest.approx(expected,rel=3e-7,abs=1e-8)


@pytest.mark.parametrize('minimum,stabilizer,expected',(
    (StaticMinimumExcitationLocation.ERROR_SUM,StaticStabilizerLocation.ERROR_SUM,5.),
    (StaticMinimumExcitationLocation.ERROR_SUM,StaticStabilizerLocation.REGULATOR_OUTPUT,4.8),
    (StaticMinimumExcitationLocation.INPUT_GATE,StaticStabilizerLocation.ERROR_SUM,3.6),
    (StaticMinimumExcitationLocation.INPUT_GATE,StaticStabilizerLocation.REGULATOR_OUTPUT,3.8),
    (StaticMinimumExcitationLocation.OUTPUT_GATE,StaticStabilizerLocation.ERROR_SUM,1.8),
    (StaticMinimumExcitationLocation.OUTPUT_GATE,StaticStabilizerLocation.REGULATOR_OUTPUT,1.8)))
def test_terminal_fed_exciter_exact_auxiliary_locations(minimum: StaticMinimumExcitationLocation, stabilizer: StaticStabilizerLocation, expected: float) -> None:
    """All six topology selections place additive and takeover signals at their distinct physical locations.

    :param minimum: Physical UEL insertion selection.
    :param stabilizer: Physical stabilizer insertion selection.
    :param expected: Independently calculated static output for the selected summations/gates.
    """
    block: Block = build_esst1a_template(VarFactory(),'static',TerminalFedExciterParameters(
        tr=0.,tc=0.,tb=0.,tc1=0.,tb1=0.,ta=0.,ka=2.,kf=0.,kc=0.,klr=0.,
        vi_max=100.,vi_min=-100.,va_max=100.,va_min=-100.,vr_max=100.,vr_min=-100.,
        minimum_location=minimum,stabilizer_location=stabilizer)).block
    values: dict[int,float] = initialized_values(block)
    assert len(block.state_vars) == 1
    values[block.in_vars[2].uid] = .2
    values[block.in_vars[3].uid] = 1.8
    values[block.in_vars[6].uid] = 100.
    states: np.ndarray = np.asarray([values[var.uid] for var in block.state_vars])
    derivative, output = evaluate_controller(block,values,states,1.)
    assert output == pytest.approx(expected)


def test_terminal_fed_exciter_active_current_limiter_initialization() -> None:
    """Actual initial field current balances regulator forcing and its limiter remains live during disturbances."""
    vf: VarFactory = VarFactory()
    block: Block = build_esst1a_template(vf,'static').block
    set_rms_model_parameter(block,'Ifd0Pu_static',3.,vf)
    values: dict[int,float] = initialized_values(block)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs],0.,atol=1e-12)
    values[block.in_vars[5].uid] = 3.2
    values[block.in_vars[6].uid] = 100.
    states: np.ndarray = np.asarray([values[var.uid] for var in block.state_vars])
    derivative, output = evaluate_controller(block,values,states,1.)
    assert output == pytest.approx(.8)


def test_terminal_fed_exciter_crossed_capability_convention_is_explicit() -> None:
    """At terminal collapse the implemented commutation ceiling has priority; no inverted-bound arithmetic creates NaN."""
    block: Block = build_esst1a_template(VarFactory(),'static').block
    values: dict[int,float] = initialized_values(block)
    values[block.in_vars[4].uid] = 0.
    values[block.in_vars[6].uid] = 100.
    states: np.ndarray = np.asarray([values[var.uid] for var in block.state_vars])
    derivative, output = evaluate_controller(block,values,states,1.)
    assert np.all(np.isfinite(derivative))
    assert output == pytest.approx(-.1)
