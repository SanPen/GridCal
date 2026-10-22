# SPDX-License-Identifier: MPL-2.0
"""Four-way limiter routing, field feedback placement and live current capability."""
from __future__ import annotations
import numpy as np
import pytest
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.compound_excitation_supply import CompoundSupplyParameters
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.st6c import CurrentLimitedFieldParameters, FieldRegulatorLimiterLocation, build_st6c_template
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from tests.RMS.test_native_turbine_governors import initialized_values, linearized_response, evaluate_controller


@pytest.mark.parametrize('minimum',tuple(FieldRegulatorLimiterLocation))
@pytest.mark.parametrize('maximum',tuple(FieldRegulatorLimiterLocation))
def test_current_limited_field_equilibrium(minimum: FieldRegulatorLimiterLocation, maximum: FieldRegulatorLimiterLocation) -> None:
    """All sixteen limiter combinations initialize five physical memories.

    :param minimum: Minimum signal insertion.
    :param maximum: Maximum signal insertion.
    """
    block: Block = build_st6c_template(VarFactory(),'field',CurrentLimitedFieldParameters(
        minimum_location=minimum,maximum_location=maximum)).block
    values: dict[int,float] = initialized_values(block)
    assert len(block.state_vars) == 5 and len(block.in_vars) == 10 and len(block.out_vars) == 5
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs],0.,atol=1e-12)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.algebraic_eqs],0.,atol=1e-12)


def test_current_limited_field_independent_transfer() -> None:
    """Feedback senses firing command before supply, yielding the independent closed-loop transfer."""
    block: Block = build_st6c_template(VarFactory(),'field',CurrentLimitedFieldParameters(
        supply=CompoundSupplyParameters(kp=2.))).block
    values: dict[int,float] = initialized_values(block)
    for frequency in (.01,.1,1.,10.):
        s: complex = 2j*np.pi*frequency
        pid: complex = 20.+10./s+.05*s/(1.+.05*s)
        inner: complex = 3.*(1.+.1*s)/((1.+.05*s)*(1.+.1*s)+.2)
        expected: complex = -2.*pid*inner/(1.+.02*s)
        assert linearized_response(block,values,1.,frequency) == pytest.approx(expected,rel=4e-7,abs=1e-8)


def test_current_limiter_caps_pid_and_recovers() -> None:
    """KCI scales ILR and the resulting moving upper capability stops outward integral motion."""
    block: Block = build_st6c_template(VarFactory(),'field',CurrentLimitedFieldParameters(kci=2.,ilr=1.,klr=3.,kda=0.)).block
    values: dict[int,float] = initialized_values(block)
    values[block.in_vars[7].uid] = 1.9
    values[block.in_vars[1].uid] = 1.1
    states: np.ndarray = np.asarray([values[variable.uid] for variable in block.state_vars])
    integral_index: int = next(index for index,variable in enumerate(block.state_vars) if variable.name == 'IntegralPu_field')
    block.out_vars[0] = next(variable for variable in block.algebraic_vars if variable.name == 'RegulatorPu_field')
    derivative: np.ndarray
    result: float
    derivative,result = evaluate_controller(block,values,states,1.)
    assert result == pytest.approx(.3) and derivative[integral_index] == 0.
    values[block.in_vars[1].uid] = .99
    derivative,result = evaluate_controller(block,values,states,1.)
    assert derivative[integral_index] < 0.


@pytest.mark.parametrize('minimum',tuple(FieldRegulatorLimiterLocation))
@pytest.mark.parametrize('maximum',tuple(FieldRegulatorLimiterLocation))
def test_current_limited_field_disturbed_routes(minimum: FieldRegulatorLimiterLocation, maximum: FieldRegulatorLimiterLocation) -> None:
    """Independent arithmetic distinguishes all input, post-gate and output limiter placements.

    :param minimum: Minimum signal insertion.
    :param maximum: Maximum signal insertion.
    """
    block: Block = build_st6c_template(VarFactory(),'field',CurrentLimitedFieldParameters(kda=0.,
        minimum_location=minimum,maximum_location=maximum)).block
    values: dict[int,float] = initialized_values(block)
    values[block.in_vars[1].uid] = 1.01
    values[block.in_vars[2].uid] = -.02
    values[block.in_vars[8].uid] = .03
    values[block.in_vars[9].uid] = -.005
    states: np.ndarray = np.asarray([values[variable.uid] for variable in block.state_vars])
    integral_index: int = next(index for index,variable in enumerate(block.state_vars) if variable.name == 'IntegralPu_field')
    firing_index: int = next(index for index,variable in enumerate(block.state_vars) if variable.name == 'FiringPu_field')
    error: float = .01+(.03 if minimum == FieldRegulatorLimiterLocation.ERROR_SUM else 0.)+(-.005 if maximum == FieldRegulatorLimiterLocation.ERROR_SUM else 0.)
    if minimum == FieldRegulatorLimiterLocation.ERROR_GATE:
        error = max(error,.03)
    else:
        pass
    if maximum == FieldRegulatorLimiterLocation.ERROR_GATE:
        error = min(error,-.005)
    else:
        pass
    error += -.02+(.03 if minimum == FieldRegulatorLimiterLocation.POST_GATE_SUM else 0.)+(-.005 if maximum == FieldRegulatorLimiterLocation.POST_GATE_SUM else 0.)
    regulator: float = min(5.,max(-5.,20.*error+states[integral_index]))
    demand: float = min(5.,max(-5.,3.*regulator-.2))
    if minimum == FieldRegulatorLimiterLocation.OUTPUT_GATE:
        demand = max(demand,.03)
    else:
        pass
    if maximum == FieldRegulatorLimiterLocation.OUTPUT_GATE:
        demand = min(demand,-.005)
    else:
        pass
    derivative: np.ndarray
    field: float
    derivative,field = evaluate_controller(block,values,states,1.)
    assert derivative[firing_index] == pytest.approx((demand-states[firing_index])/.05)
