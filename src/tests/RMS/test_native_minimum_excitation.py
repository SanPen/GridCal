# SPDX-License-Identifier: MPL-2.0
"""Physical capability geometry and rate-feedback checks for excitation limiters."""
from __future__ import annotations

import numpy as np
import pytest

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.international_standards import build_international_standard_template
from VeraGridEngine.Templates.Rms.international_standards.excitation_limiters.mnlex1 import build_mnlex1_template
from VeraGridEngine.Templates.Rms.international_standards.excitation_limiters.mnlex2 import build_mnlex2_template
from VeraGridEngine.Templates.Rms.international_standards.excitation_limiters.mnlex3 import build_mnlex3_template
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import InternationalStandardModel
from tests.RMS.test_native_turbine_governors import initialized_values, evaluate_controller


@pytest.mark.parametrize('model',(InternationalStandardModel.MNLEX1,InternationalStandardModel.MNLEX2,
                                 InternationalStandardModel.MNLEX3))
def test_limiter_nominal_equilibrium(model: InternationalStandardModel) -> None:
    """All three idle limiters initialize their actual two-state equations consistently."""
    block: Block = build_international_standard_template(model,VarFactory(),'underexcitation').block
    values: dict[int,float] = initialized_values(block)
    assert len(block.state_vars) == 2
    assert len(block.algebraic_vars) == len(block.algebraic_eqs)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs],0,atol=1e-12)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.algebraic_eqs],0,atol=1e-12)
    assert values[block.out_vars[0].uid] == 0


def test_post_limit_field_feedback_can_be_negative() -> None:
    """Field-rate damping after a bounded amplifier is not clipped by that amplifier."""
    block: Block = build_mnlex1_template(VarFactory()).block
    values: dict[int,float] = initialized_values(block)
    values[block.in_vars[2].uid] = 1.2
    states: np.ndarray = np.asarray([values[variable.uid] for variable in block.state_vars])
    derivative, output = evaluate_controller(block,values,states,.5)
    assert output == pytest.approx(-.02)
    assert derivative[0] == 0


def test_linear_current_limiter_keeps_feedback_inside_bound() -> None:
    """The same field-voltage step cannot push a bounded limiter output below zero."""
    block: Block = build_mnlex3_template(VarFactory()).block
    values: dict[int,float] = initialized_values(block)
    values[block.in_vars[2].uid] = 1.2
    states: np.ndarray = np.asarray([values[variable.uid] for variable in block.state_vars])
    derivative, output = evaluate_controller(block,values,states,.5)
    assert output == 0
    assert derivative[-1] == 0


def test_circular_capability_scales_with_squared_voltage() -> None:
    """A voltage dip changes the circle radius before amplifier limiting."""
    block: Block = build_mnlex2_template(VarFactory()).block
    values: dict[int,float] = initialized_values(block)
    states: np.ndarray = np.asarray([values[variable.uid] for variable in block.state_vars])
    values[block.in_vars[2].uid] = .6
    derivative, output = evaluate_controller(block,values,states,.5)
    assert derivative[-1] == pytest.approx((.5**2-.6**4)/.1)
    assert output == 0
    values[block.in_vars[2].uid] = 0
    derivative, output = evaluate_controller(block,values,states,.5)
    assert np.all(np.isfinite(derivative))


def test_zero_time_circular_limiter_solves_bounded_feedback_algebraically() -> None:
    """Zero amplifier time preserves the finite internal-feedback gain, without epsilon."""
    block: Block = build_mnlex2_template(VarFactory(),limiter_time=0).block
    values: dict[int,float] = initialized_values(block)
    assert len(block.state_vars) == 1
    values[block.in_vars[2].uid] = .6
    values[block.out_vars[0].uid] = (.5**2-.6**4)/1.1
    for variable,equation in zip(block.algebraic_vars,block.algebraic_eqs):
        if variable.uid != block.out_vars[0].uid:
            values[variable.uid] = 0
            values[variable.uid] = -equation.eval_uid(values)
        else:
            pass
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.algebraic_eqs],0,atol=1e-12)


def test_zero_time_current_limiter_uses_one_feedback_state() -> None:
    """Both field-feedback variants remove only the amplifier state for zero TM."""
    for block in (build_mnlex1_template(VarFactory(),limiter_time=0).block,
                  build_mnlex3_template(VarFactory(),limiter_time=0).block):
        values: dict[int,float] = initialized_values(block)
        assert len(block.state_vars) == 1
        np.testing.assert_allclose([equation.eval_uid(values) for equation in block.algebraic_eqs],0,atol=1e-12)
