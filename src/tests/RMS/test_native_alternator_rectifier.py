# SPDX-License-Identifier: MPL-2.0
"""Independent dynamic, bridge-capability and limiter-placement checks."""
from __future__ import annotations

import numpy as np
import pytest

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.alternator_rectifier import (
    AlternatorRectifierKind, AlternatorRectifierParameters, build_alternator_rectifier,
)
from VeraGridEngine.Utils.Symbolic.block import Block
from tests.RMS.test_native_turbine_governors import initialized_values, evaluate_controller, linearized_response


@pytest.mark.parametrize('kind', tuple(AlternatorRectifierKind))
@pytest.mark.parametrize('instantaneous', (False, True))
def test_alternator_rectifier_equilibrium(kind: AlternatorRectifierKind, instantaneous: bool) -> None:
    """Dynamic lags and exact algebraic reductions preserve the initial field demand."""
    parameters: AlternatorRectifierParameters = AlternatorRectifierParameters(
        tr=0 if instantaneous else .02, tc=0 if instantaneous else .1,
        tb=0 if instantaneous else .2, ta=0 if instantaneous else .05)
    block: Block = build_alternator_rectifier(VarFactory(),'bridge',kind,parameters).block
    values: dict[int,float] = initialized_values(block)
    assert len(block.state_vars) == (0 if instantaneous else 3)
    assert values[block.out_vars[0].uid] == 1
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs], 0, atol=1e-12)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.algebraic_eqs], 0, atol=1e-12)


@pytest.mark.parametrize('kind', tuple(AlternatorRectifierKind))
@pytest.mark.parametrize('frequency', (.02, .4, 2.0))
def test_alternator_rectifier_transfer(kind: AlternatorRectifierKind, frequency: float) -> None:
    """Actual native equations reproduce sensing, phase and amplifier frequency response."""
    block: Block = build_alternator_rectifier(VarFactory(),'bridge',kind).block
    values: dict[int,float] = initialized_values(block)
    values[block.in_vars[3].uid] = 0
    s: complex = 2j*np.pi*frequency
    expected: complex = -100*(1+.1*s)/((1+.02*s)*(1+.2*s)*(1+.05*s))
    assert linearized_response(block,values,1.0,frequency) == pytest.approx(expected,rel=1e-7,abs=1e-8)


@pytest.mark.parametrize('kind', tuple(AlternatorRectifierKind))
@pytest.mark.parametrize('regulator', (-10.0, 10.0))
def test_commutation_limits_and_windup(kind: AlternatorRectifierKind, regulator: float) -> None:
    """The external-clip variant winds up while the internal limiter blocks outward motion."""
    block: Block = build_alternator_rectifier(VarFactory(),'bridge',kind,
        AlternatorRectifierParameters(tr=0,tb=0,tc=0,ka=10,ta=.1,vi_max=10,vi_min=-10,kc=.5)).block
    values: dict[int,float] = initialized_values(block)
    values[block.in_vars[1].uid] = 10 if regulator > 0 else -10
    values[block.in_vars[3].uid] = -100 if kind == AlternatorRectifierKind.NONWINDUP_GATE else 0
    values[block.in_vars[4].uid] = 2
    derivative: np.ndarray
    output: float
    derivative, output = evaluate_controller(block,values,np.array([regulator]),1.0)
    expected: float = 4 if regulator > 0 else (-6 if kind == AlternatorRectifierKind.OUTPUT_CLIP else -5)
    assert output == expected
    if kind != AlternatorRectifierKind.OUTPUT_CLIP:
        assert derivative[0] == 0
    else:
        assert derivative[0] != 0


def test_minimum_excitation_gate_is_after_input_clip() -> None:
    """A gated demand can exceed the clipped voltage error while an additive input cannot."""
    for kind in AlternatorRectifierKind:
        block: Block = build_alternator_rectifier(VarFactory(),'bridge',kind,
            AlternatorRectifierParameters(tr=0,tb=0,tc=0,ka=10,ta=0,vi_max=.2,vi_min=-.2,kc=0)).block
        values: dict[int,float] = initialized_values(block)
        values[block.in_vars[3].uid] = .3
        derivative, output = evaluate_controller(block,values,np.zeros(0),1.0)
        assert output == pytest.approx(3 if kind == AlternatorRectifierKind.NONWINDUP_GATE else 2)
