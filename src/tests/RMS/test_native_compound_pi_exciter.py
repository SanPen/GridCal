# SPDX-License-Identifier: MPL-2.0
"""Independent cascaded-PI response, supply phasors and collapsed-supply behavior."""
from __future__ import annotations

import numpy as np
import pytest
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.st4b import CompoundPiExciterParameters, build_st4b_template
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Expr, Var
from tests.RMS.test_native_turbine_governors import initialized_values, evaluate_controller, linearized_response


@pytest.mark.parametrize('kir',(0.,1.))
@pytest.mark.parametrize('kim',(0.,1.))
def test_compound_pi_independent_transfer(kir: float, kim: float) -> None:
    """Each PI and its feedback reproduce an independent closed-loop frequency response.

    :param kir: Voltage-loop integral gain.
    :param kim: Field-loop integral gain.
    """
    block: Block = build_st4b_template(VarFactory(),'compound',CompoundPiExciterParameters(
        tr=.03,kpr=2.,kir=kir,ta=.07,kpm=.5,kim=kim,kg=.2,kp=2.,ki=0.,kc=0.,xl=0.)).block
    values: dict[int,float] = initialized_values(block)
    assert len(block.state_vars) == 2+int(kir>0)+int(kim>0)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs],0.,atol=1e-12)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.algebraic_eqs],0.,atol=1e-12)
    values[block.in_vars[9].uid] = 100.
    for frequency in (.02,.4,2.):
        s: complex = 2j*np.pi*frequency
        outer: complex = (2.+kir/s)/(1.+.07*s)
        inner: complex = .5+kim/s
        expected: complex = -outer*2.*inner/((1.+.03*s)*(1.+.2*2.*inner))
        assert linearized_response(block,values,1.,frequency) == pytest.approx(expected,rel=3e-7,abs=1e-8)


def test_compound_pi_collapsed_source() -> None:
    """A fully collapsed transformer source gives finite dynamics and zero delivered field."""
    block: Block = build_st4b_template(VarFactory(),'compound').block
    values: dict[int,float] = initialized_values(block)
    for port in block.in_vars[3:7]:
        values[port.uid] = 0.
    values[block.in_vars[9].uid] = 100.
    states: np.ndarray = np.asarray([values[variable.uid] for variable in block.state_vars])
    derivative: np.ndarray
    output: float
    derivative,output = evaluate_controller(block,values,states,1.)
    assert output == 0. and np.all(np.isfinite(derivative))


@pytest.mark.parametrize('kpr,kpm',((0.,.5),(2.,0.),(0.,0.)))
def test_compound_pi_pure_integral_channels(kpr: float, kpm: float) -> None:
    """Pure-integral outer/inner loops preserve independently derived gain and feasible initialization.

    :param kpr: Outer proportional gain or zero.
    :param kpm: Inner proportional gain or zero.
    """
    block: Block = build_st4b_template(VarFactory(),'compound',CompoundPiExciterParameters(
        kpr=kpr,kpm=kpm,kg=.2,kp=2.,ki=0.,kc=0.,xl=0.)).block
    values: dict[int,float] = initialized_values(block)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs],0.,atol=1e-12)
    values[block.in_vars[9].uid] = 100.
    s: complex = 2j*np.pi*.4
    outer: complex = (kpr+1./s)/(1.+.05*s)
    inner: complex = kpm+1./s
    expected: complex = -outer*2.*inner/((1.+.02*s)*(1.+.2*2.*inner))
    assert linearized_response(block,values,1.,.4) == pytest.approx(expected,rel=3e-7,abs=1e-8)


def test_compound_pi_transformer_phasor() -> None:
    """Complex phase, leakage and compounding produce the independently calculated transformer voltage."""
    block: Block = build_st4b_template(VarFactory(),'compound',CompoundPiExciterParameters(thetap=30.,xl=.2,kp=2.,ki=.3)).block
    values: dict[int,float] = initialized_values(block)
    for port,value in zip(block.in_vars[3:7],(.8,.3,.1,-.5)):
        values[port.uid] = value
    potential: Var = next(variable for variable in block.algebraic_vars if variable.name == 'PotentialPu_compound')
    equation: Expr = block.algebraic_eqs[block.algebraic_vars.index(potential)]
    expected: float = abs(2.*np.exp(1j*np.pi/6)*((.8+.3j)+.2j*(.1-.5j))+.3j*(.1-.5j))
    values[potential.uid] = expected
    assert equation.eval_uid(values) == pytest.approx(0.,abs=1e-12)


def test_compound_pi_integral_stops_and_recovery() -> None:
    """Both total PI bounds suppress only outward integral motion and release it under inward error."""
    block: Block = build_st4b_template(VarFactory(),'compound').block
    values: dict[int,float] = initialized_values(block)
    values[block.in_vars[9].uid] = 100.
    states: np.ndarray = np.asarray([values[variable.uid] for variable in block.state_vars])
    outer_index: int = next(index for index,variable in enumerate(block.state_vars) if variable.name == 'VoltageIntegralPu_compound')
    inner_index: int = next(index for index,variable in enumerate(block.state_vars) if variable.name == 'FieldIntegralPu_compound')
    regulator_index: int = next(index for index,variable in enumerate(block.state_vars) if variable.name == 'RegulatorPu_compound')
    states[outer_index] = 5.
    states[inner_index] = 1.
    states[regulator_index] = 5.
    values[block.in_vars[1].uid] = 2.
    derivative: np.ndarray
    output: float
    derivative,output = evaluate_controller(block,values,states,1.)
    assert derivative[outer_index] == 0. and derivative[inner_index] == 0.
    values[block.in_vars[1].uid] = .9
    states[regulator_index] = .8
    derivative,output = evaluate_controller(block,values,states,1.)
    assert derivative[outer_index] < 0. and derivative[inner_index] < 0.
