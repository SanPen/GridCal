# SPDX-License-Identifier: MPL-2.0
"""Independent static-exciter transfer and selected maximum-limiter placement."""
from __future__ import annotations

import numpy as np
import pytest
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.esst1a import (
    TerminalFedExciterParameters, StaticMinimumExcitationLocation,
    StaticMaximumExcitationLocation, StaticStabilizerLocation,
)
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.st1c import build_st1c_template
from VeraGridEngine.Utils.Symbolic.block import Block
from tests.RMS.test_native_turbine_governors import initialized_values, linearized_response, evaluate_controller


@pytest.mark.parametrize('minimum',tuple(StaticMinimumExcitationLocation))
@pytest.mark.parametrize('stabilizer',tuple(StaticStabilizerLocation))
@pytest.mark.parametrize('maximum',tuple(StaticMaximumExcitationLocation))
def test_static_selected_maximum_transfer(minimum: StaticMinimumExcitationLocation, stabilizer: StaticStabilizerLocation, maximum: StaticMaximumExcitationLocation) -> None:
    """All inactive selected gates retain the dual-phase, amplifier and delivered-field feedback loop.

    :param minimum: Minimum insertion location.
    :param stabilizer: Supplementary summation location.
    :param maximum: Maximum insertion location.
    """
    block: Block = build_st1c_template(VarFactory(),'static',TerminalFedExciterParameters(
        tr=.03,tc=.1,tb=.2,tc1=.04,tb1=.08,ka=4.,ta=.07,kf=.06,tf=.8,
        minimum_location=minimum,stabilizer_location=stabilizer),maximum).block
    values: dict[int,float] = initialized_values(block)
    assert len(block.out_vars) == 5 and len(block.state_vars) == 5
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs],0.,atol=1e-12)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.algebraic_eqs],0.,atol=1e-12)
    if minimum != StaticMinimumExcitationLocation.ERROR_SUM:
        values[block.in_vars[3].uid] = -100.
    else:
        pass
    if maximum != StaticMaximumExcitationLocation.ERROR_SUM:
        values[block.in_vars[6].uid] = 100.
    else:
        pass
    for frequency in (.02,.4,2.):
        s: complex = 2j*np.pi*frequency
        forward: complex = 4.*(1.+.1*s)*(1.+.04*s)/((1.+.2*s)*(1.+.08*s)*(1.+.07*s))
        feedback: complex = .06*s/(1.+.8*s)
        expected: complex = -forward/((1.+.03*s)*(1.+forward*feedback))
        assert linearized_response(block,values,1.,frequency) == pytest.approx(expected,rel=3e-7,abs=1e-8)


@pytest.mark.parametrize('maximum,expected',((StaticMaximumExcitationLocation.ERROR_SUM,5.),(StaticMaximumExcitationLocation.INPUT_GATE,1.),(StaticMaximumExcitationLocation.OUTPUT_GATE,.1)))
def test_static_maximum_actual_placement(maximum: StaticMaximumExcitationLocation, expected: float) -> None:
    """Maximum input acts before clipping, before amplification or after amplification according to its physical selection.

    :param maximum: Selected physical insertion location.
    :param expected: Independent expected delivered field voltage.
    """
    block: Block = build_st1c_template(VarFactory(),'static',TerminalFedExciterParameters(
        tr=0.,tc=0.,tb=0.,tc1=0.,tb1=0.,ka=10.,ta=0.,kf=0.,kc=0.,vi_max=.5),maximum).block
    values: dict[int,float] = initialized_values(block)
    values[block.in_vars[1].uid] = 2.
    values[block.in_vars[6].uid] = .1
    states: np.ndarray = np.asarray([values[variable.uid] for variable in block.state_vars])
    derivative: np.ndarray
    output: float
    derivative,output = evaluate_controller(block,values,states,1.)
    assert output == pytest.approx(expected)


def test_static_maximum_additive_operating_point_bias() -> None:
    """A frozen nonzero additive OEL bias initializes both its open input and the matching reference."""
    from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var
    block: Block = build_st1c_template(VarFactory(),'static').block
    bias: Var = next(variable for variable in block.event_dict if variable.name == 'Oel0Pu_static')
    block.event_dict[bias] = Const(.05)
    values: dict[int,float] = initialized_values(block)
    assert values[block.in_vars[6].uid] == pytest.approx(.05)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs],0.,atol=1e-12)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.algebraic_eqs],0.,atol=1e-12)
