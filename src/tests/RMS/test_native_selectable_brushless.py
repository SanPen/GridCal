# SPDX-License-Identifier: MPL-2.0
"""Brushless selected-gate topology, initialization and field-current-stop recovery."""
from __future__ import annotations

import numpy as np
import pytest
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.dc_exciter import RotatingLimiterLocation
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.ac1c import build_ac1c_template
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.ac2c import build_ac2c_template
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.ac5c import build_ac5c_template
from VeraGridEngine.Templates.Rms.genrou_exc_gov_rms_template import set_rms_model_parameter
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var, Expr
from VeraGridEngine.Utils.Symbolic.explicit_initialization_symbolic import collect_direct_algebraic_initializers
from tests.RMS.test_native_turbine_governors import initialized_values, evaluate_controller, linearized_response


@pytest.mark.parametrize('inner',(False,True))
@pytest.mark.parametrize('minimum',tuple(RotatingLimiterLocation))
@pytest.mark.parametrize('maximum',tuple(RotatingLimiterLocation))
def test_selectable_brushless_native_equilibrium(inner: bool, minimum: RotatingLimiterLocation, maximum: RotatingLimiterLocation) -> None:
    """All native gate selections initialize five physical states and a square algebraic graph.

    :param inner: Include the high-response inner field-current loop.
    :param minimum: Minimum limiter insertion.
    :param maximum: Maximum limiter insertion.
    """
    block: Block = (build_ac2c_template(VarFactory(),'brushless',minimum,maximum) if inner else build_ac1c_template(VarFactory(),'brushless',minimum,maximum)).block
    assignments: dict[Var,Expr] = dict()
    collect_direct_algebraic_initializers(block,assignments)
    for variable,expression in assignments.items():
        if variable not in block.init_eqs:
            block.init_eqs[variable] = expression
        else:
            pass
    values: dict[int,float] = initialized_values(block)
    assert len(block.state_vars) == 5 and len(block.in_vars) == 6 and len(block.out_vars) == 3
    assert len(block.algebraic_vars) == len(block.algebraic_eqs)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs],0.,atol=1e-10)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.algebraic_eqs],0.,atol=1e-10)


@pytest.mark.parametrize('inner',(False,True))
def test_selectable_brushless_field_current_stop(inner: bool) -> None:
    """A moving field-current ceiling blocks outward field motion and permits inward recovery.

    :param inner: Include the proportional inner loop.
    """
    block: Block = (build_ac2c_template(VarFactory(),'brushless') if inner else build_ac1c_template(VarFactory(),'brushless')).block
    variables: dict[str,Var] = dict((variable.name,variable) for variable in block.event_dict)
    ceiling: Var = variables['VFEMAX_brushless']
    block.event_dict[ceiling] = Const(.1)
    assignments: dict[Var,Expr] = dict()
    collect_direct_algebraic_initializers(block,assignments)
    for variable,expression in assignments.items():
        if variable not in block.init_eqs:
            block.init_eqs[variable] = expression
        else:
            pass
    values: dict[int,float] = initialized_values(block)
    states: np.ndarray = np.asarray([values[variable.uid] for variable in block.state_vars])
    field_index: int = next(index for index,variable in enumerate(block.state_vars) if variable.name == 'avr.integrator.y_brushless')
    amplifier_index: int = next(index for index,variable in enumerate(block.state_vars) if variable.name == 'avr.limitedFirstOrder.I.y_brushless')
    states[amplifier_index] = 5.
    derivative: np.ndarray
    output: float
    derivative,output = evaluate_controller(block,values,states,1.)
    assert derivative[field_index] == 0.
    states[amplifier_index] = -5.
    derivative,output = evaluate_controller(block,values,states,1.)
    assert derivative[field_index] < 0.


@pytest.mark.parametrize('frequency',(.02,.4,2.))
@pytest.mark.parametrize('shaped,inner',((False,False),(False,True),(True,False)))
def test_brushless_independent_feedback_transfer(frequency: float, shaped: bool, inner: bool) -> None:
    """Forward phase compensation and shaped feedback produce distinct independently derived loops.

    :param frequency: Perturbation frequency in hertz.
    :param shaped: Place phase compensation in the feedback path.
    :param inner: Include the proportional inner field-current feedback loop.
    """
    vf: VarFactory = VarFactory()
    block: Block = (build_ac5c_template(vf,'transfer') if shaped else (build_ac2c_template(vf,'transfer') if inner else build_ac1c_template(vf,'transfer'))).block
    for parameter,value in (('avr.Ka',4.),('avr.Ke',2.),('avr.Kc',0.),('avr.Kd',0.),
                            ('avr.tA',.07),('avr.tB',.2),('avr.tC',.1),('avr.tR',.03),
                            ('avr.tF',.8),('avr.Kf',.06),('avr.Sq',0.),('avr.Bsq',0.),('avr.VExcThresholdPu',0.)):
        set_rms_model_parameter(block,parameter+'_transfer',value,vf)
    if inner:
        set_rms_model_parameter(block,'KB_transfer',10.,vf)
        set_rms_model_parameter(block,'KH_transfer',.2,vf)
    else:
        pass
    assignments: dict[Var,Expr] = dict()
    collect_direct_algebraic_initializers(block,assignments)
    for variable,expression in assignments.items():
        if variable not in block.init_eqs:
            block.init_eqs[variable] = expression
        else:
            pass
    values: dict[int,float] = initialized_values(block)
    np.testing.assert_allclose([equation.eval_uid(values) for equation in block.state_eqs],0.,atol=1e-10)
    block.in_vars[0],block.in_vars[3] = block.in_vars[3],block.in_vars[0]
    s: complex = 2j*np.pi*frequency
    phase: complex = (1.+.1*s)/(1.+.2*s)
    forward: complex = 40./((1.+.07*s)*(6.+.5*s)) if inner else 4./((1.+.07*s)*(2.+.5*s))
    feedback: complex = 2.*.06*s/(1.+.8*s)
    if shaped:
        feedback = feedback*phase
    else:
        forward = forward*phase
    expected: complex = -forward/((1.+.03*s)*(1.+forward*feedback))
    assert linearized_response(block,values,1.,frequency) == pytest.approx(expected,rel=3e-7,abs=1e-8)
