# SPDX-License-Identifier: MPL-2.0
"""Independent cascaded-PI transfer and physical insertion of excitation take-over gates."""
from __future__ import annotations

import json
import numpy as np
import pytest
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.st4c import FilteredCompoundPiParameters, CompoundExcitationSource, CompoundSupplementLocation, build_st4c_template
from VeraGridEngine.Templates.Rms.self_feedback_exciter import ExcitationLimiterLocation
from VeraGridEngine.Utils.Symbolic.block import Block
from tests.RMS.test_native_turbine_governors import initialized_values, linearized_response, evaluate_controller


@pytest.mark.parametrize('kir,kim,ta',((10.,1.,.02),(0.,1.,.02),(10.,0.,.02),(0.,0.,0.)))
@pytest.mark.parametrize('source',(CompoundExcitationSource.TERMINAL,CompoundExcitationSource.INDEPENDENT))
def test_filtered_compound_pi_independent_transfer(kir: float, kim: float, ta: float, source: CompoundExcitationSource) -> None:
    """Feedback senses bridge VA before supply scaling, with its own positive-time memory.

    :param kir: Outer integral gain or exact proportional reduction.
    :param kim: Inner integral gain or exact proportional reduction.
    :param ta: Firing lag or exact algebraic reduction.
    :param source: Terminal compound potential or independent potential.
    """
    block: Block = build_st4c_template(VarFactory(),'filtered',FilteredCompoundPiParameters(kir=kir,kim=kim,ta=ta,source=source)).block
    values: dict[int,float] = initialized_values(block)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.algebraic_eqs],0.,atol=1e-12)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs],0.,atol=1e-12)
    supply: float = next(values[variable.uid] for variable in block.algebraic_vars if variable.name == 'SupplyPu_filtered')
    assert len(block.state_vars) == 2+int(kir>0)+int(kim>0)+int(ta>0)
    for frequency in (.02,.4,2.):
        s: complex = 2j*np.pi*frequency
        outer: complex = 20.+kir/s
        inner: complex = 1.+kim/s
        firing: complex = 1./(1.+ta*s)
        feedback: complex = 1./(1.+.1*s)
        expected: complex = -supply*outer*inner*firing/((1.+.02*s)*(1.+inner*firing*feedback))
        assert linearized_response(block,values,1.,frequency) == pytest.approx(expected,rel=3e-7,abs=1e-7)


@pytest.mark.parametrize('minimum,maximum',((1,1),(1,2),(2,3),(3,1),(3,2),(2,2)))
@pytest.mark.parametrize('supplement',(CompoundSupplementLocation.ERROR_SUM,CompoundSupplementLocation.AFTER_MINIMUM_GATE))
def test_filtered_compound_pi_gate_equilibrium(minimum: int, maximum: int, supplement: CompoundSupplementLocation) -> None:
    """Absent additive controllers and equilibrium take-over bypasses preserve all memories.

    :param minimum: Minimum-excitation insertion point.
    :param maximum: Maximum-excitation insertion point.
    :param supplement: Supplement insertion relative to the input minimum gate.
    """
    block: Block = build_st4c_template(VarFactory(),'filtered',FilteredCompoundPiParameters(
        minimum_location=ExcitationLimiterLocation(minimum),maximum_location=ExcitationLimiterLocation(maximum),
        supplement_location=supplement)).block
    values: dict[int,float] = initialized_values(block)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.algebraic_eqs],0.,atol=1e-12)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs],0.,atol=1e-12)
    assert values[block.out_vars[0].uid] == 1.


def test_filtered_compound_feedback_ceiling_is_external() -> None:
    """Feedback clipping leaves its memory able to recover without changing the firing state limit."""
    block: Block = build_st4c_template(VarFactory(),'filtered',FilteredCompoundPiParameters(vgmax=.1)).block
    values: dict[int,float] = initialized_values(block)
    states: np.ndarray = np.asarray([values[variable.uid] for variable in block.state_vars])
    feedback_index: int = next(index for index,variable in enumerate(block.state_vars) if variable.name == 'FeedbackMemoryPu_filtered')
    states[feedback_index] = 2.
    derivative: np.ndarray
    field: float
    derivative,field = evaluate_controller(block,values,states,1.)
    firing: float = next(values[variable.uid] for variable in block.state_vars if variable.name == 'FiringPu_filtered')
    assert derivative[feedback_index] == pytest.approx((firing-2.)/.1)
    assert field == pytest.approx(1.)


def test_filtered_compound_pi_native_persistence() -> None:
    """New physical signal ports and differential memories survive native persistence."""
    block: Block = build_st4c_template(VarFactory(),'filtered').block
    payload: dict[str,object] = json.loads(json.dumps(block.to_dict()))
    assert json.loads(json.dumps(Block.parse(payload).to_dict())) == payload


@pytest.mark.parametrize('minimum,maximum',((1,1),(1,2),(2,3),(3,1),(3,2),(2,2)))
@pytest.mark.parametrize('supplement',(CompoundSupplementLocation.ERROR_SUM,CompoundSupplementLocation.AFTER_MINIMUM_GATE))
def test_filtered_compound_gate_order_under_disturbance(minimum: int, maximum: int, supplement: CompoundSupplementLocation) -> None:
    """High/low take-over gates act at the selected physical stages, with supplement between input gates when selected.

    :param minimum: Minimum-excitation insertion point.
    :param maximum: Maximum-excitation insertion point.
    :param supplement: Supplement placement relative to the input minimum gate.
    """
    block: Block = build_st4c_template(VarFactory(),'filtered',FilteredCompoundPiParameters(
        kpr=2.,kir=0.,kim=0.,ta=0.,minimum_location=ExcitationLimiterLocation(minimum),
        maximum_location=ExcitationLimiterLocation(maximum),supplement_location=supplement)).block
    values: dict[int,float] = initialized_values(block)
    values[block.in_vars[1].uid] = 1.1
    values[block.in_vars[2].uid] = .05
    values[block.in_vars[8].uid] = .3
    values[block.in_vars[9].uid] = .2
    error: float = .1+(.05 if supplement == CompoundSupplementLocation.ERROR_SUM else 0.)
    if minimum == 1:
        error += .3
    elif minimum == 2:
        error = max(error,.3)
    else:
        pass
    # An additive maximum signal enters before the minimum take-over gate.
    if maximum == 1:
        error = max(.1+.2+(.05 if supplement == CompoundSupplementLocation.ERROR_SUM else 0.),.3) if minimum == 2 else error+.2
    else:
        pass
    if supplement == CompoundSupplementLocation.AFTER_MINIMUM_GATE:
        error += .05
    else:
        pass
    if maximum == 2:
        error = min(error,.2)
    else:
        pass
    feedback: float = next(values[variable.uid] for variable in block.algebraic_vars if variable.name == 'FeedbackPu_filtered')
    bridge: float = float(np.clip(2.*error-feedback,-5.,5.))
    if minimum == 3:
        bridge = max(bridge,.3)
    else:
        pass
    if maximum == 3:
        bridge = min(bridge,.2)
    else:
        pass
    supply: float = next(values[variable.uid] for variable in block.algebraic_vars if variable.name == 'SupplyPu_filtered')
    states: np.ndarray = np.asarray([values[variable.uid] for variable in block.state_vars])
    derivative: np.ndarray
    field: float
    derivative,field = evaluate_controller(block,values,states,1.)
    assert field == pytest.approx(supply*float(np.clip(bridge,-5.,5.)))


def test_filtered_compound_independent_integral_stops() -> None:
    """Each PI suppresses its own outward motion and permits inward recovery."""
    block: Block = build_st4c_template(VarFactory(),'filtered').block
    values: dict[int,float] = initialized_values(block)
    states: np.ndarray = np.asarray([values[variable.uid] for variable in block.state_vars])
    outer: int = next(index for index,variable in enumerate(block.state_vars) if variable.name == 'VoltageIntegralPu_filtered')
    inner: int = next(index for index,variable in enumerate(block.state_vars) if variable.name == 'FieldIntegralPu_filtered')
    states[outer] = 10.
    states[inner] = 10.
    values[block.in_vars[1].uid] = 2.
    derivative: np.ndarray
    field: float
    derivative,field = evaluate_controller(block,values,states,1.)
    assert derivative[outer] == 0. and derivative[inner] == 0.
    values[block.in_vars[1].uid] = .9
    derivative,field = evaluate_controller(block,values,states,1.)
    assert derivative[outer] < 0.
    # Recover the inner integral independently after its upstream demand falls.
    states[outer] = 0.
    values[block.in_vars[1].uid] = .99
    derivative,field = evaluate_controller(block,values,states,1.)
    assert derivative[inner] < 0.
