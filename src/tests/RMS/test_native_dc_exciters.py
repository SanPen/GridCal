# SPDX-License-Identifier: MPL-2.0
"""Physical initialization, saturation, gate placement and DC field limits."""
from __future__ import annotations

import numpy as np
import pytest

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.dc_exciter import DcExciterKind, DcExciterParameters, build_dc_exciter
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from tests.RMS.test_native_turbine_governors import initialized_values, evaluate_controller, linearized_response


@pytest.mark.parametrize('kind',tuple(DcExciterKind))
@pytest.mark.parametrize('instantaneous',(False,True))
@pytest.mark.parametrize('automatic',(False,True))
def test_dc_exciter_physical_equilibrium(kind: DcExciterKind, instantaneous: bool, automatic: bool) -> None:
    """Field balance and rheostat calibration hold with dynamic and algebraic stages.

    :param kind: Explicit physical limiter/regulator structure.
    :param instantaneous: Select algebraic sensing, phase and regulator stages.
    :param automatic: Derive regulator capability and the operating-point rheostat.
    """
    p: DcExciterParameters = DcExciterParameters(tr=0 if instantaneous else .02,
        ta=0 if instantaneous else .05,tb=0 if instantaneous else .2,
        tc=0 if instantaneous else .1,vrmax=None if automatic else 5,
        ke=None if automatic else 1,e1=.8,se1=.1,e2=1.2,se2=.4)
    block: Block = build_dc_exciter(VarFactory(),'dc',kind,p).block
    values: dict[int,float] = initialized_values(block)
    expected_states: int = 2 if instantaneous else (4 if kind in (DcExciterKind.TYPE1,DcExciterKind.TYPE2,DcExciterKind.BRUSHLESS) else 5)
    if kind in (DcExciterKind.TYPE2,DcExciterKind.COMPENSATED_TYPE2,DcExciterKind.BRUSHLESS):
        expected_states += 1
    elif kind == DcExciterKind.LIMITED_TYPE1 and not instantaneous:
        expected_states = 3
    else:
        pass
    assert len(block.state_vars) == expected_states
    assert len(block.algebraic_vars) == len(block.algebraic_eqs)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs],0,atol=1e-12)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.algebraic_eqs],0,atol=1e-12)
    if automatic:
        regulator: Var = next(variable for variable in block.get_all_vars() if variable.name == 'RegulatorPu_dc')
        assert values[regulator.uid] == pytest.approx(.048)
    else:
        pass


@pytest.mark.parametrize('kind',tuple(DcExciterKind))
def test_dc_exciter_limit_scaling_uses_actual_terminal_voltage(kind: DcExciterKind) -> None:
    """Regulator capability uses terminal voltage independently of compensated sensing.

    :param kind: Native physical regulator variant.
    """
    block: Block = build_dc_exciter(VarFactory(),'dc',kind,DcExciterParameters(ta=0)).block
    values: dict[int,float] = initialized_values(block)
    values[block.in_vars[1].uid] = 10.0
    values[block.in_vars[4].uid] = .2
    states: np.ndarray = np.asarray([values[variable.uid] for variable in block.state_vars])
    derivative, output = evaluate_controller(block,values,states,1.0)
    regulator: float = 1.0 if kind in (DcExciterKind.DC2,DcExciterKind.DC2A,DcExciterKind.BOUNDED_TERMINAL_SUPPLY) else 5.0
    assert derivative[-1] == pytest.approx((regulator-1.0)/.5)
    assert output == 1.0


@pytest.mark.parametrize('kind',(DcExciterKind.TYPE1,DcExciterKind.COMPENSATED_TYPE1,DcExciterKind.DC1A))
def test_dc_exciter_minimum_excitation_signal_location(kind: DcExciterKind) -> None:
    """A gated input competes after phase compensation; an additive input sums before it.

    :param kind: Native additive or high-value-gated structure.
    """
    block: Block = build_dc_exciter(VarFactory(),'dc',kind,DcExciterParameters(
        ka=2,ta=0,tb=0,tc=0,se1=0,se2=0)).block
    values: dict[int,float] = initialized_values(block)
    values[block.in_vars[1].uid] = 1.5
    values[block.in_vars[3].uid] = .8
    states: np.ndarray = np.asarray([values[variable.uid] for variable in block.state_vars])
    derivative, output = evaluate_controller(block,values,states,1.0)
    expected: float = 1.2 if kind is DcExciterKind.DC1A else 3.2
    assert derivative[-1] == pytest.approx(expected)
    assert output == 1.0


def test_dc1a_field_lower_stop_allows_inward_recovery() -> None:
    """A discharged field cannot move below zero, but positive forcing releases it."""
    block: Block = build_dc_exciter(VarFactory(),'dc',DcExciterKind.DC1A).block
    values: dict[int,float] = initialized_values(block)
    states: np.ndarray = np.asarray([values[variable.uid] for variable in block.state_vars])
    states[-1] = 0
    states[-2] = -1
    derivative, output = evaluate_controller(block,values,states,1.0)
    assert derivative[-1] == 0
    states[-2] = 1
    derivative, output = evaluate_controller(block,values,states,1.0)
    assert derivative[-1] == pytest.approx(2)


@pytest.mark.parametrize('kind',(DcExciterKind.DC2,DcExciterKind.DC2A))
def test_dc_exciter_capability_collapses_before_regulator_memory_moves(kind: DcExciterKind) -> None:
    """A network fault clips regulator output even while its memory is continuous.

    :param kind: Terminal-voltage-dependent physical regulator variant.
    """
    block: Block = build_dc_exciter(VarFactory(),'dc',kind).block
    values: dict[int,float] = initialized_values(block)
    values[block.in_vars[4].uid] = 0
    states: np.ndarray = np.asarray([values[variable.uid] for variable in block.state_vars])
    derivative, output = evaluate_controller(block,values,states,1.0)
    assert derivative[-1] == pytest.approx(-2.0)
    assert output == 1.0


@pytest.mark.parametrize('kind',tuple(DcExciterKind))
@pytest.mark.parametrize('frequency',(.02,.4,2.0))
def test_dc_exciter_feedback_transfer_function(kind: DcExciterKind, frequency: float) -> None:
    """Independent closed-loop transfer functions distinguish the three feedback sources.

    :param kind: Explicit native physical exciter structure.
    :param frequency: Perturbation frequency in hertz.
    """
    block: Block = build_dc_exciter(VarFactory(),'dc',kind,DcExciterParameters(
        tr=.03,ka=4,ta=.07,tb=.2,tc=.1,ke=2,te=.5,kf=.06,tf=.8,tf2=.3,tf3=.1,se1=0,se2=0)).block
    values: dict[int,float] = initialized_values(block)
    values[block.in_vars[3].uid] = 0
    actual: complex = linearized_response(block,values,1.0,frequency)
    s: complex = 2j*np.pi*frequency
    lead: complex = 1 if kind in (DcExciterKind.TYPE1,DcExciterKind.TYPE2,DcExciterKind.BRUSHLESS,DcExciterKind.LIMITED_TYPE1) else (1+.1*s)/(1+.2*s)
    amplifier: complex = 4*lead/(1+.07*s)
    field: complex = 1/(2+.5*s)
    feedback: complex = .06*s/(1+.8*s)
    loop: complex
    if kind in (DcExciterKind.TYPE2,DcExciterKind.COMPENSATED_TYPE2):
        loop = amplifier*feedback/(1+.3*s)
    elif kind is DcExciterKind.TYPE2A:
        loop = amplifier*field*2*feedback
    elif kind == DcExciterKind.BRUSHLESS:
        loop = amplifier*field*2*feedback*(1+.1*s)/(1+.3*s)
    else:
        loop = amplifier*field*feedback
    sensing: complex = 1 if kind == DcExciterKind.LIMITED_TYPE1 else 1+.03*s
    expected: complex = -amplifier*field/((1+loop)*sensing)
    assert actual == pytest.approx(expected,rel=1e-7,abs=1e-8)


@pytest.mark.parametrize('second_time,lead_time', ((0.0, 0.0), (0.0, .7), (.3, 0.0), (.3, .1)))
def test_brushless_secondary_feedback_stage(second_time: float, lead_time: float) -> None:
    """The loaded field-current feedback has its own lead and exact zero-lag bypass."""
    block: Block = build_dc_exciter(VarFactory(),'brushless',DcExciterKind.BRUSHLESS,
        DcExciterParameters(tr=.03,ka=4,ta=.07,ke=2,te=.5,kf=.06,tf=.8,
            tf2=second_time,tf3=lead_time,se1=0,se2=0)).block
    values: dict[int,float] = initialized_values(block)
    assert len(block.state_vars) == (4 if second_time == 0 else 5)
    s: complex = 2j*np.pi*.4
    amplifier: complex = 4/(1+.07*s)
    field: complex = 1/(2+.5*s)
    feedback: complex = .06*s/(1+.8*s)
    if second_time != 0:
        feedback *= (1+s*lead_time)/(1+s*second_time)
    else:
        pass
    expected: complex = -amplifier*field/((1+amplifier*field*2*feedback)*(1+.03*s))
    assert linearized_response(block,values,1.0,.4) == pytest.approx(expected,rel=1e-7,abs=1e-8)


def test_brushless_field_lower_stop() -> None:
    """Negative regulator forcing cannot drive the rectified field output below zero."""
    block: Block = build_dc_exciter(VarFactory(),'brushless',DcExciterKind.BRUSHLESS).block
    values: dict[int,float] = initialized_values(block)
    states: np.ndarray = np.asarray([values[variable.uid] for variable in block.state_vars])
    states[-1] = 0
    states[-2] = -1
    derivative, output = evaluate_controller(block,values,states,1.0)
    assert derivative[-1] == 0
    assert output == 0
    states[-2] = 1
    derivative, output = evaluate_controller(block,values,states,1.0)
    assert derivative[-1] == pytest.approx(2)


@pytest.mark.parametrize('memory,reference,expected_output,expected_derivative', (
    (3.0, 1.5, 2.0, -2.8), (3.0, 10.0, 2.0, 6.0),
    (-1.0, 1.5, -.5, 3.8), (-1.0, -10.0, -.5, -9.0),
))
def test_external_field_clip_keeps_internal_memory(memory: float, reference: float,
                                                   expected_output: float, expected_derivative: float) -> None:
    """Rate feedback senses unclipped memory, field losses sense clipped voltage, and clipping permits windup."""
    block: Block = build_dc_exciter(VarFactory(),'limited',DcExciterKind.LIMITED_TYPE1,
        DcExciterParameters(ka=2,ta=0,ke=1,te=.5,kf=.1,tf=1,e1=1,se1=0,e2=2,se2=0,field_min=-.5)).block
    values: dict[int,float] = initialized_values(block)
    values[block.in_vars[1].uid] = reference
    states: np.ndarray = np.asarray([values[variable.uid] for variable in block.state_vars])
    states[-1] = memory
    derivative: np.ndarray
    output: float
    derivative, output = evaluate_controller(block,values,states,1.0)
    assert len(block.state_vars) == 2
    assert output == pytest.approx(expected_output)
    assert derivative[-1] == pytest.approx(expected_derivative)
