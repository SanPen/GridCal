# SPDX-License-Identifier: MPL-2.0
"""Independent selected limiter equations and controlled-bridge transfer."""
from __future__ import annotations

import numpy as np
import pytest
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.alternator_rectifier import AlternatorRectifierParameters, RectifierLimiterLocation
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.ac4c import build_ac4c_template
from VeraGridEngine.Utils.Symbolic.block import Block
from tests.RMS.test_native_turbine_governors import initialized_values, evaluate_controller, linearized_response


@pytest.mark.parametrize('minimum',tuple(RectifierLimiterLocation))
@pytest.mark.parametrize('maximum',tuple(RectifierLimiterLocation))
def test_selectable_bridge_transfer(minimum: RectifierLimiterLocation, maximum: RectifierLimiterLocation) -> None:
    """Inactive gates preserve sensing, phase compensation and amplifier poles.

    :param minimum: Minimum-excitation insertion location.
    :param maximum: Maximum-excitation insertion location.
    """
    block: Block = build_ac4c_template(VarFactory(),'bridge',minimum_location=minimum,maximum_location=maximum).block
    values: dict[int,float] = initialized_values(block)
    assert len(block.in_vars) == 6 and len(block.out_vars) == 3
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs],0.,atol=1e-12)
    if minimum == RectifierLimiterLocation.TAKEOVER_GATE:
        values[block.in_vars[3].uid] = -100.
    else:
        pass
    if maximum == RectifierLimiterLocation.TAKEOVER_GATE:
        values[block.in_vars[5].uid] = 100.
    else:
        pass
    for frequency in (.02,.4,2.):
        s: complex = 2j*np.pi*frequency
        expected: complex = -100*(1+.1*s)/((1+.02*s)*(1+.2*s)*(1+.05*s))
        assert linearized_response(block,values,1.,frequency) == pytest.approx(expected,rel=3e-7,abs=1e-8)


@pytest.mark.parametrize('minimum',tuple(RectifierLimiterLocation))
@pytest.mark.parametrize('maximum',tuple(RectifierLimiterLocation))
def test_selectable_bridge_gate_order(minimum: RectifierLimiterLocation, maximum: RectifierLimiterLocation) -> None:
    """Error clipping precedes high/low gates, and the maximum gate has final priority.

    :param minimum: Minimum-excitation insertion.
    :param maximum: Maximum-excitation insertion.
    """
    block: Block = build_ac4c_template(VarFactory(),'bridge',AlternatorRectifierParameters(
        tr=0.,ta=0.,tb=0.,tc=0.,ka=10.,kc=0.),minimum,maximum).block
    values: dict[int,float] = initialized_values(block)
    values[block.in_vars[1].uid] = 1.
    values[block.in_vars[3].uid] = .3
    values[block.in_vars[5].uid] = .1
    derivative: np.ndarray
    output: float
    derivative, output = evaluate_controller(block,values,np.zeros(0),1.)
    expected: float = .1 if maximum == RectifierLimiterLocation.TAKEOVER_GATE else (.3 if minimum == RectifierLimiterLocation.TAKEOVER_GATE else .2)
    assert output == pytest.approx(10.*expected)
    assert derivative.size == 0
