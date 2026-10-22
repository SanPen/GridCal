# SPDX-License-Identifier: MPL-2.0
"""Bounded rotating field capability, selected limiter gates and reversible saturation sample order."""
from __future__ import annotations

import numpy as np
import pytest
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.dc_exciter import DcExciterKind, DcExciterParameters, RotatingLimiterLocation, build_dc_exciter
from VeraGridEngine.Utils.Symbolic.block import Block
from tests.RMS.test_native_turbine_governors import initialized_values, evaluate_controller, linearized_response


@pytest.mark.parametrize('kind',(DcExciterKind.BOUNDED_FIXED_SUPPLY,DcExciterKind.BOUNDED_TERMINAL_SUPPLY))
@pytest.mark.parametrize('minimum',tuple(RotatingLimiterLocation))
@pytest.mark.parametrize('maximum',tuple(RotatingLimiterLocation))
def test_bounded_rotating_independent_transfer(kind: DcExciterKind, minimum: RotatingLimiterLocation, maximum: RotatingLimiterLocation) -> None:
    """All limiter selections retain the physical phase/regulator/field/washout loop when the gates are inactive.

    :param kind: Fixed or terminal-fed regulator capability.
    :param minimum: Minimum-excitation insertion point.
    :param maximum: Maximum-excitation insertion point.
    """
    block: Block = build_dc_exciter(VarFactory(),'bounded',kind,DcExciterParameters(
        tr=.03,ka=4.,ta=.07,ke=2.,te=.5,kf=.06,tf=.8,se1=0.,se2=0.,field_min=-2.,field_max=3.),minimum,maximum).block
    values: dict[int,float] = initialized_values(block)
    assert len(block.in_vars) == 6 and len(block.out_vars) == 3
    assert len(block.state_vars) == 5
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs],0.,atol=1e-12)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.algebraic_eqs],0.,atol=1e-12)
    if minimum == RotatingLimiterLocation.TAKEOVER_GATE:
        values[block.in_vars[3].uid] = -100.
    else:
        pass
    if maximum == RotatingLimiterLocation.TAKEOVER_GATE:
        values[block.in_vars[5].uid] = 100.
    else:
        pass
    for frequency in (.02,.4,2.):
        s: complex = 2j*np.pi*frequency
        forward: complex = 4.*(1.+.1*s)/((1.+.2*s)*(1.+.07*s)*(2.+.5*s))
        feedback: complex = .06*s/(1.+.8*s)
        expected: complex = -forward/((1.+.03*s)*(1.+forward*feedback))
        assert linearized_response(block,values,1.,frequency) == pytest.approx(expected,rel=3e-7,abs=1e-8)


@pytest.mark.parametrize('kind,forcing',((DcExciterKind.BOUNDED_FIXED_SUPPLY,5.),(DcExciterKind.BOUNDED_TERMINAL_SUPPLY,1.)))
def test_bounded_rotating_live_regulator_capability(kind: DcExciterKind, forcing: float) -> None:
    """Actual terminal voltage scales only the terminal-fed regulator, separately from fixed field stops.

    :param kind: Physical regulator power supply.
    :param forcing: Independent expected limited forcing after a low-voltage event.
    """
    block: Block = build_dc_exciter(VarFactory(),'bounded',kind,DcExciterParameters(ta=0.,se1=0.,se2=0.,field_min=-2.,field_max=3.)).block
    values: dict[int,float] = initialized_values(block)
    values[block.in_vars[1].uid] = 10.
    values[block.in_vars[4].uid] = .2
    states: np.ndarray = np.asarray([values[var.uid] for var in block.state_vars])
    derivative, output = evaluate_controller(block,values,states,1.)
    assert derivative[-1] == pytest.approx((forcing-1.)/.5)
    assert output == 1.


@pytest.mark.parametrize('reverse',(False,True))
def test_bounded_rotating_saturation_sample_order(reverse: bool) -> None:
    """Explicit capability permits either sample order, including a zero lower saturation factor.

    :param reverse: Supply high-voltage saturation data before the lower sample.
    """
    p: DcExciterParameters = DcExciterParameters(e1=1.2 if reverse else .8,se1=.4 if reverse else 0.,
        e2=.8 if reverse else 1.2,se2=0. if reverse else .4,field_min=-2.,field_max=3.)
    block: Block = build_dc_exciter(VarFactory(),'bounded',DcExciterKind.BOUNDED_FIXED_SUPPLY,p).block
    values: dict[int,float] = initialized_values(block)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs],0.,atol=1e-12)
    regulator = next(var for var in block.algebraic_vars if var.name == 'RegulatorPu_bounded')
    assert values[regulator.uid] == pytest.approx(1.12)


def test_bounded_rotating_field_stops_allow_recovery() -> None:
    """The field integrator has independent upper/lower travel stops and permits inward forcing immediately."""
    block: Block = build_dc_exciter(VarFactory(),'bounded',DcExciterKind.BOUNDED_FIXED_SUPPLY,
        DcExciterParameters(se1=0.,se2=0.,field_min=-.5,field_max=1.2)).block
    values: dict[int,float] = initialized_values(block)
    states: np.ndarray = np.asarray([values[var.uid] for var in block.state_vars])
    states[-1] = 1.2
    states[-2] = 5.
    derivative, output = evaluate_controller(block,values,states,1.)
    assert derivative[-1] == 0. and output == 1.2
    states[-2] = -1.
    derivative, output = evaluate_controller(block,values,states,1.)
    assert derivative[-1] < 0.
    states[-1] = -.5
    derivative, output = evaluate_controller(block,values,states,1.)
    assert derivative[-1] == 0.
    states[-2] = 1.
    derivative, output = evaluate_controller(block,values,states,1.)
    assert derivative[-1] > 0.
