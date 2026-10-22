# SPDX-License-Identifier: MPL-2.0
"""Independent biased-regulator response, frozen bias and error-clipping placement."""
from __future__ import annotations

import numpy as np
import pytest
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.dc_exciter import DcExciterParameters
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.ieet1b import RotatingRateFeedbackSignal, build_ieet1b_template
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from tests.RMS.test_native_turbine_governors import initialized_values, evaluate_controller, linearized_response


@pytest.mark.parametrize('feedback',tuple(RotatingRateFeedbackSignal))
def test_biased_rotating_independent_transfer(feedback: RotatingRateFeedbackSignal) -> None:
    """Each selected physical feedback point retains its independent two-amplifier/field transfer.

    :param feedback: Second-regulator or field-voltage feedback.
    """
    block: Block = build_ieet1b_template(VarFactory(),'biased',DcExciterParameters(
        tr=.03,ka=4.,ta=.07,ke=1.4,te=.7,kf=.06,tf=.8,se1=0.,se2=0.),second_time=.09,feedback_signal=feedback).block
    values: dict[int,float] = initialized_values(block)
    assert len(block.state_vars) == 5
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs],0.,atol=1e-12)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.algebraic_eqs],0.,atol=1e-12)
    for frequency in (.02,.4,2.):
        s: complex = 2j*np.pi*frequency
        amplifier: complex = 4./((1.+.07*s)*(1.+.09*s))
        field: complex = 1./(1.4+.7*s)
        rate: complex = .06*s/(1.+.8*s)
        loop: complex = amplifier*rate*(field if feedback == RotatingRateFeedbackSignal.FIELD_VOLTAGE else 1.)
        expected: complex = -amplifier*field/((1.+.03*s)*(1.+loop))
        assert linearized_response(block,values,1.,frequency) == pytest.approx(expected,rel=3e-7,abs=1e-8)


def test_biased_rotating_auxiliary_bypasses_error_clip() -> None:
    """Supplementary voltage follows error clipping while the field-balance bias stays frozen."""
    block: Block = build_ieet1b_template(VarFactory(),'biased',DcExciterParameters(
        tr=0.,ka=4.,ta=0.,ke=1.4,te=.7,kf=0.,vrmax=100.,se1=0.,se2=0.),second_time=0.,
        error_max=.5,error_min=-.5,feedback_signal=RotatingRateFeedbackSignal.FIELD_VOLTAGE).block
    values: dict[int,float] = initialized_values(block)
    values[block.in_vars[2].uid] = 2.
    states: np.ndarray = np.asarray([values[variable.uid] for variable in block.state_vars])
    field_index: int = next(index for index,variable in enumerate(block.state_vars) if variable.name == 'EfdPu_biased')
    derivative: np.ndarray
    output: float
    derivative,output = evaluate_controller(block,values,states,1.)
    assert derivative[field_index] == pytest.approx(8./.7)
    bias: Var = next(variable for variable in block.event_dict if variable.name == 'BiasPu_biased')
    assert values[bias.uid] == pytest.approx(1.4/4.)
    states[field_index] = 2.
    derivative,output = evaluate_controller(block,values,states,1.)
    assert derivative[field_index] == pytest.approx((9.4-2.8)/.7)
    assert values[bias.uid] == pytest.approx(1.4/4.)


def test_biased_rotating_current_compensation_precedes_sensor() -> None:
    """Current-magnitude compensation enters before transducer dynamics on its declared machine base."""
    block: Block = build_ieet1b_template(VarFactory(),'biased',DcExciterParameters(tr=.05),compensation=.2).block
    values: dict[int,float] = initialized_values(block)
    values[block.in_vars[5].uid] = 1.
    states: np.ndarray = np.asarray([values[variable.uid] for variable in block.state_vars])
    sensor_index: int = next(index for index,variable in enumerate(block.state_vars) if variable.name == 'MeasuredPu_biased')
    derivative: np.ndarray
    output: float
    derivative,output = evaluate_controller(block,values,states,1.)
    assert derivative[sensor_index] == pytest.approx(4.)
