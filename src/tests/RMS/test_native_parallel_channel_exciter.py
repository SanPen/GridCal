# SPDX-License-Identifier: MPL-2.0
"""Bounded lead-lag tracking and independent three-channel take-over dynamics."""
from __future__ import annotations

import numpy as np
import pytest
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.control_realization import ControlRealization
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.st5b import ParallelChannelExciterParameters, build_st5b_template
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var
from tests.RMS.test_native_turbine_governors import initialized_values, linearized_response, evaluate_controller


@pytest.mark.parametrize('lead,lag',((.1,.2),(.5,.2),(.2,.2),(0.,.2),(0.,0.)))
def test_bounded_lead_lag_independent_transfer(lead: float, lag: float) -> None:
    """Output-tracking and exact zero-time reductions retain the specified unsaturated transfer.

    :param lead: Numerator time.
    :param lag: Denominator time.
    """
    c: ControlRealization = ControlRealization(VarFactory(),'tracking')
    source: Var = c.input('Input',Const(0.))
    output: Var = c.bounded_lead_lag('Output',source,Const(lead),Const(lag),lead,lag,Const(0.),Const(-1.),Const(1.))
    block: Block = c.finish((output,),'Bounded lead-lag tracking').block
    values: dict[int,float] = initialized_values(block)
    for frequency in (.02,.4,2.):
        s: complex = 2j*np.pi*frequency
        assert linearized_response(block,values,0.,frequency) == pytest.approx((1.+lead*s)/(1.+lag*s),rel=1e-7)


def test_bounded_lead_lag_clipped_memory_tracking() -> None:
    """Clipped output drives the memory through numerator time, rather than an unrestricted input lag."""
    c: ControlRealization = ControlRealization(VarFactory(),'tracking')
    source: Var = c.input('Input',Const(0.))
    output: Var = c.bounded_lead_lag('Output',source,Const(.1),Const(.2),.1,.2,Const(0.),Const(-1.),Const(1.))
    block: Block = c.finish((output,),'Bounded lead-lag tracking').block
    values: dict[int,float] = initialized_values(block)
    derivative: np.ndarray
    result: float
    derivative,result = evaluate_controller(block,values,np.array([0.]),10.)
    assert result == 1. and derivative[0] == pytest.approx(10.)
    derivative,result = evaluate_controller(block,values,np.array([.9]),0.)
    assert result == pytest.approx(.45) and derivative[0] == pytest.approx(-4.5)


def test_parallel_channel_independent_ordinary_transfer() -> None:
    """Ordinary voltage regulation includes its own two compensators and the final field lag."""
    block: Block = build_st5b_template(VarFactory(),'parallel').block
    values: dict[int,float] = initialized_values(block)
    assert len(block.state_vars) == 8
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs],0.,atol=1e-12)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.algebraic_eqs],0.,atol=1e-12)
    values[block.in_vars[5].uid] = -.2
    values[block.in_vars[6].uid] = .2
    for frequency in (.02,.4,2.):
        s: complex = 2j*np.pi*frequency
        expected: complex = -20.*(1.+.1*s)*(1.+.05*s)/((1.+.02*s)*(1.+.2*s)*(1.+.1*s)*(1.+.05*s))
        assert linearized_response(block,values,1.,frequency) == pytest.approx(expected,rel=3e-7,abs=1e-7)


@pytest.mark.parametrize('minimum,maximum,expected',((-.1,.2,.0125),(.1,.2,.1),(-.1,.02,.17),(.1,.02,.17)))
def test_parallel_channel_selection_and_inactive_memories(minimum: float, maximum: float, expected: float) -> None:
    """Distinct live channel memories survive inactivity and low-gate takeover wins conflicting requests.

    :param minimum: High-gate request.
    :param maximum: Low-gate request.
    :param expected: Independently calculated selected channel output.
    """
    block: Block = build_st5b_template(VarFactory(),'parallel').block
    values: dict[int,float] = initialized_values(block)
    values[block.in_vars[1].uid] = 1.05
    values[block.in_vars[5].uid] = minimum
    values[block.in_vars[6].uid] = maximum
    states: np.ndarray = np.asarray([0. if variable.name.startswith('Normal') else .1 if variable.name.startswith('Minimum') else
        .2 if variable.name.startswith('Maximum') else values[variable.uid] for variable in block.state_vars])
    block.out_vars[0] = next(variable for variable in block.algebraic_vars if variable.name == 'SelectedDemandPu_parallel')
    derivative: np.ndarray
    result: float
    derivative,result = evaluate_controller(block,values,states,1.)
    assert result == pytest.approx(expected)
    if minimum < 0 and maximum > .05:
        inactive: int = next(index for index,variable in enumerate(block.state_vars) if variable.name == 'MinimumFirstPuMemory_parallel')
        assert derivative[inactive] == pytest.approx(-1./6.)
    else:
        pass


def test_parallel_channel_terminal_capability_collapse() -> None:
    """Available terminal supply clips field immediately while its lag memory recovers continuously."""
    block: Block = build_st5b_template(VarFactory(),'parallel').block
    values: dict[int,float] = initialized_values(block)
    values[block.in_vars[4].uid] = 0.
    states: np.ndarray = np.asarray([values[variable.uid] for variable in block.state_vars])
    derivative: np.ndarray
    field: float
    derivative,field = evaluate_controller(block,values,states,1.)
    assert field == 0.


def test_parallel_channel_exact_static_compensation_reduction() -> None:
    """Six disabled compensation stages introduce no artificial memories or small times."""
    block: Block = build_st5b_template(VarFactory(),'parallel',ParallelChannelExciterParameters(
        tc1=0.,tb1=0.,tc2=0.,tb2=0.,tuc1=0.,tub1=0.,tuc2=0.,tub2=0.,toc1=0.,tob1=0.,toc2=0.,tob2=0.)).block
    values: dict[int,float] = initialized_values(block)
    assert len(block.state_vars) == 2
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs],0.,atol=1e-12)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.algebraic_eqs],0.,atol=1e-12)
