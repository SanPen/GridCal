# SPDX-License-Identifier: MPL-2.0
"""Independent static feedback transfer, limiter topology and auxiliary routing checks."""
from __future__ import annotations

import numpy as np
import pytest
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.bbsex1 import AuxiliaryVoltageLocation, FeedbackStaticExciterParameters, build_bbsex1_template
from VeraGridEngine.Utils.Symbolic.block import Block
from tests.RMS.test_native_turbine_governors import initialized_values, evaluate_controller, linearized_response


@pytest.mark.parametrize('location',tuple(AuxiliaryVoltageLocation))
@pytest.mark.parametrize('instantaneous',(False,True))
@pytest.mark.parametrize('frequency',(.01,.1,1.,10.))
def test_feedback_static_exciter_independent_transfer(location: AuxiliaryVoltageLocation, instantaneous: bool, frequency: float) -> None:
    """Bounded-output feedback realizes the specified regulator lead/lag with consistent initialization.

    :param location: Physical supplementary-signal insertion point.
    :param instantaneous: Use algebraic sensing and phase compensation.
    :param frequency: Perturbation frequency in hertz.
    """
    tr: float = 0. if instantaneous else .02
    t3: float = 0. if instantaneous else .05
    t4: float = 0. if instantaneous else .1
    block: Block = build_bbsex1_template(VarFactory(),'feedback',FeedbackStaticExciterParameters(
        tr=tr,t3=t3,t4=t4,auxiliary_location=location)).block
    values: dict[int,float] = initialized_values(block)
    assert len(block.state_vars) == (1 if instantaneous else 3)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs],0.,atol=1e-12)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.algebraic_eqs],0.,atol=1e-12)
    s: complex = 2j*np.pi*frequency
    expected: complex = -20.*(1.+.1*s)*(1.+t3*s)/((1.+.2*s)*(1.+t4*s)*(1.+tr*s))
    assert linearized_response(block,values,1.,frequency) == pytest.approx(expected,rel=2e-7,abs=1e-8)


@pytest.mark.parametrize('location',tuple(AuxiliaryVoltageLocation))
def test_static_auxiliary_routing_and_live_field_capability(location: AuxiliaryVoltageLocation) -> None:
    """Auxiliary injection acts at its specified summation and terminal voltage bounds only the final output.

    :param location: Supplementary voltage error or field voltage insertion point.
    """
    block: Block = build_bbsex1_template(VarFactory(),'feedback',FeedbackStaticExciterParameters(
        tr=0.,t3=0.,t4=0.,auxiliary_location=location)).block
    values: dict[int,float] = initialized_values(block)
    values[block.in_vars[2].uid] = .1
    states: np.ndarray = np.asarray([values[var.uid] for var in block.state_vars])
    derivative, output = evaluate_controller(block,values,states,1.)
    expected: float = 2. if location == AuxiliaryVoltageLocation.VOLTAGE_ERROR else 1.1
    assert output == pytest.approx(expected)
    # An output voltage collapse must not reset the bounded regulator's feedback.
    before: np.ndarray = derivative.copy()
    values[block.in_vars[4].uid] = 0.
    derivative, output = evaluate_controller(block,values,states,1.)
    assert output == 0.
    np.testing.assert_allclose(derivative,before,atol=1e-12)


def test_static_feedback_tracks_clipped_regulator_and_recovers() -> None:
    """The memory integrates bounded internal regulator voltage, independently of field-output clipping."""
    block: Block = build_bbsex1_template(VarFactory(),'feedback',FeedbackStaticExciterParameters(
        tr=0.,t3=0.,t4=0.,regulator_max=3.,field_max=2.)).block
    values: dict[int,float] = initialized_values(block)
    values[block.in_vars[1].uid] = 11.
    states: np.ndarray = np.asarray([1.])
    derivative, output = evaluate_controller(block,values,states,1.)
    assert derivative[0] == pytest.approx((3.-1.)/.1)
    assert output == 2.
    states[0] = 3.
    derivative, output = evaluate_controller(block,values,states,1.)
    assert derivative[0] == 0.
    values[block.in_vars[1].uid] = 0.
    derivative, output = evaluate_controller(block,values,states,1.)
    assert derivative[0] < 0.
    assert output < 2.


@pytest.mark.parametrize('location',tuple(AuxiliaryVoltageLocation))
def test_static_feedback_nonzero_auxiliary_initialization(location: AuxiliaryVoltageLocation) -> None:
    """A nonzero auxiliary operating point balances the correct error or field summation without double subtraction.

    :param location: Physical auxiliary insertion point.
    """
    from VeraGridEngine.Templates.Rms.genrou_exc_gov_rms_template import set_rms_model_parameter
    from VeraGridEngine.Utils.Symbolic.symbolic import Const
    vf: VarFactory = VarFactory()
    block: Block = build_bbsex1_template(vf,'feedback',FeedbackStaticExciterParameters(auxiliary_location=location)).block
    set_rms_model_parameter(block,'Aux0Pu_feedback',.3,vf)
    block.init_eqs[block.in_vars[2]] = Const(.2)
    block.init_eqs[block.in_vars[3]] = Const(.1)
    values: dict[int,float] = initialized_values(block)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs],0.,atol=1e-12)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.algebraic_eqs],0.,atol=1e-12)
    assert values[block.out_vars[0].uid] == pytest.approx(1.)
    assert values[block.out_vars[1].uid] == pytest.approx(1. if location == AuxiliaryVoltageLocation.VOLTAGE_ERROR else .7)


@pytest.mark.parametrize('t1,t2,t3,t4',((0.,.1,0.,0.),(.2,0.,0.,0.),(.2,.1,.1,0.),(.2,.1,0.,float('nan'))))
def test_static_feedback_invalid_dynamic_structure(t1: float, t2: float, t3: float, t4: float) -> None:
    """The feedback realization requires proper, finite dynamics rather than invented small time constants.

    :param t1: Effective regulator lag.
    :param t2: Feedback-memory time.
    :param t3: Input compensation lead.
    :param t4: Input compensation lag.
    """
    with pytest.raises(ValueError):
        build_bbsex1_template(VarFactory(),parameters=FeedbackStaticExciterParameters(t1=t1,t2=t2,t3=t3,t4=t4))
